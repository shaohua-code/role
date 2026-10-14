"""模型网关配额预留/结算契约与 PostgreSQL 事务测试。"""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.model_usage import (
    list_model_usage_events,
    list_model_usage_reviews,
    resolve_model_usage_review,
)
from app.api.v1.model_usage import reserve_usage, settle_usage
from app.core.config import get_settings
from app.db.session import get_engine
from app.models.application import Application
from app.models.identity import AuditEvent, Tenant, TenantMembership, User
from app.models.model_catalog import ModelCatalog, ModelUsageEvent, ModelUsageReservation
from app.schemas.models import ModelUsageReservationRequest, ModelUsageReviewRequest, ModelUsageSettlementRequest


class ModelUsageQuotaContractTests(unittest.TestCase):
    def test_reservation_requires_full_authorization_context(self) -> None:
        with self.assertRaises(ValidationError):
            ModelUsageReservationRequest(
                request_id="request-123", model_id=str(uuid4()),
                reserved_input_tokens=12, reserved_output_tokens=30,
            )

    def test_settlement_rejects_negative_token_usage(self) -> None:
        with self.assertRaises(ValidationError):
            ModelUsageSettlementRequest(
                request_id="request-123", input_tokens=-1, output_tokens=0,
                outcome="failed", latency_ms=1,
            )

    def test_release_requires_explicit_provider_not_called_confirmation(self) -> None:
        with self.assertRaises(ValidationError):
            ModelUsageReviewRequest(
                request_id="review-request-0001", decision="release", reason="provider logs",
            )

    def test_manual_settlement_requires_actual_or_estimated_token_counts(self) -> None:
        with self.assertRaises(ValidationError):
            ModelUsageReviewRequest(
                request_id="review-request-0001", decision="settle", reason="provider logs",
            )

    def test_usage_event_list_returns_page_metadata_and_clamps_bounds(self) -> None:
        db = Mock()
        db.scalar.return_value = 451
        db.execute.return_value.all.return_value = []

        page = list_model_usage_events(limit=500, offset=-3, db=db)

        self.assertEqual(page, {"items": [], "total": 451, "limit": 200, "offset": 0})
        db.scalar.assert_called_once()
        db.execute.assert_called_once()


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is required for PostgreSQL integration tests")
class ModelUsageQuotaIntegrationTests(unittest.TestCase):
    gateway_key = "test-only-model-gateway-key-0123456789"

    def setUp(self) -> None:
        self.connection = get_engine().connect()
        self.outer_transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.tenant_id, self.user_id, self.application_id, self.model_id = (
            uuid4(), uuid4(), uuid4(), uuid4())
        self.tenant = Tenant(id=self.tenant_id, name="Quota Test", slug=f"quota-{uuid4().hex[:20]}")
        self.user = User(id=self.user_id, email=f"quota-{uuid4().hex}@example.test",
                         password_hash="test-only", display_name="Quota Test")
        self.membership = TenantMembership(
            id=uuid4(), tenant_id=self.tenant_id, user_id=self.user_id, status="active")
        self.application = Application(
            id=self.application_id, tenant_id=self.tenant_id, client_id=f"quota-{uuid4().hex}",
            name="Quota Test App", status="active")
        self.model = ModelCatalog(
            id=self.model_id, tenant_id=self.tenant_id, key="quota-test-model", provider="test",
            model_name="test-model", display_name="Quota Test Model", capabilities=["chat"],
            rpm_limit=1, tpm_limit=10_000, status="active")
        # 显式按外键依赖分层 flush，避免测试夹具依赖 ORM 未配置的对象排序。
        self.db.add_all([self.tenant, self.user])
        self.db.flush()
        self.db.add_all([self.membership, self.application])
        self.db.flush()
        self.db.add(self.model)
        self.db.flush()
        self.enabled_settings = SimpleNamespace(
            model_usage_api_key=self.gateway_key, model_quota_enforcement_enabled=True)

    def tearDown(self) -> None:
        self.db.close()
        self.outer_transaction.rollback()
        self.connection.close()

    def request(self, request_id: str, input_tokens: int = 10,
                output_tokens: int = 20) -> ModelUsageReservationRequest:
        return ModelUsageReservationRequest(
            request_id=request_id, tenant_id=self.tenant_id, model_id=self.model_id,
            application_id=self.application_id, user_id=self.user_id,
            reserved_input_tokens=input_tokens, reserved_output_tokens=output_tokens)

    def test_reservation_is_idempotent_and_rpm_limit_rejects_next_request(self) -> None:
        with patch("app.api.v1.model_usage.get_settings", return_value=self.enabled_settings):
            first = reserve_usage(self.request("rpm-request-0001"), self.gateway_key, self.db)
            retry = reserve_usage(self.request("rpm-request-0001"), self.gateway_key, self.db)
            self.assertTrue(first["reservation_required"])
            self.assertTrue(retry["duplicate"])
            with self.assertRaises(HTTPException) as conflict:
                reserve_usage(self.request("rpm-request-0001", 11, 20), self.gateway_key, self.db)
            with self.assertRaises(HTTPException) as raised:
                reserve_usage(self.request("rpm-request-0002"), self.gateway_key, self.db)

        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.headers["Retry-After"], "60")
        self.assertEqual(raised.exception.detail["dimensions"], ["rpm"])
        self.assertEqual(self.db.query(ModelUsageReservation).count(), 1)

    def test_tpm_limit_counts_active_estimated_tokens(self) -> None:
        self.model.rpm_limit = None
        self.model.tpm_limit = 50
        self.db.flush()
        with patch("app.api.v1.model_usage.get_settings", return_value=self.enabled_settings):
            reserve_usage(self.request("tpm-request-0001", 10, 30), self.gateway_key, self.db)
            with self.assertRaises(HTTPException) as raised:
                reserve_usage(self.request("tpm-request-0002", 8, 3), self.gateway_key, self.db)

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.detail["dimensions"], ["tpm"])

    def test_settlement_writes_usage_once_and_reports_overrun(self) -> None:
        body = self.request("settle-request-0001", 10, 20)
        usage = ModelUsageSettlementRequest(
            request_id=body.request_id, input_tokens=12, output_tokens=18,
            outcome="succeeded", latency_ms=250)
        with patch("app.api.v1.model_usage.get_settings", return_value=self.enabled_settings):
            reserve_usage(body, self.gateway_key, self.db)
            settled = settle_usage(usage, self.gateway_key, self.db)
            retry = settle_usage(usage, self.gateway_key, self.db)

        self.assertTrue(settled["settled"])
        self.assertTrue(settled["overrun"])
        self.assertFalse(retry["settled"])
        self.assertTrue(retry["duplicate"])
        self.assertEqual(self.db.query(ModelUsageReservation).one().status, "settled")

    def test_disabled_flag_still_persists_a_reviewable_reservation(self) -> None:
        disabled_settings = SimpleNamespace(
            model_usage_api_key=self.gateway_key, model_quota_enforcement_enabled=False)
        with patch("app.api.v1.model_usage.get_settings", return_value=disabled_settings):
            result = reserve_usage(self.request("disabled-request-0001"), self.gateway_key, self.db)

        self.assertTrue(result["allowed"])
        self.assertFalse(result["enforced"])
        self.assertTrue(result["reservation_required"])
        self.assertEqual(self.db.query(ModelUsageReservation).count(), 1)

    def test_expired_unresolved_reservation_remains_in_tpm_window(self) -> None:
        self.model.rpm_limit = None
        self.model.tpm_limit = 45
        self.db.flush()
        with patch("app.api.v1.model_usage.get_settings", return_value=self.enabled_settings):
            reserve_usage(self.request("expired-pending-0001", 10, 20), self.gateway_key, self.db)
            row = self.db.query(ModelUsageReservation).one()
            row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            self.db.flush()
            with self.assertRaises(HTTPException) as raised:
                reserve_usage(self.request("expired-pending-0002", 15, 1), self.gateway_key, self.db)

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.detail["dimensions"], ["tpm"])

    def test_admin_can_reconcile_expired_reservation_with_audit(self) -> None:
        with patch("app.api.v1.model_usage.get_settings", return_value=self.enabled_settings):
            reserve_usage(self.request("review-settle-0001"), self.gateway_key, self.db)
        row = self.db.query(ModelUsageReservation).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.db.flush()
        visible = list_model_usage_reviews(tenant_id=self.tenant_id, db=self.db)
        self.assertEqual(visible["total"], 1)
        self.assertEqual([item["request_id"] for item in visible["items"]], [row.request_id])

        request = Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": "/api/v1/admin/model-usage/reviews", "raw_path": b"/api/v1/admin/model-usage/reviews",
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 1234),
            "server": ("localhost", 80),
        })
        body = ModelUsageReviewRequest(
            request_id=row.request_id, decision="settle", reason="checked provider usage log",
            input_tokens=12, output_tokens=18, outcome="succeeded", usage_is_estimated=True,
        )
        result = resolve_model_usage_review(body, request, actor=self.user, db=self.db)

        event = self.db.query(ModelUsageEvent).one()
        audit_event = self.db.query(AuditEvent).filter(
            AuditEvent.action == "model_usage.review.settle").one()
        self.assertEqual(result["status"], "settled")
        self.assertEqual(event.source, "admin_reconciliation")
        self.assertTrue(event.usage_is_estimated)
        self.assertIsNone(event.latency_ms)
        self.assertEqual(audit_event.details["reason"], "checked provider usage log")

    def test_admin_review_queue_pages_all_pending_calls_and_reports_total(self) -> None:
        self.model.rpm_limit = None
        self.db.flush()
        with patch("app.api.v1.model_usage.get_settings", return_value=self.enabled_settings):
            for index in range(3):
                reserve_usage(self.request(f"review-page-{index:04d}"), self.gateway_key, self.db)
        rows = self.db.query(ModelUsageReservation).order_by(ModelUsageReservation.request_id).all()
        expiry = datetime.now(timezone.utc) - timedelta(minutes=15)
        for index, row in enumerate(rows):
            row.expires_at = expiry + timedelta(minutes=index)
        self.db.flush()

        first_page = list_model_usage_reviews(tenant_id=self.tenant_id, limit=2, offset=0, db=self.db)
        second_page = list_model_usage_reviews(tenant_id=self.tenant_id, limit=2, offset=2, db=self.db)

        self.assertEqual(first_page["total"], 3)
        self.assertEqual(first_page["limit"], 2)
        self.assertEqual(first_page["offset"], 0)
        self.assertEqual(len(first_page["items"]), 2)
        self.assertEqual(len(second_page["items"]), 1)
        self.assertEqual(
            {row["request_id"] for row in first_page["items"] + second_page["items"]},
            {row.request_id for row in rows},
        )

    def test_usage_events_are_paginated_with_total_and_stable_order(self) -> None:
        created_at = datetime.now(timezone.utc)
        rows = [ModelUsageEvent(
            id=uuid4(), request_id=f"usage-page-{index:04d}", tenant_id=self.tenant_id,
            model_id=self.model_id, application_id=self.application_id, user_id=self.user_id,
            input_tokens=index + 1, output_tokens=index + 2, outcome="succeeded",
            created_at=created_at,
        ) for index in range(3)]
        self.db.add_all(rows)
        self.db.flush()
        expected_ids = [str(row.id) for row in sorted(rows, key=lambda row: str(row.id), reverse=True)]

        first_page = list_model_usage_events(tenant_id=self.tenant_id, limit=2, offset=0, db=self.db)
        second_page = list_model_usage_events(tenant_id=self.tenant_id, limit=2, offset=2, db=self.db)

        self.assertEqual(first_page["total"], 3)
        self.assertEqual(first_page["limit"], 2)
        self.assertEqual(first_page["offset"], 0)
        self.assertEqual([row["id"] for row in first_page["items"]], expected_ids[:2])
        self.assertEqual([row["id"] for row in second_page["items"]], expected_ids[2:])

    def test_admin_release_requires_confirmation_and_writes_no_usage_event(self) -> None:
        with patch("app.api.v1.model_usage.get_settings", return_value=self.enabled_settings):
            reserve_usage(self.request("review-release-0001"), self.gateway_key, self.db)
        row = self.db.query(ModelUsageReservation).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.db.flush()
        request = Request({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": "/api/v1/admin/model-usage/reviews", "raw_path": b"/api/v1/admin/model-usage/reviews",
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 1234),
            "server": ("localhost", 80),
        })
        body = ModelUsageReviewRequest(
            request_id=row.request_id, decision="release", reason="provider logs confirm no call",
            provider_not_called=True,
        )
        result = resolve_model_usage_review(body, request, actor=self.user, db=self.db)

        self.assertEqual(result["status"], "released")
        self.assertEqual(self.db.query(ModelUsageEvent).count(), 0)
        self.assertEqual(self.db.query(AuditEvent).filter(
            AuditEvent.action == "model_usage.review.release").count(), 1)


if __name__ == "__main__":
    unittest.main()
