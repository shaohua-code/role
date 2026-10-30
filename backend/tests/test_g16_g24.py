"""G16–G24 批量隔离测试：用户详情聚合 / 主题恢复 / 邀请批量重发 / 角色反查 /
组嵌套递归继承 / 组织负责人 / 素材上传 / Back-Channel Logout（内存 SQLite）。
"""

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.access_control import list_role_holders
from app.api.v1.admin.applications import update_application
from app.api.v1.admin.groups import create_user_group, update_user_group
from app.api.v1.admin.invitations import create_invitations_batch, resend_invitation
from app.api.v1.admin.organizations import create_organization, update_organization
from app.api.v1.admin.themes import restore_theme
from app.api.v1.admin.uploads import get_theme_asset, upload_theme_asset
from app.api.v1.admin.users import get_user_profile
from app.core.config import get_settings
from app.db.base import Base
from app.models.application import Application, ApplicationTheme
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import Tenant, TenantMembership, User, UserInvitation
from app.models.organization import Organization
from app.schemas.applications import ApplicationUpdate as AppUpdate
from app.schemas.auth import AdminInvitationBatchCreate, AdminInvitationResend
from app.schemas.groups import UserGroupCreate, UserGroupUpdate
from app.schemas.organizations import OrganizationCreate, OrganizationUpdate
from app.services.effective_roles import list_effective_roles


class G16G24BatchTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不触碰开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"biz-{uuid4().hex[:10]}")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only",
                          display_name="管理员", status="active")
        self.member = User(email=f"u-{uuid4().hex}@example.test", password_hash="test-only",
                           display_name="普通成员", status="active")
        self.db.add_all([self.tenant, self.actor, self.member])
        self.db.flush()
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        self.membership = TenantMembership(tenant_id=self.tenant.id, user_id=self.member.id, status="active")
        self.db.add(self.membership)
        self.role = Role(tenant_id=self.tenant.id, key=f"role-{uuid4().hex[:6]}", name="演示角色", kind="tenant")
        self.db.add(self.role)
        self.db.flush()
        self.binding = RoleBinding(membership_id=self.membership.id, role_id=self.role.id)
        self.db.add(self.binding)
        self.application = Application(tenant_id=self.tenant.id, client_id=f"client-{uuid4().hex[:8]}",
                                       name="演示应用", redirect_uris=["https://a.example.test/cb"],
                                       status="active")
        self.db.add(self.application)
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

    # ---- G16 用户详情聚合 ----

    def test_user_profile_aggregates_memberships_roles_sessions(self) -> None:
        profile = get_user_profile(self.member.id, actor=self.actor, db=self.db)
        self.assertEqual(profile["email"], self.member.email)
        self.assertEqual(len(profile["memberships"]), 1)
        self.assertEqual(profile["memberships"][0]["tenant_name"], self.tenant.name)
        self.assertEqual(len(profile["role_bindings"]), 1)
        self.assertEqual(profile["role_bindings"][0]["role_key"], self.role.key)
        self.assertEqual(profile["sessions"], [])
        self.assertEqual(profile["recent_auth_events"], [])
        self.assertEqual(profile["effective_permissions"], [])

    def test_user_profile_effective_permissions_include_direct_and_group_sources(self) -> None:
        """G28：有效权限码并集带来源（直授角色 / 用户组）。"""
        direct_permission = Permission(
            code="org.read", catalog_namespace="platform", resource_type="org",
            scope="read", description="读取组织", surface="management", requires_data_scope=False,
        )
        group_permission = Permission(
            code="org.group.read", catalog_namespace="platform", resource_type="org",
            scope="read", description="读取用户组", surface="management", requires_data_scope=False,
        )
        group_role = Role(tenant_id=self.tenant.id, key=f"grole-{uuid4().hex[:6]}", name="组角色", kind="tenant")
        group = UserGroup(tenant_id=self.tenant.id, key=f"g-{uuid4().hex[:6]}", name="演示组")
        self.db.add_all([direct_permission, group_permission, group_role, group])
        self.db.flush()
        self.db.add_all([
            RolePermission(role_id=self.role.id, permission_id=direct_permission.id),
            RolePermission(role_id=group_role.id, permission_id=group_permission.id),
            UserGroupMembership(group_id=group.id, membership_id=self.membership.id, tenant_id=self.tenant.id),
            UserGroupRole(group_id=group.id, role_id=group_role.id, tenant_id=self.tenant.id),
        ])
        self.db.commit()
        profile = get_user_profile(self.member.id, actor=self.actor, db=self.db)
        by_code = {item["code"]: item for item in profile["effective_permissions"]}
        self.assertIn("org.read", by_code)
        self.assertIn("org.group.read", by_code)
        direct_sources = {item["source_type"] for item in by_code["org.read"]["sources"]}
        group_sources = {item["source_type"] for item in by_code["org.group.read"]["sources"]}
        self.assertEqual(direct_sources, {"direct"})
        self.assertEqual(group_sources, {"group"})
        self.assertEqual(by_code["org.group.read"]["sources"][0]["group_name"], "演示组")

    def test_user_profile_returns_404_and_gates_non_admin(self) -> None:
        with self.assertRaises(HTTPException) as missing:
            get_user_profile(uuid4(), actor=self.actor, db=self.db)
        self.assertEqual(missing.exception.status_code, 404)
        with self.assertRaises(HTTPException) as forbidden:
            get_user_profile(self.member.id, actor=self.member, db=self.db)
        self.assertEqual(forbidden.exception.status_code, 403)

    # ---- G17 主题历史恢复 ----

    def test_theme_restore_creates_new_version_without_touching_history(self) -> None:
        history = ApplicationTheme(application_id=self.application.id, version=1, status="archived",
                                   config={"primary_color": "#18181B"},
                                   published_at=datetime.now(timezone.utc))
        published = ApplicationTheme(application_id=self.application.id, version=2, status="published",
                                     config={"primary_color": "#52525B"},
                                     published_at=datetime.now(timezone.utc))
        self.db.add_all([history, published])
        self.db.commit()

        result = restore_theme(self.application.id, history.id, request=self.request,
                               publish=True, actor=self.actor, db=self.db)

        self.db.expire_all()
        self.assertEqual(result["version"], 3)
        self.assertEqual(result["restored_from_version"], 1)
        self.assertEqual(result["config"]["primary_color"], "#18181B")
        statuses = {row.version: row.status for row in self.db.scalars(
            select(ApplicationTheme).where(ApplicationTheme.application_id == self.application.id)).all()}
        self.assertEqual(statuses[1], "archived")
        self.assertEqual(statuses[2], "archived")
        self.assertEqual(statuses[3], "published")

    def test_theme_restore_returns_404_for_foreign_theme(self) -> None:
        other_app = Application(tenant_id=self.tenant.id, client_id=f"c-{uuid4().hex[:8]}",
                                name="其他应用", redirect_uris=[], status="active")
        self.db.add(other_app)
        self.db.flush()
        foreign = ApplicationTheme(application_id=other_app.id, version=1, status="draft", config={})
        self.db.add(foreign)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            restore_theme(self.application.id, foreign.id, request=self.request,
                          actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    # ---- G21 邀请批量 + 重发 ----

    def test_invitation_batch_creates_and_skips_conflicts(self) -> None:
        pending = UserInvitation(tenant_id=self.tenant.id, role_id=self.role.id,
                                 email="taken@example.com", display_name="已有邀请",
                                 token_hash=uuid4().hex * 2,
                                 expires_at=datetime.now(timezone.utc) + timedelta(hours=2))
        self.db.add(pending)
        self.db.commit()
        body = AdminInvitationBatchCreate(
            tenant_id=self.tenant.id,
            emails=["New-1@Example.com", "new-1@example.com", "taken@example.com", "fresh@example.com"],
            display_name="批量受邀人", role_id=self.role.id, expires_in_hours=24,
        )
        result = create_invitations_batch(body, self.request, Response(), actor=self.actor, db=self.db)
        # 大小写归一去重后 3 个邮箱：1 个冲突跳过，2 个创建。
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["skipped"], 1)
        created = [item for item in result["items"] if item["status"] == "created"]
        self.assertTrue(all(item["invite_url"].startswith("http") for item in created))
        skipped = next(item for item in result["items"] if item["status"] == "skipped")
        self.assertIn("邀请", skipped["reason"])

    def test_invitation_resend_rotates_token_and_extends_expiry(self) -> None:
        invite = UserInvitation(tenant_id=self.tenant.id, role_id=self.role.id,
                                email="again@example.test", display_name="重发对象",
                                token_hash="old-hash",
                                expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        self.db.add(invite)
        self.db.commit()
        result = resend_invitation(invite.id, AdminInvitationResend(expires_in_hours=48),
                                   self.request, Response(), actor=self.actor, db=self.db)
        self.db.expire_all()
        row = self.db.get(UserInvitation, invite.id)
        self.assertNotEqual(row.token_hash, "old-hash")
        expiry = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        self.assertGreater(expiry, datetime.now(timezone.utc) + timedelta(hours=40))
        self.assertIn("invite=", result["invite_url"])

    def test_invitation_resend_rejects_accepted(self) -> None:
        invite = UserInvitation(tenant_id=self.tenant.id, role_id=self.role.id,
                                email="done@example.test", display_name="已接受",
                                token_hash=uuid4().hex * 2,
                                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                                accepted_at=datetime.now(timezone.utc))
        self.db.add(invite)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            resend_invitation(invite.id, AdminInvitationResend(), self.request, Response(),
                              actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    # ---- G22 角色持有者反查 ----

    def test_role_holders_merges_direct_and_group_sources(self) -> None:
        group = UserGroup(tenant_id=self.tenant.id, key=f"g-{uuid4().hex[:6]}", name="演示组")
        self.db.add(group)
        self.db.flush()
        self.db.add_all([
            UserGroupMembership(group_id=group.id, membership_id=self.membership.id, tenant_id=self.tenant.id),
            UserGroupRole(group_id=group.id, role_id=self.role.id, tenant_id=self.tenant.id),
        ])
        self.db.commit()
        result = list_role_holders(self.role.id, actor=self.actor, db=self.db)
        self.assertEqual(result["total"], 1)
        holder = result["items"][0]
        self.assertEqual(holder["user_id"], str(self.member.id))
        self.assertIn("direct", holder["sources"])
        self.assertIn("group", holder["sources"])
        self.assertEqual(holder["via_groups"], ["演示组"])
        with self.assertRaises(HTTPException) as missing:
            list_role_holders(uuid4(), actor=self.actor, db=self.db)
        self.assertEqual(missing.exception.status_code, 404)

    # ---- G24 用户组嵌套 + 递归继承 ----

    def test_group_nesting_cycle_is_rejected(self) -> None:
        parent = create_user_group(
            UserGroupCreate(tenant_id=self.tenant.id, key=f"p-{uuid4().hex[:6]}", name="父组"),
            self.request, actor=self.actor, db=self.db,
        )
        child = create_user_group(
            UserGroupCreate(tenant_id=self.tenant.id, key=f"c-{uuid4().hex[:6]}", name="子组",
                            parent_group_id=UUID(parent["id"])),
            self.request, actor=self.actor, db=self.db,
        )
        # 把父组的父指向子组 → 成环，必须 422。
        with self.assertRaises(HTTPException) as ctx:
            update_user_group(UUID(parent["id"]),
                              UserGroupUpdate(parent_group_id=UUID(child["id"])),
                              self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        # 跨租户/不存在的父组同样拒绝。
        with self.assertRaises(HTTPException) as missing:
            create_user_group(
                UserGroupCreate(tenant_id=self.tenant.id, key=f"x-{uuid4().hex[:6]}", name="野组",
                                parent_group_id=uuid4()),
                self.request, actor=self.actor, db=self.db,
            )
        self.assertEqual(missing.exception.status_code, 422)

    def test_effective_roles_include_ancestor_group_roles(self) -> None:
        """G24 递归继承：成员在子组，父组挂的角色也应生效；停用父组不生效。"""
        # 坑（同 greenfield_fixture 警告）：先 flush 父组拿到 ID，再构造子组引用。
        parent = UserGroup(tenant_id=self.tenant.id, key=f"p-{uuid4().hex[:6]}", name="父组")
        self.db.add(parent)
        self.db.flush()
        disabled_parent = UserGroup(tenant_id=self.tenant.id, key=f"d-{uuid4().hex[:6]}", name="停用父组",
                                    status="disabled")
        child = UserGroup(tenant_id=self.tenant.id, key=f"c-{uuid4().hex[:6]}", name="子组",
                          parent_group_id=parent.id)
        ancestor_role = Role(tenant_id=self.tenant.id, key=f"ar-{uuid4().hex[:6]}", name="祖先角色", kind="tenant")
        self.db.add_all([disabled_parent, child, ancestor_role])
        self.db.flush()
        self.db.add_all([
            UserGroupMembership(group_id=child.id, membership_id=self.membership.id, tenant_id=self.tenant.id),
            UserGroupRole(group_id=parent.id, role_id=ancestor_role.id, tenant_id=self.tenant.id),
        ])
        self.db.commit()
        effective = {role.id for role in list_effective_roles(
            db=self.db, membership_id=self.membership.id, tenant_id=self.tenant.id)}
        self.assertIn(self.role.id, effective)
        self.assertIn(ancestor_role.id, effective)
        # 停用父组挂的角色不生效。
        disabled_role = Role(tenant_id=self.tenant.id, key=f"dr-{uuid4().hex[:6]}", name="停用角色", kind="tenant")
        self.db.add(disabled_role)
        self.db.flush()
        self.db.add(UserGroupRole(group_id=disabled_parent.id, role_id=disabled_role.id, tenant_id=self.tenant.id))
        self.db.commit()
        effective = {role.id for role in list_effective_roles(
            db=self.db, membership_id=self.membership.id, tenant_id=self.tenant.id)}
        self.assertNotIn(disabled_role.id, effective)

    # ---- G24 组织负责人 ----

    def test_organization_owner_must_be_active_member_and_changes_are_audited(self) -> None:
        outsider = User(email=f"o-{uuid4().hex}@example.test", password_hash="t", display_name="外人")
        self.db.add(outsider)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            create_organization(
                OrganizationCreate(tenant_id=self.tenant.id, key=f"org-{uuid4().hex[:6]}", name="部门A",
                                   owner_user_id=outsider.id),
                self.request, actor=self.actor, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 422)
        org = create_organization(
            OrganizationCreate(tenant_id=self.tenant.id, key=f"org-{uuid4().hex[:6]}", name="部门B",
                               owner_user_id=self.member.id),
            self.request, actor=self.actor, db=self.db,
        )
        self.assertEqual(org["owner_user_id"], str(self.member.id))
        update_organization(UUID(org["id"]), OrganizationUpdate(owner_user_id=None),
                            self.request, actor=self.actor, db=self.db)
        from sqlalchemy import select as _select
        from app.models.identity import AuditEvent

        event = self.db.scalar(_select(AuditEvent).where(AuditEvent.action == "organization.owner.change"))
        self.assertIsNotNone(event)

    # ---- G18 素材上传 ----

    def test_theme_asset_upload_validates_type_and_serves_publicly(self) -> None:
        def _receive(body: bytes):
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            return receive

        settings = get_settings()
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 64
        upload_request = Request({
            "type": "http", "method": "POST", "path": "/api/v1/admin/uploads/theme-assets",
            "headers": [(b"content-type", b"image/png"), (b"content-length", str(len(png_bytes)).encode())],
            "query_string": b"", "scheme": "http", "server": ("t", 80), "client": ("127.0.0.1", 5),
        }, receive=_receive(png_bytes))
        result = asyncio.run(upload_theme_asset(
            upload_request, application_id=self.application.id, actor=self.actor, db=self.db))
        self.assertTrue(result["url"].endswith(".png"))
        self.assertTrue(result["url"].startswith(get_settings().api_v1_prefix))
        filename = result["url"].rsplit("/", 1)[-1]
        served = get_theme_asset(filename)
        self.assertEqual(served.media_type, "image/png")
        # 非白名单类型 415；伪造文件名 404。
        svg_request = Request({
            "type": "http", "method": "POST", "path": "/api/v1/admin/uploads/theme-assets",
            "headers": [(b"content-type", b"image/svg+xml"), (b"content-length", b"9")],
            "query_string": b"", "scheme": "http", "server": ("t", 80), "client": ("127.0.0.1", 5),
        }, receive=_receive(b"<svg></svg>"))
        with self.assertRaises(HTTPException) as rejected:
            asyncio.run(upload_theme_asset(
                svg_request, application_id=self.application.id, actor=self.actor, db=self.db))
        self.assertEqual(rejected.exception.status_code, 415)
        with self.assertRaises(HTTPException) as traversal:
            get_theme_asset("../../etc/passwd")
        self.assertEqual(traversal.exception.status_code, 404)

    # ---- G19 Back-Channel Logout ----

    def test_backchannel_logout_token_claims_and_update_validation(self) -> None:
        from app.services import backchannel_logout

        captured: list = []

        def fake_sign(claims, token_type):
            captured.append({"claims": claims, "token_type": token_type})
            return "stub-token"

        with patch.object(backchannel_logout, "get_settings",
                          return_value=SimpleNamespaceLike(oidc_issuer="https://iam.example.test")), \
                patch.object(backchannel_logout, "sign_jwt", side_effect=fake_sign):
            token = backchannel_logout.build_logout_token(self.application, self.member.id, uuid4())
            self.assertEqual(token, "stub-token")
            # 无 sub/sid 的广播形态（用户/会话缺省）。
            backchannel_logout.build_logout_token(self.application, None, None)
        self.assertEqual(captured[0]["token_type"], "logout+jwt")
        first = captured[0]["claims"]
        self.assertEqual(first["iss"], "https://iam.example.test")
        self.assertEqual(first["aud"], self.application.client_id)
        self.assertEqual(first["events"],
                         ["http://schemas.openid.net/event/backchannel-logout"])
        self.assertNotIn("nonce", first)
        self.assertEqual(first["sid"], claims_sid := first.get("sid"))
        self.assertTrue(claims_sid)
        # 广播形态不含 sub/sid。
        self.assertNotIn("sub", captured[1]["claims"])
        self.assertNotIn("sid", captured[1]["claims"])

        # 应用更新：非法 URI 422，合法 HTTPS 保存。
        with self.assertRaises(HTTPException) as invalid:
            update_application(self.application.id, AppUpdate(backchannel_logout_uri="ftp://x.test"),
                               self.request, actor=self.actor, db=self.db)
        self.assertEqual(invalid.exception.status_code, 422)
        updated = update_application(
            self.application.id,
            AppUpdate(backchannel_logout_uri="https://app.example.test/backchannel-logout"),
            self.request, actor=self.actor, db=self.db)
        self.assertEqual(updated["backchannel_logout_uri"], "https://app.example.test/backchannel-logout")


class SimpleNamespaceLike:
    """轻量设置替身：只暴露被测代码读取的属性。"""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


if __name__ == "__main__":
    unittest.main()
