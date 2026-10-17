"""Register DeerFlow skill, subagent, and MCP administration permissions.

Revision ID: 0029_deerflow_agent_extension_permissions
Revises: 0028_deerflow_connector_permissions
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0029_deerflow_agent_extension_permissions"
down_revision = "0028_deerflow_connector_permissions"
branch_labels = None
depends_on = None


# Definitions only: deployment operators must explicitly grant them to roles.
DEERFLOW_PERMISSIONS = (
    ("deerflow.skill.read", "skill", "read", "读取 DeerFlow 技能目录和本人自定义技能"),
    ("deerflow.skill.write", "skill", "write", "安装或修改本人 DeerFlow 自定义技能"),
    ("deerflow.skill.delete", "skill", "delete", "删除本人 DeerFlow 自定义技能"),
    ("deerflow.skill.admin", "skill", "admin", "管理部署级 DeerFlow 技能配置和缓存"),
    ("deerflow.subagent.read", "subagent", "read", "读取 DeerFlow 子 Agent 目录"),
    ("deerflow.subagent.admin", "subagent", "admin", "管理部署级 DeerFlow 子 Agent 定义"),
    ("deerflow.mcp.admin", "mcp", "admin", "读取和管理部署级 DeerFlow MCP 配置"),
)


def upgrade() -> None:
    """Append stable permission definitions without assigning role grants."""
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
    """Preserve catalog entries that may already be referenced by grants."""
    return None
