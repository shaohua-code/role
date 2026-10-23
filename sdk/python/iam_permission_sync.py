"""权限目录同步工具：把应用的权限清单批量登记到 IAM 权限目录。

管理面组件——调用方必须持有平台管理 access JWT（HS256 management token，
token_use=management_access）；终端用户 OIDC access token 会被 IAM 以 403 拒绝。

设计边界（fail closed / 幂等）：
- 清单在发起任何网络请求前本地预检（字段/长度/重复码），非法即 ValueError，绝不猜测。
- 先拉取现有目录建 code 索引，只创建缺失项；已存在条目一律跳过，
  不修改其描述或状态（状态变更走管理台 PATCH /admin/permissions/{id}/status）。
- 单条创建失败（含 409 并发冲突、网络抖动）只记入报告不中断整批；
  409 会重拉目录确认：已存在视为 skipped，仍缺失才记为 failed。
- 目录不可达（无法建立索引）时直接抛 IamAdminError(503)，同步不可能半途开始。
"""
from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class IamAdminError(RuntimeError):
    """IAM 管理 API 拒绝请求、返回无效响应或不可达；调用方必须按失败处理。"""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PermissionSyncReport:
    """一次同步的结果分类；failed 非空时调用方应人工核对后重跑（幂等安全）。"""

    created: tuple[str, ...]
    skipped: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]


def _derive_catalog_namespace(code: str) -> str:
    """与 IAM 服务端 derive_catalog_namespace_value 对齐。"""
    cleaned = code.strip()
    if cleaned.startswith("iam."):
        return "platform"
    if "." not in cleaned:
        raise ValueError(f"permission code must contain a namespace segment: {code!r}")
    return cleaned.split(".", maxsplit=1)[0].lower()


class IamAdminClient:
    """IAM 管理面最小客户端；仅覆盖权限目录 list/create 两个端点。

    与授权判定 client 同风格：标准库零依赖、固定超时、错误归一为 IamAdminError，
    绝不把异常原文透给调用方。
    """

    def __init__(self, api_base_url: str, timeout_seconds: float = 3.0) -> None:
        self.permissions_endpoint = api_base_url.rstrip("/") + "/api/v1/admin/permissions"
        self.timeout_seconds = timeout_seconds

    def list_permissions(self, management_token: str) -> list[dict[str, Any]]:
        """返回权限目录条目列表；响应不是数组或缺 code 即契约错误（502）。"""
        body = self._request("GET", self.permissions_endpoint, management_token)
        # 后端契约：GET /admin/permissions 返回裸数组（limit 1000，按 code 排序）。
        if not isinstance(body, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("code"), str) or not item["code"]
            for item in body
        ):
            raise IamAdminError(502, "IAM returned an invalid permission catalog response")
        return body

    def create_permission(
        self,
        management_token: str,
        *,
        code: str,
        resource_type: str,
        scope: str,
        description: str | None = None,
        catalog_namespace: str | None = None,
    ) -> dict[str, Any]:
        """创建一条权限码；201 返回目录条目，409/422 等按 IamAdminError 抛出。"""
        namespace = catalog_namespace or _derive_catalog_namespace(code)
        payload: dict[str, Any] = {
            "code": code,
            "catalog_namespace": namespace,
            "resource_type": resource_type,
            "scope": scope,
        }
        if description is not None:
            payload["description"] = description
        return self._request("POST", self.permissions_endpoint, management_token, payload)

    def _request(
        self, method: str, endpoint: str, management_token: str, payload: dict[str, Any] | None = None
    ) -> Any:
        """统一传输层：HS256 管理 JWT 走 Bearer 头；错误语义对齐既有 SDK 约定。"""
        if not management_token:
            raise ValueError("A platform management access token is required")
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Authorization": f"Bearer {management_token}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            # 保留 IAM 状态码（409 冲突/422 校验/401 未认证/403 非平台管理员），
            # 不透出响应体细节，供同步循环按码分类处理。
            raise IamAdminError(exc.code, "IAM rejected the management request") from None
        except (URLError, TimeoutError, OSError):
            raise IamAdminError(503, "IAM management API is unavailable") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise IamAdminError(502, "IAM returned an invalid management response") from None


def sync_permission_manifest(
    manifest: Sequence[Mapping[str, Any]],
    *,
    client: IamAdminClient,
    management_token: str,
) -> PermissionSyncReport:
    """把权限清单幂等同步到目录：缺失的创建、已存在的跳过、失败逐条入报告。

    manifest 每项：{"code", "resource_type", "scope", "description"?}，
    字段约束与后端 PermissionCreate 对齐（code 3–180 / resource_type 1–100 /
    scope 1–80 / description ≤500）。清单内重复 code 属清单错误，预检即拒绝。
    """
    entries = _validate_manifest(manifest)
    # 先建目录索引；这一步失败意味着无法判断哪些码已存在，直接抛错而不是盲发创建。
    existing = {item["code"] for item in client.list_permissions(management_token)}
    created: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    for entry in entries:
        code = entry["code"]
        if code in existing:
            skipped.append(code)
            continue
        try:
            client.create_permission(
                management_token,
                code=code,
                resource_type=entry["resource_type"],
                scope=entry["scope"],
                description=entry.get("description"),
                catalog_namespace=entry.get("catalog_namespace"),
            )
            created.append(code)
        except IamAdminError as error:
            if error.status_code == 409:
                # 并发窗口：索引建立后他人可能已登记同码；重拉目录确认，
                # 无法确认（网络故障/响应异常）时保守记为 failed 待人工核对。
                try:
                    current = {item["code"] for item in client.list_permissions(management_token)}
                except IamAdminError:
                    failed.append((code, "conflict but catalog recheck failed"))
                    continue
                if code in current:
                    skipped.append(code)
                else:
                    failed.append((code, "conflict but code missing from catalog"))
            else:
                failed.append((code, f"iam error {error.status_code}"))
    return PermissionSyncReport(tuple(created), tuple(skipped), tuple(failed))


def _validate_manifest(manifest: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """清单本地预检：任何网络请求前拦截非法输入（fail closed，不猜测字段）。"""
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("manifest must be a non-empty list")
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for item in manifest:
        if not isinstance(item, Mapping):
            raise ValueError("each manifest entry must be an object")
        code = item.get("code")
        resource_type = item.get("resource_type")
        scope = item.get("scope")
        description = item.get("description")
        catalog_namespace = item.get("catalog_namespace")
        # 长度约束与后端 PermissionCreate 完全对齐，提前拦截无谓的 422。
        if not isinstance(code, str) or not 3 <= len(code) <= 180:
            raise ValueError(f"permission code must be a 3-180 char string: {code!r}")
        if not isinstance(resource_type, str) or not 1 <= len(resource_type) <= 100:
            raise ValueError(f"resource_type must be a 1-100 char string for {code}")
        if not isinstance(scope, str) or not 1 <= len(scope) <= 80:
            raise ValueError(f"scope must be a 1-80 char string for {code}")
        if description is not None and (not isinstance(description, str) or len(description) > 500):
            raise ValueError(f"description must be a string of at most 500 chars for {code}")
        derived_namespace = _derive_catalog_namespace(code)
        if catalog_namespace is not None:
            if not isinstance(catalog_namespace, str) or not 1 <= len(catalog_namespace) <= 100:
                raise ValueError(f"catalog_namespace must be a 1-100 char string for {code}")
            if catalog_namespace.strip().lower() != derived_namespace:
                raise ValueError(f"catalog_namespace must match code prefix for {code}")
        if code in seen:
            # 同一码出现两次属清单自相矛盾；不允许静默去重掩盖清单错误。
            raise ValueError(f"duplicate permission code in manifest: {code}")
        seen.add(code)
        entries.append({
            "code": code,
            "resource_type": resource_type,
            "scope": scope,
            "description": description,
            "catalog_namespace": catalog_namespace.strip().lower() if isinstance(catalog_namespace, str) else derived_namespace,
        })
    return entries
