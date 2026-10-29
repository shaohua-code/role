"""租户管理员 API 聚合入口；具体资源处理器还会逐请求验证 tenant 权限。"""

from fastapi import APIRouter, Depends

from app.api.v1.admin.groups import router as user_groups_router
from app.api.v1.admin.organizations import router as organizations_router
from app.api.v1.admin.applications import router as applications_router
from app.api.v1.tenant_admin.application_roles import router as application_roles_router
from app.core.security import current_user


router = APIRouter(
    prefix="/tenant-admin",
    tags=["租户管理员"],
    dependencies=[Depends(current_user)],
)

# 每个 handler 都调用 admin_authorization.py / rbac_guards.py 按角色门禁（ensure_roles / 过渡期码→角色映射）校验目标租户/应用。
# 绿场规则：组管理首期即挂 tenant-admin（L3 持 tenant.admin（组管理走角色门禁））。
router.include_router(organizations_router)
router.include_router(applications_router)
router.include_router(application_roles_router)
router.include_router(user_groups_router)

