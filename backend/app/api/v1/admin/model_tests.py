"""模型测试台：服务端权威判定 + 受控 Provider 出口（docs/模型测试台设计.md §5）。

能力边界：
- `GET /{model_id}/test-context`：目录配置 + 三级下发交集 + 操作者应用访问的权威判定。
- `POST /{model_id}/test-connection`：固定短探针（凭据解析 → 网络/TLS → Provider 响应），
  使用 OpenAI 兼容 GET /models，不产生对话与计费 token。
- `POST /{model_id}/test-conversations`：创建对话测试会话（判权 → 进程内会话 →
  后台任务经受控出口流式外呼），返回 conversation_id / request_id；正文不落库不进日志。
- `GET /{model_id}/test-conversations/{id}/events`：SSE 事件流（单调 sequence，
  支持 last_sequence 断线重连去重），事件类型 status/authz/reasoning_visible/
  answer_delta/usage/error/done。
- `POST /{model_id}/test-conversations/{id}/cancel`：停止当前调用；已收到部分用量
  如实结算为 failed/估算，不伪装成完成。

诚实性红线（设计文档 §2/§5）：Provider 凭据只在服务端解析发送；错误统一稳定分类，
不透传上游原始正文；测试用量 source=model_test 落账（可区分但不漏计）；外呼前
逐请求重验三级下发交集。数据库需迁移 0010（放宽 source CHECK）后账目才能写入。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field as PydanticField, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit
from app.core.config import get_settings
from app.core.security import current_user, is_platform_admin_user
from app.db.session import get_db_session, get_engine
from app.models.application import Application
from app.models.identity import Tenant, User
from app.models.model_catalog import ModelCatalog, ModelUsageEvent
from app.services.admin_authorization import AdminAccessGuard
from app.services.model_channel import (
    ChannelError,
    probe_provider,
    resolve_base_url,
    resolve_credential,
    stream_chat,
)
from app.services.model_distribution import ModelDistribution
from app.services.permission_kinds import ROLE_SCOPE_SUPER
from app.services.rbac_guards import PermissionEnforcer
from sqlalchemy import select
from decimal import Decimal

router = APIRouter(prefix="/models", tags=["模型测试台"])

# 会话注册表：进程内存（正文不落库不进日志），TTL 由创建时顺带回收。
_CONVERSATIONS: dict[str, "_Conversation"] = {}

logger = logging.getLogger(__name__)


def _ensure_model_test(actor: User, db: Session) -> None:
    """测试台入口 = 超管范围 + button.models.manage（设计文档 §6 现行边界）。"""
    PermissionEnforcer.ensure_scope(actor, db, ROLE_SCOPE_SUPER, detail="模型测试台需要超管范围")
    PermissionEnforcer.ensure_codes(actor, db, "button.models.manage", detail="缺少管理权限：button.models.manage")


def _operator_can_access_application(actor: User, application: Application, db: Session) -> bool:
    """操作者对目标应用是否存在访问关系（平台管理员恒可代管）。"""
    if is_platform_admin_user(actor, db):
        return True
    readable = AdminAccessGuard.list_readable_application_capabilities(actor, application.tenant_id, db)
    return application.id in readable


def _judge_sync(db: Session, model_id: UUID, application_id: UUID | None) -> tuple[ModelCatalog, Application | None, list[str]]:
    """三级下发交集判定（同步，供线程池调用）；返回 (模型, 应用, 缺失层级列表)。"""
    model = db.get(ModelCatalog, model_id)
    if model is None or model.tenant_id != ModelDistribution.get_platform_tenant(db).id:
        raise HTTPException(404, "模型不存在")
    application_row: Application | None = None
    missing: list[str] = []
    if model.status != "active":
        missing.append("模型已停用")
    if application_id is not None:
        application_row = db.get(Application, application_id)
        if application_row is None:
            raise HTTPException(404, "应用不存在")
        if not ModelDistribution.tenant_grant_is_active(db, model.id, application_row.tenant_id):
            missing.append("租户未下发该模型")
        if not ModelDistribution.application_grant_is_active(db, model.id, application_row.id):
            missing.append("应用未下发该模型")
    return model, application_row, missing


@router.get("/{model_id}/test-context")
async def get_model_test_context(
    model_id: UUID,
    application_id: UUID | None = Query(default=None),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """目录配置 + 三级下发交集 + 操作者访问的权威判定（无 Provider 外呼）。"""
    await run_in_threadpool(_ensure_model_test, actor, db)
    model, application_row, _missing = await run_in_threadpool(_judge_sync, db, model_id, application_id)
    operator_app_access = True
    if application_row is not None:
        operator_app_access = await run_in_threadpool(_operator_can_access_application, actor, application_row, db)

    platform_catalog: str = model.status
    tenant_grant = "missing"
    application_grant = "missing"
    if application_row is not None and operator_app_access:
        tenant_grant = "active" if await run_in_threadpool(
            ModelDistribution.tenant_grant_is_active, db, model.id, application_row.tenant_id) else "missing"
        application_grant = "active" if await run_in_threadpool(
            ModelDistribution.application_grant_is_active, db, model.id, application_row.id) else "missing"
    elif application_row is not None:
        # 无访问关系：下发明细对操作者不可见（防枚举，与 AdminAccessGuard 口径一致）。
        tenant_grant = "hidden"
        application_grant = "hidden"

    missing: list[str] = []
    if platform_catalog != "active":
        missing.append("模型已停用" if platform_catalog == "disabled" else "模型不在平台目录")
    if application_row is not None:
        if not operator_app_access:
            missing.append("当前操作者无该应用访问关系")
        if tenant_grant == "missing":
            missing.append("租户未下发该模型")
        if application_grant == "missing":
            missing.append("应用未下发该模型")

    tenant_name = None
    if application_row is not None:
        tenant_row = await run_in_threadpool(db.get, Tenant, application_row.tenant_id)
        tenant_name = tenant_row.name if tenant_row else None

    return {
        "model": {
            "id": str(model.id), "key": model.key, "display_name": model.display_name,
            "provider": model.provider, "model_name": model.model_name,
            "endpoint_url": model.endpoint_url, "status": model.status,
            "credential_configured": bool(model.credential_ref), "capabilities": model.capabilities,
        },
        "application": None if application_row is None else {
            "id": str(application_row.id), "name": application_row.name,
            "tenant_id": str(application_row.tenant_id), "tenant_name": tenant_name,
            "status": application_row.status,
        },
        "levels": {
            "platform_catalog": platform_catalog,
            "tenant_grant": tenant_grant,
            "application_grant": application_grant,
        },
        "operator_app_access": operator_app_access,
        "authz_allowed": platform_catalog == "active" and (
            application_row is None or (
                operator_app_access and tenant_grant == "active" and application_grant == "active"
            )
        ),
        "missing": missing,
        # 受控出口已接入（探针/对话通道随本路由提供）。
        "test_channel_available": True,
    }


# ── 连接探针 ────────────────────────────────────────────────────────────────

@router.post("/{model_id}/test-connection")
async def test_connection(
    model_id: UUID,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """固定短探针：凭据解析 → 网络/TLS → Provider 响应；不产生计费 token。"""
    await run_in_threadpool(_ensure_model_test, actor, db)
    model, _app, _missing = await run_in_threadpool(_judge_sync, db, model_id, None)
    started = time.monotonic()
    stages: list[dict] = []
    test_id = f"tst-{uuid4().hex[:12]}"
    request_id = f"mt-{uuid4().hex}"

    def _stage_credential() -> tuple[str, str]:
        """凭据解析阶段（同步环境变量读取）；返回 (api_key 摘要状态, base_url)。"""
        api_key = resolve_credential(model.credential_ref)
        base_url = resolve_base_url(model.endpoint_url, model.provider)
        return api_key, base_url

    try:
        api_key, base_url = await run_in_threadpool(_stage_credential)
        stages.append({"name": "凭据解析（受控引用，不回显原文）", "status": "ok", "latency_ms": _elapsed(started)})
    except ChannelError as error:
        stages.append({"name": "凭据解析（受控引用，不回显原文）", "status": "failed", "latency_ms": _elapsed(started)})
        _audit_test(db, actor, request, "model.test.connection", model, {"test_id": test_id, "verdict": "failed", "stage": "credential"})
        db.commit()
        return _probe_response(test_id, request_id, stages, "fail",
                               {"code": error.code, "message": error.message, "stage": "credential"})

    try:
        await probe_provider(base_url, api_key)
        stages.append({"name": "网络 / TLS", "status": "ok", "latency_ms": _elapsed(started)})
        stages.append({"name": "Provider 响应（GET /models）", "status": "ok", "latency_ms": _elapsed(started)})
    except ChannelError as error:
        stages.append({"name": "网络 / TLS", "status": "failed", "latency_ms": _elapsed(started)})
        _audit_test(db, actor, request, "model.test.connection", model,
                    {"test_id": test_id, "verdict": "failed", "stage": error.code})
        db.commit()
        return _probe_response(test_id, request_id, stages, "fail",
                               {"code": error.code, "message": error.message,
                                "stage": "network_tls", "retry_after_seconds": error.retry_after_seconds})

    _audit_test(db, actor, request, "model.test.connection", model, {"test_id": test_id, "verdict": "ok"})
    db.commit()
    return _probe_response(test_id, request_id, stages, "ok", None, base_url=base_url)


def _elapsed(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _probe_response(test_id: str, request_id: str, stages: list[dict], verdict: str,
                    error: dict | None, base_url: str | None = None) -> dict:
    return {"test_id": test_id, "request_id": request_id, "stages": stages,
            "verdict": verdict, "error": error, "endpoint": base_url}


def _audit_test(db: Session, actor: User, request: Request, action: str,
                model: ModelCatalog, details: dict) -> None:
    """测试动作审计：只记操作者/模型/动作/结果/请求 ID/时间，不记提示词、回复或凭据。"""
    audit(db, actor, request, action, "model", str(model.id),
          {**details, "model_key": model.key})


# ── 对话测试会话 ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _ModelSnapshot:
    """后台任务使用的模型字段快照。

    请求会话 commit 后 ORM 实例字段过期、响应结束后会话关闭实例分离；后台任务
    若再触碰 ORM 对象会抛 DetachedInstanceError 且被静默吞掉。因此外呼任务只允许
    读取创建时固化的这份不可变快照。
    """

    id: UUID
    key: str
    model_name: str
    provider: str
    credential_ref: str | None
    endpoint_url: str | None


@dataclass
class _Conversation:
    conversation_id: str
    request_id: str
    model_id: UUID
    application_id: UUID
    tenant_id: UUID
    operator_id: UUID
    created_at: float
    events: list[dict] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None
    finished: bool = False
    seq: int = 0
    # 用量统计：usage 事件与落账共用；Provider 未返回真实用量时按字符数估算并标记。
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    usage_estimated: bool = False
    first_token_ms: int | None = None


def _push_event(conversation: _Conversation, event_type: str, payload: dict) -> dict:
    """追加事件（单调 sequence）并广播给订阅者；事件仅存进程内存。"""
    conversation.seq += 1
    event = {
        "sequence": conversation.seq,
        "request_id": conversation.request_id,
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    conversation.events.append(event)
    for queue in list(conversation.subscribers):
        queue.put_nowait(event)
    return event


def _purge_expired_conversations() -> None:
    """回收超过 TTL 的会话（含未完成任务取消），防止注册表无限增长。"""
    ttl = get_settings().model_test_session_ttl_seconds
    now = time.monotonic()
    for key in [key for key, conv in _CONVERSATIONS.items() if now - conv.created_at > ttl]:
        conversation = _CONVERSATIONS.pop(key, None)
        if conversation is not None and conversation.task is not None and not conversation.task.done():
            conversation.cancel_event.set()


def _record_usage_sync(conversation: _Conversation, outcome: str) -> None:
    """测试用量落账（source=model_test，与业务流量可区分但不漏计）。

    独立 Session：后台任务与请求生命周期解耦；绝不写提示词/回复正文/凭据。
    Provider 未返回精确用量时按字符数估算并置 usage_is_estimated（未知≠0）。
    """
    input_tokens = conversation.input_tokens
    output_tokens = conversation.output_tokens
    estimated = conversation.usage_estimated
    if input_tokens is None:
        input_tokens = 0
        estimated = True
    if output_tokens is None:
        output_tokens = 0
        estimated = True
    with Session(get_engine()) as session:
        model = session.get(ModelCatalog, conversation.model_id)
        if model is None:
            return
        estimated_cost = None
        if model.input_cost_per_million is not None and model.output_cost_per_million is not None:
            estimated_cost = (Decimal(input_tokens) * model.input_cost_per_million
                              + Decimal(output_tokens) * model.output_cost_per_million) / Decimal(1_000_000)
        session.add(ModelUsageEvent(
            request_id=conversation.request_id,
            tenant_id=conversation.tenant_id, model_id=conversation.model_id,
            application_id=conversation.application_id, user_id=conversation.operator_id,
            input_tokens=input_tokens, output_tokens=output_tokens,
            estimated_cost=estimated_cost, outcome=outcome,
            usage_is_estimated=estimated, source="model_test",
            latency_ms=int((time.monotonic() - conversation.created_at) * 1000),
        ))
        session.commit()


async def _run_conversation(conversation: _Conversation, model: _ModelSnapshot,
                            message: str, history: list[dict], params: dict) -> None:
    """后台任务外壳：任何未预期异常都转为 error+done 事件并如实落账，绝不静默挂起。"""
    started = time.monotonic()
    try:
        await _execute_conversation(conversation, model, message, history, params, started)
    except Exception:
        # 兜底：未预期异常若被吞掉，前端将永远等不到 done；记录服务端日志并给稳定分类。
        logger.exception("模型测试台后台任务内部异常 conversation=%s request=%s",
                         conversation.conversation_id, conversation.request_id)
        try:
            if not conversation.finished:
                _push_event(conversation, "error", {
                    "code": "internal_error", "stage": "internal",
                    "message": "测试台内部错误，本次调用已终止（详情见服务端日志）"})
                await run_in_threadpool(_record_usage_sync, conversation, "failed")
                _push_event(conversation, "done", {"finish_reason": "error", "outcome": "failed"})
                conversation.finished = True
        except Exception:
            logger.exception("模型测试台兜底落账失败 conversation=%s", conversation.conversation_id)


def _provider_messages(message: str, history: list[dict], params: dict) -> list[dict]:
    messages: list[dict] = []
    system_prompt = (params.get("system_prompt") or "").strip()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend({"role": turn["role"], "content": turn["content"]} for turn in history)
    messages.append({"role": "user", "content": message})
    return messages


async def _execute_conversation(conversation: _Conversation, model: _ModelSnapshot,
                                message: str, history: list[dict], params: dict, started: float) -> None:
    """后台任务主体：经受控出口流式外呼，事件驱动前端；异常/取消都如实落账。"""
    try:
        api_key, base_url = await run_in_threadpool(
            lambda: (resolve_credential(model.credential_ref),
                     resolve_base_url(model.endpoint_url, model.provider)))
    except ChannelError as error:
        _push_event(conversation, "error", {"code": error.code, "message": error.message, "stage": "credential"})
        await run_in_threadpool(_record_usage_sync, conversation, "failed")
        _push_event(conversation, "done", {"finish_reason": "error", "provider_not_called": True})
        conversation.finished = True
        return

    _push_event(conversation, "status", {"stage": "provider_connect", "endpoint": base_url})
    messages = _provider_messages(message, history, params)
    # 输入用量先按字符估算兜底；Provider 返回真实 usage 后覆盖（估算标记同步解除）。
    conversation.input_tokens = sum(len(str(m["content"])) for m in messages) // 3
    conversation.usage_estimated = True

    outcome = "succeeded"
    finish_reason = "stop"
    try:
        async for chunk in stream_chat(
            base_url, api_key, model_name=model.model_name, messages=messages,
            temperature=float(params.get("temperature", 0.7)),
            top_p=float(params.get("top_p", 0.9)),
            max_tokens=int(params.get("max_tokens") or get_settings().model_test_max_output_tokens),
            cancel_event=conversation.cancel_event,
        ):
            if conversation.first_token_ms is None and chunk.kind in ("answer", "reasoning"):
                conversation.first_token_ms = int((time.monotonic() - started) * 1000)
            if chunk.kind == "reasoning":
                _push_event(conversation, "reasoning_visible", {"text": chunk.text})
            elif chunk.kind == "answer":
                _push_event(conversation, "answer_delta", {"text": chunk.text})
            elif chunk.kind == "usage":
                if chunk.input_tokens is not None:
                    conversation.input_tokens = chunk.input_tokens
                    conversation.usage_estimated = False
                if chunk.output_tokens is not None:
                    conversation.output_tokens = chunk.output_tokens
            elif chunk.kind == "finish":
                finish_reason = chunk.finish_reason or finish_reason
        if conversation.cancel_event.is_set():
            # 用户停止：已收到部分内容如实保留，账目按 failed/估算进入待核对（不伪装完成）。
            outcome = "failed"
            _push_event(conversation, "status", {
                "stage": "cancelled", "reached_provider": True,
                "billing": "部分消耗按估算入账，待核对",
            })
    except ChannelError as error:
        outcome = "failed"
        _push_event(conversation, "error", {
            "code": error.code, "message": error.message, "stage": "provider_response",
            "http_status": error.http_status, "retry_after_seconds": error.retry_after_seconds,
        })

    _push_event(conversation, "usage", {
        "input_tokens": conversation.input_tokens, "output_tokens": conversation.output_tokens,
        "usage_is_estimated": conversation.usage_estimated,
        "quality": "estimated" if conversation.usage_estimated else "actual",
        "first_token_ms": conversation.first_token_ms,
        "total_ms": int((time.monotonic() - started) * 1000),
    })
    await run_in_threadpool(_record_usage_sync, conversation, outcome)
    _push_event(conversation, "done", {"finish_reason": finish_reason, "outcome": outcome})
    conversation.finished = True


class TestConversationParams(BaseModel):
    """白名单调试参数；超出白名单的字段直接拒绝（422），不静默忽略。"""

    model_config = ConfigDict(extra="forbid")

    temperature: float = PydanticField(default=0.7, ge=0, le=2)
    top_p: float = PydanticField(default=0.9, ge=0, le=1)
    max_tokens: int = PydanticField(default=2048, ge=64, le=8192)
    system_prompt: str = PydanticField(default="", max_length=8000)


class TestConversationTurn(BaseModel):
    """仅接受已完成轮次的用户输入与助手正文。"""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = PydanticField(min_length=1, max_length=32000)


class TestConversationCreate(BaseModel):
    """对话测试创建请求：消息必填，应用必填（应用对话测试按应用逐次判权）。"""

    model_config = ConfigDict(extra="forbid")

    application_id: UUID
    message: str = PydanticField(min_length=1, max_length=16000)
    history: list[TestConversationTurn] = PydanticField(default_factory=list, max_length=20)
    params: TestConversationParams = PydanticField(default_factory=TestConversationParams)

    @model_validator(mode="after")
    def validate_history(self) -> "TestConversationCreate":
        if not self.message.strip():
            raise ValueError("当前消息不能为空")
        if len(self.history) % 2:
            raise ValueError("历史消息必须由完整的用户与助手轮次组成")
        for index, turn in enumerate(self.history):
            expected = "user" if index % 2 == 0 else "assistant"
            if turn.role != expected or not turn.content.strip():
                raise ValueError("历史消息必须按用户、助手顺序交替且内容非空")
        if sum(len(turn.content) for turn in self.history) > 32000:
            raise ValueError("历史上下文超过 32000 字，请清空或缩短会话")
        return self


@router.post("/{model_id}/test-conversations", status_code=201)
async def create_test_conversation(
    model_id: UUID,
    body: TestConversationCreate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """创建对话测试会话：外呼前重验三级下发交集（设计文档 §5），正文不落库。"""
    await run_in_threadpool(_ensure_model_test, actor, db)
    model, application_row, missing = await run_in_threadpool(_judge_sync, db, model_id, body.application_id)
    if missing:
        _audit_test(db, actor, request, "model.test.conversation", model,
                    {"verdict": "authz_denied", "missing": missing})
        db.commit()
        raise HTTPException(status_code=403, detail={
            "code": "authz_denied", "message": "授权不可用，外呼前判定未通过", "missing": missing})

    _purge_expired_conversations()
    conversation = _Conversation(
        conversation_id=f"conv-{uuid4().hex[:16]}",
        request_id=f"mt-{uuid4().hex}",
        model_id=model.id,
        application_id=application_row.id,
        tenant_id=application_row.tenant_id,
        operator_id=actor.id,
        created_at=time.monotonic(),
    )
    _push_event(conversation, "status", {
        "stage": "request_created", "mode": "app",
        "model": model.key, "application": application_row.name,
        "params": body.params.model_dump(),
    })
    _push_event(conversation, "authz", {
        "result": "pass",
        "intersection": ["platform_catalog:active", "tenant_grant:active", "application_grant:active"],
    })
    # 在请求会话 commit（字段过期）前固化字段快照：后台任务绝不触碰 ORM 实例。
    snapshot = _ModelSnapshot(
        id=model.id, key=model.key, model_name=model.model_name, provider=model.provider,
        credential_ref=model.credential_ref, endpoint_url=model.endpoint_url,
    )
    conversation.task = asyncio.create_task(_run_conversation(
        conversation, snapshot, body.message,
        [turn.model_dump() for turn in body.history], body.params.model_dump()))
    _CONVERSATIONS[conversation.conversation_id] = conversation
    _audit_test(db, actor, request, "model.test.conversation", model,
                {"conversation_id": conversation.conversation_id,
                 "request_id": conversation.request_id, "verdict": "started"})
    db.commit()
    return {"conversation_id": conversation.conversation_id, "request_id": conversation.request_id}


def _load_conversation(model_id: UUID, conversation_id: str) -> _Conversation:
    """按 ID 取会话；不存在或已过期与模型不匹配一律 404（会话不落库，重启即失）。"""
    conversation = _CONVERSATIONS.get(conversation_id)
    if conversation is None or conversation.model_id != model_id:
        raise HTTPException(404, "测试会话不存在或已过期（会话仅存服务端进程内存）")
    return conversation


@router.get("/{model_id}/test-conversations/{conversation_id}/events")
async def stream_test_conversation_events(
    model_id: UUID,
    conversation_id: str,
    last_sequence: int = Query(default=0, ge=0),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """SSE 事件流：先重放 sequence > last_sequence 的事件，再实时推送；done 终结。"""
    await run_in_threadpool(_ensure_model_test, actor, db)
    conversation = _load_conversation(model_id, conversation_id)

    async def generator():
        queue: asyncio.Queue = asyncio.Queue()
        conversation.subscribers.append(queue)
        cursor = last_sequence
        try:
            # 先重放历史（订阅之后的重复由 cursor 去重），再实时消费队列。
            for event in list(conversation.events):
                if event["sequence"] > cursor:
                    cursor = event["sequence"]
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    if event["type"] == "done":
                        return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if event["sequence"] <= cursor:
                    continue
                cursor = event["sequence"]
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["type"] == "done":
                    return
        finally:
            if queue in conversation.subscribers:
                conversation.subscribers.remove(queue)

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{model_id}/test-conversations/{conversation_id}/cancel")
async def cancel_test_conversation(
    model_id: UUID,
    conversation_id: str,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """停止当前调用：置取消标志由后台任务中断流并按已收用量如实落账。"""
    await run_in_threadpool(_ensure_model_test, actor, db)
    conversation = _load_conversation(model_id, conversation_id)
    already_finished = conversation.finished
    if not already_finished:
        conversation.cancel_event.set()
        _push_event(conversation, "status", {"stage": "cancel_requested"})
    _audit_test(db, actor, request, "model.test.cancel",
                SimpleNamespace(id=conversation.model_id, key=conversation.request_id),
                {"conversation_id": conversation_id, "verdict": "cancelled"})
    db.commit()
    return {"cancelled": True, "already_finished": already_finished,
            "reached_provider": True, "billing": "已收用量按实际情况结算或进入待核对"}
