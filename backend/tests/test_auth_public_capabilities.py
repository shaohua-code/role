"""公开认证能力探针：SMTP 找回与管理台绑定 client 的注册入口。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.api.v1.auth import public_capabilities
from app.core.config import Settings
from app.db.base import Base
from app.models.application import Application, ApplicationTheme
from app.models.authorization import Role
from app.models.identity import Tenant
class AuthPublicCapabilitiesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.settings = Settings(
            app_env="development",
            jwt_secret="j" * 32,
            allow_public_registration=True,
            public_registration_secret="r" * 32,
            smtp_host="smtp.example.test",
            smtp_from="no-reply@example.test",
            console_registration_client_id="console-reg-client",
        )
        self.tenant = Tenant(name="ToC", slug=f"toc-{uuid4().hex[:10]}", kind="consumer")
        self.db.add(self.tenant)
        self.db.flush()
        self.application = Application(
            tenant_id=self.tenant.id,
            client_id="console-reg-client",
            name="控制台注册试点",
            redirect_uris=["http://localhost:5175/callback"],
            post_logout_redirect_uris=[],
            registration_policy="open",
            registration_terms_version="terms-v1",
            registration_privacy_version="privacy-v1",
        )
        self.db.add(self.application)
        self.db.flush()
        self.role = Role(
            tenant_id=self.tenant.id,
            application_id=self.application.id,
            key="console.member",
            name="普通用户",
            status="active",
        )
        self.db.add(self.role)
        self.db.flush()
        self.application.registration_role_id = self.role.id
        self.db.add(ApplicationTheme(
            application_id=self.application.id,
            version=1,
            status="published",
            config={
                "show_register": True,
                "terms_url": "https://example.test/terms",
                "privacy_url": "https://example.test/privacy",
            },
        ))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_reports_password_reset_and_console_registration(self) -> None:
        with patch("app.api.v1.auth.get_settings", return_value=self.settings):
            payload = public_capabilities(self.db)
        self.assertTrue(payload.password_reset_available)
        self.assertIsNotNone(payload.console_registration)
        assert payload.console_registration is not None
        self.assertEqual(payload.console_registration.client_id, "console-reg-client")
        self.assertTrue(payload.console_registration.registration.available)

    def test_console_registration_hidden_when_smtp_missing(self) -> None:
        settings = self.settings.model_copy(update={"smtp_host": None, "smtp_from": None})
        with patch("app.api.v1.auth.get_settings", return_value=settings):
            payload = public_capabilities(self.db)
        self.assertFalse(payload.password_reset_available)
        self.assertIsNone(payload.console_registration)


if __name__ == "__main__":
    unittest.main()
