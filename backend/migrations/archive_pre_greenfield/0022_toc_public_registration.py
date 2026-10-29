"""为 ToC 应用自助注册增加逐应用策略、邮箱验证、限流、发件箱与同意留痕。"""

from alembic import op
import sqlalchemy as sa

revision = "0022_toc_public_registration"
down_revision = "0021_resume_wallet_perms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """默认所有现有应用关闭匿名注册；不会自动创建用户或授予任何角色。"""
    op.add_column("applications", sa.Column(
        "registration_policy", sa.String(length=20), server_default="disabled", nullable=False,
    ))
    op.add_column("applications", sa.Column("registration_role_id", sa.Uuid(), nullable=True))
    op.add_column("applications", sa.Column("registration_terms_version", sa.String(length=80), nullable=True))
    op.add_column("applications", sa.Column("registration_privacy_version", sa.String(length=80), nullable=True))
    op.create_check_constraint(
        "ck_application_registration_policy", "applications",
        "registration_policy IN ('disabled', 'open')",
    )
    op.create_index("ix_applications_registration_role_id", "applications", ["registration_role_id"])

    op.create_table(
        "public_registration_throttles",
        sa.Column("bucket_hash", sa.String(length=64), primary_key=True),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_public_registration_throttles_expires_at", "public_registration_throttles", ["expires_at"])

    op.create_table(
        "public_registration_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("existing_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verification_code_hash", sa.String(length=64), nullable=False),
        sa.Column("terms_version", sa.String(length=80), nullable=False),
        sa.Column("privacy_version", sa.String(length=80), nullable=False),
        sa.Column("terms_url", sa.String(length=2048), nullable=False),
        sa.Column("privacy_url", sa.String(length=2048), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("failed_attempts >= 0", name="ck_registration_failed_attempts_nonnegative"),
        sa.UniqueConstraint("application_id", "email_hash", name="uq_registration_app_email"),
    )
    op.create_index("ix_public_registration_challenges_application_id", "public_registration_challenges", ["application_id"])
    op.create_index("ix_public_registration_challenges_existing_user_id", "public_registration_challenges", ["existing_user_id"])
    op.create_index("ix_public_registration_challenges_expires_at", "public_registration_challenges", ["expires_at"])

    op.create_table(
        "public_registration_email_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("challenge_id", sa.Uuid(), sa.ForeignKey("public_registration_challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("retry_after", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'sending', 'sent', 'failed')", name="ck_registration_outbox_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_registration_outbox_attempts_nonnegative"),
        sa.UniqueConstraint("challenge_id", name="uq_registration_outbox_challenge"),
    )
    op.create_table(
        "public_registration_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("terms_version", sa.String(length=80), nullable=False),
        sa.Column("privacy_version", sa.String(length=80), nullable=False),
        sa.Column("terms_url", sa.String(length=2048), nullable=False),
        sa.Column("privacy_url", sa.String(length=2048), nullable=False),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "application_id", "terms_version", "privacy_version",
                            name="uq_registration_consent_policy_version"),
    )
    op.create_index("ix_public_registration_consents_user_id", "public_registration_consents", ["user_id"])
    op.create_index("ix_public_registration_consents_application_id", "public_registration_consents", ["application_id"])


def downgrade() -> None:
    """保留用户/授权数据不可逆向删除；回滚结构仅移除注册专属表与应用配置列。"""
    op.drop_index("ix_public_registration_consents_application_id", table_name="public_registration_consents")
    op.drop_index("ix_public_registration_consents_user_id", table_name="public_registration_consents")
    op.drop_table("public_registration_consents")
    op.drop_table("public_registration_email_outbox")
    op.drop_index("ix_public_registration_challenges_expires_at", table_name="public_registration_challenges")
    op.drop_index("ix_public_registration_challenges_existing_user_id", table_name="public_registration_challenges")
    op.drop_index("ix_public_registration_challenges_application_id", table_name="public_registration_challenges")
    op.drop_table("public_registration_challenges")
    op.drop_index("ix_public_registration_throttles_expires_at", table_name="public_registration_throttles")
    op.drop_table("public_registration_throttles")
    op.drop_index("ix_applications_registration_role_id", table_name="applications")
    op.drop_constraint("ck_application_registration_policy", "applications", type_="check")
    op.drop_column("applications", "registration_privacy_version")
    op.drop_column("applications", "registration_terms_version")
    op.drop_column("applications", "registration_role_id")
    op.drop_column("applications", "registration_policy")
