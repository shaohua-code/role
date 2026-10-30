"""绿场五级平台角色的自动预置：租户创建时配 L3，应用创建时配多应用/单应用/成员模板。

权限码常量与 seed_greenfield.py 共用同一份目录语义；判权侧见 rbac_guards。
P405：产品上分两类——五个模板 key 是平台角色；钉应用且非模板 key 的才是应用角色。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.authorization import Permission, Role, RolePermission

# L1 平台超管：全部管理面码（由 seed_greenfield 授予）。
L1_ROLE_KEY = "platform.admin"
# L3 租户组织管理员：当前租户下的一切——应用/业务权限码/模型/主题/审计全域管理 + 组织成员协作；
# 平台权限目录写（rbac.permission.manage）仅 L1；专属边界（account.*/tenant.*/overview）由种子只授 L1。
L3_ROLE_KEY = "tenant.admin"
L3_PERMISSION_CODES: tuple[str, ...] = (
    "org.read",
    "org.manage",
    "org.member.read",
    "org.member.manage",
    "org.group.read",
    "org.group.manage",
    "app.read",
    "app.manage",
    "app.secret.rotate",
    "org.invite.manage",
    "rbac.app_role.assign",
    "rbac.app_role.read",
    "rbac.app_role.manage",
    "rbac.role.read",
    "rbac.permission.read",
    "ops.model.read",
    "ops.model.manage",
    "ops.theme.manage",
    "ops.audit.read",
    "ops.authz.simulate",
)
# G32：存量 L3 可能仍持有该码；预置时显式剥离（_grant_codes 只增不减）。
L3_REVOKED_PERMISSION_CODES: tuple[str, ...] = ("rbac.permission.manage",)
# L2 应用管理员模板：钉死单应用的平台侧管理——应用配置/密钥 + 角色/成员/邀请/组/主题/审计；
# 组织域（organization.*）归 L3，应用生命周期（创建/删除）同样归 L3。不能再任命应用管理员。
L2_ROLE_KEY = "app.admin"
L2_PERMISSION_CODES: tuple[str, ...] = (
    "app.read",
    "app.manage",
    "app.secret.rotate",
    "rbac.app_role.read",
    "rbac.app_role.manage",
    "org.member.read",
    "org.member.manage",
    "org.invite.manage",
    "org.group.read",
    "org.group.manage",
    "ops.theme.manage",
    "ops.audit.read",
    "ops.model.read",
    "rbac.permission.read",
    "ops.authz.simulate",
)
# 多应用管理员：与 L2 同级钉住单个应用，管 N 个应用 = 绑 N 次；比 L2 多任命权。
L2M_ROLE_KEY = "apps.admin"
L2M_PERMISSION_CODES: tuple[str, ...] = L2_PERMISSION_CODES + ("rbac.app_role.assign",)
# L4 应用普通成员模板：平台侧只表示「属于该应用」；业务码/菜单只挂在应用角色上。
L4_ROLE_KEY = "app.member"

# 五个种子模板角色：产品上全部是平台角色。其余钉应用的自定义 key 才是应用角色。
TEMPLATE_ROLE_KEYS: frozenset[str] = frozenset({
    L1_ROLE_KEY, L3_ROLE_KEY, L2M_ROLE_KEY, L2_ROLE_KEY, L4_ROLE_KEY,
})
# 钉住应用的平台管理员（多应用 + 单应用）。
APP_SCOPED_ADMIN_ROLE_KEYS: tuple[str, ...] = (L2M_ROLE_KEY, L2_ROLE_KEY)
# 可进管理台配权的角色（不含应用成员）。
CONSOLE_ADMIN_ROLE_KEYS: tuple[str, ...] = (L3_ROLE_KEY, L2M_ROLE_KEY, L2_ROLE_KEY)
# 授权权码：仍用于文案/能力说明；P405 起不再禁止自定义角色持有，改为「看得见才能配」。
AUTHORITY_MANAGE_CODES: frozenset[str] = frozenset({
    "rbac.app_role.manage",
    "org.member.manage",
    "org.invite.manage",
    "org.group.manage",
})


def is_custom_role(role: Role) -> bool:
    """五个模板 key 之外一律视为自定义角色。"""
    return role.key not in TEMPLATE_ROLE_KEYS


def is_platform_class_role(role: Role) -> bool:
    """产品「平台角色」：五级模板，或未钉应用的自定义租户/平台角色。"""
    return role.key in TEMPLATE_ROLE_KEYS or role.application_id is None


def is_application_class_role(role: Role) -> bool:
    """产品「应用角色」：钉住应用且不是五级平台模板。"""
    return role.application_id is not None and role.key not in TEMPLATE_ROLE_KEYS


def _permission_ids_by_codes(db: Session, codes: tuple[str, ...]) -> dict[str, UUID]:
    """按权限码解析 ID；模板码缺失即报错，防止角色静默缺授权。"""
    rows = db.execute(select(Permission.code, Permission.id).where(Permission.code.in_(codes))).all()
    found = dict(rows)
    missing = sorted(set(codes) - set(found))
    if missing:
        raise RuntimeError(f"权限目录缺少种子码：{', '.join(missing)}（请先运行 seed_greenfield）")
    return found


def _ensure_role(
    db: Session,
    *,
    tenant_id: UUID,
    application_id: UUID | None,
    kind: str,
    key: str,
    name: str,
    description: str,
) -> tuple[Role, bool]:
    """幂等获取或创建角色；唯一键与部分索引保证 (tenant, application, key) 唯一。"""
    statement = select(Role).where(
        Role.tenant_id == tenant_id,
        Role.key == key,
        Role.application_id.is_(None) if application_id is None else Role.application_id == application_id,
    )
    role = db.scalar(statement)
    if role:
        return role, False
    role = Role(
        tenant_id=tenant_id,
        application_id=application_id,
        kind=kind,
        key=key,
        name=name,
        description=description,
    )
    db.add(role)
    db.flush()
    return role, True


def _grant_codes(db: Session, role: Role, codes: tuple[str, ...]) -> None:
    """幂等补齐角色授权；已有授权不重复插入。"""
    existing = set(db.scalars(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id),
    ).all())
    permission_ids = _permission_ids_by_codes(db, codes)
    for code, permission_id in permission_ids.items():
        if permission_id not in existing:
            db.add(RolePermission(role_id=role.id, permission_id=permission_id))


def _revoke_codes(db: Session, role: Role, codes: tuple[str, ...]) -> None:
    """从模板角色剥离已不再属于模板的码；目录缺失时静默跳过。"""
    if not codes:
        return
    permission_ids = set(db.scalars(
        select(Permission.id).where(Permission.code.in_(codes)),
    ).all())
    if not permission_ids:
        return
    db.execute(delete(RolePermission).where(
        RolePermission.role_id == role.id,
        RolePermission.permission_id.in_(permission_ids),
    ))


def provision_tenant_admin_role(db: Session, tenant_id: UUID) -> Role:
    """租户开通时预置 L3 组织管理员角色（幂等）。"""
    role, _ = _ensure_role(
        db, tenant_id=tenant_id, application_id=None, kind="tenant",
        key=L3_ROLE_KEY, name="租户管理员",
        description="L3：当前租户下的一切——应用、业务权限码、模型、主题、组织、成员、用户组、审计；可任命应用管理员。平台权限目录写仍仅 L1",
    )
    _grant_codes(db, role, L3_PERMISSION_CODES)
    from app.services.permission_kinds import extra_ui_codes_for, grant_codes_skip_missing
    grant_codes_skip_missing(db, role.id, extra_ui_codes_for(L3_PERMISSION_CODES))
    # G32：平台目录写仅 L1，存量 L3 上的 rbac.permission.manage 必须剥掉。
    _revoke_codes(db, role, L3_REVOKED_PERMISSION_CODES)
    db.flush()
    return role


def provision_multi_app_admin_role(db: Session, tenant_id: UUID, application_id: UUID) -> Role:
    """应用创建时预置多应用管理员模板（幂等，钉住该应用）。管多个应用需分别绑定。"""
    role, _ = _ensure_role(
        db, tenant_id=tenant_id, application_id=application_id, kind="application",
        key=L2M_ROLE_KEY, name="多应用管理员",
        description="可管理本应用的平台侧配置，并任命该应用的应用管理员；不能新建或删除应用",
    )
    _grant_codes(db, role, L2M_PERMISSION_CODES)
    from app.services.permission_kinds import extra_ui_codes_for, grant_codes_skip_missing
    grant_codes_skip_missing(db, role.id, extra_ui_codes_for(L2M_PERMISSION_CODES))
    db.flush()
    return role


def provision_application_admin_role(db: Session, tenant_id: UUID, application_id: UUID) -> Role:
    """应用创建时预置应用管理员模板角色（幂等，钉住该应用）。"""
    role, _ = _ensure_role(
        db, tenant_id=tenant_id, application_id=application_id, kind="application",
        key=L2_ROLE_KEY, name="应用管理员",
        description="本应用的平台侧管理——配置、密钥、成员与应用角色；不能再任命应用管理员，不能新建应用",
    )
    _grant_codes(db, role, L2_PERMISSION_CODES)
    from app.services.permission_kinds import extra_ui_codes_for, grant_codes_skip_missing
    grant_codes_skip_missing(db, role.id, extra_ui_codes_for(L2_PERMISSION_CODES))
    db.flush()
    return role


def provision_application_member_role(db: Session, tenant_id: UUID, application_id: UUID) -> Role:
    """应用创建时预置应用成员模板（幂等）；不挂业务码，业务权限走应用角色。"""
    role, _ = _ensure_role(
        db, tenant_id=tenant_id, application_id=application_id, kind="application",
        key=L4_ROLE_KEY, name="应用成员",
        description="平台侧表示属于该应用；无管理面码。菜单与按钮由另行绑定的应用角色决定",
    )
    db.flush()
    return role


def provision_application_platform_roles(db: Session, tenant_id: UUID, application_id: UUID) -> tuple[Role, Role, Role]:
    """应用开通时预置三个平台角色模板：多应用管理员、应用管理员、应用成员。"""
    multi = provision_multi_app_admin_role(db, tenant_id, application_id)
    admin = provision_application_admin_role(db, tenant_id, application_id)
    member = provision_application_member_role(db, tenant_id, application_id)
    return multi, admin, member
