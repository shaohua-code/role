"""管理路由共用的审计和事务冲突处理；写操作与审计必须处于同一事务。"""

from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.application import Application
from app.models.authorization import Role
from app.models.identity import AuditEvent, User
from app.services.login_throttle import client_ip_for_request


def audit(
    db: Session,
    actor: User,
    request: Request,
    action: str,
    target_type: str,
    target_id: str | None,
    details: dict | None = None,
) -> None:
    """写入不含凭证明文的审计摘要，并尽可能将事件绑定到对应租户。"""
    tenant_id = None
    if details and details.get("tenant_id"):
        try:
            tenant_id = UUID(str(details["tenant_id"]))
        except ValueError:
            tenant_id = None
    if tenant_id is None and target_type == "tenant" and target_id:
        try:
            tenant_id = UUID(target_id)
        except ValueError:
            pass
    if tenant_id is None and target_id and target_type in {"role", "application", "theme"}:
        if target_type == "role":
            related_role = db.get(Role, UUID(target_id))
            tenant_id = related_role.tenant_id if related_role else None
        elif target_type == "application":
            related_app = db.get(Application, UUID(target_id))
            tenant_id = related_app.tenant_id if related_app else None
        elif details and details.get("application_id"):
            related_app = db.get(Application, UUID(str(details["application_id"])) )
            tenant_id = related_app.tenant_id if related_app else None
    # 破窗旁路（默认关闭）产生的写审计必须显式标记，便于灾备后复盘。
    from app.services.rbac_guards import user_is_break_glass

    audit_details = dict(details or {})
    if user_is_break_glass(actor):
        audit_details.setdefault("break_glass", True)
    db.add(AuditEvent(actor_user_id=actor.id, tenant_id=tenant_id, action=action,
                      target_type=target_type, target_id=target_id,
                      source_ip=client_ip_for_request(request, get_settings()), details=audit_details))


def commit_or_conflict(db: Session) -> None:
    """提交事务；唯一键冲突回滚后只向调用方暴露稳定的 409 文案。"""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "记录冲突，请检查唯一标识或关联数据") from None


def flush_or_conflict(db: Session) -> None:
    """在提交前执行约束检查，避免 flush 阶段的数据库细节泄露到响应。"""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "记录冲突，请检查唯一标识或关联数据") from None


def valid_redirect_uri(value: str) -> bool:
    """校验外部 URL：生产只接受 HTTPS，开发例外限定 localhost。"""
    try:
        parsed = urlsplit(value)
        if parsed.fragment or not parsed.netloc or parsed.username or parsed.password:
            return False
        return parsed.scheme == "https" or (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        )
    except ValueError:
        return False
