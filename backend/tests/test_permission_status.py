"""覆盖稳定权限编码停用后的默认拒绝、历史授权保留和恢复语义。"""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.access_control import (
    grant_permission,
    revoke_permission,
    set_permission_status,
)
from app.db.base import Base
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.identity import AuditEvent, Tenant, TenantMembership, User
from app.models.organization import RoleDataScope
from app.schemas.access_control import PermissionStatusUpdate
from app.services.authorization import evaluate_access
from app.services.permission_impact import (
    apply_role_permissions,
    preview_role_permissions,
)


class PermissionStatusTests(unittest.TestCase):
    """每个用例只操作独立内存库，不触碰当前开发或生产数据库。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(id=uuid4(), name="权限状态测试", slug=f"permission-{uuid4().hex[:16]}")
        self.actor = User(id=uuid4(), email=f"permission-{uuid4().hex}@example.test",
                          password_hash="test-only", display_name="权限管理员")
        self.user = User(id=uuid4(), email=f"member-{uuid4().hex}@example.test",
                         password_hash="test-only", display_name="租户成员")
        self.role = Role(id=uuid4(), tenant_id=self.tenant.id, key=f"role-{uuid4().hex[:12]}", name="阅读角色")
        self.permission = Permission(id=uuid4(), code=f"document.read.{uuid4().hex[:8]}",
                                     resource_type="document", scope="read")
        self.db.add_all([self.tenant, self.actor, self.user, self.role, self.permission])
        self.db.flush()
        self.membership = TenantMembership(tenant_id=self.tenant.id, user_id=self.user.id, status="active")
        self.db.add(self.membership)
        self.db.flush()
        self.grant = RolePermission(role_id=self.role.id, permission_id=self.permission.id)
        self.db.add_all([self.grant, RoleBinding(membership_id=self.membership.id, role_id=self.role.id)])
        self.db.commit()
        self.request = Request({
            "type": "http", "http_version": "1.1", "method": "PATCH", "scheme": "http",
            "path": f"/api/v1/admin/permissions/{self.permission.id}/status",
            "raw_path": f"/api/v1/admin/permissions/{self.permission.id}/status".encode(),
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80), "root_path": "",
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _body(self) -> SimpleNamespace:
        return SimpleNamespace(tenant_id=self.tenant.id, application_id=None,
                               permission_code=self.permission.code, resource_id=None,
                               include_data_scope=False)

    def test_disable_denies_online_check_and_preserves_grant_for_explicit_restore(self) -> None:
        self.assertTrue(evaluate_access(self._body(), self.user, self.db)["decision"]["allowed"])

        disabled = set_permission_status(
            self.permission.id,
            PermissionStatusUpdate(expected_status="active", status="disabled"),
            self.request, self.actor, self.db,
        )

        self.assertEqual(disabled["status"], "disabled")
        self.assertEqual(disabled["assigned_role_count"], 1)
        self.assertFalse(evaluate_access(self._body(), self.user, self.db)["decision"]["allowed"])
        self.assertIsNotNone(self.db.get(RolePermission, self.grant.id))

        restored = set_permission_status(
            self.permission.id,
            PermissionStatusUpdate(expected_status="disabled", status="active"),
            self.request, self.actor, self.db,
        )

        self.assertTrue(restored["reactivates_existing_grants"])
        self.assertTrue(evaluate_access(self._body(), self.user, self.db)["decision"]["allowed"])
        events = self.db.scalars(select(AuditEvent).where(AuditEvent.action == "permission.status.change")).all()
        self.assertEqual(len(events), 2)
        self.assertEqual({event.details["to_status"] for event in events}, {"active", "disabled"})

    def test_stale_expected_status_returns_conflict(self) -> None:
        with self.assertRaises(HTTPException) as error:
            set_permission_status(
                self.permission.id,
                PermissionStatusUpdate(expected_status="disabled", status="active"),
                self.request, self.actor, self.db,
            )
        self.assertEqual(error.exception.status_code, 409)

    def test_disabled_permission_cannot_be_granted_but_existing_grant_can_be_retained_or_removed(self) -> None:
        set_permission_status(
            self.permission.id,
            PermissionStatusUpdate(expected_status="active", status="disabled"),
            self.request, self.actor, self.db,
        )
        second_role = Role(tenant_id=self.tenant.id, key=f"role-{uuid4().hex[:12]}", name="新角色")
        self.db.add(second_role)
        self.db.commit()

        with self.assertRaises(ValueError):
            preview_role_permissions(second_role.id, [self.permission.id], self.db)
        with self.assertRaises(HTTPException) as error:
            grant_permission(second_role.id, self.permission.id, self.request, None, self.actor, self.db)
        self.assertEqual(error.exception.status_code, 409)

        retained = apply_role_permissions(self.role.id, [self.permission.id], [self.permission.id], self.db)
        self.assertFalse(retained["changed"])
        grant_id = self.grant.id
        removed = apply_role_permissions(self.role.id, [], [self.permission.id], self.db)
        self.assertTrue(removed["changed"])
        self.assertIsNone(self.db.get(RolePermission, grant_id))

    def test_resource_revoke_removes_exact_grant_and_preserves_scope_until_last_grant(self) -> None:
        """撤销资源权限只影响目标 ID，数据范围在同权限最后一项撤销前保留。"""
        first_resource, second_resource = "knowledge-app-a", "knowledge-app-b"
        first_grant = RolePermission(
            role_id=self.role.id,
            permission_id=self.permission.id,
            resource_id=first_resource,
        )
        second_grant = RolePermission(
            role_id=self.role.id,
            permission_id=self.permission.id,
            resource_id=second_resource,
        )
        data_scope = RoleDataScope(
            tenant_id=self.tenant.id,
            role_id=self.role.id,
            permission_id=self.permission.id,
            scope_type="tenant",
            organization_ids=[],
        )
        self.db.add_all([first_grant, second_grant, data_scope])
        self.db.commit()
        first_grant_id = first_grant.id
        second_grant_id = second_grant.id
        generic_grant_id = self.grant.id
        data_scope_id = data_scope.id

        revoke_permission(
            self.role.id,
            self.permission.id,
            self.request,
            self.actor,
            self.db,
            resource_id=first_resource,
        )

        self.assertIsNone(self.db.get(RolePermission, first_grant_id))
        self.assertIsNotNone(self.db.get(RolePermission, second_grant_id))
        self.assertIsNotNone(self.db.get(RolePermission, generic_grant_id))
        self.assertIsNotNone(self.db.get(RoleDataScope, data_scope_id))

        revoke_permission(
            self.role.id,
            self.permission.id,
            self.request,
            self.actor,
            self.db,
            resource_id=None,
        )
        self.assertIsNotNone(self.db.get(RoleDataScope, data_scope_id))

        revoke_permission(
            self.role.id,
            self.permission.id,
            self.request,
            self.actor,
            self.db,
            resource_id=second_resource,
        )
        self.assertIsNone(self.db.get(RoleDataScope, data_scope_id))


if __name__ == "__main__":
    unittest.main()
