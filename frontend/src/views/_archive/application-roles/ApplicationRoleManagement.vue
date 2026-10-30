<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { PERMISSION_SCOPES, resolvePermissionScope } from '@/utils/permissionGroups'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminTableToolbar from '@/components/AdminTableToolbar.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'

interface TenantOption { id: string; name: string; can_read_applications?: boolean }
interface ApplicationRecord {
  id: string
  tenant_id: string
  name: string
  client_id: string
  status: string
  can_manage?: boolean
}
interface RoleRecord {
  id: string
  tenant_id: string
  application_id: string
  key: string
  name: string
  description: string | null
  status: 'active' | 'disabled'
  permission_codes: string[]
}
interface PermissionRecord {
  id: string
  code: string
  description?: string | null
  resource_type: string
  scope: string
  status: 'active' | 'disabled'
}
interface PermissionOption {
  label: string
  value: string
  code: string
  description: string
  scope: string
  disabled?: boolean
}
interface RoleAssignment { id: string; key: string; name: string; status: string; sources: ('direct' | 'group')[] }
interface MemberRecord { user_id: string; email: string | null; display_name: string; roles: RoleAssignment[] }
interface PermissionImpact {
  current_permission_ids: string[]
  grant_permission_codes: string[]
  revoke_permission_codes: string[]
  potentially_affected_members: number
  analysis_note: string
  permission_impacts: { permission_code: string; action: 'grant' | 'revoke'; eligible_members: number; covered_by_other_general_roles: number; potentially_affected_members: number }[]
}

const props = defineProps<{ active: boolean; tenants: TenantOption[] }>()
const applications = ref<ApplicationRecord[]>([])
const applicationId = ref('')
const roles = ref<RoleRecord[]>([])
const members = ref<MemberRecord[]>([])
const memberTotal = ref(0)
const memberPage = ref(1)
const memberQuery = ref('')
const loadingApplications = ref(false)
const loadingRoles = ref(false)
const loadingMembers = ref(false)
const errorText = ref('')

const roleDialogOpen = ref(false)
const roleSaving = ref(false)
const editingRole = ref<RoleRecord | null>(null)
const roleForm = reactive({ key: '', name: '', description: '' })

const permissionDialogOpen = ref(false)
const permissionSaving = ref(false)
const permissionLoading = ref(false)
const permissionOptions = ref<PermissionOption[]>([])
const permissionIds = ref<string[]>([])
const permissionImpact = ref<PermissionImpact | null>(null)
const permissionPreviewKey = ref('')
const permissionRole = ref<RoleRecord | null>(null)
const impactLoading = ref(false)

const memberEmail = ref('')
const memberRoleId = ref('')
const memberSaving = ref(false)

let applicationSequence = 0
let roleSequence = 0
let memberSequence = 0

const readableTenants = computed(() => props.tenants.filter(tenant => tenant.can_read_applications))
const selectedApplication = computed(() => applications.value.find(application => application.id === applicationId.value) || null)
const canManage = computed(() => selectedApplication.value?.can_manage === true)
const canAssign = computed(() => canManage.value && selectedApplication.value?.status === 'active')
const roleSelectOptions = computed(() => roles.value
  .filter(role => role.status === 'active')
  .map(role => ({ value: role.id, label: `${role.name}（${role.key}）` })))
const roleColumns = computed(() => [
  { title: '角色名称', dataIndex: 'name', key: 'name', width: 170, ellipsis: true },
  { title: '角色标识', dataIndex: 'key', key: 'key', width: 180, ellipsis: true },
  { title: '权限编码', dataIndex: 'permission_codes', key: 'permissions', width: 320 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  ...(canManage.value ? [{ title: '操作', dataIndex: 'actions', key: 'actions', width: 280, fixed: 'right' as const }] : []),
])
const memberColumns = computed(() => [
  { title: '成员', dataIndex: 'display_name', key: 'display_name', width: 180, ellipsis: true },
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 230, ellipsis: true },
  { title: '应用角色', dataIndex: 'roles', key: 'roles', width: 430 },
])
const permissionSelectionKey = computed(() => [...permissionIds.value].sort().join('|'))
const previewIsCurrent = computed(() => Boolean(permissionImpact.value)
  && permissionPreviewKey.value === permissionSelectionKey.value)
// 按租户 / 应用 / 业务码分组，方便在权限平台页勾选看得见的管理码。
const permissionGroups = computed(() => {
  const buckets = new Map<string, PermissionOption[]>()
  for (const option of permissionOptions.value) {
    const list = buckets.get(option.scope) || []
    list.push(option)
    buckets.set(option.scope, list)
  }
  return PERMISSION_SCOPES
    .filter(scope => (buckets.get(scope.key) || []).length)
    .map(scope => ({
      key: scope.key,
      label: scope.label,
      hint: scope.hint,
      options: buckets.get(scope.key) || [],
    }))
})

async function loadApplications(): Promise<void> {
  if (!props.active) return
  const sequence = ++applicationSequence
  loadingApplications.value = true
  errorText.value = ''
  try {
    const scoped = await Promise.all(readableTenants.value.map(tenant =>
      api<ApplicationRecord[]>(`/tenant-admin/applications?tenant_id=${encodeURIComponent(tenant.id)}`).catch(() => []),
    ))
    if (sequence !== applicationSequence || !props.active) return
    applications.value = scoped.flat().filter(application => application.can_manage !== undefined)
    if (!applications.value.some(application => application.id === applicationId.value)) {
      applicationId.value = applications.value[0]?.id || ''
    }
    if (!applications.value.length) errorText.value = '当前账号没有可查看的应用'
  } catch (error) {
    if (sequence !== applicationSequence) return
    applications.value = []
    applicationId.value = ''
    errorText.value = error instanceof Error ? error.message : '读取应用授权范围失败'
  } finally {
    if (sequence === applicationSequence) loadingApplications.value = false
  }
}

async function loadRoles(): Promise<void> {
  const application = selectedApplication.value
  if (!props.active || !application) { roles.value = []; return }
  const sequence = ++roleSequence
  loadingRoles.value = true
  try {
    const rows = await api<RoleRecord[]>(`/tenant-admin/applications/${application.id}/roles`)
    if (sequence === roleSequence && props.active && application.id === applicationId.value) roles.value = rows
  } catch (error) {
    if (sequence === roleSequence) {
      roles.value = []
      message.error(error instanceof Error ? error.message : '读取应用角色失败')
    }
  } finally {
    if (sequence === roleSequence) loadingRoles.value = false
  }
}

async function loadMembers(page = memberPage.value): Promise<void> {
  const application = selectedApplication.value
  if (!props.active || !application) { members.value = []; memberTotal.value = 0; return }
  const sequence = ++memberSequence
  loadingMembers.value = true
  try {
    const params = new URLSearchParams({ limit: '20', offset: String((page - 1) * 20) })
    if (memberQuery.value.trim()) params.set('q', memberQuery.value.trim())
    const result = await api<{ items: MemberRecord[]; total: number }>(
      `/tenant-admin/applications/${application.id}/members?${params.toString()}`,
    )
    if (sequence !== memberSequence || !props.active || application.id !== applicationId.value) return
    members.value = result.items
    memberTotal.value = result.total
    memberPage.value = page
  } catch (error) {
    if (sequence === memberSequence) message.error(error instanceof Error ? error.message : '读取应用成员失败')
  } finally {
    if (sequence === memberSequence) loadingMembers.value = false
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([loadRoles(), loadMembers(1)])
}

function openCreateRole(): void {
  editingRole.value = null
  roleForm.key = ''
  roleForm.name = ''
  roleForm.description = ''
  roleDialogOpen.value = true
}

function openEditRole(role: RoleRecord): void {
  editingRole.value = role
  roleForm.key = role.key
  roleForm.name = role.name
  roleForm.description = role.description || ''
  roleDialogOpen.value = true
}

async function saveRole(): Promise<void> {
  const application = selectedApplication.value
  if (!application || !canManage.value) return
  const editing = editingRole.value
  if (!roleForm.name.trim() || roleForm.name.trim().length > 120 || roleForm.description.trim().length > 500) {
    message.error('请检查角色名称和说明长度')
    return
  }
  if (!editing && !/^[a-z0-9][a-z0-9._-]{1,99}$/.test(roleForm.key.trim())) {
    message.error('角色标识需为 2 至 100 位小写字母、数字、点、下划线或连字符')
    return
  }
  roleSaving.value = true
  try {
    await api(editing
      ? `/tenant-admin/applications/${application.id}/roles/${editing.id}`
      : `/tenant-admin/applications/${application.id}/roles`, {
      method: editing ? 'PATCH' : 'POST',
      body: JSON.stringify(editing
        ? { name: roleForm.name.trim(), description: roleForm.description.trim() || null }
        : { key: roleForm.key.trim(), name: roleForm.name.trim(), description: roleForm.description.trim() || null }),
    })
    message.success(editing ? '角色资料已更新' : '应用角色已创建')
    roleDialogOpen.value = false
    await refreshAll()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存应用角色失败')
  } finally { roleSaving.value = false }
}

function changeRoleStatus(role: RoleRecord): void {
  if (!canManage.value || !selectedApplication.value) return
  const status = role.status === 'active' ? 'disabled' : 'active'
  Modal.confirm({
    title: status === 'active' ? '启用应用角色？' : '停用应用角色？',
    content: status === 'disabled' ? `停用“${role.name}”后，直接绑定和用户组继承的成员都不再通过此角色获得权限。` : undefined,
    okText: status === 'active' ? '启用角色' : '停用角色',
    cancelText: '取消',
    okButtonProps: status === 'disabled' ? { danger: true } : undefined,
    onOk: async () => {
      try {
        await api(`/tenant-admin/applications/${selectedApplication.value!.id}/roles/${role.id}/status`, {
          method: 'PATCH', body: JSON.stringify({ expected_status: role.status, status }),
        })
        message.success(status === 'active' ? '应用角色已启用' : '应用角色已停用')
        await refreshAll()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '更新应用角色状态失败')
        throw error
      }
    },
  })
}

async function openPermissionEditor(role: RoleRecord): Promise<void> {
  const application = selectedApplication.value
  if (!application) return
  permissionRole.value = role
  permissionImpact.value = null
  permissionPreviewKey.value = ''
  permissionLoading.value = true
  try {
    const catalogQuery = new URLSearchParams({ role_id: role.id, include_management: 'true' })
    const [catalog, grants] = await Promise.all([
      api<PermissionRecord[]>(`/tenant-admin/applications/${application.id}/permissions?${catalogQuery}`),
      api<Array<{ permission_id: string; resource_id: string | null }>>(
        `/tenant-admin/applications/${application.id}/roles/${role.id}/permissions`,
      ),
    ])
    const currentIds = grants.filter(grant => grant.resource_id === null).map(grant => grant.permission_id)
    const currentSet = new Set(currentIds)
    permissionOptions.value = catalog
      .filter(permission => permission.status === 'active' || currentSet.has(permission.id))
      .map(permission => {
        const description = (permission.description || '').trim()
        return {
          label: description || permission.code,
          value: permission.id,
          code: permission.code,
          description,
          scope: resolvePermissionScope(permission.code).key,
          disabled: permission.status !== 'active' && !currentSet.has(permission.id),
        }
      })
    permissionIds.value = currentIds
    permissionDialogOpen.value = true
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取应用权限编码失败')
  } finally { permissionLoading.value = false }
}

async function previewPermissionChanges(): Promise<void> {
  const application = selectedApplication.value
  const role = permissionRole.value
  if (!application || !role) return
  impactLoading.value = true
  try {
    permissionImpact.value = await api<PermissionImpact>(
      `/tenant-admin/applications/${application.id}/roles/${role.id}/permissions/preview`, {
        method: 'POST', body: JSON.stringify({ permission_ids: permissionIds.value }),
      },
    )
    permissionPreviewKey.value = permissionSelectionKey.value
  } catch (error) {
    permissionImpact.value = null
    permissionPreviewKey.value = ''
    message.error(error instanceof Error ? error.message : '预览授权变更失败')
  } finally { impactLoading.value = false }
}

async function savePermissionChanges(): Promise<void> {
  const application = selectedApplication.value
  const role = permissionRole.value
  const impact = permissionImpact.value
  if (!application || !role || !impact || !previewIsCurrent.value || !canManage.value) return
  if (!impact.grant_permission_codes.length && !impact.revoke_permission_codes.length) {
    message.info('权限集合没有变化')
    return
  }
  permissionSaving.value = true
  try {
    await api(`/tenant-admin/applications/${application.id}/roles/${role.id}/permissions`, {
      method: 'PUT',
      body: JSON.stringify({
        permission_ids: permissionIds.value,
        expected_current_permission_ids: impact.current_permission_ids,
      }),
    })
    message.success('应用角色权限已更新')
    permissionDialogOpen.value = false
    permissionImpact.value = null
    await loadRoles()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '授权保存失败，请重新预览')
  } finally { permissionSaving.value = false }
}

async function bindMember(): Promise<void> {
  const application = selectedApplication.value
  if (!application || !canAssign.value || !memberEmail.value.trim() || !memberRoleId.value) {
    message.error('请填写租户成员邮箱并选择启用的应用角色')
    return
  }
  memberSaving.value = true
  try {
    await api(`/tenant-admin/applications/${application.id}/role-bindings`, {
      method: 'PUT',
      body: JSON.stringify({ email: memberEmail.value.trim(), role_id: memberRoleId.value }),
    })
    memberEmail.value = ''
    message.success('已分配应用角色，并同时成为该应用的平台成员')
    await Promise.all([loadMembers(1), loadRoles()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '绑定应用角色失败；非租户成员需先由租户管理员邀请')
  } finally { memberSaving.value = false }
}

function removeMemberRole(member: MemberRecord, role: RoleAssignment): void {
  const application = selectedApplication.value
  if (!application || !canManage.value || !role.sources.includes('direct')) return
  Modal.confirm({
    title: '移除成员的直接应用角色？',
    content: `将移除 ${member.display_name} 的“${role.name}”直接绑定。若该角色仍由用户组继承，成员仍保留此权限。`,
    okText: '移除绑定', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`/tenant-admin/applications/${application.id}/members/${member.user_id}/roles/${role.id}`, { method: 'DELETE' })
        message.success('直接角色绑定已移除')
        await Promise.all([loadMembers(), loadRoles()])
      } catch (error) {
        message.error(error instanceof Error ? error.message : '移除应用角色失败')
        throw error
      }
    },
  })
}

function onMemberPageChange(pagination: { current?: number }): void {
  void loadMembers(pagination.current || 1)
}

watch(() => [props.active, readableTenants.value.map(tenant => tenant.id).join('|')], () => {
  if (props.active) void loadApplications()
}, { immediate: true })
watch(applicationId, () => {
  if (!applicationId.value) { roles.value = []; members.value = []; memberTotal.value = 0; return }
  void refreshAll()
})
watch(memberQuery, () => { memberPage.value = 1 })
</script>

<template>
  <section class="application-role-page">
    <AdminPageHeader
      eyebrow="应用角色与成员"
      title="应用角色与成员"
      subtitle="本页给当前应用的角色配置你看得见的租户/应用管理权限，以及本应用业务码。五级平台模板仍在「高级管理 → 角色」。"
    />

    <a-card class="data-card" :bordered="false">
      <AdminTableToolbar :hint="canManage ? '写入会记录审计。可挂你看得见的租户/应用管理码与本应用业务码；分配应用角色时会同时成为该应用的平台成员。' : '当前只有读取权限；联系应用管理员申请角色管理权限。'">
        <a-select v-model:value="applicationId" placeholder="选择已授权应用"
          :loading="loadingApplications" :options="applications.map(item => ({ value: item.id, label: `${item.name} · ${item.client_id}` }))" />
        <template #actions>
          <a-button :loading="loadingRoles || loadingMembers" :disabled="!applicationId" @click="refreshAll">刷新</a-button>
          <a-button v-if="canManage" type="primary" :disabled="selectedApplication?.status !== 'active'" @click="openCreateRole">新建应用角色</a-button>
        </template>
      </AdminTableToolbar>
      <a-alert v-if="errorText" class="page-alert" type="info" show-icon :message="errorText" />
      <a-alert v-if="selectedApplication?.status === 'disabled'" class="page-alert" type="warning" show-icon
        message="当前应用已停用" description="你可以查看和整理角色；停用应用期间不能新增成员角色绑定。" />

      <a-tabs>
        <a-tab-pane key="roles" tab="角色与权限">
          <a-table class="scroll-actions-on-mobile" :data-source="roles" :columns="roleColumns" :loading="loadingRoles" row-key="id" :scroll="{ x: 900, y: 'calc(100vh - 470px)' }"
            :pagination="{ pageSize: 10, showSizeChanger: true }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'permissions'">
                <a-tag v-for="code in record.permission_codes" :key="code" class="font-mono">{{ code }}</a-tag>
                <span v-if="!record.permission_codes.length" class="muted">未配置</span>
              </template>
              <template v-else-if="column.key === 'status'">
                <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-button type="link" size="small" @click="openPermissionEditor(record)">{{ canManage ? '配置权限' : '查看权限' }}</a-button>
                <a-button v-if="canManage" type="link" size="small" @click="openEditRole(record)">编辑</a-button>
                <a-button v-if="canManage" type="link" size="small" :danger="record.status === 'active'" @click="changeRoleStatus(record)">{{ record.status === 'active' ? '停用' : '启用' }}</a-button>
              </template>
            </template>
            <template #emptyText><AdminEmpty emoji="🎭" description="当前应用还没有专属角色" /></template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane key="members" tab="应用成员">
          <div v-if="canManage" class="sub-toolbar">
            <a-input v-model:value="memberEmail" class="member-email" type="email" autocomplete="off" placeholder="输入已加入本租户的成员邮箱" />
            <a-select v-model:value="memberRoleId" class="member-role" placeholder="选择启用的应用角色" :options="roleSelectOptions" />
            <a-button type="primary" :loading="memberSaving" :disabled="!canAssign" @click="bindMember">绑定角色</a-button>
            <span class="member-hint">会同时成为该应用的平台成员；已有则跳过。同一用户可绑定多个应用角色。</span>
          </div>
          <AdminTableToolbar hint="用户组继承的角色会标记为「用户组」；直接移除后若仍有继承，授权仍然有效。">
            <AdminSearchField v-model="memberQuery" placeholder="搜索已授权成员，回车查询" @search="() => loadMembers(1)" />
          </AdminTableToolbar>
          <a-table :data-source="members" :columns="memberColumns" :loading="loadingMembers" row-key="user_id"
            :scroll="{ x: 840, y: 'calc(100vh - 470px)' }" :pagination="{ current: memberPage, pageSize: 20, total: memberTotal, showSizeChanger: false }"
            @change="onMemberPageChange">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'roles'">
                <div v-for="role in record.roles" :key="role.id" class="member-role-row">
                  <span><a-tag>{{ role.name }}</a-tag>
                    <a-tag v-if="role.sources.includes('group')">用户组</a-tag></span>
                  <a-button v-if="canManage && role.sources.includes('direct')" type="link" size="small" danger @click="removeMemberRole(record, role)">移除直接绑定</a-button>
                </div>
              </template>
            </template>
            <template #emptyText><AdminEmpty emoji="👥" description="当前应用没有已授权成员" /></template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <a-modal v-model:open="roleDialogOpen" :title="editingRole ? '编辑应用角色' : '新建应用角色'"
      ok-text="保存角色" cancel-text="取消" :confirm-loading="roleSaving" @ok="saveRole">
      <a-form layout="vertical">
        <a-form-item v-if="!editingRole" label="角色标识" help="创建后不可更改；只在当前应用内唯一。">
          <a-input v-model:value="roleForm.key" :maxlength="100" placeholder="例如 resume.editor" />
        </a-form-item>
        <a-form-item label="角色名称"><a-input v-model:value="roleForm.name" :maxlength="120" placeholder="例如简历编辑者" /></a-form-item>
        <a-form-item label="说明"><a-input v-model:value="roleForm.description" :maxlength="500" placeholder="说明这个应用角色的用途" /></a-form-item>
        <a-alert type="info" show-icon message="角色限定当前应用" description="此页不会创建五级平台模板。成员必须先由租户管理员加入租户。" />
      </a-form>
    </a-modal>

    <a-modal v-model:open="permissionDialogOpen" :title="`${canManage ? '配置' : '查看'}「${permissionRole?.name || '应用角色'}」权限`" width="760px"
      :footer="null" :confirm-loading="permissionSaving">
      <a-spin :spinning="permissionLoading">
        <a-alert class="page-alert" type="info" show-icon message="可勾选你看得见的租户管理码、应用管理码；本应用业务码也可挂。看不见的码不会出现。" />
        <a-checkbox-group v-model:value="permissionIds" :disabled="!canManage" class="flex max-h-[48vh] w-full flex-col gap-4 overflow-auto py-3">
          <div v-for="group in permissionGroups" :key="group.key" class="flex flex-col gap-2">
            <p class="m-0 text-sm font-medium text-[var(--color-text-primary)]">{{ group.label }}</p>
            <p class="m-0 text-xs text-[var(--color-text-secondary)]">{{ group.hint }}</p>
            <a-checkbox v-for="option in group.options" :key="option.value" :value="option.value" :disabled="option.disabled">
              <span class="flex flex-col">
                <span>{{ option.label }}</span>
                <span class="font-mono text-xs text-[var(--color-text-muted)]">{{ option.code }}</span>
              </span>
            </a-checkbox>
          </div>
          <AdminEmpty v-if="!permissionGroups.length" emoji="🔐" description="当前没有可配的权限编码。租户管理员可看到租户码，应用管理员可看到应用码。" />
        </a-checkbox-group>
        <div v-if="canManage" class="modal-actions">
          <a-button :loading="impactLoading" @click="previewPermissionChanges">预览影响</a-button>
          <a-button type="primary" :loading="permissionSaving" :disabled="!previewIsCurrent || impactLoading" @click="savePermissionChanges">确认保存</a-button>
        </div>
        <a-alert v-if="permissionImpact && previewIsCurrent" class="page-alert" type="warning" show-icon
          :message="`潜在受影响 ${permissionImpact.potentially_affected_members} 位成员（含直接绑定和用户组继承）`"
          :description="`${permissionImpact.grant_permission_codes.join('、') || '无新增'}；撤销：${permissionImpact.revoke_permission_codes.join('、') || '无'}。${permissionImpact.permission_impacts.map(item => `${item.permission_code}：${item.potentially_affected_members} 位（其它通用角色覆盖 ${item.covered_by_other_general_roles} 位）`).join('；')}。${permissionImpact.analysis_note}`" />
      </a-spin>
    </a-modal>
  </section>
</template>

<style scoped>
.application-role-page { display: grid; gap: 20px; }
.data-card { border-radius: 16px; }
.sub-toolbar, .modal-actions { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.application-filter { width: min(360px, 100%); flex: 0 0 auto; }
.member-search { width: min(340px, 100%); }
.member-email { width: min(320px, 100%); }
.member-role { width: min(260px, 100%); }
.table-hint, .muted { flex: 1; color: var(--color-text-secondary); font-size: 12px; }
.page-alert { margin-bottom: 14px; }
.permission-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 18px; max-height: 48vh; overflow: auto; padding: 12px 2px; }
.member-role-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 4px; }
.modal-actions { justify-content: flex-end; margin: 14px 0; }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
  .table-toolbar, .sub-toolbar { align-items: stretch; flex-direction: column; }
  .application-filter, .member-search, .member-email, .member-role { width: 100%; }
  .permission-list { grid-template-columns: 1fr; }
}
.member-hint { color: var(--color-text-secondary); font-size: 12px; }
</style>

