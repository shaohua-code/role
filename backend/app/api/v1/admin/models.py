"""平台模型目录与三级分发路由；Provider 凭证只接收外部密钥管理器引用。

目录行统一归属平台租户（slug=platform）：超管维护目录并下发租户；
租户管理员在应用工作台把本租户收到的模型下发 / 回收给应用（见
tenant_admin/application_models.py）。可见性唯一口径见 services/model_distribution.py。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict, valid_redirect_uri
from app.core.config import get_settings
from app.core.security import current_user
from app.db.session import get_db_session
from app.models.identity import Tenant, User
from app.models.model_catalog import ModelApplicationGrant, ModelCatalog, ModelTenantGrant
from app.schemas.models import (
    ModelCatalogCreate,
    ModelCatalogStatusUpdate,
    ModelCatalogUpdate,
    ModelTenantGrantCreate,
)
from app.services.model_distribution import ModelDistribution
from app.services.permission_kinds import ROLE_SCOPE_SUPER
from app.services.rbac_guards import ActorVisibility, PermissionEnforcer

router = APIRouter(prefix="/models", tags=["模型目录"])


def _serialize_model(
    model: ModelCatalog,
    *,
    tenant_grant_count: int | None = None,
    application_grant_count: int | None = None,
) -> dict:
    """目录行摘要；凭证引用只转换为是否已配置，不向控制台回传。"""
    enforcement_enabled = get_settings().model_quota_enforcement_enabled
    item = {
        "id": str(model.id),
        "tenant_id": str(model.tenant_id),
        "key": model.key,
        "provider": model.provider,
        "model_name": model.model_name,
        "display_name": model.display_name,
        "endpoint_url": model.endpoint_url,
        "credential_configured": bool(model.credential_ref),
        "capabilities": model.capabilities,
        "rpm_limit": model.rpm_limit,
        "tpm_limit": model.tpm_limit,
        "input_cost_per_million": float(model.input_cost_per_million)
        if model.input_cost_per_million is not None else None,
        "output_cost_per_million": float(model.output_cost_per_million)
        if model.output_cost_per_million is not None else None,
        "quota_status": (
            "unlimited" if model.rpm_limit is None and model.tpm_limit is None
            else "enforced" if enforcement_enabled else "configured_only"
        ),
        "status": model.status,
        "created_at": model.created_at,
    }
    if tenant_grant_count is not None:
        item["tenant_grant_count"] = tenant_grant_count
    if application_grant_count is not None:
        item["application_grant_count"] = application_grant_count
    return item


def _ensure_model_write(actor: User, db: Session) -> None:
    """模型治理写 = 超管：范围闸门 + button.models.manage 节点双重收口。"""
    PermissionEnforcer.ensure_scope(actor, db, ROLE_SCOPE_SUPER, detail="模型治理写操作需要超管范围")
    PermissionEnforcer.ensure_codes(actor, db, "button.models.manage", detail="缺少管理权限：button.models.manage")


def _get_platform_model(db: Session, model_id: UUID) -> ModelCatalog:
    """按 ID 加载平台目录行；非平台租户目录行与不存在不可区分（404），守住目录不变式。

    「所有目录行归属 platform 租户」不能只由创建路径保证：按 ID 的编辑 / 状态 /
    删除 / 下发路径必须统一复用本校验，防止存量异常行经 API 被改写或传播。
    """
    model = db.get(ModelCatalog, model_id)
    if not model or model.tenant_id != ModelDistribution.get_platform_tenant(db).id:
        raise HTTPException(404, "模型不存在")
    return model


def _get_platform_model_for_update(db: Session, model_id: UUID) -> ModelCatalog | None:
    """行锁版平台目录行加载（状态变更 / 删除用）；非平台目录行返回 None 走 404。"""
    return db.scalar(select(ModelCatalog).where(
        ModelCatalog.id == model_id,
        ModelCatalog.tenant_id == ModelDistribution.get_platform_tenant(db).id,
    ).with_for_update())


@router.get("")
def list_models(actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> list[dict]:
    """按操作者范围返回可见模型（三级可见性唯一口径）。

    超管：平台目录全集 + 已下发租户计数；租户级：本租户收到的模型（只读）；
    应用级：本应用收到的模型（只读）。数据边界由 ActorVisibility 收口。
    """
    PermissionEnforcer.ensure_codes(actor, db, "menu.models", detail="缺少管理权限：menu.models")
    platform_tenant = ModelDistribution.get_platform_tenant(db)
    tenant_scope = ActorVisibility.list_actor_management_tenant_ids(actor, db)

    if tenant_scope is None:
        # 超管：平台目录全集 + active 租户下发计数。
        rows = db.scalars(select(ModelCatalog).where(
            ModelCatalog.tenant_id == platform_tenant.id,
        ).order_by(ModelCatalog.created_at.desc(), ModelCatalog.id).limit(500)).all()
        counts: dict[UUID, int] = {}
        if rows:
            counts = dict(db.execute(
                select(ModelTenantGrant.model_id, func.count()).where(
                    ModelTenantGrant.model_id.in_([row.id for row in rows]),
                    ModelTenantGrant.status == "active",
                ).group_by(ModelTenantGrant.model_id),
            ).all())
        return [_serialize_model(row, tenant_grant_count=counts.get(row.id, 0)) for row in rows]

    # 租户级：本操作者全部租户的 active 租户下发模型（含活跃应用下发计数，供治理页只读展示）。
    if tenant_scope:
        rows = db.scalars(select(ModelCatalog).join(
            ModelTenantGrant, ModelTenantGrant.model_id == ModelCatalog.id,
        ).where(
            ModelCatalog.tenant_id == platform_tenant.id,
            ModelCatalog.status == "active",
            ModelTenantGrant.tenant_id.in_(tenant_scope),
            ModelTenantGrant.status == "active",
        ).order_by(ModelCatalog.created_at.desc(), ModelCatalog.id).limit(500)).all()
        counts = dict(db.execute(
            select(ModelApplicationGrant.model_id, func.count()).where(
                ModelApplicationGrant.model_id.in_([row.id for row in rows]),
                ModelApplicationGrant.tenant_id.in_(tenant_scope),
                ModelApplicationGrant.status == "active",
            ).group_by(ModelApplicationGrant.model_id),
        ).all()) if rows else {}
        return [_serialize_model(row, application_grant_count=counts.get(row.id, 0)) for row in rows]

    # 应用级：本操作者绑定应用的 active 应用下发模型（只读）。
    bound_apps = ActorVisibility.list_actor_bound_application_ids(actor, db)
    if not bound_apps:
        return []
    rows = db.scalars(select(ModelCatalog).join(
        ModelApplicationGrant, ModelApplicationGrant.model_id == ModelCatalog.id,
    ).where(
        ModelCatalog.tenant_id == platform_tenant.id,
        ModelCatalog.status == "active",
        ModelApplicationGrant.application_id.in_(bound_apps),
        ModelApplicationGrant.status == "active",
    ).order_by(ModelCatalog.created_at.desc(), ModelCatalog.id).limit(500)).all()
    return [_serialize_model(row) for row in rows]


@router.post("", status_code=201)
def create_model(
    body: ModelCatalogCreate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """目录只接收 Secret Manager 引用；不能把 Provider API Key 放入业务表。"""
    _ensure_model_write(actor, db)
    # 平台目录行统一归属平台租户；tenant_id 不再来自请求体。
    platform_tenant = ModelDistribution.get_platform_tenant(db)
    if body.endpoint_url and not valid_redirect_uri(body.endpoint_url):
        raise HTTPException(422, "模型端点必须为 HTTPS 或本地开发地址")
    if body.credential_ref and not body.credential_ref.startswith(("vault://", "secret://")):
        raise HTTPException(422, "凭证只接受 vault:// 或 secret:// 外部密钥引用")

    row = ModelCatalog(**body.model_dump(), tenant_id=platform_tenant.id)
    db.add(row)
    flush_or_conflict(db)
    audit(db, actor, request, "model.create", "model", str(row.id),
          {"tenant_id": str(row.tenant_id), "key": row.key})
    commit_or_conflict(db)
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "key": row.key,
        "provider": row.provider,
        "model_name": row.model_name,
        "status": row.status,
    }


@router.patch("/{model_id}")
def update_model(
    model_id: UUID,
    body: ModelCatalogUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """更新模型资料与显式 RPM/TPM 策略；限额执行仍由服务级开关控制。"""
    row = _get_platform_model(db, model_id)
    _ensure_model_write(actor, db)

    # 未提交字段保持不变；显式 null 可清除可选值或限额。
    # Secret Manager 引用不会进入审计详情或 API 响应，限额变更只审计字段名。
    changes = body.model_dump(exclude_unset=True)
    if "endpoint_url" in changes and changes["endpoint_url"] and not valid_redirect_uri(changes["endpoint_url"]):
        raise HTTPException(422, "模型端点必须为 HTTPS 或本地开发地址")
    credential_ref = changes.get("credential_ref")
    if credential_ref and not credential_ref.startswith(("vault://", "secret://")):
        raise HTTPException(422, "凭证只接受 vault:// 或 secret:// 外部密钥引用")

    for field, value in changes.items():
        setattr(row, field, value)
    audit(db, actor, request, "model.update", "model", str(row.id), {
        "tenant_id": str(row.tenant_id),
        "updated_fields": sorted(changes),
        "credential_ref_configured": bool(row.credential_ref),
    })
    commit_or_conflict(db)
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "updated_fields": sorted(changes),
        "credential_configured": bool(row.credential_ref),
        "status": row.status,
    }


@router.patch("/{model_id}/status")
def set_model_status(
    model_id: UUID,
    body: ModelCatalogStatusUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """行锁保护模型状态转换，过期页面不能覆盖新状态；停用 = 全链路立即不可见。"""
    row = _get_platform_model_for_update(db, model_id)
    if not row:
        raise HTTPException(404, "模型不存在")
    _ensure_model_write(actor, db)
    if row.status != body.expected_status:
        raise HTTPException(409, "模型状态已被其他管理员修改，请刷新后重试")
    if row.status == body.status:
        return {"id": str(row.id), "status": row.status}

    row.status = body.status
    audit(db, actor, request, "model.status.change", "model", str(row.id),
          {"tenant_id": str(row.tenant_id), "from_status": body.expected_status, "to_status": body.status})
    commit_or_conflict(db)
    return {"id": str(row.id), "status": row.status}


@router.delete("/{model_id}", status_code=204)
def delete_model(
    model_id: UUID,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """删除平台模型目录项；存在用量事件/预留（RESTRICT）时阻塞，提示走停用下线。"""
    from app.models.model_catalog import ModelUsageEvent, ModelUsageReservation

    row = _get_platform_model_for_update(db, model_id)
    if not row:
        raise HTTPException(404, "模型不存在")
    _ensure_model_write(actor, db)
    usage_exists = db.scalar(select(ModelUsageEvent.id).where(ModelUsageEvent.model_id == row.id).limit(1))
    reservation_exists = db.scalar(select(ModelUsageReservation.id).where(ModelUsageReservation.model_id == row.id).limit(1))
    if usage_exists or reservation_exists:
        raise HTTPException(409, "该模型存在用量账目，无法删除；如需下线请改用停用")
    audit(db, actor, request, "model.delete", "model", str(row.id),
          {"tenant_id": str(row.tenant_id), "key": row.key, "display_name": row.display_name})
    # 下发关系随目录行级联删除（ON DELETE CASCADE）；用量账目外的授权关系无保留价值。
    db.delete(row)
    commit_or_conflict(db)


# ── 平台 → 租户 下发 / 回收（超管）───────────────────────────────────────────


@router.get("/{model_id}/tenant-grants")
def list_model_tenant_grants(
    model_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """列出模型的租户下发关系；非超管只回传自己租户范围内的行（数据边界收口）。"""
    PermissionEnforcer.ensure_codes(actor, db, "menu.models", detail="缺少管理权限：menu.models")
    row = _get_platform_model(db, model_id)
    statement = (
        select(ModelTenantGrant, Tenant.name)
        .join(Tenant, Tenant.id == ModelTenantGrant.tenant_id)
        .where(ModelTenantGrant.model_id == row.id)
        .order_by(ModelTenantGrant.granted_at.desc())
    )
    tenant_scope = ActorVisibility.list_actor_management_tenant_ids(actor, db)
    if tenant_scope is not None:
        if not tenant_scope:
            return []
        statement = statement.where(ModelTenantGrant.tenant_id.in_(tenant_scope))
    return [{
        "model_id": str(grant.model_id),
        "tenant_id": str(grant.tenant_id),
        "tenant_name": tenant_name,
        "status": grant.status,
        "granted_at": grant.granted_at,
        "revoked_at": grant.revoked_at,
    } for grant, tenant_name in db.execute(statement).all()]


@router.post("/{model_id}/tenant-grants", status_code=201)
def grant_model_to_tenant(
    model_id: UUID,
    body: ModelTenantGrantCreate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """把平台模型下发给租户；幂等：重复下发不产生重复行，回收后重发即复活。"""
    _ensure_model_write(actor, db)
    row = _get_platform_model(db, model_id)
    if row.status != "active":
        raise HTTPException(422, "已停用的模型不能下发；请先启用模型")
    created = ModelDistribution.grant_to_tenant(db, row.id, body.tenant_id, actor.id)
    audit(db, actor, request, "model.distribute.tenant", "model", str(row.id),
          {"tenant_id": str(body.tenant_id), "model_key": row.key, "created": created})
    commit_or_conflict(db)
    return {"model_id": str(row.id), "tenant_id": str(body.tenant_id),
            "status": "active", "created": created}


@router.delete("/{model_id}/tenant-grants/{tenant_id}")
def revoke_model_from_tenant(
    model_id: UUID,
    tenant_id: UUID,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """回收租户下发（软失效），并级联软失效该租户全部应用下发；行不存在时 404。"""
    _ensure_model_write(actor, db)
    row = _get_platform_model(db, model_id)
    if not db.get(Tenant, tenant_id):
        raise HTTPException(404, "租户不存在")
    revoked, cascaded = ModelDistribution.revoke_from_tenant(db, row.id, tenant_id)
    if not revoked:
        existing = db.scalar(select(ModelTenantGrant).where(
            ModelTenantGrant.model_id == row.id, ModelTenantGrant.tenant_id == tenant_id))
        if existing is None:
            raise HTTPException(404, "该模型尚未下发给此租户")
    audit(db, actor, request, "model.revoke.tenant", "model", str(row.id),
          {"tenant_id": str(tenant_id), "cascaded_applications": cascaded})
    commit_or_conflict(db)
    return {"model_id": str(row.id), "tenant_id": str(tenant_id),
            "status": "revoked", "cascaded_applications": cascaded}
