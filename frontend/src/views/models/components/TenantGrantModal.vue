<script setup lang="ts">
// 下发租户管理弹窗（超管，button.models.manage）：新增下发 + 关系列表（软失效语义）。
// API 契约与原页内实现一致：POST/DELETE /admin/models/{id}/tenant-grants；
// 回收为软失效并级联失效该租户下全部应用的本模型下发，重新下发即恢复。
import { computed, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { ADMIN_API_PREFIX } from '@/api/capabilities'
import StatusDot from './StatusDot.vue'

// 结构化最小契约：与页面 ModelRecord / Tenant 字段兼容（TS 结构化类型，避免循环依赖）。
interface GrantTarget {
  id: string
  key: string
  display_name: string
  status: 'active' | 'disabled'
}
interface TenantOption {
  id: string
  name: string
  slug: string
  status: string
}
interface TenantGrantRow {
  model_id: string
  tenant_id: string
  tenant_name: string
  status: 'active' | 'revoked'
  granted_at: string
  revoked_at?: string | null
}

const open = defineModel<boolean>('open', { default: false })
const props = withDefaults(defineProps<{
  /** 下发目标模型；null 时不加载 */
  model?: GrantTarget | null
  /** 页面已加载的租户目录（用于可下发租户下拉） */
  tenants?: TenantOption[]
}>(), {
  model: null,
  tenants: () => [],
})
const emit = defineEmits<{ changed: [] }>()

const grantRows = ref<TenantGrantRow[]>([])
const grantRowsLoading = ref(false)
const grantTenantId = ref<string | undefined>(undefined)
const granting = ref(false)

// 下发关系表列。
const grantColumns = [
  { title: '租户', dataIndex: 'tenant_name', key: 'tenant_name', width: 160, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 96 },
  { title: '下发时间', dataIndex: 'granted_at', key: 'granted_at', width: 170 },
  { title: '回收时间', dataIndex: 'revoked_at', key: 'revoked_at', width: 170 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 90 },
]

// 可选租户：排除平台租户（目录宿主自身）与已 active 下发的租户（重复下发无意义）。
const grantableTenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.slug !== 'platform' && tenant.status === 'active')
  .filter(tenant => !grantRows.value.some(row => row.tenant_id === tenant.id && row.status === 'active'))
  .map(tenant => ({ value: tenant.id, label: tenant.name })))

watch([open, () => props.model], ([isOpen]) => {
  if (isOpen && props.model) {
    grantTenantId.value = undefined
    grantRows.value = []
    void loadTenantGrants()
  }
})

async function loadTenantGrants(): Promise<void> {
  if (!props.model) return
  grantRowsLoading.value = true
  try {
    grantRows.value = await api<TenantGrantRow[]>(
      `${ADMIN_API_PREFIX}/models/${props.model.id}/tenant-grants`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取下发关系失败')
  } finally { grantRowsLoading.value = false }
}

async function grantToTenant(): Promise<void> {
  if (!props.model || !grantTenantId.value) {
    message.warning('请选择要下发的租户')
    return
  }
  granting.value = true
  try {
    await api(`${ADMIN_API_PREFIX}/models/${props.model.id}/tenant-grants`, {
      method: 'POST', body: JSON.stringify({ tenant_id: grantTenantId.value }),
    })
    message.success('模型已下发给租户')
    grantTenantId.value = undefined
    await loadTenantGrants()
    emit('changed')
  } catch (error) { message.error(error instanceof Error ? error.message : '下发模型失败') }
  finally { granting.value = false }
}

function revokeFromTenant(row: TenantGrantRow): void {
  Modal.confirm({
    title: `回收租户“${row.tenant_name}”的模型？`,
    content: '回收为软失效（可重新下发恢复）；该租户下全部应用的本模型下发会一并失效，业务端模型清单立即不可见。',
    okText: '确认回收', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`${ADMIN_API_PREFIX}/models/${row.model_id}/tenant-grants/${row.tenant_id}`, { method: 'DELETE' })
        message.success('已回收该租户的模型下发')
        await loadTenantGrants()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '回收模型下发失败') }
    },
  })
}
</script>

<template>
  <a-modal v-model:open="open" :title="`下发租户：${model?.display_name || ''}`" :width="720" :footer="null">
    <!-- 目标模型摘要：显示名 + 标识 + 状态点 -->
    <p class="grant-summary">
      <span class="font-medium text-[var(--color-text-primary)]">{{ model?.display_name }}</span>
      <span class="grant-key">{{ model?.key }}</span>
      <StatusDot
        v-if="model"
        :tone="model.status === 'active' ? 'ok' : 'off'"
        :text="model.status === 'active' ? '启用' : '停用'"
      />
    </p>

    <!-- 新增下发：选择租户 + 下发按钮（模型停用时禁用） -->
    <div class="mb-4 flex items-center gap-2">
      <a-select
        v-model:value="grantTenantId"
        class="min-w-0 flex-1"
        aria-label="选择要下发的租户"
        placeholder="选择要下发的租户"
        allow-clear
        :disabled="model?.status !== 'active'"
        :options="grantableTenantOptions"
      />
      <a-button
        type="primary"
        :loading="granting"
        :disabled="!grantTenantId || model?.status !== 'active'"
        @click="grantToTenant"
      >下发</a-button>
    </div>
    <a-alert
      v-if="model && model.status !== 'active'"
      class="mb-3" type="warning" show-icon
      message="模型已停用：全链路不可见；启用后才能重新下发。"
    />

    <a-table
      :data-source="grantRows"
      :columns="grantColumns"
      :loading="grantRowsLoading"
      row-key="tenant_id"
      :pagination="false"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <StatusDot :tone="record.status === 'active' ? 'ok' : 'off'" :text="record.status === 'active' ? '生效中' : '已回收'" />
        </template>
        <template v-else-if="column.key === 'granted_at'">
          <span class="font-mono text-xs">{{ record.granted_at ? new Date(record.granted_at).toLocaleString() : '—' }}</span>
        </template>
        <template v-else-if="column.key === 'revoked_at'">
          <span class="font-mono text-xs">{{ record.revoked_at ? new Date(record.revoked_at).toLocaleString() : '—' }}</span>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-button v-if="record.status === 'active'" type="link" size="small" danger @click="revokeFromTenant(record)">回收</a-button>
          <span v-else class="text-xs text-[var(--color-text-muted)]">—</span>
        </template>
      </template>
      <template #emptyText>
        <div class="flex flex-col items-center gap-2 px-4 py-6 text-center">
          <span class="flex h-10 w-10 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--color-bg-subtle)] text-lg opacity-90 ring-1 ring-[var(--color-border)] grayscale" aria-hidden="true">🏷️</span>
          <p class="m-0 text-sm text-[var(--color-text-muted)]">尚未下发给任何租户</p>
        </div>
      </template>
    </a-table>
    <p class="grant-note">回收为软失效：该租户下全部应用的本模型下发一并失效；重新下发即恢复租户级可见（应用级需租户重新下发）。</p>
  </a-modal>
</template>

<style scoped>
.grant-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0 0 12px;
  font-size: 13px;
}
.grant-key {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--color-text-muted);
}
.grant-note {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-text-muted);
}
</style>
