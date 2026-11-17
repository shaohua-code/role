"""模型三级分发回归（内存 SQLite，不动开发库）。

覆盖产品需求 §6.4 与验收标准 15：
- 平台目录归属 platform 租户，写操作仅超管（button.models.manage）；
- 超管下发 / 回收租户（软失效、幂等复活、级联应用下发）；
- 租户管理员在应用工作台下发 / 回收应用（button.models.distribute，L2 只读）；
- 三级可见性唯一口径（list_models 三视角、my-models 交集）；
- my-models 绑定已验证 OIDC 应用身份（同租户跨应用 / 管理会话一律拒绝）；
- 按 ID 操作强制平台租户归属（非平台目录行 404，领域服务同口径）；
- model.invoke 按「活动模型 + 活动租户下发 + 活动应用下发 + 主体有效角色」判定；
- 用量预留按「租户下发 + 应用下发均 active」收口。
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.models import (
    create_model,
    delete_model,
    grant_model_to_tenant,
    list_model_tenant_grants,
    list_models,
    revoke_model_from_tenant,
    set_model_status,
    update_model,
)
from app.api.v1.authorization import list_my_models
from app.api.v1.model_usage import reserve_usage
from app.api.v1.tenant_admin.application_models import (
    grant_application_model,
    list_application_models,
    revoke_application_model,
)
from app.core.config import get_settings
from app.db.base import Base
from app.models.application import Application
from app.models.identity import TenantMembership, User
from app.models.model_catalog import (
    ModelApplicationGrant,
    ModelCatalog,
    ModelTenantGrant,
)
from app.schemas.access_control import AuthorizationCheck
from app.schemas.models import (
    ModelApplicationGrantCreate,
    ModelCatalogCreate,
    ModelCatalogStatusUpdate,
    ModelCatalogUpdate,
    ModelTenantGrantCreate,
)
from app.services.authorization import AuthorizationEvaluator
from app.services.model_distribution import ModelDistribution
from app.services.permission_impact import PermissionImpactService
from app.services.role_provisioning import (
    L2_GRANT_NODE_CODES,
    L3_GRANT_NODE_CODES,
    RoleProvisioning,
)
from tests.greenfield_fixture import ensure_platform_tenant, make_platform_admin_binding


class ModelDistributionTests(unittest.TestCase):
    """每个用例在内存 SQLite 中运行；平台目录行归属 platform 租户。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.platform_tenant = ensure_platform_tenant(self.db)
        self.tenant = self._tenant("业务租户", f"t-{uuid4().hex[:10]}")
        self.other_tenant = self._tenant("他租户", f"o-{uuid4().hex[:10]}")
        self.app_a = self._application(self.tenant, "appa")
        self.app_b = self._application(self.tenant, "appb")
        self.other_app = self._application(self.other_tenant, "appo")
        # 管理面节点目录（L3/L2 模板节点全集），供 provision 角色授权。
        from app.models.authorization import Permission

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
        # 操作者：L1 / L3 / L2（钉 app_a）/ 普通成员（my-models 调用者）。
        self.l1 = self._user("l1")
        make_platform_admin_binding(self.db, self.l1)
        self.l3 = self._user("l3")
        l3_role = RoleProvisioning.provision_tenant_admin_role(self.db)
        self._bind(self.l3, self.tenant, l3_role)
        self.l2 = self._user("l2")
        admin_role, member_role = RoleProvisioning.provision_application_platform_roles(
            self.db, self.tenant.id, self.app_a.id,
        )
        self.l2_admin_role = admin_role
        self._bind(self.l2, self.tenant, admin_role)
        self.member = self._user("member")
        self._bind(self.member, self.tenant, member_role)
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

    # ── 夹具辅助 ────────────────────────────────────────────────────────────

    def _tenant(self, name: str, slug: str):
        from app.models.identity import Tenant

        row = Tenant(name=name, slug=slug)
        self.db.add(row)
        self.db.flush()
        return row

    def _application(self, tenant, namespace: str):
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

    def _bind(self, user: User, tenant, role) -> None:
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, status="active")
        self.db.add(membership)
        self.db.flush()
        from app.models.authorization import RoleBinding

        self.db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
        self.db.flush()

    @staticmethod
    def _oidc(user: User, application) -> User:
        """模拟 current_user 验签后的 OIDC 上下文：应用身份取自 token，不由调用方传入。"""
        user._auth_protocol = "oidc"
        user._oidc_application_id = application.id
        return user

    def _create_model(self, key: str, actor) -> dict:
        return create_model(
            ModelCatalogCreate(key=key, provider="test", model_name=key,
                               display_name=key.upper(), capabilities=["chat"]),
            self.request, actor, self.db,
        )

    @staticmethod
    def _mid(value) -> UUID:
        """直调 handler 时把 dict 响应 / str id 显式转回 UUID（裸路径参数惯例）。"""
        if isinstance(value, dict):
            value = value["id"]
        return value if isinstance(value, UUID) else UUID(str(value))

    def _grant_tenant(self, model_id, tenant_id) -> dict:
        return grant_model_to_tenant(
            self._mid(model_id),
            ModelTenantGrantCreate(tenant_id=tenant_id), self.request, self.l1, self.db)

    def _grant_app(self, model_id, application_id, actor=None) -> dict:
        return grant_application_model(
            application_id, ModelApplicationGrantCreate(model_id=self._mid(model_id)),
            self.request, actor or self.l3, self.db)

    def _app_grant_count(self, model_id) -> int:
        return self.db.scalar(select(func.count()).select_from(ModelApplicationGrant).where(
            ModelApplicationGrant.model_id == self._mid(model_id),
            ModelApplicationGrant.status == "active",
        )) or 0

    # ── 平台目录 ────────────────────────────────────────────────────────────

    def test_create_model_assigns_platform_tenant_and_rejects_non_super(self) -> None:
        """目录行归属平台租户；L3 / L2 无写权限（范围闸门 + 按钮节点双重收口）。"""
        result = self._create_model("gpt-test", self.l1)
        self.assertEqual(result["tenant_id"], str(self.platform_tenant.id))
        row = self.db.get(ModelCatalog, self._mid(result))
        self.assertEqual(row.tenant_id, self.platform_tenant.id)
        with self.assertRaises(HTTPException) as denied:
            self._create_model("gpt-l3", self.l3)
        self.assertEqual(denied.exception.status_code, 403)
        # 契约：Create 不含 tenant_id 字段（归属一律由服务端指定）。
        self.assertNotIn("tenant_id", ModelCatalogCreate.model_fields)

    # ── 平台 → 租户 下发 / 回收 ─────────────────────────────────────────────

    def test_grant_tenant_is_idempotent_revivable_and_platform_tenant_rejected(self) -> None:
        model = self._create_model("m-idem", self.l1)
        mid = self._mid(model)
        first = self._grant_tenant(model, self.tenant.id)
        self.assertTrue(first["created"])
        repeat = self._grant_tenant(model, self.tenant.id)
        self.assertFalse(repeat["created"])
        total = self.db.scalar(select(func.count()).select_from(ModelTenantGrant).where(
            ModelTenantGrant.model_id == mid))
        self.assertEqual(total, 1)
        with self.assertRaises(HTTPException) as denied:
            self._grant_tenant(model, self.platform_tenant.id)
        self.assertEqual(denied.exception.status_code, 422)

    def test_revoke_tenant_is_soft_cascade_and_404_when_never_granted(self) -> None:
        model = self._create_model("m-revoke", self.l1)
        mid = self._mid(model)
        self._grant_tenant(model, self.tenant.id)
        self._grant_app(model, self.app_a.id)
        self._grant_app(model, self.app_b.id)
        result = revoke_model_from_tenant(
            mid, self.tenant.id, self.request, self.l1, self.db)
        self.assertEqual(result["cascaded_applications"], 2)
        grants = self.db.scalars(select(ModelTenantGrant).where(
            ModelTenantGrant.model_id == mid)).all()
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0].status, "revoked")
        self.assertIsNotNone(grants[0].revoked_at)
        # 软失效后 L3 视角不再可见；重新下发复活同一行。
        self.assertEqual(list_models(self.l3, self.db), [])
        self.assertTrue(self._grant_tenant(model, self.tenant.id)["created"])
        rows = self.db.scalars(select(ModelTenantGrant).where(
            ModelTenantGrant.model_id == mid)).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "active")
        with self.assertRaises(HTTPException) as missing:
            revoke_model_from_tenant(
                mid, self.other_tenant.id, self.request, self.l1, self.db)
        self.assertEqual(missing.exception.status_code, 404)

    # ── 列表三视角与下发关系清单 ────────────────────────────────────────────

    def test_list_models_views_per_scope(self) -> None:
        m1 = self._create_model("m-view-a", self.l1)
        self._create_model("m-view-b", self.l1)
        self._grant_tenant(m1["id"], self.tenant.id)
        # 超管：全集 + 下发计数。
        l1_rows = list_models(self.l1, self.db)
        self.assertEqual(len(l1_rows), 2)
        counts = {row["key"]: row.get("tenant_grant_count") for row in l1_rows}
        self.assertEqual(counts["m-view-a"], 1)
        self.assertEqual(counts["m-view-b"], 0)
        # 租户级：只见收到的模型 + 本租户活跃应用下发计数。
        l3_rows = list_models(self.l3, self.db)
        self.assertEqual([row["key"] for row in l3_rows], ["m-view-a"])
        self.assertEqual(l3_rows[0]["application_grant_count"], 0)
        self._grant_app(m1["id"], self.app_a.id)
        self.assertEqual(list_models(self.l3, self.db)[0]["application_grant_count"], 1)
        # 应用级：L2 模板本无 menu.models（403）；显式补挂后只见绑定应用收到的模型（无计数泄漏）。
        from app.models.authorization import RolePermission

        self.db.add(RolePermission(
            role_id=self.l2_admin_role.id,
            permission_id=self.catalog["menu.models"].id))
        self.db.commit()
        l2_rows = list_models(self.l2, self.db)
        self.assertEqual([row["key"] for row in l2_rows], ["m-view-a"])
        self.assertNotIn("tenant_grant_count", l2_rows[0])

    def test_tenant_grants_listing_scoped_by_actor(self) -> None:
        model = self._create_model("m-grants", self.l1)
        self._grant_tenant(model, self.tenant.id)
        self._grant_tenant(model, self.other_tenant.id)
        l1_rows = list_model_tenant_grants(self._mid(model), self.l1, self.db)
        self.assertEqual(len(l1_rows), 2)
        l3_rows = list_model_tenant_grants(self._mid(model), self.l3, self.db)
        self.assertEqual({row["tenant_id"] for row in l3_rows}, {str(self.tenant.id)})

    # ── 应用工作台模型 Tab：清单 + 下发 / 回收 ──────────────────────────────

    def test_application_models_tab_lists_received_and_granted(self) -> None:
        granted = self._create_model("m-tab-on", self.l1)
        self._create_model("m-tab-off", self.l1)
        self._grant_tenant(granted["id"], self.tenant.id)
        payload = list_application_models(self.app_a.id, self.l3, self.db)
        self.assertEqual([row["key"] for row in payload["received"]], ["m-tab-on"])
        self.assertEqual(payload["granted_model_ids"], [])
        self._grant_app(granted["id"], self.app_a.id)
        payload = list_application_models(self.app_a.id, self.l3, self.db)
        self.assertEqual(payload["granted_model_ids"], [granted["id"]])

    def test_grant_application_requires_tenant_grant_and_distribute_code(self) -> None:
        granted = self._create_model("m-grant-flow", self.l1)
        other = self._create_model("m-not-received", self.l1)
        granted_mid = self._mid(granted)
        self._grant_tenant(granted, self.tenant.id)
        # 租户未收到 m-not-received → 与不存在不可区分（404 防目录枚举）。
        with self.assertRaises(HTTPException) as missing:
            self._grant_app(other, self.app_a.id)
        self.assertEqual(missing.exception.status_code, 404)
        self.assertTrue(self._grant_app(granted, self.app_a.id)["created"])
        self.assertFalse(self._grant_app(granted, self.app_a.id)["created"])
        # L2（应用级）读得到清单，但没有 button.models.distribute（min_scope=tenant）→ 写 403。
        payload = list_application_models(self.app_a.id, self.l2, self.db)
        self.assertEqual(len(payload["received"]), 1)
        with self.assertRaises(HTTPException) as denied:
            self._grant_app(granted, self.app_a.id, actor=self.l2)
        self.assertEqual(denied.exception.status_code, 403)
        # L3 回收（软失效）；未下发的 other 模型回收 404。
        result = revoke_application_model(
            self.app_a.id, granted_mid, self.request, self.l3, self.db)
        self.assertEqual(result["status"], "revoked")
        with self.assertRaises(HTTPException) as never:
            revoke_application_model(
                self.app_a.id, self._mid(other), self.request, self.l3, self.db)
        self.assertEqual(never.exception.status_code, 404)

    # ── my-models 三级交集 ──────────────────────────────────────────────────

    def test_my_models_returns_exact_three_level_intersection(self) -> None:
        model = self._create_model("m-my", self.l1)
        other_tenant_model = self._create_model("m-my-other", self.l1)
        client_id = self.app_a.client_id
        caller = self._oidc(self.member, self.app_a)
        # 未下发 → 空。
        self.assertEqual(list_my_models(client_id, caller, self.db), [])
        self._grant_tenant(model, self.tenant.id)
        # 租户收到但未下发应用 → 仍空。
        self.assertEqual(list_my_models(client_id, caller, self.db), [])
        self._grant_app(model, self.app_a.id)
        rows = list_my_models(client_id, caller, self.db)
        self.assertEqual([row["key"] for row in rows], ["m-my"])
        self.assertNotIn("endpoint_url", rows[0])
        self.assertNotIn("credential_ref", rows[0])
        # 回收应用下发 → 立即消失。
        revoke_application_model(self.app_a.id, self._mid(model), self.request, self.l3, self.db)
        self.assertEqual(list_my_models(client_id, caller, self.db), [])
        # 恢复后停用平台模型 → 全链路不可见。
        self._grant_app(model, self.app_a.id)
        row = self.db.get(ModelCatalog, self._mid(model))
        row.status = "disabled"
        self.db.flush()
        self.assertEqual(list_my_models(client_id, caller, self.db), [])
        self.assertEqual(self._app_grant_count(other_tenant_model["id"]), 0)

    def test_my_models_rejects_cross_application_and_management_session(self) -> None:
        """P1 收口：清单范围绑定已验证应用身份，不信任客户端传入的 client_id。"""
        granted = self._create_model("m-cross", self.l1)
        self._grant_tenant(granted, self.tenant.id)
        self._grant_app(granted, self.app_a.id)
        # 同租户持应用 A token 查应用 B → 拒绝，且不得返回任何模型字段。
        cross = self._oidc(self.member, self.app_a)
        with self.assertRaises(HTTPException) as denied:
            list_my_models(self.app_b.client_id, cross, self.db)
        self.assertEqual(denied.exception.status_code, 403)
        # 他租户成员持本租户应用的 client_id 查询 → 同样拒绝（不泄露目标应用信息）。
        outsider = self._user("outsider")
        self.db.add(TenantMembership(user_id=outsider.id, tenant_id=self.other_tenant.id, status="active"))
        self.db.flush()
        with self.assertRaises(HTTPException) as foreign:
            list_my_models(self.app_a.client_id, self._oidc(outsider, self.other_app), self.db)
        self.assertEqual(foreign.exception.status_code, 403)
        # 管理会话（无已验证 OIDC 应用上下文）→ fail-closed 拒绝；用独立用户避免
        # 与上一分支共享被写入 OIDC 上下文的同一 ORM 身份。
        console_user = self._user("console")
        self.db.add(TenantMembership(user_id=console_user.id, tenant_id=self.tenant.id, status="active"))
        self.db.flush()
        with self.assertRaises(HTTPException) as denied_session:
            list_my_models(self.app_a.client_id, console_user, self.db)
        self.assertEqual(denied_session.exception.status_code, 403)

    # ── 平台租户归属不变式（按 ID 操作）────────────────────────────────────

    def _rogue_model(self) -> ModelCatalog:
        """直接造一条归属业务租户的异常目录行（模拟存量脏数据）。"""
        rogue = ModelCatalog(
            key=f"rogue-{uuid4().hex[:8]}", provider="test", model_name="rogue",
            display_name="Rogue", tenant_id=self.tenant.id, capabilities=["chat"],
        )
        self.db.add(rogue)
        self.db.flush()
        return rogue

    def test_non_platform_catalog_rows_rejected_by_id_based_operations(self) -> None:
        """P2 收口：非平台目录行对所有按 ID 操作 404，且不进入三级可见性。"""
        rogue = self._rogue_model()
        rid = rogue.id
        # 编辑 / 状态 / 删除 / 租户下发 / 应用下发全部 404（与不存在不可区分）。
        with self.assertRaises(HTTPException) as denied:
            update_model(rid, ModelCatalogUpdate(display_name="Hijacked"), self.request, self.l1, self.db)
        self.assertEqual(denied.exception.status_code, 404)
        with self.assertRaises(HTTPException) as status_denied:
            set_model_status(rid, ModelCatalogStatusUpdate(expected_status="active", status="disabled"),
                             self.request, self.l1, self.db)
        self.assertEqual(status_denied.exception.status_code, 404)
        with self.assertRaises(HTTPException) as delete_denied:
            delete_model(rid, self.request, self.l1, self.db)
        self.assertEqual(delete_denied.exception.status_code, 404)
        with self.assertRaises(HTTPException) as grant_denied:
            grant_model_to_tenant(rid, ModelTenantGrantCreate(tenant_id=self.tenant.id),
                                  self.request, self.l1, self.db)
        self.assertEqual(grant_denied.exception.status_code, 404)
        with self.assertRaises(HTTPException) as app_denied:
            grant_application_model(self.app_a.id, ModelApplicationGrantCreate(model_id=rid),
                                    self.request, self.l3, self.db)
        self.assertEqual(app_denied.exception.status_code, 404)
        # 超管目录列表与三级可见性（租户 / 应用 / my-models）都不出现异常行。
        self.assertEqual([row["key"] for row in list_models(self.l1, self.db)], [])
        self.db.add(ModelTenantGrant(model_id=rid, tenant_id=self.tenant.id, status="active"))
        self.db.add(ModelApplicationGrant(
            model_id=rid, tenant_id=self.tenant.id, application_id=self.app_a.id, status="active"))
        self.db.flush()
        self.assertEqual(ModelDistribution.list_models_for_tenant(self.db, self.tenant.id), [])
        self.assertEqual(ModelDistribution.list_models_for_application(self.db, self.app_a), [])
        self.assertEqual(list_my_models(
            self.app_a.client_id, self._oidc(self.member, self.app_a), self.db), [])
        # 正常平台目录行仍可操作（避免修复误伤合法路径）。
        normal = self._create_model("m-normal", self.l1)
        updated = update_model(self._mid(normal), ModelCatalogUpdate(display_name="改名"),
                               self.request, self.l1, self.db)
        self.assertEqual(updated["updated_fields"], ["display_name"])
        status_result = set_model_status(
            self._mid(normal), ModelCatalogStatusUpdate(expected_status="active", status="disabled"),
            self.request, self.l1, self.db)
        self.assertEqual(status_result["status"], "disabled")

    # ── model.invoke 三级下发判权（/authorization/check 唯一口径）───────────

    def _invoke_check(self, model, application, tenant=None) -> dict:
        """构造网关调用前检查；管理模拟路径（无 token 上下文钉定）。"""
        body = AuthorizationCheck(
            tenant_id=tenant.id if tenant else self.tenant.id,
            application_id=application.id,
            permission_code="model.invoke",
            resource_id=str(model["id"] if isinstance(model, dict) else model.id),
        )
        return AuthorizationEvaluator.evaluate_access(body, self.member, self.db)["decision"]

    def test_model_invoke_follows_three_level_distribution(self) -> None:
        """P1 收口：model.invoke 按三级下发关系判定，不再看目录行租户归属。"""
        granted = self._create_model("m-invoke", self.l1)
        # 未下发 → 拒绝（旧口径下 catalog 行在平台租户同样拒绝，但原因是归属不匹配）。
        decision = self._invoke_check(granted, self.app_a)
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "model_tenant_grant_inactive")
        self._grant_tenant(granted, self.tenant.id)
        # 只下发租户、未下发应用 → 拒绝。
        decision = self._invoke_check(granted, self.app_a)
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "model_application_grant_inactive")
        self._grant_app(granted, self.app_a.id)
        # 三级齐备 + 主体持应用有效角色（member 钉 app_a）→ 放行。
        decision = self._invoke_check(granted, self.app_a)
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["reason"], "model_distribution_grant")
        # 回收应用下发 → 立即拒绝。
        revoke_application_model(self.app_a.id, self._mid(granted), self.request, self.l3, self.db)
        self.assertFalse(self._invoke_check(granted, self.app_a)["allowed"])
        self._grant_app(granted, self.app_a.id)
        # 停用平台模型 → 拒绝。
        row = self.db.get(ModelCatalog, self._mid(granted))
        row.status = "disabled"
        self.db.flush()
        decision = self._invoke_check(granted, self.app_a)
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "model_inactive_or_missing")
        row.status = "active"
        self.db.flush()
        # 无应用上下文（tenant-wide 请求）→ 拒绝；未下发模型 → 拒绝。
        no_app = AuthorizationCheck(
            tenant_id=self.tenant.id, permission_code="model.invoke",
            resource_id=str(self._mid(granted)))
        decision = AuthorizationEvaluator.evaluate_access(no_app, self.member, self.db)["decision"]
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "model_application_context_required")
        other = self._create_model("m-invoke-other", self.l1)
        decision = self._invoke_check(other, self.app_a)
        self.assertFalse(decision["allowed"])
        # 主体对目标应用无有效角色（纯成员关系、无任何绑定）→ 拒绝。
        bare_user = self._user("bare")
        self.db.add(TenantMembership(user_id=bare_user.id, tenant_id=self.tenant.id, status="active"))
        self.db.flush()
        body = AuthorizationCheck(
            tenant_id=self.tenant.id, application_id=self.app_a.id,
            permission_code="model.invoke", resource_id=str(self._mid(granted)))
        decision = AuthorizationEvaluator.evaluate_access(body, bare_user, self.db)["decision"]
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "no_effective_role_in_target_application")
        # OIDC token 钉定应用：持 app_a token 查 app_b → token 上下文不匹配拒绝。
        oidc_user = self._oidc(self.member, self.app_a)
        cross_body = AuthorizationCheck(
            tenant_id=self.tenant.id, application_id=self.app_b.id,
            permission_code="model.invoke", resource_id=str(self._mid(granted)))
        decision = AuthorizationEvaluator.evaluate_access(cross_body, oidc_user, self.db)["decision"]
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "token_application_mismatch")

    def test_model_invoke_impact_uses_distribution_semantics(self) -> None:
        """影响分析与在线判权同口径：按三级下发关系判断 model.invoke 是否可能生效。"""
        from app.models.authorization import Role

        role = Role(key=f"biz-{uuid4().hex[:8]}", name="业务角色", kind="tenant",
                    tenant_id=self.tenant.id, application_id=None, status="active")
        self.db.add(role)
        self.db.flush()
        model = self._create_model("m-impact", self.l1)
        # 无租户下发 → 不可能生效。
        self.assertFalse(PermissionImpactService._permission_can_be_live(role, "model.invoke", self.db, None))
        self._grant_tenant(model, self.tenant.id)
        # 租户下发后 → 通用角色可生效。
        self.assertTrue(PermissionImpactService._permission_can_be_live(role, "model.invoke", self.db, None))
        # 应用级角色：还需要其钉住的应用存在活动应用下发（应用角色必须传应用对象）。
        app_role = Role(key=f"app-biz-{uuid4().hex[:8]}", name="应用业务角色", kind="application",
                        tenant_id=self.tenant.id, application_id=self.app_a.id, status="active")
        self.db.add(app_role)
        self.db.flush()
        self.assertFalse(PermissionImpactService._permission_can_be_live(
            app_role, "model.invoke", self.db, self.app_a))
        self._grant_app(model, self.app_a.id)
        self.assertTrue(PermissionImpactService._permission_can_be_live(
            app_role, "model.invoke", self.db, self.app_a))

    # ── 用量预留与三级下发的一致性 ──────────────────────────────────────────

    def test_reservation_requires_active_tenant_and_application_grants(self) -> None:
        from app.schemas.models import ModelUsageReservationRequest

        model = self._create_model("m-quota", self.l1)
        body = ModelUsageReservationRequest(
            request_id=f"req-{uuid4().hex[:12]}", tenant_id=self.tenant.id,
            model_id=model["id"], application_id=self.app_a.id, user_id=self.member.id,
            reserved_input_tokens=10, reserved_output_tokens=20)
        settings = SimpleNamespace(
            model_usage_api_key="test-only-model-gateway-key-0123456789",
            model_quota_enforcement_enabled=False)
        with patch("app.api.v1.model_usage.get_settings", return_value=settings):
            # 未下发租户 → 422。
            with self.assertRaises(HTTPException) as denied:
                reserve_usage(body, settings.model_usage_api_key, self.db)
            self.assertEqual(denied.exception.status_code, 422)
            self._grant_tenant(model["id"], self.tenant.id)
            # 租户已下发但应用未下发 → 仍 422。
            with self.assertRaises(HTTPException) as denied:
                reserve_usage(body, settings.model_usage_api_key, self.db)
            self.assertEqual(denied.exception.status_code, 422)
            self._grant_app(model["id"], self.app_a.id)
            result = reserve_usage(body, settings.model_usage_api_key, self.db)
            self.assertTrue(result["allowed"])


if __name__ == "__main__":
    unittest.main()
