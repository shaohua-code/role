"""用隔离 SQLite 验证用户组管理路由的租户校验、幂等写入和审计。"""

import unittest
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.db.base import Base
from app.models import AuditEvent, Role, Tenant, TenantMembership, User
from app.models.groups import UserGroupMembership, UserGroupRole
from app.schemas.groups import UserGroupCreate, UserGroupMembersUpdate, UserGroupRolesUpdate, UserGroupUpdate
from app.api.v1.admin.groups import (
    create_user_group,
    list_user_group_members,
    list_user_group_roles,
    replace_user_group_members,
    replace_user_group_roles,
    set_user_group_status,
    update_user_group,
)


class UserGroupAdminTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不改动本地开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="租户 A", slug=f"groups-a-{uuid4().hex[:10]}")
        self.other_tenant = Tenant(name="租户 B", slug=f"groups-b-{uuid4().hex[:10]}")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only", display_name="管理员")
        self.member = User(email=f"member-{uuid4().hex}@example.test", password_hash="test-only", display_name="成员")
        self.foreign_member = User(email=f"foreign-{uuid4().hex}@example.test", password_hash="test-only", display_name="异租户成员")
        self.role = Role(tenant_id=None, key=f"role-{uuid4().hex[:8]}", name="组角色")
        self.foreign_role = Role(tenant_id=None, key=f"role-{uuid4().hex[:8]}", name="异租户角色")
        self.db.add_all([self.tenant, self.other_tenant, self.actor, self.member, self.foreign_member])
        self.db.flush()
        self.role.tenant_id = self.tenant.id
        self.foreign_role.tenant_id = self.other_tenant.id
        self.db.add_all([self.role, self.foreign_role,
                         TenantMembership(tenant_id=self.tenant.id, user_id=self.member.id),
                         TenantMembership(tenant_id=self.other_tenant.id, user_id=self.foreign_member.id)])
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "PUT", "path": "/api/v1/admin/groups",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })
        self.group = create_user_group(
            UserGroupCreate(tenant_id=self.tenant.id, key=f"team-{uuid4().hex[:8]}", name="产品组"),
            self.request, actor=self.actor, db=self.db,
        )
        self.group_id = UUID(self.group["id"])

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_member_and_role_replacement_are_idempotent_and_audited(self) -> None:
        first_members = replace_user_group_members(
            self.group_id,
            UserGroupMembersUpdate(user_ids=[self.member.id]),
            self.request, actor=self.actor, db=self.db,
        )
        self.assertTrue(first_members["changed"])
        repeated_members = replace_user_group_members(
            self.group_id,
            UserGroupMembersUpdate(user_ids=[self.member.id]),
            self.request, actor=self.actor, db=self.db,
        )
        self.assertFalse(repeated_members["changed"])
        self.assertTrue(list_user_group_members(self.group_id, self.db)[0]["in_group"])

        result = replace_user_group_roles(
            self.group_id,
            UserGroupRolesUpdate(role_ids=[self.role.id]),
            self.request, actor=self.actor, db=self.db,
        )
        self.assertTrue(result["changed"])
        self.assertTrue(next(row for row in list_user_group_roles(self.group_id, self.db)
                             if row["id"] == str(self.role.id))["assigned"])
        actions = set(self.db.scalars(select(AuditEvent.action)).all())
        self.assertTrue({"user_group.create", "user_group.members.replace", "user_group.roles.replace"}.issubset(actions))

    def test_cross_tenant_member_and_role_are_rejected_without_audit(self) -> None:
        with self.assertRaises(HTTPException) as member_error:
            replace_user_group_members(
                self.group_id,
                UserGroupMembersUpdate(user_ids=[self.foreign_member.id]),
                self.request, actor=self.actor, db=self.db,
            )
        self.assertEqual(member_error.exception.status_code, 422)

        with self.assertRaises(HTTPException) as role_error:
            replace_user_group_roles(
                self.group_id,
                UserGroupRolesUpdate(role_ids=[self.foreign_role.id]),
                self.request, actor=self.actor, db=self.db,
            )
        self.assertEqual(role_error.exception.status_code, 422)
        self.db.rollback()
        actions = set(self.db.scalars(select(AuditEvent.action)).all())
        self.assertEqual(actions, {"user_group.create"})

    def test_disabling_group_preserves_configured_members_and_roles(self) -> None:
        group_id = self.group_id
        replace_user_group_members(group_id, UserGroupMembersUpdate(user_ids=[self.member.id]),
                                   self.request, actor=self.actor, db=self.db)
        replace_user_group_roles(group_id, UserGroupRolesUpdate(role_ids=[self.role.id]),
                                 self.request, actor=self.actor, db=self.db)
        disabled = set_user_group_status(group_id, "disabled", self.request, actor=self.actor, db=self.db)
        self.assertEqual(disabled["status"], "disabled")
        self.assertEqual(self.db.scalar(select(UserGroupMembership.group_id).where(
            UserGroupMembership.group_id == group_id)), group_id)
        self.assertEqual(self.db.scalar(select(UserGroupRole.role_id).where(
            UserGroupRole.group_id == group_id)), self.role.id)

    def test_unchanged_group_patch_does_not_write_duplicate_audit(self) -> None:
        update = UserGroupUpdate(name="新产品组", description=None)
        update_user_group(self.group_id, update, self.request, actor=self.actor, db=self.db)
        audit_ids = self.db.scalars(select(AuditEvent.id).where(
            AuditEvent.action == "user_group.update"
        )).all()
        self.assertEqual(len(audit_ids), 1)
        update_user_group(self.group_id, update, self.request, actor=self.actor, db=self.db)
        current_audit_ids = self.db.scalars(select(AuditEvent.id).where(
            AuditEvent.action == "user_group.update"
        )).all()
        self.assertEqual(len(current_audit_ids), len(audit_ids))


if __name__ == "__main__":
    unittest.main()
