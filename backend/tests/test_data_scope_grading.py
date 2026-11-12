"""F4 数据范围写分级与叶子码双写的隔离测试（内存 SQLite，不改动开发库）。

覆盖：
- L2（app.admin）写数据范围 → 403；同一 L2 读 → 200；
- 手工给 L2 挂 button.org.manage 节点后写 → 仍 403（节点 + 角色双条件纵深防御）；
- L3 写 → 200，且 RoleDataScope 旧表与 *.scope.* 叶子码授权双写并存；
- 替换收窄/清空后叶子授权镜像收敛，evaluate_access 并集语义不残留放宽范围。
"""

import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.organizations import get_role_data_scopes, replace_role_data_scopes
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.models.organization import Organization, RoleDataScope
from app.schemas.access_control import AuthorizationCheck
from app.schemas.organizations import RoleDataScopeItem, RoleDataScopesUpdate
from app.services.authorization import evaluate_access
from app.services.role_provisioning import (
    L2_GRANT_NODE_CODES,
    L3_GRANT_NODE_CODES,
    provision_application_platform_roles,
    provision_tenant_admin_role,
)
from tests.greenfield_fixture import make_platform_admin_binding


class DataScopeGradingTests(unittest.TestCase):
    """每个用例在内存 SQLite 中运行，夹具仿 test_p405_layering 的绿场风格。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"t-{uuid4().hex[:10]}")
        self.db.add(self.tenant)
        self.db.flush()
        # selected_organizations 策略依 schema 必须携带本租户真实组织，夹具预置一个锚点。
        self.organization = Organization(
            tenant_id=self.tenant.id, key="org-root", name="根组织", status="active",
        )
        self.db.add(self.organization)
        self.db.flush()
        self.application = Application(
            tenant_id=self.tenant.id, client_id=f"a-{uuid4().hex[:8]}",
            name="应用A", permission_namespace="appa",
            redirect_uris=["https://a.example.com/cb"], status="active",
        )
        self.db.add(self.application)
        self.db.flush()
        # 管理面节点目录：L3 模板含 button.org.manage，L2 模板不含（纵深场景需手工挂码）。
        self.catalog: dict[str, Permission] = {}
        for code in sorted(set(L3_GRANT_NODE_CODES) | set(L2_GRANT_NODE_CODES)):
            row = Permission(
                code=code, catalog_namespace="platform",
                resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
                surface="management", requires_data_scope=False,
            )
            self.db.add(row)
            self.catalog[code] = row
        # 业务码：强制数据范围，写策略时叶子码由 ensure_data_scope_children 补建。
        self.business = Permission(
            code="appa.doc.read", catalog_namespace="appa", resource_type="doc",
            scope="read", surface="business", requires_data_scope=True,
        )
        self.db.add(self.business)
        self.db.flush()
        self.l1 = self._user("l1")
        make_platform_admin_binding(self.db, self.l1)
        self.l3 = self._user("l3")
        self.l2 = self._user("l2")
        self.member = self._user("member")
        l3_role = provision_tenant_admin_role(self.db, self.tenant.id)
        # 应用开通预置 (应用管理员, 应用成员) 二元组（多应用管理员已并入应用管理员）。
        self.admin_role, self.member_role = provision_application_platform_roles(
            self.db, self.tenant.id, self.application.id,
        )
        self._bind(self.l3, l3_role)
        self._bind(self.l2, self.admin_role)
        # 只读业务角色：持有业务码，是数据范围策略的配置对象。
        self.reader = Role(
            tenant_id=self.tenant.id, application_id=self.application.id,
            kind="application", key="appa.reader", name="只读", status="active",
        )
        self.db.add(self.reader)
        self.db.flush()
        self.db.add(RolePermission(role_id=self.reader.id, permission_id=self.business.id))
        self.member_membership = self._membership(self.member)
        self._bind(self.member, self.reader)
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "PUT", "path": "/api/v1",
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

    def _policy_body(self, scope_type: str) -> RoleDataScopesUpdate:
        # selected_organizations 依 schema 必须至少携带一个本租户组织；其余范围禁止携带。
        organization_ids = [self.organization.id] if scope_type == "selected_organizations" else []
        return RoleDataScopesUpdate(policies=[RoleDataScopeItem(
            permission_id=self.business.id, scope_type=scope_type,
            organization_ids=organization_ids,
        )])

    def _leaf(self, scope_type: str) -> Permission | None:
        return self.db.scalar(select(Permission).where(
            Permission.code == f"appa.doc.read.scope.{scope_type}",
        ))

    def _role_holds(self, permission_id) -> bool:
        return self.db.scalar(select(RolePermission.id).where(
            RolePermission.role_id == self.reader.id,
            RolePermission.permission_id == permission_id,
        )) is not None

    def _member_check(self) -> dict:
        check = AuthorizationCheck(
            tenant_id=self.tenant.id, application_id=self.application.id,
            permission_code=self.business.code, include_data_scope=True,
        )
        return evaluate_access(check, self.member, self.db)["decision"]

    # ── 写分级：L2 只读 ─────────────────────────────────────────────────────

    def test_l2_write_data_scope_403_and_read_200(self) -> None:
        # L2 应用管理员写数据范围 → 403（缺 button.org.manage 节点 + 缺 L3 角色）。
        with self.assertRaises(HTTPException) as ctx:
            replace_role_data_scopes(
                self.reader.id, self._policy_body("self"),
                self.request, actor=self.l2, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("org.manage", str(ctx.exception.detail))
        # 未落任何旧表策略或叶子授权。
        self.assertEqual(self.db.scalars(select(RoleDataScope).where(
            RoleDataScope.role_id == self.reader.id,
        )).all(), [])
        # 同一 L2 只读查询正常（200，空策略清单）。
        self.assertEqual(get_role_data_scopes(self.reader.id, actor=self.l2, db=self.db), [])

    def test_l2_with_manual_org_manage_code_still_403(self) -> None:
        # 纵深场景：手工给 L2 模板角色挂上 button.org.manage 节点，仍因缺 L3 角色被拒。
        self.db.add(RolePermission(
            role_id=self.admin_role.id, permission_id=self.catalog["button.org.manage"].id,
        ))
        self.db.flush()
        with self.assertRaises(HTTPException) as ctx:
            replace_role_data_scopes(
                self.reader.id, self._policy_body("self"),
                self.request, actor=self.l2, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("L3", str(ctx.exception.detail))

    # ── L3 写 + 双写断言 ────────────────────────────────────────────────────

    def test_l3_write_dual_writes_leaf_grant(self) -> None:
        result = replace_role_data_scopes(
            self.reader.id, self._policy_body("self"),
            self.request, actor=self.l3, db=self.db,
        )
        # 响应回读策略（200 语义）。
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["scope_type"], "self")
        self.assertEqual(result[0]["permission_code"], "appa.doc.read")
        # 双写一：RoleDataScope 旧表照写。
        policy = self.db.scalar(select(RoleDataScope).where(
            RoleDataScope.role_id == self.reader.id,
        ))
        self.assertIsNotNone(policy)
        self.assertEqual(policy.scope_type, "self")
        # 双写二：*.scope.* 叶子权限行存在且角色持有该叶子授权。
        leaf = self._leaf("self")
        self.assertIsNotNone(leaf)
        self.assertEqual(leaf.kind, "data")
        self.assertTrue(self._role_holds(leaf.id))
        # 双读并集语义不回归：成员判权放行且约束为 owner（self）。
        decision = self._member_check()
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["data_scope"]["constraints"], [{
            "kind": "owner", "field": "owner_user_id",
            "user_id": str(self.member.id), "tenant_id": str(self.tenant.id),
        }])

    def test_replace_narrowing_mirrors_leaf_grants(self) -> None:
        # 第一步：配置 tenant 范围 → tenant 叶子被授权。
        replace_role_data_scopes(
            self.reader.id, self._policy_body("tenant"),
            self.request, actor=self.l3, db=self.db,
        )
        leaf_tenant = self._leaf("tenant")
        self.assertIsNotNone(leaf_tenant)
        self.assertTrue(self._role_holds(leaf_tenant.id))
        self.assertTrue(self._member_check()["allowed"])
        # 第二步：收窄为 self → 旧 tenant 叶子授权必须被收敛，不能残留放宽范围。
        replace_role_data_scopes(
            self.reader.id, self._policy_body("self"),
            self.request, actor=self.l3, db=self.db,
        )
        self.assertFalse(self._role_holds(leaf_tenant.id))
        leaf_self = self._leaf("self")
        self.assertTrue(self._role_holds(leaf_self.id))
        # 旧表与叶子码一致：仅剩 self 策略，判权约束同步收窄为 owner。
        decision = self._member_check()
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["data_scope"]["constraints"][0]["kind"], "owner")
        # 第三步：清空策略 → 旧表与叶子授权同时收敛，判权默认拒绝。
        replace_role_data_scopes(
            self.reader.id, RoleDataScopesUpdate(policies=[]),
            self.request, actor=self.l3, db=self.db,
        )
        self.assertEqual(self.db.scalars(select(RoleDataScope).where(
            RoleDataScope.role_id == self.reader.id,
        )).all(), [])
        self.assertFalse(self._role_holds(leaf_self.id))
        decision = self._member_check()
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "data_scope_policy_missing")

    def test_l1_can_replace_data_scopes(self) -> None:
        # 平台管理员代管放行：双写同样生效。
        result = replace_role_data_scopes(
            self.reader.id, self._policy_body("selected_organizations"),
            self.request, actor=self.l1, db=self.db,
        )
        self.assertEqual(result[0]["scope_type"], "selected_organizations")
        leaf = self._leaf("selected_organizations")
        self.assertIsNotNone(leaf)
        self.assertTrue(self._role_holds(leaf.id))
        policy = self.db.scalar(select(RoleDataScope).where(
            RoleDataScope.role_id == self.reader.id,
        ))
        self.assertIsNotNone(policy)
        self.assertEqual(policy.scope_type, "selected_organizations")


if __name__ == "__main__":
    unittest.main()
