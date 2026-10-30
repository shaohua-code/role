"""Add immediate revocation records for signed access tokens."""

from alembic import op
import sqlalchemy as sa

revision = "0009_access_token_revocations"
down_revision = "0008_model_usage_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """索引化短 JWT 的随机 ID 摘要；过期时间支持按需回收旧撤销记录。"""
    op.create_table(
        "revoked_access_tokens",
        sa.Column("jti_hash", sa.String(64), primary_key=True),
        sa.Column("token_use", sa.String(24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_revoked_access_tokens_expires_at", "revoked_access_tokens", ["expires_at"])


def downgrade() -> None:
    """仅删除撤销索引与短期凭据黑名单，不修改用户或刷新会话数据。"""
    op.drop_index("ix_revoked_access_tokens_expires_at", table_name="revoked_access_tokens")
    op.drop_table("revoked_access_tokens")
