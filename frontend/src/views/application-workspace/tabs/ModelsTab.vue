<script setup lang="ts">
// 应用工作台「模型」Tab（模型三级分发第三级）：
// 展示本租户收到的平台模型清单；持 button.models.distribute 的租户级管理员
// 可把模型下发 / 回收给本应用（回收为软失效，业务端 my-models 立即不可见）。
// 应用管理员（L2）只读——后端写接口按节点 min_scope=tenant 收口，前端同码隐藏按钮。
import { computed, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { hasButton, TENANT_ADMIN_API_PREFIX } from '@/api/capabilities'
import { formatCapabilities } from '@/utils/modelCapabilities'
import AdminTable from '@/components/AdminTable.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'

interface ApplicationRef {
  id: string
  name: string
  permission_namespace: string
  can_manage?: boolean
}

interface ReceivedModel {
  id: string; key: string; provider: string; model_name: string; display_name: string
  capabilities: string[]; rpm_limit?: number | null; tpm_limit?: number | null
  input_cost_per_million?: number | null; output_cost_per_million?: number | null
  status: 'active' | 'disabled'
}

interface ModelsPayload {
  application_id: string; tenant_id: string
  received: ReceivedModel[]; granted_model_ids: string[]
}

const props = withDefaults(defineProps<{
  application: ApplicationRef | null
  active?: boolean
}>(), {
  active: true,
})

const emit = defineEmits<{ changed: [], stats: [count: number] }>()

const received = ref<ReceivedModel[]>([])
const grantedIds = ref<Set<string>>(new Set())
const loading = ref(false)
let requestSequence = 0

// 下发 / 回收认 button.models.distribute（节点下限租户级；应用级不可见）。
const canDistribute = computed(() => hasButton('button.models.distribute'))
const isGranted = (model: ReceivedModel): boolean => grantedIds.value.has(model.id)

const modelColumns = [
  { title: '模型', dataIndex: 'display_name', key: 'display_name', width: 180, ellipsis: true },
  { title: '模型标识', dataIndex: 'key', key: 'key', width: 150, ellipsis: true },
  { title: '提供方', dataIndex: 'provider', key: 'provider', width: 130 },
  { title: '能力', dataIndex: 'capabilities', key: 'capabilities', width: 130, ellipsis: true },
  { title: 'RPM', dataIndex: 'rpm_limit', key: 'rpm_limit', width: 80 },
  { title: 'TPM', dataIndex: 'tpm_limit', key: 'tpm_limit', width: 90 },
  { title: '输入价格/百万', dataIndex: 'input_cost_per_million', key: 'input_cost_per_million', width: 120 },
  { title: '输出价格/百万', dataIndex: 'output_cost_per_million', key: 'output_cost_per_million', width: 120 },
  { title: '本应用', dataIndex: 'granted', key: 'granted', width: 100 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 100, fixed: 'right' as const },
]
const modelTableScrollWidth = modelColumns.reduce((width, column) => width + column.width, 0)

function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '未知'
  return String(value)
}

async function load(): Promise<void> {
  if (!props.application) {
    received.value = []
    grantedIds.value = new Set()
    emit('stats', 0)
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  try {
    const payload = await api<ModelsPayload>(
      `${TENANT_ADMIN_API_PREFIX}/applications/${props.application.id}/models`)
    if (sequence !== requestSequence) return
    received.value = payload.received
    grantedIds.value = new Set(payload.granted_model_ids)
    emit('stats', payload.received.length)
  } catch (error) {
    if (sequence !== requestSequence) return
    received.value = []
    grantedIds.value = new Set()
    message.error(error instanceof Error ? error.message : '读取应用模型清单失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function grantModel(model: ReceivedModel): void {
  if (!props.application) return
  const run = async (): Promise<void> => {
    try {
      await api(`${TENANT_ADMIN_API_PREFIX}/applications/${props.application!.id}/models`, {
        method: 'POST', body: JSON.stringify({ model_id: model.id }),
      })
      message.success(`已把「${model.display_name}」下发给本应用`)
      await load()
      emit('changed')
    } catch (error) { message.error(error instanceof Error ? error.message : '下发模型失败') }
  }
  void run()
}

function revokeModel(model: ReceivedModel): void {
  if (!props.application) return
  Modal.confirm({
    title: `回收本应用的「${model.display_name}」？`,
    content: '回收后该模型立即从业务端的可见模型清单消失（软失效，可重新下发恢复）；用量账目保留。',
    okText: '确认回收', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`${TENANT_ADMIN_API_PREFIX}/applications/${props.application!.id}/models/${model.id}`, {
          method: 'DELETE',
        })
        message.success('已回收该模型的下发')
        await load()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '回收模型失败') }
    },
  })
}

watch([() => props.active, () => props.application?.id], ([active]) => {
  if (active) void load()
}, { immediate: true })
</script>

<template>
  <div class="flex min-w-0 flex-col gap-3">
    <p class="m-0 text-xs text-[var(--color-text-secondary)]">
      本租户已收到 {{ received.length }} 个平台模型；勾选下发给本应用后，业务端登录用户即可在应用内使用。回收为软失效，可重新下发。
    </p>
    <a-card :bordered="false" class="min-w-0">
      <AdminTable
        :columns="modelColumns"
        :data-source="received"
        :loading="loading"
        row-key="id"
        :scroll="{ x: modelTableScrollWidth, y: 'calc(max(320px, 100vh - 480px))' }"
        :pagination="{ pageSize: 10, showSizeChanger: true }"
        empty-emoji="🧠"
        empty-text="租户尚未收到平台下发的模型，请联系平台管理员"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'capabilities'">{{ formatCapabilities(record.capabilities) }}</template>
          <template v-else-if="column.key === 'input_cost_per_million'">{{ formatPrice(record.input_cost_per_million) }}</template>
          <template v-else-if="column.key === 'output_cost_per_million'">{{ formatPrice(record.output_cost_per_million) }}</template>
          <template v-else-if="column.key === 'granted'">
            <a-tag :color="isGranted(record) ? 'green' : 'default'">{{ isGranted(record) ? '已下发' : '未下发' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button v-if="canDistribute && !isGranted(record)" type="link" size="small" @click="grantModel(record)">下发</a-button>
            <a-button v-else-if="canDistribute" type="link" size="small" danger @click="revokeModel(record)">回收</a-button>
            <span v-else class="text-xs text-[var(--color-text-muted)]">只读</span>
          </template>
        </template>
      </AdminTable>
    </a-card>
  </div>
</template>
