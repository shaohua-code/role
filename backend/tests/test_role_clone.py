"""角色复制采用隔离 SQLite 验证范围、默认拒绝和授权复制规则。"""

import unittest
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.access_control import clone_role
from app.db.base import Base
from app.models import (
    Application,
    AuditEvent,
    Permission,
    Role,
    RoleBinding,
    RolePermission,
    Tenant,
    TenantMembership,
    User,
    UserGroup,
    UserGroupRole,
)
from app.models.organization import RoleDataScope
from app.schemas.access_control import RoleCloneRequest


class RoleCloneContractTests(unittest.TestCase):
    def test_authorization_copy_is_opt_in_and_strict_boolean(self) -> None:
        body = RoleCloneRequest(key="copy.role", name="副本")
        self.assertFalse(body.copy_authorizations)

        for value in ("true", 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RoleCloneRequest(key="copy.role", name="副本", copy_authorizations=value)

    def test_clone_fields_are_normalized_and_extra_fields_rejected(self) -> None:
        body = RoleCloneRequest(key="  copy.role  ", name="  副本  ", description="  说明  ")
        self.assertEqual((body.key, body.name, body.description), ("copy.role", "副本", "说明"))
        with self.assertRaises(ValueError):
            RoleCloneRequest(key="copy.role", name="副本", tenant_id=str(uuid4()))


class RoleCloneIsolationTests(unittest.TestCase):
    """每例使用独立内存数据库，不触碰项目开发库或任何租户数据。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(id=uuid4(), name="复制测试租户", slug=f"clone-{uuid4().hex[:16]}")
        self.actor = User(id=uuid4(), email=f"actor-{uuid4().hex}@example.test",
                          password_hash="test-only", display_name="平台管理员")
        self.member = User(id=uuid4(), email=f"member-{uuid4().hex}@example.test",
                           password_hash="test-only", display_name="原角色成员")
        self.db.add_all([self.tenant, self.actor, self.member])
        self.db.flush()
        # 绿场规则：平台权限只认角色绑定，actor 需显式绑定 L1。
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        self.application = Application(
            id=uuid4(), tenant_id=self.tenant.id, client_id=f"client-{uuid4().hex}",
            name="复制测试应用", redirect_uris=["http://localhost/callback"],
            post_logout_redirect_uris=[], trusted=False,
        )
        self.source = Role(
            id=uuid4(), tenant_id=self.tenant.id, application_id=self.application.id,
            key="source.role", name="源角色", description="源角色说明", status="disabled",
        )
        self.active_permission = Permission(
            id=uuid4(), code=f"clone.read.{uuid4().hex[:8]}",
            resource_type="document", scope="read", status="active",
        )
        self.disabled_permission = Permission(
            id=uuid4(), code=f"clone.admin.{uuid4().hex[:8]}",
            resource_type="document", scope="admin", status="disabled",
        )
        self.group = UserGroup(
            id=uuid4(), tenant_id=self.tenant.id, key="source-group", name="原角色用户组",
        )
        self.db.add_all([
            self.application, self.source, self.active_permission,
            self.disabled_permission, self.group,
        ])
        self.db.flush()
        self.membership = TenantMembership(
            id=uuid4(), tenant_id=self.tenant.id, user_id=self.member.id, status="active",
        )
        self.db.add(self.membership)
        self.db.flush()
        self.db.add_all([
            RoleBinding(membership_id=self.membership.id, role_id=self.source.id),
            UserGroupRole(group_id=self.group.id, role_id=self.source.id, tenant_id=self.tenant.id),
            RolePermission(role_id=self.source.id, permission_id=self.active_permission.id),
            RolePermission(role_id=self.source.id, permission_id=self.active_permission.id,
                           resource_id="document-42"),
            RolePermission(role_id=self.source.id, permission_id=self.disabled_permission.id,
                           resource_id="sensitive-document"),
            RoleDataScope(
                tenant_id=self.tenant.id, role_id=self.source.id,
                permission_id=self.active_permission.id, scope_type="selected_organizations",
                organization_ids=["org-a", "org-b"],
            ),
            RoleDataScope(
                tenant_id=self.tenant.id, role_id=self.source.id,
                permission_id=self.disabled_permission.id, scope_type="tenant",
                organization_ids=[],
            ),
        ])
        self.db.commit()
        self.request = Request({
            "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": f"/api/v1/admin/roles/{self.source.id}/clone",
            "raw_path": f"/api/v1/admin/roles/{self.source.id}/clone".encode(),
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80), "root_path": "",
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def make_request(self, *, copy_authorizations: bool) -> RoleCloneRequest:
        return RoleCloneRequest(
            key=f"copy-{uuid4().hex[:12]}", name="复制角色", description="复制说明",
            copy_authorizations=copy_authorizations,
        )

    def test_default_clone_copies_identity_scope_but_no_grants_or_members(self) -> None:
        result = clone_role(
            self.source.id, self.make_request(copy_authorizations=False),
            self.request, self.actor, self.db,
        )
        clone = self.db.get(Role, UUID(result["id"]))

        self.assertEqual(clone.tenant_id, self.tenant.id)
        self.assertEqual(clone.application_id, self.application.id)
        self.assertEqual((clone.name, clone.description, clone.status),
                         ("复制角色", "复制说明", "disabled"))
        self.assertEqual(self.db.scalars(select(RolePermission).where(
            RolePermission.role_id == clone.id,
        )).all(), [])
        self.assertEqual(self.db.scalars(select(RoleDataScope).where(
            RoleDataScope.role_id == clone.id,
        )).all(), [])
        self.assertEqual(self.db.scalars(select(RoleBinding).where(
            RoleBinding.role_id == clone.id,
        )).all(), [])
        self.assertEqual(self.db.scalars(select(UserGroupRole).where(
            UserGroupRole.role_id == clone.id,
        )).all(), [])
        self.assertIsNotNone(self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.role_id == self.source.id,
        )))
        event = self.db.scalar(select(AuditEvent).where(AuditEvent.action == "role.clone"))
        self.assertEqual(event.target_id, str(clone.id))
        self.assertFalse(event.details["copy_authorizations"])
        self.assertFalse(event.details["copied_member_bindings"])

    def test_explicit_copy_includes_active_instance_grants_and_matching_data_scopes_only(self) -> None:
        result = clone_role(
            self.source.id, self.make_request(copy_authorizations=True),
            self.request, self.actor, self.db,
        )
        clone = self.db.get(Role, UUID(result["id"]))
        grants = self.db.scalars(select(RolePermission).where(
            RolePermission.role_id == clone.id,
        ).order_by(RolePermission.resource_id)).all()
        self.assertEqual(
            {(grant.permission_id, grant.resource_id) for grant in grants},
            {(self.active_permission.id, None), (self.active_permission.id, "document-42")},
        )
        scopes = self.db.scalars(select(RoleDataScope).where(
            RoleDataScope.role_id == clone.id,
        )).all()
        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0].permission_id, self.active_permission.id)
        self.assertEqual(scopes[0].tenant_id, self.tenant.id)
        self.assertEqual(scopes[0].scope_type, "selected_organizations")
        self.assertEqual(scopes[0].organization_ids, ["org-a", "org-b"])
        self.assertEqual(result["copied_permission_grant_count"], 2)
        self.assertEqual(result["copied_data_scope_count"], 1)
        self.assertEqual(self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.role_id == clone.id,
        )), None)
        self.assertEqual(self.db.scalar(select(UserGroupRole.role_id).where(
            UserGroupRole.role_id == clone.id,
        )), None)
        self.assertEqual(clone.status, "disabled")

    def test_duplicate_key_returns_conflict_without_partial_clone_or_audit(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            clone_role(
                self.source.id,
                RoleCloneRequest(key=self.source.key, name="重复标识", copy_authorizations=True),
                self.request, self.actor, self.db,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.db.scalar(select(Role.id).where(Role.id != self.source.id,
                                                              Role.tenant_id == self.tenant.id)), None)
        self.assertIsNone(self.db.scalar(select(AuditEvent.id).where(AuditEvent.action == "role.clone")))

    def test_unknown_source_role_returns_not_found(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            clone_role(uuid4(), self.make_request(copy_authorizations=False),
                       self.request, self.actor, self.db)
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
