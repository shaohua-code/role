"""用户组挂角色的「范围只能向下」守卫隔离测试（内存 SQLite）。

覆盖 1.3 缺口：组角色渠道此前只校验租户归属，L3 可借 PUT /user-groups/{id}/roles
绑定 scope=super 角色提权。验证：
1. L3 租户管理员提交含 super 角色的组角色 body → 403 且组角色未被修改；
2. L3 请求组角色目录 → 响应不含 scope=super 角色。
"""

import unittest
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.groups import (
    create_user_group,
    list_user_group_roles,
    replace_user_group_roles,
)
from app.db.base import Base
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroupRole
from app.models.identity import Tenant, TenantMembership, User
from app.schemas.groups import UserGroupCreate, UserGroupRolesUpdate
from app.services.permission_kinds import ROLE_SCOPE_SUPER, ROLE_SCOPE_TENANT


class UserGroupRoleScopeTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不改动本地开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"biz-{uuid4().hex[:10]}")
        # L3 操作者：仅绑租户管理员，未绑任何 platform 层级角色。
        self.actor = User(email=f"l3-{uuid4().hex}@example.test", password_hash="test-only",
                          display_name="租户管理员")
        self.db.add_all([self.tenant, self.actor])
        self.db.flush()
        # 管理面节点目录：L3 角色需挂 menu.groups / button.groups.manage 才能通过按码判权。
        self.catalog: dict[str, Permission] = {}
        for code in ("menu.groups", "button.groups.manage"):
            row = Permission(
                code=code, catalog_namespace="platform",
                resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
                surface="management", requires_data_scope=False,
                kind="menu" if code.startswith("menu.") else "button",
            )
            self.db.add(row)
            self.catalog[code] = row
        self.db.flush()
        # 三个同租户平台类角色：L3 自身角色（tenant 秩）、越秩 super 角色、秩内普通角色。
        self.l3_role = Role(tenant_id=self.tenant.id, application_id=None, kind="tenant",
                            key="tenant.admin", name="租户管理员", status="active",
                            scope=ROLE_SCOPE_TENANT)
        self.super_role = Role(tenant_id=self.tenant.id, application_id=None, kind="tenant",
                               key=f"super-{uuid4().hex[:8]}", name="越权超管角色", status="active",
                               scope=ROLE_SCOPE_SUPER)
        self.tenant_role = Role(tenant_id=self.tenant.id, application_id=None, kind="tenant",
                                key=f"ops-{uuid4().hex[:8]}", name="普通租户角色", status="active",
                                scope=ROLE_SCOPE_TENANT)
        self.db.add_all([self.l3_role, self.super_role, self.tenant_role])
        self.db.flush()
        # L3 角色挂上组管理节点，保证 ensure_codes 门禁通过、聚焦范围秩校验本身。
        for code in ("menu.groups", "button.groups.manage"):
            self.db.add(RolePermission(role_id=self.l3_role.id, permission_id=self.catalog[code].id))
        membership = TenantMembership(tenant_id=self.tenant.id, user_id=self.actor.id)
        self.db.add(membership)
        self.db.flush()
        # 夹具直写绑定：operator_scope 经 authorized_role_ids_statement 识别直连 RoleBinding。
        self.db.add(RoleBinding(membership_id=membership.id, role_id=self.l3_role.id))
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "PUT", "path": "/api/v1/admin/groups",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })
        self.group = create_user_group(
            UserGroupCreate(tenant_id=self.tenant.id, key=f"team-{uuid4().hex[:8]}", name="产品组"),
            self.request, actor=self.actor, db=self.db,
        )
        self.group_id = UUID(self.group["id"])

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_l3_cannot_bind_super_role_via_group(self) -> None:
        """L3 经 PUT 组角色提交 scope=super 角色 → 403，且组角色未被修改。"""
        with self.assertRaises(HTTPException) as ctx:
            replace_user_group_roles(
                self.group_id,
                UserGroupRolesUpdate(role_ids=[self.super_role.id]),
                self.request, actor=self.actor, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        # 越秩请求在写入前被拦截：回滚后确认组角色关联仍为空（UserGroupRole 复合主键，用计数断言）。
        self.db.rollback()
        self.assertEqual(self.db.scalar(
            select(func.count()).select_from(UserGroupRole).where(
                UserGroupRole.group_id == self.group_id,
            ),
        ), 0)

    def test_l3_group_role_listing_hides_super_role(self) -> None:
        """L3 请求组角色目录 → 不含 scope=super 角色，同秩角色可见且标记正确。"""
        result = replace_user_group_roles(
            self.group_id,
            UserGroupRolesUpdate(role_ids=[self.tenant_role.id]),
            self.request, actor=self.actor, db=self.db,
        )
        # 前置：L3 绑定同秩（tenant）角色不受影响。
        self.assertTrue(result["changed"])
        rows = list_user_group_roles(self.group_id, actor=self.actor, db=self.db)
        ids = {row["id"] for row in rows}
        self.assertNotIn(str(self.super_role.id), ids)
        self.assertIn(str(self.tenant_role.id), ids)
        self.assertTrue(next(row for row in rows if row["id"] == str(self.tenant_role.id))["assigned"])


if __name__ == "__main__":
    unittest.main()
