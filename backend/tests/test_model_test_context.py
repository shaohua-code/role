"""模型测试台 test-context 判定回归（内存 SQLite，不动开发库）。

覆盖 docs/模型测试台设计.md §2/§6 在现行边界下的可实施子集：
- 入口 = 超管范围 + button.models.manage（L3/L2/成员一律 403）；
- 三级下发交集判定：目录停用 / 租户未下发 / 应用未下发 → authz_allowed=false
  且 missing 给出可操作缺失层级；全链 active → allowed；
- 目标应用归属校验：应用不存在 404；模型不在平台目录 404（防目录枚举）；
- test_channel_available 恒为 false：M0 前不提供连接探针 / 对话通道，
  页面不得把目录存在或授权判定包装成真实连通。
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.api.v1.admin.model_tests import get_model_test_context
from app.db.base import Base
from app.models.application import Application
from app.models.identity import Tenant, TenantMembership, User
from app.models.model_catalog import ModelCatalog
from app.services.model_distribution import ModelDistribution
from app.services.role_provisioning import (
    L2_GRANT_NODE_CODES,
    L3_GRANT_NODE_CODES,
    RoleProvisioning,
)
from tests.greenfield_fixture import ensure_platform_tenant, make_platform_admin_binding


class ModelTestContextTests(unittest.IsolatedAsyncioTestCase):
    """每个用例在内存 SQLite 中运行；目录行归属 platform 租户。"""

    def setUp(self) -> None:
        # 路由判定经 run_in_threadpool 执行：内存 SQLite 需允许跨线程复用同一连接
        # （StaticPool 单连接 + 关闭线程亲和）；生产 PostgreSQL 连接池本身支持。
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.platform_tenant = ensure_platform_tenant(self.db)
        self.tenant = self._tenant("业务租户", f"t-{uuid4().hex[:10]}")
        self.other_tenant = self._tenant("他租户", f"o-{uuid4().hex[:10]}")
        self.app_a = self._application(self.tenant, "appa")
        self.app_b = self._application(self.tenant, "appb")
        self.other_app = self._application(self.other_tenant, "appo")
        # 管理面节点目录，供 provision 角色授权（与 test_model_distribution 同口径）。
        from app.models.authorization import Permission

        for code in sorted(set(L3_GRANT_NODE_CODES) | set(L2_GRANT_NODE_CODES)):
            self.db.add(Permission(
                code=code, catalog_namespace="platform",
                resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
                surface="management", requires_data_scope=False,
            ))
        self.db.flush()
        # 操作者：L1（测试台现行唯一边界）；L3/L2 仅用于验证 403 闸门。
        self.l1 = self._user("l1")
        make_platform_admin_binding(self.db, self.l1)
        self.l3 = self._user("l3")
        l3_role = RoleProvisioning.provision_tenant_admin_role(self.db)
        self._bind(self.l3, self.tenant, l3_role)
        self.l2 = self._user("l2")
        admin_role, _member_role = RoleProvisioning.provision_application_platform_roles(
            self.db, self.tenant.id, self.app_a.id,
        )
        self._bind(self.l2, self.tenant, admin_role)
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "GET", "path": "/api/v1",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ── 夹具辅助（与 test_model_distribution 同构） ─────────────────────────

    def _tenant(self, name: str, slug: str) -> Tenant:
        row = Tenant(name=name, slug=slug)
        self.db.add(row)
        self.db.flush()
        return row

    def _application(self, tenant: Tenant, namespace: str) -> Application:
        row = Application(
            tenant_id=tenant.id, client_id=f"{namespace}-{uuid4().hex[:8]}",
            name=f"应用-{namespace}", permission_namespace=namespace,
            redirect_uris=[f"https://{namespace}.example.com/cb"], status="active",
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _user(self, tag: str) -> User:
        row = User(email=f"{tag}-{uuid4().hex[:8]}@example.test",
                   password_hash="test-only", display_name=tag)
        self.db.add(row)
        self.db.flush()
        return row

    def _bind(self, user: User, tenant: Tenant, role) -> None:
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, status="active")
        self.db.add(membership)
        self.db.flush()
        from app.models.authorization import RoleBinding

        self.db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
        self.db.flush()

    def _model(self, key: str, *, status: str = "active") -> ModelCatalog:
        row = ModelCatalog(
            tenant_id=self.platform_tenant.id, key=key, provider="test-provider",
            model_name=key, display_name=key.upper(), capabilities=["chat", "reasoning"],
            status=status, credential_ref=f"cred://{key}",
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _context(self, model: ModelCatalog, application=None, *, actor=None):
        """路由已 async 化（线程池包同步判定），直调需 await。"""
        return get_model_test_context(
            model.id,
            None if application is None else application.id,
            actor or self.l1, self.db,
        )

    # ── 入口边界 ────────────────────────────────────────────────────────────

    async def test_requires_super_scope(self) -> None:
        """L3 / L2 / 未授权成员一律 403：超管范围 + 按钮码双重收口。"""
        model = self._model("m-gate")
        for actor in (self.l3, self.l2):
            with self.assertRaises(HTTPException) as denied:
                await self._context(model, self.app_a, actor=actor)
            self.assertEqual(denied.exception.status_code, 403)

    async def test_unknown_or_non_platform_model_404(self) -> None:
        """不存在 / 非平台目录行与缺失不可区分（404，防目录枚举）。"""
        with self.assertRaises(HTTPException) as missing:
            await get_model_test_context(uuid4(), None, self.l1, self.db)
        self.assertEqual(missing.exception.status_code, 404)
        foreign = ModelCatalog(
            tenant_id=self.tenant.id, key="m-foreign", provider="p", model_name="m",
            display_name="M", capabilities=["chat"], status="active",
        )
        self.db.add(foreign)
        self.db.flush()
        with self.assertRaises(HTTPException) as not_platform:
            await self._context(foreign)
        self.assertEqual(not_platform.exception.status_code, 404)

    async def test_unknown_application_404(self) -> None:
        model = self._model("m-app404")
        with self.assertRaises(HTTPException) as denied:
            await get_model_test_context(model.id, uuid4(), self.l1, self.db)
        self.assertEqual(denied.exception.status_code, 404)

    # ── 三级下发交集判定 ────────────────────────────────────────────────────

    async def test_full_chain_allowed(self) -> None:
        """目录 active + 租户下发 + 应用下发全链 active → authz_allowed=true。"""
        model = self._model("m-full")
        ModelDistribution.grant_to_tenant(self.db, model.id, self.tenant.id, self.l1.id)
        ModelDistribution.grant_to_application(self.db, model.id, self.app_a, self.l1.id)
        result = await self._context(model, self.app_a)
        self.assertTrue(result["authz_allowed"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["levels"], {
            "platform_catalog": "active", "tenant_grant": "active", "application_grant": "active",
        })
        self.assertTrue(result["operator_app_access"])
        # 受控出口已接入：通道可用标记为 true。
        self.assertTrue(result["test_channel_available"])
        self.assertEqual(result["model"]["id"], str(model.id))
        self.assertTrue(result["model"]["credential_configured"])
        self.assertEqual(result["application"]["tenant_name"], self.tenant.name)

    async def test_missing_levels_reported_individually(self) -> None:
        """租户 / 应用下发缺失分别指出缺失层级，发送闸门为 false。"""
        model = self._model("m-partial")
        result = await self._context(model, self.app_a)
        self.assertFalse(result["authz_allowed"])
        self.assertEqual(result["levels"]["tenant_grant"], "missing")
        self.assertEqual(result["levels"]["application_grant"], "missing")
        self.assertIn("租户未下发该模型", result["missing"])
        self.assertIn("应用未下发该模型", result["missing"])

    async def test_tenant_grant_missing_blocks_app_grant_judgment(self) -> None:
        """租户未收到时应用下发不可能存在（级联软失效口径）；两级均报 missing。"""
        model = self._model("m-cascade")
        ModelDistribution.grant_to_tenant(self.db, model.id, self.tenant.id, self.l1.id)
        ModelDistribution.grant_to_application(self.db, model.id, self.app_a, self.l1.id)
        ModelDistribution.revoke_from_tenant(self.db, model.id, self.tenant.id)
        result = await self._context(model, self.app_a)
        self.assertFalse(result["authz_allowed"])
        self.assertEqual(result["levels"]["tenant_grant"], "missing")
        self.assertEqual(result["levels"]["application_grant"], "missing")

    async def test_disabled_model_reports_config_failure(self) -> None:
        """模型停用 → 目录层级 disabled，缺失层级为「模型已停用」（下发关系仍保留）。"""
        model = self._model("m-disabled")
        ModelDistribution.grant_to_tenant(self.db, model.id, self.tenant.id, self.l1.id)
        ModelDistribution.grant_to_application(self.db, model.id, self.app_a, self.l1.id)
        model.status = "disabled"
        self.db.flush()
        result = await self._context(model, self.app_a)
        self.assertEqual(result["levels"]["platform_catalog"], "disabled")
        self.assertFalse(result["authz_allowed"])
        self.assertIn("模型已停用", result["missing"])

    async def test_cross_tenant_application_reports_missing_tenant_grant(self) -> None:
        """目标应用属他租户：本租户下发关系不适用，判权仍为 false。"""
        model = self._model("m-cross")
        ModelDistribution.grant_to_tenant(self.db, model.id, self.tenant.id, self.l1.id)
        result = await self._context(model, self.other_app)
        self.assertFalse(result["authz_allowed"])
        self.assertEqual(result["levels"]["tenant_grant"], "missing")
        self.assertIn("租户未下发该模型", result["missing"])

    async def test_context_without_application_only_judges_catalog(self) -> None:
        """未选应用（平台连接视角）：只判目录层级，授权交由外呼前逐次判定。"""
        model = self._model("m-platform")
        result = await self._context(model)
        self.assertEqual(result["application"], None)
        self.assertTrue(result["authz_allowed"])
        self.assertEqual(result["levels"]["tenant_grant"], "missing")


if __name__ == "__main__":
    unittest.main()
