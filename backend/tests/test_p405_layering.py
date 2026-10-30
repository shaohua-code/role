"""P405：平台 / 应用权限分层——两类角色、五级模板、任命链、自动补成员。"""

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
from app.services.admin_authorization import has_application_admin_access
from app.services.authorization import evaluate_access
from app.services.role_provisioning import (
    L2M_PERMISSION_CODES,
    L2M_ROLE_KEY,
    L2_PERMISSION_CODES,
    L2_ROLE_KEY,
    L3_PERMISSION_CODES,
    L3_ROLE_KEY,
    L4_ROLE_KEY,
    TEMPLATE_ROLE_KEYS,
    provision_application_platform_roles,
    provision_tenant_admin_role,
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
        for code in sorted(
            set(L3_PERMISSION_CODES) | set(L2_PERMISSION_CODES) | set(L2M_PERMISSION_CODES)
            | {"platform.overview.read", "rbac.permission.manage"},
        ):
            row = Permission(
                code=code, catalog_namespace="platform",
                resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
                surface="management", requires_data_scope=False,
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
        self.l2m = self._user("l2m")
        self.l2 = self._user("l2")
        self.member = self._user("member")
        l3_role = provision_tenant_admin_role(self.db, self.tenant.id)
        self.multi_role, self.admin_role, self.member_role = provision_application_platform_roles(
            self.db, self.tenant.id, self.application.id,
        )
        self._bind(self.l3, l3_role)
        self._bind(self.l2m, self.multi_role)
        self._bind(self.l2, self.admin_role)
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

    def test_five_template_keys(self) -> None:
        self.assertEqual(len(TEMPLATE_ROLE_KEYS), 5)
        self.assertIn(L2M_ROLE_KEY, TEMPLATE_ROLE_KEYS)
        self.assertEqual(self._held(self.admin_role), set(L2_PERMISSION_CODES))
        self.assertEqual(self._held(self.multi_role), set(L2M_PERMISSION_CODES))
        self.assertIn("rbac.app_role.assign", self._held(self.multi_role))
        self.assertEqual(self._held(self.member_role), set())

    def test_platform_role_rejects_business_code(self) -> None:
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["app.read"].id, self.business.id],
            expected_current_permission_ids=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(self.admin_role.id, body, self.request, actor=self.l1, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台角色不能挂应用权限", str(ctx.exception.detail))

    def test_application_role_rejects_invisible_management_code(self) -> None:
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["org.read"].id],
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
            permission_ids=[self.catalog["org.read"].id],
            expected_current_permission_ids=[],
        )
        result = replace_application_role_permissions(
            self.application.id, self.reader.id, body, self.request, actor=self.l3, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertIn("org.read", self._held(self.reader))

    def test_l2_can_grant_app_management_on_application_role(self) -> None:
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["app.read"].id],
            expected_current_permission_ids=[],
        )
        result = replace_application_role_permissions(
            self.application.id, self.reader.id, body, self.request, actor=self.l2, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertIn("app.read", self._held(self.reader))

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
        self.assertIn("org.read", l3_codes)
        self.assertIn("app.read", l3_codes)
        self.assertIn("appa.doc.read", l3_codes)
        self.assertNotIn("org.read", l2_codes)
        self.assertIn("app.read", l2_codes)
        self.assertIn("org.member.manage", l2_codes)
        self.assertNotIn("org.read", business_only)
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
        denied = evaluate_access(check, self.member, self.db)
        self.assertFalse(denied["decision"]["allowed"])
        self.db.add(RoleBinding(membership_id=self.member_membership.id, role_id=self.reader.id))
        self.db.commit()
        allowed = evaluate_access(check, self.member, self.db)
        self.assertTrue(allowed["decision"]["allowed"])

    def test_l3_can_appoint_multi_and_single_admin(self) -> None:
        target = self._user("appointee")
        membership = TenantMembership(user_id=target.id, tenant_id=self.tenant.id, status="active")
        self.db.add(membership)
        self.db.commit()
        bind_application_role(
            self.application.id,
            ApplicationRoleBindingCreate(email=target.email, role_id=self.multi_role.id),
            self.request, actor=self.l3, db=self.db,
        )
        self.assertTrue(self._has_binding(membership.id, self.multi_role.id))
        other = self._user("direct-l2")
        other_membership = TenantMembership(user_id=other.id, tenant_id=self.tenant.id, status="active")
        self.db.add(other_membership)
        self.db.commit()
        bind_application_role(
            self.application.id,
            ApplicationRoleBindingCreate(email=other.email, role_id=self.admin_role.id),
            self.request, actor=self.l3, db=self.db,
        )
        self.assertTrue(self._has_binding(other_membership.id, self.admin_role.id))

    def test_multi_admin_can_appoint_app_admin_but_not_peer(self) -> None:
        target = self._user("next-admin")
        membership = TenantMembership(user_id=target.id, tenant_id=self.tenant.id, status="active")
        self.db.add(membership)
        self.db.commit()
        bind_application_role(
            self.application.id,
            ApplicationRoleBindingCreate(email=target.email, role_id=self.admin_role.id),
            self.request, actor=self.l2m, db=self.db,
        )
        self.assertTrue(self._has_binding(membership.id, self.admin_role.id))
        peer = self._user("peer-multi")
        peer_membership = TenantMembership(user_id=peer.id, tenant_id=self.tenant.id, status="active")
        self.db.add(peer_membership)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            bind_application_role(
                self.application.id,
                ApplicationRoleBindingCreate(email=peer.email, role_id=self.multi_role.id),
                self.request, actor=self.l2m, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_app_admin_cannot_appoint_app_admin(self) -> None:
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

    def test_catalog_hides_codes_actor_does_not_hold(self) -> None:
        l2_codes = self._codes(list_permissions(actor=self.l2, db=self.db))
        self.assertIn("app.manage", l2_codes)
        self.assertNotIn("org.read", l2_codes)
        self.assertNotIn("platform.overview.read", l2_codes)
        self.assertNotIn("appa.doc.read", l2_codes)
        self.assertTrue(l2_codes.issubset(set(L2_PERMISSION_CODES)))
        l3_codes = self._codes(list_permissions(actor=self.l3, db=self.db))
        self.assertIn("org.read", l3_codes)
        self.assertNotIn("platform.overview.read", l3_codes)
        self.assertNotIn("appa.doc.read", l3_codes)
        self.assertTrue(l3_codes.issubset(set(L3_PERMISSION_CODES)))

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
        self.assertNotIn(L2M_ROLE_KEY, keys)
        self.assertNotIn(L2_ROLE_KEY, keys)
        self.assertNotIn(L4_ROLE_KEY, keys)

    def test_l2_platform_role_list_hides_tenant_admin(self) -> None:
        payload = list_roles(
            q=None, kind=None, tenant_id=None, application_id=None, status=None,
            role_class="platform", actor=self.l2, db=self.db,
        )
        keys = {item["key"] for item in payload["items"]}
        self.assertIn(L2_ROLE_KEY, keys)
        self.assertIn(L2M_ROLE_KEY, keys)
        self.assertNotIn(L3_ROLE_KEY, keys)
        self.assertNotIn("appa.reader", keys)

    def test_admin_role_list_platform_class_excludes_business_roles(self) -> None:
        payload = list_roles(
            q=None, kind=None, tenant_id=None, application_id=None, status=None,
            role_class="platform", actor=self.l3, db=self.db,
        )
        keys = {item["key"] for item in payload["items"]}
        self.assertIn(L3_ROLE_KEY, keys)
        self.assertIn(L2M_ROLE_KEY, keys)
        self.assertNotIn("appa.reader", keys)

    def test_l3_and_l2_can_create_custom_platform_role(self) -> None:
        created = create_role(
            RoleCreate(tenant_id=self.tenant.id, key="ops.reviewer", name="复核"),
            self.request, actor=self.l3, db=self.db,
        )
        self.assertEqual(created["key"], "ops.reviewer")
        self.assertIsNone(created["application_id"])
        created_l2 = create_role(
            RoleCreate(tenant_id=self.tenant.id, key="ops.other", name="其他"),
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
            permission_ids=[self.catalog["platform.overview.read"].id, self.catalog["org.read"].id],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(
            UUID(created["id"]), body, self.request, actor=self.l1, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertIn("platform.overview.read", result["grant_permission_codes"])

    def test_l3_can_replace_tenant_admin_template_with_own_codes(self) -> None:
        l3_role = self.db.scalar(select(Role).where(
            Role.tenant_id == self.tenant.id, Role.key == L3_ROLE_KEY,
        ))
        current = self._permission_ids(l3_role)
        body = RolePermissionsUpdate(
            permission_ids=current, expected_current_permission_ids=current,
        )
        result = replace_role_permissions(
            l3_role.id, body, self.request, actor=self.l3, db=self.db,
        )
        self.assertFalse(result["changed"])

    def test_l3_cannot_add_upward_code_to_tenant_admin_template(self) -> None:
        l3_role = self.db.scalar(select(Role).where(
            Role.tenant_id == self.tenant.id, Role.key == L3_ROLE_KEY,
        ))
        current = self._permission_ids(l3_role)
        body = RolePermissionsUpdate(
            permission_ids=[*current, self.catalog["platform.overview.read"].id],
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

    def test_l2_cannot_grant_upward_preset_apps_admin(self) -> None:
        current = self._permission_ids(self.multi_role)
        body = RolePermissionsUpdate(
            permission_ids=current, expected_current_permission_ids=current,
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(
                self.multi_role.id, body, self.request, actor=self.l2, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("不能配置上级预置角色的授权", str(ctx.exception.detail))

    def test_l3_cannot_grant_unheld_management_code(self) -> None:
        created = create_role(
            RoleCreate(tenant_id=self.tenant.id, key="ops.limited", name="受限"),
            self.request, actor=self.l3, db=self.db,
        )
        from uuid import UUID
        body = RolePermissionsUpdate(
            permission_ids=[self.catalog["platform.overview.read"].id],
            expected_current_permission_ids=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(UUID(created["id"]), body, self.request, actor=self.l3, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        detail = str(ctx.exception.detail)
        self.assertTrue(
            "不能配置你没有的权限" in detail or "该角色作用域不可新增权限" in detail,
            detail,
        )

    def test_multi_admin_has_application_admin_access(self) -> None:
        self.assertTrue(has_application_admin_access(
            self.l2m, self.tenant.id, self.db, manage=True, application_id=self.application.id,
        ))
        self.assertFalse(has_application_admin_access(
            self.l2m, self.tenant.id, self.db, manage=True, application_id=None,
        ))


if __name__ == "__main__":
    unittest.main()
