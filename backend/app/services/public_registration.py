"""ToC 自助注册策略、邮箱验证与事务发件箱。"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.models.application import Application, ApplicationTheme
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import (
    PublicRegistrationChallenge,
    PublicRegistrationEmailOutbox,
    PublicRegistrationThrottle,
    Tenant,
    User,
)
from app.models.organization import RoleDataScope
from app.services.email import send_public_registration_code

logger = logging.getLogger(__name__)
_FORBIDDEN_ROLE_SCOPES = {"admin", "manage", "delete", "secret", "*"}
_DELIVERY_MAX_ATTEMPTS = 5
_DELIVERY_LEASE_SECONDS = 90


class RegistrationPolicyChanged(ValueError):
    """应用管理员更改策略或协议后，旧登录页需要刷新。"""


def _hmac(secret: str, value: str) -> str:
    """注册邮箱/验证码/限流键都只以服务端密钥 HMAC 的形式持久化。"""
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _registration_secret(settings: Settings) -> str:
    """注册功能启用时由配置校验强制独立密钥；关闭时保留旧测试/维护路径兼容。"""
    return settings.public_registration_secret or settings.jwt_secret


def registration_email_hash(settings: Settings, application_id: UUID, email: str) -> str:
    return _hmac(_registration_secret(settings), f"iam-registration-email:{application_id}:{email}")


def _derived_code(settings: Settings, challenge_id: UUID) -> str:
    """从服务器密钥与挑战 ID 派生验证码，让重试发件箱无需保存 OTP 明文。"""
    digest = hmac.new(_registration_secret(settings).encode(), b"iam-registration-otp:" + challenge_id.bytes,
                      hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def _code_digest(settings: Settings, challenge_id: UUID, code: str) -> str:
    return _hmac(_registration_secret(settings), f"iam-registration-code:{challenge_id}:{code}")


def registration_role_fingerprint(db: Session, role: Role, *, lock_permissions: bool = False) -> str:
    """摘要角色的有效授权内容，防止 OTP 挑战套用申请后变更的权限或数据范围。"""
    grants_statement = (
        select(Permission.id, Permission.code, Permission.resource_type, Permission.scope,
               Permission.status, RolePermission.resource_id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
        .order_by(Permission.id, RolePermission.resource_id, RolePermission.id)
    )
    if lock_permissions:
        # 权限目录停用也会改变角色效果；锁目录行使其与验证事务串行化。
        grants_statement = grants_statement.with_for_update(of=Permission)
    grants = db.execute(grants_statement).all()
    scopes = db.execute(
        select(RoleDataScope.permission_id, RoleDataScope.scope_type, RoleDataScope.organization_ids)
        .where(RoleDataScope.role_id == role.id)
        .order_by(RoleDataScope.permission_id)
    ).all()
    policy = {
        "role_id": str(role.id),
        "tenant_id": str(role.tenant_id),
        "application_id": str(role.application_id) if role.application_id else None,
        "status": role.status,
        "grants": [
            [
                str(row.id), row.code, row.resource_type, row.scope, row.status,
                str(row.resource_id) if row.resource_id is not None else None,
            ]
            for row in grants
        ],
        "data_scopes": [
            [str(row.permission_id), row.scope_type, sorted(str(value) for value in (row.organization_ids or []))]
            for row in scopes
        ],
    }
    canonical = json.dumps(policy, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def eligible_registration_role(db: Session, application: Application, role_id: UUID | None,
                               *, lock: bool = False) -> Role | None:
    """只允许当前应用的活动普通角色，禁止误把 IAM 平台管理角色设为默认角色。"""
    if not role_id:
        return None
    statement = select(Role).where(
        Role.id == role_id,
        Role.tenant_id == application.tenant_id,
        Role.application_id == application.id,
        Role.status == "active",
    )
    if lock:
        # 验证 OTP 时锁住默认角色，避免并发停用后仍新增绑定。
        statement = statement.with_for_update()
    role = db.scalar(statement)
    if role is None:
        return None
    grants = db.execute(
        select(Permission.code, Permission.scope)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id, Permission.status == "active")
    ).all()
    for code, scope in grants:
        if code.startswith("iam.") or scope.casefold() in _FORBIDDEN_ROLE_SCOPES:
            return None
    # 自助注册角色不能顺手拿到整租户/组织数据范围。只给“普通角色”命名并不足够，
    # 还要确认它的数据策略不会让新用户读取其他成员的数据；无数据范围策略的权限
    # 仍由业务服务自己的资源归属检查保护，不能把 IAM membership 当作 owner 过滤。
    has_broad_data_scope = db.scalar(select(RoleDataScope.id).where(
        RoleDataScope.role_id == role.id,
        RoleDataScope.scope_type != "self",
    ).limit(1))
    if has_broad_data_scope:
        return None
    return role


def application_registration_details(
    db: Session,
    application: Application,
    *,
    settings: Settings | None = None,
) -> dict | None:
    """返回允许展示/接受注册的最小字段；主题草稿不参与匿名注册。"""
    settings = settings or get_settings()
    if (not settings.allow_public_registration or not settings.smtp_host or not settings.smtp_from
            or application.registration_policy != "open"
            or not application.registration_terms_version or not application.registration_privacy_version
            or not db.scalar(select(Tenant.id).where(
                Tenant.id == application.tenant_id, Tenant.status == "active", Tenant.kind == "consumer",
            ))
            or eligible_registration_role(db, application, application.registration_role_id) is None):
        return None
    theme = db.scalar(select(ApplicationTheme).where(
        ApplicationTheme.application_id == application.id,
        ApplicationTheme.status == "published",
    ).order_by(ApplicationTheme.version.desc()).limit(1))
    config = theme.config if theme and isinstance(theme.config, dict) else {}
    terms_url, privacy_url = config.get("terms_url"), config.get("privacy_url")
    if not config.get("show_register") or not terms_url or not privacy_url:
        return None
    return {
        "available": True,
        "resend_cooldown_seconds": settings.public_registration_cooldown_seconds,
        "terms_url": terms_url,
        "privacy_url": privacy_url,
        "terms_version": application.registration_terms_version,
        "privacy_version": application.registration_privacy_version,
    }


def request_registration_code(
    db: Session,
    *,
    application: Application,
    email: str,
    display_name: str,
    terms_version: str,
    privacy_version: str,
    terms_url: str,
    privacy_url: str,
    client_ip: str,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> bool:
    """登记/轮换待验证申请与发件箱；返回值只表示是否排入邮件队列。"""
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    # 先核对用户刚才查看的法律文档再碰节流桶，以免陈旧登录页消耗新政策的配额。
    registration_details = application_registration_details(db, application, settings=settings)
    if (terms_version != application.registration_terms_version
            or privacy_version != application.registration_privacy_version
            or registration_details is None
            or terms_url != registration_details["terms_url"]
            or privacy_url != registration_details["privacy_url"]):
        raise RegistrationPolicyChanged("当前应用暂未开放注册或注册协议已更新")
    role = eligible_registration_role(db, application, application.registration_role_id, lock=True)
    if role is None:
        raise RegistrationPolicyChanged("当前应用的默认注册角色不可用")
    # OTP 绑定的不只是角色 ID，也包括权限目录状态、资源级授权和数据范围。
    role_fingerprint = registration_role_fingerprint(db, role, lock_permissions=True)

    # PostgreSQL UPSERT 将节流判定与更新时间放在单条语句里，避免并发请求绕过冷却时间。
    throttle_keys = (
        _hmac(_registration_secret(settings), f"iam-registration-throttle-email:{application.id}:{email}"),
        _hmac(_registration_secret(settings), f"iam-registration-throttle-ip:{client_ip}"),
    )
    throttle_table = PublicRegistrationThrottle.__table__
    allowed = True
    for bucket_hash in throttle_keys:
        statement = pg_insert(PublicRegistrationThrottle).values(
            bucket_hash=bucket_hash,
            last_requested_at=now,
            expires_at=now + timedelta(days=1),
        ).on_conflict_do_update(
            index_elements=["bucket_hash"],
            set_={"last_requested_at": now, "expires_at": now + timedelta(days=1)},
            where=throttle_table.c.last_requested_at
            <= now - timedelta(seconds=settings.public_registration_cooldown_seconds),
        ).returning(throttle_table.c.bucket_hash)
        if db.scalar(statement) is None:
            allowed = False

    # 同邮箱已有 IAM 账号时也可加入新的 ToC 应用，但必须在兑换验证码时再证明当前密码。
    existing_user = db.scalar(select(User).where(func.lower(User.email) == email).with_for_update())
    if not allowed or (existing_user and existing_user.status != "active"):
        db.commit()
        return False

    email_hash = registration_email_hash(settings, application.id, email)
    challenge = db.scalar(select(PublicRegistrationChallenge).where(
        PublicRegistrationChallenge.application_id == application.id,
        PublicRegistrationChallenge.email_hash == email_hash,
    ).with_for_update())
    if challenge and challenge.expires_at > now and challenge.consumed_at is None:
        challenge_id = challenge.id
    else:
        if challenge:
            db.delete(challenge)
            db.flush()
        challenge = PublicRegistrationChallenge(
            application_id=application.id,
            email_hash=email_hash,
            email=email,
            display_name=existing_user.display_name if existing_user else display_name,
            existing_user_id=existing_user.id if existing_user else None,
            registration_role_id=role.id,
            registration_role_fingerprint=role_fingerprint,
            verification_code_hash="pending",
            terms_version=terms_version,
            privacy_version=privacy_version,
            terms_url=terms_url,
            privacy_url=privacy_url,
            expires_at=now + timedelta(minutes=settings.public_registration_code_minutes),
        )
        db.add(challenge)
        db.flush()
        challenge_id = challenge.id

    challenge.email = email
    challenge.display_name = existing_user.display_name if existing_user else display_name
    challenge.existing_user_id = existing_user.id if existing_user else None
    # 重发申请时记录当前默认角色，重发验证码后才接受这版策略。
    challenge.registration_role_id = role.id
    challenge.registration_role_fingerprint = role_fingerprint
    challenge.terms_version = terms_version
    challenge.privacy_version = privacy_version
    challenge.terms_url = terms_url
    challenge.privacy_url = privacy_url
    challenge.verification_code_hash = _code_digest(settings, challenge_id, _derived_code(settings, challenge_id))
    challenge.failed_attempts = 0
    challenge.expires_at = now + timedelta(minutes=settings.public_registration_code_minutes)
    challenge.consumed_at = None
    # 唯一发件箱记录被重置为可发送状态；即使 API worker 中途退出，后台循环也会重试。
    outbox = db.scalar(select(PublicRegistrationEmailOutbox).where(
        PublicRegistrationEmailOutbox.challenge_id == challenge_id,
    ).with_for_update())
    if outbox is None:
        outbox = PublicRegistrationEmailOutbox(challenge_id=challenge_id)
        db.add(outbox)
    else:
        outbox.status = "pending"
        outbox.attempts = 0
        outbox.retry_after = now
        outbox.locked_until = None
    db.commit()
    return True


def deliver_registration_emails(*, batch_size: int = 5) -> int:
    """事务发件箱按 at-least-once 语义重试；同一挑战重试始终使用同一个 OTP。"""
    settings = get_settings()
    if (not settings.allow_public_registration or not settings.smtp_host or not settings.smtp_from
            or len(settings.jwt_secret) < 32):
        return 0
    now = datetime.now(timezone.utc)
    jobs: list[tuple[UUID, UUID, str, str]] = []
    with Session(get_engine()) as db:
        rows = db.scalars(select(PublicRegistrationEmailOutbox).join(
            PublicRegistrationChallenge,
            PublicRegistrationChallenge.id == PublicRegistrationEmailOutbox.challenge_id,
        ).where(
            PublicRegistrationChallenge.expires_at > now,
            PublicRegistrationChallenge.consumed_at.is_(None),
            PublicRegistrationEmailOutbox.attempts < _DELIVERY_MAX_ATTEMPTS,
            ((PublicRegistrationEmailOutbox.status == "pending")
             & (PublicRegistrationEmailOutbox.retry_after <= now))
            | ((PublicRegistrationEmailOutbox.status == "sending")
               & (PublicRegistrationEmailOutbox.locked_until <= now)),
        ).order_by(PublicRegistrationEmailOutbox.created_at).limit(batch_size).with_for_update(
            skip_locked=True,
        )).all()
        for row in rows:
            row.status = "sending"
            row.attempts += 1
            row.locked_until = now + timedelta(seconds=_DELIVERY_LEASE_SECONDS)
            challenge = db.get(PublicRegistrationChallenge, row.challenge_id)
            application = db.get(Application, challenge.application_id) if challenge else None
            registration_details = (
                application_registration_details(db, application, settings=settings)
                if challenge and application else None
            )
            if (challenge and application and registration_details is not None
                    and challenge.terms_version == application.registration_terms_version
                    and challenge.privacy_version == application.registration_privacy_version
                    and challenge.terms_url == registration_details["terms_url"]
                    and challenge.privacy_url == registration_details["privacy_url"]):
                jobs.append((row.id, challenge.id, challenge.email, application.name))
            else:
                # 总开关/租户/角色/主题策略发生变化时，不再投递旧申请的验证码。
                row.status = "failed"
                row.locked_until = None
        db.commit()

    delivered = 0
    for outbox_id, challenge_id, email, application_name in jobs:
        try:
            send_public_registration_code(email, _derived_code(settings, challenge_id), application_name,
                                          settings.public_registration_code_minutes)
            success = True
            error_type = None
        except Exception as exc:
            success = False
            error_type = type(exc).__name__
            # SMTP 客户端错误可能包含收件地址；日志仅保留异常类型，不落邮箱或验证码。
            logger.error("ToC 注册验证码投递失败，错误类型：%s", error_type)
        completed_at = datetime.now(timezone.utc)
        with Session(get_engine()) as db:
            row = db.scalar(select(PublicRegistrationEmailOutbox).where(
                PublicRegistrationEmailOutbox.id == outbox_id,
            ).with_for_update())
            if row is None:
                continue
            if success:
                row.status = "sent"
                row.locked_until = None
                delivered += 1
            elif row.attempts >= _DELIVERY_MAX_ATTEMPTS:
                row.status = "failed"
                row.locked_until = None
            else:
                row.status = "pending"
                row.retry_after = completed_at + timedelta(seconds=min(300, 15 * (2 ** (row.attempts - 1))))
                row.locked_until = None
            db.commit()
    return delivered


def verify_registration_code(db: Session, challenge: PublicRegistrationChallenge, code: str,
                             *, now: datetime | None = None,
                             settings: Settings | None = None) -> bool:
    """常量时间比较验证码摘要；错误次数达到上限后立即消费申请。"""
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    candidate = _code_digest(settings, challenge.id, code)
    if not hmac.compare_digest(candidate, challenge.verification_code_hash):
        challenge.failed_attempts += 1
        if challenge.failed_attempts >= settings.public_registration_max_attempts:
            challenge.consumed_at = now
        db.commit()
        return False
    return True
