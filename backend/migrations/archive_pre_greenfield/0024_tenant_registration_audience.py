"""区分消费租户与组织租户，确保公开注册只能在 ToC 登录域启用。"""

from alembic import op
import sqlalchemy as sa

revision = "0024_tenant_registration_audience"
down_revision = "0023_user_membership_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """租户默认保持组织边界，并清除旧注册挑战中暂存的密码摘要。"""
    op.add_column("tenants", sa.Column(
        "kind", sa.String(length=20), server_default="organization", nullable=False,
    ))
    op.create_check_constraint(
        "ck_tenant_kind", "tenants", "kind IN ('organization', 'consumer')",
    )
    # 邮箱验证前不再接受/保存密码；部署升级时一并清理旧 challenge 摘要。
    op.execute(sa.text("UPDATE public_registration_challenges SET password_hash = NULL"))
    op.drop_column("public_registration_challenges", "password_hash")


def downgrade() -> None:
    """恢复旧 challenge 的空摘要列；此前清理的密码摘要不可恢复。"""
    op.add_column("public_registration_challenges", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.drop_constraint("ck_tenant_kind", "tenants", type_="check")
    op.drop_column("tenants", "kind")
