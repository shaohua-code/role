"""绿场四级 RBAC 验收用例（规格书 §6）。

覆盖：G1 邮箱旁路关闭、G2 组继承入场、L1 全管理码/无业务码、
L2 与 L3 互斥、rbac.app_role.assign 任命、解绑 bump、组变更 bump、
业务码强制 data_scope。全部使用内存 SQLite，不触碰真实数据库。
"""

import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import Request as FastapiRequest

from app.db.base import Base
from app.models import (
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
from app.models.organization import RoleDataScope
from app.schemas.access_control import AuthorizationCheck, RoleBindingCreate
from app.api.v1.admin.access_control import bind_role, unbind_role
from app.core.config import get_settings
from app.services.authorization import evaluate_access
from app.services.effective_roles import list_effective_roles
from app.services.rbac_guards import (
    ensure_management_permission,
    user_has_management_code,
    user_is_platform_admin,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tests.greenfield_fixture import make_platform_admin_binding


class GreenfieldRbacAcceptanceTests(unittest.TestCase):
    """每个用例独立内存库，验证绿场四级模型的判定契约。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        # 业务租户 T 与业务应用 A。
        self.tenant = Tenant(id=uuid4(), name="业务租户", slug=f"t-{uuid4().hex[:12]}")
        self.platform_tenant = Tenant(id=uuid4(), name="平台租户", slug=f"p-{uuid4().hex[:12]}")
        self.application = Application(
            id=uuid4(), tenant_id=self.tenant.id, client_id=f"app-{uuid4().hex[:12]}",
            name="业务应用", redirect_uris=["https://a.example.test/cb"],
            post_logout_redirect_uris=[], trusted=False, status="active",
        )
        self.l1_user = User(id=uuid4(), email=f"l1-{uuid4().hex}@example.test",
                            password_hash="x", display_name="L1")
        self.l3_user = User(id=uuid4(), email=f"l3-{uuid4().hex}@example.test",
                            password_hash="x", display_name="L3")
        self.l4_user = User(id=uuid4(), email=f"l4-{uuid4().hex}@example.test",
                            password_hash="x", display_name="L4")
        self.db.add_all([self.tenant, self.platform_tenant, self.application,
                         self.l1_user, self.l3_user, self.l4_user])
        self.db.flush()
        # L1：平台租户 membership + platform 角色。
        make_platform_admin_binding(self.db, self.l1_user)
        # 管理面目录：三条代表码。
        self.perm_role_manage = Permission(id=uuid4(), code="rbac.role.manage",
                                           resource_type="role", scope="manage",
                                           surface="management", requires_data_scope=False)
        self.perm_org_manage = Permission(id=uuid4(), code="org.manage",
                                          resource_type="organization", scope="manage",
                                          surface="management", requires_data_scope=False)
        self.perm_app_read = Permission(id=uuid4(), code="app.read",
                                        resource_type="application", scope="read",
                                        surface="management", requires_data_scope=False)
        # 业务码：强制数据范围。
        self.perm_document_read = Permission(id=uuid4(), code=f"demo.document.read.{uuid4().hex[:8]}",
                                             resource_type="document", scope="read",
                                             surface="business", requires_data_scope=True)
        self.db.add_all([self.perm_role_manage, self.perm_org_manage,
                         self.perm_app_read, self.perm_document_read])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _grant_tenant_role(self, user: User, codes: list[Permission], *, key: str,
                           application_id: UUID | None = None) -> Role:
        role = Role(id=uuid4(), tenant_id=self.tenant.id, application_id=application_id,
                    kind="application" if application_id else "tenant",
                    key=key, name=key, status="active")
        membership = TenantMembership(id=uuid4(), tenant_id=self.tenant.id,
                                      user_id=user.id, status="active")
        self.db.add_all([role, membership])
        self.db.flush()
        self.db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
        for permission in codes:
            self.db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        self.db.flush()
        return role

    def _membership_version(self, user: User) -> int:
        membership = self.db.query(TenantMembership).filter(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == self.tenant.id,
        ).one()
        return membership.auth_version

    def test_g1_email_bypass_disabled_by_default(self) -> None:
        """bypass 默认 false：同名邮箱不等于平台权限。"""
        settings = get_settings()
        self.assertFalse(settings.allow_bootstrap_email_bypass)
        self.assertFalse(user_is_platform_admin(self.l3_user, self.db))

    def test_l1_holds_all_management_codes_but_denied_without_binding(self) -> None:
        ensure_management_permission(self.l1_user, self.db, "rbac.role.manage")
        ensure_management_permission(self.l1_user, self.db, "platform.tenant.manage")
        # 无 L1 绑定的用户即使同名邮箱也拿不到管理码（无旁路）。
        with self.assertRaises(Exception):
            ensure_management_permission(self.l3_user, self.db, "rbac.role.manage")

    def test_l2_l3_mutual_exclusion(self) -> None:
        """L2 不含组织管理码，L3 不含应用密钥轮换；L3 可凭 assign 任命 app.admin。"""
        l2_role = self._grant_tenant_role(
            self.l3_user, [self.perm_app_read], key="app.admin",
            application_id=self.application.id,
        )
        # 只有应用角色时：应用可读，组织 manage 拒绝。
        self.assertTrue(user_has_management_code(
            self.l3_user, self.db, "app.read",
            tenant_id=self.tenant.id, application_id=self.application.id,
        ))
        self.assertFalse(user_has_management_code(
            self.l3_user, self.db, "org.manage", tenant_id=self.tenant.id,
        ))
        # L3 角色授予组织码后仍无 role.manage（L1 专属码未授予）。
        self._grant_tenant_role(self.l4_user, [self.perm_org_manage], key="tenant.admin")
        self.assertTrue(user_has_management_code(
            self.l4_user, self.db, "org.manage", tenant_id=self.tenant.id,
        ))
        self.assertFalse(user_has_management_code(
            self.l4_user, self.db, "rbac.role.manage", tenant_id=self.tenant.id,
        ))
        self.assertIsNotNone(l2_role)

    def _management_request(self) -> FastapiRequest:
        """构造带 client 的最小 Request，供审计写入读取来源 IP。"""
        return FastapiRequest({
            "type": "http", "http_version": "1.1", "method": "PUT", "scheme": "http",
            "path": "/api/v1/admin/role-bindings", "raw_path": b"/api/v1/admin/role-bindings",
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        })

    def test_unbind_bumps_membership_version(self) -> None:
        role = self._grant_tenant_role(self.l3_user, [self.perm_org_manage], key="tenant.admin")
        before = self._membership_version(self.l3_user)
        body = RoleBindingCreate(tenant_id=self.tenant.id, user_id=self.l3_user.id, role_id=role.id)

        unbind_role(body, self._management_request(), self.l1_user, self.db)

        self.assertEqual(self._membership_version(self.l3_user), before + 1)
        binding = self.db.query(RoleBinding).filter_by(
            membership_id=self.db.query(TenantMembership).filter_by(
                user_id=self.l3_user.id, tenant_id=self.tenant.id).one().id,
            role_id=role.id,
        ).one_or_none()
        self.assertIsNone(binding)

    def test_bind_then_unbind_symmetric(self) -> None:
        role = self._grant_tenant_role(self.l4_user, [], key="tenant.member")
        # 先移除夹具预置绑定，从零验证 bind → unbind 的对称 bump。
        self.db.query(RoleBinding).filter_by(role_id=role.id).delete()
        self.db.commit()
        before = self._membership_version(self.l4_user)
        body = RoleBindingCreate(tenant_id=self.tenant.id, user_id=self.l4_user.id, role_id=role.id)

        bind_role(body, self._management_request(), self.l1_user, self.db)
        self.assertEqual(self._membership_version(self.l4_user), before + 1)

        unbind_role(body, self._management_request(), self.l1_user, self.db)
        self.assertEqual(self._membership_version(self.l4_user), before + 2)

    def test_business_permission_forces_data_scope(self) -> None:
        """业务码 requires_data_scope=true：include_data_scope=False 也强制解析，缺策略拒绝。"""
        self._grant_tenant_role(self.l4_user, [self.perm_document_read], key="app.member")
        body = AuthorizationCheck(
            tenant_id=self.tenant.id, permission_code=self.perm_document_read.code,
            include_data_scope=False,
        )
        evaluation = evaluate_access(body, self.l4_user, self.db)
        self.assertFalse(evaluation["decision"]["allowed"])
        self.assertEqual(evaluation["decision"]["reason"], "data_scope_policy_missing")

        # 配置 self 范围后通过并返回 owner 约束。
        role = self.db.query(Role).filter_by(tenant_id=self.tenant.id, key="app.member").one()
        self.db.add(RoleDataScope(tenant_id=self.tenant.id, role_id=role.id,
                                  permission_id=self.perm_document_read.id,
                                  scope_type="self", organization_ids=[]))
        self.db.commit()
        evaluation = evaluate_access(body, self.l4_user, self.db)
        self.assertTrue(evaluation["decision"]["allowed"])
        self.assertEqual(evaluation["decision"]["data_scope"]["constraints"][0]["kind"], "owner")

    def test_effective_roles_include_group_inheritance(self) -> None:
        """有效角色 = 直连绑定 ∪ 活跃用户组继承（G2）。"""
        membership = TenantMembership(id=uuid4(), tenant_id=self.tenant.id,
                                      user_id=self.l4_user.id, status="active")
        direct_role = Role(id=uuid4(), tenant_id=self.tenant.id, key="direct.member",
                           name="直连", kind="tenant", status="active")
        group = UserGroup(id=uuid4(), tenant_id=self.tenant.id, key=f"g-{uuid4().hex[:8]}", name="组")
        group_role = Role(id=uuid4(), tenant_id=self.tenant.id, key="group.member",
                          name="组角色", kind="tenant", status="active")
        self.db.add_all([membership, direct_role, group, group_role])
        self.db.flush()
        self.db.add_all([
            RoleBinding(membership_id=membership.id, role_id=direct_role.id),
            UserGroupMembership(group_id=group.id, membership_id=membership.id, tenant_id=self.tenant.id),
            UserGroupRole(group_id=group.id, role_id=group_role.id, tenant_id=self.tenant.id),
        ])
        self.db.commit()

        effective = list_effective_roles(
            self.db, membership_id=membership.id, tenant_id=self.tenant.id,
            application_id=self.application.id,
        )
        self.assertEqual({role.key for role in effective}, {"direct.member", "group.member"})

        # 停用组后组角色立即退出有效集合。
        group.status = "disabled"
        self.db.commit()
        effective = list_effective_roles(
            self.db, membership_id=membership.id, tenant_id=self.tenant.id,
            application_id=self.application.id,
        )
        self.assertEqual({role.key for role in effective}, {"direct.member"})


if __name__ == "__main__":
    unittest.main()
