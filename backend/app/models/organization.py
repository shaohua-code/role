"""租户组织树、成员组织归属和角色级数据范围策略。"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
                        Index, JSON, String, UniqueConstraint, func, text)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Organization(Base):
    """租户内的部门节点；复合自引用外键保证父部门一定属于同一租户。"""

    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_organization_tenant_key"),
        UniqueConstraint("id", "tenant_id", name="uq_organization_id_tenant"),
        ForeignKeyConstraint(["parent_id", "tenant_id"], ["organizations.id", "organizations.tenant_id"],
                             ondelete="RESTRICT", name="fk_organization_parent_same_tenant"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    # 父部门自引用（复合外键限同租户）；存在子节点时删除会被 RESTRICT 拒绝。
    parent_id: Mapped[UUID | None] = mapped_column(index=True)
    # 部门负责人（G24）：指向该租户内某成员的全局用户；归属校验由服务层完成，不设跨表外键。
    owner_user_id: Mapped[UUID | None] = mapped_column(index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MembershipOrganization(Base):
    """租户成员与组织的多对多关系；复合外键防止跨租户挂接身份或部门。"""

    __tablename__ = "membership_organizations"
    __table_args__ = (
        ForeignKeyConstraint(["membership_id", "tenant_id"], ["tenant_memberships.id", "tenant_memberships.tenant_id"],
                             ondelete="CASCADE", name="fk_membership_organization_member_tenant"),
        ForeignKeyConstraint(["organization_id", "tenant_id"], ["organizations.id", "organizations.tenant_id"],
                             ondelete="CASCADE", name="fk_membership_organization_org_tenant"),
        Index("uq_membership_primary_organization", "membership_id", unique=True,
              postgresql_where=text("is_primary IS TRUE")),
    )

    membership_id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    # 主组织标记；部分唯一索引保证每名成员至多有一个主组织。
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RoleDataScope(Base):
    """角色针对单个权限定义的数据过滤范围；selected 仅保存同租户部门 ID。"""

    __tablename__ = "role_data_scopes"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission_data_scope"),
        ForeignKeyConstraint(["role_id", "tenant_id"], ["roles.id", "roles.tenant_id"],
                             ondelete="CASCADE", name="fk_data_scope_role_tenant"),
        CheckConstraint("scope_type IN ('tenant', 'self', 'organization', 'organization_tree', 'selected_organizations')",
                        name="ck_data_scope_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    role_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    permission_id: Mapped[UUID] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), index=True, nullable=False)
    # tenant=全租户、self=仅本人、organization=本部门、organization_tree=本部门及子树、selected_organizations=指定部门。
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # JSON 仅存配置的部门 ID 列表，不存业务数据；API 在写入与决策时均校验租户归属。
    organization_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
