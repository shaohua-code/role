"""租户成员身份和状态管理路由。"""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import hash_password, platform_admin
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Role, RoleBinding
from app.models.identity import RefreshSession, Tenant, TenantMembership, User
from app.models.oidc import OAuthAuthorizationCode, OAuthConsentRequest, OAuthRefreshToken
from app.schemas.auth import AdminUserCreate, UserStatusUpdate

router = APIRouter(tags=["用户管理"])


@router.get("/users/{user_id}/sessions")
def list_user_sessions(user_id: UUID, actor: User = Depends(platform_admin),
                      db: Session = Depends(get_db_session)) -> dict:
    """列出仍可续期的管理台与 OIDC 会话，不暴露任何 refresh token 摘要。"""
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
    actor: User = Depends(platform_admin),
    db: Session = Depends(get_db_session),
) -> dict:
    """撤销一个用户会话并在同一事务写入管理审计。"""
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
    return {"user_id": str(user_id), "session_type": session_type,
            "session_id": str(session_id), "revoked_at": revoked_at}

@router.get("/users")
def list_users(q: str | None = None, db: Session = Depends(get_db_session)) -> list[dict]:
    stmt = select(User).order_by(User.created_at.desc()).limit(500)
    if q: stmt = stmt.where(User.email.ilike(f"%{q[:100]}%") | User.display_name.ilike(f"%{q[:100]}%"))
    return [{"id": str(u.id), "email": u.email, "display_name": u.display_name, "status": u.status,
             "tenant_count": db.scalar(select(func.count()).select_from(TenantMembership).where(TenantMembership.user_id == u.id)) or 0,
            "created_at": u.created_at} for u in db.scalars(stmt).all()]


@router.post("/users", status_code=201)
def create_user(body: AdminUserCreate, request: Request, actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """创建租户成员时要求明确租户；初始密码仅从受保护管理请求进入，不在响应中回显。"""
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
                    actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """全局锁/停用会使此前所有 IAM/OIDC 身份凭证失效；解锁不会恢复旧会话。"""
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
    return {"id": str(row.id), "status": row.status, "auth_version": row.auth_version}
