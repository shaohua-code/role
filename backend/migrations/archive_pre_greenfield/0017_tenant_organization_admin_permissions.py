"""Seed permission codes for tenant-scoped organization administration."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0017_tenant_org_admin_permissions"
down_revision = "0016_permission_status"
branch_labels = None
depends_on = None


ORGANIZATION_ADMIN_PERMISSIONS = (
    ("iam.organization.read", "read", "查看本租户组织、成员组织归属与角色数据范围"),
    ("iam.organization.manage", "manage", "维护本租户组织、成员组织归属与角色数据范围"),
)


def upgrade() -> None:
    """登记稳定权限编码；不自动授予租户角色，需平台管理员显式配置。"""
    # 默认 alembic_version.version_num 是 VARCHAR(32)，本迁移链含更长 revision ID；先扩列以免迁移完成后无法写入版本号。
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
    connection = op.get_bind()
    statement = sa.text(
        """
        INSERT INTO permissions (id, code, resource_type, scope, description)
        VALUES (CAST(:id AS uuid), :code, :resource_type, :scope, :description)
        ON CONFLICT (code) DO NOTHING
        """
    )
    for code, scope, description in ORGANIZATION_ADMIN_PERMISSIONS:
        connection.execute(statement, {
            "id": str(uuid4()),
            "code": code,
            "resource_type": "iam.organization",
            "scope": scope,
            "description": description,
        })


def downgrade() -> None:
    """保留可能已被租户角色使用的管理权限目录项。"""
    # 权限编码可能已被角色授权；回退 schema 时不级联删除实际授权与审计语义。
    return None
