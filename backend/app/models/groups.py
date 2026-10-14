"""租户内用户组，以及组成员和组角色的强制租户隔离关系。"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserGroup(Base):
    """用户组只存在于单一租户内；停用组会立即停止通过组继承角色。"""

    __tablename__ = "user_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_user_group_tenant_key"),
        UniqueConstraint("id", "tenant_id", name="uq_user_group_id_tenant"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserGroupMembership(Base):
    """用户组与租户成员关联；复合外键禁止把别的租户成员加入该组。"""

    __tablename__ = "user_group_memberships"
    __table_args__ = (
        ForeignKeyConstraint(["group_id", "tenant_id"], ["user_groups.id", "user_groups.tenant_id"],
                             ondelete="CASCADE", name="fk_user_group_membership_group_tenant"),
        ForeignKeyConstraint(["membership_id", "tenant_id"], ["tenant_memberships.id", "tenant_memberships.tenant_id"],
                             ondelete="CASCADE", name="fk_user_group_membership_member_tenant"),
    )

    group_id: Mapped[UUID] = mapped_column(primary_key=True)
    membership_id: Mapped[UUID] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserGroupRole(Base):
    """用户组继承角色的配置；数据库同时约束组和角色属于同一租户。"""

    __tablename__ = "user_group_roles"
    __table_args__ = (
        ForeignKeyConstraint(["group_id", "tenant_id"], ["user_groups.id", "user_groups.tenant_id"],
                             ondelete="CASCADE", name="fk_user_group_role_group_tenant"),
        ForeignKeyConstraint(["role_id", "tenant_id"], ["roles.id", "roles.tenant_id"],
                             ondelete="CASCADE", name="fk_user_group_role_role_tenant"),
    )

    group_id: Mapped[UUID] = mapped_column(primary_key=True)
    role_id: Mapped[UUID] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
