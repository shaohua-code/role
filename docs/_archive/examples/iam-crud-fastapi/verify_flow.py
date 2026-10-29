"""CRUD 示例无头验收脚本（P322）：对真实 IAM 走通 SDK 五件套完整链路。

流程：受信切换（管理员，结束恢复）→ crud-demo 登录 IAM → OIDC 静默授权换取
CRUD 会话 → 批量权限快照 → 创建/读取/删除文档（在线判权 + owner 过滤）→
无会话 401。所有凭证只在进程内解析，绝不打印。
"""
import sys
from pathlib import Path
from urllib.parse import quote

import httpx

HERE = Path(__file__).resolve().parent
API_BASE = "http://localhost:8002"  # 必须与 OIDC issuer 同 host，否则登录 cookie 不随 authorize 发送
APP_BASE = "http://localhost:8000"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> None:
    local = load_env(HERE / ".env.local")
    root = load_env(HERE.parent.parent / ".env")
    admin_password = root["IAM_ADMIN_PASSWORD"]
    demo_password = local["DEMO_USER_PASSWORD"]
    application_id = local["IAM_APPLICATION_ID"]
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'} {name}{('：' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    with httpx.Client(base_url=API_BASE, timeout=15.0) as admin:
        # 1) 管理员登录并把示例应用临时设为受信（静默授权）；结束后恢复。
        token = admin.post("/api/v1/auth/login", json={
            "email": "admin@example.com", "password": admin_password,
        }).raise_for_status().json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        current = admin.get(f"/api/v1/admin/applications/{application_id}", headers=headers)
        already_trusted = current.status_code == 200 and current.json().get("trusted") is True
        if not already_trusted:
            admin.patch(f"/api/v1/admin/applications/{application_id}/trusted",
                        params={"trusted": "true"}, headers=headers).raise_for_status()
        print(f"[prep] 应用受信={'原本已受信' if already_trusted else '已临时开启'}")

    try:
        browser = httpx.Client(timeout=15.0, follow_redirects=True)

        # 2) crud-demo 登录 IAM（8002 refresh cookie 即 OIDC 浏览器会话）。
        login = browser.post(f"{API_BASE}/api/v1/auth/login", json={
            "email": local["DEMO_USER_EMAIL"], "password": demo_password,
        })
        check("IAM 账号登录（crud-demo）", login.status_code == 200)

        # 3) 走 SDK 登录路由：8000 → authorize（静默受信授权）→ callback 换会话。
        flow = browser.get(f"{APP_BASE}/auth/login")
        check("OIDC 静默授权 + SDK callback 建会话",
              "iam_session" in browser.cookies and flow.status_code in (200, 404),
              f"最终 {flow.status_code}")

        # 4) 批量权限快照（check_batch 真实调用）。
        perms = browser.get(f"{APP_BASE}/me/permissions").json().get("permissions", {})
        check("check_batch 快照三码全 allowed",
              perms == {"document.read": True, "document.create": True, "document.delete": True},
              str(perms))

        # 5) 创建（require_permission 在线判权）→ owner 列表 → 单查。
        created = browser.post(f"{APP_BASE}/documents", json={"title": "P322 真实联调文档"})
        body = created.json() if created.status_code == 201 else {}
        document_id = body.get("id", "")
        check("创建文档 201（document.create 在线判权）", created.status_code == 201, str(body))
        listing = browser.get(f"{APP_BASE}/documents").json().get("documents", {})
        check("owner 列表包含新文档", document_id in listing)
        detail = browser.get(f"{APP_BASE}/documents/{quote(document_id)}")
        check("单查文档 200", detail.status_code == 200)

        # 6) 删除（204）→ 复查 404（owner 过滤先行，不泄露存在性）。
        deleted = browser.delete(f"{APP_BASE}/documents/{quote(document_id)}")
        check("删除文档 204", deleted.status_code == 204)
        recheck = browser.get(f"{APP_BASE}/documents/{quote(document_id)}")
        check("删除后复查 404", recheck.status_code == 404)

        # 7) 无会话访问受保护路由必须 401（fail closed）。
        anon = httpx.Client(timeout=15.0)
        check("无会话 401", anon.get(f"{APP_BASE}/documents").status_code == 401)

        browser.close()
        anon.close()
    finally:
        # 8) 恢复逐次用户确认（非受信）。
        with httpx.Client(base_url=API_BASE, timeout=15.0) as admin:
            token = admin.post("/api/v1/auth/login", json={
                "email": "admin@example.com", "password": admin_password,
            }).raise_for_status().json()["access_token"]
            admin.patch(f"/api/v1/admin/applications/{application_id}/trusted",
                        params={"trusted": "false"},
                        headers={"Authorization": f"Bearer {token}"}).raise_for_status()
        print("[cleanup] 应用受信已恢复为关闭")

    if failures:
        print(f"\n{len(failures)} 项失败：{failures}")
        raise SystemExit(1)
    print("\n全部通过：SDK 五件套真实链路（登录路由/适配层判权/批量快照/owner 过滤/无会话拒绝）")


if __name__ == "__main__":
    main()
