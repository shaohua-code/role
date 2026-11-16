"""status_server_default_alignment

模型对齐：为 8 张业务表的 status 列补齐数据库层默认值 'active'（与 ORM default 一致）。
涉及表：tenants / users / tenant_memberships / roles / applications / user_groups /
organizations / model_catalog。

动机：这些列此前只有 Python 侧 default，裸 SQL / 非 ORM 写入路径会因 NOT NULL 违规失败；
补 server_default 后所有写入路径行为一致。存量数据全部已为 'active'，本迁移不更新任何行。

门禁（docs/部署与运维.md §门禁）：数据库迁移须先完成受保护备份、审阅影响并取得明确授权。
本迁移已获用户授权（2026-11-16），迁移前备份：
backups/iam-postgres-20261116T062825Z-59bd81af.dump（SHA-256 见同名 .sha256）。
幂等可重放：重复设置相同默认值无副作用。

Revision ID: 0008_status_server_default
Revises: 0007_role_scope_backfill
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_status_server_default"
down_revision: Union[str, Sequence[str], None] = "0007_role_scope_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (表名, 列名) 全部为 String(20) NOT NULL status 列，统一补 'active' 默认值。
_STATUS_TABLES = (
    "tenants",
    "users",
    "tenant_memberships",
    "roles",
    "applications",
    "user_groups",
    "organizations",
    "model_catalog",
)


def upgrade() -> None:
    for table in _STATUS_TABLES:
        op.alter_column(
            table,
            "status",
            existing_type=sa.String(20),
            server_default="active",
            existing_nullable=False,
        )


def downgrade() -> None:
    # 回退仅撤销数据库层默认值，不修改任何存量行。
    for table in _STATUS_TABLES:
        op.alter_column(
            table,
            "status",
            existing_type=sa.String(20),
            server_default=None,
            existing_nullable=False,
        )
