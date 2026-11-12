"""role_scope_converge_three_admins

授权范围收敛：三管理员 + 应用成员。
1. roles 增加 scope 列（super/tenant/app/member，只能向下）并按模板 key 回填；
2. apps.admin（多应用管理员）并入 app.admin：绑定迁移后删除模板行；
3. 管理面删除 27 接口码与「权限编码」目录节点（菜单/按钮树成为唯一权限目录）。
本文件只入库，不在未授权前对开发库执行。

Revision ID: 0006_role_scope_nodes
Revises: 0005_permission_kind
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_role_scope_nodes"
down_revision: Union[str, Sequence[str], None] = "0005_permission_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 角色授权范围列（空值由判权层按模板 key / 钉应用推导，历史库一律回填）。
    op.add_column("roles", sa.Column("scope", sa.String(length=20), nullable=True))
    op.create_index("ix_roles_scope", "roles", ["scope"])
    op.create_check_constraint(
        "ck_role_scope",
        "roles",
        "scope IS NULL OR scope IN ('super', 'tenant', 'app', 'member')",
    )
    op.execute("UPDATE roles SET scope = 'super' WHERE key = 'platform.admin' AND scope IS NULL")
    op.execute("UPDATE roles SET scope = 'tenant' WHERE key = 'tenant.admin' AND scope IS NULL")
    op.execute("UPDATE roles SET scope = 'app' WHERE key IN ('apps.admin', 'app.admin') AND scope IS NULL")
    op.execute("UPDATE roles SET scope = 'member' WHERE key = 'app.member' AND scope IS NULL")
    op.execute("UPDATE roles SET scope = 'app' WHERE scope IS NULL AND application_id IS NOT NULL")
    op.execute("UPDATE roles SET scope = 'tenant' WHERE scope IS NULL")

    # 2. apps.admin 并入 app.admin：同租户同应用的冲突绑定先删，其余迁移后删模板行。
    op.execute(
        "DELETE FROM role_bindings WHERE id IN ("
        " SELECT rb.id FROM role_bindings rb"
        " JOIN roles s ON s.id = rb.role_id AND s.key = 'apps.admin'"
        " JOIN roles t ON t.key = 'app.admin' AND t.tenant_id = s.tenant_id"
        "  AND t.application_id = s.application_id)"
    )
    op.execute(
        "UPDATE role_bindings SET role_id = ("
        " SELECT t.id FROM roles s, roles t"
        " WHERE s.id = role_bindings.role_id AND s.key = 'apps.admin'"
        "  AND t.key = 'app.admin' AND t.tenant_id = s.tenant_id"
        "  AND t.application_id = s.application_id LIMIT 1)"
        " WHERE role_id IN (SELECT id FROM roles WHERE key = 'apps.admin')"
    )
    op.execute("DELETE FROM role_bindings WHERE role_id IN (SELECT id FROM roles WHERE key = 'apps.admin')")
    op.execute("DELETE FROM user_group_roles WHERE role_id IN (SELECT id FROM roles WHERE key = 'apps.admin')")
    op.execute("DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE key = 'apps.admin')")
    op.execute("DELETE FROM role_data_scopes WHERE role_id IN (SELECT id FROM roles WHERE key = 'apps.admin')")
    op.execute("DELETE FROM roles WHERE key = 'apps.admin'")

    # 3. 管理面权限收敛：接口码目录整体下线；「权限编码」菜单与目录写按钮一并删除。
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ("
        " SELECT id FROM permissions WHERE surface = 'management' AND kind = 'api')"
    )
    op.execute("DELETE FROM permissions WHERE surface = 'management' AND kind = 'api'")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ("
        " SELECT id FROM permissions WHERE code IN ('menu.permissions', 'button.permissions.manage'))"
    )
    op.execute("DELETE FROM permissions WHERE code IN ('menu.permissions', 'button.permissions.manage')")


def downgrade() -> None:
    # 授权范围与目录删除不可逆（接口码清单已废）；仅回滚列结构供架构回退。
    op.drop_constraint("ck_role_scope", "roles", type_="check")
    op.drop_index("ix_roles_scope", table_name="roles")
    op.drop_column("roles", "scope")
