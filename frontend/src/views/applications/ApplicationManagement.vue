<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHas, getCachedCapabilities } from '@/api/capabilities'
import { DownOutlined } from '@/plugins/icons'
import AdminListPage from '@/components/AdminListPage.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminDetailDrawer from '@/components/AdminDetailDrawer.vue'
import AdminMonoValue from '@/components/AdminMonoValue.vue'
import ApplicationPermissionDrawer from './ApplicationPermissionDrawer.vue'

interface TenantOption {
  id: string; name: string; status: string; kind?: 'organization' | 'consumer'
  can_read_applications?: boolean; can_manage_applications?: boolean; can_rotate_application_secret?: boolean
}
interface Application {
  id: string; tenant_id: string; name: string; client_id: string; permission_namespace: string
  description?: string | null
  trusted: boolean; status: 'active' | 'disabled'; redirect_uris: string[]
  post_logout_redirect_uris: string[]; created_at: string
  registration_policy: 'disabled' | 'open'; registration_role_id?: string | null
  registration_terms_version?: string | null; registration_privacy_version?: string | null
  backchannel_logout_uri?: string | null
  can_manage?: boolean; can_rotate_secret?: boolean
}
interface RegistrationRole { id: string; key: string; name: string }

const props = withDefaults(defineProps<{
  active: boolean
  tenants: TenantOption[]
  apiPrefix?: string
  shellApplications?: Application[] | null
  shellCatalogGeneration?: number
}>(), { apiPrefix: '/admin' })
const emit = defineEmits<{ changed: [] }>()

let hydratedCatalogGeneration = -1

const applications = ref<Application[]>([])
const registrationRoles = ref<RegistrationRole[]>([])
const loading = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const formOpen = ref(false)
const formRef = ref<{ validate: () => Promise<unknown> }>()
const permissionDrawerOpen = ref(false)
const permissionDrawerApplication = ref<Application | null>(null)
const secretOpen = ref(false)
const secretTitle = ref('保存应用客户端密钥')
const oneTimeSecret = ref('')
let requestSequence = 0
const form = reactive({
  tenant_id: '', client_id: '', name: '', description: '', permission_namespace: '', redirect_uris: '', post_logout_redirect_uris: '',
  registration_policy: 'disabled' as 'disabled' | 'open', registration_role_id: '',
  registration_terms_version: '', registration_privacy_version: '',
  backchannel_logout_uri: '',
})

// 与后端 default_namespace_from_client_id 对齐：取 Client ID 首段分隔符前的字母数字段
function defaultNamespaceFromClientId(clientId: string): string {
  const raw = clientId.trim()
  if (!raw) return ''
  const segment = raw.split(/[._-]/)[0]?.toLowerCase() || ''
  return /^[a-z0-9][a-z0-9._-]{0,99}$/.test(segment) ? segment : ''
}
const activeTenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.status === 'active' && canManageTenant(tenant.id))
  .map(tenant => ({ value: tenant.id, label: `${tenant.name} · ${tenant.kind === 'consumer' ? 'ToC 消费' : '组织/企业'}` })))
const isConsumerTenant = computed(() => props.tenants.find(tenant => tenant.id === form.tenant_id)?.kind === 'consumer')
const canCreateApplication = computed(() => activeTenantOptions.value.length > 0)
const canSetTrust = computed(() => Boolean(getCachedCapabilities()?.platform_admin) && cachedHas('app.manage'))
const rules = {
  tenant_id: [{ required: true, message: '请选择所属租户', trigger: 'change' }],
  client_id: [
    { required: true, message: '请输入 Client ID', trigger: 'blur' },
    { min: 3, max: 160, pattern: /^[A-Za-z0-9._-]+$/, message: 'Client ID 为 3–160 位字母、数字、点、下划线或连字符', trigger: 'blur' },
  ],
  name: [{ required: true, whitespace: true, max: 160, message: '请输入不超过 160 个字符的应用名称', trigger: 'blur' }],
  description: [{ max: 500, message: '说明不能超过 500 个字符', trigger: 'blur' }],
}
const columns = [
  // P397 列收敛：11 列 → 7 列（回调地址、授权模式、自助注册、说明收进详情抽屉）
  { title: '应用', dataIndex: 'name', key: 'name', width: 170, ellipsis: true },
  { title: '所属租户', dataIndex: 'tenant_id', key: 'tenant_id', width: 120, ellipsis: true },
  { title: 'Client ID', dataIndex: 'client_id', key: 'client_id', width: 150, ellipsis: true },
  { title: '权限命名空间', dataIndex: 'permission_namespace', key: 'permission_namespace', width: 110, ellipsis: true },
  { title: '回调', key: 'callbacks', width: 120 },
  { title: '状态', key: 'status_trust', width: 110 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 170, fixed: 'right' as const },
]
// 列宽合计 = 170+120+150+110+120+110+170 = 950

// ===== P397 工具条筛选：搜索 + 租户/状态/受信（前端即时过滤，兼容租户模式合并后的数据） =====
const searchText = ref('')
const tenantFilter = ref<string | undefined>(undefined)
const statusFilter = ref('')
const trustedFilter = ref('')
const filterTenantOptions = computed(() => props.tenants.map(tenant => ({ value: tenant.id, label: tenant.name })))
const statusOptions = [
  { value: 'active', label: '启用' },
  { value: 'disabled', label: '停用' },
]
const trustedOptions = [
  { value: 'trusted', label: '受信应用' },
  { value: 'untrusted', label: '普通应用' },
]
const filteredApplications = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return applications.value.filter(application => {
    if (tenantFilter.value && application.tenant_id !== tenantFilter.value) return false
    if (statusFilter.value && application.status !== statusFilter.value) return false
    if (trustedFilter.value === 'trusted' && !application.trusted) return false
    if (trustedFilter.value === 'untrusted' && application.trusted) return false
    if (!query) return true
    return `${application.name} ${application.client_id} ${application.description || ''}`.toLocaleLowerCase().includes(query)
  })
})

// ===== 行点击 → 应用详情抽屉：回调清单、协议信息与全部操作集中一处 =====
const detailOpen = ref(false)
const detailApplication = ref<Application | null>(null)

function openDetail(application: Application): void {
  detailApplication.value = application
  detailOpen.value = true
}

// 详情抽屉内打开权限项面板：关抽屉再开，避免双层叠放
function openPermissionsFromDrawer(): void {
  const application = detailApplication.value
  if (!application) return
  detailOpen.value = false
  openApplicationPermissions(application)
}

// 详情抽屉「更多」菜单：与表格行操作同口径（轮换/受信/启停/删除）
function onDetailMenuClick(info: { key: string | number }): void {
  const application = detailApplication.value
  if (!application) return
  const key = String(info.key) as ApplicationRowMenuKey
  if (key === 'rotateSecret') confirmSecretRotation(application)
  else if (key === 'trust') confirmTrustChange(application)
  else if (key === 'disable' || key === 'enable') changeStatus(application)
  else if (key === 'delete') deleteApplication(application)
}

// 行点击下钻详情；操作列与行内链接用 @click.stop 防冒泡
function rowProps(record: Application): Record<string, unknown> {
  return { class: 'cursor-pointer', onClick: () => openDetail(record) }
}

function tenantName(id: string): string {
  return props.tenants.find(tenant => tenant.id === id)?.name || '未知租户'
}

function canManageTenant(tenantId: string): boolean {
  // 以权限码为准：平台侧持 app.manage；租户侧看 capabilities 换算的 can_*。
  if (cachedHas('app.manage') && getCachedCapabilities()?.platform_admin) return true
  if (cachedHas('app.manage') && props.apiPrefix === '/admin') return true
  return props.tenants.some(tenant => tenant.id === tenantId && tenant.can_manage_applications === true)
}

function canManageApplication(application: Application): boolean {
  if (application.can_manage === true) return true
  // 平台列表未必回传 can_manage；L1 持 manage 码时可操作任意应用
  return cachedHas('app.manage') && Boolean(getCachedCapabilities()?.platform_admin)
}

function canRotateSecret(application: Application): boolean {
  if (application.can_rotate_secret === true) return true
  return cachedHas('app.secret.rotate') && Boolean(getCachedCapabilities()?.platform_admin)
}

function applicationPath(path: string): string {
  return `${props.apiPrefix}${path}`
}

function parseLines(value: string): string[] {
  return value.split(/\r?\n/).map(item => item.trim()).filter(Boolean)
}

function isSafeRedirectUri(value: string): boolean {
  try {
    const url = new URL(value)
    if (url.hash || url.username || url.password) return false
    return url.protocol === 'https:' || (url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))
  } catch { return false }
}

function hydrateFromShell(): boolean {
  if (props.apiPrefix !== '/admin' || props.shellApplications == null) return false
  const generation = props.shellCatalogGeneration ?? -1
  if (generation < 0 || generation === hydratedCatalogGeneration) return false
  applications.value = props.shellApplications
  hydratedCatalogGeneration = generation
  return true
}

async function loadApplications(): Promise<void> {
  const sequence = ++requestSequence
  loading.value = true
  try {
    let result: Application[]
    if (props.apiPrefix === '/admin') {
      result = await api<Application[]>(applicationPath('/applications'))
    } else {
      // 每个租户独立请求并带 tenant_id；即使个别租户权限刚被撤销，其它授权目录仍可用。
      const responses = await Promise.allSettled(props.tenants.map(tenant =>
        api<Application[]>(`${applicationPath('/applications')}?tenant_id=${encodeURIComponent(tenant.id)}`),
      ))
      result = responses.flatMap(response => response.status === 'fulfilled' ? response.value : [])
      if (responses.some(response => response.status === 'rejected')) {
        message.warning('部分租户应用目录暂时无法读取，已保留可访问的目录结果')
      }
    }
    if (sequence === requestSequence) {
      applications.value = result
      // 详情抽屉开着时同步最新记录，避免抽屉内操作后展示过期状态
      if (detailOpen.value && detailApplication.value) {
        detailApplication.value = result.find(item => item.id === detailApplication.value?.id) || detailApplication.value
      }
    }
  } catch (error) {
    if (sequence === requestSequence) {
      applications.value = []
      message.error(error instanceof Error ? error.message : '读取应用失败')
    }
  } finally { if (sequence === requestSequence) loading.value = false }
}

function openApplicationPermissions(application: Application): void {
  permissionDrawerApplication.value = application
  permissionDrawerOpen.value = true
}

function resetForm(): void {
  Object.assign(form, {
    tenant_id: activeTenantOptions.value[0]?.value || '', client_id: '', name: '', description: '', permission_namespace: '',
    redirect_uris: '', post_logout_redirect_uris: '',
    registration_policy: 'disabled', registration_role_id: '',
    registration_terms_version: '', registration_privacy_version: '',
    backchannel_logout_uri: '',
  })
  registrationRoles.value = []
  editingId.value = null
}

function createApplication(): void {
  resetForm()
  formOpen.value = true
}

async function editApplication(application: Application): Promise<void> {
  editingId.value = application.id
  Object.assign(form, {
    tenant_id: application.tenant_id, client_id: application.client_id, name: application.name,
    permission_namespace: application.permission_namespace,
    description: application.description || '', redirect_uris: application.redirect_uris.join('\n'),
    post_logout_redirect_uris: application.post_logout_redirect_uris.join('\n'),
    registration_policy: application.registration_policy || 'disabled',
    registration_role_id: application.registration_role_id || '',
    registration_terms_version: application.registration_terms_version || '',
    registration_privacy_version: application.registration_privacy_version || '',
    backchannel_logout_uri: application.backchannel_logout_uri || '',
  })
  formOpen.value = true
  try {
    registrationRoles.value = await api<RegistrationRole[]>(applicationPath(`/applications/${application.id}/registration-roles`))
  } catch (error) {
    registrationRoles.value = []
    message.error(error instanceof Error ? error.message : '无法读取应用可用的普通角色')
  }
}

async function saveApplication(): Promise<void> {
  try { await formRef.value?.validate() }
  catch { return }

  const isEditing = Boolean(editingId.value)
  if (isEditing && form.registration_policy === 'open'
      && (!form.registration_role_id || !form.registration_terms_version.trim() || !form.registration_privacy_version.trim())) {
    message.warning('开放自助注册需要选择普通角色，并配置条款与隐私政策版本')
    return
  }
  if (isEditing && form.registration_policy === 'open' && !isConsumerTenant.value) {
    message.warning('只有 ToC 消费租户可以开放自助注册；请先关闭注册并转换租户类型。')
    return
  }
  const redirectUris = parseLines(form.redirect_uris)
  const logoutUris = parseLines(form.post_logout_redirect_uris)
  if (!isEditing && !redirectUris.length) {
    message.warning('至少登记一个登录回调地址；应用创建后当前接口不允许修改回调白名单。')
    return
  }
  if (redirectUris.length > 20 || logoutUris.length > 20) {
    message.warning('每类回调地址最多登记 20 个')
    return
  }
  if ([...redirectUris, ...logoutUris].some(uri => !isSafeRedirectUri(uri))) {
    message.warning('回调地址必须使用 HTTPS；本地开发仅允许 localhost 或 127.0.0.1 的 HTTP 地址，且不能包含凭据或片段')
    return
  }

  saving.value = true
  const payload = isEditing
    ? {
        name: form.name.trim(), description: form.description.trim() || null,
        registration_policy: form.registration_policy,
        registration_role_id: form.registration_role_id || null,
        registration_terms_version: form.registration_terms_version.trim() || null,
        registration_privacy_version: form.registration_privacy_version.trim() || null,
        backchannel_logout_uri: form.backchannel_logout_uri.trim() || null,
      }
    : {
        tenant_id: form.tenant_id, client_id: form.client_id.trim(), name: form.name.trim(),
        description: form.description.trim() || null, redirect_uris: redirectUris,
        post_logout_redirect_uris: logoutUris,
        permission_namespace: form.permission_namespace.trim() || defaultNamespaceFromClientId(form.client_id) || undefined,
      }
  try {
    const result = await api<{ client_secret?: string }>(applicationPath(isEditing ? `/applications/${editingId.value}` : '/applications'), {
      method: isEditing ? 'PATCH' : 'POST', body: JSON.stringify(payload),
    })
    if (result.client_secret) showOneTimeSecret(result.client_secret, '保存新建应用的客户端密钥')
    message.success(isEditing ? '应用已更新' : '应用已创建')
    formOpen.value = false
    await loadApplications()
    emit('changed')
  } catch (error) { message.error(error instanceof Error ? error.message : '保存应用失败') }
  finally { saving.value = false }
}

function showOneTimeSecret(secret: string, title: string): void {
  oneTimeSecret.value = secret
  secretTitle.value = title
  secretOpen.value = true
}

function clearOneTimeSecret(): void { oneTimeSecret.value = '' }

async function copyOneTimeSecret(): Promise<void> {
  try { await navigator.clipboard.writeText(oneTimeSecret.value); message.success('密钥已复制') }
  catch { message.error('复制失败，请手动复制') }
}

function confirmSecretRotation(application: Application): void {
  Modal.confirm({
    title: '立即轮换 Client Secret？',
    content: '旧密钥会立即失效。确认你能同步更新业务服务端的密钥配置；新密钥只展示一次，未保存将无法再次读取。',
    okText: '立即轮换', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        const result = await api<{ client_secret: string }>(applicationPath(`/applications/${application.id}/rotate-secret`), { method: 'POST' })
        showOneTimeSecret(result.client_secret, '保存轮换后的应用客户端密钥')
        await loadApplications()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '客户端密钥轮换失败') }
    },
  })
}

function confirmTrustChange(application: Application): void {
  const trusted = !application.trusted
  Modal.confirm({
    title: trusted ? '确认设为受信应用？' : '确认撤销应用信任？',
    content: trusted
      ? '受信应用可跳过常规用户授权确认。只对经过审核的第一方应用开启。'
      : '撤销后新的授权请求将重新要求用户确认，并撤销该应用现有刷新会话。',
    okText: trusted ? '确认受信' : '撤销信任', cancelText: '取消',
    okButtonProps: trusted ? { danger: true } : undefined,
    onOk: async () => {
      try {
        await api(applicationPath(`/applications/${application.id}/trusted?trusted=${trusted}`), { method: 'PATCH' })
        message.success(trusted ? '应用已设为受信' : '已撤销应用信任，活动刷新会话已撤销')
        await loadApplications()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '修改应用信任状态失败') }
    },
  })
}

function changeStatus(application: Application): void {
  const status = application.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(applicationPath(`/applications/${application.id}/status`), {
        method: 'PATCH',
        body: JSON.stringify({ expected_status: application.status, status }),
      })
      message.success(status === 'active' ? '应用已启用' : '应用已停用，现有刷新会话已撤销')
      await loadApplications()
      emit('changed')
    } catch (error) { message.error(error instanceof Error ? error.message : '更新应用状态失败') }
  }
  if (status === 'disabled') Modal.confirm({
    title: '停用应用？', content: `停用“${application.name}”会阻止后续登录和令牌刷新；现有刷新会话会被撤销。`,
    okText: '停用应用', cancelText: '取消', okButtonProps: { danger: true }, onOk: update,
  })
  else void update()
}

// 操作列「更多」菜单（P352 收敛）：低频动作统一入口，删除为永久操作。
type ApplicationRowMenuKey = 'rotateSecret' | 'trust' | 'disable' | 'enable' | 'delete'

function onRowMenuClick(info: { key: string | number }, application: Application): void {
  const key = String(info.key) as ApplicationRowMenuKey
  if (key === 'rotateSecret') confirmSecretRotation(application)
  else if (key === 'trust') confirmTrustChange(application)
  else if (key === 'disable' || key === 'enable') changeStatus(application)
  else if (key === 'delete') deleteApplication(application)
}

// 删除应用（P352）：主题/OIDC 令牌级联清除，应用角色退化为租户角色；有用量账目时后端 409。
function deleteApplication(application: Application): void {
  Modal.confirm({
    title: `删除应用“${application.name}”？`,
    content: '将永久删除该应用及其主题、OIDC 客户端凭证、授权码与刷新令牌；该应用的角色会保留并退化为租户角色。此操作不可恢复。',
    okText: '永久删除', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(applicationPath(`/applications/${application.id}`), { method: 'DELETE' })
        message.success('应用已删除')
        await loadApplications()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '删除应用失败') }
    },
  })
}

watch(() => props.active, active => {
  if (!active) return
  // 平台壳已预拉应用目录时复用，避免路由激活重复请求 /admin/applications。
  if (hydrateFromShell()) return
  void loadApplications()
}, { immediate: true })

watch(() => [props.shellCatalogGeneration, props.shellApplications?.length] as const, () => {
  if (props.active) hydrateFromShell()
})

watch(() => form.client_id, clientId => {
  if (editingId.value) return
  const derived = defaultNamespaceFromClientId(clientId)
  if (derived) form.permission_namespace = derived
})
</script>

<template>
  <section class="application-management-page w-full min-w-0 max-w-full">
        <a-alert type="info" show-icon class="mb-3" message="高级列表：应用完整 CRUD。配角色/权限码/资源树请到「应用工作台」。" />
<AdminListPage
      eyebrow="APPLICATION DIRECTORY"
      title="应用管理"
      subtitle="登记 OAuth 客户端、精确回调白名单和授权信任策略。客户端密钥只在创建或轮换时展示一次。租户模式下新建需要租户范围管理权限。"
      hint="点击行查看应用详情与回调清单；应用归属、Client ID 和回调白名单创建后只读，编辑只更新名称与说明。"
      :columns="columns"
      :data-source="filteredApplications"
      :loading="loading"
      row-key="id"
      :custom-row="rowProps"
      class="scroll-actions-on-mobile"
      :scroll="{ x: 950, y: 'calc(100vh - 430px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
      empty-emoji="🧩"
      :empty-text="searchText || tenantFilter || statusFilter || trustedFilter ? '没有匹配的应用' : '暂无应用，可创建客户端并登记回调白名单'"
    >
      <template #header-extra>
        <a-button v-if="canCreateApplication" type="primary" @click="createApplication">＋ 新建应用</a-button>
      </template>
      <AdminSearchField v-model="searchText" placeholder="搜索应用名称、Client ID 或说明" :submit-on-clear="false" />
      <a-select v-model:value="tenantFilter" allow-clear show-search option-filter-prop="label" placeholder="全部租户" :options="filterTenantOptions" class="admin-filter-wide" />
      <a-select v-model:value="statusFilter" allow-clear placeholder="全部状态" :options="statusOptions" />
      <a-select v-model:value="trustedFilter" allow-clear placeholder="全部信任" :options="trustedOptions" />
      <template #actions>
        <a-button :loading="loading" @click="loadApplications">刷新</a-button>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <!-- 应用主行 + 说明副行：说明列收进抽屉后保留一行摘要 -->
          <div class="flex min-w-0 flex-col gap-0.5">
            <span class="truncate font-medium text-[var(--color-text-primary)]">{{ record.name }}</span>
            <span v-if="record.description" class="truncate text-xs text-[var(--color-text-muted)]">{{ record.description }}</span>
          </div>
        </template>
        <template v-else-if="column.key === 'tenant_id'">{{ tenantName(record.tenant_id) }}</template>
        <template v-else-if="column.key === 'client_id'">
          <AdminMonoValue :value="String(record.client_id)" max-width="140px" />
        </template>
        <template v-else-if="column.key === 'permission_namespace'">
          <span class="font-mono text-xs text-[var(--color-text-secondary)]">{{ record.permission_namespace }}</span>
        </template>
        <template v-else-if="column.key === 'callbacks'">
          <!-- 回调计数合并单元格：登录 n · 登出 m，点击进详情抽屉查看全部地址 -->
          <a-button v-if="record.redirect_uris.length || record.post_logout_redirect_uris.length" type="link" size="small" class="px-0" @click.stop="openDetail(record as Application)">
            登录 {{ record.redirect_uris.length }} · 登出 {{ record.post_logout_redirect_uris.length }}
          </a-button>
          <span v-else class="text-xs text-[var(--color-text-muted)]">未配置</span>
        </template>
        <template v-else-if="column.key === 'status_trust'">
          <div class="flex items-center gap-1">
            <a-tag :color="record.status === 'active' ? 'green' : 'default'" class="mr-0">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
            <a-tooltip v-if="record.trusted" title="受信应用：跳过常规用户授权确认（静默授权）">
              <span class="cursor-help border border-solid border-[var(--color-warning)] px-1 rounded-[2px] text-[10px] leading-4 text-[var(--color-warning)]">受信</span>
            </a-tooltip>
          </div>
        </template>
        <template v-else-if="column.key === 'actions'"><a-space :size="2" @click.stop>
          <a-button type="link" size="small" @click="openApplicationPermissions(record as Application)">权限项</a-button>
          <a-button v-if="canManageApplication(record as Application)" type="link" size="small" @click="editApplication(record as Application)">编辑</a-button>
          <a-dropdown v-if="canManageApplication(record as Application)">
            <a-button type="link" size="small" class="flex items-center gap-1">
              更多
              <DownOutlined class="text-[11px]" />
            </a-button>
            <template #overlay>
              <a-menu @click="onRowMenuClick($event, record as Application)">
                <a-menu-item v-if="canRotateSecret(record as Application)" key="rotateSecret">轮换密钥</a-menu-item>
                <a-menu-item v-if="canSetTrust" key="trust">{{ record.trusted ? '撤销信任' : '设为受信' }}</a-menu-item>
                <a-menu-divider />
                <a-menu-item key="disable" v-if="record.status === 'active'">停用</a-menu-item>
                <a-menu-item key="enable" v-else>启用</a-menu-item>
                <a-menu-divider />
                <a-menu-item key="delete" danger>删除应用</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </a-space></template>
      </template>
    </AdminListPage>

    <!-- 应用详情抽屉：协议信息 + 回调清单 + 全部操作（替代原 Popover 与分散列） -->
    <AdminDetailDrawer
      v-model:open="detailOpen"
      :title="detailApplication?.name || ''"
      :subtitle="detailApplication?.client_id || ''"
      :width="640"
    >
      <a-descriptions :column="1" size="small" bordered class="mb-4">
        <a-descriptions-item label="所属租户">{{ detailApplication ? tenantName(detailApplication.tenant_id) : '' }}</a-descriptions-item>
        <a-descriptions-item label="权限命名空间">
          <span class="font-mono text-xs text-[var(--color-text-secondary)]">{{ detailApplication?.permission_namespace }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="授权模式">{{ detailApplication?.trusted ? '受信 · 静默授权' : '逐次用户确认' }}</a-descriptions-item>
        <a-descriptions-item label="运行状态">
          <a-tag :color="detailApplication?.status === 'active' ? 'green' : 'default'">{{ detailApplication?.status === 'active' ? '启用' : '停用' }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="自助注册">
          <template v-if="detailApplication?.registration_policy === 'open'">
            开放<span v-if="detailApplication?.registration_terms_version" class="text-xs text-[var(--color-text-muted)]">（条款 {{ detailApplication.registration_terms_version }} · 隐私 {{ detailApplication.registration_privacy_version || '—' }}）</span>
          </template>
          <template v-else>关闭</template>
        </a-descriptions-item>
        <a-descriptions-item label="单点登出联动">
          <span v-if="detailApplication?.backchannel_logout_uri" class="font-mono text-xs break-all text-[var(--color-text-secondary)]">{{ detailApplication.backchannel_logout_uri }}</span>
          <span v-else class="text-xs text-[var(--color-text-muted)]">未接入</span>
        </a-descriptions-item>
      </a-descriptions>

      <div class="mb-2 text-[13px] font-semibold text-[var(--color-text-primary)]">登录回调（{{ detailApplication?.redirect_uris.length || 0 }}）</div>
      <div class="mb-4 flex flex-col gap-1">
        <code v-for="uri in detailApplication?.redirect_uris || []" :key="uri" class="border border-solid border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 py-1 rounded-[var(--radius-sm)] font-mono text-xs break-all text-[var(--color-text-secondary)]">{{ uri }}</code>
        <span v-if="!detailApplication?.redirect_uris.length" class="text-xs text-[var(--color-text-muted)]">未配置</span>
      </div>
      <div class="mb-2 text-[13px] font-semibold text-[var(--color-text-primary)]">登出回调（{{ detailApplication?.post_logout_redirect_uris.length || 0 }}）</div>
      <div class="mb-4 flex flex-col gap-1">
        <code v-for="uri in detailApplication?.post_logout_redirect_uris || []" :key="uri" class="border border-solid border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 py-1 rounded-[var(--radius-sm)] font-mono text-xs break-all text-[var(--color-text-secondary)]">{{ uri }}</code>
        <span v-if="!detailApplication?.post_logout_redirect_uris.length" class="text-xs text-[var(--color-text-muted)]">未配置</span>
      </div>

      <template #footer>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <a-space :size="4">
            <a-button size="small" @click="openPermissionsFromDrawer">权限项</a-button>
            <a-button v-if="detailApplication && canManageApplication(detailApplication)" size="small" @click="editApplication(detailApplication); detailOpen = false">编辑</a-button>
          </a-space>
          <a-dropdown v-if="detailApplication && canManageApplication(detailApplication)">
            <a-button size="small" class="flex items-center gap-1">
              更多操作
              <DownOutlined class="text-[11px]" />
            </a-button>
            <template #overlay>
              <a-menu @click="onDetailMenuClick">
                <a-menu-item v-if="detailApplication && canRotateSecret(detailApplication)" key="rotateSecret">轮换密钥</a-menu-item>
                <a-menu-item v-if="canSetTrust" key="trust">{{ detailApplication?.trusted ? '撤销信任' : '设为受信' }}</a-menu-item>
                <a-menu-divider />
                <a-menu-item key="disable" v-if="detailApplication?.status === 'active'">停用</a-menu-item>
                <a-menu-item key="enable" v-else>启用</a-menu-item>
                <a-menu-divider />
                <a-menu-item key="delete" danger>删除应用</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </template>
    </AdminDetailDrawer>

    <a-modal v-model:open="formOpen" :title="editingId ? `编辑应用：${form.name}` : '新建应用'"
      ok-text="保存" cancel-text="取消" :confirm-loading="saving" @ok="saveApplication">
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <template v-if="editingId">
          <a-form-item label="所属租户"><a-input :value="tenantName(form.tenant_id)" disabled /></a-form-item>
          <a-form-item label="Client ID"><a-input :value="form.client_id" disabled /></a-form-item>
          <a-form-item label="权限命名空间"><a-input :value="form.permission_namespace" disabled /></a-form-item>
          <a-form-item label="登录回调地址"><a-textarea :value="form.redirect_uris" :rows="3" disabled /></a-form-item>
          <a-form-item label="退出回调地址"><a-textarea :value="form.post_logout_redirect_uris || '未配置'" :rows="2" disabled /></a-form-item>
        </template>
        <template v-else>
          <a-form-item label="所属租户" name="tenant_id"><a-select v-model:value="form.tenant_id" :options="activeTenantOptions" placeholder="选择所属租户" /></a-form-item>
          <a-form-item label="Client ID" name="client_id"><a-input v-model:value="form.client_id" :maxlength="160" /></a-form-item>
          <a-form-item label="权限命名空间" required>
            <a-input v-model:value="form.permission_namespace" :maxlength="100" placeholder="默认随 Client ID 首段推导，创建后不可修改" />
          </a-form-item>
          <a-form-item label="登录回调地址（每行一个，最多 20 个）" required><a-textarea v-model:value="form.redirect_uris" :rows="4" placeholder="https://app.example.com/auth/callback" /></a-form-item>
          <a-form-item label="退出回调地址（每行一个，最多 20 个）"><a-textarea v-model:value="form.post_logout_redirect_uris" :rows="3" placeholder="https://app.example.com/logout/callback" /></a-form-item>
        </template>
        <a-form-item label="应用名称" name="name"><a-input v-model:value="form.name" :maxlength="160" /></a-form-item>
        <a-form-item label="描述" name="description"><a-textarea v-model:value="form.description" :rows="2" :maxlength="500" /></a-form-item>
        <template v-if="editingId">
          <a-divider orientation="left">ToC 用户自助注册</a-divider>
          <a-alert class="registration-policy-hint" :message="isConsumerTenant ? '开放注册还要求全局 ALLOW_PUBLIC_REGISTRATION、SMTP、已发布登录主题的注册入口及用户协议/隐私链接同时可用。' : '当前为组织/企业租户，后端禁止公开注册。请先关闭注册，再将租户显式转换为 ToC 消费租户。'" type="info" show-icon />
          <a-form-item label="注册策略"><a-select v-model:value="form.registration_policy"><a-select-option value="disabled">关闭（默认）</a-select-option><a-select-option value="open" :disabled="!isConsumerTenant">允许用户自助注册</a-select-option></a-select></a-form-item>
          <template v-if="form.registration_policy === 'open'">
            <a-form-item label="新用户默认角色"><a-select v-model:value="form.registration_role_id" :options="registrationRoles.map(role => ({ value: role.id, label: `${role.name}（${role.key}）` }))" placeholder="选择当前应用的普通角色" /></a-form-item>
            <div class="registration-version-grid">
              <a-form-item label="用户协议版本"><a-input v-model:value="form.registration_terms_version" :maxlength="80" placeholder="例如 2026-10" /></a-form-item>
              <a-form-item label="隐私政策版本"><a-input v-model:value="form.registration_privacy_version" :maxlength="80" placeholder="例如 2026-10" /></a-form-item>
            </div>
            <p class="table-hint">需先在登录主题中填写用户协议与隐私政策链接并发布；只有邮箱验证成功后，系统才会创建用户并绑定这里选择的角色。</p>
          </template>
        </template>
        <!-- G19 OIDC Back-Channel Logout：IAM 撤销会话后向该地址推送 logout_token，联动业务方销毁本地会话。 -->
        <template v-if="editingId">
          <a-divider orientation="left">单点登出联动（OIDC Back-Channel Logout）</a-divider>
          <a-form-item label="Back-Channel Logout 地址">
            <a-input v-model:value="form.backchannel_logout_uri" :maxlength="500"
              placeholder="https://app.example.com/backchannel-logout（留空表示未接入）" />
          </a-form-item>
          <p class="table-hint">必须为 HTTPS（本地开发限 localhost）。应用未配置时，IAM 登出/撤权不向业务方推送登出令牌，业务会话依赖令牌过期或在线校验失效。</p>
        </template>
        <a-alert :message="editingId ? '编辑不会修改租户、Client ID、回调白名单、密钥和信任状态。' : '请核对回调白名单后再创建。新应用默认要求用户确认；Client Secret 只展示一次。回调地址创建后不可通过当前 API 修改。'" :type="editingId ? 'info' : 'warning'" show-icon />
      </a-form>
    </a-modal>

    <ApplicationPermissionDrawer
      v-model:open="permissionDrawerOpen"
      :application="permissionDrawerApplication"
      :api-prefix="apiPrefix"
      @changed="emit('changed')"
    />

    <a-modal v-model:open="secretOpen" :title="secretTitle" ok-text="我已安全保存"
      :cancel-button-props="{ style: { display: 'none' } }" @ok="clearOneTimeSecret" @after-close="clearOneTimeSecret">
      <a-alert message="客户端密钥只展示这一次。请将它保存到业务系统服务端的密钥管理器，不要提交到前端代码或版本库。轮换密钥会让旧密钥立即失效。" type="warning" show-icon />
      <a-input-password class="client-secret-field" :value="oneTimeSecret" readonly />
      <a-button block @click="copyOneTimeSecret">复制密钥</a-button>
    </a-modal>
  </section>
</template>

<style scoped>
.application-management-page { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; min-width: 0; max-width: 100%; }
.data-card { border-radius: 16px; }
.table-hint { flex: 1; color: var(--color-text-secondary); font-size: 12px; }
.registration-policy-hint { margin-bottom: 16px; }
.registration-version-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
</style>
