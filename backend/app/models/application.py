"""OIDC 应用登记和逐应用登录品牌配置。"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Application(Base):
    """一个业务系统的 OIDC 客户端登记信息。

    密钥仅在创建或轮换时明文返回一次，数据库保存服务端验证所需的哈希；
    回调地址作为 JSON 数组保存，授权码流程必须对提交值做精确白名单匹配。
    """

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("registration_policy IN ('disabled', 'open')", name="ck_application_registration_policy"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    client_secret_hash: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    redirect_uris: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    post_logout_redirect_uris: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # 仅平台管理员可以将应用标记为 trusted；默认要求终端用户逐次确认授权。
    trusted: Mapped[bool] = mapped_column(default=False, nullable=False)
    # ToC 自助注册必须逐应用开启；角色 ID 由服务端校验为同租户、同应用的普通角色。
    registration_policy: Mapped[str] = mapped_column(
        String(20), default="disabled", server_default="disabled", nullable=False
    )
    registration_role_id: Mapped[UUID | None] = mapped_column(index=True)
    registration_terms_version: Mapped[str | None] = mapped_column(String(80))
    registration_privacy_version: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApplicationTheme(Base):
    """每个应用的登录品牌主题，采用 JSON 配置但由 API schema 限制可配置字段。"""

    __tablename__ = "application_themes"
    __table_args__ = (UniqueConstraint("application_id", "version", name="uq_application_theme_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
