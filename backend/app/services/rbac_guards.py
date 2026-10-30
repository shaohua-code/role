"""管理面守卫：安全边界为有效角色；权限码主要服务前端 capabilities。

四级角色语义（L1 platform / L2 application / L3 tenant / L4 business）：
- 管理台 / 租户台 API 主门禁：ensure_roles / require_roles（带租户/应用作用域）；
- 权限码仍由角色派生，供 GET /auth/me(/capabilities) 裁菜单；前端码不可信；
- ensure_management_permission 保留为过渡期映射（码 → 角色），标为 deprecated。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import TenantMembership, User
from app.services.effective_roles import (
    authorized_role_ids_statement,
    list_effective_roles,
    user_is_platform_admin,
)
from app.services.role_provisioning import (
    APP_SCOPED_ADMIN_ROLE_KEYS,
    CONSOLE_ADMIN_ROLE_KEYS,
    L1_ROLE_KEY,
    L2M_ROLE_KEY,
    L2_PERMISSION_CODES,
    L2_ROLE_KEY,
    L2M_PERMISSION_CODES,
    L3_PERMISSION_CODES,
    L3_ROLE_KEY,
    L4_ROLE_KEY,
    TEMPLATE_ROLE_KEYS,
    is_platform_class_role,
)

# ── 绿场管理面权限码（与 seed_greenfield 保持一致）───────────────────────────
PLATFORM_MANAGEMENT_CODES: tuple[str, ...] = (
    "platform.overview.read",
    "platform.tenant.read",
    "platform.tenant.manage",
    "platform.account.read",
    "platform.account.manage",
    "rbac.permission.read",
    "rbac.permission.manage",
    "rbac.role.read",
    "rbac.role.manage",
    "org.group.read",
    "org.group.manage",
    "org.member.read",
    "org.member.manage",
    "org.read",
    "org.manage",
    "app.read",
    "app.manage",
    "app.secret.rotate",
    "rbac.app_role.read",
    "rbac.app_role.manage",
    "rbac.app_role.assign",
    "org.invite.manage",
    "ops.audit.read",
    "ops.authz.simulate",
    "ops.model.read",
    "ops.model.manage",
    "ops.theme.manage",
)


def user_has_management_code(
    user: User,
    db: Session,
    code: str,
    *,
    tenant_id: UUID | None = None,
    application_id: UUID | None = None,
    resource_id: str | None = None,
) -> bool:
    """判定用户是否持某管理面码；L1 平台角色覆盖全部管理码（代管）。"""
    if user_is_platform_admin(user, db):
        return True
    if tenant_id is None:
        # 未限定租户的平台级码只认 L1；租户级码必须显式给出租户上下文。
        return False
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.status == "active",
    ))
    if not membership:
        return False
    roles = list_effective_roles(
        db, membership_id=membership.id, tenant_id=tenant_id, application_id=application_id,
    )
    if application_id is None:
        # 加宽 L2（11 号文档 §5.3）：应用角色授予的管理面码在其租户内生效。
        # 本函数只判 management surface 码（下方语句硬编码），业务码不会借此跨域泄漏。
        roles = list(roles) + list(db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, tenant_id)),
            Role.status == "active",
            Role.tenant_id == tenant_id,
            Role.application_id.isnot(None),
        )).all())
    if not roles:
        return False
    statement = (
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
        statement = statement.where(
            RolePermission.resource_id.is_(None) | (RolePermission.resource_id == resource_id),
        )
    return db.scalar(statement.limit(1)) is not None



# ── 角色门禁（管理台主路径）────────────────────────────────────────────────

def list_actor_roles(user: User, db: Session) -> list[dict]:
    """列出用户全部有效角色（跨活跃成员身份），供 GET /auth/me 返回。

    每项含 key / kind / name / tenant_id / application_id；同一角色 key 可因不同
    租户或应用出现多次。算法复用 authorized_role_ids_statement，与 OIDC 入场一致。
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
            Role.tenant_id == membership.tenant_id,
        )).all()
        for role in roles:
            payload.append({
                "key": role.key,
                "kind": role.kind,
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
            Role.tenant_id == membership.tenant_id,
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
    """无匹配角色时 403。L1（及开启时的破窗）在 allow_platform_admin 下直接放行。"""
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


# 管理面码 → 角色门禁映射（过渡期；新代码应直接 ensure_roles）。
# L2 模板含人治码，故组织/成员/组/邀请同时接受 app.admin（租户内任一应用）与 tenant.admin。
_PLATFORM_ONLY_CODES = frozenset({
    "platform.overview.read",
    "platform.tenant.read", "platform.tenant.manage",
    "platform.account.read", "platform.account.manage",
    "rbac.permission.manage",
    "rbac.role.manage",
    "ops.model.manage",
})
_TENANT_PEOPLE_CODES = frozenset({
    "org.read", "org.manage",
    "org.member.read", "org.member.manage",
    "org.group.read", "org.group.manage",
    "org.invite.manage",
})
_SHARED_CONSOLE_CODES = frozenset({
    "rbac.permission.read",
    "ops.authz.simulate",
    "ops.model.read",
    "rbac.role.read",
})
_APPLICATION_CODES = frozenset({
    "app.read", "app.manage",
    "app.secret.rotate",
    "rbac.app_role.read", "rbac.app_role.manage",
})
_L2_EXTRA_CODES = frozenset({
    "ops.theme.manage",
    "ops.audit.read",
})
_L3_ASSIGN_CODES = frozenset({
    "rbac.app_role.assign",
})
# 敏感写：角色通过后再轻量校验权限码（防自定义同名角色误扩权时的额外闸门）。
_SENSITIVE_CODE_DUAL_CHECK = frozenset({
    "app.secret.rotate",
})


def _role_keys_for_management_code(code: str) -> tuple[tuple[str, ...], bool, bool]:
    """返回 (role_keys, requires_tenant, prefers_application)。"""
    if code in _PLATFORM_ONLY_CODES:
        return (L1_ROLE_KEY,), False, False
    if code in _TENANT_PEOPLE_CODES:
        return CONSOLE_ADMIN_ROLE_KEYS, True, False
    if code in _SHARED_CONSOLE_CODES:
        return CONSOLE_ADMIN_ROLE_KEYS, True, False
    if code in _APPLICATION_CODES:
        return APP_SCOPED_ADMIN_ROLE_KEYS, True, True
    if code in _L2_EXTRA_CODES:
        return APP_SCOPED_ADMIN_ROLE_KEYS, True, False
    if code in _L3_ASSIGN_CODES:
        return (L3_ROLE_KEY, L2M_ROLE_KEY), True, False
    # 未知管理码：仅 L1，避免静默放行。
    return (L1_ROLE_KEY,), False, False


def ensure_management_permission(
    user: User,
    db: Session,
    code: str,
    *,
    tenant_id: UUID | None = None,
    application_id: UUID | None = None,
    resource_id: str | None = None,
) -> None:
    """Deprecated：按管理码映射到角色门禁；新路由请改用 ensure_roles / require_roles。

    敏感写（如 secret.rotate）在角色通过后仍轻量校验原权限码。
    resource_id 保留签名兼容，角色门禁不再使用。
    """
    del resource_id  # 角色门禁不按 resource_id 细分；资源级业务用 data_scope。
    role_keys, requires_tenant, prefers_application = _role_keys_for_management_code(code)
    # 应用码在无租户且无应用上下文时视为平台级操作（如 trust 标记），只认 L1。
    if prefers_application and application_id is None and tenant_id is None:
        role_keys = (L1_ROLE_KEY,)
    scoped_application = application_id if prefers_application else None
    ensure_roles(
        user,
        db,
        role_keys,
        tenant_id=tenant_id,
        application_id=scoped_application,
        allow_platform_admin=True,
        detail=f"缺少管理角色（原权限码 {code}）",
    )
    if code in _SENSITIVE_CODE_DUAL_CHECK:
        # 轻量码 check：角色通过后仍要求该码存在于有效角色授权（模板 L2 含 rotate）。
        if not user_has_management_code(
            user, db, code, tenant_id=tenant_id, application_id=application_id,
        ):
            # L1 / 破窗已在 ensure_roles 放行；此处仅约束非平台身份。
            from app.core.security import is_platform_admin_user
            if not is_platform_admin_user(user, db):
                raise HTTPException(status_code=403, detail=f"缺少管理权限：{code}")


def list_actor_management_tenant_ids(user: User, db: Session) -> set[UUID] | None:
    """无租户锚 API 的范围过滤器（11 号文档 §6 要点 4）。

    返回 None 表示 L1 平台角色（全域可查）；否则返回该用户全部活跃成员身份的
    租户 ID 集合，调用方必须把查询范围限制在这些租户内。空集合 = 无任何范围。
    """
    if user_is_platform_admin(user, db):
        return None
    return set(db.scalars(select(TenantMembership.tenant_id).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all())


def actor_has_tenant_admin(user: User, db: Session, *, tenant_id: UUID | None = None) -> bool:
    """是否持有 L3 tenant.admin（L1 视为代管通过）。"""
    if user_is_platform_admin(user, db):
        return True
    return user_has_any_role(user, db, (L3_ROLE_KEY,), tenant_id=tenant_id)


def list_actor_pinned_application_ids(user: User, db: Session) -> set[UUID]:
    """多应用/应用管理员钉住的应用 ID；不含应用成员与自定义应用角色。"""
    ids: set[UUID] = set()
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all()
    for membership in memberships:
        roles = db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, membership.tenant_id)),
            Role.status == "active",
            Role.tenant_id == membership.tenant_id,
            Role.key.in_(APP_SCOPED_ADMIN_ROLE_KEYS),
            Role.application_id.isnot(None),
        )).all()
        for role in roles:
            if role.application_id is not None:
                ids.add(role.application_id)
    return ids


def list_actor_visible_application_ids(user: User, db: Session) -> set[UUID] | None:
    """可见应用集合。None=L1 不限制；L3=本租户全部应用；L2=钉住应用。"""
    if user_is_platform_admin(user, db):
        return None
    tenant_scope = list_actor_management_tenant_ids(user, db)
    if not tenant_scope:
        return set()
    if user_has_any_role(user, db, (L3_ROLE_KEY,)):
        return set(db.scalars(select(Application.id).where(
            Application.tenant_id.in_(tenant_scope),
        )).all())
    return list_actor_pinned_application_ids(user, db)


def actor_grantable_management_codes(user: User, db: Session) -> frozenset[str] | None:
    """操作者可授、因而可在目录看见的管理面码。None=L1 全量。P405 按已有身份并集。"""
    if user_is_platform_admin(user, db):
        return None
    codes: set[str] = set()
    if user_has_any_role(user, db, (L3_ROLE_KEY,)):
        codes.update(L3_PERMISSION_CODES)
    if user_has_any_role(user, db, (L2M_ROLE_KEY,)):
        codes.update(L2M_PERMISSION_CODES)
    if user_has_any_role(user, db, (L2_ROLE_KEY,)):
        codes.update(L2_PERMISSION_CODES)
    return frozenset(codes)


def list_actor_visible_business_namespaces(user: User, db: Session) -> set[str] | None:
    """可见业务码命名空间。None=L1 不限制。"""
    app_ids = list_actor_visible_application_ids(user, db)
    if app_ids is None:
        return None
    if not app_ids:
        return set()
    return set(db.scalars(select(Application.permission_namespace).where(
        Application.id.in_(app_ids),
    )).all())


def assert_actor_can_see_role(user: User, db: Session, role: Role) -> None:
    """角色深链可见性：非 L1 限本租户；L3 本租户全可见；L2 钉住应用模板 + 自定义平台角色。"""
    ensure_tenant_in_actor_scope(user, db, role.tenant_id)
    if user_is_platform_admin(user, db):
        return
    if actor_has_tenant_admin(user, db, tenant_id=role.tenant_id):
        return
    pinned = list_actor_pinned_application_ids(user, db)
    if is_platform_class_role(role) and role.key not in TEMPLATE_ROLE_KEYS:
        return
    if role.application_id in pinned:
        return
    raise HTTPException(status_code=404, detail="角色不存在")


# 预置模板只允许本级及以下管理员改授权，禁止改上级模板（避免整表替换抽空上级码）。
PRESET_ROLE_GRANT_ACTORS: dict[str, tuple[str, ...]] = {
    L1_ROLE_KEY: (L1_ROLE_KEY,),
    L3_ROLE_KEY: (L1_ROLE_KEY, L3_ROLE_KEY),
    L2M_ROLE_KEY: (L1_ROLE_KEY, L3_ROLE_KEY, L2M_ROLE_KEY),
    L2_ROLE_KEY: (L1_ROLE_KEY, L3_ROLE_KEY, L2M_ROLE_KEY, L2_ROLE_KEY),
    L4_ROLE_KEY: (L1_ROLE_KEY, L3_ROLE_KEY, L2M_ROLE_KEY, L2_ROLE_KEY),
}


def assert_actor_can_grant_preset_role(user: User, db: Session, role: Role) -> None:
    """预置角色：四个管理员可改本级及以下；往上的模板 403。码集仍由看得见才能配收口。"""
    if role.key not in TEMPLATE_ROLE_KEYS:
        return
    if user_is_platform_admin(user, db):
        return
    allowed = PRESET_ROLE_GRANT_ACTORS.get(role.key, (L1_ROLE_KEY,))
    if user_has_any_role(user, db, allowed):
        return
    raise HTTPException(status_code=403, detail="不能配置上级预置角色的授权")


def ensure_tenant_in_actor_scope(
    user: User,
    db: Session,
    tenant_id: UUID,
) -> None:
    """非 L1 用户访问他租户资源时默认拒绝（403）；L1 直接放行。"""
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
    {"platform_admin": bool, "platform_codes": [...],
     "tenants": [{"tenant_id", "codes", "applications": [{"application_id", "codes"}]}]}
    """
    platform_admin = user_is_platform_admin(user, db)
    platform_codes = list(PLATFORM_MANAGEMENT_CODES) if platform_admin else []

    tenants_payload: list[dict] = []
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all()
    for membership in memberships:
        if platform_admin:
            tenants_payload.append({
                "tenant_id": str(membership.tenant_id),
                "codes": sorted(PLATFORM_MANAGEMENT_CODES),
                "applications": [],
            })
            continue
        # 全部有效角色（直连绑定 ∪ 活跃组，含应用角色）——不能只用 list_effective_roles(None)，
        # 否则 L2 钉住应用的角色会被排除，capabilities 误判为 no_access。
        effective_roles = list(db.scalars(select(Role).where(
            Role.id.in_(authorized_role_ids_statement(membership.id, membership.tenant_id)),
            Role.status == "active",
            Role.tenant_id == membership.tenant_id,
        )).all())
        # 租户域角色（L3）授予的码；平台角色仅存在于平台租户，业务租户天然不出现。
        tenant_codes = _codes_for_roles(db, [
            role for role in effective_roles
            if role.application_id is None and role.kind in ("platform", "tenant")
        ])
        # 应用域角色（L2/业务自定义管理角色）按钉住的应用归组。
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
        # 只有确实持有管理码才收录条目：L4 纯业务角色不应让前端误入租户控制台（规格 §4.4 no_access）。
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
        "platform_codes": sorted(platform_codes),
        "tenants": tenants_payload,
        "roles": list_actor_roles(user, db),
    }


def _codes_for_roles(db: Session, roles: Iterable[Role]) -> set[str]:
    """批量解析一组角色持有的活跃管理面码并集（capabilities 汇总用）。"""
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

    「持有」含直连 RoleBinding，以及经活跃用户组继承该角色的成员（规格 §2.3）。
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

