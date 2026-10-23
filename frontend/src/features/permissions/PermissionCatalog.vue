<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '../../shared/services/api'
import AdminPageHeader from '../../shared/components/AdminPageHeader.vue'
import AdminTableToolbar from '../../shared/components/AdminTableToolbar.vue'
import AdminSearchField from '../../shared/components/AdminSearchField.vue'

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

const props = defineProps<{ active: boolean }>()
const permissions = ref<PermissionRecord[]>([])
const searchText = ref('')
const namespaceFilter = ref('')
const loading = ref(false)
const errorText = ref('')
const createOpen = ref(false)
const creating = ref(false)
const changingPermissionId = ref('')
const form = reactive({ code: '', resource_type: '', scope: '', description: '' })
let requestSequence = 0

const namespaceOptions = computed(() => {
  const values = new Set(permissions.value.map(item => item.catalog_namespace))
  return [{ value: '', label: '全部分组' }, ...[...values].sort().map(value => ({ value, label: value }))]
})

const filteredPermissions = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return permissions.value.filter(permission => {
    if (namespaceFilter.value && permission.catalog_namespace !== namespaceFilter.value) return false
    if (!query) return true
    return `${permission.code} ${permission.catalog_namespace} ${permission.resource_type} ${permission.scope} ${permission.description || ''}`
      .toLocaleLowerCase().includes(query)
  })
})

const columns = [
  { title: '命名空间', dataIndex: 'catalog_namespace', key: 'catalog_namespace', width: 120 },
  { title: '权限编码', dataIndex: 'code', key: 'code', width: 260, ellipsis: true },
  { title: '资源类型', dataIndex: 'resource_type', key: 'resource_type', width: 180 },
  { title: '操作 Scope', dataIndex: 'scope', key: 'scope', width: 160 },
  { title: '说明', dataIndex: 'description', key: 'description', width: 320, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '关联角色', dataIndex: 'assigned_role_count', key: 'assigned_role_count', width: 110 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 110, fixed: 'right' as const },
]

async function loadPermissions(): Promise<void> {
  if (!props.active) return
  const sequence = ++requestSequence
  loading.value = true
  errorText.value = ''
  try {
    const result = await api<PermissionRecord[]>('/admin/permissions')
    if (sequence === requestSequence && props.active) permissions.value = result
  } catch (error) {
    if (sequence !== requestSequence) return
    permissions.value = []
    errorText.value = error instanceof Error ? error.message : '读取权限目录失败'
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
  const fields: [string, string, number][] = [
    ['权限编码', form.code.trim(), 180],
    ['资源类型', form.resource_type.trim(), 100],
    ['操作 Scope', form.scope.trim(), 80],
  ]
  const invalid = fields.find(([label, value, max]) => !value || value.length > max)
  if (invalid) {
    message.error(`${invalid[0]}必填且不能超过 ${invalid[2]} 个字符`)
    return false
  }
  if (form.code.trim().length < 3) {
    message.error('权限编码至少需要 3 个字符')
    return false
  }
  if (form.description.trim().length > 500) {
    message.error('说明不能超过 500 个字符')
    return false
  }
  return true
}

async function createPermission(): Promise<void> {
  if (!validateForm()) return
  creating.value = true
  try {
    await api('/admin/permissions', {
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
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建权限项失败')
  } finally {
    creating.value = false
  }
}

function changeStatus(permission: PermissionRecord): void {
  const nextStatus = permission.status === 'active' ? 'disabled' : 'active'
  const reactivating = nextStatus === 'active'
  Modal.confirm({
    title: reactivating ? '恢复该权限编码？' : '停用该权限编码？',
    content: reactivating
      ? `恢复后，该编码保留的历史角色授权将重新生效（关联 ${permission.assigned_role_count} 个角色）。如不希望恢复这些授权，请先在角色管理中撤销。`
      : `停用会立即让所有使用该编码的在线授权判定失败；${permission.assigned_role_count} 个角色的既有授权与数据范围会保留。`,
    okText: reactivating ? '恢复权限' : '确认停用',
    okType: reactivating ? 'primary' : 'danger',
    cancelText: '取消',
    onOk: async () => {
      changingPermissionId.value = permission.id
      try {
        await api(`/admin/permissions/${permission.id}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ expected_status: permission.status, status: nextStatus }),
        })
        message.success(reactivating ? '权限已恢复；历史授权已重新生效' : '权限已停用；历史授权关系已保留')
        await loadPermissions()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '更新权限状态失败')
      } finally {
        changingPermissionId.value = ''
      }
    },
  })
}

watch(() => props.active, active => {
  if (active) void loadPermissions()
}, { immediate: true })
</script>

<template>
  <AdminPageHeader
    eyebrow="PERMISSION REGISTRY"
    title="权限目录"
    subtitle="平台全览各产品命名空间下的稳定权限编码；业务权限的日常维护请在「应用管理 → 权限项」中按应用命名空间登记。"
  />

  <a-card class="data-card" :bordered="false">
    <a-alert
      class="permission-hint"
      type="info"
      show-icon
      message="业务权限与 OAuth 应用通过 permission_namespace 绑定。新建业务权限请进入对应应用的「权限项」抽屉；此页用于全览与 platform/运维登记。"
    />
    <AdminTableToolbar :hint="`${filteredPermissions.length} 条权限 · 最多读取 1000 条`">
      <a-select v-model:value="namespaceFilter" :options="namespaceOptions" class="permission-namespace-filter" placeholder="命名空间" />
      <AdminSearchField v-model="searchText" placeholder="搜索编码、资源、Scope 或说明" :submit-on-clear="false" />
      <template #actions>
        <a-button type="link" @click="openCreate">平台直接登记</a-button>
        <a-button :loading="loading" @click="loadPermissions">刷新</a-button>
      </template>
    </AdminTableToolbar>
    <a-alert v-if="errorText" type="error" show-icon :message="errorText" class="permission-error" />
    <a-table :data-source="filteredPermissions" :columns="columns" :loading="loading" row-key="id" :scroll="{ x: 920 }" :pagination="{ pageSize: 10, showSizeChanger: true }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'assigned_role_count'">{{ record.assigned_role_count }} 个角色</template>
        <template v-else-if="column.key === 'actions'">
          <a-button size="small" :danger="record.status === 'active'" :loading="changingPermissionId === record.id" :disabled="Boolean(changingPermissionId)" @click="changeStatus(record)">
            {{ record.status === 'active' ? '停用' : '恢复' }}
          </a-button>
        </template>
      </template>
      <template #emptyText><a-empty :description="searchText || namespaceFilter ? '没有匹配的权限项' : '暂无权限项'" /></template>
    </a-table>
    <p class="permission-note">权限编码应保持稳定，不能编辑或删除。停用会保留既有角色授权并让服务端判权默认拒绝；恢复会重新激活历史授权。菜单显示本身不构成服务端授权。</p>
  </a-card>

  <a-modal v-model:open="createOpen" title="平台登记权限项（运维）" ok-text="创建" cancel-text="取消" :confirm-loading="creating" @ok="createPermission">
    <a-form layout="vertical" class="create-form">
      <a-form-item label="权限编码" required help="建议使用 product.resource.action 格式；至少 3 个字符，最长 180 个字符。">
        <a-input v-model:value="form.code" :maxlength="180" placeholder="resume.resume.read" />
      </a-form-item>
      <a-form-item label="资源类型" required><a-input v-model:value="form.resource_type" :maxlength="100" placeholder="resume" /></a-form-item>
      <a-form-item label="操作 Scope" required><a-input v-model:value="form.scope" :maxlength="80" placeholder="read" /></a-form-item>
      <a-form-item label="说明"><a-textarea v-model:value="form.description" :rows="3" :maxlength="500" show-count /></a-form-item>
    </a-form>
  </a-modal>
</template>

<style scoped>
.permission-toolbar { flex-wrap: wrap; }
.permission-search { width: min(100%, 420px); }
.permission-hint { margin-bottom: 16px; }
.permission-namespace-filter { min-width: 160px; }
.permission-error { margin-bottom: 16px; }
.permission-note { margin: 14px 0 0; color: var(--subtle); font-size: 12px; line-height: 1.6; }
@media (max-width: 650px) {
  .permission-search { width: 100%; }
}
</style>
