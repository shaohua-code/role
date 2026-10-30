"""生产配置必须显式绑定可信公网地址与强签名密钥。"""

import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import Settings


# 容器/本机可能注入 SMTP 与注册策略环境变量；配置单测必须与运行环境隔离。
CONTAMINATING_ENV_KEYS = (
    "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM",
    "SMTP_STARTTLS", "SMTP_SSL", "SMTP_TIMEOUT_SECONDS",
    "ALLOW_PUBLIC_REGISTRATION", "PUBLIC_REGISTRATION_SECRET",
    "BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_PASSWORD",
    "ALLOW_BOOTSTRAP_EMAIL_BYPASS", "INVITATION_EMAIL_ENABLED",
)


class ProductionSettingsTests(unittest.TestCase):
    def valid_production_settings(self, **overrides) -> Settings:
        values = {
            "app_env": "production",
            "database_url": "postgresql+psycopg://iam:password@postgres:5432/iam",
            "jwt_secret": "a" * 48,
            "oidc_issuer": "https://iam.example.test",
            "console_public_url": "https://iam.example.test",
            "bootstrap_admin_email": "admin@example.test",
        }
        values.update(overrides)
        # 配置单测必须与开发机 .env/容器环境隔离，避免隐式读取真实本地部署值。
        environment = {key: value for key, value in os.environ.items() if key not in CONTAMINATING_ENV_KEYS}
        with patch.dict(os.environ, environment, clear=True):
            return Settings(**values, _env_file=None)

    def test_accepts_valid_public_https_configuration(self) -> None:
        settings = self.valid_production_settings()
        self.assertEqual(settings.app_env, "production")

    def test_rejects_missing_database_or_short_jwt_secret(self) -> None:
        with self.assertRaises(ValidationError):
            self.valid_production_settings(database_url=None)
        with self.assertRaises(ValidationError):
            self.valid_production_settings(database_url="sqlite:///./iam.db")
        with self.assertRaises(ValidationError):
            self.valid_production_settings(jwt_secret="short")

    def test_rejects_http_or_missing_oidc_and_console_urls(self) -> None:
        for field, value in (
            ("oidc_issuer", "http://iam.example.test"),
            ("oidc_issuer", None),
            ("oidc_issuer", "https://@iam.example.test"),
            ("oidc_issuer", "https://iam.example.test?tenant=untrusted"),
            ("console_public_url", "http://iam.example.test"),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValidationError):
                    self.valid_production_settings(**{field: value})

    def test_development_retains_local_http_defaults(self) -> None:
        settings = Settings(app_env="development", console_public_url="http://localhost:5175",
                            _env_file=None)
        self.assertEqual(settings.console_public_url, "http://localhost:5175")

    def test_public_registration_is_development_only_until_signup_policy_is_complete(self) -> None:
        with self.assertRaises(ValidationError):
            self.valid_production_settings(allow_public_registration=True)
        local = Settings(
            app_env="development", allow_public_registration=True,
            public_registration_secret="r" * 32, _env_file=None,
        )
        self.assertTrue(local.allow_public_registration)

    def test_credential_cleanup_interval_and_batch_are_bounded(self) -> None:
        settings = self.valid_production_settings()
        self.assertEqual(settings.credential_cleanup_interval_seconds, 3600)
        self.assertEqual(settings.credential_cleanup_batch_size, 1000)
        with self.assertRaises(ValidationError):
            self.valid_production_settings(credential_cleanup_interval_seconds=59)
        with self.assertRaises(ValidationError):
            self.valid_production_settings(credential_cleanup_batch_size=10001)

    def test_smtp_password_recovery_requires_complete_credentials_and_transport_security(self) -> None:
        settings = self.valid_production_settings(smtp_host="smtp.example.test", smtp_from="iam@example.test")
        self.assertTrue(settings.smtp_starttls)
        with self.assertRaises(ValidationError):
            self.valid_production_settings(smtp_host="smtp.example.test")
        with self.assertRaises(ValidationError):
            self.valid_production_settings(smtp_host="smtp.example.test", smtp_from="iam@example.test",
                                           smtp_username="iam-sender")
        with self.assertRaises(ValidationError):
            self.valid_production_settings(smtp_host="smtp.example.test", smtp_from="iam@example.test",
                                           smtp_starttls=False, smtp_ssl=False)
        ssl_settings = self.valid_production_settings(smtp_host="smtp.example.test", smtp_from="iam@example.test",
                                                      smtp_starttls=False, smtp_ssl=True)
        self.assertTrue(ssl_settings.smtp_ssl)


if __name__ == "__main__":
    unittest.main()
