"""Add explicit end-user OIDC consent requests and admin trusted-client control."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_oidc_user_consent"
down_revision = "0006_user_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("trusted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "oauth_consent_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_hash", sa.String(64), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("client_state", sa.String(512), nullable=False),
        sa.Column("scope", sa.String(500), nullable=False),
        sa.Column("nonce", sa.String(255), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("code_challenge_method", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ticket_hash", name="uq_oauth_consent_request_ticket_hash"),
    )
    op.create_index("ix_oauth_consent_requests_application_id", "oauth_consent_requests", ["application_id"])
    op.create_index("ix_oauth_consent_requests_user_id", "oauth_consent_requests", ["user_id"])
    op.create_index("ix_oauth_consent_requests_expiry", "oauth_consent_requests", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_oauth_consent_requests_expiry", table_name="oauth_consent_requests")
    op.drop_index("ix_oauth_consent_requests_user_id", table_name="oauth_consent_requests")
    op.drop_index("ix_oauth_consent_requests_application_id", table_name="oauth_consent_requests")
    op.drop_table("oauth_consent_requests")
    op.drop_column("applications", "trusted")
