"""租户用户组管理路由：同挂 /admin 与 /tenant-admin，按组管理码判权。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user
from app.db.seed_greenfield import PLATFORM_TENANT_SLUG
from app.db.session import get_db_session
from app.models.authorization import Role
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import Tenant, TenantMembership, User
from app.schemas.groups import (
    UserGroupCreate,
    UserGroupMembersUpdate,
    UserGroupRolesUpdate,
    UserGroupUpdate,
)
from app.services.rbac_guards import ensure_roles, bump_membership_versions
from app.services.role_provisioning import CONSOLE_ADMIN_ROLE_KEYS, L1_ROLE_KEY, L3_ROLE_KEY

router = APIRouter(prefix="/groups", tags=["用户组管理"])


def _group_member_membership_ids(db: Session, group: UserGroup) -> list[UUID]:
    """组内全部成员的 membership ID，供组角色/状态变更后统一 bump。"""
    return list(db.scalars(select(UserGroupMembership.membership_id).where(
        UserGroupMembership.group_id == group.id,
        UserGroupMembership.tenant_id == group.tenant_id,
    )).all())


def _validate_parent_group(db: Session, group: UserGroup | None, tenant_id: UUID,
                           parent_group_id: UUID | None) -> None:
    """G24 组嵌套校验：父组必须同租户且启用；沿父链上溯检查防环。

    group 为 None 表示创建场景（无需防自环）；变更场景传现有行，
    new_parent 沿 parent 链上溯时遇到自身即成环，拒绝。
    """
    if parent_group_id is None:
        return
    cursor_id: UUID | None = parent_group_id
    visited: set[UUID] = set()
    while cursor_id:
        if group is not None and cursor_id == group.id:
            raise HTTPException(422, "父用户组关系不能形成循环")
        if cursor_id in visited:
            raise HTTPException(422, "父用户组关系不能形成循环")
        visited.add(cursor_id)
        parent = db.get(UserGroup, cursor_id)
        if not parent or parent.tenant_id != tenant_id or parent.status != "active":
            raise HTTPException(422, "父用户组必须属于同一租户且处于启用状态")
        cursor_id = parent.parent_group_id


@router.get("")
def list_user_groups(tenant_id: UUID | None = None, actor: User = Depends(current_user),
                     db: Session = Depends(get_db_session)) -> list[dict]:
    """列出租户用户组和组成员/角色数量；两类关联数通过聚合查询避免逐行访问数据库。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=tenant_id, detail="缺少管理角色（原 org.group.read）")
    member_counts = (select(UserGroupMembership.group_id.label("group_id"),
                             func.count(UserGroupMembership.membership_id).label("member_count"))
                     .group_by(UserGroupMembership.group_id).subquery())
    role_counts = (select(UserGroupRole.group_id.label("group_id"),
                          func.count(UserGroupRole.role_id).label("role_count"))
                   .group_by(UserGroupRole.group_id).subquery())
    statement = (select(UserGroup, func.coalesce(member_counts.c.member_count, 0).label("member_count"),
                        func.coalesce(role_counts.c.role_count, 0).label("role_count"))
                 .outerjoin(member_counts, member_counts.c.group_id == UserGroup.id)
                 .outerjoin(role_counts, role_counts.c.group_id == UserGroup.id)
                 .order_by(UserGroup.created_at.desc()).limit(500))
    if tenant_id:
        statement = statement.where(UserGroup.tenant_id == tenant_id)
    return [{"id": str(group.id), "tenant_id": str(group.tenant_id), "key": group.key,
             "name": group.name, "description": group.description, "status": group.status,
             "parent_group_id": str(group.parent_group_id) if group.parent_group_id else None,
             "member_count": member_count, "role_count": role_count, "created_at": group.created_at}
            for group, member_count, role_count in db.execute(statement).all()]


@router.post("", status_code=201)
def create_user_group(body: UserGroupCreate, request: Request,
                      actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """创建租户内用户组，唯一键冲突统一走受控的 409 响应。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=body.tenant_id, detail="缺少管理角色（原 org.group.manage）")
    tenant = db.get(Tenant, body.tenant_id)
    if not tenant:
        raise HTTPException(404, "租户不存在")
    # 平台引导租户是系统保留租户，用户组等业务协作对象只应挂在业务租户下。
    if tenant.slug == PLATFORM_TENANT_SLUG:
        raise HTTPException(422, "平台引导租户为系统保留租户，不支持业务用户组")
    # G24 组嵌套：父组必须同租户且启用；创建场景无自环问题。
    _validate_parent_group(db, None, tenant.id, body.parent_group_id)
    row = UserGroup(tenant_id=tenant.id, key=body.key, name=body.name.strip(),
                    description=body.description.strip() or None if body.description else None,
                    parent_group_id=body.parent_group_id)
    db.add(row)
    flush_or_conflict(db)
    audit(db, actor, request, "user_group.create", "user_group", str(row.id),
          {"tenant_id": str(row.tenant_id), "key": row.key,
           "parent_group_id": str(row.parent_group_id) if row.parent_group_id else None})
    commit_or_conflict(db)
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "key": row.key,
            "name": row.name, "description": row.description, "status": row.status,
            "parent_group_id": str(row.parent_group_id) if row.parent_group_id else None,
            "member_count": 0, "role_count": 0}


@router.patch("/{group_id}")
def update_user_group(group_id: UUID, body: UserGroupUpdate, request: Request,
                      actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """只允许更新用户组展示信息，租户与标识保持不可变。"""
    row = db.get(UserGroup, group_id)
    if not row:
        raise HTTPException(404, "用户组不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=row.tenant_id, detail="缺少管理角色（原 org.group.manage）")
    changes = body.model_dump(exclude_unset=True)
    # G24 组嵌套：变更父组需同租户、启用且不成环。
    if "parent_group_id" in changes:
        _validate_parent_group(db, row, row.tenant_id, changes["parent_group_id"])
    changed_fields = []
    for field, value in changes.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed_fields.append(field)
    # 幂等 PATCH 不应制造没有实际业务变化的审计噪声。
    if changed_fields:
        audit(db, actor, request, "user_group.update", "user_group", str(row.id),
              {"tenant_id": str(row.tenant_id), "updated_fields": sorted(changed_fields),
               "parent_group_id": str(row.parent_group_id) if row.parent_group_id else None})
        commit_or_conflict(db)
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "key": row.key,
            "name": row.name, "description": row.description, "status": row.status,
            "parent_group_id": str(row.parent_group_id) if row.parent_group_id else None}


@router.patch("/{group_id}/status")
def set_user_group_status(group_id: UUID, status: str, request: Request,
                          actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """停用组会即时停止组角色参与授权；成员和角色配置会保留以便恢复。"""
    if status not in {"active", "disabled"}:
        raise HTTPException(422, "状态仅支持 active 或 disabled")
    row = db.scalar(select(UserGroup).where(UserGroup.id == group_id).with_for_update())
    if not row:
        raise HTTPException(404, "用户组不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=row.tenant_id, detail="缺少管理角色（原 org.group.manage）")
    if row.status != status:
        row.status = status
        # 组启停改变成员有效角色，bump 让组内成员旧 OIDC 凭证立即失效。
        bump_membership_versions(db, _group_member_membership_ids(db, row))
        audit(db, actor, request, "user_group.status.change", "user_group", str(row.id),
              {"tenant_id": str(row.tenant_id), "status": status})
        commit_or_conflict(db)
    return {"id": str(row.id), "status": row.status}


@router.delete("/{group_id}", status_code=204)
def delete_user_group(group_id: UUID, request: Request,
                      actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> None:
    """删除用户组：成员挂接与组角色分配随外键级联清除；删除前 bump 组内成员使旧凭证失效。"""
    group = db.scalar(select(UserGroup).where(UserGroup.id == group_id).with_for_update())
    if not group:
        raise HTTPException(404, "用户组不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=group.tenant_id, detail="缺少管理角色（原 org.group.manage）")
    # 组删除改变成员有效角色：先对组内成员统一 bump，再级联删除两张关联表。
    bump_membership_versions(db, _group_member_membership_ids(db, group))
    audit(db, actor, request, "user_group.delete", "user_group", str(group.id),
          {"tenant_id": str(group.tenant_id), "key": group.key, "name": group.name})
    db.delete(group)
    commit_or_conflict(db)


@router.get("/{group_id}/members")
def list_user_group_members(group_id: UUID, actor: User = Depends(current_user),
                            db: Session = Depends(get_db_session)) -> list[dict]:
    """列出该租户全部成员并标记组内成员，便于编辑时保留停用成员的显式配置。"""
    group = db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(404, "用户组不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=group.tenant_id, detail="缺少管理角色（原 org.group.read）")
    assigned_ids = set(db.scalars(select(UserGroupMembership.membership_id).where(
        UserGroupMembership.group_id == group.id,
        UserGroupMembership.tenant_id == group.tenant_id,
    )).all())
    rows = db.execute(select(TenantMembership, User).join(User, User.id == TenantMembership.user_id).where(
        TenantMembership.tenant_id == group.tenant_id,
    ).order_by(User.display_name, User.email).limit(1000)).all()
    return [{"user_id": str(membership.user_id), "membership_id": str(membership.id),
             "email": user.email, "display_name": user.display_name, "user_status": user.status,
             "membership_status": membership.status, "in_group": membership.id in assigned_ids}
            for membership, user in rows]


@router.put("/{group_id}/members")
def replace_user_group_members(group_id: UUID, body: UserGroupMembersUpdate, request: Request,
                               actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """全量替换组成员；锁定组并校验每个用户均有该租户的成员记录。"""
    group = db.scalar(select(UserGroup).where(UserGroup.id == group_id).with_for_update())
    if not group:
        raise HTTPException(404, "用户组不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=group.tenant_id, detail="缺少管理角色（原 org.group.manage）")
    requested_ids = set(body.user_ids)
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.tenant_id == group.tenant_id,
        TenantMembership.user_id.in_(requested_ids) if requested_ids else False,
    )).all()
    by_user_id = {membership.user_id: membership for membership in memberships}
    if set(by_user_id) != requested_ids:
        raise HTTPException(422, "成员列表包含不属于该租户的用户")
    current_rows = db.scalars(select(UserGroupMembership).where(
        UserGroupMembership.group_id == group.id,
        UserGroupMembership.tenant_id == group.tenant_id,
    )).all()
    current_ids = {row.membership_id for row in current_rows}
    next_ids = {membership.id for membership in memberships}
    if current_ids != next_ids:
        db.execute(delete(UserGroupMembership).where(
            UserGroupMembership.group_id == group.id,
            UserGroupMembership.tenant_id == group.tenant_id,
        ))
        db.add_all([UserGroupMembership(group_id=group.id, membership_id=membership.id,
                                        tenant_id=group.tenant_id)
                    for membership in memberships])
        # 成员进出组立即改变有效角色：对进出集合的并集统一 bump。
        bump_membership_versions(db, current_ids | next_ids)
        audit(db, actor, request, "user_group.members.replace", "user_group", str(group.id),
              {"tenant_id": str(group.tenant_id), "member_count": len(memberships)})
        commit_or_conflict(db)
    return {"group_id": str(group.id), "member_count": len(next_ids), "changed": current_ids != next_ids}


@router.get("/{group_id}/roles")
def list_user_group_roles(group_id: UUID, actor: User = Depends(current_user),
                          db: Session = Depends(get_db_session)) -> list[dict]:
    """返回同租户角色目录并标记已分配项，避免客户端拼接租户边界。"""
    group = db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(404, "用户组不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=group.tenant_id, detail="缺少管理角色（原 org.group.read）")
    assigned_ids = set(db.scalars(select(UserGroupRole.role_id).where(
        UserGroupRole.group_id == group.id, UserGroupRole.tenant_id == group.tenant_id,
    )).all())
    roles = db.scalars(select(Role).where(Role.tenant_id == group.tenant_id)
                       .order_by(Role.name, Role.key).limit(500)).all()
    return [{"id": str(role.id), "key": role.key, "name": role.name,
             "status": role.status, "application_id": str(role.application_id) if role.application_id else None,
             "assigned": role.id in assigned_ids}
            for role in roles]


@router.put("/{group_id}/roles")
def replace_user_group_roles(group_id: UUID, body: UserGroupRolesUpdate, request: Request,
                             actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """全量替換組角色；組、角色和審計在同一資料庫事務提交。"""
    group = db.scalar(select(UserGroup).where(UserGroup.id == group_id).with_for_update())
    if not group:
        raise HTTPException(404, "用户组不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=group.tenant_id, detail="缺少管理角色（原 org.group.manage）")
    requested_ids = set(body.role_ids)
    roles = db.scalars(select(Role).where(
        Role.tenant_id == group.tenant_id,
        Role.id.in_(requested_ids) if requested_ids else False,
    )).all()
    if {role.id for role in roles} != requested_ids:
        raise HTTPException(422, "角色列表包含不属于该租户的角色")
    current_ids = set(db.scalars(select(UserGroupRole.role_id).where(
        UserGroupRole.group_id == group.id, UserGroupRole.tenant_id == group.tenant_id,
    )).all())
    if current_ids != requested_ids:
        db.execute(delete(UserGroupRole).where(
            UserGroupRole.group_id == group.id, UserGroupRole.tenant_id == group.tenant_id,
        ))
        db.add_all([UserGroupRole(group_id=group.id, role_id=role.id, tenant_id=group.tenant_id)
                    for role in roles])
        # 组角色替换影响全部组内成员的有效角色，统一 bump。
        bump_membership_versions(db, _group_member_membership_ids(db, group))
        audit(db, actor, request, "user_group.roles.replace", "user_group", str(group.id),
              {"tenant_id": str(group.tenant_id), "role_count": len(requested_ids)})
        commit_or_conflict(db)
    return {"group_id": str(group.id), "role_count": len(requested_ids), "changed": current_ids != requested_ids}
