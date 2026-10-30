"""OIDC Provider 路由装配。具体协议端点按职责拆分到独立模块。"""

from fastapi import APIRouter

from .authorization import router as authorization_router
from .logout import router as logout_router
from .tokens import router as token_router
from .metadata import discovery_document

router = APIRouter(prefix="/oidc", tags=["OAuth 2.0 / OpenID Connect"])
router.include_router(authorization_router)
router.include_router(token_router)
router.include_router(logout_router)

# 兼容历史导入路径：原 oidc.py 垫片的再导出已并入包入口，新代码可直接从这里导入。
from .authorization import authorize, consent_context, consent_decision, login_context
from .logout import end_session
from .metadata import discovery
from .tokens import (
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
