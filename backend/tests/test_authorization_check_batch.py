"""批量授权判定端点的契约测试：schema 约束与逐码单一判定路径。"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from pydantic import ValidationError

from app.api.v1.authorization import check_access_batch
from app.schemas.access_control import AuthorizationCheckBatch

TENANT_ID = str(uuid4())


def _batch(codes):
    return AuthorizationCheckBatch(tenant_id=TENANT_ID, permission_codes=codes)


class AuthorizationCheckBatchSchemaTests(unittest.TestCase):
    def test_empty_permission_codes_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _batch([])

    def test_more_than_32_permission_codes_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _batch([f"iam.perm.{index}" for index in range(33)])

    def test_duplicate_permission_codes_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _batch(["iam.organization.read", "iam.organization.read"])


class AuthorizationCheckBatchEndpointTests(unittest.TestCase):
    def test_each_code_evaluated_once_and_mapped_by_code(self) -> None:
        codes = ["iam.organization.read", "iam.application.manage"]
        decisions = iter([{"allowed": True}, {"allowed": False, "reason": "no_matching_grant"}])
        with patch("app.api.v1.authorization.evaluate_access", side_effect=lambda _c, _u, _db: {"decision": next(decisions)}):
            result = check_access_batch(_batch(codes), user=SimpleNamespace(), db=Mock())
        self.assertEqual(set(result["results"].keys()), set(codes))
        self.assertTrue(result["results"]["iam.organization.read"]["allowed"])
        self.assertFalse(result["results"]["iam.application.manage"]["allowed"])
        self.assertNotIn("application_id", result["results"]["iam.organization.read"])

    def test_password_user_allowed_result_has_no_oidc_application_id(self) -> None:
        user = SimpleNamespace(_auth_protocol="password")
        with patch("app.api.v1.authorization.evaluate_access", return_value={"decision": {"allowed": True}}):
            result = check_access_batch(_batch(["iam.application.read"]), user=user, db=Mock())
        self.assertNotIn("application_id", result["results"]["iam.application.read"])

    def test_oidc_allowed_result_carries_verified_application_id(self) -> None:
        app_id = str(uuid4())
        user = SimpleNamespace(_auth_protocol="oidc", _oidc_application_id=app_id)
        with patch("app.api.v1.authorization.evaluate_access", return_value={"decision": {"allowed": True}}):
            result = check_access_batch(_batch(["model.invoke"]), user=user, db=Mock())
        self.assertEqual(result["results"]["model.invoke"]["application_id"], app_id)


if __name__ == "__main__":
    unittest.main()
