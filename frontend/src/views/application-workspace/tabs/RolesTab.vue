<script setup lang="ts">
// 工作台「角色」Tab：列出当前应用的角色、新建；行内打开应用权限 / 配置成员。
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { cachedHasAny } from '@/api/capabilities'
import { PAGE_PATHS } from '@/router/navigation'
import AdminTableToolbar from '@/components/AdminTableToolbar.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import ApplicationPermissionModal from '../components/ApplicationPermissionModal.vue'
import RoleMembersModal from '../components/RoleMembersModal.vue'
import { asPagedList } from '@/utils/paged'

interface ApplicationRef {
  id: string
  tenant_id: string
  name: string
  status: string
  can_manage?: boolean
  permission_namespace?: string
}
interface RoleRecord {
  id: string
  key: string
  name: string
  description: string | null
  status: 'active' | 'disabled'
  permission_codes: string[]
  application_id?: string | null
}

const props = withDefaults(defineProps<{
  active?: boolean
  application: ApplicationRef | null
  apiPrefix?: string
}>(), {
  active: true,
  apiPrefix: '/admin',
})

const emit = defineEmits<{ changed: [], stats: [count: number] }>()
const router = useRouter()

const roles = ref<RoleRecord[]>([])
const loading = ref(false)
const createOpen = ref(false)
const saving = ref(false)
const form = reactive({ key: '', name: '', description: '' })
const grantOpen = ref(false)
const grantRoleId = ref('')
const grantRoleName = ref('')
const memberOpen = ref(false)
const memberRoleId = ref('')
const memberRoleName = ref('')
let requestSequence = 0

const isPlatform = computed(() => props.apiPrefix === '/admin')
const canManage = computed(() => props.application?.can_manage === true
  || (isPlatform.value && cachedHasAny(['button.app_role.manage'])))
const canCreate = computed(() => canManage.value && props.application?.status === 'active')

const columns = [
  { title: '角色名称', dataIndex: 'name', key: 'name', width: 180, ellipsis: true },
  { title: '角色标识', dataIndex: 'key', key: 'key', width: 200, ellipsis: true },
  { title: '权限编码', dataIndex: 'permission_codes', key: 'permission_codes', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 200, fixed: 'right' as const },
]

function rolesPath(): string {
  if (isPlatform.value) {
    const applicationId = props.application?.id || ''
    const params = new URLSearchParams({
      role_class: 'application',
      application_id: applicationId,
      limit: '500',
    })
    return `/admin/roles?${params}`
  }
  return `/tenant-admin/applications/${props.application?.id}/roles`
}

async function loadRoles(): Promise<void> {
  if (!props.active || !props.application) {
    roles.value = []
    emit('stats', 0)
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  try {
    const rows = asPagedList(await api<RoleRecord[] | { items: RoleRecord[] }>(rolesPath())).items
    if (sequence !== requestSequence) return
    roles.value = rows
    emit('stats', roles.value.length)
  } catch (error) {
    if (sequence === requestSequence) {
      roles.value = []
      emit('stats', 0)
      message.error(error instanceof Error ? error.message : '读取应用角色失败')
    }
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function openCreate(): void {
  form.key = ''
  form.name = ''
  form.description = ''
  createOpen.value = true
}

async function saveRole(): Promise<void> {
  const application = props.application
  if (!application || !canCreate.value) return
  if (!/^[a-z0-9][a-z0-9._-]{1,99}$/.test(form.key.trim())) {
    message.error('角色标识需为 2 至 100 位小写字母、数字、点、下划线或连字符')
    return
  }
  if (!form.name.trim() || form.name.trim().length > 120) {
    message.error('角色名称需填写且不超过 120 个字符')
    return
  }
  if (form.description.trim().length > 500) {
    message.error('角色说明不能超过 500 个字符')
    return
  }
  saving.value = true
  try {
    const created = await api<RoleRecord>(`/tenant-admin/applications/${application.id}/roles`, {
      method: 'POST',
      body: JSON.stringify({
        key: form.key.trim(),
        name: form.name.trim(),
        description: form.description.trim() || null,
      }),
    })
    message.success('角色已创建')
    createOpen.value = false
    await loadRoles()
    emit('changed')
    if (created?.id) {
      Modal.confirm({
        title: '角色已创建，现在配置应用权限？',
        content: '为该角色配置权限编码、资源树和数据权限后，成员才能真正获得能力。',
        okText: '去配置应用权限',
        cancelText: '稍后',
        onOk: () => openGrantEditor(created),
      })
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建角色失败')
  } finally {
    saving.value = false
  }
}

function openGrantEditor(role: RoleRecord): void {
  grantRoleId.value = role.id
  grantRoleName.value = role.name
  grantOpen.value = true
}

function openMembersEditor(role: RoleRecord): void {
  memberRoleId.value = role.id
  memberRoleName.value = role.name
  memberOpen.value = true
}

function goAdvancedRoles(): void {
  void router.push(PAGE_PATHS.roles)
}

async function onGrantsSaved(): Promise<void> {
  await loadRoles()
  emit('changed')
}

const grantCatalogPath = computed(() => {
  if (!grantRoleId.value || !props.application) return ''
  return `/tenant-admin/applications/${props.application.id}/permissions?role_id=${encodeURIComponent(grantRoleId.value)}&include_management=true`
})
const grantGrantsPath = computed(() => {
  if (!grantRoleId.value || !props.application) return ''
  return `/tenant-admin/applications/${props.application.id}/roles/${grantRoleId.value}/permissions`
})

watch(() => [props.active, props.application?.id] as const, ([active]) => {
  if (active) void loadRoles()
  else roles.value = []
}, { immediate: true })
</script>

<template>
  <div class="flex flex-col gap-4">
    <AdminTableToolbar :hint="canManage
      ? '本页只列出应用角色（财务 / 只读等）。「应用权限」里勾选你看得见的租户/应用管理码、业务码和资源树；「配置成员」会同时成为该应用的平台成员。五级平台模板请到「高级管理 → 平台角色」。'
      : '本页只列出应用角色；当前只读。'">
      <template #actions>
        <a-button :loading="loading" :disabled="!application" @click="loadRoles">刷新</a-button>
        <a-button v-if="isPlatform" @click="goAdvancedRoles">平台角色</a-button>
        <a-button v-if="canCreate" type="primary" @click="openCreate">新建应用角色</a-button>
      </template>
    </AdminTableToolbar>

    <a-table
      :data-source="roles"
      :columns="columns"
      :loading="loading"
      row-key="id"
      :scroll="{ x: 960, y: 'calc(100vh - 520px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'permission_codes'">
          <a-button type="link" size="small" class="px-0" @click="openGrantEditor(record as RoleRecord)">
            {{ record.permission_codes?.length ? `${record.permission_codes.length} 项` : '未挂码' }}
          </a-button>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <span class="inline-flex flex-wrap items-center gap-x-1">
            <a-button type="link" size="small" @click="openGrantEditor(record as RoleRecord)">应用权限</a-button>
            <a-button type="link" size="small" @click="openMembersEditor(record as RoleRecord)">配置成员</a-button>
          </span>
        </template>
      </template>
      <template #emptyText>
        <AdminEmpty emoji="🎭" description="当前应用还没有应用角色；先新建，再配置应用权限与成员" />
      </template>
    </a-table>

    <a-modal v-model:open="createOpen" title="新建应用角色" ok-text="创建" cancel-text="取消" :confirm-loading="saving" @ok="saveRole">
      <a-form layout="vertical">
        <a-form-item label="角色标识" help="创建后不可更改；2–100 位小写字母、数字、点、下划线或连字符">
          <a-input v-model:value="form.key" :maxlength="100" placeholder="例如 report.viewer" />
        </a-form-item>
        <a-form-item label="角色名称" required>
          <a-input v-model:value="form.name" :maxlength="120" placeholder="例如报表查看者" />
        </a-form-item>
        <a-form-item label="说明">
          <a-textarea v-model:value="form.description" :rows="2" :maxlength="500" placeholder="说明这个角色的用途" />
        </a-form-item>
      </a-form>
    </a-modal>

    <ApplicationPermissionModal
      v-if="application && grantCatalogPath && grantGrantsPath"
      v-model:open="grantOpen"
      :application-id="application.id"
      :tenant-id="application.tenant_id"
      :role-id="grantRoleId"
      :role-name="grantRoleName"
      :role-namespace="application.permission_namespace || ''"
      :catalog-path="grantCatalogPath"
      :grants-path="grantGrantsPath"
      :can-manage="canManage"
      @saved="onGrantsSaved"
    />

    <RoleMembersModal
      v-if="application"
      v-model:open="memberOpen"
      :application-id="application.id"
      :role-id="memberRoleId"
      :role-name="memberRoleName"
      :can-manage="canCreate"
    />
  </div>
</template>
