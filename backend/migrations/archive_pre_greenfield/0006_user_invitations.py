"""Add one-time tenant user invitations with hash-only bearer tokens."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_user_invitations"
down_revision = "0005_model_usage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["role_id", "tenant_id"], ["roles.id", "roles.tenant_id"],
                                ondelete="RESTRICT", name="fk_user_invitation_role_tenant"),
    )
    for field in ("tenant_id", "role_id", "email", "expires_at", "created_by"):
        op.create_index(f"ix_user_invitations_{field}", "user_invitations", [field])
    op.create_index("uq_user_invitation_pending_email", "user_invitations", ["tenant_id", "email"],
                    unique=True, postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_user_invitation_pending_email", table_name="user_invitations")
    for field in ("created_by", "expires_at", "email", "role_id", "tenant_id"):
        op.drop_index(f"ix_user_invitations_{field}", table_name="user_invitations")
    op.drop_table("user_invitations")
