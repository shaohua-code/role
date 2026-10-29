"""到期认证凭证清理边界测试；使用独立 SQLite，不触碰开发 PostgreSQL 数据。"""

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - register the full metadata before creating the SQLite fixture
from app.db.base import Base
from app.models.identity import (
    LoginAttemptBucket,
    PasswordResetThrottle,
    PasswordResetToken,
    PublicRegistrationChallenge,
    PublicRegistrationThrottle,
    RefreshSession,
    RevokedAccessToken,
)
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.services.maintenance import cleanup_expired_credentials


class ExpiredCredentialCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.now = datetime(2030, 1, 2, tzinfo=timezone.utc)
        self.expired = self.now - timedelta(seconds=1)
        self.valid = self.now + timedelta(seconds=1)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _add_one_time_rows(self) -> None:
        self.db.add_all([
            RefreshSession(user_id=uuid4(), token_hash=f"expired-session-{uuid4().hex}", expires_at=self.expired),
            RefreshSession(user_id=uuid4(), token_hash=f"live-session-{uuid4().hex}", expires_at=self.valid),
            RevokedAccessToken(jti_hash=f"{uuid4().hex}{uuid4().hex}", token_use="management_access",
                               expires_at=self.expired),
            RevokedAccessToken(jti_hash=f"{uuid4().hex}{uuid4().hex}", token_use="management_access",
                               expires_at=self.valid),
            OAuthAuthorizationCode(application_id=uuid4(), user_id=uuid4(), code_hash=f"{uuid4().hex}{uuid4().hex}",
                                   redirect_uri="https://client.example.test/callback", scope="openid",
                                   nonce="nonce", code_challenge="challenge", code_challenge_method="S256",
                                   expires_at=self.expired),
            OAuthAuthorizationCode(application_id=uuid4(), user_id=uuid4(), code_hash=f"{uuid4().hex}{uuid4().hex}",
                                   redirect_uri="https://client.example.test/callback", scope="openid",
                                   nonce="nonce", code_challenge="challenge", code_challenge_method="S256",
                                   expires_at=self.valid),
            OAuthConsentRequest(application_id=uuid4(), user_id=uuid4(), ticket_hash=f"{uuid4().hex}{uuid4().hex}",
                                redirect_uri="https://client.example.test/callback", client_state="state",
                                scope="openid", nonce="nonce", code_challenge="challenge",
                                code_challenge_method="S256", expires_at=self.expired),
            OAuthConsentRequest(application_id=uuid4(), user_id=uuid4(), ticket_hash=f"{uuid4().hex}{uuid4().hex}",
                                redirect_uri="https://client.example.test/callback", client_state="state",
                                scope="openid", nonce="nonce", code_challenge="challenge",
                                code_challenge_method="S256", expires_at=self.valid),
            PasswordResetToken(user_id=uuid4(), token_hash=f"{uuid4().hex}{uuid4().hex}",
                               expires_at=self.expired),
            PasswordResetToken(user_id=uuid4(), token_hash=f"{uuid4().hex}{uuid4().hex}",
                               expires_at=self.valid),
            PasswordResetThrottle(email_hash=f"{uuid4().hex}{uuid4().hex}",
                                  last_requested_at=self.expired - timedelta(days=1), expires_at=self.expired),
            PasswordResetThrottle(email_hash=f"{uuid4().hex}{uuid4().hex}",
                                  last_requested_at=self.valid - timedelta(days=1), expires_at=self.valid),
            LoginAttemptBucket(key_hash=f"{uuid4().hex}{uuid4().hex}", failed_attempts=2,
                               window_started_at=self.expired - timedelta(minutes=20), expires_at=self.expired),
            LoginAttemptBucket(key_hash=f"{uuid4().hex}{uuid4().hex}", failed_attempts=0,
                               window_started_at=self.valid - timedelta(minutes=1), expires_at=self.valid),
            PublicRegistrationChallenge(
                id=uuid4(), application_id=uuid4(), email_hash=f"{uuid4().hex}{uuid4().hex}",
                email="expired@example.com", display_name="过期申请",
                existing_user_id=None,
                registration_role_id=uuid4(),
                registration_role_fingerprint="f" * 64,
                verification_code_hash="a" * 64,
                terms_version="terms-v1", privacy_version="privacy-v1",
                terms_url="https://example.test/terms", privacy_url="https://example.test/privacy",
                failed_attempts=0,
                expires_at=self.expired,
            ),
            PublicRegistrationChallenge(
                id=uuid4(), application_id=uuid4(), email_hash=f"{uuid4().hex}{uuid4().hex}",
                email="live@example.com", display_name="有效申请",
                existing_user_id=None,
                registration_role_id=uuid4(),
                registration_role_fingerprint="f" * 64,
                verification_code_hash="b" * 64,
                terms_version="terms-v1", privacy_version="privacy-v1",
                terms_url="https://example.test/terms", privacy_url="https://example.test/privacy",
                failed_attempts=0,
                expires_at=self.valid,
            ),
            PublicRegistrationThrottle(
                bucket_hash=f"{uuid4().hex}{uuid4().hex}",
                last_requested_at=self.expired - timedelta(days=1), expires_at=self.expired,
            ),
            PublicRegistrationThrottle(
                bucket_hash=f"{uuid4().hex}{uuid4().hex}",
                last_requested_at=self.valid - timedelta(days=1), expires_at=self.valid,
            ),
            # 即便旧 refresh token 已到期，也保留记录用于整族重放检测。
            OAuthRefreshToken(family_id=uuid4(), application_id=uuid4(), user_id=uuid4(),
                              token_hash=f"{uuid4().hex}{uuid4().hex}", scope="openid offline_access",
                              expires_at=self.expired, revoked_at=self.expired),
        ])
        self.db.commit()

    def _count(self, model: type) -> int:
        return self.db.scalar(select(func.count()).select_from(model)) or 0

    def test_only_expired_ephemeral_credentials_are_deleted(self) -> None:
        self._add_one_time_rows()

        deleted = cleanup_expired_credentials(self.db, now=self.now, batch_size=20)

        self.assertEqual(deleted, {
            "refresh_sessions": 1,
            "revoked_access_tokens": 1,
            "oauth_authorization_codes": 1,
            "oauth_consent_requests": 1,
            "password_reset_tokens": 1,
            "password_reset_throttles": 1,
            "login_attempt_buckets": 1,
            "public_registration_challenges": 1,
            "public_registration_throttles": 1,
        })
        self.assertEqual(self._count(RefreshSession), 1)
        self.assertEqual(self._count(RevokedAccessToken), 1)
        self.assertEqual(self._count(OAuthAuthorizationCode), 1)
        self.assertEqual(self._count(OAuthConsentRequest), 1)
        self.assertEqual(self._count(PasswordResetToken), 1)
        self.assertEqual(self._count(PasswordResetThrottle), 1)
        self.assertEqual(self._count(LoginAttemptBucket), 1)
        self.assertEqual(self._count(PublicRegistrationChallenge), 1)
        self.assertEqual(self._count(PublicRegistrationThrottle), 1)
        self.assertEqual(self._count(OAuthRefreshToken), 1)

    def test_cleanup_is_bounded_and_idempotent(self) -> None:
        self._add_one_time_rows()
        second_expired = self.now - timedelta(minutes=1)
        self.db.add(RefreshSession(user_id=uuid4(), token_hash=f"expired-session-{uuid4().hex}",
                                   expires_at=second_expired))
        self.db.commit()

        first = cleanup_expired_credentials(self.db, now=self.now, batch_size=1)
        second = cleanup_expired_credentials(self.db, now=self.now, batch_size=1)

        self.assertEqual(first["refresh_sessions"], 1)
        self.assertEqual(second["refresh_sessions"], 1)
        self.assertEqual(self._count(RefreshSession), 1)
        self.assertTrue(all(count <= 1 for count in first.values()))
        self.assertEqual(second, {
            "refresh_sessions": 1,
            "revoked_access_tokens": 0,
            "oauth_authorization_codes": 0,
            "oauth_consent_requests": 0,
            "password_reset_tokens": 0,
            "password_reset_throttles": 0,
            "login_attempt_buckets": 0,
            "public_registration_challenges": 0,
            "public_registration_throttles": 0,
        })

    def test_rejects_naive_timestamp_and_empty_batch(self) -> None:
        with self.assertRaises(ValueError):
            cleanup_expired_credentials(self.db, now=datetime(2030, 1, 2), batch_size=1)
        with self.assertRaises(ValueError):
            cleanup_expired_credentials(self.db, now=self.now, batch_size=0)


if __name__ == "__main__":
    unittest.main()
