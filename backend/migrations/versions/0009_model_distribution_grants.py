"""model_distribution_grants

模型三级分发：新增 model_tenant_grants（平台 → 租户下发）与
model_application_grants（租户 → 应用下发）两张关系表。

口径（产品需求 §6.4）：应用可见 = 平台目录 ∩ 租户下发 ∩ 应用下发；下发关系
即授权唯一依据；回收为软失效（status='revoked' 保留行供恢复与审计）。
平台目录沿用 model_catalog 表（目录行归属 platform 租户，slug=platform），
本迁移不改该表结构、不搬迁存量（应用前现网 model_catalog 为 0 行，已核验）。

门禁（docs/部署与运维.md §门禁）：数据库迁移须先完成受保护备份、审阅影响
并取得明确授权。迁移前备份：
backups/iam-postgres-20261116T091107Z-48ca66ff.dump（SHA-256 见同名 .sha256）。
对 dev 库的应用操作须待用户明确授权后执行。

Revision ID: 0009_model_distribution
Revises: 0008_status_server_default
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_model_distribution'
down_revision: Union[str, Sequence[str], None] = '0008_status_server_default'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建平台→租户与租户→应用两张下发关系表（回收软失效语义）。"""
    op.create_table('model_tenant_grants',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('model_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
    sa.Column('granted_by', sa.Uuid(), nullable=True),
    sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('active', 'revoked')", name='ck_model_tenant_grant_status'),
    sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['model_id'], ['model_catalog.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('model_id', 'tenant_id', name='uq_model_tenant_grant')
    )
    op.create_index(op.f('ix_model_tenant_grants_model_id'), 'model_tenant_grants', ['model_id'], unique=False)
    op.create_index(op.f('ix_model_tenant_grants_tenant_status'), 'model_tenant_grants', ['tenant_id', 'status'], unique=False)
    op.create_table('model_application_grants',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('model_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('application_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
    sa.Column('granted_by', sa.Uuid(), nullable=True),
    sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('active', 'revoked')", name='ck_model_application_grant_status'),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['model_id'], ['model_catalog.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('model_id', 'application_id', name='uq_model_application_grant')
    )
    op.create_index(op.f('ix_model_application_grants_model_id'), 'model_application_grants', ['model_id'], unique=False)
    op.create_index(op.f('ix_model_application_grants_app_status'), 'model_application_grants', ['application_id', 'status'], unique=False)
    op.create_index(op.f('ix_model_application_grants_tenant_status'), 'model_application_grants', ['tenant_id', 'status'], unique=False)


def downgrade() -> None:
    """回滚：删除两张下发关系表（软失效关系一并消失，目录与用量账本不受影响）。"""
    op.drop_index(op.f('ix_model_application_grants_tenant_status'), table_name='model_application_grants')
    op.drop_index(op.f('ix_model_application_grants_app_status'), table_name='model_application_grants')
    op.drop_index(op.f('ix_model_application_grants_model_id'), table_name='model_application_grants')
    op.drop_table('model_application_grants')
    op.drop_index(op.f('ix_model_tenant_grants_tenant_status'), table_name='model_tenant_grants')
    op.drop_index(op.f('ix_model_tenant_grants_model_id'), table_name='model_tenant_grants')
    op.drop_table('model_tenant_grants')
