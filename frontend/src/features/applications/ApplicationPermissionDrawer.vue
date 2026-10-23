<script setup lang="ts">
import { computed, reactive, ref, watch, withDefaults } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '../../shared/services/api'
import AdminSearchField from '../../shared/components/AdminSearchField.vue'

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

const open = defineModel<boolean>('open', { default: false })

const props = withDefaults(defineProps<{
  application: ApplicationRef | null
  apiPrefix?: string
}>(), {
  apiPrefix: '/admin',
})

const emit = defineEmits<{ changed: [] }>()

const permissions = ref<PermissionRecord[]>([])
const searchText = ref('')
const loading = ref(false)
const createOpen = ref(false)
const creating = ref(false)
const changingPermissionId = ref('')
const form = reactive({ code: '', resource_type: '', scope: '', description: '' })
let requestSequence = 0

const canManage = computed(() => props.apiPrefix === '/admin' || props.application?.can_manage === true)

const filteredPermissions = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  if (!query) return permissions.value
  return permissions.value.filter(permission =>
    `${permission.code} ${permission.resource_type} ${permission.scope} ${permission.description || ''}`
      .toLocaleLowerCase().includes(query),
  )
})

const columns = [
  { title: '权限编码', dataIndex: 'code', key: 'code', width: 240, ellipsis: true },
  { title: '资源类型', dataIndex: 'resource_type', key: 'resource_type', width: 120 },
  { title: 'Scope', dataIndex: 'scope', key: 'scope', width: 100 },
  { title: '说明', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '关联角色', dataIndex: 'assigned_role_count', key: 'assigned_role_count', width: 100 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 90 },
]

function applicationPath(path: string): string {
  return `${props.apiPrefix || '/admin'}${path}`
}

async function loadPermissions(): Promise<void> {
  if (!open.value || !props.application) return
  const sequence = ++requestSequence
  loading.value = true
  try {
    const result = await api<PermissionRecord[]>(
      applicationPath(`/applications/${props.application.id}/permissions`),
    )
    if (sequence === requestSequence) permissions.value = result
  } catch (error) {
    if (sequence === requestSequence) {
      permissions.value = []
      message.error(error instanceof Error ? error.message : '读取应用权限目录失败')
    }
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

function validateForm(): boolean {
  const ns = props.application?.permission_namespace || ''
  const code = form.code.trim()
  if (!code || code.length > 180) {
    message.error('权限编码必填且不能超过 180 个字符')
    return false
  }
  if (!code.startsWith(`${ns}.`) && code !== ns) {
    message.error(`权限编码须以「${ns}.」为前缀`)
    return false
  }
  if (!form.resource_type.trim() || form.resource_type.trim().length > 100) {
    message.error('资源类型必填且不能超过 100 个字符')
    return false
  }
  if (!form.scope.trim() || form.scope.trim().length > 80) {
    message.error('操作 Scope 必填且不能超过 80 个字符')
    return false
  }
  if (form.description.trim().length > 500) {
    message.error('说明不能超过 500 个字符')
    return false
  }
  return true
}

async function createPermission(): Promise<void> {
  if (!props.application || !validateForm()) return
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

watch([open, () => props.application?.id], () => {
  if (open.value) loadPermissions()
  else permissions.value = []
})
</script>

<template>
  <a-drawer
    v-model:open="open"
    :title="application ? `${application.name} · 权限项` : '应用权限项'"
    width="720"
    destroy-on-close
  >
    <a-alert
      v-if="application"
      class="mb-4"
      type="info"
      show-icon
      :message="`命名空间：${application.permission_namespace}（权限编码须以该前缀登记）`"
    />
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <AdminSearchField v-model="searchText" placeholder="搜索编码、资源类型或说明" class="min-w-[200px] flex-1" />
      <a-button v-if="canManage" type="primary" @click="openCreate">新建权限</a-button>
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
            v-if="canManage && props.apiPrefix === '/admin'"
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
  </a-drawer>
</template>
