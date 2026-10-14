"""OIDC Authorization Code、PKCE 与用户授权同意端点。"""

import secrets
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.application import Application, ApplicationTheme
from app.models.identity import Tenant, TenantMembership, User
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest
from app.services.public_registration import application_registration_details
from app.schemas.auth import OIDCConsentDecision, OIDCConsentTicket
from .common import _active_client, _app_membership, _append_query, _browser_user, _error, _hash, _issuer, _oauth_audit, _oauth_redirect_error, _redirect_uri, _single
from .constants import ALLOWED_SCOPES, AUTHORIZATION_CODE_TTL, CHALLENGE_RE, CONSENT_TICKET_TTL, REFRESH_COOKIE
router = APIRouter()


def _issue_code(db: Session, user: User, app: Application, callback: str, state: str,
                scope: str, nonce: str, challenge: str, request: Request,
                membership: TenantMembership) -> RedirectResponse:
    """只在完成登录/授权确认后创建绑定原请求上下文的一次性授权码。"""
    raw_code = secrets.token_urlsafe(36)
    db.add(OAuthAuthorizationCode(
        application_id=app.id, user_id=user.id, auth_version=user.auth_version or 1,
        membership_version=membership.auth_version or 1,
        code_hash=_hash(raw_code), redirect_uri=callback,
        scope=scope, nonce=nonce, code_challenge=challenge,
        code_challenge_method="S256", expires_at=datetime.now(timezone.utc) + AUTHORIZATION_CODE_TTL,
    ))
    _oauth_audit(db, user, app, "oidc.authorize", scope, request)
    db.commit()
    return RedirectResponse(_append_query(callback, [
        ("code", raw_code), ("state", state), ("iss", _issuer()),
    ]), status_code=302, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


def _consent_redirect(db: Session, user: User, app: Application, callback: str, state: str,
                      scope: str, nonce: str, challenge: str,
                      membership: TenantMembership) -> RedirectResponse:
    """浏览器只拿高熵一次性 ticket；授权请求其余参数保留在受服务端保护的短期记录中。"""
    now = datetime.now(timezone.utc)
    # 同步回收过期请求，避免长期运行的 Provider 积累不可再使用的确认票据。
    db.execute(delete(OAuthConsentRequest).where(OAuthConsentRequest.expires_at <= now))
    ticket = secrets.token_urlsafe(48)
    db.add(OAuthConsentRequest(
        application_id=app.id, user_id=user.id, auth_version=user.auth_version or 1,
        membership_version=membership.auth_version or 1,
        ticket_hash=_hash(ticket), redirect_uri=callback,
        client_state=state, scope=scope, nonce=nonce, code_challenge=challenge,
        code_challenge_method="S256", expires_at=now + CONSENT_TICKET_TTL,
    ))
    db.commit()
    console = get_settings().console_public_url.rstrip("/")
    return RedirectResponse(f"{console}/#consent={quote(ticket, safe='')}", status_code=302,
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/login-context")
def login_context(client_id: str, db: Session = Depends(get_db_session)) -> dict:
    """匿名页只读取活动应用和已发布主题，不返回客户端密钥或草稿。"""
    app = _active_client(db, client_id)
    if not app:
        raise HTTPException(404, "应用不存在或已停用")
    theme = db.scalar(select(ApplicationTheme).where(
        ApplicationTheme.application_id == app.id, ApplicationTheme.status == "published",
    ).order_by(ApplicationTheme.version.desc()).limit(1))
    return {
        "application_name": app.name,
        "client_id": app.client_id,
        "theme": theme.config if theme else {},
        "registration": application_registration_details(db, app),
    }


@router.get("/authorize")
def authorize(
    request: Request,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: Session = Depends(get_db_session),
) -> Response:
    """先精确校验客户端回调，再登录/拒绝或签发 2 分钟一次性授权码。"""
    params = request.query_params
    try:
        client_id = _single(params, "client_id", required=True)
        requested_redirect = _single(params, "redirect_uri")
        response_type = _single(params, "response_type", required=True)
    except ValueError:
        return _error("invalid_request", "授权请求包含缺失或重复的客户端参数")
    app = _active_client(db, client_id or "")
    if not app:
        return _error("invalid_client", "客户端不存在或已停用")
    callback = _redirect_uri(app, requested_redirect)
    if not callback:
        return _error("invalid_request", "redirect_uri 未与客户端精确登记值匹配")
    state_value = params.get("state", "")
    try:
        for name in ("state", "scope", "nonce", "code_challenge", "code_challenge_method", "response_mode", "prompt"):
            if len(params.getlist(name)) > 1:
                raise ValueError(name)
        if response_type != "code":
            raise ValueError("response_type")
        if not state_value or len(state_value) > 512:
            raise ValueError("state")
        nonce = _single(params, "nonce", required=True)
        if len(nonce or "") > 255:
            raise ValueError("nonce")
        code_challenge = _single(params, "code_challenge", required=True)
        if not CHALLENGE_RE.fullmatch(code_challenge or ""):
            raise ValueError("code_challenge")
        if _single(params, "code_challenge_method", required=True) != "S256":
            raise ValueError("code_challenge_method")
        response_mode = _single(params, "response_mode")
        if response_mode not in (None, "query"):
            raise ValueError("response_mode")
        requested_scopes = _single(params, "scope")
        scopes = set((requested_scopes or "openid").split())
        if "openid" not in scopes or not scopes.issubset(ALLOWED_SCOPES):
            return _oauth_redirect_error(callback, state_value, "invalid_scope", "请求的 scope 不受支持")
        prompts = set((_single(params, "prompt") or "").split())
        if prompts - {"login", "none", "consent"} or ("none" in prompts and len(prompts) > 1):
            raise ValueError("prompt")
    except ValueError as exc:
        return _oauth_redirect_error(callback, state_value or None, "invalid_request", f"授权请求参数无效：{exc}")

    user = None if "login" in prompts else _browser_user(db, refresh_cookie)
    if user is None:
        if "none" in prompts:
            return _oauth_redirect_error(callback, state_value, "login_required", "当前浏览器没有活动登录会话")
        # login 后重放原始授权参数；清除 prompt=login 避免再次强制登录造成循环。
        continue_params = [(key, value) for key, value in params.multi_items() if not (key == "prompt" and value == "login")]
        return_to = f"{get_settings().api_v1_prefix}/oidc/authorize?{urlencode(continue_params)}"
        console = get_settings().console_public_url.rstrip("/")
        return RedirectResponse(f"{console}/?return_to={quote(return_to, safe='')}", status_code=302)

    membership = _app_membership(db, app, user)
    if not membership:
        return _oauth_redirect_error(callback, state_value, "access_denied", "账号没有该应用的活动租户角色授权")
    scope_value = " ".join(sorted(scopes))
    # 不受信应用逐次获取用户授权；prompt=consent 对受信应用也强制显示确认。
    if not app.trusted or "consent" in prompts:
        if "none" in prompts:
            return _oauth_redirect_error(callback, state_value, "consent_required", "此请求需要用户授权确认")
        return _consent_redirect(db, user, app, callback, state_value, scope_value,
                                 nonce or "", code_challenge or "", membership)
    # RFC 9207 issuer response parameter protects clients from authorization-server mix-up.
    return _issue_code(db, user, app, callback, state_value, scope_value,
                       nonce or "", code_challenge or "", request, membership)


@router.post("/consent/context")
def consent_context(response: Response, body: OIDCConsentTicket,
                    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
                    db: Session = Depends(get_db_session)) -> dict:
    """以同源 HttpOnly 会话校验短期 ticket；只展示用户能够判断授权范围所需的信息。"""
    # 个人身份和一次性授权上下文不能进入浏览器、代理或共享缓存。
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    user = _browser_user(db, refresh_cookie)
    if not user:
        raise HTTPException(401, "登录会话已过期，请重新发起应用登录")
    now = datetime.now(timezone.utc)
    row = db.scalar(select(OAuthConsentRequest).where(
        OAuthConsentRequest.ticket_hash == _hash(body.ticket),
        OAuthConsentRequest.consumed_at.is_(None), OAuthConsentRequest.expires_at > now,
    ))
    if not row or row.user_id != user.id or row.auth_version != user.auth_version:
        raise HTTPException(404, "授权请求无效或已过期")
    app = db.scalar(select(Application).where(Application.id == row.application_id,
                                               Application.status == "active"))
    tenant = db.scalar(select(Tenant).where(Tenant.id == app.tenant_id, Tenant.status == "active")) if app else None
    membership = _app_membership(db, app, user) if app else None
    if (not app or not tenant or not membership
            or row.membership_version != membership.auth_version):
        raise HTTPException(404, "应用访问授权已失效")
    theme = db.scalar(select(ApplicationTheme).where(
        ApplicationTheme.application_id == app.id, ApplicationTheme.status == "published",
    ).order_by(ApplicationTheme.version.desc()).limit(1))
    return {"application_name": app.name, "tenant_name": tenant.name, "email": user.email,
            "scope": row.scope.split(), "expires_at": row.expires_at,
            "theme": theme.config if theme else {}}


@router.post("/consent/decision")
def consent_decision(response: Response, body: OIDCConsentDecision, request: Request,
                     refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
                     db: Session = Depends(get_db_session)) -> dict:
    """锁定并单次消费确认票据；授权码签发和授权审计与消费状态同事务提交。"""
    # 响应可能含授权码或拒绝后的回跳地址，禁止缓存一次性凭据。
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    user = _browser_user(db, refresh_cookie)
    if not user:
        raise HTTPException(401, "登录会话已过期，请重新发起应用登录")
    now = datetime.now(timezone.utc)
    row = db.scalar(select(OAuthConsentRequest).where(
        OAuthConsentRequest.ticket_hash == _hash(body.ticket),
    ).with_for_update())
    if (not row or row.user_id != user.id or row.auth_version != user.auth_version
            or row.consumed_at or row.expires_at <= now):
        raise HTTPException(404, "授权请求无效、已使用或已过期")
    app = db.scalar(select(Application).where(Application.id == row.application_id,
                                               Application.status == "active"))
    membership = _app_membership(db, app, user) if app else None
    if (not app or not membership or row.membership_version != membership.auth_version):
        row.consumed_at = now
        db.commit()
        raise HTTPException(403, "应用访问授权已失效")
    row.consumed_at = now
    if not body.approved:
        _oauth_audit(db, user, app, "oidc.consent.deny", row.scope, request)
        db.commit()
        destination = _oauth_redirect_error(row.redirect_uri, row.client_state,
                                            "access_denied", "用户拒绝应用授权")
        return {"redirect_to": destination.headers["location"]}
    raw_code = secrets.token_urlsafe(36)
    db.add(OAuthAuthorizationCode(
        application_id=app.id, user_id=user.id, auth_version=user.auth_version or 1,
        membership_version=membership.auth_version or 1,
        code_hash=_hash(raw_code),
        redirect_uri=row.redirect_uri, scope=row.scope, nonce=row.nonce,
        code_challenge=row.code_challenge, code_challenge_method=row.code_challenge_method,
        expires_at=now + AUTHORIZATION_CODE_TTL,
    ))
    _oauth_audit(db, user, app, "oidc.consent.approve", row.scope, request)
    db.commit()
    destination = _append_query(row.redirect_uri, [
        ("code", raw_code), ("state", row.client_state), ("iss", _issuer()),
    ])
    return {"redirect_to": destination}
