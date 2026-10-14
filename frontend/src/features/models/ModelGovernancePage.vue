<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api, ApiRequestError } from '../../shared/services/api'

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

const props = defineProps<{ active: boolean; view: View }>()
const tenants = ref<Tenant[]>([])
const tenantId = ref('')
const models = ref<ModelRecord[]>([])
const events = ref<UsageEvent[]>([])
const usageEventTotal = ref(0)
const usageEventPage = ref(1)
const usageEventPageSize = ref(10)
const reviews = ref<UsageReview[]>([])
const reviewTotal = ref(0)
const reviewPage = ref(1)
const reviewPageSize = ref(10)
const summary = ref<UsageSummary>({ requests: 0, succeeded: 0, failed: 0, input_tokens: 0, output_tokens: 0, estimated_cost: null, unknown_cost_requests: 0, estimated_usage_requests: 0 })
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

const title = computed(() => props.view === 'catalog' ? '模型管理' : '模型用量')
const summaryMetrics = computed(() => [
  { label: '请求总数', value: summary.value.requests },
  { label: '成功', value: summary.value.succeeded },
  { label: '失败', value: summary.value.failed },
  { label: '输入 Token', value: summary.value.input_tokens },
  { label: '输出 Token', value: summary.value.output_tokens },
  { label: '估算费用', value: summary.value.estimated_cost ?? '未配置价格' },
  { label: '估算用量请求', value: summary.value.estimated_usage_requests },
  { label: '未知费用请求', value: summary.value.unknown_cost_requests },
])
const modelColumns = [
  { title: '模型', dataIndex: 'display_name', key: 'display_name', width: 180 },
  { title: '租户', dataIndex: 'tenant_id', key: 'tenant_id', width: 180 },
  { title: '模型标识', dataIndex: 'key', key: 'key', width: 150 },
  { title: '提供方', dataIndex: 'provider', key: 'provider', width: 150 },
  { title: '模型名称', dataIndex: 'model_name', key: 'model_name', width: 170 },
  { title: '端点', dataIndex: 'endpoint_url', key: 'endpoint_url', width: 220, ellipsis: true },
  { title: '能力', dataIndex: 'capabilities', key: 'capabilities', width: 150 },
  { title: '凭证引用', dataIndex: 'credential_configured', key: 'credential_configured', width: 110 },
  { title: 'RPM', dataIndex: 'rpm_limit', key: 'rpm_limit', width: 90 },
  { title: 'TPM', dataIndex: 'tpm_limit', key: 'tpm_limit', width: 100 },
  { title: '输入价格/百万', dataIndex: 'input_cost_per_million', key: 'input_cost_per_million', width: 120 },
  { title: '输出价格/百万', dataIndex: 'output_cost_per_million', key: 'output_cost_per_million', width: 120 },
  { title: '限额执行', dataIndex: 'quota_status', key: 'quota_status', width: 140 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 150, fixed: 'right' as const },
]
const usageColumns = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 170 },
  { title: '应用', dataIndex: 'application_name', key: 'application_name', width: 160 },
  { title: '用户', dataIndex: 'user_email', key: 'user_email', width: 190 },
  { title: '输入 Token', dataIndex: 'input_tokens', key: 'input_tokens', width: 110 },
  { title: '输出 Token', dataIndex: 'output_tokens', key: 'output_tokens', width: 110 },
  { title: '记录来源', dataIndex: 'source', key: 'source', width: 120 },
  { title: '计量方式', dataIndex: 'usage_is_estimated', key: 'usage_is_estimated', width: 100 },
  { title: '估算费用', dataIndex: 'estimated_cost', key: 'estimated_cost', width: 120 },
  { title: '结果', dataIndex: 'outcome', key: 'outcome', width: 90 },
  { title: '延迟（毫秒）', dataIndex: 'latency_ms', key: 'latency_ms', width: 120 },
  { title: '网关请求 ID', dataIndex: 'request_id', key: 'request_id', width: 210 },
]
const reviewColumns = [
  { title: '过期时间', dataIndex: 'expires_at', key: 'expires_at', width: 180 },
  { title: '等待核对', dataIndex: 'waiting_minutes', key: 'waiting_minutes', width: 110 },
  { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 170 },
  { title: '应用', dataIndex: 'application_name', key: 'application_name', width: 160 },
  { title: '用户', dataIndex: 'user_email', key: 'user_email', width: 190 },
  { title: '预留输入', dataIndex: 'reserved_input_tokens', key: 'reserved_input_tokens', width: 110 },
  { title: '预留输出', dataIndex: 'reserved_output_tokens', key: 'reserved_output_tokens', width: 110 },
  { title: '请求 ID', dataIndex: 'request_id', key: 'request_id', width: 210 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 110, fixed: 'right' as const },
]

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
  void load()
}

function reviewTotalText(total: number): string {
  return `共 ${total} 条待核对调用`
}

function usageEventTotalText(total: number): string {
  return `共 ${total} 条模型调用账目`
}

function changeUsageEventPage(pagination: { current?: number; pageSize?: number }): void {
  const nextPageSize = Math.min(Math.max(pagination.pageSize ?? usageEventPageSize.value, 1), 200)
  if (nextPageSize !== usageEventPageSize.value) {
    usageEventPageSize.value = nextPageSize
    usageEventPage.value = 1
  } else {
    usageEventPage.value = pagination.current ?? 1
  }
  void load()
}

async function load(): Promise<void> {
  const sequence = ++requestSequence.value
  loading.value = true
  const tenantQuery = tenantId.value ? `?tenant_id=${encodeURIComponent(tenantId.value)}` : ''
  try {
    if (props.view === 'catalog') {
      const [tenantRows, modelRows] = await Promise.all([
        api<Tenant[]>('/admin/tenants'), api<ModelRecord[]>(`/admin/models${tenantQuery}`),
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
      if (tenantId.value) eventParams.set('tenant_id', tenantId.value)
      eventParams.set('limit', String(usageEventPageSize.value))
      eventParams.set('offset', String((usageEventPage.value - 1) * usageEventPageSize.value))
      const [tenantRows, eventRows, usageSummary, reviewRows] = await Promise.all([
        tenants.value.length ? Promise.resolve(tenants.value) : api<Tenant[]>('/admin/tenants'),
        api<UsageEventPage>(`/admin/model-usage/events?${eventParams.toString()}`),
        api<UsageSummary>(`/admin/model-usage/summary${tenantQuery}`),
        api<UsageReviewPage>(`/admin/model-usage/reviews?${reviewParams.toString()}`),
      ])
      if (sequence !== requestSequence.value) return
      tenants.value = tenantRows
      events.value = eventRows.items
      usageEventTotal.value = eventRows.total
      summary.value = usageSummary
      reviews.value = reviewRows.items
      reviewTotal.value = reviewRows.total
    }
  } catch (error) {
    if (sequence === requestSequence.value) {
      if (props.view === 'catalog') models.value = []
      else { events.value = []; usageEventTotal.value = 0; reviews.value = []; reviewTotal.value = 0; summary.value = { requests: 0, succeeded: 0, failed: 0, input_tokens: 0, output_tokens: 0, estimated_cost: null, unknown_cost_requests: 0, estimated_usage_requests: 0 } }
      message.error(error instanceof Error ? error.message : '读取模型治理数据失败')
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

watch([() => props.active, () => props.view, tenantId], ([active], previous) => {
  if (previous && tenantId.value !== previous[2]) {
    reviewPage.value = 1
    usageEventPage.value = 1
  }
  if (active) void load()
}, { immediate: true })
</script>

<template>
  <section class="model-governance-page">
    <header class="page-heading">
      <div><p class="eyebrow">MODEL GOVERNANCE</p><h1>{{ title }}</h1>
        <p class="subtitle">{{ view === 'catalog' ? '维护租户模型目录、外部凭证引用、价格与调用限额。' : '查看可信网关报告的请求量、Token 消耗和费用估算。' }}</p></div>
      <a-button v-if="view === 'catalog'" type="primary" :disabled="!tenants.length" @click="createModel">＋ 新建模型</a-button>
    </header>

    <div v-if="view === 'usage'" class="status-grid usage-summary">
      <article v-for="metric in summaryMetrics" :key="metric.label" class="status-card"><h3>{{ metric.label }}</h3><div class="metric number">{{ metric.value }}</div></article>
    </div>

    <a-card v-if="view === 'usage'" class="data-card review-card" :bordered="false">
      <div class="review-heading"><div><h2>待核对调用 <a-badge :count="reviewTotal" :show-zero="false" /></h2>
        <p>超过 10 分钟仍未结算的预留会列在此处，不会自动按上限收费或释放额度；待核对期间仍占用保守 TPM 额度。</p></div>
        <a-button :loading="loading" @click="load">刷新核对队列</a-button></div>
      <a-alert message="请先对照 Provider 用量日志。只有确认 Provider 从未被调用，才能释放预留；无法还原用量时请按可核实依据结算并标记为估算。" type="warning" show-icon />
      <a-table class="review-table" :data-source="reviews" :columns="reviewColumns" :loading="loading" row-key="request_id"
        :scroll="{ x: 1450 }"
        :pagination="{ current: reviewPage, pageSize: reviewPageSize, total: reviewTotal, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'], showTotal: reviewTotalText }"
        @change="changeReviewPage">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'expires_at'">{{ new Date(record.expires_at).toLocaleString() }}</template>
          <template v-else-if="column.key === 'actions'"><a-button type="primary" size="small" @click="openReview(record)">核对</a-button></template>
        </template>
        <template #emptyText><a-empty description="没有待核对调用" /></template>
      </a-table>
    </a-card>

    <a-card class="data-card" :bordered="false">
      <div class="table-toolbar">
        <a-select v-model:value="tenantId" class="tenant-filter" placeholder="全部租户" allow-clear
          :options="tenants.map(tenant => ({ value: tenant.id, label: tenant.name }))" />
        <span class="table-hint">{{ view === 'catalog' ? '凭证仅保存外部 Secret Manager 引用；RPM/TPM 是否拦截由服务端开关控制。' : `共 ${usageEventTotal} 条模型调用账目，按时间倒序分页；记录不含 Prompt、响应内容或凭证引用。` }}</span>
        <a-button :loading="loading" @click="load">刷新</a-button>
      </div>
      <a-table v-if="view === 'catalog'" :data-source="models" :columns="modelColumns" :loading="loading" row-key="id"
        :scroll="{ x: 2050 }" :pagination="{ pageSize: 10, showSizeChanger: true }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'tenant_id'">{{ tenantName(record.tenant_id) }}</template>
          <template v-else-if="column.key === 'capabilities'">{{ record.capabilities.join('、') || '—' }}</template>
          <template v-else-if="column.key === 'credential_configured'"><a-tag :color="record.credential_configured ? 'blue' : 'default'">{{ record.credential_configured ? '已配置' : '未配置' }}</a-tag></template>
          <template v-else-if="column.key === 'quota_status'"><a-tag :color="record.quota_status === 'enforced' ? 'orange' : record.quota_status === 'configured_only' ? 'blue' : 'default'">{{ ({ enforced: '已启用拦截', configured_only: '已配置，未拦截', unlimited: '未设置限额' } as Record<string, string>)[record.quota_status] }}</a-tag></template>
          <template v-else-if="column.key === 'status'"><a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag></template>
          <template v-else-if="column.key === 'actions'"><a-space :size="2"><a-button type="link" size="small" @click="editModel(record)">编辑</a-button><a-button type="link" size="small" :danger="record.status === 'active'" @click="changeStatus(record)">{{ record.status === 'active' ? '停用' : '启用' }}</a-button></a-space></template>
        </template>
        <template #emptyText><a-empty description="暂无模型目录项，可创建模型" /></template>
      </a-table>
      <a-table v-else :data-source="events" :columns="usageColumns" :loading="loading" row-key="id"
        :scroll="{ x: 1550 }"
        :pagination="{ current: usageEventPage, pageSize: usageEventPageSize, total: usageEventTotal, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'], showTotal: usageEventTotalText }"
        @change="changeUsageEventPage">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'created_at'">{{ new Date(record.created_at).toLocaleString() }}</template>
          <template v-else-if="column.key === 'estimated_cost'">{{ record.estimated_cost ?? '未知' }}</template>
          <template v-else-if="column.key === 'source'"><a-tag :color="record.source === 'admin_reconciliation' ? 'purple' : 'blue'">{{ record.source === 'admin_reconciliation' ? '管理员核对' : '网关上报' }}</a-tag></template>
          <template v-else-if="column.key === 'usage_is_estimated'"><a-tag :color="record.usage_is_estimated ? 'orange' : 'green'">{{ record.usage_is_estimated ? '估算' : '实测' }}</a-tag></template>
          <template v-else-if="column.key === 'outcome'"><a-tag :color="record.outcome === 'succeeded' ? 'green' : 'red'">{{ record.outcome === 'succeeded' ? '成功' : '失败' }}</a-tag></template>
        </template>
        <template #emptyText><a-empty description="暂无模型调用记录" /></template>
      </a-table>
    </a-card>

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
.model-governance-page { display: grid; gap: 20px; }
.page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.page-heading h1 { margin: 5px 0 7px; font-size: clamp(25px, 3vw, 32px); letter-spacing: -.035em; }
.page-heading .subtitle { max-width: 760px; margin: 0; color: #7c8798; line-height: 1.65; }
.eyebrow { margin: 0; color: #766fe8; font-size: 11px; font-weight: 750; letter-spacing: .14em; }
.data-card { border-radius: 16px; }
.review-card { display: grid; gap: 16px; }
.review-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.review-heading h2 { display: flex; align-items: center; gap: 10px; margin: 0; font-size: 17px; }
.review-heading p { margin: 5px 0 0; color: #7c8798; font-size: 12px; }
.review-table { min-width: 0; }
.review-warning { margin-bottom: 14px; }
.review-request { overflow-wrap: anywhere; color: #697586; font-size: 12px; }
.table-toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.tenant-filter { width: 250px; flex: 0 0 auto; }
.table-hint { flex: 1; color: #7c8798; font-size: 12px; }
.usage-summary { grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
  .table-toolbar { align-items: stretch; flex-direction: column; }
  .tenant-filter { width: 100%; }
  .review-heading { align-items: flex-start; flex-direction: column; }
}
</style>
