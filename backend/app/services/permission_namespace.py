"""权限目录与应用之间的命名空间归属规则。"""

import re

from fastapi import HTTPException

NAMESPACE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
PLATFORM_NAMESPACE = "platform"


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
    """从稳定权限编码推导目录命名空间（无 HTTP 上下文）。"""
    cleaned = code.strip()
    if cleaned.startswith("iam."):
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
    return normalize_namespace(catalog_namespace) == PLATFORM_NAMESPACE


def assert_application_grant_permissions(
    application_permission_namespace: str,
    proposed: list,
    current_ids: set,
) -> None:
    """应用角色只能新增同命名空间的业务权限，不能新增 platform/iam 目录项。"""
    namespace = normalize_namespace(application_permission_namespace)
    for permission in proposed:
        if permission.id in current_ids:
            continue
        if is_platform_catalog_namespace(permission.catalog_namespace):
            raise HTTPException(403, "应用管理员不能新增 IAM 管理权限")
        if permission.catalog_namespace != namespace:
            raise HTTPException(422, "权限不属于当前应用命名空间")
        if permission.code.startswith("iam."):
            raise HTTPException(403, "应用管理员不能新增 IAM 管理权限")
