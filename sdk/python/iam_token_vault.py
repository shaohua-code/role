"""Authenticated encryption helpers for server-side IAM OIDC token vaults.

This module only encrypts/decrypts token strings. Callers own persistence,
rotation, revocation, expiry, and access control. Plaintext tokens are never
cached or logged, and the authenticated context prevents ciphertext from being
copied between issuers, users, tenants, or token purposes.

Install the ``oidc`` extra (``PyJWT[crypto]``) to provide the AES-GCM backend.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Final

_VERSION: Final[str] = "v1"
_NONCE_BYTES: Final[int] = 12
_KEY_BYTES: Final[int] = 32
_MAX_TOKEN_BYTES: Final[int] = 16_384
_MAX_ENVELOPE_CHARS: Final[int] = 32_768
_TOKEN_PURPOSES: Final[frozenset[str]] = frozenset({"access_token", "refresh_token", "id_token"})
_CONTEXT_RE: Final[re.Pattern[str]] = re.compile(r"^[^\x00\r\n]{1,512}$")


class TokenVaultError(ValueError):
    """The key, envelope, or authenticated token context is invalid."""


class IamTokenVaultCipher:
    """AES-256-GCM envelope cipher for OIDC tokens kept by a backend service."""

    __slots__ = ("_aesgcm",)

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) != _KEY_BYTES:
            raise ValueError("IAM token-vault key must contain exactly 32 raw bytes")
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            raise RuntimeError("Install the IAM SDK 'oidc' extra to use AES-GCM token encryption") from None
        self._aesgcm = AESGCM(key)

    def __repr__(self) -> str:
        return "IamTokenVaultCipher(<redacted>)"

    @staticmethod
    def _associated_data(*, issuer: str, subject: str, tenant_id: str, token_type: str) -> bytes:
        values = (issuer, subject, tenant_id, token_type)
        if any(not isinstance(value, str) or not _CONTEXT_RE.fullmatch(value) for value in values):
            raise TokenVaultError("IAM token-vault context is incomplete or invalid")
        if token_type not in _TOKEN_PURPOSES:
            raise TokenVaultError("IAM token-vault token type is invalid")
        # JSON array encoding is deterministic and avoids delimiter ambiguity.
        return json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode("ascii")

    def encrypt(
        self,
        token: str,
        *,
        issuer: str,
        subject: str,
        tenant_id: str,
        token_type: str,
    ) -> str:
        """Return a versioned URL-safe envelope; callers should persist only this value."""
        if not isinstance(token, str) or not token:
            raise TokenVaultError("IAM token is empty or exceeds the supported size")
        try:
            plaintext = token.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise TokenVaultError("IAM token is not valid UTF-8") from None
        if len(plaintext) > _MAX_TOKEN_BYTES:
            raise TokenVaultError("IAM token is empty or exceeds the supported size")
        aad = self._associated_data(
            issuer=issuer, subject=subject, tenant_id=tenant_id, token_type=token_type,
        )
        import secrets

        nonce = secrets.token_bytes(_NONCE_BYTES)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, aad)
        encoded = base64.urlsafe_b64encode(nonce + ciphertext).rstrip(b"=").decode("ascii")
        return f"{_VERSION}.{encoded}"

    def decrypt(
        self,
        envelope: str,
        *,
        issuer: str,
        subject: str,
        tenant_id: str,
        token_type: str,
    ) -> str:
        """Decrypt one envelope only when its full trusted identity context matches."""
        if (not isinstance(envelope, str) or len(envelope) > _MAX_ENVELOPE_CHARS
                or not envelope.startswith(f"{_VERSION}.")):
            raise TokenVaultError("IAM token-vault envelope is malformed or unsupported")
        aad = self._associated_data(
            issuer=issuer, subject=subject, tenant_id=tenant_id, token_type=token_type,
        )
        encoded = envelope[len(_VERSION) + 1:]
        if not encoded or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
            raise TokenVaultError("IAM token-vault envelope is malformed or unsupported")
        padded = encoded + "=" * (-len(encoded) % 4)
        try:
            combined = base64.b64decode(padded, altchars=b"-_", validate=True)
        except (binascii.Error, ValueError):
            raise TokenVaultError("IAM token-vault envelope is malformed or unsupported") from None
        if len(combined) <= _NONCE_BYTES + 16:
            raise TokenVaultError("IAM token-vault envelope is malformed or unsupported")
        nonce, ciphertext = combined[:_NONCE_BYTES], combined[_NONCE_BYTES:]
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, aad)
            token = plaintext.decode("utf-8", errors="strict")
        except Exception:
            # Do not expose cryptographic details or any token-bearing input.
            raise TokenVaultError("IAM token-vault authentication failed") from None
        if not token or len(plaintext) > _MAX_TOKEN_BYTES:
            raise TokenVaultError("IAM token-vault plaintext is invalid")
        return token
