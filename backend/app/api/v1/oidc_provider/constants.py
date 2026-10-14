"""OIDC Provider 的协议常量。"""

import re
from datetime import timedelta

REFRESH_COOKIE = "iam_refresh_token"
AUTHORIZATION_CODE_TTL = timedelta(minutes=2)
CONSENT_TICKET_TTL = timedelta(minutes=5)
ACCESS_TOKEN_TTL = timedelta(minutes=10)
ALLOWED_SCOPES = {"openid", "profile", "email", "offline_access"}
VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
