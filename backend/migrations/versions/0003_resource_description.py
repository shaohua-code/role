"""application_resource_description

应用资源树补 description 描述列（P358：资源感知增强，仅展示用途）。

Revision ID: 0003_resource_description
Revises: 0002_application_resources
Create Date: 2026-10-27
（revision id 全长须 ≤32：alembic_version.version_num 为 varchar(32)）

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_resource_description'
down_revision: Union[str, Sequence[str], None] = '0002_application_resources'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为应用资源树增加可选描述列。"""
    op.add_column('application_resources', sa.Column('description', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """回滚：删除描述列。"""
    op.drop_column('application_resources', 'description')
