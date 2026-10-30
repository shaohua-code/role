"""应用资源树与角色资源授权接口契约。"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# 资源三分类：菜单（导航节点）、按钮（页面操作）、数据规则（行级过滤条件说明）。
ResourceType = Literal["menu", "button", "data_rule"]


class ApplicationResourceCreate(BaseModel):
    """创建资源树节点；按钮/数据规则必须挂在菜单之下，由路由层校验父节点类型。"""

    parent_id: UUID | None = None
    resource_type: ResourceType
    code: str = Field(min_length=2, max_length=180)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    path: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, max_length=120)
    sort: int = Field(default=0, ge=-9999, le=9999)
    extra: dict[str, Any] = Field(default_factory=dict)
    status: Literal["active", "disabled"] = "active"

    @field_validator("code", "name", "description", mode="before")
    @classmethod
    def trim_text_fields(cls, value):
        """先清理首尾空白，再让 Field 的长度规则验证标准化值。"""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ApplicationResourceUpdate(BaseModel):
    """部分更新资源节点；parent_id 移动时的环形层级由路由层检测。"""

    model_config = ConfigDict(extra="forbid")

    parent_id: UUID | None = None
    resource_type: ResourceType | None = None
    code: str | None = Field(default=None, min_length=2, max_length=180)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    path: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, max_length=120)
    sort: int | None = Field(default=None, ge=-9999, le=9999)
    extra: dict[str, Any] | None = None
    status: Literal["active", "disabled"] | None = None

    @field_validator("code", "name", "description", mode="before")
    @classmethod
    def trim_text_fields(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个可编辑字段")
        return self


class RoleResourcesAssign(BaseModel):
    """全量替换角色在当前应用的资源授权集合；服务端自动补齐祖先节点。"""

    resource_ids: list[UUID] = Field(max_length=500)

    @model_validator(mode="after")
    def resource_ids_must_be_unique(self):
        if len(set(self.resource_ids)) != len(self.resource_ids):
            raise ValueError("resource_ids 包含重复项")
        return self
