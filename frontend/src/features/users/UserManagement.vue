<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '../../shared/services/api'

interface TenantOption { id: string; name: string; status: string }
interface UserRecord {
  id: string
  email: string
  display_name: string
  status: 'active' | 'disabled' | 'locked'
  tenant_count: number
  created_at: string
}
interface RoleOption { id: string; tenant_id: string; name: string; status: string }
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
const roleId = ref('')
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
let requestSequence = 0
let organizationRequestSequence = 0

const activeTenants = computed(() => props.tenants.filter(tenant => tenant.status === 'active'))
const tenantOptions = computed(() => activeTenants.value.map(tenant => ({ value: tenant.id, label: tenant.name })))
const availableRoles = computed(() => roles.value
  .filter(role => role.tenant_id === roleTenantId.value && role.status === 'active')
  .map(role => ({ value: role.id, label: role.name })))

const columns = [
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 240, ellipsis: true },
  { title: '姓名', dataIndex: 'display_name', key: 'display_name', width: 170, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '租户关系数', dataIndex: 'tenant_count', key: 'tenant_count', width: 115 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 190 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 490, fixed: 'right' as const },
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
  roleId.value = ''
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
      message.warning('该用户没有活动租户成员关系，无法分配租户角色')
      return
    }
    roleDialogOpen.value = true
  } catch (error) { message.error(error instanceof Error ? error.message : '读取角色目录失败') }
}

async function saveRoleBinding(): Promise<void> {
  if (!roleUserId.value || !roleTenantId.value || !roleId.value) {
    message.warning('请选择租户和角色')
    return
  }
  roleSaving.value = true
  try {
    await api('/admin/role-bindings', {
      method: 'PUT',
      body: JSON.stringify({ user_id: roleUserId.value, tenant_id: roleTenantId.value, role_id: roleId.value }),
    })
    message.success('角色已绑定')
    roleDialogOpen.value = false
    await loadUsers()
    emit('changed')
  } catch (error) { message.error(error instanceof Error ? error.message : '角色绑定失败') }
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
    <header class="page-heading">
      <div><p class="eyebrow">IDENTITY DIRECTORY</p><h1>用户管理</h1>
        <p class="subtitle">全局账号状态会影响所有产品；租户停用和离职仅影响选中的租户成员关系。</p></div>
      <a-button type="primary" :disabled="!tenantOptions.length" @click="openCreate">＋ 新建用户</a-button>
    </header>

    <a-card class="data-card" :bordered="false">
      <div class="table-toolbar">
        <a-input-search v-model:value="searchText" class="user-search" placeholder="搜索邮箱或姓名" allow-clear
          @search="loadUsers" @clear="loadUsers" />
        <span class="table-hint">最多读取最近 500 个身份；用户可加入多个租户。</span>
        <a-button :loading="loading" @click="loadUsers">刷新</a-button>
      </div>
      <a-table :data-source="users" :columns="columns" :loading="loading" row-key="id"
        :scroll="{ x: 1320 }" :pagination="{ pageSize: 10, showSizeChanger: true }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'green' : record.status === 'locked' ? 'orange' : 'default'">
              {{ record.status === 'active' ? '启用' : record.status === 'locked' ? '管理员锁定' : '停用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'created_at'">{{ record.created_at ? new Date(record.created_at).toLocaleString() : '—' }}</template>
          <template v-else-if="column.key === 'actions'">
            <a-space :size="2">
              <a-button type="link" size="small" @click="openRoleBinding(record)">分配角色</a-button>
              <a-button type="link" size="small" @click="openOrganizationAssignment(record)">分配组织</a-button>
              <a-button type="link" size="small" @click="openMemberships(record)">租户关系</a-button>
              <a-button type="link" size="small" @click="openSessions(record)">会话</a-button>
              <a-button v-if="record.status === 'active'" type="link" size="small" @click="changeStatus(record, 'locked')">锁定</a-button>
              <a-button v-if="record.status === 'locked'" type="link" size="small" @click="changeStatus(record, 'active')">解锁</a-button>
              <a-button v-if="record.status !== 'disabled'" type="link" size="small" danger @click="changeStatus(record, 'disabled')">停用账号</a-button>
              <a-button v-if="record.status === 'disabled'" type="link" size="small" @click="changeStatus(record, 'active')">启用账号</a-button>
            </a-space>
          </template>
        </template>
        <template #emptyText><a-empty description="当前条件下没有用户，可创建用户或调整搜索条件" /></template>
      </a-table>
    </a-card>

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
        <a-empty v-if="!membershipLoading && !memberships.length" description="该用户暂未加入任何租户" />
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
                <a-button size="small" :loading="membershipSaving === membership.tenant_id" @click="changeMembershipStatus(membership, 'disabled')">停用成员</a-button>
                <a-button size="small" danger :loading="membershipSaving === membership.tenant_id" @click="changeMembershipStatus(membership, 'departed')">标记离职</a-button>
              </template>
              <template v-else-if="membership.membership_status === 'disabled'">
                <a-button size="small" type="primary" :loading="membershipSaving === membership.tenant_id" @click="changeMembershipStatus(membership, 'active')">重新启用</a-button>
                <a-button size="small" danger :loading="membershipSaving === membership.tenant_id" @click="changeMembershipStatus(membership, 'departed')">标记离职</a-button>
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
              <a-tag :color="record.type === 'management' ? 'purple' : 'blue'">
                {{ record.type === 'management' ? '管理台' : '业务应用' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'created_at' || column.key === 'expires_at'">
              {{ record[column.key] ? new Date(record[column.key]).toLocaleString() : '—' }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-button type="link" danger size="small"
                :loading="revokingSession === `${record.type}:${record.id}`"
                :disabled="sessionUser?.id === props.currentUserId"
                :title="sessionUser?.id === props.currentUserId ? '请使用页面右上角的安全退出' : undefined"
                @click="revokeSession(record)">远程退出</a-button>
            </template>
          </template>
        </a-table>
        <a-empty v-else-if="!sessionsLoading" description="该用户当前没有可续期的活动会话" />
      </a-spin>
      <a-alert class="membership-note" type="info" show-icon
        message="当前系统未采集会话设备名、浏览器 UA 或来源 IP，因此列表仅展示应用、会话起始时间和续期凭证到期时间。" />
    </a-modal>

    <a-modal v-model:open="roleDialogOpen" title="分配租户角色" ok-text="绑定角色" cancel-text="取消"
      :confirm-loading="roleSaving" @ok="saveRoleBinding">
      <a-form layout="vertical">
        <a-form-item label="目标租户">
          <a-select v-model:value="roleTenantId" :options="roleTenantOptions" placeholder="选择用户所属的活动租户"
            @change="roleId = ''" />
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model:value="roleId" :options="availableRoles" :disabled="!roleTenantId"
            placeholder="选择该租户中的启用角色" />
        </a-form-item>
        <a-alert type="info" show-icon message="服务端会校验用户成员关系和角色租户归属，防止跨租户绑定。" />
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
.page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.page-heading h1 { margin: 5px 0 7px; font-size: clamp(25px, 3vw, 32px); letter-spacing: -.035em; }
.page-heading .subtitle { max-width: 800px; margin: 0; color: #7c8798; line-height: 1.65; }
.eyebrow { margin: 0; color: #766fe8; font-size: 11px; font-weight: 750; letter-spacing: .14em; }
.data-card { border-radius: 16px; }
.table-toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.user-search { width: min(320px, 100%); flex: 0 0 auto; }
.table-hint { flex: 1; color: #7c8798; font-size: 12px; }
.membership-intro { margin: 0 0 16px; color: #7c8798; line-height: 1.6; }
.membership-list { display: grid; gap: 10px; }
.membership-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px; border: 1px solid #e8ebf2; border-radius: 12px; }
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
