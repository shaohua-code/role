"""G02 密码救济双通道隔离测试：自助改密与管理员重置（内存 SQLite，不触碰开发库）。

覆盖：成功路径的凭证级联（撤销会话/令牌、消费 code/consent/重置链接、bump auth_version、
审计）、当前密码错误负路径、短口令 422、管理员重置的自保护/非启用/越权负路径，
以及改密后旧访问令牌即时失效。
"""

import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.users import reset_user_password
from app.api.v1.auth import change_own_password
from app.core.config import get_settings
from app.core.security import create_access_token, current_user, hash_password, verify_password
from app.db.base import Base
from app.models.application import Application
from app.models.identity import (AuditEvent, PasswordResetToken, RefreshSession, Tenant, User)
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.schemas.auth import AdminPasswordReset, PasswordChange


class PasswordChangeApiTests(unittest.TestCase):
    """每个用例在内存数据库中运行；签名密钥打桩避免依赖宿主环境。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.settings = get_settings().model_copy(update={"jwt_secret": "change-test-signing-secret-" + "x" * 32})
        self.patches = ExitStack()
        self.patches.enter_context(patch("app.api.v1.auth.get_settings", return_value=self.settings))
        self.patches.enter_context(patch("app.core.security.get_settings", return_value=self.settings))

        self.tenant = Tenant(name="业务租户", slug=f"biz-{uuid4().hex[:10]}")
        self.user = User(email=f"u-{uuid4().hex}@example.test", password_hash=hash_password("Old-password-123"),
                         display_name="普通用户", status="active")
        self.db.add_all([self.tenant, self.user])
        self.db.flush()
        self.application = Application(
            tenant_id=self.tenant.id, client_id=f"client-{uuid4().hex[:8]}", name="演示应用",
            redirect_uris=["https://client.example.test/callback"], status="active",
        )
        self.db.add(self.application)
        self.db.flush()
        self.request = Request({
            "type": "http", "method": "POST", "path": "/api/v1",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.patches.close()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ---- 造数 ----

    def _seed_credentials(self) -> RefreshSession:
        """为用户造一套完整可撤销凭证：IAM 会话 + OIDC family + code/consent/重置链接。"""
        now = datetime.now(timezone.utc)
        session = RefreshSession(
            user_id=self.user.id, token_hash=uuid4().hex * 2,
            expires_at=now + timedelta(days=1),
        )
        code = OAuthAuthorizationCode(
            application_id=self.application.id, user_id=self.user.id, code_hash=uuid4().hex * 2,
            redirect_uri="https://client.example.test/callback", scope="openid", nonce="nonce",
            code_challenge="challenge", code_challenge_method="S256", expires_at=now + timedelta(minutes=2),
        )
        consent = OAuthConsentRequest(
            application_id=self.application.id, user_id=self.user.id, ticket_hash=uuid4().hex * 2,
            redirect_uri="https://client.example.test/callback", client_state="state", scope="openid",
            nonce="nonce", code_challenge="challenge", code_challenge_method="S256",
            expires_at=now + timedelta(minutes=3),
        )
        oauth_refresh = OAuthRefreshToken(
            family_id=uuid4(), application_id=self.application.id, user_id=self.user.id,
            token_hash=uuid4().hex * 2, scope="openid offline_access", expires_at=now + timedelta(days=1),
        )
        reset_token = PasswordResetToken(
            user_id=self.user.id, token_hash=uuid4().hex * 2,
            expires_at=now + timedelta(minutes=20),
        )
        self.db.add_all([session, code, consent, oauth_refresh, reset_token])
        self.db.flush()
        return session

    def _assert_cascade_revoked(self) -> None:
        """断言五类凭证全部失效且审计不含口令。"""
        self.db.expire_all()
        self.assertIsNotNone(self.db.scalar(select(RefreshSession).where(
            RefreshSession.user_id == self.user.id, RefreshSession.revoked_at.isnot(None))))
        self.assertIsNotNone(self.db.scalar(select(OAuthRefreshToken).where(
            OAuthRefreshToken.user_id == self.user.id, OAuthRefreshToken.revoked_at.isnot(None))))
        self.assertIsNotNone(self.db.scalar(select(OAuthAuthorizationCode).where(
            OAuthAuthorizationCode.user_id == self.user.id, OAuthAuthorizationCode.consumed_at.isnot(None))))
        self.assertIsNotNone(self.db.scalar(select(OAuthConsentRequest).where(
            OAuthConsentRequest.user_id == self.user.id, OAuthConsentRequest.consumed_at.isnot(None))))
        self.assertIsNotNone(self.db.scalar(select(PasswordResetToken).where(
            PasswordResetToken.user_id == self.user.id, PasswordResetToken.consumed_at.isnot(None))))

    # ---- 自助修改密码 ----

    def test_change_password_revokes_all_credentials_and_invalidates_old_access_token(self) -> None:
        self._seed_credentials()
        old_access = create_access_token(self.user)

        result = change_own_password(
            PasswordChange(current_password="Old-password-123", new_password="New-password-456"),
            self.request, Response(), user=self.user, db=self.db,
        )

        self.db.expire_all()
        row = self.db.get(User, self.user.id)
        self.assertIn("重新登录", result["message"])
        self.assertTrue(verify_password("New-password-456", row.password_hash))
        self.assertFalse(verify_password("Old-password-123", row.password_hash))
        self.assertEqual(row.auth_version, 2)
        self._assert_cascade_revoked()
        event = self.db.scalar(select(AuditEvent).where(AuditEvent.action == "auth.password.change"))
        self.assertIsNotNone(event)
        self.assertNotIn("password", str(event.details).casefold())
        # 旧访问令牌随 auth_version 提升与 refresh session 撤销即时失效。
        with self.assertRaises(HTTPException) as stale:
            current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=old_access), self.db)
        self.assertEqual(stale.exception.status_code, 401)

    def test_change_password_rejects_wrong_current_password_without_touching_credentials(self) -> None:
        session = self._seed_credentials()
        with self.assertRaises(HTTPException) as ctx:
            change_own_password(
                PasswordChange(current_password="Wrong-password-000", new_password="New-password-456"),
                self.request, Response(), user=self.user, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.db.expire_all()
        row = self.db.get(User, self.user.id)
        self.assertTrue(verify_password("Old-password-123", row.password_hash))
        self.assertEqual(row.auth_version, 1)
        self.db.refresh(session)
        self.assertIsNone(session.revoked_at)
        event = self.db.scalar(select(AuditEvent).where(
            AuditEvent.action == "auth.password.change", AuditEvent.outcome == "failure"))
        self.assertIsNotNone(event)

    def test_change_password_enforces_minimum_length(self) -> None:
        with self.assertRaises(ValidationError):
            PasswordChange(current_password="Old-password-123", new_password="short-7")

    # ---- 管理员重置 ----

    def _make_admin(self) -> User:
        admin = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only",
                     display_name="管理员", status="active")
        self.db.add(admin)
        self.db.flush()
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, admin)
        return admin

    def test_admin_reset_revokes_credentials_and_bumps_auth_version(self) -> None:
        admin = self._make_admin()
        self._seed_credentials()

        result = reset_user_password(self.user.id, AdminPasswordReset(new_password="Reset-pass-789"),
                                     request=self.request, actor=admin, db=self.db)

        self.db.expire_all()
        row = self.db.get(User, self.user.id)
        self.assertEqual(result["auth_version"], 2)
        self.assertTrue(verify_password("Reset-pass-789", row.password_hash))
        self.assertFalse(verify_password("Old-password-123", row.password_hash))
        self._assert_cascade_revoked()
        event = self.db.scalar(select(AuditEvent).where(AuditEvent.action == "user.password.reset"))
        self.assertIsNotNone(event)
        self.assertEqual(event.actor_user_id, admin.id)
        self.assertNotIn("password", str(event.details).casefold())

    def test_admin_reset_forbids_self_service_bypass(self) -> None:
        admin = self._make_admin()
        with self.assertRaises(HTTPException) as ctx:
            reset_user_password(admin.id, AdminPasswordReset(new_password="Reset-pass-789"),
                                request=self.request, actor=admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_admin_reset_requires_active_user(self) -> None:
        admin = self._make_admin()
        self.user.status = "disabled"
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            reset_user_password(self.user.id, AdminPasswordReset(new_password="Reset-pass-789"),
                                request=self.request, actor=admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_admin_reset_requires_platform_admin(self) -> None:
        # 无角色绑定的普通用户直接调用管理端点必须 403（绿场后权限只认角色绑定）。
        with self.assertRaises(HTTPException) as ctx:
            reset_user_password(self.user.id, AdminPasswordReset(new_password="Reset-pass-789"),
                                request=self.request, actor=self.user, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
