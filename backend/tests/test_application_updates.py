"""应用展示资料更新契约与 PostgreSQL 事务集成覆盖。"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.applications import rotate_application_secret, set_application_status, update_application
from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.db.session import get_engine
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.identity import AuditEvent, Tenant, TenantMembership, User
from app.schemas.applications import ApplicationCreate, ApplicationStatusUpdate, ApplicationUpdate


class ApplicationContractTests(unittest.TestCase):
    def test_status_contract_requires_expected_and_target_status(self) -> None:
        self.assertEqual(ApplicationStatusUpdate(expected_status="active", status="disabled").status, "disabled")
        with self.assertRaises(ValidationError):
            ApplicationStatusUpdate(expected_status="active", status="unknown")
        with self.assertRaises(ValidationError):
            ApplicationStatusUpdate(expected_status="active", status="disabled", tenant_id=str(uuid4()))

    def test_status_transition_locks_row_audits_change_and_rejects_stale_page(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        row = SimpleNamespace(id=application_id, tenant_id=tenant_id, status="active")
        db = Mock()
        db.scalar.return_value = row
        request, actor = Mock(), Mock()

        with patch("app.api.v1.admin.applications.has_application_admin_access", return_value=True), patch("app.api.v1.admin.applications.audit") as write_audit, patch(
            "app.api.v1.admin.applications.commit_or_conflict"
        ) as commit:
            result = set_application_status(
                application_id, ApplicationStatusUpdate(expected_status="active", status="disabled"),
                request, actor, db,
            )
            self.assertEqual(result, {"id": str(application_id), "status": "disabled"})
            self.assertEqual(row.status, "disabled")
            locked_query = str(db.scalar.call_args.args[0].compile(dialect=postgresql.dialect()))
            self.assertIn("FOR UPDATE", locked_query)
            revoke_query = str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
            self.assertIn("UPDATE oauth_refresh_tokens", revoke_query)
            write_audit.assert_called_once_with(db, actor, request, "application.status.change", "application",
                str(application_id), {"tenant_id": str(tenant_id), "from_status": "active", "to_status": "disabled"})
            commit.assert_called_once_with(db)

            write_audit.reset_mock()
            commit.reset_mock()
            db.execute.reset_mock()
            with self.assertRaises(HTTPException) as error:
                set_application_status(
                    application_id, ApplicationStatusUpdate(expected_status="active", status="disabled"),
                    request, actor, db,
                )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(row.status, "disabled")
        write_audit.assert_not_called()
        commit.assert_not_called()
        db.execute.assert_not_called()

    def test_application_creation_requires_one_to_twenty_login_redirects(self) -> None:
        payload = {
            "tenant_id": str(uuid4()),
            "name": "Candidate Portal",
            "client_id": "candidate-portal",
            "redirect_uris": ["https://portal.example.test/oidc/callback"],
        }
        self.assertEqual(len(ApplicationCreate(**payload).redirect_uris), 1)
        twenty_redirects = {**payload, "redirect_uris": [
            f"https://portal.example.test/callback/{index}" for index in range(20)
        ]}
        self.assertEqual(len(ApplicationCreate(**twenty_redirects).redirect_uris), 20)

        missing_redirects = {key: value for key, value in payload.items() if key != "redirect_uris"}
        with self.assertRaises(ValidationError):
            ApplicationCreate(**missing_redirects)

        for redirect_uris in ([], [f"https://portal.example.test/callback/{index}" for index in range(21)]):
            with self.subTest(count=len(redirect_uris)), self.assertRaises(ValidationError):
                ApplicationCreate(**{**payload, "redirect_uris": redirect_uris})

    def test_patch_rejects_identity_oauth_configuration_and_secrets(self) -> None:
        forbidden = {
            "tenant_id": str(uuid4()),
            "client_id": "replacement-client",
            "redirect_uris": ["https://example.test/callback"],
            "post_logout_redirect_uris": ["https://example.test/logout"],
            "client_secret": "not-allowed",
            "client_secret_hash": "not-allowed",
            "trusted": True,
            "status": "disabled",
        }
        for field, value in forbidden.items():
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ApplicationUpdate(**{field: value})

    def test_patch_requires_a_field_and_a_nonblank_name(self) -> None:
        with self.assertRaises(ValidationError):
            ApplicationUpdate()
        for name in (None, "   "):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                ApplicationUpdate(name=name)

    def test_description_can_be_cleared(self) -> None:
        self.assertEqual(ApplicationUpdate(description=None).model_dump(exclude_unset=True),
                         {"description": None})


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL integration tests")
class ApplicationUpdateIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.tenant_id, self.user_id, self.application_id = (uuid4() for _ in range(3))
        self.tenant = Tenant(id=self.tenant_id, name="Application Update Test", slug=f"app-{uuid4().hex[:20]}")
        self.actor = User(id=self.user_id, email=f"app-{uuid4().hex}@example.test",
                          password_hash="test-only", display_name="Application Update Test")
        self.application = Application(
            id=self.application_id, tenant_id=self.tenant_id, client_id=f"client-{uuid4().hex[:20]}",
            client_secret_hash="test-secret-hash", name="Original App", description="Original description",
            redirect_uris=["https://app.example.test/callback"],
            post_logout_redirect_uris=["https://app.example.test/logout"], trusted=False, status="active",
        )
        self.db.add_all([self.tenant, self.actor])
        self.db.flush()
        self.membership = TenantMembership(tenant_id=self.tenant_id, user_id=self.user_id)
        self.db.add(self.membership)
        self.db.flush()
        self.db.add(self.application)
        self.db.flush()

        # Application management now goes through the same tenant/application RBAC evaluator
        # as production requests. Seed a realistic app-scoped admin role for these integration cases.
        self.role = Role(
            tenant_id=self.tenant_id, application_id=self.application_id,
            key=f"app-admin-{uuid4().hex[:16]}", name="Application Update Test Admin",
        )
        self.db.add(self.role)
        self.db.flush()
        self.db.add(RoleBinding(membership_id=self.membership.id, role_id=self.role.id))
        for code, resource_type, scope in (
            ("app.manage", "iam.application", "manage"),
            ("app.secret.rotate", "iam.application", "secret.rotate"),
        ):
            permission = self.db.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                # 绿场规则：iam.* 为管理面码，不强制数据范围。
                permission = Permission(code=code, resource_type=resource_type, scope=scope,
                                        surface="management", requires_data_scope=False)
                self.db.add(permission)
                self.db.flush()
            self.db.add(RolePermission(role_id=self.role.id, permission_id=permission.id))
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def test_patch_preserves_client_identity_and_oauth_configuration(self) -> None:
        request = Request({
            "type": "http", "http_version": "1.1", "method": "PATCH", "scheme": "http",
            "path": f"/api/v1/admin/applications/{self.application_id}",
            "raw_path": f"/api/v1/admin/applications/{self.application_id}".encode(),
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80), "root_path": "",
        })
        result = update_application(
            self.application_id, ApplicationUpdate(name="Updated App", description=None),
            request, self.actor, self.db,
        )

        self.db.refresh(self.application)
        audit_event = self.db.scalar(select(AuditEvent).where(AuditEvent.action == "application.update"))
        self.assertEqual(self.application.name, "Updated App")
        self.assertIsNone(self.application.description)
        self.assertEqual(self.application.tenant_id, self.tenant_id)
        self.assertEqual(self.application.client_id, result["client_id"])
        self.assertEqual(self.application.client_secret_hash, "test-secret-hash")
        self.assertEqual(self.application.redirect_uris, ["https://app.example.test/callback"])
        self.assertEqual(self.application.post_logout_redirect_uris, ["https://app.example.test/logout"])
        self.assertFalse(self.application.trusted)
        self.assertEqual(self.application.status, "active")
        self.assertEqual(result["updated_fields"], ["description", "name"])
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.details["updated_fields"], ["description", "name"])
        self.assertNotIn("client_secret_hash", result)
        self.assertNotIn("client_secret_hash", audit_event.details)

    def test_secret_rotation_replaces_hash_and_only_audits_the_operation(self) -> None:
        old_secret = f"old-secret-{uuid4().hex}"
        self.application.client_secret_hash = hash_password(old_secret)
        self.db.flush()
        request = Request({
            "type": "http", "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": f"/api/v1/admin/applications/{self.application_id}/rotate-secret",
            "raw_path": f"/api/v1/admin/applications/{self.application_id}/rotate-secret".encode(),
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80), "root_path": "",
        })

        response = Response()
        result = rotate_application_secret(self.application_id, request, response, self.actor, self.db)

        self.db.refresh(self.application)
        audit_event = self.db.scalar(
            select(AuditEvent).where(AuditEvent.action == "application.secret.rotate")
        )
        self.assertGreaterEqual(len(result["client_secret"]), 48)
        self.assertTrue(verify_password(result["client_secret"], self.application.client_secret_hash))
        self.assertFalse(verify_password(old_secret, self.application.client_secret_hash))
        self.assertEqual(result["client_id"], self.application.client_id)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")
        self.assertIsNotNone(audit_event)
        self.assertNotIn(result["client_secret"], str(audit_event.details))
        self.assertNotIn(self.application.client_secret_hash, str(audit_event.details))
        self.assertEqual(audit_event.details["tenant_id"], str(self.tenant_id))


if __name__ == "__main__":
    unittest.main()
