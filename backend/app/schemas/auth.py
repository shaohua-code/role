"""认证 API 的输入输出契约；响应模型刻意不包含 password_hash。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """邮箱验证前只接受身份与同意信息，不接收密码、租户、角色或管理员标志。"""

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    accepted_terms: bool
    accepted_privacy: bool
    terms_version: str = Field(min_length=1, max_length=80)
    privacy_version: str = Field(min_length=1, max_length=80)
    # 与服务端当前已发布主题核对，防止旧登录页按新协议版本提交。
    terms_url: str = Field(min_length=1, max_length=2048)
    privacy_url: str = Field(min_length=1, max_length=2048)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        """避免空白名称绕过 min_length 后创建难以识别的用户记录。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("姓名不能为空")
        return cleaned


class RegisterVerifyRequest(BaseModel):
    """邮箱 OTP 成功后设置新密码或证明当前密码；不接受任何权限字段。"""

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=1, max_length=128)


class InvitationTokenRequest(BaseModel):
    """邀请 token 提交请求：仅承载短期一次性邀请令牌本身。"""

    token: str = Field(min_length=40, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class AcceptInvitationRequest(InvitationTokenRequest):
    # 对新账号是初始密码；已注册用户需输入当前密码，以把邀请安全绑定到原账号。
    # 既有账号可能使用较早的口令策略；新账号在服务端单独要求至少 12 位。
    password: str = Field(min_length=1, max_length=128)


class AdminInvitationCreate(BaseModel):
    tenant_id: UUID
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    role_id: UUID
    expires_in_hours: int = Field(default=72, ge=1, le=336)


class AdminInvitationBatchCreate(BaseModel):
    """G21 批量邀请：同一租户同一角色一次邀请多个邮箱；部分失败不阻断其余邮箱。"""

    tenant_id: UUID
    emails: list[EmailStr] = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=120)
    role_id: UUID
    expires_in_hours: int = Field(default=72, ge=1, le=336)


class AdminInvitationResend(BaseModel):
    """G21 重发邀请：换发新 token 并顺延有效期；仅未接受、未撤销的邀请可重发。"""

    expires_in_hours: int = Field(default=72, ge=1, le=336)


class LoginRequest(BaseModel):
    """邮箱密码登录请求；密码仅用于本次认证，响应不含凭证。"""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    """公开找回入口只接受邮箱；响应不暴露该账号是否存在。"""

    email: EmailStr


class PasswordResetComplete(BaseModel):
    """一次性邮件凭证与新密码；Token 只经请求体传输，不放在查询参数。"""

    token: str = Field(min_length=40, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    new_password: str = Field(min_length=12, max_length=128)


class PasswordChange(BaseModel):
    """登录态自助修改密码：必须验证当前口令，新口令沿用注册期 12 位下限。"""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class AdminPasswordReset(BaseModel):
    """管理员重置用户密码：新口令仅经受保护管理请求进入，不在响应回显。"""

    new_password: str = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    """全局用户信息响应；刻意不含密码哈希等凭证字段。"""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str | None
    display_name: str
    status: str
    created_at: datetime


class RoleBrief(BaseModel):
    """有效角色摘要；前端可展示，不可作为安全边界。"""

    key: str
    kind: str
    name: str | None = None
    tenant_id: UUID
    application_id: UUID | None = None


class MeResponse(UserResponse):
    """登录后身份包：用户信息 + 有效角色 + 由角色派生的 capabilities。"""

    roles: list[RoleBrief] = Field(default_factory=list)
    capabilities: dict = Field(default_factory=dict)


class AuthResponse(BaseModel):
    """签发成功响应：短期 access token 与用户信息；expires_in 为秒数。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TenantCreate(BaseModel):
    """创建租户：slug 为全局唯一 URL 标识；kind 决定注册受众类型。"""

    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")
    kind: Literal["organization", "consumer"] = "organization"


class TenantKindUpdate(BaseModel):
    """转换注册受众时使用 expected_kind 防止过期管理页覆盖并发修改。"""

    model_config = ConfigDict(extra="forbid")

    expected_kind: Literal["organization", "consumer"]
    kind: Literal["organization", "consumer"]


class OIDCConsentTicket(BaseModel):
    """授权确认会话票据请求；浏览器仅持有 ticket，不接触原始授权参数。"""

    ticket: str = Field(min_length=40, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class OIDCConsentDecision(OIDCConsentTicket):
    """用户对授权请求的批准/拒绝决定；票据一次性消费。"""

    approved: bool


class ThemeUpdate(BaseModel):
    """更新应用登录主题 JSON 配置；可配置字段白名单由路由层校验。"""

    config: dict = Field(max_length=40)


class AdminUserCreate(BaseModel):
    """管理员直建用户：初始密码至少 12 位；role_id 可选，缺省不授予角色。"""

    tenant_id: UUID
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    initial_password: str = Field(min_length=12, max_length=128)
    role_id: UUID | None = None


class PublicRegistrationCapabilities(BaseModel):
    """匿名登录页可展示的注册策略摘要；不含 client secret 或草稿主题。"""

    available: bool
    resend_cooldown_seconds: int
    terms_url: str
    privacy_url: str
    terms_version: str
    privacy_version: str


class ConsoleRegistrationContext(BaseModel):
    client_id: str
    application_name: str
    registration: PublicRegistrationCapabilities


class AuthPublicCapabilities(BaseModel):
    """登录页公开能力摘要：找回密码入口与各应用控制台自助注册上下文。"""

    password_reset_available: bool
    console_registration: ConsoleRegistrationContext | None = None


class UserStatusUpdate(BaseModel):
    """携带页面读取时的全局账号状态，阻止过期管理页覆盖新状态。"""

    model_config = ConfigDict(extra="forbid")

    expected_status: Literal["active", "disabled", "locked"]
    status: Literal["active", "disabled", "locked"]
