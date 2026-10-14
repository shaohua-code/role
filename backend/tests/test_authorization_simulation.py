"""用隔离 SQLite 覆盖管理端授权模拟和生产判定共享逻辑。"""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from app.db.base import Base
from app.models import (
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
from app.models.organization import MembershipOrganization, Organization, RoleDataScope
from app.services.authorization import evaluate_access
from app.services.permission_impact import (
    StaleRolePermissionPreview,
    apply_role_permissions,
    preview_role_permissions,
)
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session


class AuthorizationSimulationTests(unittest.TestCase):
    """每个测试使用内存数据库，不读取项目配置库或留下持久数据。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(id=uuid4(), name="预演租户", slug=f"simulate-{uuid4().hex[:12]}")
        self.user = User(id=uuid4(), email=f"simulate-{uuid4().hex}@example.test", password_hash="test-only",
                         display_name="预演用户")
        self.role = Role(id=uuid4(), tenant_id=self.tenant.id, key=f"sim-{uuid4().hex[:10]}", name="只读角色")
        self.permission = Permission(id=uuid4(), code=f"simulation.read.{uuid4().hex[:8]}",
                                     resource_type="document", scope="read")
        self.db.add_all([self.tenant, self.user, self.role, self.permission])
        self.db.flush()
        self.membership = TenantMembership(tenant_id=self.tenant.id, user_id=self.user.id, status="active")
        self.db.add(self.membership)
        self.db.flush()
        self.db.add_all([
            RoleBinding(membership_id=self.membership.id, role_id=self.role.id),
            RolePermission(role_id=self.role.id, permission_id=self.permission.id),
        ])
        self.db.commit()
        self.body = self.make_body()

    def make_body(self, **overrides: object) -> SimpleNamespace:
        """模拟服务所需的已校验输入，不引入 API schema 的邮箱校验依赖。"""
        values = {"tenant_id": self.tenant.id, "application_id": None,
                  "permission_code": self.permission.code, "resource_id": None,
                  "include_data_scope": False}
        values.update(overrides)
        return SimpleNamespace(**values)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_matching_grant_explains_role_without_changing_live_api_shape(self) -> None:
        evaluation = evaluate_access(self.body, self.user, self.db)

        self.assertEqual(evaluation["decision"], {"allowed": True, "reason": "matching_role_grant"})
        self.assertEqual(evaluation["matching_roles"], [{
            "id": str(self.role.id), "key": self.role.key, "name": self.role.name,
            "application_id": None, "resource_id": None,
        }])
        self.assertEqual(evaluation["checks"][-1]["reason"], "not_requested")

    def test_missing_tenant_membership_is_explained_as_denial(self) -> None:
        other_user = User(email=f"other-{uuid4().hex}@example.test", password_hash="test-only",
                          display_name="无租户用户")
        self.db.add(other_user)
        self.db.commit()

        evaluation = evaluate_access(self.body, other_user, self.db)

        self.assertFalse(evaluation["decision"]["allowed"])
        self.assertEqual(evaluation["decision"]["reason"], "no_active_tenant_membership")
        self.assertEqual(evaluation["checks"][-1], {
            "check": "membership", "passed": False, "reason": "no_active_tenant_membership",
        })

    def test_missing_data_scope_still_fails_closed_and_shows_matching_grant(self) -> None:
        body = self.make_body(include_data_scope=True)

        evaluation = evaluate_access(body, self.user, self.db)

        self.assertFalse(evaluation["decision"]["allowed"])
        self.assertEqual(evaluation["decision"]["reason"], "data_scope_policy_missing")
        self.assertEqual(len(evaluation["matching_roles"]), 1)
        self.assertEqual(evaluation["checks"][-1]["check"], "data_scope")

    def test_active_group_inherits_a_role_and_disabled_group_stops_it(self) -> None:
        """用户组只把同租户角色加入授权集合；停用组立即停止继承。"""
        self.db.execute(delete(RoleBinding).where(RoleBinding.membership_id == self.membership.id))
        group = UserGroup(tenant_id=self.tenant.id, key=f"group-{uuid4().hex[:10]}", name="组授权")
        inherited_role = Role(tenant_id=self.tenant.id, key=f"inherited-{uuid4().hex[:10]}", name="组继承角色")
        self.db.add_all([group, inherited_role])
        self.db.flush()
        self.db.add_all([
            UserGroupMembership(group_id=group.id, membership_id=self.membership.id, tenant_id=self.tenant.id),
            UserGroupRole(group_id=group.id, role_id=inherited_role.id, tenant_id=self.tenant.id),
            RolePermission(role_id=inherited_role.id, permission_id=self.permission.id),
        ])
        self.db.commit()

        allowed = evaluate_access(self.body, self.user, self.db)
        self.assertTrue(allowed["decision"]["allowed"])
        self.assertEqual([role["id"] for role in allowed["matching_roles"]], [str(inherited_role.id)])

        group.status = "disabled"
        self.db.commit()
        denied = evaluate_access(self.body, self.user, self.db)
        self.assertFalse(denied["decision"]["allowed"])
        self.assertEqual(denied["decision"]["reason"], "no_matching_grant")

    def test_self_scope_preview_matches_runtime_filter_contract(self) -> None:
        self.db.add(RoleDataScope(tenant_id=self.tenant.id, role_id=self.role.id,
                                  permission_id=self.permission.id, scope_type="self", organization_ids=[]))
        self.db.commit()
        body = self.make_body(include_data_scope=True)

        evaluation = evaluate_access(body, self.user, self.db)

        self.assertTrue(evaluation["decision"]["allowed"])
        self.assertEqual(evaluation["decision"]["data_scope"]["constraints"], [{
            "kind": "owner", "field": "owner_user_id", "user_id": str(self.user.id),
            "tenant_id": str(self.tenant.id),
        }])


    def test_tenant_scope_returns_a_tenant_bound_filter(self) -> None:
        self.db.add(RoleDataScope(tenant_id=self.tenant.id, role_id=self.role.id,
                                  permission_id=self.permission.id, scope_type="tenant", organization_ids=[]))
        self.db.commit()

        evaluation = evaluate_access(self.make_body(include_data_scope=True), self.user, self.db)

        self.assertTrue(evaluation["decision"]["allowed"])
        self.assertEqual(evaluation["decision"]["data_scope"], {
            "mode": "any_of", "constraints": [{"kind": "tenant", "tenant_id": str(self.tenant.id)}],
        })

    def test_organization_tree_includes_active_descendants_only(self) -> None:
        # 组织树从成员被分配的节点展开，只允许当前租户内的有效节点进入过滤器。
        root = Organization(tenant_id=self.tenant.id, key="root", name="研发部")
        self.db.add(root)
        self.db.flush()
        child = Organization(tenant_id=self.tenant.id, parent_id=root.id, key="child", name="平台组")
        disabled = Organization(tenant_id=self.tenant.id, parent_id=root.id, key="disabled", name="停用组",
                                 status="disabled")
        unrelated = Organization(tenant_id=self.tenant.id, key="unrelated", name="财务部")
        self.db.add_all([child, disabled, unrelated])
        self.db.flush()
        self.db.add_all([
            MembershipOrganization(membership_id=self.membership.id, organization_id=root.id,
                                   tenant_id=self.tenant.id, is_primary=True),
            RoleDataScope(tenant_id=self.tenant.id, role_id=self.role.id,
                          permission_id=self.permission.id, scope_type="organization_tree", organization_ids=[]),
        ])
        self.db.commit()

        evaluation = evaluate_access(self.make_body(include_data_scope=True), self.user, self.db)

        constraint = evaluation["decision"]["data_scope"]["constraints"][0]
        self.assertEqual(constraint["kind"], "organizations")
        self.assertEqual(constraint["tenant_id"], str(self.tenant.id))
        self.assertEqual(constraint["organization_ids"], sorted([str(root.id), str(child.id)]))
        self.assertNotIn(str(disabled.id), constraint["organization_ids"])
        self.assertNotIn(str(unrelated.id), constraint["organization_ids"])

    def test_selected_organizations_filter_out_foreign_tenant_and_disabled_ids(self) -> None:
        selected = Organization(tenant_id=self.tenant.id, key="selected", name="指定部门")
        disabled = Organization(tenant_id=self.tenant.id, key="selected-disabled", name="停用部门", status="disabled")
        other_tenant = Tenant(id=uuid4(), name="其它租户", slug=f"other-{uuid4().hex[:12]}")
        self.db.add_all([selected, disabled, other_tenant])
        self.db.flush()
        foreign = Organization(tenant_id=other_tenant.id, key="foreign", name="外租户部门")
        self.db.add(foreign)
        self.db.flush()
        self.db.add(RoleDataScope(
            tenant_id=self.tenant.id, role_id=self.role.id, permission_id=self.permission.id,
            scope_type="selected_organizations",
            organization_ids=[str(selected.id), str(disabled.id), str(foreign.id)],
        ))
        self.db.commit()

        evaluation = evaluate_access(self.make_body(include_data_scope=True), self.user, self.db)

        constraint = evaluation["decision"]["data_scope"]["constraints"][0]
        self.assertEqual(constraint["organization_ids"], [str(selected.id)])
        self.assertEqual(constraint["tenant_id"], str(self.tenant.id))

    def test_permission_impact_preview_counts_active_direct_members(self) -> None:
        additional_permission = Permission(
            code=f"simulation.write.{uuid4().hex[:8]}", resource_type="document", scope="write",
        )
        self.db.add(additional_permission)
        self.db.commit()

        impact = preview_role_permissions(self.role.id, [self.permission.id, additional_permission.id], self.db)

        self.assertEqual(impact["grant_permission_codes"], [additional_permission.code])
        self.assertEqual(impact["revoke_permission_codes"], [])
        self.assertEqual(impact["bound_active_members"], 1)
        self.assertEqual(impact["potentially_affected_members"], 1)
        self.assertEqual(impact["current_permission_ids"], [str(self.permission.id)])

    def test_permission_impact_preview_marks_orphan_data_scope_for_cleanup(self) -> None:
        self.db.add(RoleDataScope(tenant_id=self.tenant.id, role_id=self.role.id,
                                  permission_id=self.permission.id, scope_type="self", organization_ids=[]))
        self.db.commit()

        impact = preview_role_permissions(self.role.id, [], self.db)

        self.assertEqual(impact["revoke_permission_codes"], [self.permission.code])
        self.assertEqual(impact["data_scopes_to_delete"], [{
            "permission_id": str(self.permission.id), "permission_code": self.permission.code,
            "scope_type": "self",
        }])

    def test_permission_impact_keeps_scope_if_resource_grant_remains(self) -> None:
        self.db.add_all([
            RolePermission(role_id=self.role.id, permission_id=self.permission.id, resource_id="document-1"),
            RoleDataScope(tenant_id=self.tenant.id, role_id=self.role.id,
                          permission_id=self.permission.id, scope_type="self", organization_ids=[]),
        ])
        self.db.commit()

        impact = preview_role_permissions(self.role.id, [], self.db)

        self.assertEqual(impact["data_scopes_to_delete"], [])

    def test_batch_permission_update_removes_orphan_scope_in_same_transaction(self) -> None:
        self.db.add(RoleDataScope(tenant_id=self.tenant.id, role_id=self.role.id,
                                  permission_id=self.permission.id, scope_type="self", organization_ids=[]))
        self.db.commit()

        result = apply_role_permissions(self.role.id, [], [self.permission.id], self.db)

        self.assertTrue(result["changed"])
        self.assertEqual(self.db.query(RolePermission).filter_by(role_id=self.role.id).count(), 0)
        self.assertEqual(self.db.query(RoleDataScope).filter_by(role_id=self.role.id).count(), 0)

    def test_batch_permission_update_preserves_scope_for_remaining_resource_grant(self) -> None:
        self.db.add_all([
            RolePermission(role_id=self.role.id, permission_id=self.permission.id, resource_id="document-1"),
            RoleDataScope(tenant_id=self.tenant.id, role_id=self.role.id,
                          permission_id=self.permission.id, scope_type="self", organization_ids=[]),
        ])
        self.db.commit()

        result = apply_role_permissions(self.role.id, [], [self.permission.id], self.db)

        self.assertTrue(result["changed"])
        self.assertEqual(self.db.query(RolePermission).filter_by(role_id=self.role.id).count(), 1)
        self.assertEqual(self.db.query(RoleDataScope).filter_by(role_id=self.role.id).count(), 1)

    def test_batch_permission_update_rejects_stale_preview_without_writing(self) -> None:
        with self.assertRaises(StaleRolePermissionPreview):
            apply_role_permissions(self.role.id, [], [], self.db)

        self.assertEqual(self.db.query(RolePermission).filter_by(role_id=self.role.id).count(), 1)


if __name__ == "__main__":
    unittest.main()
