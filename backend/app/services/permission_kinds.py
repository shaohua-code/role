"""权限目录：管理面只有一棵「菜单 → 按钮」树；业务面（应用工作台）保持业务码 + 数据叶子。

三管理员授权范围（只能向下：超管 > 租户级 > 应用级；member 不参与配权）：
- super 超管：平台所有内容可见；
- tenant 租户级：当前用户所有租户的数据；
- app 应用级：当前用户所有应用的数据。

menu.* / button.* 节点编码同时是后端判权单元：侧栏认菜单节点，页内写按钮与
接口映射认按钮节点；每个节点带 min_scope 授权下限（只能授予不低于自身范围的角色）。
目录函数统一收敛在 :class:`PermissionCatalog`；目录数据（MENU_CATALOG/BUTTON_CATALOG/
各范围常量）保留在模块层，作为前后端共用的权威码表。
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authorization import Permission, RolePermission
from app.services.permission_namespace import derive_catalog_namespace_value

logger = logging.getLogger(__name__)

# ── 授权范围常量（角色表 roles.scope；只能向下继承）─────────────────────────
ROLE_SCOPE_SUPER = "super"
ROLE_SCOPE_TENANT = "tenant"
ROLE_SCOPE_APP = "app"
ROLE_SCOPE_MEMBER = "member"
# 范围秩：数值越大权限越大；比较一律用秩，不比字符串。
ROLE_SCOPE_RANK: dict[str, int] = {
    ROLE_SCOPE_MEMBER: 0,
    ROLE_SCOPE_APP: 1,
    ROLE_SCOPE_TENANT: 2,
    ROLE_SCOPE_SUPER: 3,
}
ROLE_SCOPE_LABELS: dict[str, str] = {
    ROLE_SCOPE_SUPER: "超管",
    ROLE_SCOPE_TENANT: "租户级",
    ROLE_SCOPE_APP: "应用级",
    ROLE_SCOPE_MEMBER: "成员",
}
# 配权下拉可选范围（应用成员不参与配权）。
GRANTABLE_ROLE_SCOPES: tuple[str, ...] = (ROLE_SCOPE_SUPER, ROLE_SCOPE_TENANT, ROLE_SCOPE_APP)
# 四个模板角色的固定范围。
TEMPLATE_ROLE_SCOPES: dict[str, str] = {
    "platform.admin": ROLE_SCOPE_SUPER,
    "tenant.admin": ROLE_SCOPE_TENANT,
    "app.admin": ROLE_SCOPE_APP,
    "app.member": ROLE_SCOPE_MEMBER,
}

DATA_SCOPE_TYPES: tuple[str, ...] = (
    "self",
    "organization",
    "organization_tree",
    "selected_organizations",
    "tenant",
)

DATA_SCOPE_LABELS: dict[str, str] = {
    "self": "本人",
    "organization": "本组织",
    "organization_tree": "组织及下级",
    "selected_organizations": "指定组织",
    "tenant": "本租户",
}

# 菜单节点 ↔ 现网侧栏；(编码, 名称, min_scope 授权下限)。
# min_scope 语义：持有该节点的角色的授权范围不得低于该值（只能向下）。
MENU_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("menu.overview", "运营总览", ROLE_SCOPE_APP),
    ("menu.organization_workspace", "组织工作台", ROLE_SCOPE_TENANT),
    ("menu.users", "用户管理", ROLE_SCOPE_APP),
    ("menu.invitations", "成员邀请", ROLE_SCOPE_TENANT),
    ("menu.application_workspace", "应用工作台", ROLE_SCOPE_APP),
    ("menu.roles", "平台角色", ROLE_SCOPE_APP),
    ("menu.groups", "用户组", ROLE_SCOPE_TENANT),
    ("menu.tenants", "租户管理", ROLE_SCOPE_TENANT),
    ("menu.themes", "登录主题", ROLE_SCOPE_APP),
    ("menu.models", "模型治理", ROLE_SCOPE_APP),
    ("menu.model_usage", "模型用量", ROLE_SCOPE_APP),
    ("menu.audit", "审计日志", ROLE_SCOPE_APP),
    ("menu.authz", "鉴权模拟", ROLE_SCOPE_APP),
)

# 按钮节点按页收口，挂在对应菜单下；(编码, 名称, min_scope)。
BUTTON_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("button.users.manage", "用户写操作", ROLE_SCOPE_TENANT),
    ("button.tenants.manage", "租户写操作", ROLE_SCOPE_SUPER),
    ("button.roles.manage", "平台角色写操作", ROLE_SCOPE_APP),
    ("button.org.manage", "组织写操作", ROLE_SCOPE_TENANT),
    ("button.groups.manage", "用户组写操作", ROLE_SCOPE_TENANT),
    ("button.invitations.manage", "邀请写操作", ROLE_SCOPE_TENANT),
    ("button.apps.manage", "应用写操作", ROLE_SCOPE_APP),
    ("button.apps.secret", "轮换应用密钥", ROLE_SCOPE_APP),
    ("button.app_role.manage", "应用角色写操作", ROLE_SCOPE_APP),
    # 任命应用管理员是租户级能力（应用级不能向上）。
    ("button.app_role.assign", "任命应用管理员", ROLE_SCOPE_TENANT),
    ("button.models.manage", "模型写操作", ROLE_SCOPE_SUPER),
    # 模型三级分发：租户管理员在应用工作台把本租户收到的模型下发 / 回收给应用。
    ("button.models.distribute", "模型分发", ROLE_SCOPE_TENANT),
    ("button.themes.manage", "登录主题写操作", ROLE_SCOPE_APP),
    ("button.authz.simulate", "执行鉴权模拟", ROLE_SCOPE_APP),
)

# 菜单 → 按钮。
MENU_BUTTONS: dict[str, tuple[str, ...]] = {
    "menu.organization_workspace": ("button.org.manage",),
    "menu.users": ("button.users.manage",),
    "menu.invitations": ("button.invitations.manage",),
    "menu.application_workspace": (
        "button.apps.manage", "button.apps.secret",
        "button.app_role.manage", "button.app_role.assign",
        "button.models.distribute",
    ),
    "menu.roles": ("button.roles.manage",),
    "menu.groups": ("button.groups.manage",),
    "menu.tenants": ("button.tenants.manage",),
    "menu.themes": ("button.themes.manage",),
    "menu.models": ("button.models.manage",),
    "menu.authz": ("button.authz.simulate",),
}

MENU_CODES: tuple[str, ...] = tuple(item[0] for item in MENU_CATALOG)
BUTTON_CODES: tuple[str, ...] = tuple(item[0] for item in BUTTON_CATALOG)
# 管理面判权节点全集（菜单 + 按钮）。
MANAGEMENT_NODE_CODES: tuple[str, ...] = MENU_CODES + BUTTON_CODES
NODE_MIN_SCOPE: dict[str, str] = {
    **{code: min_scope for code, _title, min_scope in MENU_CATALOG},
    **{code: min_scope for code, _title, min_scope in BUTTON_CATALOG},
}

# 与侧栏 NAV_GROUPS 同形；运营总览单独置顶，不进带标题分组。
MENU_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("identity", "身份与组织", ("menu.organization_workspace", "menu.users", "menu.invitations")),
    ("access", "应用与权限", ("menu.application_workspace",)),
    ("advanced", "高级管理", ("menu.roles", "menu.groups")),
    ("platform", "平台治理", ("menu.tenants", "menu.themes", "menu.models", "menu.model_usage")),
    ("ops", "审计与验证", ("menu.authz", "menu.audit")),
)

KIND_LABELS: dict[str, str] = {
    "menu": "菜单",
    "button": "按钮",
    "data": "数据权限",
    "api": "接口",
}

# 仅超管可见/可授的菜单（授权下限=super 的派生视图）。
L1_ONLY_MENU_CODES: frozenset[str] = frozenset(
    code for code, _title, min_scope in MENU_CATALOG if min_scope == ROLE_SCOPE_SUPER
)


class PermissionCatalog:
    """权限目录服务：种类判定、范围校验、种子写入与菜单/按钮树构建。

    全部方法为静态方法（db 会话由调用方传入），保持与原模块函数一一对应的行为。
    """

    @staticmethod
    def infer_permission_kind(code: str) -> str:
        """前缀兜底推断（迁移兼容专用）：menu.* / button.* / *.scope.{范围} / 其余为接口。

        仅服务一种场景：存量行 permissions.kind 列为空（未回填）时由 permission_kind_of
        兜底调用。库列 kind 是唯一事实源；业务面仍会登记 api 类业务码。
        """
        cleaned = code.strip()
        if cleaned.startswith("menu."):
            return "menu"
        if cleaned.startswith("button."):
            return "button"
        parent, scope_type = PermissionCatalog.split_data_scope_code(cleaned)
        if parent and scope_type:
            return "data"
        return "api"

    @staticmethod
    def permission_kind_of(item: dict | Permission) -> str:
        """种类判定单一入口：库列 permissions.kind 为准；仅当行为空（或脏值不在四类）时
        按前缀兜底（迁移兼容，见 infer_permission_kind）。
        """
        if isinstance(item, dict):
            kind = item.get("kind")
            code = item.get("code") or ""
        else:
            kind = getattr(item, "kind", None)
            code = getattr(item, "code", "") or ""
        if kind in KIND_LABELS:
            return kind
        return PermissionCatalog.infer_permission_kind(code)

    @staticmethod
    def split_data_scope_code(code: str) -> tuple[str | None, str | None]:
        """把 appa.doc.read.scope.self 拆成业务码 + 范围类型。"""
        marker = ".scope."
        if marker not in code:
            return None, None
        parent, scope_type = code.rsplit(marker, 1)
        if scope_type in DATA_SCOPE_TYPES and parent:
            return parent, scope_type
        return None, None

    @staticmethod
    def data_scope_code(permission_code: str, scope_type: str) -> str:
        """业务码对应的数据权限叶子编码。"""
        return f"{permission_code}.scope.{scope_type}"

    @staticmethod
    def node_allows_scope(code: str, scope: str) -> bool:
        """节点授权下限校验：持有/授予该节点的角色范围秩不得低于 min_scope。"""
        needed = ROLE_SCOPE_RANK.get(NODE_MIN_SCOPE.get(code, ROLE_SCOPE_APP), 0)
        return ROLE_SCOPE_RANK.get(scope, 0) >= needed

    @staticmethod
    def effective_role_scope_label(role_or_scope: object) -> str:
        """范围中文标签：接受范围字符串或带 scope 的角色对象（未知值原样返回）。"""
        scope = getattr(role_or_scope, "scope", role_or_scope)
        return ROLE_SCOPE_LABELS.get(scope, scope)

    @staticmethod
    def all_ui_codes() -> tuple[str, ...]:
        return MANAGEMENT_NODE_CODES

    @staticmethod
    def ensure_data_scope_children(db: Session, parent: Permission) -> int:
        """业务码强制范围时补齐 5 个数据叶子；已有则跳过。"""
        if parent.surface != "business" or not parent.requires_data_scope:
            return 0
        if PermissionCatalog.permission_kind_of(parent) != "api":
            return 0
        created = 0
        namespace = parent.catalog_namespace
        for scope_type in DATA_SCOPE_TYPES:
            code = PermissionCatalog.data_scope_code(parent.code, scope_type)
            existing = db.scalar(select(Permission).where(Permission.code == code))
            if existing is not None:
                continue
            db.add(Permission(
                code=code,
                catalog_namespace=namespace,
                resource_type="data",
                scope=scope_type,
                description=f"{parent.description or parent.code} · {DATA_SCOPE_LABELS[scope_type]}",
                surface="business",
                requires_data_scope=False,
                kind="data",
            ))
            created += 1
        if created:
            db.flush()
        return created

    @staticmethod
    def seed_ui_permissions(db: Session) -> int:
        """幂等写入菜单/按钮节点，并回填 kind；已下线节点（权限编码页）不再创建。"""
        created = 0
        for code, title, _min_scope in MENU_CATALOG + BUTTON_CATALOG:
            permission = db.scalar(select(Permission).where(Permission.code == code))
            kind = "menu" if code.startswith("menu.") else "button"
            if permission is not None:
                if getattr(permission, "kind", None) != kind:
                    permission.kind = kind
                if not permission.description:
                    permission.description = title
                continue
            db.add(Permission(
                code=code,
                catalog_namespace=derive_catalog_namespace_value(code),
                resource_type=kind,
                scope="read" if kind == "menu" else "manage",
                description=title,
                surface="management",
                requires_data_scope=False,
                kind=kind,
            ))
            created += 1
        if created:
            db.flush()
        return created

    @staticmethod
    def map_role_data_scopes_to_codes(db: Session) -> int:
        """把存量 RoleDataScope 映射成数据码授权；缺叶子则补建。"""
        from app.models.organization import RoleDataScope

        granted = 0
        policies = db.scalars(select(RoleDataScope)).all()
        for policy in policies:
            parent = db.get(Permission, policy.permission_id)
            if parent is None:
                continue
            PermissionCatalog.ensure_data_scope_children(db, parent)
            leaf_code = PermissionCatalog.data_scope_code(parent.code, policy.scope_type)
            leaf = db.scalar(select(Permission).where(Permission.code == leaf_code))
            if leaf is None:
                continue
            exists = db.scalar(select(RolePermission.id).where(
                RolePermission.role_id == policy.role_id,
                RolePermission.permission_id == leaf.id,
            ))
            if exists:
                continue
            db.add(RolePermission(role_id=policy.role_id, permission_id=leaf.id))
            granted += 1
        if granted:
            db.flush()
        return granted

    # ── 菜单/按钮树构建（私有节点工厂 + 主入口）─────────────────────────────

    @staticmethod
    def _leaf_node(permission: dict, *, extra: dict | None = None) -> dict:
        node = {
            "key": permission["id"],
            "title": permission.get("description") or permission["code"],
            "kind": PermissionCatalog.permission_kind_of(permission),
            "code": permission["code"],
            "status": permission.get("status", "active"),
            "assigned_role_count": int(permission.get("assigned_role_count") or 0),
            "is_leaf": True,
            "selectable": True,
            "children": [],
            "prefix": f"{permission['code']}.",
            "parent_code": permission.get("parent_code"),
            "parent_title": permission.get("parent_title"),
        }
        if extra:
            node.update(extra)
        return node

    @staticmethod
    def _menu_node(permission: dict, children: list[dict]) -> dict:
        code = permission["code"]
        return {
            "key": permission["id"],
            "title": permission.get("description") or code,
            "kind": "menu",
            "code": code,
            "status": permission.get("status", "active"),
            "assigned_role_count": int(permission.get("assigned_role_count") or 0),
            "is_leaf": not children,
            "selectable": True,
            "children": children,
            "prefix": f"{code}.",
            "parent_code": permission.get("parent_code"),
            "parent_title": permission.get("parent_title"),
        }

    @staticmethod
    def _group_node(key: str, title: str, kind: str, children: list[dict], prefix: str = "") -> dict:
        return {
            "key": key,
            "title": title,
            "kind": kind,
            "code": None,
            "status": "active",
            "assigned_role_count": 0,
            "is_leaf": False,
            "selectable": False,
            "children": children,
            "prefix": prefix,
            "parent_code": None,
            "parent_title": None,
        }

    @staticmethod
    def _longest_menu_parent(code: str, menu_codes: set[str]) -> str | None:
        parts = code.split(".")
        for end in range(len(parts) - 1, 0, -1):
            candidate = ".".join(parts[:end])
            if candidate in menu_codes:
                return candidate
        return None

    @staticmethod
    def _build_data_tree(items: list[dict], by_code: dict[str, dict]) -> list[dict]:
        data_by_ns: dict[str, dict[str, list[dict]]] = {}
        for item in items:
            parent_code, scope_type = PermissionCatalog.split_data_scope_code(item["code"])
            parent = by_code.get(parent_code or "")
            namespace = item.get("catalog_namespace") or (parent_code.split(".", 1)[0] if parent_code else "other")
            parent_title = (parent or {}).get("description") or parent_code or "未分组"
            packed = f"{parent_code}|{parent_title}"
            data_by_ns.setdefault(namespace, {}).setdefault(packed, []).append(
                PermissionCatalog._leaf_node(item, extra={"scope_type": scope_type, "parent_code": parent_code, "parent_title": parent_title}),
            )
        roots: list[dict] = []
        for namespace, parents in sorted(data_by_ns.items()):
            parent_nodes = []
            for packed, leaves in sorted(parents.items()):
                parent_code, parent_title = packed.split("|", 1)
                parent_nodes.append(PermissionCatalog._group_node(
                    f"data:{parent_code}", parent_title, "data", leaves, prefix=f"{parent_code}.scope.",
                ))
            roots.append(PermissionCatalog._group_node(f"data-ns:{namespace}", namespace, "data", parent_nodes, prefix=f"{namespace}."))
        return roots

    @staticmethod
    def build_permission_trees(permissions: list[dict]) -> tuple[list[dict], list[dict]]:
        """资源树（侧栏形菜单→按钮）+ 数据树（仅业务码数据叶子）。

        管理面不再有接口节点；业务面（api/数据）结构保持不变，供应用工作台复用。
        """
        by_code: dict[str, dict] = {}
        for raw in permissions:
            kind = PermissionCatalog.permission_kind_of(raw)
            item = {**raw, "kind": kind}
            by_code[item["code"]] = item

        menu_codes = {code for code, item in by_code.items() if item["kind"] == "menu"}
        used: set[str] = set()

        def attach_under_menu(menu_code: str) -> list[dict]:
            children: list[dict] = []
            menu_item = by_code.get(menu_code)
            menu_title = (menu_item or {}).get("description") or menu_code
            for btn in MENU_BUTTONS.get(menu_code, ()):
                if btn in by_code:
                    children.append(PermissionCatalog._leaf_node(by_code[btn], extra={"parent_code": menu_code, "parent_title": menu_title}))
                    used.add(btn)
            nested_menus: list[dict] = []
            nested_others: list[dict] = []
            prefix = f"{menu_code}."
            for code, item in by_code.items():
                if code == menu_code or code in used:
                    continue
                if not code.startswith(prefix):
                    continue
                if item["kind"] == "data":
                    continue
                parent = PermissionCatalog._longest_menu_parent(code, menu_codes)
                if parent != menu_code:
                    continue
                if item["kind"] == "menu":
                    nested_menus.append(item)
                else:
                    nested_others.append(item)
            for item in nested_others:
                children.append(PermissionCatalog._leaf_node(item, extra={"parent_code": menu_code, "parent_title": menu_title}))
                used.add(item["code"])
            for item in sorted(nested_menus, key=lambda row: row["code"]):
                used.add(item["code"])
                sub_children = attach_under_menu(item["code"])
                children.append(PermissionCatalog._menu_node({**item, "parent_code": menu_code, "parent_title": menu_title}, sub_children))
            return children

        resource: list[dict] = []
        overview = by_code.get("menu.overview")
        if overview:
            used.add("menu.overview")
            resource.append(PermissionCatalog._menu_node(overview, attach_under_menu("menu.overview")))

        for group_key, group_title, codes in MENU_GROUPS:
            group_children: list[dict] = []
            for code in codes:
                item = by_code.get(code)
                if item is None:
                    continue
                used.add(code)
                group_children.append(PermissionCatalog._menu_node(
                    {**item, "parent_code": None, "parent_title": group_title},
                    attach_under_menu(code),
                ))
            if group_children:
                resource.append(PermissionCatalog._group_node(f"nav:{group_key}", group_title, "menu", group_children, prefix="menu."))

        stray_top = sorted(
            code for code in menu_codes
            if code not in used and PermissionCatalog._longest_menu_parent(code, menu_codes) is None
        )
        if stray_top:
            other_children = []
            for code in stray_top:
                used.add(code)
                other_children.append(PermissionCatalog._menu_node(by_code[code], attach_under_menu(code)))
            resource.append(PermissionCatalog._group_node("nav:other", "其他", "menu", other_children, prefix="menu."))

        leftovers = [
            item for code, item in sorted(by_code.items())
            if code not in used and item["kind"] != "data"
        ]
        if leftovers:
            resource.append(PermissionCatalog._group_node(
                "nav:unmapped", "未挂载", "api",
                [PermissionCatalog._leaf_node(item) for item in leftovers],
            ))

        data_items = [item for item in by_code.values() if item["kind"] == "data"]
        return resource, PermissionCatalog._build_data_tree(data_items, by_code)

    @staticmethod
    def grant_codes_skip_missing(
        db: Session,
        role_id: UUID,
        codes: tuple[str, ...],
        *,
        skip_missing: bool = False,
    ) -> int:
        """给角色补授权；契约要求的码缺失时默认抛错，不再静默吞掉。

        严格模式（默认）：任一码在 permissions 表不存在即抛 RuntimeError，消息列出缺失码。
        隔离场景（测试库未造全目录）调用方必须显式传 skip_missing=True：跳过的码按条数记
        WARN 日志，返回新增授权条数。
        """
        if not codes:
            return 0
        rows = db.execute(select(Permission.id, Permission.code).where(Permission.code.in_(codes))).all()
        found = {code: permission_id for permission_id, code in rows}
        missing = sorted(set(codes) - set(found))
        if missing and not skip_missing:
            raise RuntimeError(
                f"权限目录缺少契约必需码：{', '.join(missing)}（请先运行 seed_greenfield，体检 H6 可暴露同源缺口）"
            )
        if missing:
            logger.warning(
                "grant_codes_skip_missing 跳过缺失码 %d 个：%s（role_id=%s）",
                len(missing), ", ".join(missing), role_id,
            )
        existing = set(db.scalars(select(RolePermission.permission_id).where(
            RolePermission.role_id == role_id,
        )).all())
        added = 0
        for code, permission_id in found.items():
            if permission_id in existing:
                continue
            db.add(RolePermission(role_id=role_id, permission_id=permission_id))
            added += 1
        if added:
            db.flush()
        return added
