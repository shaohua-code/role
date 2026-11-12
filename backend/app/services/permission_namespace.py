"""权限目录与应用之间的命名空间归属规则。"""

import re

from fastapi import HTTPException

NAMESPACE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
PLATFORM_NAMESPACE = "platform"
# P392 管理面五域前缀：这些域的编码目录命名空间统一归 platform（应用命名空间不得占用）。
MANAGEMENT_DOMAIN_PREFIXES = ("platform.", "rbac.", "org.", "app.", "ops.", "menu.", "button.")


def normalize_namespace(value: str) -> str:
    """规范化命名空间为小写并校验格式。"""
    cleaned = value.strip().lower()
    if not cleaned or not NAMESPACE_PATTERN.fullmatch(cleaned):
        raise HTTPException(422, "权限命名空间格式无效")
    return cleaned


def default_namespace_from_client_id(client_id: str) -> str:
    """从 Client ID 推导默认权限命名空间（首段字母数字，遇分隔符截断）。"""
    raw = client_id.strip()
    if not raw:
        raise HTTPException(422, "无法从 Client ID 推导权限命名空间，请显式填写")
    segment = re.split(r"[._-]", raw, maxsplit=1)[0].lower()
    if not segment or not NAMESPACE_PATTERN.fullmatch(segment):
        raise HTTPException(422, "无法从 Client ID 推导权限命名空间，请显式填写")
    return segment


def derive_catalog_namespace_value(code: str) -> str:
    """从稳定权限编码推导目录命名空间（无 HTTP 上下文）。

    P392 五域体系：管理面码（platform/rbac/org/app/ops 前缀）统一归 platform 命名空间；
    业务码按应用命名空间（编码首段）归属。
    """
    cleaned = code.strip()
    if cleaned.startswith(MANAGEMENT_DOMAIN_PREFIXES):
        return PLATFORM_NAMESPACE
    if "." not in cleaned:
        raise ValueError("权限编码格式无效")
    segment = cleaned.split(".", maxsplit=1)[0].lower()
    if not NAMESPACE_PATTERN.fullmatch(segment):
        raise ValueError("权限编码命名空间无效")
    return segment


def derive_catalog_namespace(code: str) -> str:
    """从稳定权限编码推导目录命名空间。"""
    try:
        return derive_catalog_namespace_value(code)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def permission_matches_namespace(code: str, namespace: str) -> bool:
    """判断权限码是否属于指定应用命名空间。"""
    normalized = normalize_namespace(namespace)
    cleaned = code.strip()
    if cleaned.startswith(MANAGEMENT_DOMAIN_PREFIXES) and normalized == PLATFORM_NAMESPACE:
        return True
    return cleaned == normalized or cleaned.startswith(f"{normalized}.")


def resolve_permission_namespace(*, code: str, catalog_namespace: str | None) -> str:
    """创建权限时确定 catalog_namespace，并与 code 推导结果一致。"""
    derived = derive_catalog_namespace(code)
    if catalog_namespace is None:
        return derived
    normalized = normalize_namespace(catalog_namespace)
    if normalized != derived:
        raise HTTPException(422, "catalog_namespace 与权限编码前缀不一致")
    return normalized


def is_platform_catalog_namespace(catalog_namespace: str) -> bool:
    """判断目录命名空间是否为平台保留命名空间（platform）。"""
    return normalize_namespace(catalog_namespace) == PLATFORM_NAMESPACE


# 与前端 permissionGroups.ts 同一套管理面判定：五域前缀或菜单/按钮码。
def is_management_code(code: str) -> bool:
    """管理面码判定：五域前缀或菜单/按钮码。"""
    return code.startswith(MANAGEMENT_DOMAIN_PREFIXES)


# 旧五域作用域矩阵（PLATFORM_SCOPE_CODES/TENANT_SCOPE_CODES/HIDDEN_SCOPES_BY_KIND/
# resolve_permission_scope_key/assert_role_kind_grant_permissions）已随 27 接口码模型
# 一并删除：节点越权改由「节点授权下限（node_allows_scope）+ 角色授权范围」收口。


def assert_application_grant_permissions(
    application_permission_namespace: str,
    proposed: list,
    current_ids: set,
    grantable_management_codes: frozenset[str] | None = None,
) -> None:
    """应用角色可挂：本应用业务码，以及操作者看得见的租户/应用管理码。

    grantable_management_codes=None 表示平台超管，管理面不限制。
    """
    namespace = normalize_namespace(application_permission_namespace)
    for permission in proposed:
        if permission.id in current_ids:
            continue
        if is_management_code(permission.code) or getattr(permission, "surface", None) == "management":
            if grantable_management_codes is not None and permission.code not in grantable_management_codes:
                raise HTTPException(422, f"不能配置你没有的权限：{permission.code}")
            continue
        if permission.catalog_namespace != namespace:
            raise HTTPException(422, "权限不属于当前应用命名空间")
        if not permission_matches_namespace(permission.code, namespace):
            raise HTTPException(422, "权限不属于当前应用命名空间")
