"""租户管理权限必须由既有 RBAC 决策服务授予，平台权限仍独立受保护。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.services.admin_authorization import (
    ORGANIZATION_MANAGE,
    ORGANIZATION_READ,
    has_organization_admin_access,
    require_organization_admin_access,
)


class TenantOrganizationAdminAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actor = object()
        self.db = object()
        self.tenant_id = uuid4()

    @patch("app.services.admin_authorization.evaluate_access")
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=True)
    def test_platform_admin_bypasses_tenant_grants(self, _is_platform_admin, evaluate_access) -> None:
        self.assertTrue(has_organization_admin_access(self.actor, self.tenant_id, self.db, manage=True))
        evaluate_access.assert_not_called()

    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    @patch("app.services.admin_authorization.evaluate_access")
    def test_manage_grant_also_allows_read(self, evaluate_access, _is_platform_admin) -> None:
        evaluate_access.side_effect = [
            {"decision": {"allowed": False}},
            {"decision": {"allowed": True}},
        ]

        self.assertTrue(has_organization_admin_access(self.actor, self.tenant_id, self.db))
        codes = [call.args[0].permission_code for call in evaluate_access.call_args_list]
        self.assertEqual(codes, [ORGANIZATION_READ, ORGANIZATION_MANAGE])

    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    @patch("app.services.admin_authorization.evaluate_access")
    def test_read_only_grant_cannot_manage(self, evaluate_access, _is_platform_admin) -> None:
        evaluate_access.return_value = {"decision": {"allowed": False}}

        self.assertFalse(has_organization_admin_access(self.actor, self.tenant_id, self.db, manage=True))
        self.assertEqual(evaluate_access.call_args.args[0].permission_code, ORGANIZATION_MANAGE)

    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    @patch("app.services.admin_authorization.evaluate_access")
    def test_missing_grant_fails_closed_with_forbidden(self, evaluate_access, _is_platform_admin) -> None:
        evaluate_access.return_value = {"decision": {"allowed": False}}

        with self.assertRaises(HTTPException) as denied:
            require_organization_admin_access(self.actor, self.tenant_id, self.db, manage=True)
        self.assertEqual(denied.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
