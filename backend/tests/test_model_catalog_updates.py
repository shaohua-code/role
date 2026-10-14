"""模型目录元数据更新的契约与 PostgreSQL 事务集成覆盖。"""

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

from app.api.v1.admin.models import set_model_status, update_model
from app.core.config import get_settings
from app.db.session import get_engine
from app.models.identity import AuditEvent, Tenant, User
from app.models.model_catalog import ModelCatalog
from app.schemas.models import ModelCatalogStatusUpdate, ModelCatalogUpdate


class ModelCatalogUpdateContractTests(unittest.TestCase):
    def test_patch_allows_quota_values_but_rejects_tenant_and_identity_fields(self) -> None:
        self.assertEqual(ModelCatalogUpdate(rpm_limit=10, tpm_limit=None).rpm_limit, 10)
        self.assertIsNone(ModelCatalogUpdate(tpm_limit=None).tpm_limit)
        with self.assertRaises(ValidationError):
            ModelCatalogUpdate(tenant_id=str(uuid4()))
        with self.assertRaises(ValidationError):
            ModelCatalogUpdate(key="replacement-model")

    def test_patch_requires_at_least_one_field(self) -> None:
        with self.assertRaises(ValidationError):
            ModelCatalogUpdate()

    def test_status_patch_requires_expected_state_and_rejects_unknown_fields(self) -> None:
        body = ModelCatalogStatusUpdate(expected_status="active", status="disabled")
        self.assertEqual(body.expected_status, "active")
        with self.assertRaises(ValidationError):
            ModelCatalogStatusUpdate(expected_status="active", status="unknown")
        with self.assertRaises(ValidationError):
            ModelCatalogStatusUpdate(expected_status="active", status="disabled", tenant_id=str(uuid4()))

    def test_status_transition_is_audited_and_stale_state_conflicts_without_mutation(self) -> None:
        model_id, tenant_id = uuid4(), uuid4()
        row = SimpleNamespace(id=model_id, tenant_id=tenant_id, status="active")
        db = Mock()
        db.scalar.return_value = row
        request, actor = Mock(), Mock()

        with patch("app.api.v1.admin.models.audit") as write_audit, patch(
            "app.api.v1.admin.models.commit_or_conflict"
        ) as commit:
            result = set_model_status(
                model_id, ModelCatalogStatusUpdate(expected_status="active", status="disabled"),
                request, actor, db,
            )

            self.assertEqual(result, {"id": str(model_id), "status": "disabled"})
            self.assertEqual(row.status, "disabled")
            locked_query = str(db.scalar.call_args.args[0].compile(dialect=postgresql.dialect()))
            self.assertIn("FOR UPDATE", locked_query)
            write_audit.assert_called_once_with(db, actor, request, "model.status.change", "model", str(model_id), {
                "tenant_id": str(tenant_id), "from_status": "active", "to_status": "disabled",
            })
            commit.assert_called_once_with(db)

            write_audit.reset_mock()
            commit.reset_mock()
            with self.assertRaises(HTTPException) as error:
                set_model_status(
                    model_id, ModelCatalogStatusUpdate(expected_status="active", status="disabled"),
                    request, actor, db,
                )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(row.status, "disabled")
        write_audit.assert_not_called()
        commit.assert_not_called()


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL integration tests")
class ModelCatalogUpdateIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.tenant_id, self.user_id, self.model_id = uuid4(), uuid4(), uuid4()
        self.secret_ref = f"vault://team/{uuid4().hex}"
        self.tenant = Tenant(id=self.tenant_id, name="Model Update Test", slug=f"model-{uuid4().hex[:20]}")
        self.actor = User(id=self.user_id, email=f"model-{uuid4().hex}@example.test",
                          password_hash="test-only", display_name="Model Update Test")
        self.model = ModelCatalog(
            id=self.model_id, tenant_id=self.tenant_id, key="fixed-model-key", provider="original-provider",
            model_name="original-model", display_name="Original Model", endpoint_url="https://old.example.test",
            credential_ref="vault://team/original", capabilities=["chat"], rpm_limit=17, tpm_limit=2400,
            input_cost_per_million=0.25, output_cost_per_million=0.5, status="active",
        )
        self.db.add_all([self.tenant, self.actor])
        self.db.flush()
        self.db.add(self.model)
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def test_metadata_patch_preserves_identity_updates_limits_and_never_exposes_secret(self) -> None:
        request = Request({
            "type": "http", "http_version": "1.1", "method": "PATCH", "scheme": "http",
            "path": f"/api/v1/admin/models/{self.model_id}", "raw_path": f"/api/v1/admin/models/{self.model_id}".encode(),
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345), "server": ("testserver", 80),
            "root_path": "",
        })
        result = update_model(
            self.model_id,
            ModelCatalogUpdate(provider="updated-provider", display_name="Updated Model",
                               credential_ref=self.secret_ref, input_cost_per_million=None,
                               rpm_limit=None, tpm_limit=1200),
            request,
            self.actor,
            self.db,
        )

        self.db.refresh(self.model)
        audit_event = self.db.scalar(select(AuditEvent).where(AuditEvent.action == "model.update"))
        self.assertEqual(self.model.provider, "updated-provider")
        self.assertEqual(self.model.display_name, "Updated Model")
        self.assertIsNone(self.model.input_cost_per_million)
        self.assertEqual(self.model.tenant_id, self.tenant_id)
        self.assertEqual(self.model.key, "fixed-model-key")
        self.assertIsNone(self.model.rpm_limit)
        self.assertEqual(self.model.tpm_limit, 1200)
        self.assertNotIn("credential_ref", result)
        self.assertNotIn(self.secret_ref, str(result))
        self.assertIsNotNone(audit_event)
        self.assertNotIn(self.secret_ref, str(audit_event.details))
        self.assertEqual(audit_event.details["updated_fields"], [
            "credential_ref", "display_name", "input_cost_per_million", "provider", "rpm_limit", "tpm_limit",
        ])

    def test_status_transition_rejects_stale_admin_page_and_audits_only_applied_change(self) -> None:
        request = Request({
            "type": "http", "http_version": "1.1", "method": "PATCH", "scheme": "http",
            "path": f"/api/v1/admin/models/{self.model_id}/status",
            "raw_path": f"/api/v1/admin/models/{self.model_id}/status".encode(),
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80), "root_path": "",
        })

        result = set_model_status(
            self.model_id, ModelCatalogStatusUpdate(expected_status="active", status="disabled"),
            request, self.actor, self.db,
        )
        self.assertEqual(result["status"], "disabled")

        with self.assertRaises(HTTPException) as error:
            set_model_status(
                self.model_id, ModelCatalogStatusUpdate(expected_status="active", status="disabled"),
                request, self.actor, self.db,
            )
        self.assertEqual(error.exception.status_code, 409)
        self.db.refresh(self.model)
        self.assertEqual(self.model.status, "disabled")
        events = self.db.scalars(select(AuditEvent).where(AuditEvent.action == "model.status.change")).all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].details["from_status"], "active")
        self.assertEqual(events[0].details["to_status"], "disabled")


if __name__ == "__main__":
    unittest.main()
