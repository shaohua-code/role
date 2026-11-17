"""应用工作台「模型」Tab：本租户收到的平台模型清单 + 对本应用的下发 / 回收。

可见性口径（产品需求 §6.4）：应用可见 = 平台目录 ∩ 租户下发 ∩ 应用下发。
读接口走应用工作台应用边界（应用管理员可读）；写接口需 `button.models.distribute`
（节点授权下限租户级，应用级拿不到——范围只能向下）。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict
from app.core.security import current_user
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import User
from app.models.model_catalog import ModelApplicationGrant, ModelCatalog
from app.schemas.models import ModelApplicationGrantCreate
from app.services.admin_authorization import AdminAccessGuard
from app.services.model_distribution import ModelDistribution
from app.services.rbac_guards import PermissionEnforcer

router = APIRouter(tags=["应用模型分发"])


def _authorized_application(application_id: UUID, actor: User, db: Session) -> Application:
    """先确认授权再查应用，避免应用 ID 成为跨租户枚举接口（与角色 Tab 同口径）。"""
    application = db.get(Application, application_id)
    if not application or not AdminAccessGuard.has_application_admin_access(
        actor,
        application.tenant_id,
        db,
        manage=False,
        application_id=application.id,
    ):
        raise HTTPException(404, "应用不存在")
    return application


def _serialize_received(model: ModelCatalog) -> dict:
    """租户收到模型的展示字段；不含端点与凭证引用（凭证不回读、业务自持）。"""
    return {
        "id": str(model.id),
        "key": model.key,
        "provider": model.provider,
        "model_name": model.model_name,
        "display_name": model.display_name,
        "capabilities": model.capabilities,
        "rpm_limit": model.rpm_limit,
        "tpm_limit": model.tpm_limit,
        "input_cost_per_million": float(model.input_cost_per_million)
        if model.input_cost_per_million is not None else None,
        "output_cost_per_million": float(model.output_cost_per_million)
        if model.output_cost_per_million is not None else None,
        "status": model.status,
    }


def _ensure_distribute_permission(actor: User, db: Session, tenant_id: UUID) -> None:
    """下发 / 回收 = button.models.distribute；节点 min_scope=tenant 已把应用级挡在门外。"""
    PermissionEnforcer.ensure_codes(
        actor, db, "button.models.distribute", tenant_id=tenant_id,
        detail="缺少管理权限：button.models.distribute",
    )


@router.get("/applications/{application_id}/models")
def list_application_models(
    application_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """返回本租户收到的模型清单与本应用已下发集合；未下发模型不出现即不可用。"""
    application = _authorized_application(application_id, actor, db)
    received = ModelDistribution.list_models_for_tenant(db, application.tenant_id)
    granted_ids = set(db.scalars(select(ModelApplicationGrant.model_id).where(
        ModelApplicationGrant.application_id == application.id,
        ModelApplicationGrant.status == "active",
    )).all())
    return {
        "application_id": str(application.id),
        "tenant_id": str(application.tenant_id),
        "received": [_serialize_received(model) for model in received],
        "granted_model_ids": sorted(str(model_id) for model_id in granted_ids),
    }


@router.post("/applications/{application_id}/models", status_code=201)
def grant_application_model(
    application_id: UUID,
    body: ModelApplicationGrantCreate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """把本租户收到的平台模型下发给本应用；幂等，回收后重发即复活。"""
    application = _authorized_application(application_id, actor, db)
    _ensure_distribute_permission(actor, db, application.tenant_id)
    created = ModelDistribution.grant_to_application(db, body.model_id, application, actor.id)
    model = db.get(ModelCatalog, body.model_id)
    audit(db, actor, request, "model.distribute.application", "model", str(body.model_id),
          {"tenant_id": str(application.tenant_id), "application_id": str(application.id),
           "model_key": model.key if model else None, "created": created})
    commit_or_conflict(db)
    return {"model_id": str(body.model_id), "application_id": str(application.id),
            "status": "active", "created": created}


@router.delete("/applications/{application_id}/models/{model_id}")
def revoke_application_model(
    application_id: UUID,
    model_id: UUID,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """回收应用下发（软失效）；该模型立即从应用 my-models 清单消失。"""
    application = _authorized_application(application_id, actor, db)
    _ensure_distribute_permission(actor, db, application.tenant_id)
    revoked = ModelDistribution.revoke_from_application(db, model_id, application.id)
    if not revoked:
        existing = db.scalar(select(ModelApplicationGrant).where(
            ModelApplicationGrant.model_id == model_id,
            ModelApplicationGrant.application_id == application.id))
        if existing is None:
            raise HTTPException(404, "该模型未下发给此应用")
    audit(db, actor, request, "model.revoke.application", "model", str(model_id),
          {"tenant_id": str(application.tenant_id), "application_id": str(application.id)})
    commit_or_conflict(db)
    return {"model_id": str(model_id), "application_id": str(application.id), "status": "revoked"}
