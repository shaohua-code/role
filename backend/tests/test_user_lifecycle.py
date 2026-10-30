"""账号与租户成员生命周期的 API 契约和事务边界测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.admin.organizations import set_user_membership_status
from app.api.v1.admin.users import set_user_status
from app.core.config import get_settings
from app.db.session import get_engine
from app.models.identity import Tenant, TenantMembership, User
from app.schemas.auth import UserStatusUpdate
from app.schemas.organizations import MembershipStatusUpdate


class UserStatusContractTests(unittest.TestCase):
    def test_global_and_tenant_statuses_are_separate_and_forbid_extra_fields(self) -> None:
        self.assertEqual(UserStatusUpdate(expected_status="active", status="locked").status, "locked")
        self.assertEqual(MembershipStatusUpdate(expected_status="active", status="departed").status, "departed")
        for payload in (
            {"expected_status": "active", "status": "departed"},
            {"expected_status": "active", "status": "deleted"},
            {"expected_status": "active", "status": "locked", "tenant_id": str(uuid4())},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                UserStatusUpdate(**payload)
        with self.assertRaises(ValidationError):
            MembershipStatusUpdate(expected_status="active", status="disabled", user_id=str(uuid4()))

    def test_global_lock_increments_identity_version_revokes_credentials_and_audits(self) -> None:
        user_id, actor_id = uuid4(), uuid4()
        row = SimpleNamespace(id=user_id, status="active", auth_version=8)
        db, request, actor = Mock(), Mock(), SimpleNamespace(id=actor_id)
        db.scalar.return_value = row

        # 绿场规则：平台权限只认角色绑定；Mock 契约测试直接假定 actor 持 L1。
        with patch("app.services.rbac_guards.user_is_platform_admin", return_value=True), \
             patch("app.api.v1.admin.users.audit") as write_audit, patch(
            "app.api.v1.admin.users.commit_or_conflict"
        ) as commit, patch("app.api.v1.admin.users.deliver_for_user"):
            # 全局锁定后还会做站内信 back-channel 投递，Mock db 无法承载其内部查询，需一并打桩。
            result = set_user_status(
                user_id, UserStatusUpdate(expected_status="active", status="locked"), request, actor, db,
            )

        self.assertEqual(result, {"id": str(user_id), "status": "locked", "auth_version": 9})
        self.assertEqual(row.status, "locked")
        self.assertEqual(row.auth_version, 9)
        self.assertIn("FOR UPDATE", str(db.scalar.call_args.args[0].compile(dialect=postgresql.dialect())))
        statements = [str(call.args[0].compile(dialect=postgresql.dialect())) for call in db.execute.call_args_list]
        self.assertEqual(len(statements), 4)
        self.assertIn("UPDATE refresh_sessions", statements[0])
        self.assertIn("UPDATE oauth_refresh_tokens", statements[1])
        self.assertIn("UPDATE oauth_authorization_codes", statements[2])
        self.assertIn("UPDATE oauth_consent_requests", statements[3])
        write_audit.assert_called_once_with(db, actor, request, "user.status.change", "user", str(user_id), {
            "from_status": "active", "to_status": "locked",
        })
        commit.assert_called_once_with(db)

    def test_global_status_rejects_stale_page_and_self_lock_without_mutation(self) -> None:
        user_id, actor_id = uuid4(), uuid4()
        row = SimpleNamespace(id=user_id, status="disabled", auth_version=2)
        db, request, actor = Mock(), Mock(), SimpleNamespace(id=actor_id)
        db.scalar.return_value = row
        with patch("app.services.rbac_guards.user_is_platform_admin", return_value=True), \
             patch("app.api.v1.admin.users.audit") as write_audit, patch(
            "app.api.v1.admin.users.commit_or_conflict"
        ) as commit:
            with self.assertRaises(HTTPException) as stale:
                set_user_status(user_id, UserStatusUpdate(expected_status="active", status="locked"), request, actor, db)
            self.assertEqual(stale.exception.status_code, 409)
            db.scalar.return_value = SimpleNamespace(id=actor_id, status="active", auth_version=1)
            with self.assertRaises(HTTPException) as self_lock:
                set_user_status(actor_id, UserStatusUpdate(expected_status="active", status="locked"), request,
                                SimpleNamespace(id=actor_id), db)

        self.assertEqual(self_lock.exception.status_code, 400)
        db.execute.assert_not_called()


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL lifecycle tests")
class UserLifecycleConstraintIntegrationTests(unittest.TestCase):
    """确保 Alembic 状态约束在真实 PostgreSQL 而不只是 Pydantic 层生效。"""

    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.tenant = Tenant(name="Lifecycle Constraint Test", slug=f"life-{uuid4().hex[:24]}")
        self.user = User(email=f"lifecycle-{uuid4().hex}@example.test", password_hash="test-only",
                         display_name="Lifecycle Test", status="active")
        self.db.add_all([self.tenant, self.user])
        self.db.flush()
        self.membership = TenantMembership(tenant_id=self.tenant.id, user_id=self.user.id, status="active")
        self.db.add(self.membership)
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def test_database_rejects_mixed_global_and_membership_states(self) -> None:
        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.user.status = "departed"
                self.db.flush()
        self.db.refresh(self.user)
        self.assertEqual(self.user.status, "active")

        with self.assertRaises(IntegrityError):
            with self.db.begin_nested():
                self.membership.status = "locked"
                self.db.flush()
        self.db.refresh(self.membership)
        self.assertEqual(self.membership.status, "active")

    def test_departure_clears_tenant_grants_and_revokes_only_tenant_oauth(self) -> None:
        user_id, tenant_id, membership_id = uuid4(), uuid4(), uuid4()
        row = SimpleNamespace(id=membership_id, user_id=user_id, tenant_id=tenant_id,
                              status="active", auth_version=1)
        db, request, actor = Mock(), Mock(), SimpleNamespace(id=uuid4())
        db.scalar.return_value = row

        with patch("app.api.v1.admin.organizations.require_organization_admin_access") as require_access, patch(
            "app.api.v1.admin.organizations.audit"
        ) as write_audit, patch(
            "app.api.v1.admin.organizations.commit_or_conflict"
        ) as commit:
            result = set_user_membership_status(
                user_id, tenant_id, MembershipStatusUpdate(expected_status="active", status="departed"),
                request, actor, db,
            )

        require_access.assert_called_once_with(actor, tenant_id, db, manage=True)
        self.assertEqual(result, {
            "user_id": str(user_id), "tenant_id": str(tenant_id),
            "status": "departed", "membership_version": 2,
        })
        self.assertEqual(row.status, "departed")
        self.assertEqual(row.auth_version, 2)
        self.assertIn("FOR UPDATE", str(db.scalar.call_args.args[0].compile(dialect=postgresql.dialect())))
        statements = [str(call.args[0].compile(dialect=postgresql.dialect())) for call in db.execute.call_args_list]
        self.assertEqual(len(statements), 6)
        self.assertIn("UPDATE oauth_refresh_tokens", statements[0])
        self.assertIn("UPDATE oauth_authorization_codes", statements[1])
        self.assertIn("UPDATE oauth_consent_requests", statements[2])
        self.assertIn("DELETE FROM role_bindings", statements[3])
        self.assertIn("DELETE FROM user_group_memberships", statements[4])
        self.assertIn("DELETE FROM membership_organizations", statements[5])
        write_audit.assert_called_once_with(db, actor, request, "membership.status.change", "user", str(user_id), {
            "tenant_id": str(tenant_id), "from_status": "active", "to_status": "departed",
        })
        commit.assert_called_once_with(db)

    def test_departure_rejects_stale_state_and_departed_reactivation(self) -> None:
        user_id, tenant_id = uuid4(), uuid4()
        row = SimpleNamespace(id=uuid4(), user_id=user_id, tenant_id=tenant_id, status="disabled")
        db, request, actor = Mock(), Mock(), SimpleNamespace(id=uuid4())
        db.scalar.return_value = row
        with patch("app.api.v1.admin.organizations.require_organization_admin_access"), patch(
            "app.api.v1.admin.organizations.audit"
        ) as write_audit, patch(
            "app.api.v1.admin.organizations.commit_or_conflict"
        ) as commit:
            with self.assertRaises(HTTPException) as stale:
                set_user_membership_status(
                    user_id, tenant_id, MembershipStatusUpdate(expected_status="active", status="departed"),
                    request, actor, db,
                )
            self.assertEqual(stale.exception.status_code, 409)
            db.scalar.return_value = SimpleNamespace(
                id=uuid4(), user_id=user_id, tenant_id=tenant_id, status="departed",
            )
            with self.assertRaises(HTTPException) as reactivation:
                set_user_membership_status(
                    user_id, tenant_id, MembershipStatusUpdate(expected_status="departed", status="active"),
                    request, actor, db,
                )

        self.assertEqual(reactivation.exception.status_code, 409)
        db.execute.assert_not_called()
        write_audit.assert_not_called()
        commit.assert_not_called()

    def test_membership_status_requires_tenant_manage_permission_before_row_lock(self) -> None:
        user_id, tenant_id = uuid4(), uuid4()
        db, request, actor = Mock(), Mock(), SimpleNamespace(id=uuid4())
        with patch("app.api.v1.admin.organizations.require_organization_admin_access",
                   side_effect=HTTPException(403, "forbidden")):
            with self.assertRaises(HTTPException) as error:
                set_user_membership_status(
                    user_id, tenant_id,
                    MembershipStatusUpdate(expected_status="active", status="departed"),
                    request, actor, db,
                )

        self.assertEqual(error.exception.status_code, 403)
        db.scalar.assert_not_called()
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
