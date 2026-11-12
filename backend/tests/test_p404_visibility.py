"""P404：五级可见范围收口——L2 不能新建应用、看不见上级节点与外应用；L3 看不见外租户。"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.access_control import list_permissions, list_role_holders, list_roles
from app.api.v1.admin.applications import create_application, delete_application
from app.api.v1.admin.audit import search_audit
from app.api.v1.admin.model_usage import list_model_usage_events
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import AuditEvent, Tenant, User
from app.models.model_catalog import ModelCatalog, ModelUsageEvent
from app.schemas.applications import ApplicationCreate
from app.services.permission_kinds import ROLE_SCOPE_TENANT
from app.services.role_provisioning import (
    L2_GRANT_NODE_CODES,
    L2_ROLE_KEY,
    L3_GRANT_NODE_CODES,
    L3_ROLE_KEY,
)
from tests.greenfield_fixture import make_tenant_role_binding


class P404VisibilityTests(unittest.TestCase):
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
            name="应用A", permission_namespace="appa", redirect_uris=["https://a.example.test/cb"],
        )
        self.app_b = Application(
            tenant_id=self.tenant.id, client_id=f"b-{uuid4().hex[:8]}",
            name="应用B", permission_namespace="appb", redirect_uris=["https://b.example.test/cb"],
        )
        self.other_app = Application(
            tenant_id=self.other_tenant.id, client_id=f"o-{uuid4().hex[:8]}",
            name="外租户应用", permission_namespace="other", redirect_uris=["https://o.example.test/cb"],
        )
        self.db.add_all([self.app_a, self.app_b, self.other_app])
        self.db.flush()
        # 管理节点目录：L3 模板 + L2 模板；业务码分属三个命名空间。
        self.catalog: dict[str, Permission] = {}
        for code in sorted(set(L3_GRANT_NODE_CODES) | set(L2_GRANT_NODE_CODES)):
            row = Permission(
                code=code, catalog_namespace="platform",
                resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
                surface="management", requires_data_scope=False,
            )
            self.db.add(row)
            self.catalog[code] = row
        for code, namespace in (
            ("appa.doc.read", "appa"),
            ("appb.doc.read", "appb"),
            ("other.doc.read", "other"),
        ):
            row = Permission(
                code=code, catalog_namespace=namespace, resource_type="doc",
                scope="read", surface="business", requires_data_scope=True,
            )
            self.db.add(row)
            self.catalog[code] = row
        self.db.flush()
        # SQLite 把 (tenant_id, key) 当全局唯一，其它应用角色必须用不同 key。
        self.app_b_custom_role = Role(
            tenant_id=self.tenant.id, application_id=self.app_b.id,
            kind="application", key="custom.b", name="应用B自定义", status="active",
        )
        self.other_tenant_admin_role = Role(
            tenant_id=self.other_tenant.id, kind="tenant", key=L3_ROLE_KEY,
            name="外租户管理员", status="active", scope=ROLE_SCOPE_TENANT,
        )
        self.db.add_all([self.app_b_custom_role, self.other_tenant_admin_role])
        self.db.flush()
        self.l2 = self._user("l2")
        self.l3 = self._user("l3")
        # 判权只认节点：模板角色必须显式挂节点，模拟「种子已授权」的真实状态；
        # 节点 ID 从目录常量解析，禁止手抄。L3 模板显式带 scope=tenant（范围过滤依据）。
        self.l2_role = make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=self.l2,
            role_key=L2_ROLE_KEY, role_name="应用管理员",
            application_id=self.app_a.id,
            permission_ids=[self.catalog[code].id for code in L2_GRANT_NODE_CODES],
        )
        self.l3_role = make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=self.l3,
            role_key=L3_ROLE_KEY, role_name="租户管理员",
            permission_ids=[self.catalog[code].id for code in L3_GRANT_NODE_CODES],
        )
        # fixture 不写 scope 列：这里按模板语义回填，供角色列表的范围过滤使用。
        self.l3_role.scope = ROLE_SCOPE_TENANT
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

    def _user(self, prefix: str) -> User:
        user = User(
            email=f"{prefix}-{uuid4().hex[:8]}@example.test",
            password_hash="test-only",
            display_name=prefix,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def _codes(self, payload: dict) -> set[str]:
        return {item["code"] for item in payload["items"]}

    def test_l2_cannot_create_application(self) -> None:
        body = ApplicationCreate(
            tenant_id=self.tenant.id,
            name="越权新建",
            client_id=f"x-{uuid4().hex[:8]}",
            redirect_uris=["https://x.example.test/cb"],
        )
        with self.assertRaises(HTTPException) as ctx:
            create_application(body, self.request, Response(), actor=self.l2, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_l2_cannot_delete_pinned_application(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            delete_application(self.app_a.id, self.request, actor=self.l2, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_l2_permission_catalog_hides_l3_and_foreign_app_codes(self) -> None:
        payload = list_permissions(actor=self.l2, db=self.db)
        codes = self._codes(payload)
        self.assertIn("menu.application_workspace", codes)
        self.assertNotIn("appa.doc.read", codes)
        self.assertNotIn("menu.organization_workspace", codes)
        self.assertNotIn("menu.tenants", codes)
        self.assertNotIn("appb.doc.read", codes)
        self.assertNotIn("other.doc.read", codes)
        self.assertTrue(codes.issubset(set(L2_GRANT_NODE_CODES)))

    def test_l3_permission_catalog_hides_l1_and_foreign_tenant_codes(self) -> None:
        payload = list_permissions(actor=self.l3, db=self.db)
        codes = self._codes(payload)
        self.assertIn("menu.organization_workspace", codes)
        self.assertNotIn("appa.doc.read", codes)
        self.assertNotIn("appb.doc.read", codes)
        self.assertNotIn("button.tenants.manage", codes)
        self.assertNotIn("other.doc.read", codes)
        self.assertTrue(codes.issubset(set(L3_GRANT_NODE_CODES)))

    def test_l2_role_list_only_pinned_application(self) -> None:
        payload = list_roles(
            q=None, kind=None, tenant_id=None, application_id=None, status=None,
            actor=self.l2, db=self.db,
        )
        keys = {(item["key"], item["application_id"]) for item in payload["items"]}
        self.assertTrue(all(item["kind"] == "application" for item in payload["items"]))
        self.assertIn((L2_ROLE_KEY, str(self.app_a.id)), keys)
        self.assertNotIn((L3_ROLE_KEY, None), keys)
        self.assertNotIn(("custom.b", str(self.app_b.id)), keys)

    def test_l3_role_list_global_platform_and_bounded_app_roles(self) -> None:
        # 平台角色全局化：平台类角色（application_id IS NULL）全局可见，不再按租户收口——
        # 本租户与外租户宿主的平台类角色（tenant.admin）都出现在 L3 列表中；
        # 应用类角色仍按数据边界收口，只会出现本租户（绑定租户）的应用角色。
        payload = list_roles(
            q=None, kind=None, tenant_id=None, application_id=None, status=None,
            actor=self.l3, db=self.db,
        )
        platform_rows = [item for item in payload["items"] if item["application_id"] is None]
        application_rows = [item for item in payload["items"] if item["application_id"] is not None]
        keys = {item["key"] for item in payload["items"]}
        self.assertIn(L3_ROLE_KEY, keys)
        self.assertTrue(platform_rows)
        self.assertEqual(
            {item["tenant_id"] for item in application_rows}, {str(self.tenant.id)},
        )

    def test_l2_cannot_read_tenant_admin_holders(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            list_role_holders(self.l3_role.id, actor=self.l2, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_l2_audit_only_pinned_application_targets(self) -> None:
        self.db.add_all([
            AuditEvent(
                actor_user_id=self.l2.id, tenant_id=self.tenant.id,
                action="user.create", target_type="user", target_id=str(self.l3.id),
            ),
            AuditEvent(
                actor_user_id=self.l2.id, tenant_id=self.tenant.id,
                action="application.update", target_type="application",
                target_id=str(self.app_a.id),
            ),
            AuditEvent(
                actor_user_id=self.l2.id, tenant_id=self.tenant.id,
                action="application.update", target_type="application",
                target_id=str(self.app_b.id),
            ),
            AuditEvent(
                actor_user_id=self.l2.id, tenant_id=self.other_tenant.id,
                action="application.update", target_type="application",
                target_id=str(self.other_app.id),
            ),
        ])
        self.db.commit()
        payload = search_audit(
            limit=50, offset=0, action=None, target_type=None, target_id=None,
            outcome=None, actor_user_id=None, tenant_id=None, start_at=None,
            end_at=None, action_prefix=None, actor=self.l2, db=self.db,
        )
        self.assertEqual(payload.total, 1)
        self.assertEqual(payload.items[0].target_id, str(self.app_a.id))

    def test_usage_l2_pinned_app_and_l3_tenant_only(self) -> None:
        # 应用级模板不含模型用量菜单；为验证「应用级按钉住应用收敛」的边界，
        # 给 L2 模板角色补挂 menu.model_usage 节点（min_scope=app 允许）。
        self.db.add(RolePermission(
            role_id=self.l2_role.id, permission_id=self.catalog["menu.model_usage"].id,
        ))
        self.db.commit()
        model_a = ModelCatalog(
            tenant_id=self.tenant.id, key="m-a", provider="test",
            model_name="m-a", display_name="模型A",
        )
        model_other = ModelCatalog(
            tenant_id=self.other_tenant.id, key="m-o", provider="test",
            model_name="m-o", display_name="外租户模型",
        )
        self.db.add_all([model_a, model_other])
        self.db.flush()
        for index, application in enumerate((self.app_a, self.app_b)):
            self.db.add(ModelUsageEvent(
                request_id=f"req-a-{index}", tenant_id=self.tenant.id,
                model_id=model_a.id, application_id=application.id,
                user_id=self.l3.id, input_tokens=1, output_tokens=1,
                outcome="succeeded",
            ))
        self.db.add(ModelUsageEvent(
            request_id="req-other", tenant_id=self.other_tenant.id,
            model_id=model_other.id, application_id=self.other_app.id,
            user_id=self.l3.id, input_tokens=1, output_tokens=1,
            outcome="succeeded",
        ))
        self.db.commit()
        l2_payload = list_model_usage_events(actor=self.l2, db=self.db)
        self.assertEqual({item["application_id"] for item in l2_payload["items"]}, {str(self.app_a.id)})
        l3_payload = list_model_usage_events(actor=self.l3, db=self.db)
        self.assertEqual(
            {item["application_id"] for item in l3_payload["items"]},
            {str(self.app_a.id), str(self.app_b.id)},
        )


if __name__ == "__main__":
    unittest.main()
