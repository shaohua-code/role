"""增加租户组织树、成员组织归属及角色数据范围策略。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_organizations_data_scopes"
down_revision = "0003_oauth_code_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加复合唯一约束后，数据库能用复合外键阻止跨租户成员/部门/角色引用。
    op.create_unique_constraint("uq_membership_id_tenant", "tenant_memberships", ["id", "tenant_id"])
    op.create_unique_constraint("uq_role_id_tenant", "roles", ["id", "tenant_id"])
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True)),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "key", name="uq_organization_tenant_key"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_organization_id_tenant"),
        sa.ForeignKeyConstraint(["parent_id", "tenant_id"], ["organizations.id", "organizations.tenant_id"],
                                ondelete="RESTRICT", name="fk_organization_parent_same_tenant"),
    )
    op.create_index("ix_organizations_tenant_id", "organizations", ["tenant_id"])
    op.create_index("ix_organizations_parent_id", "organizations", ["parent_id"])
    op.create_table(
        "membership_organizations",
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["membership_id", "tenant_id"], ["tenant_memberships.id", "tenant_memberships.tenant_id"],
                                ondelete="CASCADE", name="fk_membership_organization_member_tenant"),
        sa.ForeignKeyConstraint(["organization_id", "tenant_id"], ["organizations.id", "organizations.tenant_id"],
                                ondelete="CASCADE", name="fk_membership_organization_org_tenant"),
    )
    op.create_index("ix_membership_organizations_organization_id", "membership_organizations", ["organization_id"])
    op.create_index("ix_membership_organizations_tenant_id", "membership_organizations", ["tenant_id"])
    op.create_index("uq_membership_primary_organization", "membership_organizations", ["membership_id"],
                    unique=True, postgresql_where=sa.text("is_primary IS TRUE"))
    op.create_table(
        "role_data_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("organization_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["role_id", "tenant_id"], ["roles.id", "roles.tenant_id"],
                                ondelete="CASCADE", name="fk_data_scope_role_tenant"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission_data_scope"),
        sa.CheckConstraint("scope_type IN ('tenant', 'self', 'organization', 'organization_tree', 'selected_organizations')",
                           name="ck_data_scope_type"),
    )
    op.create_index("ix_role_data_scopes_tenant_id", "role_data_scopes", ["tenant_id"])
    op.create_index("ix_role_data_scopes_role_id", "role_data_scopes", ["role_id"])
    op.create_index("ix_role_data_scopes_permission_id", "role_data_scopes", ["permission_id"])


def downgrade() -> None:
    op.drop_index("ix_role_data_scopes_permission_id", table_name="role_data_scopes")
    op.drop_index("ix_role_data_scopes_role_id", table_name="role_data_scopes")
    op.drop_index("ix_role_data_scopes_tenant_id", table_name="role_data_scopes")
    op.drop_table("role_data_scopes")
    op.drop_index("uq_membership_primary_organization", table_name="membership_organizations")
    op.drop_index("ix_membership_organizations_tenant_id", table_name="membership_organizations")
    op.drop_index("ix_membership_organizations_organization_id", table_name="membership_organizations")
    op.drop_table("membership_organizations")
    op.drop_index("ix_organizations_parent_id", table_name="organizations")
    op.drop_index("ix_organizations_tenant_id", table_name="organizations")
    op.drop_table("organizations")
    op.drop_constraint("uq_role_id_tenant", "roles", type_="unique")
    op.drop_constraint("uq_membership_id_tenant", "tenant_memberships", type_="unique")
