<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api, ApiRequestError } from '@/api'
import { cachedHasAny, getCachedCapabilities } from '@/api/capabilities'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminTableToolbar from '@/components/AdminTableToolbar.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
// P369：复用概览账本指标卡（clickable=false 纯展示态），统一「编号 + 巨号数字」设计语言。
import OverviewStatCard from '@/views/overview/components/OverviewStatCard.vue'
// P400：用量趋势与模型分布图表（echarts 复用概览基建），数据来自新增的同口径聚合端点。
import ModelUsageCharts from './components/ModelUsageCharts.vue'
import type { UsageModelAggregate, UsageTimelinePoint } from './components/ModelUsageCharts.vue'

type View = 'catalog' | 'usage'
interface Tenant { id: string; name: string; status: string }
interface ModelRecord {
  id: string; tenant_id: string; key: string; provider: string; model_name: string; display_name: string
  endpoint_url?: string | null; credential_configured: boolean; capabilities: string[]
  rpm_limit?: number | null; tpm_limit?: number | null; input_cost_per_million?: number | null
  output_cost_per_million?: number | null; quota_status: 'enforced' | 'configured_only' | 'unlimited'
  status: 'active' | 'disabled'; created_at?: string
}
interface UsageEvent {
  id: string; request_id: string; tenant_id: string; model_name: string; application_name: string
  user_email: string; input_tokens: number; output_tokens: number; estimated_cost?: string | null
  outcome: 'succeeded' | 'failed'; source: 'gateway' | 'admin_reconciliation'
  usage_is_estimated: boolean; latency_ms: number | null; created_at: string
}
interface UsageEventPage { items: UsageEvent[]; total: number; limit: number; offset: number }
interface UsageReview {
  request_id: string; tenant_id: string; model_name: string; application_name: string
  user_email: string; reserved_input_tokens: number; reserved_output_tokens: number
  created_at: string; expires_at: string; waiting_minutes: number
}
interface UsageReviewPage { items: UsageReview[]; total: number; limit: number; offset: number }
interface UsageSummary {
  requests: number; succeeded: number; failed: number; input_tokens: number; output_tokens: number
  estimated_cost: string | null; unknown_cost_requests: number; estimated_usage_requests: number
}

const props = defineProps<{ active: boolean; view: View; seedTenants?: Tenant[] }>()
// 页内写按钮认 button.models.manage，过渡期 any-of 接口码 / L1。
const canManageModels = computed(() =>
  getCachedCapabilities()?.platform_admin === true
  || cachedHasAny(['button.models.manage']))
const USAGE_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/
const OUTCOME_FILTER_OPTIONS = [
  { value: 'succeeded', label: '成功' },
  { value: 'failed', label: '失败' },
]

const tenants = ref<Tenant[]>([])
const tenantId = ref<string>()
const outcomeFilter = ref<'succeeded' | 'failed'>()
const modelFilter = ref<string>()
const createdFrom = ref('')
const createdTo = ref('')
const appliedCreatedFrom = ref('')
const appliedCreatedTo = ref('')
const usageDateError = ref('')
const catalogModels = ref<ModelRecord[]>([])
const models = ref<ModelRecord[]>([])
const events = ref<UsageEvent[]>([])
const usageEventTotal = ref(0)
const usageEventPage = ref(1)
const usageEventPageSize = ref(10)
const reviews = ref<UsageReview[]>([])
const reviewTotal = ref(0)
const reviewPage = ref(1)
const reviewPageSize = ref(10)
const summary = ref<UsageSummary>(emptyUsageSummary())
// P400：聚合图表数据；失败时保留旧图（stale-but-visible），由 chartsLoadFailed 提示可能过期。
const timeline = ref<UsageTimelinePoint[] | null>(null)
const byModel = ref<UsageModelAggregate[] | null>(null)
const chartsLoadFailed = ref(false)
const usageDataLoaded = ref(false)
const usageLoadError = ref('')
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const editingId = ref<string | null>(null)
const clearCredentialRef = ref(false)
const reviewOpen = ref(false)
const reviewing = ref(false)
const reviewTarget = ref<UsageReview | null>(null)
const reviewForm = reactive({
  decision: 'settle' as 'settle' | 'release', reason: '', input_tokens: 0,
  output_tokens: 0, outcome: 'succeeded' as 'succeeded' | 'failed',
  usage_is_estimated: true, latency_ms: null as number | null, provider_not_called: false,
})
const requestSequence = ref(0)
const form = reactive({
  tenant_id: '', key: '', provider: '', model_name: '', display_name: '', endpoint_url: '', credential_ref: '',
  capabilities: 'chat', rpm_limit: null as number | null, tpm_limit: null as number | null,
  input_cost_per_million: null as number | null, output_cost_per_million: null as number | null,
})

function emptyUsageSummary(): UsageSummary {
  return { requests: 0, succeeded: 0, failed: 0, input_tokens: 0, output_tokens: 0, estimated_cost: null, unknown_cost_requests: 0, estimated_usage_requests: 0 }
}

// 后端 Decimal 序列化可能输出科学计数法（如 0E-8、1.5E-7）；统一转为普通小数并去掉尾随零。
function formatCostValue(value: string): string {
  if (!/^-?\d+(\.\d+)?E-?\d+$/i.test(value)) return value
  return Number(value).toFixed(8).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '') || '0'
}

const title = computed(() => props.view === 'catalog' ? '模型管理' : '模型用量')
const modelFilterOptions = computed(() => catalogModels.value.map(model => ({
  value: model.id,
  label: model.display_name,
})))
const estimatedCostSummary = computed(() => {
  if (summary.value.requests === 0) return '暂无用量'
  return summary.value.estimated_cost === null ? '费用未知' : formatCostValue(summary.value.estimated_cost)
})
// P369：账本式汇总指标卡（对齐 P368 概览 01–05），大数千分位格式化；数据未加载时统一显示占位符。
const usageMetricCards = computed(() => {
  const loaded = usageDataLoaded.value
  const count = (value: number): number | string => (loaded ? value.toLocaleString('zh-CN') : '—')
  return [
    { index: '01', label: '请求总数', value: count(summary.value.requests) },
    { index: '02', label: '成功率', value: loaded && summary.value.requests > 0 ? `${(summary.value.succeeded / summary.value.requests * 100).toFixed(1)}%` : '—' },
    { index: '03', label: '输入 Token', value: count(summary.value.input_tokens) },
    { index: '04', label: '输出 Token', value: count(summary.value.output_tokens) },
    { index: '05', label: '估算费用', value: loaded ? estimatedCostSummary.value : '—' },
  ]
})
// 次级审计指标（成功/失败绝对数、估算与未知费用计数）收进脚注行，保证指标卡单行 5 张与概览一致。
const usageAuditFootnote = computed(() => {
  const count = (value: number): string => value.toLocaleString('zh-CN')
  return `成功 ${count(summary.value.succeeded)} · 失败 ${count(summary.value.failed)} · 估算用量请求 ${count(summary.value.estimated_usage_requests)} · 未知费用请求 ${count(summary.value.unknown_cost_requests)}`
})

const modelColumns = [
  // 15 列宽表以横向滚动为合理形态；此轮仅压缩明显虚胖列（2120→1784），减少滚动量
  { title: '模型', dataIndex: 'display_name', key: 'display_name', width: 160, ellipsis: true },
  { title: '租户', dataIndex: 'tenant_id', key: 'tenant_id', width: 140, ellipsis: true },
  { title: '模型标识', dataIndex: 'key', key: 'key', width: 130, ellipsis: true },
  { title: '提供方', dataIndex: 'provider', key: 'provider', width: 120 },
  { title: '模型名称', dataIndex: 'model_name', key: 'model_name', width: 140, ellipsis: true },
  { title: '端点', dataIndex: 'endpoint_url', key: 'endpoint_url', width: 170, ellipsis: true },
  { title: '能力', dataIndex: 'capabilities', key: 'capabilities', width: 110, ellipsis: true },
  { title: '凭证引用', dataIndex: 'credential_configured', key: 'credential_configured', width: 96 },
  { title: 'RPM', dataIndex: 'rpm_limit', key: 'rpm_limit', width: 80 },
  { title: 'TPM', dataIndex: 'tpm_limit', key: 'tpm_limit', width: 80 },
  { title: '输入价格/百万', dataIndex: 'input_cost_per_million', key: 'input_cost_per_million', width: 110 },
  { title: '输出价格/百万', dataIndex: 'output_cost_per_million', key: 'output_cost_per_million', width: 110 },
  { title: '限额执行', dataIndex: 'quota_status', key: 'quota_status', width: 110, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 88 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 140, fixed: 'right' as const },
]
const usageColumns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 150, ellipsis: true },
  { title: '应用', dataIndex: 'application_name', key: 'application_name', width: 140, ellipsis: true },
  { title: '用户', dataIndex: 'user_email', key: 'user_email', width: 170, ellipsis: true },
  { title: '输入 Token', dataIndex: 'input_tokens', key: 'input_tokens', width: 110, align: 'right' as const },
  { title: '输出 Token', dataIndex: 'output_tokens', key: 'output_tokens', width: 110, align: 'right' as const },
  { title: '记录来源', dataIndex: 'source', key: 'source', width: 110 },
  { title: '计量方式', dataIndex: 'usage_is_estimated', key: 'usage_is_estimated', width: 100 },
  { title: '估算费用', dataIndex: 'estimated_cost', key: 'estimated_cost', width: 110, align: 'right' as const },
  { title: '结果', dataIndex: 'outcome', key: 'outcome', width: 90 },
  { title: '延迟（毫秒）', dataIndex: 'latency_ms', key: 'latency_ms', width: 110, align: 'right' as const },
  { title: '网关请求 ID', dataIndex: 'request_id', key: 'request_id', width: 180, ellipsis: true },
]
const reviewColumns = [
  { title: '过期时间', dataIndex: 'expires_at', key: 'expires_at', width: 180 },
  { title: '等待核对', dataIndex: 'waiting_minutes', key: 'waiting_minutes', width: 110, align: 'right' as const },
  { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 170 },
  { title: '应用', dataIndex: 'application_name', key: 'application_name', width: 160 },
  { title: '用户', dataIndex: 'user_email', key: 'user_email', width: 190 },
  { title: '预留输入', dataIndex: 'reserved_input_tokens', key: 'reserved_input_tokens', width: 110, align: 'right' as const },
  { title: '预留输出', dataIndex: 'reserved_output_tokens', key: 'reserved_output_tokens', width: 110, align: 'right' as const },
  { title: '请求 ID', dataIndex: 'request_id', key: 'request_id', width: 210 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 110, fixed: 'right' as const },
]
// Keep each table viewport at least as wide as the sum of its configured columns.
const modelTableScrollWidth = modelColumns.reduce((width, column) => width + column.width, 0)
const usageTableScrollWidth = usageColumns.reduce((width, column) => width + column.width, 0)
const reviewTableScrollWidth = reviewColumns.reduce((width, column) => width + column.width, 0)

function tenantName(id: string): string {
  return tenants.value.find(tenant => tenant.id === id)?.name || '未知租户'
}

function changeReviewPage(pagination: { current?: number; pageSize?: number }): void {
  const nextPageSize = Math.min(Math.max(pagination.pageSize ?? reviewPageSize.value, 1), 200)
  if (nextPageSize !== reviewPageSize.value) {
    reviewPageSize.value = nextPageSize
    reviewPage.value = 1
  } else {
    reviewPage.value = pagination.current ?? 1
  }
  reviews.value = []
  reviewTotal.value = 0
  void load()
}

function reviewTotalText(total: number): string {
  return `共 ${total} 条待核对调用`
}

function usageEventTotalText(total: number): string {
  return `共 ${total} 条模型调用账目`
}

function appendLedgerFilters(params: URLSearchParams): void {
  if (tenantId.value) params.set('tenant_id', tenantId.value)
  if (modelFilter.value) params.set('model_id', modelFilter.value)
  if (outcomeFilter.value === 'succeeded' || outcomeFilter.value === 'failed') {
    params.set('outcome', outcomeFilter.value)
  }
  if (appliedCreatedFrom.value) params.set('created_from', appliedCreatedFrom.value)
  if (appliedCreatedTo.value) params.set('created_to', appliedCreatedTo.value)
}

function isCompleteUtcDate(value: string): boolean {
  if (!USAGE_DATE_PATTERN.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const parsed = new Date(Date.UTC(year, month - 1, day))
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day
}

function commitUsageDates(): void {
  const from = (createdFrom.value || '').trim()
  const to = (createdTo.value || '').trim()
  const drafts = [from, to]
  // 未输完时不请求，也不把半截日期当成错误。
  if (drafts.some(value => value && (value.length < 10 || !USAGE_DATE_PATTERN.test(value)))) {
    usageDateError.value = ''
    return
  }
  if (drafts.some(value => value && !isCompleteUtcDate(value))) {
    usageDateError.value = '日期请使用有效的 YYYY-MM-DD'
    return
  }
  if (from && to && from > to) {
    usageDateError.value = '开始日期不能晚于结束日期'
    return
  }
  usageDateError.value = ''
  if (from === appliedCreatedFrom.value && to === appliedCreatedTo.value) return
  appliedCreatedFrom.value = from
  appliedCreatedTo.value = to
}

function changeUsageEventPage(pagination: { current?: number; pageSize?: number }): void {
  const nextPageSize = Math.min(Math.max(pagination.pageSize ?? usageEventPageSize.value, 1), 200)
  if (nextPageSize !== usageEventPageSize.value) {
    usageEventPageSize.value = nextPageSize
    usageEventPage.value = 1
  } else {
    usageEventPage.value = pagination.current ?? 1
  }
  events.value = []
  usageEventTotal.value = 0
  void load()
}

async function load(): Promise<void> {
  const sequence = ++requestSequence.value
  loading.value = true
  if (props.view === 'usage') usageLoadError.value = ''
  // 租户模式（L2/L3）必须显式锚定租户才能通过后端 ops.model.read 判权，默认选首个可见租户。
  const knownTenants = props.seedTenants?.length ? props.seedTenants : tenants.value
  if (!tenantId.value && knownTenants.length) tenantId.value = knownTenants[0].id
  const tenantQuery = tenantId.value ? `?tenant_id=${encodeURIComponent(tenantId.value)}` : ''
  // seedTenants 提供时跳过 /admin/tenants（租户管理员无 platform.tenant.read）。
  const tenantsSource = props.seedTenants?.length
    ? Promise.resolve(props.seedTenants)
    : api<Tenant[]>('/admin/tenants')
  try {
    if (props.view === 'catalog') {
      const [tenantRows, modelRows] = await Promise.all([
        tenantsSource, api<ModelRecord[]>(`/admin/models${tenantQuery}`),
      ])
      if (sequence !== requestSequence.value) return
      tenants.value = tenantRows
      models.value = modelRows
    } else {
      const reviewParams = new URLSearchParams()
      if (tenantId.value) reviewParams.set('tenant_id', tenantId.value)
      reviewParams.set('limit', String(reviewPageSize.value))
      reviewParams.set('offset', String((reviewPage.value - 1) * reviewPageSize.value))
      const eventParams = new URLSearchParams()
      appendLedgerFilters(eventParams)
      eventParams.set('limit', String(usageEventPageSize.value))
      eventParams.set('offset', String((usageEventPage.value - 1) * usageEventPageSize.value))
      const summaryParams = new URLSearchParams()
      appendLedgerFilters(summaryParams)
      const summaryQuery = summaryParams.toString()
      // 模型目录失败不影响账目；保留上一次模型列表，避免筛选框被清空。
      const modelRowsPromise = api<ModelRecord[]>(`/admin/models${tenantQuery}`).catch(() => null)
      // P400：趋势与分布与汇总共用同一套筛选参数（summaryQuery），保证口径一致；
      // 指定模型筛选时分布退化为单柱，直接跳过请求并清空旧图。
      const timelinePromise = api<{ items: UsageTimelinePoint[] }>(`/admin/model-usage/timeline?${summaryQuery}`).catch(() => null)
      const byModelPromise = modelFilter.value
        ? Promise.resolve(null)
        : api<{ items: UsageModelAggregate[] }>(`/admin/model-usage/by-model?${summaryQuery}`).catch(() => null)
      const [tenantRows, eventRows, usageSummary, reviewRows, modelRows, timelineRows, byModelRows] = await Promise.all([
        tenants.value.length ? Promise.resolve(tenants.value) : tenantsSource,
        api<UsageEventPage>(`/admin/model-usage/events?${eventParams.toString()}`),
        api<UsageSummary>(`/admin/model-usage/summary${summaryQuery ? `?${summaryQuery}` : ''}`),
        api<UsageReviewPage>(`/admin/model-usage/reviews?${reviewParams.toString()}`),
        modelRowsPromise,
        timelinePromise,
        byModelPromise,
      ])
      if (sequence !== requestSequence.value) return
      tenants.value = tenantRows
      if (modelRows) {
        catalogModels.value = modelRows
        if (modelFilter.value && !modelRows.some(model => model.id === modelFilter.value)) modelFilter.value = undefined
      }
      events.value = eventRows.items
      usageEventTotal.value = eventRows.total
      summary.value = usageSummary
      reviews.value = reviewRows.items
      reviewTotal.value = reviewRows.total
      // 聚合图请求失败不回滚旧图，只把失败态交给图表区显示「可能过期」提示。
      if (timelineRows) {
        timeline.value = timelineRows.items
        chartsLoadFailed.value = false
      } else {
        chartsLoadFailed.value = true
      }
      if (modelFilter.value) byModel.value = null
      else if (byModelRows) byModel.value = byModelRows.items
      usageDataLoaded.value = true
    }
  } catch (error) {
    if (sequence === requestSequence.value) {
      if (props.view === 'catalog') {
        models.value = []
        message.error(error instanceof Error ? error.message : '读取模型治理数据失败')
      } else {
        // 筛选或租户切换已清掉旧账本时，不能再声称画面上仍是上次成功结果。
        usageLoadError.value = usageDataLoaded.value
          ? '模型用量读取失败。当前数据可能是上次成功结果；请刷新重试。'
          : '模型用量读取失败，请刷新重试。'
      }
    }
  } finally {
    if (sequence === requestSequence.value) loading.value = false
  }
}

function openReview(record: UsageReview): void {
  reviewTarget.value = record
  Object.assign(reviewForm, {
    decision: 'settle', reason: '', input_tokens: record.reserved_input_tokens,
    output_tokens: record.reserved_output_tokens, outcome: 'succeeded',
    usage_is_estimated: true, latency_ms: null, provider_not_called: false,
  })
  reviewOpen.value = true
}

async function resolveReview(): Promise<void> {
  if (!reviewTarget.value || !reviewForm.reason.trim()) {
    message.warning('请填写核对依据')
    return
  }
  if (reviewForm.decision === 'release' && !reviewForm.provider_not_called) {
    message.warning('只有确认 Provider 从未被调用时，才能释放预留')
    return
  }
  reviewing.value = true
  const payload: Record<string, unknown> = {
    request_id: reviewTarget.value.request_id, decision: reviewForm.decision,
    reason: reviewForm.reason.trim(),
    provider_not_called: reviewForm.decision === 'release' && reviewForm.provider_not_called,
  }
  if (reviewForm.decision === 'settle') Object.assign(payload, {
    input_tokens: reviewForm.input_tokens, output_tokens: reviewForm.output_tokens,
    outcome: reviewForm.outcome, usage_is_estimated: reviewForm.usage_is_estimated,
    latency_ms: reviewForm.latency_ms,
  })
  try {
    await api('/admin/model-usage/reviews', { method: 'POST', body: JSON.stringify(payload) })
    message.success(reviewForm.decision === 'settle' ? '用量已核对并入账' : '已确认未调用 Provider，额度已释放')
    reviewOpen.value = false
    if (reviews.value.length === 1 && reviewPage.value > 1) reviewPage.value -= 1
    await load()
  } catch (error) { message.error(error instanceof Error ? error.message : '核对用量失败') }
  finally { reviewing.value = false }
}

function resetForm(): void {
  Object.assign(form, {
    tenant_id: tenantId.value || tenants.value[0]?.id || '', key: '', provider: '', model_name: '', display_name: '',
    endpoint_url: '', credential_ref: '', capabilities: 'chat', rpm_limit: null, tpm_limit: null,
    input_cost_per_million: null, output_cost_per_million: null,
  })
  editingId.value = null
  clearCredentialRef.value = false
}

function createModel(): void {
  resetForm()
  modalOpen.value = true
}

function editModel(record: ModelRecord): void {
  Object.assign(form, {
    tenant_id: record.tenant_id, key: record.key, provider: record.provider, model_name: record.model_name,
    display_name: record.display_name, endpoint_url: record.endpoint_url || '', credential_ref: '',
    capabilities: record.capabilities.join(','), rpm_limit: record.rpm_limit ?? null, tpm_limit: record.tpm_limit ?? null,
    input_cost_per_million: record.input_cost_per_million ?? null, output_cost_per_million: record.output_cost_per_million ?? null,
  })
  editingId.value = record.id
  clearCredentialRef.value = false
  modalOpen.value = true
}

async function saveModel(): Promise<void> {
  if (!form.provider.trim() || !form.model_name.trim() || !form.display_name.trim() || (!editingId.value && (!form.tenant_id || !form.key.trim()))) {
    message.warning('请填写所有必填模型信息')
    return
  }
  saving.value = true
  const isEditing = Boolean(editingId.value)
  const payload: Record<string, unknown> = {
    provider: form.provider.trim(), model_name: form.model_name.trim(), display_name: form.display_name.trim(),
    endpoint_url: form.endpoint_url.trim() || null,
    capabilities: form.capabilities.split(',').map(value => value.trim()).filter(Boolean),
    rpm_limit: form.rpm_limit, tpm_limit: form.tpm_limit,
    input_cost_per_million: form.input_cost_per_million, output_cost_per_million: form.output_cost_per_million,
  }
  if (!isEditing) {
    payload.tenant_id = form.tenant_id
    payload.key = form.key.trim()
    if (form.credential_ref.trim()) payload.credential_ref = form.credential_ref.trim()
  } else if (clearCredentialRef.value) payload.credential_ref = null
  else if (form.credential_ref.trim()) payload.credential_ref = form.credential_ref.trim()
  try {
    await api(isEditing ? `/admin/models/${editingId.value}` : '/admin/models', {
      method: isEditing ? 'PATCH' : 'POST', body: JSON.stringify(payload),
    })
    message.success(isEditing ? '模型已更新' : '模型已创建')
    modalOpen.value = false
    await load()
  } catch (error) { message.error(error instanceof Error ? error.message : '保存模型失败') }
  finally { saving.value = false }
}

function changeStatus(record: ModelRecord): void {
  const status = record.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(`/admin/models/${record.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ expected_status: record.status, status }),
      })
      message.success(status === 'active' ? '模型已启用' : '模型已停用')
      await load()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '更新模型状态失败')
      // 并发冲突时读取最新目录；不要让管理员继续基于过期状态发起切换。
      if (error instanceof ApiRequestError && error.status === 409) await load()
    }
  }
  if (status === 'disabled') Modal.confirm({
    title: '停用模型？', content: `停用“${record.display_name}”后，使用该模型的授权调用会受到影响。`,
    okText: '停用模型', cancelText: '取消', okButtonProps: { danger: true }, onOk: update,
  })
  else void update()
}

// 删除模型目录项（P352）：存在用量账目时后端 409 提示改用停用下线。
function deleteModel(record: ModelRecord): void {
  Modal.confirm({
    title: `删除模型“${record.display_name}”？`,
    content: '将永久删除该模型目录项；存在用量账目时无法删除（需改用停用下线）。此操作不可恢复。',
    okText: '永久删除', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`/admin/models/${record.id}`, { method: 'DELETE' })
        message.success('模型已删除')
        await load()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '删除模型失败')
        if (error instanceof ApiRequestError && error.status === 409) await load()
      }
    },
  })
}

watch([
  () => props.active, () => props.view, tenantId, outcomeFilter, modelFilter, appliedCreatedFrom, appliedCreatedTo,
], ([active], previous) => {
  const tenantChanged = Boolean(previous && tenantId.value !== previous[2])
  const ledgerFilterChanged = Boolean(previous && (
    outcomeFilter.value !== previous[3]
    || modelFilter.value !== previous[4]
    || appliedCreatedFrom.value !== previous[5]
    || appliedCreatedTo.value !== previous[6]
  ))
  if (tenantChanged || ledgerFilterChanged) usageEventPage.value = 1
  if (tenantChanged) {
    reviewPage.value = 1
    // 模型属于租户，切换租户后丢掉上一租户的模型条件。
    if (modelFilter.value) modelFilter.value = undefined
  }
  if (props.view === 'usage' && tenantChanged) {
    events.value = []
    usageEventTotal.value = 0
    reviews.value = []
    reviewTotal.value = 0
    summary.value = emptyUsageSummary()
    // P400：图表跟随租户口径，切租户后清掉上一租户的聚合图数据。
    timeline.value = null
    byModel.value = null
    chartsLoadFailed.value = false
    usageDataLoaded.value = false
    catalogModels.value = []
  } else if (props.view === 'usage' && ledgerFilterChanged) {
    events.value = []
    usageEventTotal.value = 0
    summary.value = emptyUsageSummary()
    // P400：结果/日期筛选同时作用于图表口径，旧聚合随之失效。
    timeline.value = null
    byModel.value = null
    chartsLoadFailed.value = false
    usageDataLoaded.value = false
  }
  if (active) void load()
}, { immediate: true })
</script>

<template>
  <section class="model-governance-page">
    <AdminPageHeader
      eyebrow="MODEL GOVERNANCE"
      :title="title"
      :subtitle="view === 'catalog' ? '维护租户模型目录、外部凭证引用、价格与调用限额。' : '查看可信网关报告的请求量、Token 消耗和费用估算。可按模型、结果和 UTC 日期筛选。'"
    >
      <template #extra>
        <a-button v-if="view === 'catalog' && canManageModels" type="primary" :disabled="!tenants.length" @click="createModel">＋ 新建模型</a-button>
      </template>
    </AdminPageHeader>

    <a-alert v-if="view === 'usage' && usageLoadError" type="error" show-icon :message="usageLoadError" role="alert" />

    <!-- P369：账本式用量汇总，对齐 P368 概览设计语言（编号头 + 5 张巨号指标卡 + 审计脚注）。 -->
    <div v-if="view === 'usage'" class="min-w-0">
      <div class="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">01</span>
          用量汇总
        </h3>
        <p class="mb-0 text-xs text-[var(--color-text-muted)]">统计口径与下方账目筛选一致，不含待核对预留</p>
      </div>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        <OverviewStatCard
          v-for="metric in usageMetricCards"
          :key="metric.label"
          :clickable="false"
          :label="metric.label"
          :value="metric.value"
          :index="metric.index"
        />
      </div>
      <!-- 次级审计指标收进脚注行，指标卡保持单行 5 张与概览一致。 -->
      <p class="mb-0 mt-2 font-mono text-[11px] tracking-wide text-[var(--color-text-muted)]">{{ usageAuditFootnote }}</p>
    </div>

    <!-- P400：02 用量趋势 + 03 模型分布；与汇总共用筛选口径，选中具体模型时隐藏分布卡。 -->
    <ModelUsageCharts
      v-if="view === 'usage'"
      :timeline="timeline"
      :by-model="byModel"
      :loading="loading"
      :load-failed="chartsLoadFailed"
      :show-by-model="!modelFilter"
    />

    <!-- P369：编号头 04 上移到卡片外与概览区块头同构；卡内保留说明、警示与队列表格。 -->
    <div v-if="view === 'usage'" class="flex min-w-0 flex-col">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h3 class="mb-0 flex items-center gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">04</span>
          待核对调用
          <a-badge :count="reviewTotal" :show-zero="false" />
        </h3>
        <a-button :loading="loading" @click="load">刷新核对队列</a-button>
      </div>
      <a-card class="data-card review-card" :bordered="false">
        <!-- P400 降噪：原「灰字说明 + 大黄条」两行堆叠合为一条轻警示，规则只说一遍。 -->
        <a-alert message="超时预留不会自动收费或释放（核对前仍占保守 TPM 额度）；请先对照 Provider 日志——确认从未调用才可释放，无法还原用量时按可核实依据结算并标记为估算。" type="warning" show-icon />
        <a-table v-if="reviews.length > 0" class="review-table" :data-source="reviews" :columns="reviewColumns" :loading="loading" row-key="request_id"
          :scroll="{ x: reviewTableScrollWidth, y: 'calc(100vh - 430px)' }"
          :pagination="{ current: reviewPage, pageSize: reviewPageSize, total: reviewTotal, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'], showTotal: reviewTotalText }"
          @change="changeReviewPage">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'expires_at'">{{ new Date(record.expires_at).toLocaleString() }}</template>
            <template v-else-if="column.key === 'actions'"><a-button v-if="canManageModels" type="primary" size="small" @click="openReview(record)">核对</a-button></template>
          </template>
        </a-table>
        <div v-else-if="loading" class="table-empty-state" role="status">正在加载待核对调用…</div>
        <div v-else-if="usageLoadError" class="table-empty-state" role="alert">暂时无法读取待核对调用，请刷新重试。</div>
        <AdminEmpty v-else class="table-empty-state" emoji="🧾" description="没有待核对调用" />
      </a-card>
    </div>

    <!-- P369：编号头 05（目录视图无汇总/图表/复核区，编号为 01 模型目录）。 -->
    <div class="flex min-w-0 flex-col">
      <div class="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">{{ view === 'usage' ? '05' : '01' }}</span>
          {{ view === 'usage' ? '调用账目' : '模型目录' }}
        </h3>
      </div>
      <a-card class="data-card" :bordered="false">
        <AdminTableToolbar :hint="view === 'catalog' ? '凭证仅保存外部 Secret Manager 引用；RPM/TPM 是否拦截由服务端开关控制。' : `共 ${usageEventTotal} 条模型调用账目，按时间倒序分页。结果、模型和 UTC 日期同时作用于汇总与账目，不筛选待核对队列。`">
          <div class="tenant-filter-control">
            <span class="tenant-filter-label">租户</span>
            <a-select v-model:value="tenantId" class="tenant-filter" aria-label="按租户筛选" placeholder="全部租户" allow-clear
              :options="tenants.map(tenant => ({ value: tenant.id, label: tenant.name }))" />
          </div>
          <template v-if="view === 'usage'">
            <div class="tenant-filter-control">
              <span class="tenant-filter-label">结果</span>
              <a-select v-model:value="outcomeFilter" class="tenant-filter" aria-label="按调用结果筛选" placeholder="全部结果" allow-clear
                :options="OUTCOME_FILTER_OPTIONS" />
            </div>
            <div class="tenant-filter-control">
              <span class="tenant-filter-label">模型</span>
              <a-select v-model:value="modelFilter" class="tenant-filter" aria-label="按模型筛选" placeholder="全部模型" allow-clear
                :options="modelFilterOptions" />
            </div>
            <div class="tenant-filter-control">
              <span class="tenant-filter-label">开始日期</span>
              <a-input v-model:value="createdFrom" class="tenant-filter" :maxlength="10" allow-clear placeholder="YYYY-MM-DD" aria-label="开始日期，UTC" @blur="commitUsageDates" @change="commitUsageDates" />
            </div>
            <div class="tenant-filter-control">
              <span class="tenant-filter-label">结束日期</span>
              <a-input v-model:value="createdTo" class="tenant-filter" :maxlength="10" allow-clear placeholder="YYYY-MM-DD" aria-label="结束日期，UTC" @blur="commitUsageDates" @change="commitUsageDates" />
            </div>
          </template>
          <template #actions>
            <a-button :loading="loading" @click="load">刷新</a-button>
          </template>
        </AdminTableToolbar>
        <p v-if="view === 'usage' && usageDateError" class="m-0 mb-3 text-xs text-red-400" role="alert">{{ usageDateError }}</p>
        <a-table v-if="view === 'catalog'" :data-source="models" :columns="modelColumns" :loading="loading" row-key="id"
          :scroll="{ x: modelTableScrollWidth, y: 'calc(100vh - 430px)' }" :pagination="{ pageSize: 10, showSizeChanger: true }">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'tenant_id'">{{ tenantName(record.tenant_id) }}</template>
            <template v-else-if="column.key === 'capabilities'">{{ record.capabilities.join('、') || '—' }}</template>
            <template v-else-if="column.key === 'credential_configured'"><a-tag>{{ record.credential_configured ? '已配置' : '未配置' }}</a-tag></template>
            <template v-else-if="column.key === 'quota_status'"><a-tag :color="record.quota_status === 'enforced' ? 'orange' : record.quota_status === 'configured_only' ? 'blue' : 'default'">{{ ({ enforced: '已启用拦截', configured_only: '已配置，未拦截', unlimited: '未设置限额' } as Record<string, string>)[record.quota_status] }}</a-tag></template>
            <template v-else-if="column.key === 'status'"><a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag></template>
            <template v-else-if="column.key === 'actions'"><a-space v-if="canManageModels" :size="2"><a-button type="link" size="small" @click="editModel(record)">编辑</a-button><a-button type="link" size="small" @click="changeStatus(record)">{{ record.status === 'active' ? '停用' : '启用' }}</a-button><a-button type="link" size="small" danger @click="deleteModel(record)">删除</a-button></a-space></template>
          </template>
          <template #emptyText><AdminEmpty emoji="🤖" description="暂无模型目录项，可创建模型" /></template>
        </a-table>
        <a-table v-else-if="events.length > 0" :data-source="events" :columns="usageColumns" :loading="loading" row-key="id"
          :scroll="{ x: usageTableScrollWidth, y: 'calc(100vh - 430px)' }"
          :pagination="{ current: usageEventPage, pageSize: usageEventPageSize, total: usageEventTotal, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'], showTotal: usageEventTotalText }"
          @change="changeUsageEventPage">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'created_at'">{{ new Date(record.created_at).toLocaleString() }}</template>
            <template v-else-if="column.key === 'estimated_cost'">{{ record.estimated_cost === null ? '未知' : formatCostValue(record.estimated_cost) }}</template>
            <template v-else-if="column.key === 'source'"><a-tag>{{ record.source === 'admin_reconciliation' ? '管理员核对' : '网关上报' }}</a-tag></template>
            <template v-else-if="column.key === 'usage_is_estimated'"><a-tag :color="record.usage_is_estimated ? 'orange' : 'green'">{{ record.usage_is_estimated ? '估算' : '实测' }}</a-tag></template>
            <template v-else-if="column.key === 'outcome'"><a-tag :color="record.outcome === 'succeeded' ? 'green' : 'red'">{{ record.outcome === 'succeeded' ? '成功' : '失败' }}</a-tag></template>
          </template>
        </a-table>
        <div v-else-if="loading" class="table-empty-state" role="status">正在加载模型用量…</div>
        <div v-else-if="usageLoadError" class="table-empty-state" role="alert">暂时无法读取模型调用记录，请刷新重试。</div>
        <AdminEmpty v-else class="table-empty-state" emoji="📊" description="暂无模型调用记录" />
      </a-card>
    </div>

    <a-modal v-model:open="modalOpen" :title="editingId ? `编辑模型：${form.display_name}` : '新建模型'"
      ok-text="保存" cancel-text="取消" :confirm-loading="saving" @ok="saveModel">
      <a-form layout="vertical">
        <a-form-item v-if="!editingId" label="所属租户"><a-select v-model:value="form.tenant_id" :options="tenants.filter(tenant => tenant.status === 'active').map(tenant => ({ value: tenant.id, label: tenant.name }))" /></a-form-item>
        <a-form-item v-if="!editingId" label="模型标识"><a-input v-model:value="form.key" :maxlength="100" placeholder="gpt-4o" /></a-form-item>
        <a-form-item label="提供方"><a-input v-model:value="form.provider" :maxlength="100" placeholder="openai-compatible" /></a-form-item>
        <a-form-item label="模型名称"><a-input v-model:value="form.model_name" :maxlength="160" /></a-form-item>
        <a-form-item label="展示名称"><a-input v-model:value="form.display_name" :maxlength="160" /></a-form-item>
        <a-form-item label="端点 URL（HTTPS）"><a-input v-model:value="form.endpoint_url" :maxlength="500" placeholder="留空可清除当前地址" /></a-form-item>
        <a-form-item label="外部凭证引用"><a-input v-model:value="form.credential_ref" :maxlength="300" :disabled="clearCredentialRef" :placeholder="editingId ? '留空保持现有引用不变' : 'vault://team/provider-key'" /></a-form-item>
        <a-checkbox v-if="editingId" v-model:checked="clearCredentialRef">清除当前凭证引用</a-checkbox>
        <a-form-item label="能力（逗号分隔）"><a-input v-model:value="form.capabilities" placeholder="chat,vision,embedding" /></a-form-item>
        <a-form-item label="RPM 限额（请求/分钟）"><a-input-number v-model:value="form.rpm_limit" :min="1" style="width:100%" placeholder="留空表示不限制" /></a-form-item>
        <a-form-item label="TPM 限额（Token/分钟）"><a-input-number v-model:value="form.tpm_limit" :min="1" style="width:100%" placeholder="留空表示不限制" /></a-form-item>
        <a-form-item label="输入价格/百万 Token"><a-input-number v-model:value="form.input_cost_per_million" :min="0" :precision="6" style="width:100%" /></a-form-item>
        <a-form-item label="输出价格/百万 Token"><a-input-number v-model:value="form.output_cost_per_million" :min="0" :precision="6" style="width:100%" /></a-form-item>
        <a-alert :message="editingId ? '模型标识和租户范围只读；凭证留空保持原引用，只有勾选清除才会删除。' : '模型凭证仅接受 vault:// 或 secret:// 外部引用；限额是否拦截由服务端配额开关控制。'" type="info" show-icon />
      </a-form>
    </a-modal>

    <a-modal v-model:open="reviewOpen" title="核对模型调用" ok-text="提交核对" cancel-text="取消"
      :confirm-loading="reviewing" @ok="resolveReview">
      <a-alert class="review-warning" type="warning" show-icon
        message="Provider 可能已经完成调用。请根据 Provider 账单或日志填写，不能仅为清空队列而释放。" />
      <p v-if="reviewTarget" class="review-request">{{ reviewTarget.model_name }} · {{ reviewTarget.application_name }} · {{ reviewTarget.request_id }}</p>
      <a-form layout="vertical">
        <a-form-item label="处理方式"><a-radio-group v-model:value="reviewForm.decision">
          <a-radio value="settle">记录实际或估算用量</a-radio><a-radio value="release">确认未调用，释放额度</a-radio>
        </a-radio-group></a-form-item>
        <template v-if="reviewForm.decision === 'settle'">
          <a-form-item label="输入 Token"><a-input-number v-model:value="reviewForm.input_tokens" :min="0" :max="10000000" style="width:100%" /></a-form-item>
          <a-form-item label="输出 Token"><a-input-number v-model:value="reviewForm.output_tokens" :min="0" :max="10000000" style="width:100%" /></a-form-item>
          <a-form-item label="调用结果"><a-select v-model:value="reviewForm.outcome" :options="[{ value: 'succeeded', label: '成功' }, { value: 'failed', label: '失败' }]" /></a-form-item>
          <a-checkbox v-model:checked="reviewForm.usage_is_estimated">这是估算用量</a-checkbox>
          <a-form-item label="延迟（毫秒，可留空）"><a-input-number v-model:value="reviewForm.latency_ms" :min="0" :max="86400000" style="width:100%" /></a-form-item>
        </template>
        <a-form-item v-else>
          <a-checkbox v-model:checked="reviewForm.provider_not_called">我已确认 Provider 从未被调用</a-checkbox>
        </a-form-item>
        <a-form-item label="核对依据（必填，写明日志或账单来源，不要填写提示词或密钥）">
          <a-textarea v-model:value="reviewForm.reason" :maxlength="500" :rows="3" show-count />
        </a-form-item>
      </a-form>
    </a-modal>
  </section>
</template>

<style scoped>
.model-governance-page { display: flex; flex-direction: column; gap: 20px; min-width: 0; max-width: 100%; }
/* P370 修复：原 grid 布局在 P364 section 拉伸下 align-content:stretch 会把页头行也拉高，
   叠加 AdminPageHeader 的 items-end 使标题被推到底部 → 头部空白近百px。改 flex 后子项默认不拉伸，
   仅让最后一个区块吃剩余高度，保住页脚贴底与卡片撑满的骨架效果。 */
.model-governance-page > :last-child { flex: 1 0 auto; }
.model-governance-page > :last-child > .data-card { flex: 1 0 auto; }
.data-card { min-width: 0; max-width: 100%; border-radius: 16px; }
.review-card { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
.model-governance-page :deep(.ant-card-body) { min-width: 0; max-width: 100%; }
.model-governance-page :deep(.ant-table-wrapper) { width: 100%; min-width: 0; max-width: 100%; overflow: hidden; }
.model-governance-page :deep(.ant-table-content) { max-width: 100%; }
.review-table { min-width: 0; }
.table-empty-state { padding: 24px 0; }
div.table-empty-state { display: grid; place-items: center; min-height: 140px; color: var(--subtle); font-size: 13px; }
.review-warning { margin-bottom: 14px; }
.review-request { overflow-wrap: anywhere; color: var(--color-text-secondary); font-size: 12px; }
.table-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 14px; margin-bottom: 18px; }
.tenant-filter-control { display: flex; align-items: center; gap: 8px; flex: 0 0 auto; }
.tenant-filter-label { color: var(--color-text-muted); font-size: 12px; white-space: nowrap; }
/* P398 宽度统一由 style.css 工具条规则（208px）权威管理，这里只保留不收缩与窄屏全宽 */
.tenant-filter { flex: 0 0 auto; }
.table-hint { flex: 1; min-width: 0; color: var(--color-text-secondary); font-size: 12px; }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
  .table-toolbar { align-items: stretch; flex-direction: column; }
  .tenant-filter-control { align-items: stretch; flex-direction: column; gap: 6px; }
  .tenant-filter { width: 100%; }
}
</style>
