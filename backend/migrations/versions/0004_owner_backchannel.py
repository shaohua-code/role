"""owner_group_parent_backchannel

G19/G24 批量 schema 增强（三项均为可空列，存量数据零影响）：
1. applications.backchannel_logout_uri —— OIDC Back-Channel Logout 1.0 推送地址
2. organizations.owner_user_id —— 部门负责人
3. user_groups.parent_group_id —— 用户组嵌套（复合外键限同租户，RESTRICT 防孤孙）

Revision ID: 0004_owner_backchannel
Revises: 0003_resource_description
Create Date: 2026-10-28
（revision id 全长须 ≤32：alembic_version.version_num 为 varchar(32)）

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_owner_backchannel'
down_revision: Union[str, Sequence[str], None] = '0003_resource_description'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """三表各加一个可空列；用户组嵌套需要 SQLite batch 模式建复合外键。"""
    op.add_column('applications', sa.Column('backchannel_logout_uri', sa.String(length=500), nullable=True))

    op.add_column('organizations', sa.Column('owner_user_id', sa.Uuid(), nullable=True))
    op.create_index('ix_organizations_owner_user_id', 'organizations', ['owner_user_id'])

    with op.batch_alter_table('user_groups') as batch:
        batch.add_column(sa.Column('parent_group_id', sa.Uuid(), nullable=True))
        batch.create_index('ix_user_groups_parent_group_id', ['parent_group_id'])
        batch.create_foreign_key(
            'fk_user_group_parent_same_tenant',
            'user_groups', ['parent_group_id', 'tenant_id'], ['id', 'tenant_id'],
            ondelete='RESTRICT',
        )


def downgrade() -> None:
    """回滚按逆序删除三列（用户组先删外键与索引再删列）。"""
    with op.batch_alter_table('user_groups') as batch:
        batch.drop_constraint('fk_user_group_parent_same_tenant', type_='foreignkey')
        batch.drop_index('ix_user_groups_parent_group_id')
        batch.drop_column('parent_group_id')
    op.drop_index('ix_organizations_owner_user_id', table_name='organizations')
    op.drop_column('organizations', 'owner_user_id')
    op.drop_column('applications', 'backchannel_logout_uri')
