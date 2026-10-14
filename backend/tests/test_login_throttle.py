"""短期登录节流桶测试；使用 SQLite 内存库，不触碰 IAM 开发 PostgreSQL。"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.identity import LoginAttemptBucket
from app.services.login_throttle import (begin_login_attempt, client_ip_for_request,
                                         clear_login_identifier_failures, record_login_failure)


class LoginThrottleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        LoginAttemptBucket.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.settings = SimpleNamespace(
            jwt_secret="test-login-throttle-key-that-is-long-enough",
            login_attempt_window_seconds=300,
            login_identifier_max_failures=2,
            login_ip_max_failures=3,
            login_block_seconds=60,
            trust_proxy_client_ip=False,
        )
        self.now = datetime(2030, 1, 2, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    @staticmethod
    def _request(*, client_host: str = "192.0.2.15", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
        path = "/api/v1/auth/login"
        return Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http", "path": path,
            "raw_path": path.encode(), "root_path": "", "query_string": b"",
            "headers": headers or [], "client": (client_host, 51002), "server": ("localhost", 8000),
        })

    def test_identifier_pair_is_blocked_after_failures_and_only_hashed_keys_are_stored(self) -> None:
        first = begin_login_attempt(self.db, "Person@Example.test", "192.0.2.15", self.settings, now=self.now)
        record_login_failure(self.db, first, self.settings, now=self.now)
        self.db.commit()

        second = begin_login_attempt(self.db, "person@example.test", "192.0.2.15", self.settings,
                                     now=self.now + timedelta(seconds=1))
        self.assertIsNone(second.blocked_until)
        record_login_failure(self.db, second, self.settings, now=self.now + timedelta(seconds=1))
        self.db.commit()

        blocked = begin_login_attempt(self.db, "person@example.test", "192.0.2.15", self.settings,
                                      now=self.now + timedelta(seconds=2))
        self.assertEqual(blocked.blocked_until, self.now + timedelta(seconds=61))
        stored_keys = self.db.scalars(select(LoginAttemptBucket.key_hash)).all()
        self.assertEqual(len(stored_keys), 2)
        self.assertTrue(all(len(key) == 64 for key in stored_keys))
        self.assertNotIn("person@example.test", "".join(stored_keys))
        self.assertNotIn("192.0.2.15", "".join(stored_keys))

    def test_success_resets_only_the_current_identifier_pair(self) -> None:
        first = begin_login_attempt(self.db, "person@example.test", "192.0.2.15", self.settings, now=self.now)
        record_login_failure(self.db, first, self.settings, now=self.now)
        clear_login_identifier_failures(self.db, first, self.settings, now=self.now + timedelta(seconds=1))
        self.db.commit()

        next_attempt = begin_login_attempt(self.db, "person@example.test", "192.0.2.15", self.settings,
                                           now=self.now + timedelta(seconds=2))
        self.assertIsNone(next_attempt.blocked_until)
        self.assertEqual(self.db.get(LoginAttemptBucket, first.identifier_key).failed_attempts, 0)
        self.assertEqual(self.db.get(LoginAttemptBucket, first.address_key).failed_attempts, 1)

    def test_expired_failure_window_resets_before_password_check(self) -> None:
        first = begin_login_attempt(self.db, "person@example.test", "192.0.2.15", self.settings, now=self.now)
        record_login_failure(self.db, first, self.settings, now=self.now)
        self.db.commit()

        next_attempt = begin_login_attempt(self.db, "person@example.test", "192.0.2.15", self.settings,
                                           now=self.now + timedelta(seconds=301))
        self.assertIsNone(next_attempt.blocked_until)
        self.assertEqual(self.db.get(LoginAttemptBucket, first.identifier_key).failed_attempts, 0)

    def test_address_bucket_caps_failures_across_different_accounts(self) -> None:
        for index in range(self.settings.login_ip_max_failures):
            ticket = begin_login_attempt(
                self.db, f"person-{index}@example.test", "192.0.2.15", self.settings,
                now=self.now + timedelta(seconds=index),
            )
            self.assertIsNone(ticket.blocked_until)
            record_login_failure(self.db, ticket, self.settings, now=self.now + timedelta(seconds=index))
            self.db.commit()

        blocked = begin_login_attempt(self.db, "another@example.test", "192.0.2.15", self.settings,
                                      now=self.now + timedelta(seconds=10))
        self.assertEqual(blocked.blocked_until, self.now + timedelta(seconds=62))

    def test_proxy_address_is_used_only_when_explicitly_trusted(self) -> None:
        request = self._request(client_host="10.0.0.9", headers=[(b"x-iam-client-ip", b"2001:0db8::1")])
        self.assertEqual(client_ip_for_request(request, self.settings), "10.0.0.9")

        self.settings.trust_proxy_client_ip = True
        self.assertEqual(client_ip_for_request(request, self.settings), "2001:db8::1")
        bad_request = self._request(headers=[(b"x-iam-client-ip", b"attacker-value")])
        with self.assertRaises(HTTPException) as raised:
            client_ip_for_request(bad_request, self.settings)
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
