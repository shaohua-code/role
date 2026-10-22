<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '../../shared/services/api'

interface TenantOption { id: string; name: string; status: string }
interface ApplicationOption { id: string; tenant_id: string; name: string; status: string }
interface RoleRecord {
  id: string
  tenant_id: string
  application_id: string | null
  key: string
  name: string
  description: string | null
  status: string
  permission_codes: string[]
}
interface PermissionImpact {
  role: { id: string; key: string; name: string; status: string; tenant_id: string }
  current_permission_ids: string[]
  current_permission_codes: string[]
  proposed_permission_codes: string[]
  grant_permission_codes: string[]
  revoke_permission_codes: string[]
  data_scopes_to_delete: { permission_id: string; permission_code: string; scope_type: string }[]
  bound_active_members: number
  potentially_affected_members: number
  analysis_note: string
  permission_impacts: { permission_code: string; action: 'grant' | 'revoke'; eligible_members: number; covered_by_other_general_roles: number; potentially_affected_members: number }[]
}
interface PermissionRecord { id: string; code: string; resource_type: string; scope: string; status: 'active' | 'disabled' }
/** API 中通用授权与资源实例授权共用的视图；资源编辑器只操作非空 resource_id。 */
interface RolePermissionGrant { permission_id: string; code: string; resource_id: string | null }
interface ResourcePermissionGrant extends RolePermissionGrant { resource_id: string }
interface DataScopePolicy { permission_id: string; scope_type: string; organization_ids: string[] }
interface DataScopeEntry { permission_id: string; permission_code: string; scope_type: string; organization_ids: string[] }

const props = defineProps<{
  active: boolean
  tenants: TenantOption[]
  applications: ApplicationOption[]
  shellRoles?: RoleRecord[] | null
  shellCatalogGeneration?: number
}>()
const emit = defineEmits<{ changed: [] }>()

let hydratedCatalogGeneration = -1

const roles = ref<RoleRecord[]>([])
const tenantFilter = ref('')
const searchText = ref('')
const loading = ref(false)
const errorText = ref('')
const editorOpen = ref(false)
const savingRole = ref(false)
const editingRole = ref<RoleRecord | null>(null)
const form = reactive({ tenant_id: '', application_id: '', key: '', name: '', description: '' })
const cloneDialogOpen = ref(false)
const cloningRole = ref(false)
const cloneSourceRole = ref<RoleRecord | null>(null)
const cloneForm = reactive({ key: '', name: '', description: '', copy_authorizations: false })

const grantDialogOpen = ref(false)
const permissionOptions = ref<{ label: string; value: string }[]>([])
const grantRoleId = ref('')
const grantPermissionIds = ref<string[]>([])
const impactPreview = ref<PermissionImpact | null>(null)
const impactPreviewKey = ref('')
const impactLoading = ref(false)
const savingGrants = ref(false)

const resourceGrantDialogOpen = ref(false)
const resourceGrantRoleId = ref('')
const resourceGrantLoading = ref(false)
const resourceGrantSaving = ref(false)
const resourceGrantError = ref('')
const resourcePermissionOptions = ref<PermissionRecord[]>([])
const resourcePermissionGrants = ref<ResourcePermissionGrant[]>([])
const resourcePermissionId = ref('')
const resourceIdInput = ref('')

const dataScopeDialogOpen = ref(false)
const dataScopeRoleId = ref('')
const dataScopeEntries = ref<DataScopeEntry[]>([])
const dataScopeOrganizationOptions = ref<{ label: string; value: string }[]>([])
const savingDataScopes = ref(false)

let requestSequence = 0

const tenantOptions = computed(() => props.tenants.map(tenant => ({ value: tenant.id, label: tenant.name })))
const applicationOptions = computed(() => props.applications
  .filter(application => application.tenant_id === form.tenant_id && application.status === 'active')
  .map(application => ({ value: application.id, label: application.name })))
const filteredRoles = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return roles.value.filter(role => {
    const matchesTenant = !tenantFilter.value || role.tenant_id === tenantFilter.value
    const matchesQuery = !query || `${role.name} ${role.key} ${role.description || ''}`.toLocaleLowerCase().includes(query)
    return matchesTenant && matchesQuery
  })
})

const columns = [
  { title: '角色名称', dataIndex: 'name', key: 'name', width: 170, ellipsis: true },
  { title: '角色标识', dataIndex: 'key', key: 'key', width: 180, ellipsis: true },
  { title: '租户', dataIndex: 'tenant_id', key: 'tenant_id', width: 190, ellipsis: true },
  { title: '应用范围', dataIndex: 'application_id', key: 'application_id', width: 190, ellipsis: true },
  { title: '权限', dataIndex: 'permission_codes', key: 'permission_codes', width: 250 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '说明', dataIndex: 'description', key: 'description', width: 240, ellipsis: true },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 470, fixed: 'right' as const },
]

function hydrateFromShell(): boolean {
  if (props.shellRoles == null) return false
  const generation = props.shellCatalogGeneration ?? -1
  if (generation < 0 || generation === hydratedCatalogGeneration) return false
  roles.value = props.shellRoles
  hydratedCatalogGeneration = generation
  return true
}

async function loadRoles(): Promise<void> {
  if (!props.active) return
  const sequence = ++requestSequence
  loading.value = true
  errorText.value = ''
  try {
    const result = await api<RoleRecord[]>('/admin/roles')
    if (sequence === requestSequence && props.active) roles.value = result
  } catch (error) {
    if (sequence !== requestSequence) return
    roles.value = []
    errorText.value = error instanceof Error ? error.message : '读取角色目录失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function openCreate(): void {
  editingRole.value = null
  form.tenant_id = props.tenants.find(tenant => tenant.status === 'active')?.id || ''
  form.application_id = ''
  form.key = ''
  form.name = ''
  form.description = ''
  editorOpen.value = true
}

function openEdit(role: RoleRecord): void {
  editingRole.value = role
  form.tenant_id = role.tenant_id
  form.application_id = role.application_id || ''
  form.key = role.key
  form.name = role.name
  form.description = role.description || ''
  editorOpen.value = true
}

function validateRoleForm(): boolean {
  if (editingRole.value) {
    if (!form.name.trim() || form.name.trim().length > 120) {
      message.error('角色名称需填写且不超过 120 个字符')
      return false
    }
    if (form.description.trim().length > 500) {
      message.error('角色说明不能超过 500 个字符')
      return false
    }
    return true
  }
  if (!props.tenants.some(tenant => tenant.id === form.tenant_id && tenant.status === 'active')) {
    message.error('请选择活动租户')
    return false
  }
  if (!/^[a-z0-9][a-z0-9._-]{1,99}$/.test(form.key.trim())) {
    message.error('角色标识需为 2 至 100 位小写字母、数字、点、下划线或连字符')
    return false
  }
  if (!form.name.trim() || form.name.trim().length > 120) {
    message.error('角色名称需填写且不超过 120 个字符')
    return false
  }
  if (form.description.trim().length > 500) {
    message.error('角色说明不能超过 500 个字符')
    return false
  }
  if (form.application_id && !applicationOptions.value.some(option => option.value === form.application_id)) {
    message.error('应用必须属于所选租户且处于启用状态')
    return false
  }
  return true
}

async function saveRole(): Promise<void> {
  if (!validateRoleForm()) return
  const editing = editingRole.value
  const payload = editing
    ? { name: form.name.trim(), description: form.description.trim() || null }
    : {
        tenant_id: form.tenant_id,
        ...(form.application_id ? { application_id: form.application_id } : {}),
        key: form.key.trim(),
        name: form.name.trim(),
        description: form.description.trim() || null,
      }
  savingRole.value = true
  try {
    await api(editing ? `/admin/roles/${editing.id}` : '/admin/roles', {
      method: editing ? 'PATCH' : 'POST', body: JSON.stringify(payload),
    })
    message.success(editing ? '角色已更新' : '角色已创建')
    editorOpen.value = false
    await loadRoles()
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : editing ? '更新角色失败' : '创建角色失败')
  } finally {
    savingRole.value = false
  }
}

function openClone(role: RoleRecord): void {
  cloneSourceRole.value = role
  const suffix = '.copy'
  const baseKey = role.key.slice(0, 100 - suffix.length).replace(/[._-]+$/, '')
  cloneForm.key = `${baseKey || 'role'}${suffix}`
  cloneForm.name = `${Array.from(role.name).slice(0, 116).join('')}（副本）`
  cloneForm.description = role.description || ''
  // 复制授权会扩大新角色可访问范围，因此每次都从关闭状态开始。
  cloneForm.copy_authorizations = false
  cloneDialogOpen.value = true
}

async function submitRoleClone(): Promise<void> {
  const source = cloneSourceRole.value
  if (!source || cloningRole.value) return
  const key = cloneForm.key.trim()
  const name = cloneForm.name.trim()
  const description = cloneForm.description.trim()
  const copyAuthorizations = cloneForm.copy_authorizations
  if (!/^[a-z0-9][a-z0-9._-]{1,99}$/.test(key)) {
    message.error('角色标识需为 2 至 100 位小写字母、数字、点、下划线或连字符')
    return
  }
  if (!name || name.length > 120) {
    message.error('角色名称需填写且不超过 120 个字符')
    return
  }
  if (description.length > 500) {
    message.error('角色说明不能超过 500 个字符')
    return
  }

  cloningRole.value = true
  try {
    const result = await api<{ copied_permission_grant_count: number; copied_data_scope_count: number }>(
      `/admin/roles/${source.id}/clone`,
      {
        method: 'POST',
        body: JSON.stringify({
          key, name, description: description || null,
          copy_authorizations: copyAuthorizations,
        }),
      },
    )
    message.success(copyAuthorizations
      ? `角色已复制，复制 ${result.copied_permission_grant_count} 项授权和 ${result.copied_data_scope_count} 项数据范围`
      : '角色已复制，未复制任何权限或数据范围')
    cloneDialogOpen.value = false
    cloneSourceRole.value = null
    await loadRoles()
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '复制角色失败')
  } finally {
    cloningRole.value = false
  }
}

function confirmStatusChange(role: RoleRecord): void {
  const nextStatus = role.status === 'active' ? 'disabled' : 'active'
  const updateStatus = async (): Promise<void> => {
    try {
      await api(`/admin/roles/${role.id}/status?status=${nextStatus}`, { method: 'PATCH' })
      message.success(nextStatus === 'active' ? '角色已启用' : '角色已停用')
      await loadRoles()
      emit('changed')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '更新角色状态失败')
      throw error
    }
  }
  if (nextStatus === 'disabled') {
    Modal.confirm({
      title: '确认停用角色？',
      content: `停用“${role.name}”后，绑定该角色的成员将不再通过此角色获得权限。`,
      okText: '确认停用', cancelText: '取消', okButtonProps: { danger: true }, onOk: updateStatus,
    })
  } else {
    void updateStatus()
  }
}

async function openGrantEditor(role: RoleRecord): Promise<void> {
  grantRoleId.value = role.id
  impactPreview.value = null
  impactPreviewKey.value = ''
  try {
    const [permissions, grants] = await Promise.all([
      api<PermissionRecord[]>('/admin/permissions'),
      api<{ permission_id: string; resource_id: string | null }[]>(`/admin/roles/${role.id}/permissions`),
    ])
      // 只编辑通用授权，避免多选框覆盖资源实例授权。
      const currentGrantIds = grants.filter(grant => grant.resource_id === null).map(grant => grant.permission_id)
      const currentGrantIdSet = new Set(currentGrantIds)
      permissionOptions.value = permissions
        .filter(permission => permission.status === 'active' || currentGrantIdSet.has(permission.id))
        .map(permission => ({
          label: permission.status === 'active' ? permission.code : `${permission.code}（停用，仅可撤销）`,
          value: permission.id,
          disabled: permission.status !== 'active' && !currentGrantIdSet.has(permission.id),
        }))
      grantPermissionIds.value = currentGrantIds
    grantDialogOpen.value = true
  } catch (error) {
    message.error(error instanceof Error ? error.message : '权限目录读取失败')
  }
}

/** 重新读取当前角色的授权，并把通用授权排除在资源编辑器之外。 */
async function loadResourcePermissionGrants(): Promise<void> {
  if (!resourceGrantRoleId.value) return
  const grants = await api<RolePermissionGrant[]>(
    `/admin/roles/${resourceGrantRoleId.value}/permissions`,
  )
  resourcePermissionGrants.value = grants.filter(
    (grant): grant is ResourcePermissionGrant => grant.resource_id !== null,
  )
}

/** 加载活动权限编码和历史资源授权，供管理员逐资源维护中央判权范围。 */
async function openResourceGrantEditor(role: RoleRecord): Promise<void> {
  resourceGrantRoleId.value = role.id
  resourcePermissionId.value = ''
  resourceIdInput.value = ''
  resourceGrantError.value = ''
  resourceGrantDialogOpen.value = true
  resourceGrantLoading.value = true
  try {
    const permissions = await api<PermissionRecord[]>('/admin/permissions')
    resourcePermissionOptions.value = permissions.filter(permission => permission.status === 'active')
    await loadResourcePermissionGrants()
  } catch (error) {
    resourceGrantError.value = error instanceof Error ? error.message : '读取资源级授权失败'
  } finally {
    resourceGrantLoading.value = false
  }
}

/** 新增单一 permission/resource 组合，服务器会锁定角色并记录审计。 */
async function saveResourcePermissionGrant(): Promise<void> {
  const permissionId = resourcePermissionId.value
  const resourceId = resourceIdInput.value.trim()
  if (!permissionId) {
    message.error('请选择权限编码')
    return
  }
  if (!resourceId || resourceId.length > 180) {
    message.error('资源 ID 需填写且不超过 180 个字符')
    return
  }
  if (resourcePermissionGrants.value.some(
    grant => grant.permission_id === permissionId && grant.resource_id === resourceId,
  )) {
    message.info('该资源授权已存在')
    return
  }
  resourceGrantSaving.value = true
  try {
    const query = new URLSearchParams({ resource_id: resourceId })
    await api<void>(
      `/admin/roles/${resourceGrantRoleId.value}/permissions/${permissionId}?${query}`,
      { method: 'PUT' },
    )
    message.success('资源级授权已添加')
    resourcePermissionId.value = ''
    resourceIdInput.value = ''
    await loadResourcePermissionGrants()
    await loadRoles()
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '添加资源级授权失败')
  } finally {
    resourceGrantSaving.value = false
  }
}

/** 二次确认精确资源撤销，避免误删同权限下的其他资源或通用授权。 */
function confirmRevokeResourceGrant(grant: ResourcePermissionGrant): void {
  Modal.confirm({
    title: '撤销这条资源级授权？',
    content: `${grant.code} 对资源 ${grant.resource_id} 的授权将立即失效。其他资源和通用授权不受影响。`,
    okText: '确认撤销',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk: async () => {
      resourceGrantSaving.value = true
      try {
        const query = new URLSearchParams({ resource_id: grant.resource_id })
        await api<void>(
          `/admin/roles/${resourceGrantRoleId.value}/permissions/${grant.permission_id}?${query}`,
          { method: 'DELETE' },
        )
        message.success('资源级授权已撤销')
        await loadResourcePermissionGrants()
        await loadRoles()
        emit('changed')
      } catch (error) {
        message.error(error instanceof Error ? error.message : '撤销资源级授权失败')
        throw error
      } finally {
        resourceGrantSaving.value = false
      }
    },
  })
}

function selectionKey(permissionIds: string[]): string {
  return [...permissionIds].sort().join('|')
}

function clearImpactPreview(): void {
  impactPreview.value = null
  impactPreviewKey.value = ''
}

async function previewGrantChanges(): Promise<void> {
  if (!grantRoleId.value) return
  impactLoading.value = true
  try {
    impactPreview.value = await api<PermissionImpact>(`/admin/roles/${grantRoleId.value}/permissions/preview`, {
      method: 'POST', body: JSON.stringify({ permission_ids: grantPermissionIds.value }),
    })
    impactPreviewKey.value = selectionKey(grantPermissionIds.value)
  } catch (error) {
    clearImpactPreview()
    message.error(error instanceof Error ? error.message : '授权影响预览失败')
  } finally {
    impactLoading.value = false
  }
}

async function applyGrantChanges(): Promise<void> {
  const preview = impactPreview.value
  if (!preview) return
  savingGrants.value = true
  try {
    await api(`/admin/roles/${grantRoleId.value}/permissions`, {
      method: 'PUT',
      body: JSON.stringify({
        permission_ids: grantPermissionIds.value,
        expected_current_permission_ids: preview.current_permission_ids,
      }),
    })
    message.success('角色权限已原子更新')
    grantDialogOpen.value = false
    clearImpactPreview()
    await loadRoles()
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '权限保存失败；如授权已被其他管理员更新，请重新预览')
  } finally {
    savingGrants.value = false
  }
}

function confirmGrantChanges(): void {
  const preview = impactPreview.value
  if (!preview || impactPreviewKey.value !== selectionKey(grantPermissionIds.value)) {
    void previewGrantChanges()
    message.info('先预览授权影响，核对结果后再确认保存')
    return
  }
  if (!preview.grant_permission_codes.length && !preview.revoke_permission_codes.length) {
    message.info('权限集合没有变化')
    return
  }
  const summary = [
    `新增 ${preview.grant_permission_codes.length} 项授权`,
    `撤销 ${preview.revoke_permission_codes.length} 项授权`,
    `清理 ${preview.data_scopes_to_delete.length} 项失去授权前置条件的数据范围`,
    `当前潜在覆盖 ${preview.potentially_affected_members} 名活动成员`,
  ].join('；')
  Modal.confirm({
    title: `确认更新「${preview.role.name}」的授权？`,
    content: `${summary}。${preview.analysis_note}`,
    okText: '确认并保存', cancelText: '返回检查', onOk: applyGrantChanges,
  })
}

async function openDataScopeEditor(role: RoleRecord): Promise<void> {
  dataScopeRoleId.value = role.id
  try {
    const [permissions, organizations, configured] = await Promise.all([
      api<PermissionRecord[]>('/admin/permissions'),
      api<{ id: string; key: string; name: string; status: string }[]>(`/admin/organizations?tenant_id=${encodeURIComponent(role.tenant_id)}`),
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

function tenantName(id: string): string {
  return props.tenants.find(tenant => tenant.id === id)?.name || id
}

function applicationName(id: string | null): string {
  if (!id) return '全部应用'
  return props.applications.find(application => application.id === id)?.name || id
}

watch(() => props.active, active => {
  if (!active) return
  // 平台壳已预拉角色目录时复用，避免路由激活重复请求 /admin/roles。
  if (hydrateFromShell()) return
  void loadRoles()
}, { immediate: true })

watch(() => [props.shellCatalogGeneration, props.shellRoles?.length] as const, () => {
  if (props.active) hydrateFromShell()
})
</script>

<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">ROLE &amp; POLICY</p>
      <h1>角色管理</h1>
      <p class="subtitle">维护租户/应用角色、通用权限授予和数据范围策略。</p>
    </div>
    <a-button type="primary" @click="openCreate">＋ 新建角色</a-button>
  </div>

  <a-card class="data-card" :bordered="false">
    <div class="table-toolbar role-toolbar">
      <a-input-search v-model:value="searchText" allow-clear placeholder="搜索角色名称、标识或说明" class="role-search" />
      <a-select v-model:value="tenantFilter" allow-clear show-search option-filter-prop="label" placeholder="全部租户" class="role-tenant-filter" :options="tenantOptions" />
      <span class="table-hint">{{ filteredRoles.length }} 条角色 · 最多读取 500 条</span>
      <a-button :loading="loading" @click="loadRoles">刷新</a-button>
    </div>
    <a-alert v-if="errorText" type="error" show-icon :message="errorText" class="role-error" />
    <a-table class="scroll-actions-on-mobile" :data-source="filteredRoles" :columns="columns" :loading="loading" row-key="id" :scroll="{ x: 1780 }" :pagination="{ pageSize: 10, showSizeChanger: true }">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'tenant_id'">{{ tenantName(String(record.tenant_id)) }}</template>
        <template v-else-if="column.key === 'application_id'">{{ applicationName(record.application_id ? String(record.application_id) : null) }}</template>
        <template v-else-if="column.key === 'permission_codes'">
          <a-tooltip :title="Array.isArray(record.permission_codes) ? record.permission_codes.join('、') || '尚未授予权限' : ''">
            <a-tag color="blue">{{ Array.isArray(record.permission_codes) ? `${record.permission_codes.length} 项` : '0 项' }}</a-tag>
          </a-tooltip>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-button type="link" size="small" @click="openEdit(record as RoleRecord)">编辑</a-button>
          <a-button type="link" size="small" @click="openGrantEditor(record as RoleRecord)">配置权限</a-button>
          <a-button type="link" size="small" @click="openResourceGrantEditor(record as RoleRecord)">资源授权</a-button>
          <a-button type="link" size="small" @click="openDataScopeEditor(record as RoleRecord)">数据范围</a-button>
          <a-button type="link" size="small" @click="openClone(record as RoleRecord)">复制</a-button>
          <a-button type="link" size="small" :danger="record.status === 'active'" @click="confirmStatusChange(record as RoleRecord)">{{ record.status === 'active' ? '停用' : '启用' }}</a-button>
        </template>
      </template>
      <template #emptyText><a-empty :description="searchText || tenantFilter ? '没有匹配条件的角色' : '暂无角色，可创建角色后配置权限'" /></template>
    </a-table>
    <div class="scope-note">授权遵循默认拒绝。数据范围按同一权限的多角色策略取并集；缺少有效数据策略时，受控业务请求默认拒绝。</div>
  </a-card>

  <a-modal v-model:open="editorOpen" :title="editingRole ? `编辑角色：${editingRole.name}` : '新建角色'" ok-text="保存" cancel-text="取消" :confirm-loading="savingRole" @ok="saveRole">
    <a-form layout="vertical" class="create-form">
      <template v-if="editingRole">
        <a-form-item label="所属租户"><a-input :value="tenantName(form.tenant_id)" disabled /></a-form-item>
        <a-form-item label="应用范围"><a-input :value="applicationName(form.application_id || null)" disabled /></a-form-item>
        <a-form-item label="角色标识"><a-input v-model:value="form.key" disabled /></a-form-item>
      </template>
      <template v-else>
        <a-form-item label="所属租户" required><a-select v-model:value="form.tenant_id" :options="tenantOptions.filter(option => props.tenants.find(tenant => tenant.id === option.value)?.status === 'active')" @change="form.application_id = ''" /></a-form-item>
        <a-form-item label="应用范围（可选）"><a-select v-model:value="form.application_id" allow-clear :options="applicationOptions" placeholder="不选表示该租户的通用角色" /></a-form-item>
        <a-form-item label="角色标识" required help="2–100 位小写字母、数字、点、下划线或连字符"><a-input v-model:value="form.key" :maxlength="100" placeholder="tenant.admin" /></a-form-item>
      </template>
      <a-form-item label="角色名称" required><a-input v-model:value="form.name" :maxlength="120" /></a-form-item>
      <a-form-item label="说明"><a-textarea v-model:value="form.description" :rows="3" :maxlength="500" show-count /></a-form-item>
      <a-alert v-if="editingRole" message="租户、应用范围和角色标识创建后不可修改；编辑只更新名称和说明，授权关系保持不变。" type="info" show-icon />
    </a-form>
  </a-modal>

  <a-modal
    v-model:open="cloneDialogOpen"
    title="复制角色"
    ok-text="创建副本"
    cancel-text="取消"
    :confirm-loading="cloningRole"
    @ok="submitRoleClone"
    @after-close="cloneSourceRole = null"
  >
    <a-form layout="vertical" class="create-form">
      <a-form-item label="源角色">
        <a-input :value="cloneSourceRole ? `${cloneSourceRole.name}（${cloneSourceRole.key}）` : ''" disabled />
      </a-form-item>
      <a-form-item label="新角色标识" required help="同一租户/应用范围内必须唯一">
        <a-input v-model:value="cloneForm.key" :maxlength="100" />
      </a-form-item>
      <a-form-item label="新角色名称" required>
        <a-input v-model:value="cloneForm.name" :maxlength="120" />
      </a-form-item>
      <a-form-item label="说明">
        <a-textarea v-model:value="cloneForm.description" :rows="3" :maxlength="500" show-count />
      </a-form-item>
      <a-checkbox v-model:checked="cloneForm.copy_authorizations">复制当前启用的权限、资源授权和对应数据范围</a-checkbox>
      <a-alert
        class="clone-policy-note"
        type="info"
        show-icon
        :message="cloneSourceRole?.status === 'disabled' ? '源角色已停用，副本也会保持停用' : '新副本沿用源角色的租户和应用范围'"
        description="默认不复制授权。勾选后只复制权限目录当前启用的授权及其数据范围；直接成员绑定和用户组角色绑定永远不会复制。"
      />
    </a-form>
  </a-modal>

  <a-modal v-model:open="grantDialogOpen" title="配置角色权限" width="680px" :footer="null" @after-close="clearImpactPreview">
    <div class="permission-grant-editor">
      <a-alert type="info" show-icon message="先预览授权变更，再提交保存" description="本表单只编辑通用权限；资源实例级授权保持不变。保存会以单个数据库事务应用新增、撤销和数据范围清理。" />
      <a-select v-model:value="grantPermissionIds" mode="multiple" show-search style="width:100%" placeholder="选择资源操作权限" :options="permissionOptions" :disabled="impactLoading || savingGrants" @change="clearImpactPreview" />
      <div v-if="impactPreview" class="permission-impact-preview">
        <a-alert type="warning" show-icon :message="`角色关联 ${impactPreview.bound_active_members} 名活动成员（直接或用户组继承）；潜在受影响 ${impactPreview.potentially_affected_members} 名`" :description="impactPreview.analysis_note" />
        <p>新增：{{ impactPreview.grant_permission_codes.join('、') || '无' }}</p>
        <p>撤销：{{ impactPreview.revoke_permission_codes.join('、') || '无' }}</p>
        <p v-for="item in impactPreview.permission_impacts" :key="`${item.action}:${item.permission_code}`">
          {{ item.action === 'grant' ? '新增' : '撤销' }} {{ item.permission_code }}：潜在影响 {{ item.potentially_affected_members }} 名，其他通用角色已覆盖 {{ item.covered_by_other_general_roles }} 名
        </p>
        <p v-if="impactPreview.data_scopes_to_delete.length">同时清理失去授权前置条件的数据范围：{{ impactPreview.data_scopes_to_delete.map(item => `${item.permission_code}（${item.scope_type}）`).join('、') }}</p>
        <p v-else>无需清理数据范围策略。</p>
      </div>
      <div class="permission-impact-actions">
        <a-button @click="grantDialogOpen = false">取消</a-button>
        <a-button :loading="impactLoading" @click="previewGrantChanges">预览影响</a-button>
        <a-button type="primary" :loading="savingGrants" :disabled="!impactPreview || impactPreviewKey !== selectionKey(grantPermissionIds) || (!impactPreview.grant_permission_codes.length && !impactPreview.revoke_permission_codes.length)" @click="confirmGrantChanges">保存授权</a-button>
      </div>
    </div>
  </a-modal>

  <a-modal v-model:open="resourceGrantDialogOpen" title="配置资源级授权" width="820px" :footer="null">
    <div class="resource-grant-editor">
      <a-alert
        type="info"
        show-icon
        message="资源级权限按 permission code + resource ID 精确匹配"
        description="资源 ID 使用业务系统自己的稳定标识，例如 DeerFlow 模型 UUID。不填资源 ID 的通用授权仍覆盖该权限范围；业务服务必须在查询时执行这个条件。"
      />
      <a-alert v-if="resourceGrantError" type="error" show-icon :message="resourceGrantError" />
      <div class="resource-grant-form">
        <a-select
          v-model:value="resourcePermissionId"
          show-search
          option-filter-prop="label"
          :options="resourcePermissionOptions.map(permission => ({ label: permission.code, value: permission.id }))"
          placeholder="选择活动权限编码"
          :disabled="resourceGrantLoading || resourceGrantSaving"
        />
        <a-input
          v-model:value="resourceIdInput"
          :maxlength="180"
          placeholder="资源 ID，例如 DeerFlow 模型 UUID"
          :disabled="resourceGrantLoading || resourceGrantSaving"
          @press-enter="saveResourcePermissionGrant"
        />
        <a-button
          type="primary"
          :loading="resourceGrantSaving"
          :disabled="resourceGrantLoading"
          @click="saveResourcePermissionGrant"
        >添加授权</a-button>
      </div>
      <a-spin :spinning="resourceGrantLoading">
        <div v-if="!resourceGrantLoading && !resourcePermissionGrants.length" class="resource-grant-empty">
          当前角色没有资源级授权。
        </div>
        <div v-else class="resource-grant-list">
          <div v-for="grant in resourcePermissionGrants" :key="`${grant.permission_id}:${grant.resource_id}`" class="resource-grant-row">
            <div class="resource-grant-identity">
              <strong>{{ grant.code }}</strong>
              <code>{{ grant.resource_id }}</code>
            </div>
            <a-button
              danger
              size="small"
              :loading="resourceGrantSaving"
              @click="confirmRevokeResourceGrant(grant)"
            >撤销</a-button>
          </div>
        </div>
      </a-spin>
    </div>
  </a-modal>

  <a-modal v-model:open="dataScopeDialogOpen" title="配置角色数据范围" width="760px" ok-text="保存范围" cancel-text="取消" :confirm-loading="savingDataScopes" @ok="saveDataScopes">
    <a-alert class="scope-modal-help" type="info" show-icon message="策略按同一权限的多角色结果取并集。未配置有效数据范围的业务请求默认拒绝。" />
    <div v-if="!dataScopeEntries.length" class="scope-empty">请先为该角色配置至少一项权限，再添加对应的数据范围。</div>
    <div v-for="entry in dataScopeEntries" :key="entry.permission_id" class="scope-policy-row">
      <strong>{{ entry.permission_code }}</strong>
      <a-select v-model:value="entry.scope_type" allow-clear placeholder="不授予数据范围" :options="[{ value: 'tenant', label: '当前租户全部数据' }, { value: 'self', label: '仅本人数据' }, { value: 'organization', label: '所属组织' }, { value: 'organization_tree', label: '所属组织及下级' }, { value: 'selected_organizations', label: '指定组织' }]" />
      <a-select v-if="entry.scope_type === 'selected_organizations'" v-model:value="entry.organization_ids" mode="multiple" :options="dataScopeOrganizationOptions" placeholder="选择允许访问的组织" />
    </div>
  </a-modal>
</template>

<style scoped>
.role-toolbar { flex-wrap: wrap; }
.role-search { width: min(100%, 360px); }
.role-tenant-filter { width: min(100%, 260px); }
.role-error { margin-bottom: 16px; }
.clone-policy-note { margin-top: 12px; }
/* 资源级授权表单在桌面横向排列，窄屏折叠为单列，长资源 ID 自动换行。 */
.resource-grant-editor { display: grid; gap: 16px; }
.resource-grant-form { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(220px, 1.4fr) auto; gap: 10px; }
.resource-grant-list { display: grid; max-height: 320px; overflow: auto; border: 1px solid #e9edf3; border-radius: 10px; }
.resource-grant-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px 14px; border-bottom: 1px solid #eef1f5; }
.resource-grant-row:last-child { border-bottom: 0; }
.resource-grant-identity { display: grid; min-width: 0; gap: 5px; }
.resource-grant-identity code { overflow-wrap: anywhere; color: #667085; }
.resource-grant-empty { padding: 24px 12px; color: #667085; text-align: center; }
@media (max-width: 650px) {
  .role-search, .role-tenant-filter { width: 100%; }
  .resource-grant-form { grid-template-columns: 1fr; }
}
</style>

