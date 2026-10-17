<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '../../shared/services/api'

interface TenantOption { id: string; name: string; status: string; can_read_organizations?: boolean; can_manage_organizations?: boolean }
interface MemberRecord {
  user_id: string
  tenant_id: string
  email: string | null
  display_name: string
  user_status: string
  membership_status: string
  created_at: string
}
interface RoleRecord { id: string; tenant_id: string; application_id: string | null; key: string; name: string; status: string }
interface OrganizationRecord { id: string; tenant_id: string; key: string; name: string; status: string }
interface PermissionRecord { id: string; code: string; status: string }
interface DataScopeRecord { permission_id: string; permission_code: string; scope_type: string; organization_ids: string[] }
type ScopeType = '' | 'tenant' | 'self' | 'organization' | 'organization_tree' | 'selected_organizations'
interface ScopeEntry { permission_id: string; permission_code: string; permission_status: string; scope_type: ScopeType; organization_ids: string[] }

const props = defineProps<{ active: boolean; tenants: TenantOption[] }>()
const activeTab = ref<'members' | 'scopes'>('members')
const tenantId = ref('')
const canManage = computed(() => props.tenants.some(tenant => tenant.id === tenantId.value && tenant.can_manage_organizations === true))
const tenantOptions = computed(() => props.tenants.map(tenant => ({ value: tenant.id, label: tenant.name })))
const organizations = ref<OrganizationRecord[]>([])
const activeOrganizationOptions = computed(() => organizations.value
  .filter(organization => organization.status === 'active')
  .map(organization => ({ value: organization.id, label: `${organization.name} (${organization.key})` })))
const allOrganizationOptions = computed(() => organizations.value.map(organization => ({
  value: organization.id,
  label: `${organization.status === 'active' ? '' : '已停用 · '}${organization.name} (${organization.key})`,
})))

const memberQuery = ref('')
const members = ref<MemberRecord[]>([])
const memberTotal = ref(0)
const memberPage = ref(1)
const memberPageSize = 20
const membersLoading = ref(false)
const memberDialogOpen = ref(false)
const memberSaving = ref(false)
const editingMember = ref<MemberRecord | null>(null)
const memberOrganizationIds = ref<string[]>([])
const primaryOrganizationId = ref('')
const memberInactiveOrganizationIds = computed(() => memberOrganizationIds.value.filter(id =>
  organizations.value.some(organization => organization.id === id && organization.status !== 'active')))
const selectedPrimaryOptions = computed(() => allOrganizationOptions.value
  .filter(option => memberOrganizationIds.value.includes(option.value)))

const roles = ref<RoleRecord[]>([])
const rolesLoading = ref(false)
const scopeDialogOpen = ref(false)
const scopeSaving = ref(false)
const scopeRole = ref<RoleRecord | null>(null)
const scopeEntries = ref<ScopeEntry[]>([])
const scopeInactiveOrganizationIds = computed(() => {
  const inactiveIds = scopeEntries.value
    .filter(entry => entry.scope_type === 'selected_organizations')
    .flatMap(entry => entry.organization_ids)
    .filter(id => organizations.value.some(organization => organization.id === id && organization.status !== 'active'))
  return [...new Set(inactiveIds)]
})

let membersSequence = 0
let organizationsSequence = 0
let rolesSequence = 0

const memberColumns = computed(() => [
  { title: '成员', dataIndex: 'display_name', key: 'display_name', width: 180, ellipsis: true },
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 240, ellipsis: true },
  { title: '账号状态', dataIndex: 'user_status', key: 'user_status', width: 110 },
  { title: '租户成员状态', dataIndex: 'membership_status', key: 'membership_status', width: 130 },
  ...(canManage.value ? [{ title: '操作', dataIndex: 'actions', key: 'actions', width: 150, fixed: 'right' as const }] : []),
])
const roleColumns = computed(() => [
  { title: '角色', dataIndex: 'name', key: 'name', width: 220, ellipsis: true },
  { title: '标识', dataIndex: 'key', key: 'key', width: 200, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '应用范围', dataIndex: 'application_id', key: 'application_id', width: 220, ellipsis: true },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 140, fixed: 'right' as const },
])

async function loadMembers(page = memberPage.value): Promise<void> {
  if (!props.active || !tenantId.value) return
  const sequence = ++membersSequence
  membersLoading.value = true
  try {
    const params = new URLSearchParams({ tenant_id: tenantId.value, limit: String(memberPageSize), offset: String((page - 1) * memberPageSize) })
    if (memberQuery.value.trim()) params.set('q', memberQuery.value.trim())
    const result = await api<{ items: MemberRecord[]; total: number }>(`/tenant-admin/members?${params.toString()}`)
    if (sequence !== membersSequence) return
    members.value = result.items
    memberTotal.value = result.total
    memberPage.value = page
  } catch (error) {
    if (sequence === membersSequence) message.error(error instanceof Error ? error.message : '读取租户成员失败')
  } finally { if (sequence === membersSequence) membersLoading.value = false }
}

async function loadOrganizations(): Promise<void> {
  if (!props.active || !tenantId.value) return
  const sequence = ++organizationsSequence
  try {
    const rows = await api<OrganizationRecord[]>(`/tenant-admin/organizations?tenant_id=${encodeURIComponent(tenantId.value)}`)
    if (sequence === organizationsSequence) organizations.value = rows
  } catch (error) {
    if (sequence === organizationsSequence) message.error(error instanceof Error ? error.message : '读取组织列表失败')
  }
}

async function loadRoles(): Promise<void> {
  if (!props.active || !tenantId.value) return
  const sequence = ++rolesSequence
  rolesLoading.value = true
  try {
    const rows = await api<RoleRecord[]>(`/tenant-admin/roles?tenant_id=${encodeURIComponent(tenantId.value)}`)
    if (sequence === rolesSequence) roles.value = rows
  } catch (error) {
    if (sequence === rolesSequence) message.error(error instanceof Error ? error.message : '读取租户角色失败')
  } finally { if (sequence === rolesSequence) rolesLoading.value = false }
}

async function refreshAll(): Promise<void> {
  await Promise.all([loadOrganizations(), loadMembers(1), loadRoles()])
}

function onMemberPageChange(pagination: { current?: number }): void {
  void loadMembers(pagination.current || 1)
}

async function openMemberOrganizations(member: MemberRecord): Promise<void> {
  if (!canManage.value || member.membership_status !== 'active' || member.user_status !== 'active') return
  try {
    const result = await api<{ organization_ids: string[]; primary_organization_id: string | null }>(
      `/tenant-admin/users/${member.user_id}/organizations?tenant_id=${encodeURIComponent(tenantId.value)}`,
    )
    editingMember.value = member
    memberOrganizationIds.value = result.organization_ids
    primaryOrganizationId.value = result.primary_organization_id || ''
    memberDialogOpen.value = true
  } catch (error) { message.error(error instanceof Error ? error.message : '读取成员组织归属失败') }
}

watch(memberOrganizationIds, selected => {
  if (primaryOrganizationId.value && !selected.includes(primaryOrganizationId.value)) primaryOrganizationId.value = ''
})

async function saveMemberOrganizations(): Promise<void> {
  if (!canManage.value || !editingMember.value) return
  if (memberInactiveOrganizationIds.value.length) {
    message.error('请先移除已停用组织，再保存成员归属')
    return
  }
  if (primaryOrganizationId.value && !memberOrganizationIds.value.includes(primaryOrganizationId.value)) {
    message.error('主组织必须包含在成员组织列表中')
    return
  }
  memberSaving.value = true
  try {
    await api(`/tenant-admin/users/${editingMember.value.user_id}/organizations`, {
      method: 'PUT',
      body: JSON.stringify({
        tenant_id: tenantId.value,
        organization_ids: memberOrganizationIds.value,
        primary_organization_id: primaryOrganizationId.value || null,
      }),
    })
    message.success('成员组织归属已更新')
    memberDialogOpen.value = false
    await loadMembers()
  } catch (error) { message.error(error instanceof Error ? error.message : '更新成员组织归属失败') }
  finally { memberSaving.value = false }
}

async function openRoleScopes(role: RoleRecord): Promise<void> {
  scopeRole.value = role
  try {
    const [permissionRows, savedPolicies] = await Promise.all([
      api<PermissionRecord[]>(`/tenant-admin/roles/${role.id}/permissions`),
      api<DataScopeRecord[]>(`/tenant-admin/roles/${role.id}/data-scopes`),
    ])
    scopeEntries.value = permissionRows.map(permission => {
      const policy = savedPolicies.find(item => item.permission_id === permission.id)
      return {
        permission_id: permission.id,
        permission_code: permission.code,
        permission_status: permission.status,
        scope_type: (policy?.scope_type || '') as ScopeType,
        organization_ids: policy?.organization_ids || [],
      }
    })
    scopeDialogOpen.value = true
  } catch (error) { message.error(error instanceof Error ? error.message : '读取角色数据范围失败') }
}

async function saveRoleScopes(): Promise<void> {
  if (!canManage.value || !scopeRole.value) return
  if (scopeEntries.value.some(entry => entry.scope_type === 'selected_organizations' && !entry.organization_ids.length)) {
    message.error('指定组织范围至少选择一个组织')
    return
  }
  if (scopeInactiveOrganizationIds.value.length) {
    message.error('已停用组织不能保留在指定组织范围中，请先移除')
    return
  }
  scopeSaving.value = true
  try {
    const policies = scopeEntries.value.filter(entry => entry.scope_type).map(entry => ({
      permission_id: entry.permission_id,
      scope_type: entry.scope_type,
      organization_ids: entry.scope_type === 'selected_organizations' ? entry.organization_ids : [],
    }))
    await api(`/tenant-admin/roles/${scopeRole.value.id}/data-scopes`, {
      method: 'PUT', body: JSON.stringify({ policies }),
    })
    message.success('角色数据范围已保存')
    scopeDialogOpen.value = false
  } catch (error) { message.error(error instanceof Error ? error.message : '保存角色数据范围失败') }
  finally { scopeSaving.value = false }
}

function statusLabel(status: string): string {
  return status === 'active' ? '启用' : '停用'
}

watch(() => props.tenants, available => {
  if (!available.some(tenant => tenant.id === tenantId.value)) tenantId.value = available[0]?.id || ''
}, { deep: true, immediate: true })
watch(() => [props.active, tenantId.value] as const, ([active, selectedTenant]) => {
  if (active && selectedTenant) void refreshAll()
}, { immediate: true })
</script>

<template>
  <section class="tenant-access-page">
    <header class="page-heading">
      <div><p class="eyebrow">TENANT ACCESS CONTROL</p><h1>成员与数据范围</h1>
        <p class="subtitle">在当前租户内维护成员组织归属，并为角色已获得的权限配置数据过滤范围。</p></div>
    </header>

    <a-card class="data-card" :bordered="false">
      <div class="table-toolbar">
        <a-select v-model:value="tenantId" class="tenant-filter" placeholder="选择租户" :options="tenantOptions" />
        <span class="table-hint">{{ canManage ? '修改会记录审计；业务系统仍需执行 IAM 返回的数据过滤条件。' : '当前角色为只读；需要 iam.organization.manage 才能保存变更。' }}</span>
        <a-button :loading="membersLoading || rolesLoading" :disabled="!tenantId" @click="refreshAll">刷新</a-button>
      </div>

      <a-tabs v-model:active-key="activeTab">
        <a-tab-pane key="members" tab="成员组织归属">
          <div class="sub-toolbar">
            <a-input-search v-model:value="memberQuery" class="member-search" placeholder="搜索姓名或邮箱" enter-button="搜索" @search="() => loadMembers(1)" />
            <span class="table-hint">仅显示当前租户成员；跨租户身份不会出现在此列表。</span>
          </div>
          <a-table :data-source="members" :columns="memberColumns" :loading="membersLoading" row-key="user_id"
            :scroll="{ x: 860 }" :pagination="{ current: memberPage, pageSize: memberPageSize, total: memberTotal, showSizeChanger: false }"
            @change="onMemberPageChange">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'user_status'">
                <a-tag :color="record.user_status === 'active' ? 'green' : 'default'">{{ statusLabel(record.user_status) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'membership_status'">
                <a-tag :color="record.membership_status === 'active' ? 'blue' : 'default'">{{ statusLabel(record.membership_status) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-button type="link" size="small" :disabled="record.user_status !== 'active' || record.membership_status !== 'active'" @click="openMemberOrganizations(record)">配置组织</a-button>
              </template>
            </template>
            <template #emptyText><a-empty description="该租户暂无匹配成员" /></template>
          </a-table>
        </a-tab-pane>

        <a-tab-pane key="scopes" tab="角色数据范围">
          <a-alert class="scope-notice" type="info" show-icon
            message="数据范围按角色和已授予权限配置。未配置有效范围时，业务端请求 include_data_scope 会默认拒绝。"
            description="配置只描述过滤条件。业务服务必须映射本地字段并在查询时执行。当前试点 DeerFlow 的项目、线程、运行和文档按本人过滤。" />
          <a-table :data-source="roles" :columns="roleColumns" :loading="rolesLoading" row-key="id"
            :scroll="{ x: 820 }" :pagination="{ pageSize: 10, showSizeChanger: true }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ statusLabel(record.status) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'application_id'">{{ record.application_id || '租户通用' }}</template>
              <template v-else-if="column.key === 'actions'">
                <a-button type="link" size="small" @click="openRoleScopes(record)">{{ canManage ? '配置范围' : '查看范围' }}</a-button>
              </template>
            </template>
            <template #emptyText><a-empty description="该租户暂无角色" /></template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <a-modal v-model:open="memberDialogOpen" :title="`配置「${editingMember?.display_name || '成员'}」的组织归属`"
      ok-text="保存归属" cancel-text="取消" :confirm-loading="memberSaving" :ok-button-props="{ disabled: !canManage || memberInactiveOrganizationIds.length > 0 }" @ok="saveMemberOrganizations">
      <a-form layout="vertical">
        <a-form-item label="所属组织">
          <a-select v-model:value="memberOrganizationIds" mode="multiple" :options="allOrganizationOptions" placeholder="选择一个或多个启用组织" />
        </a-form-item>
        <a-form-item label="主组织（可选）">
          <a-select v-model:value="primaryOrganizationId" allow-clear :options="selectedPrimaryOptions" placeholder="不指定主组织" />
        </a-form-item>
        <a-alert v-if="memberInactiveOrganizationIds.length" type="warning" show-icon
          message="成员已关联停用组织，请从上方选择中移除后再保存。" />
      </a-form>
    </a-modal>

    <a-modal v-model:open="scopeDialogOpen" :title="`配置「${scopeRole?.name || '角色'}」的数据范围`" width="800px"
      ok-text="保存范围" cancel-text="关闭" :confirm-loading="scopeSaving"
      :ok-button-props="{ style: { display: canManage ? undefined : 'none' }, disabled: scopeInactiveOrganizationIds.length > 0 }" @ok="saveRoleScopes">
      <a-alert v-if="!scopeEntries.length" type="warning" show-icon class="scope-notice"
        message="该角色尚未获得权限，无法配置数据范围。" />
      <div v-else class="scope-policy-list">
        <div v-for="entry in scopeEntries" :key="entry.permission_id" class="scope-policy-row">
          <div class="scope-permission"><strong>{{ entry.permission_code }}</strong><a-tag v-if="entry.permission_status === 'disabled'" color="default">权限已停用</a-tag></div>
          <a-select v-model:value="entry.scope_type" allow-clear :disabled="!canManage" placeholder="未配置（请求数据范围时默认拒绝）"
            :options="[{ value: 'tenant', label: '当前租户全部数据' }, { value: 'self', label: '仅本人数据' }, { value: 'organization', label: '所属组织' }, { value: 'organization_tree', label: '所属组织及下级' }, { value: 'selected_organizations', label: '指定组织' }]" />
          <a-select v-if="entry.scope_type === 'selected_organizations'" v-model:value="entry.organization_ids" mode="multiple"
            :disabled="!canManage" :options="allOrganizationOptions" placeholder="选择允许访问的组织" />
        </div>
      </div>
      <a-alert v-if="scopeInactiveOrganizationIds.length" type="warning" show-icon class="scope-notice"
        message="指定范围包含已停用组织，请先移除后保存。" />
      <template #footer>
        <a-button @click="scopeDialogOpen = false">关闭</a-button>
        <a-button v-if="canManage" type="primary" :loading="scopeSaving" :disabled="scopeInactiveOrganizationIds.length > 0" @click="saveRoleScopes">保存范围</a-button>
      </template>
    </a-modal>
  </section>
</template>

<style scoped>
.tenant-access-page { display: grid; gap: 20px; }
.page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.page-heading h1 { margin: 5px 0 7px; font-size: clamp(25px, 3vw, 32px); letter-spacing: -.035em; }
.page-heading .subtitle { max-width: 800px; margin: 0; color: #7c8798; line-height: 1.65; }
.eyebrow { margin: 0; color: #766fe8; font-size: 11px; font-weight: 750; letter-spacing: .14em; }
.data-card { border-radius: 16px; }
.table-toolbar, .sub-toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.tenant-filter { width: min(280px, 100%); flex: 0 0 auto; }
.member-search { width: min(360px, 100%); }
.table-hint { flex: 1; color: #7c8798; font-size: 12px; }
.scope-notice { margin-bottom: 16px; }
.scope-policy-list { display: grid; gap: 12px; max-height: 54vh; overflow: auto; padding-right: 4px; }
.scope-policy-row { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(220px, 1.1fr); gap: 10px; align-items: start; padding: 12px; border: 1px solid #e8ebf2; border-radius: 10px; }
.scope-policy-row > :last-child:nth-child(3) { grid-column: 2; }
.scope-permission { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-height: 32px; overflow-wrap: anywhere; }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
  .table-toolbar, .sub-toolbar { align-items: stretch; flex-direction: column; }
  .tenant-filter, .member-search { width: 100%; }
  .scope-policy-row { grid-template-columns: 1fr; }
  .scope-policy-row > :last-child:nth-child(3) { grid-column: 1; }
}
</style>
