"""登录主题配置白名单与字段边界；配置内容只允许数据值，不接受可执行样式。"""

import re
from urllib.parse import urlsplit


THEME_KEYS = frozenset({
    "logo_url", "background_url", "background_color", "primary_color", "title", "welcome_text",
    "layout", "card_position", "card_width", "card_radius", "show_register", "show_forgot_password",
    "terms_url", "privacy_url", "help_url", "background_position", "background_size",
    "background_overlay", "card_background_color", "card_opacity", "title_color", "text_color",
    "font_family", "logo_size", "card_shadow", "card_padding", "input_radius", "button_radius",
    "button_height",
})

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
ALLOWED_VALUES = {
    "layout": {"centered", "split", "banner"},
    "card_position": {"left", "center", "right"},
    "background_position": {"center", "top", "bottom", "left", "right"},
    "background_size": {"cover", "contain", "auto"},
    "font_family": {"system", "serif", "rounded"},
    "card_shadow": {"none", "soft", "medium", "strong"},
}
COLOR_KEYS = {"primary_color", "background_color", "card_background_color", "title_color", "text_color"}
INTEGER_RANGES = {
    "card_width": (320, 720),
    "card_radius": (0, 32),
    "background_overlay": (0, 70),
    "card_opacity": (60, 100),
    "logo_size": (32, 96),
    "card_padding": (12, 40),
    "input_radius": (0, 24),
    "button_radius": (0, 24),
    "button_height": (40, 60),
}
BOOLEAN_KEYS = {"show_register", "show_forgot_password"}
TEXT_LIMITS = {"title": 120, "welcome_text": 300}
ASSET_KEYS = {"logo_url", "background_url", "terms_url", "privacy_url", "help_url"}


def valid_asset_url(value: str) -> bool:
    """仅接受空值、HTTPS 外链或单斜线站内地址，阻止 CSS 字符串逃逸。"""
    if value == "":
        # 可选素材清空是合法操作；旧实现拒绝空值，导致默认主题无法保存。
        return True
    if len(value) > 2048:
        return False
    if value != value.strip() or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        return False
    if any(char in value for char in ('\\', '"', "'", "<", ">")):
        return False
    try:
        parsed = urlsplit(value)
        # 访问 port 也会验证 malformed port，且拒绝用户名/密码避免把凭据嵌进地址。
        _ = parsed.port
        if parsed.scheme == "https":
            return (value.lower().startswith("https://") and bool(parsed.hostname)
                    and not parsed.username and not parsed.password and not parsed.fragment)
        return (value.startswith("/") and not value.startswith("//") and not parsed.netloc
                and not parsed.scheme and not parsed.fragment)
    except ValueError:
        return False


def validate_theme_config(config: dict) -> None:
    """验证存入主题 JSON 的所有键和值，禁止把动态 CSS/HTML 当成主题字段。"""
    unknown = set(config) - THEME_KEYS
    if unknown:
        raise ValueError("主题包含不支持的配置项")

    for key in COLOR_KEYS & config.keys():
        if not isinstance(config[key], str) or not HEX_COLOR.fullmatch(config[key]):
            raise ValueError(f"{key} 必须是六位十六进制颜色")

    for key, choices in ALLOWED_VALUES.items():
        if key in config and (not isinstance(config[key], str) or config[key] not in choices):
            raise ValueError(f"{key} 只能使用预设选项")

    for key, (minimum, maximum) in INTEGER_RANGES.items():
        if key in config and (type(config[key]) is not int or not minimum <= config[key] <= maximum):
            raise ValueError(f"{key} 必须是 {minimum} 至 {maximum} 之间的整数")

    for key in BOOLEAN_KEYS:
        if key in config and type(config[key]) is not bool:
            raise ValueError(f"{key} 必须是布尔值")

    for key, limit in TEXT_LIMITS.items():
        if key in config and (not isinstance(config[key], str) or len(config[key]) > limit):
            raise ValueError(f"{key} 文案长度无效")

    for key in ASSET_KEYS & config.keys():
        if not isinstance(config[key], str) or not valid_asset_url(config[key]):
            raise ValueError(f"{key} 仅支持空值、HTTPS 或站内路径")
