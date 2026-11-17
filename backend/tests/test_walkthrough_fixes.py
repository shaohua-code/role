"""2026-11-09 走查缺陷修复的回归测试（内存 SQLite，不动开发库）。

覆盖走查报告的修复点：
- P0-1/P1-1：用户管理读/写路径的目标边界与层级保护（L3 对 L1 / 跨租户账号一律 404）；
- P1-2：组织台写路径按 button.org.manage 节点收口（L2 建组织 403，L3 正常）；
- P1-3：groups / invitations / models 列表不传 tenant_id 时收敛到操作者管理租户；
- P1-4：邀请创建的任命天花板（高于操作者范围的自定义角色 403）；
- P2-1：auth 审计事件按成员租户补写 tenant_id；
- P2-2：运营总览按数据边界过滤计数；
- P2-4：鉴权模拟拒绝目标租户外的用户（404）。
"""

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.access_control import simulate_authorization
from app.api.v1.admin.groups import list_user_groups
from app.api.v1.admin.invitations import _validate_invitation_target, list_invitations
from app.api.v1.admin.models import list_models
from app.api.v1.admin.organizations import create_organization
from app.api.v1.admin.overview import overview as overview_endpoint
from app.api.v1.admin.users import (
    get_user_profile,
    list_user_sessions,
    reset_user_password,
    revoke_user_session,
    set_user_status,
)
from app.api.v1.auth import record_event
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding
from app.models.groups import UserGroup
from app.models.identity import AuditEvent, Tenant, TenantMembership, User, UserInvitation
from app.models.model_catalog import ModelCatalog
from app.schemas.access_control import AuthorizationSimulation
from app.schemas.auth import AdminPasswordReset, UserStatusUpdate
from app.schemas.organizations import OrganizationCreate
from app.services.role_provisioning import (
    L2_GRANT_NODE_CODES,
    L3_GRANT_NODE_CODES,
    RoleProvisioning,
)
from tests.greenfield_fixture import make_platform_admin_binding


class WalkthroughFixTests(unittest.TestCase):
    """每个用例在内存 SQLite 中运行，夹具仿 test_data_scope_grading 的绿场风格。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        # 业务租户 + 第二租户（越界探测对象）。
        self.tenant = Tenant(name="业务租户", slug=f"t-{uuid4().hex[:10]}")
        self.other_tenant = Tenant(name="他租户", slug=f"o-{uuid4().hex[:10]}")
        self.db.add_all([self.tenant, self.other_tenant])
        self.db.flush()
        self.application = Application(
            tenant_id=self.tenant.id, client_id=f"a-{uuid4().hex[:8]}",
            name="应用A", permission_namespace="appa",
            redirect_uris=["https://a.example.com/cb"], status="active",
        )
        self.db.add(self.application)
        self.db.flush()
        # 管理面节点目录：L3/L2 模板节点 + 组织写节点。
        self.catalog: dict[str, Permission] = {}
        for code in sorted(set(L3_GRANT_NODE_CODES) | set(L2_GRANT_NODE_CODES)):
            row = Permission(
                code=code, catalog_namespace="platform",
                resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
                surface="management", requires_data_scope=False,
            )
            self.db.add(row)
            self.catalog[code] = row
        self.db.flush()
        self.l1 = self._user("l1")
        make_platform_admin_binding(self.db, self.l1)
        self.l3 = self._user("l3")
        self.l2 = self._user("l2")
        self.member = self._user("member")
        self.outsider = self._user("outsider")
        l3_role = RoleProvisioning.provision_tenant_admin_role(self.db, self.tenant.id)
        self.admin_role, self.member_role = RoleProvisioning.provision_application_platform_roles(
            self.db, self.tenant.id, self.application.id,
        )
        self._bind(self.l3, l3_role)
        self._bind(self.l2, self.admin_role)
        self._bind(self.member, self.member_role)
        # 外人只在他租户有成员身份。
        self.db.add(TenantMembership(
            user_id=self.outsider.id, tenant_id=self.other_tenant.id, status="active",
        ))
        # 他租户的越界数据：用户组 / 模型 / 邀请各一条。
        self.db.add(UserGroup(
            tenant_id=self.other_tenant.id, key="other-group", name="他组", status="active",
        ))
        self.db.add(ModelCatalog(
            tenant_id=self.other_tenant.id, key="other-model", provider="demo",
            model_name="m", display_name="他模型", status="active",
        ))
        other_role = Role(
            tenant_id=self.other_tenant.id, application_id=None, kind="tenant",
            key=f"custom-{uuid4().hex[:6]}", name="他角色", status="active",
        )
        self.db.add(other_role)
        self.db.flush()
        self.other_invitation = UserInvitation(
            tenant_id=self.other_tenant.id, role_id=other_role.id,
            email="outsider-invite@example.com", display_name="他邀请",
            token_hash="x" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        self.db.add(self.other_invitation)
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "PATCH", "path": "/api/v1",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ── 夹具辅助 ────────────────────────────────────────────────────────────

    def _membership(self, user: User) -> TenantMembership:
        membership = self.db.scalar(select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == self.tenant.id,
        ))
        if membership is None:
            membership = TenantMembership(
                user_id=user.id, tenant_id=self.tenant.id, status="active",
            )
            self.db.add(membership)
            self.db.flush()
        return membership

    def _bind(self, user: User, role: Role) -> None:
        membership = self._membership(user)
        if self.db.scalar(select(RoleBinding.id).where(
            RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id,
        )) is None:
            self.db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
            self.db.flush()

    def _user(self, prefix: str) -> User:
        user = User(
            email=f"{prefix}-{uuid4().hex[:8]}@example.com",
            password_hash="test-only",
            display_name=prefix,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def _assert_http(self, callable_fn, *args, status: int) -> None:
        with self.assertRaises(HTTPException) as ctx:
            callable_fn(*args)
        self.assertEqual(ctx.exception.status_code, status)

    # ── P0-1 / P1-1：用户管理目标边界与层级保护 ────────────────────────────

    def test_l3_cannot_write_platform_admin_account(self) -> None:
        """L3 对超管账号停用/重置/撤销会话一律 404（层级保护，空操作也拒绝）。"""
        self._assert_http(set_user_status, self.l1.id,
                          UserStatusUpdate(expected_status="active", status="active"),
                          self.request, self.l3, self.db, status=404)
        self._assert_http(reset_user_password, self.l1.id,
                          AdminPasswordReset(new_password="x" * 12),
                          self.request, self.l3, self.db, status=404)

    def test_l3_cannot_read_or_revoke_platform_admin_account(self) -> None:
        """L3 对超管账号的档案/会话读与撤销同样 404。"""
        self._assert_http(get_user_profile, self.l1.id, self.l3, self.db, status=404)
        self._assert_http(list_user_sessions, self.l1.id, self.l3, self.db, status=404)
        self._assert_http(revoke_user_session, self.l1.id, "management", uuid4(),
                          self.request, self.l3, self.db, status=404)

    def test_l3_cannot_touch_out_of_scope_user(self) -> None:
        """L3 对他租户成员（无平台角色）读写均 404。"""
        self._assert_http(get_user_profile, self.outsider.id, self.l3, self.db, status=404)
        self._assert_http(set_user_status, self.outsider.id,
                          UserStatusUpdate(expected_status="active", status="active"),
                          self.request, self.l3, self.db, status=404)

    def test_l3_can_read_own_tenant_member(self) -> None:
        """边界内普通成员：档案与会话可读，status 空操作放行（200）。"""
        profile = get_user_profile(self.member.id, self.l3, self.db)
        self.assertEqual(profile["email"], self.member.email)
        sessions = list_user_sessions(self.member.id, self.l3, self.db)
        self.assertEqual(sessions["user_id"], str(self.member.id))
        result = set_user_status(self.member.id,
                                 UserStatusUpdate(expected_status="active", status="active"),
                                 self.request, self.l3, self.db)
        self.assertEqual(result["status"], "active")

    # ── P1-2：组织台写路径节点收口 ─────────────────────────────────────────

    def test_l2_cannot_create_organization(self) -> None:
        """应用级管理员（app.admin 模板）不能在本租户创建组织（403）。"""
        body = OrganizationCreate(tenant_id=self.tenant.id, key="zz-l2-org", name="越权组织")
        self._assert_http(create_organization, body, self.request, self.l2, self.db, status=403)

    def test_l3_can_create_organization(self) -> None:
        """租户级管理员持 button.org.manage 正常创建组织。"""
        body = OrganizationCreate(tenant_id=self.tenant.id, key="zz-l3-org", name="租户组织")
        row = create_organization(body, self.request, self.l3, self.db)
        self.assertEqual(row["key"], "zz-l3-org")

    # ── 审计操作者候选（人性化筛选后端）：同码判权 + 租户边界 + UUID 兜底 ──

    def test_audit_actor_options_scoped_with_uuid_fallback(self) -> None:
        """候选搜索按 menu.audit 判权；q 模糊匹配名字/邮箱，完整 UUID 退化为按 ID 精确。"""
        from fastapi import HTTPException

        from app.api.v1.admin.audit import list_audit_actor_options

        # l3 只能搜到本租户成员；他租户用户不在候选中（数据边界与审计事件同口径）。
        hits = list_audit_actor_options(q=self.member.email, actor=self.l3, db=self.db)
        self.assertEqual([row["id"] for row in hits], [str(self.member.id)])
        # UUID 粘贴兜底：完整 UUID 按 ID 精确查找。
        by_uuid = list_audit_actor_options(q=str(self.member.id), actor=self.l3, db=self.db)
        self.assertEqual([row["id"] for row in by_uuid], [str(self.member.id)])
        self.assertEqual(list_audit_actor_options(q=self.outsider.email, actor=self.l3, db=self.db), [])
        # 无 menu.audit（L4 应用成员）→ 403；候选端点不旁路审计判权。
        with self.assertRaises(HTTPException) as denied:
            list_audit_actor_options(q="anything", actor=self.member, db=self.db)
        self.assertEqual(denied.exception.status_code, 403)

    # ── P1-3：可选租户列表的边界收敛 ───────────────────────────────────────

    def test_lists_scoped_without_tenant_param(self) -> None:
        """groups / invitations 不传 tenant_id 时只出自身管理租户的数据。

        models 列表已升级为三级分发口径（平台目录 ∩ 租户下发）：本租户未收到
        任何平台下发时返回空，他租户数据同样不可见。
        """
        for list_fn in (list_user_groups, list_invitations):
            with self.subTest(endpoint=list_fn.__name__):
                rows = list_fn(None, self.l3, self.db)
                tenants = {row["tenant_id"] for row in rows}
                self.assertNotIn(str(self.other_tenant.id), tenants)
        # 三级口径：l3 只能看到下发给本租户的平台模型；夹具未下发 → 空列表。
        self.assertEqual(list_models(self.l3, self.db), [])

    def test_lists_unscoped_for_platform_admin(self) -> None:
        """超管不传 tenant_id 仍全域可见。"""
        groups = list_user_groups(None, self.l1, self.db)
        self.assertIn(str(self.other_tenant.id), {row["tenant_id"] for row in groups})

    # ── P1-4：邀请任命天花板 ───────────────────────────────────────────────

    def test_invitation_role_ceiling(self) -> None:
        """L3 不能邀请高于自己范围的自定义角色（403）。"""
        above = Role(
            tenant_id=self.tenant.id, application_id=None, kind="tenant",
            key=f"super-{uuid4().hex[:6]}", name="超范围角色", status="active",
            scope="super",
        )
        self.db.add(above)
        self.db.flush()
        self._assert_http(_validate_invitation_target, self.db, self.tenant.id,
                          above.id, self.l3, status=403)
        # 平台/租户管理员模板宿主平台租户，经业务租户邀请先被「角色必须属于所选租户」422 拦截，
        # 层级保护不可达（仍不可邀）。
        l3_role = self.db.scalar(select(Role).where(Role.key == "tenant.admin"))
        self._assert_http(_validate_invitation_target, self.db, self.tenant.id,
                          l3_role.id, self.l3, status=422)

    # ── P2-1：auth 审计事件按成员租户补写 ─────────────────────────────────

    def test_record_event_writes_membership_tenants(self) -> None:
        """真实用户的登录审计按其全部活跃成员身份各写一行；匿名保持 NULL。"""
        record_event(self.db, "auth.login", "user", str(self.member.id), self.member,
                     self.request)
        record_event(self.db, "auth.login", "user", None, None, self.request, "denied")
        self.db.flush()
        rows = self.db.scalars(select(AuditEvent).where(AuditEvent.action == "auth.login")).all()
        member_rows = [row for row in rows if row.actor_user_id == self.member.id]
        self.assertEqual({row.tenant_id for row in member_rows}, {self.tenant.id})
        anonymous_rows = [row for row in rows if row.actor_user_id is None]
        self.assertEqual([row.tenant_id for row in anonymous_rows], [None])

    # ── P2-2：运营总览按范围过滤 ───────────────────────────────────────────

    def test_overview_scoped_for_l3(self) -> None:
        """L3 总览只统计自身管理租户；超管返回全域（平台租户 + 两个业务租户）。"""
        l3_view = overview_endpoint(self.l3, self.db)
        self.assertEqual(l3_view["tenants"], 1)
        self.assertEqual(l3_view["applications"], 1)
        super_view = overview_endpoint(self.l1, self.db)
        self.assertEqual(super_view["tenants"], 3)

    # ── P2-4：鉴权模拟目标归属 ─────────────────────────────────────────────

    def test_simulate_rejects_user_outside_tenant(self) -> None:
        """模拟对象不是请求租户成员时 404（防借 user_id 探测存在性）。"""
        body = AuthorizationSimulation(
            tenant_id=self.tenant.id, user_id=self.outsider.id,
            permission_code="menu.users",
        )
        self._assert_http(simulate_authorization, body, self.l3, self.db, status=404)


if __name__ == "__main__":
    unittest.main()
