"""租户生命周期管理路由。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import Tenant, TenantMembership, User
from app.models.oidc import OAuthRefreshToken
from app.schemas.auth import TenantCreate, TenantKindUpdate
from app.db.seed_greenfield import PLATFORM_TENANT_SLUG
from app.services.rbac_guards import ensure_roles
from app.services.role_provisioning import L1_ROLE_KEY, provision_tenant_admin_role

router = APIRouter(tags=["租户管理"])

@router.get("/tenants")
def list_tenants(
    q: str | None = Query(default=None, max_length=100),
    kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """列出租户及成员/应用计数；仅 L1 平台管理员可见全局租户目录。

    q/kind/status 为可选服务端过滤（管理台已有前端本地过滤，参数供深链与未来分页使用）。
    """
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.tenant.read）")
    if kind not in (None, "organization", "consumer"):
        raise HTTPException(422, "kind 仅支持 organization 或 consumer")
    if status not in (None, "active", "disabled"):
        raise HTTPException(422, "status 仅支持 active 或 disabled")
    stmt = select(Tenant).order_by(Tenant.created_at.desc()).limit(500)
    search = q.strip()[:100] if q else ""
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Tenant.name.ilike(pattern) | Tenant.slug.ilike(pattern))
    if kind:
        stmt = stmt.where(Tenant.kind == kind)
    if status:
        stmt = stmt.where(Tenant.status == status)
    tenants = db.scalars(stmt).all()
    # 应用计数一次性聚合（group by tenant_id），避免逐租户 N+1
    app_counts = dict(db.execute(
        select(Application.tenant_id, func.count()).group_by(Application.tenant_id),
    ).all())
    return [{"id": str(x.id), "name": x.name, "slug": x.slug, "kind": x.kind, "status": x.status,
             "member_count": db.scalar(select(func.count()).select_from(TenantMembership).where(TenantMembership.tenant_id == x.id)) or 0,
             "application_count": int(app_counts.get(x.id, 0))}
            for x in tenants]


@router.post("/tenants", status_code=201)
def create_tenant(body: TenantCreate, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """创建租户并预置 L3 管理角色模板；slug 唯一冲突统一转 409。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.tenant.manage）")
    row = Tenant(name=body.name, slug=body.slug, kind=body.kind)
    db.add(row); flush_or_conflict(db)
    # 绿场规则：租户开通即预置 L3 tenant.admin 角色模板（幂等）。
    provision_tenant_admin_role(db, row.id)
    audit(db, actor, request, "tenant.create", "tenant", str(row.id), {"slug": row.slug, "kind": row.kind}); commit_or_conflict(db)
    return {"id": str(row.id), "name": row.name, "slug": row.slug, "kind": row.kind, "status": row.status}


@router.patch("/tenants/{tenant_id}/kind")
def set_tenant_kind(tenant_id: UUID, body: TenantKindUpdate, request: Request,
                    actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """切换租户注册受众前必须先关闭其所有应用的公开注册，形成明确的二次确认。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.tenant.manage）")
    row = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if not row:
        raise HTTPException(404, "租户不存在")
    # 平台引导租户的类型由种子定义（organization）：切成 consumer 会让它混入 ToC 消费目录，
    # 造成「平台租户与业务租户混淆」；保持固定，不让运行期人工切换。
    if row.slug == PLATFORM_TENANT_SLUG:
        raise HTTPException(422, "平台引导租户的类型由系统种子定义，不允许切换")
    if row.kind != body.expected_kind:
        raise HTTPException(409, "租户类型已被其他管理员修改，请刷新后重试")
    if row.kind == body.kind:
        return {"id": str(row.id), "kind": row.kind}
    open_application = db.scalar(select(Application.id).where(
        Application.tenant_id == row.id,
        Application.registration_policy == "open",
    ).limit(1))
    if open_application:
        raise HTTPException(409, "请先关闭该租户下所有应用的自助注册，再切换租户类型")
    old_kind = row.kind
    row.kind = body.kind
    audit(db, actor, request, "tenant.kind.change", "tenant", str(row.id),
          {"from": old_kind, "to": row.kind})
    commit_or_conflict(db)
    return {"id": str(row.id), "kind": row.kind}


@router.patch("/tenants/{tenant_id}/status")
def set_tenant_status(tenant_id: UUID, status: str, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """启停租户；停用时撤销旗下应用的 OAuth 刷新令牌，阻断旧会话续期。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.tenant.manage）")
    if status not in {"active", "disabled"}: raise HTTPException(422, "状态仅支持 active 或 disabled")
    row = db.get(Tenant, tenant_id)
    if not row: raise HTTPException(404, "租户不存在")
    # 平台引导租户承载系统应用与 L1 角色/引导超管宿主，停用会锁死整个平台管理面；
    # 恢复为 active 走幂等放行，只在 disabled 分支拦截。
    if status == "disabled" and row.slug == PLATFORM_TENANT_SLUG:
        raise HTTPException(422, "平台引导租户承载系统应用与 L1 宿主，不允许停用")
    if status == "disabled":
        # 停用租户时撤销旗下应用的 OAuth 刷新令牌，避免旧会话继续续期。
        db.execute(update(OAuthRefreshToken).where(
            OAuthRefreshToken.application_id.in_(select(Application.id).where(Application.tenant_id == row.id)),
            OAuthRefreshToken.revoked_at.is_(None),
        ).values(revoked_at=datetime.now(timezone.utc)))
    row.status = status; audit(db, actor, request, "tenant.status.change", "tenant", str(row.id), {"status": status}); commit_or_conflict(db)
    return {"id": str(row.id), "status": row.status}


@router.delete("/tenants/{tenant_id}", status_code=204)
def delete_tenant(tenant_id: UUID, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> None:
    """删除租户：级联清除成员/角色/应用/邀请/用户组/组织/模型目录；用量账目存在时阻塞。

    平台引导租户（platform）是 L1 角色与引导超管的宿主，永久禁止删除。
    """
    from app.models.model_catalog import ModelUsageEvent, ModelUsageReservation

    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.tenant.manage）")
    row = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if not row:
        raise HTTPException(404, "租户不存在")
    if row.slug == PLATFORM_TENANT_SLUG:
        raise HTTPException(422, "平台引导租户为种子保护租户，不允许删除")
    # 用量账目（事件/预留）对租户为 RESTRICT：先给出可操作的 409 文案而非暴露数据库约束。
    usage_exists = db.scalar(select(ModelUsageEvent.id).where(ModelUsageEvent.tenant_id == row.id).limit(1))
    reservation_exists = db.scalar(select(ModelUsageReservation.id).where(ModelUsageReservation.tenant_id == row.id).limit(1))
    if usage_exists or reservation_exists:
        raise HTTPException(409, "该租户存在模型用量账目，无法删除；请先归档用量数据")
    # 成员/角色/应用等随外键级联删除；AuditEvent.tenant_id 为 SET NULL，历史审计保留但脱钩租户。
    audit(db, actor, request, "tenant.delete", "tenant", str(tenant_id), {"slug": row.slug, "name": row.name})
    db.delete(row)
    commit_or_conflict(db)
