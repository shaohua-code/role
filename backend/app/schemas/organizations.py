"""组织结构、成员组织关系和角色数据范围的 API 契约。"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrganizationCreate(BaseModel):
    tenant_id: UUID
    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=160)
    parent_id: UUID | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")
    parent_id: UUID | None = None


class MembershipOrganizationsUpdate(BaseModel):
    tenant_id: UUID
    organization_ids: list[UUID] = Field(max_length=100)
    primary_organization_id: UUID | None = None

    @model_validator(mode="after")
    def primary_must_be_assigned(self):
        if self.primary_organization_id and self.primary_organization_id not in self.organization_ids:
            raise ValueError("主组织必须同时包含在 organization_ids 中")
        if len(set(self.organization_ids)) != len(self.organization_ids):
            raise ValueError("组织列表不能包含重复项")
        return self


class MembershipStatusUpdate(BaseModel):
    """成员状态是租户范围状态，不能用它停用用户的其他租户身份。"""

    model_config = ConfigDict(extra="forbid")

    expected_status: Literal["active", "disabled", "departed"]
    status: Literal["active", "disabled", "departed"]


class RoleDataScopeItem(BaseModel):
    permission_id: UUID
    scope_type: str = Field(pattern=r"^(tenant|self|organization|organization_tree|selected_organizations)$")
    organization_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_scope_payload(self):
        if self.scope_type == "selected_organizations" and not self.organization_ids:
            raise ValueError("指定组织范围必须至少选择一个组织")
        if self.scope_type != "selected_organizations" and self.organization_ids:
            raise ValueError("只有指定组织范围可以携带 organization_ids")
        if len(set(self.organization_ids)) != len(self.organization_ids):
            raise ValueError("组织列表不能包含重复项")
        return self


class RoleDataScopesUpdate(BaseModel):
    policies: list[RoleDataScopeItem] = Field(max_length=200)

    @model_validator(mode="after")
    def permission_must_be_unique(self):
        permission_ids = [row.permission_id for row in self.policies]
        if len(set(permission_ids)) != len(permission_ids):
            raise ValueError("同一角色下一个权限只能配置一条数据范围策略")
        return self
