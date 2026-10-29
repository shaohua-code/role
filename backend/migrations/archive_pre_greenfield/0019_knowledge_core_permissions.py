"""登记知识库应用域的中央读写与管理权限编码。"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0019_knowledge_core_permissions"
down_revision = "0018_tenant_application_admin_permissions"
branch_labels = None
depends_on = None


# 迁移只登记全局权限目录，不自动授予任何 IAM 租户角色。
KNOWLEDGE_PERMISSIONS = (
    ("knowledge.read", "read", "读取知识库应用域的集合、文档、评测和运行信息"),
    ("knowledge.write", "write", "创建或修改知识库应用域资源并启动业务操作"),
    ("knowledge.admin", "admin", "管理知识库平台成员、模型目录和平台级配置"),
)


def upgrade() -> None:
    """为知识库中央授权守卫登记稳定编码，保留已存在的目录项。"""
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO permissions (id, code, resource_type, scope, description)
        VALUES (CAST(:id AS uuid), :code, :resource_type, :scope, :description)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, scope, description in KNOWLEDGE_PERMISSIONS:
        connection.execute(statement, {
            "id": str(uuid4()),
            "code": code,
            "resource_type": "knowledge",
            "scope": scope,
            "description": description,
        })


def downgrade() -> None:
    """保留可能已授权的目录项，降级不删除管理员配置和历史关联。"""
    # 角色授权可能已引用这些编码，因此回退 revision 时不删除权限行。
    return None
