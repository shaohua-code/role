"""Distinguish measured model usage from provider-failure estimates."""

from alembic import op
import sqlalchemy as sa

revision = "0015_model_usage_estimation"
down_revision = "0014_model_invoke_permission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为历史账目保守标记实测数据，新失败估算由网关显式设置标志。"""
    op.add_column(
        "model_usage_events",
        sa.Column("usage_is_estimated", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """移除估算标记列；此迁移不删除账目数据。"""
    op.drop_column("model_usage_events", "usage_is_estimated")
