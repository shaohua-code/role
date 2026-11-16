"""租户成员身份和状态管理路由。"""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user, hash_password, is_platform_admin_user
from app.db.seed_greenfield import PLATFORM_TENANT_SLUG
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupRole
from app.models.identity import (AuditEvent, PasswordResetToken, RefreshSession, Tenant,
                                 TenantMembership, User)
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.models.organization import MembershipOrganization, Organization
from app.schemas.auth import AdminPasswordReset, AdminUserCreate, UserStatusUpdate
from app.services.backchannel_logout import BackchannelLogoutService
from app.services.effective_roles import EffectiveRoleResolver
from app.services.rbac_guards import ActorVisibility, PermissionEnforcer
from app.services.permission_kinds import ROLE_SCOPE_TENANT
from app.services.role_provisioning import (
    L1_ROLE_KEY,
    L2_ROLE_KEY,
    L3_ROLE_KEY,
    L4_ROLE_KEY,
    TEMPLATE_ROLE_KEYS,
    RoleProvisioning,
)

router = APIRouter(tags=["用户管理"])


def _assert_user_within_actor_boundary(actor: User, db: Session, user: User) -> None:
    """目标用户边界闸：读/写路径统一（超管放行，404 隐藏存在性）。

    1. 数据边界：目标用户至少一个活跃成员身份落在操作者管理租户范围内；
    2. 层级保护：非超管不得操作持有平台类角色（application_id IS NULL，含
       platform.admin / tenant.admin 模板与全局自定义）的账号——租户/应用级
       管理员停用、重置或枚举上级账号是平台接管链入口，一律 404。
    """
    if is_platform_admin_user(actor, db):
        return
    tenant_scope = ActorVisibility.list_actor_management_tenant_ids(actor, db) or set()
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.status == "active",
    )).all()
    if not any(membership.tenant_id in tenant_scope for membership in memberships):
        raise HTTPException(404, "用户不存在")
    holds_platform_role = db.scalar(
        select(Role.id)
        .join(RoleBinding, RoleBinding.role_id == Role.id)
        .join(TenantMembership, TenantMembership.id == RoleBinding.membership_id)
        .where(
            TenantMembership.user_id == user.id,
            TenantMembership.status == "active",
            Role.status == "active",
            Role.application_id.is_(None),
        )
        .limit(1)
    )
    if holds_platform_role:
        raise HTTPException(404, "用户不存在")


@router.get("/users/{user_id}/sessions")
def list_user_sessions(user_id: UUID, actor: User = Depends(current_user),
                      db: Session = Depends(get_db_session)) -> dict:
    """列出仍可续期的管理台与 OIDC 会话，不暴露任何 refresh token 摘要。"""
    PermissionEnforcer.ensure_codes(actor, db, "menu.users", detail="缺少管理权限：menu.users")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    # 数据边界：非超管只能查看自身管理租户内成员的会话。
    _assert_user_within_actor_boundary(actor, db, user)
    now = datetime.now(timezone.utc)
    items: list[dict] = []

    # IAM refresh session 的 ID 在轮换时保持不变，因此 access/refresh 凭证可一起即时撤销。
    management_sessions = db.scalars(select(RefreshSession).where(
        RefreshSession.user_id == user_id,
        RefreshSession.revoked_at.is_(None),
        RefreshSession.expires_at > now,
    ).order_by(RefreshSession.created_at.desc())).all()
    items.extend({
        "id": str(session.id),
        "type": "management",
        "application_name": "IAM 管理台",
        "client_id": None,
        "created_at": session.created_at,
        "expires_at": session.expires_at,
    } for session in management_sessions)

    # OIDC 轮换历史保留在同一 family；用最早创建时间展示会话起始时间，只列当前有效的 family。
    family_history = (
        select(OAuthRefreshToken.family_id.label("family_id"),
               func.min(OAuthRefreshToken.created_at).label("started_at"))
        .where(OAuthRefreshToken.user_id == user_id)
        .group_by(OAuthRefreshToken.family_id)
        .subquery()
    )
    oidc_sessions = db.execute(
        select(OAuthRefreshToken, Application, family_history.c.started_at)
        .join(Application, Application.id == OAuthRefreshToken.application_id)
        .join(family_history, family_history.c.family_id == OAuthRefreshToken.family_id)
        .where(
            OAuthRefreshToken.user_id == user_id,
            OAuthRefreshToken.revoked_at.is_(None),
            OAuthRefreshToken.expires_at > now,
        )
        .order_by(OAuthRefreshToken.created_at.desc())
    ).all()
    seen_families: set[UUID] = set()
    for session, application, started_at in oidc_sessions:
        if session.family_id in seen_families:
            continue
        seen_families.add(session.family_id)
        items.append({
            "id": str(session.family_id),
            "type": "oidc",
            "application_name": application.name,
            "client_id": application.client_id,
            "created_at": started_at,
            "expires_at": session.expires_at,
        })

    items.sort(key=lambda item: item["created_at"] or now, reverse=True)
    return {"user_id": str(user_id), "items": items}


@router.post("/users/{user_id}/sessions/{session_type}/{session_id}/revoke")
def revoke_user_session(
    user_id: UUID,
    session_type: Literal["management", "oidc"],
    session_id: UUID,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """撤销一个用户会话并在同一事务写入管理审计。"""
    PermissionEnforcer.ensure_codes(actor, db, "button.users.manage", detail="缺少管理权限：button.users.manage")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    # 目标边界：非超管只能撤销自身管理租户内非平台角色账号的会话。
    _assert_user_within_actor_boundary(actor, db, user)
    # 避免管理员误操作当前身份导致管理台立即失去权限；本人仍可通过“安全退出”注销当前设备。
    if actor.id == user_id:
        raise HTTPException(400, "不能从用户管理中远程注销当前管理员账号；请使用安全退出")

    now = datetime.now(timezone.utc)
    application_id: UUID | None = None
    changed = False
    if session_type == "management":
        session = db.scalar(select(RefreshSession).where(
            RefreshSession.id == session_id,
            RefreshSession.user_id == user_id,
        ).with_for_update())
        if not session:
            raise HTTPException(404, "管理台会话不存在")
        if session.revoked_at is None:
            session.revoked_at = now
            changed = True
        revoked_at = session.revoked_at or now
    else:
        # 锁定同一 family 的轮换记录并撤销仍有效的子令牌；在线 access token 随即失效。
        family_rows = db.scalars(select(OAuthRefreshToken).where(
            OAuthRefreshToken.family_id == session_id,
            OAuthRefreshToken.user_id == user_id,
        ).order_by(OAuthRefreshToken.created_at.desc()).with_for_update()).all()
        if not family_rows:
            raise HTTPException(404, "OIDC 会话不存在")
        application_id = family_rows[0].application_id
        for row in family_rows:
            if row.revoked_at is None:
                row.revoked_at = now
                changed = True
        revoked_at = next((row.revoked_at for row in family_rows if row.revoked_at), now)

    if changed:
        audit(db, actor, request, "user.session.revoke", "auth_session", f"{session_type}:{session_id}", {
            "session_type": session_type,
            "application_id": str(application_id) if application_id else None,
        })
    commit_or_conflict(db)
    # G19：撤销 OIDC 会话族后向该应用的 back-channel 地址推送 logout_token（best-effort）。
    if changed and session_type == "oidc" and application_id:
        application = db.get(Application, application_id)
        if application:
            BackchannelLogoutService.deliver_backchannel_logout([application], user_id=user_id, session_id=session_id)
    return {"user_id": str(user_id), "session_type": session_type,
            "session_id": str(session_id), "revoked_at": revoked_at}

def list_user_effective_permissions(db: Session, user_id: UUID) -> list[dict]:
    """G28 有效权限码并集 + 来源（直授角色 / 用户组继承）。

    只统计活动成员身份、活动角色、活动权限；组停用不参与继承（与 EffectiveRoleResolver.list_effective_roles 同口径）。
    """
    membership_rows = db.execute(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == user_id, TenantMembership.status == "active")
        .order_by(Tenant.name)
    ).all()
    aggregated: dict[str, dict] = {}
    for membership, tenant in membership_rows:
        role_ids = list(db.scalars(EffectiveRoleResolver.authorized_role_ids_statement(membership.id, tenant.id)).all())
        if not role_ids:
            continue
        roles = list(db.scalars(
            select(Role).where(Role.id.in_(role_ids), Role.status == "active"),
        ).all())
        if not roles:
            continue
        role_by_id = {role.id: role for role in roles}
        direct_ids = set(db.scalars(
            select(RoleBinding.role_id).where(
                RoleBinding.membership_id == membership.id,
                RoleBinding.role_id.in_(list(role_by_id)),
            )
        ).all())
        ancestor_groups = EffectiveRoleResolver.ancestor_group_cte(membership.id, tenant.id)
        group_rows = db.execute(
            select(UserGroupRole.role_id, UserGroup)
            .join(UserGroup, UserGroup.id == UserGroupRole.group_id)
            .where(
                UserGroupRole.role_id.in_(list(role_by_id)),
                UserGroupRole.tenant_id == tenant.id,
                UserGroup.status == "active",
                UserGroup.id.in_(select(ancestor_groups.c.group_id)),
            )
            .order_by(UserGroup.name)
        ).all()
        groups_by_role: dict[UUID, list[UserGroup]] = {}
        for role_id, group in group_rows:
            groups_by_role.setdefault(role_id, []).append(group)
        grant_rows = db.execute(
            select(Permission, RolePermission.role_id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(
                RolePermission.role_id.in_(list(role_by_id)),
                Permission.status == "active",
            )
            .order_by(Permission.code)
        ).all()
        for permission, role_id in grant_rows:
            role = role_by_id[role_id]
            entry = aggregated.setdefault(permission.code, {
                "code": permission.code,
                "description": permission.description,
                "surface": permission.surface,
                "status": permission.status,
                "sources": [],
            })
            seen = {
                (item["source_type"], item["role_id"], item.get("group_id"))
                for item in entry["sources"]
            }
            if role.id in direct_ids:
                marker = ("direct", str(role.id), None)
                if marker not in seen:
                    entry["sources"].append({
                        "source_type": "direct",
                        "role_id": str(role.id),
                        "role_key": role.key,
                        "role_name": role.name,
                        "tenant_id": str(tenant.id),
                        "tenant_name": tenant.name,
                        "application_id": str(role.application_id) if role.application_id else None,
                        "group_id": None,
                        "group_name": None,
                    })
                    seen.add(marker)
            for group in groups_by_role.get(role.id, []):
                marker = ("group", str(role.id), str(group.id))
                if marker in seen:
                    continue
                entry["sources"].append({
                    "source_type": "group",
                    "role_id": str(role.id),
                    "role_key": role.key,
                    "role_name": role.name,
                    "tenant_id": str(tenant.id),
                    "tenant_name": tenant.name,
                    "application_id": str(role.application_id) if role.application_id else None,
                    "group_id": str(group.id),
                    "group_name": group.name,
                })
                seen.add(marker)
    return [aggregated[code] for code in sorted(aggregated)]


@router.get("/users/{user_id}/profile")
def get_user_profile(user_id: UUID, actor: User = Depends(current_user),
                     db: Session = Depends(get_db_session)) -> dict:
    """G16 用户详情聚合：资料、租户成员关系、全部角色、活动会话与最近认证事件一次返回。

    复用现有数据源拼装（sessions 复用 list_user_sessions），不新增任何授权语义；
    PRD IAM-USER-006 要求的一体详情由本端点承载，前端详情抽屉单次拉取。
    G28 追加有效权限码并集与来源（直授 / 用户组）。
    """
    PermissionEnforcer.ensure_codes(actor, db, "menu.users", detail="缺少管理权限：menu.users")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    # 数据边界：非超管只能查看自身管理租户内非平台角色账号的完整档案。
    _assert_user_within_actor_boundary(actor, db, user)
    membership_rows = db.execute(
        select(TenantMembership, Tenant).join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == user_id).order_by(TenantMembership.created_at)
    ).all()
    membership_ids = [membership.id for membership, _ in membership_rows]
    bindings: list[dict] = []
    if membership_ids:
        binding_rows = db.execute(
            select(RoleBinding, Role, Tenant, TenantMembership)
            .join(Role, Role.id == RoleBinding.role_id)
            .join(Tenant, Tenant.id == Role.tenant_id)
            .join(TenantMembership, TenantMembership.id == RoleBinding.membership_id)
            .where(RoleBinding.membership_id.in_(membership_ids))
            .order_by(Tenant.name, Role.name)
        ).all()
        bindings = [{
            "role_id": str(role.id), "role_key": role.key, "role_name": role.name,
            "role_status": role.status,
            "application_id": str(role.application_id) if role.application_id else None,
            "tenant_id": str(tenant.id), "tenant_name": tenant.name,
            "membership_status": membership.status,
        } for _binding, role, tenant, membership in binding_rows]
    recent_auth_events = [{
        "action": event.action, "outcome": event.outcome, "created_at": event.created_at,
    } for event in db.scalars(select(AuditEvent).where(
        AuditEvent.actor_user_id == user_id, AuditEvent.action.like("auth.%"),
    ).order_by(AuditEvent.created_at.desc()).limit(10)).all()]
    return {
        "id": str(user.id), "email": user.email, "display_name": user.display_name,
        "status": user.status, "auth_version": user.auth_version,
        "created_at": user.created_at,
        "memberships": [{
            "tenant_id": str(tenant.id), "tenant_name": tenant.name,
            "tenant_status": tenant.status, "membership_status": membership.status,
            "joined_at": membership.created_at,
            # 组织绑定随成员关系一并返回（前端详情展示绑定组织）。
            "organizations": [
                {"organization_id": str(org.id), "organization_name": org.name, "is_primary": link.is_primary}
                for link, org in db.execute(
                    select(MembershipOrganization, Organization)
                    .join(Organization, Organization.id == MembershipOrganization.organization_id)
                    .where(MembershipOrganization.membership_id == membership.id)
                    .order_by(MembershipOrganization.is_primary.desc(), Organization.name)
                ).all()
            ],
        } for membership, tenant in membership_rows],
        "role_bindings": bindings,
        "effective_permissions": list_user_effective_permissions(db, user_id),
        "sessions": list_user_sessions(user_id, actor=actor, db=db)["items"],
        "recent_auth_events": recent_auth_events,
    }


@router.get("/users")
def list_users(q: str | None = None, actor: User = Depends(current_user),
               db: Session = Depends(get_db_session)) -> list[dict]:
    """按邮箱/名称模糊查询用户目录与租户数；非超管只出数据边界内（自己租户/应用）的用户。"""
    PermissionEnforcer.ensure_codes(actor, db, "menu.users", detail="缺少管理权限：menu.users")
    stmt = select(User).order_by(User.created_at.desc()).limit(500)
    if q:
        # LIKE 通配符按字面匹配，避免 %/_ 意外扩大结果集（audit.py 同口径）。
        escaped = (q[:100].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_"))
        stmt = stmt.where(User.email.ilike(f"%{escaped}%", escape="\\")
                          | User.display_name.ilike(f"%{escaped}%", escape="\\"))
    # 数据边界：超管全域；租户级限自己活跃成员身份所在租户；
    # 应用级收口到「绑定应用的用户」（角色钉住可见应用的成员），不放宽到同租户全部用户。
    tenant_scope = ActorVisibility.list_actor_management_tenant_ids(actor, db)
    if tenant_scope is not None:
        if PermissionEnforcer.scope_at_least(actor, db, ROLE_SCOPE_TENANT):
            if not tenant_scope:
                return []
            stmt = stmt.where(User.id.in_(select(TenantMembership.user_id).where(
                TenantMembership.tenant_id.in_(tenant_scope),
                TenantMembership.status == "active",
            )))
        else:
            visible_apps = ActorVisibility.list_actor_visible_application_ids(actor, db) or set()
            if not visible_apps:
                return []
            stmt = stmt.where(User.id.in_(
                select(TenantMembership.user_id)
                .join(RoleBinding, RoleBinding.membership_id == TenantMembership.id)
                .join(Role, Role.id == RoleBinding.role_id)
                .where(
                    Role.application_id.in_(visible_apps),
                    Role.status == "active",
                    TenantMembership.status == "active",
                )
            ))
    return [{"id": str(u.id), "email": u.email, "display_name": u.display_name, "status": u.status,
             "tenant_count": db.scalar(select(func.count()).select_from(TenantMembership).where(TenantMembership.user_id == u.id)) or 0,
            "created_at": u.created_at} for u in db.scalars(stmt).all()]


@router.post("/users", status_code=201)
def create_user(body: AdminUserCreate, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """创建用户并落地三类绑定（多选）：租户成员（至少一个）、组织归属、应用成员。

    - 绑定租户 = 逐租户写 TenantMembership（前端默认选中一个租户）；
    - 绑定组织 = 写 MembershipOrganization（组织必须属于所选租户，每租户首个组织为主组织）；
    - 绑定应用 = 自动补该应用的 app.member 模板角色（应用必须属于所选租户）；
    - role_id 可选，挂在第一个租户下。
    """
    PermissionEnforcer.ensure_codes(actor, db, "button.users.manage", detail="缺少管理权限：button.users.manage")
    # 去重保序；至少一个租户。
    tenant_ids = list(dict.fromkeys(body.tenant_ids))
    if not tenant_ids:
        raise HTTPException(422, "至少选择一个租户")
    tenants: list[Tenant] = []
    for tenant_id in tenant_ids:
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(404, "租户不存在")
        # 数据边界：非超管只能在自己范围内的租户建人。
        ActorVisibility.ensure_tenant_in_actor_scope(actor, db, tenant_id)
        tenants.append(tenant)
    # 平台租户隔离：非超管不得把业务成员落进平台管理租户（仅超管可为平台租户增删成员）。
    if not is_platform_admin_user(actor, db):
        for tenant in tenants:
            if tenant.slug == PLATFORM_TENANT_SLUG:
                raise HTTPException(422, "平台管理租户为系统保留租户，不支持业务成员")
    email = str(body.email).casefold()
    if db.scalar(select(User.id).where(User.email == email)): raise HTTPException(409, "邮箱已存在")
    # 组织归属校验：必须属于所选租户；按租户分组便于设置主组织。
    orgs_by_tenant: dict[UUID, list[Organization]] = {}
    for org_id in dict.fromkeys(body.organization_ids):
        org = db.get(Organization, org_id)
        if not org or org.tenant_id not in tenant_ids:
            raise HTTPException(422, "组织必须属于所选租户")
        if org.status != "active":
            raise HTTPException(422, f"组织已停用：{org.name}")
        orgs_by_tenant.setdefault(org.tenant_id, []).append(org)
    # 应用绑定校验：必须属于所选租户；随后自动补 app.member 模板角色。
    apps_by_tenant: dict[UUID, list[Application]] = {}
    for app_id in dict.fromkeys(body.application_ids):
        app = db.get(Application, app_id)
        if not app or app.tenant_id not in tenant_ids:
            raise HTTPException(422, "应用必须属于所选租户")
        apps_by_tenant.setdefault(app.tenant_id, []).append(app)
    # 可选初始角色：应用类角色按其所属应用生效（可跨租户任命，非超管限数据边界内应用）；
    # 平台类角色全局有效（不限租户）。
    role = db.get(Role, body.role_id) if body.role_id else None
    if body.role_id and (not role or role.status != "active"):
        raise HTTPException(422, "初始角色不存在或已停用")
    if role:
        # 任命天花板与 bind_role 同口径：全局平台角色可直接被选中，须收口模板管理员任命。
        platform_actor = is_platform_admin_user(actor, db)
        if role.application_id:
            # 应用角色按其所属应用生效（可跨租户任命）；非超管仅可绑定数据边界内应用的角色。
            role_app = db.get(Application, role.application_id)
            if not role_app:
                raise HTTPException(422, "角色绑定的应用不存在或已停用")
            if not platform_actor:
                visible_apps = ActorVisibility.list_actor_visible_application_ids(actor, db)
                if visible_apps is not None and role.application_id not in visible_apps:
                    raise HTTPException(403, "不能绑定不在你数据边界内的应用角色")
        if role.key == L1_ROLE_KEY and not platform_actor:
            raise HTTPException(403, "不能任命平台超级管理员")
        if role.key == L3_ROLE_KEY and not platform_actor:
            raise HTTPException(403, "不能任命租户管理员")
        if role.key == L2_ROLE_KEY and role.application_id and not platform_actor:
            PermissionEnforcer.ensure_scope(actor, db, ROLE_SCOPE_TENANT, detail="任命应用管理员需要租户级及以上范围")
        elif role.key not in TEMPLATE_ROLE_KEYS:
            PermissionEnforcer.ensure_scope(actor, db, ActorVisibility.effective_role_scope(role), detail="不能绑定高于自己授权范围的角色")

    user = User(email=email, display_name=body.display_name, password_hash=hash_password(body.initial_password))
    db.add(user); flush_or_conflict(db)
    created_membership_ids: list[UUID] = []
    for tenant in tenants:
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id)
        db.add(membership); flush_or_conflict(db)
        created_membership_ids.append(membership.id)
        # 组织挂接：每租户首个组织标记为主组织。
        for index, org in enumerate(orgs_by_tenant.get(tenant.id, [])):
            db.add(MembershipOrganization(
                membership_id=membership.id, organization_id=org.id,
                tenant_id=tenant.id, is_primary=(index == 0),
            ))
        # 应用绑定：自动补该应用的 app.member（应用成员身份由模板角色承载）。
        for app in apps_by_tenant.get(tenant.id, []):
            member_role = db.scalar(select(Role).where(
                Role.tenant_id == tenant.id,
                Role.application_id == app.id,
                Role.key == L4_ROLE_KEY,
                Role.status == "active",
            ))
            if member_role is not None:
                db.add(RoleBinding(membership_id=membership.id, role_id=member_role.id))
    if role:
        db.add(RoleBinding(membership_id=created_membership_ids[0], role_id=role.id))
        # 与 bind_role 同口径：初始角色为应用角色时自动补该应用的成员（L4）模板角色。
        if RoleProvisioning.is_application_class_role(role) and role.application_id:
            member_role = db.scalar(select(Role).where(
                Role.tenant_id == role.tenant_id,
                Role.application_id == role.application_id,
                Role.key == L4_ROLE_KEY,
                Role.status == "active",
            ))
            if member_role is not None:
                db.add(RoleBinding(membership_id=created_membership_ids[0], role_id=member_role.id))
    audit(db, actor, request, "user.create", "user", str(user.id), {
        "tenant_ids": [str(item) for item in tenant_ids],
        "organization_count": len(body.organization_ids),
        "application_count": len(body.application_ids),
        "role_id": str(role.id) if role else None,
    })
    commit_or_conflict(db)
    return {
        "id": str(user.id), "email": user.email, "display_name": user.display_name,
        "status": user.status,
        "tenant_ids": [str(item) for item in tenant_ids],
        "organization_ids": [str(item) for item in dict.fromkeys(body.organization_ids)],
        "application_ids": [str(item) for item in dict.fromkeys(body.application_ids)],
    }


@router.patch("/users/{user_id}/status")
def set_user_status(user_id: UUID, body: UserStatusUpdate, request: Request,
                    actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """全局锁/停用会使此前所有 IAM/OIDC 身份凭证失效；解锁不会恢复旧会话。"""
    PermissionEnforcer.ensure_codes(actor, db, "button.users.manage", detail="缺少管理权限：button.users.manage")
    row = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not row: raise HTTPException(404, "用户不存在")
    # 目标边界：非超管不能停用/锁定越边界账号或平台角色账号（含空操作探测，一并 404）。
    _assert_user_within_actor_boundary(actor, db, row)
    if row.status != body.expected_status:
        raise HTTPException(status_code=409, detail="用户状态已被其他管理员修改，请刷新后重试")
    if row.status == body.status:
        return {"id": str(row.id), "status": row.status, "auth_version": row.auth_version}
    if row.id == actor.id and body.status != "active":
        raise HTTPException(400, "不能锁定或停用当前管理员账号")

    previous_status = row.status
    row.status = body.status
    if body.status in {"disabled", "locked"}:
        # 增加身份版本令 IAM、UserInfo、Introspection 和在线 SDK 即时拒绝旧 access token。
        row.auth_version = (row.auth_version or 1) + 1
        # 关闭全局身份时撤销所有产品的续期凭证，并消费尚未兑换的 code/consent。
        db.execute(update(RefreshSession).where(RefreshSession.user_id == row.id,
                                               RefreshSession.revoked_at.is_(None))
                   .values(revoked_at=datetime.now(timezone.utc)))
        db.execute(update(OAuthRefreshToken).where(OAuthRefreshToken.user_id == row.id,
                                                   OAuthRefreshToken.revoked_at.is_(None))
                   .values(revoked_at=datetime.now(timezone.utc)))
        now = datetime.now(timezone.utc)
        db.execute(update(OAuthAuthorizationCode).where(
            OAuthAuthorizationCode.user_id == row.id, OAuthAuthorizationCode.consumed_at.is_(None),
        ).values(consumed_at=now))
        db.execute(update(OAuthConsentRequest).where(
            OAuthConsentRequest.user_id == row.id, OAuthConsentRequest.consumed_at.is_(None),
        ).values(consumed_at=now))
    audit(db, actor, request, "user.status.change", "user", str(row.id), {
        "from_status": previous_status, "to_status": body.status,
    })
    commit_or_conflict(db)
    # G19：全局凭证级联后向用户有过会话的应用推送 back-channel 登出（仅停用/锁停触发级联）。
    if body.status in {"disabled", "locked"}:
        BackchannelLogoutService.deliver_for_user(db, row.id)
    return {"id": str(row.id), "status": row.status, "auth_version": row.auth_version}


@router.post("/users/{user_id}/password")
def reset_user_password(user_id: UUID, body: AdminPasswordReset, request: Request,
                        actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """管理员重置用户密码：换哈希、提高认证版本并撤销该用户全部续期凭证，与审计同事务。

    兜底 SMTP 故障时忘记密码用户的管理救济；本人必须走「验证当前密码」的自助通道。
    """
    PermissionEnforcer.ensure_codes(actor, db, "button.users.manage", detail="缺少管理权限：button.users.manage")
    if actor.id == user_id:
        raise HTTPException(400, "不能重置当前管理员自己的密码；请使用「修改密码」")
    row = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not row:
        raise HTTPException(404, "用户不存在")
    # 目标边界：非超管不能重置越边界账号或平台角色账号的密码。
    _assert_user_within_actor_boundary(actor, db, row)
    if row.status != "active":
        raise HTTPException(400, "仅允许为启用状态的用户重置密码；停用/锁定账号请先恢复启用")

    row.password_hash = hash_password(body.new_password)
    row.auth_version = (row.auth_version or 1) + 1
    now = datetime.now(timezone.utc)
    # 与停用/锁停同一条凭证级联：旧会话、旧令牌、未兑换 code/consent 与旧重置链接一并作废。
    db.execute(update(RefreshSession).where(RefreshSession.user_id == row.id,
                                            RefreshSession.revoked_at.is_(None))
               .values(revoked_at=now))
    db.execute(update(OAuthRefreshToken).where(OAuthRefreshToken.user_id == row.id,
                                               OAuthRefreshToken.revoked_at.is_(None))
               .values(revoked_at=now))
    db.execute(update(OAuthAuthorizationCode).where(
        OAuthAuthorizationCode.user_id == row.id, OAuthAuthorizationCode.consumed_at.is_(None),
    ).values(consumed_at=now))
    db.execute(update(OAuthConsentRequest).where(
        OAuthConsentRequest.user_id == row.id, OAuthConsentRequest.consumed_at.is_(None),
    ).values(consumed_at=now))
    db.execute(update(PasswordResetToken).where(
        PasswordResetToken.user_id == row.id, PasswordResetToken.consumed_at.is_(None),
    ).values(consumed_at=now))
    audit(db, actor, request, "user.password.reset", "user", str(row.id), {
        "auth_version": row.auth_version, "iam_refresh_sessions_revoked": True,
    })
    commit_or_conflict(db)
    # G19：管理员重置同样撤销了该用户全部 OIDC 续期凭证，联动业务方登出。
    BackchannelLogoutService.deliver_for_user(db, row.id)
    return {"id": str(row.id), "auth_version": row.auth_version}
