"""租户角色邀请生命周期管理路由。"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.config import get_settings
from app.core.security import current_user
from app.db.seed_greenfield import PLATFORM_TENANT_SLUG
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Role, RoleBinding
from app.models.identity import Tenant, TenantMembership, User, UserInvitation
from app.schemas.auth import AdminInvitationBatchCreate, AdminInvitationCreate, AdminInvitationResend
from app.services.email import send_invitation_email
from app.services.rbac_guards import ensure_roles
from app.services.role_provisioning import CONSOLE_ADMIN_ROLE_KEYS, L1_ROLE_KEY, L3_ROLE_KEY

router = APIRouter(tags=["成员邀请"])
logger = logging.getLogger(__name__)

@router.get("/invitations")
def list_invitations(tenant_id: UUID | None = None, actor: User = Depends(current_user),
                     db: Session = Depends(get_db_session)) -> list[dict]:
    """只列出邀请状态和邮箱信息，永不回传 invitation token 或链接。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=tenant_id, detail="缺少管理角色（原 org.invite.manage）")
    stmt = (select(UserInvitation, Tenant, Role)
            .join(Tenant, Tenant.id == UserInvitation.tenant_id)
            .join(Role, Role.id == UserInvitation.role_id)
            .order_by(UserInvitation.created_at.desc()).limit(500))
    if tenant_id:
        stmt = stmt.where(UserInvitation.tenant_id == tenant_id)
    now = datetime.now(timezone.utc)
    rows = []
    for invite, tenant, role in db.execute(stmt).all():
        state = ("accepted" if invite.accepted_at else "revoked" if invite.revoked_at else
                 "expired" if invite.expires_at <= now else "pending")
        rows.append({"id": str(invite.id), "tenant_id": str(tenant.id), "tenant_name": tenant.name,
                     "email": invite.email, "display_name": invite.display_name,
                     "role_id": str(role.id), "role_name": role.name, "status": state,
                     "expires_at": invite.expires_at, "accepted_at": invite.accepted_at,
                     "created_at": invite.created_at})
    return rows


def _validate_invitation_target(db: Session, tenant_id: UUID, role_id: UUID) -> tuple[Tenant, Role]:
    """校验活动租户与租户内活动角色（应用角色还要求应用活动），不通过统一 422。"""
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "active"))
    role = db.scalar(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                        Role.status == "active"))
    if not tenant or not role:
        raise HTTPException(422, "必须选择活动租户和该租户内的活动角色")
    # 平台引导租户是系统保留租户：单发与批量创建共用本校验，在循环外一次性拦截；
    # 重发/撤销/兑换不经过这里，历史邀请的生命周期管理不受影响。
    if tenant.slug == PLATFORM_TENANT_SLUG:
        raise HTTPException(422, "平台引导租户为系统保留租户，不支持成员邀请")
    if role.application_id:
        app = db.scalar(select(Application).where(Application.id == role.application_id,
                                                  Application.tenant_id == tenant.id,
                                                  Application.status == "active"))
        if not app:
            raise HTTPException(422, "邀请角色绑定的应用不存在或已停用")
    return tenant, role


def _create_pending_invitation(db: Session, tenant: Tenant, role: Role, email: str,
                               display_name: str, expires_in_hours: int,
                               actor_id) -> tuple[UserInvitation, str]:
    """为单个邮箱签发待接受邀请；返回 (邀请行, 原始 token)。冲突抛 409，不提交事务。"""
    now = datetime.now(timezone.utc)
    # 已过期的待处理邀请让出唯一有效名额，保留为 revoked 历史记录。
    db.execute(update(UserInvitation).where(
        UserInvitation.tenant_id == tenant.id, UserInvitation.email == email,
        UserInvitation.accepted_at.is_(None), UserInvitation.revoked_at.is_(None),
        UserInvitation.expires_at <= now,
    ).values(revoked_at=now))
    if db.scalar(select(UserInvitation.id).where(
        UserInvitation.tenant_id == tenant.id, UserInvitation.email == email,
        UserInvitation.accepted_at.is_(None), UserInvitation.revoked_at.is_(None),
        UserInvitation.expires_at > now,
    )):
        raise HTTPException(409, "该邮箱已有未完成的租户邀请")
    existing_user = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing_user:
        membership = db.scalar(select(TenantMembership).where(
            TenantMembership.user_id == existing_user.id, TenantMembership.tenant_id == tenant.id,
            TenantMembership.status == "active",
        ))
        if membership and db.scalar(select(RoleBinding.id).where(
            RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id,
        )):
            raise HTTPException(409, "该用户已经拥有此租户角色")
    raw_token = secrets.token_urlsafe(48)
    invite = UserInvitation(tenant_id=tenant.id, role_id=role.id, email=email,
                            display_name=display_name,
                            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                            expires_at=now + timedelta(hours=expires_in_hours), created_by=actor_id)
    db.add(invite)
    flush_or_conflict(db)
    return invite, raw_token


def _deliver_invitation(invite: UserInvitation, raw_token: str, tenant_name: str, role_name: str) -> str:
    """优先邮件投递；SMTP 失败或未配置时回退 manual_copy，不抛异常（邀请行已提交）。"""
    settings = get_settings()
    if not settings.invitation_email_enabled:
        return "manual_copy"
    try:
        send_invitation_email(
            email=invite.email,
            token=raw_token,
            tenant_name=tenant_name,
            role_name=role_name,
            expires_at=invite.expires_at.astimezone(timezone.utc).isoformat(),
        )
        return "email_sent"
    except Exception as error:
        # 邀请已提交后才发信；失败不能撤销已发出的数据库记录，备用链接仍由 no-store 响应交给管理员。
        # 日志只记录邀请 ID 和异常类型，不记录邮箱、邮件正文、原始 Token 或 SMTP 响应文本。
        logger.warning("invitation_email_delivery_failed invitation_id=%s error_type=%s",
                       invite.id, type(error).__name__)
        return "email_failed"


@router.post("/invitations", status_code=201)
def create_invitation(body: AdminInvitationCreate, request: Request, response: Response,
                      actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """为租户成员签发 48-byte 一次性链接；数据库仅存 SHA-256 摘要，原始链接只回传一次且响应禁止缓存。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=body.tenant_id, detail="缺少管理角色（原 org.invite.manage）")
    tenant, role = _validate_invitation_target(db, body.tenant_id, body.role_id)
    email = str(body.email).casefold()
    invite, raw_token = _create_pending_invitation(db, tenant, role, email,
                                                   body.display_name, body.expires_in_hours, actor.id)
    audit(db, actor, request, "user.invitation.create", "invitation", str(invite.id),
          {"tenant_id": str(tenant.id), "role_id": str(role.id), "email": email,
           "expires_at": invite.expires_at.isoformat()})
    commit_or_conflict(db)
    return _invitation_link_response(response, invite, raw_token, tenant.name, role.name)


def _invitation_link_response(response: Response, invite: UserInvitation, raw_token: str,
                              tenant_name: str, role_name: str) -> dict:
    """组装含原始链接的响应；一次性 bearer 链接必须禁止浏览器与代理缓存。"""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    invite_url = f"{get_settings().console_public_url.rstrip('/')}/#invite={raw_token}"
    delivery = _deliver_invitation(invite, raw_token, tenant_name, role_name)
    return {"id": str(invite.id), "email": invite.email, "tenant_id": str(invite.tenant_id),
            "role_id": str(invite.role_id), "expires_at": invite.expires_at,
            "invite_url": invite_url, "delivery": delivery}


@router.post("/invitations/batch", status_code=201)
def create_invitations_batch(body: AdminInvitationBatchCreate, request: Request, response: Response,
                             actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """G21 批量邀请：同一租户同一角色一次邀请多个邮箱；单邮箱冲突跳过不阻断其余。"""
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=body.tenant_id, detail="缺少管理角色（原 org.invite.manage）")
    tenant, role = _validate_invitation_target(db, body.tenant_id, body.role_id)
    # 大小写归一并去重，保持首现顺序；响应包含每邮箱的原始链接，同样禁止缓存。
    seen: set[str] = set()
    results: list[dict] = []
    for raw_email in body.emails:
        email = str(raw_email).casefold()
        if email in seen:
            continue
        seen.add(email)
        try:
            invite, raw_token = _create_pending_invitation(db, tenant, role, email,
                                                           body.display_name, body.expires_in_hours, actor.id)
        except HTTPException as error:
            results.append({"email": email, "status": "skipped", "reason": error.detail})
            continue
        audit(db, actor, request, "user.invitation.create", "invitation", str(invite.id),
              {"tenant_id": str(tenant.id), "role_id": str(role.id), "email": email,
               "expires_at": invite.expires_at.isoformat(), "batch": True})
        commit_or_conflict(db)
        item = _invitation_link_response(response, invite, raw_token, tenant.name, role.name)
        results.append({"email": email, "status": "created", **item})
    return {"created": sum(1 for r in results if r["status"] == "created"),
            "skipped": sum(1 for r in results if r["status"] == "skipped"),
            "items": results}


@router.post("/invitations/{invitation_id}/resend")
def resend_invitation(invitation_id: UUID, body: AdminInvitationResend, request: Request, response: Response,
                      actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """G21 重发邀请：换发新 token 并顺延有效期；仅未接受、未撤销的邀请可重发。"""
    invite = db.scalar(select(UserInvitation).where(UserInvitation.id == invitation_id).with_for_update())
    if not invite:
        raise HTTPException(404, "邀请不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=invite.tenant_id, detail="缺少管理角色（原 org.invite.manage）")
    if invite.accepted_at:
        raise HTTPException(409, "已接受的邀请不可重发")
    if invite.revoked_at:
        raise HTTPException(409, "已撤销的邀请不可重发；请新建邀请")
    tenant = db.get(Tenant, invite.tenant_id)
    role = db.get(Role, invite.role_id)
    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(48)
    # 旧链接立即失效（token_hash 被覆盖），有效期从当前时间顺延。
    invite.token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    invite.expires_at = now + timedelta(hours=body.expires_in_hours)
    audit(db, actor, request, "user.invitation.resend", "invitation", str(invite.id),
          {"tenant_id": str(invite.tenant_id), "email": invite.email,
           "expires_at": invite.expires_at.isoformat()})
    commit_or_conflict(db)
    return _invitation_link_response(response, invite, raw_token,
                                     tenant.name if tenant else "", role.name if role else "")


@router.post("/invitations/{invitation_id}/revoke")
def revoke_invitation(invitation_id: UUID, request: Request,
                      actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """行锁撤销未接受邀请；已接受返回 409，重复撤销幂等返回当前状态。"""
    invite = db.scalar(select(UserInvitation).where(UserInvitation.id == invitation_id).with_for_update())
    if not invite:
        raise HTTPException(404, "邀请不存在")
    ensure_roles(actor, db, list(CONSOLE_ADMIN_ROLE_KEYS), tenant_id=invite.tenant_id, detail="缺少管理角色（原 org.invite.manage）")
    if invite.accepted_at:
        raise HTTPException(409, "已接受的邀请不可撤销")
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(timezone.utc)
        audit(db, actor, request, "user.invitation.revoke", "invitation", str(invite.id),
              {"tenant_id": str(invite.tenant_id), "email": invite.email})
        commit_or_conflict(db)
    return {"id": str(invite.id), "status": "revoked"}
