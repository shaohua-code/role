"""Create tenant-scoped user groups, memberships, and role assignments."""

from alembic import op
import sqlalchemy as sa

revision = "0010_tenant_user_groups"
down_revision = "0009_access_token_revocations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为租户组和继承关系建立复合外键，数据库层封死跨租户关联。"""
    op.create_table(
        "user_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_user_group_id_tenant"),
        sa.UniqueConstraint("tenant_id", "key", name="uq_user_group_tenant_key"),
    )
    op.create_index("ix_user_groups_tenant_id", "user_groups", ["tenant_id"])

    op.create_table(
        "user_group_memberships",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["group_id", "tenant_id"], ["user_groups.id", "user_groups.tenant_id"],
                                ondelete="CASCADE", name="fk_user_group_membership_group_tenant"),
        sa.ForeignKeyConstraint(["membership_id", "tenant_id"], ["tenant_memberships.id", "tenant_memberships.tenant_id"],
                                ondelete="CASCADE", name="fk_user_group_membership_member_tenant"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "membership_id"),
    )
    op.create_index("ix_user_group_memberships_membership_id", "user_group_memberships", ["membership_id"])
    op.create_index("ix_user_group_memberships_tenant_id", "user_group_memberships", ["tenant_id"])

    op.create_table(
        "user_group_roles",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["group_id", "tenant_id"], ["user_groups.id", "user_groups.tenant_id"],
                                ondelete="CASCADE", name="fk_user_group_role_group_tenant"),
        sa.ForeignKeyConstraint(["role_id", "tenant_id"], ["roles.id", "roles.tenant_id"],
                                ondelete="CASCADE", name="fk_user_group_role_role_tenant"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "role_id"),
    )
    op.create_index("ix_user_group_roles_role_id", "user_group_roles", ["role_id"])
    op.create_index("ix_user_group_roles_tenant_id", "user_group_roles", ["tenant_id"])


def downgrade() -> None:
    """逆序移除租户组关联及其索引。"""
    op.drop_index("ix_user_group_roles_tenant_id", table_name="user_group_roles")
    op.drop_index("ix_user_group_roles_role_id", table_name="user_group_roles")
    op.drop_table("user_group_roles")
    op.drop_index("ix_user_group_memberships_tenant_id", table_name="user_group_memberships")
    op.drop_index("ix_user_group_memberships_membership_id", table_name="user_group_memberships")
    op.drop_table("user_group_memberships")
    op.drop_index("ix_user_groups_tenant_id", table_name="user_groups")
    op.drop_table("user_groups")
