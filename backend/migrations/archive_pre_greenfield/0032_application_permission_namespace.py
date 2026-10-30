"""Bind applications and permission catalog entries to product namespaces."""

from alembic import op
import sqlalchemy as sa

revision = "0032_application_permission_namespace"
down_revision = "0031_model_usage_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "permissions",
        sa.Column("catalog_namespace", sa.String(length=100), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE permissions
            SET catalog_namespace = CASE
                WHEN code LIKE 'iam.%' THEN 'platform'
                ELSE split_part(code, '.', 1)
            END
            """
        )
    )
    op.alter_column("permissions", "catalog_namespace", nullable=False)
    op.create_index(
        "ix_permissions_catalog_namespace_code",
        "permissions",
        ["catalog_namespace", "code"],
        unique=False,
    )

    op.add_column(
        "applications",
        sa.Column("permission_namespace", sa.String(length=100), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE applications
            SET permission_namespace = lower(
                split_part(
                    regexp_replace(client_id, '[._-].*$', ''),
                    '.',
                    1
                )
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE applications
            SET permission_namespace = 'app'
            WHERE permission_namespace IS NULL OR permission_namespace = ''
            """
        )
    )
    op.alter_column("applications", "permission_namespace", nullable=False)


def downgrade() -> None:
    op.drop_column("applications", "permission_namespace")
    op.drop_index("ix_permissions_catalog_namespace_code", table_name="permissions")
    op.drop_column("permissions", "catalog_namespace")
