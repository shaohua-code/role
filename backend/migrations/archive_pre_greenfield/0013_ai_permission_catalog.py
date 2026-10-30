"""Seed the stable IAM permission code used by AI Resume generation routes."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0013_ai_permission_catalog"
down_revision = "0012_resume_permission_catalog"
branch_labels = None
depends_on = None


# 仅登记 AI 功能入口的全局权限编码；授权关系由租户管理员显式维护。
AI_PERMISSIONS = (
    ("ai.generate", "generate", "调用 AI 简历生成、优化、识别、匹配、评分和面试题能力"),
)


def upgrade() -> None:
    """登记 AI 业务路由使用的稳定权限编码，不默认授予任何角色。"""
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO permissions (id, code, resource_type, scope, description)
        VALUES (CAST(:id AS uuid), :code, :resource_type, :scope, :description)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, scope, description in AI_PERMISSIONS:
        connection.execute(statement, {
            "id": str(uuid4()),
            "code": code,
            "resource_type": "ai",
            "scope": scope,
            "description": description,
        })


def downgrade() -> None:
    """保留权限目录项，避免降级时误删已被角色引用的编码。"""
    # 权限目录可能已被管理员分配；回退版本不删除业务授权数据。
    return None
