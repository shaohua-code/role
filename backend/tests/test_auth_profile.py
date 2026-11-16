"""登录态自助更新展示名（PATCH /auth/me）：校验、短路、审计三闸。"""

import contextlib
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.api.v1.auth import update_me
from app.core.config import Settings
from app.db.base import Base
from app.models.identity import AuditEvent, Tenant, TenantMembership, User
from app.schemas.auth import ProfileUpdate


def make_settings() -> Settings:
    return Settings(app_env="development", jwt_secret="j" * 32, _env_file=None)


@contextlib.contextmanager
def patched_settings():
    with patch("app.api.v1.auth.get_settings", return_value=make_settings()):
        yield


class AuthProfileUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.request = Request({
            "type": "http",
            "method": "PATCH",
            "path": "/api/v1/auth/me",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "scheme": "http",
        })
        self.tenant = Tenant(name="测试租户", slug=f"t-{uuid4().hex[:10]}", kind="organization")
        self.user = User(
            id=uuid4(), email="member@example.test", display_name="旧名字",
            password_hash="x" * 64, status="active",
        )
        self.db.add(self.tenant)
        self.db.add(self.user)
        self.db.flush()
        self.db.add(TenantMembership(id=uuid4(), tenant_id=self.tenant.id, user_id=self.user.id, status="active"))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _audit_events(self) -> list[AuditEvent]:
        return list(self.db.scalars(select(AuditEvent)).all())

    def test_update_renames_user_and_writes_audit(self) -> None:
        with patched_settings():
            result = update_me(ProfileUpdate(display_name="  新名字  "), self.request, self.user, self.db)

        self.assertEqual(result.display_name, "新名字")
        self.assertEqual(self.user.display_name, "新名字")
        events = self._audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, "auth.profile.update")
        self.assertEqual(events[0].target_id, str(self.user.id))
        # strip 生效：入库值与审计新值一致，不含首尾空白
        self.assertEqual(events[0].details.get("new_display_name"), "新名字")
        self.assertEqual(events[0].details.get("old_display_name"), "旧名字")

    def test_blank_display_name_rejected(self) -> None:
        with patched_settings():
            with self.assertRaises(HTTPException) as ctx:
                update_me(ProfileUpdate(display_name="   "), self.request, self.user, self.db)

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(self.user.display_name, "旧名字")
        self.assertEqual(self._audit_events(), [])

    def test_same_name_short_circuits_without_audit(self) -> None:
        with patched_settings():
            result = update_me(ProfileUpdate(display_name="旧名字"), self.request, self.user, self.db)

        self.assertEqual(result.display_name, "旧名字")
        self.assertEqual(self._audit_events(), [])


if __name__ == "__main__":
    unittest.main()
