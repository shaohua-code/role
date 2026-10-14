"""Add reversible activation state to the stable permission registry."""

from alembic import op
import sqlalchemy as sa

revision = "0016_permission_status"
down_revision = "0015_model_usage_estimation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """将现有权限编码视为启用，后续由平台管理员显式停用。"""
    op.add_column(
        "permissions",
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.create_check_constraint(
        "ck_permission_status",
        "permissions",
        "status IN ('active', 'disabled')",
    )


def downgrade() -> None:
    """删除状态列；注意回退会丢失停用状态，不能作为产品级权限恢复操作。"""
    op.drop_constraint("ck_permission_status", "permissions", type_="check")
    op.drop_column("permissions", "status")
