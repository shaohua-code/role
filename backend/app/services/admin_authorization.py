"""租户管理 API 的服务端授权辅助；前端菜单状态不能替代这里的策略判定。"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import is_platform_admin_user
from app.models.application import Application
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.services.effective_roles import list_effective_roles


ORGANIZATION_READ = "org.read"
ORGANIZATION_MANAGE = "org.manage"
APPLICATION_READ = "app.read"
APPLICATION_MANAGE = "app.manage"
APPLICATION_SECRET_ROTATE = "app.secret.rotate"


def has_organization_admin_access(
    actor: User,
    tenant_id: UUID,
    db: Session,
    *,
    manage: bool = False,
) -> bool:
    """L1 代管；否则须持本租户 tenant.admin 或任一 app.admin（L2 模板含人治码）。

    manage 仅保留调用签名兼容；角色门禁不再区分 read/manage 细码。
    """
    del manage  # 角色门禁：组织台读写统一认 L3/L2 角色。
    from app.services.rbac_guards import user_has_any_role
    from app.services.role_provisioning import CONSOLE_ADMIN_ROLE_KEYS

    if is_platform_admin_user(actor, db):
        return True
    return user_has_any_role(
        actor, db, CONSOLE_ADMIN_ROLE_KEYS, tenant_id=tenant_id,
    )


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
    """L1 代管；L3 管本租户全部应用；L2 仅钉住的应用。未指定 application_id 视为创建入口，仅 L3。

    P404：L2 不能借「租户内任一 app.admin」走创建/删除。rotate_secret / manage 保留签名。
    """
    del manage
    from app.services.rbac_guards import user_has_any_role, user_has_management_code
    from app.services.role_provisioning import APP_SCOPED_ADMIN_ROLE_KEYS, L3_ROLE_KEY

    if is_platform_admin_user(actor, db):
        return True
    # L3 租户角色 application_id 为空，指定应用时仍命中。
    if user_has_any_role(actor, db, (L3_ROLE_KEY,), tenant_id=tenant_id):
        if rotate_secret:
            return user_has_management_code(
                actor, db, APPLICATION_SECRET_ROTATE,
                tenant_id=tenant_id, application_id=application_id,
                resource_id=str(application_id) if application_id else None,
            )
        return True
    # 未钉应用 = 租户级生命周期（创建）；L2 必须带具体 application_id。
    if application_id is None:
        return False
    if not user_has_any_role(
        actor, db, APP_SCOPED_ADMIN_ROLE_KEYS, tenant_id=tenant_id, application_id=application_id,
    ):
        return False
    if rotate_secret:
        return user_has_management_code(
            actor, db, APPLICATION_SECRET_ROTATE,
            tenant_id=tenant_id, application_id=application_id,
            resource_id=str(application_id) if application_id else None,
        )
    return True


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
    """批量筛选可读应用：L1 全量；L3 本租户全可管；否则按有效角色钉住的应用（及租户级码兼容）。

    列表用有效角色并集；单项写/轮换仍走 has_application_admin_access。
    """
    from app.services.rbac_guards import user_has_any_role
    from app.services.role_provisioning import L3_ROLE_KEY

    if is_platform_admin_user(actor, db):
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

    # L3 与写路径对齐：不依赖模板是否仍持 app.manage 码。
    if user_has_any_role(actor, db, (L3_ROLE_KEY,), tenant_id=tenant_id):
        applications = db.scalars(select(Application).where(Application.tenant_id == tenant_id)).all()
        return {
            application.id: {"can_manage": True, "can_rotate_secret": True}
            for application in applications
        }

    applications = db.scalars(select(Application).where(
        Application.tenant_id == tenant_id,
    )).all()
    if not applications:
        return {}

    effective_roles = list_effective_roles(
        db, membership_id=membership.id, tenant_id=tenant_id, application_id=None,
    )
    # 应用级授权需要按每个应用单独求值；数量有限（租户应用数），可接受。
    per_application_roles: dict[UUID, list[Role]] = {}
    for application in applications:
        per_application_roles[application.id] = list_effective_roles(
            db, membership_id=membership.id, tenant_id=tenant_id,
            application_id=application.id,
        )

    all_roles = {role.id: role for role in effective_roles}
    for roles in per_application_roles.values():
        for role in roles:
            all_roles[role.id] = role
    grant_rows = db.execute(
        select(RolePermission.role_id, Role.application_id, Permission.code, RolePermission.resource_id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            RolePermission.role_id.in_(all_roles) if all_roles else False,
            Permission.status == "active",
            Permission.code.in_((APPLICATION_READ, APPLICATION_MANAGE, APPLICATION_SECRET_ROTATE)),
        )
    ).all()

    grants_by_role: dict[UUID, list[tuple]] = {}
    for role_id, role_application_id, code, resource_id in grant_rows:
        grants_by_role.setdefault(role_id, []).append((role_application_id, code, resource_id))

    def matched_codes_for(role_ids: list[UUID], application_id_value: UUID) -> set[str]:
        """汇总一组角色在指定应用上命中的管理码（resource_id 为空表示通用授权）。"""
        matched: set[str] = set()
        for role_id in role_ids:
            for _, code, resource_id in grants_by_role.get(role_id, []):
                if resource_id is None or resource_id == str(application_id_value):
                    matched.add(code)
        return matched

    capabilities: dict[UUID, dict[str, bool]] = {}
    for application in applications:
        # 租户级角色授予的应用码 + 钉住该应用的角色授权，合并为该应用能力。
        matched_codes = matched_codes_for(
            [role.id for role in effective_roles], application.id,
        ) | matched_codes_for(
            [role.id for role in per_application_roles[application.id]], application.id,
        )
        can_manage = APPLICATION_MANAGE in matched_codes
        if APPLICATION_READ not in matched_codes and not can_manage:
            # secret.rotate 不能据此枚举应用或暴露应用资料。
            continue
        capabilities[application.id] = {
            "can_manage": can_manage,
            "can_rotate_secret": APPLICATION_SECRET_ROTATE in matched_codes,
        }
    return capabilities
