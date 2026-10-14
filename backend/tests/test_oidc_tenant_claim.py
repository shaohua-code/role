"""OIDC tenant claims that do not need a database integration fixture."""

import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from app.api.v1.oidc_provider.metadata import discovery_document
from app.api.v1.oidc_provider.tokens import _id_token, _token_payload
from app.models.application import Application
from app.models.identity import TenantMembership, User


class OIDCTenantClaimTests(unittest.TestCase):
    def test_offline_access_token_carries_its_refresh_family_session_id(self) -> None:
        user = User(id=uuid4(), email="user@example.test", password_hash="test-only",
                    display_name="Test User", status="active", auth_version=3)
        application = Application(id=uuid4(), tenant_id=uuid4(), client_id="test-client", name="Test App")
        membership = TenantMembership(id=uuid4(), user_id=user.id, tenant_id=application.tenant_id,
                                      status="active", auth_version=7)
        database = Mock()

        with patch("app.api.v1.oidc_provider.tokens._issuer", return_value="https://iam.example.test"), \
                patch("app.api.v1.oidc_provider.tokens.sign_jwt", return_value="signed-token") as signer:
            payload, refresh_row = _token_payload(
                database, user, application, {"openid", "offline_access"}, None, membership,
            )

        self.assertIsNotNone(refresh_row)
        self.assertIn("refresh_token", payload)
        access_claims = signer.call_args_list[0].args[0]
        self.assertEqual(access_claims["sid"], str(refresh_row.family_id))

    def test_short_oidc_access_token_without_offline_access_has_no_session_id(self) -> None:
        user = User(id=uuid4(), email="user@example.test", password_hash="test-only",
                    display_name="Test User", status="active", auth_version=3)
        application = Application(id=uuid4(), tenant_id=uuid4(), client_id="test-client", name="Test App")
        membership = TenantMembership(id=uuid4(), user_id=user.id, tenant_id=application.tenant_id,
                                      status="active", auth_version=7)
        database = Mock()

        with patch("app.api.v1.oidc_provider.tokens._issuer", return_value="https://iam.example.test"), \
                patch("app.api.v1.oidc_provider.tokens.sign_jwt", return_value="signed-token") as signer:
            payload, refresh_row = _token_payload(
                database, user, application, {"openid"}, None, membership,
            )

        self.assertIsNone(refresh_row)
        self.assertNotIn("refresh_token", payload)
        access_claims = signer.call_args_list[0].args[0]
        self.assertNotIn("sid", access_claims)
        database.add.assert_not_called()

    def test_signed_id_token_payload_includes_application_tenant(self) -> None:
        tenant_id = uuid4()
        user = User(id=uuid4(), email="user@example.test", password_hash="test-only",
                    display_name="Test User", status="active")
        application = Application(tenant_id=tenant_id, client_id="test-client")

        with patch("app.api.v1.oidc_provider.tokens._issuer", return_value="https://iam.example.test"), \
                patch("app.api.v1.oidc_provider.tokens.sign_jwt", return_value="signed-id-token") as signer:
            token = _id_token(user, application, {"openid"}, None, "access-token")

        self.assertEqual(token, "signed-id-token")
        claims = signer.call_args.args[0]
        self.assertEqual(claims["tenant_id"], str(tenant_id))
        self.assertEqual(claims["sub"], str(user.id))

    def test_discovery_advertises_signed_tenant_claim(self) -> None:
        with patch("app.api.v1.oidc_provider.metadata._issuer", return_value="https://iam.example.test"), \
                patch("app.api.v1.oidc_provider.metadata._endpoint",
                      side_effect=lambda name: f"https://iam.example.test/oidc/{name}"):
            metadata = discovery_document()

        self.assertIn("tenant_id", metadata["claims_supported"])


if __name__ == "__main__":
    unittest.main()
