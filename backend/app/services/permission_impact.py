"""计算角色权限批量变更的只读影响摘要。"""

from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import Tenant, TenantMembership, User
from app.models.model_catalog import ModelCatalog
from app.models.organization import RoleDataScope


APPLICATION_ADMIN_PERMISSION_CODES = frozenset({
    "app.read",
    "app.manage",
    "app.secret.rotate",
})


class StaleRolePermissionPreview(Exception):
    """预览生成后，其他管理员已修改了该角色的通用授权集合。"""


def _active_role_member_ids(role: Role, db: Session) -> set[UUID]:
    """统计可通过直接绑定或活动用户组继承此角色的活动租户成员。"""
    direct_members = (
        select(TenantMembership.id.label("membership_id"))
        .join(User, User.id == TenantMembership.user_id)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .join(RoleBinding, RoleBinding.membership_id == TenantMembership.id)
        .where(
            RoleBinding.role_id == role.id,
            TenantMembership.tenant_id == role.tenant_id,
            TenantMembership.status == "active",
            Tenant.status == "active",
            User.status == "active",
        )
    )
    group_members = (
        select(TenantMembership.id.label("membership_id"))
        .join(User, User.id == TenantMembership.user_id)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .join(UserGroupMembership,
              (UserGroupMembership.membership_id == TenantMembership.id)
              & (UserGroupMembership.tenant_id == TenantMembership.tenant_id))
        .join(UserGroup,
              (UserGroup.id == UserGroupMembership.group_id)
              & (UserGroup.tenant_id == UserGroupMembership.tenant_id))
        .join(UserGroupRole,
              (UserGroupRole.group_id == UserGroup.id)
              & (UserGroupRole.tenant_id == UserGroup.tenant_id))
        .where(
            UserGroupRole.role_id == role.id,
            TenantMembership.tenant_id == role.tenant_id,
            TenantMembership.status == "active",
            Tenant.status == "active",
            User.status == "active",
            UserGroup.status == "active",
        )
    )
    # UNION 在数据库侧去重，避免同一成员既直接绑定又经多个用户组继承时重复计数。
    return set(db.scalars(direct_members.union(group_members)).all())


def _other_general_role_grants(
    role: Role,
    membership_ids: set[UUID],
    permission_codes: set[str],
    db: Session,
) -> set[tuple[UUID, str]]:
    """查找同成员可用的其它通用授权；实例授权不视为覆盖所有资源。"""
    if not membership_ids or not permission_codes:
        return set()

    # 通用租户角色可用于任意应用上下文；应用角色只覆盖本应用及通用角色。
    application_scope = (Role.application_id.is_(None) if role.application_id is None else
                         or_(Role.application_id.is_(None), Role.application_id == role.application_id))
    common_filters = (
        TenantMembership.id.in_(membership_ids),
        TenantMembership.tenant_id == role.tenant_id,
        TenantMembership.status == "active",
        User.status == "active",
        Role.id != role.id,
        Role.tenant_id == role.tenant_id,
        Role.status == "active",
        application_scope,
        Permission.code.in_(permission_codes),
        Permission.status == "active",
        RolePermission.resource_id.is_(None),
    )
    direct_grants = (
        select(TenantMembership.id.label("membership_id"), Permission.code.label("permission_code"))
        .join(User, User.id == TenantMembership.user_id)
        .join(RoleBinding, RoleBinding.membership_id == TenantMembership.id)
        .join(Role, Role.id == RoleBinding.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(*common_filters)
    )
    group_grants = (
        select(TenantMembership.id.label("membership_id"), Permission.code.label("permission_code"))
        .join(User, User.id == TenantMembership.user_id)
        .join(UserGroupMembership,
              (UserGroupMembership.membership_id == TenantMembership.id)
              & (UserGroupMembership.tenant_id == TenantMembership.tenant_id))
        .join(UserGroup,
              (UserGroup.id == UserGroupMembership.group_id)
              & (UserGroup.tenant_id == UserGroupMembership.tenant_id))
        .join(UserGroupRole,
              (UserGroupRole.group_id == UserGroup.id)
              & (UserGroupRole.tenant_id == UserGroup.tenant_id))
        .join(Role, (Role.id == UserGroupRole.role_id) & (Role.tenant_id == UserGroupRole.tenant_id))
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(*common_filters, UserGroup.status == "active")
    )
    rows = db.execute(direct_grants.union(group_grants)).all()
    return {(row.membership_id, row.permission_code) for row in rows}


def _permission_can_be_live(role: Role, permission_code: str, db: Session,
                            application: Application | None) -> bool:
    """按在线判权的角色、应用及模型状态，过滤当前不可能生效的授权变化。"""
    if role.status != "active":
        return False
    if role.application_id is not None:
        if not application or application.tenant_id != role.tenant_id:
            return False
        if application.status != "active" and permission_code not in APPLICATION_ADMIN_PERMISSION_CODES:
            return False
    if permission_code == "model.invoke":
        active_model_exists = db.scalar(select(ModelCatalog.id).where(
            ModelCatalog.tenant_id == role.tenant_id,
            ModelCatalog.status == "active",
        ).limit(1))
        if not active_model_exists:
            return False
    return True


def preview_role_permissions(
    role_id: UUID,
    proposed_permission_ids: list[UUID],
    db: Session,
    *,
    lock_permissions: bool = False,
) -> dict:
    """比较角色通用授权集合并估算权限变化的潜在成员影响。"""
    role = db.get(Role, role_id)
    if not role:
        raise LookupError("角色不存在")
    if len(set(proposed_permission_ids)) != len(proposed_permission_ids):
        raise ValueError("权限列表不能包含重复项")

    requested_statement = select(Permission).where(Permission.id.in_(proposed_permission_ids))
    if lock_permissions:
        # 提交时与目录停用事务串行化，避免刚停用的编码同时被写入新角色授权。
        requested_statement = requested_statement.with_for_update()
    requested_permissions = db.scalars(requested_statement).all() if proposed_permission_ids else []
    if len(requested_permissions) != len(proposed_permission_ids):
        raise ValueError("权限目录中存在无效权限")
    requested_by_id = {permission.id: permission for permission in requested_permissions}

    current_rows = db.execute(
        select(RolePermission.permission_id, Permission.code, Permission.status)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == role.id, RolePermission.resource_id.is_(None))
    ).all()
    current_by_id = {row.permission_id: row.code for row in current_rows}
    current_status_by_id = {row.permission_id: row.status for row in current_rows}
    current_ids = set(current_by_id)
    proposed_ids = set(proposed_permission_ids)
    inactive_new_ids = {
        permission.id for permission in requested_permissions
        if permission.status != "active" and permission.id not in current_ids
    }
    if inactive_new_ids:
        raise ValueError("停用权限不能新增角色授权")
    added_ids = proposed_ids - current_ids
    removed_ids = current_ids - proposed_ids

    member_ids = _active_role_member_ids(role, db)
    bound_active_members = len(member_ids)

    # 若撤销通用授权但仍存在实例级授权，关联数据范围仍有用途；否则本次会一并清理失效策略。
    remaining_resource_grants = set(db.scalars(
        select(RolePermission.permission_id).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id.in_(removed_ids),
            RolePermission.resource_id.is_not(None),
        )
    ).all()) if removed_ids else set()
    orphaned_scope_permission_ids = removed_ids - remaining_resource_grants
    scope_rows = db.execute(
        select(RoleDataScope.permission_id, RoleDataScope.scope_type, Permission.code)
        .join(Permission, Permission.id == RoleDataScope.permission_id)
        .where(
            RoleDataScope.role_id == role.id,
            RoleDataScope.permission_id.in_(orphaned_scope_permission_ids),
        )
    ).all() if orphaned_scope_permission_ids else []

    application = db.get(Application, role.application_id) if role.application_id else None
    change_rows: list[tuple[UUID, str, str]] = []
    for permission_id in added_ids:
        change_rows.append((permission_id, requested_by_id[permission_id].code, "grant"))
    for permission_id in removed_ids:
        change_rows.append((permission_id, current_by_id[permission_id], "revoke"))
    live_change_codes = {
        code for permission_id, code, action in change_rows
        if _permission_can_be_live(role, code, db, application)
        and ((action == "grant" and requested_by_id[permission_id].status == "active")
             or (action == "revoke" and current_status_by_id[permission_id] == "active"))
    }
    covered_grants = _other_general_role_grants(role, member_ids, live_change_codes, db)

    permission_impacts = []
    potentially_affected_member_ids: set[UUID] = set()
    for _permission_id, permission_code, action in sorted(change_rows, key=lambda item: (item[2], item[1])):
        can_be_live = permission_code in live_change_codes
        covered_member_ids = {
            membership_id for membership_id, code in covered_grants if code == permission_code
        } if can_be_live else set()
        affected_member_ids = member_ids - covered_member_ids if can_be_live else set()
        potentially_affected_member_ids.update(affected_member_ids)
        permission_impacts.append({
            "permission_code": permission_code,
            "action": action,
            "eligible_members": len(member_ids) if can_be_live else 0,
            "covered_by_other_general_roles": len(covered_member_ids),
            "potentially_affected_members": len(affected_member_ids),
        })

    return {
        "role": {"id": str(role.id), "key": role.key, "name": role.name,
                 "status": role.status, "tenant_id": str(role.tenant_id)},
        "current_permission_ids": sorted(map(str, current_ids)),
        "current_permission_codes": sorted(current_by_id.values()),
        "proposed_permission_codes": sorted(requested_by_id[permission_id].code for permission_id in proposed_ids),
        "grant_permission_codes": sorted(requested_by_id[permission_id].code for permission_id in added_ids),
        "revoke_permission_codes": sorted(current_by_id[permission_id] for permission_id in removed_ids),
        "data_scopes_to_delete": sorted(
            ({"permission_id": str(row.permission_id), "permission_code": row.code,
              "scope_type": row.scope_type} for row in scope_rows),
            key=lambda row: (row["permission_code"], row["scope_type"]),
        ),
        "bound_active_members": int(bound_active_members),
        "potentially_affected_members": len(potentially_affected_member_ids),
        "permission_impacts": permission_impacts,
        "analysis_note": (
            "成员按活动租户成员去重，包含直接绑定及活动用户组继承。逐权限估算会扣除适用范围内其它活动角色的通用授权；"
            "资源实例授权不视为覆盖所有资源，且未逐个模拟业务资源和数据范围策略，因此人数表示潜在覆盖，不是完整净差异。"
            "停用角色、停用权限、停用应用中的普通权限及当前没有活动模型的 model.invoke 不计入在线影响。"
        ),
    }


def apply_role_permissions(role_id: UUID, proposed_permission_ids: list[UUID],
                           expected_current_permission_ids: list[UUID], db: Session) -> dict:
    """锁定角色并在单一事务中替换通用授权及其失效数据范围。"""
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    if not role:
        raise LookupError("角色不存在")
    impact = preview_role_permissions(role_id, proposed_permission_ids, db, lock_permissions=True)
    current_ids = {UUID(value) for value in impact["current_permission_ids"]}
    if set(expected_current_permission_ids) != current_ids:
        raise StaleRolePermissionPreview("授权预览后角色权限发生变化，请重新预览")

    proposed_ids = set(proposed_permission_ids)
    removed_ids = current_ids - proposed_ids
    added_ids = proposed_ids - current_ids
    if not removed_ids and not added_ids:
        return {"changed": False, **impact}

    if removed_ids:
        db.execute(delete(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id.in_(removed_ids),
            RolePermission.resource_id.is_(None),
        ))
    db.add_all(RolePermission(role_id=role_id, permission_id=permission_id)
               for permission_id in added_ids)

    # 清理本次撤销后已没有任何匹配授权的数据范围，阻止未来重授时意外复活。
    scope_ids_to_delete = {UUID(item["permission_id"]) for item in impact["data_scopes_to_delete"]}
    if scope_ids_to_delete:
        db.execute(delete(RoleDataScope).where(
            RoleDataScope.role_id == role_id,
            RoleDataScope.permission_id.in_(scope_ids_to_delete),
        ))
    db.flush()
    return {"changed": True, **impact}



