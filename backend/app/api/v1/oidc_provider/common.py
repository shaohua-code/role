"""OIDC Provider 通用校验、响应与身份上下文辅助函数。"""

import hashlib
from datetime import datetime, timezone
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.application import Application
from app.models.identity import AuditEvent, RefreshSession, Tenant, TenantMembership, User
from app.services.login_throttle import client_ip_for_request


def _issuer() -> str:
    """读取并校验 issuer 配置：生产必须 HTTPS，仅开发放行 localhost 的 HTTP。"""
    value = get_settings().oidc_issuer
    parts = urlsplit(value or "")
    local_http = parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}
    if (not value or (parts.scheme != "https" and not local_http) or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment):
        raise HTTPException(503, "OIDC_ISSUER 必须配置为 HTTPS 地址（开发环境可用 localhost）")
    return value.rstrip("/")


def _endpoint(path: str) -> str:
    """拼接 issuer 与版本化前缀，生成对外公布的端点完整地址。"""
    return f"{_issuer()}{get_settings().api_v1_prefix}/oidc/{path}"


def _error(error: str, description: str, status_code: int = 400, *, challenge: bool = False) -> JSONResponse:
    """OAuth 错误不得缓存；Basic 客户端认证失败带标准 challenge 响应头。"""
    headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}
    if challenge:
        headers["WWW-Authenticate"] = 'Basic realm="iam-token", charset="UTF-8"'
    return JSONResponse({"error": error, "error_description": description}, status_code=status_code, headers=headers)


def _append_query(uri: str, params: list[tuple[str, str]]) -> str:
    """向已有 URI 追加查询参数，保留原 query 顺序与空值、fragment。"""
    parts = urlsplit(uri)
    existing = parse_qsl(parts.query, keep_blank_values=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode([*existing, *params]), parts.fragment))


def _oauth_redirect_error(uri: str, state: str | None, error: str, description: str) -> RedirectResponse:
    """按 OAuth 规范把错误码经 302 回传到 redirect_uri，回显 state 并附 iss。"""
    params = [("error", error), ("error_description", description)]
    if state:
        params.append(("state", state))
    params.append(("iss", _issuer()))
    return RedirectResponse(_append_query(uri, params), status_code=302, headers={"Cache-Control": "no-store"})


def _single(params, name: str, *, required: bool = False) -> str | None:
    """取单值查询参数；出现重复或必填缺失时抛错，由调用方转 invalid_request。"""
    values = params.getlist(name)
    if len(values) > 1 or (required and (not values or not values[0])):
        raise ValueError(name)
    return values[0] if values else None


def _active_client(db: Session, client_id: str) -> Application | None:
    """按 client_id 查活动状态的应用客户端，停用客户端视同不存在。"""
    return db.scalar(select(Application).where(Application.client_id == client_id, Application.status == "active"))


def _redirect_uri(app: Application, requested: str | None) -> str | None:
    """精确匹配注册回调地址；未传且仅注册一个时自动补全，杜绝开放重定向。"""
    if requested is None and len(app.redirect_uris) == 1:
        return app.redirect_uris[0]
    if requested and requested in app.redirect_uris:
        return requested
    return None


def _oauth_audit(db: Session, user: User, app: Application, action: str, scope: str, request: Request) -> None:
    """审计保存应用和 Scope 摘要，不保存 code、token、nonce 或 PKCE verifier。"""
    db.add(AuditEvent(actor_user_id=user.id, tenant_id=app.tenant_id, action=action,
                      target_type="application", target_id=str(app.id),
                      source_ip=client_ip_for_request(request, get_settings()),
                      details={"client_id": app.client_id, "scope": scope}))


def _browser_user(db: Session, raw_cookie: str | None) -> User | None:
    """OIDC 登录状态来自服务端 HttpOnly refresh session，不信任浏览器提交的 user id。"""
    if not raw_cookie:
        return None
    digest = hashlib.sha256(raw_cookie.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    session = db.scalar(select(RefreshSession).where(
        RefreshSession.token_hash == digest, RefreshSession.revoked_at.is_(None), RefreshSession.expires_at > now,
    ))
    if not session:
        return None
    user = db.scalar(select(User).where(User.id == session.user_id, User.status == "active"))
    if user is None or session.auth_version != user.auth_version:
        return None
    return user


def _app_membership(db: Session, app: Application, user: User) -> TenantMembership | None:
    """SSO 入场与 evaluate_access 共用有效角色：直连绑定 ∪ 活跃用户组继承角色。"""
    if not db.scalar(select(Tenant.id).where(Tenant.id == app.tenant_id, Tenant.status == "active")):
        return None
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user.id, TenantMembership.tenant_id == app.tenant_id,
        TenantMembership.status == "active",
    ))
    if not membership:
        return None
    from app.services.effective_roles import list_effective_roles

    effective_roles = list_effective_roles(
        db, membership_id=membership.id, tenant_id=app.tenant_id, application_id=app.id,
    )
    return membership if effective_roles else None


def _hash(raw: str) -> str:
    """opaque 凭证的 SHA-256 摘要，数据库只存摘要不存原文。"""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_form(body: bytes) -> dict[str, str]:
    """表单原始解析保留重复字段信息，严格拒绝重复参数。"""
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=16)
        if any(len(values) != 1 for values in parsed.values()):
            raise ValueError("duplicate")
        return {key: values[0] for key, values in parsed.items()}
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(400, "invalid_request") from None
