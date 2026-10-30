"""角色、权限、绑定与授权模拟管理路由；写入一律按管理面权限码校验。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user, is_platform_admin_user
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import Tenant, TenantMembership, User, UserInvitation
from app.models.organization import RoleDataScope
from app.schemas.access_control import (
    AuthorizationCheck,
    AuthorizationSimulation,
    MembershipRoleBindingsUpdate,
    PermissionCreate,
    PermissionStatusUpdate,
    RoleBindingCreate,
    RoleCloneRequest,
    RoleCreate,
    RolePermissionsPreview,
    RolePermissionsUpdate,
    RoleUpdate,
)
from app.services.authorization import evaluate_access
from app.services.permission_impact import (
    StaleRolePermissionPreview,
    apply_role_permissions,
    preview_role_permissions,
)
from app.services.permission_namespace import (
    assert_role_kind_grant_permissions,
    is_management_code,
    normalize_namespace,
    permission_matches_namespace,
    resolve_permission_namespace,
)
from app.services.rbac_guards import (
    actor_grantable_management_codes,
    actor_has_tenant_admin,
    assert_actor_can_grant_preset_role,
    assert_actor_can_see_role,
    bump_membership_versions,
    bump_memberships_holding_role,
    ensure_roles,
    ensure_tenant_in_actor_scope,
    list_actor_management_tenant_ids,
    list_actor_pinned_application_ids,
    list_actor_visible_application_ids,
    list_actor_visible_business_namespaces,
)
from app.services.role_provisioning import (
    CONSOLE_ADMIN_ROLE_KEYS,
    L1_ROLE_KEY,
    L3_ROLE_KEY,
    L4_ROLE_KEY,
    TEMPLATE_ROLE_KEYS,
    is_application_class_role,
    is_platform_class_role,
)

router = APIRouter(tags=["RBAC 权限管理"])

# 绿场种子保护：L1 平台超管角色不允许停用，避免把唯一管理面入口锁死。
PROTECTED_PLATFORM_ROLE_KEYS = frozenset({"platform.admin"})


@router.post("/authorization/simulate")
def simulate_authorization(body: AuthorizationSimulation, actor: User = Depends(current_user),
                           db: Session = Depends(get_db_session)) -> dict:
    """以当前策略只读预演用户授权；该管理 API 不创建授权记录或审计变更。

    L2/L3 模拟对象限本租户（11 号文档 §4.4）：目标租户不在 actor 管理范围时 403。
    """
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), detail="缺少管理角色（原 ops.authz.simulate）")
    target_user = db.get(User, body.user_id)
    if not target_user:
        raise HTTPException(404, "模拟用户不存在")
    check = AuthorizationCheck(**body.model_dump(exclude={"user_id"}))
    # 范围校验：非 L1 只能预演自己租户内的授权场景，防止跨租户策略探测。
    ensure_tenant_in_actor_scope(actor, db, check.tenant_id)
    evaluation = evaluate_access(check, target_user, db, enforce_token_context=False)
    return {
        "subject": {"user_id": str(target_user.id), "email": target_user.email,
                    "display_name": target_user.display_name, "status": target_user.status},
        "request": {"tenant_id": str(check.tenant_id),
                    "application_id": str(check.application_id) if check.application_id else None,
                    "permission_code": check.permission_code, "resource_id": check.resource_id,
                    "include_data_scope": check.include_data_scope},
        **evaluation,
    }


@router.get("/roles")
def list_roles(q: str | None = Query(default=None, max_length=120),
               kind: str | None = Query(default=None),
               tenant_id: UUID | None = Query(default=None),
               application_id: UUID | None = Query(default=None),
               status: str | None = Query(default=None),
               role_class: Annotated[str | None, Query()] = None,
               limit: Annotated[int, Query(ge=1, le=500)] = 50,
               offset: Annotated[int, Query(ge=0)] = 0,
               actor: User = Depends(current_user),
               db: Session = Depends(get_db_session)) -> dict:
    """角色列表；L3 的 rbac.role.read 只读其租户内角色（非 L1 强制范围过滤）。

    q/kind/tenant_id/application_id/status/role_class 为可选服务端过滤。
    role_class=platform 只出五级模板 + 未钉应用的自定义平台角色；
    role_class=application 只出自定义应用角色。
    """
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), detail="缺少管理角色（原 rbac.role.read）")
    if kind not in (None, "platform", "tenant", "application"):
        raise HTTPException(422, "kind 仅支持 platform、tenant 或 application")
    if status not in (None, "active", "disabled"):
        raise HTTPException(422, "status 仅支持 active 或 disabled")
    if role_class not in (None, "platform", "application"):
        raise HTTPException(422, "role_class 仅支持 platform 或 application")
    tenant_scope = list_actor_management_tenant_ids(actor, db)
    if tenant_scope is not None:
        if not tenant_scope:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}
        # 非 L1：请求的 tenant_id 必须落在自己的管理范围内，防止越租户探测
        if tenant_id is not None and tenant_id not in tenant_scope:
            raise HTTPException(403, "请求的租户不在你的管理范围内")
    statement = select(Role)
    if tenant_scope is not None:
        statement = statement.where(Role.tenant_id.in_(tenant_scope))
        # 纯 L2：默认仍只看钉住应用；平台角色页额外放出本租户自定义平台角色（不含租户管理员模板）。
        if not actor_has_tenant_admin(actor, db):
            pinned = list_actor_pinned_application_ids(actor, db)
            if not pinned:
                return {"items": [], "total": 0, "limit": limit, "offset": offset}
            if application_id is not None and application_id not in pinned:
                return {"items": [], "total": 0, "limit": limit, "offset": offset}
            if role_class == "platform":
                statement = statement.where(
                    or_(
                        and_(
                            Role.key.in_(TEMPLATE_ROLE_KEYS),
                            Role.application_id.in_(pinned),
                        ),
                        and_(
                            Role.application_id.is_(None),
                            Role.key.notin_(TEMPLATE_ROLE_KEYS),
                        ),
                    ),
                )
            else:
                statement = statement.where(
                    Role.kind == "application",
                    Role.application_id.in_(pinned),
                )
    if tenant_id is not None:
        statement = statement.where(Role.tenant_id == tenant_id)
    if application_id is not None:
        statement = statement.where(Role.application_id == application_id)
    if kind:
        statement = statement.where(Role.kind == kind)
    if status:
        statement = statement.where(Role.status == status)
    if role_class == "platform":
        statement = statement.where(or_(Role.key.in_(TEMPLATE_ROLE_KEYS), Role.application_id.is_(None)))
    elif role_class == "application":
        statement = statement.where(
            Role.application_id.isnot(None),
            Role.key.notin_(TEMPLATE_ROLE_KEYS),
        )
    search = q.strip()[:120] if q else ""
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            Role.name.ilike(pattern) | Role.key.ilike(pattern) | Role.description.ilike(pattern),
        )
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(statement.order_by(Role.created_at.desc()).limit(limit).offset(offset)).all()
    # 权限码一次 join 聚合（仅当前结果集角色），修复逐角色查询的 N+1
    grant_rows = db.execute(
        select(RolePermission.role_id, Permission.code)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id.in_([r.id for r in rows])),
    ).all() if rows else []
    codes_by_role: dict[UUID, list[str]] = {}
    for role_id, code in grant_rows:
        codes_by_role.setdefault(role_id, []).append(code)
    items = [{"id": str(r.id), "tenant_id": str(r.tenant_id), "application_id": str(r.application_id) if r.application_id else None,
             "kind": r.kind, "key": r.key, "name": r.name, "description": r.description, "status": r.status,
             "permission_codes": sorted(codes_by_role.get(r.id, []))}
            for r in rows]
    return {"items": items, "total": int(total), "limit": limit, "offset": offset}


@router.get("/roles/{role_id}/holders")
def list_role_holders(role_id: UUID, actor: User = Depends(current_user),
                      db: Session = Depends(get_db_session)) -> dict:
    """G22 角色持有者反查：回答「改/停/删这个角色影响谁」。

    返回直连绑定与经由用户组继承两类来源；组来源标注具体组名（继承语义与
    list_effective_roles 一致：组停用即不生效，因此只统计 active 组）。
    """
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), detail="缺少管理角色（原 rbac.role.read）")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    # P404：非 L1 限本租户；纯 L2 看不到 tenant.admin 或其他应用角色。
    assert_actor_can_see_role(actor, db, role)

    holders: dict[UUID, dict] = {}

    def _record(membership: TenantMembership, user: User, source: str, group_name: str | None) -> None:
        entry = holders.setdefault(membership.id, {
            "user_id": str(user.id), "email": user.email, "display_name": user.display_name,
            "membership_status": membership.status, "sources": [], "via_groups": [],
        })
        if source not in entry["sources"]:
            entry["sources"].append(source)
        if group_name and group_name not in entry["via_groups"]:
            entry["via_groups"].append(group_name)

    direct_rows = db.execute(
        select(TenantMembership, User)
        .join(RoleBinding, RoleBinding.membership_id == TenantMembership.id)
        .join(User, User.id == TenantMembership.user_id)
        .where(RoleBinding.role_id == role_id)
    ).all()
    for membership, user in direct_rows:
        _record(membership, user, "direct", None)
    inherited_rows = db.execute(
        select(TenantMembership, User, UserGroup)
        .join(UserGroupMembership, UserGroupMembership.membership_id == TenantMembership.id)
        .join(UserGroup, UserGroup.id == UserGroupMembership.group_id)
        .join(UserGroupRole, UserGroupRole.group_id == UserGroup.id)
        .join(User, User.id == TenantMembership.user_id)
        .where(UserGroupRole.role_id == role_id, UserGroup.status == "active")
    ).all()
    for membership, user, group in inherited_rows:
        _record(membership, user, "group", group.name)

    return {
        "role": {"id": str(role.id), "key": role.key, "name": role.name,
                 "tenant_id": str(role.tenant_id), "status": role.status},
        "total": len(holders),
        "items": sorted(holders.values(), key=lambda item: (item["display_name"] or "", item["email"] or "")),
    }


@router.post("/roles", status_code=201)
def create_role(body: RoleCreate, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """创建自定义平台角色（前四级管理员）；应用角色请走应用工作台。key 冲突转 409。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), detail="缺少管理角色（原 rbac.role.manage）")
    ensure_tenant_in_actor_scope(actor, db, body.tenant_id)
    if not db.get(Tenant, body.tenant_id): raise HTTPException(404, "租户不存在")
    if body.key in TEMPLATE_ROLE_KEYS:
        raise HTTPException(422, "不能新建系统预置平台角色")
    if body.application_id:
        if not is_platform_admin_user(actor, db):
            raise HTTPException(422, "应用角色请在应用工作台创建")
        app = db.get(Application, body.application_id)
        if not app or app.tenant_id != body.tenant_id: raise HTTPException(422, "应用必须属于所选租户")
    # kind 按 application_id 推导：钉应用即应用角色，否则为租户侧自定义平台角色。
    role = Role(tenant_id=body.tenant_id, application_id=body.application_id,
                kind="application" if body.application_id else "tenant",
                key=body.key, name=body.name, description=body.description)
    db.add(role); flush_or_conflict(db); audit(db, actor, request, "role.create", "role", str(role.id), {"tenant_id": str(role.tenant_id)}); commit_or_conflict(db)
    return {
        "id": str(role.id), "key": role.key, "name": role.name,
        "tenant_id": str(role.tenant_id),
        "application_id": str(role.application_id) if role.application_id else None,
        "kind": role.kind, "status": role.status, "permission_codes": [],
    }


@router.post("/roles/{role_id}/clone", status_code=201)
def clone_role(role_id: UUID, body: RoleCloneRequest, request: Request,
               actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """在源租户和应用范围内原子复制角色；成员绑定和组绑定始终留在源角色。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    # 锁定源角色，使其状态/范围在复制事务中保持稳定，并与角色权限维护采用相同锁顺序。
    source = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    if not source:
        raise HTTPException(404, "角色不存在")

    clone = Role(
        tenant_id=source.tenant_id,
        application_id=source.application_id,
        kind=source.kind,
        key=body.key,
        name=body.name,
        description=body.description,
        # 复制停用角色时不意外恢复访问；管理员可在确认影响后单独启用副本。
        status=source.status,
    )
    db.add(clone)
    flush_or_conflict(db)

    copied_permission_count = 0
    copied_data_scope_count = 0
    if body.copy_authorizations:
        # 仅复制目录当前启用的权限。停用权限的历史授予/数据策略保留在源角色，
        # 但不应被新副本重新引入。锁定权限行可串行化与权限停用操作。
        active_permissions = db.scalars(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == source.id, Permission.status == "active")
            .order_by(Permission.id)
            .with_for_update()
        ).all()
        active_permission_ids = {permission.id for permission in active_permissions}
        if active_permission_ids:
            source_grants = db.scalars(
                select(RolePermission)
                .where(RolePermission.role_id == source.id,
                       RolePermission.permission_id.in_(active_permission_ids))
                .order_by(RolePermission.permission_id, RolePermission.resource_id, RolePermission.id)
            ).all()
            # P405：看得见才能配，克隆不再剥离授权权码。
            copied_grants = [
                RolePermission(role_id=clone.id, permission_id=grant.permission_id,
                               resource_id=grant.resource_id)
                for grant in source_grants
            ]
            db.add_all(copied_grants)
            copied_permission_count = len(copied_grants)

            source_scopes = db.scalars(
                select(RoleDataScope)
                .where(RoleDataScope.role_id == source.id,
                       RoleDataScope.permission_id.in_(active_permission_ids))
                .order_by(RoleDataScope.permission_id)
            ).all()
            # JSON 列使用新列表，避免 ORM 对象之间共享可变组织 ID 集合。
            db.add_all([
                RoleDataScope(
                    tenant_id=clone.tenant_id,
                    role_id=clone.id,
                    permission_id=scope.permission_id,
                    scope_type=scope.scope_type,
                    organization_ids=list(scope.organization_ids or []),
                )
                for scope in source_scopes
            ])
            copied_data_scope_count = len(source_scopes)

    audit(db, actor, request, "role.clone", "role", str(clone.id), {
        "tenant_id": str(clone.tenant_id),
        "application_id": str(clone.application_id) if clone.application_id else None,
        "source_role_id": str(source.id),
        "copy_authorizations": body.copy_authorizations,
        "copied_permission_grant_count": copied_permission_count,
        "copied_data_scope_count": copied_data_scope_count,
        "copied_member_bindings": False,
        "status": clone.status,
    })
    # 角色、授权、数据范围和审计事件在同一事务提交，避免出现半成品副本。
    flush_or_conflict(db)
    commit_or_conflict(db)
    return {
        "id": str(clone.id),
        "source_role_id": str(source.id),
        "tenant_id": str(clone.tenant_id),
        "application_id": str(clone.application_id) if clone.application_id else None,
        "key": clone.key,
        "name": clone.name,
        "status": clone.status,
        "copied_permission_grant_count": copied_permission_count,
        "copied_data_scope_count": copied_data_scope_count,
        "copied_member_bindings": False,
    }


@router.patch("/roles/{role_id}")
def update_role(role_id: UUID, body: RoleUpdate, request: Request,
                actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """只改角色名称和说明，保持 tenant/application/key 与现有授权绑定不变。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(role, field, value)
    audit(db, actor, request, "role.update", "role", str(role.id),
          {"tenant_id": str(role.tenant_id), "updated_fields": sorted(changes)})
    commit_or_conflict(db)
    return {"id": str(role.id), "tenant_id": str(role.tenant_id), "application_id": str(role.application_id) if role.application_id else None,
            "key": role.key, "name": role.name, "description": role.description,
            "updated_fields": sorted(changes)}


@router.patch("/roles/{role_id}/status")
def set_role_status(role_id: UUID, status: str, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """启停角色；停用即时收敛持有者凭证，平台超管角色受种子保护禁止停用。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    if status not in {"active", "disabled"}: raise HTTPException(422, "状态仅支持 active 或 disabled")
    role = db.get(Role, role_id)
    if not role: raise HTTPException(404, "角色不存在")
    # 种子保护：禁止停用 L1 平台超管角色，避免锁死平台管理面。
    if status == "disabled" and role.kind == "platform" and role.key in PROTECTED_PLATFORM_ROLE_KEYS:
        raise HTTPException(422, "平台超管角色为种子保护角色，不允许停用")
    role.status = status
    if status == "disabled":
        # 角色停用后持有者权限即时收敛，必须使其旧 OIDC 凭证失效。
        bump_memberships_holding_role(db, role.id)
    audit(db, actor, request, "role.status.change", "role", str(role.id), {"status": status, "tenant_id": str(role.tenant_id)}); commit_or_conflict(db)
    return {"id": str(role.id), "status": role.status}


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(role_id: UUID, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> None:
    """删除角色：授权/绑定/组分配/数据范围级联清除；未兑换邀请引用该角色时阻塞。

    平台超管角色（platform.admin）为种子保护角色，永久禁止删除。
    """
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    if role.kind == "platform" and role.key in PROTECTED_PLATFORM_ROLE_KEYS:
        raise HTTPException(422, "平台超管角色为种子保护角色，不允许删除")
    # UserInvitation 对角色为 RESTRICT：存在引用该角色的邀请时给出可操作文案而非数据库约束错误。
    invitation_exists = db.scalar(select(UserInvitation.id).where(UserInvitation.role_id == role.id).limit(1))
    if invitation_exists:
        raise HTTPException(409, "该角色仍被成员邀请引用，请先撤销相关邀请再删除")
    # 应用自助注册的默认角色无外键约束，删除角色前手动解除悬挂引用。
    db.execute(update(Application).where(Application.registration_role_id == role.id)
               .values(registration_role_id=None))
    # 删除前 bump 持有者：直连绑定与组继承成员的旧 OIDC 凭证即时失效；绑定随后随角色级联清除。
    bump_memberships_holding_role(db, role.id)
    audit(db, actor, request, "role.delete", "role", str(role.id),
          {"tenant_id": str(role.tenant_id), "key": role.key, "name": role.name})
    db.delete(role)
    commit_or_conflict(db)


@router.put("/role-bindings", status_code=204)
def bind_role(body: RoleBindingCreate, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> None:
    """绑定前同时校验成员与角色的租户归属，阻断跨租户拼接 ID 的越权请求。"""
    ensure_roles(actor, db, [L1_ROLE_KEY, L3_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    ensure_tenant_in_actor_scope(actor, db, body.tenant_id)
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == body.user_id,
                                                           TenantMembership.tenant_id == body.tenant_id,
                                                           TenantMembership.status == "active"))
    role = db.get(Role, body.role_id)
    if not membership or not role or role.tenant_id != body.tenant_id or role.status != "active":
        raise HTTPException(422, "用户成员关系和角色必须有效且属于同一租户")
    if role.key == L1_ROLE_KEY and not is_platform_admin_user(actor, db):
        raise HTTPException(403, "不能任命平台超级管理员")
    if role.key == L3_ROLE_KEY and not is_platform_admin_user(actor, db):
        raise HTTPException(403, "不能任命租户管理员")
    if role.application_id:
        role_app = db.get(Application, role.application_id)
        if not role_app or role_app.tenant_id != body.tenant_id:
            raise HTTPException(422, "角色应用必须属于所选租户")
    existing = db.scalar(select(RoleBinding.id).where(RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id))
    if existing and not is_application_class_role(role):
        return
    if not existing:
        db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
    if is_application_class_role(role) and role.application_id:
        member_role = db.scalar(select(Role).where(
            Role.tenant_id == role.tenant_id,
            Role.application_id == role.application_id,
            Role.key == L4_ROLE_KEY,
            Role.status == "active",
        ))
        if member_role is not None and db.scalar(select(RoleBinding.id).where(
            RoleBinding.membership_id == membership.id, RoleBinding.role_id == member_role.id,
        )) is None:
            db.add(RoleBinding(membership_id=membership.id, role_id=member_role.id))
    elif existing:
        return
    # 绑定变更即时生效：bump 让目标成员旧 OIDC 凭证在下一次请求时失效重签。
    bump_membership_versions(db, [membership.id])
    audit(db, actor, request, "role.bind", "user", str(body.user_id), {"tenant_id": str(body.tenant_id), "role_id": str(role.id)})
    commit_or_conflict(db)


@router.delete("/role-bindings", status_code=204)
def unbind_role(body: RoleBindingCreate, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> None:
    """解绑角色：与绑定对称的平台侧 DELETE API；成功后同样 bump 目标成员版本。"""
    ensure_roles(actor, db, [L1_ROLE_KEY, L3_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    ensure_tenant_in_actor_scope(actor, db, body.tenant_id)
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == body.user_id,
                                                           TenantMembership.tenant_id == body.tenant_id))
    role = db.get(Role, body.role_id)
    if not membership or not role or role.tenant_id != body.tenant_id:
        raise HTTPException(422, "用户成员关系和角色必须属于同一租户")
    result = db.execute(delete(RoleBinding).where(
        RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id,
    ))
    if not result.rowcount:
        raise HTTPException(404, "该成员未绑定此角色")
    bump_membership_versions(db, [membership.id])
    audit(db, actor, request, "role.unbind", "user", str(body.user_id), {"tenant_id": str(body.tenant_id), "role_id": str(role.id)})
    commit_or_conflict(db)




@router.get("/users/{user_id}/role-bindings")
def list_user_role_bindings(
    user_id: UUID,
    tenant_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """列出用户在指定租户下的直接角色绑定（不含用户组继承）。"""
    ensure_roles(actor, db, [L1_ROLE_KEY, L3_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    ensure_tenant_in_actor_scope(actor, db, tenant_id)
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user_id,
        TenantMembership.tenant_id == tenant_id,
    ))
    if not membership:
        raise HTTPException(404, "用户不在该租户")
    rows = db.execute(
        select(Role)
        .join(RoleBinding, RoleBinding.role_id == Role.id)
        .where(
            RoleBinding.membership_id == membership.id,
            Role.tenant_id == tenant_id,
        )
        .order_by(Role.kind, Role.name)
    ).scalars().all()
    return {
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "role_ids": [str(role.id) for role in rows],
        "roles": [
            {
                "id": str(role.id),
                "key": role.key,
                "name": role.name,
                "kind": role.kind,
                "status": role.status,
                "application_id": str(role.application_id) if role.application_id else None,
            }
            for role in rows
        ],
    }


@router.put("/users/{user_id}/role-bindings")
def replace_user_role_bindings(
    user_id: UUID,
    body: MembershipRoleBindingsUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """原子替换成员在指定租户下的直接角色绑定；同一用户可同时持有多个角色。"""
    ensure_roles(actor, db, [L1_ROLE_KEY, L3_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    ensure_tenant_in_actor_scope(actor, db, body.tenant_id)
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user_id,
        TenantMembership.tenant_id == body.tenant_id,
        TenantMembership.status == "active",
    ))
    if not membership:
        raise HTTPException(404, "活跃租户成员不存在")
    roles = []
    if body.role_ids:
        roles = list(db.scalars(select(Role).where(
            Role.id.in_(body.role_ids),
            Role.tenant_id == body.tenant_id,
            Role.status == "active",
        )).all())
        if len(roles) != len(body.role_ids):
            raise HTTPException(422, "角色列表必须全部为该租户下的有效启用角色")
        platform_actor = is_platform_admin_user(actor, db)
        for role in roles:
            if role.key == L1_ROLE_KEY and not platform_actor:
                raise HTTPException(403, "不能任命平台超级管理员")
            if role.key == L3_ROLE_KEY and not platform_actor:
                raise HTTPException(403, "不能任命租户管理员")
            if role.application_id:
                role_app = db.get(Application, role.application_id)
                if not role_app or role_app.tenant_id != body.tenant_id:
                    raise HTTPException(422, "角色应用必须属于所选租户")
        # 分配应用角色时自动补齐该应用的平台成员。
        bound_ids = {role.id for role in roles}
        extra: list[Role] = []
        for role in roles:
            if not is_application_class_role(role) or not role.application_id:
                continue
            member_role = db.scalar(select(Role).where(
                Role.tenant_id == role.tenant_id,
                Role.application_id == role.application_id,
                Role.key == L4_ROLE_KEY,
                Role.status == "active",
            ))
            if member_role is not None and member_role.id not in bound_ids:
                extra.append(member_role)
                bound_ids.add(member_role.id)
        roles = roles + extra
    db.execute(delete(RoleBinding).where(RoleBinding.membership_id == membership.id))
    db.add_all([RoleBinding(membership_id=membership.id, role_id=role.id) for role in roles])
    bump_membership_versions(db, [membership.id])
    audit(db, actor, request, "role.bindings.replace", "user", str(user_id), {
        "tenant_id": str(body.tenant_id),
        "role_ids": [str(role.id) for role in roles],
        "role_count": len(roles),
    })
    commit_or_conflict(db)
    return {
        "user_id": str(user_id),
        "tenant_id": str(body.tenant_id),
        "role_ids": [str(role.id) for role in roles],
        "roles": [
            {
                "id": str(role.id),
                "key": role.key,
                "name": role.name,
                "kind": role.kind,
                "status": role.status,
                "application_id": str(role.application_id) if role.application_id else None,
            }
            for role in roles
        ],
    }


@router.get("/permissions")
def list_permissions(
    actor: User = Depends(current_user),
    catalog_namespace: Annotated[str | None, Query(max_length=100)] = None,
    application_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db_session),
) -> dict:
    """高级管理权限目录：只出平台管理面码。业务码走应用工作台。

    G29 返回 {items,total,limit,offset}；默认 1000 条、上限 1000，total 暴露截断。
    P405：默认为 surface=management；可见码 = 操作者已有管理码。
    """
    del application_id  # 业务码不再从本目录按应用过滤，避免混进平台编码页。
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), detail="缺少管理角色（原 rbac.permission.read）")
    empty = {"items": [], "total": 0, "limit": limit, "offset": offset}
    namespace_filter: str | None = None
    if catalog_namespace:
        namespace_filter = normalize_namespace(catalog_namespace)
        if namespace_filter != "platform":
            return empty

    grantable = actor_grantable_management_codes(actor, db)

    assigned_roles = (
        select(
            RolePermission.permission_id.label("permission_id"),
            func.count(func.distinct(RolePermission.role_id)).label("assigned_role_count"),
        )
        .group_by(RolePermission.permission_id)
        .subquery()
    )
    statement = (
        select(Permission, func.coalesce(assigned_roles.c.assigned_role_count, 0))
        .outerjoin(assigned_roles, assigned_roles.c.permission_id == Permission.id)
        .where(Permission.surface == "management")
    )
    if namespace_filter is not None:
        statement = statement.where(Permission.catalog_namespace == namespace_filter)
    if grantable is not None:
        if not grantable:
            return empty
        statement = statement.where(Permission.code.in_(list(grantable)))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(
        statement.order_by(Permission.catalog_namespace, Permission.code).limit(limit).offset(offset),
    ).all()
    items = [{"id": str(permission.id), "code": permission.code,
             "catalog_namespace": permission.catalog_namespace,
             "resource_type": permission.resource_type, "scope": permission.scope,
             "description": permission.description, "status": permission.status,
             "surface": permission.surface,
             "requires_data_scope": permission.requires_data_scope,
             "assigned_role_count": int(assigned_role_count)}
            for permission, assigned_role_count in rows]
    return {"items": items, "total": int(total), "limit": limit, "offset": offset}


@router.post("/permissions", status_code=201)
def create_permission(body: PermissionCreate, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """在平台目录登记权限；编码必须与 catalog_namespace 匹配（唯一冲突转 409）。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 rbac.permission.manage）")
    catalog_namespace = resolve_permission_namespace(
        code=body.code,
        catalog_namespace=body.catalog_namespace,
    )
    if not permission_matches_namespace(body.code, catalog_namespace):
        raise HTTPException(422, "权限编码与 catalog_namespace 不匹配")
    row = Permission(
        code=body.code.strip(),
        catalog_namespace=catalog_namespace,
        resource_type=body.resource_type.strip(),
        scope=body.scope.strip(),
        description=body.description.strip() if body.description else None,
        surface=body.surface,
        requires_data_scope=body.requires_data_scope,
    )
    db.add(row)
    flush_or_conflict(db)
    audit(db, actor, request, "permission.create", "permission", str(row.id), {
        "code": row.code,
        "catalog_namespace": row.catalog_namespace,
        "surface": row.surface,
        "requires_data_scope": row.requires_data_scope,
    })
    commit_or_conflict(db)
    return {"id": str(row.id), "code": row.code, "catalog_namespace": row.catalog_namespace,
            "resource_type": row.resource_type,
            "scope": row.scope, "status": row.status,
            "surface": row.surface, "requires_data_scope": row.requires_data_scope,
            "assigned_role_count": 0}


@router.patch("/permissions/{permission_id}/status")
def set_permission_status(permission_id: UUID, body: PermissionStatusUpdate, request: Request,
                           actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """停用/恢复稳定权限编码；停用保留历史角色授权并立即从在线判定中排除。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 rbac.permission.manage）")
    permission = db.scalar(select(Permission).where(Permission.id == permission_id).with_for_update())
    if not permission:
        raise HTTPException(404, "权限项不存在")
    if permission.status != body.expected_status:
        raise HTTPException(409, "权限状态已被其他管理员修改，请刷新后重试")

    assigned_role_count = int(db.scalar(
        select(func.count(func.distinct(RolePermission.role_id))).where(
            RolePermission.permission_id == permission.id,
        )
    ) or 0)
    if permission.status == body.status:
        return {"id": str(permission.id), "status": permission.status,
                "assigned_role_count": assigned_role_count,
                "reactivates_existing_grants": permission.status == "active" and assigned_role_count > 0}

    old_status = permission.status
    permission.status = body.status
    if body.status == "disabled":
        # 停用权限即时收敛所有持有该权限授权的角色成员。
        holder_role_ids = db.scalars(select(RolePermission.role_id).where(
            RolePermission.permission_id == permission.id,
        )).all()
        holder_membership_ids = db.scalars(select(RoleBinding.membership_id).where(
            RoleBinding.role_id.in_(holder_role_ids),
        )).all() if holder_role_ids else []
        bump_membership_versions(db, holder_membership_ids)
    audit(db, actor, request, "permission.status.change", "permission", str(permission.id), {
        "code": permission.code,
        "from_status": old_status,
        "to_status": permission.status,
        "retained_role_count": assigned_role_count,
    })
    commit_or_conflict(db)
    return {"id": str(permission.id), "status": permission.status,
            "assigned_role_count": assigned_role_count,
            "reactivates_existing_grants": permission.status == "active" and assigned_role_count > 0}


@router.get("/roles/{role_id}/permissions")
def list_role_permissions(role_id: UUID, actor: User = Depends(current_user),
                          db: Session = Depends(get_db_session)) -> list[dict]:
    """返回角色的通用与资源实例级授权，供管理员准确编辑通用授权集合。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), detail="缺少管理角色（原 rbac.role.read）")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    # P404：非 L1 限本租户；纯 L2 只能读钉住应用的角色授权。
    assert_actor_can_see_role(actor, db, role)
    rows = db.execute(
        select(RolePermission, Permission)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == role_id)
        .order_by(Permission.code, RolePermission.resource_id)
    ).all()
    return [{"id": str(grant.id), "permission_id": str(permission.id), "code": permission.code,
             "description": permission.description, "resource_id": grant.resource_id}
            for grant, permission in rows]


def _assert_role_permission_scope(role: Role, permission_ids: list[UUID], db: Session) -> None:
    """平台角色只挂管理码，应用角色只挂本应用业务码；历史已持有豁免。"""
    current_ids = set(db.scalars(select(RolePermission.permission_id).where(
        RolePermission.role_id == role.id,
        RolePermission.resource_id.is_(None),
    )).all())
    proposed = db.scalars(select(Permission).where(
        Permission.id.in_(permission_ids),
    )).all() if permission_ids else []
    if len(proposed) != len(set(permission_ids)):
        raise HTTPException(422, "权限目录中存在无效权限")
    if is_platform_class_role(role):
        for permission in proposed:
            if permission.id in current_ids:
                continue
            if permission.surface != "management" or not is_management_code(permission.code):
                raise HTTPException(422, f"平台角色不能挂应用权限：{permission.code}")
        # 自定义平台角色按操作者可见集自由搭配；五级模板仍按层级藏码，避免把 L1 专属码写进下级模板。
        if role.key not in TEMPLATE_ROLE_KEYS:
            return
        application_namespace = None
        if role.application_id:
            application = db.get(Application, role.application_id)
            application_namespace = application.permission_namespace if application else None
        assert_role_kind_grant_permissions(
            kind=(
                "platform" if role.key == L1_ROLE_KEY else "tenant" if role.key == L3_ROLE_KEY else "application"
            ),
            application_namespace=application_namespace,
            proposed=proposed,
            current_ids=current_ids,
        )
        return
    application_namespace = None
    if role.application_id:
        application = db.get(Application, role.application_id)
        application_namespace = application.permission_namespace if application else None
    for permission in proposed:
        if permission.id in current_ids:
            continue
        if permission.surface == "management" or is_management_code(permission.code):
            raise HTTPException(422, f"应用角色不能挂平台权限：{permission.code}")
    assert_role_kind_grant_permissions(
        kind="application",
        application_namespace=application_namespace,
        proposed=proposed,
        current_ids=current_ids,
    )


def _assert_actor_grantable_permissions(actor: User, role: Role, permission_ids: list[UUID], db: Session) -> None:
    """新增挂码必须落在操作者已有集合里（看得见才能配）。"""
    current_ids = set(db.scalars(select(RolePermission.permission_id).where(
        RolePermission.role_id == role.id,
        RolePermission.resource_id.is_(None),
    )).all())
    new_ids = [item for item in permission_ids if item not in current_ids]
    if not new_ids:
        return
    grantable = actor_grantable_management_codes(actor, db)
    if grantable is None:
        return
    if is_application_class_role(role):
        return
    new_codes = set(db.scalars(select(Permission.code).where(Permission.id.in_(new_ids))).all())
    forbidden = sorted(code for code in new_codes if code not in grantable)
    if forbidden:
        raise HTTPException(422, f"不能配置你没有的权限：{', '.join(forbidden)}")


@router.post("/roles/{role_id}/permissions/preview")
def preview_role_permission_update(role_id: UUID, body: RolePermissionsPreview,
                                   actor: User = Depends(current_user),
                                   db: Session = Depends(get_db_session)) -> dict:
    """在保存前预演通用授权增删及可能清理的数据范围策略；该接口只读。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), detail="缺少管理角色（原 rbac.role.read）")
    # 读取锁避免预览正在被其它管理请求变更的角色授权集合。
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update(read=True))
    if not role:
        raise HTTPException(404, "角色不存在")
    # P404：非 L1 限本租户；纯 L2 只能预览钉住应用的角色授权。
    assert_actor_can_see_role(actor, db, role)
    assert_actor_can_grant_preset_role(actor, db, role)
    _assert_role_permission_scope(role, body.permission_ids, db)
    _assert_actor_grantable_permissions(actor, role, body.permission_ids, db)
    try:
        return preview_role_permissions(role_id, body.permission_ids, db)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.put("/roles/{role_id}/permissions")
def replace_role_permissions(role_id: UUID, body: RolePermissionsUpdate, request: Request,
                              actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """事务性替换角色通用权限；资源实例级授权不受本表单影响。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), detail="缺少管理角色（原 rbac.role.manage）")
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    assert_actor_can_see_role(actor, db, role)
    if is_application_class_role(role) and not is_platform_admin_user(actor, db):
        raise HTTPException(422, "应用角色请在应用工作台配权")
    assert_actor_can_grant_preset_role(actor, db, role)
    _assert_role_permission_scope(role, body.permission_ids, db)
    _assert_actor_grantable_permissions(actor, role, body.permission_ids, db)
    try:
        impact = apply_role_permissions(
            role_id, body.permission_ids, body.expected_current_permission_ids, db,
        )
    except StaleRolePermissionPreview as error:
        raise HTTPException(409, str(error)) from error
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if not impact["changed"]:
        return impact

    # 权限集替换即时收敛持有者旧凭证。
    bump_memberships_holding_role(db, role_id)
    audit(db, actor, request, "role.permissions.replace", "role", str(role_id), {
        "tenant_id": impact["role"]["tenant_id"],
        "granted_permissions": impact["grant_permission_codes"],
        "revoked_permissions": impact["revoke_permission_codes"],
        "removed_data_scope_policy_count": len(impact["data_scopes_to_delete"]),
    })
    commit_or_conflict(db)
    return {"changed": True, **impact}


@router.put("/roles/{role_id}/permissions/{permission_id}", status_code=204)
def grant_permission(role_id: UUID, permission_id: UUID, request: Request,
                     resource_id: Annotated[str | None, Query(min_length=1, max_length=180)] = None,
                     actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> None:
    """授予角色单条权限（可带资源实例 ID）；已存在则幂等返回，停用权限拒绝新授权。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    # 同一角色授权变更与批量更新串行化，避免并发创建重复授予。
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    permission = db.scalar(select(Permission).where(Permission.id == permission_id).with_for_update())
    if not role or not permission: raise HTTPException(404, "角色或权限不存在")
    if permission.status != "active": raise HTTPException(409, "停用权限不能新增角色授权")
    exists = db.scalar(select(RolePermission.id).where(RolePermission.role_id == role_id, RolePermission.permission_id == permission_id, RolePermission.resource_id == resource_id))
    if exists: return
    db.add(RolePermission(role_id=role_id, permission_id=permission_id, resource_id=resource_id))
    bump_memberships_holding_role(db, role_id)
    audit(db, actor, request, "role.permission.grant", "role", str(role_id), {"permission": permission.code, "resource_id": resource_id}); commit_or_conflict(db)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=204)
def revoke_permission(
    role_id: UUID,
    permission_id: UUID,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
    resource_id: Annotated[str | None, Query(min_length=1, max_length=180)] = None,
) -> None:
    """按资源 ID 精确撤销授权；同一权限仍有其他 grant 时保留数据策略。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 rbac.role.manage）")
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    permission = db.get(Permission, permission_id)
    if not role or not permission: raise HTTPException(404, "角色或权限不存在")
    result = db.execute(delete(RolePermission).where(RolePermission.role_id == role_id,
                                                     RolePermission.permission_id == permission_id,
                                                     RolePermission.resource_id == resource_id))
    if result.rowcount:
        # 通用授权与多个实例授权可以并存；只有最后一条授权撤销时数据策略才失去前置条件。
        remaining_grant = db.scalar(select(RolePermission.id).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        ).limit(1))
        removed_scope_count = 0
        if not remaining_grant:
            removed_scope_count = db.execute(delete(RoleDataScope).where(
                RoleDataScope.role_id == role_id,
                RoleDataScope.permission_id == permission_id,
            )).rowcount or 0
        bump_memberships_holding_role(db, role_id)
        audit(db, actor, request, "role.permission.revoke", "role", str(role_id), {
            "permission": permission.code,
            "resource_id": resource_id,
            "removed_data_scope_policy_count": removed_scope_count,
        })
        commit_or_conflict(db)
