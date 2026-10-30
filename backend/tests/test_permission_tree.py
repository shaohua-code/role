"""隔离验证权限目录资源树、模板菜单码、自定义角色按码生效与数据权限叶子。"""

from __future__ import annotations

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.v1.admin.access_control import list_permission_tree
from app.db.base import Base
from app.db.seed_greenfield import seed_l1_role, seed_permissions, seed_platform_tenant
from app.models.authorization import Permission, RolePermission
from app.models.identity import Tenant, User
from app.models.organization import RoleDataScope
from app.schemas.access_control import AuthorizationCheck
from app.services.authorization import evaluate_access
from app.services.permission_kinds import (
    extra_ui_codes_for,
    map_role_data_scopes_to_codes,
    seed_ui_permissions,
)
from app.services.rbac_guards import ensure_codes, user_has_management_code
from app.services.role_provisioning import (
    L2_PERMISSION_CODES,
    L3_PERMISSION_CODES,
    provision_application_admin_role,
    provision_tenant_admin_role,
)
from tests.greenfield_fixture import make_platform_admin_binding, make_tenant_role_binding

SIDEBAR_GROUPS = ["身份与组织", "应用与权限", "高级管理", "平台治理", "审计与验证"]


class PermissionTreeTests(unittest.TestCase):
    """每个用例在内存 SQLite 中运行，不改动开发库。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.actor = User(
            email=f"admin-{uuid4().hex}@example.test",
            password_hash="test-only",
            display_name="管理员",
        )
        self.db.add(self.actor)
        self.db.flush()
        make_platform_admin_binding(self.db, self.actor)
        seed_permissions(self.db)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _all_codes(self, nodes: list[dict]) -> set[str]:
        codes: set[str] = set()

        def walk(items: list[dict]) -> None:
            for node in items:
                if node.get("code"):
                    codes.add(node["code"])
                children = node.get("children") or []
                if children:
                    walk(children)

        walk(nodes)
        return codes

    def _find(self, nodes: list[dict], *, title: str | None = None, code: str | None = None) -> dict:
        for node in nodes:
            if title is not None and node.get("title") == title:
                return node
            if code is not None and node.get("code") == code:
                return node
            children = node.get("children") or []
            if children:
                try:
                    return self._find(children, title=title, code=code)
                except AssertionError:
                    pass
        self.fail(f"node not found title={title} code={code}")

    def test_resource_tree_matches_sidebar_and_nests_buttons_apis(self) -> None:
        from app.services.permission_kinds import ensure_data_scope_children

        parent = Permission(
            code="appa.doc.read",
            catalog_namespace="appa",
            resource_type="document",
            scope="read",
            description="读文档",
            surface="business",
            requires_data_scope=True,
            kind="api",
        )
        self.db.add(parent)
        self.db.flush()
        ensure_data_scope_children(self.db, parent)
        payload = list_permission_tree(actor=self.actor, db=self.db)
        resource = payload["resource"]
        data = payload["data"]
        self.assertEqual(resource[0]["title"], "运营总览")
        self.assertEqual(resource[0]["code"], "menu.overview")
        self.assertTrue(resource[0]["selectable"])
        self.assertFalse(resource[0]["is_leaf"])
        titles = [node["title"] for node in resource]
        for group in SIDEBAR_GROUPS:
            self.assertIn(group, titles)
        overview_codes = {child["code"] for child in resource[0]["children"]}
        self.assertIn("platform.overview.read", overview_codes)

        identity = self._find(resource, title="身份与组织")
        self.assertFalse(identity["selectable"])
        users = self._find(identity["children"], code="menu.users")
        self.assertTrue(users["selectable"])
        user_child_codes = {child["code"] for child in users["children"]}
        self.assertIn("button.users.manage", user_child_codes)
        self.assertIn("org.member.read", user_child_codes)
        self.assertIn("platform.account.read", user_child_codes)

        platform_group = self._find(resource, title="平台治理")
        platform_codes = {child["code"] for child in platform_group["children"]}
        self.assertIn("menu.model_usage", platform_codes)
        self.assertIn("menu.models", platform_codes)
        self.assertIn("menu.tenants", platform_codes)

        resource_codes = self._all_codes(resource)
        self.assertIn("menu.overview", resource_codes)
        self.assertIn("button.users.manage", resource_codes)
        self.assertIn("platform.overview.read", resource_codes)

        data_codes = self._all_codes(data)
        self.assertIn("appa.doc.read.scope.self", data_codes)
        self.assertNotIn("platform.overview.read", data_codes)
        self.assertNotIn("org.member.read", data_codes)

    def test_l1_template_includes_menu_codes(self) -> None:
        platform_tenant = seed_platform_tenant(self.db)
        role = seed_l1_role(self.db, platform_tenant)
        granted = set(self.db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id),
        ).all())
        self.assertIn("menu.tenants", granted)
        self.assertIn("menu.overview", granted)
        self.assertIn("menu.model_usage", granted)
        self.assertIn("button.permissions.manage", granted)

    def test_l3_template_has_workspace_menu_not_tenants(self) -> None:
        tenant = Tenant(name="业务租户", slug=f"t-{uuid4().hex[:10]}")
        self.db.add(tenant)
        self.db.flush()
        role = provision_tenant_admin_role(self.db, tenant.id)
        granted = set(self.db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id),
        ).all())
        self.assertIn("menu.organization_workspace", granted)
        self.assertNotIn("menu.tenants", granted)
        for code in extra_ui_codes_for(L3_PERMISSION_CODES):
            self.assertIn(code, granted)

    def test_l2_template_has_no_menu_tenants(self) -> None:
        from app.models.application import Application

        tenant = Tenant(name="业务租户", slug=f"t-{uuid4().hex[:10]}")
        self.db.add(tenant)
        self.db.flush()
        application = Application(
            tenant_id=tenant.id,
            client_id=f"a-{uuid4().hex[:8]}",
            name="应用A",
            permission_namespace="appa",
            redirect_uris=[],
        )
        self.db.add(application)
        self.db.flush()
        role = provision_application_admin_role(self.db, tenant.id, application.id)
        granted = set(self.db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id),
        ).all())
        self.assertNotIn("menu.tenants", granted)
        self.assertIn("menu.application_workspace", granted)
        for code in extra_ui_codes_for(L2_PERMISSION_CODES):
            self.assertIn(code, granted)

    def test_custom_role_menu_and_member_read_passes_without_template_key(self) -> None:
        tenant = Tenant(name="业务租户", slug=f"reader-{uuid4().hex[:8]}")
        reader = User(
            email=f"reader-{uuid4().hex}@example.test",
            password_hash="test-only",
            display_name="只读用户",
        )
        stranger = User(
            email=f"stranger-{uuid4().hex}@example.test",
            password_hash="test-only",
            display_name="无码用户",
        )
        self.db.add_all([tenant, reader, stranger])
        self.db.flush()
        menu = self.db.scalar(select(Permission).where(Permission.code == "menu.users"))
        api = self.db.scalar(select(Permission).where(Permission.code == "org.member.read"))
        self.assertIsNotNone(menu)
        self.assertIsNotNone(api)
        make_tenant_role_binding(
            self.db,
            tenant_id=tenant.id,
            actor=reader,
            role_key="custom.users.reader",
            role_name="用户只读",
            permission_ids=[menu.id, api.id],
        )
        self.assertTrue(user_has_management_code(reader, self.db, "org.member.read", tenant_id=tenant.id))
        self.assertTrue(user_has_management_code(reader, self.db, "menu.users"))
        ensure_codes(reader, self.db, "org.member.read")
        with self.assertRaises(HTTPException) as ctx:
            ensure_codes(stranger, self.db, "org.member.read")
        self.assertEqual(ctx.exception.status_code, 403)


class DataScopeCodeTests(unittest.TestCase):
    """业务码缺数据叶子拒绝；映射 RoleDataScope 后放行。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(
            email=f"scope-{uuid4().hex}@example.test",
            password_hash="test-only",
            display_name="范围用户",
        )
        self.tenant = Tenant(name="范围租户", slug=f"scope-{uuid4().hex[:10]}")
        self.db.add_all([self.user, self.tenant])
        self.db.flush()
        self.permission = Permission(
            code="appa.doc.read",
            catalog_namespace="appa",
            resource_type="document",
            scope="read",
            description="读文档",
            surface="business",
            requires_data_scope=True,
            kind="api",
        )
        self.db.add(self.permission)
        self.db.flush()
        self.role = make_tenant_role_binding(
            self.db,
            tenant_id=self.tenant.id,
            actor=self.user,
            role_key="doc.reader",
            role_name="文档读者",
            permission_ids=[self.permission.id],
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _decide(self) -> dict:
        return evaluate_access(
            AuthorizationCheck(
                tenant_id=self.tenant.id,
                permission_code="appa.doc.read",
                include_data_scope=True,
            ),
            self.user,
            self.db,
            enforce_token_context=False,
        )

    def test_business_code_without_data_leaf_is_denied(self) -> None:
        result = self._decide()
        self.assertFalse(result["decision"]["allowed"])
        self.assertEqual(result["decision"]["reason"], "data_scope_policy_missing")

    def test_granting_data_leaf_allows_self_scope(self) -> None:
        from app.services.permission_kinds import data_scope_code, ensure_data_scope_children, grant_codes_skip_missing

        ensure_data_scope_children(self.db, self.permission)
        grant_codes_skip_missing(self.db, self.role.id, (data_scope_code("appa.doc.read", "self"),))
        result = self._decide()
        self.assertTrue(result["decision"]["allowed"])
        self.assertEqual(result["decision"]["data_scope"]["constraints"][0]["kind"], "owner")

    def test_mapping_role_data_scope_then_allows(self) -> None:
        from app.services.permission_kinds import data_scope_code

        self.db.add(RoleDataScope(
            tenant_id=self.tenant.id,
            role_id=self.role.id,
            permission_id=self.permission.id,
            scope_type="tenant",
            organization_ids=[],
        ))
        self.db.flush()
        mapped = map_role_data_scopes_to_codes(self.db)
        self.assertGreaterEqual(mapped, 1)
        leaf = self.db.scalar(select(Permission).where(
            Permission.code == data_scope_code("appa.doc.read", "tenant"),
        ))
        self.assertIsNotNone(leaf)
        granted = self.db.scalar(select(RolePermission.id).where(
            RolePermission.role_id == self.role.id,
            RolePermission.permission_id == leaf.id,
        ))
        self.assertIsNotNone(granted)
        result = self._decide()
        self.assertTrue(result["decision"]["allowed"])
        self.assertEqual(result["decision"]["data_scope"]["constraints"][0]["kind"], "tenant")


class SeedUiIdempotentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_seed_ui_permissions_is_idempotent(self) -> None:
        first = seed_ui_permissions(self.db)
        second = seed_ui_permissions(self.db)
        self.assertGreater(first, 0)
        self.assertEqual(second, 0)
        usage = self.db.scalar(select(Permission).where(Permission.code == "menu.model_usage"))
        self.assertIsNotNone(usage)
        self.assertEqual(usage.kind, "menu")
