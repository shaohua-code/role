"""role_scope_backfill_nulls

存量回填：roles.scope 空值行按 effective_role_scope 推导口径补齐（同 services/rbac_guards.py）：
1. 模板 key（platform.admin / tenant.admin / app.admin / app.member）→ 模板固定范围；
2. 其余钉应用行（application_id 非空）→ app；
3. 其余平台角色行（application_id 为空）→ tenant。

门禁（docs/部署与运维.md §门禁）：数据库迁移须先完成受保护备份、审阅影响并取得明确授权。
本迁移幂等可重放（仅命中 scope IS NULL 行，重放无副作用）；执行成功后 roles.scope 不应再有 NULL。
回填验证通过后，GET /admin/roles（list_roles）中的空值兼容条件可简化为
Role.scope.in_(allowed_scopes)（见 access_control.py 的 NULL-scope 注释）。
本文件只入库，不在未授权前对开发库执行。

Revision ID: 0007_role_scope_backfill
Revises: 0006_role_scope_nodes
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "0007_role_scope_backfill"
down_revision: Union[str, Sequence[str], None] = "0006_role_scope_nodes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # 先统计再执行：打印将要回填的行数，留痕于迁移日志。
    pending = bind.execute(
        text("SELECT count(*) FROM roles WHERE scope IS NULL")
    ).scalar_one()
    print(f"[0007_role_scope_backfill] 待回填 roles.scope IS NULL 行数：{pending}")
    # 幂等回填：CASE 分支与 effective_role_scope 逐条对应；仅命中 scope IS NULL 行，重放无副作用。
    op.execute(
        "UPDATE roles SET scope = CASE"
        " WHEN key = 'platform.admin' THEN 'super'"
        " WHEN key = 'tenant.admin' THEN 'tenant'"
        " WHEN key = 'app.admin' THEN 'app'"
        " WHEN key = 'app.member' THEN 'member'"
        " WHEN application_id IS NOT NULL THEN 'app'"
        " ELSE 'tenant' END"
        " WHERE scope IS NULL"
    )
    # 执行后校验：roles.scope 不应再有 NULL（有残留说明口径存在未覆盖分支，须排查）。
    after = bind.execute(
        text("SELECT count(*) FROM roles WHERE scope IS NULL")
    ).scalar_one()
    print(f"[0007_role_scope_backfill] 回填后 scope IS NULL 行数：{after}（应为 0）")


def downgrade() -> None:
    # 数据回填不可逆（空值仅为历史存量状态，无业务含义）；如需回到回填前状态请恢复受保护备份。
    pass
