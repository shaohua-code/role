"""创建 PostgreSQL 引擎和请求级数据库会话。"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """按需创建并复用连接池；没有数据库配置时明确报错，不偷偷退化。"""
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    # pool_pre_ping 在取出连接时做轻量探测，避免把已断开的连接交给请求。
    return create_engine(database_url, pool_pre_ping=True)


def get_db_session() -> Generator[Session, None, None]:
    """为单个请求提供 Session，并确保请求结束后释放连接资源。

    事务由 service 层显式提交或回滚；依赖只负责生命周期，防止路由之间
    共享 Session。业务写入接入后，失败路径必须回滚后再抛出异常。
    """
    with Session(get_engine()) as session:
        yield session
