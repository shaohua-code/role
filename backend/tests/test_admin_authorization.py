"""租户管理权限必须由角色/节点判权授予，平台权限仍独立受保护。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from app.services.admin_authorization import (
    APPLICATION_MANAGE,
    APPLICATION_READ,
    APPLICATION_SECRET_ROTATE,
    AdminAccessGuard,
)


class TenantOrganizationAdminAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actor = object()
        self.db = object()
        self.tenant_id = uuid4()

    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_any_role", return_value=False)
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=True)
    def test_platform_admin_bypasses_tenant_grants(self, _is_platform_admin, has_role) -> None:
        self.assertTrue(AdminAccessGuard.has_organization_admin_access(self.actor, self.tenant_id, self.db, manage=True))
        has_role.assert_not_called()

    @patch("app.services.rbac_guards.PermissionEnforcer.ensure_codes")
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    def test_read_and_manage_check_node_codes(self, _is_platform_admin, ensure_codes_mock) -> None:
        # 读主分支按节点 any-of 判权：menu.organization_workspace（组织工作台）或
        # menu.users（绿场 §6.6 租户模式用户管理页的入口码，避免「菜单可见但接口 403」
        # 口径漂移）；写（P1-2 收口）统一认 button.org.manage。
        self.assertTrue(AdminAccessGuard.has_organization_admin_access(self.actor, self.tenant_id, self.db))
        self.assertIn("menu.organization_workspace", ensure_codes_mock.call_args.args[2:])
        self.assertIn("menu.users", ensure_codes_mock.call_args.args[2:])
        self.assertTrue(AdminAccessGuard.has_organization_admin_access(self.actor, self.tenant_id, self.db, manage=True))
        self.assertEqual(ensure_codes_mock.call_args.args[2], "button.org.manage")

    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_any_role", return_value=True)
    @patch("app.services.rbac_guards.PermissionEnforcer.ensure_codes",
           side_effect=HTTPException(status_code=403, detail="缺少组织查看权限"))
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    def test_read_falls_back_to_console_roles(self, _is_platform_admin, _ensure, has_role) -> None:
        # 读兜底：无组织菜单码但持租户管理台角色（L2/L3）→ 放行（数据范围端点「L2 只读」
        # 把本读检查复用为角色可见性语义，L2 模板不含租户级组织菜单码）。
        self.assertTrue(AdminAccessGuard.has_organization_admin_access(self.actor, self.tenant_id, self.db))
        self.assertTrue(has_role.called)

    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_any_role", return_value=False)
    @patch("app.services.rbac_guards.PermissionEnforcer.ensure_codes",
           side_effect=HTTPException(status_code=403, detail="缺少组织查看权限"))
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    def test_read_fails_closed(self, _is_platform_admin, _ensure, has_role) -> None:
        # 既无菜单码也无管理台角色 → 拒绝。
        self.assertFalse(AdminAccessGuard.has_organization_admin_access(self.actor, self.tenant_id, self.db))

    @patch("app.services.rbac_guards.PermissionEnforcer.ensure_codes",
           side_effect=HTTPException(status_code=403, detail="缺少组织管理权限"))
    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_any_role", return_value=False)
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    def test_missing_grant_fails_closed_with_forbidden(self, _is_platform_admin, _has_role, _ensure) -> None:
        with self.assertRaises(HTTPException) as denied:
            AdminAccessGuard.require_organization_admin_access(self.actor, self.tenant_id, self.db, manage=True)
        self.assertEqual(denied.exception.status_code, 403)


class ApplicationAdminAccessTests(unittest.TestCase):
    """应用管理判权：租户级及以上管本租户全部应用；应用级按节点判权且不能向上。"""

    def setUp(self) -> None:
        self.actor = object()
        self.db = object()
        self.tenant_id = uuid4()
        self.application_id = uuid4()

    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_management_code", return_value=False)
    @patch("app.services.rbac_guards.PermissionEnforcer.scope_at_least", return_value=False)
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=True)
    def test_platform_admin_bypasses(self, _is_platform_admin, _scope, _code) -> None:
        self.assertTrue(AdminAccessGuard.has_application_admin_access(
            self.actor, self.tenant_id, self.db, manage=True, application_id=self.application_id,
        ))

    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_management_code", return_value=False)
    @patch("app.services.rbac_guards.PermissionEnforcer.scope_at_least", return_value=True)
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    @patch("app.services.admin_authorization.AdminAccessGuard.has_active_tenant_membership", return_value=True)
    def test_tenant_scope_manages_all_apps_in_tenant(self, _membership, _is_platform_admin, _scope, code) -> None:
        # 租户级读写全部放行；密钥轮换仍需持 button.apps.secret 节点。
        self.assertTrue(AdminAccessGuard.has_application_admin_access(
            self.actor, self.tenant_id, self.db, manage=True, application_id=self.application_id,
        ))
        code.assert_not_called()
        self.assertFalse(AdminAccessGuard.has_application_admin_access(
            self.actor, self.tenant_id, self.db, rotate_secret=True, application_id=self.application_id,
        ))
        self.assertEqual(code.call_args.args[2], APPLICATION_SECRET_ROTATE)

    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_management_code", return_value=False)
    @patch("app.services.rbac_guards.PermissionEnforcer.scope_at_least", return_value=True)
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    @patch("app.services.admin_authorization.AdminAccessGuard.has_active_tenant_membership", return_value=False)
    def test_cross_tenant_scope_denied_without_target_membership(
            self, _membership, _is_platform_admin, _scope, code) -> None:
        # P1 收口：范围秩跨所有成员关系取最高，租户 A 管理员对无成员关系的租户 B
        # 必须一律拒绝（含读、写与创建入口），不能凭范围秩放行。
        self.assertFalse(AdminAccessGuard.has_application_admin_access(
            self.actor, self.tenant_id, self.db, manage=True, application_id=self.application_id,
        ))
        self.assertFalse(AdminAccessGuard.has_application_admin_access(
            self.actor, self.tenant_id, self.db, application_id=self.application_id,
        ))
        self.assertFalse(AdminAccessGuard.has_application_admin_access(
            self.actor, self.tenant_id, self.db, manage=True,
        ))
        code.assert_not_called()

    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_management_code", return_value=True)
    @patch("app.services.rbac_guards.PermissionEnforcer.scope_at_least", return_value=False)
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    @patch("app.services.admin_authorization.AdminAccessGuard.has_active_tenant_membership", return_value=True)
    def test_app_scope_requires_nodes(self, _membership, _is_platform_admin, _scope, code) -> None:
        # 应用级：读/写/轮换分别认对应按钮/菜单节点。
        self.assertTrue(AdminAccessGuard.has_application_admin_access(
            self.actor, self.tenant_id, self.db, application_id=self.application_id,
        ))
        self.assertEqual(code.call_args.args[2], APPLICATION_READ)
        self.assertTrue(AdminAccessGuard.has_application_admin_access(
            self.actor, self.tenant_id, self.db, manage=True, application_id=self.application_id,
        ))
        self.assertEqual(code.call_args.args[2], APPLICATION_MANAGE)

    @patch("app.services.rbac_guards.PermissionEnforcer.user_has_management_code", return_value=True)
    @patch("app.services.rbac_guards.PermissionEnforcer.scope_at_least", return_value=False)
    @patch("app.services.admin_authorization.is_platform_admin_user", return_value=False)
    @patch("app.services.admin_authorization.AdminAccessGuard.has_active_tenant_membership", return_value=True)
    def test_app_scope_cannot_create(self, _membership, _is_platform_admin, _scope, code) -> None:
        # 未钉应用 = 租户级生命周期（创建入口）；应用级不能向上。
        code.assert_not_called()
        self.assertFalse(AdminAccessGuard.has_application_admin_access(self.actor, self.tenant_id, self.db, manage=True))


if __name__ == "__main__":
    unittest.main()
