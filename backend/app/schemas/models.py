"""模型目录和可信网关计量的请求契约，与身份/认证契约分离。"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelCatalogCreate(BaseModel):
    """登记模型条目：credential_ref 只存外部密钥管理器引用，不接收密钥明文。"""

    tenant_id: UUID
    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    provider: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=160)
    endpoint_url: str | None = Field(default=None, max_length=500)
    credential_ref: str | None = Field(default=None, max_length=300)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    rpm_limit: int | None = Field(default=None, ge=1)
    tpm_limit: int | None = Field(default=None, ge=1)
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)


class ModelCatalogUpdate(BaseModel):
    """模型目录的部分更新；RPM/TPM 是可审计策略字段，执行仍由服务级开关控制。"""

    model_config = ConfigDict(extra="forbid")

    provider: str | None = Field(default=None, min_length=1, max_length=100)
    model_name: str | None = Field(default=None, min_length=1, max_length=160)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    endpoint_url: str | None = Field(default=None, min_length=1, max_length=500)
    credential_ref: str | None = Field(default=None, min_length=1, max_length=300)
    capabilities: list[str] | None = Field(default=None, max_length=20)
    rpm_limit: int | None = Field(default=None, ge=1)
    tpm_limit: int | None = Field(default=None, ge=1)
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_patch_fields(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的模型字段")
        for field in ("provider", "model_name", "display_name", "capabilities"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能设置为 null")
        return self


class ModelCatalogStatusUpdate(BaseModel):
    """模型启停携带读取时状态，避免旧管理页面覆盖另一位管理员的改动。"""

    model_config = ConfigDict(extra="forbid")

    expected_status: Literal["active", "disabled"]
    status: Literal["active", "disabled"]


class ModelUsageReport(BaseModel):
    """可信模型网关报告实测或明确标记为估算的用量；不接收提示词或模型响应内容。"""

    request_id: str = Field(min_length=8, max_length=180, pattern=r"^[A-Za-z0-9._:-]+$")
    tenant_id: UUID
    model_id: UUID
    application_id: UUID
    user_id: UUID
    input_tokens: int = Field(ge=0, le=10_000_000)
    output_tokens: int = Field(ge=0, le=10_000_000)
    outcome: str = Field(pattern=r"^(succeeded|failed)$")
    usage_is_estimated: bool = False
    latency_ms: int = Field(ge=0, le=86_400_000)


class ModelUsageReservationRequest(BaseModel):
    """可信网关调用 Provider 前申请 RPM/TPM 预留；该操作不替代用户授权检查。"""

    request_id: str = Field(min_length=8, max_length=180, pattern=r"^[A-Za-z0-9._:-]+$")
    tenant_id: UUID
    model_id: UUID
    application_id: UUID
    user_id: UUID
    reserved_input_tokens: int = Field(ge=0, le=10_000_000)
    # 输出预留下限为 1，区别于允许为 0 的输入预留。
    reserved_output_tokens: int = Field(ge=1, le=10_000_000)


class ModelUsageSettlementRequest(BaseModel):
    """Provider 请求结束后的用量；估算值必须明确标记，不接收内容或供应商凭证。"""

    request_id: str = Field(min_length=8, max_length=180, pattern=r"^[A-Za-z0-9._:-]+$")
    input_tokens: int = Field(ge=0, le=10_000_000)
    output_tokens: int = Field(ge=0, le=10_000_000)
    outcome: str = Field(pattern=r"^(succeeded|failed)$")
    usage_is_estimated: bool = False
    latency_ms: int = Field(ge=0, le=86_400_000)


class ModelUsageReviewRequest(BaseModel):
    """管理员对过期的未结预留作出可审计决定；原因不得包含提示词或凭证明文。"""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=8, max_length=180, pattern=r"^[A-Za-z0-9._:-]+$")
    decision: Literal["settle", "release"]
    reason: str = Field(min_length=3, max_length=500)
    # 结算时必须为假；释放时必须为真，即确认 Provider 从未被调用。
    provider_not_called: bool = False
    input_tokens: int | None = Field(default=None, ge=0, le=10_000_000)
    output_tokens: int | None = Field(default=None, ge=0, le=10_000_000)
    outcome: Literal["succeeded", "failed"] | None = None
    usage_is_estimated: bool = True
    latency_ms: int | None = Field(default=None, ge=0, le=86_400_000)

    @model_validator(mode="after")
    def validate_decision_fields(self):
        if self.decision == "settle":
            if self.input_tokens is None or self.output_tokens is None or self.outcome is None:
                raise ValueError("结算必须提供输入 Token、输出 Token 和调用结果")
            if self.provider_not_called:
                raise ValueError("已调用 Provider 的请求不能选择未调用确认")
        elif any(value is not None for value in
                 (self.input_tokens, self.output_tokens, self.outcome, self.latency_ms)):
            raise ValueError("释放预留不能包含 Token 或调用结果")
        elif not self.provider_not_called:
            raise ValueError("释放前必须确认 Provider 从未被调用")
        return self
