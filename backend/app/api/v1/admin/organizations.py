"""租户组织结构、成员归属和角色数据范围管理路由。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user, is_platform_admin_user
from app.db.session import get_db_session
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.application import Application
from app.models.groups import UserGroupMembership
from app.models.identity import Tenant, TenantMembership, User
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.models.organization import MembershipOrganization, Organization, RoleDataScope
from app.services.admin_authorization import (
    has_application_admin_access,
    has_organization_admin_access,
    require_organization_admin_access,
)
from app.services.rbac_guards import bump_memberships_holding_role
from app.schemas.organizations import (
    MembershipOrganizationsUpdate,
    MembershipStatusUpdate,
    OrganizationCreate,
    OrganizationUpdate,
    RoleDataScopesUpdate,
)
from app.db.seed_greenfield import PLATFORM_TENANT_SLUG

router = APIRouter(tags=["组织与数据范围"])


@router.get("/organizations")
def list_organizations(tenant_id: UUID, actor: User = Depends(current_user),
                       db: Session = Depends(get_db_session)) -> list[dict]:
    """组织树以平面记录返回，避免深层结构形成不可控的大型嵌套响应。"""
    require_organization_admin_access(actor, tenant_id, db)
    if not db.get(Tenant, tenant_id):
        raise HTTPException(404, "租户不存在")
    rows = db.scalars(select(Organization).where(Organization.tenant_id == tenant_id)
                      .order_by(Organization.key).limit(2000)).all()
    names = {row.id: row.name for row in rows}
    # G24 部门负责人展示名：一次拉取本租户用户名映射，避免逐行查询。
    owner_ids = {row.owner_user_id for row in rows if row.owner_user_id}
    owner_names = dict(db.execute(select(User.id, User.display_name).where(User.id.in_(owner_ids))).all()) if owner_ids else {}
    # parent_id 供组织工作台前端拼层级树；旧列表页只消费 parent_name，新增字段向后兼容。
    return [{"id": str(row.id), "tenant_id": str(row.tenant_id),
             "parent_id": str(row.parent_id) if row.parent_id else None,
             "parent_name": names.get(row.parent_id, "顶层组织") if row.parent_id else "顶层组织",
             "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
             "owner_name": owner_names.get(row.owner_user_id) if row.owner_user_id else None,
             "key": row.key, "name": row.name, "status": row.status, "created_at": row.created_at} for row in rows]


@router.get("/organizations/{organization_id}/members")
def list_organization_members(
    organization_id: UUID,
    q: str | None = Query(default=None, max_length=100),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """Wave 2 组织工作台「成员」Tab：列出直接挂接该组织的成员（只读，不递归子组织）。"""
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(404, "组织不存在")
    require_organization_admin_access(actor, organization.tenant_id, db)
    stmt = (select(MembershipOrganization, TenantMembership, User)
            .join(TenantMembership, TenantMembership.id == MembershipOrganization.membership_id)
            .join(User, User.id == TenantMembership.user_id)
            .where(MembershipOrganization.organization_id == organization.id))
    search = q.strip()[:100] if q else ""
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(User.display_name.ilike(pattern) | User.email.ilike(pattern))
    rows = db.execute(stmt.order_by(User.display_name, User.email).limit(1000)).all()
    return [{
        "user_id": str(user.id),
        "membership_id": str(membership.id),
        "email": user.email,
        "display_name": user.display_name,
        "user_status": user.status,
        "membership_status": membership.status,
        "is_primary": link.is_primary,
    } for link, membership, user in rows]


@router.get("/members")
def list_tenant_members(
    tenant_id: UUID,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
    actor: User = Depends(current_user),
) -> dict:
    """只列出目标租户自己的成员；搜索条件不能扩大到其他租户的全局身份。"""
    require_organization_admin_access(actor, tenant_id, db)
    if not db.get(Tenant, tenant_id):
        raise HTTPException(404, "租户不存在")

    stmt = select(TenantMembership, User).join(User, User.id == TenantMembership.user_id).where(
        TenantMembership.tenant_id == tenant_id,
    )
    count_stmt = select(func.count()).select_from(TenantMembership).join(
        User, User.id == TenantMembership.user_id,
    ).where(TenantMembership.tenant_id == tenant_id)
    search = q.strip()[:100] if q else ""
    if search:
        pattern = f"%{search}%"
        predicate = User.display_name.ilike(pattern) | User.email.ilike(pattern)
        stmt = stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)

    rows = db.execute(stmt.order_by(User.display_name, User.email, TenantMembership.id)
                      .limit(limit).offset(offset)).all()
    return {
        "items": [{
            "user_id": str(user.id),
            "tenant_id": str(membership.tenant_id),
            "email": user.email,
            "display_name": user.display_name,
            "user_status": user.status,
            "membership_status": membership.status,
            "created_at": membership.created_at,
        } for membership, user in rows],
        "total": int(db.scalar(count_stmt) or 0),
        "limit": limit,
        "offset": offset,
    }


@router.get("/roles")
def list_tenant_roles(tenant_id: UUID, actor: User = Depends(current_user),
                      db: Session = Depends(get_db_session)) -> list[dict]:
    """角色目录强制限制在授权租户内，供租户管理员配置该租户的数据范围。"""
    require_organization_admin_access(actor, tenant_id, db)
    if not db.get(Tenant, tenant_id):
        raise HTTPException(404, "租户不存在")
    roles = db.scalars(select(Role).where(Role.tenant_id == tenant_id)
                       .order_by(Role.name, Role.key).limit(500)).all()
    return [{
        "id": str(role.id),
        "tenant_id": str(role.tenant_id),
        "application_id": str(role.application_id) if role.application_id else None,
        "key": role.key,
        "name": role.name,
        "status": role.status,
    } for role in roles]


@router.post("/organizations", status_code=201)
def create_organization(body: OrganizationCreate, request: Request,
                        actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """新组织的父节点必须是同一活动租户里的有效部门。"""
    require_organization_admin_access(actor, body.tenant_id, db, manage=True)
    tenant = db.get(Tenant, body.tenant_id)
    if not tenant or tenant.status != "active":
        raise HTTPException(404, "活动租户不存在")
    # 平台引导租户是 L1 宿主与系统应用载体，业务组织挂上去会污染平台保留域。
    if tenant.slug == PLATFORM_TENANT_SLUG:
        raise HTTPException(422, "平台引导租户为系统保留租户，不支持业务组织")
    if not body.name.strip():
        raise HTTPException(422, "组织名称不能为空")
    if body.parent_id:
        parent = db.get(Organization, body.parent_id)
        if not parent or parent.tenant_id != tenant.id or parent.status != "active":
            raise HTTPException(422, "父组织必须属于同一活动租户")
    # G24 部门负责人：必须是该租户的活动成员（跨租户/不存在成员拒绝）。
    if body.owner_user_id:
        owner_membership = db.scalar(select(TenantMembership).where(
            TenantMembership.user_id == body.owner_user_id, TenantMembership.tenant_id == tenant.id,
            TenantMembership.status == "active",
        ))
        if not owner_membership:
            raise HTTPException(422, "负责人必须是该租户的活动成员")
    row = Organization(tenant_id=tenant.id, parent_id=body.parent_id,
                       key=body.key, name=body.name.strip(), owner_user_id=body.owner_user_id)
    db.add(row)
    flush_or_conflict(db)
    audit(db, actor, request, "organization.create", "organization", str(row.id),
          {"tenant_id": str(tenant.id), "key": row.key, "parent_id": str(row.parent_id) if row.parent_id else None,
           "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None})
    commit_or_conflict(db)
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "parent_id": str(row.parent_id) if row.parent_id else None,
            "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
            "key": row.key, "name": row.name, "status": row.status}


@router.patch("/organizations/{organization_id}")
def update_organization(organization_id: UUID, body: OrganizationUpdate, request: Request,
                        actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """编辑组织名称/状态/父节点，并拒绝自引用和向下移动导致的循环。"""
    row = db.get(Organization, organization_id)
    if not row:
        raise HTTPException(404, "组织不存在")
    if not has_organization_admin_access(actor, row.tenant_id, db, manage=True):
        raise HTTPException(404, "组织不存在")
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(422, "组织名称不能为空")
        row.name = body.name.strip()
    if body.status is not None:
        row.status = body.status
    if "parent_id" in body.model_fields_set:
        cursor_id = body.parent_id
        visited: set[UUID] = set()
        while cursor_id:
            if cursor_id == row.id or cursor_id in visited:
                raise HTTPException(422, "父组织关系不能形成循环")
            visited.add(cursor_id)
            parent = db.get(Organization, cursor_id)
            if not parent or parent.tenant_id != row.tenant_id or parent.status != "active":
                raise HTTPException(422, "父组织必须属于同一租户且处于启用状态")
            cursor_id = parent.parent_id
        row.parent_id = body.parent_id
    # G24 负责人变更：None 表示清空；指定时校验活动成员归属，变更写入审计。
    previous_owner = row.owner_user_id
    if "owner_user_id" in body.model_fields_set:
        if body.owner_user_id:
            owner_membership = db.scalar(select(TenantMembership).where(
                TenantMembership.user_id == body.owner_user_id, TenantMembership.tenant_id == row.tenant_id,
                TenantMembership.status == "active",
            ))
            if not owner_membership:
                raise HTTPException(422, "负责人必须是该租户的活动成员")
        row.owner_user_id = body.owner_user_id
    audit(db, actor, request, "organization.update", "organization", str(row.id),
          {"tenant_id": str(row.tenant_id), "status": row.status, "parent_id": str(row.parent_id) if row.parent_id else None,
           "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None})
    if previous_owner != row.owner_user_id:
        audit(db, actor, request, "organization.owner.change", "organization", str(row.id),
              {"tenant_id": str(row.tenant_id),
               "from_owner_user_id": str(previous_owner) if previous_owner else None,
               "to_owner_user_id": str(row.owner_user_id) if row.owner_user_id else None})
    commit_or_conflict(db)
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "parent_id": str(row.parent_id) if row.parent_id else None,
            "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
            "key": row.key, "name": row.name, "status": row.status}


@router.delete("/organizations/{organization_id}", status_code=204)
def delete_organization(organization_id: UUID, request: Request,
                        actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> None:
    """删除组织：成员挂接随外键级联摘除（成员本身保留）；存在子组织时阻塞。

    RoleDataScope 的 organization_ids 为 JSON 列（非外键），删除后相关数据范围中的
    组织 ID 失效并按「无有效范围默认拒绝」语义收敛，不阻塞删除。
    """
    row = db.scalar(select(Organization).where(Organization.id == organization_id).with_for_update())
    if not row:
        raise HTTPException(404, "组织不存在")
    if not has_organization_admin_access(actor, row.tenant_id, db, manage=True):
        raise HTTPException(404, "组织不存在")
    # 父引用为 RESTRICT：必须先删除或移动子组织，避免留下孤儿层级。
    child_exists = db.scalar(select(Organization.id).where(Organization.parent_id == row.id).limit(1))
    if child_exists:
        raise HTTPException(409, "该组织存在子组织，请先删除或移动子组织")
    audit(db, actor, request, "organization.delete", "organization", str(row.id),
          {"tenant_id": str(row.tenant_id), "key": row.key, "name": row.name})
    db.delete(row)
    commit_or_conflict(db)


@router.get("/users/{user_id}/organizations")
def get_user_organizations(user_id: UUID, tenant_id: UUID, actor: User = Depends(current_user),
                           db: Session = Depends(get_db_session)) -> dict:
    """查看用户在指定租户的组织挂接与主组织（共享序列化见 _user_organization_payload）。"""
    require_organization_admin_access(actor, tenant_id, db)
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == user_id,
                                                            TenantMembership.tenant_id == tenant_id))
    if not membership:
        raise HTTPException(404, "用户不属于该租户")
    return _user_organization_payload(user_id, tenant_id, membership.id, db)


def _user_organization_payload(user_id: UUID, tenant_id: UUID, membership_id: UUID,
                               db: Session) -> dict:
    """共享只读序列化逻辑，避免写路由绕过 actor 授权直接调用另一个路由函数。"""
    rows = db.execute(select(MembershipOrganization, Organization).join(
        Organization, Organization.id == MembershipOrganization.organization_id).where(
            MembershipOrganization.membership_id == membership_id,
            MembershipOrganization.tenant_id == tenant_id,
        ).order_by(Organization.key)).all()
    return {"tenant_id": str(tenant_id), "user_id": str(user_id),
            "organization_ids": [str(link.organization_id) for link, _ in rows],
            "primary_organization_id": next((str(link.organization_id) for link, _ in rows if link.is_primary), None),
            "organizations": [{"id": str(org.id), "key": org.key, "name": org.name, "status": org.status}
                              for _, org in rows]}


@router.get("/users/{user_id}/memberships")
def list_user_memberships(user_id: UUID, actor: User = Depends(current_user),
                          db: Session = Depends(get_db_session)) -> list[dict]:
    """本人可查看自己的租户关系；查询其他用户时仅返回组织管理员有权查看的租户。"""
    platform_admin = is_platform_admin_user(actor, db)
    if platform_admin and not db.get(User, user_id):
        raise HTTPException(404, "用户不存在")
    rows = db.execute(select(TenantMembership, Tenant).join(Tenant, Tenant.id == TenantMembership.tenant_id)
                      .where(TenantMembership.user_id == user_id).order_by(Tenant.name)).all()
    return [{"tenant_id": str(membership.tenant_id), "tenant_name": tenant.name, "tenant_kind": tenant.kind,
             "membership_status": membership.status, "tenant_status": tenant.status}
            for membership, tenant in rows
            if platform_admin
            or has_organization_admin_access(actor, tenant.id, db)
            # 自己的 membership 是身份上下文发现信息；它不授予跨用户成员目录读取权。
            or user_id == actor.id]


@router.patch("/users/{user_id}/memberships/{tenant_id}/status")
def set_user_membership_status(
    user_id: UUID,
    tenant_id: UUID,
    body: MembershipStatusUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """停用只暂停单租户访问；离职会清除该租户授权并要求重新邀请后才能加入。"""
    # organizations_router 同时挂在 /admin 与 /tenant-admin 下；必须在 handler 内
    # 再按目标 tenant 做 manage 判权，不能依赖 platform-admin 聚合路由的保护。
    require_organization_admin_access(actor, tenant_id, db, manage=True)
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user_id,
        TenantMembership.tenant_id == tenant_id,
    ).with_for_update())
    if not membership:
        raise HTTPException(404, "租户成员不存在")
    if user_id == actor.id and body.status != "active":
        raise HTTPException(400, "不能停用或标记自己离开当前租户")
    if membership.status != body.expected_status:
        raise HTTPException(status_code=409, detail="成员状态已被其他管理员修改，请刷新后重试")
    if membership.status == body.status:
        return {"user_id": str(user_id), "tenant_id": str(tenant_id), "status": membership.status}
    if membership.status == "departed":
        raise HTTPException(409, "离职成员必须通过新的租户邀请重新加入")

    now = datetime.now(timezone.utc)
    if body.status in {"disabled", "departed"}:
        # 只撤销该租户应用的 OAuth 会话，避免误踢同一全局账号的其他产品。
        application_ids = select(Application.id).where(Application.tenant_id == tenant_id)
        db.execute(update(OAuthRefreshToken).where(
            OAuthRefreshToken.user_id == user_id,
            OAuthRefreshToken.application_id.in_(application_ids),
            OAuthRefreshToken.revoked_at.is_(None),
        ).values(revoked_at=now))
        db.execute(update(OAuthAuthorizationCode).where(
            OAuthAuthorizationCode.user_id == user_id,
            OAuthAuthorizationCode.application_id.in_(application_ids),
            OAuthAuthorizationCode.consumed_at.is_(None),
        ).values(consumed_at=now))
        db.execute(update(OAuthConsentRequest).where(
            OAuthConsentRequest.user_id == user_id,
            OAuthConsentRequest.application_id.in_(application_ids),
            OAuthConsentRequest.consumed_at.is_(None),
        ).values(consumed_at=now))
    if body.status == "departed":
        # departed 是历史身份状态，不删除 membership 主记录和审计轨迹，但彻底移除旧授权关系。
        db.execute(delete(RoleBinding).where(RoleBinding.membership_id == membership.id))
        db.execute(delete(UserGroupMembership).where(UserGroupMembership.membership_id == membership.id))
        db.execute(delete(MembershipOrganization).where(MembershipOrganization.membership_id == membership.id))

    previous_status = membership.status
    membership.status = body.status
    # 让离线验签的 resource server 也能在 token 中识别旧授权版本；恢复成员时旧 JWT 不会复活。
    membership.auth_version = (membership.auth_version or 1) + 1
    audit(db, actor, request, "membership.status.change", "user", str(user_id), {
        "tenant_id": str(tenant_id), "from_status": previous_status, "to_status": body.status,
    })
    commit_or_conflict(db)
    return {"user_id": str(user_id), "tenant_id": str(tenant_id), "status": membership.status,
            "membership_version": membership.auth_version}


@router.put("/users/{user_id}/organizations")
def set_user_organizations(user_id: UUID, body: MembershipOrganizationsUpdate, request: Request,
                           actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """替换用户在单个租户中的组织归属；跨租户关系还由 PostgreSQL 复合外键兜底。"""
    require_organization_admin_access(actor, body.tenant_id, db, manage=True)
    tenant = db.get(Tenant, body.tenant_id)
    if not tenant or tenant.status != "active":
        raise HTTPException(404, "活动租户不存在")
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == user_id,
                                                            TenantMembership.tenant_id == body.tenant_id,
                                                            TenantMembership.status == "active"))
    if not membership:
        raise HTTPException(404, "活动租户成员不存在")
    orgs = db.scalars(select(Organization).where(Organization.id.in_(body.organization_ids),
                                                Organization.tenant_id == body.tenant_id,
                                                Organization.status == "active")).all() if body.organization_ids else []
    if len(orgs) != len(body.organization_ids):
        raise HTTPException(422, "组织列表包含不存在、停用或跨租户组织")
    db.execute(delete(MembershipOrganization).where(MembershipOrganization.membership_id == membership.id))
    db.add_all([MembershipOrganization(membership_id=membership.id, tenant_id=body.tenant_id,
                                       organization_id=org.id, is_primary=(org.id == body.primary_organization_id))
                for org in orgs])
    audit(db, actor, request, "membership.organizations.replace", "user", str(user_id),
          {"tenant_id": str(body.tenant_id), "organization_count": len(orgs),
           "primary_organization_id": str(body.primary_organization_id) if body.primary_organization_id else None})
    commit_or_conflict(db)
    return _user_organization_payload(user_id, body.tenant_id, membership.id, db)


@router.get("/roles/{role_id}/data-scopes")
def get_role_data_scopes(role_id: UUID, actor: User = Depends(current_user),
                         db: Session = Depends(get_db_session)) -> list[dict]:
    """读取角色当前的数据范围策略清单（跨租户/无权角色统一 404）。"""
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    if not has_organization_admin_access(actor, role.tenant_id, db):
        raise HTTPException(404, "角色不存在")
    return _role_data_scopes_payload(role, db)


@router.get("/roles/{role_id}/permissions")
def list_tenant_role_permissions(role_id: UUID, actor: User = Depends(current_user),
                                 db: Session = Depends(get_db_session)) -> list[dict]:
    """返回该租户角色已有的权限编码，数据范围编辑器不得读取全局权限目录。"""
    role = db.get(Role, role_id)
    if not role or not has_organization_admin_access(actor, role.tenant_id, db):
        raise HTTPException(404, "角色不存在")
    rows = db.execute(
        select(Permission.id, Permission.code, Permission.status)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
        .distinct()
        .order_by(Permission.code)
    ).all()
    return [{"id": str(permission_id), "code": code, "status": status}
            for permission_id, code, status in rows]


def _role_data_scopes_payload(role: Role, db: Session) -> list[dict]:
    """共享策略序列化；写路由不能直接调用带 FastAPI Depends 参数的 GET handler。"""
    rows = db.execute(select(RoleDataScope, Permission).join(Permission, Permission.id == RoleDataScope.permission_id)
                      .where(RoleDataScope.role_id == role.id).order_by(Permission.code)).all()
    return [{"id": str(policy.id), "permission_id": str(permission.id), "permission_code": permission.code,
             "scope_type": policy.scope_type, "organization_ids": [str(value) for value in policy.organization_ids]}
            for policy, permission in rows]


@router.put("/roles/{role_id}/data-scopes")
def replace_role_data_scopes(role_id: UUID, body: RoleDataScopesUpdate, request: Request,
                             actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> list[dict]:
    """批量替换角色数据范围；权限唯一、组织清单必须属于角色所在租户。"""
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    if not has_organization_admin_access(actor, role.tenant_id, db, manage=True):
        raise HTTPException(404, "角色不存在")
    # 与权限撤销共享角色行锁，确保数据范围不会和其前置授权发生竞态。
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    if not role:
        raise HTTPException(404, "角色不存在")
    permission_ids = [item.permission_id for item in body.policies]
    permissions = db.scalars(select(Permission).where(Permission.id.in_(permission_ids))).all() if permission_ids else []
    if len(permissions) != len(permission_ids):
        raise HTTPException(422, "权限目录中存在无效权限")
    granted_permission_ids = set(db.scalars(select(RolePermission.permission_id).where(
        RolePermission.role_id == role.id, RolePermission.permission_id.in_(permission_ids),
    )).all()) if permission_ids else set()
    if granted_permission_ids != set(permission_ids):
        raise HTTPException(422, "数据范围只能配置在该角色已经授予的权限上")
    org_ids = {org_id for item in body.policies for org_id in item.organization_ids}
    organizations = db.scalars(select(Organization).where(Organization.id.in_(org_ids),
                                                           Organization.tenant_id == role.tenant_id,
                                                           Organization.status == "active")).all() if org_ids else []
    if len(organizations) != len(org_ids):
        raise HTTPException(422, "指定组织范围包含无效、停用或跨租户组织")
    db.execute(delete(RoleDataScope).where(RoleDataScope.role_id == role.id))
    db.add_all([RoleDataScope(tenant_id=role.tenant_id, role_id=role.id, permission_id=item.permission_id,
                              scope_type=item.scope_type, organization_ids=[str(value) for value in item.organization_ids])
                for item in body.policies])
    # 数据范围替换即时收敛持有者旧凭证（绿场规则：数据范围变更建议 bump）。
    bump_memberships_holding_role(db, role.id)
    audit(db, actor, request, "role.data_scopes.replace", "role", str(role.id),
          {"tenant_id": str(role.tenant_id), "policy_count": len(body.policies)})
    commit_or_conflict(db)
    return _role_data_scopes_payload(role, db)
