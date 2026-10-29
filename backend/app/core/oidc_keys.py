"""RS256 OIDC 签名、JWKS 发布与验证。

非对称私钥只能从部署挂载路径读取；公钥以 JWKS 发布。访问令牌和 ID Token
固定只接受 RS256，避免同一验证入口混用对称/非对称算法。
"""

import base64
import hashlib
from functools import lru_cache
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.core.config import get_settings


def _b64url_integer(value: int) -> str:
    """把 RSA 公钥大整数编码为 RFC 7518 JWK 所需的无填充 base64url。"""
    length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(length, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _load_rsa_private_key(path: str) -> RSAPrivateKey:
    """加载并校验部署挂载的 RSA 私钥，不把底层路径或 PEM 写进日志。"""
    try:
        key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError("OIDC 签名私钥缺失或格式无效") from exc
    if not isinstance(key, RSAPrivateKey) or key.key_size < 2048:
        raise RuntimeError("OIDC 私钥必须是至少 2048 位 RSA 密钥")
    return key


@lru_cache(maxsize=1)
def signing_private_key() -> RSAPrivateKey:
    """读取活动签名私钥；进程缓存要求轮换配置变更后重启 API。"""
    return _load_rsa_private_key(get_settings().oidc_signing_key_path)


@lru_cache(maxsize=1)
def previous_signing_private_key() -> RSAPrivateKey | None:
    """加载轮换重叠期的备用私钥；若配置路径损坏则拒绝静默降级。"""
    path = get_settings().oidc_previous_signing_key_path
    return _load_rsa_private_key(path) if path else None


def signing_key_id_for(key: RSAPrivateKey) -> str:
    """使用公钥 DER 摘要标识密钥版本，不暴露私钥材料。"""
    public_der = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(public_der).hexdigest()[:32]


def signing_key_id() -> str:
    """返回活动签名密钥的稳定 kid。"""
    return signing_key_id_for(signing_private_key())


def _verification_public_keys() -> dict[str, RSAPublicKey]:
    """按 kid 构建活动/备用公钥表；活动密钥优先处理重复密钥文件。"""
    active = signing_private_key()
    keys = {signing_key_id_for(active): active.public_key()}
    previous = previous_signing_private_key()
    if previous is not None:
        keys.setdefault(signing_key_id_for(previous), previous.public_key())
    return keys


def sign_jwt(claims: dict, token_type: str = "JWT") -> str:
    """统一 RS256 签名并固定 kid、typ，所有 claims 由服务端构造。"""
    return jwt.encode(
        claims,
        signing_private_key(),
        algorithm="RS256",
        headers={"kid": signing_key_id(), "typ": token_type},
    )


def public_jwks() -> dict[str, list[dict[str, str]]]:
    """只发布活动/备用公钥的 modulus/exponent，不返回任何私密字段。"""
    keys = []
    for kid, public_key in _verification_public_keys().items():
        numbers = public_key.public_numbers()
        keys.append({
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": kid,
            "n": _b64url_integer(numbers.n),
            "e": _b64url_integer(numbers.e),
        })
    return {"keys": keys}


def decode_oidc_jwt(token: str, *, audience: str | None = None, verify_exp: bool = True) -> dict:
    """仅按 token 的 kid 选择本服务 RS256 公钥；未知密钥与算法均拒绝。"""
    settings = get_settings()
    if not settings.oidc_issuer:
        raise RuntimeError("OIDC_ISSUER 尚未配置")
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    if not isinstance(kid, str) or not kid:
        raise jwt.InvalidTokenError("OIDC Token 缺少 kid")
    public_key = _verification_public_keys().get(kid)
    if public_key is None:
        raise jwt.InvalidTokenError("OIDC Token 使用未知 kid")
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        issuer=settings.oidc_issuer.rstrip("/"),
        options={"verify_exp": verify_exp, **({} if audience else {"verify_aud": False})},
        **({"audience": audience} if audience else {}),
    )
