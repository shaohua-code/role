"""管理会话 JWT 撤销集成用例；数据库操作在外层事务中回滚。"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.auth import logout
from app.core.config import get_settings
from app.core.security import create_access_token, current_user
from app.db.session import get_engine
from app.models.identity import RevokedAccessToken, User


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL integration tests")
class AccessTokenRevocationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(email=f"revoke-{uuid4().hex}@example.test", password_hash="test-only",
                         display_name="Revocation Test", status="active")
        self.db.add(self.user)
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def test_management_logout_revocation_is_immediate_and_stores_only_jti_digest(self) -> None:
        raw_token = create_access_token(self.user)
        bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw_token)
        self.assertEqual(current_user(bearer, self.db).id, self.user.id)

        path = "/api/v1/auth/logout"
        request = Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"",
            "headers": [], "client": ("127.0.0.1", 51001), "server": ("localhost", 8000),
        })
        logout(request, Response(), None, bearer, self.user, self.db)

        with self.assertRaises(HTTPException) as denied:
            current_user(bearer, self.db)
        self.assertEqual(denied.exception.status_code, 401)
        row = self.db.scalar(select(RevokedAccessToken))
        self.assertIsNotNone(row)
        self.assertEqual(len(row.jti_hash), 64)
        self.assertNotIn(raw_token, row.jti_hash)
