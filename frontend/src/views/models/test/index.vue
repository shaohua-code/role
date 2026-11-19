<script setup lang="ts">
// 模型测试台（/models/test，不占侧栏：模型治理目录行操作进入）。
// 全链真实数据：配置/授权来自服务端 test-context 权威判定；发送/探针经受控出口
// 真实外呼 Provider（OpenAI 兼容），用量 source=model_test 落账（可区分但不漏计）。
// 会话仅存当前浏览器内存；正文/思考不落库、不进日志与审计。
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import { api } from '@/api'
import { hasButton } from '@/api/capabilities'
import { ClearOutlined, DownOutlined, ExperimentOutlined, SettingOutlined, ThunderboltOutlined } from '@/plugins/icons'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import type { StripCell } from './components/StatusStrip.vue'
import ChatColumn from './components/ChatColumn.vue'
import TestSidePanel from './components/TestSidePanel.vue'
import DebugDrawer from './components/DebugDrawer.vue'
import {
  cancelConversation, defaultDebugParams, eventSummary, loadTestContext,
  probeConnection, startConversation, streamConversationEvents,
  type ConversationHistoryTurn, type DebugParams, type ModelTestContext, type TestChatMessage,
  type TestEventItem, type TestModelSummary, type TestSSEEvent,
} from './api'

interface SeedTenant { id: string; name: string; status: string }
interface ApplicationRow { id: string; name: string; tenant_id: string; status: string }

const props = defineProps<{ seedTenants?: SeedTenant[] }>()

const route = useRoute()

// 页内边界：与模型治理写操作一致（超管范围 + button.models.manage，设计文档 §6）。
const canManage = computed(() => hasButton('button.models.manage'))

// ── 目录与上下文 ────────────────────────────────────────────────────────────
const models = ref<TestModelSummary[]>([])
const tenants = ref<SeedTenant[]>([])
const applications = ref<ApplicationRow[]>([])

const mode = ref<'app' | 'platform'>('app')
const modelId = ref('')
const tenantId = ref('')
const applicationId = ref('')

const context = ref<ModelTestContext | null>(null)
const contextLoading = ref(false)
const contextError = ref('')
let contextSequence = 0

// ── 会话（仅浏览器内存）─────────────────────────────────────────────────────
const messages = ref<TestChatMessage[]>([])
const events = ref<TestEventItem[]>([])
// 诊断失效源：助手消息对象在流式期间被原地变更（同一引用），数组替换虽触发父组件重渲染，
// 但诊断 computed 链上游（lastSettledAssistant）重算后返回同引用，会被 Object.is 相等短路，
// 下游（thinkingText/usageSnapshot 等）永不失效——实测表现为 Tab 永久冻结在流式初期值。
// 每个 SSE 事件落地时自增，诊断 computed 显式依赖它强制重算。
const diagnosticTick = ref(0)
const params = ref<DebugParams>(defaultDebugParams())
const drawerOpen = ref(false)
const diagnosticTab = ref<'thinking' | 'events' | 'usage'>('thinking')
const sending = ref(false)
const probeRunning = ref(false)
const lastTestedAt = ref('')
// 当前流式消费的取消器：切换上下文/离开页面时断开 SSE。
let streamAbort: AbortController | null = null
let streamConversationId = ''
let streamModelId = ''
let sessionEpoch = 0

// Provider / 本次生成两段状态：只有真实通道交互才更新；上下文切换即复位为「未测试」。
const providerCell = reactive<StripCell>({ state: 'pending' })
const generationCell = reactive<StripCell>({ state: 'pending' })

const selectedModel = computed(() => models.value.find(model => model.id === modelId.value) ?? null)
const streaming = computed(() => messages.value.some(m => m.role === 'assistant' && m.status === 'streaming'))

// ── 状态行计算：配置 / 授权来自服务端权威判定 ────────────────────────────────
const configCell = computed<StripCell>(() => {
  if (!modelId.value) return { state: 'pending' }
  if (contextError.value) return { state: 'warn', hint: contextError.value }
  if (!context.value) return { state: 'pending' }
  if (context.value.levels.platform_catalog === 'disabled') return { state: 'fail', hint: '模型已停用' }
  if (!context.value.model.credential_configured) return { state: 'fail', hint: '凭据引用未配置：请先在模型目录配置凭证' }
  if (context.value.levels.platform_catalog === 'active') return { state: 'ok' }
  return { state: 'warn', hint: '模型不在平台目录' }
})

const authCell = computed<StripCell>(() => {
  if (mode.value === 'platform') return { state: 'na', hint: '平台连接模式不做应用授权判定' }
  if (!modelId.value || !applicationId.value) return { state: 'pending' }
  if (contextError.value) return { state: 'warn', hint: contextError.value }
  if (!context.value) return { state: 'pending' }
  if (context.value.authz_allowed) return { state: 'ok' }
  return { state: 'fail', hint: `缺失层级：${context.value.missing.join('、')}` }
})

// 发送禁用原因（空串 = 可发送）；授权判定以后端逐请求判权为准，前端只做同口径预检。
const sendDisabledReason = computed(() => {
  if (!selectedModel.value) return '请先选择模型'
  if (!applicationId.value && mode.value === 'app') return '请先选择应用'
  if (contextLoading.value) return '正在读取测试上下文…'
  if (contextError.value) return '测试上下文读取失败，请重试'
  if (!context.value) return '正在读取测试上下文…'
  if (mode.value === 'app' && context.value && !context.value.authz_allowed) {
    return `授权不可用：${context.value.missing.join('、')}`
  }
  return ''
})

const probeDisabled = computed(() => !modelId.value || probeRunning.value || Boolean(contextError.value))

// 思考区：区分「有内容」与缺失原因（模型不支持 / 参数关闭 / Provider 未提供）。
// 诊断源取「最近一条已终结」的助手消息（done/aborted/failed）：生成中的消息思考与用量尚未定形，
// 且任何卡死的流式幽灵消息都会把诊断 Tab 永久钉在「生成中 / 尚未执行调用」（实测缺陷：
// 聊天区已展示 195 字思考与实测用量，诊断 Tab 仍等待）。流式中的实时思考仍由消息内思考块展示。
const lastSettledAssistant = computed(() => {
  const assistants = [...messages.value].reverse().filter(m => m.role === 'assistant')
  return assistants.find(m => m.status !== 'streaming') ?? assistants[0] ?? null
})
const thinkingText = computed(() => {
  void diagnosticTick.value // 消息对象原地变更，依赖 tick 强制失效（见 diagnosticTick 注）
  return lastSettledAssistant.value?.thinking ?? ''
})
const thinkingReason = computed(() => {
  void diagnosticTick.value
  if (thinkingText.value) return ''
  if (!selectedModel.value) return '未选择模型'
  if (!lastSettledAssistant.value) return '尚未调用'
  if (lastSettledAssistant.value.status === 'streaming') return '生成中'
  if (lastSettledAssistant.value.status === 'failed' || lastSettledAssistant.value.status === 'aborted') return '调用未完成'
  if (!selectedModel.value.capabilities.includes('thinking_output')) return '模型不支持'
  return 'Provider 未提供'
})
const thinkingDetail = computed(() => ({
  '': '',
  '未选择模型': '选择模型与上下文后再开始测试',
  '尚未调用': '发送消息后展示 Provider 实际返回的可见思考',
  '生成中': '正在等待 Provider 返回可见思考片段',
  '调用未完成': '本次请求未成功结束，无法据此判断 Provider 是否支持可见思考',
  '模型不支持': '模型目录未声明 thinking_output，预期不会返回可见过程',
  'Provider 未提供': '本次调用 Provider 未返回可见思考内容，也不得根据最终答案猜测步骤',
}[thinkingReason.value] ?? ''))

// 生效参数摘要（仅诊断区「请求与用量」明细使用；输入区 chips 已删减避免重复信息）。
const paramsSummary = computed(() => {
  const p = params.value
  return [
    `T ${p.temperature}`,
    `top_p ${p.topP}`,
    `≤${p.maxTokens} tok`,
    ...(p.systemPrompt.trim() ? ['系统提示词'] : []),
  ].join(' · ')
})

// 测试范围选择已从顶部工具条移入右栏统一卡（用户标注「和下面卡片融合成一个」），
// 上下文切换组件由 TestSidePanel 内的 ContextBar 承接。

// 最近一次「已终结」请求的用量快照（usage 事件驱动；未知显示待核对，不显示 0）。
const usageSnapshot = computed(() => {
  void diagnosticTick.value // 消息对象原地变更，依赖 tick 强制失效（见 diagnosticTick 注）
  const usage = lastSettledAssistant.value?.usage
  if (!usage) return null
  return {
    requestId: lastSettledAssistant.value?.requestId ?? '—',
    httpStatus: lastSettledAssistant.value?.status === 'failed' ? '—' : '2xx',
    quality: usage.quality,
    inputTokens: usage.inputTokens,
    outputTokens: usage.outputTokens,
    reasoningTokens: null,
    note: usage.quality === 'estimated'
      ? '本次用量为估算（Provider 未返回精确计数）或调用中止，账目已标记待核对，以 Provider 账单为准。'
      : '',
  }
})

// ── 诊断事件：真实服务端事件（sequence 单调）────────────────────────────────
function pushLocalEvent(event: TestSSEEvent): void {
  events.value.push({ requestId: event.request_id, seq: event.sequence, type: event.type, summary: eventSummary(event), payload: event.payload, at: Date.now() })
}

// ── 数据加载 ────────────────────────────────────────────────────────────────
async function loadDictionaries(): Promise<void> {
  if (!canManage.value) return
  try {
    const tenantsSource = props.seedTenants?.length
      ? Promise.resolve(props.seedTenants)
      : api<SeedTenant[]>('/admin/tenants')
    const tenantRows = await tenantsSource
    // 应用字典：平台管理员全局目录；租户域操作者必须按租户显式查询（后端判权口径）。
    const appLists = tenantRows.length
      ? await Promise.all(tenantRows.map(tenant =>
          api<ApplicationRow[]>(`/admin/applications?tenant_id=${encodeURIComponent(tenant.id)}`).catch(() => [] as ApplicationRow[])))
      : [await api<ApplicationRow[]>('/admin/applications').catch(() => [] as ApplicationRow[])]
    const modelRows = await api<TestModelSummary[]>('/admin/models')
    tenants.value = tenantRows
    applications.value = appLists.flat()
    models.value = modelRows
    // 深链预选：/models/test?model_id=...（模型治理行操作入口携带）。
    const queryModelId = typeof route.query.model_id === 'string' ? route.query.model_id : ''
    if (!modelId.value && queryModelId && modelRows.some(model => model.id === queryModelId)) {
      modelId.value = queryModelId
    }
    if (!tenantId.value && tenantRows.length) tenantId.value = tenantRows[0].id
    syncApplicationToTenant()
    if (!applicationId.value && applications.value.length) applicationId.value = applications.value[0].id
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取模型目录失败')
  }
}

// 租户切换后应用必须跟随（应用不属于所选租户时取该租户首个应用）。
function syncApplicationToTenant(): void {
  const owned = applications.value.filter(application =>
    application.tenant_id === tenantId.value && application.status === 'active')
  if (!owned.some(application => application.id === applicationId.value)) {
    applicationId.value = owned[0]?.id ?? ''
  }
}

// ── 测试上下文（配置 / 授权权威判定）────────────────────────────────────────
async function loadContext(): Promise<void> {
  const sequence = ++contextSequence
  if (!modelId.value) {
    context.value = null
    contextError.value = ''
    return
  }
  contextLoading.value = true
  contextError.value = ''
  try {
    const result = await loadTestContext(modelId.value, mode.value === 'app' ? applicationId.value : undefined)
    if (sequence !== contextSequence) return
    context.value = result
  } catch (error) {
    if (sequence !== contextSequence) return
    context.value = null
    contextError.value = error instanceof Error ? error.message : '测试上下文读取失败'
  } finally {
    if (sequence === contextSequence) contextLoading.value = false
  }
}

// 会话清理：切换模型/租户/应用/模式自动清空（设计文档 §3.1），并断开进行中的 SSE。
function resetSession(): void {
  sessionEpoch += 1
  if (streamConversationId && streamModelId) {
    void cancelConversation(streamModelId, streamConversationId).catch(() => undefined)
  }
  streamAbort?.abort()
  streamAbort = null
  streamConversationId = ''
  streamModelId = ''
  messages.value = []
  events.value = []
  sending.value = false
  probeRunning.value = false
  lastTestedAt.value = ''
  providerCell.state = 'pending'
  providerCell.hint = undefined
  generationCell.state = 'pending'
  generationCell.hint = undefined
}

watch([modelId, applicationId, mode], () => {
  resetSession()
  void loadContext()
})
watch(tenantId, () => {
  syncApplicationToTenant()
  resetSession()
  void loadContext()
})
// 深链变化（模型治理再次携带不同 model_id 进入）：同步模型选择。
watch(() => route.query.model_id, (value) => {
  const next = typeof value === 'string' ? value : ''
  if (next && next !== modelId.value && models.value.some(model => model.id === next)) {
    modelId.value = next
  }
})

// lg 断点响应式：lg+ 用 Splitpanes 拖拽分栏，窄屏降级为纵向堆叠 + 页面滚动。
const desktopMedia = typeof window !== 'undefined' ? window.matchMedia('(min-width: 1024px)') : null
const isDesktop = ref(desktopMedia?.matches ?? true)
const showMobileDiagnostics = ref(false)
function onDesktopChange(event: MediaQueryListEvent): void {
  isDesktop.value = event.matches
  if (event.matches) showMobileDiagnostics.value = false
}

onMounted(() => {
  desktopMedia?.addEventListener('change', onDesktopChange)
  void loadDictionaries().then(() => loadContext())
})
onBeforeUnmount(() => {
  resetSession()
  desktopMedia?.removeEventListener('change', onDesktopChange)
})

function nowText(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

// ── SSE 事件处理 ────────────────────────────────────────────────────────────
function applyEvent(event: TestSSEEvent, assistant: TestChatMessage): void {
  pushLocalEvent(event)
  const payload = event.payload
  switch (event.type) {
    case 'reasoning_visible':
      // 可见思考独立流：增量拼进同一连续文本（按片段分行会导致逐字竖排），不与正文混排。
      assistant.thinking += String(payload.text ?? '')
      break
    case 'answer_delta':
      assistant.answer += String(payload.text ?? '')
      break
    case 'usage': {
      const input = typeof payload.input_tokens === 'number' ? payload.input_tokens : null
      const output = typeof payload.output_tokens === 'number' ? payload.output_tokens : null
      assistant.usage = {
        inputTokens: input, outputTokens: output,
        quality: payload.quality === 'actual' ? 'actual' : 'estimated',
        firstTokenMs: typeof payload.first_token_ms === 'number' ? payload.first_token_ms : null,
        totalMs: typeof payload.total_ms === 'number' ? payload.total_ms : null,
      }
      break
    }
    case 'error':
      assistant.error = {
        code: String(payload.code ?? 'request_failed'),
        message: String(payload.message ?? '调用失败'),
        retryAfterSeconds: typeof payload.retry_after_seconds === 'number' ? payload.retry_after_seconds : null,
      }
      assistant.status = 'failed'
      generationCell.state = 'fail'
      generationCell.hint = `${assistant.error.code}: ${assistant.error.message}`
      if (payload.stage === 'provider_response') providerCell.state = 'ok'
      break
    case 'status':
      if (payload.stage === 'provider_connect') {
        providerCell.state = 'ok'
        providerCell.hint = undefined
      }
      if (payload.stage === 'cancelled') {
        // 用户停止：保留已收到内容，状态标「已中止」（不伪装完成）。
        assistant.status = 'aborted'
        assistant.finishReason = 'aborted'
        generationCell.state = 'warn'
        generationCell.hint = '已中止：已收用量按估算入账待核对'
      }
      break
    case 'done':
      if (assistant.status === 'streaming') {
        assistant.status = payload.outcome === 'failed' ? 'failed' : 'done'
      }
      assistant.finishReason = String(payload.finish_reason ?? assistant.finishReason ?? '')
      if (payload.provider_not_called) {
        providerCell.state = 'warn'
      }
      // 遥测闭环：成功完结翻转 GENERATION=ok；兜底 failed（无前置 error 事件时）置 fail。
      if (assistant.status === 'done') {
        generationCell.state = 'ok'
        generationCell.hint = undefined
      } else if (assistant.status === 'failed' && generationCell.state === 'pending') {
        generationCell.state = 'fail'
        generationCell.hint = '调用未成功完结，详见消息错误横幅'
      }
      break
    default:
      break
  }
  // 事件落地：数组替换驱动消息区重渲染；tick 驱动诊断 computed 失效（见 diagnosticTick 注）。
  messages.value = [...messages.value]
  diagnosticTick.value += 1
}

/** 订阅事件流；done 或错误终止。返回是否正常完结。 */
async function consumeEvents(assistant: TestChatMessage, activeModelId: string, epoch: number, lastSequence: number, allowRetry: boolean): Promise<boolean> {
  if (!assistant.conversationId) return false
  let cursor = lastSequence
  const controller = new AbortController()
  streamAbort = controller
  try {
    await streamConversationEvents(activeModelId, assistant.conversationId, {
      lastSequence,
      signal: controller.signal,
      onEvent: (event) => {
        if (epoch !== sessionEpoch) return
        if (event.sequence <= cursor) return
        cursor = event.sequence
        applyEvent(event, assistant)
      },
    })
    return assistant.status !== 'streaming'
  } catch {
    if (controller.signal.aborted || epoch !== sessionEpoch) return true
    // 断线重连一次：Last-Event-ID 语义，服务端按 sequence 去重续传。
    if (allowRetry && assistant.status === 'streaming') {
      message.warning('事件流中断，正在按最后序号重连续传…')
      return await consumeEvents(assistant, activeModelId, epoch, cursor, false)
    }
    if (assistant.status === 'streaming') {
      // 重连后仍失败：已收内容如实保留，标记为「流中断」未完成（用量待核对）。
      assistant.status = 'aborted'
      assistant.finishReason = 'stream_disconnected'
      assistant.error = { code: 'stream_disconnected', message: '事件流中断且重连失败，已收内容保留；用量进入待核对' }
      generationCell.state = 'warn'
      generationCell.hint = '流中断：用量待核对'
      messages.value = [...messages.value]
    }
    return false
  } finally {
    // 连接释放由 streamConversationEvents 在 done 时 cancel 完成；这里仅清理引用，
    // 不再 abort（正常完结用 abort 会在控制台产生 net::ERR_ABORTED 噪音）。
    if (streamAbort === controller) streamAbort = null
  }
}

// ── 动作 ────────────────────────────────────────────────────────────────────
/** 仅将已成功完成的轮次带入下一次请求；保留最近 10 轮，且不超过服务端字符上限。 */
function buildHistory(source: TestChatMessage[]): ConversationHistoryTurn[] {
  const pairs: [ConversationHistoryTurn, ConversationHistoryTurn][] = []
  for (let index = 0; index < source.length - 1; index += 1) {
    const user = source[index]
    const assistant = source[index + 1]
    if (user.role === 'user' && assistant.role === 'assistant' && assistant.status === 'done' && assistant.answer.trim()) {
      pairs.push([{ role: 'user', content: user.text }, { role: 'assistant', content: assistant.answer }])
    }
  }
  const selected: typeof pairs = []
  let length = 0
  for (const pair of pairs.slice(-10).reverse()) {
    const pairLength = pair[0].content.length + pair[1].content.length
    if (length + pairLength > 32000) break
    selected.unshift(pair)
    length += pairLength
  }
  return selected.flat()
}

const contextTurnCount = computed(() => buildHistory(messages.value).length / 2)

/** 发送消息：创建会话（服务端重验判权）→ 订阅 SSE 事件流渲染流式回复。 */
async function sendMessage(text: string): Promise<void> {
  if (sendDisabledReason.value || !text || sending.value) return
  const epoch = sessionEpoch
  const activeModelId = modelId.value
  const activeApplicationId = applicationId.value
  const history = buildHistory(messages.value)
  const activeParams = { ...params.value }
  const userMessage: TestChatMessage = {
    id: `u-${Date.now()}`, role: 'user', text, thinking: '', answer: '', status: 'done', createdAt: Date.now(),
  }
  const assistant: TestChatMessage = {
    id: `a-${Date.now()}`, role: 'assistant', text: '', thinking: '', answer: '', status: 'streaming', createdAt: Date.now(),
  }
  messages.value.push(userMessage, assistant)
  messages.value = [...messages.value]
  sending.value = true
  providerCell.state = 'pending'
  providerCell.hint = undefined
  generationCell.state = 'pending'
  generationCell.hint = undefined
  try {
    const start = await startConversation(activeModelId, activeApplicationId, text, history, activeParams)
    if (epoch !== sessionEpoch) {
      void cancelConversation(activeModelId, start.conversation_id).catch(() => undefined)
      return
    }
    assistant.requestId = start.request_id
    assistant.conversationId = start.conversation_id
    streamConversationId = start.conversation_id
    streamModelId = activeModelId
    messages.value = [...messages.value]
    await consumeEvents(assistant, activeModelId, epoch, 0, true)
  } catch (error) {
    if (epoch !== sessionEpoch) return
    // 创建阶段失败：403=授权不可用（外呼前拦截）/ 404=模型或应用不存在 / 其他=请求失败。
    const reason = error instanceof Error ? error.message : '请求失败'
    assistant.error = { code: reason.includes('授权不可用') ? 'authz_denied' : 'request_failed', message: reason }
    assistant.status = 'failed'
    generationCell.state = 'fail'
    generationCell.hint = reason
    messages.value = [...messages.value]
  } finally {
    if (epoch === sessionEpoch) {
      // 流生命周期兜底：正常路径 done 事件已置终态；若因任何异常路径（done 帧丢失 /
      // 流静默关闭未被识别）仍处 streaming，这里如实标记「已中止」，防止卡死的
      // 「生成中」幽灵消息永久污染诊断 Tab（思考/用量）与轮次展示。
      if (assistant.status === 'streaming') {
        assistant.status = 'aborted'
        assistant.finishReason = 'stream_disconnected'
        assistant.error = { code: 'stream_disconnected', message: '事件流未正常完结，已收内容保留；用量进入待核对' }
        generationCell.state = 'warn'
        generationCell.hint = '流中断：用量待核对'
        messages.value = [...messages.value]
      }
      streamConversationId = ''
      streamModelId = ''
      sending.value = false
      lastTestedAt.value = nowText()
    }
  }
}

/** 停止生成：服务端中断流并按已收用量如实落账；本地等 done 事件确认。 */
async function stopGeneration(): Promise<void> {
  if (!streamConversationId || !streamModelId) return
  try {
    await cancelConversation(streamModelId, streamConversationId)
    message.success('已发送停止请求；已收内容保留，用量按实际情况结算')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '停止请求失败')
  }
}

/** 连接探针：分阶段真实结果（凭据解析→网络/TLS→Provider 响应）。 */
async function runProbe(): Promise<void> {
  if (!modelId.value || probeRunning.value) return
  const epoch = sessionEpoch
  const activeModelId = modelId.value
  probeRunning.value = true
  const probeMessage: TestChatMessage = {
    id: `p-${Date.now()}`, role: 'probe', text: '', thinking: '', answer: '', status: 'done', createdAt: Date.now(),
    probe: {
      pending: true,
      report: { test_id: '—', request_id: '—', stages: [], verdict: 'ok', error: null },
    },
  }
  messages.value.push(probeMessage)
  messages.value = [...messages.value]
  try {
    const report = await probeConnection(activeModelId)
    if (epoch !== sessionEpoch) return
    probeMessage.probe = { pending: false, report }
    providerCell.state = report.verdict === 'ok' ? 'ok' : 'warn'
    providerCell.hint = report.error ? `${report.error.message}` : undefined
  } catch (error) {
    if (epoch !== sessionEpoch) return
    probeMessage.probe = {
      pending: false,
      report: {
        test_id: '—', request_id: '—', stages: [], verdict: 'fail',
        error: { code: 'request_failed', message: error instanceof Error ? error.message : '探针执行失败', stage: 'gateway' },
      },
    }
    providerCell.state = 'warn'
    providerCell.hint = probeMessage.probe.report.error?.message
  } finally {
    if (epoch === sessionEpoch) {
      probeRunning.value = false
      lastTestedAt.value = nowText()
      messages.value = [...messages.value]
    }
  }
}

/** 清空会话：二次确认（设计文档 §3.1 危险操作确认口径）。 */
function clearSession(): void {
  if (sending.value || probeRunning.value || !messages.value.length) return
  Modal.confirm({
    title: '清空会话？',
    content: '当前会话仅存于浏览器内存，清空后不可恢复；诊断事件将一并清除。',
    okText: '清空', cancelText: '取消', okButtonProps: { danger: true },
    onOk: () => {
      if (sending.value || probeRunning.value) return
      resetSession()
      message.success('会话已清空')
    },
  })
}

/** 编辑重发：从该轮截断后续上下文后重发（界面已先提示截断语义）。 */
function resendFrom(index: number, text: string): void {
  if (sending.value || probeRunning.value || messages.value[index]?.role !== 'user') return
  messages.value = messages.value.slice(0, index)
  void sendMessage(text)
}

function regenerateFrom(index: number): void {
  const user = messages.value[index - 1]
  if (user?.role === 'user') resendFrom(index - 1, user.text)
}

/** 应用调试参数：提交后作用于下一次发送（对话区摘要即时刷新）。 */
function applyParams(next: DebugParams): void {
  params.value = next
  message.success('参数已应用，将作用于下一次发送')
}
</script>

<template>
  <!-- lg+ 视口锁定：本页内部双列各自滚动，外壳不滚；窄屏降级为页面滚动 + 面板固定高度 -->
  <div class="flex min-h-0 flex-1 flex-col gap-3 lg:shrink lg:overflow-hidden max-lg:overflow-y-auto">
    <AdminPageHeader
      class="!mb-2"
      eyebrow="平台治理 · 模型治理"
      title="模型测试台"
      subtitle="在指定应用中验证模型，连续对话并查看每次请求的诊断结果。"
    />

    <!-- 权限守卫：测试台现行边界 = 超管范围 + button.models.manage（与后端逐请求判权一致） -->
    <div v-if="!canManage" class="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-2 shadow-[var(--shadow-sm)]">
      <AdminEmpty
        emoji="🔒"
        description="模型测试台需要超管范围与 button.models.manage 管理权限；按钮隐藏不替代后端逐请求判权"
      />
    </div>

    <template v-else>
      <!-- 工作区：顶部紧凑工具条（身份/探针/上下文/操作）+ 可拖拽分栏 -->
      <div class="flex min-h-0 flex-1 flex-col gap-3">
        <!-- 工作台工具条：模型身份、当前范围与操作集中在一处。 -->
        <div class="shrink-0 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
          <div class="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3">
            <template v-if="selectedModel">
              <div class="flex min-w-0 items-center gap-3">
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-tech-accent-subtle)] font-mono text-xs font-semibold text-[var(--color-tech-accent)]">{{ selectedModel.display_name.slice(0, 2).toUpperCase() }}</span>
                <div class="min-w-0">
                  <p class="m-0 truncate text-sm font-semibold leading-tight text-[var(--color-text-primary)]">{{ selectedModel.display_name }}</p>
                  <p class="m-0 mt-1 truncate font-mono text-[11px] leading-4 text-[var(--color-text-muted)]">{{ selectedModel.key }}</p>
                </div>
              </div>
              <span class="hidden h-7 w-px bg-[var(--color-border)] lg:block" aria-hidden="true" />
              <div class="hidden items-center gap-1.5 lg:flex">
                <span class="h-2 w-2 rounded-full" :class="selectedModel.status === 'active' ? 'bg-[var(--color-success)]' : 'bg-[var(--color-error)]'" aria-hidden="true" />
                <span class="text-xs text-[var(--color-text-secondary)]">{{ selectedModel.status === 'active' ? '已启用' : '已停用' }}</span>
              </div>
              <div class="hidden items-center gap-1.5 lg:flex">
                <span class="h-2 w-2 rounded-full" :class="selectedModel.credential_configured ? 'bg-[var(--color-success)]' : 'bg-[var(--color-error)]'" aria-hidden="true" />
                <span class="text-xs text-[var(--color-text-secondary)]">{{ selectedModel.credential_configured ? '凭据已配置' : '凭据未配置' }}</span>
              </div>
              <span v-if="lastTestedAt" class="hidden text-xs text-[var(--color-text-muted)] xl:inline">最近测试 {{ lastTestedAt }}</span>
              <!-- 连接测试：独立于对话生成的轻量探针。 -->
              <a-tooltip title="服务端固定短探针：凭据解析 → 网络/TLS → Provider 响应（GET /models），不产生计费 token">
                <button
                  type="button"
                  class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md border border-[var(--color-border-strong)] px-3 text-xs font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-tech-accent)] hover:text-[var(--color-tech-accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-tech-accent)] disabled:cursor-not-allowed disabled:opacity-40"
                  :disabled="probeDisabled"
                  @click="runProbe"
                >
                  <ThunderboltOutlined :spin="probeRunning" />
                  {{ probeRunning ? '测试中…' : '连接测试' }}
                </button>
              </a-tooltip>
            </template>
            <!-- 未选模型占位：与选中态同构（40px 图标位 + 主/副两行），避免高度跳动；
                 引导收敛为一句短话，长说明放 tooltip -->
            <div v-else class="flex min-w-0 items-center gap-3">
              <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-md)] border border-dashed border-[var(--color-border-strong)] text-sm text-[var(--color-text-muted)]" aria-hidden="true">
                <ExperimentOutlined />
              </span>
              <div class="min-w-0">
                <p class="m-0 text-sm font-semibold leading-tight text-[var(--color-text-secondary)]">未选择模型</p>
                <a-tooltip title="可从模型治理目录行操作进入；或在右侧「测试范围」中选择模型、租户与应用">
                  <p class="m-0 mt-1 cursor-help truncate text-[11px] leading-4 text-[var(--color-text-muted)]">在右侧「测试范围」中选择模型</p>
                </a-tooltip>
              </div>
            </div>

            <!-- 右侧操作组：清空 / 调试（测试范围选择已移入右栏统一卡） -->
            <div class="ml-auto flex flex-wrap items-center gap-2">
              <button type="button" class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] px-3 text-xs text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-tech-accent)] hover:text-[var(--color-tech-accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-tech-accent)] disabled:cursor-not-allowed disabled:opacity-40" :disabled="sending || probeRunning || !messages.length" @click="clearSession">
                <ClearOutlined />
                清空
              </button>
              <button type="button" class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] px-3 text-xs text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-tech-accent)] hover:text-[var(--color-tech-accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-tech-accent)]" @click="drawerOpen = true">
                <SettingOutlined />
                调试
              </button>
            </div>
          </div>
        </div>

        <!-- 工作区分栏：lg+ Splitpanes 可拖拽（左对话最大化 / 右信息面板），窄屏纵向堆叠 -->
        <!-- splitter 常显竖向拖拽把手（用户标注「拖拽不明」）：14px 热区 + 居中胶囊 grip，hover 展高转科技蓝，拖拽中保持高亮。
             选择器用 [role=separator] 而非 .splitpanes__splitter：Tailwind 任意变体把 _ 转空格，__ 会生成死选择器；
             仅 min-w 需后缀 ! 压过 splitpanes.css 的 min-width:1px -->
        <Splitpanes
          v-if="isDesktop"
          class="test-splitpanes min-h-0 flex-1 [&_[role=separator]]:relative [&_[role=separator]]:shrink-0 [&_[role=separator]]:w-[14px] [&_[role=separator]]:min-w-[14px]! [&_[role=separator]]:cursor-col-resize [&_[role=separator]]:before:content-[''] [&_[role=separator]]:before:absolute [&_[role=separator]]:before:left-1/2 [&_[role=separator]]:before:top-1/2 [&_[role=separator]]:before:h-10 [&_[role=separator]]:before:w-1 [&_[role=separator]]:before:-translate-x-1/2 [&_[role=separator]]:before:-translate-y-1/2 [&_[role=separator]]:before:rounded-full [&_[role=separator]]:before:bg-[var(--color-border-strong)] [&_[role=separator]]:before:transition-[height,background-color] [&_[role=separator]:hover]:bg-[var(--color-tech-accent-subtle)] [&_[role=separator]:hover]:before:h-14 [&_[role=separator]:hover]:before:bg-[var(--color-tech-accent)] [&.splitpanes--dragging_[role=separator]]:before:bg-[var(--color-tech-accent)]"
        >
          <Pane :size="64" :min="38">
            <ChatColumn
              :mode="mode"
              :selected-model="selectedModel"
              :messages="messages"
              :send-disabled-reason="sendDisabledReason"
              :sending="sending"
              :streaming="streaming"
              :context-turn-count="contextTurnCount"
              @send="sendMessage"
              @stop="stopGeneration"
              @resend="resendFrom"
              @regenerate="regenerateFrom"
            />
          </Pane>
          <Pane :size="36" :min="26" :max="62">
            <TestSidePanel
              v-model:mode="mode"
              v-model:model-id="modelId"
              v-model:tenant-id="tenantId"
              v-model:application-id="applicationId"
              v-model:tab="diagnosticTab"
              :models="models"
              :tenants="tenants"
              :applications="applications"
              :config="configCell"
              :auth="authCell"
              :provider="providerCell"
              :generation="generationCell"
              :events="events"
              :thinking-text="thinkingText"
              :thinking-reason="thinkingReason || 'Provider 未提供'"
              :thinking-detail="thinkingDetail"
              :usage="usageSnapshot"
              :params-summary="paramsSummary"
            />
          </Pane>
        </Splitpanes>

        <!-- 窄屏降级：固定高度纵向堆叠（shrink-0 保持固定高，滚动交给页面级容器） -->
        <div v-else class="flex shrink-0 flex-col gap-3">
          <ChatColumn
            class="h-[440px] sm:h-[560px]"
            :mode="mode"
            :selected-model="selectedModel"
            :messages="messages"
            :send-disabled-reason="sendDisabledReason"
            :sending="sending"
            :streaming="streaming"
            :context-turn-count="contextTurnCount"
            @send="sendMessage"
            @stop="stopGeneration"
            @resend="resendFrom"
            @regenerate="regenerateFrom"
          />
          <button
            type="button"
            class="flex h-10 w-full items-center justify-between rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 text-xs font-medium text-[var(--color-text-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-tech-accent)]"
            :aria-expanded="showMobileDiagnostics"
            @click="showMobileDiagnostics = !showMobileDiagnostics"
          >
            <span>{{ showMobileDiagnostics ? '收起范围与诊断' : '展开测试范围与诊断' }}</span>
            <DownOutlined :class="showMobileDiagnostics ? 'rotate-180' : ''" aria-hidden="true" />
          </button>
          <TestSidePanel
            v-if="showMobileDiagnostics"
            v-model:mode="mode"
            v-model:model-id="modelId"
            v-model:tenant-id="tenantId"
            v-model:application-id="applicationId"
            v-model:tab="diagnosticTab"
            class="h-[520px]"
            :models="models"
            :tenants="tenants"
            :applications="applications"
            :config="configCell"
            :auth="authCell"
            :provider="providerCell"
            :generation="generationCell"
            :events="events"
            :thinking-text="thinkingText"
            :thinking-reason="thinkingReason || 'Provider 未提供'"
            :thinking-detail="thinkingDetail"
            :usage="usageSnapshot"
            :params-summary="paramsSummary"
          />
        </div>
      </div>
    </template>

    <!-- 调试设置抽屉：按目录能力逐项开放；关闭重置未提交修改 -->
    <DebugDrawer
      v-model:open="drawerOpen"
      :params="params"
      @apply="applyParams"
    />
  </div>
</template>
