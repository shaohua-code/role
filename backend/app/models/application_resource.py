"""面向应用的显式资源树（菜单/按钮/数据规则）与角色资源授权关联。"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, Integer, JSON, String,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApplicationResource(Base):
    """应用内资源树节点：menu/button/data_rule 三类，parent_id 构成层级。

    菜单携带路由 path、icon 与 extra JSON 额外参数，业务端登录后拉取整棵树渲染导航；
    按钮与数据规则挂在菜单之下，作为角色分配的最小授权单元。
    """

    __tablename__ = "application_resources"
    __table_args__ = (
        UniqueConstraint("application_id", "code", name="uq_application_resource_app_code"),
        CheckConstraint("resource_type IN ('menu', 'button', 'data_rule')", name="ck_application_resource_type"),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_application_resource_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 自引用外键：删除父节点时级联删除整棵子树。
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("application_resources.id", ondelete="CASCADE"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(180), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # 描述/备注：说明资源用途，仅管理面与下发展示，不参与判权。
    description: Mapped[str | None] = mapped_column(String(500))
    # 菜单路由路径；按钮/数据规则可为空。
    path: Mapped[str | None] = mapped_column(String(300))
    icon: Mapped[str | None] = mapped_column(String(120))
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # 额外参数以 JSON 存储，由业务端自行解释（如重定向、徽标、meta 配置等）。
    # 默认值用方言无关的字面量 {}，同时兼容 PostgreSQL 与隔离测试的 SQLite。
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RoleApplicationResource(Base):
    """角色与应用资源的多对多授权关联；分配即授权，移除即回收。"""

    __tablename__ = "role_application_resources"

    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("application_resources.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
