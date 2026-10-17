"""租户管理员 API 聚合入口；具体资源处理器还会逐请求验证 tenant 权限。"""

from fastapi import APIRouter, Depends

from app.api.v1.admin.organizations import router as organizations_router
from app.api.v1.admin.applications import router as applications_router
from app.api.v1.tenant_admin_application_roles import router as application_roles_router
from app.core.security import current_user


router = APIRouter(
    prefix="/tenant-admin",
    tags=["租户管理员"],
    dependencies=[Depends(current_user)],
)

# 每个 handler 都调用 admin_authorization.py 按请求目标租户/资源做服务端 RBAC 校验。
router.include_router(organizations_router)
router.include_router(applications_router)
router.include_router(application_roles_router)
