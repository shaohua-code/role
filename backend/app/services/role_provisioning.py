"""绿场四级角色的自动预置：租户创建时配 L3，应用创建时配 L2 模板。

权限码常量与 seed_greenfield.py 共用同一份目录语义；判权侧见 rbac_guards。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authorization import Permission, Role, RolePermission

# L1 平台超管：全部管理面码（由 seed_greenfield 授予）。
L1_ROLE_KEY = "platform.admin"
# L3 租户组织管理员：当前租户下的一切——应用/权限码/模型/主题/审计全域管理 + 组织成员协作；
# 专属边界（user.*/tenant.*/platform.overview.read）由种子只授 L1 保证。
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
    "rbac.permission.manage",
    "ops.model.read",
    "ops.model.manage",
    "ops.theme.manage",
    "ops.audit.read",
    "ops.authz.simulate",
)
# L2 应用管理员模板：钉死单应用的一切相关管理——应用配置/密钥 + 角色/成员/邀请/组/主题/审计；
# 组织域（organization.*）归 L3，应用生命周期（创建/删除）同样归 L3。
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
# L4 应用普通成员模板：不携带任何管理面码，业务码由应用管理员另行授予。
L4_ROLE_KEY = "app.member"

# 四个种子模板角色的 key：key 命中即模板角色，否则视为业务自定义角色（如 L2 创建的「管理员」）。
TEMPLATE_ROLE_KEYS: frozenset[str] = frozenset({
    L1_ROLE_KEY, L3_ROLE_KEY, L2_ROLE_KEY, L4_ROLE_KEY,
})
# 授权权码：改变「谁有什么权限」的元权限。自定义角色强制不可持有（管理员不能管理管理员）；
# 模板角色不受限（L2/L3 本身就是授权者的来源）。
AUTHORITY_MANAGE_CODES: frozenset[str] = frozenset({
    "rbac.app_role.manage",
    "org.member.manage",
    "org.invite.manage",
    "org.group.manage",
})


def is_custom_role(role: Role) -> bool:
    """模板角色（四级固定 key）之外的一律视为业务自定义角色。"""
    return role.key not in TEMPLATE_ROLE_KEYS


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


def provision_tenant_admin_role(db: Session, tenant_id: UUID) -> Role:
    """租户开通时预置 L3 组织管理员角色（幂等）。"""
    role, _ = _ensure_role(
        db, tenant_id=tenant_id, application_id=None, kind="tenant",
        key=L3_ROLE_KEY, name="租户管理员",
        description="L3：当前租户下的一切——应用、权限码、模型、主题、组织、成员、用户组、审计；可任命应用管理员",
    )
    _grant_codes(db, role, L3_PERMISSION_CODES)
    db.flush()
    return role


def provision_application_admin_role(db: Session, tenant_id: UUID, application_id: UUID) -> Role:
    """应用创建时预置 L2 应用管理员模板角色（幂等，钉住该应用）。"""
    role, _ = _ensure_role(
        db, tenant_id=tenant_id, application_id=application_id, kind="application",
        key=L2_ROLE_KEY, name="应用管理员",
        description="L2：本应用的一切——配置、密钥轮换、角色、成员、邀请、用户组、主题与审计",
    )
    _grant_codes(db, role, L2_PERMISSION_CODES)
    db.flush()
    return role


def provision_application_member_role(db: Session, tenant_id: UUID, application_id: UUID) -> Role:
    """应用创建时预置 L4 普通成员角色（幂等）；业务码与数据范围由管理员后续授予。"""
    role, _ = _ensure_role(
        db, tenant_id=tenant_id, application_id=application_id, kind="application",
        key=L4_ROLE_KEY, name="应用成员",
        description="L4：无管理面码；可被授予业务权限与数据范围",
    )
    db.flush()
    return role
