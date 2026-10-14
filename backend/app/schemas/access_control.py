"""RBAC 角色、权限和授权判定接口契约。"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictBool, field_validator, model_validator


class RoleCreate(BaseModel):
    tenant_id: UUID
    application_id: UUID | None = None
    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class RoleUpdate(BaseModel):
    """角色仅允许编辑展示信息；租户、应用范围、标识和授权关系保持稳定。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个可编辑字段")
        if "name" in self.model_fields_set:
            if self.name is None or not self.name.strip():
                raise ValueError("角色名称不能为空")
            self.name = self.name.strip()
        if "description" in self.model_fields_set and self.description is not None:
            self.description = self.description.strip() or None
        return self


class RoleCloneRequest(BaseModel):
    """复制角色的展示字段，并要求每次明确是否携带现行授权策略。"""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    # 默认清空授权，避免管理员只想复用角色信息时意外扩大访问面。
    copy_authorizations: StrictBool = False

    @field_validator("key", "name", mode="before")
    @classmethod
    def trim_text_fields(cls, value):
        """先清理首尾空白，再让 Field 的格式/长度规则验证标准化值。"""
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def normalize_clone_fields(self):
        self.key = self.key.strip()
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("角色名称不能为空")
        if self.description is not None:
            self.description = self.description.strip() or None
        return self


class ApplicationRoleCreate(BaseModel):
    """应用管理员只能创建当前应用范围内的角色；tenant/application 由路由上下文决定。"""

    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class RoleStatusUpdate(BaseModel):
    """角色状态更新使用期望值，防止陈旧页面覆盖并发状态变化。"""

    model_config = ConfigDict(extra="forbid")

    expected_status: Literal["active", "disabled"]
    status: Literal["active", "disabled"]


class ApplicationRoleBindingCreate(BaseModel):
    """只允许通过邮箱将已存在的租户成员绑定到指定应用角色，不暴露租户成员目录。"""

    email: EmailStr
    role_id: UUID


class PermissionCreate(BaseModel):
    code: str = Field(min_length=3, max_length=180)
    resource_type: str = Field(min_length=1, max_length=100)
    scope: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class PermissionStatusUpdate(BaseModel):
    """权限目录状态变更需带上页面读取到的状态，防止覆盖并发修改。"""

    model_config = ConfigDict(extra="forbid")

    expected_status: Literal["active", "disabled"]
    status: Literal["active", "disabled"]


class RoleBindingCreate(BaseModel):
    tenant_id: UUID
    user_id: UUID
    role_id: UUID


class AuthorizationCheck(BaseModel):
    tenant_id: UUID
    application_id: UUID | None = None
    permission_code: str = Field(min_length=3, max_length=180)
    resource_id: str | None = Field(default=None, max_length=180)
    include_data_scope: bool = False


class AuthorizationSimulation(AuthorizationCheck):
    """管理员只读模拟指定成员的授权请求；模拟结果不会修改角色或策略。"""

    user_id: UUID


class RolePermissionsPreview(BaseModel):
    """预演拟保存的角色通用权限集合。"""

    permission_ids: list[UUID] = Field(max_length=500)

    @model_validator(mode="after")
    def permission_ids_must_be_unique(self):
        if len(set(self.permission_ids)) != len(self.permission_ids):
            raise ValueError("权限列表不能包含重复项")
        return self


class RolePermissionsUpdate(RolePermissionsPreview):
    """原子替换角色通用权限时，必须提交刚预览过的当前集合。"""

    expected_current_permission_ids: list[UUID] = Field(max_length=500)

    @model_validator(mode="after")
    def expected_permission_ids_must_be_unique(self):
        if len(set(self.expected_current_permission_ids)) != len(self.expected_current_permission_ids):
            raise ValueError("预览版本的权限列表不能包含重复项")
        return self
