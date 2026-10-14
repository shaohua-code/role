"""密码重置原子性与会话失效集成测试；所有写入在外层事务回滚。"""

import hashlib
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.auth import complete_password_reset
from app.core.config import get_settings
from app.core.security import create_access_token, current_user, hash_password, verify_password
from app.db.session import get_engine
from app.models.application import Application
from app.models.identity import (AuditEvent, PasswordResetToken, RefreshSession, Tenant, User)
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.schemas.auth import PasswordResetComplete, PasswordResetRequest


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL integration tests")
class PasswordResetIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.settings = get_settings().model_copy(update={"jwt_secret": "reset-test-signing-secret-" + "x" * 32})
        self.patches = ExitStack()
        self.patches.enter_context(patch("app.api.v1.auth.get_settings", return_value=self.settings))
        self.patches.enter_context(patch("app.core.security.get_settings", return_value=self.settings))

        suffix = uuid4().hex
        self.tenant = Tenant(name="Password Reset Test", slug=f"password-reset-{suffix}")
        self.user = User(email=f"reset-{suffix}@example.com", password_hash=hash_password("Old-password-123"),
                         display_name="Password Reset Test")
        self.db.add_all([self.tenant, self.user])
        self.db.flush()
        self.application = Application(
            tenant_id=self.tenant.id, client_id=f"reset-test-{suffix}", name="Reset Test Client",
            redirect_uris=["https://client.example.test/callback"],
            post_logout_redirect_uris=[], status="active",
        )
        self.db.add(self.application)
        self.db.flush()

    def tearDown(self) -> None:
        self.patches.close()
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    @staticmethod
    def _request() -> Request:
        path = "/api/v1/auth/password-reset/complete"
        return Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http", "path": path,
            "raw_path": path.encode(), "root_path": "", "query_string": b"", "headers": [],
            "client": ("127.0.0.1", 51002), "server": ("localhost", 8000),
        })

    def test_reset_consumes_token_revokes_sessions_and_invalidates_old_access_token(self) -> None:
        raw_reset = "password-reset-" + uuid4().hex + uuid4().hex
        raw_refresh = "browser-refresh-" + uuid4().hex
        reset_row = PasswordResetToken(
            user_id=self.user.id,
            token_hash=hashlib.sha256(raw_reset.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=20),
        )
        session = RefreshSession(
            user_id=self.user.id, token_hash=hashlib.sha256(raw_refresh.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        old_access = create_access_token(self.user)
        now = datetime.now(timezone.utc)
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
        self.db.add_all([reset_row, session, code, consent, oauth_refresh])
        self.db.flush()

        result = complete_password_reset(
            PasswordResetComplete(token=raw_reset, new_password="New-password-456"),
            self._request(), Response(), self.db,
        )

        self.db.refresh(self.user)
        self.db.refresh(reset_row)
        self.db.refresh(session)
        self.db.refresh(code)
        self.db.refresh(consent)
        self.db.refresh(oauth_refresh)
        self.assertIn("密码已重置", result["message"])
        self.assertTrue(verify_password("New-password-456", self.user.password_hash))
        self.assertFalse(verify_password("Old-password-123", self.user.password_hash))
        self.assertIsNotNone(self.user.email_verified_at)
        self.assertEqual(self.user.auth_version, 2)
        self.assertEqual(reset_row.consumed_at, session.revoked_at)
        self.assertIsNotNone(code.consumed_at)
        self.assertIsNotNone(consent.consumed_at)
        self.assertIsNotNone(oauth_refresh.revoked_at)
        with self.assertRaises(HTTPException) as stale_access:
            current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=old_access), self.db)
        self.assertEqual(stale_access.exception.status_code, 401)

        with self.assertRaises(HTTPException) as replay:
            complete_password_reset(
                PasswordResetComplete(token=raw_reset, new_password="Another-password-789"),
                self._request(), Response(), self.db,
            )
        self.assertEqual(replay.exception.status_code, 400)
        event = self.db.scalar(select(AuditEvent).where(AuditEvent.action == "auth.password_reset.complete"))
        self.assertIsNotNone(event)
        self.assertNotIn("password", str(event.details).casefold())

    def test_request_does_not_disclose_account_existence_and_throttles_email(self) -> None:
        self.settings = self.settings.model_copy(update={
            "smtp_host": "smtp.example.test", "smtp_from": "iam@example.com",
            "password_reset_cooldown_seconds": 60,
        })
        with patch("app.api.v1.auth.get_settings", return_value=self.settings), \
                patch("app.api.v1.auth.send_password_reset_email") as send_email:
            from app.api.v1.auth import request_password_reset

            known = request_password_reset(PasswordResetRequest(email=self.user.email), self._request(), Response(), self.db)
            throttled = request_password_reset(PasswordResetRequest(email=self.user.email), self._request(), Response(), self.db)
            unknown = request_password_reset(
                PasswordResetRequest(email=f"unknown-{uuid4().hex}@example.com"),
                self._request(), Response(), self.db,
            )

        self.assertEqual(known, throttled)
        self.assertEqual(known, unknown)
        send_email.assert_called_once()
        reset_row = self.db.scalar(select(PasswordResetToken).where(
            PasswordResetToken.user_id == self.user.id,
        ))
        self.assertIsNotNone(reset_row)
        self.assertNotEqual(reset_row.token_hash, send_email.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
