"""OIDC Token、UserInfo、Introspection、JWKS 与 Revocation 端点。"""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus
from uuid import UUID, uuid4
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.oidc_keys import decode_oidc_jwt, public_jwks, sign_jwt
from app.core.security import (access_token_is_revoked, dummy_password_hash, oidc_session_is_active,
                               revoke_access_token, verify_password)
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import TenantMembership, User
from app.models.oidc import OAuthAuthorizationCode, OAuthRefreshToken
from .common import _active_client, _app_membership, _error, _hash, _issuer, _oauth_audit, _parse_form
from .constants import ACCESS_TOKEN_TTL, VERIFIER_RE
router = APIRouter()


def _b64url(raw: bytes) -> str:
    """标准 URL-safe base64（去填充），用于 at_hash 等摘要编码。"""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _access_token(user: User, app: Application, scope: str, membership_version: int = 1,
                  family_id: UUID | None = None) -> tuple[str, int]:
    """签发 RS256 access token；claims 携带身份/成员版本号供资源服务器离线验权。"""
    now = datetime.now(timezone.utc)
    claims = {
        "iss": _issuer(), "sub": str(user.id), "aud": app.client_id,
        "tenant_id": str(app.tenant_id),
        "iat": int(now.timestamp()), "exp": int((now + ACCESS_TOKEN_TTL).timestamp()),
        "jti": str(uuid4()), "client_id": app.client_id, "scope": scope, "token_use": "access_token",
        "auth_version": getattr(user, "auth_version", 1) or 1,
        "membership_version": membership_version,
    }
    # 申请 offline_access 的 access token 与 refresh family 共用 sid，整族撤销可立即生效。
    if family_id:
        claims["sid"] = str(family_id)
    token = sign_jwt(claims, token_type="at+jwt")
    return token, int(ACCESS_TOKEN_TTL.total_seconds())


def _id_token(user: User, app: Application, scopes: set[str], nonce: str | None, access_token: str) -> str:
    """按 scope 裁剪身份断言；nonce 与 at_hash 绑定授权请求和 access token。"""
    now = datetime.now(timezone.utc)
    claims: dict = {"iss": _issuer(), "sub": str(user.id), "aud": app.client_id,
                    # Tenant context is part of the signed identity assertion so
                    # OIDC relying parties can bind the user to the right tenant.
                    "tenant_id": str(app.tenant_id),
                    "iat": int(now.timestamp()), "exp": int((now + ACCESS_TOKEN_TTL).timestamp())}
    if nonce:
        claims["nonce"] = nonce
    if access_token:
        # OIDC Core 规定 at_hash 为访问令牌 SHA-256 摘要左半段的 base64url。
        claims["at_hash"] = _b64url(hashlib.sha256(access_token.encode("ascii")).digest()[:16])
    if "profile" in scopes:
        claims["name"] = user.display_name
    if "email" in scopes and user.email:
        claims["email"] = user.email
        claims["email_verified"] = user.email_verified_at is not None
    return sign_jwt(claims)


def _token_payload(db: Session, user: User, app: Application, scopes: set[str], nonce: str | None,
                   membership: TenantMembership,
                   *, family_id: UUID | None = None) -> tuple[dict, OAuthRefreshToken | None]:
    """组装 token 响应；仅当请求含 offline_access 时创建 refresh token（opaque 存摘要）。"""
    scope = " ".join(sorted(scopes))
    membership_version = membership.auth_version or 1
    session_family_id = (family_id or uuid4()) if "offline_access" in scopes else None
    access, expires_in = _access_token(user, app, scope, membership_version, session_family_id)
    result = {"access_token": access, "token_type": "Bearer", "expires_in": expires_in,
              "scope": scope, "id_token": _id_token(user, app, scopes, nonce, access)}
    refresh_row = None
    if "offline_access" in scopes:
        raw_refresh = secrets.token_urlsafe(48)
        refresh_row = OAuthRefreshToken(
            family_id=session_family_id, application_id=app.id, user_id=user.id,
            auth_version=getattr(user, "auth_version", 1) or 1,
            membership_version=membership_version,
            token_hash=_hash(raw_refresh), scope=scope,
            expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_days),
        )
        db.add(refresh_row)
        result["refresh_token"] = raw_refresh
    return result, refresh_row


def _token_response(payload: dict) -> JSONResponse:
    """token 响应统一禁止缓存，防止令牌落入共享代理。"""
    return JSONResponse(payload, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})




def _authenticate_client(db: Session, authorization: str | None) -> Application | JSONResponse:
    """仅接受 client_secret_basic；Basic 凭据按 RFC form-url-decode 后验证 Argon2 哈希。"""
    if not authorization or not authorization.startswith("Basic "):
        return _error("invalid_client", "需要 HTTP Basic 客户端认证", 401, challenge=True)
    try:
        decoded = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
        client_id_encoded, secret_encoded = decoded.split(":", 1)
        client_id, secret = unquote_plus(client_id_encoded), unquote_plus(secret_encoded)
    except (ValueError, UnicodeDecodeError):
        return _error("invalid_client", "客户端认证信息无效", 401, challenge=True)
    app = _active_client(db, client_id)
    try:
        valid = verify_password(secret, app.client_secret_hash if app else dummy_password_hash())
    except (ValueError, TypeError):
        valid = False
    if not app or not app.client_secret_hash or not valid:
        return _error("invalid_client", "客户端认证信息无效", 401, challenge=True)
    return app


@router.post("/token")
async def token(request: Request, authorization: str | None = Header(default=None),
                db: Session = Depends(get_db_session)) -> Response:
    """兑换授权码或轮换刷新令牌；重放旧刷新值会撤销整个 token family。"""
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
        return _error("invalid_request", "token 请求必须使用 application/x-www-form-urlencoded")
    try:
        form = _parse_form(await request.body())
    except HTTPException:
        return _error("invalid_request", "token 请求表单无效")
    if "client_id" in form or "client_secret" in form:
        return _error("invalid_request", "客户端只能通过 client_secret_basic 认证")
    app = _authenticate_client(db, authorization)
    if isinstance(app, JSONResponse):
        return app
    now = datetime.now(timezone.utc)

    if form.get("grant_type") == "authorization_code":
        code, redirect_uri, verifier = form.get("code", ""), form.get("redirect_uri", ""), form.get("code_verifier", "")
        if not code or not redirect_uri or not VERIFIER_RE.fullmatch(verifier):
            return _error("invalid_grant", "授权码、回调地址或 PKCE verifier 无效")
        code_row = db.scalar(select(OAuthAuthorizationCode).where(
            OAuthAuthorizationCode.code_hash == _hash(code), OAuthAuthorizationCode.application_id == app.id,
        ).with_for_update())
        if (not code_row or code_row.consumed_at or code_row.expires_at <= now
                or not hmac.compare_digest(code_row.redirect_uri, redirect_uri)):
            return _error("invalid_grant", "授权码不存在、已使用、过期或回调地址不匹配")
        verifier_hash = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        # S256(verifier) 必须与授权请求登记的 challenge 完全一致，防止授权码被截获后冒用。
        if code_row.code_challenge_method != "S256" or not hmac.compare_digest(verifier_hash, code_row.code_challenge):
            return _error("invalid_grant", "PKCE 校验失败")
        user = db.scalar(select(User).where(User.id == code_row.user_id, User.status == "active"))
        membership = _app_membership(db, app, user) if user else None
        if (not user or code_row.auth_version != user.auth_version or not membership
                or code_row.membership_version != membership.auth_version):
            code_row.consumed_at = now
            db.commit()
            return _error("invalid_grant", "用户已停用或不再拥有应用访问权限")
        code_row.consumed_at = now
        result, _ = _token_payload(db, user, app, set(code_row.scope.split()), code_row.nonce, membership)
        _oauth_audit(db, user, app, "oidc.token.exchange", code_row.scope, request)
        db.commit()
        return _token_response(result)

    if form.get("grant_type") == "refresh_token":
        raw_refresh = form.get("refresh_token", "")
        if not raw_refresh:
            return _error("invalid_grant", "refresh_token 缺失")
        stored = db.scalar(select(OAuthRefreshToken).where(
            OAuthRefreshToken.token_hash == _hash(raw_refresh), OAuthRefreshToken.application_id == app.id,
        ).with_for_update())
        if not stored:
            return _error("invalid_grant", "refresh_token 无效")
        if stored.revoked_at is not None:
            # 旧值重放意味着令牌可能被复制；同一族现存子令牌一并撤销，阻止攻击者继续续期。
            db.execute(update(OAuthRefreshToken).where(
                OAuthRefreshToken.family_id == stored.family_id, OAuthRefreshToken.revoked_at.is_(None),
            ).values(revoked_at=now))
            db.commit()
            return _error("invalid_grant", "检测到 refresh_token 重放，当前会话族已撤销")
        user = db.scalar(select(User).where(User.id == stored.user_id, User.status == "active"))
        membership = _app_membership(db, app, user) if user else None
        if (stored.expires_at <= now or not user or stored.auth_version != user.auth_version
                or not membership or stored.membership_version != membership.auth_version):
            stored.revoked_at = now
            db.commit()
            return _error("invalid_grant", "refresh_token 已过期或用户授权已失效")
        old_scopes = set(stored.scope.split())
        requested_scope = form.get("scope")
        scopes = set(requested_scope.split()) if requested_scope else old_scopes
        if not scopes.issubset(old_scopes) or "openid" not in scopes:
            return _error("invalid_scope", "刷新请求不得扩大已授权 Scope")
        stored.revoked_at = now
        result, replacement = _token_payload(db, user, app, scopes, None, membership,
                                             family_id=stored.family_id)
        if replacement is None:
            return _error("invalid_scope", "refresh token 仅可用于已获 offline_access 的会话")
        stored.replaced_by_id = replacement.id
        _oauth_audit(db, user, app, "oidc.token.refresh", " ".join(sorted(scopes)), request)
        db.commit()
        return _token_response(result)
    return _error("unsupported_grant_type", "仅支持 authorization_code 和 refresh_token")


@router.get("/userinfo")
def userinfo(authorization: str | None = Header(default=None), db: Session = Depends(get_db_session)) -> Response:
    """只接受本 Provider 签发的 access token；ID Token 不可作为 UserInfo 凭证。"""
    if not authorization or not authorization.startswith("Bearer "):
        return _error("invalid_token", "需要 Bearer access token", 401)
    try:
        claims = decode_oidc_jwt(authorization[7:])
    except (jwt.PyJWTError, RuntimeError):
        return _error("invalid_token", "access token 无效或已过期", 401)
    if claims.get("token_use") != "access_token":
        return _error("invalid_token", "该 JWT 不能用于 UserInfo", 401)
    if access_token_is_revoked(claims, db) or not oidc_session_is_active(claims, db):
        return _error("invalid_token", "access token 已撤销", 401)
    client_id = claims.get("client_id")
    if not isinstance(client_id, str) or claims.get("aud") != client_id:
        return _error("invalid_token", "token audience 无效", 401)
    app = _active_client(db, client_id)
    try:
        user_id = UUID(claims.get("sub", ""))
    except (ValueError, TypeError):
        user_id = None
    user = db.scalar(select(User).where(User.id == user_id, User.status == "active")) if user_id else None
    token_auth_version = claims.get("auth_version", 1)
    token_membership_version = claims.get("membership_version", 1)
    membership = _app_membership(db, app, user) if app and user else None
    if (not app or not user or isinstance(token_auth_version, bool)
            or not isinstance(token_auth_version, int) or token_auth_version != user.auth_version
            or isinstance(token_membership_version, bool) or not isinstance(token_membership_version, int)
            or not membership or token_membership_version != membership.auth_version):
        return _error("invalid_token", "用户或应用已停用/撤权", 401)
    scopes = set(str(claims.get("scope", "")).split())
    output = {"sub": str(user.id)}
    if "profile" in scopes:
        output["name"] = user.display_name
    if "email" in scopes and user.email:
        output["email"] = user.email
        output["email_verified"] = user.email_verified_at is not None
    return JSONResponse(output, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


@router.post("/introspect")
async def introspect(request: Request, authorization: str | None = Header(default=None),
                     db: Session = Depends(get_db_session)) -> Response:
    """RFC 7662 client-authenticated online check for this application's own token.

    The endpoint accepts access and refresh tokens, but never returns token material.
    Cross-client, expired, revoked, malformed, or currently unauthorized credentials all
    return the same inactive response so the endpoint cannot reveal another app's tokens.
    """
    no_store = {"Cache-Control": "no-store", "Pragma": "no-cache"}
    inactive = JSONResponse({"active": False}, headers=no_store)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
        return _error("invalid_request", "introspect 请求必须使用 application/x-www-form-urlencoded")
    try:
        form = _parse_form(await request.body())
    except HTTPException:
        return _error("invalid_request", "introspect 请求表单无效")
    if "client_id" in form or "client_secret" in form:
        return _error("invalid_request", "客户端只能通过 client_secret_basic 认证")
    raw_token = form.get("token", "")
    if not raw_token or len(raw_token) > 8192:
        return _error("invalid_request", "token 参数缺失或过长")

    application = _authenticate_client(db, authorization)
    if isinstance(application, JSONResponse):
        return application
    now = datetime.now(timezone.utc)
    # RFC 7662 token_type_hint is only a lookup hint. Search both token types so a
    # wrong or stale hint cannot turn an active credential into a false inactive result.
    # Refresh tokens are opaque and stored only as SHA-256 digests. The client binding
    # comes from the authenticated Basic identity, never from a request-body client_id.
    refresh = db.scalar(select(OAuthRefreshToken).where(
        OAuthRefreshToken.token_hash == _hash(raw_token),
        OAuthRefreshToken.application_id == application.id,
        OAuthRefreshToken.revoked_at.is_(None),
        OAuthRefreshToken.expires_at > now,
    ))
    if refresh:
        user = db.scalar(select(User).where(User.id == refresh.user_id, User.status == "active"))
        membership = _app_membership(db, application, user) if user else None
        if (user and membership and refresh.auth_version == user.auth_version
                and refresh.membership_version == membership.auth_version):
            return JSONResponse({
                "active": True,
                "scope": refresh.scope,
                "client_id": application.client_id,
                "sub": str(user.id),
                "aud": application.client_id,
                "iss": _issuer(),
                "tenant_id": str(application.tenant_id),
                "exp": int(refresh.expires_at.timestamp()),
                "iat": int(refresh.created_at.timestamp()),
            }, headers=no_store)

    # Access tokens are signature-checked even when expired so all invalid states can
    # converge on active:false. The local expiry, jti revocation and live tenant/role
    # checks below determine whether a resource server may honor this bearer token now.
    try:
        claims = decode_oidc_jwt(raw_token, verify_exp=False)
        issued_at, expires_at = claims.get("iat"), claims.get("exp")
        subject_id = UUID(str(claims.get("sub", "")))
        tenant_id = UUID(str(claims.get("tenant_id", "")))
    except (jwt.PyJWTError, RuntimeError, TypeError, ValueError):
        return inactive
    if (claims.get("token_use") != "access_token"
            or claims.get("client_id") != application.client_id
            or claims.get("aud") != application.client_id
            or isinstance(issued_at, bool) or not isinstance(issued_at, int)
            or isinstance(expires_at, bool) or not isinstance(expires_at, int)
            or expires_at <= int(now.timestamp()) or issued_at > int(now.timestamp())
            or tenant_id != application.tenant_id
            or access_token_is_revoked(claims, db)
            or not oidc_session_is_active(claims, db)):
        return inactive
    user = db.scalar(select(User).where(User.id == subject_id, User.status == "active"))
    token_auth_version = claims.get("auth_version", 1)
    token_membership_version = claims.get("membership_version", 1)
    membership = _app_membership(db, application, user) if user else None
    if (not user or isinstance(token_auth_version, bool) or not isinstance(token_auth_version, int)
            or token_auth_version != user.auth_version or isinstance(token_membership_version, bool)
            or not isinstance(token_membership_version, int) or not membership
            or token_membership_version != membership.auth_version):
        return inactive
    scopes = claims.get("scope")
    if not isinstance(scopes, str):
        return inactive
    return JSONResponse({
        "active": True,
        "scope": scopes,
        "client_id": application.client_id,
        "token_type": "Bearer",
        "sub": str(user.id),
        "aud": application.client_id,
        "iss": _issuer(),
        "tenant_id": str(tenant_id),
        "exp": expires_at,
        "iat": issued_at,
    }, headers=no_store)


@router.get("/jwks")
def jwks() -> dict:
    """只向 OIDC 客户端发布当前签名公钥集合。"""
    return public_jwks()


@router.post("/revoke")
async def revoke(request: Request, authorization: str | None = Header(default=None),
                 db: Session = Depends(get_db_session)) -> Response:
    """RFC 7009 风格令牌撤销。OAuth 令牌不存在时同样返回 200，降低凭证探测信息。"""
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
        return _error("invalid_request", "revoke 请求必须使用 application/x-www-form-urlencoded")
    try:
        form = _parse_form(await request.body())
    except HTTPException:
        return _error("invalid_request", "revoke 请求表单无效")
    app = _authenticate_client(db, authorization)
    if isinstance(app, JSONResponse):
        return app
    raw = form.get("token", "")
    if not raw:
        return _error("invalid_request", "revoke 请求必须包含 token 参数")
    # RFC 7009 defines token_type_hint as a hint, not an authoritative type assertion.
    # Unknown hints are ignored, and both opaque refresh tokens and signed access
    # tokens are searched so clients cannot cause a valid token to be missed.
    stored = db.scalar(select(OAuthRefreshToken).where(
        OAuthRefreshToken.token_hash == _hash(raw), OAuthRefreshToken.application_id == app.id,
    ).with_for_update())
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return Response(status_code=200, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
    try:
        claims = decode_oidc_jwt(raw)
    except (jwt.PyJWTError, RuntimeError):
        claims = None
    if (claims and claims.get("token_use") == "access_token"
            and claims.get("client_id") == app.client_id and claims.get("aud") == app.client_id):
        already_revoked = access_token_is_revoked(claims, db)
        if not already_revoked and revoke_access_token(raw, db):
            user_id = claims.get("sub")
            user = db.scalar(select(User).where(User.id == user_id)) if user_id else None
            _oauth_audit(db, user, app, "oidc.token.revoke", str(claims.get("scope", "")), request) if user else None
            db.commit()
    return Response(status_code=200, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
