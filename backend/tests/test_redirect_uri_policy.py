"""登录/登出回调 URI 的 scheme 放行策略：默认 HTTPS-only（localhost 例外），开关放行任意 http。

服务端间地址（Back-Channel Logout、模型网关 endpoint）不受开关影响，始终 HTTPS-only。
"""

import unittest
from unittest.mock import patch

from app.api.v1.admin.common import valid_login_redirect_uri, valid_redirect_uri
from app.core.config import Settings


def settings_with(allow_insecure: bool) -> Settings:
    return Settings(app_env="development", jwt_secret="j" * 32,
                    allow_insecure_redirect_uris=allow_insecure, _env_file=None)


class LoginRedirectUriPolicyTests(unittest.TestCase):
    def test_default_rejects_non_local_http(self) -> None:
        with patch("app.api.v1.admin.common.get_settings", return_value=settings_with(False)):
            self.assertFalse(valid_login_redirect_uri("http://192.168.1.10:3000/oidc/callback"))
            self.assertFalse(valid_login_redirect_uri("http://intranet.example.test/callback"))
            # 基线口径不受影响
            self.assertTrue(valid_login_redirect_uri("https://portal.example.test/callback"))
            self.assertTrue(valid_login_redirect_uri("http://localhost:3000/callback"))
            self.assertTrue(valid_login_redirect_uri("http://127.0.0.1:8080/callback"))

    def test_switch_allows_intranet_http_only(self) -> None:
        with patch("app.api.v1.admin.common.get_settings", return_value=settings_with(True)):
            self.assertTrue(valid_login_redirect_uri("http://192.168.1.10:3000/oidc/callback"))
            self.assertTrue(valid_login_redirect_uri("http://intranet.example.test/callback"))
            self.assertTrue(valid_login_redirect_uri("https://portal.example.test/callback"))

    def test_switch_never_relaxes_fragment_or_userinfo(self) -> None:
        with patch("app.api.v1.admin.common.get_settings", return_value=settings_with(True)):
            self.assertFalse(valid_login_redirect_uri("http://intranet.example.test/callback#frag"))
            self.assertFalse(valid_login_redirect_uri("http://user@intranet.example.test/callback"))
            self.assertFalse(valid_login_redirect_uri("http://user:pass@intranet.example.test/callback"))
            self.assertFalse(valid_login_redirect_uri("ftp://intranet.example.test/callback"))
            self.assertFalse(valid_login_redirect_uri("http:///no-host"))

    def test_server_to_server_uris_stay_https_only(self) -> None:
        """Back-Channel Logout / 模型网关地址不读开关：服务端间传输令牌必须保持 HTTPS。"""
        with patch("app.api.v1.admin.common.get_settings", return_value=settings_with(True)):
            self.assertFalse(valid_redirect_uri("http://192.168.1.10:3000/logout"))
            self.assertTrue(valid_redirect_uri("https://portal.example.test/logout"))
            self.assertTrue(valid_redirect_uri("http://localhost:3000/logout"))


if __name__ == "__main__":
    unittest.main()
