"""SQLite regression coverage for role-permission impact previews."""

import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (  # noqa: F401 - import all mappings before creating the test schema
    Application,
    Permission,
    Role,
    RoleBinding,
    RolePermission,
    Tenant,
    TenantMembership,
    User,
    UserGroup,
    UserGroupMembership,
    UserGroupRole,
)
from app.services.permission_impact import preview_role_permissions


class PermissionImpactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant_id = uuid4()
        self.tenant = Tenant(id=self.tenant_id, name="Impact Test", slug=f"impact-{uuid4().hex[:20]}")
        self.target_role = Role(
            id=uuid4(), tenant_id=self.tenant_id, key=f"target-{uuid4().hex[:8]}",
            name="Target", status="active",
        )
        self.permission = Permission(
            id=uuid4(), code=f"resume.read.{uuid4().hex[:8]}",
            resource_type="resume", scope="read", status="active",
        )
        self.db.add(self.tenant)
        self.db.flush()
        self.db.add_all([self.target_role, self.permission])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_member(self, suffix: str) -> TenantMembership:
        user = User(
            id=uuid4(), email=f"{suffix}-{uuid4().hex[:8]}@example.test",
            password_hash="test-only", display_name=suffix, status="active",
        )
        self.db.add(user)
        self.db.flush()
        membership = TenantMembership(
            id=uuid4(), tenant_id=self.tenant_id, user_id=user.id, status="active",
        )
        self.db.add(membership)
        self.db.flush()
        return membership

    def test_counts_direct_and_group_members_once_and_subtracts_general_overlap(self) -> None:
        first, second = self.add_member("first"), self.add_member("second")
        other_role = Role(
            id=uuid4(), tenant_id=self.tenant_id, key=f"other-{uuid4().hex[:8]}",
            name="Other", status="active",
        )
        group = UserGroup(
            id=uuid4(), tenant_id=self.tenant_id, key=f"group-{uuid4().hex[:8]}",
            name="Editors", status="active",
        )
        self.db.add_all([other_role, group])
        self.db.flush()
        # 第一位成员同时直接绑定并经用户组继承目标角色，应只统计一次。
        self.db.add_all([
            RoleBinding(membership_id=first.id, role_id=self.target_role.id),
            RoleBinding(membership_id=first.id, role_id=other_role.id),
            UserGroupMembership(group_id=group.id, membership_id=first.id, tenant_id=self.tenant_id),
            UserGroupMembership(group_id=group.id, membership_id=second.id, tenant_id=self.tenant_id),
            UserGroupRole(group_id=group.id, role_id=self.target_role.id, tenant_id=self.tenant_id),
            RolePermission(role_id=other_role.id, permission_id=self.permission.id),
        ])
        self.db.flush()

        impact = preview_role_permissions(self.target_role.id, [self.permission.id], self.db)

        self.assertEqual(impact["bound_active_members"], 2)
        self.assertEqual(impact["potentially_affected_members"], 1)
        self.assertEqual(impact["permission_impacts"], [{
            "permission_code": self.permission.code,
            "action": "grant",
            "eligible_members": 2,
            "covered_by_other_general_roles": 1,
            "potentially_affected_members": 1,
        }])

    def test_resource_instance_grant_does_not_cover_a_general_grant(self) -> None:
        member = self.add_member("scoped")
        other_role = Role(
            id=uuid4(), tenant_id=self.tenant_id, key=f"other-{uuid4().hex[:8]}",
            name="Other", status="active",
        )
        self.db.add(other_role)
        self.db.flush()
        self.db.add_all([
            RoleBinding(membership_id=member.id, role_id=self.target_role.id),
            RoleBinding(membership_id=member.id, role_id=other_role.id),
            RolePermission(role_id=other_role.id, permission_id=self.permission.id, resource_id="resume-1"),
        ])
        self.db.flush()

        impact = preview_role_permissions(self.target_role.id, [self.permission.id], self.db)

        self.assertEqual(impact["bound_active_members"], 1)
        self.assertEqual(impact["potentially_affected_members"], 1)
        self.assertEqual(impact["permission_impacts"][0]["covered_by_other_general_roles"], 0)

    def test_disabled_group_does_not_contribute_members(self) -> None:
        member = self.add_member("disabled-group")
        group = UserGroup(
            id=uuid4(), tenant_id=self.tenant_id, key=f"group-{uuid4().hex[:8]}",
            name="Disabled", status="disabled",
        )
        self.db.add(group)
        self.db.flush()
        self.db.add_all([
            UserGroupMembership(group_id=group.id, membership_id=member.id, tenant_id=self.tenant_id),
            UserGroupRole(group_id=group.id, role_id=self.target_role.id, tenant_id=self.tenant_id),
        ])
        self.db.flush()

        impact = preview_role_permissions(self.target_role.id, [self.permission.id], self.db)
        self.assertEqual(impact["bound_active_members"], 0)
        self.assertEqual(impact["potentially_affected_members"], 0)


    def test_other_application_role_does_not_cover_target_application_change(self) -> None:
        member = self.add_member("app-scoped")
        target_application = Application(
            id=uuid4(), tenant_id=self.tenant_id, client_id=f"target-{uuid4().hex[:10]}",
            name="Target app", redirect_uris=[], post_logout_redirect_uris=[], status="active",
        )
        other_application = Application(
            id=uuid4(), tenant_id=self.tenant_id, client_id=f"other-{uuid4().hex[:10]}",
            name="Other app", redirect_uris=[], post_logout_redirect_uris=[], status="active",
        )
        other_role = Role(
            id=uuid4(), tenant_id=self.tenant_id, application_id=other_application.id,
            key=f"other-{uuid4().hex[:8]}", name="Other app role", status="active",
        )
        self.db.add_all([target_application, other_application, other_role])
        self.db.flush()
        self.target_role.application_id = target_application.id
        self.db.add_all([
            RoleBinding(membership_id=member.id, role_id=self.target_role.id),
            RoleBinding(membership_id=member.id, role_id=other_role.id),
            RolePermission(role_id=other_role.id, permission_id=self.permission.id),
        ])
        self.db.flush()

        impact = preview_role_permissions(self.target_role.id, [self.permission.id], self.db)

        self.assertEqual(impact["permission_impacts"][0]["covered_by_other_general_roles"], 0)
        self.assertEqual(impact["permission_impacts"][0]["potentially_affected_members"], 1)

if __name__ == "__main__":
    unittest.main()


