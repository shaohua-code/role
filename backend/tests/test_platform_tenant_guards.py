"""平台租户防呆保护隔离测试：停用租户 / 创建组织 / 单发邀请 / 批量邀请 / 创建用户组
五个写入口对 slug=platform 的引导租户一律 422；业务租户正路径不受影响（内存 SQLite）。
"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.groups import create_user_group
from app.api.v1.admin.invitations import create_invitation, create_invitations_batch
from app.api.v1.admin.organizations import create_organization
from app.api.v1.admin.tenants import set_tenant_status
from app.db.base import Base
from app.db.seed_greenfield import PLATFORM_TENANT_SLUG
from app.models.authorization import Role, RoleBinding
from app.models.identity import Tenant, TenantMembership, User
from app.schemas.auth import AdminInvitationBatchCreate, AdminInvitationCreate
from app.schemas.groups import UserGroupCreate
from app.schemas.organizations import OrganizationCreate


class PlatformTenantGuardTests(unittest.TestCase):
    """每个用例在内存数据库中运行，直接调用 handler 验证平台租户防呆保护。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        # 被保护对象：slug 固定 platform 的引导租户（与绿场种子一致），外加组织/消费两类业务租户对照。
        self.platform_tenant = Tenant(name="平台管理租户", slug=PLATFORM_TENANT_SLUG, kind="organization")
        self.org_tenant = Tenant(name="业务组织租户", slug=f"biz-{uuid4().hex[:10]}", kind="organization")
        self.consumer_tenant = Tenant(name="消费租户", slug=f"toc-{uuid4().hex[:10]}", kind="consumer")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only",
                          display_name="平台管理员", status="active")
        self.db.add_all([self.platform_tenant, self.org_tenant, self.consumer_tenant, self.actor])
        self.db.flush()
        # 照 greenfield_fixture 的做法造 L1（平台层级角色 + membership + RoleBinding），
        # 但直接挂在 slug=platform 的引导租户上，贴近线上「引导超管宿主」的真实关系。
        l1_role = Role(id=uuid4(), tenant_id=self.platform_tenant.id, application_id=None,
                       kind="platform", key="platform.admin", name="平台超级管理员", status="active")
        membership = TenantMembership(id=uuid4(), tenant_id=self.platform_tenant.id,
                                      user_id=self.actor.id, status="active")
        self.db.add_all([l1_role, membership])
        self.db.flush()
        self.db.add(RoleBinding(membership_id=membership.id, role_id=l1_role.id))
        # 邀请校验要求「活动租户 + 租户内活动角色」：先备好普通租户角色，
        # 保证负路径能穿过通用校验、精确命中平台租户拦截分支。
        self.platform_role = Role(tenant_id=self.platform_tenant.id, key=f"invite-{uuid4().hex[:6]}",
                                  name="平台演示角色", kind="tenant")
        self.org_role = Role(tenant_id=self.org_tenant.id, key=f"role-{uuid4().hex[:6]}",
                             name="业务演示角色", kind="tenant")
        self.db.add_all([self.platform_role, self.org_role])
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "POST", "path": "/api/v1",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ---- 负路径：平台引导租户一律 422 ----

    def test_platform_tenant_cannot_be_disabled(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            set_tenant_status(self.platform_tenant.id, "disabled", self.request,
                              actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台引导租户", ctx.exception.detail)
        # 拦截发生在任何写库之前，租户状态必须保持 active。
        self.db.expire_all()
        self.assertEqual(self.db.get(Tenant, self.platform_tenant.id).status, "active")

    def test_platform_tenant_rejects_organization(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_organization(
                OrganizationCreate(tenant_id=self.platform_tenant.id,
                                   key=f"org-{uuid4().hex[:6]}", name="平台部门"),
                self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台引导租户", ctx.exception.detail)

    def test_platform_tenant_rejects_invitation(self) -> None:
        body = AdminInvitationCreate(tenant_id=self.platform_tenant.id, email="new@example.com",
                                     display_name="受邀人", role_id=self.platform_role.id)
        with self.assertRaises(HTTPException) as ctx:
            create_invitation(body, self.request, Response(), actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台引导租户", ctx.exception.detail)

    def test_platform_tenant_rejects_batch_invitation(self) -> None:
        body = AdminInvitationBatchCreate(tenant_id=self.platform_tenant.id,
                                          emails=["a@example.com", "b@example.com"],
                                          display_name="批量受邀人", role_id=self.platform_role.id)
        with self.assertRaises(HTTPException) as ctx:
            create_invitations_batch(body, self.request, Response(), actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台引导租户", ctx.exception.detail)

    def test_platform_tenant_rejects_user_group(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            create_user_group(
                UserGroupCreate(tenant_id=self.platform_tenant.id,
                                key=f"g-{uuid4().hex[:6]}", name="平台组"),
                self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("平台引导租户", ctx.exception.detail)

    # ---- 正路径对照：业务租户不受影响，active 幂等放行 ----

    def test_business_tenant_organization_still_works(self) -> None:
        org = create_organization(
            OrganizationCreate(tenant_id=self.org_tenant.id,
                               key=f"org-{uuid4().hex[:6]}", name="业务部门"),
            self.request, actor=self.actor, db=self.db)
        self.assertEqual(org["name"], "业务部门")
        self.assertEqual(org["tenant_id"], str(self.org_tenant.id))

    def test_platform_tenant_active_is_idempotent_allowed(self) -> None:
        # 已是 active 的平台租户再次设为 active 必须幂等放行，不触发 422。
        result = set_tenant_status(self.platform_tenant.id, "active", self.request,
                                   actor=self.actor, db=self.db)
        self.assertEqual(result["status"], "active")


if __name__ == "__main__":
    unittest.main()
