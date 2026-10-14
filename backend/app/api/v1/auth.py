"""账号密码认证与浏览器会话接口，为管理台和后续 OIDC 授权流程提供用户会话。"""

import hashlib
import hmac
import logging
import secrets
from math import ceil
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (bearer_scheme, create_access_token, current_user, dummy_password_hash,
                                hash_password, revoke_access_token, verify_password)
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import (AuditEvent, PasswordResetThrottle, PasswordResetToken,
                                 PublicRegistrationChallenge, PublicRegistrationConsent,
                                 RefreshSession, Tenant, TenantMembership, User)
from app.models.authorization import Role, RoleBinding
from app.models.identity import UserInvitation
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.schemas.auth import (AcceptInvitationRequest, AuthResponse, InvitationTokenRequest,
                              LoginRequest, PasswordResetComplete, PasswordResetRequest,
                              RegisterRequest, RegisterVerifyRequest, UserResponse)
from app.services.email import send_password_reset_email
from app.services.login_throttle import (begin_login_attempt, clear_login_identifier_failures,
                                         client_ip_for_request, record_login_failure)
from app.services.public_registration import (
    RegistrationPolicyChanged,
    application_registration_details,
    eligible_registration_role,
    registration_email_hash,
    registration_role_fingerprint,
    request_registration_code,
    verify_registration_code,
)

router = APIRouter(prefix="/auth", tags=["认证"])
REFRESH_COOKIE = "iam_refresh_token"
logger = logging.getLogger(__name__)
PASSWORD_RESET_MESSAGE = "如果邮箱已登记且邮件服务可用，你将收到密码重置链接。"
PUBLIC_REGISTRATION_MESSAGE = "如果该邮箱可用于此应用注册，系统会向该邮箱发送验证码。"


def ensure_signing_key() -> None:
    """在写入用户或会话之前验证签名密钥，避免密钥缺失导致半成功注册。"""
    if len(get_settings().jwt_secret) < 32:
        raise HTTPException(503, "认证服务密钥未配置（至少 32 个字符）")


def record_event(db: Session, action: str, target_type: str, target_id: str | None, actor: User | None,
                 request: Request, outcome: str = "success", *, tenant_id=None, details: dict | None = None) -> None:
    """统一审计写入；请求体不会进入审计，避免口令或令牌意外落盘。"""
    db.add(AuditEvent(actor_user_id=actor.id if actor else None, tenant_id=tenant_id, action=action,
                      target_type=target_type, target_id=target_id,
                      source_ip=client_ip_for_request(request, get_settings()), outcome=outcome,
                      details=details or {}))


def new_refresh_token(
    db: Session,
    user: User,
    expires_at: datetime | None = None,
    *,
    existing_session: RefreshSession | None = None,
) -> tuple[str, datetime, UUID]:
    """生成 opaque refresh token 并返回稳定 session ID；数据库只保留 token 摘要。"""
    raw_token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    absolute_expiry = expires_at or now + timedelta(days=get_settings().refresh_token_days)
    if existing_session is None:
        existing_session = RefreshSession(
            user_id=user.id,
            token_hash=token_hash,
            auth_version=user.auth_version or 1,
            expires_at=absolute_expiry,
        )
        db.add(existing_session)
        # SQLAlchemy 在 INSERT 时分配 UUID 主键；先 flush 才能把同一 ID 写进 access JWT。
        db.flush()
    else:
        # 原位轮换摘要，保留 session ID；旧 refresh token 因摘要已替换而无法再次兑换。
        existing_session.token_hash = token_hash
        existing_session.auth_version = user.auth_version or 1
        existing_session.expires_at = absolute_expiry
        existing_session.revoked_at = None
    return raw_token, absolute_expiry, existing_session.id


def set_refresh_cookie(response: Response, raw_token: str, expires_at: datetime) -> None:
    """Cookie 限定版本化 API 路径供后续 OIDC 授权共用，且禁止脚本读取；非开发环境强制 Secure。"""
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        max_age=max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds())),
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        # OIDC 授权端点也要能读取浏览器会话，因此限定在版本化 API 下；
        # 其他 API 仍只接受 Bearer，不会因 Cookie 自动登录或授权。
        path=settings.api_v1_prefix,
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=REFRESH_COOKIE,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        path=settings.api_v1_prefix,
    )


@router.post("/register", status_code=202)
def register(body: RegisterRequest, request: Request, response: Response,
             db: Session = Depends(get_db_session)) -> dict[str, str]:
    """只登记 ToC 应用待验证申请；既有账号也必须在验证时证明当前密码。"""
    settings = get_settings()
    ensure_signing_key()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if not settings.allow_public_registration or not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(403, "当前应用暂不开放自助注册")
    if not body.accepted_terms or not body.accepted_privacy:
        raise HTTPException(422, "请先阅读并接受用户协议和隐私政策")
    application = db.scalar(select(Application).where(
        Application.client_id == body.client_id,
        Application.status == "active",
    ).with_for_update())
    if not application or application_registration_details(db, application, settings=settings) is None:
        raise HTTPException(403, "当前应用暂不开放自助注册")
    if (body.terms_version != application.registration_terms_version
            or body.privacy_version != application.registration_privacy_version):
        raise HTTPException(409, "注册协议已更新，请刷新页面后重试")
    email = str(body.email).casefold()
    try:
        request_registration_code(
            db,
            application=application,
            email=email,
            display_name=body.display_name.strip(),
            terms_version=body.terms_version,
            privacy_version=body.privacy_version,
            terms_url=body.terms_url,
            privacy_url=body.privacy_url,
            client_ip=client_ip_for_request(request, settings),
            settings=settings,
        )
    except RegistrationPolicyChanged as exc:
        raise HTTPException(409, str(exc)) from None
    except IntegrityError:
        db.rollback()
        # 邮箱/申请并发冲突不回显是否已有账号，避免匿名账号枚举。
        return {"message": PUBLIC_REGISTRATION_MESSAGE}
    return {"message": PUBLIC_REGISTRATION_MESSAGE}


@router.post("/register/verify", response_model=AuthResponse, status_code=201)
def verify_registration(body: RegisterVerifyRequest, request: Request, response: Response,
                        db: Session = Depends(get_db_session)) -> AuthResponse:
    """验证码通过后在一个事务中创建全局身份、应用租户成员、普通角色、同意记录和会话。"""
    settings = get_settings()
    ensure_signing_key()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if not settings.allow_public_registration or not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(400, "验证码无效或已过期")
    application = db.scalar(select(Application).where(
        Application.client_id == body.client_id,
        Application.status == "active",
    ).with_for_update())
    if not application:
        raise HTTPException(400, "验证码无效或已过期")
    role = eligible_registration_role(db, application, application.registration_role_id, lock=True)
    if (role is None or application_registration_details(db, application, settings=settings) is None):
        raise HTTPException(400, "验证码无效或已过期")
    email = str(body.email).casefold()
    email_hash = registration_email_hash(settings, application.id, email)
    now = datetime.now(timezone.utc)
    challenge = db.scalar(select(PublicRegistrationChallenge).where(
        PublicRegistrationChallenge.application_id == application.id,
        PublicRegistrationChallenge.email_hash == email_hash,
        PublicRegistrationChallenge.expires_at > now,
        PublicRegistrationChallenge.consumed_at.is_(None),
    ).with_for_update())
    if challenge is None:
        raise HTTPException(400, "验证码无效或已过期")
    current_role_fingerprint = registration_role_fingerprint(db, role, lock_permissions=True)
    if (challenge.registration_role_id != role.id
            or challenge.registration_role_fingerprint != current_role_fingerprint):
        # 注册默认角色变更等同于授权策略变更；消费旧 challenge 并要求用户重新申请验证码。
        challenge.consumed_at = now
        db.commit()
        raise HTTPException(400, "验证码无效或已过期")
    if not verify_registration_code(db, challenge, body.code, now=now, settings=settings):
        raise HTTPException(400, "验证码无效或已过期")

    # 条款可能在用户收验证码期间更新；旧版本申请不能用新策略创建成员。
    registration_details = application_registration_details(db, application, settings=settings)
    if (registration_details is None
            or challenge.terms_version != application.registration_terms_version
            or challenge.privacy_version != application.registration_privacy_version
            or challenge.terms_url != registration_details["terms_url"]
            or challenge.privacy_url != registration_details["privacy_url"]):
        challenge.consumed_at = now
        db.commit()
        raise HTTPException(400, "验证码无效或已过期")
    # 先证明邮箱持有权，再处理凭据。既有身份须证明当前密码；新身份此时才设置密码。
    # 申请阶段不保存密码摘要，也不会因新账号密码长度校验产生邮箱枚举响应差异。
    user = db.scalar(select(User).where(func.lower(User.email) == email).with_for_update())
    if user:
        if (user.status != "active"
                or (challenge.existing_user_id is not None and user.id != challenge.existing_user_id)
                or not verify_password(body.password, user.password_hash)):
            challenge.failed_attempts += 1
            if challenge.failed_attempts >= settings.public_registration_max_attempts:
                challenge.consumed_at = now
            db.commit()
            raise HTTPException(400, "验证码无效或已过期")
        user.email_verified_at = user.email_verified_at or now
    else:
        if len(body.password) < 12:
            raise HTTPException(422, "新账号密码至少需要 12 个字符")
        user = User(email=email, password_hash=hash_password(body.password),
                    display_name=challenge.display_name, email_verified_at=now)
        db.add(user)
        db.flush()

    # 以租户行锁串行化同租户多个应用的首次加入，避免并发重复创建 membership。
    tenant = db.scalar(select(Tenant).where(
        Tenant.id == application.tenant_id, Tenant.status == "active",
    ).with_for_update())
    if tenant is None:
        challenge.consumed_at = now
        db.commit()
        raise HTTPException(400, "验证码无效或已过期")
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.tenant_id == tenant.id,
    ).with_for_update())
    if membership and membership.status != "active":
        challenge.consumed_at = now
        db.commit()
        raise HTTPException(400, "验证码无效或已过期")
    if membership is None:
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, status="active")
        db.add(membership)
        db.flush()
    if not db.scalar(select(RoleBinding.id).where(
        RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id,
    )):
        db.add(RoleBinding(membership_id=membership.id, role_id=role.id))

    consent = db.scalar(select(PublicRegistrationConsent).where(
        PublicRegistrationConsent.user_id == user.id,
        PublicRegistrationConsent.application_id == application.id,
        PublicRegistrationConsent.terms_version == challenge.terms_version,
        PublicRegistrationConsent.privacy_version == challenge.privacy_version,
    ).with_for_update())
    if consent is None:
        consent = PublicRegistrationConsent(
            user_id=user.id,
            application_id=application.id,
            terms_version=challenge.terms_version,
            privacy_version=challenge.privacy_version,
            terms_url=challenge.terms_url,
            privacy_url=challenge.privacy_url,
            source_ip=client_ip_for_request(request, settings),
            accepted_at=now,
        )
        db.add(consent)
    challenge.consumed_at = now
    refresh_token, refresh_expiry, session_id = new_refresh_token(db, user)
    record_event(db, "auth.register", "user", str(user.id), user, request,
                 tenant_id=application.tenant_id,
                 details={"application_id": str(application.id), "role_id": str(role.id),
                          "terms_version": challenge.terms_version,
                          "privacy_version": challenge.privacy_version})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "验证码无效或已过期") from None
    db.refresh(user)
    set_refresh_cookie(response, refresh_token, refresh_expiry)
    return AuthResponse(access_token=create_access_token(user, session_id), expires_in=settings.access_token_minutes * 60, user=user)


@router.post("/invitations/inspect")
def inspect_invitation(body: InvitationTokenRequest, db: Session = Depends(get_db_session)) -> dict:
    """检查持有者的短期邀请链接，只回传接受邀请页必需的非敏感资料。"""
    digest = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    invite = db.scalar(select(UserInvitation).where(UserInvitation.token_hash == digest,
                                                     UserInvitation.accepted_at.is_(None),
                                                     UserInvitation.revoked_at.is_(None),
                                                     UserInvitation.expires_at > now))
    if not invite:
        raise HTTPException(404, "邀请链接无效、已使用或已过期")
    tenant = db.scalar(select(Tenant).where(Tenant.id == invite.tenant_id, Tenant.status == "active"))
    role = db.scalar(select(Role).where(Role.id == invite.role_id, Role.tenant_id == invite.tenant_id,
                                         Role.status == "active"))
    if not tenant or not role:
        raise HTTPException(404, "邀请链接无效、已使用或已过期")
    if role.application_id and not db.scalar(select(Application.id).where(
        Application.id == role.application_id, Application.tenant_id == tenant.id, Application.status == "active",
    )):
        raise HTTPException(404, "邀请链接无效、已使用或已过期")
    return {"email": invite.email, "display_name": invite.display_name,
            "tenant_name": tenant.name, "role_name": role.name, "expires_at": invite.expires_at}


@router.post("/invitations/accept", response_model=AuthResponse, status_code=201)
def accept_invitation(body: AcceptInvitationRequest, request: Request, response: Response,
                      db: Session = Depends(get_db_session)) -> AuthResponse:
    """用行锁消费一次性邀请；新邮箱设定口令，已存在账号须证明当前口令后加租户成员。"""
    ensure_signing_key()
    digest = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    invite = db.scalar(select(UserInvitation).where(UserInvitation.token_hash == digest).with_for_update())
    if (not invite or invite.accepted_at is not None or invite.revoked_at is not None
            or invite.expires_at <= now):
        raise HTTPException(404, "邀请链接无效、已使用或已过期")
    tenant = db.scalar(select(Tenant).where(Tenant.id == invite.tenant_id, Tenant.status == "active"))
    role = db.scalar(select(Role).where(Role.id == invite.role_id, Role.tenant_id == invite.tenant_id,
                                         Role.status == "active"))
    if not tenant or not role:
        raise HTTPException(409, "租户或邀请角色已停用")
    if role.application_id and not db.scalar(select(Application.id).where(
        Application.id == role.application_id, Application.tenant_id == tenant.id, Application.status == "active",
    )):
        raise HTTPException(409, "邀请角色所属应用已停用")

    # 邮箱持有者通过邀请链接确认邮箱。若账号已存在，仍要求当前口令，避免邀请链接劫持原身份。
    user = db.scalar(select(User).where(func.lower(User.email) == invite.email).with_for_update())
    if user:
        if user.status != "active" or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "账号凭据无效或账号已停用")
    else:
        if len(body.password) < 12:
            raise HTTPException(422, "新账号密码至少需要 12 个字符")
        user = User(email=invite.email, display_name=invite.display_name,
                    password_hash=hash_password(body.password), email_verified_at=now)
        db.add(user)
        db.flush()

    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user.id, TenantMembership.tenant_id == tenant.id,
    ).with_for_update())
    membership_was_active = membership is not None and membership.status == "active"
    if membership is None:
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, status="active")
        db.add(membership)
        db.flush()
    elif membership.status != "active":
        # 重新加入只授予本邀请角色，先清除停用前绑定，禁止悄悄恢复旧权限。
        db.execute(delete(RoleBinding).where(RoleBinding.membership_id == membership.id))
        membership.status = "active"

    binding = db.scalar(select(RoleBinding.id).where(RoleBinding.membership_id == membership.id,
                                                       RoleBinding.role_id == role.id))
    if binding and membership_was_active:
        raise HTTPException(409, "账号已经拥有该租户角色")
    if not binding:
        db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
    invite.accepted_at = now
    refresh_token, refresh_expiry, session_id = new_refresh_token(db, user)
    record_event(db, "auth.invitation.accept", "user", str(user.id), user, request,
                 tenant_id=tenant.id, details={"invitation_id": str(invite.id), "role_id": str(role.id)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "邀请已被使用或账号记录发生冲突") from None
    db.refresh(user)
    set_refresh_cookie(response, refresh_token, refresh_expiry)
    return AuthResponse(access_token=create_access_token(user, session_id),
                        expires_in=get_settings().access_token_minutes * 60, user=user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db_session)) -> AuthResponse:
    """登录失败统一返回，并先串行检查短期节流桶以降低口令猜测与 Argon2 拒绝服务。"""
    settings = get_settings()
    ensure_signing_key()
    email = str(body.email).casefold()
    ticket = begin_login_attempt(db, email, client_ip_for_request(request, settings), settings)
    if ticket.blocked_until:
        retry_after = max(1, ceil((ticket.blocked_until - datetime.now(timezone.utc)).total_seconds()))
        db.commit()
        raise HTTPException(429, "登录尝试过于频繁，请稍后再试。", headers={"Retry-After": str(retry_after)})

    user = db.scalar(select(User).where(User.email == email).with_for_update())
    valid = verify_password(body.password, user.password_hash) if user else verify_password(body.password, dummy_password_hash())
    if not user or not valid or user.status != "active":
        record_login_failure(db, ticket, settings)
        record_event(db, "auth.login", "user", str(user.id) if user else None, user, request, "denied")
        db.commit()
        raise HTTPException(401, "账号或密码错误")
    clear_login_identifier_failures(db, ticket, settings)
    refresh_token, refresh_expiry, session_id = new_refresh_token(db, user)
    record_event(db, "auth.login", "user", str(user.id), user, request)
    db.commit()
    set_refresh_cookie(response, refresh_token, refresh_expiry)
    return AuthResponse(access_token=create_access_token(user, session_id), expires_in=settings.access_token_minutes * 60, user=user)


@router.post("/refresh", response_model=AuthResponse)
def refresh_session(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: Session = Depends(get_db_session),
) -> AuthResponse:
    """一次性轮换 refresh token；行锁避免并发重放，同一数据库事务撤销旧令牌并保存新令牌。"""
    ensure_signing_key()
    if not refresh_token:
        raise HTTPException(401, "刷新会话不存在或已过期")
    digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest).with_for_update())
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at is not None or session.expires_at <= now:
        raise HTTPException(401, "刷新会话不存在或已过期")
    user = db.scalar(select(User).where(User.id == session.user_id, User.status == "active"))
    if user is None or session.auth_version != user.auth_version:
        session.revoked_at = now
        db.commit()
        raise HTTPException(401, "账号不存在或已停用")

    # 刷新令牌仅使用一次；若并发重放，第二个请求在取得行锁后看到 revoked_at 并被拒绝。
    session.revoked_at = now
    rotated_token, session_expiry, session_id = new_refresh_token(
        db, user, session.expires_at, existing_session=session,
    )
    record_event(db, "auth.refresh", "user", str(user.id), user, request)
    db.commit()
    set_refresh_cookie(response, rotated_token, session_expiry)
    return AuthResponse(access_token=create_access_token(user, session_id), expires_in=get_settings().access_token_minutes * 60, user=user)


@router.post("/password-reset/request")
def request_password_reset(body: PasswordResetRequest, request: Request, response: Response,
                           db: Session = Depends(get_db_session)) -> dict[str, str]:
    """公开找回接口统一响应账号是否存在，并按 HMAC 邮箱键限制邮件触发频率。"""
    settings = get_settings()
    ensure_signing_key()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(503, "密码重置邮件服务暂不可用")

    now = datetime.now(timezone.utc)
    email = str(body.email).casefold()
    email_hash = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        f"iam-password-reset:{email}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    throttle_table = PasswordResetThrottle.__table__
    throttle_statement = pg_insert(PasswordResetThrottle).values(
        email_hash=email_hash,
        last_requested_at=now,
        expires_at=now + timedelta(days=1),
    ).on_conflict_do_update(
        index_elements=["email_hash"],
        set_={"last_requested_at": now, "expires_at": now + timedelta(days=1)},
        where=throttle_table.c.last_requested_at
        <= now - timedelta(seconds=settings.password_reset_cooldown_seconds),
    ).returning(throttle_table.c.email_hash)
    accepted = db.scalar(throttle_statement) is not None
    if not accepted:
        db.commit()
        return {"message": PASSWORD_RESET_MESSAGE}

    user = db.scalar(select(User).where(
        func.lower(User.email) == email, User.status == "active",
    ).with_for_update())
    raw_token = None
    reset = None
    if user and user.email:
        # 新链接使该账户尚未使用的旧链接失效，避免同时存在多个有效恢复凭证。
        db.execute(update(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None),
        ).values(consumed_at=now))
        raw_token = secrets.token_urlsafe(36)
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            expires_at=now + timedelta(minutes=settings.password_reset_token_minutes),
        )
        db.add(reset)
        db.flush()

    # 不在审计中放邮箱、邮件正文、一次性凭证或请求字段；未知账号使用相同事件形态。
    record_event(db, "auth.password_reset.request", "password_reset", None, None, request, "accepted")
    db.commit()
    if reset and user and raw_token:
        try:
            send_password_reset_email(user.email or "", raw_token)
        except Exception as exc:
            # SMTP 异常正文可能回显收件地址；日志和审计仅保留异常类型。
            record_event(db, "auth.password_reset.delivery_failed", "password_reset", None, None, request,
                         "failed", details={"error_type": type(exc).__name__})
            db.commit()
            logger.error("密码重置邮件投递失败，错误类型：%s", type(exc).__name__)
    return {"message": PASSWORD_RESET_MESSAGE}


@router.post("/password-reset/complete")
def complete_password_reset(body: PasswordResetComplete, request: Request, response: Response,
                            db: Session = Depends(get_db_session)) -> dict[str, str]:
    """一次性消费邮件令牌并原子修改密码、提高认证版本、撤销所有既有会话。"""
    ensure_signing_key()
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    reset = db.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == digest,
        PasswordResetToken.consumed_at.is_(None),
        PasswordResetToken.expires_at > now,
    ).with_for_update())
    if not reset:
        raise HTTPException(400, "密码重置链接无效、已使用或已过期")

    user = db.scalar(select(User).where(User.id == reset.user_id).with_for_update())
    if not user or user.status != "active":
        raise HTTPException(400, "密码重置链接无效、已使用或已过期")

    reset.consumed_at = now
    user.password_hash = hash_password(body.new_password)
    user.auth_version = (user.auth_version or 1) + 1
    # 成功兑换邮件链接证明调用者控制该邮箱，也使 OIDC email_verified 反映此事实。
    user.email_verified_at = user.email_verified_at or now
    db.execute(update(RefreshSession).where(
        RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None),
    ).values(revoked_at=now))
    db.execute(update(OAuthRefreshToken).where(
        OAuthRefreshToken.user_id == user.id, OAuthRefreshToken.revoked_at.is_(None),
    ).values(revoked_at=now))
    db.execute(update(OAuthAuthorizationCode).where(
        OAuthAuthorizationCode.user_id == user.id, OAuthAuthorizationCode.consumed_at.is_(None),
    ).values(consumed_at=now))
    db.execute(update(OAuthConsentRequest).where(
        OAuthConsentRequest.user_id == user.id, OAuthConsentRequest.consumed_at.is_(None),
    ).values(consumed_at=now))
    db.execute(update(PasswordResetToken).where(
        PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None),
    ).values(consumed_at=now))
    record_event(db, "auth.password_reset.complete", "user", str(user.id), user, request,
                 details={"iam_refresh_sessions_revoked": True})
    db.commit()
    clear_refresh_cookie(response)
    return {"message": "密码已重置，请使用新密码登录。"}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    user: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """同一事务撤销当前 refresh session 与 access JWT，再清除浏览器 Cookie。"""
    revoke_access_token(credentials.credentials, db)
    if refresh_token:
        digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == digest).with_for_update())
        if session and session.user_id == user.id and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
    record_event(db, "auth.logout", "user", str(user.id), user, request)
    db.commit()
    clear_refresh_cookie(response)
