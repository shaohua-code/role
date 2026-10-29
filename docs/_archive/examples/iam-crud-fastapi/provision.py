"""面向真实 IAM 的 CRUD 示例联调准备脚本。

管理员登录 → 选租户 → 登记 application（幂等）→ SDK L2 清单同步
登记 crud.document.* → 建角色并授权 + RoleDataScope=self → 创建测试用户。
凭证写入本目录 .env.local；管理员密码只进内存，绝不打印。
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from iam_permission_sync import IamAdminClient, sync_permission_manifest

API_BASE = "http://127.0.0.1:8002"
HERE = Path(__file__).resolve().parent
ROOT_ENV = HERE.parent.parent / ".env"
LOCAL_ENV = HERE / ".env.local"
MANIFEST = [
    {"code": "crud.document.read", "resource_type": "document", "scope": "read", "description": "CRUD 示例：读取文档"},
    {"code": "crud.document.create", "resource_type": "document", "scope": "write", "description": "CRUD 示例：创建文档"},
    {"code": "crud.document.delete", "resource_type": "document", "scope": "delete", "description": "CRUD 示例：删除文档"},
]
CLIENT_ID = "crud-demo"
ROLE_KEY = "crud-demo"
USER_EMAIL = "crud-demo@example.com"


def load_admin_password() -> str:
    for line in ROOT_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("IAM_ADMIN_PASSWORD="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise SystemExit("项目根 .env 缺少 IAM_ADMIN_PASSWORD")


def api(
    method: str,
    path: str,
    token: str | None = None,
    *,
    json_body: Any = None,
    params: dict[str, str] | None = None,
) -> Any:
    url = API_BASE + path
    if params:
        url = url + ("&" if "?" in url else "?") + urlencode(params)
    headers: dict[str, str] = {"Accept": "application/json"}
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"FAIL {method} {path} -> {exc.code} {body}", file=sys.stderr)
        raise SystemExit(1) from None
    except URLError as exc:
        print(f"FAIL {method} {path} -> network {exc}", file=sys.stderr)
        raise SystemExit(1) from None


def main() -> None:
    password = load_admin_password()

    token = api(
        "POST",
        "/api/v1/auth/login",
        json_body={"email": "admin@example.com", "password": password},
    )["access_token"]
    print("[1/6] 管理员登录成功（management token 已获取，不打印）")

    tenants = api("GET", "/api/v1/admin/tenants", token)
    tenant_id, tenant_name = tenants[0]["id"], tenants[0]["name"]
    print(f"[2/6] 联调租户：{tenant_name}（{tenant_id}）")

    local: dict[str, str] = {}
    if LOCAL_ENV.exists():
        for line in LOCAL_ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                local[key.strip()] = value.strip()

    applications = api("GET", "/api/v1/admin/applications", token)
    items = applications if isinstance(applications, list) else applications.get("items", [])
    existing = next((item for item in items if item.get("client_id") == CLIENT_ID), None)
    if existing:
        application_id = existing["id"]
        if not local.get("IAM_CLIENT_SECRET"):
            raise SystemExit(
                "application 已存在但 .env.local 无 client_secret；请先 rotate-secret 或删除后重建"
            )
        print(f"[3/6] application 复用已有：{application_id}")
    else:
        created = api(
            "POST",
            "/api/v1/admin/applications",
            token,
            json_body={
                "tenant_id": tenant_id,
                "name": "CRUD Demo",
                "client_id": CLIENT_ID,
                "redirect_uris": ["http://localhost:8000/auth/callback"],
                "description": "SDK 五件套联调示例应用",
            },
        )
        application_id, local["IAM_CLIENT_SECRET"] = created["id"], created["client_secret"]
        print(f"[3/6] application 已创建：{application_id}（client_secret 已写入 .env.local）")

    report = sync_permission_manifest(
        MANIFEST,
        client=IamAdminClient(API_BASE, application_id=application_id),
        management_token=token,
    )
    print(
        f"[4/6] 清单同步(L2)：created={list(report.created)} skipped={list(report.skipped)} "
        f"failed={[(code, reason) for code, reason in report.failed]}"
    )
    if report.failed:
        raise SystemExit("清单同步存在 failed 项，先人工核对后重跑")

    roles = api("GET", "/api/v1/admin/roles", token)
    role = next(
        (
            item
            for item in roles
            if item.get("key") == ROLE_KEY and item.get("application_id") == application_id
        ),
        None,
    )
    if role:
        role_id = role["id"]
        print(f"[5/6] 角色复用已有：{role_id}")
    else:
        role_id = api(
            "POST",
            "/api/v1/admin/roles",
            token,
            json_body={
                "tenant_id": tenant_id,
                "application_id": application_id,
                "key": ROLE_KEY,
                "name": "CRUD Demo",
                "description": "SDK 联调专用角色",
            },
        )["id"]
        print(f"[5/6] 角色已创建：{role_id}")

    permissions = api("GET", "/api/v1/admin/permissions", token)
    id_by_code = {item["code"]: item["id"] for item in permissions}
    for entry in MANIFEST:
        if entry["code"] not in id_by_code:
            raise SystemExit(f"权限码未出现在目录：{entry['code']}")
        api(
            "PUT",
            f"/api/v1/admin/roles/{role_id}/permissions/{id_by_code[entry['code']]}",
            token,
        )
    api(
        "PUT",
        f"/api/v1/admin/roles/{role_id}/data-scopes",
        token,
        json_body={
            "policies": [
                {"permission_id": id_by_code[entry["code"]], "scope_type": "self"}
                for entry in MANIFEST
            ],
        },
    )
    print(f"      已授予并配置 self 数据范围：{[entry['code'] for entry in MANIFEST]}")

    users = api("GET", "/api/v1/admin/users", token, params={"q": USER_EMAIL})
    user_items = users if isinstance(users, list) else users.get("items", [])
    user = next((item for item in user_items if item.get("email") == USER_EMAIL), None)
    if user:
        print(f"[6/6] 测试用户复用已有：{USER_EMAIL}")
    else:
        local["DEMO_USER_PASSWORD"] = secrets.token_urlsafe(12)
        api(
            "POST",
            "/api/v1/admin/users",
            token,
            json_body={
                "tenant_id": tenant_id,
                "email": USER_EMAIL,
                "display_name": "CRUD Demo User",
                "initial_password": local["DEMO_USER_PASSWORD"],
                "role_id": role_id,
            },
        )
        print(f"[6/6] 测试用户已创建并绑定角色：{USER_EMAIL}")

    local.update(
        {
            "IAM_API_URL": API_BASE,
            "IAM_ISSUER": "http://localhost:8002",
            "IAM_APPLICATION_ID": application_id,
            "IAM_CLIENT_ID": CLIENT_ID,
            "IAM_REDIRECT_URI": "http://localhost:8000/auth/callback",
            "DEMO_USER_EMAIL": USER_EMAIL,
        }
    )
    lines = "".join(f"{key}={value}\n" for key, value in sorted(local.items()))
    LOCAL_ENV.write_text(lines, encoding="utf-8")
    print(f"\n完成：凭证与连接配置已写入 {LOCAL_ENV}")
    print(
        "下一步：加载 .env.local 后 uvicorn app:app --port 8000，浏览器打开 http://localhost:8000/auth/login"
    )


if __name__ == "__main__":
    main()
