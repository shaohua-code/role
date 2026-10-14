"""模型调用用量与费用估算管理路由。"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict
from app.core.security import platform_admin
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import User
from app.models.model_catalog import ModelCatalog, ModelUsageEvent, ModelUsageReservation
from app.schemas.models import ModelUsageReviewRequest

router = APIRouter(tags=["模型用量"])


@router.get("/model-usage/reviews")
def list_model_usage_reviews(
    tenant_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db_session),
) -> dict:
    """分页列出超时未结算预留，避免长期待核对队列被固定条数截断。"""
    # API 参数由 FastAPI 转成整数；仍在函数内夹紧范围，保证直接调用或内部复用安全。
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    now = datetime.now(timezone.utc)
    filters = [
        ModelUsageReservation.status == "reserved",
        ModelUsageReservation.expires_at <= now,
    ]
    if tenant_id:
        filters.append(ModelUsageReservation.tenant_id == tenant_id)
    total = db.scalar(select(func.count()).select_from(ModelUsageReservation).where(*filters)) or 0
    stmt = (select(ModelUsageReservation, ModelCatalog, Application, User)
            .join(ModelCatalog, ModelCatalog.id == ModelUsageReservation.model_id)
            .join(Application, Application.id == ModelUsageReservation.application_id)
            .join(User, User.id == ModelUsageReservation.user_id)
            .where(*filters)
            .order_by(ModelUsageReservation.expires_at.asc(), ModelUsageReservation.request_id.asc())
            .limit(limit).offset(offset))
    items = [{
        "request_id": row.request_id, "tenant_id": str(row.tenant_id),
        "model_id": str(row.model_id), "model_name": model.display_name,
        "application_id": str(app.id), "application_name": app.name,
        "user_id": str(user.id), "user_email": user.email,
        "reserved_input_tokens": row.reserved_input_tokens,
        "reserved_output_tokens": row.reserved_output_tokens,
        "created_at": row.created_at, "expires_at": row.expires_at,
        "waiting_minutes": max(0, int((now - row.expires_at).total_seconds() // 60)),
    } for row, model, app, user in db.execute(stmt).all()]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/model-usage/reviews")
def resolve_model_usage_review(
    body: ModelUsageReviewRequest,
    request: Request,
    actor: User = Depends(platform_admin),
    db: Session = Depends(get_db_session),
) -> dict:
    """核对超时调用：实用量入账，或在确认 Provider 未被调用后释放预留。"""
    candidate = db.scalar(select(ModelUsageReservation).where(
        ModelUsageReservation.request_id == body.request_id))
    if not candidate:
        raise HTTPException(status_code=404, detail="找不到对应的额度预留")

    # 所有结算入口保持相同锁顺序，确保管理员操作与网关重试互斥。
    model = db.scalar(select(ModelCatalog).where(
        ModelCatalog.id == candidate.model_id).with_for_update())
    reservation = db.scalar(select(ModelUsageReservation).where(
        ModelUsageReservation.request_id == body.request_id).with_for_update())
    if not model or not reservation:
        db.rollback()
        raise HTTPException(status_code=404, detail="额度预留关联的模型不存在")
    if reservation.status != "reserved":
        db.rollback()
        raise HTTPException(status_code=409, detail="该调用已处理，不能重复核对")
    now = datetime.now(timezone.utc)
    if reservation.expires_at > now:
        db.rollback()
        raise HTTPException(status_code=409, detail="预留尚未超过 10 分钟核对期限")

    event = db.scalar(select(ModelUsageEvent).where(
        ModelUsageEvent.request_id == body.request_id).with_for_update())
    if event:
        db.rollback()
        raise HTTPException(status_code=409, detail="该调用已有用量账目，请刷新后重新核对")

    if body.decision == "settle":
        assert body.input_tokens is not None and body.output_tokens is not None and body.outcome
        cost = None
        if model.input_cost_per_million is not None and model.output_cost_per_million is not None:
            cost = (Decimal(body.input_tokens) * model.input_cost_per_million
                    + Decimal(body.output_tokens) * model.output_cost_per_million) / Decimal(1_000_000)
        event = ModelUsageEvent(
            id=uuid4(), request_id=reservation.request_id,
            tenant_id=reservation.tenant_id, model_id=reservation.model_id,
            application_id=reservation.application_id, user_id=reservation.user_id,
            input_tokens=body.input_tokens, output_tokens=body.output_tokens,
            estimated_cost=cost, outcome=body.outcome,
            usage_is_estimated=body.usage_is_estimated,
            source="admin_reconciliation", latency_ms=body.latency_ms,
            # 以 Provider 调用的原始时间记账，管理员处理延迟不改变限额窗口。
            created_at=reservation.created_at,
        )
        db.add(event)
        reservation.status = "settled"
    else:
        reservation.status = "released"

    reservation.settled_at = now
    audit(db, actor, request, f"model_usage.review.{body.decision}",
          "model_usage_reservation", str(reservation.id), {
              "request_id": reservation.request_id, "tenant_id": str(reservation.tenant_id),
              "reason": body.reason, "provider_not_called": body.provider_not_called,
              "input_tokens": body.input_tokens, "output_tokens": body.output_tokens,
              "outcome": body.outcome, "usage_is_estimated": body.usage_is_estimated,
              "latency_ms": body.latency_ms,
          })
    commit_or_conflict(db)
    return {"request_id": reservation.request_id, "status": reservation.status,
            "event_id": str(event.id) if event else None, "resolved_at": now}

@router.get("/model-usage/summary")
def model_usage_summary(tenant_id: UUID | None = None, db: Session = Depends(get_db_session)) -> dict:
    """返回留存用量汇总；未知目录价格单独计数，不伪装为零成本。"""
    stmt = select(
        func.count(ModelUsageEvent.id).label("requests"),
        func.sum(ModelUsageEvent.input_tokens).label("input_tokens"),
        func.sum(ModelUsageEvent.output_tokens).label("output_tokens"),
        func.sum(ModelUsageEvent.estimated_cost).label("estimated_cost"),
        func.count().filter(ModelUsageEvent.estimated_cost.is_(None)).label("unknown_cost_requests"),
        func.count().filter(ModelUsageEvent.outcome == "succeeded").label("succeeded"),
        func.count().filter(ModelUsageEvent.outcome == "failed").label("failed"),
        func.count().filter(ModelUsageEvent.usage_is_estimated.is_(True)).label("estimated_usage_requests"),
    )
    if tenant_id:
        stmt = stmt.where(ModelUsageEvent.tenant_id == tenant_id)
    result = db.execute(stmt).one()
    return {"requests": result.requests or 0, "input_tokens": result.input_tokens or 0,
            "output_tokens": result.output_tokens or 0,
            "estimated_cost": str(result.estimated_cost) if result.estimated_cost is not None else None,
            "unknown_cost_requests": result.unknown_cost_requests or 0,
            "succeeded": result.succeeded or 0, "failed": result.failed or 0,
            "estimated_usage_requests": result.estimated_usage_requests or 0}


@router.get("/model-usage/events")
def list_model_usage_events(
    tenant_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db_session),
) -> dict:
    """最近的计量账目只输出身份/计数/费用元数据，不含模型内容或密钥引用。"""
    # 账目可能持续增长；总数和 offset 分页让管理台可以完整审阅历史记录。
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    filters = []
    if tenant_id:
        filters.append(ModelUsageEvent.tenant_id == tenant_id)
    total = db.scalar(
        select(func.count()).select_from(ModelUsageEvent).where(*filters)
    ) or 0
    stmt = (select(ModelUsageEvent, ModelCatalog, Application, User)
            .join(ModelCatalog, ModelCatalog.id == ModelUsageEvent.model_id)
            .join(Application, Application.id == ModelUsageEvent.application_id)
            .join(User, User.id == ModelUsageEvent.user_id)
            .where(*filters)
            .order_by(ModelUsageEvent.created_at.desc(), ModelUsageEvent.id.desc())
            .limit(limit).offset(offset))
    items = [{"id": str(event.id), "request_id": event.request_id,
             "tenant_id": str(event.tenant_id), "model_id": str(event.model_id),
             "model_name": model.display_name, "application_id": str(app.id), "application_name": app.name,
             "user_id": str(user.id), "user_email": user.email,
             "input_tokens": event.input_tokens, "output_tokens": event.output_tokens,
             "estimated_cost": str(event.estimated_cost) if event.estimated_cost is not None else None,
              "outcome": event.outcome, "usage_is_estimated": event.usage_is_estimated,
              "source": event.source,
             "latency_ms": event.latency_ms, "created_at": event.created_at}
            for event, model, app, user in db.execute(stmt).all()]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
