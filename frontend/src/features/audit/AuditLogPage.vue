<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../../shared/services/api'

interface AuditEvent {
  id: string
  actor_user_id: string | null
  tenant_id: string | null
  action: string
  target_type: string
  target_id: string | null
  outcome: string
  source_ip: string | null
  details: unknown
  created_at: string
}

interface AuditSearchResult {
  items: AuditEvent[]
  limit: number
  offset: number
  total: number
  has_more: boolean
}

interface AuditFilters {
  action: string
  outcome: string | undefined
  target_type: string
  target_id: string
  actor_user_id: string
  tenant_id: string
  start_at: string
  end_at: string
}

const props = defineProps<{ active: boolean }>()
const events = ref<AuditEvent[]>([])
const filters = ref<AuditFilters>({
  action: '', outcome: undefined, target_type: '', target_id: '',
  actor_user_id: '', tenant_id: '', start_at: '', end_at: '',
})
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const errorText = ref('')
const selectedEvent = ref<AuditEvent | null>(null)
const detailsOpen = ref(false)
let requestSequence = 0

const columns = [
  { title: '发生时间', dataIndex: 'created_at', key: 'created_at', width: 190 },
  { title: '操作者 ID', dataIndex: 'actor_user_id', key: 'actor_user_id', width: 190, ellipsis: true },
  { title: '操作', dataIndex: 'action', key: 'action', width: 200, ellipsis: true },
  { title: '对象类型', dataIndex: 'target_type', key: 'target_type', width: 130, ellipsis: true },
  { title: '对象 ID', dataIndex: 'target_id', key: 'target_id', width: 190, ellipsis: true },
  { title: '结果', dataIndex: 'outcome', key: 'outcome', width: 100 },
  { title: '来源 IP', dataIndex: 'source_ip', key: 'source_ip', width: 140 },
  { title: '详情', dataIndex: 'details', key: 'details', width: 90, fixed: 'right' as const },
]

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function toUtcIso(value: string): string | undefined {
  if (!value) return undefined
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) throw new Error('日期时间格式无效')
  return date.toISOString()
}

async function loadEvents(): Promise<void> {
  if (!props.active) return
  const sequence = ++requestSequence
  loading.value = false
  errorText.value = ''
  const actorId = filters.value.actor_user_id.trim()
  const tenantId = filters.value.tenant_id.trim()
  if (actorId && !uuidPattern.test(actorId)) {
    errorText.value = '操作者 ID 需要填写有效的 UUID'
    return
  }
  if (tenantId && !uuidPattern.test(tenantId)) {
    errorText.value = '租户 ID 需要填写有效的 UUID'
    return
  }

  let startAt: string | undefined
  let endAt: string | undefined
  try {
    startAt = toUtcIso(filters.value.start_at)
    endAt = toUtcIso(filters.value.end_at)
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '日期时间格式无效'
    return
  }
  if (startAt && endAt && startAt >= endAt) {
    errorText.value = '结束时间必须晚于开始时间'
    return
  }

  loading.value = true
  errorText.value = ''
  try {
    const query = new URLSearchParams({ limit: String(pageSize.value), offset: String((page.value - 1) * pageSize.value) })
    const exactFilters: Array<[keyof AuditFilters, string | undefined]> = [
      ['action', filters.value.action.trim()],
      ['outcome', filters.value.outcome],
      ['target_type', filters.value.target_type.trim()],
      ['target_id', filters.value.target_id.trim()],
      ['actor_user_id', actorId],
      ['tenant_id', tenantId],
      ['start_at', startAt],
      ['end_at', endAt],
    ]
    for (const [key, value] of exactFilters) if (value) query.set(key, value)

    const result = await api<AuditSearchResult>(`/admin/audit/search?${query.toString()}`)
    if (sequence === requestSequence && props.active) {
      events.value = result.items
      total.value = result.total
    }
  } catch (error) {
    if (sequence !== requestSequence) return
    events.value = []
    total.value = 0
    errorText.value = error instanceof Error ? error.message : '读取审计记录失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function search(): void {
  page.value = 1
  void loadEvents()
}

function handleTableChange(pagination: { current?: number; pageSize?: number }): void {
  const nextPageSize = pagination.pageSize || pageSize.value
  if (nextPageSize !== pageSize.value) page.value = 1
  else page.value = pagination.current || 1
  pageSize.value = nextPageSize
  void loadEvents()
}

function formatTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function formatDetails(value: unknown): string {
  if (value === null || value === undefined) return '暂无详情'
  if (typeof value === 'string') return value
  try { return JSON.stringify(value, null, 2) } catch { return '[无法展示的记录]' }
}

function showDetails(event: AuditEvent): void {
  selectedEvent.value = event
  detailsOpen.value = true
}

watch(() => props.active, (active) => {
  if (active) void loadEvents()
}, { immediate: true })
</script>

<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">SECURITY &amp; COMPLIANCE</p>
      <h1>审计日志</h1>
      <p class="subtitle">追踪身份、访问策略和平台配置的管理操作；此页面只读。</p>
    </div>
  </div>

  <a-card class="data-card" :bordered="false">
    <div class="audit-filters">
      <a-input v-model:value="filters.action" allow-clear placeholder="操作编码（精确匹配）" :maxlength="120" @press-enter="search" />
      <a-select v-model:value="filters.outcome" allow-clear placeholder="全部结果">
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="denied">拒绝</a-select-option>
      </a-select>
      <a-input v-model:value="filters.target_type" allow-clear placeholder="对象类型（精确匹配）" :maxlength="80" @press-enter="search" />
      <a-input v-model:value="filters.target_id" allow-clear placeholder="对象 ID（精确匹配）" :maxlength="180" @press-enter="search" />
      <a-input v-model:value="filters.actor_user_id" allow-clear placeholder="操作者 UUID" @press-enter="search" />
      <a-input v-model:value="filters.tenant_id" allow-clear placeholder="租户 UUID" @press-enter="search" />
      <label class="audit-date-filter"><span>开始</span><input v-model="filters.start_at" type="datetime-local" aria-label="审计开始时间" /></label>
      <label class="audit-date-filter"><span>结束</span><input v-model="filters.end_at" type="datetime-local" aria-label="审计结束时间" /></label>
      <div class="audit-filter-actions">
        <a-button type="primary" :loading="loading" @click="search">查询</a-button>
        <a-button :loading="loading" @click="loadEvents">刷新</a-button>
      </div>
    </div>
    <div class="audit-toolbar-summary"><span class="table-hint">符合条件 {{ total }} 条；按时间倒序分页</span></div>
    <a-alert v-if="errorText" type="error" show-icon :message="errorText" class="audit-error" />
    <a-table
      :data-source="events"
      :columns="columns"
      :loading="loading"
      row-key="id"
      :scroll="{ x: 1580 }"
      :pagination="{ current: page, pageSize, total, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'], showTotal: (count: number) => `共 ${count} 条` }"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'created_at'">{{ formatTime(String(record.created_at || '')) }}</template>
        <template v-else-if="column.key === 'action'"><a-tag color="blue">{{ record.action || '—' }}</a-tag></template>
        <template v-else-if="column.key === 'outcome'">
          <a-tag :color="record.outcome === 'success' ? 'green' : record.outcome === 'denied' ? 'red' : 'default'">
            {{ record.outcome === 'success' ? '成功' : record.outcome === 'denied' ? '拒绝' : record.outcome || '未知' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'details'"><a-button type="link" size="small" @click="showDetails(record)">查看详情</a-button></template>
        <template v-else-if="record[column.dataIndex] === null || record[column.dataIndex] === undefined">—</template>
      </template>
      <template #emptyText><a-empty :description="total ? '当前页没有记录' : '没有匹配的审计记录'" /></template>
    </a-table>
    <p class="audit-retention-note">审计事件只读；结束时间按开区间查询。来源 IP 展示 API 接收到的地址，经过代理时可能是代理节点。</p>
  </a-card>

  <a-modal v-model:open="detailsOpen" title="审计事件详情" :footer="null" width="720px">
    <template v-if="selectedEvent">
      <a-descriptions bordered :column="1" size="small" class="audit-event-meta">
        <a-descriptions-item label="事件 ID">{{ selectedEvent.id }}</a-descriptions-item>
        <a-descriptions-item label="操作者 ID">{{ selectedEvent.actor_user_id || '—' }}</a-descriptions-item>
        <a-descriptions-item label="租户 ID">{{ selectedEvent.tenant_id || '—' }}</a-descriptions-item>
        <a-descriptions-item label="发生时间">{{ formatTime(selectedEvent.created_at) }}</a-descriptions-item>
        <a-descriptions-item label="操作 / 结果">{{ selectedEvent.action }} / {{ selectedEvent.outcome }}</a-descriptions-item>
        <a-descriptions-item label="目标">{{ selectedEvent.target_type }} / {{ selectedEvent.target_id || '—' }}</a-descriptions-item>
        <a-descriptions-item label="来源 IP">{{ selectedEvent.source_ip || '—' }}</a-descriptions-item>
      </a-descriptions>
      <h3 class="audit-detail-heading">变更摘要</h3>
      <pre class="audit-detail-json">{{ formatDetails(selectedEvent.details) }}</pre>
    </template>
  </a-modal>
</template>

<style scoped>
.audit-filters { display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 12px; align-items: center; }
.audit-toolbar-summary { display: flex; justify-content: space-between; align-items: center; margin: 14px 0; }
.audit-date-filter { display: grid; grid-template-columns: max-content minmax(0, 1fr); min-width: 0; align-items: center; gap: 8px; color: var(--subtle); font-size: 12px; }
.audit-date-filter > span { white-space: nowrap; }
.audit-date-filter input { min-width: 0; width: 100%; height: 32px; padding: 4px 8px; border: 1px solid var(--line); border-radius: 6px; color: var(--text); background: var(--surface); }
.audit-filter-actions { display: flex; gap: 8px; }
.audit-error { margin-bottom: 16px; }
.audit-retention-note { margin: 14px 0 0; color: var(--subtle); font-size: 12px; line-height: 1.6; }
.audit-event-meta { margin-top: 8px; overflow-wrap: anywhere; }
.audit-detail-heading { margin: 20px 0 8px; font-size: 14px; font-weight: 600; }
.audit-detail-json { max-height: 360px; overflow: auto; padding: 14px; border-radius: 8px; color: var(--text); background: var(--soft); font-size: 12px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 900px) { .audit-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .audit-filters { grid-template-columns: 1fr; } }
</style>
