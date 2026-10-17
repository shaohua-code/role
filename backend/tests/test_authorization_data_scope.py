"""PostgreSQL integration coverage for fail-closed, tenant-safe data scopes.

Each case uses random identities inside a database savepoint and rolls the entire
outer transaction back, so it can run against the developer database without
leaving users, permissions, roles, or audit records behind.
"""

import unittest
from uuid import uuid4

from sqlalchemy.orm import Session

from app.api.v1.authorization import check_access
from app.core.config import get_settings
from app.db.session import get_engine
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.models.organization import MembershipOrganization, Organization, RoleDataScope
from app.schemas.access_control import AuthorizationCheck


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL integration tests")
class DataScopeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        # Savepoint lets Session rollback cleanly while the test owns the outer transaction.
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.tenant_id, self.other_tenant_id = uuid4(), uuid4()
        self.user_id, self.membership_id = uuid4(), uuid4()
        self.role_id, self.permission_id = uuid4(), uuid4()
        self.permission_code = f"test.scope.{uuid4().hex}"
        self.parent_id, self.child_id, self.sibling_id = uuid4(), uuid4(), uuid4()
        self.user = User(id=self.user_id, email=f"scope-{uuid4().hex}@example.test",
                         password_hash="test-only", display_name="Scope Test")
        self.tenant = Tenant(id=self.tenant_id, name="Scope Test", slug=f"scope-{uuid4().hex[:20]}")
        self.other_tenant = Tenant(id=self.other_tenant_id, name="Other Scope Test",
                                   slug=f"other-{uuid4().hex[:20]}")
        self.membership = TenantMembership(id=self.membership_id, tenant_id=self.tenant_id,
                                            user_id=self.user_id, status="active")
        self.role = Role(id=self.role_id, tenant_id=self.tenant_id, key=f"test-{uuid4().hex[:12]}",
                         name="Scope Test", status="active")
        self.permission = Permission(id=self.permission_id, code=self.permission_code,
                                     resource_type="test", scope="read")
        # Flush dependency roots first: these objects use scalar foreign keys and intentionally
        # do not hold ORM relationships that would otherwise establish unit-of-work ordering.
        self.db.add_all([self.user, self.tenant, self.other_tenant])
        self.db.flush()
        self.db.add_all([self.membership, self.role, self.permission])
        self.db.flush()
        self.db.add_all([
            RoleBinding(membership_id=self.membership_id, role_id=self.role_id),
            RolePermission(role_id=self.role_id, permission_id=self.permission_id),
        ])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def decide(self) -> dict:
        return check_access(AuthorizationCheck(tenant_id=self.tenant_id,
                                               permission_code=self.permission_code,
                                               include_data_scope=True), self.user, self.db)

    def test_self_scope_is_bound_to_tenant_and_global_user(self) -> None:
        self.db.add(RoleDataScope(tenant_id=self.tenant_id, role_id=self.role_id,
                                  permission_id=self.permission_id, scope_type="self", organization_ids=[]))
        self.db.flush()
        result = self.decide()
        self.assertTrue(result["allowed"])
        self.assertEqual(result["data_scope"]["constraints"], [{
            "kind": "owner", "field": "owner_user_id", "user_id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
        }])

    def test_organization_tree_contains_descendants_but_not_siblings(self) -> None:
        parent = Organization(id=self.parent_id, tenant_id=self.tenant_id, key="parent", name="Parent")
        child = Organization(id=self.child_id, tenant_id=self.tenant_id, parent_id=self.parent_id,
                             key="child", name="Child")
        sibling = Organization(id=self.sibling_id, tenant_id=self.tenant_id, key="sibling", name="Sibling")
        self.db.add_all([parent, child, sibling])
        self.db.flush()
        self.db.add_all([
            MembershipOrganization(membership_id=self.membership_id, tenant_id=self.tenant_id,
                                  organization_id=self.parent_id, is_primary=True),
            RoleDataScope(tenant_id=self.tenant_id, role_id=self.role_id,
                          permission_id=self.permission_id, scope_type="organization_tree", organization_ids=[]),
        ])
        self.db.flush()
        result = self.decide()
        self.assertTrue(result["allowed"])
        constraint = result["data_scope"]["constraints"][0]
        self.assertEqual(constraint["kind"], "organizations")
        self.assertEqual(set(constraint["organization_ids"]), {str(self.parent_id), str(self.child_id)})
        self.assertNotIn(str(self.sibling_id), constraint["organization_ids"])
        self.assertEqual(constraint["tenant_id"], str(self.tenant_id))

    def test_missing_policy_denies_even_when_role_grant_matches(self) -> None:
        result = self.decide()
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "data_scope_policy_missing")

    def test_tenant_scope_is_limited_to_verified_membership_tenant(self) -> None:
        self.db.add(RoleDataScope(tenant_id=self.tenant_id, role_id=self.role_id,
                                  permission_id=self.permission_id, scope_type="tenant", organization_ids=[]))
        self.db.flush()
        result = self.decide()
        self.assertTrue(result["allowed"])
        self.assertEqual(result["data_scope"]["constraints"], [
            {"kind": "tenant", "tenant_id": str(self.tenant_id)},
        ])
        self.assertNotEqual(result["data_scope"]["constraints"][0]["tenant_id"], str(self.other_tenant_id))

    def test_selected_organizations_excludes_foreign_tenant_ids(self) -> None:
        allowed_org = Organization(tenant_id=self.tenant_id, key="allowed", name="Allowed")
        foreign_org = Organization(tenant_id=self.other_tenant_id, key="foreign", name="Foreign")
        self.db.add_all([allowed_org, foreign_org])
        self.db.flush()
        # Simulate legacy/corrupt policy data: runtime resolution must still re-check tenant ownership.
        self.db.add(RoleDataScope(
            tenant_id=self.tenant_id, role_id=self.role_id, permission_id=self.permission_id,
            scope_type="selected_organizations",
            organization_ids=[str(allowed_org.id), str(foreign_org.id)],
        ))
        self.db.flush()
        result = self.decide()
        self.assertTrue(result["allowed"])
        constraint = result["data_scope"]["constraints"][0]
        self.assertEqual(constraint["tenant_id"], str(self.tenant_id))
        self.assertEqual(constraint["organization_ids"], [str(allowed_org.id)])


if __name__ == "__main__":
    unittest.main()
