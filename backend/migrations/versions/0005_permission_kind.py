"""permission_kind

为 permissions 增加 kind 列（menu / button / api / data），并从编码前缀回填。
本文件只入库，不在未授权前对开发库执行。

Revision ID: 0005_permission_kind
Revises: 0004_owner_backchannel
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_permission_kind"
down_revision: Union[str, Sequence[str], None] = "0004_owner_backchannel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """存量行默认 api，再按编码前缀回填菜单/按钮/数据。"""
    op.add_column(
        "permissions",
        sa.Column("kind", sa.String(length=20), server_default="api", nullable=False),
    )
    op.create_index("ix_permissions_kind", "permissions", ["kind"])
    op.create_check_constraint(
        "ck_permission_kind",
        "permissions",
        "kind IN ('menu', 'button', 'api', 'data')",
    )
    op.execute("UPDATE permissions SET kind = 'menu' WHERE code LIKE 'menu.%'")
    op.execute("UPDATE permissions SET kind = 'button' WHERE code LIKE 'button.%'")
    op.execute(
        "UPDATE permissions SET kind = 'data' WHERE code LIKE '%.scope.self' "
        "OR code LIKE '%.scope.organization' "
        "OR code LIKE '%.scope.organization_tree' "
        "OR code LIKE '%.scope.selected_organizations' "
        "OR code LIKE '%.scope.tenant'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_permission_kind", "permissions", type_="check")
    op.drop_index("ix_permissions_kind", table_name="permissions")
    op.drop_column("permissions", "kind")
