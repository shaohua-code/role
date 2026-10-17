"""Add atomic pre-call reservations for model RPM/TPM limits."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_model_usage_reservations"
down_revision = "0007_oidc_user_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """保留每次模型请求在 provider 调用前分配的并发额度。"""
    op.create_table(
        "model_usage_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", sa.String(180), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_catalog.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reserved_input_tokens", sa.Integer(), nullable=False),
        sa.Column("reserved_output_tokens", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="reserved"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("request_id", name="uq_model_usage_reservation_request_id"),
        sa.CheckConstraint("reserved_input_tokens >= 0 AND reserved_output_tokens >= 0",
                           name="ck_model_usage_reservation_tokens_nonnegative"),
        sa.CheckConstraint("status IN ('reserved', 'settled')", name="ck_model_usage_reservation_status"),
    )
    for field in ("tenant_id", "model_id", "application_id", "user_id", "expires_at"):
        op.create_index(f"ix_model_usage_reservations_{field}", "model_usage_reservations", [field])
    op.create_index("ix_model_usage_reservations_model_expiry", "model_usage_reservations", ["model_id", "expires_at"])


def downgrade() -> None:
    """此迁移只删除配额预留数据表，不会改写既有用量账目。"""
    op.drop_index("ix_model_usage_reservations_model_expiry", table_name="model_usage_reservations")
    for field in ("expires_at", "user_id", "application_id", "model_id", "tenant_id"):
        op.drop_index(f"ix_model_usage_reservations_{field}", table_name="model_usage_reservations")
    op.drop_table("model_usage_reservations")
