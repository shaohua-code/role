"""模型三级分发服务：平台目录归属、下发 / 回收（软失效）与三级可见性解析。

口径（产品需求 §6.4）：应用可见 = 平台目录 ∩ 租户下发 ∩ 应用下发；
租户可见 = 平台目录 ∩ 租户下发；下发关系即授权唯一依据，业务码 / 资源树不参与模型判权。
平台目录行统一归属 platform 租户（slug=platform）；下发关系回收为软失效
（revoked 行保留供恢复与审计），租户级回收级联软失效其全部应用下发。
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.identity import Tenant
from app.models.model_catalog import ModelApplicationGrant, ModelCatalog, ModelTenantGrant


class ModelDistribution:
    """三级分发领域服务；全部 @staticmethod，db 会话由调用方传入（OOP 约定）。"""

    PLATFORM_TENANT_SLUG = "platform"

    @staticmethod
    def get_platform_tenant(db: Session) -> Tenant:
        """平台租户（slug=platform）持有全部平台目录行；引导初始化保证存在。"""
        tenant = db.scalar(select(Tenant).where(Tenant.slug == ModelDistribution.PLATFORM_TENANT_SLUG))
        if tenant is None:
            raise RuntimeError("平台租户缺失：请先运行引导初始化")
        return tenant

    @staticmethod
    def _get_platform_catalog_row(db: Session, model_id: UUID) -> ModelCatalog | None:
        """按 ID 加载目录行并校验平台租户归属；非平台目录行与缺失同样返回 None。

        「目录行统一归属 platform 租户」的不变式在领域服务入口二次收口，
        避免未来新的调用方绕过 API 层 helper 把异常行当全平台模型传播。
        """
        model = db.get(ModelCatalog, model_id)
        if model is None or model.tenant_id != ModelDistribution.get_platform_tenant(db).id:
            return None
        return model

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    # ── 平台 → 租户 下发 / 回收 ─────────────────────────────────────────────

    @staticmethod
    def grant_to_tenant(db: Session, model_id: UUID, tenant_id: UUID, actor_id: UUID) -> bool:
        """下发平台模型给租户；幂等：已 active 直接返回 False，revoked 复活返回 True。"""
        if ModelDistribution._get_platform_catalog_row(db, model_id) is None:
            raise HTTPException(404, "模型不存在")
        tenant = db.get(Tenant, tenant_id)
        if tenant is None or tenant.status != "active":
            raise HTTPException(404, "租户不存在")
        if tenant.slug == ModelDistribution.PLATFORM_TENANT_SLUG:
            raise HTTPException(422, "平台模型不能下发给平台租户")
        grant = db.scalar(select(ModelTenantGrant).where(
            ModelTenantGrant.model_id == model_id, ModelTenantGrant.tenant_id == tenant_id))
        if grant is None:
            db.add(ModelTenantGrant(
                model_id=model_id, tenant_id=tenant_id, status="active", granted_by=actor_id))
            db.flush()
            return True
        if grant.status == "active":
            return False
        grant.status = "active"
        grant.granted_by = actor_id
        grant.revoked_at = None
        db.flush()
        return True

    @staticmethod
    def revoke_from_tenant(db: Session, model_id: UUID, tenant_id: UUID) -> tuple[bool, int]:
        """软失效租户下发，并级联软失效该租户全部应用下发。

        返回 (是否发生本次回收, 级联失效的应用下发条数)；行不存在时 (False, 0)。
        """
        grant = db.scalar(select(ModelTenantGrant).where(
            ModelTenantGrant.model_id == model_id, ModelTenantGrant.tenant_id == tenant_id,
            ModelTenantGrant.status == "active"))
        if grant is None:
            return False, 0
        now = ModelDistribution._now()
        grant.status = "revoked"
        grant.revoked_at = now
        app_grants = db.scalars(select(ModelApplicationGrant).where(
            ModelApplicationGrant.model_id == model_id,
            ModelApplicationGrant.tenant_id == tenant_id,
            ModelApplicationGrant.status == "active",
        )).all()
        for row in app_grants:
            row.status = "revoked"
            row.revoked_at = now
        db.flush()
        return True, len(app_grants)

    # ── 租户 → 应用 下发 / 回收 ─────────────────────────────────────────────

    @staticmethod
    def grant_to_application(db: Session, model_id: UUID, application: Application, actor_id: UUID) -> bool:
        """把本租户已收到的平台模型下发给应用；模型缺失 / 停用 / 租户未收到统一 404
        （防目录枚举：操作者看不见的模型与不存在的模型不可区分——「看得见才能配」）。"""
        model = ModelDistribution._get_platform_catalog_row(db, model_id)
        tenant_grant = None
        if model is not None:
            tenant_grant = db.scalar(select(ModelTenantGrant).where(
                ModelTenantGrant.model_id == model_id,
                ModelTenantGrant.tenant_id == application.tenant_id,
                ModelTenantGrant.status == "active"))
        if model is None or model.status != "active" or tenant_grant is None:
            raise HTTPException(404, "模型不存在或未下发给本租户")
        grant = db.scalar(select(ModelApplicationGrant).where(
            ModelApplicationGrant.model_id == model_id,
            ModelApplicationGrant.application_id == application.id))
        if grant is None:
            db.add(ModelApplicationGrant(
                model_id=model_id, tenant_id=application.tenant_id,
                application_id=application.id, status="active", granted_by=actor_id))
            db.flush()
            return True
        if grant.status == "active":
            return False
        grant.status = "active"
        grant.granted_by = actor_id
        grant.revoked_at = None
        db.flush()
        return True

    @staticmethod
    def revoke_from_application(db: Session, model_id: UUID, application_id: UUID) -> bool:
        """软失效应用下发；行不存在或已回收返回 False。"""
        grant = db.scalar(select(ModelApplicationGrant).where(
            ModelApplicationGrant.model_id == model_id,
            ModelApplicationGrant.application_id == application_id,
            ModelApplicationGrant.status == "active"))
        if grant is None:
            return False
        grant.status = "revoked"
        grant.revoked_at = ModelDistribution._now()
        db.flush()
        return True

    # ── 三级可见性解析（唯一口径）────────────────────────────────────────────

    @staticmethod
    def list_models_for_tenant(db: Session, tenant_id: UUID) -> list[ModelCatalog]:
        """租户可见 = 平台目录 active ∩ 租户下发 active；目录行按平台租户归属过滤。"""
        return list(db.scalars(select(ModelCatalog).join(
            ModelTenantGrant, ModelTenantGrant.model_id == ModelCatalog.id,
        ).where(
            ModelCatalog.tenant_id == ModelDistribution.get_platform_tenant(db).id,
            ModelCatalog.status == "active",
            ModelTenantGrant.tenant_id == tenant_id,
            ModelTenantGrant.status == "active",
        ).order_by(ModelCatalog.created_at.desc(), ModelCatalog.id)).all())

    @staticmethod
    def list_models_for_application(db: Session, application: Application) -> list[ModelCatalog]:
        """应用可见 = 平台目录 active ∩ 租户下发 active ∩ 应用下发 active（my-models 契约口径）。"""
        return list(db.scalars(select(ModelCatalog).join(
            ModelTenantGrant, ModelTenantGrant.model_id == ModelCatalog.id,
        ).join(
            ModelApplicationGrant, ModelApplicationGrant.model_id == ModelCatalog.id,
        ).where(
            ModelCatalog.tenant_id == ModelDistribution.get_platform_tenant(db).id,
            ModelCatalog.status == "active",
            ModelTenantGrant.tenant_id == application.tenant_id,
            ModelTenantGrant.status == "active",
            ModelApplicationGrant.application_id == application.id,
            ModelApplicationGrant.status == "active",
        ).order_by(ModelCatalog.created_at.desc(), ModelCatalog.id)).all())

    @staticmethod
    def application_grant_is_active(db: Session, model_id: UUID, application_id: UUID) -> bool:
        """用量上报前置校验：该应用对本模型存在 active 下发。"""
        return db.scalar(select(ModelApplicationGrant.id).where(
            ModelApplicationGrant.model_id == model_id,
            ModelApplicationGrant.application_id == application_id,
            ModelApplicationGrant.status == "active",
        )) is not None

    @staticmethod
    def tenant_grant_is_active(db: Session, model_id: UUID, tenant_id: UUID) -> bool:
        """用量上报前置校验：该租户对本模型存在 active 下发。"""
        return db.scalar(select(ModelTenantGrant.id).where(
            ModelTenantGrant.model_id == model_id,
            ModelTenantGrant.tenant_id == tenant_id,
            ModelTenantGrant.status == "active",
        )) is not None
