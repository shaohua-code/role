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
from app.core.security import platform_admin
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Role, RoleBinding
from app.models.identity import Tenant, TenantMembership, User, UserInvitation
from app.schemas.auth import AdminInvitationCreate
from app.services.email import send_invitation_email

router = APIRouter(tags=["成员邀请"])
logger = logging.getLogger(__name__)

@router.get("/invitations")
def list_invitations(tenant_id: UUID | None = None, db: Session = Depends(get_db_session)) -> list[dict]:
    """只列出邀请状态和邮箱信息，永不回传 invitation token 或链接。"""
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


@router.post("/invitations", status_code=201)
def create_invitation(body: AdminInvitationCreate, request: Request, response: Response,
                      actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """为租户成员签发 48-byte 一次性链接；数据库仅存 SHA-256 摘要，原始链接只回传一次且响应禁止缓存。"""
    tenant = db.scalar(select(Tenant).where(Tenant.id == body.tenant_id, Tenant.status == "active"))
    role = db.scalar(select(Role).where(Role.id == body.role_id, Role.tenant_id == body.tenant_id,
                                         Role.status == "active"))
    if not tenant or not role:
        raise HTTPException(422, "必须选择活动租户和该租户内的活动角色")
    if role.application_id:
        app = db.scalar(select(Application).where(Application.id == role.application_id,
                                                   Application.tenant_id == tenant.id,
                                                   Application.status == "active"))
        if not app:
            raise HTTPException(422, "邀请角色绑定的应用不存在或已停用")
    email = str(body.email).casefold()
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
                            display_name=body.display_name,
                            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                            expires_at=now + timedelta(hours=body.expires_in_hours), created_by=actor.id)
    db.add(invite)
    flush_or_conflict(db)
    audit(db, actor, request, "user.invitation.create", "invitation", str(invite.id),
          {"tenant_id": str(tenant.id), "role_id": str(role.id), "email": email,
           "expires_at": invite.expires_at.isoformat()})
    commit_or_conflict(db)
    # This response contains the raw one-time bearer link; prevent browser and proxy caches from retaining it.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    settings = get_settings()
    invite_url = f"{settings.console_public_url.rstrip('/')}/#invite={raw_token}"
    delivery = "manual_copy"
    if settings.invitation_email_enabled:
        try:
            send_invitation_email(
                email=invite.email,
                token=raw_token,
                tenant_name=tenant.name,
                role_name=role.name,
                expires_at=invite.expires_at.astimezone(timezone.utc).isoformat(),
            )
            delivery = "email_sent"
        except Exception as error:
            # 邀请已提交后才发信；失败不能撤销已发出的数据库记录，备用链接仍由 no-store 响应交给管理员。
            # 日志只记录邀请 ID 和异常类型，不记录邮箱、邮件正文、原始 Token 或 SMTP 响应文本。
            logger.warning("invitation_email_delivery_failed invitation_id=%s error_type=%s",
                           invite.id, type(error).__name__)
            delivery = "email_failed"
    return {"id": str(invite.id), "email": invite.email, "tenant_id": str(tenant.id),
            "role_id": str(role.id), "expires_at": invite.expires_at,
            "invite_url": invite_url, "delivery": delivery}


@router.post("/invitations/{invitation_id}/revoke")
def revoke_invitation(invitation_id: UUID, request: Request,
                      actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    invite = db.scalar(select(UserInvitation).where(UserInvitation.id == invitation_id).with_for_update())
    if not invite:
        raise HTTPException(404, "邀请不存在")
    if invite.accepted_at:
        raise HTTPException(409, "已接受的邀请不可撤销")
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(timezone.utc)
        audit(db, actor, request, "user.invitation.revoke", "invitation", str(invite.id),
              {"tenant_id": str(invite.tenant_id), "email": invite.email})
        commit_or_conflict(db)
    return {"id": str(invite.id), "status": "revoked"}
