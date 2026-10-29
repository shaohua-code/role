<script setup lang="ts">
import { ref, watch } from 'vue'
type DayjsLike = { isValid: () => boolean; toISOString: () => string }
import { api } from '@/api'
import AdminListPage from '@/components/AdminListPage.vue'
import AdminFilterPanel from '@/components/AdminFilterPanel.vue'
import AdminFilterField from '@/components/AdminFilterField.vue'
import { DownOutlined, FilterOutlined, UpOutlined } from '@/plugins/icons'

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
}

const props = defineProps<{ active: boolean }>()
// Wave 3 审计拆 Tab：登录与认证（auth.* 前缀）与管理操作分开浏览，服务端 action_prefix 过滤保证分页计数真实。
const auditTab = ref<'actions' | 'auth'>('actions')
const events = ref<AuditEvent[]>([])
const filters = ref<AuditFilters>({
  action: '', outcome: undefined, target_type: '', target_id: '',
  actor_user_id: '', tenant_id: '',
})
const startAt = ref<DayjsLike | null>(null)
const endAt = ref<DayjsLike | null>(null)
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

function toUtcIso(value: DayjsLike | null): string | undefined {
  if (!value) return undefined
  if (!value.isValid()) throw new Error('日期时间格式无效')
  return value.toISOString()
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

  let startIso: string | undefined
  let endIso: string | undefined
  try {
    startIso = toUtcIso(startAt.value)
    endIso = toUtcIso(endAt.value)
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '日期时间格式无效'
    return
  }
  if (startIso && endIso && startIso >= endIso) {
    errorText.value = '结束时间必须晚于开始时间'
    return
  }

  loading.value = true
  errorText.value = ''
  try {
    const query = new URLSearchParams({ limit: String(pageSize.value), offset: String((page.value - 1) * pageSize.value) })
    // 登录 Tab 固定按 auth. 前缀聚合；操作 Tab 不加前缀即全量管理事件。
    if (auditTab.value === 'auth') query.set('action_prefix', 'auth.')
    const exactFilters: Array<[string, string | undefined]> = [
      ['action', filters.value.action.trim()],
      ['outcome', filters.value.outcome],
      ['target_type', filters.value.target_type.trim()],
      ['target_id', filters.value.target_id.trim()],
      ['actor_user_id', actorId],
      ['tenant_id', tenantId],
      ['start_at', startIso],
      ['end_at', endIso],
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

// 切换 Tab 重置分页后按新类别重新查询。
function switchAuditTab(): void {
  page.value = 1
  void loadEvents()
}

// 筛选区默认折叠：占半屏高度的表单会挤压表格可用空间，导致内容区与表格出现双纵向滚动条。
const filtersOpen = ref(false)

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

// G23 深链预填：用户详情抽屉跳转 #/audit?actor=<uuid> 时自动切到「登录与认证」、预填操作者并触发查询。
function applyDeepLinkPrefill(): void {
  const hash = window.location.hash
  const queryIndex = hash.indexOf('?')
  if (queryIndex === -1) return
  const params = new URLSearchParams(hash.slice(queryIndex + 1))
  const actor = params.get('actor') || ''
  if (!actor || !uuidPattern.test(actor)) return
  auditTab.value = 'auth'
  filters.value = { ...filters.value, actor_user_id: actor }
  filtersOpen.value = true
  window.history.replaceState(null, '', hash.slice(0, queryIndex))
  void search()
}

watch(() => props.active, (active) => {
  if (active) {
    applyDeepLinkPrefill()
    void loadEvents()
  }
}, { immediate: true })
</script>

<template>
  <AdminListPage
    eyebrow="SECURITY & COMPLIANCE"
    title="审计日志"
    subtitle="按「管理操作 / 登录与认证」两个类别追踪平台事件；此页面只读。"
    :columns="columns"
    :data-source="events"
    :loading="loading"
    row-key="id"
    :scroll="{ x: 1580, y: 'calc(100vh - 430px)' }"
    :pagination="{ current: page, pageSize, total, showSizeChanger: true, pageSizeOptions: ['10', '20', '50', '100'], showTotal: (count: number) => `共 ${count} 条` }"
    :error-text="errorText"
    empty-emoji="🔍"
    :empty-text="total ? '当前页没有记录' : (auditTab === 'auth' ? '没有匹配的登录与认证记录' : '没有匹配的审计记录')"
    @table-change="handleTableChange"
  >
    <!-- 卡片顶部：登录/操作类别 Tab + 筛选开关行（默认收起）+ 筛选表单 -->
    <template #card-top>
      <a-tabs v-model:active-key="auditTab" class="mb-1" @change="switchAuditTab">
        <a-tab-pane key="actions" tab="管理操作" />
        <a-tab-pane key="auth" tab="登录与认证" />
      </a-tabs>
      <div class="mb-3 flex min-w-0 flex-wrap items-center gap-3">
        <!-- flex+gap 修正裸文本节点不触发 antd 图标间距、svg 基线偏移导致的图标文字错位 -->
        <a-button class="flex items-center gap-2" @click="filtersOpen = !filtersOpen">
          <FilterOutlined />
          {{ filtersOpen ? '收起筛选' : '筛选条件' }}
          <UpOutlined v-if="filtersOpen" />
          <DownOutlined v-else />
        </a-button>
        <span class="min-w-0 flex-1 truncate text-xs text-[var(--color-text-muted)]">符合条件 {{ total }} 条；按时间倒序分页</span>
      </div>
      <div v-show="filtersOpen" class="audit-filters-wrap">
        <AdminFilterPanel>
          <AdminFilterField label="操作编码"><a-input v-model:value="filters.action" allow-clear placeholder="精确匹配" :maxlength="120" @press-enter="search" /></AdminFilterField>
          <AdminFilterField label="结果">
            <a-select v-model:value="filters.outcome" allow-clear placeholder="全部结果">
              <a-select-option value="success">成功</a-select-option>
              <a-select-option value="denied">拒绝</a-select-option>
            </a-select>
          </AdminFilterField>
          <AdminFilterField label="对象类型"><a-input v-model:value="filters.target_type" allow-clear placeholder="精确匹配" :maxlength="80" @press-enter="search" /></AdminFilterField>
          <AdminFilterField label="对象 ID"><a-input v-model:value="filters.target_id" allow-clear placeholder="精确匹配" :maxlength="180" @press-enter="search" /></AdminFilterField>
          <AdminFilterField label="操作者 UUID"><a-input v-model:value="filters.actor_user_id" allow-clear placeholder="按回车查询" @press-enter="search" /></AdminFilterField>
          <AdminFilterField label="租户 UUID"><a-input v-model:value="filters.tenant_id" allow-clear placeholder="按回车查询" @press-enter="search" /></AdminFilterField>
          <AdminFilterField label="开始时间"><a-date-picker v-model:value="startAt" show-time placeholder="开始时间" class="w-full" aria-label="审计开始时间" /></AdminFilterField>
          <AdminFilterField label="结束时间"><a-date-picker v-model:value="endAt" show-time placeholder="结束时间" class="w-full" aria-label="审计结束时间" /></AdminFilterField>
          <template #actions>
            <a-button type="primary" :loading="loading" @click="search">查询</a-button>
            <a-button :loading="loading" @click="loadEvents">刷新</a-button>
          </template>
        </AdminFilterPanel>
      </div>
    </template>
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'created_at'">{{ formatTime(String(record.created_at || '')) }}</template>
      <!-- 操作类型用中性 mono tag（P350 黑白灰：蓝色块破坏灰阶体系），结果列保留语义色 -->
      <template v-else-if="column.key === 'action'"><a-tag class="font-mono">{{ record.action || '—' }}</a-tag></template>
      <template v-else-if="column.key === 'outcome'">
        <a-tag :color="record.outcome === 'success' ? 'green' : record.outcome === 'denied' ? 'red' : 'default'">
          {{ record.outcome === 'success' ? '成功' : record.outcome === 'denied' ? '拒绝' : record.outcome || '未知' }}
        </a-tag>
      </template>
      <template v-else-if="column.key === 'details'"><a-button type="link" size="small" @click="showDetails(record)">查看详情</a-button></template>
      <template v-else-if="record[column.dataIndex] === null || record[column.dataIndex] === undefined">—</template>
    </template>
    <!-- 卡片底部：只读说明 -->
    <template #card-bottom>
      <p class="audit-retention-note">审计事件只读；结束时间按开区间查询。来源 IP 展示 API 接收到的地址，经过代理时可能是代理节点。</p>
    </template>
  </AdminListPage>

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
.audit-retention-note { margin: 14px 0 0; color: var(--subtle); font-size: 12px; line-height: 1.6; }
.audit-event-meta { margin-top: 8px; overflow-wrap: anywhere; }
.audit-detail-heading { margin: 20px 0 8px; font-size: 14px; font-weight: 600; }
.audit-detail-json { max-height: 360px; overflow: auto; padding: 14px; border-radius: 8px; color: var(--text); background: var(--soft); font-size: 12px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
