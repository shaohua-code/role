"""新增短期登录失败桶，不在数据库保留登录标识明文。"""

from alembic import op
import sqlalchemy as sa

revision = "0020_login_attempt_throttles"
down_revision = "0019_knowledge_core_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建仅含 HMAC 摘要和短期计数的表，用于限制口令猜测。"""
    op.create_table(
        "login_attempt_buckets",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key_hash"),
        sa.CheckConstraint("failed_attempts >= 0", name="ck_login_attempt_buckets_nonnegative"),
    )
    op.create_index("ix_login_attempt_buckets_expires_at", "login_attempt_buckets", ["expires_at"])


def downgrade() -> None:
    """仅移除临时限流表，不修改用户凭证或会话。"""
    op.drop_index("ix_login_attempt_buckets_expires_at", table_name="login_attempt_buckets")
    op.drop_table("login_attempt_buckets")
