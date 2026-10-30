"""OIDC Back-Channel Logout 1.0（G19）：会话撤销时向业务方推送签名 logout_token。

规范要点（OpenID Connect Back-Channel Logout 1.0，实施者注）：
- POST application/x-www-form-urlencoded，body 只有 logout_token 一个参数；
- logout_token 是 RS256 签名 JWT，typ=logout+jwt，claims 含 iss/aud/iat/exp/jti 与
  events=["http://schemas.openid.net/event/backchannel-logout"]，必须不含 nonce；
- 带 sid 表示只登出该会话；业务方校验通过后应销毁对应本地会话。
- 投递 best-effort：后台守护线程 3 秒超时、失败只记日志不重试——业务方仍有
  introspection / 在线判权 / 10 分钟 access token 过期三重兜底，不因推送失败阻塞撤销。
"""

import logging
import threading
import time
from urllib import parse as url_parse
from urllib import request as url_request
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.core.oidc_keys import sign_jwt
from app.models.application import Application
from app.models.oidc import OAuthRefreshToken

logger = logging.getLogger(__name__)
BACKCHANNEL_LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"
_DELIVERY_TIMEOUT_SECONDS = 3


def build_logout_token(application: Application, user_id: UUID | None,
                       session_id: UUID | None) -> str | None:
    """构造并签名 logout_token；未配置 issuer（极端开发环境）时返回 None 跳过投递。"""
    issuer = get_settings().oidc_issuer
    if not issuer:
        return None
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": application.client_id,
        "iat": now,
        "exp": now + 120,
        "jti": uuid4().hex,
        "events": [BACKCHANNEL_LOGOUT_EVENT],
    }
    if user_id:
        claims["sub"] = str(user_id)
    if session_id:
        claims["sid"] = str(session_id)
    return sign_jwt(claims, token_type="logout+jwt")


def deliver_backchannel_logout(applications, *, user_id: UUID | None = None,
                               session_id: UUID | None = None) -> None:
    """向已配置 back-channel URI 的应用推送登出令牌；令牌在调用线程构造（会话仍可用）。"""
    payloads: list[tuple[str, str]] = []
    for application in applications:
        if not application.backchannel_logout_uri:
            continue
        token = build_logout_token(application, user_id, session_id)
        if token:
            payloads.append((application.backchannel_logout_uri, token))
    if not payloads:
        return
    thread = threading.Thread(target=_deliver_all, args=(payloads,), daemon=True,
                              name="iam-backchannel-logout")
    thread.start()


def deliver_for_user(db, user_id: UUID) -> None:
    """全量撤销类事件（停用/锁停/改密/重置）：向该用户有过 OIDC 会话的应用推送。

    调用方必须在凭证级联提交后调用；此时 refresh token 行仍在（只是 revoked_at
    已写入），可据此还原 application_id 集合。
    """
    application_ids = set(db.scalars(select(OAuthRefreshToken.application_id).where(
        OAuthRefreshToken.user_id == user_id,
    )).all())
    if not application_ids:
        return
    applications = db.scalars(select(Application).where(Application.id.in_(application_ids))).all()
    deliver_backchannel_logout(applications, user_id=user_id)


def _deliver_all(payloads: list[tuple[str, str]]) -> None:
    """后台线程逐个投递；异常类型入日志，URL 与令牌不落日志（含身份断言）。"""
    for uri, token in payloads:
        try:
            body = url_parse.urlencode({"logout_token": token}).encode("utf-8")
            request = url_request.Request(
                uri, data=body, method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with url_request.urlopen(request, timeout=_DELIVERY_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", None) or response.getcode()
            if not (200 <= int(status) < 300):
                logger.warning("backchannel_logout_non_2xx status=%s", status)
        except Exception as error:  # noqa: BLE001 — best-effort 投递，任何失败都不上抛
            logger.warning("backchannel_logout_delivery_failed error_type=%s", type(error).__name__)
