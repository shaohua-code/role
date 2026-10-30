"""管理员审计查询路由；旧列表接口保留，新搜索接口负责服务端分页。"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db_session
from app.models.identity import AuditEvent, User
from app.schemas.audit import AuditEventResponse, AuditSearchResponse
from app.services.rbac_guards import (
    actor_has_tenant_admin,
    ensure_codes,
    list_actor_management_tenant_ids,
    list_actor_pinned_application_ids,
)
from app.services.role_provisioning import CONSOLE_ADMIN_ROLE_KEYS, L1_ROLE_KEY, L3_ROLE_KEY

router = APIRouter(tags=["审计日志"])


def _query_audit_events(
    *,
    limit: int,
    offset: int,
    action: str | None,
    target_type: str | None,
    target_id: str | None,
    outcome: str | None,
    actor_user_id: UUID | None,
    tenant_id: UUID | None,
    start_at: datetime | None,
    end_at: datetime | None,
    db: Session,
    tenant_scope: set[UUID] | None = None,
    action_prefix: str | None = None,
    application_ids: set[UUID] | None = None,
) -> AuditSearchResponse:
    """执行统一的精确筛选和分页；结束时间用开区间避免相邻范围重叠。

    tenant_scope 非 None 时强制把结果限制在这些租户内（L2/L3 范围过滤）：
    请求指定 tenant_id 时取交集且交集为空直接返回空集，未指定时查全部可见租户。
    application_ids 非 None 时（纯 L2）只返回 target_type=application 且 target_id 落在钉住应用上的事件。
    """
    if start_at and (start_at.tzinfo is None or start_at.utcoffset() is None):
        raise HTTPException(status_code=422, detail="start_at 必须包含时区偏移")
    if end_at and (end_at.tzinfo is None or end_at.utcoffset() is None):
        raise HTTPException(status_code=422, detail="end_at 必须包含时区偏移")
    if start_at and end_at and start_at >= end_at:
        raise HTTPException(status_code=422, detail="end_at 必须晚于 start_at")

    # 页面清空输入后会传空字符串；忽略它，其他文本字段都使用精确匹配。
    filters = []
    if action and action.strip():
        filters.append(AuditEvent.action == action.strip())
    if action_prefix and action_prefix.strip():
        # Wave 3 审计拆 Tab 用：按前缀聚合事件类别（如 auth. = 登录与认证）。
        # LIKE 通配符按字面匹配，避免前缀里的 %/_ 意外扩大结果集。
        escaped = (action_prefix.strip()
                   .replace("\\", "\\\\")
                   .replace("%", "\\%")
                   .replace("_", "\\_"))
        filters.append(AuditEvent.action.like(f"{escaped}%", escape="\\"))
    if target_type and target_type.strip():
        filters.append(AuditEvent.target_type == target_type.strip())
    if target_id and target_id.strip():
        filters.append(AuditEvent.target_id == target_id.strip())
    if outcome and outcome.strip():
        filters.append(AuditEvent.outcome == outcome.strip())
    if actor_user_id:
        filters.append(AuditEvent.actor_user_id == actor_user_id)
    # 范围过滤：请求的 tenant_id 必须与可见租户集合相交，交集为空 = 无可见数据。
    if tenant_scope is not None:
        if tenant_id:
            if tenant_id not in tenant_scope:
                return AuditSearchResponse(items=[], limit=limit, offset=offset, total=0, has_more=False)
            filters.append(AuditEvent.tenant_id == tenant_id)
        else:
            filters.append(AuditEvent.tenant_id.in_(tenant_scope))
    elif tenant_id:
        filters.append(AuditEvent.tenant_id == tenant_id)
    # P404：纯 L2 审计无 application_id 列，只能按应用目标尽力收敛；无法归属的租户级事件不返回。
    if application_ids is not None:
        if not application_ids:
            return AuditSearchResponse(items=[], limit=limit, offset=offset, total=0, has_more=False)
        filters.append(AuditEvent.target_type == "application")
        filters.append(AuditEvent.target_id.in_([str(item) for item in application_ids]))
    if start_at:
        filters.append(AuditEvent.created_at >= start_at)
    if end_at:
        filters.append(AuditEvent.created_at < end_at)

    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*filters)) or 0
    statement = (
        select(AuditEvent)
        .where(*filters)
        # 用主键打破同一时间戳的并列，保证相邻分页结果稳定。
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )
    events = db.scalars(statement).all()
    items = [
        AuditEventResponse(
            id=str(event.id),
            actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
            tenant_id=str(event.tenant_id) if event.tenant_id else None,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            outcome=event.outcome,
            source_ip=event.source_ip,
            details=event.details,
            created_at=event.created_at,
        )
        for event in events
    ]
    return AuditSearchResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        has_more=offset + len(items) < total,
    )


@router.get("/audit", response_model=list[AuditEventResponse])
def list_audit(
    limit: int = 100,
    action: str | None = None,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[AuditEventResponse]:
    """兼容旧调用方：保留最新记录数组响应和原有 limit/action 参数。"""
    ensure_codes(actor, db, "ops.audit.read", detail="缺少管理权限：ops.audit.read")
    tenant_scope = list_actor_management_tenant_ids(actor, db)
    application_ids = None
    if tenant_scope is not None and not actor_has_tenant_admin(actor, db):
        application_ids = list_actor_pinned_application_ids(actor, db)
    return _query_audit_events(
        limit=min(max(limit, 1), 500),
        offset=0,
        action=action[:120] if action else None,
        target_type=None,
        target_id=None,
        outcome=None,
        actor_user_id=None,
        tenant_id=None,
        start_at=None,
        end_at=None,
        db=db,
        tenant_scope=tenant_scope,
        application_ids=application_ids,
    ).items


@router.get("/audit/search", response_model=AuditSearchResponse)
def search_audit(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
    action: str | None = Query(default=None, max_length=120),
    target_type: str | None = Query(default=None, max_length=80),
    target_id: str | None = Query(default=None, max_length=180),
    outcome: str | None = Query(default=None, max_length=20),
    actor_user_id: UUID | None = None,
    tenant_id: UUID | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    action_prefix: str | None = Query(default=None, max_length=30),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> AuditSearchResponse:
    """按精确字段及 ISO 8601 时间范围查询审计事件；action_prefix 支持类别前缀聚合。"""
    ensure_codes(actor, db, "ops.audit.read", detail="缺少管理权限：ops.audit.read")
    tenant_scope = list_actor_management_tenant_ids(actor, db)
    application_ids = None
    if tenant_scope is not None and not actor_has_tenant_admin(actor, db):
        application_ids = list_actor_pinned_application_ids(actor, db)
    return _query_audit_events(
        limit=limit,
        offset=offset,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        actor_user_id=actor_user_id,
        tenant_id=tenant_id,
        start_at=start_at,
        end_at=end_at,
        db=db,
        tenant_scope=tenant_scope,
        action_prefix=action_prefix,
        application_ids=application_ids,
    )
