"""OIDC 授权码和 OAuth 刷新令牌的服务端记录。

原始授权码/刷新令牌只在签发响应中出现一次；数据库存其 SHA-256 摘要，
以便服务端查找并撤销，同时避免数据库备份泄漏即可直接兑换的凭证。
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OAuthAuthorizationCode(Base):
    """极短时、绑定客户端/回调/PKCE/用户的一次性授权码。"""

    __tablename__ = "oauth_authorization_codes"
    __table_args__ = (
        UniqueConstraint("code_hash", name="uq_oauth_authorization_code_hash"),
        Index("ix_oauth_authorization_codes_client_expiry", "application_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    auth_version: Mapped[int] = mapped_column(default=1, nullable=False)
    membership_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(500), nullable=False)
    nonce: Mapped[str] = mapped_column(String(255), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OAuthConsentRequest(Base):
    """短期一次性授权确认请求；保存客户端原请求参数，浏览器仅持有 ticket。"""

    __tablename__ = "oauth_consent_requests"
    __table_args__ = (
        UniqueConstraint("ticket_hash", name="uq_oauth_consent_request_ticket_hash"),
        Index("ix_oauth_consent_requests_expiry", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    auth_version: Mapped[int] = mapped_column(default=1, nullable=False)
    membership_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    ticket_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    client_state: Mapped[str] = mapped_column(String(512), nullable=False)
    scope: Mapped[str] = mapped_column(String(500), nullable=False)
    nonce: Mapped[str] = mapped_column(String(255), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    code_challenge_method: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OAuthRefreshToken(Base):
    """绑定用户和客户端、支持轮换与整族撤销的 OAuth 刷新令牌。"""

    __tablename__ = "oauth_refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_oauth_refresh_token_hash"),
        Index("ix_oauth_refresh_tokens_family_revoked", "family_id", "revoked_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    family_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    auth_version: Mapped[int] = mapped_column(default=1, nullable=False)
    membership_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("oauth_refresh_tokens.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
