"""保存单次 OIDC 授权码和可轮换 OAuth 刷新令牌。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_oauth_code_storage"
down_revision = "0002_refresh_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(500), nullable=False),
        sa.Column("nonce", sa.String(255), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("code_challenge_method", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code_hash", name="uq_oauth_authorization_code_hash"),
    )
    op.create_index("ix_oauth_authorization_codes_application_id", "oauth_authorization_codes", ["application_id"])
    op.create_index("ix_oauth_authorization_codes_user_id", "oauth_authorization_codes", ["user_id"])
    op.create_index("ix_oauth_authorization_codes_expires_at", "oauth_authorization_codes", ["expires_at"])
    op.create_index("ix_oauth_authorization_codes_client_expiry", "oauth_authorization_codes", ["application_id", "expires_at"])

    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("oauth_refresh_tokens.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_oauth_refresh_token_hash"),
    )
    op.create_index("ix_oauth_refresh_tokens_family_id", "oauth_refresh_tokens", ["family_id"])
    op.create_index("ix_oauth_refresh_tokens_application_id", "oauth_refresh_tokens", ["application_id"])
    op.create_index("ix_oauth_refresh_tokens_user_id", "oauth_refresh_tokens", ["user_id"])
    op.create_index("ix_oauth_refresh_tokens_expires_at", "oauth_refresh_tokens", ["expires_at"])
    op.create_index("ix_oauth_refresh_tokens_family_revoked", "oauth_refresh_tokens", ["family_id", "revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_oauth_refresh_tokens_family_revoked", table_name="oauth_refresh_tokens")
    op.drop_index("ix_oauth_refresh_tokens_expires_at", table_name="oauth_refresh_tokens")
    op.drop_index("ix_oauth_refresh_tokens_user_id", table_name="oauth_refresh_tokens")
    op.drop_index("ix_oauth_refresh_tokens_application_id", table_name="oauth_refresh_tokens")
    op.drop_index("ix_oauth_refresh_tokens_family_id", table_name="oauth_refresh_tokens")
    op.drop_table("oauth_refresh_tokens")
    op.drop_index("ix_oauth_authorization_codes_client_expiry", table_name="oauth_authorization_codes")
    op.drop_index("ix_oauth_authorization_codes_expires_at", table_name="oauth_authorization_codes")
    op.drop_index("ix_oauth_authorization_codes_user_id", table_name="oauth_authorization_codes")
    op.drop_index("ix_oauth_authorization_codes_application_id", table_name="oauth_authorization_codes")
    op.drop_table("oauth_authorization_codes")
