"""Bind pending public registration challenges to their configured role policy."""

from alembic import op
import sqlalchemy as sa

revision = "0025_registration_role_snapshot"
down_revision = "0024_tenant_registration_audience"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Invalidate old pending OTPs because they lack a safe authorization snapshot."""
    op.execute(sa.text(
        "UPDATE public_registration_challenges "
        "SET consumed_at = now() WHERE consumed_at IS NULL"
    ))
    op.add_column(
        "public_registration_challenges",
        sa.Column("registration_role_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "public_registration_challenges",
        sa.Column("registration_role_fingerprint", sa.String(64), nullable=True),
    )
    op.create_foreign_key(
        "fk_public_registration_challenges_registration_role",
        "public_registration_challenges", "roles", ["registration_role_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_public_registration_challenges_registration_role_id",
        "public_registration_challenges", ["registration_role_id"],
    )
    op.create_check_constraint(
        "ck_registration_challenge_role_snapshot_required", "public_registration_challenges",
        "consumed_at IS NOT NULL OR "
        "(registration_role_id IS NOT NULL AND registration_role_fingerprint IS NOT NULL)",
    )


def downgrade() -> None:
    """Remove only the role snapshot; consumed challenges stay consumed."""
    op.drop_constraint(
        "ck_registration_challenge_role_snapshot_required",
        "public_registration_challenges", type_="check",
    )
    op.drop_index(
        "ix_public_registration_challenges_registration_role_id",
        table_name="public_registration_challenges",
    )
    op.drop_constraint(
        "fk_public_registration_challenges_registration_role",
        "public_registration_challenges", type_="foreignkey",
    )
    op.drop_column("public_registration_challenges", "registration_role_fingerprint")
    op.drop_column("public_registration_challenges", "registration_role_id")