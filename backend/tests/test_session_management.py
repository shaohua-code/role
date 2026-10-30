"""平台管理员查看与远程撤销 IAM/OIDC 会话的 PostgreSQL 回归用例。"""

from datetime import datetime, timedelta, timezone
import unittest
from uuid import uuid4

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.users import list_user_sessions, revoke_user_session
from app.core.config import get_settings
from app.core.security import create_access_token, current_user, oidc_session_is_active
from app.db.session import get_engine
from app.models.application import Application
from app.models.identity import AuditEvent, RefreshSession, Tenant, User
from app.models.oidc import OAuthRefreshToken


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL session tests")
class UserSessionManagementIntegrationTests(unittest.TestCase):
    """每个用例通过外层事务回滚，避免把测试身份留在业务数据库。"""

    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.actor = User(
            email=f"session-admin-{uuid4().hex}@example.test",
            password_hash="test-only",
            display_name="Session Admin",
            status="active",
        )
        self.user = User(
            email=f"session-user-{uuid4().hex}@example.test",
            password_hash="test-only",
            display_name="Session User",
            status="active",
        )
        self.tenant = Tenant(name="Session Test Tenant", slug=f"session-{uuid4().hex[:24]}")
        self.db.add_all([self.actor, self.user, self.tenant])
        self.db.flush()
        # 绿场规则：actor 需显式绑定 L1 才能通过按码判权。
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        self.application = Application(
            tenant_id=self.tenant.id,
            client_id=f"session-client-{uuid4().hex}",
            name="Session Test Application",
            status="active",
        )
        self.db.add(self.application)
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    @staticmethod
    def request() -> Request:
        path = "/api/v1/admin/users/sessions"
        return Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"",
            "headers": [], "client": ("127.0.0.1", 51002), "server": ("localhost", 8000),
        })

    def test_list_returns_active_management_and_oidc_sessions_without_token_hashes(self) -> None:
        now = datetime.now(timezone.utc)
        management = RefreshSession(
            user_id=self.user.id,
            token_hash="a" * 64,
            auth_version=1,
            expires_at=now + timedelta(days=2),
        )
        family_id = uuid4()
        oidc = OAuthRefreshToken(
            family_id=family_id,
            application_id=self.application.id,
            user_id=self.user.id,
            auth_version=1,
            membership_version=1,
            token_hash="b" * 64,
            scope="openid profile offline_access",
            expires_at=now + timedelta(days=5),
        )
        expired = RefreshSession(
            user_id=self.user.id,
            token_hash="c" * 64,
            auth_version=1,
            expires_at=now - timedelta(seconds=1),
        )
        self.db.add_all([management, oidc, expired])
        self.db.flush()

        result = list_user_sessions(self.user.id, self.actor, self.db)

        self.assertEqual(result["user_id"], str(self.user.id))
        self.assertEqual({row["type"] for row in result["items"]}, {"management", "oidc"})
        self.assertEqual(len(result["items"]), 2)
        self.assertNotIn("token_hash", str(result))
        oidc_item = next(row for row in result["items"] if row["type"] == "oidc")
        self.assertEqual(oidc_item["id"], str(family_id))
        self.assertEqual(oidc_item["application_name"], self.application.name)

    def test_management_session_revoke_immediately_denies_bound_access_token(self) -> None:
        session = RefreshSession(
            user_id=self.user.id,
            token_hash="d" * 64,
            auth_version=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        )
        self.db.add(session)
        self.db.flush()
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=create_access_token(self.user, session.id),
        )
        self.assertEqual(current_user(credentials, self.db).id, self.user.id)

        result = revoke_user_session(
            self.user.id, "management", session.id, self.request(), self.actor, self.db,
        )

        self.assertEqual(result["session_id"], str(session.id))
        self.assertIsNotNone(session.revoked_at)
        with self.assertRaises(HTTPException) as denied:
            current_user(credentials, self.db)
        self.assertEqual(denied.exception.status_code, 401)
        audit_row = self.db.scalar(select(AuditEvent).where(AuditEvent.action == "user.session.revoke"))
        self.assertIsNotNone(audit_row)
        self.assertEqual(audit_row.target_id, f"management:{session.id}")

    def test_oidc_family_revoke_invalidates_online_session_and_is_idempotent(self) -> None:
        now = datetime.now(timezone.utc)
        family_id = uuid4()
        current = OAuthRefreshToken(
            family_id=family_id,
            application_id=self.application.id,
            user_id=self.user.id,
            auth_version=1,
            membership_version=1,
            token_hash="e" * 64,
            scope="openid offline_access",
            expires_at=now + timedelta(days=3),
        )
        prior = OAuthRefreshToken(
            family_id=family_id,
            application_id=self.application.id,
            user_id=self.user.id,
            auth_version=1,
            membership_version=1,
            token_hash="f" * 64,
            scope="openid offline_access",
            expires_at=now + timedelta(days=3),
            revoked_at=now - timedelta(minutes=1),
        )
        self.db.add_all([current, prior])
        self.db.flush()
        claims = {"sid": str(family_id), "sub": str(self.user.id), "client_id": self.application.client_id}
        self.assertTrue(oidc_session_is_active(claims, self.db))

        result = revoke_user_session(
            self.user.id, "oidc", family_id, self.request(), self.actor, self.db,
        )

        self.assertEqual(result["session_id"], str(family_id))
        self.assertIsNotNone(current.revoked_at)
        self.assertFalse(oidc_session_is_active(claims, self.db))
        audit_count = self.db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "user.session.revoke")
        )
        self.assertEqual(audit_count, 1)

        repeated = revoke_user_session(
            self.user.id, "oidc", family_id, self.request(), self.actor, self.db,
        )
        self.assertEqual(repeated["session_id"], str(family_id))
        final_audit_count = self.db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "user.session.revoke")
        )
        self.assertEqual(final_audit_count, 1)

    def test_admin_cannot_remote_revoke_own_user_sessions(self) -> None:
        # 非隔离库可能已有历史审计，改用调用前后对比验证拒绝路径未新增审计。
        audit_before = self.db.scalar(select(func.count()).select_from(AuditEvent))
        with self.assertRaises(HTTPException) as denied:
            revoke_user_session(
                self.actor.id, "management", uuid4(), self.request(), self.actor, self.db,
            )

        self.assertEqual(denied.exception.status_code, 400)
        audit_after = self.db.scalar(select(func.count()).select_from(AuditEvent))
        self.assertEqual(audit_after, audit_before)


if __name__ == "__main__":
    unittest.main()
