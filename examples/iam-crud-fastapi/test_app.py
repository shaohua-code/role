"""End-to-end contract tests for the CRUD example; both IAM clients are mocked."""
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app import create_app
from iam_authorization import AuthorizationDecision, AuthorizationServiceError
from iam_oidc import AuthorizationAttempt, OIDCIdentity, TokenSet
from typing import Any

TENANT = "tenant-uuid"


def owner_scope(subject: str) -> dict:
    return {"mode": "any_of", "constraints": [
        {"kind": "owner", "field": "owner_user_id", "user_id": subject, "tenant_id": TENANT},
    ]}


def make_identity(subject: str, access_token: str) -> OIDCIdentity:
    """与真实 IamOIDCClient 返回一致：OIDCIdentity dataclass（插件会 asdict 序列化）。"""
    return OIDCIdentity(
        subject=subject,
        tenant_id=TENANT,
        profile={},
        tokens=TokenSet(access_token=access_token, refresh_token=f"refresh-{subject}", id_token="id-1"),
    )


class CrudExampleTests(unittest.TestCase):
    """登录 → 快照 → 创建 → owner 列表 → 越权 404 → 删除 全链路。"""

    def setUp(self) -> None:
        self.documents: dict[str, dict] = {}
        self.oidc = Mock()
        # create_authorization_request 由登录路由插件调用并序列化入库，需返回真实结构。
        self.oidc.create_authorization_request.return_value = AuthorizationAttempt(
            authorization_url="https://iam.example/authorize?state=state-1",
            state="state-1",
            nonce="nonce-1",
            code_verifier="verifier-1",
            scopes=("openid", "profile", "email"),
        )
        # callback 用直接注入会话替代；complete_login 返回目标身份。
        self.iam_client = Mock()
        self.iam_client.check.return_value = AuthorizationDecision(
            True, "matching_role_grant", data_scope=owner_scope("alice"),
        )
        self.iam_client.require.return_value = AuthorizationDecision(True, "matching_role_grant")
        self.iam_client.check_batch.return_value = {
            code: AuthorizationDecision(True, "matching_role_grant") for code in (
                "demo.document.read", "demo.document.create", "demo.document.delete",
            )
        }
        self.app = create_app(
            oidc_client=self.oidc,
            authorization_client=self.iam_client,
            documents=self.documents,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _login(self, subject: str) -> str:
        """走真实登录路由+mock 回调，模拟 mount_oidc_auth 完成后的状态。"""
        self.oidc.complete_login.return_value = make_identity(subject, f"token-{subject}")
        login = self.client.get("/auth/login", follow_redirects=False)
        attempt_cookie = login.cookies.get("iam_attempt")
        callback = self.client.get(
            "/auth/callback?code=abc&state=state-1",
            cookies={"iam_attempt": attempt_cookie},
            follow_redirects=False,
        )
        self.assertEqual(callback.status_code, 302)
        return callback.cookies.get("iam_session")

    def test_full_owner_isolated_crud_flow(self) -> None:
        alice = self._login("alice")
        # 1) 权限快照：一次批量判定全部菜单码。
        snapshot = self.client.get("/me/permissions", cookies={"iam_session": alice})
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json(), {"permissions": {
            "document.read": True, "document.create": True, "document.delete": True,
        }})
        # 快照请求应使用批量端点而不是 3 次单码调用。
        self.iam_client.check_batch.assert_called_once()
        self.iam_client.check.assert_not_called()
        # 2) 创建文档。
        created = self.client.post(
            "/documents", json={"title": "我的文档"}, cookies={"iam_session": alice},
        )
        self.assertEqual(created.status_code, 201)
        document_id = created.json()["id"]
        self.assertEqual(self.documents[document_id]["owner_subject"], "alice")
        # 3) owner 列表只见自己的文档。
        listing = self.client.get("/documents", cookies={"iam_session": alice})
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(list(listing.json()["documents"]), [document_id])
        # 4) bob 登录后：列表不含 alice 的文档，直取该文档 404（不泄露存在性）。
        bob = self._login("bob")
        self.iam_client.check.return_value = AuthorizationDecision(
            True, "matching_role_grant", data_scope=owner_scope("bob"),
        )
        bob_list = self.client.get("/documents", cookies={"iam_session": bob})
        self.assertEqual(bob_list.status_code, 200)
        self.assertEqual(bob_list.json()["documents"], {})
        forbidden = self.client.get(f"/documents/{document_id}", cookies={"iam_session": bob})
        self.assertEqual(forbidden.status_code, 404)
        # 5) alice 删除自己的文档成功；bob 删除同一 id 404。
        # bob 登录时把 check 的 owner scope 覆盖成了 bob，恢复 alice 视角后再删除。
        self.iam_client.check.return_value = AuthorizationDecision(
            True, "matching_role_grant", data_scope=owner_scope("alice"),
        )
        deleted = self.client.delete(f"/documents/{document_id}", cookies={"iam_session": alice})
        self.assertEqual(deleted.status_code, 204)
        self.assertNotIn(document_id, self.documents)
        # 真实 IAM 会按请求者返回本人 scope：bob 拿到自己的 scope 后，数据过滤表现为 404。
        self.iam_client.check.return_value = AuthorizationDecision(
            True, "matching_role_grant", data_scope=owner_scope("bob"),
        )
        bob_delete = self.client.delete(f"/documents/{document_id}", cookies={"iam_session": bob})
        self.assertEqual(bob_delete.status_code, 404)

    def test_missing_session_is_unauthorized_on_every_protected_route(self) -> None:
        self.assertEqual(self.client.get("/me/permissions").status_code, 401)
        self.assertEqual(self.client.get("/documents").status_code, 401)
        self.assertEqual(self.client.post("/documents", json={"title": "x"}).status_code, 401)

    def test_iam_unavailability_maps_to_503(self) -> None:
        alice = self._login("alice")
        self.iam_client.require.side_effect = AuthorizationServiceError(
            503, "IAM authorization service is unavailable",
        )
        response = self.client.post("/documents", json={"title": "x"}, cookies={"iam_session": alice})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
