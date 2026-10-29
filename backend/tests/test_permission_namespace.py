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
    assert_role_kind_grant_permissions,
    default_namespace_from_client_id,
    derive_catalog_namespace_value,
    permission_matches_namespace,
    resolve_permission_scope_key,
)


class PermissionNamespaceUnitTests(unittest.TestCase):
    def test_derive_catalog_namespace(self) -> None:
        self.assertEqual(derive_catalog_namespace_value("platform.tenant.read"), "platform")
        self.assertEqual(derive_catalog_namespace_value("rbac.role.read"), "platform")
        self.assertEqual(derive_catalog_namespace_value("org.member.read"), "platform")
        self.assertEqual(derive_catalog_namespace_value("app.read"), "platform")
        self.assertEqual(derive_catalog_namespace_value("ops.audit.read"), "platform")
        self.assertEqual(derive_catalog_namespace_value("demoapp.project.read"), "demoapp")
        self.assertEqual(derive_catalog_namespace_value("resume.read"), "resume")

    def test_permission_matches_namespace(self) -> None:
        self.assertTrue(permission_matches_namespace("deerflow.run.create", "deerflow"))
        self.assertFalse(permission_matches_namespace("resume.read", "deerflow"))

    def test_default_namespace_from_client_id(self) -> None:
        self.assertEqual(default_namespace_from_client_id("deerflow-web"), "deerflow")


class RoleKindGrantGuardTests(unittest.TestCase):
    def _permission(self, code: str, namespace: str = "platform") -> Permission:
        row = Permission(
            code=code,
            catalog_namespace=namespace,
            resource_type=code.rsplit(".", 1)[0],
            scope=code.rsplit(".", 1)[-1],
        )
        row.id = uuid4()
        return row

    def test_scope_key_matrix(self) -> None:
        self.assertEqual(resolve_permission_scope_key("platform.tenant.read"), "platform")
        self.assertEqual(resolve_permission_scope_key("org.read"), "tenant")
        self.assertEqual(resolve_permission_scope_key("app.read"), "app")
        self.assertEqual(resolve_permission_scope_key("demoapp.item.read"), "business")

    def test_tenant_role_rejects_new_platform_scope(self) -> None:
        permission = self._permission("platform.tenant.read")
        with self.assertRaises(HTTPException) as ctx:
            assert_role_kind_grant_permissions(
                kind="tenant", application_namespace=None,
                proposed=[permission], current_ids=set(),
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_tenant_role_keeps_historical_platform_scope(self) -> None:
        permission = self._permission("platform.tenant.read")
        assert_role_kind_grant_permissions(
            kind="tenant", application_namespace=None,
            proposed=[permission], current_ids={permission.id},
        )

    def test_application_role_rejects_other_namespace(self) -> None:
        permission = self._permission("otherapp.item.read", "otherapp")
        with self.assertRaises(HTTPException) as ctx:
            assert_role_kind_grant_permissions(
                kind="application", application_namespace="demoapp",
                proposed=[permission], current_ids=set(),
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("不属于当前应用命名空间", str(ctx.exception.detail))


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
            code="app.read",
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
