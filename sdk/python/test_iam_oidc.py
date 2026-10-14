"""IAM OIDC RP SDK 回归用例：使用临时 RSA 密钥签名，不依赖外网。"""

import base64
import hashlib
import json
import time
import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from iam_oidc import IamOIDCClient, OIDCProtocolError


class _JSONResponse:
    """提供与 urllib response 相同的只读接口，避免测试触发真实网络请求。"""

    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _limit: int = -1) -> bytes:
        return self._body


class _FakeJwks:
    """只向测试中的 ephemeral RSA 公钥验签，不发起 JWKS HTTP 请求。"""

    def __init__(self, public_key) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, _token: str):
        return SimpleNamespace(key=self.public_key)


class _FakeHTTP:
    """只模拟 token 和 UserInfo；检查 RP 发出的 PKCE 与客户端认证字段。"""

    def __init__(self, token_payload: dict, subject: str) -> None:
        self.token_payload = token_payload
        self.subject = subject
        self.requests = []

    def open(self, request, timeout: float):
        self.requests.append(request)
        self.assert_timeout = timeout
        if request.full_url.endswith("/token"):
            self.assert_form = request.data.decode("ascii")
            self.assert_auth = request.get_header("Authorization")
            return _JSONResponse(self.token_payload)
        if request.full_url.endswith("/revoke"):
            self.assert_form = request.data.decode("ascii")
            self.assert_auth = request.get_header("Authorization")
            return _JSONResponse({})
        if request.full_url.endswith("/introspect"):
            self.assert_form = request.data.decode("ascii")
            self.assert_auth = request.get_header("Authorization")
            return _JSONResponse(getattr(self, "introspection_payload", {"active": False}))
        if request.full_url.endswith("/userinfo"):
            if request.get_header("Authorization") != f"Bearer {self.token_payload['access_token']}":
                raise AssertionError("UserInfo must receive the access token")
            return _JSONResponse({"sub": self.subject, "name": "Test User", "email": "test@example.test"})
        raise AssertionError("The SDK requested an unexpected URL")


class IamOIDCClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.issuer = "https://iam.example.test"
        self.client_id = "client-123"
        self.client_secret = "a-secret-value"
        self.redirect_uri = "https://resume.example.test/auth/callback"
        self.tenant_id = str(uuid4())
        self.subject = str(uuid4())
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.client = IamOIDCClient(self.issuer, self.client_id, self.client_secret, self.redirect_uri)
        self.metadata = {
            "issuer": self.issuer,
            "authorization_endpoint": self.issuer + "/api/v1/oidc/authorize",
            "token_endpoint": self.issuer + "/api/v1/oidc/token",
            "userinfo_endpoint": self.issuer + "/api/v1/oidc/userinfo",
            "introspection_endpoint": self.issuer + "/api/v1/oidc/introspect",
            "jwks_uri": self.issuer + "/api/v1/oidc/jwks",
            "revocation_endpoint": self.issuer + "/api/v1/oidc/revoke",
            "end_session_endpoint": self.issuer + "/api/v1/oidc/logout",
            "authorization_response_iss_parameter_supported": True,
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
        }
        self.client._metadata_cache = self.metadata
        self.client._jwks_client = _FakeJwks(self.private_key.public_key())
        self.attempt = self.client.create_authorization_request()

    def _signed_tokens(self, nonce: str | None, *, id_tenant_id: str | None = None) -> dict:
        now = int(time.time())
        access_token = jwt.encode({
            "iss": self.issuer, "sub": self.subject, "aud": self.client_id,
            "client_id": self.client_id, "tenant_id": self.tenant_id,
            "token_use": "access_token", "iat": now, "exp": now + 600,
        }, self.private_key, algorithm="RS256", headers={"kid": "fixture-key"})
        at_hash = base64.urlsafe_b64encode(hashlib.sha256(access_token.encode("ascii")).digest()[:16]).rstrip(b"=").decode("ascii")
        id_claims = {
            "iss": self.issuer, "sub": self.subject, "aud": self.client_id,
            "iat": now, "exp": now + 600, "at_hash": at_hash,
        }
        if id_tenant_id is not None:
            id_claims["tenant_id"] = id_tenant_id
        if nonce is not None:
            id_claims["nonce"] = nonce
        id_token = jwt.encode(id_claims, self.private_key, algorithm="RS256", headers={"kid": "fixture-key"})
        return {"access_token": access_token, "id_token": id_token,
                "refresh_token": "refresh-fixture", "token_type": "Bearer",
                "expires_in": 600, "scope": "openid profile email"}

    def _callback(self, **overrides: str) -> str:
        values = {"code": "one-time-code", "state": self.attempt.state, "iss": self.issuer}
        values.update(overrides)
        return self.redirect_uri + "?" + urlencode(values)

    def test_authorization_request_uses_random_state_nonce_and_s256(self) -> None:
        second = self.client.create_authorization_request()
        params = parse_qs(urlsplit(self.attempt.authorization_url).query)
        self.assertNotEqual(self.attempt.state, second.state)
        self.assertNotEqual(self.attempt.nonce, second.nonce)
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertEqual(params["response_type"], ["code"])
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self.attempt.code_verifier.encode("ascii")).digest(),
        ).rstrip(b"=").decode("ascii")
        self.assertEqual(params["code_challenge"], [expected_challenge])
        self.assertNotIn(self.attempt.code_verifier, self.attempt.authorization_url)

    def test_login_validates_callback_token_binding_and_userinfo(self) -> None:
        payload = self._signed_tokens(self.attempt.nonce, id_tenant_id=self.tenant_id)
        fake_http = _FakeHTTP(payload, self.subject)
        self.client._opener = fake_http
        identity = self.client.complete_login(self._callback(), self.attempt)
        self.assertEqual(identity.subject, self.subject)
        self.assertEqual(identity.tenant_id, self.tenant_id)
        self.assertEqual(identity.profile["email"], "test@example.test")
        self.assertEqual(identity.tokens.scope, ("openid", "profile", "email"))
        self.assertEqual(len(fake_http.requests), 2)
        submitted = parse_qs(fake_http.assert_form)
        self.assertEqual(submitted["code_verifier"], [self.attempt.code_verifier])
        decoded = base64.b64decode(fake_http.assert_auth.split(" ", 1)[1]).decode("ascii")
        self.assertEqual(decoded, "client-123:a-secret-value")
        self.assertNotIn("a-secret-value", repr(identity))

    def test_login_rejects_id_token_tenant_mismatch(self) -> None:
        payload = self._signed_tokens(self.attempt.nonce, id_tenant_id=str(uuid4()))
        self.client._opener = _FakeHTTP(payload, self.subject)

        with self.assertRaises(OIDCProtocolError):
            self.client.complete_login(self._callback(), self.attempt)

    def test_refresh_rejects_id_token_tenant_mismatch(self) -> None:
        first_payload = self._signed_tokens(self.attempt.nonce, id_tenant_id=self.tenant_id)
        self.client._opener = _FakeHTTP(first_payload, self.subject)
        identity = self.client.complete_login(self._callback(), self.attempt)

        refreshed_payload = self._signed_tokens(None, id_tenant_id=str(uuid4()))
        refreshed_payload["refresh_token"] = "refresh-rotated"
        self.client._opener = _FakeHTTP(refreshed_payload, self.subject)

        with self.assertRaises(OIDCProtocolError):
            self.client.refresh(identity)

    def test_callback_state_or_issuer_mismatch_fails_before_token_exchange(self) -> None:
        fake_http = _FakeHTTP({}, self.subject)
        self.client._opener = fake_http
        with self.assertRaises(OIDCProtocolError):
            self.client.complete_login(self._callback(state="attacker-state"), self.attempt)
        self.assertEqual(fake_http.requests, [])
        with self.assertRaises(OIDCProtocolError):
            self.client.complete_login(self._callback(iss="https://evil.example.test"), self.attempt)
        self.assertEqual(fake_http.requests, [])

    def test_nonce_and_access_token_at_hash_are_checked(self) -> None:
        payload = self._signed_tokens(self.attempt.nonce)
        id_claims = jwt.decode(payload["id_token"], options={"verify_signature": False})
        id_claims["at_hash"] = "not-the-access-token-hash"
        payload["id_token"] = jwt.encode(
            id_claims, self.private_key, algorithm="RS256", headers={"kid": "fixture-key"},
        )
        self.client._opener = _FakeHTTP(payload, self.subject)
        with self.assertRaises(OIDCProtocolError):
            self.client.complete_login(self._callback(), self.attempt)

    def test_nonce_mismatch_is_rejected(self) -> None:
        payload = self._signed_tokens("wrong-nonce")
        self.client._opener = _FakeHTTP(payload, self.subject)
        with self.assertRaises(OIDCProtocolError):
            self.client.complete_login(self._callback(), self.attempt)

    def test_wrong_userinfo_subject_is_rejected(self) -> None:
        payload = self._signed_tokens(self.attempt.nonce)
        self.client._opener = _FakeHTTP(payload, "another-subject")
        with self.assertRaises(OIDCProtocolError):
            self.client.complete_login(self._callback(), self.attempt)

    def test_refresh_rotates_server_session_tokens_and_logout_revokes_new_token(self) -> None:
        first_payload = self._signed_tokens(self.attempt.nonce)
        first_http = _FakeHTTP(first_payload, self.subject)
        self.client._opener = first_http
        identity = self.client.complete_login(self._callback(), self.attempt)

        refreshed_payload = self._signed_tokens(None)
        refreshed_payload["refresh_token"] = "refresh-rotated"
        refresh_http = _FakeHTTP(refreshed_payload, self.subject)
        self.client._opener = refresh_http
        refreshed = self.client.refresh(identity)
        self.assertEqual(parse_qs(refresh_http.assert_form)["grant_type"], ["refresh_token"])
        self.assertEqual(refreshed.subject, identity.subject)
        self.assertEqual(refreshed.tenant_id, identity.tenant_id)
        self.assertEqual(refreshed.tokens.refresh_token, "refresh-rotated")

        logout = self.client.create_end_session_request(
            refreshed, "https://resume.example.test/signed-out",
        )
        logout_query = parse_qs(urlsplit(logout.url).query)
        self.assertEqual(urlsplit(logout.url).path, "/api/v1/oidc/logout")
        self.assertEqual(logout.method, "GET")
        self.assertEqual(logout_query["id_token_hint"], [refreshed.tokens.id_token])
        self.assertEqual(logout_query["state"], [logout.state])
        self.assertNotIn(refreshed.tokens.id_token, repr(logout))

        revoke_http = _FakeHTTP({}, self.subject)
        self.client._opener = revoke_http
        self.client.revoke_refresh_token(refreshed.tokens.refresh_token)
        revoke_form = parse_qs(revoke_http.assert_form)
        self.assertEqual(revoke_form["token"], ["refresh-rotated"])
        self.assertEqual(revoke_form["token_type_hint"], ["refresh_token"])

        access_revoke_http = _FakeHTTP({}, self.subject)
        self.client._opener = access_revoke_http
        self.client.revoke_access_token(refreshed.tokens.access_token)
        access_revoke_form = parse_qs(access_revoke_http.assert_form)
        self.assertEqual(access_revoke_form["token"], [refreshed.tokens.access_token])
        self.assertEqual(access_revoke_form["token_type_hint"], ["access_token"])

    def test_non_https_remote_issuer_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            IamOIDCClient("http://iam.example.test", self.client_id, self.client_secret, self.redirect_uri)

    def test_introspection_checks_client_binding_and_returns_inactive_shape(self) -> None:
        active_payload = {
            "active": True, "client_id": self.client_id, "iss": self.issuer,
            "sub": self.subject, "scope": "openid profile", "tenant_id": self.tenant_id,
            "exp": int(time.time()) + 300, "iat": int(time.time()),
        }
        fake_http = _FakeHTTP({}, self.subject)
        fake_http.introspection_payload = active_payload
        self.client._opener = fake_http

        result = self.client.introspect_token("access-token-value", "access_token")

        self.assertTrue(result["active"])
        form = parse_qs(fake_http.assert_form)
        self.assertEqual(form["token"], ["access-token-value"])
        self.assertEqual(form["token_type_hint"], ["access_token"])
        self.assertTrue(fake_http.assert_auth.startswith("Basic "))

        fake_http.introspection_payload = {"active": False}
        self.assertEqual(self.client.introspect_token("unknown-token"), {"active": False})

        fake_http.introspection_payload = {**active_payload, "client_id": "another-client"}
        with self.assertRaises(OIDCProtocolError):
            self.client.introspect_token("access-token-value")

        with self.assertRaises(ValueError):
            self.client.introspect_token("access-token-value", "id_token")


if __name__ == "__main__":
    unittest.main()
