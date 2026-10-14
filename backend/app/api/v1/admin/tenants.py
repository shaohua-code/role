"""租户生命周期管理路由。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import platform_admin
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import Tenant, TenantMembership, User
from app.models.oidc import OAuthRefreshToken
from app.schemas.auth import TenantCreate, TenantKindUpdate

router = APIRouter(tags=["租户管理"])

@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db_session)) -> list[dict]:
    return [{"id": str(x.id), "name": x.name, "slug": x.slug, "kind": x.kind, "status": x.status,
             "member_count": db.scalar(select(func.count()).select_from(TenantMembership).where(TenantMembership.tenant_id == x.id)) or 0}
            for x in db.scalars(select(Tenant).order_by(Tenant.created_at.desc()).limit(500)).all()]


@router.post("/tenants", status_code=201)
def create_tenant(body: TenantCreate, request: Request, actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    row = Tenant(name=body.name, slug=body.slug, kind=body.kind)
    db.add(row); flush_or_conflict(db); audit(db, actor, request, "tenant.create", "tenant", str(row.id), {"slug": row.slug, "kind": row.kind}); commit_or_conflict(db)
    return {"id": str(row.id), "name": row.name, "slug": row.slug, "kind": row.kind, "status": row.status}


@router.patch("/tenants/{tenant_id}/kind")
def set_tenant_kind(tenant_id: UUID, body: TenantKindUpdate, request: Request,
                    actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """切换租户注册受众前必须先关闭其所有应用的公开注册，形成明确的二次确认。"""
    row = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if not row:
        raise HTTPException(404, "租户不存在")
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
def set_tenant_status(tenant_id: UUID, status: str, request: Request, actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    if status not in {"active", "disabled"}: raise HTTPException(422, "状态仅支持 active 或 disabled")
    row = db.get(Tenant, tenant_id)
    if not row: raise HTTPException(404, "租户不存在")
    if status == "disabled":
        # 停用租户时撤销旗下应用的 OAuth 刷新令牌，避免旧会话继续续期。
        db.execute(update(OAuthRefreshToken).where(
            OAuthRefreshToken.application_id.in_(select(Application.id).where(Application.tenant_id == row.id)),
            OAuthRefreshToken.revoked_at.is_(None),
        ).values(revoked_at=datetime.now(timezone.utc)))
    row.status = status; audit(db, actor, request, "tenant.status.change", "tenant", str(row.id), {"status": status}); commit_or_conflict(db)
    return {"id": str(row.id), "status": row.status}
