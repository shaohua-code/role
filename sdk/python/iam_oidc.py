"""服务端 IAM OIDC relying-party 客户端；浏览器绝不接触客户端秘密或刷新令牌。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass, field
from time import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

import jwt


class OIDCProtocolError(RuntimeError):
    """OIDC Provider、回调或令牌无法通过校验；不得将失败转换为登录成功。"""


@dataclass(frozen=True)
class AuthorizationAttempt:
    """一次登录所需的随机状态；调用方必须将对象保存在服务端会话中。"""

    authorization_url: str = field(repr=False)
    state: str = field(repr=False)
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TokenSet:
    """服务端会话令牌；repr 隐藏全部 Bearer/refresh 凭证，避免日志误泄漏。"""

    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    id_token: str = field(default="", repr=False)
    expires_at: int = 0
    scope: tuple[str, ...] = ()


@dataclass(frozen=True)
class OIDCIdentity:
    """已验证的 IAM 用户主体与租户上下文，适合写入服务端 session。"""

    subject: str
    tenant_id: str
    profile: dict[str, Any] = field(repr=False)
    tokens: TokenSet = field(repr=False)


@dataclass(frozen=True)
class EndSessionRequest:
    """浏览器顶层退出跳转；URL 含 ID Token Hint，应从代理访问日志中脱敏。"""

    url: str = field(repr=False)
    method: str
    state: str = field(repr=False)


class _RejectRedirects(HTTPRedirectHandler):
    """阻止 token endpoint 通过 30x 把 HTTP Basic 凭证转发到其他位置。"""

    def redirect_request(self, request: Request, file: Any, code: int, message: str,
                         headers: Any, new_url: str) -> None:
        return None


class IamOIDCClient:
    """面向 IAM Provider 的同步 OIDC 客户端，供后端 route/worker 调用。

    调用方把 ``AuthorizationAttempt`` 放入服务端 session 并用 HttpOnly cookie
    绑定浏览器；回调时先从 session 取出并删除该尝试，再调用 complete_login。
    本类不负责 session/Cookie 存储，也绝不适合在 Vue/React 浏览器代码中使用。
    """

    _VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
    _MAX_RESPONSE_BYTES = 1_048_576

    def __init__(self, issuer: str, client_id: str, client_secret: str,
                 redirect_uri: str, *, timeout_seconds: float = 5.0) -> None:
        if not client_id or not client_secret or not redirect_uri:
            raise ValueError("OIDC client id, secret, and redirect URI are required")
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self._client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener(_RejectRedirects())
        self._metadata_cache: dict[str, Any] | None = None
        self._jwks_client: Any | None = None

        # Issuer 是运维配置，不允许误把客户端秘密发往不受保护的远端 HTTP 服务。
        self._validate_url(self.issuer, "issuer")
        self._validate_url(self.redirect_uri, "redirect URI")

    def create_authorization_request(self, scopes: tuple[str, ...] = ("openid", "profile", "email"),
                                     prompt: str | None = None) -> AuthorizationAttempt:
        """生成独立随机 state/nonce 和 S256 verifier，并构造 IAM 授权地址。"""
        if "openid" not in scopes or len(set(scopes)) != len(scopes):
            raise ValueError("OIDC scopes must include openid and contain no duplicates")
        if prompt not in (None, "login", "none", "consent"):
            raise ValueError("Unsupported IAM OIDC prompt")
        metadata = self._get_metadata()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = self._b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        parameters = {
            "response_type": "code", "client_id": self.client_id,
            "redirect_uri": self.redirect_uri, "scope": " ".join(scopes),
            "state": state, "nonce": nonce, "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if prompt:
            parameters["prompt"] = prompt
        separator = "&" if "?" in metadata["authorization_endpoint"] else "?"
        return AuthorizationAttempt(
            authorization_url=metadata["authorization_endpoint"] + separator + urlencode(parameters),
            state=state, nonce=nonce, code_verifier=verifier, scopes=tuple(scopes),
        )

    def complete_login(self, callback_url: str, attempt: AuthorizationAttempt) -> OIDCIdentity:
        """校验授权回调、兑换一次性 code、验签 token 并核实 UserInfo subject。"""
        callback = urlsplit(callback_url)
        configured_callback = urlsplit(self.redirect_uri)
        if (self._origin(callback_url) != self._origin(self.redirect_uri)
                or callback.path != configured_callback.path or callback.fragment):
            raise OIDCProtocolError("OIDC callback URL does not match the configured redirect URI")
        query = self._single_query(callback.query)
        returned_state = query.get("state", "")
        if not returned_state or not hmac.compare_digest(returned_state, attempt.state):
            raise OIDCProtocolError("OIDC callback state is missing or invalid")

        metadata = self._get_metadata()
        returned_issuer = query.get("iss")
        if metadata.get("authorization_response_iss_parameter_supported") is True and returned_issuer != self.issuer:
            raise OIDCProtocolError("OIDC callback issuer is missing or invalid")
        if returned_issuer is not None and returned_issuer != self.issuer:
            raise OIDCProtocolError("OIDC callback issuer is invalid")
        if query.get("error"):
            # 错误描述不回显到客户端或日志，避免将未可信 Provider 文本传播到 UI。
            raise OIDCProtocolError("IAM did not authorize this login")
        code = query.get("code", "")
        if not code:
            raise OIDCProtocolError("OIDC callback has no authorization code")

        response = self._post_form(metadata["token_endpoint"], {
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": self.redirect_uri, "code_verifier": attempt.code_verifier,
        })
        access_token = response.get("access_token")
        id_token = response.get("id_token")
        if not isinstance(access_token, str) or not access_token or not isinstance(id_token, str) or not id_token:
            raise OIDCProtocolError("IAM token response is incomplete")
        token_type = response.get("token_type")
        if not isinstance(token_type, str) or token_type.casefold() != "bearer":
            raise OIDCProtocolError("IAM token response has an unsupported token type")
        try:
            id_claims = self._verify_jwt(id_token, metadata, require_nonce=attempt.nonce,
                                         access_token=access_token)
            access_claims = self._verify_jwt(access_token, metadata)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise OIDCProtocolError("IAM returned an invalid signed token") from exc

        # IAM 使用签名 access token 固定租户/app 上下文；这些字段不能从浏览器请求体中取得。
        if id_claims.get("sub") != access_claims.get("sub"):
            raise OIDCProtocolError("ID token and access token subjects do not match")
        if access_claims.get("token_use") != "access_token" or access_claims.get("client_id") != self.client_id:
            raise OIDCProtocolError("IAM access token has an invalid purpose or client")
        try:
            tenant_id = str(UUID(str(access_claims["tenant_id"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise OIDCProtocolError("IAM access token has no valid tenant context") from exc
        # The signed access token remains authoritative for the tenant. When the
        # Provider also supplies tenant_id in the ID Token, reject disagreement
        # instead of letting two signed assertions describe different tenants.
        id_tenant_claim = id_claims.get("tenant_id")
        if id_tenant_claim is not None:
            try:
                id_tenant_id = str(UUID(str(id_tenant_claim)))
            except (TypeError, ValueError) as exc:
                raise OIDCProtocolError("IAM ID token has an invalid tenant context") from exc
            if id_tenant_id != tenant_id:
                raise OIDCProtocolError("IAM ID token and access token tenants do not match")

        profile = self._get_userinfo(metadata["userinfo_endpoint"], access_token, str(id_claims["sub"]))
        try:
            expires_in = int(response["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OIDCProtocolError("IAM token response has no valid expiry") from exc
        if isinstance(response.get("expires_in"), bool) or expires_in <= 0 or expires_in > 31_536_000:
            raise OIDCProtocolError("IAM token response has expired")
        raw_scope = response.get("scope", "")
        if not isinstance(raw_scope, str):
            raise OIDCProtocolError("IAM token response has an invalid scope")
        granted_scopes = tuple(raw_scope.split())
        if "openid" not in granted_scopes or not set(granted_scopes).issubset(set(attempt.scopes)):
            raise OIDCProtocolError("IAM returned scopes outside the original authorization request")
        refresh = response.get("refresh_token")
        if refresh is not None and not isinstance(refresh, str):
            raise OIDCProtocolError("IAM token response has an invalid refresh token")
        tokens = TokenSet(access_token=access_token, refresh_token=refresh, id_token=id_token,
                          expires_at=int(time()) + expires_in, scope=granted_scopes)
        return OIDCIdentity(subject=str(id_claims["sub"]), tenant_id=tenant_id,
                            profile=profile, tokens=tokens)

    def refresh(self, identity: OIDCIdentity) -> OIDCIdentity:
        """用服务端 refresh token 换取新 token，并要求 IAM 完成 refresh rotation。"""
        previous_refresh = identity.tokens.refresh_token
        if not previous_refresh:
            raise OIDCProtocolError("This IAM session has no refresh token")
        metadata = self._get_metadata()
        response = self._post_form(metadata["token_endpoint"], {
            "grant_type": "refresh_token", "refresh_token": previous_refresh,
        })
        access_token, id_token = response.get("access_token"), response.get("id_token")
        next_refresh = response.get("refresh_token")
        if not isinstance(access_token, str) or not access_token or not isinstance(id_token, str) or not id_token:
            raise OIDCProtocolError("IAM refresh response is incomplete")
        if not isinstance(next_refresh, str) or not next_refresh or hmac.compare_digest(next_refresh, previous_refresh):
            raise OIDCProtocolError("IAM refresh token rotation did not occur")
        token_type = response.get("token_type")
        if not isinstance(token_type, str) or token_type.casefold() != "bearer":
            raise OIDCProtocolError("IAM refresh response has an unsupported token type")
        try:
            id_claims = self._verify_jwt(id_token, metadata, access_token=access_token)
            access_claims = self._verify_jwt(access_token, metadata)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise OIDCProtocolError("IAM refresh response contains invalid signed tokens") from exc
        if id_claims.get("sub") != identity.subject or access_claims.get("sub") != identity.subject:
            raise OIDCProtocolError("IAM refresh changed the authenticated subject")
        if access_claims.get("token_use") != "access_token" or access_claims.get("client_id") != self.client_id:
            raise OIDCProtocolError("IAM refresh returned a token for another purpose or client")
        try:
            tenant_id = str(UUID(str(access_claims["tenant_id"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise OIDCProtocolError("IAM refresh token has no valid tenant context") from exc
        if tenant_id != identity.tenant_id:
            raise OIDCProtocolError("IAM refresh changed the authenticated tenant")
        id_tenant_claim = id_claims.get("tenant_id")
        if id_tenant_claim is not None:
            try:
                id_tenant_id = str(UUID(str(id_tenant_claim)))
            except (TypeError, ValueError) as exc:
                raise OIDCProtocolError("IAM refresh ID token has an invalid tenant context") from exc
            if id_tenant_id != tenant_id:
                raise OIDCProtocolError("IAM refresh ID token and access token tenants do not match")
        raw_scope = response.get("scope", " ".join(identity.tokens.scope))
        if not isinstance(raw_scope, str):
            raise OIDCProtocolError("IAM refresh response has an invalid scope")
        scopes = tuple(raw_scope.split())
        if not set(scopes).issubset(set(identity.tokens.scope)):
            raise OIDCProtocolError("IAM refresh widened the original granted scopes")
        try:
            expires_in = int(response["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OIDCProtocolError("IAM refresh response has no valid expiry") from exc
        if isinstance(response.get("expires_in"), bool) or not 0 < expires_in <= 31_536_000:
            raise OIDCProtocolError("IAM refresh response has expired")
        profile = self._get_userinfo(metadata["userinfo_endpoint"], access_token, identity.subject)
        tokens = TokenSet(access_token=access_token, refresh_token=next_refresh, id_token=id_token,
                          expires_at=int(time()) + expires_in, scope=scopes)
        return OIDCIdentity(subject=identity.subject, tenant_id=identity.tenant_id,
                            profile=profile, tokens=tokens)

    def _revoke_token(self, token: str, token_type_hint: str) -> None:
        """使用 confidential client Basic 认证撤销指定的一种 access/refresh 凭证。"""
        if not token:
            return
        metadata = self._get_metadata()
        endpoint = metadata.get("revocation_endpoint")
        if not isinstance(endpoint, str):
            raise OIDCProtocolError("IAM does not advertise a token revocation endpoint")
        encoded_id = urlencode({"value": self.client_id})[6:]
        encoded_secret = urlencode({"value": self._client_secret})[6:]
        credentials = base64.b64encode(f"{encoded_id}:{encoded_secret}".encode("ascii")).decode("ascii")
        request = Request(endpoint, data=urlencode({
            "token": token, "token_type_hint": token_type_hint,
        }).encode("ascii"), method="POST", headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                # RFC 7009 成功时允许空 body；只消费有限响应以释放连接。
                response.read(self._MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise OIDCProtocolError(f"IAM revocation endpoint returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise OIDCProtocolError("IAM revocation endpoint is unavailable") from exc

    def revoke_refresh_token(self, refresh_token: str) -> None:
        """退出应用时调用 RFC 7009 endpoint 撤销服务端保存的刷新凭证。"""
        self._revoke_token(refresh_token, "refresh_token")

    def revoke_access_token(self, access_token: str) -> None:
        """退出/权限收回时立即撤销当前 access token；离线验证方仍需等令牌过期。"""
        self._revoke_token(access_token, "access_token")

    def introspect_token(self, token: str, token_type_hint: str | None = None) -> dict[str, Any]:
        """用 client_secret_basic 查询本 client token 的实时状态；异常时抛错而不放行。"""
        if not token or len(token) > 8192:
            raise ValueError("token must be a non-empty credential no longer than 8192 characters")
        if token_type_hint not in (None, "access_token", "refresh_token"):
            raise ValueError("token_type_hint must be access_token or refresh_token")
        metadata = self._get_metadata()
        endpoint = metadata.get("introspection_endpoint")
        if not isinstance(endpoint, str):
            raise OIDCProtocolError("IAM does not advertise a token introspection endpoint")
        encoded_id = urlencode({"value": self.client_id})[6:]
        encoded_secret = urlencode({"value": self._client_secret})[6:]
        credentials = base64.b64encode(f"{encoded_id}:{encoded_secret}".encode("ascii")).decode("ascii")
        form = {"token": token}
        if token_type_hint:
            form["token_type_hint"] = token_type_hint
        request = Request(endpoint, data=urlencode(form).encode("ascii"), method="POST", headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
        payload = self._open_json(request)
        if not isinstance(payload.get("active"), bool):
            raise OIDCProtocolError("IAM returned an invalid token introspection response")
        if not payload["active"]:
            return {"active": False}
        if (payload.get("client_id") != self.client_id or payload.get("iss") != self.issuer
                or not isinstance(payload.get("sub"), str)
                or not isinstance(payload.get("scope"), str)
                or not isinstance(payload.get("tenant_id"), str)
                or isinstance(payload.get("exp"), bool) or not isinstance(payload.get("exp"), int)
                or isinstance(payload.get("iat"), bool) or not isinstance(payload.get("iat"), int)):
            raise OIDCProtocolError("IAM returned active token metadata for an unexpected client or issuer")
        return payload

    def create_end_session_request(self, identity: OIDCIdentity,
                                   post_logout_redirect_uri: str) -> EndSessionRequest:
        """生成浏览器 POST 表单并返回 state，调用方须将 state 保存到服务端 session。"""
        id_token_hint = identity.tokens.id_token
        if not id_token_hint:
            raise OIDCProtocolError("This IAM session has no ID token for logout")
        # 退出回调是 RP 本地配置；Provider 仍会独立按该 client 的登记白名单验证。
        self._validate_url(post_logout_redirect_uri, "post-logout redirect URI")
        metadata = self._get_metadata()
        endpoint = metadata.get("end_session_endpoint")
        if not isinstance(endpoint, str):
            raise OIDCProtocolError("IAM does not advertise an end-session endpoint")
        state = secrets.token_urlsafe(32)
        url = endpoint + ("&" if "?" in endpoint else "?") + urlencode({
            "id_token_hint": id_token_hint,
            "post_logout_redirect_uri": post_logout_redirect_uri,
            "state": state,
        })
        return EndSessionRequest(url=url, method="GET", state=state)

    def _get_metadata(self) -> dict[str, Any]:
        """只信任同一 HTTPS issuer 发布的 endpoint，阻断错误配置引发的凭证外送。"""
        if self._metadata_cache is not None:
            return self._metadata_cache
        discovery_url = self.issuer + "/.well-known/openid-configuration"
        metadata = self._open_json(Request(discovery_url, headers={"Accept": "application/json"}))
        if metadata.get("issuer") != self.issuer:
            raise OIDCProtocolError("OIDC discovery issuer does not match configuration")
        for field_name in ("authorization_endpoint", "token_endpoint", "userinfo_endpoint", "introspection_endpoint", "jwks_uri",
                           "revocation_endpoint", "end_session_endpoint"):
            endpoint = metadata.get(field_name)
            if not isinstance(endpoint, str):
                raise OIDCProtocolError("OIDC discovery metadata is incomplete")
            self._validate_url(endpoint, field_name)
            if self._origin(endpoint) != self._origin(self.issuer):
                raise OIDCProtocolError("OIDC endpoint is outside the configured issuer origin")
        if "client_secret_basic" not in metadata.get("token_endpoint_auth_methods_supported", []):
            raise OIDCProtocolError("IAM does not advertise client_secret_basic")
        if "RS256" not in metadata.get("id_token_signing_alg_values_supported", []):
            raise OIDCProtocolError("IAM does not advertise RS256 signing")
        if "code" not in metadata.get("response_types_supported", []):
            raise OIDCProtocolError("IAM does not advertise authorization code flow")
        if "authorization_code" not in metadata.get("grant_types_supported", []):
            raise OIDCProtocolError("IAM does not advertise authorization_code grant")
        if "S256" not in metadata.get("code_challenge_methods_supported", []):
            raise OIDCProtocolError("IAM does not advertise PKCE S256")
        self._metadata_cache = metadata
        return metadata

    def _verify_jwt(self, raw_token: str, metadata: dict[str, Any],
                    require_nonce: str | None = None,
                    access_token: str | None = None) -> dict[str, Any]:
        """固定 RS256、issuer、audience 和必要 claims 后再读取主体/租户字段。"""
        header = jwt.get_unverified_header(raw_token)
        if header.get("alg") != "RS256":
            raise OIDCProtocolError("Only RS256 tokens are accepted")
        if self._jwks_client is None:
            # JWKS URI 已通过 discovery 同源校验；PyJWT 验证签名时不会信任 token 自带的 key URL。
            from jwt import PyJWKClient

            self._jwks_client = PyJWKClient(metadata["jwks_uri"], timeout=self.timeout_seconds)
        key = self._jwks_client.get_signing_key_from_jwt(raw_token).key
        claims = jwt.decode(
            raw_token, key, algorithms=["RS256"], audience=self.client_id, issuer=self.issuer,
            options={"require": ["iss", "sub", "aud", "exp", "iat"]},
        )
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise OIDCProtocolError("OIDC subject is missing")
        authorized_party = claims.get("azp")
        if authorized_party is not None and authorized_party != self.client_id:
            raise OIDCProtocolError("OIDC authorized party does not match this client")
        if require_nonce is not None:
            nonce = claims.get("nonce")
            if not isinstance(nonce, str) or not hmac.compare_digest(nonce, require_nonce):
                raise OIDCProtocolError("OIDC nonce is missing or invalid")
        at_hash = claims.get("at_hash")
        if at_hash is not None:
            # Provider 在 code flow 返回 at_hash 时必须与同一次 token response 的 access token 对应。
            if access_token is None:
                raise OIDCProtocolError("ID token at_hash has no matching access token")
            expected_at_hash = self._b64url(hashlib.sha256(access_token.encode("ascii")).digest()[:16])
            if not isinstance(at_hash, str) or not hmac.compare_digest(at_hash, expected_at_hash):
                raise OIDCProtocolError("ID token at_hash does not match the access token")
        return claims

    def _get_userinfo(self, endpoint: str, access_token: str, expected_subject: str) -> dict[str, Any]:
        """用 Bearer access token 取 profile，且要求 UserInfo sub 与 ID token 完全相同。"""
        request = Request(endpoint, headers={"Authorization": f"Bearer {access_token}",
                                             "Accept": "application/json"})
        profile = self._open_json(request)
        if profile.get("sub") != expected_subject:
            raise OIDCProtocolError("OIDC UserInfo subject does not match the ID token")
        return profile

    def _post_form(self, endpoint: str, values: dict[str, str]) -> dict[str, Any]:
        """只向已验证的 token endpoint 发送 RFC 6749 Basic auth 与短期 code。"""
        encoded_id = urlencode({"value": self.client_id})[6:]
        encoded_secret = urlencode({"value": self._client_secret})[6:]
        credentials = base64.b64encode(f"{encoded_id}:{encoded_secret}".encode("ascii")).decode("ascii")
        request = Request(endpoint, data=urlencode(values).encode("ascii"), method="POST", headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
        return self._open_json(request)

    def _open_json(self, request: Request) -> dict[str, Any]:
        """限时、限大小读取 JSON；错误不包含响应 body，避免泄漏令牌或未可信内容。"""
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(self._MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise OIDCProtocolError(f"OIDC endpoint returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise OIDCProtocolError("OIDC endpoint is unavailable") from exc
        if len(raw) > self._MAX_RESPONSE_BYTES:
            raise OIDCProtocolError("OIDC endpoint response is too large")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OIDCProtocolError("OIDC endpoint returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise OIDCProtocolError("OIDC endpoint returned an invalid response")
        return body

    @staticmethod
    def _single_query(query: str) -> dict[str, str]:
        """拒绝重复 query 参数，避免代理、框架与应用对 state/code 解析不一致。"""
        from urllib.parse import parse_qs

        values = parse_qs(query, keep_blank_values=True, strict_parsing=False)
        if any(len(items) != 1 for items in values.values()):
            raise OIDCProtocolError("OIDC callback contains duplicated parameters")
        return {key: items[0] for key, items in values.items()}

    @staticmethod
    def _origin(url: str) -> tuple[str, str, int | None]:
        parsed = urlsplit(url)
        default_port = 443 if parsed.scheme == "https" else 80
        return parsed.scheme, (parsed.hostname or "").lower(), parsed.port or default_port

    @staticmethod
    def _validate_url(url: str, label: str) -> None:
        parsed = urlsplit(url)
        local_http = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and local_http):
            raise ValueError(f"{label} must use HTTPS (HTTP is allowed only for localhost development)")
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError(f"{label} is not a valid absolute URL")

    @staticmethod
    def _b64url(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
