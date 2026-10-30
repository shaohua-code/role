"""Keep unresolved provider-call reservations for audited administrator review.

Revision ID: 0031_model_usage_reconciliation
Revises: 0030_deerflow_preference_permissions
"""

from alembic import op
import sqlalchemy as sa

revision = "0031_model_usage_reconciliation"
down_revision = "0030_deerflow_preference_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow explicit release and distinguish gateway from manual usage entries."""
    op.drop_constraint("ck_model_usage_reservation_status", "model_usage_reservations", type_="check")
    op.create_check_constraint(
        "ck_model_usage_reservation_status", "model_usage_reservations",
        "status IN ('reserved', 'settled', 'released')",
    )
    op.add_column(
        "model_usage_events",
        sa.Column("source", sa.String(length=32), server_default="gateway", nullable=False),
    )
    op.create_check_constraint(
        "ck_model_usage_source", "model_usage_events",
        "source IN ('gateway', 'admin_reconciliation')",
    )
    op.alter_column("model_usage_events", "latency_ms", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint("ck_model_usage_nonnegative", "model_usage_events", type_="check")
    op.create_check_constraint(
        "ck_model_usage_nonnegative", "model_usage_events",
        "input_tokens >= 0 AND output_tokens >= 0 AND (latency_ms IS NULL OR latency_ms >= 0)",
    )


def downgrade() -> None:
    """Refuse a lossy downgrade after manual review decisions have been recorded."""
    connection = op.get_bind()
    released = connection.execute(sa.text(
        "SELECT count(*) FROM model_usage_reservations WHERE status = 'released'"
    )).scalar_one()
    reconciled = connection.execute(sa.text(
        "SELECT count(*) FROM model_usage_events WHERE source = 'admin_reconciliation' OR latency_ms IS NULL"
    )).scalar_one()
    if released or reconciled:
        raise RuntimeError(
            "Cannot downgrade model usage reconciliation after released reservations or manual events exist"
        )

    op.drop_constraint("ck_model_usage_nonnegative", "model_usage_events", type_="check")
    op.create_check_constraint(
        "ck_model_usage_nonnegative", "model_usage_events",
        "input_tokens >= 0 AND output_tokens >= 0 AND latency_ms >= 0",
    )
    op.alter_column("model_usage_events", "latency_ms", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("ck_model_usage_source", "model_usage_events", type_="check")
    op.drop_column("model_usage_events", "source")
    op.drop_constraint("ck_model_usage_reservation_status", "model_usage_reservations", type_="check")
    op.create_check_constraint(
        "ck_model_usage_reservation_status", "model_usage_reservations",
        "status IN ('reserved', 'settled')",
    )
