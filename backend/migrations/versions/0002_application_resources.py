"""application_resources

应用资源树（面向应用的菜单/按钮/数据规则显式资源）与角色资源授权关联表。

Revision ID: 0002_application_resources
Revises: 0001_greenfield_iam
Create Date: 2026-10-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_application_resources'
down_revision: Union[str, Sequence[str], None] = '0001_greenfield_iam'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建应用资源树与角色资源授权两张表。"""
    op.create_table('application_resources',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('application_id', sa.Uuid(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('resource_type', sa.String(length=20), nullable=False),
    sa.Column('code', sa.String(length=180), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('path', sa.String(length=300), nullable=True),
    sa.Column('icon', sa.String(length=120), nullable=True),
    sa.Column('sort', sa.Integer(), server_default='0', nullable=False),
    sa.Column('extra', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("resource_type IN ('menu', 'button', 'data_rule')", name='ck_application_resource_type'),
    sa.CheckConstraint("status IN ('active', 'disabled')", name='ck_application_resource_status'),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_id'], ['application_resources.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('application_id', 'code', name='uq_application_resource_app_code')
    )
    op.create_index(op.f('ix_application_resources_application_id'), 'application_resources', ['application_id'], unique=False)
    op.create_index(op.f('ix_application_resources_parent_id'), 'application_resources', ['parent_id'], unique=False)
    op.create_table('role_application_resources',
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('resource_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['resource_id'], ['application_resources.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('role_id', 'resource_id')
    )
    op.create_index(op.f('ix_role_application_resources_resource_id'), 'role_application_resources', ['resource_id'], unique=False)


def downgrade() -> None:
    """回滚：先删关联表，再删资源树表。"""
    op.drop_index(op.f('ix_role_application_resources_resource_id'), table_name='role_application_resources')
    op.drop_table('role_application_resources')
    op.drop_index(op.f('ix_application_resources_parent_id'), table_name='application_resources')
    op.drop_index(op.f('ix_application_resources_application_id'), table_name='application_resources')
    op.drop_table('application_resources')
