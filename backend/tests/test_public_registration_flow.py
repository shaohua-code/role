"""验证先证明邮箱、再设置新密码或证明已有账号凭据的公开注册顺序。"""

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException, Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

import app.api.v1.auth as auth_api
import app.models  # noqa: F401 - 注册完整 ORM metadata
from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.models import (
    Application,
    ApplicationTheme,
    PublicRegistrationChallenge,
    Permission,
    Role,
    RoleBinding,
    RoleDataScope,
    RolePermission,
    Tenant,
    TenantMembership,
    User,
)
from app.schemas.auth import RegisterVerifyRequest
from app.services.public_registration import (
    _code_digest,
    registration_email_hash,
    registration_role_fingerprint,
)


class PublicRegistrationCredentialFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.settings = Settings(
            app_env="development", jwt_secret="j" * 32, allow_public_registration=True,
            public_registration_secret="r" * 32, smtp_host="smtp.example.test",
            smtp_from="no-reply@example.test",
        )
        self.tenant = Tenant(name="ToC", slug=f"toc-{uuid4().hex[:12]}", kind="consumer")
        self.db.add(self.tenant)
        self.db.flush()
        self.application = Application(
            tenant_id=self.tenant.id, client_id=f"toc-{uuid4().hex[:12]}", name="ToC 产品",
            redirect_uris=["https://product.example.test/callback"], post_logout_redirect_uris=[],
            registration_policy="open", registration_role_id=None,
            registration_terms_version="terms-v1", registration_privacy_version="privacy-v1",
        )
        self.db.add(self.application)
        self.db.flush()
        self.role = Role(
            tenant_id=self.tenant.id, application_id=self.application.id,
            key="toc.member", name="普通用户", status="active",
        )
        self.db.add(self.role)
        self.db.flush()
        self.application.registration_role_id = self.role.id
        role_fingerprint = registration_role_fingerprint(self.db, self.role)
        self.db.add(ApplicationTheme(
            application_id=self.application.id, version=1, status="published",
            config={"show_register": True,
                    "terms_url": "https://product.example.test/terms",
                    "privacy_url": "https://product.example.test/privacy"},
        ))
        self.email = "person@example.com"
        self.challenge_id = uuid4()
        now = datetime.now(timezone.utc)
        self.challenge = PublicRegistrationChallenge(
            id=self.challenge_id, application_id=self.application.id,
            email_hash=registration_email_hash(self.settings, self.application.id, self.email),
            email=self.email, display_name="新用户", existing_user_id=None,
            registration_role_id=self.role.id,
            registration_role_fingerprint=role_fingerprint,
            verification_code_hash=_code_digest(self.settings, self.challenge_id, "123456"),
            terms_version="terms-v1", privacy_version="privacy-v1",
            terms_url="https://product.example.test/terms",
            privacy_url="https://product.example.test/privacy",
            failed_attempts=0, expires_at=now + timedelta(minutes=10),
        )
        self.db.add(self.challenge)
        self.db.commit()
        self.request = Request({
            "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": "/api/v1/auth/register/verify", "raw_path": b"/api/v1/auth/register/verify",
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
        })
        self.patches = [
            patch.object(auth_api, "get_settings", return_value=self.settings),
            patch.object(auth_api, "ensure_signing_key"),
            patch.object(auth_api, "new_refresh_token", return_value=("refresh", now + timedelta(days=1), uuid4())),
            patch.object(auth_api, "create_access_token", return_value="access"),
            patch.object(auth_api, "set_refresh_cookie"),
            patch.object(auth_api, "record_event"),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def verify(self, password: str):
        response = Response()
        body = RegisterVerifyRequest(
            client_id=self.application.client_id, email=self.email, code="123456", password=password,
        )
        return auth_api.verify_registration(body, self.request, response, self.db)

    def test_new_account_password_is_set_only_after_email_code_and_low_password_can_retry(self) -> None:
        with self.assertRaises(HTTPException) as error:
            self.verify("short")
        self.assertEqual(error.exception.status_code, 422)
        self.assertIsNone(self.db.scalar(select(User.id).where(User.email == self.email)))
        self.assertIsNone(self.challenge.consumed_at)

        result = self.verify("a sufficiently long password")

        self.assertEqual(result.user.email, self.email)
        user = self.db.scalar(select(User).where(User.email == self.email))
        self.assertIsNotNone(user)
        self.assertTrue(verify_password("a sufficiently long password", user.password_hash))
        membership = self.db.scalar(select(TenantMembership).where(
            TenantMembership.user_id == user.id, TenantMembership.tenant_id == self.tenant.id,
        ))
        self.assertIsNotNone(membership)
        self.assertIsNotNone(self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.membership_id == membership.id, RoleBinding.role_id == self.role.id,
        )))

    def test_changed_registration_role_consumes_old_challenge(self) -> None:
        replacement_role = Role(
            tenant_id=self.tenant.id, application_id=self.application.id,
            key="toc.member.v2", name="新普通用户角色", status="active",
        )
        self.db.add(replacement_role)
        self.db.flush()
        self.application.registration_role_id = replacement_role.id
        self.db.commit()

        with self.assertRaises(HTTPException) as error:
            self.verify("a sufficiently long password")

        self.assertEqual(error.exception.status_code, 400)
        self.assertIsNotNone(self.challenge.consumed_at)
        self.assertIsNone(self.db.scalar(select(User.id).where(User.email == self.email)))
        self.assertIsNone(self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.role_id == replacement_role.id,
        )))

    def test_permission_and_data_scope_change_on_same_role_consumes_old_challenge(self) -> None:
        permission = Permission(
            code="resume.read", resource_type="resume", scope="read", status="active",
        )
        self.db.add(permission)
        self.db.flush()
        self.db.add(RolePermission(role_id=self.role.id, permission_id=permission.id))
        self.db.add(RoleDataScope(
            tenant_id=self.tenant.id, role_id=self.role.id, permission_id=permission.id,
            scope_type="self", organization_ids=[],
        ))
        self.db.commit()

        with self.assertRaises(HTTPException) as error:
            self.verify("a sufficiently long password")

        self.assertEqual(error.exception.status_code, 400)
        self.assertIsNotNone(self.challenge.consumed_at)
        self.assertIsNone(self.db.scalar(select(User.id).where(User.email == self.email)))
    def test_existing_user_uses_current_password_without_replacing_it(self) -> None:
        old_password_hash = hash_password("old-legacy-pass")
        user = User(email=self.email, password_hash=old_password_hash, display_name="已有用户")
        self.db.add(user)
        self.db.flush()
        self.challenge.existing_user_id = user.id
        self.db.commit()

        result = self.verify("old-legacy-pass")

        self.assertEqual(result.user.id, user.id)
        self.assertEqual(user.password_hash, old_password_hash)


if __name__ == "__main__":
    unittest.main()
