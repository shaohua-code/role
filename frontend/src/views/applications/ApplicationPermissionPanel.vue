<script setup lang="ts">
// 应用权限编码面板：列表 / 搜索 / 登记 / 启停。抽自 ApplicationPermissionDrawer，
// 供应用管理抽屉与应用工作台「权限编码」Tab 两处复用，避免重复实现。
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHas, getCachedCapabilities } from '@/api/capabilities'
import AdminSearchField from '@/components/AdminSearchField.vue'

interface ApplicationRef {
  id: string
  name: string
  permission_namespace: string
  can_manage?: boolean
}

interface PermissionRecord {
  id: string
  code: string
  catalog_namespace: string
  resource_type: string
  scope: string
  description: string | null
  status: 'active' | 'disabled'
  assigned_role_count: number
}

const props = withDefaults(defineProps<{
  application: ApplicationRef | null
  apiPrefix?: string
  // 外层容器可见时才拉取数据（抽屉 open / 工作台页面激活）
  active?: boolean
}>(), {
  apiPrefix: '/admin',
  active: true,
})

const emit = defineEmits<{ changed: [], stats: [count: number] }>()

const permissions = ref<PermissionRecord[]>([])
const searchText = ref('')
const loading = ref(false)
const createOpen = ref(false)
const creating = ref(false)
const changingPermissionId = ref('')
const form = reactive({ code: '', resource_type: '', scope: '', description: '' })
let requestSequence = 0

// 绿场 §6.5：权限登记/停用是 rbac.permission.manage（仅 L1）；L2 应用管理员只读目录。
const canManageCatalog = computed(() => Boolean(getCachedCapabilities()?.platform_admin) && cachedHas('rbac.permission.manage'))

function applicationPath(path: string): string {
  return `${props.apiPrefix}${path}`
}

const columns = [
  { title: '权限编码', dataIndex: 'code', key: 'code', width: 220 },
  { title: '资源类型', dataIndex: 'resource_type', key: 'resource_type', width: 120 },
  { title: 'Scope', dataIndex: 'scope', key: 'scope', width: 100 },
  { title: '说明', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '已授角色', dataIndex: 'assigned_role_count', key: 'assigned_role_count', width: 90 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 100, fixed: 'right' as const },
]

const filteredPermissions = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return permissions.value
  return permissions.value.filter(item =>
    item.code.toLowerCase().includes(keyword)
    || item.resource_type.toLowerCase().includes(keyword)
    || (item.description || '').toLowerCase().includes(keyword),
  )
})

async function loadPermissions(): Promise<void> {
  if (!props.application) {
    permissions.value = []
    emit('stats', 0)
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  try {
    const rows = await api<PermissionRecord[]>(
      applicationPath(`/applications/${props.application.id}/permissions`),
    )
    if (sequence !== requestSequence) return
    permissions.value = rows
    // 上报权限码数给父级概览统计条（工作台场景）
    emit('stats', rows.length)
  } catch (error) {
    if (sequence !== requestSequence) return
    message.error(error instanceof Error ? error.message : '读取应用权限编码失败')
    permissions.value = []
    emit('stats', 0)
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function openCreate(): void {
  form.code = ''
  form.resource_type = ''
  form.scope = ''
  form.description = ''
  createOpen.value = true
}

async function createPermission(): Promise<void> {
  if (!props.application) return
  creating.value = true
  try {
    await api(applicationPath(`/applications/${props.application.id}/permissions`), {
      method: 'POST',
      body: JSON.stringify({
        code: form.code.trim(),
        resource_type: form.resource_type.trim(),
        scope: form.scope.trim(),
        description: form.description.trim() || null,
      }),
    })
    message.success('权限项已创建')
    createOpen.value = false
    await loadPermissions()
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建权限项失败')
  } finally {
    creating.value = false
  }
}

function changeStatus(permission: PermissionRecord): void {
  const nextStatus = permission.status === 'active' ? 'disabled' : 'active'
  Modal.confirm({
    title: nextStatus === 'disabled' ? '停用权限项？' : '恢复权限项？',
    content: nextStatus === 'disabled'
      ? '停用后在线判权立即拒绝该码，但已授予角色的历史关系会保留。'
      : '恢复后已保留的角色授权会重新生效。',
    okText: nextStatus === 'disabled' ? '停用' : '恢复',
    cancelText: '取消',
    okButtonProps: { danger: nextStatus === 'disabled' },
    onOk: async () => {
      changingPermissionId.value = permission.id
      try {
        await api(`/admin/permissions/${permission.id}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ expected_status: permission.status, status: nextStatus }),
        })
        message.success(nextStatus === 'disabled' ? '权限项已停用' : '权限项已恢复')
        await loadPermissions()
        emit('changed')
      } catch (error) {
        message.error(error instanceof Error ? error.message : '更新权限状态失败')
      } finally {
        changingPermissionId.value = ''
      }
    },
  })
}

// immediate：抽屉 destroy-on-close 与工作台 Tab 挂载时 active 已为 true，必须补首次加载。
watch([() => props.active, () => props.application?.id], ([active]) => {
  if (active) loadPermissions()
  else permissions.value = []
}, { immediate: true })
</script>

<template>
  <div class="flex flex-col gap-4">
    <a-alert
      v-if="application"
      type="info"
      show-icon
      :message="`命名空间：${application.permission_namespace}（权限编码须以该前缀登记）`"
    />
    <div class="flex flex-wrap items-center gap-3">
      <AdminSearchField v-model="searchText" placeholder="搜索编码、资源类型或说明" class="min-w-[200px] flex-1" />
      <a-button v-if="canManageCatalog" type="primary" @click="openCreate">新建权限</a-button>
      <a-button :loading="loading" @click="loadPermissions">刷新</a-button>
    </div>
    <a-table
      :columns="columns"
      :data-source="filteredPermissions"
      :loading="loading"
      row-key="id"
      size="small"
      :pagination="{ pageSize: 12, showSizeChanger: false }"
      :scroll="{ x: 640 }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'success' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-button
            v-if="canManageCatalog"
            type="link"
            size="small"
            :loading="changingPermissionId === record.id"
            @click="changeStatus(record)"
          >
            {{ record.status === 'active' ? '停用' : '恢复' }}
          </a-button>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="createOpen" title="登记应用权限" ok-text="创建" cancel-text="取消" :confirm-loading="creating" @ok="createPermission">
      <a-form layout="vertical">
        <a-form-item label="命名空间">
          <a-input :value="application?.permission_namespace" disabled />
        </a-form-item>
        <a-form-item label="权限编码" required>
          <a-input v-model:value="form.code" :placeholder="`${application?.permission_namespace}.resource.action`" :maxlength="180" />
        </a-form-item>
        <a-form-item label="资源类型" required>
          <a-input v-model:value="form.resource_type" :maxlength="100" />
        </a-form-item>
        <a-form-item label="操作 Scope" required>
          <a-input v-model:value="form.scope" :maxlength="80" />
        </a-form-item>
        <a-form-item label="说明">
          <a-textarea v-model:value="form.description" :rows="2" :maxlength="500" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
