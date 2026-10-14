"""低频维护任务；只回收到期后已不能再参与认证的短期凭证与节流键。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models.identity import (LoginAttemptBucket, PasswordResetThrottle, PasswordResetToken,
                                 PublicRegistrationChallenge, PublicRegistrationThrottle,
                                 RefreshSession, RevokedAccessToken)
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest

# 不删除 OAuthRefreshToken：已轮换的旧令牌要保留到整族会话过期，
# 才能识别迟到的重放并撤销仍有效的后继令牌。
_EXPIRABLE_CREDENTIAL_MODELS = (
    RefreshSession,
    RevokedAccessToken,
    OAuthAuthorizationCode,
    OAuthConsentRequest,
    PasswordResetToken,
    PasswordResetThrottle,
    LoginAttemptBucket,
    PublicRegistrationChallenge,
    PublicRegistrationThrottle,
)


def cleanup_expired_credentials(
    db: Session,
    *,
    now: datetime | None = None,
    batch_size: int = 1000,
) -> dict[str, int]:
    """原子回收已过期的管理会话、JWT 撤销摘要、OIDC 凭证、密码重置凭证与节流键。

    清理边界严格使用 expires_at，而不是 revoked_at/consumed_at：
    未到期凭证仍保留其单次消费与撤销证据；审计、邀请、OAuth 刷新族和模型
    request_id 记录不属于此任务，以免破坏追溯、重放检测或幂等保证。

    每张表最多处理 batch_size 行；FOR UPDATE SKIP LOCKED 允许开发环境多个
    worker 同时运行时各自领取不同记录。整个批次在一个事务中提交。
    """
    cutoff = now or datetime.now(timezone.utc)
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    deleted: dict[str, int] = {}
    try:
        for model in _EXPIRABLE_CREDENTIAL_MODELS:
            # 模型主键类型各不相同（JWT 撤销表以摘要为主键），因此从 ORM
            # Table 元数据读取主键，避免维护任务重复写死字段名。
            primary_key = next(iter(model.__table__.primary_key.columns))
            expired_ids = (
                select(primary_key)
                .where(model.expires_at <= cutoff)
                .order_by(model.expires_at, primary_key)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            result = db.execute(delete(model).where(primary_key.in_(expired_ids)))
            deleted[model.__tablename__] = max(result.rowcount or 0, 0)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return deleted


def cleanup_expired_credentials_from_database(*, batch_size: int = 1000) -> dict[str, int]:
    """后台任务入口：创建并关闭独立 Session，绝不共享 HTTP 请求 Session。"""
    with Session(get_engine()) as db:
        return cleanup_expired_credentials(db, batch_size=batch_size)
