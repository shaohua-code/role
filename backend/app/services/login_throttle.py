"""登录失败节流：原始账号标识和客户端地址只参与 HMAC，从不持久化。"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.identity import LoginAttemptBucket


@dataclass(frozen=True)
class LoginThrottleTicket:
    """一次登录请求持有的三个已锁定桶键；只在当前请求事务中使用。

    account_key 是纯邮箱维度桶（G20）：同一账号换 IP 仍受账号级锁定约束；
    阈值刻意高于“邮箱×IP”组合桶，降低恶意第三方故意锁号的代价。
    """

    account_key: str
    identifier_key: str
    address_key: str
    blocked_until: datetime | None = None


def client_ip_for_request(request: Request, settings) -> str:
    """统一解析节流与审计使用的客户端地址；只信任明确配置的专用代理头。"""
    address = None
    if settings.trust_proxy_client_ip:
        forwarded = request.headers.get("x-iam-client-ip")
        if not forwarded:
            raise HTTPException(503, "登录保护代理地址未配置")
        address = forwarded.strip()
    elif request.client:
        address = request.client.host

    try:
        # 规范化 IPv4/IPv6 表示，防止同一地址通过不同文本形式绕过计数。
        return str(ipaddress.ip_address(address or "0.0.0.0"))
    except ValueError:
        if settings.trust_proxy_client_ip:
            raise HTTPException(503, "登录保护代理地址无效") from None
        # ASGI 测试客户端或 Unix socket 没有 IP 时统一进入保守桶，不信任客户端自报地址。
        return "0.0.0.0"


def _key_hash(secret: str, purpose: str, value: str) -> str:
    """HMAC-SHA256 派生桶键摘要；purpose 域分隔避免不同用途的键互相碰撞。"""
    material = f"iam-login-throttle:{purpose}:{value}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()


def _utc(value: datetime) -> datetime:
    """SQLite 测试驱动会去掉时区；比较前统一恢复 UTC。"""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _insert_missing_buckets(db: Session, key_hashes: list[str], now: datetime, retain_seconds: int) -> None:
    """并发首次登录时用唯一键原子创建桶，等待已存在行的事务提交。"""
    dialect = db.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert is None:
        raise RuntimeError(f"登录节流不支持数据库方言：{dialect}")
    statement = insert(LoginAttemptBucket).values([
        {
            "key_hash": key_hash,
            "failed_attempts": 0,
            "window_started_at": now,
            "blocked_until": None,
            "expires_at": now + timedelta(seconds=retain_seconds),
        }
        for key_hash in key_hashes
    ]).on_conflict_do_nothing(index_elements=["key_hash"])
    db.execute(statement)


def begin_login_attempt(db: Session, email: str, client_ip: str, settings,
                        *, now: datetime | None = None) -> LoginThrottleTicket:
    """锁定账号/纯邮箱/来源三个桶后检查封禁状态，令同一来源并发请求串行通过检查。"""
    current = _utc(now or datetime.now(timezone.utc))
    address = str(ipaddress.ip_address(client_ip))
    account_key = _key_hash(settings.jwt_secret, "identity", email.casefold())
    identifier_key = _key_hash(settings.jwt_secret, "identity-address", f"{email.casefold()}|{address}")
    address_key = _key_hash(settings.jwt_secret, "address", address)
    key_hashes = sorted((account_key, identifier_key, address_key))
    retain_seconds = settings.login_attempt_window_seconds + settings.login_block_seconds
    _insert_missing_buckets(db, key_hashes, current, retain_seconds)

    # 按摘要固定排序拿行锁，避免并发登录在多个桶上形成相反锁序。
    buckets = db.scalars(
        select(LoginAttemptBucket)
        .where(LoginAttemptBucket.key_hash.in_(key_hashes))
        .order_by(LoginAttemptBucket.key_hash)
        .with_for_update()
    ).all()
    if len(buckets) != 3:
        raise RuntimeError("登录节流桶创建或读取失败")

    blocked_until = None
    for bucket in buckets:
        old_block = _utc(bucket.blocked_until) if bucket.blocked_until else None
        window_expired = _utc(bucket.window_started_at) + timedelta(
            seconds=settings.login_attempt_window_seconds
        ) <= current
        if old_block and old_block > current:
            blocked_until = max(blocked_until, old_block) if blocked_until else old_block
            continue
        if window_expired or old_block:
            bucket.failed_attempts = 0
            bucket.window_started_at = current
            bucket.blocked_until = None
            bucket.expires_at = current + timedelta(seconds=retain_seconds)

    if blocked_until:
        return LoginThrottleTicket(account_key, identifier_key, address_key, blocked_until)
    return LoginThrottleTicket(account_key, identifier_key, address_key)


def record_login_failure(db: Session, ticket: LoginThrottleTicket, settings,
                         *, now: datetime | None = None) -> None:
    """只在口令验证失败后递增桶；跨过阈值后阻止该账号/来源继续消耗 Argon2。"""
    current = _utc(now or datetime.now(timezone.utc))
    buckets = {
        row.key_hash: row
        for row in db.scalars(select(LoginAttemptBucket).where(
            LoginAttemptBucket.key_hash.in_((ticket.account_key, ticket.identifier_key, ticket.address_key))
        )).all()
    }
    thresholds = {
        ticket.account_key: settings.login_account_max_failures,
        ticket.identifier_key: settings.login_identifier_max_failures,
        ticket.address_key: settings.login_ip_max_failures,
    }
    for key_hash, threshold in thresholds.items():
        bucket = buckets.get(key_hash)
        if bucket is None:
            raise RuntimeError("登录失败计数桶丢失")
        bucket.failed_attempts += 1
        if bucket.failed_attempts >= threshold:
            bucket.blocked_until = current + timedelta(seconds=settings.login_block_seconds)
            bucket.expires_at = bucket.blocked_until + timedelta(
                seconds=settings.login_attempt_window_seconds
            )


def clear_login_identifier_failures(db: Session, ticket: LoginThrottleTicket, settings,
                                    *, now: datetime | None = None) -> None:
    """验证成功清除纯邮箱桶与当前账号/来源组合的失败数，不抹去同地址其他账号的失败轨迹。"""
    current = _utc(now or datetime.now(timezone.utc))
    for key_hash in (ticket.account_key, ticket.identifier_key):
        bucket = db.get(LoginAttemptBucket, key_hash)
        if bucket:
            bucket.failed_attempts = 0
            bucket.window_started_at = current
            bucket.blocked_until = None
            bucket.expires_at = current + timedelta(seconds=settings.login_attempt_window_seconds)
