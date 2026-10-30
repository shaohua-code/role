"""Register DeerFlow personal preference permissions.

Revision ID: 0030_deerflow_preference_permissions
Revises: 0029_deerflow_agent_extension_permissions
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0030_deerflow_preference_permissions"
down_revision = "0029_deerflow_agent_extension_permissions"
branch_labels = None
depends_on = None


# Definitions only: no existing user or role receives a grant automatically.
DEERFLOW_PERMISSIONS = (
    ("deerflow.preference.read", "preference", "read", "读取本人 DeerFlow 界面偏好"),
    ("deerflow.preference.write", "preference", "write", "修改本人 DeerFlow 界面偏好"),
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
    """Keep catalog rows that may already be referenced by grants or audit."""
    return None
