"""确保管理员不能在仍有开放应用时变更租户的公开注册边界。"""

import unittest
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

import app.models  # noqa: F401 - 注册完整 ORM metadata
from app.db.base import Base
from app.models import Application, Tenant, User
from app.schemas.auth import TenantKindUpdate
from app.api.v1.admin import tenants as tenant_api


class TenantRegistrationAudienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="组织租户", slug=f"org-{uuid4().hex[:12]}", kind="organization")
        self.db.add(self.tenant)
        self.db.flush()
        self.application = Application(
            tenant_id=self.tenant.id, client_id=f"app-{uuid4().hex[:12]}", name="应用",
            redirect_uris=["https://app.example.test/callback"], post_logout_redirect_uris=[],
            registration_policy="open",
        )
        self.db.add(self.application)
        self.db.commit()
        self.actor = User(id=uuid4(), email="admin@example.test", password_hash="test", display_name="管理员")
        self.request = Request({
            "type": "http", "http_version": "1.1", "method": "PATCH", "scheme": "http",
            "path": "/api/v1/admin/tenants", "raw_path": b"/api/v1/admin/tenants",
            "query_string": b"", "headers": [], "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
        })

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_kind_change_requires_every_application_to_disable_public_registration(self) -> None:
        with self.assertRaises(HTTPException) as error:
            tenant_api.set_tenant_kind(
                self.tenant.id,
                TenantKindUpdate(expected_kind="organization", kind="consumer"),
                self.request, self.actor, self.db,
            )
        self.assertEqual(error.exception.status_code, 409)

        self.application.registration_policy = "disabled"
        self.db.commit()
        with patch.object(tenant_api, "audit"):
            result = tenant_api.set_tenant_kind(
                self.tenant.id,
                TenantKindUpdate(expected_kind="organization", kind="consumer"),
                self.request, self.actor, self.db,
            )
        self.assertEqual(result["kind"], "consumer")


if __name__ == "__main__":
    unittest.main()
