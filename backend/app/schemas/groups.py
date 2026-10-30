"""租户用户组接口契约；保持组模型与认证请求契约分离。"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserGroupCreate(BaseModel):
    """创建租户用户组时，组标识与租户边界一并确定；父组可选（G24 组嵌套）。"""

    tenant_id: UUID
    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    parent_group_id: UUID | None = None


class UserGroupUpdate(BaseModel):
    """用户组允许变更展示信息与父组（G24），租户和标识创建后保持稳定。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    parent_group_id: UUID | None = None

    @model_validator(mode="after")
    def require_update_fields(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个可编辑字段")
        if "name" in self.model_fields_set:
            if self.name is None or not self.name.strip():
                raise ValueError("用户组名称不能为空")
            self.name = self.name.strip()
        if "description" in self.model_fields_set and self.description is not None:
            self.description = self.description.strip() or None
        return self


class UserGroupMembersUpdate(BaseModel):
    """按租户全量替换组成员；服务端会验证每位用户的有效租户成员身份。"""

    user_ids: list[UUID] = Field(max_length=1000)

    @model_validator(mode="after")
    def member_ids_must_be_unique(self):
        if len(set(self.user_ids)) != len(self.user_ids):
            raise ValueError("用户组成员列表不能包含重复用户")
        return self


class UserGroupRolesUpdate(BaseModel):
    """按租户全量替换组角色；跨租户角色由服务端拒绝。"""

    role_ids: list[UUID] = Field(max_length=500)

    @model_validator(mode="after")
    def role_ids_must_be_unique(self):
        if len(set(self.role_ids)) != len(self.role_ids):
            raise ValueError("角色列表不能包含重复项")
        return self
