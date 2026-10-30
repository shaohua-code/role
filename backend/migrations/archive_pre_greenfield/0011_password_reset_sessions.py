"""Add one-time email password resets and credential-versioned sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0011_password_reset_sessions"
down_revision = "0010_tenant_user_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """只存重置令牌摘要；版本字段使已签发的各类令牌能在线失效。"""
    for table_name in (
        "users",
        "refresh_sessions",
        "oauth_authorization_codes",
        "oauth_consent_requests",
        "oauth_refresh_tokens",
    ):
        op.add_column(table_name, sa.Column("auth_version", sa.Integer(), server_default=sa.text("1"), nullable=False))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])

    op.create_table(
        "password_reset_throttles",
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("email_hash"),
    )
    op.create_index("ix_password_reset_throttles_expires_at", "password_reset_throttles", ["expires_at"])


def downgrade() -> None:
    """删除密码重置记录并移除版本字段；仅在回滚窗口内评估旧 token 风险后使用。"""
    op.drop_index("ix_password_reset_throttles_expires_at", table_name="password_reset_throttles")
    op.drop_table("password_reset_throttles")
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    for table_name in (
        "oauth_refresh_tokens",
        "oauth_consent_requests",
        "oauth_authorization_codes",
        "refresh_sessions",
        "users",
    ):
        op.drop_column(table_name, "auth_version")
