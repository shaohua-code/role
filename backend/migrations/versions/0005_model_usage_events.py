"""Add append-only model gateway usage accounting."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_model_usage_events"
down_revision = "0004_organizations_data_scopes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", sa.String(180), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("model_catalog.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("request_id", name="uq_model_usage_request_id"),
        sa.CheckConstraint("input_tokens >= 0 AND output_tokens >= 0 AND latency_ms >= 0", name="ck_model_usage_nonnegative"),
        sa.CheckConstraint("outcome IN ('succeeded', 'failed')", name="ck_model_usage_outcome"),
    )
    for field in ("tenant_id", "model_id", "application_id", "user_id", "created_at"):
        op.create_index(f"ix_model_usage_events_{field}", "model_usage_events", [field])


def downgrade() -> None:
    for field in ("created_at", "user_id", "application_id", "model_id", "tenant_id"):
        op.drop_index(f"ix_model_usage_events_{field}", table_name="model_usage_events")
    op.drop_table("model_usage_events")
