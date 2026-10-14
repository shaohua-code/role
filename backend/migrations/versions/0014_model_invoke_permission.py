"""Seed the stable permission code for model invocation checks."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0014_model_invoke_permission"
down_revision = "0013_ai_permission_catalog"
branch_labels = None
depends_on = None


# 模型调用权限按 IAM 模型目录实例授权；迁移只登记编码，不授予任何租户角色。
MODEL_PERMISSIONS = (
    ("model.invoke", "invoke", "调用当前租户中已启用且获授权的模型"),
)


def upgrade() -> None:
    """登记 IAM 授权判定器使用的 model.invoke 稳定编码。"""
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO permissions (id, code, resource_type, scope, description)
        VALUES (CAST(:id AS uuid), :code, :resource_type, :scope, :description)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, scope, description in MODEL_PERMISSIONS:
        connection.execute(statement, {
            "id": str(uuid4()),
            "code": code,
            "resource_type": "model",
            "scope": scope,
            "description": description,
        })


def downgrade() -> None:
    """保留可能已被角色引用的权限目录项。"""
    # 管理员可能已基于此编码创建授权；回滚 revision 不删除权限目录数据。
    return None
