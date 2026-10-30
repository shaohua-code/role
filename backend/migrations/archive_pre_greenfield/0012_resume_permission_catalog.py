"""Seed stable IAM permission codes used by the first AI Resume integration."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0012_resume_permission_catalog"
down_revision = "0011_password_reset_sessions"
branch_labels = None
depends_on = None


# 权限目录是全局编码注册表；该迁移只登记可复用的操作，不绑定租户或自动授予角色。
RESUME_PERMISSIONS = (
    ("resume.read", "read", "读取本人简历、列表、历史和数量"),
    ("resume.write", "write", "创建、更新、应用历史或删除本人简历"),
    ("resume.export", "export", "导出本人简历"),
)


def upgrade() -> None:
    """登记 AI 简历中央授权所需的稳定权限编码，保留已存在的管理员目录项。"""
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO permissions (id, code, resource_type, scope, description)
        VALUES (CAST(:id AS uuid), :code, :resource_type, :scope, :description)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, scope, description in RESUME_PERMISSIONS:
        connection.execute(statement, {
            "id": str(uuid4()),
            "code": code,
            "resource_type": "resume",
            "scope": scope,
            "description": description,
        })


def downgrade() -> None:
    """保留全局权限目录项，避免回滚版本时误删已授予角色的权限或管理员既有定义。"""
    # 该迁移只写入目录数据；RolePermission 可能已引用这些 ID，因此回退 revision 不删除权限行。
    return None
