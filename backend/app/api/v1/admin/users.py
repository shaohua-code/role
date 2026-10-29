"""租户成员身份和状态管理路由。"""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user, hash_password
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupRole
from app.models.identity import (AuditEvent, PasswordResetToken, RefreshSession, Tenant,
                                 TenantMembership, User)
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.schemas.auth import AdminPasswordReset, AdminUserCreate, UserStatusUpdate
from app.services.backchannel_logout import deliver_backchannel_logout, deliver_for_user
from app.services.effective_roles import ancestor_group_cte, authorized_role_ids_statement
from app.services.rbac_guards import ensure_roles
from app.services.role_provisioning import L1_ROLE_KEY, L2_ROLE_KEY, L3_ROLE_KEY

router = APIRouter(tags=["用户管理"])


@router.get("/users/{user_id}/sessions")
def list_user_sessions(user_id: UUID, actor: User = Depends(current_user),
                      db: Session = Depends(get_db_session)) -> dict:
    """列出仍可续期的管理台与 OIDC 会话，不暴露任何 refresh token 摘要。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.account.read）")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
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
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.account.manage）")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
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
            deliver_backchannel_logout([application], user_id=user_id, session_id=session_id)
    return {"user_id": str(user_id), "session_type": session_type,
            "session_id": str(session_id), "revoked_at": revoked_at}

def list_user_effective_permissions(db: Session, user_id: UUID) -> list[dict]:
    """G28 有效权限码并集 + 来源（直授角色 / 用户组继承）。

    只统计活动成员身份、活动角色、活动权限；组停用不参与继承（与 list_effective_roles 同口径）。
    """
    membership_rows = db.execute(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == user_id, TenantMembership.status == "active")
        .order_by(Tenant.name)
    ).all()
    aggregated: dict[str, dict] = {}
    for membership, tenant in membership_rows:
        role_ids = list(db.scalars(authorized_role_ids_statement(membership.id, tenant.id)).all())
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
        ancestor_groups = ancestor_group_cte(membership.id, tenant.id)
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
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.account.read）")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
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
        } for membership, tenant in membership_rows],
        "role_bindings": bindings,
        "effective_permissions": list_user_effective_permissions(db, user_id),
        "sessions": list_user_sessions(user_id, actor=actor, db=db)["items"],
        "recent_auth_events": recent_auth_events,
    }


@router.get("/users")
def list_users(q: str | None = None, actor: User = Depends(current_user),
               db: Session = Depends(get_db_session)) -> list[dict]:
    """按邮箱/名称模糊查询全局用户目录与租户数（仅 L1）；不暴露凭证信息。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.account.read）")
    stmt = select(User).order_by(User.created_at.desc()).limit(500)
    if q: stmt = stmt.where(User.email.ilike(f"%{q[:100]}%") | User.display_name.ilike(f"%{q[:100]}%"))
    return [{"id": str(u.id), "email": u.email, "display_name": u.display_name, "status": u.status,
             "tenant_count": db.scalar(select(func.count()).select_from(TenantMembership).where(TenantMembership.user_id == u.id)) or 0,
            "created_at": u.created_at} for u in db.scalars(stmt).all()]


@router.post("/users", status_code=201)
def create_user(body: AdminUserCreate, request: Request, actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """创建租户成员时要求明确租户；初始密码仅从受保护管理请求进入，不在响应中回显。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.account.manage）")
    if not db.get(Tenant, body.tenant_id): raise HTTPException(404, "租户不存在")
    email = str(body.email).casefold()
    if db.scalar(select(User.id).where(User.email == email)): raise HTTPException(409, "邮箱已存在")
    role = db.get(Role, body.role_id) if body.role_id else None
    if body.role_id and (not role or role.tenant_id != body.tenant_id): raise HTTPException(422, "角色必须属于所选租户")
    if role and role.application_id:
        role_app = db.get(Application, role.application_id)
        if not role_app or role_app.tenant_id != body.tenant_id: raise HTTPException(422, "角色应用必须属于所选租户")
    user = User(email=email, display_name=body.display_name, password_hash=hash_password(body.initial_password))
    db.add(user); flush_or_conflict(db)
    membership = TenantMembership(user_id=user.id, tenant_id=body.tenant_id)
    db.add(membership); flush_or_conflict(db)
    if role: db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
    audit(db, actor, request, "user.create", "user", str(user.id), {"tenant_id": str(body.tenant_id), "role_id": str(role.id) if role else None})
    commit_or_conflict(db)
    return {"id": str(user.id), "email": user.email, "display_name": user.display_name, "status": user.status, "tenant_id": str(body.tenant_id)}


@router.patch("/users/{user_id}/status")
def set_user_status(user_id: UUID, body: UserStatusUpdate, request: Request,
                    actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """全局锁/停用会使此前所有 IAM/OIDC 身份凭证失效；解锁不会恢复旧会话。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.account.manage）")
    row = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not row: raise HTTPException(404, "用户不存在")
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
        deliver_for_user(db, row.id)
    return {"id": str(row.id), "status": row.status, "auth_version": row.auth_version}


@router.post("/users/{user_id}/password")
def reset_user_password(user_id: UUID, body: AdminPasswordReset, request: Request,
                        actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """管理员重置用户密码：换哈希、提高认证版本并撤销该用户全部续期凭证，与审计同事务。

    兜底 SMTP 故障时忘记密码用户的管理救济；本人必须走「验证当前密码」的自助通道。
    """
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.account.manage）")
    if actor.id == user_id:
        raise HTTPException(400, "不能重置当前管理员自己的密码；请使用「修改密码」")
    row = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not row:
        raise HTTPException(404, "用户不存在")
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
    deliver_for_user(db, row.id)
    return {"id": str(row.id), "auth_version": row.auth_version}
