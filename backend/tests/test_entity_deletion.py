"""用隔离 SQLite 验证六个实体删除端点（P352 补齐的删除能力）。

覆盖：种子保护（platform 租户 / platform.admin 角色）、RESTRICT 预检
（用量账目 / 未兑换邀请 / 子组织）、正常删除、404，以及角色删除时
应用注册默认角色的悬挂引用清理。
"""

import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.access_control import delete_role
from app.api.v1.admin.applications import delete_application
from app.api.v1.admin.groups import delete_user_group
from app.api.v1.admin.models import delete_model
from app.api.v1.admin.organizations import delete_organization
from app.api.v1.admin.tenants import delete_tenant
from app.db.base import Base
from app.db.seed_greenfield import PLATFORM_TENANT_SLUG
from app.models.application import Application
from app.models.authorization import Role
from app.models.groups import UserGroup
from app.models.identity import Tenant, User, UserInvitation
from app.models.model_catalog import ModelCatalog, ModelUsageEvent
from app.models.organization import Organization


class EntityDeletionApiTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不改动本地开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.platform_tenant = Tenant(name="平台引导租户", slug=PLATFORM_TENANT_SLUG)
        self.tenant = Tenant(name="业务租户", slug=f"biz-{uuid4().hex[:10]}")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only", display_name="管理员")
        self.db.add_all([self.platform_tenant, self.tenant, self.actor])
        self.db.flush()
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "DELETE", "path": "/api/v1/admin",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _make_role(self, key: str = f"app.member-{uuid4().hex[:6]}", kind: str = "tenant",
                   tenant_id: UUID | None = None) -> Role:
        role = Role(tenant_id=tenant_id or self.tenant.id, key=key, name=f"角色 {key}", kind=kind)
        self.db.add(role)
        self.db.commit()
        return role

    def _make_application(self) -> Application:
        row = Application(tenant_id=self.tenant.id, client_id=f"client-{uuid4().hex[:8]}",
                          name="演示应用", redirect_uris=[])
        self.db.add(row)
        self.db.commit()
        return row

    def _make_usage_event(self, *, tenant_id: UUID, model_id: UUID, application_id: UUID) -> None:
        user = User(email=f"u-{uuid4().hex}@example.test", password_hash="test-only", display_name="用量用户")
        self.db.add(user)
        self.db.flush()
        self.db.add(ModelUsageEvent(request_id=f"req-{uuid4().hex}", tenant_id=tenant_id, model_id=model_id,
                                    application_id=application_id, user_id=user.id,
                                    input_tokens=1, output_tokens=1, outcome="succeeded"))
        self.db.commit()

    # ---- 租户删除 ----

    def test_platform_tenant_is_protected_from_deletion(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            delete_tenant(self.platform_tenant.id, request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIsNotNone(self.db.get(Tenant, self.platform_tenant.id))

    def test_tenant_with_usage_records_is_blocked_with_409(self) -> None:
        app = self._make_application()
        model = ModelCatalog(tenant_id=self.tenant.id, key="gpt-x", provider="openai",
                             model_name="gpt-x", display_name="GPT-X")
        self.db.add(model)
        self.db.commit()
        self._make_usage_event(tenant_id=self.tenant.id, model_id=model.id, application_id=app.id)
        with self.assertRaises(HTTPException) as ctx:
            delete_tenant(self.tenant.id, request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_tenant_deletion_succeeds_without_usage(self) -> None:
        delete_tenant(self.tenant.id, request=self.request, actor=self.actor, db=self.db)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Tenant, self.tenant.id))

    def test_missing_tenant_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            delete_tenant(uuid4(), request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    # ---- 角色删除 ----

    def test_platform_super_admin_role_is_protected_from_deletion(self) -> None:
        role = self._make_role(key="platform.admin", kind="platform", tenant_id=self.platform_tenant.id)
        with self.assertRaises(HTTPException) as ctx:
            delete_role(role.id, request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_role_referenced_by_invitation_is_blocked_with_409(self) -> None:
        role = self._make_role()
        invitation = UserInvitation(tenant_id=self.tenant.id, role_id=role.id,
                                    email=f"invite-{uuid4().hex}@example.test", display_name="受邀人",
                                    token_hash=uuid4().hex * 2,
                                    expires_at=datetime.now(timezone.utc) + timedelta(days=3))
        self.db.add(invitation)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            delete_role(role.id, request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_role_deletion_clears_application_registration_reference(self) -> None:
        role = self._make_role()
        app = self._make_application()
        app.registration_role_id = role.id
        self.db.commit()
        delete_role(role.id, request=self.request, actor=self.actor, db=self.db)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Role, role.id))
        # 应用保留，注册默认角色悬挂引用被解除。
        self.assertIsNone(self.db.get(Application, app.id).registration_role_id)

    # ---- 用户组 / 组织删除 ----

    def test_user_group_deletion_succeeds(self) -> None:
        group = UserGroup(tenant_id=self.tenant.id, key=f"grp-{uuid4().hex[:6]}", name="运营组")
        self.db.add(group)
        self.db.commit()
        delete_user_group(group.id, request=self.request, actor=self.actor, db=self.db)
        self.db.expire_all()
        self.assertIsNone(self.db.get(UserGroup, group.id))

    def test_organization_with_children_is_blocked_with_409(self) -> None:
        parent = Organization(tenant_id=self.tenant.id, key="hq", name="总部")
        self.db.add(parent)
        self.db.flush()
        self.db.add(Organization(tenant_id=self.tenant.id, parent_id=parent.id, key="rd", name="研发部"))
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            delete_organization(parent.id, request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_leaf_organization_deletion_succeeds(self) -> None:
        parent = Organization(tenant_id=self.tenant.id, key="hq2", name="总部二")
        self.db.add(parent)
        self.db.commit()
        delete_organization(parent.id, request=self.request, actor=self.actor, db=self.db)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Organization, parent.id))

    # ---- 应用 / 模型删除 ----

    def test_application_with_usage_records_is_blocked_with_409(self) -> None:
        app = self._make_application()
        model = ModelCatalog(tenant_id=self.tenant.id, key="m-1", provider="openai",
                             model_name="m-1", display_name="M1")
        self.db.add(model)
        self.db.commit()
        self._make_usage_event(tenant_id=self.tenant.id, model_id=model.id, application_id=app.id)
        with self.assertRaises(HTTPException) as ctx:
            delete_application(app.id, request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_application_deletion_succeeds_without_usage(self) -> None:
        app = self._make_application()
        delete_application(app.id, request=self.request, actor=self.actor, db=self.db)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Application, app.id))

    def test_model_with_usage_records_is_blocked_with_409(self) -> None:
        app = self._make_application()
        model = ModelCatalog(tenant_id=self.tenant.id, key="m-2", provider="openai",
                             model_name="m-2", display_name="M2")
        self.db.add(model)
        self.db.commit()
        self._make_usage_event(tenant_id=self.tenant.id, model_id=model.id, application_id=app.id)
        with self.assertRaises(HTTPException) as ctx:
            delete_model(model.id, request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_model_deletion_succeeds_without_usage(self) -> None:
        model = ModelCatalog(tenant_id=self.tenant.id, key="m-3", provider="openai",
                             model_name="m-3", display_name="M3")
        self.db.add(model)
        self.db.commit()
        delete_model(model.id, request=self.request, actor=self.actor, db=self.db)
        self.db.expire_all()
        self.assertIsNone(self.db.get(ModelCatalog, model.id))


if __name__ == "__main__":
    unittest.main()
