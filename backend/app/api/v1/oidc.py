"""兼容入口：OIDC 端点实现位于 `oidc_provider/` 的协议域模块。

新代码应从 `app.api.v1.oidc_provider` 及其领域模块导入；保留这里的导出是为了
兼容现有应用装配和测试导入路径。
"""

from app.api.v1.oidc_provider import discovery_document, router
from app.api.v1.oidc_provider.authorization import authorize, consent_context, consent_decision, login_context
from app.api.v1.oidc_provider.logout import end_session
from app.api.v1.oidc_provider.metadata import discovery
from app.api.v1.oidc_provider.tokens import (
    _access_token,
    _id_token,
    introspect,
    jwks,
    revoke,
    token,
    userinfo,
)

__all__ = [
    "_access_token", "_id_token", "authorize", "consent_context", "consent_decision",
    "discovery", "discovery_document", "end_session", "introspect", "jwks",
    "login_context", "revoke", "router", "token", "userinfo",
]
