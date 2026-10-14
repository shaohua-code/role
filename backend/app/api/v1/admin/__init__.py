"""平台管理 API 路由聚合器。具体 handler 按业务资源和权限域拆分。"""

from fastapi import APIRouter, Depends

from app.api.v1.admin.access_control import router as access_control_router
from app.api.v1.admin.applications import router as applications_router
from app.api.v1.admin.audit import router as audit_router
from app.api.v1.admin.groups import router as user_groups_router
from app.api.v1.admin.invitations import router as invitations_router
from app.api.v1.admin.model_usage import router as model_usage_router
from app.api.v1.admin.models import router as model_catalog_router
from app.api.v1.admin.organizations import router as organization_router
from app.api.v1.admin.overview import router as overview_router
from app.api.v1.admin.tenants import router as tenants_router
from app.api.v1.admin.themes import router as themes_router
from app.api.v1.admin.users import router as users_router
from app.core.security import platform_admin

# 平台管理员保护放在统一入口，保证新增子路由默认受保护。
router = APIRouter(prefix="/admin", tags=["平台管理"], dependencies=[Depends(platform_admin)])

for domain_router in (
    overview_router,
    tenants_router,
    applications_router,
    users_router,
    invitations_router,
    access_control_router,
    user_groups_router,
    organization_router,
    model_catalog_router,
    model_usage_router,
    themes_router,
    audit_router,
):
    router.include_router(domain_router)
