"""P383 角色分层守卫隔离测试：授权权码禁选 / 克隆剥离 / 模板码数（内存 SQLite）。

覆盖三级防线：
1. 平台侧 replace_role_permissions：自定义角色含授权权码 → 422；模板角色放行；
2. 租户应用侧 replace_application_role_permissions：自定义应用角色同样 422；
3. clone_role：克隆产物为自定义角色时剥离授权权码；
4. 预置模板：L3 恰好 21 码（覆盖全部授权权码）、L2 恰好 15 码、L4 零管理面码，且幂等。
"""

import unittest
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.admin.access_control import clone_role, replace_role_permissions
from app.api.v1.tenant_admin.application_roles import replace_application_role_permissions
from app.db.base import Base
from app.models.application import Application
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import Tenant, User
from app.schemas.access_control import RoleCloneRequest, RolePermissionsUpdate
from app.services.role_provisioning import (
    AUTHORITY_MANAGE_CODES,
    L2_PERMISSION_CODES,
    L2_ROLE_KEY,
    L3_PERMISSION_CODES,
    L3_ROLE_KEY,
    TEMPLATE_ROLE_KEYS,
    is_custom_role,
    provision_application_admin_role,
    provision_application_member_role,
    provision_tenant_admin_role,
)


def _seed_permission_catalog(db: Session) -> dict[str, Permission]:
    """为模板码全集建立目录行；IAM 管理面码不强制数据范围。"""
    rows = []
    for code in sorted(set(L3_PERMISSION_CODES) | set(L2_PERMISSION_CODES)):
        rows.append(Permission(
            code=code,
            catalog_namespace="iam",
            resource_type=code.removeprefix("iam.").rsplit(".", 1)[0],
            scope=code.rsplit(".", 1)[-1],
            surface="management",
            requires_data_scope=False,
        ))
    db.add_all(rows)
    db.flush()
    return {row.code: row for row in rows}


class RoleHierarchyGuardTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不触碰开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"biz-{uuid4().hex[:10]}")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only",
                          display_name="平台管理员", status="active")
        self.db.add_all([self.tenant, self.actor])
        self.db.flush()
        from tests.greenfield_fixture import make_platform_admin_binding

        make_platform_admin_binding(self.db, self.actor)
        self.catalog = _seed_permission_catalog(self.db)
        self.application = Application(tenant_id=self.tenant.id, client_id=f"client-{uuid4().hex[:8]}",
                                       name="演示应用", permission_namespace="demoapp",
                                       redirect_uris=["https://a.example.test/cb"], status="active")
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

    # ---- 公共小工具 ----

    def pid(self, code: str) -> UUID:
        return self.catalog[code].id

    def make_role(self, key: str, *, kind: str = "tenant",
                  application_id: UUID | None = None) -> Role:
        role = Role(tenant_id=self.tenant.id, application_id=application_id, kind=kind,
                    key=key, name=f"角色-{key}", status="active")
        self.db.add(role)
        self.db.flush()
        return role

    def grant_codes(self, role: Role, *codes: str) -> None:
        for code in codes:
            self.db.add(RolePermission(role_id=role.id, permission_id=self.pid(code)))
        self.db.flush()

    def held_codes(self, role: Role) -> set[str]:
        return set(self.db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id),
        ).all())

    # ---- is_custom_role 语义 ----

    def test_is_custom_role_semantics(self) -> None:
        """四个模板 key 均视为模板角色，其余 key 一律自定义。"""
        for key in ("platform.admin", L3_ROLE_KEY, L2_ROLE_KEY, "app.member"):
            self.assertFalse(is_custom_role(Role(key=key)), key)
        self.assertTrue(is_custom_role(Role(key="ops.manager")))
        self.assertEqual(len(TEMPLATE_ROLE_KEYS), 4)

    # ---- 平台侧 replace 守卫 ----

    def test_custom_role_rejects_authority_codes_on_replace(self) -> None:
        role = self.make_role("ops.manager")
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("app.read"), self.pid("org.member.manage")],
            expected_current_permission_ids=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_role_permissions(role.id, body, self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("自定义角色不可包含授权类权限", str(ctx.exception.detail))
        # 守卫发生在授权落库之前：角色授权保持为空。
        self.assertEqual(self.held_codes(role), set())

    def test_template_role_allows_authority_codes_on_replace(self) -> None:
        """模板角色是授权者的来源：L3 key 挂授权权码不受限。"""
        role = self.make_role(L3_ROLE_KEY)
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("org.member.manage"), self.pid("org.group.manage")],
            expected_current_permission_ids=[],
        )
        result = replace_role_permissions(role.id, body, self.request, actor=self.actor, db=self.db)
        self.assertTrue(result["changed"])
        self.db.expire_all()
        self.assertEqual(self.held_codes(role), {"org.member.manage", "org.group.manage"})

    # ---- 租户应用侧 replace 守卫 ----

    def test_custom_application_role_rejects_authority_codes(self) -> None:
        role = self.make_role("ops.manager", kind="application", application_id=self.application.id)
        body = RolePermissionsUpdate(
            permission_ids=[self.pid("org.member.manage")],
            expected_current_permission_ids=[],
        )
        with self.assertRaises(HTTPException) as ctx:
            replace_application_role_permissions(
                self.application.id, role.id, body, self.request, actor=self.actor, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("自定义角色不可包含授权类权限", str(ctx.exception.detail))

    # ---- 克隆剥离 ----

    def test_clone_strips_authority_codes_from_custom_clone(self) -> None:
        """克隆产物 key 非模板 → 复制授权时强制剥离授权权码，业务码保留。"""
        source = self.make_role("ops.manager")
        self.grant_codes(source, "app.read", "org.member.manage")
        body = RoleCloneRequest(key="ops.manager.copy", name="运维副本", copy_authorizations=True)
        result = clone_role(source.id, body, self.request, actor=self.actor, db=self.db)
        self.assertEqual(result["copied_permission_grant_count"], 1)
        self.db.expire_all()
        clone = self.db.get(Role, UUID(result["id"]))
        self.assertTrue(is_custom_role(clone))
        self.assertEqual(self.held_codes(clone), {"app.read"})
        # 源角色的授权保持原样，剥离只作用于副本。
        self.assertEqual(self.held_codes(source), {"app.read", "org.member.manage"})

    # ---- 模板预置码数 ----

    def test_provisioned_template_role_code_counts(self) -> None:
        tenant_role = provision_tenant_admin_role(self.db, self.tenant.id)
        app_admin = provision_application_admin_role(self.db, self.tenant.id, self.application.id)
        app_member = provision_application_member_role(self.db, self.tenant.id, self.application.id)
        self.assertEqual(self.held_codes(tenant_role), set(L3_PERMISSION_CODES))
        self.assertEqual(len(self.held_codes(tenant_role)), 21)
        # L3 是授权者来源：覆盖全部四个授权权码。
        self.assertTrue(AUTHORITY_MANAGE_CODES <= self.held_codes(tenant_role))
        self.assertEqual(self.held_codes(app_admin), set(L2_PERMISSION_CODES))
        self.assertEqual(len(self.held_codes(app_admin)), 15)
        # L4 不携带任何管理面码。
        self.assertEqual(self.held_codes(app_member), set())
        # 幂等：重复预置不产生重复授权。
        provision_tenant_admin_role(self.db, self.tenant.id)
        provision_application_admin_role(self.db, self.tenant.id, self.application.id)
        self.db.expire_all()
        self.assertEqual(len(self.held_codes(tenant_role)), 21)
        self.assertEqual(len(self.held_codes(app_admin)), 15)


if __name__ == "__main__":
    unittest.main()
