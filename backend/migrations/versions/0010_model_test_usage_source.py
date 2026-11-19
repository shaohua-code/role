"""model_test_usage_source

模型测试台用量来源标记：model_usage_events.source 的 CHECK 约束放宽，
新增 'model_test'（管理台测试台经受控出口发起的真实 Provider 调用）。

口径（docs/模型测试台设计.md §5）：测试流量标记 source=model_test，
账目与普通业务流量可区分但不漏计；不落正文、不落提示词。

门禁（docs/部署与运维.md §门禁）：数据库迁移须先完成受保护备份、审阅影响
并取得明确授权后执行 `alembic upgrade head`。本迁移仅放宽一条 CHECK，
无数据回填；downgrade 恢复原约束（要求表中不存在 source='model_test' 行，
回滚前如已有测试台账目需先清理）。

Revision ID: 0010_model_test_usage
Revises: 0009_model_distribution
Create Date: 2026-11-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010_model_test_usage'
down_revision: Union[str, Sequence[str], None] = '0009_model_distribution'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_model_usage_source', 'model_usage_events', type_='check')
    op.create_check_constraint(
        'ck_model_usage_source', 'model_usage_events',
        "source IN ('gateway', 'admin_reconciliation', 'model_test')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_model_usage_source', 'model_usage_events', type_='check')
    op.create_check_constraint(
        'ck_model_usage_source', 'model_usage_events',
        "source IN ('gateway', 'admin_reconciliation')",
    )
