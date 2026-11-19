"""密码授权（ROPC）登录失败节流回归（内存 SQLite，不动开发库）。

覆盖复查报告 P1-2：
- 连续失败跨过阈值后 429 + Retry-After（保持 OAuth 错误结构），并写 auth.login denied 审计；
- 成功登录清理失败计数（同口径 reset）；
- 同账号跨来源仍受账号桶锁定；同来源多账号受地址桶锁定；
- 凭证正确但无本应用有效角色不计入失败桶（非撞库信号）；
- 非本次范围：授权码与 refresh grant 不经过节流分支（见 test_oidc_consent.py PG 集成用例）。
"""

import asyncio
import base64
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.oidc_provider.tokens import token
from app.core.security import hash_password
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Role, RoleBinding
from app.models.identity import AuditEvent, Tenant, TenantMembership, User


class OidcPasswordGrantThrottleTests(unittest.TestCase):
    """每个用例在内存 SQLite 中运行；节流桶走 sqlite on_conflict 分支。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"t-{uuid4().hex[:10]}")
        # 真实 Argon2 哈希（对应未泄露口令）：占位字符串会触发 UnknownHashError 绕过节流分支。
        self.user = User(email=f"u-{uuid4().hex[:8]}@example.test",
                         password_hash=hash_password("Unused-Credential-9"), display_name="直登用户")
        self.db.add_all([self.tenant, self.user])
        self.db.flush()
        self.client_secret = f"secret-{uuid4().hex}"
        self.app = Application(tenant_id=self.tenant.id, client_id=f"ropc-{uuid4().hex[:8]}",
                               name="直登应用", permission_namespace="ropc", redirect_uris=[],
                               trusted=True, client_secret_hash=hash_password(self.client_secret))
        membership = TenantMembership(user_id=self.user.id, tenant_id=self.tenant.id, status="active")
        role = Role(tenant_id=self.tenant.id, key=f"member-{uuid4().hex[:8]}", name="成员",
                    kind="application", application_id=self.app.id, status="active")
        self.db.add_all([self.app, membership, role])
        self.db.flush()
        binding = RoleBinding(membership_id=membership.id, role_id=role.id)
        self.db.add(binding)
        self.db.flush()
        self.binding_id = binding.id
        # 低阈值便于在测试内跨过：邮箱×来源 / 账号 3 次；来源桶默认调高避免干扰，
        # 仅地址桶用例单独设低。
        self.settings = SimpleNamespace(
            jwt_secret="unit-test-jwt-secret-0123456789abcdef",
            oidc_issuer="http://localhost:8000", refresh_token_days=7,
            trust_proxy_client_ip=False,
            login_attempt_window_seconds=900, login_block_seconds=900,
            login_account_max_failures=3, login_identifier_max_failures=3,
            login_ip_max_failures=100,
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ── 请求构造 ────────────────────────────────────────────────────────────

    def _password_request(self, username: str, password: str, *, ip: str = "127.0.0.1"):
        """构造带 client_secret_basic 的密码授权请求；ip 模拟不同来源。"""
        basic = f"Basic {base64.b64encode(f'{self.app.client_id}:{self.client_secret}'.encode()).decode()}"
        body = urlencode({"grant_type": "password", "username": username, "password": password}).encode()
        path = "/api/v1/oidc/token"
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": path, "raw_path": path.encode(), "root_path": "",
            "query_string": b"",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
            "client": (ip, 51000), "server": ("localhost", 8000),
        }, receive=receive)
        return request, basic

    def _run(self, username: str, password: str, *, ip: str = "127.0.0.1",
             success_patches: bool = False) -> Response:
        request, basic = self._password_request(username, password, ip=ip)
        patches = [patch("app.api.v1.oidc_provider.tokens.get_settings", return_value=self.settings),
                   patch("app.api.v1.oidc_provider.common.get_settings", return_value=self.settings)]
        if success_patches:
            # 成功路径需要签发 JWT；签名与 issuer 与本测试无关，打桩隔离（凭证/节流/审计为真实路径）。
            patches += [patch("app.api.v1.oidc_provider.tokens._issuer",
                              return_value="http://localhost:8000"),
                        patch("app.api.v1.oidc_provider.tokens.sign_jwt",
                              return_value="unit-test-signed")]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            return asyncio.run(token(request, basic, self.db))

    def _audit_count(self) -> int:
        return self.db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.action == "auth.login", AuditEvent.outcome == "denied")) or 0

    # ── 用例 ────────────────────────────────────────────────────────────────

    def test_repeated_failures_then_rate_limited_with_retry_after(self) -> None:
        """连续 3 次失败锁定；第 4 次 429 + Retry-After，且不再写失败审计。"""
        for _ in range(3):
            response = self._run(self.user.email, "wrong-password")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.body)["error"], "invalid_grant")
        self.assertEqual(self._audit_count(), 3)
        denied = self.db.scalars(select(AuditEvent).where(
            AuditEvent.action == "auth.login", AuditEvent.outcome == "denied")).first()
        self.assertEqual(denied.actor_user_id, self.user.id)
        self.assertEqual(denied.tenant_id, self.tenant.id)
        self.assertEqual(denied.source_ip, "127.0.0.1")
        self.assertEqual(denied.details["grant_type"], "password")
        blocked = self._run(self.user.email, "wrong-password")
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(json.loads(blocked.body)["error"], "rate_limited")
        self.assertIn("Retry-After", blocked.headers)
        self.assertGreaterEqual(int(blocked.headers["Retry-After"]), 1)
        # 限流分支在密码校验前返回：不新增审计。
        self.assertEqual(self._audit_count(), 3)

    def test_unknown_account_failure_counts_toward_lockout(self) -> None:
        """未知账号同样进入节流（假哈希抹平时序后计入失败桶），审计不落操作者 ID。"""
        ghost = f"ghost-{uuid4().hex[:6]}@example.test"
        for _ in range(3):
            response = self._run(ghost, "wrong-password")
            self.assertEqual(response.status_code, 400)
        blocked = self._run(ghost, "wrong-password")
        self.assertEqual(blocked.status_code, 429)
        rows = self.db.scalars(select(AuditEvent).where(
            AuditEvent.action == "auth.login", AuditEvent.outcome == "denied")).all()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row.actor_user_id is None for row in rows))

    def test_success_resets_failure_count(self) -> None:
        """成功登录清理账号/邮箱×来源桶：成功后重新计数，第 3 次失败锁定、第 4 次 429。"""
        self.user.password_hash = hash_password("Correct-Horse-1")
        self.db.flush()
        self.assertEqual(self._run(self.user.email, "wrong").status_code, 400)
        self.assertEqual(self._run(self.user.email, "wrong").status_code, 400)
        self.assertEqual(self._run(self.user.email, "Correct-Horse-1",
                                   success_patches=True).status_code, 200)
        # 成功已清零：重新累计 3 次失败才锁定（第 3 次请求自身仍返回 400）。
        self.assertEqual(self._run(self.user.email, "wrong").status_code, 400)
        self.assertEqual(self._run(self.user.email, "wrong").status_code, 400)
        self.assertEqual(self._run(self.user.email, "wrong").status_code, 400)
        self.assertEqual(self._run(self.user.email, "wrong").status_code, 429)

    def test_account_bucket_blocks_same_account_across_sources(self) -> None:
        """同账号换 IP 仍受账号桶约束（G20 纯邮箱维度）。"""
        self.settings.login_identifier_max_failures = 50
        for ip in ("10.0.0.8", "10.0.0.9", "10.0.0.10"):
            response = self._run(self.user.email, "wrong-password", ip=ip)
            self.assertEqual(response.status_code, 400)
        response = self._run(self.user.email, "wrong-password", ip="10.0.0.11")
        self.assertEqual(response.status_code, 429)

    def test_address_bucket_blocks_multiple_accounts_same_source(self) -> None:
        """同来源多账号撞库达到地址阈值后，该来源整体 429。"""
        self.settings.login_ip_max_failures = 2
        other = User(email=f"o-{uuid4().hex[:8]}@example.test",
                     password_hash=hash_password("Unused-Credential-9"), display_name="另一用户")
        self.db.add(other)
        self.db.flush()
        self.assertEqual(self._run(self.user.email, "wrong-password").status_code, 400)
        self.assertEqual(self._run(other.email, "wrong-password").status_code, 400)
        # 地址桶阈值=2：第三个请求（无论哪个账号）都被来源锁定。
        self.assertEqual(self._run(self.user.email, "wrong-password").status_code, 429)
        self.assertEqual(self._run(other.email, "wrong-password").status_code, 429)

    def test_membership_missing_does_not_count_as_failure(self) -> None:
        """凭证正确但无本应用有效角色：按入场口径拒绝且不计失败桶，不触发锁定。"""
        self.user.password_hash = hash_password("Correct-Horse-1")
        self.db.delete(self.db.get(RoleBinding, self.binding_id))
        self.db.flush()
        for _ in range(5):
            response = self._run(self.user.email, "Correct-Horse-1")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json.loads(response.body)["error"], "invalid_grant")
        # 5 次后仍未被锁定（未计入失败桶），也没有认证失败审计。
        self.assertEqual(self._run(self.user.email, "Correct-Horse-1").status_code, 400)
        self.assertEqual(self._audit_count(), 0)


if __name__ == "__main__":
    unittest.main()
