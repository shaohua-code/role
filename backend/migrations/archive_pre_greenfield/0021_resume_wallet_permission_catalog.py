"""登记 AI 简历用户钱包 API 使用的中央权限编码。"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0021_resume_wallet_perms"
down_revision = "0020_login_attempt_throttles"
branch_labels = None
depends_on = None


# 仅注册用户钱包读取和充值申请权限；业务租户管理员仍需显式分配，迁移不自动授予角色。
WALLET_PERMISSIONS = (
    ("resume.wallet.read", "read", "读取本人 AI 简历钱包余额、流水和充值信息"),
    ("resume.wallet.recharge", "recharge", "为本人 AI 简历钱包提交充值申请"),
)


def upgrade() -> None:
    """登记 AI Resume 用户钱包 API 依赖的稳定权限码。"""
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO permissions (id, code, resource_type, scope, description)
        VALUES (CAST(:id AS uuid), :code, :resource_type, :scope, :description)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, scope, description in WALLET_PERMISSIONS:
        connection.execute(statement, {
            "id": str(uuid4()),
            "code": code,
            "resource_type": "wallet",
            "scope": scope,
            "description": description,
        })


def downgrade() -> None:
    """保留可能已被角色引用的权限目录项，回滚时不删除授权数据。"""
    # 权限目录是可被管理员复用的稳定编码注册表，因此 seed migration 不反向删除目录行。
    return None
