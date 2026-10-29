"""覆盖 OIDC 签名密钥重叠发布与旧令牌验证边界。"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from app.core import oidc_keys


class OidcKeyRotationTests(TestCase):
    """用标准库 unittest 验证密钥轮换，不为生产 API 镜像引入 pytest。"""

    def setUp(self) -> None:
        self.temp_directory = TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        oidc_keys.signing_private_key.cache_clear()
        oidc_keys.previous_signing_private_key.cache_clear()
        self.addCleanup(self._clear_key_cache)

    def _clear_key_cache(self) -> None:
        """恢复进程级缓存，避免某项测试的密钥配置影响后续测试。"""
        oidc_keys.signing_private_key.cache_clear()
        oidc_keys.previous_signing_private_key.cache_clear()

    def _path(self, name: str) -> Path:
        return Path(self.temp_directory.name) / name

    def _use_settings(self, active_path: Path, previous_path: Path | None) -> None:
        """注入当前测试密钥路径，不读取部署环境中的真实私钥。"""
        settings = SimpleNamespace(
            oidc_signing_key_path=str(active_path),
            oidc_previous_signing_key_path=str(previous_path) if previous_path else None,
            oidc_issuer="https://iam.example.test",
        )
        patcher = patch.object(oidc_keys, "get_settings", return_value=settings)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _write_private_key(path: Path) -> RSAPrivateKey:
        """生成独立 RSA 测试密钥并以 PKCS8 PEM 写入临时目录。"""
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        path.write_bytes(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        return private_key

    def test_jwks_publishes_both_keys_but_new_tokens_use_only_active_key(self) -> None:
        """轮换重叠期间发布新旧公钥，但新签名必须使用活动私钥。"""
        active_path = self._path("active.pem")
        previous_path = self._path("previous.pem")
        active_key = self._write_private_key(active_path)
        previous_key = self._write_private_key(previous_path)
        self._use_settings(active_path, previous_path)

        jwks = oidc_keys.public_jwks()
        keys_by_id = {key["kid"]: key for key in jwks["keys"]}
        active_id = oidc_keys.signing_key_id()
        previous_id = oidc_keys.signing_key_id_for(previous_key)

        self.assertEqual(set(keys_by_id), {active_id, previous_id})
        public_key_fields = {"kty", "use", "alg", "kid", "n", "e"}
        self.assertEqual(set(keys_by_id[active_id]), public_key_fields)
        self.assertEqual(set(keys_by_id[previous_id]), public_key_fields)

        token = oidc_keys.sign_jwt({
            "iss": "https://iam.example.test",
            "sub": "user-1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        })

        self.assertEqual(jwt.get_unverified_header(token)["kid"], active_id)
        self.assertNotEqual(
            active_key.public_key().public_numbers(),
            previous_key.public_key().public_numbers(),
        )

    def test_decoder_accepts_previous_key_by_kid_and_rejects_unknown_kid(self) -> None:
        """旧活动密钥进入重叠配置后仍可验签，未知 kid 一律拒绝。"""
        active_path = self._path("active.pem")
        previous_path = self._path("previous.pem")
        self._write_private_key(active_path)
        previous_key = self._write_private_key(previous_path)
        self._use_settings(active_path, previous_path)
        claims = {
            "iss": "https://iam.example.test",
            "sub": "user-1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        }

        previous_token = jwt.encode(
            claims,
            previous_key,
            algorithm="RS256",
            headers={"kid": oidc_keys.signing_key_id_for(previous_key)},
        )
        unknown_token = jwt.encode(claims, previous_key, algorithm="RS256", headers={"kid": "unknown-key"})

        self.assertEqual(oidc_keys.decode_oidc_jwt(previous_token)["sub"], "user-1")
        with self.assertRaisesRegex(jwt.InvalidTokenError, "未知|unknown|kid"):
            oidc_keys.decode_oidc_jwt(unknown_token)

    def test_single_key_configuration_keeps_the_existing_jwks_shape(self) -> None:
        """未配置备用密钥时继续只发布活动公钥。"""
        active_path = self._path("active.pem")
        self._write_private_key(active_path)
        self._use_settings(active_path, None)

        jwks = oidc_keys.public_jwks()

        self.assertEqual(len(jwks["keys"]), 1)
        self.assertEqual(jwks["keys"][0]["kid"], oidc_keys.signing_key_id())

    def test_invalid_configured_previous_key_fails_closed(self) -> None:
        """备用路径配置错误时不能悄悄退回单密钥模式。"""
        active_path = self._path("active.pem")
        self._write_private_key(active_path)
        self._use_settings(active_path, self._path("missing-previous.pem"))

        with self.assertRaisesRegex(RuntimeError, "私钥缺失或格式无效"):
            oidc_keys.public_jwks()
