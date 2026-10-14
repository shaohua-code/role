"""可信模型网关的用量账目入口。

该路由只接受服务端网关上报的计量字段，不代理模型请求，也不接收 Prompt/响应体。
上报密钥来自独立部署配置；用户请求本身仍应在网关调用前通过 IAM 鉴权。
"""
import hmac
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import Tenant, TenantMembership, User
from app.models.model_catalog import ModelCatalog, ModelUsageEvent, ModelUsageReservation
from app.schemas.models import ModelUsageReport, ModelUsageReservationRequest, ModelUsageSettlementRequest

router = APIRouter(prefix="/internal/model-usage", tags=["模型网关内部接口"])


def _estimate_cost(model: ModelCatalog, body: ModelUsageReport) -> Decimal | None:
    """只按 IAM 目录价格估算成本；价格缺失时保留 NULL，不伪报 0 元。"""
    if model.input_cost_per_million is None or model.output_cost_per_million is None:
        return None
    million = Decimal(1_000_000)
    return (Decimal(body.input_tokens) * model.input_cost_per_million
            + Decimal(body.output_tokens) * model.output_cost_per_million) / million


def _require_gateway_key(gateway_key: str | None) -> None:
    """所有内部用量端点共用服务端网关密钥校验，不接受终端用户令牌替代。"""
    expected = get_settings().model_usage_api_key
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="模型网关用量接口未配置")
    if not gateway_key or not hmac.compare_digest(gateway_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="网关身份无效")


def _validate_reservation_subject(body: ModelUsageReservationRequest, db: Session) -> ModelCatalog:
    """从数据库确认网关传来的主体关系，避免把任意用户 ID 计入其它租户。"""
    tenant_active = db.scalar(select(func.count()).select_from(Tenant).where(
        Tenant.id == body.tenant_id, Tenant.status == "active"))
    model = db.scalar(select(ModelCatalog).where(
        ModelCatalog.id == body.model_id, ModelCatalog.tenant_id == body.tenant_id,
        ModelCatalog.status == "active"))
    application_active = db.scalar(select(func.count()).select_from(Application).where(
        Application.id == body.application_id, Application.tenant_id == body.tenant_id,
        Application.status == "active"))
    membership_active = db.scalar(select(func.count()).select_from(TenantMembership).join(
        User, User.id == TenantMembership.user_id).where(
            TenantMembership.user_id == body.user_id, TenantMembership.tenant_id == body.tenant_id,
            TenantMembership.status == "active", User.status == "active"))
    if not all((tenant_active, model, application_active, membership_active)):
        raise HTTPException(status_code=422, detail="预留关联的租户、模型、应用或活动用户关系无效")
    return model


def _reservation_matches(row: ModelUsageReservation, body: ModelUsageReservationRequest) -> bool:
    return (row.tenant_id == body.tenant_id and row.model_id == body.model_id
            and row.application_id == body.application_id and row.user_id == body.user_id
            and row.reserved_input_tokens == body.reserved_input_tokens
            and row.reserved_output_tokens == body.reserved_output_tokens)


@router.post("/reservations")
def reserve_usage(
    body: ModelUsageReservationRequest,
    gateway_key: str | None = Header(default=None, alias="X-IAM-Model-Gateway-Key"),
    db: Session = Depends(get_db_session),
) -> dict:
    """调用 Provider 前原子预留限额；租户和模型行锁串行化同一模型的配额判定。

    网关必须先用用户 access token 调用 /authorization/check 并确认 model.invoke，
    再申请配额。限额未配置或功能开关关闭时返回不强制的明确结果，不会拒绝调用。
    """
    _require_gateway_key(gateway_key)
    model = _validate_reservation_subject(body, db)
    settings = get_settings()

    enforced = settings.model_quota_enforcement_enabled and (
        model.rpm_limit is not None or model.tpm_limit is not None)
    # 即使未开启限额拦截，也先持久化预留，避免 Provider 已执行但 DeerFlow 崩溃后没有账目可核。
    if enforced:
        model = db.scalar(select(ModelCatalog).where(ModelCatalog.id == body.model_id).with_for_update())
        if not model or model.status != "active":
            db.rollback()
            raise HTTPException(status_code=422, detail="模型不可用")

    # 同一模型行锁内处理相同 request_id 的重试；不同载荷绝不复用预留。
    existing = db.scalar(select(ModelUsageReservation).where(
        ModelUsageReservation.request_id == body.request_id).with_for_update())
    if existing:
        if not _reservation_matches(existing, body):
            db.rollback()
            raise HTTPException(status_code=409, detail="网关请求 ID 已用于不同额度预留")
        if existing.status in {"settled", "released"}:
            db.rollback()
            return {"allowed": False, "already_resolved": True,
                    "resolution": existing.status, "reservation_required": False}
        if existing.expires_at <= datetime.now(timezone.utc):
            db.rollback()
            raise HTTPException(status_code=409, detail="额度预留已过期；不得复用该请求 ID")
        result = {"allowed": True, "duplicate": True, "enforced": enforced,
                  "reservation_required": True, "expires_at": existing.expires_at}
        db.rollback()
        return result

    # 已有用量账目说明该请求已经到达结算阶段，不能再以相同 ID 发起 Provider 调用。
    completed = db.scalar(select(ModelUsageEvent).where(ModelUsageEvent.request_id == body.request_id))
    if completed:
        same_subject = (completed.tenant_id == body.tenant_id and completed.model_id == body.model_id
                        and completed.application_id == body.application_id and completed.user_id == body.user_id)
        db.rollback()
        if not same_subject:
            raise HTTPException(status_code=409, detail="网关请求 ID 已用于不同用量数据")
        return {"allowed": False, "already_settled": True, "reservation_required": False}

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=60)
    # 过期表示进入人工核对队列，不会自动释放；未核对预留继续占用保守配额。
    pending_reservation = ModelUsageReservation.status == "reserved"
    counted_reservation = or_(ModelUsageReservation.status == "settled", pending_reservation)

    # RPM 统计最近 60 秒发起的请求；旧版未预留的 usage report 也纳入窗口。
    reserved_rpm = db.scalar(select(func.count()).select_from(ModelUsageReservation).where(
        ModelUsageReservation.model_id == model.id,
        ModelUsageReservation.created_at >= window_start,
        counted_reservation,
    )) or 0
    unreserved_rpm = db.scalar(select(func.count()).select_from(ModelUsageEvent).outerjoin(
        ModelUsageReservation, ModelUsageReservation.request_id == ModelUsageEvent.request_id).where(
            ModelUsageEvent.model_id == model.id, ModelUsageEvent.created_at >= window_start,
            ModelUsageReservation.id.is_(None),
        )) or 0
    used_rpm = reserved_rpm + unreserved_rpm

    # TPM 计入最近 60 秒的实际 Token，以及所有尚未结算的预估 Token（含待核对项）。
    active_reserved_tokens = db.scalar(select(func.coalesce(func.sum(
        ModelUsageReservation.reserved_input_tokens + ModelUsageReservation.reserved_output_tokens), 0))
        .select_from(ModelUsageReservation).where(
            ModelUsageReservation.model_id == model.id, pending_reservation,
        )) or 0
    settled_tokens = db.scalar(select(func.coalesce(func.sum(
        ModelUsageEvent.input_tokens + ModelUsageEvent.output_tokens), 0))
        .select_from(ModelUsageEvent).outerjoin(
            ModelUsageReservation, ModelUsageReservation.request_id == ModelUsageEvent.request_id).where(
                ModelUsageEvent.model_id == model.id, ModelUsageEvent.created_at >= window_start,
                or_(ModelUsageReservation.id.is_(None), ModelUsageReservation.status == "settled"),
            )) or 0
    used_tpm = active_reserved_tokens + settled_tokens

    if enforced:
        exceeded: list[str] = []
        if model.rpm_limit is not None and used_rpm + 1 > model.rpm_limit:
            exceeded.append("rpm")
        requested_tokens = body.reserved_input_tokens + body.reserved_output_tokens
        if model.tpm_limit is not None and used_tpm + requested_tokens > model.tpm_limit:
            exceeded.append("tpm")
        if exceeded:
            db.rollback()
            raise HTTPException(
                status_code=429,
                detail={"code": "model_quota_exceeded", "dimensions": exceeded,
                        "retry_after_seconds": 60},
                headers={"Retry-After": "60"},
            )

    reservation = ModelUsageReservation(
        id=uuid4(), request_id=body.request_id, tenant_id=body.tenant_id,
        model_id=body.model_id, application_id=body.application_id, user_id=body.user_id,
        reserved_input_tokens=body.reserved_input_tokens,
        reserved_output_tokens=body.reserved_output_tokens,
        status="reserved", expires_at=now + timedelta(minutes=10),
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError:
        # request_id 在其它模型上并行复用时不能让唯一键冲突变成 500。
        db.rollback()
        raise HTTPException(status_code=409, detail="网关请求 ID 已用于不同额度预留") from None
    return {"allowed": True, "duplicate": False, "enforced": enforced,
            "reservation_required": True, "expires_at": reservation.expires_at,
            "limits": {"rpm": model.rpm_limit, "tpm": model.tpm_limit}}


@router.post("/reservations/settle")
def settle_usage(
    body: ModelUsageSettlementRequest,
    gateway_key: str | None = Header(default=None, alias="X-IAM-Model-Gateway-Key"),
    db: Session = Depends(get_db_session),
) -> dict:
    """把真实用量与预留状态原子结算；允许 Provider 实际用量超过预留并显式标记。"""
    _require_gateway_key(gateway_key)
    # 先读模型 ID，再按 reservation/settlement 共用的“模型行 -> 预留行”顺序加锁。
    candidate = db.scalar(select(ModelUsageReservation).where(
        ModelUsageReservation.request_id == body.request_id))
    if not candidate:
        db.rollback()
        raise HTTPException(status_code=404, detail="找不到对应的额度预留")
    model = db.scalar(select(ModelCatalog).where(
        ModelCatalog.id == candidate.model_id).with_for_update())
    reservation = db.scalar(select(ModelUsageReservation).where(
        ModelUsageReservation.request_id == body.request_id).with_for_update())
    if not model or not reservation:
        db.rollback()
        raise HTTPException(status_code=404, detail="额度预留关联的模型不存在")
    if reservation.status == "released":
        db.rollback()
        raise HTTPException(status_code=409, detail="该调用已由管理员确认未调用 Provider，不能结算")

    existing = db.scalar(select(ModelUsageEvent).where(ModelUsageEvent.request_id == body.request_id))
    payload = {
        "request_id": body.request_id, "tenant_id": reservation.tenant_id,
        "model_id": reservation.model_id, "application_id": reservation.application_id,
        "user_id": reservation.user_id, "input_tokens": body.input_tokens,
        "output_tokens": body.output_tokens, "outcome": body.outcome,
        "usage_is_estimated": body.usage_is_estimated,
        "latency_ms": body.latency_ms,
    }
    if existing:
        same_payload = all(getattr(existing, key) == value for key, value in payload.items())
        if not same_payload:
            db.rollback()
            raise HTTPException(status_code=409, detail="网关请求 ID 已用于不同用量数据")
        if reservation.status == "settled":
            db.rollback()
            return {"settled": False, "duplicate": True,
                    "overrun": body.input_tokens > reservation.reserved_input_tokens
                    or body.output_tokens > reservation.reserved_output_tokens}
        # report_usage 可能已先记账；确认载荷一致后仍将其与预留状态一起提交。
        event_id = existing.id
        duplicate = True
    else:
        event = ModelUsageEvent(
            id=uuid4(), request_id=body.request_id,
            tenant_id=reservation.tenant_id, model_id=reservation.model_id,
            application_id=reservation.application_id, user_id=reservation.user_id,
            input_tokens=body.input_tokens, output_tokens=body.output_tokens,
            estimated_cost=(Decimal(body.input_tokens) * model.input_cost_per_million
                            + Decimal(body.output_tokens) * model.output_cost_per_million) / Decimal(1_000_000)
            if model.input_cost_per_million is not None and model.output_cost_per_million is not None else None,
        outcome=body.outcome, usage_is_estimated=body.usage_is_estimated,
        source="gateway", latency_ms=body.latency_ms,
        )
        statement = insert(ModelUsageEvent).values(**{
            column.name: getattr(event, column.name)
            for column in ModelUsageEvent.__table__.columns if column.name != "created_at"
        }).on_conflict_do_nothing(index_elements=["request_id"]).returning(ModelUsageEvent.id)
        inserted_id = db.scalar(statement)
        if inserted_id is None:
            # 普通 usage report 可以与 settle 并行；冲突后比对原账目，再提交预留状态。
            raced_event = db.scalar(select(ModelUsageEvent).where(
                ModelUsageEvent.request_id == body.request_id))
            same_payload = raced_event and all(
                getattr(raced_event, key) == value for key, value in payload.items())
            if not same_payload:
                db.rollback()
                raise HTTPException(status_code=409, detail="网关请求 ID 已用于不同用量数据")
            event_id = raced_event.id
            duplicate = True
        else:
            event_id = inserted_id
            duplicate = False

    now = datetime.now(timezone.utc)
    reservation.status = "settled"
    reservation.settled_at = now
    db.commit()
    return {"settled": True, "duplicate": duplicate, "event_id": str(event_id),
            "overrun": body.input_tokens > reservation.reserved_input_tokens
            or body.output_tokens > reservation.reserved_output_tokens,
            "reservation_expired": reservation.expires_at <= now}


@router.post("", status_code=201)
def report_usage(
    body: ModelUsageReport,
    gateway_key: str | None = Header(default=None, alias="X-IAM-Model-Gateway-Key"),
    db: Session = Depends(get_db_session),
) -> dict:
    """验证网关身份与实体租户关系，再幂等写入不可变账目。

    不信任普通用户 Bearer token 来申报用量，因为调用方可以伪造消耗量；
    共享网关密钥必须仅存放于受信服务端，线上需从部署密钥管理注入。
    """
    _require_gateway_key(gateway_key)

    tenant = db.scalar(select(Tenant).where(Tenant.id == body.tenant_id, Tenant.status == "active"))
    model = db.scalar(select(ModelCatalog).where(ModelCatalog.id == body.model_id,
                                                  ModelCatalog.tenant_id == body.tenant_id,
                                                  ModelCatalog.status == "active"))
    app = db.scalar(select(Application).where(Application.id == body.application_id,
                                               Application.tenant_id == body.tenant_id,
                                               Application.status == "active"))
    user = db.scalar(select(User).where(User.id == body.user_id, User.status == "active"))
    membership = db.scalar(select(TenantMembership.id).where(
        TenantMembership.user_id == body.user_id, TenantMembership.tenant_id == body.tenant_id,
        TenantMembership.status == "active",
    ))
    if not all((tenant, model, app, user, membership)):
        raise HTTPException(status_code=422, detail="用量关联的租户、模型、应用或活动用户关系无效")

    # 兼容旧版 report 路径：已有预留时账目写入必须同步完成预留状态。
    # 与 reserve/settle 共用模型行 -> 预留行的加锁顺序，避免并发重复结算。
    reservation_candidate = db.scalar(select(ModelUsageReservation).where(
        ModelUsageReservation.request_id == body.request_id))
    reservation = None
    if reservation_candidate:
        if (reservation_candidate.tenant_id != body.tenant_id
                or reservation_candidate.model_id != body.model_id
                or reservation_candidate.application_id != body.application_id
                or reservation_candidate.user_id != body.user_id):
            db.rollback()
            raise HTTPException(status_code=409, detail="网关请求 ID 已用于不同调用主体")
        model = db.scalar(select(ModelCatalog).where(
            ModelCatalog.id == reservation_candidate.model_id).with_for_update())
        reservation = db.scalar(select(ModelUsageReservation).where(
            ModelUsageReservation.request_id == body.request_id).with_for_update())
        if not model or not reservation or reservation.status == "released":
            db.rollback()
            raise HTTPException(status_code=409, detail="该调用预留已被管理员释放，不能补记用量")

    event = ModelUsageEvent(
        id=uuid4(),
        request_id=body.request_id, tenant_id=body.tenant_id, model_id=body.model_id,
        application_id=body.application_id, user_id=body.user_id,
        input_tokens=body.input_tokens, output_tokens=body.output_tokens,
        estimated_cost=_estimate_cost(model, body), outcome=body.outcome,
        usage_is_estimated=body.usage_is_estimated, source="gateway", latency_ms=body.latency_ms,
    )
    statement = insert(ModelUsageEvent).values(**{
        column.name: getattr(event, column.name)
        for column in ModelUsageEvent.__table__.columns if column.name != "created_at"
    }).on_conflict_do_nothing(index_elements=["request_id"]).returning(ModelUsageEvent.id)
    inserted_id = db.scalar(statement)
    if inserted_id is None:
        existing = db.scalar(select(ModelUsageEvent).where(ModelUsageEvent.request_id == body.request_id))
        same_payload = existing and (
            existing.tenant_id == body.tenant_id and existing.model_id == body.model_id
            and existing.application_id == body.application_id and existing.user_id == body.user_id
            and existing.input_tokens == body.input_tokens and existing.output_tokens == body.output_tokens
            and existing.outcome == body.outcome
            and existing.usage_is_estimated == body.usage_is_estimated
            and existing.latency_ms == body.latency_ms
        )
        if not same_payload:
            db.rollback()
            raise HTTPException(status_code=409, detail="网关请求 ID 已用于不同用量数据")
        # 完全相同的重试只返回幂等确认，不覆盖原始账目。
        if reservation and reservation.status == "reserved":
            reservation.status = "settled"
            reservation.settled_at = datetime.now(timezone.utc)
        db.commit()
        return {"recorded": False, "duplicate": True}
    if reservation and reservation.status == "reserved":
        reservation.status = "settled"
        reservation.settled_at = datetime.now(timezone.utc)
    db.commit()
    return {"recorded": True, "duplicate": False, "event_id": str(inserted_id)}
