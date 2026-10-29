"""角色分层守卫隔离测试：P405 两类角色 + 五级模板码数（内存 SQLite）。

覆盖：
1. 自定义平台角色可以持有授权权码（P405 去掉 P383 锁）；
2. 应用角色可挂操作者看得见的管理面码，看不见的码 422；
3. clone_role：自定义角色克隆保留授权权码；
4. 预置模板：五 key；L3 恰好 20 码、多应用管理员 16 码、L2 恰好 15 码、L4 零管理面码，且幂等。
"""

import unittest
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.access_control import clone_role, list_roles, replace_role_permissions
from app.api.v1.tenant_admin.application_roles import replace_application_role_permissions
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import Tenant, User
from app.schemas.access_control import RoleCloneRequest, RolePermissionsUpdate
from app.services.role_provisioning import (
    AUTHORITY_MANAGE_CODES,
    L2M_PERMISSION_CODES,
    L2M_ROLE_KEY,
    L2_PERMISSION_CODES,
    L2_ROLE_KEY,
    L3_PERMISSION_CODES,
    L3_ROLE_KEY,
    TEMPLATE_ROLE_KEYS,
    is_custom_role,
    provision_application_admin_role,
    provision_application_member_role,
    provision_multi_app_admin_role,
    provision_tenant_admin_role,
)


def _seed_permission_catalog(db: Session) -> dict[str, Permission]:
    """为模板码全集建立目录行；IAM 管理面码不强制数据范围。"""
    rows = []
    for code in sorted(set(L3_PERMISSION_CODES) | set(L2_PERMISSION_CODES) | {"rbac.permission.manage"}):
        rows.append(Permission(
            code=code,
            catalog_namespace="iam",
            resource_type=code.removeprefix("iam.").rsplit(".", 1)[0],
            scope=code.rsplit(".", 1)[-1],
            surface="management",
            requires_data_scope=False,
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
                  application_id: UUID | None = None) -> Role:
        role = Role(tenant_id=self.tenant.id, application_id=application_id, kind=kind,
                    key=key, name=f"角色-{key}", status="active")
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

    # ---- is_custom_role 语义 ----

    def test_is_custom_role_semantics(self) -> None:
        """五个模板 key 均视为模板角色，其余 key 一律自定义。"""
        for key in ("platform.admin", L3_ROLE_KEY, L2M_ROLE_KEY, L2_ROLE_KEY, "app.member"):
            self.assertFalse(is_custom_role(Role(key=key)), key)
        self.assertTrue(is_custom_role(Role(key="ops.manager")))
        self.assertEqual(len(TEMPLATE_ROLE_KEYS), 5)

    # ---- 平台侧 replace 守卫 ----

    def test_custom_role_allows_authority_codes_on_replace(self) -> None:
        """P405：看得见就能配，自定义平台角色可以挂授权权码。"""
        role = self.make_role("ops.manager")
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("app.read"), self.pid("org.member.manage")],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(role.id, body, self.request, actor=self.actor, db=self.db)
        self.assertTrue(result["changed"])
        self.db.expire_all()
        self.assertEqual(self.held_codes(role), {"app.read", "org.member.manage"})

    def test_template_role_allows_authority_codes_on_replace(self) -> None:
        """模板角色是授权者的来源：L3 key 挂授权权码不受限。"""
        role = self.make_role(L3_ROLE_KEY)
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("org.member.manage"), self.pid("org.group.manage")],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(role.id, body, self.request, actor=self.actor, db=self.db)
        self.assertTrue(result["changed"])
        self.db.expire_all()
        self.assertEqual(self.held_codes(role), {"org.member.manage", "org.group.manage"})

    # ---- 租户应用侧 replace 守卫 ----

    def test_custom_application_role_allows_visible_management_codes(self) -> None:
        role = self.make_role("ops.manager", kind="application", application_id=self.application.id)
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("org.member.manage")],
            expected_current_permission_ids=[],
        )
        result = replace_application_role_permissions(
            self.application.id, role.id, body, self.request, actor=self.actor, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertIn("org.member.manage", self.held_codes(role))

    # ---- 克隆剥离 ----

    def test_clone_keeps_authority_codes_on_custom_clone(self) -> None:
        """P405：克隆自定义平台角色时保留授权权码。"""
        source = self.make_role("ops.manager")
        self.grant_codes(source, "app.read", "org.member.manage")
        body = RoleCloneRequest(key="ops.manager.copy", name="运维副本", copy_authorizations=True)
        result = clone_role(source.id, body, self.request, actor=self.actor, db=self.db)
        self.assertEqual(result["copied_permission_grant_count"], 2)
        self.db.expire_all()
        clone = self.db.get(Role, UUID(result["id"]))
        self.assertTrue(is_custom_role(clone))
        self.assertEqual(self.held_codes(clone), {"app.read", "org.member.manage"})
        self.assertEqual(self.held_codes(source), {"app.read", "org.member.manage"})

    # ---- 模板预置码数 ----

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

    def test_custom_platform_role_allows_l1_platform_scope_on_replace(self) -> None:
        """自定义平台角色：超管可挂全部管理码，不再被 kind=tenant 藏掉 L1 专属码。"""
        self._add_permission("platform.tenant.read", "platform")
        role = self.make_role("ops.manager")
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("app.read"), self.pid("platform.tenant.read")],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(role.id, body, self.request, actor=self.actor, db=self.db)
        self.assertTrue(result["changed"])
        self.assertEqual(self.held_codes(role), {"app.read", "platform.tenant.read"})

    def test_application_role_keeps_historical_out_of_scope_on_replace(self) -> None:
        """历史已持有的越域码允许保留；新增其他应用业务码 422。"""
        self._add_permission("otherapp.item.read", "otherapp")
        role = self.make_role("viewer", kind="application", application_id=self.application.id)
        self.grant_codes(role, "org.read")
        keep_body = RolePermissionsUpdate(
            permission_ids=[self.pid("org.read")],
            expected_current_permission_ids=[self.pid("org.read")],
        )
        result = replace_role_permissions(role.id, keep_body, self.request, actor=self.actor, db=self.db)
        self.assertFalse(result["changed"])
        self.assertEqual(self.held_codes(role), {"org.read"})
        reject_body = RolePermissionsUpdate(
            permission_ids=[self.pid("org.read"), self.pid("otherapp.item.read")],
            expected_current_permission_ids=[self.pid("org.read")],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(role.id, reject_body, self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(self.held_codes(role), {"org.read"})

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

    def test_provisioned_template_role_code_counts(self) -> None:
        tenant_role = provision_tenant_admin_role(self.db, self.tenant.id)
        multi_admin = provision_multi_app_admin_role(self.db, self.tenant.id, self.application.id)
        app_admin = provision_application_admin_role(self.db, self.tenant.id, self.application.id)
        app_member = provision_application_member_role(self.db, self.tenant.id, self.application.id)
        self.assertEqual(self.held_codes(tenant_role), set(L3_PERMISSION_CODES))
        self.assertEqual(len(self.held_codes(tenant_role)), 20)
        self.assertNotIn("rbac.permission.manage", self.held_codes(tenant_role))
        self.assertTrue(AUTHORITY_MANAGE_CODES <= self.held_codes(tenant_role))
        self.assertEqual(self.held_codes(multi_admin), set(L2M_PERMISSION_CODES))
        self.assertEqual(len(self.held_codes(multi_admin)), 16)
        self.assertIn("rbac.app_role.assign", self.held_codes(multi_admin))
        self.assertEqual(self.held_codes(app_admin), set(L2_PERMISSION_CODES))
        self.assertEqual(len(self.held_codes(app_admin)), 15)
        self.assertEqual(self.held_codes(app_member), set())
        provision_tenant_admin_role(self.db, self.tenant.id)
        provision_multi_app_admin_role(self.db, self.tenant.id, self.application.id)
        provision_application_admin_role(self.db, self.tenant.id, self.application.id)
        self.db.expire_all()
        self.assertEqual(len(self.held_codes(tenant_role)), 20)
        self.assertEqual(len(self.held_codes(multi_admin)), 16)
        self.assertEqual(len(self.held_codes(app_admin)), 15)

    def test_provision_tenant_admin_strips_permission_manage(self) -> None:
        """G32：存量 L3 上的 rbac.permission.manage 在再次预置时被剥离。"""
        tenant_role = provision_tenant_admin_role(self.db, self.tenant.id)
        self.db.add(RolePermission(role_id=tenant_role.id, permission_id=self.pid("rbac.permission.manage")))
        self.db.flush()
        self.assertIn("rbac.permission.manage", self.held_codes(tenant_role))
        provision_tenant_admin_role(self.db, self.tenant.id)
        self.db.expire_all()
        self.assertNotIn("rbac.permission.manage", self.held_codes(tenant_role))
        self.assertEqual(len(self.held_codes(tenant_role)), 20)

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
