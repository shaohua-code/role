"""审计查询只在隔离 SQLite 表上验证组合筛选与分页。"""

import unittest
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.admin.audit import list_audit, search_audit
from app.db.base import Base
from app.models.identity import AuditEvent


class AuditQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        AuditEvent.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.actor_id = UUID("00000000-0000-0000-0000-000000000001")
        self.other_actor_id = UUID("00000000-0000-0000-0000-000000000002")
        self.tenant_id = UUID("10000000-0000-0000-0000-000000000001")
        self.start_at = datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)
        self.end_at = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        self.db.add_all([
            AuditEvent(
                id=UUID("20000000-0000-0000-0000-000000000001"),
                actor_user_id=self.actor_id,
                tenant_id=self.tenant_id,
                action="role.update",
                target_type="role",
                target_id="role-1",
                outcome="success",
                details={"changed": ["name"]},
                created_at=datetime(2026, 10, 5, 11, 15, tzinfo=timezone.utc),
            ),
            AuditEvent(
                id=UUID("20000000-0000-0000-0000-000000000002"),
                actor_user_id=self.actor_id,
                tenant_id=self.tenant_id,
                action="role.update",
                target_type="role",
                target_id="role-2",
                outcome="success",
                details={},
                created_at=datetime(2026, 10, 5, 11, 30, tzinfo=timezone.utc),
            ),
            AuditEvent(
                id=UUID("20000000-0000-0000-0000-000000000003"),
                actor_user_id=self.other_actor_id,
                tenant_id=self.tenant_id,
                action="user.create",
                target_type="user",
                target_id="user-3",
                outcome="denied",
                details={},
                created_at=datetime(2026, 10, 5, 11, 45, tzinfo=timezone.utc),
            ),
            AuditEvent(
                id=UUID("20000000-0000-0000-0000-000000000004"),
                actor_user_id=self.actor_id,
                tenant_id=self.tenant_id,
                action="role.update",
                target_type="role",
                target_id="role-4",
                outcome="success",
                details={},
                created_at=self.end_at,
            ),
        ])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine, tables=[AuditEvent.__table__])
        self.engine.dispose()

    def query(self, **overrides):
        arguments = {
            "limit": 50,
            "offset": 0,
            "action": None,
            "target_type": None,
            "target_id": None,
            "outcome": None,
            "actor_user_id": None,
            "tenant_id": None,
            "start_at": None,
            "end_at": None,
            "db": self.db,
        }
        arguments.update(overrides)
        return search_audit(**arguments)

    def test_combined_filters_and_end_time_are_applied(self) -> None:
        result = self.query(
            action="role.update",
            target_type="role",
            outcome="success",
            actor_user_id=self.actor_id,
            tenant_id=self.tenant_id,
            start_at=self.start_at,
            end_at=self.end_at,
        )

        self.assertEqual(result.total, 2)
        self.assertEqual([item.target_id for item in result.items], ["role-2", "role-1"])
        self.assertFalse(result.has_more)

    def test_pagination_has_stable_order_and_total(self) -> None:
        first_page = self.query(limit=2, offset=0, action="role.update")
        second_page = self.query(limit=2, offset=2, action="role.update")

        self.assertEqual(first_page.total, 3)
        self.assertTrue(first_page.has_more)
        self.assertEqual([item.target_id for item in first_page.items], ["role-4", "role-2"])
        self.assertEqual([item.target_id for item in second_page.items], ["role-1"])
        self.assertFalse(second_page.has_more)

    def test_legacy_endpoint_keeps_array_response(self) -> None:
        result = list_audit(limit=2, action="role.update", db=self.db)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(item.action == "role.update" for item in result))
    def test_date_filter_requires_timezone_and_valid_range(self) -> None:
        with self.assertRaises(HTTPException) as missing_timezone:
            self.query(start_at=datetime(2026, 10, 5, 11, 0))
        self.assertEqual(missing_timezone.exception.status_code, 422)

        with self.assertRaises(HTTPException) as invalid_range:
            self.query(start_at=self.end_at, end_at=self.start_at)
        self.assertEqual(invalid_range.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
