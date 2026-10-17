"""面向真实 IAM 的 CRUD 示例联调准备脚本（P322）。

一条命令完成：管理员登录 → 选租户 → 登记 application（幂等）→ SDK 清单同步工具
登记 demo.document.* 权限码 → 创建角色并授予三个码（增量幂等）→ 创建测试用户
（一步设密码并绑定角色）。全部凭证写入本目录 .env.local（已被 .gitignore 覆盖）；
管理员密码只在进程内解析，绝不打印；client_secret/用户密码只落 .env.local。
"""
import json
import secrets
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import httpx

from iam_permission_sync import IamAdminClient, sync_permission_manifest

API_BASE = "http://127.0.0.1:8002"
HERE = Path(__file__).resolve().parent
ROOT_ENV = HERE.parent.parent / ".env"
LOCAL_ENV = HERE / ".env.local"
MANIFEST = [
    {"code": "demo.document.read", "resource_type": "document", "scope": "read", "description": "CRUD 示例：读取文档"},
    {"code": "demo.document.create", "resource_type": "document", "scope": "write", "description": "CRUD 示例：创建文档"},
    {"code": "demo.document.delete", "resource_type": "document", "scope": "delete", "description": "CRUD 示例：删除文档"},
]
CLIENT_ID = "crud-demo"
ROLE_KEY = "crud-demo"
USER_EMAIL = "crud-demo@example.com"


def load_admin_password() -> str:
    """从项目根 .env 解析管理员密码；只进内存，绝不打印或落日志。"""
    for line in ROOT_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("IAM_ADMIN_PASSWORD="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise SystemExit("项目根 .env 缺少 IAM_ADMIN_PASSWORD")


def api(client: httpx.Client, method: str, path: str, token: str | None = None, **kwargs) -> httpx.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = client.request(method, path, headers=headers, **kwargs)
    if response.status_code >= 400:
        print(f"FAIL {method} {path} -> {response.status_code} {response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)
    return response


def main() -> None:
    password = load_admin_password()
    with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
        # 1) 管理员登录：返回的 access_token 即 HS256 management_access JWT。
        token = api(client, "POST", "/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": password}).json()["access_token"]
        print("[1/6] 管理员登录成功（management token 已获取，不打印）")

        # 2) 选第一个租户作为联调租户。
        tenants = api(client, "GET", "/api/v1/admin/tenants", token).json()
        tenant_id, tenant_name = tenants[0]["id"], tenants[0]["name"]
        print(f"[2/6] 联调租户：{tenant_name}（{tenant_id}）")

        # 3) 幂等登记 application；client_secret 仅创建响应返回一次。
        local: dict[str, str] = {}
        if LOCAL_ENV.exists():
            for line in LOCAL_ENV.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    local[key.strip()] = value.strip()
        applications = api(client, "GET", "/api/v1/admin/applications", token).json()
        items = applications if isinstance(applications, list) else applications.get("items", [])
        existing = next((item for item in items if item.get("client_id") == CLIENT_ID), None)
        if existing:
            application_id = existing["id"]
            if not local.get("IAM_CLIENT_SECRET"):
                raise SystemExit("application 已存在但 .env.local 无 client_secret；请走 rotate-secret 或删除后重建")
            print(f"[3/6] application 复用已有：{application_id}")
        else:
            created = api(client, "POST", "/api/v1/admin/applications", token, json={
                "tenant_id": tenant_id, "name": "CRUD Demo", "client_id": CLIENT_ID,
                "redirect_uris": ["http://localhost:8000/auth/callback"],
                "description": "SDK 五件套联调示例应用（P322）",
            }).json()
            application_id, local["IAM_CLIENT_SECRET"] = created["id"], created["client_secret"]
            print(f"[3/6] application 已创建：{application_id}（client_secret 已写入 .env.local）")

        # 4) 用 SDK 清单同步工具把三个权限码幂等登记到目录（五件套之五真实调用）。
        report = sync_permission_manifest(
            MANIFEST, client=IamAdminClient(API_BASE), management_token=token)
        print(f"[4/6] 清单同步：created={list(report.created)} skipped={list(report.skipped)} "
              f"failed={[(code, reason) for code, reason in report.failed]}")
        if report.failed:
            raise SystemExit("清单同步存在 failed 项，先人工核对后重跑")

        # 5) 幂等创建角色并增量授予三个码（PUT 单条授权幂等、无乐观锁）。
        roles = api(client, "GET", "/api/v1/admin/roles", token).json()
        role = next((item for item in roles
                     if item.get("key") == ROLE_KEY and item.get("application_id") == application_id), None)
        if role:
            role_id = role["id"]
            print(f"[5/6] 角色复用已有：{role_id}")
        else:
            role_id = api(client, "POST", "/api/v1/admin/roles", token, json={
                "tenant_id": tenant_id, "application_id": application_id,
                "key": ROLE_KEY, "name": "CRUD Demo", "description": "SDK 联调专用角色（P322）",
            }).json()["id"]
            print(f"[5/6] 角色已创建：{role_id}")
        permissions = api(client, "GET", "/api/v1/admin/permissions", token).json()
        id_by_code = {item["code"]: item["id"] for item in permissions}
        for entry in MANIFEST:
            api(client, "PUT", f"/api/v1/admin/roles/{role_id}/permissions/{id_by_code[entry['code']]}", token)
        # owner_only 路由要求 IAM data scope 为 self 分支；角色数据范围默认租户级，必须显式配置。
        api(client, "PUT", f"/api/v1/admin/roles/{role_id}/data-scopes", token, json={
            "policies": [{"permission_id": id_by_code[entry["code"]], "scope_type": "self"} for entry in MANIFEST],
        })
        print(f"      已授予并配置 self 数据范围：{[entry['code'] for entry in MANIFEST]}")

        # 6) 幂等创建测试用户（一步设密码并绑定角色）。
        users = api(client, "GET", "/api/v1/admin/users", token, params={"q": USER_EMAIL}).json()
        user_items = users if isinstance(users, list) else users.get("items", [])
        user = next((item for item in user_items if item.get("email") == USER_EMAIL), None)
        if user:
            print(f"[6/6] 测试用户复用已有：{USER_EMAIL}")
        else:
            local["DEMO_USER_PASSWORD"] = secrets.token_urlsafe(12)
            api(client, "POST", "/api/v1/admin/users", token, json={
                "tenant_id": tenant_id, "email": USER_EMAIL, "display_name": "CRUD Demo User",
                "initial_password": local["DEMO_USER_PASSWORD"], "role_id": role_id,
            })
            print(f"[6/6] 测试用户已创建并绑定角色：{USER_EMAIL}")

        # 写 .env.local（CRUD 示例 uvicorn 与浏览器登录用；已被 .gitignore 覆盖）。
        local.update({
            "IAM_API_URL": API_BASE,
            "IAM_ISSUER": "http://localhost:8002",
            "IAM_APPLICATION_ID": application_id,
            "IAM_CLIENT_ID": CLIENT_ID,
            "IAM_REDIRECT_URI": "http://localhost:8000/auth/callback",
            "DEMO_USER_EMAIL": USER_EMAIL,
        })
        lines = "".join(f"{key}={value}\n" for key, value in sorted(local.items()))
        LOCAL_ENV.write_text(lines, encoding="utf-8")
        print(f"\n完成：凭证与连接配置已写入 {LOCAL_ENV}")
        print("下一步：加载 .env.local 后 uvicorn app:app --port 8000，浏览器走 http://localhost:8000/auth/login")


if __name__ == "__main__":
    main()
