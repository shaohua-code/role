"""创建 IAM 首期数据模型。初始 revision 保持独立于后续 ORM 改动。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """静态建表 DDL：线上 schema 只通过 Alembic revision 演进。"""
    op.create_table("tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_table("users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("email", sa.String(320)),
        sa.Column("phone_number", sa.String(32)), sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)), sa.Column("phone_verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("email IS NOT NULL OR phone_number IS NOT NULL", name="ck_user_has_login_id"))
    op.create_index("ix_users_email", "users", ["email"], unique=True); op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=True)
    op.create_table("tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"))
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"]); op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"])
    op.create_table("applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(160), nullable=False), sa.Column("client_secret_hash", sa.String(255)),
        sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.String(500)),
        sa.Column("redirect_uris", sa.JSON(), nullable=False), sa.Column("post_logout_redirect_uris", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_applications_tenant_id", "applications", ["tenant_id"]); op.create_index("ix_applications_client_id", "applications", ["client_id"], unique=True)
    op.create_table("model_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(100), nullable=False), sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(160), nullable=False), sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("endpoint_url", sa.String(500)), sa.Column("credential_ref", sa.String(300)),
        sa.Column("capabilities", sa.JSON(), nullable=False), sa.Column("rpm_limit", sa.Integer()), sa.Column("tpm_limit", sa.Integer()),
        sa.Column("input_cost_per_million", sa.Numeric(12, 6)), sa.Column("output_cost_per_million", sa.Numeric(12, 6)),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "key", name="uq_model_tenant_key"))
    op.create_index("ix_model_catalog_tenant_id", "model_catalog", ["tenant_id"])
    op.create_table("roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="SET NULL")),
        sa.Column("key", sa.String(100), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500)), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"]); op.create_index("ix_roles_application_id", "roles", ["application_id"])
    op.create_index("uq_role_tenant_key", "roles", ["tenant_id", "key"], unique=True, postgresql_where=sa.text("application_id IS NULL"))
    op.create_index("uq_role_app_key", "roles", ["tenant_id", "application_id", "key"], unique=True, postgresql_where=sa.text("application_id IS NOT NULL"))
    op.create_table("permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("code", sa.String(180), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False), sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("description", sa.String(500)))
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True); op.create_index("ix_permissions_resource_type", "permissions", ["resource_type"])
    op.create_table("role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", sa.String(180)))
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"]); op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"]); op.create_index("ix_role_permissions_resource_id", "role_permissions", ["resource_id"])
    op.create_table("role_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_memberships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("membership_id", "role_id", name="uq_membership_role"))
    op.create_index("ix_role_bindings_membership_id", "role_bindings", ["membership_id"]); op.create_index("ix_role_bindings_role_id", "role_bindings", ["role_id"])
    op.create_table("application_themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("application_id", "version", name="uq_application_theme_version"))
    op.create_index("ix_application_themes_application_id", "application_themes", ["application_id"])
    op.create_table("audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(120), nullable=False), sa.Column("target_type", sa.String(80), nullable=False),
        sa.Column("target_id", sa.String(180)), sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("source_ip", sa.String(64)), sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"]); op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"]); op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    """回滚初始 schema 会删除所有 IAM 数据，仅可用于本地开发数据库。"""
    op.drop_table("audit_events"); op.drop_table("application_themes"); op.drop_table("role_bindings")
    op.drop_table("role_permissions"); op.drop_table("permissions"); op.drop_table("roles")
    op.drop_table("model_catalog"); op.drop_table("applications"); op.drop_table("tenant_memberships"); op.drop_table("users"); op.drop_table("tenants")
