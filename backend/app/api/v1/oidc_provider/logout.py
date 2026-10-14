"""OIDC RP-Initiated Logout 端点。"""

from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.oidc_keys import decode_oidc_jwt
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import AuditEvent, RefreshSession, User
from app.models.oidc import OAuthRefreshToken
from app.services.login_throttle import client_ip_for_request
from .common import _append_query, _error, _hash, _parse_form, _single
from .constants import REFRESH_COOKIE
router = APIRouter()


@router.api_route("/logout", methods=["GET", "POST"])
async def end_session(request: Request,
                      refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
                      db: Session = Depends(get_db_session)) -> Response:
    """按 OIDC RP-Initiated Logout 登出指定客户端会话，并严格校验退出回跳。"""
    # ID Token Hint 用于证明客户端和用户身份。GET 能带上 SameSite=Lax SSO Cookie，
    # 因而可完整结束浏览器 IAM 会话，但令牌会进入 URL；部署须脱敏访问日志。跨站 POST
    # 可减少 URL 泄露，但浏览器通常不附带 Lax Cookie，只能可靠撤销该 RP 的刷新令牌。
    try:
        if request.method == "POST":
            if request.query_params or request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/x-www-form-urlencoded":
                raise ValueError("form")
            params = _parse_form(await request.body())
            id_token_hint = params.get("id_token_hint", "")
            post_logout_uri = params.get("post_logout_redirect_uri")
            state = params.get("state")
        else:
            query = request.query_params
            id_token_hint = _single(query, "id_token_hint", required=True) or ""
            post_logout_uri = _single(query, "post_logout_redirect_uri")
            state = _single(query, "state")
        if (not id_token_hint or len(id_token_hint) > 8192
                or (state is not None and (not state or len(state) > 512))
                or (post_logout_uri is not None and len(post_logout_uri) > 2048)
                or (state is not None and post_logout_uri is None)
                or (post_logout_uri is not None and state is None)):
            raise ValueError("parameter")
    except (ValueError, HTTPException):
        return _error("invalid_request", "退出请求参数无效")

    # 退出可接受已过期但有效签名的 ID Token Hint；不允许 access token 冒充 ID Token。
    try:
        claims = decode_oidc_jwt(id_token_hint, verify_exp=False)
        client_id = claims.get("aud")
        if (not isinstance(client_id, str) or claims.get("token_use") is not None
                or claims.get("client_id") is not None or not isinstance(claims.get("sub"), str)):
            raise ValueError("id_token_claims")
        if claims.get("azp") not in (None, client_id):
            raise ValueError("azp")
        subject_id = UUID(claims["sub"])
    except (jwt.PyJWTError, RuntimeError, ValueError, TypeError):
        return _error("invalid_request", "id_token_hint 无效")

    app = db.scalar(select(Application).where(Application.client_id == client_id))
    if not app:
        return _error("invalid_request", "客户端无效")
    if post_logout_uri is not None and post_logout_uri not in app.post_logout_redirect_uris:
        return _error("invalid_request", "退出回调地址未与客户端精确登记值匹配")
    # state 由 Provider 返回；静态登记 URI 若已含同名参数会造成回调方无法安全判定。
    if post_logout_uri is not None and any(
        name == "state" for name, _ in parse_qsl(urlsplit(post_logout_uri).query, keep_blank_values=True)
    ):
        return _error("invalid_request", "退出回调地址不得预设 state 参数")

    now = datetime.now(timezone.utc)
    user = db.get(User, subject_id)
    revoke_browser_cookie = False
    if user:
        # ID Token Hint 绑定客户端/主体；登出只撤销该客户端该主体的 OAuth refresh 会话。
        db.execute(update(OAuthRefreshToken).where(
            OAuthRefreshToken.application_id == app.id,
            OAuthRefreshToken.user_id == user.id,
            OAuthRefreshToken.revoked_at.is_(None),
        ).values(revoked_at=now))

        # 同一浏览器只有在 HttpOnly session 与 ID Token 主体一致时才退出 IAM SSO 会话，
        # 避免攻击者用自己的有效 ID Token 让受害浏览器注销另一个已登录账号。
        if refresh_cookie:
            cookie_hash = _hash(refresh_cookie)
            browser_session = db.scalar(select(RefreshSession).where(
                RefreshSession.token_hash == cookie_hash,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            ).with_for_update())
            if browser_session and browser_session.user_id == user.id:
                browser_session.revoked_at = now
                revoke_browser_cookie = True

        db.add(AuditEvent(
            actor_user_id=user.id, tenant_id=app.tenant_id, action="oidc.logout",
            target_type="application", target_id=str(app.id),
            source_ip=client_ip_for_request(request, get_settings()),
            details={"client_id": app.client_id},
        ))
    db.commit()

    headers = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    }
    if post_logout_uri:
        response: Response = RedirectResponse(
            _append_query(post_logout_uri, [("state", state)]) if state is not None else post_logout_uri,
            status_code=302, headers=headers,
        )
    else:
        response = HTMLResponse(
            "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"referrer\" content=\"no-referrer\"><title>Signed out</title><body><main><h1>Signed out</h1><p>You can close this page.</p></main></body></html>",
            headers=headers,
        )

    # 只清除与 ID Token 主体匹配的 SSO cookie；不匹配时保留其他账号的会话。
    if revoke_browser_cookie:
        settings = get_settings()
        response.delete_cookie(
            key=REFRESH_COOKIE, httponly=True, secure=settings.app_env != "development",
            samesite="lax", path=settings.api_v1_prefix,
        )
    return response
