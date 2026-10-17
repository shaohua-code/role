"""FastAPI OIDC login-route plugin over `iam_oidc`.

自动挂载 login/callback/logout/me 四条路由，消除业务方重复编写 OIDC RP 流程；
attempt 与身份令牌只保存在业务方提供的 **服务端** SessionStore 中，浏览器仅持有
一次性 HttpOnly 会话 Cookie。CSRF 防护、代理访问日志脱敏与 Cookie 仍由业务方
整体负责（见技术架构与接入.md 第 3 节）。

推荐用法：

    from fastapi import FastAPI
    from iam_fastapi_auth import InMemorySessionStore, mount_oidc_auth
    from iam_oidc import IamOIDCClient

    app = FastAPI()
    mount_oidc_auth(
        app,
        oidc_client=IamOIDCClient(issuer=..., client_id=..., client_secret=..., redirect_uri=...),
        session_store=InMemorySessionStore(),  # 生产应替换为 Redis/数据库实现
        post_login_redirect="/",
    )
"""
from dataclasses import asdict, dataclass
from secrets import token_urlsafe
import threading
import time
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from iam_oidc import AuthorizationAttempt, IamOIDCClient, OIDCProtocolError

_ATTEMPT_COOKIE = "iam_attempt"


def _attempt_key(attempt_id: str) -> str:
    return f"attempt:{attempt_id}"


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


class SessionStore(Protocol):
    """业务方实现的服务端会话存储协议；生产环境应使用 Redis/数据库并加密落盘。"""

    def put(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        """保存或覆盖键值；到期后必须不可再读出。"""

    def load(self, key: str) -> dict[str, Any] | None:
        """读取键值；存在且未到期时返回副本，否则返回 None。"""

    def take(self, key: str) -> dict[str, Any] | None:
        """原子取出并删除键值；用于一次性 attempt，重复消费必须失败。"""

    def delete(self, key: str) -> None:
        """删除键值；键不存在时静默返回。"""


class InMemorySessionStore:
    """线程安全的进程内存储；仅用于本地开发与测试，不提供跨实例共享或持久化。"""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[dict[str, Any], float]] = {}
        self._lock = threading.Lock()

    def put(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        with self._lock:
            self._purge_expired()
            self._entries[key] = (dict(value), time.time() + max(1, int(ttl_seconds)))

    def load(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            self._purge_expired()
            entry = self._entries.get(key)
            return dict(entry[0]) if entry else None

    def take(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            self._purge_expired()
            entry = self._entries.pop(key, None)
            return dict(entry[0]) if entry else None

    def delete(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def _purge_expired(self) -> None:
        now = time.time()
        for key in [key for key, (_, expiry) in self._entries.items() if expiry <= now]:
            self._entries.pop(key, None)


@dataclass(frozen=True)
class OidcRouteOptions:
    """路由与 Cookie 配置；默认值对应 /auth/* 约定路径。"""

    cookie_name: str = "iam_session"
    session_ttl_seconds: int = 8 * 3600
    attempt_ttl_seconds: int = 600
    login_path: str = "/auth/login"
    callback_path: str = "/auth/callback"
    logout_path: str = "/auth/logout"
    me_path: str = "/auth/me"
    post_login_redirect: str = "/"
    post_logout_redirect: str | None = None
    cookie_secure: bool = False
    cookie_domain: str | None = None
    scopes: tuple[str, ...] = ("openid", "profile", "email")


def mount_oidc_auth(
    app: FastAPI,
    *,
    oidc_client: IamOIDCClient,
    session_store: SessionStore,
    options: OidcRouteOptions | None = None,
) -> None:
    """把 login/callback/logout/me 挂到给定 FastAPI 应用；重复调用同一应用会重复注册路由。"""
    options = options or OidcRouteOptions()

    def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
        response.set_cookie(
            key=name,
            value=value,
            max_age=max_age,
            httponly=True,
            samesite="lax",
            secure=options.cookie_secure,
            domain=options.cookie_domain,
            path="/",
        )

    @app.get(options.login_path)
    def start_login() -> Response:
        attempt = oidc_client.create_authorization_request(scopes=options.scopes)
        attempt_id = token_urlsafe(32)
        session_store.put(_attempt_key(attempt_id), asdict(attempt), options.attempt_ttl_seconds)
        response = RedirectResponse(attempt.authorization_url, status_code=302)
        _set_cookie(response, _ATTEMPT_COOKIE, attempt_id, options.attempt_ttl_seconds)
        return response

    @app.get(options.callback_path)
    def complete_login(request: Request) -> Response:
        attempt_id = request.cookies.get(_ATTEMPT_COOKIE, "")
        if not attempt_id:
            # 无 attempt Cookie 意味着流程未从 /auth/login 发起或已被消费，直接拒绝。
            raise HTTPException(status_code=403, detail="OIDC login attempt missing or expired")
        raw_attempt = session_store.take(_attempt_key(attempt_id))
        if not raw_attempt:
            raise HTTPException(status_code=403, detail="OIDC login attempt missing or expired")
        attempt = AuthorizationAttempt(
            authorization_url=raw_attempt["authorization_url"],
            state=raw_attempt["state"],
            nonce=raw_attempt["nonce"],
            code_verifier=raw_attempt["code_verifier"],
            scopes=tuple(raw_attempt.get("scopes", ())),
        )
        try:
            identity = oidc_client.complete_login(str(request.url), attempt)
        except OIDCProtocolError:
            # 不把 Provider 拒绝细节透给浏览器；完整原因留在服务端日志（由业务方记录）。
            raise HTTPException(status_code=403, detail="OIDC login failed") from None
        session_id = token_urlsafe(32)
        session_store.put(_session_key(session_id), asdict(identity), options.session_ttl_seconds)
        response = RedirectResponse(options.post_login_redirect, status_code=302)
        _set_cookie(response, options.cookie_name, session_id, options.session_ttl_seconds)
        response.delete_cookie(_ATTEMPT_COOKIE, path="/")
        return response

    @app.get(options.me_path)
    def current_identity(request: Request) -> Response:
        identity = _load_identity(request, session_store, options)
        if identity is None:
            raise HTTPException(status_code=401, detail="No active session")
        # 绝不返回 tokens；profile 只含 IdP 发布的展示声明。
        return JSONResponse({
            "subject": identity["subject"],
            "tenant_id": identity["tenant_id"],
            "profile": identity.get("profile", {}),
        })

    @app.get(options.logout_path)
    def logout(request: Request) -> Response:
        session_id = request.cookies.get(options.cookie_name, "")
        identity = session_store.take(_session_key(session_id)) if session_id else None
        if identity:
            tokens = identity.get("tokens", {})
            # 撤销失败不阻断本地登出；本地会话清理优先，撤销按 best-effort 幂等执行。
            try:
                if tokens.get("refresh_token"):
                    oidc_client.revoke_refresh_token(tokens["refresh_token"])
                if tokens.get("access_token"):
                    oidc_client.revoke_access_token(tokens["access_token"])
            except OIDCProtocolError:
                pass
        response: Response = (
            RedirectResponse(options.post_logout_redirect, status_code=302)
            if options.post_logout_redirect
            else JSONResponse({"ok": True})
        )
        response.delete_cookie(options.cookie_name, path="/")
        return response


def _load_identity(
    request: Request, session_store: SessionStore, options: OidcRouteOptions
) -> dict[str, Any] | None:
    session_id = request.cookies.get(options.cookie_name, "")
    if not session_id:
        return None
    return session_store.load(_session_key(session_id))
