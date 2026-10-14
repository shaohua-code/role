from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine
from app.schemas.health import HealthResponse

# 健康路由单独分组，后续可扩展存活探针和依赖就绪检查。
router = APIRouter(tags=["health"])


def _migration_heads() -> set[str]:
    """Return the revisions this exact backend source tree expects."""
    backend_root = Path(__file__).resolve().parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    return set(ScriptDirectory.from_config(config).get_heads())


@router.get("/health", response_model=HealthResponse, summary="API 进程健康检查")
def health_check() -> HealthResponse:
    """只报告 API 进程已响应；目前不访问数据库，不能作为数据库就绪证明。"""
    return HealthResponse(status="ok", service="iam-api")


@router.get("/ready", response_model=HealthResponse, summary="服务依赖就绪检查")
def readiness_check() -> HealthResponse:
    """确认数据库可达且已迁移到当前源码版本；失败时不泄漏连接细节。"""
    try:
        # 就绪探针只读检查连接和 Alembic 版本，不在请求中执行 schema 写入。
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
            if inspect(connection).has_table("alembic_version"):
                current_revisions = set(
                    connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
                )
            else:
                current_revisions = set()
    except (RuntimeError, SQLAlchemyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database_not_ready",
        ) from exc

    try:
        expected_revisions = _migration_heads()
    except Exception as exc:
        # 配置或迁移图无法解析时，不能把旧 schema 标记为 ready。
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="migration_state_unavailable",
        ) from exc

    if current_revisions != expected_revisions:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database_migration_pending",
        )

    return HealthResponse(status="ok", service="iam-api")
