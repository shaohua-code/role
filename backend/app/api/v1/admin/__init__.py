"""平台管理 API 路由聚合器。入口只做认证；授权由各路由按角色门禁（ensure_roles）校验。"""

from fastapi import APIRouter, Depends

from app.api.v1.admin.access_control import router as access_control_router
from app.api.v1.admin.application_resources import router as application_resources_router
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
from app.api.v1.admin.uploads import admin_router as uploads_admin_router
from app.api.v1.admin.users import router as users_router
from app.core.security import current_user

# 绿场改造：废除路由级 platform_admin 一刀切；子路由默认仅认证，
# 必须在 handler 内用 rbac_guards.ensure_roles 授权（敏感写可另做码级双检）。
router = APIRouter(prefix="/admin", tags=["平台管理"], dependencies=[Depends(current_user)])

for domain_router in (
    overview_router,
    tenants_router,
    applications_router,
    application_resources_router,
    users_router,
    invitations_router,
    access_control_router,
    user_groups_router,
    organization_router,
    themes_router,
    uploads_admin_router,
    model_catalog_router,
    model_usage_router,
    audit_router,
):
    router.include_router(domain_router)
