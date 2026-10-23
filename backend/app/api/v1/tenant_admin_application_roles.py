"""应用管理员的角色和成员入口；所有对象都由 URL 中的应用范围约束。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import TenantMembership, User
from app.schemas.access_control import (
    ApplicationRoleBindingCreate,
    ApplicationRoleCreate,
    RolePermissionsPreview,
    RolePermissionsUpdate,
    RoleStatusUpdate,
    RoleUpdate,
)
from app.services.admin_authorization import has_application_admin_access
from app.services.permission_impact import (
    StaleRolePermissionPreview,
    apply_role_permissions,
    preview_role_permissions,
)
from app.services.permission_namespace import assert_application_grant_permissions, permission_matches_namespace


router = APIRouter(tags=["应用角色与成员"])


def _authorized_application(application_id: UUID, actor: User, db: Session, *, manage: bool = False) -> Application:
    """先确认授权再查角色或成员，避免 app ID 成为跨租户枚举接口。"""
    application = db.get(Application, application_id)
    if not application or not has_application_admin_access(
        actor,
        application.tenant_id,
        db,
        manage=manage,
        application_id=application.id,
    ):
        raise HTTPException(404, "应用不存在")
    return application


def _authorized_role(application: Application, role_id: UUID, actor: User, db: Session,
                     *, manage: bool = False, lock: bool = False) -> Role:
    """角色必须同时属于 URL 中的租户和应用，禁止把其他范围的 role_id 拼进请求。"""
    statement = select(Role).where(
        Role.id == role_id,
        Role.tenant_id == application.tenant_id,
        Role.application_id == application.id,
    )
    if lock:
        statement = statement.with_for_update()
    role = db.scalar(statement)
    if not role:
        raise HTTPException(404, "应用角色不存在")
    if not has_application_admin_access(
        actor,
        application.tenant_id,
        db,
        manage=manage,
        application_id=application.id,
    ):
        raise HTTPException(404, "应用角色不存在")
    return role


def _role_payloads(roles: list[Role], db: Session) -> list[dict]:
    """一次性读取当前页角色授权，避免角色目录逐行访问数据库。"""
    if not roles:
        return []
    role_ids = [role.id for role in roles]
    rows = db.execute(
        select(RolePermission.role_id, Permission.code)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id.in_(role_ids))
        .order_by(Permission.code)
    ).all()
    permission_codes: dict[UUID, list[str]] = {role_id: [] for role_id in role_ids}
    for role_id, code in rows:
        permission_codes[role_id].append(code)
    return [
        {
            "id": str(role.id),
            "tenant_id": str(role.tenant_id),
            "application_id": str(role.application_id),
            "key": role.key,
            "name": role.name,
            "description": role.description,
            "status": role.status,
            "permission_codes": permission_codes[role.id],
        }
        for role in roles
    ]


def _reject_ineligible_application_permissions(
    application: Application,
    role: Role,
    proposed_permission_ids: list[UUID],
    db: Session,
) -> None:
    """应用角色只能绑定同命名空间业务权限，不能新增 IAM/platform 目录项。"""
    current_ids = set(db.scalars(select(RolePermission.permission_id).where(
        RolePermission.role_id == role.id,
        RolePermission.resource_id.is_(None),
    )).all())
    proposed = db.scalars(select(Permission).where(
        Permission.id.in_(proposed_permission_ids),
    ).with_for_update()).all() if proposed_permission_ids else []
    if len(proposed) != len(set(proposed_permission_ids)):
        raise HTTPException(422, "权限目录中存在无效权限")
    assert_application_grant_permissions(application.permission_namespace, proposed, current_ids)


@router.get("/applications/{application_id}/roles")
def list_application_roles(
    application_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """只返回当前授权应用的角色；租户通用和其他应用角色均不会暴露。"""
    application = _authorized_application(application_id, actor, db)
    roles = db.scalars(
        select(Role)
        .where(
            Role.tenant_id == application.tenant_id,
            Role.application_id == application.id,
        )
        .order_by(Role.created_at.desc())
        .limit(500)
    ).all()
    return _role_payloads(list(roles), db)


@router.post("/applications/{application_id}/roles", status_code=201)
def create_application_role(
    application_id: UUID,
    body: ApplicationRoleCreate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """应用角色的租户与应用范围只从已授权的 URL 对象派生。"""
    application = _authorized_application(application_id, actor, db, manage=True)
    if application.status != "active":
        raise HTTPException(409, "请先启用应用，再创建角色")
    role = Role(
        tenant_id=application.tenant_id,
        application_id=application.id,
        key=body.key,
        name=body.name.strip(),
        description=body.description.strip() or None if body.description else None,
    )
    db.add(role)
    flush_or_conflict(db)
    audit(db, actor, request, "application.role.create", "role", str(role.id), {
        "tenant_id": str(application.tenant_id),
        "application_id": str(application.id),
    })
    commit_or_conflict(db)
    return {
        "id": str(role.id),
        "tenant_id": str(role.tenant_id),
        "application_id": str(role.application_id),
        "key": role.key,
        "name": role.name,
        "description": role.description,
        "status": role.status,
        "permission_codes": [],
    }


@router.patch("/applications/{application_id}/roles/{role_id}")
def update_application_role(
    application_id: UUID,
    role_id: UUID,
    body: RoleUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    application = _authorized_application(application_id, actor, db, manage=True)
    role = _authorized_role(application, role_id, actor, db, manage=True)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(role, field, value)
    audit(db, actor, request, "application.role.update", "role", str(role.id), {
        "tenant_id": str(application.tenant_id),
        "application_id": str(application.id),
        "updated_fields": sorted(changes),
    })
    commit_or_conflict(db)
    return {"id": str(role.id), "name": role.name, "description": role.description,
            "updated_fields": sorted(changes)}


@router.patch("/applications/{application_id}/roles/{role_id}/status")
def set_application_role_status(
    application_id: UUID,
    role_id: UUID,
    body: RoleStatusUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    application = _authorized_application(application_id, actor, db, manage=True)
    role = _authorized_role(application, role_id, actor, db, manage=True, lock=True)
    if role.status != body.expected_status:
        raise HTTPException(409, "角色状态已被其他管理员修改，请刷新后重试")
    if role.status == body.status:
        return {"id": str(role.id), "status": role.status}
    previous_status = role.status
    role.status = body.status
    audit(db, actor, request, "application.role.status.change", "role", str(role.id), {
        "tenant_id": str(application.tenant_id),
        "application_id": str(application.id),
        "from_status": previous_status,
        "to_status": body.status,
    })
    commit_or_conflict(db)
    return {"id": str(role.id), "status": role.status}


@router.get("/applications/{application_id}/permissions")
def list_application_permissions(
    application_id: UUID,
    role_id: UUID = Query(...),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """只为当前应用内指定角色返回业务候选与其历史授权，避免角色间目录信息泄漏。"""
    application = _authorized_application(application_id, actor, db)
    role = _authorized_role(application, role_id, actor, db)
    currently_assigned_ids = set(db.scalars(select(RolePermission.permission_id).where(
        RolePermission.role_id == role.id,
    )).all())
    namespace = application.permission_namespace
    catalog_clauses = [
        and_(Permission.status == "active", Permission.catalog_namespace == namespace),
    ]
    if currently_assigned_ids:
        catalog_clauses.append(Permission.id.in_(currently_assigned_ids))
    rows = db.scalars(
        select(Permission)
        .where(or_(*catalog_clauses))
        .order_by(Permission.code)
        .limit(1000)
    ).all()
    return [{"id": str(permission.id), "code": permission.code,
             "catalog_namespace": permission.catalog_namespace,
             "resource_type": permission.resource_type, "scope": permission.scope,
             "status": permission.status}
            for permission in rows
            if permission_matches_namespace(permission.code, namespace)
            or permission.id in currently_assigned_ids]


@router.get("/applications/{application_id}/roles/{role_id}/permissions")
def list_application_role_permissions(
    application_id: UUID,
    role_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    application = _authorized_application(application_id, actor, db)
    role = _authorized_role(application, role_id, actor, db)
    rows = db.execute(
        select(RolePermission, Permission)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == role.id)
        .order_by(Permission.code, RolePermission.resource_id)
    ).all()
    return [{"id": str(grant.id), "permission_id": str(permission.id),
             "code": permission.code, "resource_id": grant.resource_id}
            for grant, permission in rows]


@router.post("/applications/{application_id}/roles/{role_id}/permissions/preview")
def preview_application_role_permissions(
    application_id: UUID,
    role_id: UUID,
    body: RolePermissionsPreview,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    application = _authorized_application(application_id, actor, db, manage=True)
    role = _authorized_role(application, role_id, actor, db, manage=True, lock=True)
    _reject_ineligible_application_permissions(application, role, body.permission_ids, db)
    try:
        return preview_role_permissions(role.id, body.permission_ids, db)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.put("/applications/{application_id}/roles/{role_id}/permissions")
def replace_application_role_permissions(
    application_id: UUID,
    role_id: UUID,
    body: RolePermissionsUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """只替换角色的通用业务权限；不改动实例级授权或数据范围策略。"""
    application = _authorized_application(application_id, actor, db, manage=True)
    role = _authorized_role(application, role_id, actor, db, manage=True, lock=True)
    _reject_ineligible_application_permissions(application, role, body.permission_ids, db)
    try:
        impact = apply_role_permissions(
            role.id,
            body.permission_ids,
            body.expected_current_permission_ids,
            db,
        )
    except StaleRolePermissionPreview as error:
        raise HTTPException(409, str(error)) from error
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if not impact["changed"]:
        return impact
    audit(db, actor, request, "application.role.permissions.replace", "role", str(role.id), {
        "tenant_id": str(application.tenant_id),
        "application_id": str(application.id),
        "granted_permissions": impact["grant_permission_codes"],
        "revoked_permissions": impact["revoke_permission_codes"],
        "removed_data_scope_policy_count": len(impact["data_scopes_to_delete"]),
    })
    commit_or_conflict(db)
    return {"changed": True, **impact}


@router.get("/applications/{application_id}/members")
def list_application_members(
    application_id: UUID,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """只列出已通过该应用角色取得授权的成员，避免暴露完整租户用户目录。"""
    application = _authorized_application(application_id, actor, db)
    direct_memberships = (
        select(RoleBinding.membership_id.label("membership_id"))
        .join(Role, Role.id == RoleBinding.role_id)
        .where(Role.tenant_id == application.tenant_id, Role.application_id == application.id)
    )
    group_memberships = (
        select(UserGroupMembership.membership_id.label("membership_id"))
        .join(UserGroupRole, and_(
            UserGroupRole.group_id == UserGroupMembership.group_id,
            UserGroupRole.tenant_id == UserGroupMembership.tenant_id,
        ))
        .join(UserGroup, and_(
            UserGroup.id == UserGroupRole.group_id,
            UserGroup.tenant_id == UserGroupRole.tenant_id,
        ))
        .join(Role, and_(
            Role.id == UserGroupRole.role_id,
            Role.tenant_id == UserGroupRole.tenant_id,
        ))
        .where(
            UserGroupMembership.tenant_id == application.tenant_id,
            UserGroup.status == "active",
            Role.status == "active",
            Role.application_id == application.id,
        )
    )
    eligible_memberships = direct_memberships.union(group_memberships).subquery()
    filters = [
        TenantMembership.tenant_id == application.tenant_id,
        TenantMembership.status == "active",
        User.status == "active",
        TenantMembership.id.in_(select(eligible_memberships.c.membership_id)),
    ]
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(User.email.ilike(pattern), User.display_name.ilike(pattern)))

    total = int(db.scalar(
        select(func.count(TenantMembership.id))
        .join(User, User.id == TenantMembership.user_id)
        .where(*filters)
    ) or 0)
    member_rows = db.execute(
        select(TenantMembership.id, User.id.label("user_id"), User.email, User.display_name)
        .join(User, User.id == TenantMembership.user_id)
        .where(*filters)
        .order_by(User.display_name, User.email)
        .offset(offset)
        .limit(limit)
    ).all()
    if not member_rows:
        return {"items": [], "total": total}

    membership_ids = [row.id for row in member_rows]
    assignments: dict[UUID, dict[UUID, dict]] = {row.user_id: {} for row in member_rows}

    direct_assignments = db.execute(
        select(TenantMembership.user_id, Role.id, Role.key, Role.name, Role.status)
        .join(RoleBinding, RoleBinding.membership_id == TenantMembership.id)
        .join(Role, Role.id == RoleBinding.role_id)
        .where(
            TenantMembership.id.in_(membership_ids),
            Role.tenant_id == application.tenant_id,
            Role.application_id == application.id,
        )
    ).all()
    for user_id, role_id, key, name, status in direct_assignments:
        entry = assignments[user_id].setdefault(role_id, {
            "id": str(role_id), "key": key, "name": name, "status": status, "sources": [],
        })
        entry["sources"].append("direct")

    inherited_assignments = db.execute(
        select(TenantMembership.user_id, Role.id, Role.key, Role.name, Role.status)
        .join(UserGroupMembership, UserGroupMembership.membership_id == TenantMembership.id)
        .join(UserGroup, and_(
            UserGroup.id == UserGroupMembership.group_id,
            UserGroup.tenant_id == UserGroupMembership.tenant_id,
        ))
        .join(UserGroupRole, and_(
            UserGroupRole.group_id == UserGroup.id,
            UserGroupRole.tenant_id == UserGroup.tenant_id,
        ))
        .join(Role, and_(
            Role.id == UserGroupRole.role_id,
            Role.tenant_id == UserGroupRole.tenant_id,
        ))
        .where(
            TenantMembership.id.in_(membership_ids),
            UserGroup.status == "active",
            Role.status == "active",
            Role.application_id == application.id,
        )
    ).all()
    for user_id, role_id, key, name, status in inherited_assignments:
        entry = assignments[user_id].setdefault(role_id, {
            "id": str(role_id), "key": key, "name": name, "status": status, "sources": [],
        })
        if "group" not in entry["sources"]:
            entry["sources"].append("group")

    return {
        "items": [
            {
                "user_id": str(user_id),
                "email": email,
                "display_name": display_name,
                "roles": sorted(assignments[user_id].values(), key=lambda item: item["name"].casefold()),
            }
            for membership_id, user_id, email, display_name in member_rows
        ],
        "total": total,
    }


@router.put("/applications/{application_id}/role-bindings", status_code=204)
def bind_application_role(
    application_id: UUID,
    body: ApplicationRoleBindingCreate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """按管理员指定的邮箱绑定现有租户成员；不提供可枚举的候选成员目录。"""
    application = _authorized_application(application_id, actor, db, manage=True)
    if application.status != "active":
        raise HTTPException(409, "停用应用不能分配新成员")
    role = _authorized_role(application, body.role_id, actor, db, manage=True)
    if role.status != "active":
        raise HTTPException(409, "停用角色不能绑定成员")

    email = str(body.email).casefold()
    membership = db.scalar(
        select(TenantMembership)
        .join(User, User.id == TenantMembership.user_id)
        .where(
            func.lower(User.email) == email,
            TenantMembership.tenant_id == application.tenant_id,
            TenantMembership.status == "active",
            User.status == "active",
        )
    )
    if not membership:
        raise HTTPException(404, "请先由租户管理员将该成员加入租户")
    existing = db.scalar(select(RoleBinding.id).where(
        RoleBinding.membership_id == membership.id,
        RoleBinding.role_id == role.id,
    ))
    if existing:
        return
    db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
    audit(db, actor, request, "application.role.bind", "user", str(membership.user_id), {
        "tenant_id": str(application.tenant_id),
        "application_id": str(application.id),
        "role_id": str(role.id),
    })
    commit_or_conflict(db)


@router.delete("/applications/{application_id}/members/{user_id}/roles/{role_id}", status_code=204)
def unbind_application_role(
    application_id: UUID,
    user_id: UUID,
    role_id: UUID,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """只移除直接绑定；用户组继承的应用角色须由租户管理员维护用户组。"""
    application = _authorized_application(application_id, actor, db, manage=True)
    role = _authorized_role(application, role_id, actor, db, manage=True)
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user_id,
        TenantMembership.tenant_id == application.tenant_id,
    ))
    if not membership:
        raise HTTPException(404, "应用成员角色不存在")
    binding = db.scalar(select(RoleBinding).where(
        RoleBinding.membership_id == membership.id,
        RoleBinding.role_id == role.id,
    ).with_for_update())
    if not binding:
        return
    db.execute(delete(RoleBinding).where(RoleBinding.id == binding.id))
    audit(db, actor, request, "application.role.unbind", "user", str(user_id), {
        "tenant_id": str(application.tenant_id),
        "application_id": str(application.id),
        "role_id": str(role.id),
    })
    commit_or_conflict(db)
