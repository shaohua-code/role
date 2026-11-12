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


def ancestor_group_cte(membership_id: UUID, tenant_id: UUID):
    """成员所属活跃组及其全部祖先组（G24 嵌套）。组停用不参与继承。"""
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
    return group_tree.union_all(
        select(UserGroup.id, UserGroup.parent_group_id).join(
            group_tree, UserGroup.id == group_tree.c.parent_group_id,
        ).where(
            UserGroup.tenant_id == tenant_id,
            UserGroup.status == "active",
        )
    )


def authorized_role_ids_statement(membership_id: UUID, tenant_id: UUID) -> Select:
    """直连绑定与活跃用户组角色（含嵌套父组递归，G24）的并集。

    平台角色全局化：直连绑定的平台类角色（application_id IS NULL）跨租户全局生效，
    不再过滤角色租户；应用类角色（钉应用）仍要求与成员同租户。
    组继承分支保持组所在租户：组停用时保留配置但不参与继承；组层级沿
    parent_group_id 向上递归——成员所属组及其全部祖先组挂的角色均生效。
    组层级在写入时强制无环（服务层校验 + 复合外键），递归必然终止。
    """
    ancestor_groups = ancestor_group_cte(membership_id, tenant_id)
    inherited_role_ids = (
        select(UserGroupRole.role_id)
        .join(UserGroup, UserGroup.id == UserGroupRole.group_id)
        .where(
            UserGroup.id.in_(select(ancestor_groups.c.group_id)),
            UserGroupRole.tenant_id == tenant_id,
            UserGroup.status == "active",
        )
    )
    # 直连分支：平台类角色跨租户全局生效；应用类角色按其所属应用生效（跨租户任命：
    # 应用上下文匹配由 list_effective_roles 的 application_id 条件负责，不再要求成员与角色同租户）。
    direct_role_ids = (
        select(RoleBinding.role_id)
        .join(Role, Role.id == RoleBinding.role_id)
        .where(RoleBinding.membership_id == membership_id)
    )
    return direct_role_ids.union(inherited_role_ids)


def list_effective_roles(
    db: Session,
    *,
    membership_id: UUID,
    tenant_id: UUID,
    application_id: UUID | None = None,
) -> list[Role]:
    """返回成员在 (tenant, application) 上下文中的全部有效角色。

    平台角色全局化：平台类角色（application_id IS NULL，宿主平台管理租户）
    绑定到任意租户成员均生效；应用类角色按其所属应用生效（跨租户任命，不再要求成员同租户），
    应用上下文由 application_id 精确匹配，不会跨应用泄漏。
    application_id 为 None 时只取应用维度为空的角色（平台/租户级）；
    指定应用时取平台类角色 ∪ 钉住该应用的应用角色（L2/业务角色）。
    """
    statement = select(Role).where(
        Role.id.in_(authorized_role_ids_statement(membership_id, tenant_id)),
        Role.status == "active",
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
