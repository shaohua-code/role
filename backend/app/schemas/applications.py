"""OAuth 应用管理请求契约，与登录认证请求保持领域分离。"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApplicationCreate(BaseModel):
    """创建 confidential client；登录回调是授权码流程的必要安全边界。"""

    tenant_id: UUID
    name: str = Field(min_length=1, max_length=160)
    client_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9._-]+$")
    description: str | None = Field(default=None, max_length=500)
    # 服务端 schema 强制非空，不能依赖管理台表单阻止无回调客户端。
    redirect_uris: list[str] = Field(min_length=1, max_length=20)
    post_logout_redirect_uris: list[str] = Field(default_factory=list, max_length=20)
    # 权限命名空间；提交前自动去首尾空白并转小写，缺省由服务端补默认值。
    permission_namespace: str | None = Field(default=None, max_length=100)

    @field_validator("permission_namespace", mode="before")
    @classmethod
    def trim_permission_namespace(cls, value):
        if value is None or not isinstance(value, str):
            return value
        cleaned = value.strip().lower()
        return cleaned or None


class ApplicationUpdate(BaseModel):
    """更新应用展示信息与逐应用 ToC 注册策略；客户端身份安全配置不属于此契约。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    registration_policy: Literal["disabled", "open"] | None = None
    registration_role_id: UUID | None = None
    registration_terms_version: str | None = Field(default=None, max_length=80)
    registration_privacy_version: str | None = Field(default=None, max_length=80)
    # OIDC Back-Channel Logout 1.0（G19）：服务端推送登出令牌的 HTTPS 地址；空串表示清除。
    backchannel_logout_uri: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个可编辑字段")
        if "registration_policy" in self.model_fields_set and self.registration_policy is None:
            raise ValueError("注册策略不能为 null")
        if "name" in self.model_fields_set:
            if self.name is None or not self.name.strip():
                raise ValueError("应用名称不能为空")
            self.name = self.name.strip()
        if "description" in self.model_fields_set and self.description is not None:
            self.description = self.description.strip() or None
        for field_name in ("registration_terms_version", "registration_privacy_version"):
            if field_name in self.model_fields_set and getattr(self, field_name) is not None:
                cleaned = getattr(self, field_name).strip()
                setattr(self, field_name, cleaned or None)
        return self


class ApplicationStatusUpdate(BaseModel):
    """携带读取时的应用状态，阻止过期管理页覆盖其他管理员的变更。"""

    model_config = ConfigDict(extra="forbid")

    expected_status: Literal["active", "disabled"]
    status: Literal["active", "disabled"]
