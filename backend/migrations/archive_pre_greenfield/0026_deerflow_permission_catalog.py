"""Register the stable permission codes used by the DeerFlow IAM pilot."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0026_deerflow_permission_catalog"
down_revision = "0025_registration_role_snapshot"
branch_labels = None
depends_on = None


# The migration only registers global permission definitions. It deliberately
# does not create tenants, applications, roles, bindings, grants, or data scopes.
DEERFLOW_PERMISSIONS = (
    ("deerflow.project.read", "project", "read", "读取本人 DeerFlow 项目"),
    ("deerflow.project.write", "project", "write", "创建或更新本人 DeerFlow 项目"),
    ("deerflow.project.delete", "project", "delete", "删除本人 DeerFlow 项目"),
    ("deerflow.thread.read", "thread", "read", "读取本人 DeerFlow 会话"),
    ("deerflow.thread.write", "thread", "write", "创建或更新本人 DeerFlow 会话"),
    ("deerflow.thread.delete", "thread", "delete", "删除本人 DeerFlow 会话"),
    ("deerflow.run.create", "run", "create", "创建 DeerFlow Agent 运行"),
    ("deerflow.run.read", "run", "read", "读取本人 DeerFlow 运行记录"),
    ("deerflow.run.cancel", "run", "cancel", "取消本人 DeerFlow 运行"),
    ("deerflow.model.list", "model", "list", "查看 DeerFlow 可用模型"),
    ("deerflow.model.use", "model", "use", "在 DeerFlow 中调用模型"),
    ("deerflow.tool.use", "tool", "use", "在 DeerFlow Agent 中使用工具"),
    ("deerflow.sandbox.execute", "sandbox", "execute", "在 DeerFlow 中执行沙箱操作"),
)


def upgrade() -> None:
    """Register DeerFlow's permission vocabulary without granting access."""
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
    """Keep the append-only permission catalog to preserve grants and audit history."""
    return None
