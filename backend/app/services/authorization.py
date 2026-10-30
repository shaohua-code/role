"""集中执行租户内 RBAC 和数据范围判定，供业务 API 与管理模拟共用。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.models.application import Application
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.models.model_catalog import ModelCatalog
from app.models.organization import MembershipOrganization, Organization, RoleDataScope
from app.services.effective_roles import authorized_role_ids_statement
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.schemas.access_control import AuthorizationCheck


# 即使应用停用，也必须允许有权限的管理员查看它并重新启用。
APPLICATION_ADMIN_PERMISSION_CODES = frozenset({
    "app.read",
    "app.manage",
    "app.secret.rotate",
})


def evaluate_access(body: AuthorizationCheck, user: User, db: Session, *, enforce_token_context: bool = True) -> dict:
    """用默认拒绝规则判定授权，并保留管理模拟需要的命中详情。"""
    checks: list[dict] = []
    matching_roles: list[dict] = []

    def record(check: str, passed: bool | None, reason: str) -> None:
        checks.append({"check": check, "passed": passed, "reason": reason})

    def finish(allowed: bool, reason: str, data_scope: dict | None = None) -> dict:
        decision = {"allowed": allowed, "reason": reason}
        if data_scope is not None:
            decision["data_scope"] = data_scope
        return {"decision": decision, "checks": checks, "matching_roles": matching_roles}

    if user.status != "active":
        record("user", False, "user_inactive")
        return finish(False, "user_inactive")
    record("user", True, "user_active")

    # OIDC access tokens 绑定租户和应用；管理模拟以明确选择的用户为主体，不带 token 限定。
    oidc_tenant_id = getattr(user, "_oidc_tenant_id", None) if enforce_token_context else None
    oidc_application_id = getattr(user, "_oidc_application_id", None) if enforce_token_context else None
    if oidc_tenant_id and body.tenant_id != oidc_tenant_id:
        record("token_context", False, "token_tenant_mismatch")
        return finish(False, "token_tenant_mismatch")
    if oidc_application_id and body.application_id not in (None, oidc_application_id):
        record("token_context", False, "token_application_mismatch")
        return finish(False, "token_application_mismatch")
    record("token_context", True, "token_context_valid")
    tenant_id = oidc_tenant_id or body.tenant_id
    application_id = oidc_application_id or body.application_id
    active_tenant = db.scalar(select(Tenant.id).where(Tenant.id == tenant_id, Tenant.status == "active"))
    if not active_tenant:
        record("tenant", False, "tenant_inactive_or_missing")
        return finish(False, "tenant_inactive_or_missing")
    record("tenant", True, "tenant_active")

    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.status == "active",
    ))
    if not membership:
        record("membership", False, "no_active_tenant_membership")
        return finish(False, "no_active_tenant_membership")
    record("membership", True, "active_tenant_membership")

    if application_id:
        application = db.get(Application, application_id)
        if (not application or application.tenant_id != tenant_id
                or (application.status != "active"
                    and body.permission_code not in APPLICATION_ADMIN_PERMISSION_CODES)):
            record("application", False, "application_not_in_tenant_or_inactive")
            return finish(False, "application_not_in_tenant_or_inactive")
    record("application", True, "application_valid" if application_id else "tenant_wide_request")

    if body.permission_code == "model.invoke":
        try:
            model_id = UUID(body.resource_id or "")
        except ValueError:
            record("model", False, "model_resource_id_required")
            return finish(False, "model_resource_id_required")
        model = db.get(ModelCatalog, model_id)
        if not model or model.tenant_id != tenant_id or model.status != "active":
            record("model", False, "model_inactive_or_not_in_tenant")
            return finish(False, "model_inactive_or_not_in_tenant")
        record("model", True, "model_active")

    # 直接角色与活动用户组角色均按同一租户成员身份计算；组已停用时保留配置但不授予权限。
    # 角色集合复用全站唯一的有效角色实现（evaluate_access / OIDC 入场 / rbac_guards 共用）。
    authorized_role_ids = authorized_role_ids_statement(membership.id, tenant_id)

    statement = (select(
        RolePermission.role_id,
        Permission.id.label("permission_id"),
        Permission.requires_data_scope.label("requires_data_scope"),
        Role.key.label("role_key"),
        Role.name.label("role_name"),
        Role.application_id,
        RolePermission.resource_id,
    )
        .join(Role, Role.id == RolePermission.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            Role.id.in_(authorized_role_ids),
            Role.status == "active",
            Role.tenant_id == tenant_id,
            Permission.code == body.permission_code,
            Permission.status == "active",
            or_(RolePermission.resource_id.is_(None), RolePermission.resource_id == body.resource_id),
        ))
    if application_id:
        statement = statement.where(or_(Role.application_id.is_(None), Role.application_id == application_id))
    else:
        statement = statement.where(Role.application_id.is_(None))
    matching_grants = db.execute(statement).all()
    matching_roles.extend({
        "id": str(row.role_id),
        "key": row.role_key,
        "name": row.role_name,
        "application_id": str(row.application_id) if row.application_id else None,
        "resource_id": row.resource_id,
    } for row in matching_grants)
    if not matching_grants:
        record("permission_grant", False, "no_matching_grant")
        return finish(False, "no_matching_grant")
    record("permission_grant", True, "matching_role_grant")
    # 绿场规则：业务权限（requires_data_scope=true）忽略调用方 include_data_scope=False，
    # 强制解析数据范围；管理面码可不带 scope 直接放行。
    permission_requires_scope = bool(matching_grants[0].requires_data_scope)
    if not body.include_data_scope and not permission_requires_scope:
        record("data_scope", None, "not_requested")
        return finish(True, "matching_role_grant")

    # 只读取本次命中的角色策略，不能把其它角色的数据范围混入判定。
    matched_role_ids = {row.role_id for row in matching_grants}
    permission_id = matching_grants[0].permission_id
    policies = db.scalars(select(RoleDataScope).where(
        RoleDataScope.tenant_id == tenant_id,
        RoleDataScope.role_id.in_(matched_role_ids),
        RoleDataScope.permission_id == permission_id,
    )).all()
    if not policies:
        record("data_scope", False, "data_scope_policy_missing")
        return finish(False, "data_scope_policy_missing")

    scopes = {policy.scope_type for policy in policies}
    # 任一策略声明 tenant 范围即整租户放行，跳过组织/个人级过滤。
    if "tenant" in scopes:
        data_scope = {"mode": "any_of", "constraints": [{"kind": "tenant", "tenant_id": str(tenant_id)}]}
        record("data_scope", True, "tenant_scope")
        return finish(True, "matching_role_grant", data_scope)

    clauses: list[dict] = []
    if "self" in scopes:
        # 全局用户 ID 可能跨租户复用，self 条件必须同时匹配 tenant_id。
        clauses.append({"kind": "owner", "field": "owner_user_id", "user_id": str(user.id),
                        "tenant_id": str(tenant_id)})

    organization_scope_types = scopes & {"organization", "organization_tree"}
    scoped_organization_ids: set[UUID] = set()
    if organization_scope_types:
        assigned_ids = set(db.scalars(select(MembershipOrganization.organization_id).join(
            Organization, Organization.id == MembershipOrganization.organization_id,
        ).where(
            MembershipOrganization.membership_id == membership.id,
            MembershipOrganization.tenant_id == tenant_id,
            Organization.status == "active",
        )).all())
        active_organizations = db.scalars(select(Organization).where(
            Organization.tenant_id == tenant_id,
            Organization.status == "active",
        )).all()
        if "organization" in organization_scope_types:
            scoped_organization_ids.update(assigned_ids)
        if "organization_tree" in organization_scope_types:
            # 从分配组织沿父指针向下 BFS，把可见范围扩展到全部子孙组织。
            children_by_parent: dict[UUID | None, set[UUID]] = {}
            for organization in active_organizations:
                children_by_parent.setdefault(organization.parent_id, set()).add(organization.id)
            pending = list(assigned_ids)
            scoped_organization_ids.update(assigned_ids)
            while pending:
                children = children_by_parent.get(pending.pop(), set()) - scoped_organization_ids
                scoped_organization_ids.update(children)
                pending.extend(children)

    for policy in policies:
        if policy.scope_type == "selected_organizations":
            scoped_organization_ids.update(UUID(value) for value in policy.organization_ids)
    if scoped_organization_ids:
        # 写策略时检查租户归属，运行时仍二次过滤停用组织和历史脏数据。
        current_organization_ids = set(db.scalars(select(Organization.id).where(
            Organization.id.in_(scoped_organization_ids),
            Organization.tenant_id == tenant_id,
            Organization.status == "active",
        )).all())
        clauses.append({"kind": "organizations", "field": "organization_id",
                        "tenant_id": str(tenant_id),
                        "organization_ids": sorted(map(str, current_organization_ids))})
    if not clauses:
        record("data_scope", False, "data_scope_resolves_to_empty")
        return finish(False, "data_scope_resolves_to_empty")
    record("data_scope", True, "data_scope_resolved")
    return finish(True, "matching_role_grant", {"mode": "any_of", "constraints": clauses})
