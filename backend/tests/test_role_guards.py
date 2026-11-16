"""角色门禁：ensure_roles / list_actor_roles / /auth/me 契约。"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Application, Role, RoleBinding, Tenant, TenantMembership, User
from app.models.authorization import Permission, RolePermission
from app.services.rbac_guards import ActorVisibility, PermissionEnforcer
from app.services.role_provisioning import L1_ROLE_KEY, L2_ROLE_KEY, L3_ROLE_KEY
from tests.greenfield_fixture import make_platform_admin_binding


class RoleGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(id=uuid4(), name="业务租户", slug=f"t-{uuid4().hex[:12]}")
        self.application = Application(
            id=uuid4(), tenant_id=self.tenant.id, client_id=f"app-{uuid4().hex[:12]}",
            name="业务应用", redirect_uris=["https://a.example.test/cb"],
            post_logout_redirect_uris=[], trusted=False, status="active",
        )
        self.l2_user = User(id=uuid4(), email=f"l2-{uuid4().hex}@example.test",
                            password_hash="x", display_name="L2")
        self.l3_user = User(id=uuid4(), email=f"l3-{uuid4().hex}@example.test",
                            password_hash="x", display_name="L3")
        self.l4_user = User(id=uuid4(), email=f"l4-{uuid4().hex}@example.test",
                            password_hash="x", display_name="L4")
        self.l1_user = User(id=uuid4(), email=f"l1-{uuid4().hex}@example.test",
                            password_hash="x", display_name="L1")
        self.db.add_all([self.tenant, self.application, self.l1_user, self.l2_user,
                         self.l3_user, self.l4_user])
        self.db.flush()
        make_platform_admin_binding(self.db, self.l1_user)

        self.l3_membership = TenantMembership(
            id=uuid4(), user_id=self.l3_user.id, tenant_id=self.tenant.id, status="active",
        )
        self.l2_membership = TenantMembership(
            id=uuid4(), user_id=self.l2_user.id, tenant_id=self.tenant.id, status="active",
        )
        self.l4_membership = TenantMembership(
            id=uuid4(), user_id=self.l4_user.id, tenant_id=self.tenant.id, status="active",
        )
        self.db.add_all([self.l3_membership, self.l2_membership, self.l4_membership])
        self.db.flush()

        self.l3_role = Role(
            id=uuid4(), tenant_id=self.tenant.id, application_id=None, kind="tenant",
            key=L3_ROLE_KEY, name="租户管理员", status="active",
        )
        self.l2_role = Role(
            id=uuid4(), tenant_id=self.tenant.id, application_id=self.application.id,
            kind="application", key=L2_ROLE_KEY, name="应用管理员", status="active",
        )
        self.l4_role = Role(
            id=uuid4(), tenant_id=self.tenant.id, application_id=self.application.id,
            kind="application", key="app.member", name="成员", status="active",
        )
        self.db.add_all([self.l3_role, self.l2_role, self.l4_role])
        self.db.flush()
        self.db.add_all([
            RoleBinding(membership_id=self.l3_membership.id, role_id=self.l3_role.id),
            RoleBinding(membership_id=self.l2_membership.id, role_id=self.l2_role.id),
            RoleBinding(membership_id=self.l4_membership.id, role_id=self.l4_role.id),
        ])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_l1_passes_any_ensure_roles(self) -> None:
        PermissionEnforcer.ensure_roles(self.l1_user, self.db, [L3_ROLE_KEY], tenant_id=self.tenant.id)

    def test_l3_has_tenant_org_admin(self) -> None:
        self.assertTrue(PermissionEnforcer.user_has_any_role(
            self.l3_user, self.db, [L3_ROLE_KEY], tenant_id=self.tenant.id,
        ))
        PermissionEnforcer.ensure_roles(self.l3_user, self.db, [L3_ROLE_KEY], tenant_id=self.tenant.id)

    def test_l2_scoped_to_application(self) -> None:
        self.assertTrue(PermissionEnforcer.user_has_any_role(
            self.l2_user, self.db, [L2_ROLE_KEY],
            tenant_id=self.tenant.id, application_id=self.application.id,
        ))
        other_app = uuid4()
        self.assertFalse(PermissionEnforcer.user_has_any_role(
            self.l2_user, self.db, [L2_ROLE_KEY],
            tenant_id=self.tenant.id, application_id=other_app,
        ))

    def test_l4_denied_management_roles(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            PermissionEnforcer.ensure_roles(
                self.l4_user, self.db, [L3_ROLE_KEY, L2_ROLE_KEY],
                tenant_id=self.tenant.id, allow_platform_admin=True,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_list_actor_roles_and_capabilities_include_roles(self) -> None:
        roles = ActorVisibility.list_actor_roles(self.l2_user, self.db)
        self.assertTrue(any(item["key"] == L2_ROLE_KEY for item in roles))
        caps = ActorVisibility.list_management_capabilities(self.l2_user, self.db)
        self.assertIn("roles", caps)
        self.assertTrue(any(item["key"] == L2_ROLE_KEY for item in caps["roles"]))

    # ── 敏感写节点统一清单（按钮节点全集）──────────────────────────────────

    def test_sensitive_node_codes_derive_from_button_catalog(self) -> None:
        """统一清单 = BUTTON_CODES 全集；别名入口与函数入口已由节点清单取代。"""
        from app.services.permission_kinds import BUTTON_CODES
        from app.services.rbac_guards import SENSITIVE_NODE_CODES

        expected = frozenset(BUTTON_CODES)
        self.assertEqual(SENSITIVE_NODE_CODES, expected)
        # 三个关键敏感节点必须被覆盖（建租户/建人/轮换密钥均为写类按钮）。
        for code in ("button.users.manage", "button.tenants.manage", "button.apps.secret"):
            self.assertIn(code, SENSITIVE_NODE_CODES)

    def test_ensure_codes_node_gate(self) -> None:
        """节点判权：持对应菜单/按钮节点放行；无节点 403；模板回退已删除。"""
        permission = Permission(
            id=uuid4(), code="menu.groups", catalog_namespace="platform",
            resource_type="menu", scope="read", surface="management",
            requires_data_scope=False, kind="menu",
        )
        self.db.add_all([permission, RolePermission(
            role_id=self.l3_role.id, permission_id=permission.id,
        )])
        self.db.commit()
        # 持节点：放行。
        PermissionEnforcer.ensure_codes(self.l3_user, self.db, "menu.groups", tenant_id=self.tenant.id)
        # 无节点：403（不再有 role_keys 回退）。
        with self.assertRaises(HTTPException) as ctx:
            PermissionEnforcer.ensure_codes(self.l3_user, self.db, "button.groups.manage", tenant_id=self.tenant.id)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
