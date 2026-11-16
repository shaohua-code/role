"""平台角色模板自动预置与授权范围常量。

三管理员 + 应用成员（授权范围只能向下：超管 > 租户管理员 > 应用管理员）：
- platform.admin 超管（scope=super）：平台所有内容可见；
- tenant.admin 租户管理员（scope=tenant）：当前用户所有租户的数据；
- app.admin 应用管理员（scope=app）：当前用户所有应用的数据；管 N 个应用 = 绑 N 个应用；
- app.member 应用成员（scope=member）：零管理权限，仅表示业务侧成员身份。

权限授予只有菜单/按钮两类节点（menu.* / button.*）；旧 27 接口码与数据码目录已移除。
模板持有节点、授权范围常量与 seed_greenfield / rbac_guards 共用同一份语义。
预置逻辑统一收敛在 :class:`RoleProvisioning` 服务类；
模板 key / 节点清单等常量保留在模块层供测试与前端契约引用。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import Tenant
from app.services.permission_kinds import (
    ROLE_SCOPE_APP,
    ROLE_SCOPE_MEMBER,
    ROLE_SCOPE_SUPER,
    ROLE_SCOPE_TENANT,
    TEMPLATE_ROLE_SCOPES,
)

# L1 平台超管：全部菜单/按钮节点（由 seed_greenfield 授予），授权范围=超管。
L1_ROLE_KEY = "platform.admin"
# L3 租户管理员：当前用户所有租户的数据——应用/组织/成员/用户组/邀请/主题/审计全域管理；
# 平台级治理（建删租户、模型目录写）仅超管。
L3_ROLE_KEY = "tenant.admin"
# L2 应用管理员：当前用户所有应用的数据——应用配置/密钥 + 应用角色/成员 + 主题/审计；
# 不能创建删除应用，不能再任命应用管理员（任命是租户级能力）。
L2_ROLE_KEY = "app.admin"
# L4 应用成员模板：平台侧只表示「属于该应用」；业务码/菜单只挂在应用角色上。
L4_ROLE_KEY = "app.member"

# 四个种子模板角色：产品上全部是平台角色。其余钉应用的自定义 key 才是应用角色。
TEMPLATE_ROLE_KEYS: frozenset[str] = frozenset(TEMPLATE_ROLE_SCOPES)
# 可进管理台配权的角色（不含应用成员）。
CONSOLE_ADMIN_ROLE_KEYS: tuple[str, ...] = (L3_ROLE_KEY, L2_ROLE_KEY)
# 授权权码：仅用于文案/能力说明；配权以「看得见才能配 + 范围只能向下」收口。
AUTHORITY_MANAGE_CODES: frozenset[str] = frozenset({
    "button.app_role.manage",
    "button.users.manage",
    "button.invitations.manage",
    "button.groups.manage",
})

# ── 模板持有的菜单/按钮节点（管理面只有这两类）────────────────────────────

# 租户管理员：全部菜单（平台治理写按钮仅超管）；写按钮不含租户管理/模型写。
L3_GRANT_NODE_CODES: tuple[str, ...] = (
    "menu.overview",
    "menu.organization_workspace",
    "menu.users",
    "menu.invitations",
    "menu.application_workspace",
    "menu.roles",
    "menu.groups",
    "menu.tenants",
    "menu.themes",
    "menu.models",
    "menu.model_usage",
    "menu.audit",
    "menu.authz",
    "button.users.manage",
    "button.org.manage",
    "button.groups.manage",
    "button.invitations.manage",
    "button.apps.manage",
    "button.apps.secret",
    "button.app_role.manage",
    "button.app_role.assign",
    "button.roles.manage",
    "button.themes.manage",
    "button.authz.simulate",
)
# 应用管理员：应用域菜单 + 用户只读 + 角色配置（仅能配应用级）；无组织/租户/模型/邀请/用户组。
L2_GRANT_NODE_CODES: tuple[str, ...] = (
    "menu.overview",
    "menu.users",
    "menu.application_workspace",
    "menu.roles",
    "menu.themes",
    "menu.audit",
    "menu.authz",
    "button.apps.manage",
    "button.apps.secret",
    "button.app_role.manage",
    "button.roles.manage",
    "button.themes.manage",
    "button.authz.simulate",
)

# 存量模板残留的旧接口码 / 已下线目录码：预置时显式剥离（_grant_codes 只增不减）。
LEGACY_REVOKED_NODE_CODES: tuple[str, ...] = (
    "menu.permissions",
    "button.permissions.manage",
    "menu.permission_health",
)


class RoleProvisioning:
    """角色模板预置服务：幂等创建四类平台模板角色并维护其授权节点集。

    全部方法为静态方法（db 会话由调用方传入），保持与原模块函数一一对应的行为。
    """

    @staticmethod
    def is_custom_role(role: Role) -> bool:
        """四个模板 key 之外一律视为自定义角色。"""
        return role.key not in TEMPLATE_ROLE_KEYS

    @staticmethod
    def is_platform_class_role(role: Role) -> bool:
        """产品「平台角色」：四模板，或未钉应用的自定义租户/平台角色。"""
        return role.key in TEMPLATE_ROLE_KEYS or role.application_id is None

    @staticmethod
    def is_application_class_role(role: Role) -> bool:
        """产品「应用角色」：钉住应用且不是平台模板。"""
        return role.application_id is not None and role.key not in TEMPLATE_ROLE_KEYS

    @staticmethod
    def _permission_ids_by_codes(db: Session, codes: tuple[str, ...]) -> dict[str, UUID]:
        """按权限码解析 ID；模板码缺失即报错，防止角色静默缺授权。"""
        rows = db.execute(select(Permission.code, Permission.id).where(Permission.code.in_(codes))).all()
        found = dict(rows)
        missing = sorted(set(codes) - set(found))
        if missing:
            raise RuntimeError(f"权限目录缺少种子码：{', '.join(missing)}（请先运行 seed_greenfield）")
        return found

    @staticmethod
    def _ensure_role(
        db: Session,
        *,
        tenant_id: UUID,
        application_id: UUID | None,
        kind: str,
        key: str,
        name: str,
        description: str,
        scope: str,
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
            scope=scope,
        )
        db.add(role)
        db.flush()
        return role, True

    @staticmethod
    def _grant_codes(db: Session, role: Role, codes: tuple[str, ...]) -> None:
        """幂等补齐角色授权；已有授权不重复插入。"""
        existing = set(db.scalars(
            select(RolePermission.permission_id).where(RolePermission.role_id == role.id),
        ).all())
        permission_ids = RoleProvisioning._permission_ids_by_codes(db, codes)
        for code, permission_id in permission_ids.items():
            if permission_id not in existing:
                db.add(RolePermission(role_id=role.id, permission_id=permission_id))

    @staticmethod
    def _revoke_codes(db: Session, role: Role, codes: tuple[str, ...]) -> None:
        """从模板角色剥离已不再属于模板的节点；目录缺失时静默跳过。"""
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

    @staticmethod
    def PLATFORM_TENANT_ID(db: Session) -> UUID:
        """解析平台管理租户（slug=platform）ID：平台类角色的全局宿主。

        惰性导入 seed_greenfield 常量规避循环导入；租户缺失说明种子未跑，显式报错
        防止把平台角色误挂到业务租户。
        """
        from app.db.seed_greenfield import PLATFORM_TENANT_SLUG

        tenant_id = db.scalar(select(Tenant.id).where(Tenant.slug == PLATFORM_TENANT_SLUG))
        if tenant_id is None:
            raise RuntimeError("平台管理租户不存在：请先运行 seed_greenfield（seed_platform_tenant）")
        return tenant_id

    @staticmethod
    def provision_tenant_admin_role(db: Session, tenant_id: UUID | None = None) -> Role:
        """幂等确保全局唯一的租户管理员角色（宿主平台管理租户，scope=tenant）。

        平台角色全局化后 tenant.admin 全局一份、不再按业务租户预置副本；
        tenant_id 参数仅为兼容旧签名保留，一律忽略。
        """
        del tenant_id  # 全局一份：传入的租户 ID 不再决定角色宿主。
        role, _ = RoleProvisioning._ensure_role(
            db, tenant_id=RoleProvisioning.PLATFORM_TENANT_ID(db), application_id=None, kind="tenant",
            key=L3_ROLE_KEY, name="租户管理员",
            description="租户级：当前用户所有租户的数据——应用、组织、成员、用户组、邀请、主题、审计；可任命应用管理员。建删租户与平台治理仅超管",
            scope=ROLE_SCOPE_TENANT,
        )
        if role.scope != ROLE_SCOPE_TENANT:
            role.scope = ROLE_SCOPE_TENANT
        RoleProvisioning._grant_codes(db, role, L3_GRANT_NODE_CODES)
        RoleProvisioning._revoke_codes(db, role, LEGACY_REVOKED_NODE_CODES)
        db.flush()
        return role

    @staticmethod
    def provision_application_admin_role(db: Session, tenant_id: UUID, application_id: UUID) -> Role:
        """应用创建时预置应用管理员模板角色（幂等，钉住该应用，scope=app）。"""
        role, _ = RoleProvisioning._ensure_role(
            db, tenant_id=tenant_id, application_id=application_id, kind="application",
            key=L2_ROLE_KEY, name="应用管理员",
            description="应用级：当前用户所有应用的数据——本应用配置、密钥、成员与应用角色；不能建删应用，不能再任命应用管理员",
            scope=ROLE_SCOPE_APP,
        )
        if role.scope != ROLE_SCOPE_APP:
            role.scope = ROLE_SCOPE_APP
        RoleProvisioning._grant_codes(db, role, L2_GRANT_NODE_CODES)
        RoleProvisioning._revoke_codes(db, role, LEGACY_REVOKED_NODE_CODES)
        db.flush()
        return role

    @staticmethod
    def provision_application_member_role(db: Session, tenant_id: UUID, application_id: UUID) -> Role:
        """应用创建时预置应用成员模板（幂等）；不挂业务码，业务权限走应用角色。"""
        role, _ = RoleProvisioning._ensure_role(
            db, tenant_id=tenant_id, application_id=application_id, kind="application",
            key=L4_ROLE_KEY, name="应用成员",
            description="平台侧表示属于该应用；无管理面节点。菜单与按钮由另行绑定的应用角色决定",
            scope=ROLE_SCOPE_MEMBER,
        )
        if role.scope != ROLE_SCOPE_MEMBER:
            role.scope = ROLE_SCOPE_MEMBER
        db.flush()
        return role

    @staticmethod
    def provision_application_platform_roles(db: Session, tenant_id: UUID, application_id: UUID) -> tuple[Role, Role]:
        """应用开通时预置两个平台角色模板：应用管理员、应用成员（多应用管理员已并入应用管理员）。"""
        admin = RoleProvisioning.provision_application_admin_role(db, tenant_id, application_id)
        member = RoleProvisioning.provision_application_member_role(db, tenant_id, application_id)
        return admin, member
