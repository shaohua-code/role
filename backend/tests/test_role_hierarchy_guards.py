"""角色分层守卫隔离测试：P405 两类角色 + 四模板节点集与授权范围（内存 SQLite）。

覆盖：
1. 自定义平台角色可以持有授权权节点（P405 去掉 P383 锁）；
2. 应用角色可挂操作者看得见的管理面节点，看不见的码 422；
3. clone_role：自定义角色克隆保留授权权节点；
4. 预置模板：四 key；L3 恰持 L3_GRANT_NODE_CODES、应用管理员恰持 L2_GRANT_NODE_CODES、
   应用成员零管理面节点，且幂等；任命链「应用级不能任命应用管理员（403）+ 租户级可以」。
"""

import unittest
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.access_control import bind_role, clone_role, list_roles, replace_role_permissions
from app.api.v1.tenant_admin.application_roles import replace_application_role_permissions
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.schemas.access_control import RoleBindingCreate, RoleCloneRequest, RolePermissionsUpdate
from app.services.permission_kinds import (
    ROLE_SCOPE_APP,
    ROLE_SCOPE_MEMBER,
    ROLE_SCOPE_SUPER,
    ROLE_SCOPE_TENANT,
)
from app.services.role_provisioning import (
    AUTHORITY_MANAGE_CODES,
    L2_GRANT_NODE_CODES,
    L2_ROLE_KEY,
    L3_GRANT_NODE_CODES,
    L3_ROLE_KEY,
    TEMPLATE_ROLE_KEYS,
    is_custom_role,
    provision_application_platform_roles,
    provision_tenant_admin_role,
)


def _seed_permission_catalog(db: Session) -> dict[str, Permission]:
    """为模板节点全集 + 超管专属/遗留剥离节点建立目录行；IAM 管理面节点不强制数据范围。"""
    codes = sorted(
        set(L3_GRANT_NODE_CODES) | set(L2_GRANT_NODE_CODES)
        | {"button.tenants.manage", "button.permissions.manage"},
    )
    rows = []
    for code in codes:
        rows.append(Permission(
            code=code,
            catalog_namespace="platform",
            resource_type=code.split(".", 1)[0],
            scope=code.rsplit(".", 1)[-1],
            surface="management",
            requires_data_scope=False,
            kind="menu" if code.startswith("menu.") else "button",
        ))
    db.add_all(rows)
    db.flush()
    return {row.code: row for row in rows}


class RoleHierarchyGuardTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不触碰开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"biz-{uuid4().hex[:10]}")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only",
                          display_name="平台管理员", status="active")
        self.db.add_all([self.tenant, self.actor])
        self.db.flush()
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        self.catalog = _seed_permission_catalog(self.db)
        self.application = Application(tenant_id=self.tenant.id, client_id=f"client-{uuid4().hex[:8]}",
                                       name="演示应用", permission_namespace="demoapp",
                                       redirect_uris=["https://a.example.test/cb"], status="active")
        self.db.add(self.application)
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

    # ---- 公共小工具 ----

    def pid(self, code: str) -> UUID:
        return self.catalog[code].id

    def make_role(self, key: str, *, kind: str = "tenant",
                  application_id: UUID | None = None,
                  scope: str | None = None) -> Role:
        role = Role(tenant_id=self.tenant.id, application_id=application_id, kind=kind,
                    key=key, name=f"角色-{key}", status="active", scope=scope)
        self.db.add(role)
        self.db.flush()
        return role

    def grant_codes(self, role: Role, *codes: str) -> None:
        for code in codes:
            self.db.add(RolePermission(role_id=role.id, permission_id=self.pid(code)))
        self.db.flush()

    def held_codes(self, role: Role) -> set[str]:
        return set(self.db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id),
        ).all())

    def bind_user(self, user: User, role: Role) -> TenantMembership:
        """建立成员身份并绑定角色（测试夹具直写，不走 API）。"""
        membership = TenantMembership(user_id=user.id, tenant_id=self.tenant.id, status="active")
        self.db.add(membership)
        self.db.flush()
        self.db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
        self.db.flush()
        return membership

    # ---- is_custom_role 语义 ----

    def test_is_custom_role_semantics(self) -> None:
        """四个模板 key 均视为模板角色，其余 key 一律自定义；apps.admin 已删除。"""
        for key in ("platform.admin", L3_ROLE_KEY, L2_ROLE_KEY, "app.member"):
            self.assertFalse(is_custom_role(Role(key=key)), key)
        self.assertTrue(is_custom_role(Role(key="ops.manager")))
        self.assertNotIn("apps.admin", TEMPLATE_ROLE_KEYS)
        self.assertEqual(len(TEMPLATE_ROLE_KEYS), 4)

    # ---- 平台侧 replace 守卫 ----

    def test_custom_role_allows_authority_codes_on_replace(self) -> None:
        """P405：看得见就能配，自定义平台角色可以挂授权权节点。"""
        role = self.make_role("ops.manager")
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("menu.application_workspace"), self.pid("button.users.manage")],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(role.id, body, self.request, actor=self.actor, db=self.db)
        self.assertTrue(result["changed"])
        self.db.expire_all()
        self.assertEqual(self.held_codes(role), {"menu.application_workspace", "button.users.manage"})

    def test_template_role_allows_authority_codes_on_replace(self) -> None:
        """模板角色是授权者的来源：L3 key 挂授权权节点不受限。"""
        role = self.make_role(L3_ROLE_KEY)
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("button.users.manage"), self.pid("button.groups.manage")],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(role.id, body, self.request, actor=self.actor, db=self.db)
        self.assertTrue(result["changed"])
        self.db.expire_all()
        self.assertEqual(self.held_codes(role), {"button.users.manage", "button.groups.manage"})

    # ---- 租户应用侧 replace 守卫 ----

    def test_custom_application_role_allows_visible_management_codes(self) -> None:
        role = self.make_role("ops.manager", kind="application", application_id=self.application.id)
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("button.users.manage")],
            expected_current_permission_ids=[],
        )
        result = replace_application_role_permissions(
            self.application.id, role.id, body, self.request, actor=self.actor, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertIn("button.users.manage", self.held_codes(role))

    # ---- 克隆剥离 ----

    def test_clone_keeps_authority_codes_on_custom_clone(self) -> None:
        """P405：克隆自定义平台角色时保留授权权节点。"""
        source = self.make_role("ops.manager")
        self.grant_codes(source, "menu.application_workspace", "button.users.manage")
        body = RoleCloneRequest(key="ops.manager.copy", name="运维副本", copy_authorizations=True)
        result = clone_role(source.id, body, self.request, actor=self.actor, db=self.db)
        self.assertEqual(result["copied_permission_grant_count"], 2)
        self.db.expire_all()
        clone = self.db.get(Role, UUID(result["id"]))
        self.assertTrue(is_custom_role(clone))
        self.assertEqual(self.held_codes(clone), {"menu.application_workspace", "button.users.manage"})
        self.assertEqual(self.held_codes(source), {"menu.application_workspace", "button.users.manage"})

    # ---- 模板预置节点集 ----

    def test_custom_platform_role_allows_super_min_scope_on_replace(self) -> None:
        """自定义平台角色：超管范围角色可挂 super 授权下限节点（如租户写按钮）。"""
        role = self.make_role("ops.manager", scope=ROLE_SCOPE_SUPER)
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("menu.application_workspace"), self.pid("button.tenants.manage")],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(role.id, body, self.request, actor=self.actor, db=self.db)
        self.assertTrue(result["changed"])
        self.assertEqual(self.held_codes(role), {"menu.application_workspace", "button.tenants.manage"})

    def test_application_role_keeps_historical_out_of_scope_on_replace(self) -> None:
        """历史已持有的越域节点允许保留；新增其他应用业务码 422。"""
        self._add_permission("otherapp.item.read", "otherapp")
        role = self.make_role("viewer", kind="application", application_id=self.application.id)
        self.grant_codes(role, "menu.organization_workspace")
        keep_body = RolePermissionsUpdate(
            permission_ids=[self.pid("menu.organization_workspace")],
            expected_current_permission_ids=[self.pid("menu.organization_workspace")],
        )
        result = replace_role_permissions(role.id, keep_body, self.request, actor=self.actor, db=self.db)
        self.assertFalse(result["changed"])
        self.assertEqual(self.held_codes(role), {"menu.organization_workspace"})
        reject_body = RolePermissionsUpdate(
            permission_ids=[self.pid("menu.organization_workspace"), self.pid("otherapp.item.read")],
            expected_current_permission_ids=[self.pid("menu.organization_workspace")],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(role.id, reject_body, self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(self.held_codes(role), {"menu.organization_workspace"})

    def _add_permission(self, code: str, catalog_namespace: str) -> Permission:
        row = Permission(
            code=code,
            catalog_namespace=catalog_namespace,
            resource_type=code.rsplit(".", 1)[0],
            scope=code.rsplit(".", 1)[-1],
            surface="management" if catalog_namespace == "platform" else "business",
            requires_data_scope=catalog_namespace != "platform",
        )
        self.db.add(row)
        self.db.flush()
        self.catalog[code] = row
        return row

    def test_list_roles_filters_by_application_id(self) -> None:
        app_role = self.make_role("viewer", kind="application", application_id=self.application.id)
        other = Application(
            tenant_id=self.tenant.id, client_id=f"client-{uuid4().hex[:8]}",
            name="另一应用", permission_namespace="otherapp",
            redirect_uris=["https://b.example.test/cb"], status="active",
        )
        self.db.add(other)
        self.db.flush()
        other_role = self.make_role("other.viewer", kind="application", application_id=other.id)
        tenant_role = self.make_role("ops.manager", kind="tenant")
        result = list_roles(
            q=None, kind="application", tenant_id=None, application_id=self.application.id,
            status=None, actor=self.actor, db=self.db,
        )
        ids = {row["id"] for row in result["items"]}
        self.assertIn(str(app_role.id), ids)
        self.assertNotIn(str(other_role.id), ids)
        self.assertNotIn(str(tenant_role.id), ids)

    def test_provisioned_template_roles_nodes_and_scopes(self) -> None:
        """预置 (应用管理员, 应用成员) 二元组：节点集与授权范围恰为模板契约，且幂等。"""
        tenant_role = provision_tenant_admin_role(self.db, self.tenant.id)
        admin, member = provision_application_platform_roles(self.db, self.tenant.id, self.application.id)
        # 范围断言：租户级=tenant、应用管理员=app、应用成员=member。
        self.assertEqual(tenant_role.scope, ROLE_SCOPE_TENANT)
        self.assertEqual(admin.scope, ROLE_SCOPE_APP)
        self.assertEqual(member.scope, ROLE_SCOPE_MEMBER)
        # 节点集断言：模板恰持各自 GRANT_NODE_CODES；租户写按钮是超管专属。
        self.assertEqual(self.held_codes(tenant_role), set(L3_GRANT_NODE_CODES))
        self.assertNotIn("button.tenants.manage", self.held_codes(tenant_role))
        self.assertNotIn("button.permissions.manage", self.held_codes(tenant_role))
        self.assertTrue(AUTHORITY_MANAGE_CODES <= self.held_codes(tenant_role))
        self.assertEqual(self.held_codes(admin), set(L2_GRANT_NODE_CODES))
        self.assertEqual(self.held_codes(member), set())
        # 幂等：重复预置不新增授权。
        provision_tenant_admin_role(self.db, self.tenant.id)
        provision_application_platform_roles(self.db, self.tenant.id, self.application.id)
        self.db.expire_all()
        self.assertEqual(len(self.held_codes(tenant_role)), len(L3_GRANT_NODE_CODES))
        self.assertEqual(len(self.held_codes(admin)), len(L2_GRANT_NODE_CODES))
        self.assertEqual(self.held_codes(member), set())

    def test_provision_tenant_admin_strips_legacy_nodes(self) -> None:
        """G32：存量 L3 上的遗留节点 button.permissions.manage 在再次预置时被剥离。"""
        tenant_role = provision_tenant_admin_role(self.db, self.tenant.id)
        self.db.add(RolePermission(role_id=tenant_role.id, permission_id=self.pid("button.permissions.manage")))
        self.db.flush()
        self.assertIn("button.permissions.manage", self.held_codes(tenant_role))
        provision_tenant_admin_role(self.db, self.tenant.id)
        self.db.expire_all()
        self.assertNotIn("button.permissions.manage", self.held_codes(tenant_role))
        self.assertEqual(self.held_codes(tenant_role), set(L3_GRANT_NODE_CODES))

    def test_app_admin_appointment_scoped_by_tenant(self) -> None:
        """任命链（P405）：应用级不能任命应用管理员（403），租户级可以。"""
        admin_role, _member_role = provision_application_platform_roles(
            self.db, self.tenant.id, self.application.id,
        )
        l2_user = User(email=f"l2-{uuid4().hex}@example.test", password_hash="x",
                       display_name="L2", status="active")
        l3_user = User(email=f"l3-{uuid4().hex}@example.test", password_hash="x",
                       display_name="L3", status="active")
        target = User(email=f"t-{uuid4().hex}@example.test", password_hash="x",
                      display_name="目标", status="active")
        self.db.add_all([l2_user, l3_user, target])
        self.db.flush()
        l3_role = provision_tenant_admin_role(self.db, self.tenant.id)
        # L2：绑定钉住应用的 app.admin（应用级操作者）。
        self.bind_user(l2_user, admin_role)
        # L3：绑定租户管理员（租户级操作者）。
        self.bind_user(l3_user, l3_role)
        target_membership = self.bind_user(target, admin_role)
        body = RoleBindingCreate(tenant_id=self.tenant.id, user_id=target.id, role_id=admin_role.id)
        # 应用级不能向上任命应用管理员。
        with self.assertRaises(HTTPException) as ctx:
            bind_role(body, self.request, l2_user, self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("任命应用管理员需要租户级及以上范围", str(ctx.exception.detail))
        # 租户级可以任命应用管理员。
        bind_role(body, self.request, l3_user, self.db)
        self.assertIsNotNone(self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.membership_id == target_membership.id,
            RoleBinding.role_id == admin_role.id,
        )))

    def test_list_roles_returns_paged_wrapper(self) -> None:
        """G29：角色列表带 total，limit 截断当前页而不是静默丢弃。"""
        self.make_role("ops.one", kind="tenant")
        self.make_role("ops.two", kind="tenant")
        result = list_roles(
            q=None, kind="tenant", tenant_id=self.tenant.id, application_id=None,
            status=None, limit=1, offset=0, actor=self.actor, db=self.db,
        )
        self.assertEqual(result["limit"], 1)
        self.assertEqual(result["offset"], 0)
        self.assertGreaterEqual(result["total"], 2)
        self.assertEqual(len(result["items"]), 1)


if __name__ == "__main__":
    unittest.main()
