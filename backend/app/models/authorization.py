"""租户域 RBAC 模型：角色绑定主体，角色授权资源上的具体操作 Scope。"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, event, func, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.services.permission_namespace import derive_catalog_namespace_value

# 角色层级写死为四级模型：platform=L1、tenant=L3、application=L2/业务角色。
ROLE_KINDS = ("platform", "tenant", "application")
# 权限面：management=IAM 管理面码（可授予管理台能力）；business=业务码（必须走数据范围）。
PERMISSION_SURFACES = ("management", "business")


class Role(Base):
    """角色在租户范围内唯一；kind 标识层级，application_id 用于限制到一个业务应用。"""

    __tablename__ = "roles"
    # PostgreSQL 普通唯一约束允许多个 NULL；无应用范围的租户角色因此需独立部分索引。
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_role_id_tenant"),
        Index("uq_role_tenant_key", "tenant_id", "key", unique=True, postgresql_where=text("application_id IS NULL")),
        Index("uq_role_app_key", "tenant_id", "application_id", "key", unique=True, postgresql_where=text("application_id IS NOT NULL")),
        CheckConstraint("kind IN ('platform', 'tenant', 'application')", name="ck_role_kind"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    application_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    # L1 平台角色挂在专用平台租户下；L3 租户角色 application_id 为空；L2/业务角色必须钉应用。
    kind: Mapped[str] = mapped_column(String(20), default="tenant", nullable=False)
    # 角色编程标识；配合上方部分唯一索引，保证租户内（或应用内）不重名。
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bindings: Mapped[list["RoleBinding"]] = relationship(back_populates="role")
    grants: Mapped[list["RolePermission"]] = relationship(back_populates="role")


@event.listens_for(Role, "before_insert")
def _role_kind_default(_mapper, _connection, target: Role) -> None:
    """未显式指定层级时按 application_id 推导：钉应用即应用角色，否则为租户角色。"""
    if not target.kind:
        target.kind = "application" if target.application_id is not None else "tenant"


class Permission(Base):
    """权限目录中的原子操作，如 resume.read 或 workflow.run。"""

    __tablename__ = "permissions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="ck_permission_status"),
        CheckConstraint("surface IN ('management', 'business')", name="ck_permission_surface"),
        CheckConstraint("kind IN ('menu', 'button', 'api', 'data')", name="ck_permission_kind"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    catalog_namespace: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    # 授权动作（如 read、run），与 resource_type 组成完整权限语义。
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    # 四类：菜单 / 按钮 / 接口 / 数据。菜单下新建的按钮编码可继承 menu.* 前缀，必须以本列为准。
    kind: Mapped[str] = mapped_column(String(20), default="api", server_default="api", nullable=False)
    # 目录项停用时保留角色授权关系和数据策略，避免丢失治理历史；判权只接受 active 项。
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", nullable=False)
    # 管理面码与应用注册的业务码分面管理；绿场业务码默认强制数据范围，缺策略即拒绝。
    surface: Mapped[str] = mapped_column(String(20), default="business", server_default="business", nullable=False)
    # 置位时判权必须命中 RoleDataScope 数据范围策略，缺策略即拒绝。
    requires_data_scope: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)

    grants: Mapped[list["RolePermission"]] = relationship(back_populates="permission")


@event.listens_for(Permission, "before_insert")
def _permission_catalog_namespace_default(_mapper, _connection, target: Permission) -> None:
    """测试与旧代码路径未显式传 catalog_namespace 时，从 code 推导。"""
    if not target.catalog_namespace:
        target.catalog_namespace = derive_catalog_namespace_value(target.code)


class RolePermission(Base):
    """角色对资源类型/实例授予 Scope；空 resource_id 表示该类型范围。"""

    __tablename__ = "role_permissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 资源 ID 使用字符串以支持各业务系统自有的 ID 格式，不把业务表复制进 IAM。
    resource_id: Mapped[str | None] = mapped_column(String(180), index=True)

    role: Mapped[Role] = relationship(back_populates="grants")
    permission: Mapped[Permission] = relationship(back_populates="grants")


class RoleBinding(Base):
    """将角色绑定到租户成员；租户成员与角色租户必须由服务层校验一致。"""

    __tablename__ = "role_bindings"
    __table_args__ = (UniqueConstraint("membership_id", "role_id", name="uq_membership_role"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant_memberships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    membership: Mapped["TenantMembership"] = relationship(back_populates="role_bindings")
    role: Mapped[Role] = relationship(back_populates="bindings")
