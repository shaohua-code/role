"""角色展示信息更新的输入契约和 PostgreSQL 事务集成覆盖。"""

import unittest
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.access_control import update_role
from app.core.config import get_settings
from app.db.session import get_engine
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import AuditEvent, Tenant, User
from app.schemas.access_control import RoleUpdate


class RoleUpdateContractTests(unittest.TestCase):
    def test_patch_rejects_role_identity_and_authorization_fields(self) -> None:
        for field, value in (("tenant_id", str(uuid4())), ("application_id", str(uuid4())),
                             ("key", "renamed"), ("permission_ids", [str(uuid4())])):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RoleUpdate(**{field: value})

    def test_patch_requires_a_field_and_name_cannot_be_blank(self) -> None:
        with self.assertRaises(ValidationError):
            RoleUpdate()
        for name in (None, "   "):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RoleUpdate(name=name)

    def test_description_can_be_explicitly_cleared(self) -> None:
        patch = RoleUpdate(description=None)
        self.assertEqual(patch.model_dump(exclude_unset=True), {"description": None})


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL integration tests")
class RoleUpdateIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.tenant_id, self.user_id, self.role_id, self.permission_id = (uuid4() for _ in range(4))
        self.tenant = Tenant(id=self.tenant_id, name="Role Update Test", slug=f"role-{uuid4().hex[:20]}")
        self.actor = User(id=self.user_id, email=f"role-{uuid4().hex}@example.test",
                          password_hash="test-only", display_name="Role Update Test")
        self.role = Role(id=self.role_id, tenant_id=self.tenant_id, application_id=None,
                         key="immutable-key", name="Original Role", description="Original description")
        self.permission = Permission(id=self.permission_id, code=f"role.update.{uuid4().hex[:8]}",
                                     resource_type="role", scope="update")
        self.db.add_all([self.tenant, self.actor])
        self.db.flush()
        # 绿场规则：actor 需显式绑定 L1 才能通过按码判权。
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        self.db.add_all([self.role, self.permission])
        self.db.flush()
        self.grant = RolePermission(role_id=self.role_id, permission_id=self.permission_id)
        self.db.add(self.grant)
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def test_patch_changes_description_and_name_without_touching_identity_or_grants(self) -> None:
        request = Request({
            "type": "http", "http_version": "1.1", "method": "PATCH", "scheme": "http",
            "path": f"/api/v1/admin/roles/{self.role_id}", "raw_path": f"/api/v1/admin/roles/{self.role_id}".encode(),
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
            "root_path": "",
        })
        result = update_role(self.role_id, RoleUpdate(name="Updated Role", description=None),
                             request, self.actor, self.db)

        self.db.refresh(self.role)
        audit_event = self.db.scalar(select(AuditEvent).where(AuditEvent.action == "role.update"))
        self.assertEqual(self.role.name, "Updated Role")
        self.assertIsNone(self.role.description)
        self.assertEqual(self.role.tenant_id, self.tenant_id)
        self.assertEqual(self.role.application_id, None)
        self.assertEqual(self.role.key, "immutable-key")
        self.assertEqual(self.db.scalar(select(RolePermission.id).where(RolePermission.role_id == self.role_id)), self.grant.id)
        self.assertEqual(result["updated_fields"], ["description", "name"])
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.details["updated_fields"], ["description", "name"])


if __name__ == "__main__":
    unittest.main()
