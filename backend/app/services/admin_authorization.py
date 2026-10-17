"""租户管理 API 的服务端授权辅助；前端菜单状态不能替代这里的策略判定。"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import is_platform_admin_user
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import Tenant, TenantMembership, User
from app.schemas.access_control import AuthorizationCheck
from app.services.authorization import evaluate_access


ORGANIZATION_READ = "iam.organization.read"
ORGANIZATION_MANAGE = "iam.organization.manage"
APPLICATION_READ = "iam.application.read"
APPLICATION_MANAGE = "iam.application.manage"
APPLICATION_SECRET_ROTATE = "iam.application.secret.rotate"


def has_organization_admin_access(
    actor: User,
    tenant_id: UUID,
    db: Session,
    *,
    manage: bool = False,
) -> bool:
    """平台管理员可跨租户；其他成员须由该租户内有效角色授予相应管理编码。

    manage 权限同时允许读取管理界面所需的数据；纯 read 权限不能写组织或数据范围。
    evaluate_access 会再次确认用户、租户成员、角色、应用上下文和权限状态，
    OIDC token 的租户上下文也继续由验签依赖固定。
    """
    if is_platform_admin_user(actor):
        return True

    permission_codes = [ORGANIZATION_MANAGE] if manage else [ORGANIZATION_READ, ORGANIZATION_MANAGE]
    for permission_code in permission_codes:
        evaluation = evaluate_access(
            AuthorizationCheck(tenant_id=tenant_id, permission_code=permission_code),
            actor,
            db,
        )
        if evaluation["decision"]["allowed"]:
            return True
    return False


def require_organization_admin_access(
    actor: User,
    tenant_id: UUID,
    db: Session,
    *,
    manage: bool = False,
) -> None:
    """无有效租户范围管理权限时默认拒绝。"""
    if not has_organization_admin_access(actor, tenant_id, db, manage=manage):
        action = "管理" if manage else "查看"
        raise HTTPException(status_code=403, detail=f"缺少当前租户组织{action}权限")


def has_application_admin_access(
    actor: User,
    tenant_id: UUID,
    db: Session,
    *,
    manage: bool = False,
    rotate_secret: bool = False,
    application_id: UUID | None = None,
) -> bool:
    """检查租户级或指定应用级权限；密钥轮换单独授权。

    不传 application_id 时，只匹配租户级角色，调用方用于新建应用等租户级操作。
    指定 application_id 后，共享判权还会匹配绑定到该应用的角色/资源授权。
    """
    if is_platform_admin_user(actor):
        return True

    if rotate_secret:
        permission_codes = [APPLICATION_SECRET_ROTATE]
    elif manage:
        permission_codes = [APPLICATION_MANAGE]
    else:
        # manage 包含读取目录；只授予密钥轮换的角色不因此获得应用清单读取权。
        permission_codes = [APPLICATION_READ, APPLICATION_MANAGE]

    for permission_code in permission_codes:
        evaluation = evaluate_access(
            AuthorizationCheck(
                tenant_id=tenant_id,
                application_id=application_id,
                permission_code=permission_code,
                resource_id=str(application_id) if application_id else None,
            ),
            actor,
            db,
        )
        if evaluation["decision"]["allowed"]:
            return True
    return False


def require_application_admin_access(
    actor: User,
    tenant_id: UUID,
    db: Session,
    *,
    manage: bool = False,
    rotate_secret: bool = False,
    application_id: UUID | None = None,
) -> None:
    """在租户应用管理 API 内默认拒绝；密钥轮换不能被普通 manage 权限隐式继承。"""
    if not has_application_admin_access(
        actor, tenant_id, db, manage=manage, rotate_secret=rotate_secret,
        application_id=application_id,
    ):
        action = "轮换应用密钥" if rotate_secret else "管理应用" if manage else "查看应用"
        raise HTTPException(status_code=403, detail=f"缺少当前租户{action}权限")


def list_readable_application_capabilities(
    actor: User,
    tenant_id: UUID,
    db: Session,
) -> dict[UUID, dict[str, bool]]:
    """批量筛选可读应用，保持列表匹配与 evaluate_access 的租户/应用/资源边界一致。

    列表不能逐条发起三次判权查询，因此在同一个查询里合并直接角色与活动用户组角色；
    单项读写仍由 has_application_admin_access 调用共享 evaluator 再次判定。
    """
    if is_platform_admin_user(actor):
        applications = db.scalars(select(Application).where(Application.tenant_id == tenant_id)).all()
        return {
            application.id: {"can_manage": True, "can_rotate_secret": True}
            for application in applications
        }

    active_tenant = db.scalar(select(Tenant.id).where(
        Tenant.id == tenant_id, Tenant.status == "active",
    ))
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == actor.id,
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.status == "active",
    ))
    if not active_tenant or not membership:
        return {}

    applications = db.scalars(select(Application).where(
        Application.tenant_id == tenant_id,
    )).all()
    if not applications:
        return {}

    inherited_role_ids = (
        select(UserGroupRole.role_id)
        .join(UserGroup, UserGroup.id == UserGroupRole.group_id)
        .join(UserGroupMembership,
              (UserGroupMembership.group_id == UserGroup.id)
              & (UserGroupMembership.tenant_id == UserGroup.tenant_id))
        .where(
            UserGroupMembership.membership_id == membership.id,
            UserGroupMembership.tenant_id == tenant_id,
            UserGroupRole.tenant_id == tenant_id,
            UserGroup.status == "active",
        )
    )
    authorized_role_ids = select(RoleBinding.role_id).where(
        RoleBinding.membership_id == membership.id,
    ).union(inherited_role_ids)
    grant_rows = db.execute(
        select(Role.application_id, Permission.code, RolePermission.resource_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            Role.id.in_(authorized_role_ids),
            Role.tenant_id == tenant_id,
            Role.status == "active",
            Permission.status == "active",
            Permission.code.in_((APPLICATION_READ, APPLICATION_MANAGE, APPLICATION_SECRET_ROTATE)),
        )
    ).all()

    capabilities: dict[UUID, dict[str, bool]] = {}
    for application in applications:
        matched_codes = {
            code
            for role_application_id, code, resource_id in grant_rows
            if (role_application_id is None or role_application_id == application.id)
            and (resource_id is None or resource_id == str(application.id))
        }
        can_manage = APPLICATION_MANAGE in matched_codes
        if APPLICATION_READ not in matched_codes and not can_manage:
            # secret.rotate 不能据此枚举应用或暴露应用资料。
            continue
        capabilities[application.id] = {
            "can_manage": can_manage,
            "can_rotate_secret": APPLICATION_SECRET_ROTATE in matched_codes,
        }
    return capabilities
