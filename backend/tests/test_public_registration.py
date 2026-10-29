"""覆盖 ToC 注册关键策略、验证码绑定和密钥轮换边界，不连接项目数据库。"""

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - 注册完整 ORM metadata
from app.core.config import Settings
from app.db.base import Base
from app.models import (
    Application,
    ApplicationTheme,
    Permission,
    PublicRegistrationChallenge,
    RoleDataScope,
    Role,
    RolePermission,
    Tenant,
)
from app.schemas.auth import RegisterRequest, RegisterVerifyRequest
from app.services.public_registration import (
    _code_digest,
    _derived_code,
    application_registration_details,
    eligible_registration_role,
    registration_email_hash,
    registration_role_fingerprint,
    request_registration_code,
    RegistrationPolicyChanged,
    verify_registration_code,
)


class PublicRegistrationContractTests(unittest.TestCase):
    def test_registration_inputs_reject_client_selected_authority(self) -> None:
        request = RegisterRequest(
            client_id="toc-client",
            email="person@example.com",
            display_name="用户",
            accepted_terms=True,
            accepted_privacy=True,
            terms_version="2026-10",
            privacy_version="2026-10",
            terms_url="https://product.example.test/terms",
            privacy_url="https://product.example.test/privacy",
        )
        self.assertEqual(request.display_name, "用户")
        self.assertNotIn("password", RegisterRequest.model_fields)

        with self.assertRaises(ValidationError):
            RegisterRequest(
                client_id="toc-client",
                email="person@example.com",
                display_name="用户",
                accepted_terms=True,
                accepted_privacy=True,
                terms_version="2026-10",
                privacy_version="2026-10",
                terms_url="https://product.example.test/terms",
                privacy_url="https://product.example.test/privacy",
                tenant_id=str(uuid4()),
            )
        with self.assertRaises(ValidationError):
            RegisterRequest(
                client_id="toc-client", email="person@example.com", display_name="用户",
                accepted_terms=True, accepted_privacy=True,
                terms_version="2026-10", privacy_version="2026-10",
                terms_url="https://product.example.test/terms",
                privacy_url="https://product.example.test/privacy",
                password="must-not-be-sent-before-email-verification",
            )
        with self.assertRaises(ValidationError):
            RegisterVerifyRequest(
                client_id="toc-client", email="person@example.com", code="123456",
                password="password", role_id=str(uuid4()),
            )

    def test_registration_gate_requires_a_dedicated_secret(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(
                app_env="development", allow_public_registration=True,
                public_registration_secret="too-short",
            )
        settings = Settings(
            app_env="development", allow_public_registration=True,
            public_registration_secret="r" * 32,
        )
        self.assertEqual(len(settings.public_registration_secret), 32)

    def test_registration_hmac_remains_stable_across_jwt_rotation(self) -> None:
        registration_key = "r" * 32
        old_settings = Settings(
            app_env="development", jwt_secret="a" * 32,
            public_registration_secret=registration_key,
        )
        rotated_jwt_settings = Settings(
            app_env="development", jwt_secret="b" * 32,
            public_registration_secret=registration_key,
        )
        application_id, challenge_id = uuid4(), uuid4()

        self.assertEqual(
            registration_email_hash(old_settings, application_id, "user@example.test"),
            registration_email_hash(rotated_jwt_settings, application_id, "user@example.test"),
        )
        self.assertEqual(_derived_code(old_settings, challenge_id),
                         _derived_code(rotated_jwt_settings, challenge_id))
        self.assertEqual(_code_digest(old_settings, challenge_id, "123456"),
                         _code_digest(rotated_jwt_settings, challenge_id, "123456"))


class PublicRegistrationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.settings = Settings(
            app_env="development",
            allow_public_registration=True,
            public_registration_secret="s" * 32,
            smtp_host="smtp.example.test",
            smtp_from="no-reply@example.test",
            public_registration_max_attempts=3,
            public_registration_cooldown_seconds=120,
        )
        self.tenant = Tenant(id=uuid4(), name="ToC", slug=f"toc-{uuid4().hex[:12]}", kind="consumer")
        self.db.add(self.tenant)
        self.db.flush()
        self.application = Application(
            id=uuid4(), tenant_id=self.tenant.id, client_id=f"toc-{uuid4().hex[:12]}",
            name="ToC 产品", redirect_uris=["https://product.example.test/callback"],
            post_logout_redirect_uris=[], trusted=False,
            registration_policy="open", registration_terms_version="terms-v1",
            registration_privacy_version="privacy-v1",
        )
        self.role = Role(
            id=uuid4(), tenant_id=self.tenant.id, application_id=self.application.id,
            key="toc.member", name="普通用户", status="active",
        )
        self.application.registration_role_id = self.role.id
        self.db.add_all([self.application, self.role])
        self.db.flush()
        self.role_fingerprint = registration_role_fingerprint(self.db, self.role)
        self.theme = ApplicationTheme(
            id=uuid4(), application_id=self.application.id, version=1, status="published",
            config={
                "show_register": True,
                "terms_url": "https://product.example.test/terms",
                "privacy_url": "https://product.example.test/privacy",
            },
        )
        self.db.add(self.theme)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_open_policy_needs_published_legal_theme_and_same_app_role(self) -> None:
        details = application_registration_details(
            self.db, self.application, settings=self.settings,
        )
        self.assertIsNotNone(details)
        self.assertEqual(details["terms_version"], "terms-v1")
        self.assertEqual(details["resend_cooldown_seconds"], 120)

        self.theme.config = {"show_register": False}
        self.db.commit()
        self.assertIsNone(application_registration_details(
            self.db, self.application, settings=self.settings,
        ))

    def test_organization_tenant_cannot_offer_public_registration(self) -> None:
        self.tenant.kind = "organization"
        self.db.commit()
        self.assertIsNone(application_registration_details(
            self.db, self.application, settings=self.settings,
        ))

    def test_registration_challenge_never_has_a_password_column(self) -> None:
        self.assertNotIn("password_hash", PublicRegistrationChallenge.__table__.columns)

    def test_stale_policy_url_is_rejected_before_creating_registration_request(self) -> None:
        with self.assertRaises(RegistrationPolicyChanged):
            request_registration_code(
                self.db,
                application=self.application,
                email="person@example.com",
                display_name="用户",
                terms_version="terms-v1",
                privacy_version="privacy-v1",
                terms_url="https://old.example.test/terms",
                privacy_url="https://product.example.test/privacy",
                client_ip="127.0.0.1",
                settings=self.settings,
            )

    def test_global_and_per_app_gates_default_to_deny(self) -> None:
        disabled_settings = Settings(
            app_env="development", allow_public_registration=False,
            public_registration_secret="s" * 32,
            smtp_host="smtp.example.test", smtp_from="no-reply@example.test",
        )
        self.assertIsNone(application_registration_details(
            self.db, self.application, settings=disabled_settings,
        ))

        self.application.registration_policy = "disabled"
        self.db.commit()
        self.assertIsNone(application_registration_details(
            self.db, self.application, settings=self.settings,
        ))

    def test_admin_scoped_roles_are_never_eligible_as_registration_default(self) -> None:
        admin_permission = Permission(
            id=uuid4(), code="platform.account.manage", resource_type="user", scope="read",
            status="active",
        )
        self.db.add(admin_permission)
        self.db.flush()
        self.db.add(RolePermission(role_id=self.role.id, permission_id=admin_permission.id))
        self.db.commit()

        self.assertIsNone(eligible_registration_role(self.db, self.application, self.role.id))

    def test_registration_role_cannot_grant_tenant_or_organization_data_scope(self) -> None:
        permission = Permission(
            id=uuid4(), code="resume.read", resource_type="resume", scope="read",
            status="active",
        )
        self.db.add(permission)
        self.db.flush()
        self.db.add_all([
            RolePermission(role_id=self.role.id, permission_id=permission.id),
            RoleDataScope(
                tenant_id=self.tenant.id,
                role_id=self.role.id,
                permission_id=permission.id,
                scope_type="tenant",
                organization_ids=[],
            ),
        ])
        self.db.commit()

        self.assertIsNone(eligible_registration_role(self.db, self.application, self.role.id))

    def test_registration_role_can_keep_personal_data_scope(self) -> None:
        permission = Permission(
            id=uuid4(), code="resume.read", resource_type="resume", scope="read",
            status="active",
        )
        self.db.add(permission)
        self.db.flush()
        self.db.add_all([
            RolePermission(role_id=self.role.id, permission_id=permission.id),
            RoleDataScope(
                tenant_id=self.tenant.id,
                role_id=self.role.id,
                permission_id=permission.id,
                scope_type="self",
                organization_ids=[],
            ),
        ])
        self.db.commit()

        self.assertEqual(eligible_registration_role(self.db, self.application, self.role.id).id, self.role.id)

    def test_code_attempt_limit_consumes_challenge(self) -> None:
        now = datetime.now(timezone.utc)
        challenge_id = uuid4()
        challenge = PublicRegistrationChallenge(
            id=challenge_id,
            application_id=self.application.id,
            email_hash="e" * 64,
            email="person@example.com",
            display_name="用户",
            existing_user_id=None,
            registration_role_id=self.role.id,
            registration_role_fingerprint=self.role_fingerprint,
            verification_code_hash=_code_digest(self.settings, challenge_id, "123456"),
            terms_version="terms-v1",
            privacy_version="privacy-v1",
            terms_url="https://product.example.test/terms",
            privacy_url="https://product.example.test/privacy",
            failed_attempts=0,
            expires_at=now + timedelta(minutes=10),
        )
        self.db.add(challenge)
        self.db.commit()

        for attempt in range(1, 4):
            self.assertFalse(verify_registration_code(
                self.db, challenge, "000000", now=now, settings=self.settings,
            ))
            self.assertEqual(challenge.failed_attempts, attempt)

        self.assertIsNotNone(challenge.consumed_at)


if __name__ == "__main__":
    unittest.main()
