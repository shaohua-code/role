"""登录主题 JSON 的纯标准库校验用例，不需要启动 API 或数据库。"""

import unittest

from app.services.theme_config import valid_asset_url, validate_theme_config


class ThemeConfigTests(unittest.TestCase):
    def test_default_theme_with_empty_optional_assets_is_valid(self) -> None:
        validate_theme_config({
            "title": "欢迎登录",
            "primary_color": "#756df2",
            "background_color": "#f5f6fa",
            "logo_url": "",
            "background_url": "",
            "layout": "centered",
            "card_position": "center",
            "card_width": 420,
            "card_radius": 16,
            "show_register": False,
            "show_forgot_password": True,
        })

    def test_style_presets_colors_and_dimensions_accept_boundaries(self) -> None:
        validate_theme_config({
            "background_position": "top",
            "background_size": "contain",
            "background_overlay": 70,
            "card_background_color": "#ffffff",
            "card_opacity": 60,
            "title_color": "#111827",
            "text_color": "#334155",
            "font_family": "rounded",
            "logo_size": 96,
            "card_shadow": "strong",
            "card_padding": 40,
            "input_radius": 24,
            "button_radius": 24,
            "button_height": 60,
        })

    def test_rejects_raw_css_unknown_keys_and_unlisted_preset_values(self) -> None:
        for config in (
            {"custom_css": "body { display:none }"},
            {"font_family": "url(javascript:alert(1))"},
            {"card_shadow": "0 0 0 red"},
            {"background_position": "center;display:none"},
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_theme_config(config)

    def test_integer_fields_reject_boolean_and_out_of_range_values(self) -> None:
        for value in (True, -1, 71):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_theme_config({"background_overlay": value})

    def test_asset_urls_allow_blank_https_and_local_paths_only(self) -> None:
        self.assertTrue(valid_asset_url(""))
        self.assertTrue(valid_asset_url("https://assets.example.test/logo.svg"))
        self.assertTrue(valid_asset_url("/assets/login-bg.jpg"))
        for value in (
            "//evil.example/image.png",
            "data:image/svg+xml,<svg>",
            "javascript:alert(1)",
            "https://user:password@example.test/logo.svg",
            'https://example.test/\\");background:red/*',
            "https://example.test/logo.svg#fragment",
        ):
            with self.subTest(value=value):
                self.assertFalse(valid_asset_url(value))


if __name__ == "__main__":
    unittest.main()
