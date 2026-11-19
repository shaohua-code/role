/**
 * 模型测试台 API 契约（docs/模型测试台设计.md §5，已实施）。
 *
 * - GET  /admin/models/{id}/test-context          配置 + 三级下发 + 操作者访问权威判定
 * - POST /admin/models/{id}/test-connection       固定短探针（凭据→网络/TLS→Provider 响应）
 * - POST /admin/models/{id}/test-conversations     创建对话会话（外呼前重验判权）
 * - GET  /admin/models/{id}/test-conversations/{id}/events   SSE 事件流（last_sequence 重连去重）
 * - POST /admin/models/{id}/test-conversations/{id}/cancel    停止当前调用
 *
 * 与设计稿 §5 草案的路径差异：动作统一挂在 /admin/models/{id}/ 前缀下（与
 * test-context 聚合一致）；SSE 事件形状按草案实现（单调 sequence + last_sequence 去重）。
 */
import { api, getToken } from '@/api'
import { ADMIN_API_PREFIX } from '@/api/capabilities'

/** 目录行摘要（服务端只回传允许公开的字段，凭证引用不回传）。 */
export interface TestModelSummary {
  id: string
  key: string
  display_name: string
  provider: string
  model_name: string
  endpoint_url?: string | null
  status: 'active' | 'disabled'
  credential_configured: boolean
  capabilities: string[]
}

/** 测试目标应用上下文。 */
export interface TestContextApplication {
  id: string
  name: string
  tenant_id: string
  tenant_name: string | null
  status: string
}

/** 三级层级状态：active=生效 / missing=缺失 / hidden=无访问关系不泄露明细 / disabled=停用。 */
export type TestLevelState = 'active' | 'missing' | 'hidden' | 'disabled'

/** test-context 响应：页面「配置 / 授权」两段状态的唯一权威来源。 */
export interface ModelTestContext {
  model: TestModelSummary
  application: TestContextApplication | null
  levels: { platform_catalog: TestLevelState; tenant_grant: TestLevelState; application_grant: TestLevelState }
  operator_app_access: boolean
  authz_allowed: boolean
  missing: string[]
  test_channel_available: boolean
}

/** 读取测试上下文；application_id 缺省 = 平台连接视角（只判目录层级）。 */
export function loadTestContext(modelId: string, applicationId?: string): Promise<ModelTestContext> {
  const params = new URLSearchParams()
  if (applicationId) params.set('application_id', applicationId)
  const query = params.toString()
  return api<ModelTestContext>(`${ADMIN_API_PREFIX}/models/${modelId}/test-context${query ? `?${query}` : ''}`)
}

// ── 连接探针 ────────────────────────────────────────────────────────────────

export interface ProbeStage {
  name: string
  status: 'ok' | 'failed'
  latency_ms?: number
}

export interface ProbeError {
  code: string
  message: string
  stage: string
  retry_after_seconds?: number | null
}

/** 连接探针报告：分阶段结果 + 稳定错误分类；不回显凭据原文。 */
export interface ProbeReport {
  test_id: string
  request_id: string
  stages: ProbeStage[]
  verdict: 'ok' | 'fail'
  error: ProbeError | null
  endpoint?: string | null
}

/** 连接探针：服务端受控出口外呼固定探针，可能产生少量 Provider 侧连接开销。 */
export function probeConnection(modelId: string): Promise<ProbeReport> {
  return api<ProbeReport>(`${ADMIN_API_PREFIX}/models/${modelId}/test-connection`, { method: 'POST' })
}

// ── 对话测试通道 ────────────────────────────────────────────────────────────

/** 白名单调试参数（服务端 422 拒绝白名单外字段，不静默忽略）。 */
export interface DebugParams {
  temperature: number
  topP: number
  maxTokens: number
  systemPrompt: string
}

export function defaultDebugParams(): DebugParams {
  return {
    temperature: 0.7, topP: 0.9, maxTokens: 2048, systemPrompt: '',
  }
}

export interface ConversationHistoryTurn {
  role: 'user' | 'assistant'
  content: string
}

/** 创建会话响应：conversation_id 用于订阅事件流，request_id 与用量账目关联。 */
export interface ConversationStart {
  conversation_id: string
  request_id: string
}

/** 创建对话测试会话；外呼前服务端重验三级下发交集（403 = 授权不可用）。 */
export function startConversation(
  modelId: string,
  applicationId: string,
  message: string,
  history: ConversationHistoryTurn[],
  params: DebugParams,
): Promise<ConversationStart> {
  return api<ConversationStart>(`${ADMIN_API_PREFIX}/models/${modelId}/test-conversations`, {
    method: 'POST',
    body: JSON.stringify({
      application_id: applicationId,
      message,
      history,
      params: {
        temperature: params.temperature,
        top_p: params.topP,
        max_tokens: params.maxTokens,
        system_prompt: params.systemPrompt,
      },
    }),
  })
}

/** 停止当前调用：服务端中断流，已收用量按实际情况结算或进入待核对。 */
export function cancelConversation(modelId: string, conversationId: string): Promise<unknown> {
  return api(`${ADMIN_API_PREFIX}/models/${modelId}/test-conversations/${conversationId}/cancel`, { method: 'POST' })
}

/** SSE 事件（单调 sequence；断线重连按 last_sequence 去重）。 */
export type TestSSEType = 'status' | 'authz' | 'reasoning_visible' | 'answer_delta' | 'usage' | 'error' | 'done'
export interface TestSSEEvent {
  sequence: number
  request_id: string
  type: TestSSEType
  timestamp: string
  payload: Record<string, unknown>
}

export interface EventStreamHandlers {
  lastSequence?: number
  signal?: AbortSignal
  onEvent: (event: TestSSEEvent) => void
}

/**
 * 订阅会话事件流：fetch 流式读取（EventSource 无法携带 Bearer 头）。
 * 正常结束（done）resolve；网络中断抛错，由调用方按 Last-Event-ID 语义重连去重。
 */
export async function streamConversationEvents(
  modelId: string,
  conversationId: string,
  handlers: EventStreamHandlers,
): Promise<void> {
  const { lastSequence = 0, signal, onEvent } = handlers
  const token = getToken() ?? ''
  const response = await fetch(
    `${'/api/v1' + ADMIN_API_PREFIX}/models/${modelId}/test-conversations/${conversationId}/events?last_sequence=${lastSequence}`,
    { headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' }, signal },
  )
  if (!response.ok || !response.body) {
    throw new Error(`事件流连接失败（${response.status}）`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let separator = buffer.indexOf('\n\n')
    while (separator >= 0) {
      const frame = buffer.slice(0, separator)
      buffer = buffer.slice(separator + 2)
      separator = buffer.indexOf('\n\n')
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data:')) continue
        try {
          const event = JSON.parse(line.slice(5).trim()) as TestSSEEvent
          onEvent(event)
          // done 即终态：以 cancel 正常关闭读取（避免 AbortController 产生 ERR_ABORTED 噪音）。
          if (event.type === 'done') {
            await reader.cancel().catch(() => undefined)
            return
          }
        } catch { /* 跳过无法解析的帧，不中断流 */ }
      }
    }
  }
  throw new Error('事件流在完成事件前关闭')
}

// ── 页面消息 / 事件模型 ─────────────────────────────────────────────────────

/** 助手消息状态：streaming=生成中 done=完成 aborted=已中止 failed=失败。 */
export type AssistantStatus = 'streaming' | 'done' | 'aborted' | 'failed'

/** 对话消息（含探针报告卡）；会话仅存当前浏览器内存，不落库不进审计正文。 */
export interface TestChatMessage {
  id: string
  role: 'user' | 'assistant' | 'probe'
  text: string
  /** assistant：可见思考（reasoning_visible 增量拼接的连续文本；仅 Provider 实际返回内容）。 */
  thinking: string
  /** assistant：正文（answer_delta 增量拼接）。 */
  answer: string
  status: AssistantStatus
  error?: { code: string; message: string; retryAfterSeconds?: number | null }
  requestId?: string
  conversationId?: string
  finishReason?: string
  /** assistant：Provider 返回的真实用量（usage 事件驱动）。 */
  usage?: {
    inputTokens: number | null
    outputTokens: number | null
    quality: 'actual' | 'estimated'
    firstTokenMs: number | null
    totalMs: number | null
  }
  /** probe：探针报告（pending=测试中）。 */
  probe?: { report: ProbeReport; pending: boolean }
  createdAt: number
}

/** 诊断事件（真实发生的服务端事件，按单调 sequence 展示）。 */
export interface TestEventItem {
  requestId: string
  seq: number
  type: TestSSEType
  summary: string
  payload: Record<string, unknown>
  at: number
}

/** 事件摘要文案（诊断列时间线用）。 */
export function eventSummary(event: TestSSEEvent): string {
  const payload = event.payload
  switch (event.type) {
    case 'status':
      if (payload.stage === 'request_created') return '对话请求创建（服务端受控出口）'
      if (payload.stage === 'provider_connect') return 'Provider 连接建立'
      if (payload.stage === 'cancel_requested') return '收到停止请求，正在中断流'
      if (payload.stage === 'cancelled') return '已停止：取消已生效，部分用量按估算入账'
      return `状态：${String(payload.stage ?? '更新')}`
    case 'authz':
      return payload.result === 'pass' ? '授权判定通过（三级下发交集有效）' : '授权判定未通过'
    case 'reasoning_visible':
      return `可见思考片段（${String(payload.text ?? '').length} 字）`
    case 'answer_delta':
      return `正文片段（${String(payload.text ?? '').length} 字）`
    case 'usage':
      return `用量：输入 ${payload.input_tokens ?? '未知'} · 输出 ${payload.output_tokens ?? '未知'} · 质量 ${payload.quality ?? 'unknown'}`
    case 'error':
      return `错误 ${String(payload.code ?? '')}：${String(payload.message ?? '')}`
    case 'done':
      return `生成结束 finish_reason=${String(payload.finish_reason ?? '—')}`
    default:
      return event.type
  }
}
