<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { api, ApiRequestError } from '@/api'
import { ADMIN_API_PREFIX, hasButton } from '@/api/capabilities'
import { PAGE_PATHS } from '@/router/navigation'
import { EllipsisOutlined, PlusOutlined } from '@/plugins/icons'
import { MODEL_CAPABILITY_OPTIONS } from '@/utils/modelCapabilities'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminTableToolbar from '@/components/AdminTableToolbar.vue'
import AdminTable from '@/components/AdminTable.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
// P369：复用概览账本指标卡（clickable=false 纯展示态），统一「编号 + 巨号数字」设计语言。
import OverviewStatCard from '@/views/overview/components/OverviewStatCard.vue'
// P400：用量趋势与模型分布图表（echarts 复用概览基建），数据来自新增的同口径聚合端点。
import ModelUsageCharts from './components/ModelUsageCharts.vue'
import type { UsageModelAggregate, UsageTimelinePoint } from './components/ModelUsageCharts.vue'
// 重设计（P401）：目录概览带 / 状态点 / 分区表单弹窗 / 下发租户弹窗拆分到 components/。
import CatalogSummaryCards from './components/CatalogSummaryCards.vue'
import StatusDot from './components/StatusDot.vue'
import ModelFormModal from './components/ModelFormModal.vue'
import TenantGrantModal from './components/TenantGrantModal.vue'

type View = 'catalog' | 'usage'
interface Tenant { id: string; name: string; slug: string; kind: string; status: string }
interface ModelRecord {
  id: string; tenant_id: string; key: string; provider: string; model_name: string; display_name: string
  endpoint_url?: string | null; credential_configured: boolean
  // 凭证回显：secret_env 回传环境变量名（引用不含密钥）；other（如 vault://）只标注种类
  credential_env_var?: string | null; credential_ref_kind?: 'secret_env' | 'other' | null
  capabilities: string[]
  rpm_limit?: number | null; tpm_limit?: number | null; input_cost_per_million?: number | null
  output_cost_per_million?: number | null; quota_status: 'enforced' | 'configured_only' | 'unlimited'
  status: 'active' | 'disabled'; created_at?: string
  // 三级分发计数：超管视角返回已下发租户数；租户级视角返回活跃应用下发数。
  tenant_grant_count?: number; application_grant_count?: number
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
// 页内写按钮认 button.models.manage；L1 放行语义收进 hasButton 统一判权。
const canManageModels = computed(() => hasButton('button.models.manage'))
// 模型测试台入口（设计文档 §2）：目录行操作携带 model_id 深链，可达性与模型治理同码。
const router = useRouter()
const USAGE_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/
const OUTCOME_FILTER_OPTIONS = [
  { value: 'succeeded', label: '成功' },
  { value: 'failed', label: '失败' },
]
// 能力标签中文映射（标准集）：表格 chip 与悬停提示共用。
const CAPABILITY_LABELS = new Map(MODEL_CAPABILITY_OPTIONS.map(option => [option.value, option.label]))
const CAPABILITY_HINTS = new Map(MODEL_CAPABILITY_OPTIONS.map(option => [option.value, option.hint]))
// 限额执行状态 → 色点语言：拦截中=琥珀点缀，仅记录/未设置保持中性。
const QUOTA_STATUS_META: Record<ModelRecord['quota_status'], { tone: 'warn' | 'muted' | 'hollow'; text: string }> = {
  enforced: { tone: 'warn', text: '拦截中' },
  configured_only: { tone: 'muted', text: '仅记录' },
  unlimited: { tone: 'hollow', text: '未设置' },
}

const tenants = ref<Tenant[]>([])
const tenantId = ref<string>()
// 目录视图本地筛选：关键字（标识/展示名/模型名/提供方）+ 状态（由概览带点击驱动）；数据量小（≤500），不过节流。
const catalogSearch = ref('')
const catalogStatus = ref<'active' | 'disabled' | undefined>(undefined)
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
// 重设计：模型表单弹窗 / 下发租户弹窗状态收敛为「开 + 目标」，表单与关系逻辑由子组件托管。
const formOpen = ref(false)
const editingRecord = ref<ModelRecord | null>(null)
const grantOpen = ref(false)
const grantTarget = ref<ModelRecord | null>(null)
const requestSequence = ref(0)
const reviewOpen = ref(false)
const reviewing = ref(false)
const reviewTarget = ref<UsageReview | null>(null)
const reviewForm = reactive({
  decision: 'settle' as 'settle' | 'release', reason: '', input_tokens: 0,
  output_tokens: 0, outcome: 'succeeded' as 'succeeded' | 'failed',
  usage_is_estimated: true, latency_ms: null as number | null, provider_not_called: false,
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
// 目录视图筛选后的模型列表：关键字命中标识/展示名/模型名/提供方任一，叠加状态过滤。
const filteredModels = computed(() => {
  const keyword = catalogSearch.value.trim().toLowerCase()
  return models.value.filter(model => {
    if (catalogStatus.value && model.status !== catalogStatus.value) return false
    if (!keyword) return true
    return [model.key, model.display_name, model.model_name, model.provider]
      .some(field => String(field || '').toLowerCase().includes(keyword))
  })
})
// 超管整行点击直达最高频操作（下发租户）；只读视角不加行点击避免误导可点。
function modelRowProps(record: ModelRecord): Record<string, unknown> {
  return { class: 'model-row-clickable', onClick: () => openTenantGrants(record) }
}
// 目录空态区分：有筛选条件但无命中时提示调整筛选，避免误判为目录本身为空。
const catalogEmptyDescription = computed(() => {
  if (catalogSearch.value.trim() || catalogStatus.value) return '没有符合筛选条件的模型，可调整关键字或状态'
  return canManageModels.value ? '暂无模型目录项，可创建模型' : '租户尚未收到平台下发的模型'
})
const modelFilterOptions = computed(() => catalogModels.value.map(model => ({
  value: model.id,
  label: model.display_name,
})))
const estimatedCostSummary = computed(() => {
  // M4：零请求时显示占位符 —，避免统计卡里出现长短不一的文本值破坏卡片节奏
  if (summary.value.requests === 0) return '—'
  return summary.value.estimated_cost === null ? '费用未知' : formatCostValue(summary.value.estimated_cost)
})
// P369：账本式汇总指标卡（对齐 P368 概览 01–05），大数千分位格式化；数据未加载时统一显示占位符。
// U20：卡内不再带 01–05 编号——与节编号双体系打架，卡片回归「标签+数值」纯排版。
const usageMetricCards = computed(() => {
  const loaded = usageDataLoaded.value
  const count = (value: number): number | string => (loaded ? value.toLocaleString('zh-CN') : '—')
  return [
    { label: '请求总数', value: count(summary.value.requests) },
    { label: '成功率', value: loaded && summary.value.requests > 0 ? `${(summary.value.succeeded / summary.value.requests * 100).toFixed(1)}%` : '—' },
    { label: '输入 Token', value: count(summary.value.input_tokens) },
    { label: '输出 Token', value: count(summary.value.output_tokens) },
    { label: '估算费用', value: loaded ? estimatedCostSummary.value : '—' },
  ]
})
// 次级审计指标（成功/失败绝对数、估算与未知费用计数）收进脚注行，保证指标卡单行 5 张与概览一致。
const usageAuditFootnote = computed(() => {
  const count = (value: number): string => value.toLocaleString('zh-CN')
  return `成功 ${count(summary.value.succeeded)} · 失败 ${count(summary.value.failed)} · 估算用量请求 ${count(summary.value.estimated_usage_requests)} · 未知费用请求 ${count(summary.value.unknown_cost_requests)}`
})

// U2 章节编号改「位置序」动态计算：无聚合数据时图表区合并为单个「02 用量与分布」空档带，
// 待核对/账目前移为 03/04；有数据时恢复 04/05。修复空态 01→02→04→05 跳号。
const usageChartsHaveData = computed(() => Boolean(timeline.value?.length || byModel.value?.length))
const reviewSectionNo = computed(() => (usageChartsHaveData.value ? '04' : '03'))
const ledgerSectionNo = computed(() => {
  if (props.view !== 'usage') return '01'
  return usageChartsHaveData.value ? '05' : '04'
})

// 目录表格列（重设计）：15 列收敛为 10 列——
// 模型/提供方双行单元格、能力 chip、限流与价格合并 mono 列、状态语言改色点；
// 操作列仅超管可见，收敛为「下发租户 + ⋯ 更多」。
const baseModelColumns = [
  { title: '模型', dataIndex: 'display_name', key: 'display_name', width: 180, ellipsis: true },
  { title: '提供方 / 模型', dataIndex: 'provider', key: 'provider', width: 170, ellipsis: true },
  { title: '能力', dataIndex: 'capabilities', key: 'capabilities', width: 180 },
  { title: '限流 RPM/TPM', dataIndex: 'limits', key: 'limits', width: 120, align: 'right' as const },
  { title: '价格 / 百万', dataIndex: 'price', key: 'price', width: 130, align: 'right' as const },
  { title: '凭证', dataIndex: 'credential_configured', key: 'credential_configured', width: 92 },
  { title: '限额', dataIndex: 'quota_status', key: 'quota_status', width: 96 },
  { title: '已下发', dataIndex: 'tenant_grant_count', key: 'tenant_grant_count', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 88 },
]
// 操作列 2 个元素（主操作 + 溢出菜单）约需 128px。
const modelActionColumn = { title: '操作', dataIndex: 'actions', key: 'actions', width: 128, fixed: 'right' as const }
const modelColumns = computed(() => (canManageModels.value ? [...baseModelColumns, modelActionColumn] : baseModelColumns))
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
const modelTableScrollWidth = computed(() => modelColumns.value.reduce((width, column) => width + column.width, 0))
const usageTableScrollWidth = usageColumns.reduce((width, column) => width + column.width, 0)
const reviewTableScrollWidth = reviewColumns.reduce((width, column) => width + column.width, 0)

// 目录单元格辅助：限流与价格合并为 mono 展示。
function formatLimits(record: ModelRecord): string {
  return `${record.rpm_limit ?? '—'} / ${record.tpm_limit ?? '—'}`
}
function formatPricePair(record: ModelRecord): string {
  const hasInput = record.input_cost_per_million != null
  const hasOutput = record.output_cost_per_million != null
  if (!hasInput && !hasOutput) return '未知'
  const input = hasInput ? formatCostValue(String(record.input_cost_per_million)) : '—'
  const output = hasOutput ? formatCostValue(String(record.output_cost_per_million)) : '—'
  return `${input} / ${output}`
}
function capabilityLabel(code: string): string {
  return CAPABILITY_LABELS.get(code) ?? code
}
function capabilityHint(code: string): string {
  return CAPABILITY_HINTS.get(code) ?? code
}
// 溢出菜单动作分发（测试 / 编辑 / 停用|启用 / 删除）。
function onModelMenu(record: ModelRecord, info: { key: string | number }): void {
  if (info.key === 'test') void router.push(`${PAGE_PATHS.model_test}?model_id=${encodeURIComponent(record.id)}`)
  else if (info.key === 'edit') editModel(record)
  else if (info.key === 'toggle') changeStatus(record)
  else if (info.key === 'delete') deleteModel(record)
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

// M3 日期范围选择器：一个语义控件替代两个裸文本框；value-format 让 v-model 直接持有 YYYY-MM-DD 字符串，
// 读写桥接既有 createdFrom/createdTo 与校验逻辑，选择器本身保证日期合法。
const usageDateRangeModel = computed<string[] | null>({
  get: () => (createdFrom.value && createdTo.value ? [createdFrom.value, createdTo.value] : null),
  set: (range) => {
    createdFrom.value = range?.[0] || ''
    createdTo.value = range?.[1] || ''
    commitUsageDates()
  },
})

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
  // 租户模式（L2/L3）必须显式锚定租户才能通过后端判权，默认选首个可见租户。
  const knownTenants = props.seedTenants?.length ? props.seedTenants : tenants.value
  if (!tenantId.value && knownTenants.length) tenantId.value = knownTenants[0].id
  // seedTenants 提供时跳过 /admin/tenants（租户管理员无租户管理菜单节点）。
  const tenantsSource = props.seedTenants?.length
    ? Promise.resolve(props.seedTenants)
    : api<Tenant[]>(`${ADMIN_API_PREFIX}/tenants`)
  try {
    if (props.view === 'catalog') {
      // 三级分发：目录接口按操作者范围返回（超管=平台目录全集；租户/应用级=收到的模型）。
      const [tenantRows, modelRows] = await Promise.all([
        tenants.value.length ? Promise.resolve(tenants.value) : tenantsSource,
        api<ModelRecord[]>(`${ADMIN_API_PREFIX}/models`),
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
      const modelRowsPromise = api<ModelRecord[]>(`${ADMIN_API_PREFIX}/models`).catch(() => null)
      // P400：趋势与分布与汇总共用同一套筛选参数（summaryQuery），保证口径一致；
      // 指定模型筛选时分布退化为单柱，直接跳过请求并清空旧图。
      const timelinePromise = api<{ items: UsageTimelinePoint[] }>(`${ADMIN_API_PREFIX}/model-usage/timeline?${summaryQuery}`).catch(() => null)
      const byModelPromise = modelFilter.value
        ? Promise.resolve(null)
        : api<{ items: UsageModelAggregate[] }>(`${ADMIN_API_PREFIX}/model-usage/by-model?${summaryQuery}`).catch(() => null)
      const [tenantRows, eventRows, usageSummary, reviewRows, modelRows, timelineRows, byModelRows] = await Promise.all([
        tenants.value.length ? Promise.resolve(tenants.value) : tenantsSource,
        api<UsageEventPage>(`${ADMIN_API_PREFIX}/model-usage/events?${eventParams.toString()}`),
        api<UsageSummary>(`${ADMIN_API_PREFIX}/model-usage/summary${summaryQuery ? `?${summaryQuery}` : ''}`),
        api<UsageReviewPage>(`${ADMIN_API_PREFIX}/model-usage/reviews?${reviewParams.toString()}`),
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
    await api(`${ADMIN_API_PREFIX}/model-usage/reviews`, { method: 'POST', body: JSON.stringify(payload) })
    message.success(reviewForm.decision === 'settle' ? '用量已核对并入账' : '已确认未调用 Provider，额度已释放')
    reviewOpen.value = false
    if (reviews.value.length === 1 && reviewPage.value > 1) reviewPage.value -= 1
    await load()
  } catch (error) { message.error(error instanceof Error ? error.message : '核对用量失败') }
  finally { reviewing.value = false }
}

// ── 弹窗入口（表单 / 下发关系逻辑由子组件托管，页面只持开合与目标）─────────────

function createModel(): void {
  editingRecord.value = null
  formOpen.value = true
}

function editModel(record: ModelRecord): void {
  editingRecord.value = record
  formOpen.value = true
}

function openTenantGrants(record: ModelRecord): void {
  grantTarget.value = record
  grantOpen.value = true
}

function changeStatus(record: ModelRecord): void {
  const status = record.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(`${ADMIN_API_PREFIX}/models/${record.id}/status`, {
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
        await api(`${ADMIN_API_PREFIX}/models/${record.id}`, { method: 'DELETE' })
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
      :subtitle="view === 'catalog' ? '维护平台支持的模型目录并下发租户；租户管理员在应用工作台把收到的模型分发到应用。' : '查看可信网关报告的请求量、Token 消耗和费用估算。可按模型、结果和 UTC 日期筛选。'"
    >
      <template #extra>
        <a-button v-if="view === 'catalog' && canManageModels" type="primary" @click="createModel">
          <template #icon><PlusOutlined /></template>
          新建模型
        </a-button>
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
        <!-- U30 关键口径说明从 muted 提到 secondary：11px 浅灰约 2.3:1 低于可读下限 -->
        <p class="mb-0 text-xs text-[var(--color-text-secondary)]">统计口径与下方账目筛选一致，不含待核对预留</p>
      </div>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <OverviewStatCard
          v-for="metric in usageMetricCards"
          :key="metric.label"
          :clickable="false"
          :label="metric.label"
          :value="metric.value"
        />
      </div>
      <!-- U12 次级审计指标收进脚注行：去 mono/字距，作常规说明行避免读作悬浮裁切数字 -->
      <p class="mb-0 mt-1 text-xs text-[var(--color-text-muted)]">{{ usageAuditFootnote }}</p>
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
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">{{ reviewSectionNo }}</span>
          待核对调用
          <a-badge :count="reviewTotal" :show-zero="false" />
        </h3>
        <a-button :loading="loading" @click="load">刷新核对队列</a-button>
      </div>
      <a-card class="data-card review-card" :bordered="false">
        <!-- M2 降噪：超时预留警示只在队列确实有待核对项时出现，空队列不再常驻橙条 -->
        <a-alert v-if="reviews.length > 0" message="超时预留不会自动收费或释放（核对前仍占保守 TPM 额度）；请先对照 Provider 日志——确认从未调用才可释放，无法还原用量时按可核实依据结算并标记为估算。" type="warning" show-icon />
        <!-- M2 统一表格组件：加载 / 错误 / 空态由 AdminTable 托管，替代原 v-if 自定义空态分支 -->
        <AdminTable
          class="review-table"
          :columns="reviewColumns"
          :data-source="reviews"
          :loading="loading"
          :error-text="usageLoadError"
          row-key="request_id"
          :scroll="{ x: reviewTableScrollWidth, y: 'calc(max(360px, 100vh - 430px))' }"
          :pagination="{ current: reviewPage, pageSize: reviewPageSize, total: reviewTotal, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'], showTotal: reviewTotalText }"
          empty-emoji="🧾"
          empty-text="没有待核对调用"
          @table-change="changeReviewPage"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'expires_at'">{{ new Date(record.expires_at).toLocaleString() }}</template>
            <template v-else-if="column.key === 'actions'"><a-button v-if="canManageModels" type="primary" size="small" @click="openReview(record)">核对</a-button></template>
          </template>
        </AdminTable>
      </a-card>
    </div>

    <!-- P369：编号头 05（目录视图无汇总/图表/复核区，编号为 01 模型目录）。 -->
    <div class="flex min-w-0 flex-col">
      <div class="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">{{ ledgerSectionNo }}</span>
          {{ view === 'usage' ? '调用账目' : '模型目录' }}
        </h3>
      </div>

      <!-- 重设计：目录视图增加账本式概览带（点击卡片即筛选状态），位于目录区块之上。 -->
      <CatalogSummaryCards
        v-if="view === 'catalog'"
        v-model:status-filter="catalogStatus"
        :models="models"
        :super-view="canManageModels"
        class="mb-4"
      />

      <a-card class="data-card" :bordered="false">
        <AdminTableToolbar :hint="view === 'catalog' ? '平台模型目录：超管维护并下发租户；租户/应用级视角只显示收到的模型（只读）。凭证仅保存外部引用，不回读。' : `共 ${usageEventTotal} 条模型调用账目，按时间倒序分页。结果、模型和 UTC 日期同时作用于汇总与账目，不筛选待核对队列。`">
          <!-- 目录视图本地筛选：关键字（状态筛选由概览带承接）；数据量小，纯前端过滤即时生效 -->
          <template v-if="view === 'catalog'">
            <AdminSearchField v-model="catalogSearch" class="tenant-filter" placeholder="搜索名称 / 标识 / 提供方" />
          </template>
          <div v-if="view === 'usage'" class="tenant-filter-control">
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
            <!-- M3 日期筛选：范围选择器一个控件替代两个文本框（自带合法校验，口径仍为 UTC 日期字符串） -->
            <a-range-picker
              v-model:value="usageDateRangeModel"
              class="w-full shrink-0 lg:w-[264px]"
              value-format="YYYY-MM-DD"
              :placeholder="['开始日期', '结束日期']"
              separator="→"
              allow-clear
              aria-label="按 UTC 日期范围筛选"
            />
          </template>
          <template #actions>
            <a-button :loading="loading" @click="load">刷新</a-button>
          </template>
        </AdminTableToolbar>
        <!-- M4 日期错误提示用语义 token（原 Tailwind red-400） -->
        <p v-if="view === 'usage' && usageDateError" class="m-0 mb-3 text-xs text-[var(--color-error)]" role="alert">{{ usageDateError }}</p>

        <!-- 目录表：双行主列 + 能力 chip + mono 限流/价格 + 色点状态 + 收敛操作列 -->
        <a-table v-if="view === 'catalog'" :data-source="filteredModels" :columns="modelColumns" :loading="loading" row-key="id"
          :custom-row="canManageModels ? modelRowProps : undefined"
          :scroll="{ x: modelTableScrollWidth, y: 'calc(max(360px, 100vh - 430px))' }" :pagination="{ pageSize: 10, showSizeChanger: true }">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'display_name'">
              <div class="min-w-0">
                <div class="truncate font-medium text-[var(--color-text-primary)]">{{ record.display_name }}</div>
                <div class="truncate font-mono text-[11px] leading-4 text-[var(--color-text-muted)]">{{ record.key }}</div>
              </div>
            </template>
            <template v-else-if="column.key === 'provider'">
              <!-- 悬停展示端点地址（原独立列收进提示，压缩横向宽度） -->
              <div class="min-w-0" :title="record.endpoint_url || undefined">
                <div class="truncate">{{ record.provider }}</div>
                <div class="truncate font-mono text-[11px] leading-4 text-[var(--color-text-muted)]">{{ record.model_name }}</div>
              </div>
            </template>
            <template v-else-if="column.key === 'capabilities'">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="cap in record.capabilities"
                  :key="cap"
                  class="cap-chip"
                  :title="capabilityHint(cap)"
                >{{ capabilityLabel(cap) }}</span>
                <span v-if="!record.capabilities?.length" class="text-[var(--color-text-muted)]">—</span>
              </div>
            </template>
            <template v-else-if="column.key === 'limits'">
              <span class="font-mono text-[12.5px] tabular-nums" :title="`RPM ${record.rpm_limit ?? '不限'} · TPM ${record.tpm_limit ?? '不限'}`">{{ formatLimits(record) }}</span>
            </template>
            <template v-else-if="column.key === 'price'">
              <span class="font-mono text-[12.5px] tabular-nums" :class="{ 'text-[var(--color-text-muted)]': record.input_cost_per_million == null && record.output_cost_per_million == null }">{{ formatPricePair(record) }}</span>
            </template>
            <template v-else-if="column.key === 'credential_configured'">
              <StatusDot :tone="record.credential_configured ? 'muted' : 'hollow'" :text="record.credential_configured ? '已配置' : '未配置'" />
            </template>
            <template v-else-if="column.key === 'quota_status'">
              <StatusDot :tone="QUOTA_STATUS_META[record.quota_status as ModelRecord['quota_status']].tone" :text="QUOTA_STATUS_META[record.quota_status as ModelRecord['quota_status']].text" />
            </template>
            <template v-else-if="column.key === 'tenant_grant_count'">
              <a-button v-if="canManageModels" type="link" size="small" class="!px-0" @click.stop="openTenantGrants(record)">
                {{ record.tenant_grant_count ?? 0 }} 个租户
              </a-button>
              <span v-else class="tabular-nums">{{ record.application_grant_count ?? 0 }} 个应用</span>
            </template>
            <template v-else-if="column.key === 'status'">
              <StatusDot :tone="record.status === 'active' ? 'ok' : 'off'" :text="record.status === 'active' ? '启用' : '停用'" />
            </template>
            <template v-else-if="column.key === 'actions'">
              <!-- 操作收敛：主操作直达下发租户，低频动作进溢出菜单（§9 操作列收敛） -->
              <div class="flex items-center" @click.stop>
                <a-button type="link" size="small" class="!px-0" @click="openTenantGrants(record)">下发租户</a-button>
                <a-dropdown trigger="click" placement="bottomRight">
                  <a-button type="text" size="small" aria-label="更多操作" @click.prevent>
                    <EllipsisOutlined />
                  </a-button>
                  <template #overlay>
                    <a-menu :selectable="false" @click="onModelMenu(record, $event)">
                      <a-menu-item key="test">测试</a-menu-item>
                      <a-menu-item key="edit">编辑</a-menu-item>
                      <a-menu-item key="toggle">{{ record.status === 'active' ? '停用' : '启用' }}</a-menu-item>
                      <a-menu-item key="delete" danger>删除</a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </div>
            </template>
          </template>
          <template #emptyText><AdminEmpty emoji="🤖" :description="catalogEmptyDescription" /></template>
        </a-table>

        <!-- M3 统一表格组件：加载 / 错误 / 空态由 AdminTable 托管，替代原 v-if 三分支自定义空态 -->
        <AdminTable v-else
          :columns="usageColumns"
          :data-source="events"
          :loading="loading"
          :error-text="usageLoadError"
          row-key="id"
          :scroll="{ x: usageTableScrollWidth, y: 'calc(max(360px, 100vh - 430px))' }"
          :pagination="{ current: usageEventPage, pageSize: usageEventPageSize, total: usageEventTotal, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'], showTotal: usageEventTotalText }"
          empty-emoji="📊"
          empty-text="暂无模型调用记录"
          @table-change="changeUsageEventPage"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'created_at'">{{ new Date(record.created_at).toLocaleString() }}</template>
            <template v-else-if="column.key === 'estimated_cost'">
              <span class="font-mono text-[12.5px] tabular-nums" :class="record.estimated_cost === null ? 'text-[var(--color-text-muted)]' : ''">{{ record.estimated_cost === null ? '未知' : formatCostValue(record.estimated_cost) }}</span>
            </template>
            <template v-else-if="column.key === 'source'">
              <span class="text-[13px] text-[var(--color-text-secondary)]">{{ record.source === 'admin_reconciliation' ? '管理员核对' : '网关上报' }}</span>
            </template>
            <template v-else-if="column.key === 'usage_is_estimated'">
              <StatusDot :tone="record.usage_is_estimated ? 'warn' : 'ok'" :text="record.usage_is_estimated ? '估算' : '实测'" />
            </template>
            <template v-else-if="column.key === 'outcome'">
              <StatusDot :tone="record.outcome === 'succeeded' ? 'ok' : 'err'" :text="record.outcome === 'succeeded' ? '成功' : '失败'" />
            </template>
            <template v-else-if="column.key === 'latency_ms'">
              <span class="font-mono text-[12.5px] tabular-nums">{{ record.latency_ms ?? '—' }}</span>
            </template>
          </template>
        </AdminTable>
      </a-card>
    </div>

    <!-- 重设计：模型表单弹窗（分区表单，保存链路契约不变） -->
    <ModelFormModal v-model:open="formOpen" :model="editingRecord" @saved="load" />

    <!-- 三级分发：平台模型 → 租户 下发管理（超管；回收为软失效并级联应用下发）。 -->
    <TenantGrantModal v-model:open="grantOpen" :model="grantTarget" :tenants="tenants" @changed="load" />

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
.review-warning { margin-bottom: 14px; }
.review-request { overflow-wrap: anywhere; color: var(--color-text-secondary); font-size: 12px; }
.tenant-filter-control { display: flex; align-items: center; gap: 8px; flex: 0 0 auto; }
.tenant-filter-label { color: var(--color-text-muted); font-size: 12px; white-space: nowrap; }
/* P398 宽度统一由 style.css 工具条规则（208px）权威管理，这里只保留不收缩与窄屏全宽 */
.tenant-filter { flex: 0 0 auto; }
/* 超管视角整行可点（直达下发租户）；hover 高亮沿用 antd 行悬停默认 */
.model-governance-page :deep(.model-row-clickable) { cursor: pointer; }
/* 能力 chip：原生 span + token（P362/P388 教训，不走 a-tag），黑白灰发丝线轮廓 */
.cap-chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  padding: 2px 8px;
  font-size: 11.5px;
  line-height: 1.4;
  color: var(--color-text-secondary);
  background: var(--color-bg-elevated);
  white-space: nowrap;
}
@media (max-width: 700px) {
  .tenant-filter-control { align-items: stretch; flex-direction: column; gap: 6px; }
  .tenant-filter { width: 100%; }
}
</style>
