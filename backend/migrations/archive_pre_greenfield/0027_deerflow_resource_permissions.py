"""Register DeerFlow agent and memory permissions added after the pilot catalog."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0027_deerflow_resource_permissions"
down_revision = "0026_deerflow_permission_catalog"
branch_labels = None
depends_on = None


# Register stable definitions only. Application roles, grants, and self data
# scopes must be configured explicitly; migration grants no product access.
DEERFLOW_PERMISSIONS = (
    ("deerflow.agent.read", "agent", "read", "读取本人 DeerFlow 自建 Agent"),
    ("deerflow.agent.write", "agent", "write", "创建或更新本人 DeerFlow 自建 Agent"),
    ("deerflow.agent.delete", "agent", "delete", "删除本人 DeerFlow 自建 Agent"),
    ("deerflow.agent.admin", "agent", "admin", "管理 DeerFlow 部署级共享 Agent 用户资料"),
    ("deerflow.memory.read", "memory", "read", "读取本人 DeerFlow 记忆数据"),
    ("deerflow.memory.write", "memory", "write", "创建或更新本人 DeerFlow 记忆数据"),
    ("deerflow.memory.delete", "memory", "delete", "删除本人 DeerFlow 记忆数据"),
    ("deerflow.memory.admin", "memory", "admin", "查看 DeerFlow 记忆服务配置"),
)


def upgrade() -> None:
    """Append agent and memory permission codes without assigning them to roles."""
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO permissions (id, code, resource_type, scope, description)
        VALUES (CAST(:id AS uuid), :code, :resource_type, :scope, :description)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, resource_type, scope, description in DEERFLOW_PERMISSIONS:
        connection.execute(
            statement,
            {
                "id": str(uuid4()),
                "code": code,
                "resource_type": resource_type,
                "scope": scope,
                "description": description,
            },
        )


def downgrade() -> None:
    """Preserve permission definitions referenced by grants or audit history."""
    return None
