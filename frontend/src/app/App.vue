<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, theme as antTheme } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { MenuOutlined } from './icons'
import AdminPageHeader from '../shared/components/AdminPageHeader.vue'
import AdminColorField from '../shared/components/AdminColorField.vue'
import { ApiRequestError, api, getToken, setToken, type AdminOverview } from '../shared/services/api'
import { getReadiness, ReadinessError } from '../shared/services/health'
import { ensureManagementUi } from './ui/antd'
import FeatureLoading from '../shared/components/FeatureLoading.vue'
import AppSidebar from './components/AppSidebar.vue'
import AuthEntry from './auth/AuthEntry.vue'
import { NAV_ITEMS, PAGE_INFO as pageInfo, PAGE_PATHS, TENANT_NAV_ITEMS, type PageKey } from './navigation'
import {
  ApplicationManagement,
  ApplicationRoleManagement,
  AuditLogPage,
  AuthorizationSimulator,
  GroupManagement,
  InvitationManagement,
  LoginThemeManagement,
  ModelGovernancePage,
  OrganizationManagement,
  OverviewPage,
  PermissionCatalog,
  RoleManagement,
  TenantAccessManagement,
  TenantManagement,
  UserManagement,
  ProjectIntegrationPage,
} from './featureLoaders'

type Row = Record<string, unknown>
type ConsoleMode = 'platform' | 'tenant' | 'no_access'
type TenantMembership = { tenant_id: string; tenant_name: string; tenant_kind: 'organization' | 'consumer'; membership_status: string; tenant_status: string }
const route = useRoute()
const router = useRouter()
// 当前页由 URL 决定，便于刷新与深链；非法路由会在 visibleNavigation 变化时被纠正。
const page = computed(() => {
  const name = route.name
  if (typeof name === 'string' && name in pageInfo) return name as PageKey
  return 'overview'
})
// 未访问页面不创建 DOM；访问过的页面在导航切换后保留，避免丢失草稿和筛选状态。
const visitedPages = ref(new Set<PageKey>())
const currentUser = ref<{ id?: string; email?: string; display_name?: string } | null>(null)
const consoleMode = ref<ConsoleMode>('platform')
const loading = ref(false)
const overview = ref<AdminOverview | null>(null)
const healthState = ref('检查中')
const readinessRefreshing = ref(false)
const dictionariesLoading = ref(false)
const dictionariesNeedRetry = ref(false)
// 平台壳字典只预拉一次；子页复用 generation 感知刷新，避免路由切换重复打 tenants/applications/roles。
const dictionariesReady = ref(false)
const platformCatalogGeneration = ref(0)
const READINESS_POLL_OK_MS = 120_000
const READINESS_POLL_DEGRADED_MS = 30_000
let readinessTimer: number | undefined
let readinessPollGeneration = 0
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

function stopReadinessPolling(): void {
  if (readinessTimer === undefined) return
  window.clearTimeout(readinessTimer)
  readinessTimer = undefined
}

function scheduleReadinessPoll(delayMs: number): void {
  stopReadinessPolling()
  const generation = ++readinessPollGeneration
  readinessTimer = window.setTimeout(async () => {
    if (generation !== readinessPollGeneration) return
    if (document.visibilityState === 'hidden') {
      scheduleReadinessPoll(delayMs)
      return
    }
    await refreshReadiness()
    const nextDelay = healthState.value === '服务正常' ? READINESS_POLL_OK_MS : READINESS_POLL_DEGRADED_MS
    scheduleReadinessPoll(nextDelay)
  }, delayMs)
}

function onReadinessVisibilityChange(): void {
  if (document.visibilityState !== 'visible') return
  void refreshReadiness()
  scheduleReadinessPoll(healthState.value === '服务正常' ? READINESS_POLL_OK_MS : READINESS_POLL_DEGRADED_MS)
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
// 恢复已有 token 时先展示加载态，等管理组件注册与会话探测并行完成后再渲染控制台表格。
const sessionBootstrapping = ref(Boolean(token.value))
const tenants = ref<Row[]>([])
const applications = ref<Row[]>([])
const roleOptions = ref<Row[]>([])
const themeAppId = ref('')
const platformTenantOptions = computed(() => tenants.value.map(tenant => ({
  id: String(tenant.id),
  name: String(tenant.name),
})))
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

type ThemePreference = 'light' | 'dark' | 'system'
function readThemePreference(): ThemePreference {
  const stored = localStorage.getItem('iam-theme')
  if (stored === 'dark' || stored === 'light' || stored === 'system') return stored
  return 'light'
}
const themePreference = ref<ThemePreference>(readThemePreference())
const systemPrefersDark = ref(window.matchMedia('(prefers-color-scheme: dark)').matches)
// 跟随系统时用操作系统配色，已保存的浅色/深色选择保持不变。
const themeMode = computed(() => themePreference.value === 'system' ? (systemPrefersDark.value ? 'dark' : 'light') : themePreference.value)
const primaryColor = ref(/^#[\da-f]{6}$/i.test(localStorage.getItem('iam-primary-color') || '') ? localStorage.getItem('iam-primary-color')! : '#756df2')
const density = ref(localStorage.getItem('iam-density') === 'compact' ? 'compact' : 'comfortable')
// 舒适=middle、紧凑=small，交给 ConfigProvider，不再用 data-density 补丁表格。
const componentSize = computed(() => density.value === 'compact' ? 'small' : 'middle')
const MOBILE_MEDIA_QUERY = '(max-width: 650px)'
const isMobile = ref(window.matchMedia(MOBILE_MEDIA_QUERY).matches)
const mobileNavOpen = ref(false)
let mobileQuery: MediaQueryList | null = null
function onMobileViewportChange(event: MediaQueryListEvent): void {
  isMobile.value = event.matches
  if (!event.matches) mobileNavOpen.value = false
}
// 桌面侧栏折叠只记在当前浏览器。缺省或无法识别的值保持展开，不改浅色/深色/跟随系统。
const sidebarCollapsed = ref(localStorage.getItem('iam-sidebar-collapsed') === 'collapsed')
function toggleSidebar(): void {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('iam-sidebar-collapsed', sidebarCollapsed.value ? 'collapsed' : 'expanded')
}
function applyPrimaryColor(hex: string): void {
  if (/^#[\da-f]{6}$/i.test(hex)) {
    primaryColor.value = hex
    onThemePreferenceChange()
  }
}
// 浅色顶栏/侧栏与内容区同一套皮。Header 默认仍是 #001529，token 盖不住时用内联色。
const headerSurfaceStyle = computed(() => (
  themeMode.value === 'dark'
    ? { backgroundColor: '#1e293b', color: '#e2e8f0' }
    : { backgroundColor: '#ffffff', color: '#202a3b' }
))
const antdTheme = computed(() => {
  const isDark = themeMode.value === 'dark'
  const primary = primaryColor.value
  return {
    algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
    token: {
      colorPrimary: primary,
      borderRadius: 10,
      colorBgLayout: isDark ? '#0f172a' : '#f4f6fa',
      colorBgContainer: isDark ? '#1e293b' : '#ffffff',
      fontFamily: 'Inter, "Noto Sans SC", system-ui, sans-serif',
    },
    components: {
      Layout: {
        headerBg: isDark ? '#1e293b' : '#ffffff',
        headerColor: isDark ? '#e2e8f0' : '#202a3b',
        siderBg: isDark ? '#1e293b' : '#ffffff',
        bodyBg: isDark ? '#0f172a' : '#f4f6fa',
      },
      Menu: {
        itemSelectedBg: isDark ? 'rgba(117, 109, 242, 0.18)' : '#f3f0ff',
        itemSelectedColor: primary,
        itemHoverBg: isDark ? 'rgba(117, 109, 242, 0.1)' : '#f5f3ff',
      },
      Card: {
        boxShadowTertiary: '0 1px 2px rgba(15, 23, 42, 0.06)',
      },
    },
  }
})
let systemThemeQuery: MediaQueryList | null = null
function onSystemThemeChange(event: MediaQueryListEvent): void {
  systemPrefersDark.value = event.matches
}
async function loadPage(force = false): Promise<void> {
  if (!token.value || consoleMode.value !== 'platform' || page.value !== 'overview') return
  // 登录初始化已写入 overview 时，路由同步不再重复请求。
  if (!force && overview.value) return
  const requestSequence = ++pageRequestSequence
  loading.value = true
  try {
    const result = await api<AdminOverview>('/admin/overview')
    if (requestSequence === pageRequestSequence && page.value === 'overview') overview.value = result
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取概览失败')
  } finally { if (requestSequence === pageRequestSequence) loading.value = false }
}

async function loadDictionaries(force = false): Promise<void> {
  if (consoleMode.value !== 'platform' || dictionariesLoading.value) return
  if (dictionariesReady.value && !force) return
  dictionariesLoading.value = true
  try {
    const [tenantRows, applicationRows, roles] = await Promise.all([
      api<Row[]>('/admin/tenants'), api<Row[]>('/admin/applications'), api<Row[]>('/admin/roles'),
    ])
    tenants.value = tenantRows
    applications.value = applicationRows
    roleOptions.value = roles
    dictionariesNeedRetry.value = false
    dictionariesReady.value = true
    platformCatalogGeneration.value += 1
    if (applications.value.length && !themeAppId.value) themeAppId.value = String(applications.value[0].id)
  } catch {
    // 初始化时字典读取失败会禁用创建入口；保留重试标记，后续导航时重新拉取。
    dictionariesNeedRetry.value = true
    dictionariesReady.value = false
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
      // 一次批量判定本租户的 5 个管理权限码，消除逐权限往返（P302 遗留 N+1）。
      const batch = await api<{ results: Record<string, { allowed?: boolean }> }>('/authorization/check-batch', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: membership.tenant_id,
          permission_codes: [
            'iam.organization.read',
            'iam.organization.manage',
            'iam.application.read',
            'iam.application.manage',
            'iam.application.secret.rotate',
          ],
        }),
      })
      // 管理权限也可读；只查 manage 会把只有 read 权限的租户管理员误判成无权访问。
      const allowed = (permissionCode: string): boolean => batch.results[permissionCode]?.allowed === true
      const scopedApplications = await api<Row[]>(`/tenant-admin/applications?tenant_id=${encodeURIComponent(membership.tenant_id)}`).catch(() => [])
      const organizationRead = allowed('iam.organization.read')
      const organizationManage = allowed('iam.organization.manage')
      const applicationRead = allowed('iam.application.read')
      const applicationManage = allowed('iam.application.manage')
      const secretRotate = allowed('iam.application.secret.rotate')
      const canReadOrganizations = organizationRead || organizationManage
      const canReadApplications = applicationRead || applicationManage || scopedApplications.length > 0
      if (!canReadOrganizations && !canReadApplications) return null
      return { id: membership.tenant_id, name: membership.tenant_name, kind: membership.tenant_kind, status: membership.tenant_status,
        can_read_organizations: canReadOrganizations,
        can_manage_organizations: organizationManage,
        can_read_applications: canReadApplications,
        can_manage_applications: applicationManage,
        can_rotate_application_secret: secretRotate
          || scopedApplications.some(application => application.can_rotate_secret === true) }
    } catch { return null }
  }))
  tenants.value = scopedTenants.filter((tenant): tenant is NonNullable<typeof tenant> => tenant !== null)
  consoleMode.value = tenants.value.length ? 'tenant' : 'no_access'
  const firstPage = visibleNavigation.value[0]?.key || 'organizations'
  visitedPages.value = new Set<PageKey>([firstPage])
  await router.replace(PAGE_PATHS[firstPage])
}

async function initializeConsole(user: { id?: string }): Promise<void> {
  try {
    // `/admin/overview` is server-protected and serves as the platform-admin capability check.
    overview.value = await api<AdminOverview>('/admin/overview')
    consoleMode.value = 'platform'
    // 登录后保留浏览器当前 path（若属于平台菜单），支持刷新与深链。
    const entryPage = NAV_ITEMS.some(item => item.key === page.value) ? page.value : 'overview'
    visitedPages.value = new Set<PageKey>([entryPage])
    if (page.value !== entryPage) await router.replace(PAGE_PATHS[entryPage])
    void loadDictionaries()
    return
  } catch (error) {
    if (!(error instanceof ApiRequestError) || error.status !== 403) {
      message.error(error instanceof Error ? error.message : '无法初始化管理台')
      consoleMode.value = 'no_access'
      await router.replace(PAGE_PATHS.organizations)
      return
    }
  }

  if (!user.id) {
    consoleMode.value = 'no_access'
    await router.replace(PAGE_PATHS.organizations)
    return
  }
  try { await loadTenantConsole(user.id) }
  catch {
    consoleMode.value = 'no_access'
    tenants.value = []
    await router.replace(PAGE_PATHS.organizations)
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
  dictionariesReady.value = false
  platformCatalogGeneration.value = 0
  overview.value = null
}

function setPage(next: PageKey): void {
  if (!visibleNavigation.value.some(item => item.key === next)) return
  void router.push(PAGE_PATHS[next])
  if (dictionariesNeedRetry.value) void loadDictionaries(true)
}

// 路由变化时维护 visitedPages、概览刷新与导航纠正。
function syncRoutePage(next: PageKey, previous?: PageKey): void {
  if (!token.value || sessionBootstrapping.value) return
  if (consoleMode.value !== 'no_access' && !visibleNavigation.value.some(item => item.key === next)) {
    const fallback = visibleNavigation.value[0]?.key || 'overview'
    void router.replace(PAGE_PATHS[fallback])
    return
  }
  visitedPages.value.add(next)
  // 仅进入工作台时刷新概览，避免每次路由切换都打 /admin/overview。
  if (next === 'overview') void loadPage()
  if (previous && previous !== next) window.scrollTo({ top: 0, behavior: 'smooth' })
}

watch(page, (next, previous) => { syncRoutePage(next, previous) }, { immediate: true })
watch(sessionBootstrapping, (booting) => {
  if (!booting) syncRoutePage(page.value)
})

watch(visibleNavigation, () => {
  if (!token.value || sessionBootstrapping.value || consoleMode.value === 'no_access') return
  if (!visibleNavigation.value.some(item => item.key === page.value)) {
    const fallback = visibleNavigation.value[0]?.key || 'overview'
    void router.replace(PAGE_PATHS[fallback])
  }
})
function onThemePreferenceChange(): void {
  localStorage.setItem('iam-theme', themePreference.value); localStorage.setItem('iam-primary-color', primaryColor.value); localStorage.setItem('iam-density', density.value)
}

onMounted(async () => {
  systemThemeQuery = window.matchMedia('(prefers-color-scheme: dark)')
  systemPrefersDark.value = systemThemeQuery.matches
  systemThemeQuery.addEventListener('change', onSystemThemeChange)
  mobileQuery = window.matchMedia(MOBILE_MEDIA_QUERY)
  isMobile.value = mobileQuery.matches
  mobileQuery.addEventListener('change', onMobileViewportChange)
  // api.ts 已清除本标签页 token 并广播其他标签页；此处只更新 Vue 状态，避免收到远端事件后再次广播。
  window.addEventListener('iam:unauthorized', () => { token.value = null; currentUser.value = null })
  // 状态探测与认证会话恢复并行，探针慢或失败不阻塞后台登录。
  document.addEventListener('visibilitychange', onReadinessVisibilityChange)
  void refreshReadiness().then(() => {
    scheduleReadinessPoll(healthState.value === '服务正常' ? READINESS_POLL_OK_MS : READINESS_POLL_DEGRADED_MS)
  })
  if (token.value) {
    sessionBootstrapping.value = true
    try {
      const user = await Promise.all([
        api<{ id?: string; email?: string; display_name?: string }>('/auth/me'),
        ensureManagementUi(),
      ]).then(([me]) => {
        currentUser.value = me
        return me
      })
      await initializeConsole(user)
    }
    catch { setToken(null); token.value = null }
    finally { sessionBootstrapping.value = false }
  }
})

onUnmounted(() => {
  systemThemeQuery?.removeEventListener('change', onSystemThemeChange)
  mobileQuery?.removeEventListener('change', onMobileViewportChange)
  document.removeEventListener('visibilitychange', onReadinessVisibilityChange)
  stopReadinessPolling()
})
</script>

<template>
  <a-config-provider :theme="antdTheme" :locale="zhCN" :component-size="componentSize">
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
    <a-layout v-else-if="sessionBootstrapping" class="min-h-screen">
      <a-layout-content class="flex min-h-screen items-center justify-center">
        <FeatureLoading />
      </a-layout-content>
    </a-layout>
    <!-- 视口内滚动：侧栏不随页面上下滚，只有右侧内容区滚。 -->
    <a-layout v-else class="h-screen w-full overflow-hidden">
      <AppSidebar
        v-model:mobile-open="mobileNavOpen"
        :health-state="healthState"
        :items="visibleNavigation"
        :mode-label="consoleMode === 'platform' ? '平台管理' : consoleMode === 'tenant' ? '租户管理' : '访问受限'"
        :collapsed="sidebarCollapsed"
        :is-mobile="isMobile"
        @toggle-sidebar="toggleSidebar"
      />
      <!-- 侧栏旁的内容列必须能收缩，否则宽表会把整页撑出横向滚动。 -->
      <a-layout class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden" :style="{ minWidth: '0' }">
        <a-layout-header
          class="z-10 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-slate-200 px-4 leading-none shadow-sm dark:border-slate-700"
          :style="headerSurfaceStyle"
        >
          <div class="flex min-w-0 items-center gap-3">
            <a-button v-if="isMobile" type="text" aria-label="打开导航" @click="mobileNavOpen = true">
              <MenuOutlined />
            </a-button>
            <a-breadcrumb>
              <a-breadcrumb-item>{{ consoleMode === 'tenant' ? '租户工作台' : consoleMode === 'platform' ? '平台' : '访问受限' }}</a-breadcrumb-item>
              <a-breadcrumb-item>{{ pageInfo[page].title }}</a-breadcrumb-item>
            </a-breadcrumb>
          </div>
          <a-space :size="8" wrap>
            <a-popover trigger="click" placement="bottomRight">
              <template #content>
                <div class="grid min-w-48 gap-2">
                  <span class="text-xs text-slate-500">界面主题</span>
                  <a-radio-group v-model:value="themePreference" button-style="solid" @change="onThemePreferenceChange">
                    <a-radio-button value="light">浅色</a-radio-button>
                    <a-radio-button value="dark">深色</a-radio-button>
                    <a-radio-button value="system">跟随系统</a-radio-button>
                  </a-radio-group>
                  <span class="text-xs text-slate-500">界面密度</span>
                  <a-radio-group v-model:value="density" button-style="solid" @change="onThemePreferenceChange">
                    <a-radio-button value="comfortable">舒适</a-radio-button>
                    <a-radio-button value="compact">紧凑</a-radio-button>
                  </a-radio-group>
                  <span class="text-xs text-slate-500">品牌主色</span>
                  <AdminColorField :model-value="primaryColor" @update:model-value="applyPrimaryColor" />
                  <small class="text-xs text-slate-400">外观偏好保存在当前会话浏览器</small>
                </div>
              </template>
              <a-button>外观</a-button>
            </a-popover>
            <span class="hidden max-w-40 truncate text-sm sm:inline">{{ currentUser?.display_name || currentUser?.email || '平台管理员' }}</span>
            <a-button type="link" @click="signOut">退出</a-button>
          </a-space>
        </a-layout-header>

        <a-layout-content class="mx-auto w-full min-h-0 min-w-0 max-w-[1500px] flex-1 overflow-x-hidden overflow-y-auto px-4 py-6 sm:px-6">
          <router-view aria-hidden="true" class="hidden" />
          <a-card v-if="consoleMode === 'no_access'" :bordered="false">
            <a-alert type="error" show-icon message="当前账号尚未获得管理权限"
              description="请联系平台管理员，为你的租户角色授予 iam.organization.read、iam.organization.manage、iam.application.read 或 iam.application.manage 权限。" />
          </a-card>
          <template v-else>
          <div v-if="visitedPages.has('overview')" v-show="page === 'overview'">
            <OverviewPage
              :overview="overview"
              :health-state="healthState"
              :loading="loading"
              :primary-color="primaryColor"
              @navigate="setPage"
              @refresh="() => loadPage(true)"
            />
          </div>
          <div v-if="visitedPages.has('project_integration')" v-show="page === 'project_integration'">
            <ProjectIntegrationPage :active="page === 'project_integration'" />
          </div>
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
            <TenantManagement
              :active="page === 'tenants'"
              :shell-catalog-generation="platformCatalogGeneration"
              :shell-tenants="consoleMode === 'platform' ? tenants : null"
              @changed="() => loadDictionaries(true)"
            />
          </div>
          <div v-if="visitedPages.has('applications')" v-show="page === 'applications'">
            <ApplicationManagement :active="page === 'applications'"
              :api-prefix="consoleMode === 'tenant' ? '/tenant-admin' : '/admin'"
              :shell-catalog-generation="platformCatalogGeneration"
              :shell-applications="consoleMode === 'platform' ? applications : null"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), can_read_applications: tenant.can_read_applications === true, can_manage_applications: tenant.can_manage_applications === true, can_rotate_application_secret: tenant.can_rotate_application_secret === true }))"
              @changed="consoleMode === 'platform' ? loadDictionaries(true) : undefined" />
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
              :shell-catalog-generation="platformCatalogGeneration"
              :shell-roles="consoleMode === 'platform' ? roleOptions : null"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) }))"
              :applications="applications.map(application => ({ id: String(application.id), tenant_id: String(application.tenant_id), name: String(application.name), status: String(application.status) }))"
              @changed="() => loadDictionaries(true)"
            />
          </div>
          <div v-if="visitedPages.has('permissions')" v-show="page === 'permissions'">
            <PermissionCatalog :active="page === 'permissions'" />
          </div>
          <div v-if="visitedPages.has('users')" v-show="page === 'users'">
            <UserManagement :active="page === 'users'"
              :current-user-id="String(currentUser?.id || '')"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) }))"
              @changed="() => loadDictionaries(true)" />
          </div>
          <div v-if="visitedPages.has('organizations')" v-show="page === 'organizations'">
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
          <div v-if="visitedPages.has('groups')" v-show="page === 'groups'">
            <GroupManagement
              :active="page === 'groups'"
              :tenants="consoleMode === 'platform' ? platformTenantOptions : []"
            />
          </div>
          <div v-if="visitedPages.has('authorization_simulation')" v-show="page === 'authorization_simulation'">
            <AdminPageHeader
              eyebrow="ACCESS POLICY PREVIEW"
              title="授权模拟"
              subtitle="用当前生效的成员、角色和数据范围规则预演一次请求，不会修改授权配置。"
            />
            <AuthorizationSimulator
              :active="page === 'authorization_simulation'"
              :seed-tenants="consoleMode === 'platform' ? tenants : []"
              :seed-applications="consoleMode === 'platform' ? applications : []"
            />
          </div>
          <footer class="mt-6 flex min-w-0 max-w-full flex-col justify-between gap-2 border-t border-slate-200 pt-3 text-xs text-slate-400 dark:border-slate-700 sm:flex-row">
            <span class="min-w-0 shrink-0">统一身份与权限管理平台</span>
            <span class="min-w-0 break-words sm:text-right">{{ page === 'authorization_simulation' ? '授权模拟只读，不会修改策略' : '管理变更由服务端鉴权并写入审计' }}</span>
          </footer>
          </template>
        </a-layout-content>
      </a-layout>
    </a-layout>
  </a-config-provider>
</template>
