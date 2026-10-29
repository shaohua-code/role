"""应用管理员的角色和成员入口；所有对象都由 URL 中的应用范围约束。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user, is_platform_admin_user
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
from app.services.permission_namespace import (
    assert_application_grant_permissions,
    is_management_code,
    permission_matches_namespace,
)
from app.services.role_provisioning import (
    L2M_ROLE_KEY,
    L2_ROLE_KEY,
    L3_ROLE_KEY,
    L4_ROLE_KEY,
    TEMPLATE_ROLE_KEYS,
    is_application_class_role,
)
from app.services.rbac_guards import (
    actor_grantable_management_codes,
    bump_membership_versions,
    user_has_any_role,
)


router = APIRouter(tags=["应用角色与成员"])

def _ensure_app_role_binding_permission(
    actor: User, db: Session, application: Application, role: Role,
) -> None:
    """P405 任命链：L3 可任命多应用/应用管理员；多应用管理员可再任命应用管理员；应用管理员不能任命管理员。"""
    if is_platform_admin_user(actor, db):
        return
    tenant_id = application.tenant_id
    app_id = application.id
    if user_has_any_role(actor, db, (L3_ROLE_KEY,), tenant_id=tenant_id):
        return
    is_multi = user_has_any_role(
        actor, db, (L2M_ROLE_KEY,), tenant_id=tenant_id, application_id=app_id,
    )
    is_single = user_has_any_role(
        actor, db, (L2_ROLE_KEY,), tenant_id=tenant_id, application_id=app_id,
    )
    if is_multi:
        if role.key == L2M_ROLE_KEY:
            raise HTTPException(403, "多应用管理员不能任命多应用管理员")
        return
    if is_single:
        if role.key in {L2M_ROLE_KEY, L2_ROLE_KEY}:
            raise HTTPException(403, "应用管理员不能任命应用管理员")
        if role.key == L4_ROLE_KEY or is_application_class_role(role):
            return
        raise HTTPException(403, "缺少应用角色成员管理权限")
    raise HTTPException(403, "缺少应用角色成员管理权限")


def _ensure_application_member_binding(
    db: Session, application: Application, membership_id,
) -> None:
    """给平台成员分配应用角色时，自动补绑该应用的 app.member（已有则跳过）。"""
    member_role = db.scalar(select(Role).where(
        Role.tenant_id == application.tenant_id,
        Role.application_id == application.id,
        Role.key == L4_ROLE_KEY,
        Role.status == "active",
    ))
    if member_role is None:
        return
    existing = db.scalar(select(RoleBinding.id).where(
        RoleBinding.membership_id == membership_id,
        RoleBinding.role_id == member_role.id,
    ))
    if existing:
        return
    db.add(RoleBinding(membership_id=membership_id, role_id=member_role.id))


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
    actor: User,
    db: Session,
) -> None:
    """本应用业务码 + 操作者已有的租户/应用管理码；超出可见集 422。"""
    current_ids = set(db.scalars(select(RolePermission.permission_id).where(
        RolePermission.role_id == role.id,
        RolePermission.resource_id.is_(None),
    )).all())
    proposed = db.scalars(select(Permission).where(
        Permission.id.in_(proposed_permission_ids),
    ).with_for_update()).all() if proposed_permission_ids else []
    if len(proposed) != len(set(proposed_permission_ids)):
        raise HTTPException(422, "权限目录中存在无效权限")
    assert_application_grant_permissions(
        application.permission_namespace,
        proposed,
        current_ids,
        actor_grantable_management_codes(actor, db),
    )


@router.get("/applications/{application_id}/roles")
def list_application_roles(
    application_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """只返回当前应用的自定义应用角色；五级平台模板不出现在工作台。"""
    application = _authorized_application(application_id, actor, db)
    roles = db.scalars(
        select(Role)
        .where(
            Role.tenant_id == application.tenant_id,
            Role.application_id == application.id,
            Role.key.notin_(TEMPLATE_ROLE_KEYS),
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
    if body.key in TEMPLATE_ROLE_KEYS:
        raise HTTPException(422, "不能把系统预置平台角色建成应用角色")
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
    """修改角色名称/描述等基础字段，审计记录仅含变更字段名清单。"""
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
    """行锁下乐观切换角色启停；expected_status 与现状不符返回 409，幂等时直接返回。"""
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
    include_management: Annotated[bool, Query()] = False,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """本应用业务码；include_management 时并上操作者可授的租户/应用管理码。"""
    application = _authorized_application(application_id, actor, db)
    role = _authorized_role(application, role_id, actor, db)
    currently_assigned_ids = set(db.scalars(select(RolePermission.permission_id).where(
        RolePermission.role_id == role.id,
    )).all())
    namespace = application.permission_namespace
    catalog_clauses = [
        and_(
            Permission.status == "active",
            Permission.catalog_namespace == namespace,
            Permission.surface == "business",
        ),
    ]
    grantable = actor_grantable_management_codes(actor, db) if include_management else frozenset()
    if include_management:
        management_filters = [Permission.status == "active", Permission.surface == "management"]
        if grantable is not None:
            management_filters.append(Permission.code.in_(list(grantable) or ["__none__"]))
        catalog_clauses.append(and_(*management_filters))
    if currently_assigned_ids:
        catalog_clauses.append(Permission.id.in_(currently_assigned_ids))
    rows = db.scalars(
        select(Permission)
        .where(or_(*catalog_clauses))
        .order_by(Permission.code)
        .limit(1000)
    ).all()
    payload: list[dict] = []
    for permission in rows:
        assigned = permission.id in currently_assigned_ids
        management = is_management_code(permission.code) or permission.surface == "management"
        if assigned:
            pass
        elif management:
            if not include_management:
                continue
            if grantable is not None and permission.code not in grantable:
                continue
        elif not permission_matches_namespace(permission.code, namespace):
            continue
        payload.append({
            "id": str(permission.id),
            "code": permission.code,
            "catalog_namespace": permission.catalog_namespace,
            "resource_type": permission.resource_type,
            "scope": permission.scope,
            "description": permission.description,
            "status": permission.status,
        })
    return payload


@router.get("/applications/{application_id}/roles/{role_id}/permissions")
def list_application_role_permissions(
    application_id: UUID,
    role_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """列出角色当前的权限授权清单（含实例级 resource_id）。"""
    application = _authorized_application(application_id, actor, db)
    role = _authorized_role(application, role_id, actor, db)
    rows = db.execute(
        select(RolePermission, Permission)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == role.id)
        .order_by(Permission.code, RolePermission.resource_id)
    ).all()
    return [{"id": str(grant.id), "permission_id": str(permission.id),
             "code": permission.code, "description": permission.description,
             "resource_id": grant.resource_id}
            for grant, permission in rows]


@router.post("/applications/{application_id}/roles/{role_id}/permissions/preview")
def preview_application_role_permissions(
    application_id: UUID,
    role_id: UUID,
    body: RolePermissionsPreview,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """预览替换角色权限的影响（授予/回收码、待删数据范围策略），不写库。"""
    application = _authorized_application(application_id, actor, db, manage=True)
    role = _authorized_role(application, role_id, actor, db, manage=True, lock=True)
    _reject_ineligible_application_permissions(application, role, body.permission_ids, actor, db)
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
    """替换角色通用授权：本应用业务码 + 操作者可授的租户/应用管理码。"""
    application = _authorized_application(application_id, actor, db, manage=True)
    role = _authorized_role(application, role_id, actor, db, manage=True, lock=True)
    if not is_application_class_role(role):
        raise HTTPException(422, "平台角色不能在应用工作台挂应用权限")
    _reject_ineligible_application_permissions(application, role, body.permission_ids, actor, db)
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
    role_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """只列出已通过该应用角色取得授权的成员，避免暴露完整租户用户目录。"""
    application = _authorized_application(application_id, actor, db)
    # 角色行「配置成员」只看持有指定应用角色的人，避免分页把别的角色成员夹进来。
    scoped_role = _authorized_role(application, role_id, actor, db) if role_id else None
    direct_memberships = (
        select(RoleBinding.membership_id.label("membership_id"))
        .join(Role, Role.id == RoleBinding.role_id)
        .where(Role.tenant_id == application.tenant_id, Role.application_id == application.id)
    )
    if scoped_role is not None:
        direct_memberships = direct_memberships.where(RoleBinding.role_id == scoped_role.id)
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
    if scoped_role is not None:
        group_memberships = group_memberships.where(Role.id == scoped_role.id)
    # 可见成员 = 应用角色直连绑定 ∪ 活跃用户组继承该应用角色，两者取并集。
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
    """按管理员指定的邮箱绑定现有租户成员；不提供可枚举的候选成员目录。

    判权顺序：先要求应用可读（L3 assign 也需要看到应用），再按 manage/assign
    双层码决定是否允许绑定目标角色；L3 只能任命 key=app.admin。
    """
    application = _authorized_application(application_id, actor, db, manage=False)
    if application.status != "active":
        raise HTTPException(409, "停用应用不能分配新成员")
    role = _authorized_role(application, body.role_id, actor, db, manage=False)
    if role.status != "active":
        raise HTTPException(409, "停用角色不能绑定成员")
    _ensure_app_role_binding_permission(actor, db, application, role)

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
    if existing and not is_application_class_role(role):
        return
    if not existing:
        db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
    # 分配应用角色时自动成为该应用的平台成员。
    if is_application_class_role(role):
        _ensure_application_member_binding(db, application, membership.id)
    elif existing:
        return
    # 绑定即时生效：bump 让目标成员旧 OIDC 凭证失效重签。
    bump_membership_versions(db, [membership.id])
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
    application = _authorized_application(application_id, actor, db, manage=False)
    role = _authorized_role(application, role_id, actor, db, manage=False)
    _ensure_app_role_binding_permission(actor, db, application, role)
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
    # 解绑即时生效：bump 让被撤职成员旧 OIDC 凭证失效。
    bump_membership_versions(db, [membership.id])
    audit(db, actor, request, "application.role.unbind", "user", str(user_id), {
        "tenant_id": str(application.tenant_id),
        "application_id": str(application.id),
        "role_id": str(role.id),
    })
    commit_or_conflict(db)
