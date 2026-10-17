"""模型目录元数据；模型凭证只保存外部 Secret Manager 引用，不保存密钥明文。"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, func, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelCatalog(Base):
    """记录可发现、可授权的模型能力；代理、费用结算和额度执行属于调用网关。"""
    __tablename__ = "model_catalog"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_model_tenant_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(String(500))
    credential_ref: Mapped[str | None] = mapped_column(String(300))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    rpm_limit: Mapped[int | None] = mapped_column()
    tpm_limit: Mapped[int | None] = mapped_column()
    input_cost_per_million: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    output_cost_per_million: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelUsageEvent(Base):
    """模型网关完成请求后写入的不可变用量账目；绝不保存 Prompt、响应正文或凭证。"""
    __tablename__ = "model_usage_events"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_model_usage_request_id"),
        CheckConstraint("input_tokens >= 0 AND output_tokens >= 0 AND (latency_ms IS NULL OR latency_ms >= 0)", name="ck_model_usage_nonnegative"),
        CheckConstraint("outcome IN ('succeeded', 'failed')", name="ck_model_usage_outcome"),
        CheckConstraint("source IN ('gateway', 'admin_reconciliation')", name="ck_model_usage_source"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(180), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model_catalog.id", ondelete="RESTRICT"), index=True, nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="RESTRICT"), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    input_tokens: Mapped[int] = mapped_column(nullable=False)
    output_tokens: Mapped[int] = mapped_column(nullable=False)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    usage_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="gateway", server_default="gateway", nullable=False)
    latency_ms: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class ModelUsageReservation(Base):
    """调用前的并发配额预留；网关完成后与用量账目在同一事务结算。"""

    __tablename__ = "model_usage_reservations"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_model_usage_reservation_request_id"),
        CheckConstraint("reserved_input_tokens >= 0 AND reserved_output_tokens >= 0",
                        name="ck_model_usage_reservation_tokens_nonnegative"),
        CheckConstraint("status IN ('reserved', 'settled', 'released')", name="ck_model_usage_reservation_status"),
        Index("ix_model_usage_reservations_model_expiry", "model_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(180), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, nullable=False)
    model_id: Mapped[UUID] = mapped_column(ForeignKey("model_catalog.id", ondelete="RESTRICT"), index=True, nullable=False)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="RESTRICT"), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    reserved_input_tokens: Mapped[int] = mapped_column(nullable=False)
    reserved_output_tokens: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="reserved", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
