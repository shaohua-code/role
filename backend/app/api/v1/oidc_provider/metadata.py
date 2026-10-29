"""OIDC Discovery 元数据。"""

from .common import _endpoint, _issuer
from .constants import ALLOWED_SCOPES
def discovery_document() -> dict:
    """元数据只列出本 Provider 实际实现并支持的协议能力。"""
    return {
        "issuer": _issuer(),
        "authorization_endpoint": _endpoint("authorize"),
        "token_endpoint": _endpoint("token"),
        "introspection_endpoint": _endpoint("introspect"),
        "revocation_endpoint": _endpoint("revoke"),
        "end_session_endpoint": _endpoint("logout"),
        "userinfo_endpoint": _endpoint("userinfo"),
        "jwks_uri": _endpoint("jwks"),
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic"],
        "introspection_endpoint_auth_methods_supported": ["client_secret_basic"],
        "revocation_endpoint_auth_methods_supported": ["client_secret_basic"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": sorted(ALLOWED_SCOPES),
        "prompt_values_supported": ["login", "none", "consent"],
        "claims_supported": ["sub", "tenant_id", "name", "email", "email_verified", "nonce", "at_hash"],
        "authorization_response_iss_parameter_supported": True,
    }


def discovery() -> dict:
    """兼容旧导入路径的发现文档别名，新代码直接调用 discovery_document。"""
    return discovery_document()
