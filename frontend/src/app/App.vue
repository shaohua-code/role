<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, type Component } from 'vue'
import { message, theme as antTheme } from 'ant-design-vue'
import { ApiRequestError, api, getToken, setToken, type AdminOverview } from '../shared/services/api'
import { getReadiness, ReadinessError } from '../shared/services/health'
import { ensureManagementUi } from './ui/antd'
import FeatureLoadError from '../shared/components/FeatureLoadError.vue'
import FeatureLoading from '../shared/components/FeatureLoading.vue'
import AppSidebar from './components/AppSidebar.vue'
import AuthEntry from './auth/AuthEntry.vue'
import { NAV_ITEMS, PAGE_INFO as pageInfo, TENANT_NAV_ITEMS, type PageKey } from './navigation'

// 按管理领域拆分异步模块：首屏先加载工作台，导航到其他功能时再下载对应页面。
// 加载状态组件共用一份，失败时提示用户刷新以读取当前部署的静态资源清单。
type FeatureLoader = () => Promise<{ default: Component }>
const loadFeature = (loader: FeatureLoader) => defineAsyncComponent({
  loader,
  loadingComponent: FeatureLoading,
  errorComponent: FeatureLoadError,
  delay: 120,
  timeout: 30_000,
})
const AuthorizationSimulator = loadFeature(() => import('../features/access-control/AuthorizationSimulator.vue'))
const GroupManagement = loadFeature(() => import('../features/groups/GroupManagement.vue'))
const LoginThemeManagement = loadFeature(() => import('../features/themes/LoginThemeManagement.vue'))
const OverviewPage = loadFeature(() => import('../features/overview/OverviewPage.vue'))
const ModelGovernancePage = loadFeature(() => import('../features/models/ModelGovernancePage.vue'))
const TenantManagement = loadFeature(() => import('../features/tenants/TenantManagement.vue'))
const ApplicationManagement = loadFeature(() => import('../features/applications/ApplicationManagement.vue'))
const ApplicationRoleManagement = loadFeature(() => import('../features/application-roles/ApplicationRoleManagement.vue'))
const AuditLogPage = loadFeature(() => import('../features/audit/AuditLogPage.vue'))
const InvitationManagement = loadFeature(() => import('../features/invitations/InvitationManagement.vue'))
const RoleManagement = loadFeature(() => import('../features/roles/RoleManagement.vue'))
const PermissionCatalog = loadFeature(() => import('../features/permissions/PermissionCatalog.vue'))
const UserManagement = loadFeature(() => import('../features/users/UserManagement.vue'))
const OrganizationManagement = loadFeature(() => import('../features/organizations/OrganizationManagement.vue'))
const TenantAccessManagement = loadFeature(() => import('../features/tenant-admin/TenantAccessManagement.vue'))

type Row = Record<string, unknown>
type ConsoleMode = 'platform' | 'tenant' | 'no_access'
type TenantMembership = { tenant_id: string; tenant_name: string; tenant_kind: 'organization' | 'consumer'; membership_status: string; tenant_status: string }
const page = ref<PageKey>('overview')
// 未访问页面不创建 DOM；访问过的页面在导航切换后保留，避免丢失草稿和筛选状态。
// 开发容器启用 Vite polling，Windows bind mount 更新后会重新编译本模块。
const visitedPages = ref(new Set<PageKey>(['overview']))
const currentUser = ref<{ id?: string; email?: string; display_name?: string } | null>(null)
const consoleMode = ref<ConsoleMode>('platform')
const loading = ref(false)
const overview = ref<AdminOverview | null>(null)
const healthState = ref('检查中')
const readinessRefreshing = ref(false)
const dictionariesLoading = ref(false)
const dictionariesNeedRetry = ref(false)
let readinessTimer: number | undefined
// 在侧栏显示可操作的依赖状态，避免把“API 进程存活”误报为“服务已经可用”。
async function refreshReadiness(): Promise<void> {
  // 定时轮询和用户手动重查可能同时触发；同一时刻只保留一个探针请求。
  if (readinessRefreshing.value) return
  readinessRefreshing.value = true
  try {
    await getReadiness()
    healthState.value = '服务正常'
  } catch (error) {
    if (!(error instanceof ReadinessError)) {
      healthState.value = '后端未连接'
      return
    }
    healthState.value = ({
      database_migration_pending: '数据库待迁移',
      database_not_ready: '数据库不可用',
      migration_state_unavailable: '迁移状态不可用',
    } as Record<string, string>)[error.reason] ?? '服务未就绪'
  } finally {
    readinessRefreshing.value = false
  }
}
// OIDC 往返地址只允许本站的授权端点，避免 return_to 成为开放重定向。
const loginReturnTo = (() => {
  const raw = new URLSearchParams(window.location.search).get('return_to') || ''
  try {
    const target = new URL(raw, window.location.origin)
    return target.origin === window.location.origin && target.pathname === '/api/v1/oidc/authorize'
      ? `${target.pathname}${target.search}` : ''
  } catch { return '' }
})()
// 一次性凭证通过 fragment 交付，避免进入服务端访问日志或 Referer；读取后立即清掉当前历史项里的 fragment。
const authFragment = new URLSearchParams(window.location.hash.replace(/^#/, ''))
const invitationToken = authFragment.get('invite') || ''
const consentTicket = authFragment.get('consent') || ''
const passwordResetToken = authFragment.get('password-reset') || ''
if (['invite', 'consent', 'password-reset'].some((key) => authFragment.has(key))) {
  window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`)
}
const token = ref(loginReturnTo || invitationToken || consentTicket || passwordResetToken ? null : getToken())
const tenants = ref<Row[]>([])
const applications = ref<Row[]>([])
const roleOptions = ref<Row[]>([])
const themeAppId = ref('')
const visibleNavigation = computed(() => consoleMode.value === 'platform'
  ? NAV_ITEMS
  : consoleMode.value === 'tenant'
    ? TENANT_NAV_ITEMS.filter(item => {
      if (item.key === 'applications') return tenants.value.some(tenant => tenant.can_read_applications || tenant.can_manage_applications)
      if (item.key === 'application_roles') return tenants.value.some(tenant => tenant.can_read_applications || tenant.can_manage_applications)
      if (item.key === 'organizations' || item.key === 'tenant_access') return tenants.value.some(tenant => tenant.can_read_organizations)
      return false
    })
    : [])
let pageRequestSequence = 0

const themeMode = ref(localStorage.getItem('iam-theme') === 'dark' ? 'dark' : 'light')
const primaryColor = ref(/^#[\da-f]{6}$/i.test(localStorage.getItem('iam-primary-color') || '') ? localStorage.getItem('iam-primary-color')! : '#756df2')
const density = ref(localStorage.getItem('iam-density') === 'compact' ? 'compact' : 'comfortable')
const antdTheme = computed(() => ({ algorithm: themeMode.value === 'dark' ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
  token: { colorPrimary: primaryColor.value, borderRadius: 8 } }))
async function loadPage(): Promise<void> {
  if (!token.value || consoleMode.value !== 'platform' || page.value !== 'overview') return
  const requestSequence = ++pageRequestSequence
  loading.value = true
  try {
    const result = await api<AdminOverview>('/admin/overview')
    if (requestSequence === pageRequestSequence && page.value === 'overview') overview.value = result
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取概览失败')
  } finally { if (requestSequence === pageRequestSequence) loading.value = false }
}

async function loadDictionaries(): Promise<void> {
  if (consoleMode.value !== 'platform' || dictionariesLoading.value) return
  dictionariesLoading.value = true
  try {
    const [tenantRows, applicationRows, roles] = await Promise.all([
      api<Row[]>('/admin/tenants'), api<Row[]>('/admin/applications'), api<Row[]>('/admin/roles'),
    ])
    tenants.value = tenantRows
    applications.value = applicationRows
    roleOptions.value = roles
    dictionariesNeedRetry.value = false
    if (applications.value.length && !themeAppId.value) themeAppId.value = String(applications.value[0].id)
  } catch {
    // 初始化时字典读取失败会禁用创建入口；保留重试标记，后续导航时重新拉取。
    dictionariesNeedRetry.value = true
    message.warning('租户、应用或角色目录暂时无法读取；切换页面后会自动重试。')
  } finally {
    dictionariesLoading.value = false
  }
}

async function loadTenantConsole(userId: string): Promise<void> {
  // 先读取当前用户自己的成员关系，再分别检查组织权限和逐应用授权；路由仍会自行过滤数据。
  const memberships = await api<TenantMembership[]>(`/tenant-admin/users/${encodeURIComponent(userId)}/memberships`)
  const activeMemberships = memberships.filter(item => item.membership_status === 'active' && item.tenant_status === 'active')
  const scopedTenants = await Promise.all(activeMemberships.map(async membership => {
    try {
      // 管理权限也可读；只查 manage 会把只有 read 权限的租户管理员误判成无权访问。
      const checkPermission = (permissionCode: string) => api<{ allowed?: boolean }>('/authorization/check', {
        method: 'POST',
        body: JSON.stringify({ tenant_id: membership.tenant_id, permission_code: permissionCode }),
      })
      const [organizationRead, organizationManage, applicationRead, applicationManage, secretRotate, scopedApplications] = await Promise.all([
        checkPermission('iam.organization.read'),
        checkPermission('iam.organization.manage'),
        checkPermission('iam.application.read'),
        checkPermission('iam.application.manage'),
        checkPermission('iam.application.secret.rotate'),
        api<Row[]>(`/tenant-admin/applications?tenant_id=${encodeURIComponent(membership.tenant_id)}`).catch(() => []),
      ])
      const canReadOrganizations = organizationRead.allowed === true || organizationManage.allowed === true
      const canReadApplications = applicationRead.allowed === true || applicationManage.allowed === true
        || scopedApplications.length > 0
      if (!canReadOrganizations && !canReadApplications) return null
      return { id: membership.tenant_id, name: membership.tenant_name, kind: membership.tenant_kind, status: membership.tenant_status,
        can_read_organizations: canReadOrganizations,
        can_manage_organizations: organizationManage.allowed === true,
        can_read_applications: canReadApplications,
        can_manage_applications: applicationManage.allowed === true,
        can_rotate_application_secret: secretRotate.allowed === true
          || scopedApplications.some(application => application.can_rotate_secret === true) }
    } catch { return null }
  }))
  tenants.value = scopedTenants.filter((tenant): tenant is NonNullable<typeof tenant> => tenant !== null)
  consoleMode.value = tenants.value.length ? 'tenant' : 'no_access'
  const firstPage = visibleNavigation.value[0]?.key || 'organizations'
  page.value = firstPage
  visitedPages.value = new Set<PageKey>([firstPage])
}

async function initializeConsole(user: { id?: string }): Promise<void> {
  try {
    // `/admin/overview` is server-protected and serves as the platform-admin capability check.
    overview.value = await api<AdminOverview>('/admin/overview')
    consoleMode.value = 'platform'
    page.value = 'overview'
    visitedPages.value = new Set<PageKey>(['overview'])
    await loadDictionaries()
    return
  } catch (error) {
    if (!(error instanceof ApiRequestError) || error.status !== 403) {
      message.error(error instanceof Error ? error.message : '无法初始化管理台')
      consoleMode.value = 'no_access'
      page.value = 'organizations'
      return
    }
  }

  if (!user.id) {
    consoleMode.value = 'no_access'
    page.value = 'organizations'
    return
  }
  try { await loadTenantConsole(user.id) }
  catch {
    consoleMode.value = 'no_access'
    page.value = 'organizations'
    tenants.value = []
  }
}

async function onAuthenticated(
  result: { access_token: string; user: { id?: string; email?: string; display_name?: string } },
  redirectTo?: string,
): Promise<void> {
  // OIDC 登录会立刻跳回业务应用，无须下载管理组件；邀请接受会进入控制台，必须先注册它们。
  if (!redirectTo) {
    try { await ensureManagementUi() }
    catch {
      message.error('管理组件加载失败，请刷新页面后重新登录')
      return
    }
  }
  setToken(result.access_token)
  token.value = result.access_token
  currentUser.value = result.user
  // OIDC 登录马上返回业务应用；此时只建立 IAM 管理会话，不预加载管理台目录。
  if (redirectTo) return
  await initializeConsole(result.user)
}

async function signOut(): Promise<void> {
  try { await api('/auth/logout', { method: 'POST' }) } catch { /* 令牌过期时本地仍须可退出。 */ }
  setToken(null); token.value = null; currentUser.value = null
  consoleMode.value = 'platform'; tenants.value = []; applications.value = []; roleOptions.value = []
}

function setPage(next: PageKey): void {
  if (!visibleNavigation.value.some(item => item.key === next)) return
  page.value = next
  visitedPages.value.add(next)
  void loadPage()
  if (dictionariesNeedRetry.value) void loadDictionaries()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
function onThemePreferenceChange(): void {
  localStorage.setItem('iam-theme', themeMode.value); localStorage.setItem('iam-primary-color', primaryColor.value); localStorage.setItem('iam-density', density.value)
}

onMounted(async () => {
  // api.ts 已清除本标签页 token 并广播其他标签页；此处只更新 Vue 状态，避免收到远端事件后再次广播。
  window.addEventListener('iam:unauthorized', () => { token.value = null; currentUser.value = null })
  // 状态探测与认证会话恢复并行，探针慢或失败不阻塞后台登录。
  void refreshReadiness()
  // 运行期间可能发生数据库/迁移状态变化；定时重查并避免保留过时的绿色状态。
  readinessTimer = window.setInterval(() => { void refreshReadiness() }, 30_000)
  if (token.value) {
    try {
      currentUser.value = await api<{ id?: string; email?: string; display_name?: string }>('/auth/me')
      await initializeConsole(currentUser.value)
    }
    catch { setToken(null); token.value = null }
  }
})

onUnmounted(() => {
  if (readinessTimer !== undefined) window.clearInterval(readinessTimer)
})
</script>

<template>
  <a-config-provider :theme="antdTheme">
      <AuthEntry v-if="!token"
        :login-return-to="loginReturnTo"
        :invitation-token="invitationToken"
        :consent-ticket="consentTicket"
        :password-reset-token="passwordResetToken"
        :readiness-state="healthState"
        :readiness-loading="readinessRefreshing"
        @authenticated="onAuthenticated"
        @refresh-readiness="refreshReadiness"
      />
    <div v-else class="admin-shell" :data-theme="themeMode" :data-density="density" :style="{ '--accent': primaryColor }">
      <AppSidebar :page="page" :health-state="healthState" :items="visibleNavigation"
        :mode-label="consoleMode === 'platform' ? '平台管理' : consoleMode === 'tenant' ? '租户管理' : '访问受限'" @navigate="setPage" />
      <main class="main">
        <header class="topbar">
          <div class="breadcrumbs">{{ consoleMode === 'tenant' ? '租户工作台' : consoleMode === 'platform' ? '平台' : '访问受限' }} <span>/</span> {{ pageInfo[page].title }}</div>
          <div class="profile">
            <a-popover trigger="click" placement="bottomRight"><template #content><div class="appearance-panel">
              <label>界面主题</label><a-radio-group v-model:value="themeMode" button-style="solid" @change="onThemePreferenceChange"><a-radio-button value="light">浅色</a-radio-button><a-radio-button value="dark">深色</a-radio-button></a-radio-group>
              <label>界面密度</label><a-radio-group v-model:value="density" button-style="solid" @change="onThemePreferenceChange"><a-radio-button value="comfortable">舒适</a-radio-button><a-radio-button value="compact">紧凑</a-radio-button></a-radio-group>
              <label>品牌主色</label><input v-model="primaryColor" class="color-input" type="color" @change="onThemePreferenceChange" />
              <small>外观偏好保存在当前会话浏览器</small></div></template><a-button>◐ 外观</a-button></a-popover>
            <span class="avatar">{{ currentUser?.display_name?.slice(0, 1) || '管' }}</span><span>{{ currentUser?.display_name || currentUser?.email || '平台管理员' }}</span><a-button type="link" @click="signOut">退出</a-button>
          </div>
        </header>

        <section class="content">
          <div v-if="visitedPages.has('themes')" v-show="page === 'themes'">
            <LoginThemeManagement
              :active="page === 'themes'"
              :applications="applications"
              v-model:selected-application-id="themeAppId"
              @navigate="setPage"
            />
          </div>
          <div v-if="visitedPages.has('models') || visitedPages.has('model_usage')" v-show="page === 'models' || page === 'model_usage'">
            <ModelGovernancePage :active="page === 'models' || page === 'model_usage'" :view="page === 'models' ? 'catalog' : 'usage'" />
          </div>
          <div v-if="visitedPages.has('tenants')" v-show="page === 'tenants'">
            <TenantManagement :active="page === 'tenants'" @changed="loadDictionaries" />
          </div>
          <div v-if="visitedPages.has('applications')" v-show="page === 'applications'">
            <ApplicationManagement :active="page === 'applications'"
              :api-prefix="consoleMode === 'tenant' ? '/tenant-admin' : '/admin'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), can_read_applications: tenant.can_read_applications === true, can_manage_applications: tenant.can_manage_applications === true, can_rotate_application_secret: tenant.can_rotate_application_secret === true }))"
              @changed="consoleMode === 'platform' ? loadDictionaries() : undefined" />
          </div>
          <div v-if="visitedPages.has('audit')" v-show="page === 'audit'">
            <AuditLogPage :active="page === 'audit'" />
          </div>
          <div v-if="visitedPages.has('invitations')" v-show="page === 'invitations'">
            <InvitationManagement
              :active="page === 'invitations'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) }))"
              :roles="roleOptions.map(role => ({ id: String(role.id), tenant_id: String(role.tenant_id), name: String(role.name), status: String(role.status) }))"
            />
          </div>
          <div v-if="visitedPages.has('roles')" v-show="page === 'roles'">
            <RoleManagement
              :active="page === 'roles'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) }))"
              :applications="applications.map(application => ({ id: String(application.id), tenant_id: String(application.tenant_id), name: String(application.name), status: String(application.status) }))"
              @changed="loadDictionaries"
            />
          </div>
          <div v-if="visitedPages.has('permissions')" v-show="page === 'permissions'">
            <PermissionCatalog :active="page === 'permissions'" />
          </div>
          <div v-if="visitedPages.has('users')" v-show="page === 'users'">
            <UserManagement :active="page === 'users'"
              :current-user-id="String(currentUser?.id || '')"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) }))"
              @changed="loadDictionaries" />
          </div>
          <div v-if="visitedPages.has('organizations') && consoleMode !== 'no_access'" v-show="page === 'organizations'">
            <OrganizationManagement :active="page === 'organizations'"
              :api-prefix="consoleMode === 'tenant' ? '/tenant-admin' : '/admin'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), can_read_organizations: consoleMode === 'platform' || tenant.can_read_organizations === true, can_manage_organizations: consoleMode === 'platform' || tenant.can_manage_organizations === true }))" />
          </div>
          <div v-if="visitedPages.has('application_roles') && consoleMode === 'tenant'" v-show="page === 'application_roles'">
            <ApplicationRoleManagement
              :active="page === 'application_roles'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), can_read_applications: tenant.can_read_applications === true || tenant.can_manage_applications === true }))"
            />
          </div>
          <div v-if="visitedPages.has('tenant_access') && consoleMode === 'tenant'" v-show="page === 'tenant_access'">
            <TenantAccessManagement :active="page === 'tenant_access'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), can_read_organizations: tenant.can_read_organizations === true, can_manage_organizations: tenant.can_manage_organizations === true }))" />
          </div>
          <template v-if="page === 'overview'">
            <OverviewPage
              :overview="overview"
              :health-state="healthState"
              :loading="loading"
              @navigate="setPage"
              @refresh="loadPage"
            />
          </template>
          <a-card v-if="consoleMode === 'no_access'" :bordered="false" class="data-card">
            <a-alert type="error" show-icon message="当前账号尚未获得管理权限"
              description="请联系平台管理员，为你的租户角色授予 iam.organization.read、iam.organization.manage、iam.application.read 或 iam.application.manage 权限。" />
          </a-card>

          <template v-else-if="page === 'themes'">
            <!-- 主题页面由上方保持挂载的领域组件渲染，切换导航时保留未保存草稿。 -->
          </template>
          <template v-else-if="page === 'tenants'">
            <!-- 租户列表、创建与启停由独立领域组件负责。 -->
          </template>
          <template v-else-if="page === 'applications'">
            <!-- OAuth 应用登记、信任策略和一次性客户端密钥由独立领域组件负责。 -->
          </template>
          <template v-else-if="page === 'audit'">
            <!-- 只读审计查询和筛选由独立审计 feature 负责。 -->
          </template>
          <template v-else-if="page === 'invitations'">
            <!-- 邀请列表、创建、撤销和一次性链接由独立领域组件负责；接受邀请仍属于公开认证流程。 -->
          </template>
          <template v-else-if="page === 'roles'">
            <!-- 角色目录、通用权限变更预览和数据范围由独立授权领域组件负责。 -->
          </template>
          <template v-else-if="page === 'permissions'">
            <!-- 权限编码目录由独立权限目录 feature 管理。 -->
          </template>
          <template v-else-if="page === 'users' || page === 'organizations'">
            <!-- 用户和组织管理由独立领域 feature 管理。 -->
          </template>
          <template v-else-if="page === 'tenant_access'">
            <!-- 租户成员组织归属和角色数据范围由租户权限 feature 管理。 -->
          </template>
          <template v-else-if="page === 'groups'">
            <GroupManagement />
          </template>

          <template v-else-if="page === 'authorization_simulation'">
            <div class="page-heading"><div><p class="eyebrow">ACCESS POLICY PREVIEW</p><h1>授权模拟</h1><p class="subtitle">用当前生效的成员、角色和数据范围规则预演一次请求，不会修改授权配置。</p></div></div>
            <AuthorizationSimulator />
          </template>
          <template v-else-if="page === 'models' || page === 'model_usage'">
            <!-- 模型目录与用量界面由保持挂载的模型治理 feature 负责。 -->
          </template>

          <template v-else />
          <footer class="page-footer"><span>统一身份与权限管理平台</span><span>{{ page === 'authorization_simulation' ? '授权模拟只读，不会修改策略' : '管理变更由服务端鉴权并写入审计' }}</span></footer>
        </section>
      </main>
    </div>
  </a-config-provider>
</template>
