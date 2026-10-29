"""用隔离 SQLite 验证菜单权限（P356，对齐蓝图资源分类）。

覆盖：应用命名空间登记 resource_type=menu 的码自动 requires_data_scope=False
（菜单/按钮类资源不做行级数据过滤，evaluate_access 由此放行）、
普通业务码（如 document 类型）仍强制数据范围。
"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.applications import create_application_permission
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission
from app.models.identity import Tenant, User
from app.schemas.access_control import PermissionCreate


class MenuPermissionApiTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不改动本地开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"menu-{uuid4().hex[:10]}")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only", display_name="管理员")
        self.db.add_all([self.tenant, self.actor])
        self.db.flush()
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        self.application = Application(tenant_id=self.tenant.id, client_id=f"app-{uuid4().hex[:8]}",
                                       name="菜单应用", permission_namespace="menuapp", redirect_uris=[])
        self.db.add(self.application)
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "POST", "path": "/api/v1/admin/applications",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _create(self, code: str, resource_type: str) -> dict:
        return create_application_permission(
            self.application.id,
            PermissionCreate(code=code, resource_type=resource_type, scope="menu" if resource_type == "menu" else "read"),
            request=self.request,
            actor=self.actor,
            db=self.db,
        )

    def test_menu_permission_disables_data_scope_enforcement(self) -> None:
        row = self._create("menuapp.menu.project.list", "menu")
        self.assertIsNotNone(row["id"])
        stored = self.db.query(Permission).filter(Permission.code == "menuapp.menu.project.list").one()
        self.assertFalse(stored.requires_data_scope)
        self.assertEqual(stored.resource_type, "menu")
        self.assertEqual(stored.surface, "business")

    def test_button_permission_also_disables_data_scope(self) -> None:
        self._create("menuapp.button.project.export", "button")
        stored = self.db.query(Permission).filter(Permission.code == "menuapp.button.project.export").one()
        self.assertFalse(stored.requires_data_scope)

    def test_document_permission_still_requires_data_scope(self) -> None:
        self._create("menuapp.document.read", "document")
        stored = self.db.query(Permission).filter(Permission.code == "menuapp.document.read").one()
        self.assertTrue(stored.requires_data_scope)

    def test_menu_code_must_match_application_namespace(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._create("otherapp.menu.home", "menu")
        self.assertEqual(ctx.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
