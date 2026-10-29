"""明确区分全局账号状态与租户成员生命周期状态。"""

from alembic import op
import sqlalchemy as sa

revision = "0023_user_membership_lifecycle"
down_revision = "0022_toc_public_registration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """补充状态枚举约束和租户成员授权版本；既有成员从版本 1 开始。"""
    op.add_column("tenant_memberships", sa.Column(
        "auth_version", sa.Integer(), server_default="1", nullable=False,
    ))
    op.add_column("oauth_authorization_codes", sa.Column(
        "membership_version", sa.Integer(), server_default="1", nullable=False,
    ))
    op.add_column("oauth_consent_requests", sa.Column(
        "membership_version", sa.Integer(), server_default="1", nullable=False,
    ))
    op.add_column("oauth_refresh_tokens", sa.Column(
        "membership_version", sa.Integer(), server_default="1", nullable=False,
    ))
    op.create_check_constraint(
        "ck_user_status", "users", "status IN ('active', 'disabled', 'locked')",
    )
    op.create_check_constraint(
        "ck_tenant_membership_status", "tenant_memberships",
        "status IN ('active', 'disabled', 'departed')",
    )


def downgrade() -> None:
    """回滚约束前恢复旧状态值，避免约束删除失败后丢失升级状态语义。"""
    op.execute(sa.text("UPDATE users SET status = 'disabled' WHERE status = 'locked'"))
    op.execute(sa.text("UPDATE tenant_memberships SET status = 'disabled' WHERE status = 'departed'"))
    op.drop_constraint("ck_tenant_membership_status", "tenant_memberships", type_="check")
    op.drop_constraint("ck_user_status", "users", type_="check")
    op.drop_column("oauth_refresh_tokens", "membership_version")
    op.drop_column("oauth_consent_requests", "membership_version")
    op.drop_column("oauth_authorization_codes", "membership_version")
    op.drop_column("tenant_memberships", "auth_version")
