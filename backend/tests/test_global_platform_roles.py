"""平台角色全局化语义的隔离验证（内存 SQLite）。

覆盖 spec「平台角色全局化」的关键行为：
1. 一个全局 tenant.admin 在用户绑定的多个租户上下文中同时生效（一角色多租户）；
2. 应用角色可跨租户任命：L1 绑定租户 Y 成员成功，且按角色所属应用生效；
3. 非超管 create_user / bind_role 触碰平台管理租户 → 422（平台租户隔离防呆）；
4. 非超管 capabilities.tenants 排除平台管理租户（租户工作台不混入平台租户）。
"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.access_control import bind_role
from app.api.v1.admin.users import create_user
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding
from app.models.identity import Tenant, TenantMembership, User
from app.schemas.access_control import RoleBindingCreate
from app.schemas.auth import AdminUserCreate
from app.services.effective_roles import EffectiveRoleResolver
from app.services.rbac_guards import ActorVisibility
from app.services.role_provisioning import (
    L2_GRANT_NODE_CODES,
    L3_GRANT_NODE_CODES,
    RoleProvisioning,
)
from tests.greenfield_fixture import (
    ensure_platform_tenant,
    make_platform_admin_binding,
)


class GlobalPlatformRoleTests(unittest.TestCase):
    """每个用例在内存 SQLite 中运行，不改动开发库。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        # 平台角色全局宿主：slug=platform 的平台管理租户必须先就位。
        self.platform_tenant = ensure_platform_tenant(self.db)
        self.tenant_x = Tenant(name="租户X", slug=f"x-{uuid4().hex[:10]}")
        self.tenant_y = Tenant(name="租户Y", slug=f"y-{uuid4().hex[:10]}")
        self.db.add_all([self.tenant_x, self.tenant_y])
        self.db.flush()
        # 管理面节点目录：供全局 L3 模板 / L2 模板挂码（模板供给要求目录码存在）。
        for code in sorted(set(L3_GRANT_NODE_CODES) | set(L2_GRANT_NODE_CODES)):
            self.db.add(Permission(
                code=code, catalog_namespace="platform",
                resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
                surface="management", requires_data_scope=False,
                kind="menu" if code.startswith("menu.") else "button",
            ))
        self.db.flush()
        # 全局唯一 tenant.admin：tenant_id 参数已废弃，一律宿主平台管理租户。
        self.l3_role = RoleProvisioning.provision_tenant_admin_role(self.db)
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "POST", "path": "/api/v1",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ── 夹具辅助 ────────────────────────────────────────────────────────────

    def _user(self, prefix: str) -> User:
        user = User(
            email=f"{prefix}-{uuid4().hex[:8]}@example.com",
            password_hash="test-only",
            display_name=prefix,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def _membership(self, user: User, tenant: Tenant) -> TenantMembership:
        membership = TenantMembership(
            user_id=user.id, tenant_id=tenant.id, status="active",
        )
        self.db.add(membership)
        self.db.flush()
        return membership

    def _application(self, tenant: Tenant, namespace: str) -> Application:
        application = Application(
            tenant_id=tenant.id, client_id=f"app-{uuid4().hex[:8]}",
            name=f"应用-{namespace}", permission_namespace=namespace,
            redirect_uris=["https://example.com/cb"], status="active",
        )
        self.db.add(application)
        self.db.flush()
        return application

    # ── 一角色多租户生效 ────────────────────────────────────────────────────

    def test_global_role_effective_in_every_bound_tenant(self) -> None:
        """用户绑租户 X、Y + 全局 tenant.admin → 在 X/Y 上下文均命中同一角色。

        绑定表达「用户在租户 Y 的成员身份上持角色 R」：同一全局角色分别绑定到
        两个成员身份即可，两个上下文命中的是同一行角色（不再需要每租户副本）。
        """
        user = self._user("multi")
        membership_x = self._membership(user, self.tenant_x)
        membership_y = self._membership(user, self.tenant_y)
        self.db.add_all([
            RoleBinding(membership_id=membership_x.id, role_id=self.l3_role.id),
            RoleBinding(membership_id=membership_y.id, role_id=self.l3_role.id),
        ])
        self.db.commit()
        for membership, tenant in (
            (membership_x, self.tenant_x), (membership_y, self.tenant_y),
        ):
            # 有效角色：两个租户上下文都命中全局 tenant.admin（不再按角色租户过滤）。
            roles = EffectiveRoleResolver.list_effective_roles(
                self.db, membership_id=membership.id, tenant_id=tenant.id,
            )
            self.assertIn(self.l3_role.id, {role.id for role in roles})
            # OIDC 授权口径：authorized_role_ids_statement 同样跨租户命中。
            authorized = set(self.db.scalars(
                EffectiveRoleResolver.authorized_role_ids_statement(membership.id, tenant.id),
            ).all())
            self.assertIn(self.l3_role.id, authorized)
        # 应用上下文同样生效：平台类角色在 (tenant, application) 维度全局命中。
        application = self._application(self.tenant_x, "appx")
        roles = EffectiveRoleResolver.list_effective_roles(
            self.db, membership_id=membership_x.id, tenant_id=self.tenant_x.id,
            application_id=application.id,
        )
        self.assertIn(self.l3_role.id, {role.id for role in roles})

    # ── 应用角色跨租户任命 ──────────────────────────────────────────────────

    def test_application_role_cross_tenant_binding_allowed(self) -> None:
        """跨租户任命：钉在租户 X 应用的应用角色可由 L1 绑定到租户 Y 成员。

        生效语义：应用角色按其所属应用生效（application_id 精确匹配）——
        在租户 Y 成员身份的应用上下文中命中该角色；非应用上下文不出现，
        也不会泄漏到角色所属应用之外。
        """
        application = self._application(self.tenant_x, "appx")
        app_role = RoleProvisioning.provision_application_admin_role(
            self.db, self.tenant_x.id, application.id,
        )
        target = self._user("target")
        membership_y = self._membership(target, self.tenant_y)
        actor = self._user("l1")
        make_platform_admin_binding(self.db, actor)
        self.db.commit()
        body = RoleBindingCreate(
            tenant_id=self.tenant_y.id, user_id=target.id, role_id=app_role.id,
        )
        # 跨租户任命：不再 422，绑定直接成功。
        bind_role(body, self.request, actor=actor, db=self.db)
        self.db.commit()
        # 绑定落库：租户 Y 成员身份上存在该应用角色的直连绑定。
        binding_exists = self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.membership_id == membership_y.id,
            RoleBinding.role_id == app_role.id,
        ))
        self.assertIsNotNone(binding_exists)
        # 应用上下文生效：租户 Y 成员在该应用上下文命中该应用角色（含自动补齐的 L4）。
        app_roles = EffectiveRoleResolver.list_effective_roles(
            self.db, membership_id=membership_y.id, tenant_id=self.tenant_y.id,
            application_id=application.id,
        )
        self.assertIn(app_role.id, {role.id for role in app_roles})
        # 非应用上下文不出现：租户级上下文（application_id=None）不含应用角色。
        tenant_roles = EffectiveRoleResolver.list_effective_roles(
            self.db, membership_id=membership_y.id, tenant_id=self.tenant_y.id,
        )
        self.assertNotIn(app_role.id, {role.id for role in tenant_roles})

    # ── 平台租户隔离防呆 ───────────────────────────────────────────────────

    def _l3_operator_with_platform_membership(self) -> User:
        """非超管 L3：持有全局 tenant.admin，同时在平台租户与业务租户有成员身份。

        平台租户成员身份使其通过 ensure_tenant_in_actor_scope 的范围校验，
        从而能触达「非超管 + 平台租户」的 422 防呆分支（而非 403 范围不足）。
        """
        operator = self._user("l3")
        membership_x = self._membership(operator, self.tenant_x)
        self._membership(operator, self.platform_tenant)
        self.db.add(RoleBinding(membership_id=membership_x.id, role_id=self.l3_role.id))
        self.db.flush()
        return operator

    def test_non_superadmin_create_user_into_platform_tenant_rejected(self) -> None:
        """非超管 create_user 把成员落进平台管理租户 → 422。"""
        operator = self._l3_operator_with_platform_membership()
        body = AdminUserCreate(
            tenant_ids=[self.platform_tenant.id],
            email=f"newbie-{uuid4().hex[:8]}@example.com",
            display_name="新人",
            initial_password="Passw0rd!12345",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_user(body, self.request, actor=operator, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台管理租户为系统保留租户", str(ctx.exception.detail))

    def test_non_superadmin_bind_role_to_platform_tenant_member_rejected(self) -> None:
        """非超管 bind_role 向平台管理租户成员绑定角色 → 422。"""
        operator = self._l3_operator_with_platform_membership()
        target = self._user("platform-member")
        self._membership(target, self.platform_tenant)
        custom_role = Role(
            tenant_id=self.platform_tenant.id, application_id=None, kind="tenant",
            key="custom.platform.ops", name="平台自定义", status="active",
        )
        self.db.add(custom_role)
        self.db.commit()
        body = RoleBindingCreate(
            tenant_id=self.platform_tenant.id, user_id=target.id, role_id=custom_role.id,
        )
        with self.assertRaises(HTTPException) as ctx:
            bind_role(body, self.request, actor=operator, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台管理租户为系统保留租户", str(ctx.exception.detail))

    # ── capabilities 平台租户隔离 ───────────────────────────────────────────

    def test_capabilities_exclude_platform_tenant_for_non_superadmin(self) -> None:
        """非超管 L3 的 capabilities.tenants 不含平台管理租户（业务租户正常收录）。"""
        operator = self._l3_operator_with_platform_membership()
        self.db.commit()
        payload = ActorVisibility.list_management_capabilities(operator, self.db)
        self.assertFalse(payload["platform_admin"])
        self.assertEqual(payload["scope"], "tenant")
        tenant_ids = {entry["tenant_id"] for entry in payload["tenants"]}
        self.assertNotIn(str(self.platform_tenant.id), tenant_ids)
        self.assertIn(str(self.tenant_x.id), tenant_ids)


if __name__ == "__main__":
    unittest.main()
