"""集中定义服务配置，避免路由和业务层各自读取环境变量。"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 这些值可由环境变量覆盖。生产密钥与数据库凭证不得写入代码仓库。
    app_name: str = "iam-api"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str | None = None
    jwt_secret: str = ""
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    oidc_issuer: str | None = None
    oidc_signing_key_path: str = "/run/iam-secrets/oidc-signing-key.pem"
    # 轮换重叠期额外发布并接受的旧/新公钥；未配置时维持单密钥行为。
    oidc_previous_signing_key_path: str | None = None
    console_public_url: str = "http://localhost:5175"
    allow_public_registration: bool = False
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    # 仅供受信任的模型网关上报用量；生产中由 Secret Manager 注入，不提供默认值。
    model_usage_api_key: str = ""
    # 配额预留执行默认关闭，必须在模型网关与故障策略验收后显式开启。
    model_quota_enforcement_enabled: bool = False
    # 邀请邮件默认关闭；启用后仅在管理员创建邀请时使用下方 SMTP 配置投递一次性链接。
    invitation_email_enabled: bool = False
    # 密码重置与可选邀请邮件共用 SMTP；不保存邮件服务密码到数据库。
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=30)
    password_reset_token_minutes: int = Field(default=30, ge=5, le=120)
    password_reset_cooldown_seconds: int = Field(default=60, ge=30, le=3600)
    # 注册 challenge、邮箱键与 OTP 使用独立稳定密钥，避免 JWT 签名密钥轮换使验证码失效。
    public_registration_secret: str = ""
    public_registration_code_minutes: int = Field(default=10, ge=3, le=30)
    public_registration_max_attempts: int = Field(default=5, ge=3, le=10)
    public_registration_cooldown_seconds: int = Field(default=60, ge=30, le=3600)
    public_registration_delivery_interval_seconds: int = Field(default=5, ge=1, le=60)
    # 登录失败计数只保留短期 HMAC 键；组合桶限制单账号/来源，来源桶限制单 IP 的批量猜测。
    login_attempt_window_seconds: int = Field(default=900, ge=60, le=86400)
    login_identifier_max_failures: int = Field(default=8, ge=3, le=100)
    login_ip_max_failures: int = Field(default=60, ge=10, le=1000)
    login_block_seconds: int = Field(default=900, ge=60, le=86400)
    # 只有生产 API 确认只能经 Caddy→Nginx 访问时，才信任代理重写的专用来源地址头。
    trust_proxy_client_ip: bool = False
    # 过期的一次性认证凭证由后台维护任务按周期回收；批次上限避免单次清理占用过久。
    credential_cleanup_interval_seconds: int = Field(default=3600, ge=60, le=86400)
    credential_cleanup_batch_size: int = Field(default=1000, ge=1, le=10000)
    cors_origins: list[str] = ["http://localhost:5173"]

    # 开发环境从 .env 读取；部署环境建议由运行平台注入环境变量。
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_non_development_configuration(self) -> "Settings":
        """阻止部署环境使用开发默认值或明文 HTTP issuer。"""
        if self.invitation_email_enabled and (not self.smtp_host or not self.smtp_from):
            raise ValueError("启用邀请邮件时必须同时配置 SMTP_HOST 与 SMTP_FROM")
        if self.allow_public_registration and len(self.public_registration_secret) < 32:
            raise ValueError("开放 ToC 自助注册必须配置至少 32 个字符的 PUBLIC_REGISTRATION_SECRET")
        if self.app_env == "development":
            return self

        if self.allow_public_registration:
            if not self.smtp_host or not self.smtp_from:
                raise ValueError("开放 ToC 自助注册必须配置 SMTP_HOST 与 SMTP_FROM")
        if not self.database_url:
            raise ValueError("DATABASE_URL 必须在非开发环境配置")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("非开发环境 DATABASE_URL 必须使用 PostgreSQL psycopg 3 驱动")
        if len(self.jwt_secret) < 32:
            raise ValueError("非开发环境 JWT_SECRET 至少需要 32 个字符")
        if not self.bootstrap_admin_email:
            raise ValueError("非开发环境必须配置 BOOTSTRAP_ADMIN_EMAIL 以限制平台管理员")

        smtp_configured = any((self.smtp_host, self.smtp_username, self.smtp_password, self.smtp_from))
        if smtp_configured and (not self.smtp_host or not self.smtp_from):
            raise ValueError("启用邮件投递时 SMTP_HOST 与 SMTP_FROM 必须同时配置")
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME 与 SMTP_PASSWORD 必须同时配置")
        if self.smtp_ssl and self.smtp_starttls:
            raise ValueError("SMTP_SSL 与 SMTP_STARTTLS 不能同时启用")
        if smtp_configured and not (self.smtp_ssl or self.smtp_starttls):
            raise ValueError("非开发环境 SMTP 必须使用 SSL 或 STARTTLS")

        # OIDC issuer 和登录控制台 URL 会进入发现文档与浏览器跳转，生产只接受 HTTPS 公网地址。
        for field_name, value in (("OIDC_ISSUER", self.oidc_issuer),
                                  ("CONSOLE_PUBLIC_URL", self.console_public_url)):
            try:
                parsed = urlsplit(value or "")
                # 访问 port 属性可让 urllib 校验损坏的 IPv6 bracket 或非数字端口。
                _ = parsed.port
                valid_https_url = (parsed.scheme == "https" and bool(parsed.hostname)
                                   and parsed.username is None and parsed.password is None
                                   and not parsed.query and not parsed.fragment)
            except ValueError:
                valid_https_url = False
            if not valid_https_url:
                raise ValueError(f"{field_name} 必须是 HTTPS 公网 URL")
        return self


@lru_cache
def get_settings() -> Settings:
    """进程内复用配置对象，避免每个请求重新解析环境变量。"""
    return Settings()
