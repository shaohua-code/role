"""用隔离 SQLite 验证应用资源树（P357：菜单/按钮/数据规则 + 角色授权 + 下发树）。

覆盖：层级校验（按钮必须挂菜单）、应用内编码唯一、环形层级拒绝、
删除级联清理角色授权、分配自动补祖先、跨应用资源忽略、
my-resources 直连绑定与组继承下发、停用节点隐藏与子树上提。
"""

import unittest
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.admin.application_resources import (
    assign_role_application_resources,
    create_application_resource,
    delete_application_resource,
    list_role_application_resources,
    update_application_resource,
)
from app.api.v1.authorization import list_my_resources
from app.db.base import Base
from app.models.application import Application
from app.models.application_resource import ApplicationResource, RoleApplicationResource
from app.models.identity import Tenant, TenantMembership, User
from app.schemas.application_resources import (
    ApplicationResourceCreate,
    ApplicationResourceUpdate,
    RoleResourcesAssign,
)
from tests.greenfield_fixture import make_platform_admin_binding, make_tenant_role_binding


class ApplicationResourceApiTests(unittest.TestCase):
    """每个用例在内存数据库中运行，不改动本地开发 PostgreSQL。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.tenant = Tenant(name="业务租户", slug=f"res-{uuid4().hex[:10]}")
        self.actor = User(email=f"admin-{uuid4().hex}@example.test", password_hash="test-only", display_name="管理员")
        self.db.add_all([self.tenant, self.actor])
        self.db.flush()
        make_platform_admin_binding(self.db, self.actor)
        self.application = Application(tenant_id=self.tenant.id, client_id=f"app-{uuid4().hex[:8]}",
                                       name="资源应用", permission_namespace="resapp", redirect_uris=[])
        self.db.add(self.application)
        self.db.commit()
        self.request = Request({
            "type": "http", "method": "POST", "path": "/api/v1/admin/applications",
            "headers": [], "query_string": b"", "scheme": "http",
            "server": ("testserver", 80), "client": ("127.0.0.1", 43100),
        })

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _create(self, resource_type: str, code: str, parent_id=None, **kwargs) -> dict:
        return create_application_resource(
            self.application.id,
            ApplicationResourceCreate(resource_type=resource_type, code=code, name=code, parent_id=parent_id, **kwargs),
            request=self.request, actor=self.actor, db=self.db,
        )

    def _make_app_role(self, user: User):
        # 直调 handler 没有 FastAPI 依赖注入，用户必须先落库拿到 UUID。
        self.db.add(user)
        self.db.flush()
        return make_tenant_role_binding(
            self.db, tenant_id=self.tenant.id, actor=user,
            role_key=f"app.viewer-{uuid4().hex[:6]}", role_name="应用查看",
            application_id=self.application.id,
        )

    def test_button_requires_menu_parent(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self._create("button", "resapp.button.export")
        self.assertEqual(ctx.exception.status_code, 422)
        # 按钮挂在按钮下同样拒绝；挂在菜单下放行。
        parent_menu = self._create("menu", "resapp.menu.project")
        sibling_button = self._create("button", "resapp.button.import", parent_id=parent_menu["id"])
        with self.assertRaises(HTTPException) as ctx2:
            self._create("button", "resapp.button.deep", parent_id=sibling_button["id"])
        self.assertEqual(ctx2.exception.status_code, 422)

    def test_duplicate_code_rejected_in_same_application(self) -> None:
        self._create("menu", "resapp.menu.home")
        with self.assertRaises(HTTPException) as ctx:
            self._create("menu", "resapp.menu.home")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_update_parent_cycle_rejected(self) -> None:
        parent = self._create("menu", "resapp.menu.a")
        child = self._create("menu", "resapp.menu.b", parent_id=parent["id"])
        # 把父节点挂到自己子节点下形成 A→B→A 环形，必须拒绝。
        with self.assertRaises(HTTPException) as ctx:
            update_application_resource(
                self.application.id, UUID(parent["id"]),
                ApplicationResourceUpdate(parent_id=child["id"]),
                request=self.request, actor=self.actor, db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_delete_with_children_rejected_then_leaf_cascade_clears_assignments(self) -> None:
        menu = self._create("menu", "resapp.menu.list")
        button = self._create("button", "resapp.button.delete", parent_id=menu["id"])
        role_user = User(email=f"u-{uuid4().hex}@example.test", password_hash="x", display_name="成员")
        role = self._make_app_role(role_user)
        assign_role_application_resources(
            self.application.id, role.id, RoleResourcesAssign(resource_ids=[button["id"]]),
            request=self.request, actor=self.actor, db=self.db,
        )
        with self.assertRaises(HTTPException) as ctx:
            delete_application_resource(self.application.id, UUID(menu["id"]),
                                        request=self.request, actor=self.actor, db=self.db)
        self.assertEqual(ctx.exception.status_code, 409)
        delete_application_resource(self.application.id, UUID(button["id"]),
                                    request=self.request, actor=self.actor, db=self.db)
        remaining = self.db.query(RoleApplicationResource).filter(
            RoleApplicationResource.resource_id == UUID(button["id"])).count()
        self.assertEqual(remaining, 0)

    def test_assign_auto_includes_ancestors_and_replaces_selection(self) -> None:
        root = self._create("menu", "resapp.menu.root", sort=1)
        mid = self._create("menu", "resapp.menu.mid", parent_id=root["id"], sort=1)
        leaf = self._create("button", "resapp.button.run", parent_id=mid["id"])
        role_user = User(email=f"u-{uuid4().hex}@example.test", password_hash="x", display_name="成员")
        role = self._make_app_role(role_user)
        result = assign_role_application_resources(
            self.application.id, role.id, RoleResourcesAssign(resource_ids=[leaf["id"]]),
            request=self.request, actor=self.actor, db=self.db,
        )
        # 只勾选叶子节点，服务端自动补齐两层祖先。
        self.assertEqual(set(result["resource_ids"]), {root["id"], mid["id"], leaf["id"]})
        stored = list_role_application_resources(
            self.application.id, role.id, actor=self.actor, db=self.db)
        self.assertEqual(set(stored["resource_ids"]), {root["id"], mid["id"], leaf["id"]})
        # 全量替换语义：再次只分配 mid 时 leaf 被移除，祖先 root 保留。
        assign_role_application_resources(
            self.application.id, role.id, RoleResourcesAssign(resource_ids=[mid["id"]]),
            request=self.request, actor=self.actor, db=self.db,
        )
        stored = list_role_application_resources(
            self.application.id, role.id, actor=self.actor, db=self.db)
        self.assertEqual(set(stored["resource_ids"]), {root["id"], mid["id"]})

    def test_assign_ignores_cross_application_resources(self) -> None:
        other_app = Application(tenant_id=self.tenant.id, client_id=f"other-{uuid4().hex[:8]}",
                                name="其他应用", permission_namespace="otherapp", redirect_uris=[])
        self.db.add(other_app)
        self.db.flush()
        foreign = ApplicationResource(application_id=other_app.id, resource_type="menu",
                                      code="otherapp.menu.x", name="外部菜单")
        self.db.add(foreign)
        self.db.commit()
        role_user = User(email=f"u-{uuid4().hex}@example.test", password_hash="x", display_name="成员")
        role = self._make_app_role(role_user)
        result = assign_role_application_resources(
            self.application.id, role.id, RoleResourcesAssign(resource_ids=[foreign.id]),
            request=self.request, actor=self.actor, db=self.db,
        )
        # 跨应用资源 ID 静默过滤，不产生任何授权行。
        self.assertEqual(result["resource_ids"], [])

    def test_my_resources_direct_binding_tree(self) -> None:
        root = self._create("menu", "resapp.menu.root", sort=1)
        mid = self._create("menu", "resapp.menu.mid", parent_id=root["id"], sort=1,
                           path="/project", icon="folder", extra={"badge": 3},
                           description="项目管理菜单")
        leaf = self._create("button", "resapp.button.run", parent_id=mid["id"])
        rule = self._create("data_rule", "resapp.data.own-only", parent_id=mid["id"])
        role_user = User(email=f"u-{uuid4().hex}@example.test", password_hash="x", display_name="成员")
        role = self._make_app_role(role_user)
        assign_role_application_resources(
            self.application.id, role.id,
            RoleResourcesAssign(resource_ids=[leaf["id"], rule["id"]]),
            request=self.request, actor=self.actor, db=self.db,
        )
        tree = list_my_resources(client_id=self.application.client_id, user=role_user, db=self.db)
        self.assertEqual(len(tree), 1)
        root_node = tree[0]
        self.assertEqual(root_node["id"], root["id"])
        self.assertEqual(len(root_node["children"]), 1)
        mid_node = root_node["children"][0]
        self.assertEqual(mid_node["path"], "/project")
        self.assertEqual(mid_node["description"], "项目管理菜单")
        self.assertEqual(mid_node["extra"], {"badge": 3})
        # 按钮与数据规则并列挂在菜单下。
        self.assertEqual({child["resource_type"] for child in mid_node["children"]},
                         {"button", "data_rule"})

    def test_my_resources_group_inherited_role(self) -> None:
        from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole

        menu = self._create("menu", "resapp.menu.only")
        member_user = User(email=f"u-{uuid4().hex}@example.test", password_hash="x", display_name="组成员")
        self.db.add(member_user)
        self.db.flush()
        role = self._make_app_role(member_user)
        membership = self.db.query(TenantMembership).filter(
            TenantMembership.user_id == member_user.id).one()
        group = UserGroup(tenant_id=self.tenant.id, key=f"grp-{uuid4().hex[:8]}", name="项目组")
        self.db.add(group)
        self.db.flush()
        self.db.add_all([
            UserGroupMembership(group_id=group.id, membership_id=membership.id, tenant_id=self.tenant.id),
            UserGroupRole(group_id=group.id, role_id=role.id, tenant_id=self.tenant.id),
        ])
        self.db.commit()
        # 直连 RoleBinding 已经存在（fixture 建立），这里验证组继承同样生效：
        # 解绑直连后仅靠组继承也应拿到资源。
        from app.models.authorization import RoleBinding

        binding = self.db.query(RoleBinding).filter(
            RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id).one()
        self.db.delete(binding)
        self.db.commit()
        assign_role_application_resources(
            self.application.id, role.id, RoleResourcesAssign(resource_ids=[menu["id"]]),
            request=self.request, actor=self.actor, db=self.db,
        )
        tree = list_my_resources(client_id=self.application.client_id, user=member_user, db=self.db)
        self.assertEqual([node["id"] for node in tree], [menu["id"]])

    def test_my_resources_hides_disabled_and_promotes_orphans(self) -> None:
        root = self._create("menu", "resapp.menu.root")
        mid = self._create("menu", "resapp.menu.mid", parent_id=root["id"])
        leaf = self._create("button", "resapp.button.run", parent_id=mid["id"])
        role_user = User(email=f"u-{uuid4().hex}@example.test", password_hash="x", display_name="成员")
        role = self._make_app_role(role_user)
        assign_role_application_resources(
            self.application.id, role.id,
            RoleResourcesAssign(resource_ids=[root["id"], mid["id"], leaf["id"]]),
            request=self.request, actor=self.actor, db=self.db,
        )
        # 停用中间节点：该节点从下发树消失，其子按钮上提为顶层。
        update_application_resource(
            self.application.id, UUID(mid["id"]), ApplicationResourceUpdate(status="disabled"),
            request=self.request, actor=self.actor, db=self.db,
        )
        tree = list_my_resources(client_id=self.application.client_id, user=role_user, db=self.db)
        top_ids = {node["id"] for node in tree}
        self.assertIn(root["id"], top_ids)
        self.assertIn(leaf["id"], top_ids)
        self.assertNotIn(mid["id"], top_ids)

    def test_my_resources_unknown_client_404(self) -> None:
        role_user = User(email=f"u-{uuid4().hex}@example.test", password_hash="x", display_name="成员")
        self.db.add(role_user)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            list_my_resources(client_id=f"missing-{uuid4().hex[:6]}", user=role_user, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
