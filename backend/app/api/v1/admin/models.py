"""租户模型目录管理路由；Provider 凭证只接收外部密钥管理器引用。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict, valid_redirect_uri
from app.core.config import get_settings
from app.core.security import platform_admin
from app.db.session import get_db_session
from app.models.identity import Tenant, User
from app.models.model_catalog import ModelCatalog
from app.schemas.models import ModelCatalogCreate, ModelCatalogStatusUpdate, ModelCatalogUpdate

router = APIRouter(prefix="/models", tags=["模型目录"])


@router.get("")
def list_models(tenant_id: UUID | None = None, db: Session = Depends(get_db_session)) -> list[dict]:
    """列出模型配置摘要；凭证引用只转换为是否已配置，不向控制台回传。"""
    statement = select(ModelCatalog).order_by(ModelCatalog.created_at.desc()).limit(500)
    if tenant_id:
        statement = statement.where(ModelCatalog.tenant_id == tenant_id)
    enforcement_enabled = get_settings().model_quota_enforcement_enabled
    return [{
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
        "quota_status": (
            "unlimited" if model.rpm_limit is None and model.tpm_limit is None
            else "enforced" if enforcement_enabled else "configured_only"
        ),
        "output_cost_per_million": float(model.output_cost_per_million)
        if model.output_cost_per_million is not None else None,
        "status": model.status,
        "created_at": model.created_at,
    } for model in db.scalars(statement).all()]


@router.post("", status_code=201)
def create_model(
    body: ModelCatalogCreate,
    request: Request,
    actor: User = Depends(platform_admin),
    db: Session = Depends(get_db_session),
) -> dict:
    """目录只接收 Secret Manager 引用；不能把 Provider API Key 放入业务表。"""
    if not db.get(Tenant, body.tenant_id):
        raise HTTPException(404, "租户不存在")
    if body.endpoint_url and not valid_redirect_uri(body.endpoint_url):
        raise HTTPException(422, "模型端点必须为 HTTPS 或本地开发地址")
    if body.credential_ref and not body.credential_ref.startswith(("vault://", "secret://")):
        raise HTTPException(422, "凭证只接受 vault:// 或 secret:// 外部密钥引用")

    row = ModelCatalog(**body.model_dump())
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
    actor: User = Depends(platform_admin),
    db: Session = Depends(get_db_session),
) -> dict:
    """更新模型资料与显式 RPM/TPM 策略；限额执行仍由服务级开关控制。"""
    row = db.get(ModelCatalog, model_id)
    if not row:
        raise HTTPException(404, "模型不存在")

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
    actor: User = Depends(platform_admin),
    db: Session = Depends(get_db_session),
) -> dict:
    """行锁保护模型状态转换，过期页面不能覆盖新状态；审计与更新同事务。"""
    row = db.scalar(select(ModelCatalog).where(ModelCatalog.id == model_id).with_for_update())
    if not row:
        raise HTTPException(404, "模型不存在")
    if row.status != body.expected_status:
        raise HTTPException(409, "模型状态已被其他管理员修改，请刷新后重试")
    if row.status == body.status:
        return {"id": str(row.id), "status": row.status}

    row.status = body.status
    audit(db, actor, request, "model.status.change", "model", str(row.id),
          {"tenant_id": str(row.tenant_id), "from_status": body.expected_status, "to_status": body.status})
    commit_or_conflict(db)
    return {"id": str(row.id), "status": row.status}
