"""租户用户组管理路由：成员、角色与状态均由父级平台管理员路由保护。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import platform_admin
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

router = APIRouter(prefix="/groups", tags=["用户组管理"])


@router.get("")
def list_user_groups(tenant_id: UUID | None = None, db: Session = Depends(get_db_session)) -> list[dict]:
    """列出租户用户组和组成员/角色数量；两类关联数通过聚合查询避免逐行访问数据库。"""
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
             "member_count": member_count, "role_count": role_count, "created_at": group.created_at}
            for group, member_count, role_count in db.execute(statement).all()]


@router.post("", status_code=201)
def create_user_group(body: UserGroupCreate, request: Request,
                      actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """创建租户内用户组，唯一键冲突统一走受控的 409 响应。"""
    tenant = db.get(Tenant, body.tenant_id)
    if not tenant:
        raise HTTPException(404, "租户不存在")
    row = UserGroup(tenant_id=tenant.id, key=body.key, name=body.name.strip(),
                    description=body.description.strip() or None if body.description else None)
    db.add(row)
    flush_or_conflict(db)
    audit(db, actor, request, "user_group.create", "user_group", str(row.id),
          {"tenant_id": str(row.tenant_id), "key": row.key})
    commit_or_conflict(db)
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "key": row.key,
            "name": row.name, "description": row.description, "status": row.status,
            "member_count": 0, "role_count": 0}


@router.patch("/{group_id}")
def update_user_group(group_id: UUID, body: UserGroupUpdate, request: Request,
                      actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """只允许更新用户组展示信息，租户与标识保持不可变。"""
    row = db.get(UserGroup, group_id)
    if not row:
        raise HTTPException(404, "用户组不存在")
    changes = body.model_dump(exclude_unset=True)
    changed_fields = []
    for field, value in changes.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed_fields.append(field)
    # 幂等 PATCH 不应制造没有实际业务变化的审计噪声。
    if changed_fields:
        audit(db, actor, request, "user_group.update", "user_group", str(row.id),
              {"tenant_id": str(row.tenant_id), "updated_fields": sorted(changed_fields)})
        commit_or_conflict(db)
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "key": row.key,
            "name": row.name, "description": row.description, "status": row.status}


@router.patch("/{group_id}/status")
def set_user_group_status(group_id: UUID, status: str, request: Request,
                          actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """停用组会即时停止组角色参与授权；成员和角色配置会保留以便恢复。"""
    if status not in {"active", "disabled"}:
        raise HTTPException(422, "状态仅支持 active 或 disabled")
    row = db.scalar(select(UserGroup).where(UserGroup.id == group_id).with_for_update())
    if not row:
        raise HTTPException(404, "用户组不存在")
    if row.status != status:
        row.status = status
        audit(db, actor, request, "user_group.status.change", "user_group", str(row.id),
              {"tenant_id": str(row.tenant_id), "status": status})
        commit_or_conflict(db)
    return {"id": str(row.id), "status": row.status}


@router.get("/{group_id}/members")
def list_user_group_members(group_id: UUID, db: Session = Depends(get_db_session)) -> list[dict]:
    """列出该租户全部成员并标记组内成员，便于编辑时保留停用成员的显式配置。"""
    group = db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(404, "用户组不存在")
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
                               actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """全量替换组成员；锁定组并校验每个用户均有该租户的成员记录。"""
    group = db.scalar(select(UserGroup).where(UserGroup.id == group_id).with_for_update())
    if not group:
        raise HTTPException(404, "用户组不存在")
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
        audit(db, actor, request, "user_group.members.replace", "user_group", str(group.id),
              {"tenant_id": str(group.tenant_id), "member_count": len(memberships)})
        commit_or_conflict(db)
    return {"group_id": str(group.id), "member_count": len(next_ids), "changed": current_ids != next_ids}


@router.get("/{group_id}/roles")
def list_user_group_roles(group_id: UUID, db: Session = Depends(get_db_session)) -> list[dict]:
    """返回同租户角色目录并标记已分配项，避免客户端拼接租户边界。"""
    group = db.get(UserGroup, group_id)
    if not group:
        raise HTTPException(404, "用户组不存在")
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
                             actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """全量替換組角色；組、角色和審計在同一資料庫事務提交。"""
    group = db.scalar(select(UserGroup).where(UserGroup.id == group_id).with_for_update())
    if not group:
        raise HTTPException(404, "用户组不存在")
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
        audit(db, actor, request, "user_group.roles.replace", "user_group", str(group.id),
              {"tenant_id": str(group.tenant_id), "role_count": len(requested_ids)})
        commit_or_conflict(db)
    return {"group_id": str(group.id), "role_count": len(requested_ids), "changed": current_ids != requested_ids}
