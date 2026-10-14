"""Standard-library tests for fail-closed behavior in the Python SDK."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from iam_authorization import AuthorizationServiceError, IamAuthorizationClient, compile_postgres_data_scope


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.payload.read()


class IamAuthorizationClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = IamAuthorizationClient("https://iam.example", "app-uuid")

    @patch("iam_authorization.urlopen")
    def test_check_sends_access_token_and_application_context(self, open_url) -> None:
        open_url.return_value = _Response({"allowed": True, "reason": "matching_role_grant"})
        decision = self.client.check("access-token", "tenant-uuid", "resume.read")
        request = open_url.call_args.args[0]
        self.assertTrue(decision.allowed)
        self.assertEqual(request.full_url, "https://iam.example/api/v1/authorization/check")
        self.assertEqual(request.get_header("Authorization"), "Bearer access-token")
        self.assertEqual(json.loads(request.data), {
            "tenant_id": "tenant-uuid", "application_id": "app-uuid",
            "permission_code": "resume.read", "include_data_scope": False,
        })

    @patch("iam_authorization.urlopen")
    def test_denied_decision_raises_when_permission_is_required(self, open_url) -> None:
        open_url.return_value = _Response({"allowed": False, "reason": "no_matching_grant"})
        with self.assertRaises(AuthorizationServiceError) as error:
            self.client.require("access-token", "tenant-uuid", "resume.delete")
        self.assertEqual(error.exception.status_code, 403)

    @patch("iam_authorization.urlopen", side_effect=URLError("offline"))
    def test_network_failure_fails_closed(self, _open_url) -> None:
        with self.assertRaises(AuthorizationServiceError) as error:
            self.client.require("access-token", "tenant-uuid", "resume.read")
        self.assertEqual(error.exception.status_code, 503)

    @patch("iam_authorization.urlopen")
    def test_invalid_decision_fails_closed(self, open_url) -> None:
        open_url.return_value = _Response({"allowed": "yes", "reason": "forged"})
        with self.assertRaises(AuthorizationServiceError) as error:
            self.client.require("access-token", "tenant-uuid", "resume.read")
        self.assertEqual(error.exception.status_code, 502)

    @patch("iam_authorization.urlopen")
    def test_valid_any_of_scope_requires_tenant_on_every_branch(self, open_url) -> None:
        open_url.return_value = _Response({"allowed": True, "reason": "matching_role_grant", "data_scope": {
            "mode": "any_of", "constraints": [
                {"kind": "owner", "field": "owner_user_id", "user_id": "user-1", "tenant_id": "tenant-uuid"},
                {"kind": "organizations", "field": "organization_id", "organization_ids": [], "tenant_id": "tenant-uuid"},
            ],
        }})
        decision = self.client.check("access-token", "tenant-uuid", "resume.read", include_data_scope=True,
                                     subject_id="user-1")
        request = open_url.call_args.args[0]
        self.assertEqual(len(decision.data_scope["constraints"]), 2)
        self.assertNotIn("user_id", json.loads(request.data))
        self.assertNotIn("subject_id", json.loads(request.data))

    @patch("iam_authorization.urlopen")
    def test_cross_tenant_or_missing_scope_fails_closed(self, open_url) -> None:
        for data_scope in (
            {"mode": "any_of", "constraints": [
                {"kind": "owner", "field": "owner_user_id", "user_id": "user-1", "tenant_id": "other-tenant"},
            ]},
            {"mode": "any_of", "constraints": []},
            {"mode": "any_of", "constraints": [{"kind": ["owner"], "tenant_id": "tenant-uuid"}]},
        ):
            with self.subTest(data_scope=data_scope):
                open_url.return_value = _Response({"allowed": True, "reason": "matching_role_grant", "data_scope": data_scope})
                with self.assertRaises(AuthorizationServiceError) as error:
                    self.client.check("access-token", "tenant-uuid", "resume.read", include_data_scope=True,
                                      subject_id="user-1")
                self.assertEqual(error.exception.status_code, 502)

    @patch("iam_authorization.urlopen")
    def test_owner_scope_must_match_the_verified_local_user(self, open_url) -> None:
        open_url.return_value = _Response({"allowed": True, "reason": "matching_role_grant", "data_scope": {
            "mode": "any_of", "constraints": [
                {"kind": "owner", "field": "owner_user_id", "user_id": "user-2", "tenant_id": "tenant-uuid"},
            ],
        }})
        with self.assertRaises(AuthorizationServiceError) as error:
            self.client.check("access-token", "tenant-uuid", "resume.read", include_data_scope=True,
                              subject_id="user-1")
        self.assertEqual(error.exception.status_code, 502)

    @patch("iam_authorization.urlopen")
    def test_data_scope_requires_verified_iam_subject_before_network_call(self, open_url) -> None:
        with self.assertRaisesRegex(ValueError, "locally verified IAM subject_id"):
            self.client.check("access-token", "tenant-uuid", "resume.read", include_data_scope=True)
        open_url.assert_not_called()

    @patch("iam_authorization.urlopen")
    def test_positive_data_aware_decision_without_scope_fails_closed(self, open_url) -> None:
        open_url.return_value = _Response({"allowed": True, "reason": "matching_role_grant"})
        with self.assertRaises(AuthorizationServiceError) as error:
            self.client.check("access-token", "tenant-uuid", "resume.read", include_data_scope=True,
                              subject_id="user-1")
        self.assertEqual(error.exception.status_code, 502)

    # 编译回归覆盖每个 OR 分支的 tenant AND、本地主键映射与参数化条件。
    def test_scope_compiler_maps_business_keys_and_binds_each_tenant_branch(self) -> None:
        result = compile_postgres_data_scope({"mode": "any_of", "constraints": [
            {"kind": "owner", "field": "owner_user_id", "user_id": "user-1", "tenant_id": "tenant-uuid"},
            {"kind": "organizations", "field": "organization_id", "organization_ids": ["org-1"], "tenant_id": "tenant-uuid"},
        ]}, tenant_id="tenant-uuid", subject_id="user-1",
            columns={"tenant_id": "r.tenant_id", "owner_user_id": "r.user_id", "organization_id": "r.organization_id"},
            map_tenant_id=lambda _tenant: "business-tenant",
            map_owner_user_id=lambda subject, _tenant: f"local-{subject}",
            map_organization_ids=lambda ids, _tenant: [f"mapped-{value}" for value in ids])

        self.assertEqual(result.sql,
                         '(("r"."tenant_id" = :iam_scope_1 AND "r"."user_id" = :iam_scope_2) OR '
                         '("r"."tenant_id" = :iam_scope_3 AND "r"."organization_id" = ANY(:iam_scope_4)))')
        self.assertEqual(result.parameters, {
            "iam_scope_1": "business-tenant", "iam_scope_2": "local-user-1",
            "iam_scope_3": "business-tenant", "iam_scope_4": ["mapped-org-1"],
        })
        self.assertEqual(result.sql.count('"r"."tenant_id" ='), 2)
        self.assertNotIn("user-1", result.parameters.values())

    # 空组织列表必须明确返回零行，列名和 tenant 错配都要被 fail closed 拒绝。
    def test_scope_compiler_empty_organization_matches_no_rows_and_rejects_tampering(self) -> None:
        result = compile_postgres_data_scope({"mode": "any_of", "constraints": [
            {"kind": "organizations", "field": "organization_id", "organization_ids": [], "tenant_id": "tenant-uuid"},
        ]}, tenant_id="tenant-uuid", subject_id="user-1",
            columns={"tenant_id": "r.tenant_id", "organization_id": "r.organization_id"})
        self.assertEqual(result.sql, '(("r"."tenant_id" = :iam_scope_1 AND FALSE))')

        with self.assertRaises(AuthorizationServiceError):
            compile_postgres_data_scope({"mode": "any_of", "constraints": [
                {"kind": "tenant", "tenant_id": "other-tenant"},
            ]}, tenant_id="tenant-uuid", subject_id="user-1", columns={"tenant_id": "r.tenant_id"})
        with self.assertRaises(AuthorizationServiceError):
            compile_postgres_data_scope({"mode": "any_of", "constraints": [
                {"kind": "tenant", "tenant_id": "tenant-uuid"},
            ]}, tenant_id="tenant-uuid", subject_id="user-1", columns={"tenant_id": "r.tenant_id OR TRUE"})
        with self.assertRaises(AuthorizationServiceError) as error:
            compile_postgres_data_scope({"mode": "any_of", "constraints": [
                {"kind": "owner", "field": "owner_user_id", "user_id": "user-1", "tenant_id": "tenant-uuid"},
            ]}, tenant_id="tenant-uuid", subject_id="user-1",
                columns={"tenant_id": "r.tenant_id", "owner_user_id": "r.user_id"},
                map_owner_user_id=lambda *_args: (_ for _ in ()).throw(RuntimeError("internal database detail")))
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("internal database detail", str(error.exception))


if __name__ == "__main__":
    unittest.main()
