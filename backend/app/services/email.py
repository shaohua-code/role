"""通过受部署环境管理的 SMTP 投递认证邮件；不记录邮件地址或一次性凭证。"""

import ssl
from email.message import EmailMessage
from smtplib import SMTP, SMTP_SSL
from urllib.parse import quote, urlsplit, urlunsplit

from app.core.config import get_settings


class EmailDeliveryNotConfigured(RuntimeError):
    """部署未配置邮件服务时，投递调用不得伪装成已完成发送。"""


def _send_message(message: EmailMessage) -> None:
    """复用经过 TLS 配置校验的 SMTP 发送路径，避免不同邮件功能安全配置漂移。"""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryNotConfigured("SMTP is not configured")

    context = ssl.create_default_context()
    connection_type = SMTP_SSL if settings.smtp_ssl else SMTP
    connection_kwargs = {"timeout": settings.smtp_timeout_seconds}
    if settings.smtp_ssl:
        connection_kwargs["context"] = context
    with connection_type(settings.smtp_host, settings.smtp_port, **connection_kwargs) as client:
        if settings.smtp_starttls:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password or "")
        client.send_message(message)


def send_password_reset_email(email: str, token: str) -> None:
    """发送仅含短时 fragment 凭证的纯文本邮件，避免 token 出现在 Web 查询日志。"""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryNotConfigured("SMTP is not configured")

    console = urlsplit(settings.console_public_url)
    reset_url = urlunsplit((console.scheme, console.netloc, "/", "", f"password-reset={quote(token, safe='')}"))
    message = EmailMessage()
    message["Subject"] = "重置统一身份平台密码"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        "我们收到了重置统一身份平台密码的请求。\n\n"
        f"请在 {settings.password_reset_token_minutes} 分钟内打开以下链接并设置新密码：\n"
        f"{reset_url}\n\n"
        "如果这不是你发起的操作，请忽略此邮件。出于安全考虑，该链接只能使用一次。"
    )

    _send_message(message)


def send_invitation_email(email: str, token: str, tenant_name: str,
                          role_name: str, expires_at: str) -> None:
    """向目标邮箱发送邀请链接；调用方只在管理员创建后触发，令牌仍仅存于 fragment。"""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryNotConfigured("SMTP is not configured")

    console = urlsplit(settings.console_public_url)
    invitation_url = urlunsplit((
        console.scheme,
        console.netloc,
        f"{console.path.rstrip('/')}/" if console.path.rstrip('/') else "/",
        "",
        f"invite={quote(token, safe='')}",
    ))
    message = EmailMessage()
    message["Subject"] = f"加入 {tenant_name} 的统一身份平台邀请"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        f"你收到加入租户「{tenant_name}」的邀请，授予角色为「{role_name}」。\n\n"
        f"请在 {expires_at} 前打开以下一次性链接并完成账号设置：\n"
        f"{invitation_url}\n\n"
        "链接包含一次性凭证，请勿转发。如果你不认识邀请发起人，请忽略此邮件。"
    )
    _send_message(message)


def send_public_registration_code(email: str, code: str, application_name: str, ttl_minutes: int) -> None:
    """发送应用专属的一次性邮箱验证码；邮件和投递异常都不进入业务审计字段。"""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryNotConfigured("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = f"{application_name} 注册验证码"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        f"你正在注册 {application_name} 账号。\n\n"
        f"验证码：{code}\n\n"
        f"验证码将在 {ttl_minutes} 分钟后失效，最多只能尝试有限次数。"
        "如果不是你本人操作，请忽略此邮件。"
    )
    _send_message(message)
