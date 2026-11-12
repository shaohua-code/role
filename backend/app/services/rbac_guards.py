"""管理面守卫：菜单/按钮节点判权 + 授权范围（只能向下）数据边界。

三管理员语义（platform.admin 超管 / tenant.admin 租户级 / app.admin 应用级 / app.member 成员）：
- 管理接口主门禁：ensure_codes（节点判权，menu.*/button.*）+ ensure_scope（范围下限）；
- 数据边界：超管全域；租户级限操作者所有租户；应用级限操作者所有应用；
- 权限节点由角色派生，供 GET /auth/me(/capabilities) 裁菜单与按钮；前端码不可信。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import Tenant, TenantMembership, User
from app.services.effective_roles import (
    authorized_role_ids_statement,
    list_effective_roles,
    user_is_platform_admin,
)
from app.services.permission_kinds import (
    BUTTON_CODES,
    MANAGEMENT_NODE_CODES,
    ROLE_SCOPE_APP,
    ROLE_SCOPE_MEMBER,
    ROLE_SCOPE_RANK,
    ROLE_SCOPE_SUPER,
    ROLE_SCOPE_TENANT,
    TEMPLATE_ROLE_SCOPES,
    all_ui_codes,
)
from app.services.role_provisioning import (
    L1_ROLE_KEY,
    L2_ROLE_KEY,
    L3_ROLE_KEY,
    L4_ROLE_KEY,
    is_platform_class_role,
)
# 平台管理租户 slug：capabilities 对非超管排除该租户（平台租户隔离）。
from app.db.seed_greenfield import PLATFORM_TENANT_SLUG

logger = logging.getLogger(__name__)


def effective_role_scope(role: Role) -> str:
    """角色授权范围：roles.scope 列为准；存量空值按模板 key / 钉应用推导。"""
    scope = getattr(role, "scope", None)
    if scope in ROLE_SCOPE_RANK:
        return scope
    if role.key in TEMPLATE_ROLE_SCOPES:
        return TEMPLATE_ROLE_SCOPES[role.key]
    return ROLE_SCOPE_APP if role.application_id is not None else ROLE_SCOPE_TENANT


def operator_scope(user: User, db: Session) -> str:
    """操作者授权范围 = 其全部有效平台角色范围的最高秩（超管 > 租户级 > 应用级 > 成员）。"""
    from app.core.security import is_platform_admin_user

    if is_platform_admin_user(user, db):
        return ROLE_SCOPE_SUPER
    best = ROLE_SCOPE_MEMBER
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all()
    for membership in memberships:
        # 操作者范围看其全部有效角色（含钉应用的应用类角色：L2/L4 的 app.admin/app.member
        # 也参与范围推导）；平台角色全局化后不再按角色租户过滤，跨租户任命的应用角色同样计入。
        roles = db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, membership.tenant_id)),
            Role.status == "active",
        )).all()
        for role in roles:
            if ROLE_SCOPE_RANK.get(effective_role_scope(role), 0) > ROLE_SCOPE_RANK[best]:
                best = effective_role_scope(role)
    return best


def ensure_scope(
    user: User,
    db: Session,
    needed: str,
    *,
    detail: str | None = None,
) -> None:
    """范围只能向下：操作者范围秩低于要求时 403（如应用级不能做租户级操作）。"""
    if ROLE_SCOPE_RANK.get(operator_scope(user, db), 0) >= ROLE_SCOPE_RANK.get(needed, 0):
        return
    raise HTTPException(
        status_code=403,
        detail=detail or f"授权范围不足：需要 {needed} 级及以上",
    )


def scope_at_least(user: User, db: Session, needed: str) -> bool:
    """范围秩比较的布尔版（前端可见性/文案分支用）。"""
    return ROLE_SCOPE_RANK.get(operator_scope(user, db), 0) >= ROLE_SCOPE_RANK.get(needed, 0)


def user_has_management_code(
    user: User,
    db: Session,
    code: str,
    *,
    tenant_id: UUID | None = None,
    application_id: UUID | None = None,
    resource_id: str | None = None,
) -> bool:
    """判定用户是否持某管理面节点（菜单/按钮）；超管平台角色覆盖全部节点（代管）。"""
    if user_is_platform_admin(user, db):
        return True
    statement = select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )
    if tenant_id is not None:
        statement = statement.where(TenantMembership.tenant_id == tenant_id)
    memberships = db.scalars(statement).all()
    for membership in memberships:
        if _membership_has_management_code(
            db, membership, code, application_id=application_id, resource_id=resource_id,
        ):
            return True
    return False


def _membership_has_management_code(
    db: Session,
    membership: TenantMembership,
    code: str,
    *,
    application_id: UUID | None,
    resource_id: str | None,
) -> bool:
    """在单个成员身份上查管理面节点（含应用角色加宽）。"""
    tenant_id = membership.tenant_id
    roles = list_effective_roles(
        db, membership_id=membership.id, tenant_id=tenant_id, application_id=application_id,
    )
    if application_id is None:
        # 加宽：应用角色授予的管理节点在其租户内生效。
        roles = list(roles) + list(db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, tenant_id)),
            Role.status == "active",
            Role.tenant_id == tenant_id,
            Role.application_id.isnot(None),
        )).all())
    if not roles:
        return False
    query = (
        select(Permission.id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(
            RolePermission.role_id.in_([role.id for role in roles]),
            Permission.code == code,
            Permission.status == "active",
            Permission.surface == "management",
        )
    )
    if resource_id is not None:
        query = query.where(
            RolePermission.resource_id.is_(None) | (RolePermission.resource_id == resource_id),
        )
    return db.scalar(query.limit(1)) is not None



# ── 角色门禁（管理台主路径）────────────────────────────────────────────────

def list_actor_roles(user: User, db: Session) -> list[dict]:
    """列出用户全部有效角色（跨活跃成员身份），供 GET /auth/me 返回。

    每项含 key / kind / scope / name / tenant_id / application_id；同一角色 key 可因
    不同租户或应用出现多次。算法复用 authorized_role_ids_statement，与 OIDC 入场一致。
    平台角色全局化：平台类角色跨租户生效，tenant_id 为绑定发生时所在成员身份的租户。
    """
    payload: list[dict] = []
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all()
    for membership in memberships:
        roles = db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, membership.tenant_id)),
            Role.status == "active",
            # 平台类角色全局生效；应用类角色仍要求与成员同租户。
            or_(Role.application_id.is_(None), Role.tenant_id == membership.tenant_id),
        )).all()
        for role in roles:
            payload.append({
                "key": role.key,
                "kind": role.kind,
                "scope": effective_role_scope(role),
                "name": role.name,
                "tenant_id": str(membership.tenant_id),
                "application_id": str(role.application_id) if role.application_id else None,
            })
    return payload


def user_has_any_role(
    user: User,
    db: Session,
    role_keys: Sequence[str],
    *,
    tenant_id: UUID | None = None,
    application_id: UUID | None = None,
) -> bool:
    """是否持有 role_keys 中任一有效角色；可选钉住租户 / 应用作用域。

    - tenant_id 限定成员身份所在租户；
    - application_id 指定时：钉住该应用的角色必须匹配；application_id 为空的租户/平台
      角色若 key 命中也算通过（例如在应用路由上同时允许 tenant.admin）。
    """
    keys = {key for key in role_keys if key}
    if not keys:
        return False
    statement = select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )
    if tenant_id is not None:
        statement = statement.where(TenantMembership.tenant_id == tenant_id)
    memberships = db.scalars(statement).all()
    for membership in memberships:
        roles = db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, membership.tenant_id)),
            Role.status == "active",
            # 平台类角色全局生效；应用类角色仍要求与成员同租户。
            or_(Role.application_id.is_(None), Role.tenant_id == membership.tenant_id),
            Role.key.in_(keys),
        )).all()
        for role in roles:
            if application_id is not None and role.application_id is not None:
                if role.application_id != application_id:
                    continue
            return True
    return False


def ensure_roles(
    user: User,
    db: Session,
    role_keys: Sequence[str],
    *,
    tenant_id: UUID | None = None,
    application_id: UUID | None = None,
    allow_platform_admin: bool = True,
    detail: str | None = None,
) -> None:
    """无匹配角色时 403。超管（及开启时的破窗）在 allow_platform_admin 下直接放行。"""
    from app.core.security import is_platform_admin_user

    if allow_platform_admin and is_platform_admin_user(user, db):
        return
    if user_has_any_role(
        user, db, role_keys, tenant_id=tenant_id, application_id=application_id,
    ):
        return
    raise HTTPException(
        status_code=403,
        detail=detail or f"缺少所需角色：{', '.join(role_keys)}",
    )


def ensure_codes(
    user: User,
    db: Session,
    *codes: str,
    tenant_id: UUID | None = None,
    application_id: UUID | None = None,
    detail: str | None = None,
) -> None:
    """无匹配菜单/按钮节点时 403。超管整段放行；节点编码即判权单元，无模板回退。"""
    from app.core.security import is_platform_admin_user

    if is_platform_admin_user(user, db):
        return
    held = [code for code in codes if code]
    for code in held:
        if user_has_management_code(
            user, db, code, tenant_id=tenant_id, application_id=application_id,
        ):
            return
    raise HTTPException(
        status_code=403,
        detail=detail or f"缺少管理权限：{', '.join(held)}",
    )


def require_roles(
    *role_keys: str,
    allow_platform_admin: bool = True,
) -> Callable:
    """FastAPI Depends 工厂：校验当前用户持有任一角色（平台作用域；无租户参数）。

    租户/应用作用域路由请在 handler 内调用 ensure_roles(..., tenant_id=..., application_id=...)。
    """
    if not role_keys:
        raise ValueError("require_roles 至少需要一个角色 key")

    def dependency(
        user: Annotated[User, Depends(_current_user_dep())],
        db: Annotated[Session, Depends(_db_dep())],
    ) -> User:
        ensure_roles(
            user, db, role_keys, allow_platform_admin=allow_platform_admin,
        )
        return user

    return dependency


def _current_user_dep():
    """惰性返回 current_user 依赖，避免 core.security 与 services 循环导入。"""
    from app.core.security import current_user
    return current_user


def _db_dep():
    """惰性返回数据库会话依赖，规避模块导入期循环引用。"""
    from app.db.session import get_db_session
    return get_db_session


# 敏感写节点：按钮节点全集（写类操作一律经按钮节点收口，防同名自定义角色误扩权）。
SENSITIVE_NODE_CODES: frozenset[str] = frozenset(BUTTON_CODES)


def __getattr__(name: str):
    """旧常量名兼容别名：SENSITIVE_API_CODES 指向按钮节点全集。"""
    if name == "SENSITIVE_API_CODES":
        return SENSITIVE_NODE_CODES
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def list_actor_management_tenant_ids(user: User, db: Session) -> set[UUID] | None:
    """租户级数据边界：None=超管（全域可查）；否则操作者全部活跃成员身份的租户 ID 集合。

    调用方必须把查询范围限制在这些租户内。空集合 = 无任何范围。
    """
    if user_is_platform_admin(user, db):
        return None
    return set(db.scalars(select(TenantMembership.tenant_id).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all())


def actor_has_tenant_admin(user: User, db: Session, *, tenant_id: UUID | None = None) -> bool:
    """是否持有租户管理员角色（超管视为代管通过）。"""
    if user_is_platform_admin(user, db):
        return True
    return user_has_any_role(user, db, (L3_ROLE_KEY,), tenant_id=tenant_id)


def list_actor_bound_application_ids(user: User, db: Session) -> set[UUID]:
    """操作者绑定的应用集合：持有任意钉住该应用的活跃角色（含应用成员/业务角色）。"""
    ids: set[UUID] = set()
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all()
    for membership in memberships:
        rows = db.scalars(select(Role.application_id).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, membership.tenant_id)),
            Role.status == "active",
            Role.tenant_id == membership.tenant_id,
            Role.application_id.isnot(None),
        )).all()
        ids.update(app_id for app_id in rows if app_id is not None)
    return ids


def list_actor_visible_application_ids(user: User, db: Session) -> set[UUID] | None:
    """可见应用集合（应用级数据边界）。None=超管不限制。

    租户级及以上：其全部租户下的应用；应用级：绑定的应用（app.member 绑定即属于）。
    两者并集（用户可能同时持有租户级与应用级角色）。
    """
    if user_is_platform_admin(user, db):
        return None
    visible: set[UUID] = set()
    if scope_at_least(user, db, ROLE_SCOPE_TENANT):
        tenant_ids = list_actor_management_tenant_ids(user, db)
        if tenant_ids:
            visible.update(db.scalars(select(Application.id).where(
                Application.tenant_id.in_(tenant_ids),
            )).all())
    visible.update(list_actor_bound_application_ids(user, db))
    return visible


def actor_grantable_management_codes(user: User, db: Session) -> frozenset[str] | None:
    """操作者可授、因而可在目录看见的管理面节点。None=超管全量。按已挂节点并集。"""
    if user_is_platform_admin(user, db):
        return None
    codes: set[str] = set()
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all()
    for membership in memberships:
        roles = db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, membership.tenant_id)),
            Role.status == "active",
            # 平台类角色全局生效；应用类角色仍要求与成员同租户。
            or_(Role.application_id.is_(None), Role.tenant_id == membership.tenant_id),
        )).all()
        codes.update(_codes_for_roles(db, roles))
    return frozenset(codes)


def list_actor_visible_business_namespaces(user: User, db: Session) -> set[str] | None:
    """可见业务码命名空间。None=超管不限制。"""
    app_ids = list_actor_visible_application_ids(user, db)
    if app_ids is None:
        return None
    if not app_ids:
        return set()
    return set(db.scalars(select(Application.permission_namespace).where(
        Application.id.in_(app_ids),
    )).all())


def assert_actor_can_see_role(user: User, db: Session, role: Role) -> None:
    """角色可见性：范围只能向下（操作者范围秩 ≥ 角色范围秩）且租户/应用在数据边界内。

    平台角色全局化：平台类角色（application_id IS NULL）全局可见，跳过租户边界校验；
    应用类角色仍要求角色租户与应用都在数据边界内。
    """
    if role.application_id is not None:
        ensure_tenant_in_actor_scope(user, db, role.tenant_id)
    if user_is_platform_admin(user, db):
        return
    role_scope = effective_role_scope(role)
    if ROLE_SCOPE_RANK.get(operator_scope(user, db), 0) < ROLE_SCOPE_RANK.get(role_scope, 0):
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.application_id is not None:
        if role.application_id not in list_actor_visible_application_ids(user, db):
            raise HTTPException(status_code=404, detail="角色不存在")


def assert_actor_can_manage_role(user: User, db: Session, role: Role) -> None:
    """角色可管理性：可见（范围只能向下）之外，预置模板仅本级及以上可改授权。"""
    assert_actor_can_see_role(user, db, role)
    if user_is_platform_admin(user, db):
        return
    # 模板角色只能被同级或更高级范围的管理员改授权（应用级不能改租户级模板）。
    if role.key in TEMPLATE_ROLE_SCOPES:
        ensure_scope(
            user, db, effective_role_scope(role),
            detail="不能配置更高级范围预置角色的授权",
        )


def ensure_tenant_in_actor_scope(
    user: User,
    db: Session,
    tenant_id: UUID,
) -> None:
    """非超管用户访问他租户资源时默认拒绝（403）；超管直接放行。"""
    scope = list_actor_management_tenant_ids(user, db)
    if scope is None:
        return
    if tenant_id not in scope:
        raise HTTPException(status_code=403, detail="无权访问该租户范围内的数据")


def user_is_break_glass(user: User) -> bool:
    """灾备破窗：仅当 ALLOW_BOOTSTRAP_EMAIL_BYPASS=true 且邮箱匹配引导账号。

    正常路径恒为 False；开启时写审计应携带 break_glass=true 标记。
    """
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.allow_bootstrap_email_bypass or not settings.bootstrap_admin_email:
        return False
    if getattr(user, "_auth_protocol", None) == "oidc" or not user.email:
        return False
    return user.email.casefold() == settings.bootstrap_admin_email.casefold()


def list_management_capabilities(user: User, db: Session) -> dict:
    """汇总用户全部管理面能力，供 GET /auth/me/capabilities 与前端 consoleMode 使用。

    返回结构：
    {"platform_admin": bool, "scope": "super|tenant|app|member", "platform_codes": [菜单/按钮节点],
     "tenants": [{"tenant_id", "codes", "applications": [{"application_id", "codes"}]}], "roles": [...]}
    """
    from app.services.permission_kinds import all_ui_codes

    platform_admin = user_is_platform_admin(user, db)
    scope = operator_scope(user, db)
    # 超管带上全部菜单/按钮节点，侧栏与写按钮按码裁剪；其余按持有节点并集。
    platform_codes = list(all_ui_codes()) if platform_admin else []

    tenants_payload: list[dict] = []
    membership_statement = select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )
    if not platform_admin:
        # 平台租户隔离：非超管的租户工作台不含平台管理租户（仅超管可为平台租户增删成员）。
        membership_statement = (
            select(TenantMembership)
            .join(Tenant, Tenant.id == TenantMembership.tenant_id)
            .where(
                TenantMembership.user_id == user.id,
                TenantMembership.status == "active",
                Tenant.slug != PLATFORM_TENANT_SLUG,
            )
        )
    memberships = db.scalars(membership_statement).all()
    for membership in memberships:
        if platform_admin:
            tenants_payload.append({
                "tenant_id": str(membership.tenant_id),
                "codes": sorted(all_ui_codes()),
                "applications": [],
            })
            continue
        # 全部有效角色（直连绑定 ∪ 活跃组，含应用角色）——不能只用 list_effective_roles(None)，
        # 否则钉住应用的角色会被排除，capabilities 误判为 no_access。
        # 平台角色全局化：平台类角色不再按角色租户过滤。
        effective_roles = list(db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, membership.tenant_id)),
            Role.status == "active",
            or_(Role.application_id.is_(None), Role.tenant_id == membership.tenant_id),
        )).all())
        # 租户域角色（平台/租户级）授予的节点。
        tenant_codes = _codes_for_roles(db, [
            role for role in effective_roles if role.application_id is None
        ])
        # 应用域角色按钉住的应用归组。
        application_ids = sorted({role.application_id for role in effective_roles if role.application_id is not None})
        applications_payload: list[dict] = []
        for application_id in application_ids:
            app_roles = [
                role for role in effective_roles if role.application_id == application_id
            ]
            applications_payload.append({
                "application_id": str(application_id),
                "codes": _codes_for_roles(db, app_roles),
            })
        # 只有确实持有管理节点才收录条目：纯应用成员不应让前端误入租户控制台。
        if tenant_codes or any(entry["codes"] for entry in applications_payload):
            tenants_payload.append({
                "tenant_id": str(membership.tenant_id),
                "codes": sorted(tenant_codes),
                "applications": [
                    entry for entry in applications_payload if entry["codes"]
                ],
            })
    return {
        "platform_admin": platform_admin,
        "scope": scope,
        "platform_codes": sorted(platform_codes),
        "tenants": tenants_payload,
        "roles": list_actor_roles(user, db),
    }


def _codes_for_roles(db: Session, roles: Iterable[Role]) -> set[str]:
    """批量解析一组角色持有的活跃管理面节点并集（capabilities 汇总用）。"""
    role_ids = [role.id for role in roles]
    if not role_ids:
        return set()
    rows = db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(
            RolePermission.role_id.in_(role_ids),
            Permission.status == "active",
            Permission.surface == "management",
        )
    ).all()
    return {row[0] for row in rows}


# ── auth_version 联动 ────────────────────────────────────────────────────────

def bump_membership_versions(db: Session, membership_ids: Iterable[UUID]) -> int:
    """绑定/解绑/组变更后 bump membership.auth_version，使旧 OIDC 凭证立即失效。"""
    ids = list({membership_id for membership_id in membership_ids if membership_id is not None})
    if not ids:
        return 0
    result = db.execute(
        update(TenantMembership)
        .where(TenantMembership.id.in_(ids))
        .values(auth_version=TenantMembership.auth_version + 1)
    )
    return result.rowcount or 0


def bump_memberships_holding_role(db: Session, role_id: UUID) -> int:
    """角色停用/权限集替换/数据范围替换时，bump 所有持有该角色的活跃成员。

    「持有」含直连 RoleBinding，以及经活跃用户组继承该角色的成员。
    """
    direct_ids = select(RoleBinding.membership_id).where(RoleBinding.role_id == role_id)
    group_ids = (
        select(UserGroupMembership.membership_id)
        .join(UserGroup, UserGroup.id == UserGroupMembership.group_id)
        .join(UserGroupRole, UserGroupRole.group_id == UserGroup.id)
        .where(
            UserGroupRole.role_id == role_id,
            UserGroup.status == "active",
        )
    )
    holder_ids = db.scalars(select(TenantMembership.id).where(
        TenantMembership.status == "active",
        TenantMembership.id.in_(direct_ids.union(group_ids)),
    )).all()
    return bump_membership_versions(db, holder_ids)
