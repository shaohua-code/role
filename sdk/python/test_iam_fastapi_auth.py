"""FastAPI OIDC route plugin contract tests; the OIDC client is mocked, no network is used."""
import unittest
from dataclasses import dataclass, field
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from iam_fastapi_auth import InMemorySessionStore, OidcRouteOptions, mount_oidc_auth
from iam_oidc import AuthorizationAttempt, OIDCProtocolError, TokenSet

ATTEMPT = AuthorizationAttempt(
    authorization_url="https://iam.example/authorize?state=state-1",
    state="state-1",
    nonce="nonce-1",
    code_verifier="verifier-1",
    scopes=("openid", "profile", "email"),
)


@dataclass
class FakeIdentity:
    subject: str = "user-1"
    tenant_id: str = "tenant-uuid"
    profile: dict = field(default_factory=lambda: {"email": "user-1@example.com"})
    tokens: TokenSet = field(default_factory=lambda: TokenSet(access_token="at-1", refresh_token="rt-1", id_token="id-1"))


class OidcAuthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.oidc = Mock()
        self.oidc.create_authorization_request.return_value = ATTEMPT
        self.oidc.complete_login.return_value = FakeIdentity()
        self.store = InMemorySessionStore()
        self.app = FastAPI()
        mount_oidc_auth(
            self.app,
            oidc_client=self.oidc,
            session_store=self.store,
            options=OidcRouteOptions(post_logout_redirect="/goodbye"),
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _login(self) -> str:
        response = self.client.get("/auth/login", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        return response.cookies.get("iam_attempt")

    def test_login_redirects_to_idp_with_httponly_attempt_cookie(self) -> None:
        response = self.client.get("/auth/login", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], ATTEMPT.authorization_url)
        self.assertEqual(response.cookies.get("iam_attempt"), response.cookies.get("iam_attempt"))
        set_cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=lax", set_cookie)
        # attempt 必须落在服务端存储，而不是只放在浏览器里。
        attempt_id = response.cookies.get("iam_attempt")
        self.assertIsNotNone(self.store.load(f"attempt:{attempt_id}"))

    def test_callback_exchanges_code_for_session_and_clears_attempt(self) -> None:
        attempt_id = self._login()
        response = self.client.get(
            "/auth/callback?code=abc&state=state-1",
            cookies={"iam_attempt": attempt_id},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/")
        self.oidc.complete_login.assert_called_once()
        session_id = response.cookies.get("iam_session")
        self.assertTrue(session_id)
        self.assertIsNotNone(self.store.load(f"session:{session_id}"))
        # attempt 是一次性的：消费后必须从服务端存储删除。
        self.assertIsNone(self.store.load(f"attempt:{attempt_id}"))

    def test_callback_attempt_is_single_use(self) -> None:
        attempt_id = self._login()
        first = self.client.get(
            "/auth/callback?code=abc&state=state-1", cookies={"iam_attempt": attempt_id}, follow_redirects=False,
        )
        self.assertEqual(first.status_code, 302)
        replay = self.client.get(
            "/auth/callback?code=abc&state=state-1", cookies={"iam_attempt": attempt_id}, follow_redirects=False,
        )
        self.assertEqual(replay.status_code, 403)

    def test_callback_without_attempt_cookie_fails_closed(self) -> None:
        response = self.client.get("/auth/callback?code=abc&state=state-1", follow_redirects=False)
        self.assertEqual(response.status_code, 403)
        self.oidc.complete_login.assert_not_called()

    def test_callback_protocol_failure_maps_to_403_without_provider_details(self) -> None:
        self.oidc.complete_login.side_effect = OIDCProtocolError("issuer mismatch with secret detail")
        attempt_id = self._login()
        response = self.client.get(
            "/auth/callback?code=abc&state=state-1", cookies={"iam_attempt": attempt_id}, follow_redirects=False,
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("secret detail", response.text)

    def test_me_returns_identity_summary_without_tokens(self) -> None:
        attempt_id = self._login()
        callback = self.client.get(
            "/auth/callback?code=abc&state=state-1", cookies={"iam_attempt": attempt_id}, follow_redirects=False,
        )
        me = self.client.get("/auth/me", cookies={"iam_session": callback.cookies.get("iam_session")})
        self.assertEqual(me.status_code, 200)
        body = me.json()
        self.assertEqual(body["subject"], "user-1")
        self.assertEqual(body["tenant_id"], "tenant-uuid")
        self.assertEqual(body["profile"]["email"], "user-1@example.com")
        self.assertNotIn("tokens", body)

    def test_me_without_session_is_unauthorized(self) -> None:
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_tokens_and_clears_session(self) -> None:
        attempt_id = self._login()
        callback = self.client.get(
            "/auth/callback?code=abc&state=state-1", cookies={"iam_attempt": attempt_id}, follow_redirects=False,
        )
        session_id = callback.cookies.get("iam_session")
        response = self.client.get("/auth/logout", cookies={"iam_session": session_id}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/goodbye")
        self.oidc.revoke_refresh_token.assert_called_once_with("rt-1")
        self.oidc.revoke_access_token.assert_called_once_with("at-1")
        self.assertIsNone(self.store.load(f"session:{session_id}"))
        # 会话已删除：同一 Cookie 再访问 me 必须 401。
        me = self.client.get("/auth/me", cookies={"iam_session": session_id})
        self.assertEqual(me.status_code, 401)

    def test_logout_without_session_is_idempotent(self) -> None:
        response = self.client.get("/auth/logout", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.oidc.revoke_refresh_token.assert_not_called()
        self.oidc.revoke_access_token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
