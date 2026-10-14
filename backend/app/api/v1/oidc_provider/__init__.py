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

__all__ = ["discovery_document", "router"]
