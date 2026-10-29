<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHas } from '@/api/capabilities'
import { validateReservedEmailDomain } from '@/utils/emailValidation'
import { DownOutlined } from '@/plugins/icons'
import AdminListPage from '@/components/AdminListPage.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import UserDetailDrawer from '@/components/UserDetailDrawer.vue'

interface TenantOption { id: string; name: string; status: string }
interface UserRecord {
  id: string
  email: string
  display_name: string
  status: 'active' | 'disabled' | 'locked'
  tenant_count: number
  created_at: string
}
interface RoleOption { id: string; tenant_id: string; key: string; name: string; status: string }
/** 角色穿梭框数据项：key=角色 ID，roleKey=角色标识（英文）。 */
interface RoleTransferItem { key: string; title: string; roleKey: string; active: boolean }
interface SelectOption { label: string; value: string; disabled?: boolean }
interface MembershipRecord {
  tenant_id: string
  tenant_name: string
  membership_status: 'active' | 'disabled' | 'departed'
  tenant_status: string
}
interface UserSession {
  id: string
  type: 'management' | 'oidc'
  application_name: string
  client_id: string | null
  created_at: string
  expires_at: string
}

const props = defineProps<{ active: boolean; tenants: TenantOption[]; currentUserId?: string }>()
const emit = defineEmits<{ changed: [] }>()

const users = ref<UserRecord[]>([])
const canManageUsers = computed(() => cachedHas('platform.account.manage'))
const loading = ref(false)
const searchText = ref('')
const createOpen = ref(false)
const createSaving = ref(false)
const createFormRef = ref<{ validate: () => Promise<unknown> }>()
const createForm = reactive({ tenant_id: '', email: '', display_name: '', initial_password: '' })
const roleDialogOpen = ref(false)
const roleSaving = ref(false)
const roleUserId = ref('')
const roleTenantId = ref('')
const roleIds = ref<string[]>([])
const roles = ref<RoleOption[]>([])
const roleTenantOptions = ref<SelectOption[]>([])
const organizationDialogOpen = ref(false)
const organizationSaving = ref(false)
const organizationUserId = ref('')
const organizationTenantId = ref('')
const organizationIds = ref<string[]>([])
const primaryOrganizationId = ref('')
const organizationOptions = ref<SelectOption[]>([])
const membershipTenantOptions = ref<SelectOption[]>([])
const membershipDialogOpen = ref(false)
const membershipLoading = ref(false)
const membershipUser = ref<UserRecord | null>(null)
const memberships = ref<MembershipRecord[]>([])
const membershipSaving = ref('')
const sessionsOpen = ref(false)
const sessionsLoading = ref(false)
const sessionUser = ref<UserRecord | null>(null)
const sessions = ref<UserSession[]>([])
const revokingSession = ref('')
// G16 用户详情抽屉：操作列「详情」高频入口。
const detailOpen = ref(false)
const detailUserId = ref('')

function openDetail(user: UserRecord): void {
  detailUserId.value = user.id
  detailOpen.value = true
}
// G02 管理员重置密码（并行会话曾误移，此处恢复）：SMTP 故障时忘记密码用户的兜底救济。
const resetPwOpen = ref(false)
const resetPwSaving = ref(false)
const resetPwUser = ref<UserRecord | null>(null)
const resetPwFormRef = ref<{ validate: () => Promise<unknown> }>()
const resetPwForm = reactive({ new_password: '' })
const resetPwRules = {
  new_password: [{ required: true, min: 12, max: 128, message: '新密码长度须为 12–128 个字符', trigger: 'blur' }],
}

function openResetPassword(user: UserRecord): void {
  if (user.id === props.currentUserId) {
    message.warning('不能重置自己的密码；请使用页面右上角「修改密码」')
    return
  }
  if (user.status !== 'active') {
    message.warning('仅允许为启用状态的用户重置密码；请先恢复启用')
    return
  }
  resetPwUser.value = user
  resetPwForm.new_password = ''
  resetPwOpen.value = true
}

async function submitResetPassword(): Promise<void> {
  if (!resetPwUser.value) return
  try { await resetPwFormRef.value?.validate() } catch { return }
  resetPwSaving.value = true
  try {
    await api(`/admin/users/${resetPwUser.value.id}/password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: resetPwForm.new_password }),
    })
    message.success('密码已重置，该用户所有登录会话已撤销')
    resetPwOpen.value = false
    resetPwForm.new_password = ''
  } catch (error) {
    message.error(error instanceof Error ? error.message : '重置密码失败')
  } finally { resetPwSaving.value = false }
}
let requestSequence = 0
let organizationRequestSequence = 0

const activeTenants = computed(() => props.tenants.filter(tenant => tenant.status === 'active'))
const tenantOptions = computed(() => activeTenants.value.map(tenant => ({ value: tenant.id, label: tenant.name })))
// 服务端口径的当前直接绑定集合：切换租户/打开弹窗时刷新，用于锁定已绑定的停用角色。
const boundRoleIds = ref<string[]>([])
const boundRoleKeySet = computed(() => new Set(boundRoleIds.value))
// 穿梭框数据源：当前租户全部角色（含停用）；antd Transfer 直接读取 item.disabled，
// 停用且未绑定的角色禁止新勾入，已绑定的停用角色保留可移除。
const roleTransferItems = computed<Array<RoleTransferItem & { disabled: boolean }>>(() => roles.value
  .filter(role => role.tenant_id === roleTenantId.value)
  .map(role => {
    const active = role.status === 'active'
    return {
      key: role.id,
      title: role.name,
      roleKey: role.key,
      active,
      disabled: !active && !boundRoleKeySet.value.has(role.id),
    }
  }))

function filterRoleTransfer(inputValue: string, item: RoleTransferItem): boolean {
  const keyword = inputValue.trim().toLowerCase()
  return !keyword
    || item.title.toLowerCase().includes(keyword)
    || item.roleKey.toLowerCase().includes(keyword)
}

// 穿梭框列表项展示英文角色标识；角色名称在 title 中用于搜索与悬浮提示。
function renderRoleTransfer(item: RoleTransferItem): string {
  return `${item.roleKey}${item.active ? '' : ' · 已停用'}`
}

const columns = [
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 200, ellipsis: true },
  { title: '姓名', dataIndex: 'display_name', key: 'display_name', width: 130, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 88 },
  { title: '租户关系数', dataIndex: 'tenant_count', key: 'tenant_count', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 162, fixed: 'right' as const },
]

const sessionColumns = [
  { title: '会话类型', dataIndex: 'type', key: 'type', width: 100 },
  { title: '应用', dataIndex: 'application_name', key: 'application_name', width: 170 },
  { title: '客户端 ID', dataIndex: 'client_id', key: 'client_id', width: 180, ellipsis: true },
  { title: '开始时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '刷新凭证到期', dataIndex: 'expires_at', key: 'expires_at', width: 180 },
  { title: '操作', key: 'actions', width: 100 },
]

const createRules = {
  tenant_id: [{ required: true, message: '请选择所属租户', trigger: 'change' }],
  email: [
    { required: true, type: 'email', max: 254, message: '请输入有效邮箱（不超过 254 个字符）', trigger: 'blur' },
    { validator: validateReservedEmailDomain, trigger: 'blur' },
  ],
  display_name: [
    { required: true, whitespace: true, max: 120, message: '请输入不超过 120 个字符的姓名', trigger: 'blur' },
  ],
  initial_password: [
    { required: true, min: 12, max: 128, message: '初始密码长度须为 12–128 个字符', trigger: 'blur' },
  ],
}

async function loadUsers(): Promise<void> {
  if (!props.active) return
  const sequence = ++requestSequence
  loading.value = true
  try {
    const query = searchText.value.trim()
    const suffix = query ? `?q=${encodeURIComponent(query)}` : ''
    const result = await api<UserRecord[]>(`/admin/users${suffix}`)
    if (sequence === requestSequence && props.active) users.value = result
  } catch (error) {
    if (sequence !== requestSequence) return
    users.value = []
    message.error(error instanceof Error ? error.message : '读取用户失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function openCreate(): void {
  Object.assign(createForm, {
    tenant_id: activeTenants.value[0]?.id || '', email: '', display_name: '', initial_password: '',
  })
  createOpen.value = true
}

async function createUser(): Promise<void> {
  try { await createFormRef.value?.validate() } catch { return }
  if (!activeTenants.value.some(tenant => tenant.id === createForm.tenant_id)) {
    message.error('请选择活动租户')
    return
  }
  createSaving.value = true
  try {
    await api('/admin/users', {
      method: 'POST',
      body: JSON.stringify({
        tenant_id: createForm.tenant_id,
        email: createForm.email.trim().toLowerCase(),
        display_name: createForm.display_name.trim(),
        initial_password: createForm.initial_password,
      }),
    })
    message.success('用户已创建')
    createOpen.value = false
    createForm.initial_password = ''
    await loadUsers()
    emit('changed')
  } catch (error) { message.error(error instanceof Error ? error.message : '创建用户失败') }
  finally { createSaving.value = false }
}

// 操作列「更多」菜单（UI 检查 P348 收敛）：低频动作统一入口。
type UserRowMenuKey = 'organizations' | 'memberships' | 'lock' | 'unlock' | 'disable' | 'enable' | 'reset-password'

function onRowMenuClick(info: { key: string | number }, user: UserRecord): void {
  const key = String(info.key) as UserRowMenuKey
  if (key === 'organizations') openOrganizationAssignment(user)
  else if (key === 'memberships') openMemberships(user)
  else if (key === 'lock') changeStatus(user, 'locked')
  else if (key === 'unlock' || key === 'enable') changeStatus(user, 'active')
  else if (key === 'disable') changeStatus(user, 'disabled')
  else if (key === 'reset-password') openResetPassword(user)
}

function changeStatus(user: UserRecord, status: UserRecord['status']): void {
  const statusText = status === 'active' ? '启用' : status === 'disabled' ? '停用' : '管理员锁定'
  const update = async (): Promise<void> => {
    try {
      await api(`/admin/users/${user.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ expected_status: user.status, status }),
      })
      message.success(`用户已${statusText}`)
      await loadUsers()
      emit('changed')
    } catch (error) { message.error(error instanceof Error ? error.message : '更新用户状态失败') }
  }
  if (status !== 'active') Modal.confirm({
    title: `${statusText}用户？`,
    content: `${statusText}“${user.display_name || user.email}”会递增身份版本、撤销 IAM/OIDC 刷新凭证并使未兑换的授权失效。恢复启用后仍需重新登录。`,
    okText: statusText, cancelText: '取消', okButtonProps: { danger: true }, onOk: update,
  })
  else void update()
}

async function openMemberships(user: UserRecord): Promise<void> {
  membershipUser.value = user
  membershipDialogOpen.value = true
  membershipLoading.value = true
  try {
    memberships.value = await api<MembershipRecord[]>(`/admin/users/${user.id}/memberships`)
  } catch (error) {
    memberships.value = []
    message.error(error instanceof Error ? error.message : '读取租户成员关系失败')
  } finally { membershipLoading.value = false }
}

async function openSessions(user: UserRecord): Promise<void> {
  sessionUser.value = user
  sessions.value = []
  sessionsOpen.value = true
  sessionsLoading.value = true
  try {
    const result = await api<{ user_id: string; items: UserSession[] }>(`/admin/users/${user.id}/sessions`)
    sessions.value = result.items
  } catch (error) {
    sessions.value = []
    message.error(error instanceof Error ? error.message : '读取用户会话失败')
  } finally { sessionsLoading.value = false }
}

function revokeSession(session: UserSession): void {
  if (!sessionUser.value) return
  const key = `${session.type}:${session.id}`
  Modal.confirm({
    title: '远程退出此会话？',
    content: `将撤销“${session.application_name}”会话的续期凭证，并立即阻止 IAM 在线接口继续接受关联的访问令牌。只离线验证 JWT 的业务系统仍可能接受当前访问令牌至其过期。`,
    okText: '远程退出', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      revokingSession.value = key
      try {
        await api(`/admin/users/${sessionUser.value?.id}/sessions/${session.type}/${session.id}/revoke`, { method: 'POST' })
        message.success('会话已远程退出')
        sessions.value = sessions.value.filter(item => `${item.type}:${item.id}` !== key)
      } catch (error) { message.error(error instanceof Error ? error.message : '远程退出失败') }
      finally { revokingSession.value = '' }
    },
  })
}

function sessionRowKey(session: UserSession): string {
  return `${session.type}:${session.id}`
}

function changeMembershipStatus(membership: MembershipRecord, status: MembershipRecord['membership_status']): void {
  const user = membershipUser.value
  if (!user) return
  const label = status === 'active' ? '重新启用' : status === 'disabled' ? '停用成员' : '标记离职'
  const updateMembership = async (): Promise<void> => {
    membershipSaving.value = membership.tenant_id
    try {
      await api(`/admin/users/${user.id}/memberships/${membership.tenant_id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ expected_status: membership.membership_status, status }),
      })
      message.success(`已${label}：${membership.tenant_name}`)
      memberships.value = await api<MembershipRecord[]>(`/admin/users/${user.id}/memberships`)
      await loadUsers()
      emit('changed')
    } catch (error) { message.error(error instanceof Error ? error.message : '更新成员状态失败') }
    finally { membershipSaving.value = '' }
  }
  if (status === 'active') {
    Modal.confirm({
      title: `重新启用 ${membership.tenant_name} 成员？`,
      content: '原有角色会恢复生效；旧 OAuth 会话已撤销，用户必须重新登录。',
      okText: '重新启用', cancelText: '取消', onOk: updateMembership,
    })
  } else {
    Modal.confirm({
      title: `${label}？`,
      content: status === 'departed'
        ? '该租户的角色、用户组和组织归属将被清除；其他租户账号不受影响。后续需重新发送邀请才能加入。'
        : '该用户将失去这个租户的权限，现有角色和组织关系暂时保留以便后续恢复；该租户应用会话会被撤销。',
      okText: label, cancelText: '取消', okButtonProps: { danger: true }, onOk: updateMembership,
    })
  }
}

async function openRoleBinding(user: UserRecord): Promise<void> {
  roleUserId.value = user.id
  roleTenantId.value = ''
  roleIds.value = []
  boundRoleIds.value = []
  try {
    const [userMemberships, roleRows] = await Promise.all([
      api<Array<{ tenant_id: string; tenant_name: string; membership_status: string; tenant_status: string }>>(
        `/admin/users/${user.id}/memberships`,
      ),
      api<RoleOption[]>('/admin/roles'),
    ])
    const tenantIds = new Set(activeTenants.value.map(tenant => tenant.id))
    roleTenantOptions.value = userMemberships
      .filter(membership => membership.membership_status === 'active'
        && membership.tenant_status === 'active' && tenantIds.has(String(membership.tenant_id)))
      .map(membership => ({ value: String(membership.tenant_id), label: membership.tenant_name }))
    const membershipIds = new Set(roleTenantOptions.value.map(option => option.value))
    roles.value = roleRows.filter(role => membershipIds.has(String(role.tenant_id)))
    if (!roleTenantOptions.value.length) {
      message.warning('该用户没有活跃租户成员关系，无法配置租户角色')
      return
    }
    roleTenantId.value = roleTenantOptions.value[0].value
    roleDialogOpen.value = true
    await loadMemberRoles()
  } catch (error) { message.error(error instanceof Error ? error.message : '读取角色目录失败') }
}

async function loadMemberRoles(): Promise<void> {
  roleIds.value = []
  boundRoleIds.value = []
  if (!roleUserId.value || !roleTenantId.value) return
  try {
    const result = await api<{ role_ids: string[] }>(
      `/admin/users/${roleUserId.value}/role-bindings?tenant_id=${encodeURIComponent(roleTenantId.value)}`,
    )
    boundRoleIds.value = result.role_ids.map(String)
    roleIds.value = [...boundRoleIds.value]
  } catch (error) {
    roleIds.value = []
    message.error(error instanceof Error ? error.message : '获取已绑定角色失败')
  }
}

async function saveRoleBinding(): Promise<void> {
  if (!roleUserId.value || !roleTenantId.value) {
    message.warning('请选择目标租户')
    return
  }
  roleSaving.value = true
  try {
    await api(`/admin/users/${roleUserId.value}/role-bindings`, {
      method: 'PUT',
      body: JSON.stringify({ tenant_id: roleTenantId.value, role_ids: roleIds.value }),
    })
    message.success(roleIds.value.length ? `已保存 ${roleIds.value.length} 个角色` : '已清空该租户下的直接角色绑定')
    roleDialogOpen.value = false
    await loadUsers()
    emit('changed')
  } catch (error) { message.error(error instanceof Error ? error.message : '保存角色失败') }
  finally { roleSaving.value = false }
}

async function loadMemberOrganizations(): Promise<void> {
  if (!organizationTenantId.value || !organizationUserId.value) {
    organizationOptions.value = []
    return
  }
  const sequence = ++organizationRequestSequence
  try {
    const [organizations, assignment] = await Promise.all([
      api<Array<{ id: string; key: string; name: string; status: string }>>(
        `/admin/organizations?tenant_id=${encodeURIComponent(organizationTenantId.value)}`,
      ),
      api<{ organization_ids: string[]; primary_organization_id: string | null }>(
        `/admin/users/${organizationUserId.value}/organizations?tenant_id=${encodeURIComponent(organizationTenantId.value)}`,
      ),
    ])
    if (sequence !== organizationRequestSequence) return
    organizationIds.value = assignment.organization_ids.map(String)
    primaryOrganizationId.value = String(assignment.primary_organization_id || '')
    const assigned = new Set(organizationIds.value)
    // 已停用的现有关联保留为可见项，避免管理员保存时无意删除；新关联仅允许选择活动组织。
    organizationOptions.value = organizations
      .filter(organization => organization.status === 'active' || assigned.has(String(organization.id)))
      .map(organization => ({
        value: String(organization.id),
        label: `${organization.name} (${organization.key})${organization.status === 'active' ? '' : ' · 已停用'}`,
        disabled: organization.status !== 'active',
      }))
  } catch (error) {
    if (sequence !== organizationRequestSequence) return
    organizationOptions.value = []
    message.error(error instanceof Error ? error.message : '读取组织归属失败')
  }
}

async function openOrganizationAssignment(user: UserRecord): Promise<void> {
  organizationUserId.value = user.id
  try {
    const memberships = await api<Array<{
      tenant_id: string; tenant_name: string; membership_status: string; tenant_status: string
    }>>(`/admin/users/${user.id}/memberships`)
    membershipTenantOptions.value = memberships
      .filter(membership => membership.membership_status === 'active' && membership.tenant_status === 'active')
      .map(membership => ({ value: String(membership.tenant_id), label: membership.tenant_name }))
  } catch (error) { message.error(error instanceof Error ? error.message : '读取用户租户失败'); return }
  if (!membershipTenantOptions.value.length) {
    message.warning('该用户没有活动租户成员关系')
    return
  }
  organizationTenantId.value = membershipTenantOptions.value[0]?.value || ''
  organizationIds.value = []
  primaryOrganizationId.value = ''
  organizationDialogOpen.value = true
  await loadMemberOrganizations()
}

function syncOrganizationSelection(ids: string[]): void {
  organizationIds.value = ids
  if (!ids.includes(primaryOrganizationId.value)) primaryOrganizationId.value = ''
}

async function saveOrganizationAssignment(): Promise<void> {
  if (!organizationUserId.value || !organizationTenantId.value) {
    message.warning('请选择租户')
    return
  }
  organizationSaving.value = true
  try {
    await api(`/admin/users/${organizationUserId.value}/organizations`, {
      method: 'PUT',
      body: JSON.stringify({
        tenant_id: organizationTenantId.value,
        organization_ids: organizationIds.value,
        primary_organization_id: primaryOrganizationId.value || null,
      }),
    })
    message.success('组织归属已保存')
    organizationDialogOpen.value = false
  } catch (error) { message.error(error instanceof Error ? error.message : '保存组织归属失败') }
  finally { organizationSaving.value = false }
}

watch(() => props.active, active => { if (active) void loadUsers() }, { immediate: true })
</script>

<template>
  <section class="users-page">
    <AdminListPage
      eyebrow="IDENTITY DIRECTORY"
      title="用户管理"
      subtitle="管理平台账号：创建用户、维护状态与锁定，并配置多租户角色。"
      hint="最多读取最近 500 个身份；用户可加入多个租户。"
      :columns="columns"
      :data-source="users"
      :loading="loading"
      row-key="id"
      :scroll="{ x: 830, y: 'calc(100vh - 430px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
      empty-emoji="🧑‍💼"
      empty-text="当前条件下没有用户，可创建用户或调整搜索条件"
    >
      <template #header-extra>
        <a-button v-if="canManageUsers" type="primary" :disabled="!tenantOptions.length" @click="openCreate">＋ 新建用户</a-button>
      </template>
      <AdminSearchField v-model="searchText" placeholder="搜索邮箱或姓名，回车查询" @search="loadUsers" />
      <template #actions>
        <a-button :loading="loading" @click="loadUsers">刷新</a-button>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : record.status === 'locked' ? 'orange' : 'default'">
            {{ record.status === 'active' ? '启用' : record.status === 'locked' ? '管理员锁定' : '停用' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'created_at'">{{ record.created_at ? new Date(record.created_at).toLocaleString() : '—' }}</template>
        <template v-else-if="column.key === 'actions'">
          <!-- UI 检查（P348）修复：操作列从 6 动作收敛为「高频 2 + 更多下拉」，符合设计系统 ≤3 规范。 -->
          <a-space v-if="canManageUsers" :size="0">
            <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
            <a-button type="link" size="small" @click="openRoleBinding(record)">配置角色</a-button>
            <a-button type="link" size="small" @click="openSessions(record)">会话</a-button>
            <a-dropdown>
              <a-button type="link" size="small" class="flex items-center gap-1">
                更多
                <DownOutlined class="text-[11px]" />
              </a-button>
              <template #overlay>
                <a-menu @click="onRowMenuClick($event, record)">
                  <a-menu-item key="organizations">分配组织</a-menu-item>
                  <a-menu-item key="memberships">租户关系</a-menu-item>
                  <a-menu-item v-if="record.status === 'active'" key="lock">锁定</a-menu-item>
                  <a-menu-item v-else-if="record.status === 'locked'" key="unlock">解锁</a-menu-item>
                  <!-- G02：管理员重置密码救济入口——仅启用状态且非本人展示，本人走右上角自助改密。 -->
                  <a-menu-item v-if="record.status === 'active' && record.id !== props.currentUserId" key="reset-password">重置密码</a-menu-item>
                  <a-menu-divider />
                  <a-menu-item v-if="record.status !== 'disabled'" key="disable" danger>停用账号</a-menu-item>
                  <a-menu-item v-else key="enable">启用账号</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </a-space>
          <span v-else class="text-xs text-[var(--color-text-muted)]">—</span>
        </template>
      </template>
    </AdminListPage>

    <!-- G16 用户详情聚合抽屉：资料/成员关系/角色/会话/最近认证事件 + 审计深链（G23）。 -->
    <UserDetailDrawer v-model:open="detailOpen" :user-id="detailUserId" />

    <!-- G02 管理员重置密码弹窗：新密码只经本请求提交，不回显；提交后该用户全部会话被撤销。 -->
    <a-modal v-model:open="resetPwOpen" title="重置用户密码" ok-text="重置" cancel-text="取消"
      :confirm-loading="resetPwSaving" @ok="submitResetPassword" @cancel="resetPwForm.new_password = ''">
      <a-form ref="resetPwFormRef" :model="resetPwForm" :rules="resetPwRules" layout="vertical">
        <a-form-item :label="`为 ${resetPwUser?.display_name || resetPwUser?.email || '用户'} 设置新密码（至少 12 位）`" name="new_password">
          <a-input-password v-model:value="resetPwForm.new_password" autocomplete="new-password" :maxlength="128" />
        </a-form-item>
        <a-alert type="warning" show-icon message="重置后该用户所有登录会话将被撤销，需使用新密码重新登录；密码不会在响应或审计中回显。" />
      </a-form>
    </a-modal>

    <a-modal v-model:open="createOpen" title="新建用户" ok-text="创建" cancel-text="取消"
      :confirm-loading="createSaving" @ok="createUser" @cancel="createForm.initial_password = ''">
      <a-form ref="createFormRef" :model="createForm" :rules="createRules" layout="vertical">
        <a-form-item label="所属租户" name="tenant_id">
          <a-select v-model:value="createForm.tenant_id" :options="tenantOptions" placeholder="选择活动租户" />
        </a-form-item>
        <a-form-item label="邮箱" name="email"><a-input v-model:value="createForm.email" autocomplete="off" :maxlength="254" /></a-form-item>
        <a-form-item label="姓名" name="display_name"><a-input v-model:value="createForm.display_name" :maxlength="120" /></a-form-item>
        <a-form-item label="初始密码" name="initial_password">
          <a-input-password v-model:value="createForm.initial_password" autocomplete="new-password" :maxlength="128" />
        </a-form-item>
        <a-alert type="info" show-icon message="密码仅在本次请求中提交，不会在创建响应或审计记录中回显。也可改用成员邀请流程。" />
      </a-form>
    </a-modal>

    <a-modal v-model:open="membershipDialogOpen" title="租户成员关系" :footer="null" width="680px">
      <p class="membership-intro">{{ membershipUser?.display_name || membershipUser?.email }} 的全局身份可关联多个租户。成员操作只作用于对应租户。</p>
      <a-spin :spinning="membershipLoading">
        <AdminEmpty v-if="!membershipLoading && !memberships.length" emoji="🔗" description="该用户暂未加入任何租户" />
        <div v-else class="membership-list">
          <div v-for="membership in memberships" :key="membership.tenant_id" class="membership-row">
            <div class="membership-info">
              <strong>{{ membership.tenant_name }}</strong>
              <a-tag :color="membership.membership_status === 'active' ? 'green' : membership.membership_status === 'departed' ? 'default' : 'orange'">
                {{ membership.membership_status === 'active' ? '在职' : membership.membership_status === 'departed' ? '已离职' : '已停用' }}
              </a-tag>
              <a-tag v-if="membership.tenant_status !== 'active'" color="default">租户已停用</a-tag>
            </div>
            <a-space class="membership-actions">
              <template v-if="membership.membership_status === 'active'">
                <a-button v-if="canManageUsers" size="small" :loading="membershipSaving === membership.tenant_id" @click="changeMembershipStatus(membership, 'disabled')">停用成员</a-button>
                <a-button v-if="canManageUsers" size="small" danger :loading="membershipSaving === membership.tenant_id" @click="changeMembershipStatus(membership, 'departed')">标记离职</a-button>
              </template>
              <template v-else-if="membership.membership_status === 'disabled'">
                <a-button v-if="canManageUsers" size="small" type="primary" :loading="membershipSaving === membership.tenant_id" @click="changeMembershipStatus(membership, 'active')">重新启用</a-button>
                <a-button v-if="canManageUsers" size="small" danger :loading="membershipSaving === membership.tenant_id" @click="changeMembershipStatus(membership, 'departed')">标记离职</a-button>
              </template>
              <a-tag v-else color="default">需重新发送邀请</a-tag>
            </a-space>
          </div>
        </div>
      </a-spin>
      <a-alert class="membership-note" type="info" show-icon message="离职后保留身份审计记录，但清除该租户的角色、用户组和组织归属。" />
    </a-modal>

    <a-modal v-model:open="sessionsOpen" :title="`${sessionUser?.display_name || sessionUser?.email || '用户'} · 活动会话`"
      :footer="null" width="980px">
      <p class="membership-intro">展示当前仍有效的 IAM 管理台会话和已申请离线访问权限的业务应用会话。远程退出后，在线 IAM 校验立即拒绝该会话。</p>
      <a-spin :spinning="sessionsLoading">
        <a-table v-if="sessions.length" :data-source="sessions" :columns="sessionColumns"
          :row-key="sessionRowKey" :pagination="{ pageSize: 6 }" :scroll="{ x: 910 }">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'type'">
              <a-tag>{{ record.type === 'management' ? '管理台' : '业务应用' }}</a-tag>
            </template>
            <template v-else-if="column.key === 'created_at' || column.key === 'expires_at'">
              {{ record[column.key] ? new Date(record[column.key]).toLocaleString() : '—' }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-button v-if="canManageUsers" type="link" danger size="small"
                :loading="revokingSession === `${record.type}:${record.id}`"
                :disabled="sessionUser?.id === props.currentUserId"
                :title="sessionUser?.id === props.currentUserId ? '请使用页面右上角的安全退出' : undefined"
                @click="revokeSession(record)">远程退出</a-button>
            </template>
          </template>
        </a-table>
        <AdminEmpty v-else-if="!sessionsLoading" emoji="🔑" description="该用户当前没有可续期的活动会话" />
      </a-spin>
      <a-alert class="membership-note" type="info" show-icon
        message="当前系统未采集会话设备名、浏览器 UA 或来源 IP，因此列表仅展示应用、会话起始时间和续期凭证到期时间。" />
    </a-modal>

    <!-- Wave 3：配权主路径第三步升级为穿梭框（对齐蓝图 distributionRole 的 Transfer 交互）。 -->
    <a-modal v-model:open="roleDialogOpen" title="配置租户角色" ok-text="保存角色" cancel-text="取消"
      width="760px" :confirm-loading="roleSaving" @ok="saveRoleBinding">
      <a-form layout="vertical">
        <a-form-item label="目标租户">
          <a-select v-model:value="roleTenantId" :options="roleTenantOptions" placeholder="选择用户所在的活跃租户"
            @change="loadMemberRoles" />
        </a-form-item>
        <a-form-item label="角色（可多选）">
          <a-transfer
            v-model:target-keys="roleIds"
            :data-source="roleTransferItems"
            class="w-full"
            show-search
            :disabled="!roleTenantId"
            :titles="['可选角色', '已配置角色']"
            :filter-option="filterRoleTransfer"
            :render="renderRoleTransfer"
            :list-style="{ width: '46%', height: '300px' }"
          />
        </a-form-item>
        <a-alert type="info" show-icon message="保存时会整表替换该用户在所选租户下的直接角色绑定（不含用户组继承）。后端按角色并集计算权限码。把角色移到右侧即完成勾选。" />
      </a-form>
    </a-modal>

    <a-modal v-model:open="organizationDialogOpen" title="分配用户组织" ok-text="保存归属" cancel-text="取消"
      :confirm-loading="organizationSaving" @ok="saveOrganizationAssignment">
      <a-form layout="vertical">
        <a-form-item label="租户">
          <a-select v-model:value="organizationTenantId" :options="membershipTenantOptions" @change="loadMemberOrganizations" />
        </a-form-item>
        <a-form-item label="组织">
          <a-select :value="organizationIds" mode="multiple" :options="organizationOptions" :max-tag-count="'responsive'"
            placeholder="选择一个或多个组织" @change="syncOrganizationSelection" />
        </a-form-item>
        <a-form-item label="主组织">
          <a-select v-model:value="primaryOrganizationId" allow-clear
            :options="organizationOptions.filter(option => organizationIds.includes(option.value))" placeholder="可选，作为默认部门" />
        </a-form-item>
        <a-alert type="info" show-icon message="成员只能关联到自己活动租户中的启用组织；停用的既有关联会保留显示。" />
      </a-form>
    </a-modal>
  </section>
</template>

<style scoped>
.users-page { display: grid; gap: 20px; }
.data-card { border-radius: 16px; }
.table-toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.user-search { width: min(320px, 100%); flex: 0 0 auto; }
.table-hint { flex: 1; color: var(--color-text-secondary); font-size: 12px; }
.membership-intro { margin: 0 0 16px; color: var(--color-text-secondary); line-height: 1.6; }
.membership-list { display: grid; gap: 10px; }
.membership-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px; border: 1px solid var(--color-border); border-radius: 12px; }
.membership-info, .membership-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.membership-info strong { margin-right: 4px; }
.membership-note { margin-top: 16px; }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
  .table-toolbar { align-items: stretch; flex-direction: column; }
  .user-search { width: 100%; }
  .membership-row { align-items: flex-start; flex-direction: column; }
}
</style>
