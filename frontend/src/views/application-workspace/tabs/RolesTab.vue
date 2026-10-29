<script setup lang="ts">
// 工作台「角色」Tab：列出当前应用的角色、新建、挂码；平台模式另提供资源树与数据范围（对齐角色列表能力）。
// 平台模式过滤全局角色目录（/admin/roles 按应用 scope），应用模式走租户应用角色目录。
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { cachedHas } from '@/api/capabilities'
import { PAGE_PATHS } from '@/router/navigation'
import { DownOutlined } from '@/plugins/icons'
import AdminTableToolbar from '@/components/AdminTableToolbar.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import RolePermissionGrantModal from '@/components/RolePermissionGrantModal.vue'
import RoleResourceGrantModal from '../components/RoleResourceGrantModal.vue'
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
interface PermissionRecord { id: string; code: string; description?: string | null; resource_type: string; scope: string; status: 'active' | 'disabled' }
interface DataScopePolicy { permission_id: string; scope_type: string; organization_ids: string[] }
interface DataScopeEntry { permission_id: string; permission_code: string; permission_description: string; scope_type: string; organization_ids: string[] }

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
const grantRoleKey = ref('')
// 管理员不能管理管理员：非模板角色（自定义「管理员」）禁选授权权码，与后端 422 同口径。
const TEMPLATE_ROLE_KEYS = new Set(['platform.admin', 'tenant.admin', 'app.admin', 'app.member'])
// P357 资源树授权弹窗状态：入口仅在平台控制台（资源端点只挂 /admin）。
const resourceOpen = ref(false)
const resourceRoleId = ref('')
const resourceRoleName = ref('')
const dataScopeDialogOpen = ref(false)
const dataScopeRoleId = ref('')
const dataScopeRoleName = ref('')
const dataScopeEntries = ref<DataScopeEntry[]>([])
const dataScopeOrganizationOptions = ref<{ label: string; value: string }[]>([])
const savingDataScopes = ref(false)
let requestSequence = 0

const isPlatform = computed(() => props.apiPrefix === '/admin')
// 平台侧挂码需要 rbac.role.manage；应用侧沿用 capabilities 换算的应用级 can_manage。
const canManage = computed(() => isPlatform.value
  ? cachedHas('rbac.role.manage')
  : props.application?.can_manage === true)
const canCreate = computed(() => canManage.value && props.application?.status === 'active')

const columns = [
  { title: '角色名称', dataIndex: 'name', key: 'name', width: 180, ellipsis: true },
  { title: '角色标识', dataIndex: 'key', key: 'key', width: 200, ellipsis: true },
  { title: '权限编码', dataIndex: 'permission_codes', key: 'permission_codes', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 180, fixed: 'right' as const },
]

function rolesPath(): string {
  if (isPlatform.value) {
    const applicationId = props.application?.id || ''
    const params = new URLSearchParams({ kind: 'application', application_id: applicationId, limit: '500' })
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
    // 平台角色需要显式指定租户与应用范围；应用角色天然限定当前应用。
    // 创建走 POST 集合路径，不能带 list 用的 kind/application_id 查询串
    const createPath = isPlatform.value
      ? '/admin/roles'
      : `/tenant-admin/applications/${application.id}/roles`
    const created = await api<RoleRecord>(createPath, {
      method: 'POST',
      body: JSON.stringify(isPlatform.value
        ? {
            tenant_id: application.tenant_id,
            application_id: application.id,
            key: form.key.trim(),
            name: form.name.trim(),
            description: form.description.trim() || null,
          }
        : {
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
        title: '角色已创建，现在配置权限？',
        content: '为该角色挂上权限编码后，成员才能真正获得能力。',
        okText: '去挂码',
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
  grantRoleKey.value = role.key
  grantOpen.value = true
}

// 打开资源树授权弹窗：勾选菜单/按钮/数据规则，保存为该角色在当前应用的全量资源集。
function openResourceEditor(role: RoleRecord): void {
  resourceRoleId.value = role.id
  resourceRoleName.value = role.name
  resourceOpen.value = true
}

async function openDataScopeEditor(role: RoleRecord): Promise<void> {
  if (!props.application || !isPlatform.value) return
  dataScopeRoleId.value = role.id
  dataScopeRoleName.value = role.name
  try {
    const [permissions, organizations, configured] = await Promise.all([
      api<PermissionRecord[] | { items: PermissionRecord[] }>('/admin/permissions?limit=1000').then(result => asPagedList(result).items),
      api<{ id: string; key: string; name: string; status: string }[]>(`/admin/organizations?tenant_id=${encodeURIComponent(props.application.tenant_id)}`),
      api<{ permission_id: string; scope_type: string; organization_ids: string[] }[]>(`/admin/roles/${role.id}/data-scopes`),
    ])
    dataScopeOrganizationOptions.value = organizations
      .filter(organization => organization.status === 'active')
      .map(organization => ({ label: `${organization.name} (${organization.key})`, value: organization.id }))
    const grants = permissions.filter(permission => role.permission_codes.includes(permission.code))
    dataScopeEntries.value = grants.map(permission => {
      const policy = configured.find(item => item.permission_id === permission.id)
      return {
        permission_id: permission.id,
        permission_code: permission.code,
        permission_description: permission.description?.trim() || '',
        scope_type: policy?.scope_type || '',
        organization_ids: policy?.organization_ids || [],
      }
    })
    dataScopeDialogOpen.value = true
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取数据范围失败')
  }
}

async function saveDataScopes(): Promise<void> {
  const invalidSelectedScope = dataScopeEntries.value.some(entry => entry.scope_type === 'selected_organizations' && !entry.organization_ids.length)
  if (invalidSelectedScope) {
    message.error('指定组织范围至少选择一个组织')
    return
  }
  savingDataScopes.value = true
  try {
    const policies: DataScopePolicy[] = dataScopeEntries.value
      .filter(entry => entry.scope_type)
      .map(entry => ({
        permission_id: entry.permission_id,
        scope_type: entry.scope_type,
        organization_ids: entry.scope_type === 'selected_organizations' ? entry.organization_ids : [],
      }))
    await api(`/admin/roles/${dataScopeRoleId.value}/data-scopes`, {
      method: 'PUT', body: JSON.stringify({ policies }),
    })
    message.success('角色数据范围已保存')
    dataScopeDialogOpen.value = false
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存数据范围失败')
  } finally {
    savingDataScopes.value = false
  }
}

function goAdvancedRoles(): void {
  void router.push(PAGE_PATHS.roles)
}

async function onGrantsSaved(): Promise<void> {
  await loadRoles()
  emit('changed')
}

// 挂码弹窗的目录与授权端点：平台走全局权限目录 + 角色授权；应用走应用权限目录（携带 role_id 保含停用码）。
const grantCatalogPath = computed(() => {
  if (!grantRoleId.value || !props.application) return ''
  return isPlatform.value
    ? '/admin/permissions?limit=1000'
    : `/tenant-admin/applications/${props.application.id}/permissions?role_id=${encodeURIComponent(grantRoleId.value)}`
})
const grantGrantsPath = computed(() => {
  if (!grantRoleId.value || !props.application) return ''
  return isPlatform.value
    ? `/admin/roles/${grantRoleId.value}/permissions`
    : `/tenant-admin/applications/${props.application.id}/roles/${grantRoleId.value}/permissions`
})

watch(() => [props.active, props.application?.id] as const, ([active]) => {
  if (active) void loadRoles()
  else roles.value = []
}, { immediate: true })
</script>

<template>
  <div class="flex flex-col gap-4">
    <AdminTableToolbar :hint="canManage
      ? '均为当前应用的角色，仅本应用生效；完整角色目录与克隆见「高级管理 → 角色管理」。'
      : '均为当前应用的角色，仅本应用生效；当前只读，挂码需平台授予 rbac.role.manage。'">
      <template #actions>
        <a-button :loading="loading" :disabled="!application" @click="loadRoles">刷新</a-button>
        <a-button v-if="isPlatform" @click="goAdvancedRoles">高级角色列表</a-button>
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
            <a-button type="link" size="small" @click="openGrantEditor(record as RoleRecord)">{{ canManage ? '配置权限' : '查看权限' }}</a-button>
            <a-dropdown v-if="isPlatform">
              <a-button type="link" size="small" class="inline-flex items-center gap-1">
                更多
                <DownOutlined class="text-[11px]" />
              </a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="resource" @click="openResourceEditor(record as RoleRecord)">配置资源</a-menu-item>
                  <a-menu-item v-if="canManage" key="dataScope" @click="openDataScopeEditor(record as RoleRecord)">数据范围</a-menu-item>
                  <a-menu-item key="advanced" @click="goAdvancedRoles">高级角色列表</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </span>
        </template>
      </template>
      <template #emptyText>
        <AdminEmpty emoji="🎭" description="当前应用还没有角色；先新建角色，再为其挂权限编码" />
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

    <RolePermissionGrantModal
      v-if="grantCatalogPath && grantGrantsPath"
      v-model:open="grantOpen"
      :role-id="grantRoleId"
      :role-name="grantRoleName"
      :lock-authority-codes="grantRoleKey !== '' && !TEMPLATE_ROLE_KEYS.has(grantRoleKey)"
      role-kind="application"
      :role-namespace="props.application?.permission_namespace || ''"
      :catalog-path="grantCatalogPath"
      :grants-path="grantGrantsPath"
      :disable-iam-codes="!isPlatform"
      @saved="onGrantsSaved"
    />

    <RoleResourceGrantModal
      v-if="isPlatform && application"
      v-model:open="resourceOpen"
      :application-id="application.id"
      :role-id="resourceRoleId"
      :role-name="resourceRoleName"
      :api-prefix="apiPrefix"
      @saved="emit('changed')"
    />

    <a-modal v-model:open="dataScopeDialogOpen" :title="`配置角色数据范围 — ${dataScopeRoleName}`" width="760px" ok-text="保存范围" cancel-text="取消" :confirm-loading="savingDataScopes" @ok="saveDataScopes">
      <a-alert class="mb-3" type="info" show-icon message="数据范围按同权限多角色取并集；未配置有效范围的权限默认拒绝访问。" />
      <div v-if="!dataScopeEntries.length" class="text-sm text-[var(--color-text-muted)]">请先为该角色配置至少一项权限，再添加对应的数据范围。</div>
      <div v-for="entry in dataScopeEntries" :key="entry.permission_id" class="mb-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_220px] sm:items-start">
        <div class="flex min-w-0 flex-col">
          <strong class="truncate text-sm text-[var(--color-text-primary)]">{{ entry.permission_description || entry.permission_code }}</strong>
          <span class="font-mono text-xs text-[var(--color-text-muted)]">{{ entry.permission_code }}</span>
        </div>
        <div class="flex flex-col gap-2">
          <a-select v-model:value="entry.scope_type" allow-clear placeholder="不授予数据范围" :options="[{ value: 'tenant', label: '当前租户全部数据' }, { value: 'self', label: '仅本人数据' }, { value: 'organization', label: '所属组织' }, { value: 'organization_tree', label: '所属组织及下级' }, { value: 'selected_organizations', label: '指定组织' }]" />
          <a-select v-if="entry.scope_type === 'selected_organizations'" v-model:value="entry.organization_ids" mode="multiple" :options="dataScopeOrganizationOptions" placeholder="选择允许访问的组织" />
        </div>
      </div>
    </a-modal>
  </div>
</template>
