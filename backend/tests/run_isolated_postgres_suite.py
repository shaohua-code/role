"""在当前 PostgreSQL 服务内建立随机临时库，迁移至 head 后运行后端套件并清理。

本脚本只会创建并删除其自身生成的 `iam_test_<uuid>` 数据库；不会连接或迁移
DATABASE_URL 指向的业务库。测试失败也会清理临时库，避免残留含测试身份的数据。
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main() -> int:
    """在测试专用数据库中执行完整 migration 和 unittest suite。"""
    source_url = os.environ.get("DATABASE_URL", "")
    if not source_url:
        print("DATABASE_URL 未配置；拒绝连接或猜测任何数据库。", file=sys.stderr)
        return 2

    url = make_url(source_url)
    if url.drivername != "postgresql+psycopg" or not url.database:
        print("仅支持已配置的 postgresql+psycopg DATABASE_URL。", file=sys.stderr)
        return 2

    test_database = f"iam_test_{uuid4().hex}"
    if not re.fullmatch(r"iam_test_[0-9a-f]{32}", test_database):
        raise RuntimeError("内部测试库标识格式异常")

    admin_engine = create_engine(url.set(database="postgres"), pool_pre_ping=True)
    created = False
    test_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = url.set(database=test_database).render_as_string(hide_password=False)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            can_create = connection.scalar(text(
                "SELECT rolsuper OR rolcreatedb FROM pg_roles WHERE rolname = current_user"
            ))
            if not can_create:
                print("当前 PostgreSQL 用户没有 CREATEDB 权限；未创建测试数据库。", file=sys.stderr)
                return 2
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_database},
            )
            if exists:
                raise RuntimeError("随机测试库名已存在；拒绝触碰该数据库")
            connection.exec_driver_sql(f'CREATE DATABASE "{test_database}"')
            created = True

        commands = (
            [sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
        )
        for command in commands:
            result = subprocess.run(command, cwd=test_root, env=env, check=False)
            if result.returncode != 0:
                return result.returncode
        return 0
    finally:
        if created:
            try:
                # 测试子进程已退出，只终止连接到本脚本随机创建的数据库的残留会话。
                with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                    connection.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname = :name AND pid <> pg_backend_pid()"
                        ),
                        {"name": test_database},
                    )
                    connection.exec_driver_sql(f'DROP DATABASE "{test_database}"')
            except Exception as exc:
                print(
                    f"无法自动删除本脚本创建的临时数据库 {test_database}；"
                    f"请在确认它仍属于本次测试后手工清理 ({type(exc).__name__})。",
                    file=sys.stderr,
                )
                raise
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
