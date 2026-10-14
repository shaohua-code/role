"""认证基础能力。访问令牌只短期签名，密码采用 Argon2 哈希。"""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any
from functools import lru_cache
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.identity import RefreshSession, RevokedAccessToken, Tenant, TenantMembership, User
from app.models.application import Application
from app.models.authorization import Role, RoleBinding
from app.models.oidc import OAuthRefreshToken
from app.core.oidc_keys import decode_oidc_jwt

password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    """只生成一次不存在账号的比较哈希，避免每次撞库都重复执行哈希生成。"""
    return password_hasher.hash("not-a-real-account-password")


def hash_password(password: str) -> str:
    """使用 Argon2id 存储单向口令哈希，禁止自行实现密码学算法。"""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """对比用户口令；登录接口对不存在的账号也执行一次哈希校验以减小时序差异。"""
    return password_hasher.verify(password, password_hash)


def create_access_token(user: User, session_id: UUID | None = None) -> str:
    settings = get_settings()
    if len(settings.jwt_secret) < 32:
        raise HTTPException(status_code=503, detail="认证服务密钥未配置")
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes),
         "iss": settings.app_name, "jti": uuid4().hex, "token_use": "management_access",
         "auth_version": getattr(user, "auth_version", 1) or 1}
    if session_id:
        # 将短期 access token 绑定到稳定的 refresh session ID，支持管理员即时远程退出。
        claims["sid"] = str(session_id)
    return jwt.encode(
        claims,
        settings.jwt_secret,
        algorithm="HS256",
    )


def _revocation_key(claims: dict[str, Any]) -> str:
    """数据库以摘要索引 JWT 的随机 jti；不保存 token 或可重建的原文。"""
    jti = claims.get("jti")
    if not isinstance(jti, str) or not jti or len(jti) > 128:
        raise ValueError("JWT is missing a valid jti")
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def access_token_is_revoked(claims: dict[str, Any], db: Session) -> bool:
    """所有 JWT 在线鉴权入口复用撤销查询；缺少 jti 的旧 token 一律拒绝。"""
    try:
        digest = _revocation_key(claims)
    except ValueError:
        return True
    return db.get(RevokedAccessToken, digest) is not None


def management_session_is_active(claims: dict[str, Any], db: Session) -> bool:
    """验证管理台 JWT 绑定的 refresh session；无 sid 的旧 token 允许自然过期。"""
    raw_session_id = claims.get("sid")
    if raw_session_id is None:
        return True
    try:
        session_id = UUID(str(raw_session_id))
        user_id = UUID(str(claims.get("sub", "")))
    except (TypeError, ValueError):
        return False
    session = db.get(RefreshSession, session_id)
    return bool(
        session
        and session.user_id == user_id
        and session.revoked_at is None
        and session.expires_at > datetime.now(timezone.utc)
    )


def oidc_session_is_active(claims: dict[str, Any], db: Session) -> bool:
    """按 OAuth refresh token family 立即失效该产品会话的在线 access token。"""
    raw_family_id = claims.get("sid")
    if raw_family_id is None:
        # 兼容升级前 token，以及未申请 offline_access 的短期 token。
        return True
    try:
        family_id = UUID(str(raw_family_id))
        user_id = UUID(str(claims.get("sub", "")))
    except (TypeError, ValueError):
        return False
    client_id = claims.get("client_id")
    if not isinstance(client_id, str) or not client_id:
        return False
    active_session = db.scalar(
        select(OAuthRefreshToken.id)
        .join(Application, Application.id == OAuthRefreshToken.application_id)
        .where(
            OAuthRefreshToken.family_id == family_id,
            OAuthRefreshToken.user_id == user_id,
            Application.client_id == client_id,
            OAuthRefreshToken.revoked_at.is_(None),
            OAuthRefreshToken.expires_at > datetime.now(timezone.utc),
        )
        .limit(1)
    )
    return active_session is not None


def revoke_access_token(raw_token: str, db: Session) -> bool:
    """校验本服务签名后按 jti 撤销；幂等写入并顺便回收已过期的短期记录。"""
    settings = get_settings()
    claims: dict[str, Any] | None = None
    token_use = ""
    if len(settings.jwt_secret) >= 32:
        try:
            claims = jwt.decode(raw_token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.app_name)
            if claims.get("token_use") == "management_access":
                token_use = "management_access"
        except jwt.PyJWTError:
            claims = None
    if claims is None:
        try:
            claims = decode_oidc_jwt(raw_token)
            if claims.get("token_use") == "access_token":
                token_use = "access_token"
        except (jwt.PyJWTError, RuntimeError):
            claims = None
    if claims is None or not token_use:
        return False
    try:
        digest = _revocation_key(claims)
        expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        return False

    # PostgreSQL conflict handling makes duplicate logout/revoke requests safe under concurrency.
    db.execute(pg_insert(RevokedAccessToken).values(
        jti_hash=digest, token_use=token_use, expires_at=expires_at,
    ).on_conflict_do_nothing(index_elements=["jti_hash"]))
    db.execute(delete(RevokedAccessToken).where(RevokedAccessToken.expires_at <= now))
    return True


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db_session),
) -> User:
    """每次请求重新检查用户状态，禁用账号的已签发令牌立即失效。"""
    settings = get_settings()
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或认证服务未配置")
    raw_token = credentials.credentials
    # Management-session HS256 tokens and external-client OIDC RS256 access tokens have
    # separate keys, claims, and authorization contexts; never relax either algorithm.
    try:
        if len(settings.jwt_secret) < 32:
            raise jwt.InvalidTokenError("management signing key is not configured")
        claims: dict[str, Any] = jwt.decode(raw_token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.app_name)
        if (claims.get("token_use") != "management_access"
                or access_token_is_revoked(claims, db)
                or not management_session_is_active(claims, db)):
            raise jwt.InvalidTokenError("management access token is revoked or missing jti")
        user_id = UUID(claims["sub"])
        token_auth_version = claims.get("auth_version", 1)
        if isinstance(token_auth_version, bool) or not isinstance(token_auth_version, int):
            raise jwt.InvalidTokenError("management token auth_version is invalid")
        user = db.scalar(select(User).where(User.id == user_id, User.status == "active"))
        if user is None:
            raise HTTPException(status_code=401, detail="账号不存在或已停用")
        if token_auth_version != user.auth_version:
            raise jwt.InvalidTokenError("management token predates a credential change")
        return user
    except (jwt.PyJWTError, KeyError, ValueError):
        pass

    try:
        claims = decode_oidc_jwt(raw_token)
        if (claims.get("token_use") != "access_token"
                or access_token_is_revoked(claims, db)
                or not oidc_session_is_active(claims, db)):
            raise ValueError("wrong token use")
        token_auth_version = claims.get("auth_version", 1)
        if isinstance(token_auth_version, bool) or not isinstance(token_auth_version, int):
            raise ValueError("invalid auth version")
        client_id = claims.get("client_id")
        if not isinstance(client_id, str) or claims.get("aud") != client_id:
            raise ValueError("wrong audience")
        user_id = UUID(claims["sub"])
        tenant_id = UUID(claims["tenant_id"])
    except (jwt.PyJWTError, RuntimeError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="登录凭证无效或已过期") from None

    app = db.scalar(select(Application).where(Application.client_id == client_id, Application.status == "active"))
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "active"))
    user = db.scalar(select(User).where(User.id == user_id, User.status == "active"))
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user_id, TenantMembership.tenant_id == tenant_id,
        TenantMembership.status == "active",
    ))
    token_membership_version = claims.get("membership_version", 1)
    role = db.scalar(select(RoleBinding.id).join(Role, Role.id == RoleBinding.role_id).where(
        RoleBinding.membership_id == membership.id if membership else False,
        Role.tenant_id == tenant_id, Role.status == "active",
        (Role.application_id.is_(None) | (Role.application_id == app.id)) if app else False,
    ).limit(1))
    if (not (app and tenant and user and membership and role)
            or token_auth_version != user.auth_version
            or isinstance(token_membership_version, bool)
            or not isinstance(token_membership_version, int)
            or token_membership_version != membership.auth_version):
        raise HTTPException(status_code=401, detail="账号、租户、应用或角色授权已失效")
    # Keep verified OIDC context on this request's ORM identity. Downstream authorization
    # pins checks to these claims rather than trusting tenant/application values from callers.
    user._auth_protocol = "oidc"
    user._oidc_tenant_id = tenant_id
    user._oidc_application_id = app.id
    return user


def is_platform_admin_user(user: User) -> bool:
    """判断引导管理员身份；OIDC 业务用户不能仅凭同邮箱取得平台级权限。"""
    configured_email = get_settings().bootstrap_admin_email
    return not (
        getattr(user, "_auth_protocol", None) == "oidc"
        or not configured_email
        or not user.email
        or user.email.casefold() != configured_email.casefold()
    )


def platform_admin(user: User = Depends(current_user)) -> User:
    """管理权限由服务端配置的引导账号确定，客户端无法通过提交角色提升权限。"""
    if not is_platform_admin_user(user):
        raise HTTPException(status_code=403, detail="需要平台管理员权限")
    return user
