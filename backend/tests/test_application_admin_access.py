"""P402/P404：L3 可管本租户应用；L2（应用级）仅钉住的应用；未指定应用不再视为可创建。

新模型判权口径（admin_authorization.has_application_admin_access）：
- 租户级及以上（按范围闸门）管本租户全部应用，未钉 application_id 的创建入口同样放行；
- 应用级按菜单/按钮节点判权：钉住该应用且持对应节点才放行；
- 跨租户数据边界由 list_readable_application_capabilities 按成员身份收口。
"""

import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed_greenfield import seed_permissions
from app.models.application import Application
from app.models.identity import Tenant, User
from app.services.admin_authorization import AdminAccessGuard
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
        # 菜单/按钮节点目录：应用级判权按节点（menu.application_workspace / button.apps.*）。
        seed_permissions(self.db)
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

    def _node(self, code: str):
        from sqlalchemy import select

        from app.models.authorization import Permission

        permission = self.db.scalar(select(Permission).where(Permission.code == code))
        self.assertIsNotNone(permission, f"目录缺节点：{code}")
        return permission

    def test_l3_can_manage_all_apps_in_tenant_and_create(self) -> None:
        # 新语义：未钉 application_id 的创建入口按范围闸门放行（租户级及以上）。
        l3 = self._user("l3")
        make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=l3,
            role_key=L3_ROLE_KEY, role_name="租户管理员",
        )
        self.assertTrue(AdminAccessGuard.has_application_admin_access(l3, self.tenant.id, self.db, manage=True))
        self.assertTrue(AdminAccessGuard.has_application_admin_access(
            l3, self.tenant.id, self.db, manage=True, application_id=self.app_a.id,
        ))
        self.assertTrue(AdminAccessGuard.has_application_admin_access(
            l3, self.tenant.id, self.db, manage=True, application_id=self.app_b.id,
        ))
        # 跨租户边界按成员身份收口：L3 无他租户成员身份 → 他租户应用不可读。
        self.assertEqual(AdminAccessGuard.list_readable_application_capabilities(l3, self.other_tenant.id, self.db), {})
        caps = AdminAccessGuard.list_readable_application_capabilities(l3, self.tenant.id, self.db)
        self.assertEqual(set(caps), {self.app_a.id, self.app_b.id})
        self.assertTrue(caps[self.app_a.id]["can_manage"])
        self.assertTrue(caps[self.app_b.id]["can_manage"])

    def test_l2_only_manages_pinned_application(self) -> None:
        # 应用级（app.admin 角色 + 节点授权）判权：钉住的应用持节点才放行。
        l2 = self._user("l2")
        make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=l2,
            role_key=L2_ROLE_KEY, role_name="应用管理员",
            application_id=self.app_a.id,
            permission_ids=[
                self._node("menu.application_workspace").id,
                self._node("button.apps.manage").id,
                self._node("button.apps.secret").id,
            ],
        )
        self.assertTrue(AdminAccessGuard.has_application_admin_access(
            l2, self.tenant.id, self.db, manage=True, application_id=self.app_a.id,
        ))
        self.assertFalse(AdminAccessGuard.has_application_admin_access(
            l2, self.tenant.id, self.db, manage=True, application_id=self.app_b.id,
        ))
        # P404：未指定应用视为创建入口，应用级不能向上。
        self.assertFalse(AdminAccessGuard.has_application_admin_access(l2, self.tenant.id, self.db, manage=True))
        # 可读能力清单只含钉住的应用。
        caps = AdminAccessGuard.list_readable_application_capabilities(l2, self.tenant.id, self.db)
        self.assertEqual(set(caps), {self.app_a.id})
        self.assertTrue(caps[self.app_a.id]["can_manage"])

    def test_member_without_admin_role_is_denied(self) -> None:
        member = self._user("l4")
        make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=member,
            role_key="app.member", role_name="应用成员",
            application_id=self.app_a.id,
        )
        self.assertFalse(AdminAccessGuard.has_application_admin_access(
            member, self.tenant.id, self.db, manage=True, application_id=self.app_a.id,
        ))
        self.assertEqual(AdminAccessGuard.list_readable_application_capabilities(member, self.tenant.id, self.db), {})


if __name__ == "__main__":
    unittest.main()
