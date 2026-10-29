"""FastAPI adapter contract tests; the IAM client is mocked, no network is used."""
import unittest
from typing import Annotated
from unittest.mock import Mock

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from iam_authorization import AuthorizationDecision, AuthorizationServiceError, IamAuthorizationClient
from iam_fastapi import IAMFastAPI, IAMUserContext

TENANT = "tenant-uuid"
SUBJECT = "user-1"
TOKEN = "access-token"


def _owner_scope(subject: str) -> dict:
    return {"mode": "any_of", "constraints": [
        {"kind": "owner", "field": "owner_user_id", "user_id": subject, "tenant_id": TENANT},
    ]}


def _fake_session(request: Request) -> IAMUserContext:
    """测试桩：扮演业务方已验签会话；缺失时按业务语义抛 401。"""
    token = request.headers.get("x-access-token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Missing session")
    return IAMUserContext(
        access_token=token,
        tenant_id=request.headers.get("x-tenant", ""),
        subject_id=request.headers.get("x-subject", ""),
    )


class IamFastapiAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = Mock(spec=IamAuthorizationClient)
        self.iam = IAMFastAPI(
            client=self.client,
            session_dependency=_fake_session,
            permission_map={"document.read": "crm.document.read"},
            local_user_id_resolver=lambda user: f"local-{user.subject_id}",
        )
        self.app = FastAPI()

        @self.app.get("/documents")
        def read_documents(permission: Annotated[object, Depends(self.iam.require_permission("document.read"))]):
            return {"allowed": permission.decision.allowed}

        @self.app.get("/my-documents")
        def my_documents(
            permission: Annotated[object, Depends(self.iam.require_permission("document.read", owner_only=True))],
        ):
            return {"local_user_id": permission.user.local_user_id}

        @self.app.get("/me")
        def me(user: Annotated[IAMUserContext, Depends(self.iam.current_user())]):
            return {"subject": user.subject_id}

        self.test_client = TestClient(self.app, raise_server_exceptions=False)

    def test_maps_alias_to_stable_code_and_returns_decision(self) -> None:
        self.client.require.return_value = AuthorizationDecision(True, "matching_role_grant")
        response = self.test_client.get(
            "/documents", headers={"x-access-token": TOKEN, "x-tenant": TENANT, "x-subject": SUBJECT},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"allowed": True})
        self.client.require.assert_called_once_with(TOKEN, TENANT, "crm.document.read")

    def test_denied_decision_maps_to_403(self) -> None:
        # 真实 require() 在 denied 时抛 403 错误；Mock 必须模拟同一行为。
        self.client.require.side_effect = AuthorizationServiceError(403, "Permission denied: no_matching_grant")
        response = self.test_client.get(
            "/documents", headers={"x-access-token": TOKEN, "x-tenant": TENANT, "x-subject": SUBJECT},
        )
        self.assertEqual(response.status_code, 403)

    def test_iam_unavailability_maps_to_503(self) -> None:
        self.client.require.side_effect = AuthorizationServiceError(503, "IAM authorization service is unavailable")
        response = self.test_client.get(
            "/documents", headers={"x-access-token": TOKEN, "x-tenant": TENANT, "x-subject": SUBJECT},
        )
        self.assertEqual(response.status_code, 503)

    def test_contract_error_maps_to_502(self) -> None:
        self.client.require.side_effect = AuthorizationServiceError(502, "IAM returned an invalid authorization decision")
        response = self.test_client.get(
            "/documents", headers={"x-access-token": TOKEN, "x-tenant": TENANT, "x-subject": SUBJECT},
        )
        self.assertEqual(response.status_code, 502)

    def test_unregistered_alias_fails_closed_before_any_request(self) -> None:
        with self.assertRaisesRegex(LookupError, "not registered"):
            self.iam.require_permission("resume.export")
        self.client.require.assert_not_called()

    def test_owner_only_passes_subject_and_resolves_local_user_id(self) -> None:
        self.client.check.return_value = AuthorizationDecision(
            True, "matching_role_grant", data_scope=_owner_scope(SUBJECT),
        )
        response = self.test_client.get(
            "/my-documents", headers={"x-access-token": TOKEN, "x-tenant": TENANT, "x-subject": SUBJECT},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"local_user_id": f"local-{SUBJECT}"})
        self.client.check.assert_called_once_with(
            TOKEN, TENANT, "crm.document.read", include_data_scope=True, subject_id=SUBJECT,
        )

    def test_owner_only_rejects_widened_scope_with_403(self) -> None:
        # any_of 是 OR 语义：任何 tenant 分支都会放宽可见范围，owner_only 必须整体拒绝。
        widened = {"mode": "any_of", "constraints": [
            {"kind": "owner", "field": "owner_user_id", "user_id": SUBJECT, "tenant_id": TENANT},
            {"kind": "tenant", "tenant_id": TENANT},
        ]}
        self.client.check.return_value = AuthorizationDecision(True, "matching_role_grant", data_scope=widened)
        response = self.test_client.get(
            "/my-documents", headers={"x-access-token": TOKEN, "x-tenant": TENANT, "x-subject": SUBJECT},
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_only_requires_local_user_id_resolver_at_configuration_time(self) -> None:
        with self.assertRaisesRegex(LookupError, "local_user_id_resolver"):
            IAMFastAPI(
                client=self.client,
                session_dependency=_fake_session,
                permission_map={"document.read": "crm.document.read"},
            ).require_permission("document.read", owner_only=True)

    def test_current_user_exposes_verified_session_context(self) -> None:
        response = self.test_client.get(
            "/me", headers={"x-access-token": TOKEN, "x-tenant": TENANT, "x-subject": SUBJECT},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"subject": SUBJECT})

    def test_missing_session_maps_to_401_via_business_dependency(self) -> None:
        response = self.test_client.get("/documents", headers={"x-tenant": TENANT, "x-subject": SUBJECT})
        self.assertEqual(response.status_code, 401)
        self.client.require.assert_not_called()


if __name__ == "__main__":
    unittest.main()
