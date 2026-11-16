"""P405：平台 / 应用权限分层——两类角色、四模板范围、任命链、自动补成员。"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.access_control import (
    create_role,
    list_permissions,
    list_roles,
    replace_role_permissions,
)
from app.api.v1.admin.applications import create_application, delete_application
from app.api.v1.tenant_admin.application_roles import (
    bind_application_role,
    list_application_member_candidates,
    list_application_members,
    list_application_permissions,
    list_application_roles,
    replace_application_role_permissions,
)
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.models.organization import RoleDataScope
from app.schemas.access_control import (
    ApplicationRoleBindingCreate,
    AuthorizationCheck,
    RoleCreate,
    RolePermissionsUpdate,
)
from app.schemas.applications import ApplicationCreate
from app.services.admin_authorization import AdminAccessGuard
from app.services.authorization import AuthorizationEvaluator
from app.services.permission_kinds import (
    ROLE_SCOPE_APP,
    ROLE_SCOPE_MEMBER,
    ROLE_SCOPE_SUPER,
    ROLE_SCOPE_TENANT,
    TEMPLATE_ROLE_SCOPES,
)
from app.services.role_provisioning import (
    L2_GRANT_NODE_CODES,
    L2_ROLE_KEY,
    L3_GRANT_NODE_CODES,
    L3_ROLE_KEY,
    L4_ROLE_KEY,
    RoleProvisioning,
    TEMPLATE_ROLE_KEYS,
)
from tests.greenfield_fixture import make_platform_admin_binding


class P405LayeringTests(unittest.TestCase):
    """每个用例在内存 SQLite 中运行，不改动开发库。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"t-{uuid4().hex[:10]}")
        self.db.add(self.tenant)
        self.db.flush()
        self.application = Application(
            tenant_id=self.tenant.id, client_id=f"a-{uuid4().hex[:8]}",
            name="应用A", permission_namespace="appa",
            redirect_uris=["https://a.example.com/cb"], status="active",
        )
        self.db.add(self.application)
        self.db.flush()
        self.catalog: dict[str, Permission] = {}
        # 管理面节点目录：三管理员模板节点全集 + 租户写按钮（超管专属，供向上越权用例）。
        for code in sorted(
            set(L3_GRANT_NODE_CODES) | set(L2_GRANT_NODE_CODES) | {"button.tenants.manage"}
        ):
            row = Permission(
                code=code, catalog_namespace="platform",
                resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
                surface="management", requires_data_scope=False,
                kind="menu" if code.startswith("menu.") else "button",
            )
            self.db.add(row)
            self.catalog[code] = row
        self.business = Permission(
            code="appa.doc.read", catalog_namespace="appa", resource_type="doc",
            scope="read", surface="business", requires_data_scope=True,
        )
        self.db.add(self.business)
        self.db.flush()
        self.l1 = self._user("l1")
        make_platform_admin_binding(self.db, self.l1)
        self.l3 = self._user("l3")
        self.l2 = self._user("l2")
        self.member = self._user("member")
        # 平台角色全局化：tenant.admin 全局一份（宿主平台管理租户），跨租户生效。
        self.l3_role = RoleProvisioning.provision_tenant_admin_role(self.db, self.tenant.id)
        # 应用开通预置 (应用管理员, 应用成员) 二元组（多应用管理员已并入应用管理员）。
        self.admin_role, self.member_role = RoleProvisioning.provision_application_platform_roles(
            self.db, self.tenant.id, self.application.id,
        )
        self._bind(self.l3, self.l3_role)
        self._bind(self.l2, self.admin_role)
        # 应用级操作者的平台侧范围角色：operator_scope 只统计未钉应用的平台角色，
        # 补一个 scope=app 的自定义平台角色让 L2 的授权范围秩为「应用级」。
        self.l2_scope_role = Role(
            tenant_id=self.tenant.id, application_id=None, kind="tenant",
            key="custom.app.level", name="应用级平台角色",
            scope=ROLE_SCOPE_APP, status="active",
        )
        self.db.add(self.l2_scope_role)
        self.db.flush()
        self._bind(self.l2, self.l2_scope_role)
        self.member_membership = self._membership(self.member)
        self.reader = Role(
            tenant_id=self.tenant.id, application_id=self.application.id,
            kind="application", key="appa.reader", name="只读", status="active",
        )
        self.db.add(self.reader)
        self.db.flush()
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

    def _membership(self, user: User) -> TenantMembership:
        membership = self.db.scalar(select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == self.tenant.id,
        ))
        if membership is None:
            membership = TenantMembership(
                user_id=user.id, tenant_id=self.tenant.id, status="active",
            )
            self.db.add(membership)
            self.db.flush()
        return membership

    def _bind(self, user: User, role: Role) -> TenantMembership:
        membership = self._membership(user)
        if self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id,
        )) is None:
            self.db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
            self.db.flush()
        return membership

    def _user(self, prefix: str) -> User:
        user = User(
            email=f"{prefix}-{uuid4().hex[:8]}@example.com",
            password_hash="test-only",
            display_name=prefix,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def _codes(self, payload: dict) -> set[str]:
        return {item["code"] for item in payload["items"]}

    def _permission_ids(self, role: Role) -> list:
        return list(self.db.scalars(
            select(RolePermission.permission_id).where(RolePermission.role_id == role.id),
        ).all())

    def _held(self, role: Role) -> set[str]:
        return set(self.db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id),
        ).all())

    def _has_binding(self, membership_id, role_id) -> bool:
        return self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.membership_id == membership_id,
            RoleBinding.role_id == role_id,
        )) is not None

    def test_four_template_keys(self) -> None:
        # 四个模板 key；apps.admin（多应用管理员）已删除。
        self.assertEqual(len(TEMPLATE_ROLE_KEYS), 4)
        self.assertNotIn("apps.admin", TEMPLATE_ROLE_KEYS)
        # 模板授权范围：超管/租户级/应用级/成员，只能向下。
        self.assertEqual(TEMPLATE_ROLE_SCOPES["platform.admin"], ROLE_SCOPE_SUPER)
        self.assertEqual(TEMPLATE_ROLE_SCOPES["tenant.admin"], ROLE_SCOPE_TENANT)
        self.assertEqual(TEMPLATE_ROLE_SCOPES["app.admin"], ROLE_SCOPE_APP)
        self.assertEqual(TEMPLATE_ROLE_SCOPES["app.member"], ROLE_SCOPE_MEMBER)
        # 节点集断言：应用管理员恰持 L2 模板节点；应用成员零管理面节点。
        self.assertEqual(self._held(self.admin_role), set(L2_GRANT_NODE_CODES))
        self.assertEqual(self._held(self.member_role), set())

    def test_platform_role_rejects_business_code(self) -> None:
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["menu.application_workspace"].id, self.business.id],
            expected_current_permission_ids=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(self.admin_role.id, body, self.request, actor=self.l1, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台角色只能挂菜单/按钮节点", str(ctx.exception.detail))

    def test_application_role_rejects_invisible_management_code(self) -> None:
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["menu.organization_workspace"].id],
            expected_current_permission_ids=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_application_role_permissions(
                self.application.id, self.reader.id, body, self.request, actor=self.l2, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("不能配置你没有的权限", str(ctx.exception.detail))

    def test_l3_can_grant_tenant_management_on_application_role(self) -> None:
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["menu.organization_workspace"].id],
            expected_current_permission_ids=[],
        )
        result = replace_application_role_permissions(
            self.application.id, self.reader.id, body, self.request, actor=self.l3, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertIn("menu.organization_workspace", self._held(self.reader))

    def test_l2_can_grant_app_management_on_application_role(self) -> None:
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["menu.application_workspace"].id],
            expected_current_permission_ids=[],
        )
        result = replace_application_role_permissions(
            self.application.id, self.reader.id, body, self.request, actor=self.l2, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertIn("menu.application_workspace", self._held(self.reader))

    def test_application_permission_catalog_respects_actor_level(self) -> None:
        l3_codes = {row["code"] for row in list_application_permissions(
            self.application.id, self.reader.id, True, actor=self.l3, db=self.db,
        )}
        l2_codes = {row["code"] for row in list_application_permissions(
            self.application.id, self.reader.id, True, actor=self.l2, db=self.db,
        )}
        business_only = {row["code"] for row in list_application_permissions(
            self.application.id, self.reader.id, actor=self.l3, db=self.db,
        )}
        self.assertIn("menu.organization_workspace", l3_codes)
        self.assertIn("menu.application_workspace", l3_codes)
        self.assertIn("appa.doc.read", l3_codes)
        self.assertNotIn("menu.organization_workspace", l2_codes)
        self.assertIn("menu.application_workspace", l2_codes)
        self.assertIn("button.app_role.manage", l2_codes)
        self.assertNotIn("menu.organization_workspace", business_only)
        self.assertIn("appa.doc.read", business_only)

    def test_bind_application_role_auto_completes_member(self) -> None:
        body = ApplicationRoleBindingCreate(email=self.member.email, role_id=self.reader.id)
        bind_application_role(self.application.id, body, self.request, actor=self.l3, db=self.db)
        self.assertTrue(self._has_binding(self.member_membership.id, self.reader.id))
        self.assertTrue(self._has_binding(self.member_membership.id, self.member_role.id))

    def test_list_members_can_filter_by_role_id(self) -> None:
        other = self._user("other-reader")
        self._membership(other)
        extra = Role(
            tenant_id=self.tenant.id, application_id=self.application.id,
            kind="application", key="appa.extra", name="额外", status="active",
        )
        self.db.add(extra)
        self.db.flush()
        bind_application_role(
            self.application.id,
            ApplicationRoleBindingCreate(email=self.member.email, role_id=self.reader.id),
            self.request, actor=self.l3, db=self.db,
        )
        bind_application_role(
            self.application.id,
            ApplicationRoleBindingCreate(email=other.email, role_id=extra.id),
            self.request, actor=self.l3, db=self.db,
        )
        filtered = list_application_members(
            self.application.id, None, self.reader.id, 20, 0, actor=self.l3, db=self.db,
        )
        ids = {item["user_id"] for item in filtered["items"]}
        self.assertIn(str(self.member.id), ids)
        self.assertNotIn(str(other.id), ids)
        self.assertEqual(filtered["total"], 1)

    def test_list_member_candidates_marks_already_bound(self) -> None:
        unbound = self._user("unbound")
        self._membership(unbound)
        self.db.commit()
        payload = list_application_member_candidates(
            self.application.id, None, self.reader.id, 50, 0, actor=self.l2, db=self.db,
        )
        by_id = {item["user_id"]: item for item in payload["items"]}
        self.assertIn(str(unbound.id), by_id)
        self.assertFalse(by_id[str(unbound.id)]["already_bound"])
        bind_application_role(
            self.application.id,
            ApplicationRoleBindingCreate(email=unbound.email, role_id=self.reader.id),
            self.request, actor=self.l3, db=self.db,
        )
        payload = list_application_member_candidates(
            self.application.id, None, self.reader.id, 50, 0, actor=self.l2, db=self.db,
        )
        by_id = {item["user_id"]: item for item in payload["items"]}
        self.assertTrue(by_id[str(unbound.id)]["already_bound"])

    def test_l2_cannot_list_other_app_member_candidates(self) -> None:
        other = Application(
            tenant_id=self.tenant.id, client_id=f"b-{uuid4().hex[:8]}",
            name="应用B", permission_namespace="appb",
            redirect_uris=["https://b.example.com/cb"], status="active",
        )
        self.db.add(other)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            list_application_member_candidates(
                other.id, None, None, 20, 0, actor=self.l2, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_plain_member_cannot_list_member_candidates(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            list_application_member_candidates(
                self.application.id, None, None, 20, 0, actor=self.member, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_member_gets_business_code_from_application_role(self) -> None:
        self.db.add(RolePermission(role_id=self.reader.id, permission_id=self.business.id))
        self.db.add(RoleDataScope(
            tenant_id=self.tenant.id, role_id=self.reader.id,
            permission_id=self.business.id, scope_type="self", organization_ids=[],
        ))
        self.db.add(RoleBinding(membership_id=self.member_membership.id, role_id=self.member_role.id))
        self.db.commit()
        check = AuthorizationCheck(
            tenant_id=self.tenant.id, application_id=self.application.id,
            permission_code=self.business.code, include_data_scope=True,
        )
        denied = AuthorizationEvaluator.evaluate_access(check, self.member, self.db)
        self.assertFalse(denied["decision"]["allowed"])
        self.db.add(RoleBinding(membership_id=self.member_membership.id, role_id=self.reader.id))
        self.db.commit()
        allowed = AuthorizationEvaluator.evaluate_access(check, self.member, self.db)
        self.assertTrue(allowed["decision"]["allowed"])

    def test_l3_can_appoint_app_admin(self) -> None:
        # 租户级可以任命应用管理员（应用管理员管 N 个应用 = 绑 N 个应用）。
        target = self._user("appointee")
        membership = TenantMembership(user_id=target.id, tenant_id=self.tenant.id, status="active")
        self.db.add(membership)
        self.db.commit()
        bind_application_role(
            self.application.id,
            ApplicationRoleBindingCreate(email=target.email, role_id=self.admin_role.id),
            self.request, actor=self.l3, db=self.db,
        )
        self.assertTrue(self._has_binding(membership.id, self.admin_role.id))

    def test_app_admin_cannot_appoint_app_admin(self) -> None:
        # 应用级不能向上任命应用管理员（任命是租户级能力）。
        target = self._user("blocked")
        membership = TenantMembership(user_id=target.id, tenant_id=self.tenant.id, status="active")
        self.db.add(membership)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            bind_application_role(
                self.application.id,
                ApplicationRoleBindingCreate(email=target.email, role_id=self.admin_role.id),
                self.request, actor=self.l2, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def _custom_tenant_role(self, key: str, node_codes: tuple[str, ...]) -> Role:
        """自定义租户级平台角色：挂给定管理面节点（不钉应用）。"""
        role = Role(
            tenant_id=self.tenant.id, application_id=None, kind="tenant",
            key=key, name=key, scope=ROLE_SCOPE_TENANT, status="active",
        )
        self.db.add(role)
        self.db.flush()
        for code in node_codes:
            self.db.add(RolePermission(role_id=role.id, permission_id=self.catalog[code].id))
        self.db.flush()
        return role

    def test_custom_tenant_role_with_manage_node_can_bind_members(self) -> None:
        # 自定义租户级管理角色持「应用角色写操作」节点：与 L3 同口径维护应用角色成员。
        manager = self._user("mgr")
        manager_role = self._custom_tenant_role("custom.app.manager", ("button.app_role.manage",))
        self._bind(manager, manager_role)
        bind_application_role(
            self.application.id,
            ApplicationRoleBindingCreate(email=self.member.email, role_id=self.reader.id),
            self.request, actor=manager, db=self.db,
        )
        self.assertTrue(self._has_binding(self.member_membership.id, self.reader.id))

    def test_custom_tenant_role_without_manage_node_cannot_bind_members(self) -> None:
        # 范围达标但未持按钮节点（只勾菜单）：绑成员仍 403（写接口认按钮节点）。
        viewer = self._user("viewer")
        viewer_role = self._custom_tenant_role(
            "custom.app.viewer", ("menu.application_workspace",),
        )
        self._bind(viewer, viewer_role)
        with self.assertRaises(HTTPException) as ctx:
            bind_application_role(
                self.application.id,
                ApplicationRoleBindingCreate(email=self.member.email, role_id=self.reader.id),
                self.request, actor=viewer, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("缺少应用角色成员管理权限", str(ctx.exception.detail))

    def test_catalog_hides_codes_actor_does_not_hold(self) -> None:
        # 目录可见性 = 操作者已挂节点并集（看得见才能配）。
        l2_codes = self._codes(list_permissions(actor=self.l2, db=self.db))
        self.assertIn("menu.application_workspace", l2_codes)
        self.assertNotIn("menu.organization_workspace", l2_codes)
        self.assertNotIn("appa.doc.read", l2_codes)
        self.assertTrue(l2_codes.issubset(set(L2_GRANT_NODE_CODES)))
        l3_codes = self._codes(list_permissions(actor=self.l3, db=self.db))
        self.assertIn("menu.organization_workspace", l3_codes)
        self.assertNotIn("appa.doc.read", l3_codes)
        self.assertTrue(l3_codes.issubset(set(L3_GRANT_NODE_CODES)))

    def test_l2_cannot_create_or_delete_application(self) -> None:
        body = ApplicationCreate(
            tenant_id=self.tenant.id, name="越权新建",
            client_id=f"x-{uuid4().hex[:8]}",
            redirect_uris=["https://x.example.com/cb"],
        )
        with self.assertRaises(HTTPException) as ctx:
            create_application(body, self.request, Response(), actor=self.l2, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(HTTPException) as ctx:
            delete_application(self.application.id, self.request, actor=self.l2, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_workspace_role_list_excludes_templates(self) -> None:
        rows = list_application_roles(self.application.id, actor=self.l3, db=self.db)
        keys = {item["key"] for item in rows}
        self.assertIn("appa.reader", keys)
        # apps.admin（多应用管理员）已删除，且不在模板 key 集合中。
        self.assertNotIn("apps.admin", keys)
        self.assertNotIn("apps.admin", TEMPLATE_ROLE_KEYS)
        self.assertNotIn(L2_ROLE_KEY, keys)
        self.assertNotIn(L4_ROLE_KEY, keys)

    def test_l2_platform_role_list_hides_tenant_admin(self) -> None:
        payload = list_roles(
            q=None, kind=None, tenant_id=None, application_id=None, status=None,
            role_class="platform", actor=self.l2, db=self.db,
        )
        keys = {item["key"] for item in payload["items"]}
        self.assertIn(L2_ROLE_KEY, keys)
        self.assertNotIn(L3_ROLE_KEY, keys)
        self.assertNotIn("appa.reader", keys)

    def test_admin_role_list_platform_class_excludes_business_roles(self) -> None:
        payload = list_roles(
            q=None, kind=None, tenant_id=None, application_id=None, status=None,
            role_class="platform", actor=self.l3, db=self.db,
        )
        keys = {item["key"] for item in payload["items"]}
        self.assertIn(L3_ROLE_KEY, keys)
        self.assertNotIn("appa.reader", keys)

    def test_l3_and_l2_can_create_custom_platform_role(self) -> None:
        created = create_role(
            RoleCreate(tenant_id=self.tenant.id, key="ops.reviewer", name="复核"),
            self.request, actor=self.l3, db=self.db,
        )
        self.assertEqual(created["key"], "ops.reviewer")
        self.assertIsNone(created["application_id"])
        # 应用级创建自定义平台角色：范围只能向下，显式选 app 范围。
        created_l2 = create_role(
            RoleCreate(tenant_id=self.tenant.id, key="ops.other", name="其他", scope="app"),
            self.request, actor=self.l2, db=self.db,
        )
        self.assertEqual(created_l2["key"], "ops.other")
        self.assertIsNone(created_l2["application_id"])

    def test_l1_custom_platform_role_accepts_all_management_codes(self) -> None:
        created = create_role(
            RoleCreate(tenant_id=self.tenant.id, key="ops.full", name="全量"),
            self.request, actor=self.l1, db=self.db,
        )
        from uuid import UUID
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["menu.overview"].id, self.catalog["menu.organization_workspace"].id],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(
            UUID(created["id"]), body, self.request, actor=self.l1, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertIn("menu.organization_workspace", result["grant_permission_codes"])

    def test_l3_can_replace_tenant_admin_template_with_own_codes(self) -> None:
        # 全局 L3 模板宿主平台管理租户，直接用 setUp 保存的引用。
        l3_role = self.l3_role
        current = self._permission_ids(l3_role)
        body = RolePermissionsUpdate(
            permission_ids=current, expected_current_permission_ids=current,
        )
        result = replace_role_permissions(
            l3_role.id, body, self.request, actor=self.l3, db=self.db,
        )
        self.assertFalse(result["changed"])

    def test_l3_cannot_add_upward_code_to_tenant_admin_template(self) -> None:
        # 全局 L3 模板宿主平台管理租户，直接用 setUp 保存的引用。
        l3_role = self.l3_role
        current = self._permission_ids(l3_role)
        body = RolePermissionsUpdate(
            permission_ids=[*current, self.catalog["button.tenants.manage"].id],
            expected_current_permission_ids=current,
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(l3_role.id, body, self.request, actor=self.l3, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_l2_can_replace_app_admin_template_with_own_codes(self) -> None:
        current = self._permission_ids(self.admin_role)
        body = RolePermissionsUpdate(
            permission_ids=current, expected_current_permission_ids=current,
        )
        result = replace_role_permissions(
            self.admin_role.id, body, self.request, actor=self.l2, db=self.db,
        )
        self.assertFalse(result["changed"])

    def test_l2_cannot_manage_upward_preset_tenant_admin(self) -> None:
        # 范围只能向下：应用级看不见（更谈不上改）租户级预置模板的授权。
        # 平台角色全局化：全局 L3 模板对应用级操作者仍按范围秩隐藏（404）。
        l3_role = self.l3_role
        current = self._permission_ids(l3_role)
        body = RolePermissionsUpdate(
            permission_ids=current, expected_current_permission_ids=current,
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(
                l3_role.id, body, self.request, actor=self.l2, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("角色不存在", str(ctx.exception.detail))

    def test_l3_cannot_grant_unheld_management_code(self) -> None:
        created = create_role(
            RoleCreate(tenant_id=self.tenant.id, key="ops.limited", name="受限"),
            self.request, actor=self.l3, db=self.db,
        )
        from uuid import UUID
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["button.tenants.manage"].id],
            expected_current_permission_ids=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(UUID(created["id"]), body, self.request, actor=self.l3, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        detail = str(ctx.exception.detail)
        self.assertTrue(
            "授权下限高于角色范围" in detail or "不能配置你没有的权限" in detail,
            detail,
        )

    def test_app_admin_access_pinned_only(self) -> None:
        # 应用管理员管 N 个应用 = 绑 N 个应用：钉住的应用可管，未钉应用（创建入口）不可向上。
        self.assertTrue(AdminAccessGuard.has_application_admin_access(
            self.l2, self.tenant.id, self.db, manage=True, application_id=self.application.id,
        ))
        self.assertFalse(AdminAccessGuard.has_application_admin_access(
            self.l2, self.tenant.id, self.db, manage=True, application_id=None,
        ))


if __name__ == "__main__":
    unittest.main()
