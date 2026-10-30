"""OIDC Provider 的协议常量。"""

import re
from datetime import timedelta

# 浏览器会话 Cookie（与认证模块共用同一名称）
REFRESH_COOKIE = "iam_refresh_token"

# 协议对象有效期：授权码一次性且短命，同意票据覆盖用户确认窗口
AUTHORIZATION_CODE_TTL = timedelta(minutes=2)
CONSENT_TICKET_TTL = timedelta(minutes=5)
ACCESS_TOKEN_TTL = timedelta(minutes=10)

# 授权范围白名单：offline_access 才允许签发 refresh token
ALLOWED_SCOPES = {"openid", "profile", "email", "offline_access"}

# PKCE（RFC 7636）：code_verifier 与 code_challenge 的格式约束
VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
