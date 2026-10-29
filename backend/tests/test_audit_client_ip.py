"""认证与管理审计必须记录可信入口解析后的客户端地址。"""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException, Request

from app.api.v1.admin.common import audit as record_admin_audit
from app.api.v1.auth import record_event
from app.api.v1.oidc_provider.common import _oauth_audit
from app.api.v1.oidc_provider.logout import end_session
from app.core.config import Settings
from app.models.identity import AuditEvent
from app.services.login_throttle import client_ip_for_request


class AuditClientIPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client_ip = "198.51.100.23"
        self.settings = Settings(trust_proxy_client_ip=True, _env_file=None)
        self.request = Request({
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"x-iam-client-ip", self.client_ip.encode("ascii"))],
            "client": ("172.20.0.4", 45123),
            "scheme": "https",
        })
        self.db = Mock()
        self.actor = SimpleNamespace(id=uuid4())

    def _event(self) -> AuditEvent:
        return self.db.add.call_args.args[0]

    def test_management_audit_uses_trusted_proxy_address(self) -> None:
        with patch("app.api.v1.admin.common.get_settings", return_value=self.settings):
            record_admin_audit(self.db, self.actor, self.request, "role.update", "user", "u-1")

        self.assertEqual(self._event().source_ip, self.client_ip)

    def test_authentication_audit_uses_trusted_proxy_address(self) -> None:
        with patch("app.api.v1.auth.get_settings", return_value=self.settings):
            record_event(self.db, "auth.login", "user", "u-1", self.actor, self.request)

        self.assertEqual(self._event().source_ip, self.client_ip)

    def test_oidc_audit_uses_trusted_proxy_address(self) -> None:
        application = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), client_id="client-a")
        with patch("app.api.v1.oidc_provider.common.get_settings", return_value=self.settings):
            _oauth_audit(self.db, self.actor, application, "oidc.authorize", "openid", self.request)

        self.assertEqual(self._event().source_ip, self.client_ip)

    def test_oidc_logout_audit_uses_trusted_proxy_address(self) -> None:
        application = SimpleNamespace(
            id=uuid4(), tenant_id=uuid4(), client_id="client-a", post_logout_redirect_uris=[]
        )
        user = SimpleNamespace(id=uuid4())
        self.request = Request({
            "type": "http",
            "method": "GET",
            "path": "/oidc/logout",
            "query_string": b"id_token_hint=signed-token",
            "headers": [(b"x-iam-client-ip", self.client_ip.encode("ascii"))],
            "client": ("172.20.0.4", 45123),
            "scheme": "https",
        })
        self.db.scalar.return_value = application
        self.db.get.return_value = user

        with (
            patch("app.api.v1.oidc_provider.logout.decode_oidc_jwt", return_value={
                "aud": "client-a", "sub": str(user.id),
            }),
            patch("app.api.v1.oidc_provider.logout.get_settings", return_value=self.settings),
        ):
            asyncio.run(end_session(self.request, None, self.db))

        self.assertEqual(self._event().source_ip, self.client_ip)

    def test_generic_forwarding_header_is_not_a_trusted_source(self) -> None:
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [(b"x-forwarded-for", b"203.0.113.99")],
            "client": ("172.20.0.4", 45123),
            "scheme": "https",
        })

        with self.assertRaises(HTTPException) as error:
            client_ip_for_request(request, self.settings)

        self.assertEqual(error.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
