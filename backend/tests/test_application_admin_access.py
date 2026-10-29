"""P402：L3 可管本租户应用；L2 仅钉住的应用；列表 can_manage 与写路径对齐。"""

import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.application import Application
from app.models.identity import Tenant, User
from app.services.admin_authorization import (
    has_application_admin_access,
    list_readable_application_capabilities,
)
from app.services.role_provisioning import L2_ROLE_KEY, L3_ROLE_KEY
from tests.greenfield_fixture import make_tenant_role_binding


class ApplicationAdminAccessTests(unittest.TestCase):
    """每个用例在内存 SQLite 中运行，不改动开发库。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"t-{uuid4().hex[:10]}")
        self.other_tenant = Tenant(name="另一租户", slug=f"t2-{uuid4().hex[:10]}")
        self.db.add_all([self.tenant, self.other_tenant])
        self.db.flush()
        self.app_a = Application(
            tenant_id=self.tenant.id, client_id=f"a-{uuid4().hex[:8]}",
            name="应用A", permission_namespace="appa", redirect_uris=[],
        )
        self.app_b = Application(
            tenant_id=self.tenant.id, client_id=f"b-{uuid4().hex[:8]}",
            name="应用B", permission_namespace="appb", redirect_uris=[],
        )
        self.other_app = Application(
            tenant_id=self.other_tenant.id, client_id=f"o-{uuid4().hex[:8]}",
            name="外租户应用", permission_namespace="other", redirect_uris=[],
        )
        self.db.add_all([self.app_a, self.app_b, self.other_app])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, prefix: str) -> User:
        user = User(
            email=f"{prefix}-{uuid4().hex[:8]}@example.test",
            password_hash="test-only",
            display_name=prefix,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def test_l3_can_manage_all_apps_in_tenant_and_create(self) -> None:
        # 裁决：租户管理员管当前租户下一切应用，含未指定 application_id 的创建入口。
        l3 = self._user("l3")
        make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=l3,
            role_key=L3_ROLE_KEY, role_name="租户管理员",
        )
        self.assertTrue(has_application_admin_access(l3, self.tenant.id, self.db, manage=True))
        self.assertTrue(has_application_admin_access(
            l3, self.tenant.id, self.db, manage=True, application_id=self.app_a.id,
        ))
        self.assertTrue(has_application_admin_access(
            l3, self.tenant.id, self.db, manage=True, application_id=self.app_b.id,
        ))
        self.assertFalse(has_application_admin_access(
            l3, self.other_tenant.id, self.db, manage=True, application_id=self.other_app.id,
        ))
        caps = list_readable_application_capabilities(l3, self.tenant.id, self.db)
        self.assertEqual(set(caps), {self.app_a.id, self.app_b.id})
        self.assertTrue(caps[self.app_a.id]["can_manage"])
        self.assertTrue(caps[self.app_b.id]["can_manage"])

    def test_l2_only_manages_pinned_application(self) -> None:
        l2 = self._user("l2")
        make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=l2,
            role_key=L2_ROLE_KEY, role_name="应用管理员",
            application_id=self.app_a.id,
        )
        self.assertTrue(has_application_admin_access(
            l2, self.tenant.id, self.db, manage=True, application_id=self.app_a.id,
        ))
        self.assertFalse(has_application_admin_access(
            l2, self.tenant.id, self.db, manage=True, application_id=self.app_b.id,
        ))
        # 未指定应用时：租户内任一 app.admin 仍可走创建入口（既有口径）。
        self.assertTrue(has_application_admin_access(l2, self.tenant.id, self.db, manage=True))

    def test_member_without_admin_role_is_denied(self) -> None:
        member = self._user("l4")
        make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=member,
            role_key="app.member", role_name="应用成员",
            application_id=self.app_a.id,
        )
        self.assertFalse(has_application_admin_access(
            member, self.tenant.id, self.db, manage=True, application_id=self.app_a.id,
        ))
        self.assertEqual(list_readable_application_capabilities(member, self.tenant.id, self.db), {})


if __name__ == "__main__":
    unittest.main()
