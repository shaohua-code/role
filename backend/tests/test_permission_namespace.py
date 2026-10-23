"""权限命名空间规则与应用角色目录过滤。"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission
from app.models.identity import Tenant
from app.services.permission_namespace import (
    assert_application_grant_permissions,
    default_namespace_from_client_id,
    derive_catalog_namespace_value,
    permission_matches_namespace,
)


class PermissionNamespaceUnitTests(unittest.TestCase):
    def test_derive_catalog_namespace(self) -> None:
        self.assertEqual(derive_catalog_namespace_value("iam.application.read"), "platform")
        self.assertEqual(derive_catalog_namespace_value("deerflow.project.read"), "deerflow")
        self.assertEqual(derive_catalog_namespace_value("resume.read"), "resume")

    def test_permission_matches_namespace(self) -> None:
        self.assertTrue(permission_matches_namespace("deerflow.run.create", "deerflow"))
        self.assertFalse(permission_matches_namespace("resume.read", "deerflow"))

    def test_default_namespace_from_client_id(self) -> None:
        self.assertEqual(default_namespace_from_client_id("deerflow-web"), "deerflow")


class DefaultNamespaceHttpTests(unittest.TestCase):
    def test_invalid_client_id_raises(self) -> None:
        with self.assertRaises(HTTPException):
            default_namespace_from_client_id("---")


class ApplicationPermissionCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.session.close()

    def test_assert_application_grant_permissions_blocks_platform(self) -> None:
        tenant_id = uuid4()
        app = Application(
            tenant_id=tenant_id,
            client_id="demo-app",
            name="Demo",
            permission_namespace="demo",
            redirect_uris=["https://localhost/cb"],
        )
        platform_permission = Permission(
            code="iam.application.read",
            catalog_namespace="platform",
            resource_type="application",
            scope="read",
        )
        with self.assertRaises(HTTPException):
            assert_application_grant_permissions("demo", [platform_permission], set())

    def test_catalog_namespace_filtering(self) -> None:
        tenant = Tenant(id=uuid4(), name="T", slug="t", status="active", kind="organization")
        tenant_id = tenant.id
        app = Application(
            tenant_id=tenant_id,
            client_id="deerflow-client",
            name="DeerFlow",
            permission_namespace="deerflow",
            redirect_uris=["https://localhost/cb"],
        )
        deerflow_permission = Permission(
            code="deerflow.thread.read",
            catalog_namespace="deerflow",
            resource_type="thread",
            scope="read",
        )
        resume_permission = Permission(
            code="resume.read",
            catalog_namespace="resume",
            resource_type="resume",
            scope="read",
        )
        self.session.add_all([tenant, app, deerflow_permission, resume_permission])
        self.session.flush()
        visible = self.session.scalars(
            select(Permission).where(Permission.catalog_namespace == app.permission_namespace),
        ).all()
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0].code, "deerflow.thread.read")


if __name__ == "__main__":
    unittest.main()
