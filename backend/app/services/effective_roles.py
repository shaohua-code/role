"""全站唯一的有效角色实现：直连绑定 ∪ 活跃用户组继承。

evaluate_access、OIDC 入场、管理台能力列表、rbac_guards 都必须复用本模块，
禁止再各自手写角色集合查询，避免组继承语义漂移。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.authorization import Role, RoleBinding
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import TenantMembership, User


def authorized_role_ids_statement(membership_id: UUID, tenant_id: UUID) -> Select:
    """直连绑定与活跃用户组角色（含嵌套父组递归，G24）的并集。

    组停用时保留配置但不参与继承；组层级沿 parent_group_id 向上递归——
    成员所属组及其全部祖先组挂的角色均生效（与主流目录的嵌套组语义一致）。
    组层级在写入时强制无环（服务层校验 + 复合外键），递归必然终止。
    """
    group_tree = (
        select(UserGroup.id.label("group_id"), UserGroup.parent_group_id.label("parent_group_id"))
        .join(
            UserGroupMembership,
            (UserGroupMembership.group_id == UserGroup.id)
            & (UserGroupMembership.tenant_id == UserGroup.tenant_id),
        )
        .where(
            UserGroupMembership.membership_id == membership_id,
            UserGroupMembership.tenant_id == tenant_id,
            UserGroup.status == "active",
        )
        .cte(name="group_tree", recursive=True)
    )
    # 递归沿 parent_group_id 向上：候选组的 ID 等于树内某节点的父 ID，即候选组是父组。
    ancestor_groups = group_tree.union_all(
        select(UserGroup.id, UserGroup.parent_group_id).join(
            group_tree, UserGroup.id == group_tree.c.parent_group_id,
        ).where(
            UserGroup.tenant_id == tenant_id,
            UserGroup.status == "active",
        )
    )
    inherited_role_ids = (
        select(UserGroupRole.role_id)
        .join(UserGroup, UserGroup.id == UserGroupRole.group_id)
        .where(
            UserGroup.id.in_(select(ancestor_groups.c.group_id)),
            UserGroupRole.tenant_id == tenant_id,
            UserGroup.status == "active",
        )
    )
    return (
        select(RoleBinding.role_id)
        .where(RoleBinding.membership_id == membership_id)
        .union(inherited_role_ids)
    )


def list_effective_roles(
    db: Session,
    *,
    membership_id: UUID,
    tenant_id: UUID,
    application_id: UUID | None = None,
) -> list[Role]:
    """返回成员在 (tenant, application) 上下文中的全部有效角色。

    application_id 为 None 时只取应用维度为空的 platform/tenant 角色；
    指定应用时取租户角色 ∪ 钉住该应用的应用角色（L2/业务角色）。
    平台角色只存在于平台租户，业务租户过滤后天然不会出现。
    """
    statement = select(Role).where(
        Role.id.in_(authorized_role_ids_statement(membership_id, tenant_id)),
        Role.status == "active",
        Role.tenant_id == tenant_id,
    )
    if application_id is None:
        statement = statement.where(
            Role.application_id.is_(None),
            Role.kind.in_(("platform", "tenant")),
        )
    else:
        statement = statement.where(
            Role.application_id.is_(None) | (Role.application_id == application_id),
        )
    return list(db.scalars(statement).all())


def user_is_platform_admin(user: User, db: Session) -> bool:
    """L1 判定：任一活跃租户成员身份持有效 platform 层级角色。

    平台角色只能绑定在专用平台租户的 membership 上；OIDC 业务身份、
    邮箱同名账号都不满足，破窗旁路由调用方单独处理。
    """
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all()
    for membership in memberships:
        if any(
            role.kind == "platform"
            for role in list_effective_roles(
                db, membership_id=membership.id, tenant_id=membership.tenant_id,
            )
        ):
            return True
    return False
