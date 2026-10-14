"""Seed tenant-scoped application administration permissions."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0018_tenant_application_admin_permissions"
down_revision = "0017_tenant_org_admin_permissions"
branch_labels = None
depends_on = None


APPLICATION_ADMIN_PERMISSIONS = (
    ("iam.application.read", "read", "查看本租户 OAuth 应用目录"),
    ("iam.application.manage", "manage", "创建、编辑和启停本租户 OAuth 应用"),
    ("iam.application.secret.rotate", "secret.rotate", "轮换本租户 OAuth 应用客户端密钥"),
)


def upgrade() -> None:
    """登记稳定权限编码；不自动授予租户角色，必须由平台管理员显式配置。"""
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO permissions (id, code, resource_type, scope, description)
        VALUES (CAST(:id AS uuid), :code, :resource_type, :scope, :description)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, scope, description in APPLICATION_ADMIN_PERMISSIONS:
        connection.execute(statement, {
            "id": str(uuid4()),
            "code": code,
            "resource_type": "iam.application",
            "scope": scope,
            "description": description,
        })


def downgrade() -> None:
    """保留可能已分配给租户角色的权限目录项。"""
    # 权限可能已经被租户角色引用；回退 schema 时不删除授权关系或审计语义。
    return None
