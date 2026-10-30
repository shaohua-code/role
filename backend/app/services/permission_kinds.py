"""权限目录：资源权限树（侧栏形菜单 + 按钮 + 接口）与数据权限树。

27 个五域接口字符串不改名，按映射挂到对应菜单下，不靠前缀猜爸爸。
种类以 permissions.kind 为准；缺列或空值时才回退前缀推断。
"""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authorization import Permission, RolePermission
from app.services.permission_namespace import derive_catalog_namespace_value

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

# 菜单码 ↔ 现网侧栏；接口码按映射挂到菜单下（不是前缀猜测）。
MENU_CATALOG: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("menu.overview", "运营总览", ("platform.overview.read",)),
    ("menu.organization_workspace", "组织工作台", ("org.read", "org.manage")),
    ("menu.users", "用户管理", (
        "platform.account.read", "platform.account.manage",
        "org.member.read", "org.member.manage",
    )),
    ("menu.invitations", "成员邀请", ("org.invite.manage",)),
    ("menu.application_workspace", "应用工作台", (
        "app.read", "app.manage", "app.secret.rotate",
        "rbac.app_role.read", "rbac.app_role.manage", "rbac.app_role.assign",
    )),
    ("menu.roles", "平台角色", ("rbac.role.read", "rbac.role.manage")),
    ("menu.permissions", "权限编码", ("rbac.permission.read", "rbac.permission.manage")),
    ("menu.groups", "用户组", ("org.group.read", "org.group.manage")),
    ("menu.tenants", "租户管理", ("platform.tenant.read", "platform.tenant.manage")),
    ("menu.themes", "登录主题", ("ops.theme.manage",)),
    ("menu.models", "模型治理", ("ops.model.read", "ops.model.manage")),
    ("menu.model_usage", "模型用量", ("ops.model.read",)),
    ("menu.audit", "审计日志", ("ops.audit.read",)),
    ("menu.authz", "鉴权模拟", ("ops.authz.simulate",)),
)

# 按钮码按页收口，挂在对应菜单下。
BUTTON_CATALOG: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("button.users.manage", "用户写操作", ("platform.account.manage",)),
    ("button.tenants.manage", "租户写操作", ("platform.tenant.manage",)),
    ("button.roles.manage", "平台角色写操作", ("rbac.role.manage", "org.manage")),
    ("button.permissions.manage", "权限目录写操作", ("rbac.permission.manage",)),
    ("button.org.manage", "组织写操作", ("org.manage",)),
    ("button.groups.manage", "用户组写操作", ("org.group.manage",)),
    ("button.invitations.manage", "邀请写操作", ("org.invite.manage",)),
    ("button.apps.manage", "应用写操作", ("app.manage",)),
    ("button.apps.secret", "轮换应用密钥", ("app.secret.rotate",)),
    ("button.app_role.manage", "应用角色写操作", ("rbac.app_role.manage",)),
    ("button.app_role.assign", "任命应用管理员", ("rbac.app_role.assign",)),
    ("button.models.manage", "模型写操作", ("ops.model.manage",)),
    ("button.themes.manage", "登录主题写操作", ("ops.theme.manage",)),
)

# 菜单 → 按钮。接口见 MENU_CATALOG。
MENU_BUTTONS: dict[str, tuple[str, ...]] = {
    "menu.organization_workspace": ("button.org.manage",),
    "menu.users": ("button.users.manage",),
    "menu.invitations": ("button.invitations.manage",),
    "menu.application_workspace": (
        "button.apps.manage", "button.apps.secret",
        "button.app_role.manage", "button.app_role.assign",
    ),
    "menu.roles": ("button.roles.manage",),
    "menu.permissions": ("button.permissions.manage",),
    "menu.groups": ("button.groups.manage",),
    "menu.tenants": ("button.tenants.manage",),
    "menu.themes": ("button.themes.manage",),
    "menu.models": ("button.models.manage",),
}

MENU_CODES: tuple[str, ...] = tuple(item[0] for item in MENU_CATALOG)
BUTTON_CODES: tuple[str, ...] = tuple(item[0] for item in BUTTON_CATALOG)
MENU_APIS: dict[str, tuple[str, ...]] = {code: apis for code, _title, apis in MENU_CATALOG}
BUTTON_APIS: dict[str, tuple[str, ...]] = {code: apis for code, _title, apis in BUTTON_CATALOG}

# 与侧栏 NAV_GROUPS 同形；运营总览单独置顶，不进带标题分组。
MENU_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("identity", "身份与组织", ("menu.organization_workspace", "menu.users", "menu.invitations")),
    ("access", "应用与权限", ("menu.application_workspace",)),
    ("advanced", "高级管理", ("menu.roles", "menu.permissions", "menu.groups")),
    ("platform", "平台治理", ("menu.tenants", "menu.themes", "menu.models", "menu.model_usage")),
    ("ops", "审计与验证", ("menu.authz", "menu.audit")),
)

KIND_LABELS: dict[str, str] = {
    "menu": "菜单",
    "button": "按钮",
    "data": "数据权限",
    "api": "接口",
}


def infer_permission_kind(code: str) -> str:
    """回退推断：menu.* / button.* / *.scope.{范围} / 其余为接口。优先用库里的 kind。"""
    cleaned = code.strip()
    if cleaned.startswith("menu."):
        return "menu"
    if cleaned.startswith("button."):
        return "button"
    parent, scope_type = split_data_scope_code(cleaned)
    if parent and scope_type:
        return "data"
    return "api"


def permission_kind_of(item: dict | Permission) -> str:
    """以存储 kind 为准；空值或不在四类时回退前缀推断。"""
    if isinstance(item, dict):
        kind = item.get("kind")
        code = item.get("code") or ""
    else:
        kind = getattr(item, "kind", None)
        code = getattr(item, "code", "") or ""
    if kind in KIND_LABELS:
        return kind
    return infer_permission_kind(code)


def related_apis_for(code: str) -> tuple[str, ...]:
    """菜单/按钮对应的接口码；自定义子码沿最长上级菜单继承。"""
    cleaned = code.strip()
    if cleaned in MENU_APIS:
        return MENU_APIS[cleaned]
    if cleaned in BUTTON_APIS:
        return BUTTON_APIS[cleaned]
    parts = cleaned.split(".")
    while len(parts) > 1:
        parts.pop()
        prefix = ".".join(parts)
        if prefix in MENU_APIS:
            return MENU_APIS[prefix]
        if prefix in BUTTON_APIS:
            return BUTTON_APIS[prefix]
    return ()


def split_data_scope_code(code: str) -> tuple[str | None, str | None]:
    """把 appa.doc.read.scope.self 拆成业务码 + 范围类型。"""
    marker = ".scope."
    if marker not in code:
        return None, None
    parent, scope_type = code.rsplit(marker, 1)
    if scope_type in DATA_SCOPE_TYPES and parent:
        return parent, scope_type
    return None, None


def data_scope_code(permission_code: str, scope_type: str) -> str:
    """业务码对应的数据权限叶子编码。"""
    return f"{permission_code}.scope.{scope_type}"


def extra_ui_codes_for(api_codes: Iterable[str]) -> tuple[str, ...]:
    """模板已有接口码时，配上对应菜单/按钮，避免刷新后侧栏空白。"""
    held = set(api_codes)
    extra: list[str] = []
    for code, _title, apis in MENU_CATALOG + BUTTON_CATALOG:
        if any(item in held for item in apis):
            extra.append(code)
    return tuple(extra)


def all_ui_codes() -> tuple[str, ...]:
    return MENU_CODES + BUTTON_CODES


def ensure_data_scope_children(db: Session, parent: Permission) -> int:
    """业务码强制范围时补齐 5 个数据叶子；已有则跳过。"""
    if parent.surface != "business" or not parent.requires_data_scope:
        return 0
    if permission_kind_of(parent) != "api":
        return 0
    created = 0
    namespace = parent.catalog_namespace
    for scope_type in DATA_SCOPE_TYPES:
        code = data_scope_code(parent.code, scope_type)
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


def seed_ui_permissions(db: Session) -> int:
    """幂等写入菜单/按钮码，并回填 kind。"""
    created = 0
    for code, title, _apis in MENU_CATALOG + BUTTON_CATALOG:
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


def map_role_data_scopes_to_codes(db: Session) -> int:
    """把存量 RoleDataScope 映射成数据码授权；缺叶子则补建。"""
    from app.models.organization import RoleDataScope

    granted = 0
    policies = db.scalars(select(RoleDataScope)).all()
    for policy in policies:
        parent = db.get(Permission, policy.permission_id)
        if parent is None:
            continue
        ensure_data_scope_children(db, parent)
        leaf_code = data_scope_code(parent.code, policy.scope_type)
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


def _leaf_node(permission: dict, *, extra: dict | None = None) -> dict:
    node = {
        "key": permission["id"],
        "title": permission.get("description") or permission["code"],
        "kind": permission_kind_of(permission),
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


def _longest_menu_parent(code: str, menu_codes: set[str]) -> str | None:
    parts = code.split(".")
    for end in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:end])
        if candidate in menu_codes:
            return candidate
    return None


def _build_data_tree(items: list[dict], by_code: dict[str, dict]) -> list[dict]:
    data_by_ns: dict[str, dict[str, list[dict]]] = {}
    for item in items:
        parent_code, scope_type = split_data_scope_code(item["code"])
        parent = by_code.get(parent_code or "")
        namespace = item.get("catalog_namespace") or (parent_code.split(".", 1)[0] if parent_code else "other")
        parent_title = (parent or {}).get("description") or parent_code or "未分组"
        packed = f"{parent_code}|{parent_title}"
        data_by_ns.setdefault(namespace, {}).setdefault(packed, []).append(
            _leaf_node(item, extra={"scope_type": scope_type, "parent_code": parent_code, "parent_title": parent_title}),
        )
    roots: list[dict] = []
    for namespace, parents in sorted(data_by_ns.items()):
        parent_nodes = []
        for packed, leaves in sorted(parents.items()):
            parent_code, parent_title = packed.split("|", 1)
            parent_nodes.append(_group_node(
                f"data:{parent_code}", parent_title, "data", leaves, prefix=f"{parent_code}.scope.",
            ))
        roots.append(_group_node(f"data-ns:{namespace}", namespace, "data", parent_nodes, prefix=f"{namespace}."))
    return roots


def build_permission_trees(permissions: list[dict]) -> tuple[list[dict], list[dict]]:
    """资源树（侧栏形）+ 数据树。分组不可勾；菜单/按钮/接口可授权。"""
    by_code: dict[str, dict] = {}
    for raw in permissions:
        kind = permission_kind_of(raw)
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
                children.append(_leaf_node(by_code[btn], extra={"parent_code": menu_code, "parent_title": menu_title}))
                used.add(btn)
        for api in MENU_APIS.get(menu_code, ()):
            if api in by_code:
                children.append(_leaf_node(by_code[api], extra={"parent_code": menu_code, "parent_title": menu_title}))
                used.add(api)
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
            parent = _longest_menu_parent(code, menu_codes)
            if parent != menu_code:
                continue
            if item["kind"] == "menu":
                nested_menus.append(item)
            else:
                nested_others.append(item)
        for item in nested_others:
            children.append(_leaf_node(item, extra={"parent_code": menu_code, "parent_title": menu_title}))
            used.add(item["code"])
        for item in sorted(nested_menus, key=lambda row: row["code"]):
            used.add(item["code"])
            sub_children = attach_under_menu(item["code"])
            children.append(_menu_node({**item, "parent_code": menu_code, "parent_title": menu_title}, sub_children))
        return children

    resource: list[dict] = []
    overview = by_code.get("menu.overview")
    if overview:
        used.add("menu.overview")
        resource.append(_menu_node(overview, attach_under_menu("menu.overview")))

    for group_key, group_title, codes in MENU_GROUPS:
        group_children: list[dict] = []
        for code in codes:
            item = by_code.get(code)
            if item is None:
                continue
            used.add(code)
            group_children.append(_menu_node(
                {**item, "parent_code": None, "parent_title": group_title},
                attach_under_menu(code),
            ))
        if group_children:
            resource.append(_group_node(f"nav:{group_key}", group_title, "menu", group_children, prefix="menu."))

    stray_top = sorted(
        code for code in menu_codes
        if code not in used and _longest_menu_parent(code, menu_codes) is None
    )
    if stray_top:
        other_children = []
        for code in stray_top:
            used.add(code)
            other_children.append(_menu_node(by_code[code], attach_under_menu(code)))
        resource.append(_group_node("nav:other", "其他", "menu", other_children, prefix="menu."))

    leftovers = [
        item for code, item in sorted(by_code.items())
        if code not in used and item["kind"] != "data"
    ]
    if leftovers:
        resource.append(_group_node(
            "nav:unmapped", "未挂载", "api",
            [_leaf_node(item) for item in leftovers],
        ))

    data_items = [item for item in by_code.values() if item["kind"] == "data"]
    return resource, _build_data_tree(data_items, by_code)


def build_permission_tree(permissions: list[dict]) -> list[dict]:
    """兼容旧调用：只返回资源树。"""
    resource, _data = build_permission_trees(permissions)
    return resource


def grant_codes_skip_missing(db: Session, role_id: UUID, codes: tuple[str, ...]) -> int:
    """给角色补授权；目录里还没有的码跳过（隔离测试未造菜单码时不炸）。"""
    if not codes:
        return 0
    existing = set(db.scalars(select(RolePermission.permission_id).where(
        RolePermission.role_id == role_id,
    )).all())
    added = 0
    rows = db.execute(select(Permission.id, Permission.code).where(Permission.code.in_(codes))).all()
    for permission_id, _code in rows:
        if permission_id in existing:
            continue
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))
        added += 1
    if added:
        db.flush()
    return added
