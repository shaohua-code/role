"""PostgreSQL integration coverage for interactive OIDC consent and trusted clients."""

import hashlib
import asyncio
import base64
import json
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.oidc_provider import (_access_token, authorize, consent_context, consent_decision, discovery_document,
                                      end_session, introspect as oidc_introspect, revoke as oidc_revoke, token, userinfo)
from app.api.v1.admin.organizations import set_user_membership_status
from app.core.config import get_settings
from app.core.oidc_keys import decode_oidc_jwt
from app.core.security import current_user, hash_password
from app.db.session import get_engine
from app.models.application import Application
from app.models.authorization import Role, RoleBinding
from app.models.identity import AuditEvent, RefreshSession, Tenant, TenantMembership, User
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.schemas.auth import OIDCConsentDecision, OIDCConsentTicket
from app.schemas.organizations import MembershipStatusUpdate


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL integration tests")
class OIDCConsentIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        now = datetime.now(timezone.utc)
        self.tenant_id, self.user_id = uuid4(), uuid4()
        self.membership_id, self.role_id, self.application_id = uuid4(), uuid4(), uuid4()
        self.client_id = f"consent-{uuid4().hex[:20]}"
        self.raw_cookie = f"refresh-{uuid4().hex}"
        self.client_secret = f"client-secret-{uuid4().hex}"
        self.verifier = f"verifier-{uuid4().hex}-{uuid4().hex}"[:64]
        self.callback = "https://client.example.test/callback"
        self.logout_callback = "https://client.example.test/signed-out"
        self.tenant = Tenant(id=self.tenant_id, name="Consent Tenant", slug=f"consent-{uuid4().hex[:20]}",
                             status="active")
        self.user = User(id=self.user_id, email=f"consent-{uuid4().hex}@example.test",
                         password_hash="test-only", display_name="Consent User", status="active")
        self.db.add_all([self.tenant, self.user])
        self.db.flush()
        self.app = Application(id=self.application_id, tenant_id=self.tenant_id, name="Consent Client",
                               client_id=self.client_id, redirect_uris=[self.callback],
                               post_logout_redirect_uris=[self.logout_callback], trusted=False, status="active",
                               client_secret_hash=hash_password(self.client_secret))
        self.membership = TenantMembership(id=self.membership_id, tenant_id=self.tenant_id,
                                           user_id=self.user_id, status="active")
        self.role = Role(id=self.role_id, tenant_id=self.tenant_id, key=f"consent-{uuid4().hex[:12]}",
                         name="Consent Access", status="active")
        self.db.add_all([self.app, self.membership, self.role])
        self.db.flush()
        self.db.add_all([
            RoleBinding(membership_id=self.membership_id, role_id=self.role_id),
            RefreshSession(user_id=self.user_id,
                           token_hash=hashlib.sha256(self.raw_cookie.encode()).hexdigest(),
                           expires_at=now + timedelta(minutes=30)),
        ])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def make_request(self, prompt: str | None = None, challenge: str = "A" * 43) -> Request:
        params = {
            "client_id": self.client_id, "redirect_uri": self.callback,
            "response_type": "code", "scope": "openid profile email",
            "state": f"state-{uuid4().hex}", "nonce": f"nonce-{uuid4().hex}",
            "code_challenge": challenge, "code_challenge_method": "S256",
        }
        if prompt:
            params["prompt"] = prompt
        path = "/api/v1/oidc/authorize"
        return Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path, "raw_path": path.encode(), "root_path": "",
            "query_string": urlencode(params).encode(), "headers": [],
            "client": ("127.0.0.1", 51234), "server": ("localhost", 8000),
        })

    def test_untrusted_client_requires_approval_before_code_is_issued(self) -> None:
        request = self.make_request()
        response = authorize(request, self.raw_cookie, self.db)
        self.assertEqual(response.status_code, 302)
        parsed = urlsplit(response.headers["location"])
        self.assertEqual(parsed.fragment.split("=", 1)[0], "consent")
        ticket = parse_qs(parsed.fragment)["consent"][0]
        self.assertEqual(self.db.scalar(select(OAuthAuthorizationCode.id)), None)

        preview = consent_context(Response(), OIDCConsentTicket(ticket=ticket), self.raw_cookie, self.db)
        self.assertEqual(preview["application_name"], self.app.name)
        self.assertEqual(preview["tenant_name"], self.tenant.name)
        self.assertEqual(set(preview["scope"]), {"openid", "profile", "email"})

        result = consent_decision(Response(), OIDCConsentDecision(ticket=ticket, approved=True),
                                  request, self.raw_cookie, self.db)
        callback = parse_qs(urlsplit(result["redirect_to"]).query)
        self.assertEqual(callback["state"][0], request.query_params["state"])
        self.assertIn("code", callback)
        self.assertEqual(self.db.scalar(select(OAuthConsentRequest).where(
            OAuthConsentRequest.ticket_hash == hashlib.sha256(ticket.encode()).hexdigest(),
        )).consumed_at is not None, True)

    def test_denial_returns_access_denied_without_issuing_code(self) -> None:
        request = self.make_request()
        response = authorize(request, self.raw_cookie, self.db)
        ticket = parse_qs(urlsplit(response.headers["location"]).fragment)["consent"][0]
        result = consent_decision(Response(), OIDCConsentDecision(ticket=ticket, approved=False),
                                  request, self.raw_cookie, self.db)
        callback = parse_qs(urlsplit(result["redirect_to"]).query)
        self.assertEqual(callback["error"][0], "access_denied")
        self.assertEqual(callback["state"][0], request.query_params["state"])
        self.assertEqual(self.db.scalar(select(OAuthAuthorizationCode.id)), None)

    def test_none_prompt_requires_consent_for_untrusted_client(self) -> None:
        response = authorize(self.make_request("none"), self.raw_cookie, self.db)
        callback = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(callback["error"][0], "consent_required")
        self.assertEqual(self.db.scalar(select(OAuthConsentRequest.id)), None)
        self.assertEqual(self.db.scalar(select(OAuthAuthorizationCode.id)), None)

    def test_trusted_client_can_skip_consent_but_explicit_consent_prompt_wins(self) -> None:
        self.app.trusted = True
        self.db.flush()
        silent = authorize(self.make_request("none"), self.raw_cookie, self.db)
        self.assertIn("code=", silent.headers["location"])
        self.assertEqual(self.db.scalar(select(OAuthConsentRequest.id)), None)

        explicit = authorize(self.make_request("consent"), self.raw_cookie, self.db)
        self.assertIn("#consent=", explicit.headers["location"])

    def test_code_to_token_exchange_succeeds_once_after_consent(self) -> None:
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()
        request = self.make_request(challenge=challenge)
        response = authorize(request, self.raw_cookie, self.db)
        ticket = parse_qs(urlsplit(response.headers["location"]).fragment)["consent"][0]
        decision = consent_decision(Response(), OIDCConsentDecision(ticket=ticket, approved=True), request, self.raw_cookie, self.db)
        code = parse_qs(urlsplit(decision["redirect_to"]).query)["code"][0]
        form = urlencode({"grant_type": "authorization_code", "code": code,
                          "redirect_uri": self.callback, "code_verifier": self.verifier}).encode()
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = asyncio.run(token(self.token_request(form), f"Basic {basic}", self.db))
        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["scope"], "email openid profile")
        self.assertIn("access_token", payload)
        self.assertIn("id_token", payload)

        replay = asyncio.run(token(self.token_request(form), f"Basic {basic}", self.db))
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(json.loads(replay.body)["error"], "invalid_grant")

    def test_confidential_client_can_revoke_access_token_immediately(self) -> None:
        access_token, _ = _access_token(self.user, self.app, "openid profile")
        bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token)
        self.assertEqual(current_user(bearer, self.db).id, self.user.id)
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        introspection_form = urlencode({"token": access_token, "token_type_hint": "access_token"}).encode()
        active = asyncio.run(oidc_introspect(self.form_request("/api/v1/oidc/introspect", introspection_form),
                                             f"Basic {basic}", self.db))
        active_claims = json.loads(active.body)
        self.assertTrue(active_claims["active"])
        self.assertEqual(active_claims["client_id"], self.client_id)
        self.assertEqual(active_claims["sub"], str(self.user.id))
        self.assertEqual(active.headers["Cache-Control"], "no-store")
        wrong_hint_form = urlencode({"token": access_token, "token_type_hint": "refresh_token"}).encode()
        hinted_as_refresh = asyncio.run(oidc_introspect(
            self.form_request("/api/v1/oidc/introspect", wrong_hint_form), f"Basic {basic}", self.db,
        ))
        self.assertTrue(json.loads(hinted_as_refresh.body)["active"])
        # An unknown hint cannot stop the provider from finding the actual token type.
        form = urlencode({"token": access_token, "token_type_hint": "future_token_type"}).encode()

        response = asyncio.run(oidc_revoke(self.form_request("/api/v1/oidc/revoke", form),
                                           f"Basic {basic}", self.db))

        self.assertEqual(response.status_code, 200)
        with self.assertRaises(HTTPException) as denied:
            current_user(bearer, self.db)
        self.assertEqual(denied.exception.status_code, 401)
        self.assertEqual(userinfo(f"Bearer {access_token}", self.db).status_code, 401)
        inactive = asyncio.run(oidc_introspect(self.form_request("/api/v1/oidc/introspect", introspection_form),
                                               f"Basic {basic}", self.db))
        self.assertEqual(json.loads(inactive.body), {"active": False})

    def test_membership_pause_and_reactivation_do_not_revive_old_oauth_credentials(self) -> None:
        raw_access, _ = _access_token(self.user, self.app, "openid offline_access")
        raw_refresh = f"membership-refresh-{uuid4().hex}"
        self.db.add(OAuthRefreshToken(
            family_id=uuid4(), application_id=self.app.id, user_id=self.user.id,
            token_hash=hashlib.sha256(raw_refresh.encode()).hexdigest(), scope="openid offline_access",
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        ))
        actor = User(email=f"lifecycle-admin-{uuid4().hex}@example.test", password_hash="test-only",
                     display_name="Lifecycle Admin", status="active")
        self.db.add(actor)
        self.db.flush()
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        access_bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw_access)
        self.assertEqual(current_user(access_bearer, self.db).id, self.user.id)
        self.assertEqual(decode_oidc_jwt(raw_access)["membership_version"], 1)

        with patch("app.api.v1.admin.organizations.require_organization_admin_access"):
            set_user_membership_status(
                self.user.id, self.tenant.id,
                MembershipStatusUpdate(expected_status="active", status="disabled"),
                self.form_request("/api/v1/admin/users/status", b""), actor, self.db,
            )
            self.db.refresh(self.membership)
            self.assertEqual(self.membership.auth_version, 2)
            set_user_membership_status(
                self.user.id, self.tenant.id,
                MembershipStatusUpdate(expected_status="disabled", status="active"),
                self.form_request("/api/v1/admin/users/status", b""), actor, self.db,
            )

        self.db.refresh(self.membership)
        self.assertEqual(self.membership.auth_version, 3)
        self.assertEqual(self.membership.status, "active")
        with self.assertRaises(HTTPException) as stale_access:
            current_user(access_bearer, self.db)
        self.assertEqual(stale_access.exception.status_code, 401)
        self.assertEqual(userinfo(f"Bearer {raw_access}", self.db).status_code, 401)
        stale_result = asyncio.run(oidc_introspect(
            self.form_request("/api/v1/oidc/introspect", urlencode({"token": raw_access}).encode()),
            f"Basic {basic}", self.db,
        ))
        self.assertEqual(json.loads(stale_result.body), {"active": False})
        revoked_refresh = self.db.scalar(select(OAuthRefreshToken).where(
            OAuthRefreshToken.token_hash == hashlib.sha256(raw_refresh.encode()).hexdigest(),
        ))
        self.assertIsNotNone(revoked_refresh.revoked_at)
        refresh_result = asyncio.run(oidc_introspect(
            self.form_request("/api/v1/oidc/introspect", urlencode({"token": raw_refresh}).encode()),
            f"Basic {basic}", self.db,
        ))
        self.assertEqual(json.loads(refresh_result.body), {"active": False})

    def test_introspection_supports_live_refresh_tokens_and_hides_cross_client_tokens(self) -> None:
        raw_refresh = f"opaque-refresh-{uuid4().hex}"
        self.db.add(OAuthRefreshToken(
            family_id=uuid4(), application_id=self.app.id, user_id=self.user.id,
            token_hash=hashlib.sha256(raw_refresh.encode()).hexdigest(), scope="openid offline_access",
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        ))
        self.db.flush()
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        # RFC 7662 calls this a hint: the server still searches the other token type.
        form = urlencode({"token": raw_refresh, "token_type_hint": "access_token"}).encode()

        response = asyncio.run(oidc_introspect(self.form_request("/api/v1/oidc/introspect", form),
                                               f"Basic {basic}", self.db))
        self.assertTrue(json.loads(response.body)["active"])
        self.assertEqual(json.loads(response.body)["scope"], "openid offline_access")

        other_secret = f"other-secret-{uuid4().hex}"
        other_app = Application(
            tenant_id=self.tenant_id, name="Other Introspection Client",
            client_id=f"other-{uuid4().hex[:20]}", client_secret_hash=hash_password(other_secret),
            redirect_uris=[self.callback], trusted=True, status="active",
        )
        self.db.add(other_app)
        self.db.flush()
        other_basic = base64.b64encode(f"{other_app.client_id}:{other_secret}".encode()).decode()
        other_response = asyncio.run(oidc_introspect(
            self.form_request("/api/v1/oidc/introspect", form), f"Basic {other_basic}", self.db,
        ))
        self.assertEqual(json.loads(other_response.body), {"active": False})

        revoked = asyncio.run(oidc_revoke(
            self.form_request("/api/v1/oidc/revoke", form), f"Basic {basic}", self.db,
        ))
        self.assertEqual(revoked.status_code, 200)
        inactive = asyncio.run(oidc_introspect(
            self.form_request("/api/v1/oidc/introspect", form), f"Basic {basic}", self.db,
        ))
        self.assertEqual(json.loads(inactive.body), {"active": False})

    def form_request(self, path: str, body: bytes) -> Request:
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
            "client": ("127.0.0.1", 51236), "server": ("localhost", 8000),
        }, receive=receive)

    def test_rp_initiated_logout_revokes_client_and_matching_browser_sessions(self) -> None:
        raw_oauth_refresh = f"oauth-refresh-{uuid4().hex}"
        self.db.add(OAuthRefreshToken(
            family_id=uuid4(), application_id=self.app.id, user_id=self.user.id,
            token_hash=hashlib.sha256(raw_oauth_refresh.encode()).hexdigest(), scope="openid offline_access",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        ))
        self.db.flush()
        self.app.post_logout_redirect_uris = [self.logout_callback]
        self.db.flush()
        from app.api.v1.oidc_provider import _id_token
        hint = _id_token(self.user, self.app, {"openid"}, None, "test-access-token")
        request = self.logout_request(hint, self.logout_callback, "logout-state-123")

        response = asyncio.run(end_session(request, self.raw_cookie, self.db))

        self.assertEqual(response.status_code, 302)
        redirected = urlsplit(response.headers["location"])
        self.assertEqual(redirected.scheme + "://" + redirected.netloc + redirected.path, self.logout_callback)
        self.assertEqual(parse_qs(redirected.query)["state"], ["logout-state-123"])
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertIn("iam_refresh_token=", response.headers["set-cookie"])
        self.assertIsNotNone(self.db.scalar(select(RefreshSession).where(
            RefreshSession.user_id == self.user.id,
        )).revoked_at)
        stored = self.db.scalar(select(OAuthRefreshToken).where(
            OAuthRefreshToken.token_hash == hashlib.sha256(raw_oauth_refresh.encode()).hexdigest(),
        ))
        self.assertIsNotNone(stored.revoked_at)
        self.assertEqual(self.db.scalar(select(AuditEvent.action).where(AuditEvent.action == "oidc.logout")), "oidc.logout")

    def test_rp_logout_rejects_unregistered_redirect_and_access_token_hint(self) -> None:
        from app.api.v1.oidc_provider import _access_token, _id_token
        id_hint = _id_token(self.user, self.app, {"openid"}, None, "test-access-token")
        bad_redirect = asyncio.run(end_session(
            self.logout_request(id_hint, "https://attacker.example.test/steal", "logout-state-123"),
            self.raw_cookie, self.db,
        ))
        self.assertEqual(bad_redirect.status_code, 400)
        self.assertIsNone(self.db.scalar(select(RefreshSession).where(
            RefreshSession.user_id == self.user.id,
        )).revoked_at)

        self.app.post_logout_redirect_uris = [self.logout_callback + "?state=fixed"]
        self.db.flush()
        duplicate_state = asyncio.run(end_session(
            self.logout_request(id_hint, self.app.post_logout_redirect_uris[0], "logout-state-123"),
            self.raw_cookie, self.db,
        ))
        self.assertEqual(duplicate_state.status_code, 400)

        self.app.post_logout_redirect_uris = [self.logout_callback]
        self.db.flush()
        access_hint, _ = _access_token(self.user, self.app, "openid")
        wrong_token_type = asyncio.run(end_session(
            self.logout_request(access_hint, self.logout_callback, "logout-state-123"),
            self.raw_cookie, self.db,
        ))
        self.assertEqual(wrong_token_type.status_code, 400)

    def test_logout_hint_cannot_clear_another_browser_account_cookie(self) -> None:
        from app.api.v1.oidc_provider import _id_token
        other_user = User(
            email=f"other-{uuid4().hex}@example.test", password_hash="test-only",
            display_name="Other Browser User", status="active",
        )
        self.db.add(other_user)
        self.db.flush()
        other_cookie = f"other-refresh-{uuid4().hex}"
        self.db.add(RefreshSession(
            user_id=other_user.id,
            token_hash=hashlib.sha256(other_cookie.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        ))
        self.db.flush()
        hint = _id_token(self.user, self.app, {"openid"}, None, "test-access-token")

        response = asyncio.run(end_session(
            self.logout_request(hint, self.logout_callback, "logout-state-123"), other_cookie, self.db,
        ))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("set-cookie", response.headers)
        other_session = self.db.scalar(select(RefreshSession).where(
            RefreshSession.token_hash == hashlib.sha256(other_cookie.encode()).hexdigest(),
        ))
        self.assertIsNone(other_session.revoked_at)

    def test_discovery_advertises_implemented_end_session_endpoint(self) -> None:
        metadata = discovery_document()
        self.assertTrue(metadata["end_session_endpoint"].endswith("/oidc/logout"))
        self.assertTrue(metadata["introspection_endpoint"].endswith("/oidc/introspect"))
        self.assertEqual(metadata["introspection_endpoint_auth_methods_supported"], ["client_secret_basic"])

    def logout_request(self, id_token_hint: str, post_logout_redirect_uri: str, state: str) -> Request:
        params = urlencode({
            "id_token_hint": id_token_hint,
            "post_logout_redirect_uri": post_logout_redirect_uri,
            "state": state,
        })
        path = "/api/v1/oidc/logout"
        return Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path, "raw_path": path.encode(), "root_path": "",
            "query_string": params.encode(), "headers": [],
            "client": ("127.0.0.1", 51237), "server": ("localhost", 8000),
        })

    def token_request(self, body: bytes) -> Request:
        path = "/api/v1/oidc/token"
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": path, "raw_path": path.encode(), "root_path": "",
            "query_string": b"", "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
            "client": ("127.0.0.1", 51235), "server": ("localhost", 8000),
        }, receive=receive)


if __name__ == "__main__":
    unittest.main()
