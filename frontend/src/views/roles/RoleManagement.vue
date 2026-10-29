<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { TablePaginationConfig } from 'ant-design-vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHas, getCachedCapabilities } from '@/api/capabilities'
import { DownOutlined } from '@/plugins/icons'
import AdminListPage from '@/components/AdminListPage.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import RolePermissionGrantModal from '@/components/RolePermissionGrantModal.vue'
import { asPagedList } from '@/utils/paged'

interface TenantOption { id: string; name: string; status: string }
interface ApplicationOption { id: string; tenant_id: string; name: string; status: string; permission_namespace?: string }
interface RoleRecord {
  id: string
  tenant_id: string
  application_id: string | null
  kind: 'platform' | 'tenant' | 'application'
  key: string
  name: string
  description: string | null
  status: string
  permission_codes: string[]
}
interface PermissionRecord { id: string; code: string; description?: string | null; resource_type: string; scope: string; status: 'active' | 'disabled' }
/** API 中通用授权与资源实例授权共用的视图；资源编辑器只操作非空 resource_id。 */
interface RolePermissionGrant { permission_id: string; code: string; description?: string | null; resource_id: string | null }
interface ResourcePermissionGrant extends RolePermissionGrant { resource_id: string }
interface DataScopePolicy { permission_id: string; scope_type: string; organization_ids: string[] }
interface DataScopeEntry { permission_id: string; permission_code: string; permission_description: string; scope_type: string; organization_ids: string[] }

const props = defineProps<{
  active: boolean
  tenants: TenantOption[]
  applications: ApplicationOption[]
}>()
const emit = defineEmits<{ changed: [] }>()
const isPlatformSuperAdmin = computed(() => getCachedCapabilities()?.platform_admin === true)
// 前四级都可新建自定义平台角色，并给自己看得见的管理码挂权。
const canCreateRoles = computed(() => isPlatformSuperAdmin.value || cachedHas('org.manage') || cachedHas('rbac.app_role.manage'))
const canMutateRoleMeta = computed(() => isPlatformSuperAdmin.value)

const roles = ref<RoleRecord[]>([])
// undefined 才能触发 Select 的 placeholder；'' 会被当作已选值导致空框无占位文案
const tenantFilter = ref<string | undefined>(undefined)
const statusFilter = ref<string | undefined>(undefined)
const statusOptions = [
  { value: 'active', label: '启用' },
  { value: 'disabled', label: '停用' },
]
const searchText = ref('')
const submittedQuery = ref('')
const loading = ref(false)
const errorText = ref('')
// G29 角色列表走服务端真分页，不再用前端切片冒充完整目录。
const listPage = ref(1)
const listPageSize = ref(20)
const listTotal = ref(0)
const editorOpen = ref(false)
const savingRole = ref(false)
const editingRole = ref<RoleRecord | null>(null)
const form = reactive({ tenant_id: '', application_id: '', key: '', name: '', description: '' })
const cloneDialogOpen = ref(false)
const cloningRole = ref(false)
const cloneSourceRole = ref<RoleRecord | null>(null)
const cloneForm = reactive({ key: '', name: '', description: '', copy_authorizations: false })

// 挂码编辑改用共享 RolePermissionGrantModal（与应用工作台/应用角色同一套预览+保存流程）。
const grantOpen = ref(false)
const grantRoleId = ref('')
const grantRoleName = ref('')
// P390 作用域收敛：弹窗按角色 kind 隐藏越域码组；应用角色业务码只显示本命名空间
const grantRoleKind = ref<'' | 'platform' | 'tenant' | 'application'>('')
const grantRoleNamespace = ref('')
// 管理员不能管理管理员：非模板角色（自定义「管理员」）禁选授权权码，与后端 422 同口径。
const TEMPLATE_ROLE_KEYS = new Set(['platform.admin', 'tenant.admin', 'apps.admin', 'app.admin', 'app.member'])

function isTemplateRole(role: RoleRecord): boolean {
  return TEMPLATE_ROLE_KEYS.has(role.key)
}

function roleClassLabel(role: RoleRecord): string {
  return isTemplateRole(role) ? '系统模板' : '自定义平台角色'
}

function canGrantRole(role: RoleRecord): boolean {
  if (isPlatformSuperAdmin.value) return true
  // 预置模板只能改本级及以下：超管改全部，租户改租户及以下，多应用改多应用及以下，应用改应用及成员。
  if (role.key === 'platform.admin') return false
  if (role.key === 'tenant.admin') return cachedHas('org.manage')
  if (role.key === 'apps.admin') return cachedHas('org.manage') || cachedHas('rbac.app_role.assign')
  if (role.key === 'app.admin' || role.key === 'app.member') {
    return cachedHas('org.manage') || cachedHas('rbac.app_role.manage')
  }
  return cachedHas('org.manage') || cachedHas('rbac.app_role.manage')
}

// 模板按层级藏码；自定义平台角色按操作者可见集，超管不再被 kind=tenant 藏掉 L1 专属码。
function grantKindForRole(role: RoleRecord): '' | 'platform' | 'tenant' | 'application' {
  if (role.key === 'platform.admin') return 'platform'
  if (role.key === 'tenant.admin') return 'tenant'
  if (isTemplateRole(role)) return 'application'
  if (isPlatformSuperAdmin.value) return 'platform'
  if (cachedHas('org.manage')) return 'tenant'
  return 'application'
}

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
// 服务端筛选是否生效：有任一条件就不能复用壳层全量 500 条
function hasServerFilters(): boolean {
  return Boolean(submittedQuery.value || tenantFilter.value || statusFilter.value)
}

const columns = [
  { title: '角色名称', dataIndex: 'name', key: 'name', width: 168, ellipsis: true },
  { title: '角色标识', dataIndex: 'key', key: 'key', width: 150, ellipsis: true },
  { title: '租户', dataIndex: 'tenant_id', key: 'tenant_id', width: 110, ellipsis: true },
  { title: '应用范围', dataIndex: 'application_id', key: 'application_id', width: 110, ellipsis: true },
  { title: '权限', dataIndex: 'permission_codes', key: 'permission_codes', width: 140 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 88 },
  { title: '说明', dataIndex: 'description', key: 'description', width: 140, ellipsis: true },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 170, fixed: 'right' as const },
]
// 列宽合计 = 168+150+110+110+140+88+140+170 = 1076

// 操作列「更多」菜单（P350 对齐用户页收敛模式）：高频直达 + 低频收纳。
type RoleRowMenuKey = 'resource' | 'dataScope' | 'clone' | 'toggle' | 'delete' | 'holders'

function onRowMenuClick(info: { key: string | number }, role: RoleRecord): void {
  const key = String(info.key) as RoleRowMenuKey
  if (key === 'resource') openResourceGrantEditor(role)
  else if (key === 'dataScope') openDataScopeEditor(role)
  else if (key === 'clone') openClone(role)
  else if (key === 'toggle') confirmStatusChange(role)
  else if (key === 'delete') deleteRole(role)
  else if (key === 'holders') openHolders(role)
}

// G22 角色持有者反查：回答「改/停/删这个角色影响谁」；来源含直连绑定与组继承。
interface RoleHolder {
  user_id: string; email: string | null; display_name: string
  membership_status: string; sources: string[]; via_groups: string[]
}
const holdersOpen = ref(false)
const holdersLoading = ref(false)
const holdersRole = ref<RoleRecord | null>(null)
const holders = ref<RoleHolder[]>([])

function openHolders(role: RoleRecord): void {
  holdersRole.value = role
  holders.value = []
  holdersOpen.value = true
  void loadHolders(role)
}

async function loadHolders(role: RoleRecord): Promise<void> {
  holdersLoading.value = true
  try {
    const result = await api<{ items: RoleHolder[] }>(`/admin/roles/${role.id}/holders`)
    holders.value = result.items
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取角色持有者失败')
  } finally { holdersLoading.value = false }
}

// 删除角色（P352）：授权/绑定/组分配级联清除；被邀请引用或平台保护角色时后端 409/422。
function deleteRole(role: RoleRecord): void {
  Modal.confirm({
    title: `删除角色“${role.name}”？`,
    content: '将永久删除该角色及其权限授权、成员绑定、用户组分配和数据范围配置；持有该角色的成员凭证会立即失效。此操作不可恢复。',
    okText: '永久删除', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`/admin/roles/${role.id}`, { method: 'DELETE' })
        message.success('角色已删除')
        await loadRoles()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '删除角色失败') }
    },
  })
}

async function loadRoles(): Promise<void> {
  if (!props.active) return
  const sequence = ++requestSequence
  loading.value = true
  errorText.value = ''
  try {
    const params = new URLSearchParams()
    if (submittedQuery.value) params.set('q', submittedQuery.value)
    // P405：高级管理只出平台角色（五级模板 + 未钉应用的自定义角色）。
    params.set('role_class', 'platform')
    if (tenantFilter.value) params.set('tenant_id', tenantFilter.value)
    if (statusFilter.value) params.set('status', statusFilter.value)
    params.set('limit', String(listPageSize.value))
    params.set('offset', String((listPage.value - 1) * listPageSize.value))
    const result = await api<RoleRecord[] | { items: RoleRecord[]; total: number }>(`/admin/roles?${params}`)
    if (sequence === requestSequence && props.active) {
      const paged = asPagedList(result)
      roles.value = paged.items
      listTotal.value = paged.total
    }
  } catch (error) {
    if (sequence !== requestSequence) return
    roles.value = []
    listTotal.value = 0
    errorText.value = error instanceof Error ? error.message : '读取角色目录失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function onSearch(query: string): void {
  submittedQuery.value = query
  listPage.value = 1
  void loadRoles()
}

function onTableChange(pagination: TablePaginationConfig): void {
  listPage.value = pagination.current || 1
  listPageSize.value = pagination.pageSize || 20
  void loadRoles()
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
  return true
}

async function saveRole(): Promise<void> {
  if (!validateRoleForm()) return
  const editing = editingRole.value
  // 新建成功后要立刻挂码，先记下作用域，避免关弹窗后表单被清空
  const payload = editing
    ? { name: form.name.trim(), description: form.description.trim() || null }
    : {
        tenant_id: form.tenant_id,
        key: form.key.trim(),
        name: form.name.trim(),
        description: form.description.trim() || null,
      }
  savingRole.value = true
  try {
    const created = await api<RoleRecord>(editing ? `/admin/roles/${editing.id}` : '/admin/roles', {
      method: editing ? 'PATCH' : 'POST', body: JSON.stringify(payload),
    })
    message.success(editing ? '角色已更新' : '角色已创建')
    editorOpen.value = false
    await loadRoles()
    emit('changed')
    if (!editing && created?.id) {
      Modal.confirm({
        title: '角色已创建，现在配置权限？',
        content: '为该角色挂上权限编码后，成员才能真正获得能力。',
        okText: '去挂码',
        cancelText: '稍后',
        onOk: () => {
          openGrantEditor({
            ...created,
            application_id: created.application_id ?? null,
            kind: created.kind || 'tenant',
            description: created.description ?? null,
            status: created.status || 'active',
            permission_codes: created.permission_codes || [],
          })
        },
      })
    }
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

function openGrantEditor(role: RoleRecord): void {
  grantRoleId.value = role.id
  grantRoleName.value = role.name
  grantRoleKind.value = grantKindForRole(role)
  grantRoleNamespace.value = role.application_id
    ? props.applications.find(application => application.id === role.application_id)?.permission_namespace || ''
    : ''
  grantOpen.value = true
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
    const permissions = asPagedList(await api<PermissionRecord[] | { items: PermissionRecord[] }>('/admin/permissions?limit=1000')).items
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

/** 共享挂码弹窗保存成功后：刷新角色目录（permission_codes 汇总列）并向上冒泡。 */
async function onGrantsSaved(): Promise<void> {
  await loadRoles()
  emit('changed')
}

async function openDataScopeEditor(role: RoleRecord): Promise<void> {
  dataScopeRoleId.value = role.id
  try {
    const [permissions, organizations, configured] = await Promise.all([
      api<PermissionRecord[] | { items: PermissionRecord[] }>('/admin/permissions?limit=1000').then(result => asPagedList(result).items),
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

function tenantName(id: string): string {
  return props.tenants.find(tenant => tenant.id === id)?.name || id
}

function applicationName(id: string | null): string {
  if (!id) return '全部应用'
  return props.applications.find(application => application.id === id)?.name || id
}

watch(() => props.active, active => {
  if (!active) return
  void loadRoles()
}, { immediate: true })

watch([tenantFilter, statusFilter], () => {
  listPage.value = 1
  if (props.active) void loadRoles()
})
</script>

<template>
  <AdminListPage
    eyebrow="平台角色"
    title="平台角色"
    subtitle="四个管理员都可给本级及以下预置角色配权，只能勾自己已有的码，不能配上级权限。应用角色请到「应用工作台 → 角色」。"
    :hint="`超管 27 码，租户管理员 20 码，多应用管理员 16 码，应用管理员 15 码；看不见的上级码不会出现。共 ${listTotal} 条角色`"
    :columns="columns"
    :data-source="roles"
    :loading="loading"
    row-key="id"
    class="scroll-actions-on-mobile"
    :scroll="{ x: 1076, y: 'calc(100vh - 430px)' }"
    :pagination="{ current: listPage, pageSize: listPageSize, total: listTotal, showSizeChanger: true, showTotal: (total: number) => `共 ${total} 条` }"
    @table-change="onTableChange"
    :error-text="errorText"
    empty-emoji="🎭"
    :empty-text="hasServerFilters() ? '没有匹配条件的角色' : '暂无角色，可创建角色后配置权限'"
  >
    <template #header-extra>
      <a-button v-if="canCreateRoles" type="primary" @click="openCreate">＋ 新建平台角色</a-button>
    </template>
    <AdminSearchField v-model="searchText" placeholder="搜索角色名称、标识或说明" @search="onSearch" />
    <a-select v-model:value="tenantFilter" allow-clear show-search option-filter-prop="label" placeholder="全部租户" :options="tenantOptions" class="admin-filter-wide" />
    <a-select v-model:value="statusFilter" allow-clear placeholder="全部状态" :options="statusOptions" />
    <template #actions>
      <a-button :loading="loading" @click="loadRoles">刷新</a-button>
    </template>
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'name'">
        <!-- P386 角色名称 + 作用域小标签：一眼分辨平台/租户/应用三级（中性灰阶，随深浅主题自适应） -->
        <div class="role-name-cell">
          <span class="role-name-text">{{ record.name }}</span>
          <span class="kind-chip" :class="isTemplateRole(record as RoleRecord) ? 'kind-platform' : 'kind-application'">{{ roleClassLabel(record as RoleRecord) }}</span>
        </div>
      </template>
      <template v-else-if="column.key === 'tenant_id'">{{ tenantName(String(record.tenant_id)) }}</template>
      <template v-else-if="column.key === 'application_id'">{{ applicationName(record.application_id ? String(record.application_id) : null) }}</template>
      <template v-else-if="column.key === 'permission_codes'">
        <a-tooltip :title="Array.isArray(record.permission_codes) ? record.permission_codes.join('、') || '尚未授予权限' : ''">
          <a-button type="link" size="small" class="px-0" @click="openGrantEditor(record as RoleRecord)">
            {{ Array.isArray(record.permission_codes) ? `${record.permission_codes.length} 项` : '0 项' }}
          </a-button>
        </a-tooltip>
      </template>
      <template v-else-if="column.key === 'status'">
        <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
      </template>
      <template v-else-if="column.key === 'actions'">
        <a-button v-if="canMutateRoleMeta" type="link" size="small" @click="openEdit(record as RoleRecord)">编辑</a-button>
        <a-button v-if="canGrantRole(record as RoleRecord)" type="link" size="small" @click="openGrantEditor(record as RoleRecord)">配置权限</a-button>
        <a-dropdown v-if="canMutateRoleMeta">
          <a-button type="link" size="small" class="flex items-center gap-1">
            更多
            <DownOutlined class="text-[11px]" />
          </a-button>
          <template #overlay>
            <a-menu @click="onRowMenuClick($event, record as RoleRecord)">
              <a-menu-item key="resource">实例资源授权</a-menu-item>
              <a-menu-item key="dataScope">数据范围</a-menu-item>
              <a-menu-item key="holders">查看持有者</a-menu-item>
              <a-menu-item key="clone">复制</a-menu-item>
              <a-menu-divider />
              <a-menu-item key="toggle" :danger="record.status === 'active'">{{ record.status === 'active' ? '停用' : '启用' }}</a-menu-item>
              <a-menu-item key="delete" danger>删除角色</a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
        <a-button v-if="!canGrantRole(record as RoleRecord)" type="link" size="small" @click="openGrantEditor(record as RoleRecord)">查看权限</a-button>
      </template>
    </template>
  </AdminListPage>

  <a-modal v-model:open="editorOpen" :title="editingRole ? `编辑角色：${editingRole.name}` : '新建角色'" ok-text="保存" cancel-text="取消" :confirm-loading="savingRole" @ok="saveRole">
    <a-form layout="vertical" class="create-form">
      <template v-if="editingRole">
        <a-form-item label="角色分类"><a-input :value="editingRole ? roleClassLabel(editingRole) : ''" disabled /></a-form-item>
        <a-form-item label="所属租户"><a-input :value="tenantName(form.tenant_id)" disabled /></a-form-item>
        <a-form-item label="应用范围"><a-input :value="applicationName(form.application_id || null)" disabled /></a-form-item>
        <a-form-item label="角色标识"><a-input v-model:value="form.key" disabled /></a-form-item>
      </template>
      <template v-else>
        <a-alert type="info" show-icon message="这里只建自定义平台角色" description="系统五级模板不可新建。应用角色（财务 / 只读）请到应用工作台 → 角色。" class="mb-4" />
        <a-form-item label="所属租户" required><a-select v-model:value="form.tenant_id" :options="tenantOptions.filter(option => props.tenants.find(tenant => tenant.id === option.value)?.status === 'active')" /></a-form-item>
        <a-form-item label="角色标识" required help="2–100 位小写字母、数字、点、下划线或连字符"><a-input v-model:value="form.key" :maxlength="100" placeholder="ops.reviewer" /></a-form-item>
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
        description="默认不复制授权。勾选后只复制权限编码目录当前启用的授权及其数据范围；直接成员绑定和用户组角色绑定永远不会复制。"
      />
    </a-form>
  </a-modal>

  <!-- 挂码编辑：共享弹窗负责目录加载、影响预览与原子保存（平台模式：停用码禁选）。 -->
  <RolePermissionGrantModal
    v-model:open="grantOpen"
    :role-id="grantRoleId"
    :role-name="grantRoleName"
    :lock-authority-codes="false"
    :role-kind="grantRoleKind"
    :role-namespace="grantRoleNamespace"
    catalog-path="/admin/permissions?limit=1000"
    :grants-path="grantRoleId ? `/admin/roles/${grantRoleId}/permissions` : ''"
    @saved="onGrantsSaved"
  />

  <a-modal v-model:open="resourceGrantDialogOpen" title="配置实例资源授权" width="820px" :footer="null">
    <div class="resource-grant-editor">
      <a-alert
        type="info"
        show-icon
        message="实例资源授权按权限编码 + 资源 ID 精确匹配，与工作台「配置资源」（应用资源树）不是一回事"
        description="资源 ID 使用业务系统自己的稳定标识（例如业务对象的 UUID）。日常菜单/按钮授权请走应用工作台「配置资源」。"
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
          placeholder="资源 ID，例如业务对象的 UUID"
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
              <!-- 描述可用时以中文为主文案，编码降为辅助信息。 -->
              <strong>{{ grant.description?.trim() || grant.code }}</strong>
              <code>{{ grant.description?.trim() ? grant.code : grant.resource_id }}</code>
              <code v-if="grant.description?.trim()">{{ grant.resource_id }}</code>
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
      <div class="flex min-w-0 flex-col">
        <strong>{{ entry.permission_description || entry.permission_code }}</strong>
        <span class="font-mono text-xs text-[var(--color-text-muted)]">{{ entry.permission_code }}</span>
      </div>
      <a-select v-model:value="entry.scope_type" allow-clear placeholder="不授予数据范围" :options="[{ value: 'tenant', label: '当前租户全部数据' }, { value: 'self', label: '仅本人数据' }, { value: 'organization', label: '所属组织' }, { value: 'organization_tree', label: '所属组织及下级' }, { value: 'selected_organizations', label: '指定组织' }]" />
      <a-select v-if="entry.scope_type === 'selected_organizations'" v-model:value="entry.organization_ids" mode="multiple" :options="dataScopeOrganizationOptions" placeholder="选择允许访问的组织" />
    </div>
  </a-modal>

  <!-- G22 角色持有者反查弹窗：直连绑定与组继承来源标注，改/停/删角色前的影响面评估。 -->
  <a-modal v-model:open="holdersOpen" :title="`角色持有者 — ${holdersRole?.name || ''}`" :footer="null" width="720px">
    <a-spin :spinning="holdersLoading">
      <p class="mb-2 text-xs text-[var(--color-text-muted)]">
        共 {{ holders.length }} 名成员持有该角色（{{ holdersRole?.key }}）；「组继承」表示经用户组获得，停用组即失效。
      </p>
      <a-empty v-if="!holdersLoading && !holders.length" description="没有任何成员持有该角色" />
      <a-table v-else :data-source="holders" row-key="user_id" size="small" :pagination="false"
        :scroll="{ y: 420 }"
        :columns="[
          { title: '成员', dataIndex: 'display_name', key: 'display_name', width: 140 },
          { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
          { title: '成员状态', key: 'membership_status', width: 100 },
          { title: '来源', key: 'sources', width: 180 },
        ]">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'membership_status'">
            <a-tag :color="(record as RoleHolder).membership_status === 'active' ? 'green' : 'default'">
              {{ (record as RoleHolder).membership_status === 'active' ? '在职' : (record as RoleHolder).membership_status }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'sources'">
            <a-space :size="4" wrap>
              <a-tag v-if="(record as RoleHolder).sources.includes('direct')" class="font-mono">直连</a-tag>
              <a-tooltip v-if="(record as RoleHolder).sources.includes('group')"
                :title="`经用户组：${(record as RoleHolder).via_groups.join('、')}`">
                <a-tag class="font-mono">组继承</a-tag>
              </a-tooltip>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-spin>
  </a-modal>
</template>

<style scoped>
.role-toolbar { flex-wrap: wrap; }
.role-search { width: min(100%, 360px); }
.role-tenant-filter { width: min(100%, 260px); }
/* P386 作用域筛选器与名称列三级 tag（中性灰阶 token，深浅主题自适应） */
.role-kind-filter { width: min(100%, 180px); }
.role-name-cell { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.role-name-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kind-chip {
  align-self: flex-start;
  display: inline-block;
  font-size: 11px;
  line-height: 18px;
  padding: 0 8px;
  border-radius: 999px;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}
.kind-chip.kind-platform { color: var(--color-text-primary); border-color: var(--color-border-strong); font-weight: 600; }
.kind-chip.kind-application { border-style: dashed; }
.scope-hint { margin-bottom: 16px; }
/* P390 作用域向导三卡：平台禁选置灰，选中黑边浅底（与授权弹窗卡片语言一致） */
.scope-wizard { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 16px; }
.scope-card {
  display: flex; flex-direction: column; gap: 3px; padding: 12px 14px;
  border: 1px solid var(--color-border); border-radius: 10px;
  background: transparent; cursor: pointer; text-align: left;
  transition: border-color .15s, background .15s;
}
.scope-card:hover:not(:disabled) { border-color: var(--color-border-strong); }
.scope-card.active { border-color: var(--color-text-primary); background: var(--color-border); box-shadow: inset 3px 0 0 var(--color-text-primary); }
.scope-card:disabled { cursor: not-allowed; opacity: .55; background: transparent; }
.scope-card-name { font-weight: 600; font-size: 13.5px; color: var(--color-text-primary); }
.scope-card-hint { font-size: 11.5px; color: var(--color-text-muted); }
@media (max-width: 700px) { .scope-wizard { grid-template-columns: 1fr; } }
.clone-policy-note { margin-top: 12px; }
/* 资源级授权表单在桌面横向排列，窄屏折叠为单列，长资源 ID 自动换行。 */
.resource-grant-editor { display: grid; gap: 16px; }
.resource-grant-form { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(220px, 1.4fr) auto; gap: 10px; }
.resource-grant-list { display: grid; max-height: 320px; overflow: auto; border: 1px solid var(--color-border); border-radius: 10px; }
.resource-grant-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px 14px; border-bottom: 1px solid var(--color-border); }
.resource-grant-row:last-child { border-bottom: 0; }
.resource-grant-identity { display: grid; min-width: 0; gap: 5px; }
.resource-grant-identity code { overflow-wrap: anywhere; color: var(--color-text-secondary); }
.resource-grant-empty { padding: 24px 12px; color: var(--color-text-secondary); text-align: center; }
@media (max-width: 650px) {
  .role-search, .role-tenant-filter, .role-kind-filter { width: 100%; }
  .resource-grant-form { grid-template-columns: 1fr; }
}
</style>

