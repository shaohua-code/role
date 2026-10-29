"""全局身份与租户成员关系模型。

用户账号表示一个人在平台中的全局身份；TenantMembership 表示其在某租户中的
成员身份。把二者拆开后，同一账号才能在不同租户拥有彼此隔离的角色和状态。
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Text, JSON

from app.db.base import Base


class Tenant(Base):
    """租户是业务用户、成员、角色及授权策略的隔离边界。"""

    __tablename__ = "tenants"
    __table_args__ = (CheckConstraint("kind IN ('organization', 'consumer')", name="ck_tenant_kind"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    # ToC 自助注册只允许显式标记为消费租户的登录域。
    kind: Mapped[str] = mapped_column(String(20), default="organization", server_default="organization", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["TenantMembership"]] = relationship(back_populates="tenant")


class User(Base):
    """跨租户唯一的登录身份；租户权限不直接挂在用户全局记录上。"""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email IS NOT NULL OR phone_number IS NOT NULL", name="ck_user_has_login_id"),
        CheckConstraint("status IN ('active', 'disabled', 'locked')", name="ck_user_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # 邮箱和手机号可以二选一；至少一个登录标识由数据库约束保障。
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    # 只保存密码哈希。API 永远不回传这个字段，审计日志也不得记录它。
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    # 修改密码后递增；在线认证服务据此立即拒绝此前签发的 access token。
    auth_version: Mapped[int] = mapped_column(default=1, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["TenantMembership"]] = relationship(back_populates="user")


class RefreshSession(Base):
    """可撤销、单次轮换的浏览器刷新会话；数据库只存随机令牌的 SHA-256 摘要。"""

    __tablename__ = "refresh_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 签发时用户全局凭证版本快照；轮换或校验时版本不一致即拒绝。
    auth_version: Mapped[int] = mapped_column(default=1, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship()


class PasswordResetToken(Base):
    """邮件密码重置凭证；只存摘要，锁行消费后同一事务撤销该用户现有会话。"""

    __tablename__ = "password_reset_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_password_reset_token_hash"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PasswordResetThrottle(Base):
    """只保留带服务端 HMAC 的邮箱短时节流键，避免公开接口被用于邮件轰炸。"""

    __tablename__ = "password_reset_throttles"

    email_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class PublicRegistrationThrottle(Base):
    """匿名注册按邮件/来源双维限流，只存服务端 HMAC 摘要而不保留原始标识。"""

    __tablename__ = "public_registration_throttles"

    bucket_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class PublicRegistrationChallenge(Base):
    """待完成的注册申请；不暂存密码，验证码与邮件地址均按短期凭证清理。"""

    __tablename__ = "public_registration_challenges"
    __table_args__ = (
        UniqueConstraint("application_id", "email_hash", name="uq_registration_app_email"),
        CheckConstraint("failed_attempts >= 0", name="ck_registration_failed_attempts_nonnegative"),
        CheckConstraint(
            "consumed_at IS NOT NULL OR (registration_role_id IS NOT NULL AND registration_role_fingerprint IS NOT NULL)",
            name="ck_registration_challenge_role_snapshot_required",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # HMAC 用于查询同一申请，不让邮箱以明文落入注册挑战表。
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # 申请邮箱已对应平台用户时记录其 ID，便于服务端按已注册路径合并处理。
    existing_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # 保存验证码的 HMAC 摘要；数据库与日志中都不出现 OTP 明文。
    verification_code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # 锁定申请时的默认角色；管理员改动角色后，旧验证码不能套用新授权。
    registration_role_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    registration_role_fingerprint: Mapped[str | None] = mapped_column(String(64))
    # 角色指纹与 registration_role_id 配套，验证时两者必须同时匹配快照。
    terms_version: Mapped[str] = mapped_column(String(80), nullable=False)
    privacy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    # 记录申请时实际展示的政策地址；发布新版本/地址后，旧 challenge 不能继续兑换。
    terms_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    privacy_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # 验证码连续错误次数；超过上限后挑战不再可用，需重新申请。
    failed_attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PublicRegistrationEmailOutbox(Base):
    """事务发件箱只引用挑战 ID；验证码由独立注册 HMAC 密钥确定性派生，不保存 OTP 明文。"""

    __tablename__ = "public_registration_email_outbox"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'sending', 'sent', 'failed')", name="ck_registration_outbox_status"),
        CheckConstraint("attempts >= 0", name="ck_registration_outbox_attempts_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    challenge_id: Mapped[UUID] = mapped_column(
        ForeignKey("public_registration_challenges.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    # 下次允许投递时间；locked_until 为发送器抢占锁到期，防止并发重复发送。
    retry_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PublicRegistrationConsent(Base):
    """按用户、应用和政策版本保留不可覆盖的同意证据。"""

    __tablename__ = "public_registration_consents"
    __table_args__ = (UniqueConstraint(
        "user_id", "application_id", "terms_version", "privacy_version",
        name="uq_registration_consent_policy_version",
    ),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    terms_version: Mapped[str] = mapped_column(String(80), nullable=False)
    privacy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    terms_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    privacy_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LoginAttemptBucket(Base):
    """只保存服务端 HMAC 键和失败计数，按来源地址与账号组合限制口令猜测。"""

    __tablename__ = "login_attempt_buckets"
    __table_args__ = (
        CheckConstraint("failed_attempts >= 0", name="ck_login_attempt_buckets_nonnegative"),
    )

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failed_attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"), nullable=False)
    # 失败计数窗口起点；窗口过期后计数清零重新累计。
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RevokedAccessToken(Base):
    """已撤销的短期 JWT 仅保存随机 jti 摘要，令牌正文不会写入数据库。"""

    __tablename__ = "revoked_access_tokens"

    jti_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 令牌用途标记，避免不同用途的 jti 混淆误判。
    token_use: Mapped[str] = mapped_column(String(24), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TenantMembership(Base):
    """用户进入租户的授权上下文；所有租户内角色绑定都必须关联此记录。"""

    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),
        UniqueConstraint("id", "tenant_id", name="uq_membership_id_tenant"),
        CheckConstraint("status IN ('active', 'disabled', 'departed')", name="ck_tenant_membership_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 取值 active/disabled/departed；departed 表示成员已离开租户，保留历史记录。
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    # 租户成员状态版本仅撤销这一 tenant 的旧 OIDC 凭证，不会注销同一全局身份的其他产品会话。
    auth_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")
    role_bindings: Mapped[list["RoleBinding"]] = relationship(back_populates="membership")


class UserInvitation(Base):
    """邮箱邀请只存 token 摘要；原始短期链接只在管理员创建响应中出现一次。"""
    __tablename__ = "user_invitations"
    __table_args__ = (
        ForeignKeyConstraint(["role_id", "tenant_id"], ["roles.id", "roles.tenant_id"],
                             ondelete="RESTRICT", name="fk_user_invitation_role_tenant"),
        # 同租户同邮箱最多一个仍有效邀请；过期记录在创建新邀请时会被标记撤销。
        Index("uq_user_invitation_pending_email", "tenant_id", "email", unique=True,
              postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    # 邀请接受后授予的角色；复合外键（RESTRICT）保证角色与邀请同租户且角色未删除。
    role_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEvent(Base):
    """只追加的管理审计事件；不保存凭证、令牌或密钥明文。"""

    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    tenant_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(180))
    outcome: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    # JSON 操作上下文快照（如请求参数与变更前后值），已由写入端脱敏。
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
