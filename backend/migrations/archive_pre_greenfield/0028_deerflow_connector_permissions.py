"""Register explicit IAM permissions for DeerFlow user connector flows."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0028_deerflow_connector_permissions"
down_revision = "0027_deerflow_resource_permissions"
branch_labels = None
depends_on = None


# Register definitions only. Never grant channel or integration permissions to
# existing roles automatically; administrators must choose the intended users.
DEERFLOW_PERMISSIONS = (
    ("deerflow.channel.read", "channel", "read", "查看本人 DeerFlow IM 连接"),
    ("deerflow.channel.write", "channel", "write", "连接或断开本人 DeerFlow IM 账号"),
    ("deerflow.channel.admin", "channel", "admin", "管理 DeerFlow 部署级 IM channel 凭据"),
    ("deerflow.integration.read", "integration", "read", "查看本人 DeerFlow 外部集成状态"),
    ("deerflow.integration.write", "integration", "write", "配置本人 DeerFlow 外部集成和授权"),
    ("deerflow.integration.admin", "integration", "admin", "安装 DeerFlow 部署级集成组件"),
)


def upgrade() -> None:
    """Append stable connector permissions without assigning them to roles."""
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
    """Preserve catalog entries referenced by grants or audit history."""
    return None