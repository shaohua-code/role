"""用隔离 SQLite 验证 Wave 2 组织工作台新增的最小只读接口。

覆盖：组织列表返回 parent_id（前端拼树必需）、按组织列成员、
成员搜索过滤、组织不存在 404、越权租户 403。
"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.db.base import Base
from app.models.identity import Tenant, TenantMembership, User
from app.models.organization import MembershipOrganization, Organization
from app.api.v1.admin.organizations import list_organizations, list_organization_members


class OrganizationWorkspaceApiTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不改动本地开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="租户 A", slug=f"org-a-{uuid4().hex[:10]}")
        self.other_tenant = Tenant(name="租户 B", slug=f"org-b-{uuid4().hex[:10]}")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only", display_name="管理员")
        self.member = User(email=f"member-{uuid4().hex}@example.test", password_hash="test-only", display_name="张成员")
        self.db.add_all([self.tenant, self.other_tenant, self.actor, self.member])
        self.db.flush()
        # 绿场规则：actor 需显式绑定 L1 才能通过按码判权。
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        # membership 显式指定 id，避免 flush 顺序影响下方挂接行的外键取值。
        self.membership_id = uuid4()
        self.membership = TenantMembership(id=self.membership_id, tenant_id=self.tenant.id, user_id=self.member.id)
        self.parent_id, self.child_id, self.foreign_org_id = uuid4(), uuid4(), uuid4()
        self.parent = Organization(id=self.parent_id, tenant_id=self.tenant.id, key="rd", name="研发部")
        self.child = Organization(id=self.child_id, tenant_id=self.tenant.id, parent_id=self.parent_id,
                                  key="rd-platform", name="平台组")
        self.foreign_org = Organization(id=self.foreign_org_id, tenant_id=self.other_tenant.id,
                                        key="foreign", name="外租户组织")
        self.db.add_all([self.membership, self.parent, self.child, self.foreign_org,
                         MembershipOrganization(membership_id=self.membership_id, organization_id=self.parent_id,
                                                tenant_id=self.tenant.id, is_primary=True)])
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "GET", "path": "/api/v1/admin/organizations",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_list_organizations_returns_parent_id_for_tree_building(self) -> None:
        rows = list_organizations(tenant_id=self.tenant.id, actor=self.actor, db=self.db)
        by_key = {row["key"]: row for row in rows}
        self.assertEqual(by_key["rd"]["parent_id"], None)
        self.assertEqual(by_key["rd-platform"]["parent_id"], str(self.parent_id))
        # 旧字段保持不变，向后兼容既有列表页。
        self.assertEqual(by_key["rd-platform"]["parent_name"], "研发部")

    def test_organization_members_lists_direct_members_with_primary_flag(self) -> None:
        # 直调 handler 时 FastAPI 的 Query 默认值不是 None，须显式传 q=None。
        rows = list_organization_members(self.parent_id, q=None, actor=self.actor, db=self.db)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["user_id"], str(self.member.id))
        self.assertEqual(row["membership_id"], str(self.membership_id))
        self.assertEqual(row["display_name"], "张成员")
        self.assertTrue(row["is_primary"])
        # 未挂接任何成员的子组织返回空列表。
        self.assertEqual(list_organization_members(self.child_id, q=None, actor=self.actor, db=self.db), [])

    def test_organization_members_supports_keyword_search(self) -> None:
        self.db.query(User).filter(User.id == self.member.id).update({"display_name": "李成员"})
        self.db.commit()
        # 关键词不匹配时返回空列表；按新名称可命中。
        self.assertEqual(list_organization_members(self.parent_id, q="张", actor=self.actor, db=self.db), [])
        rows = list_organization_members(self.parent_id, q="李", actor=self.actor, db=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["display_name"], "李成员")

    def test_missing_organization_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            list_organization_members(uuid4(), actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_actor_without_tenant_role_is_rejected_with_403(self) -> None:
        outsider = User(email=f"outside-{uuid4().hex}@example.test", password_hash="test-only", display_name="外人")
        self.db.add(outsider)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            list_organization_members(self.foreign_org_id, actor=outsider, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
