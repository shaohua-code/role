<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { LockOutlined, MenuOutlined, SettingOutlined, DownOutlined, IdcardOutlined, LogoutOutlined } from '@/plugins/icons'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminColorField from '@/components/AdminColorField.vue'
import ChangePasswordModal from '@/components/ChangePasswordModal.vue'
import { api, getToken, setToken, type AdminOverview } from '@/api'
import { allCodes, clearCapabilities, deriveConsoleMode, hasAnyCode, loadCapabilities, setCachedCapabilities, TENANT_ADMIN_API_PREFIX, type Capabilities, type ConsoleMode } from '@/api/capabilities'
import { ensureManagementUi } from '@/plugins/antd'
import FeatureLoading from '@/components/FeatureLoading.vue'
import AppSidebar from '@/layout/AppSidebar.vue'
import AppBreadcrumb from '@/layout/AppBreadcrumb.vue'
import AuthEntry from '@/views/auth/AuthEntry.vue'
import { NAV_ITEMS, PAGE_INFO as pageInfo, PAGE_PATHS, type PageKey } from '@/router/navigation'
import { asPagedList } from '@/utils/paged'
import {
  ApplicationWorkspace,
  AuditLogPage,
  AuthorizationSimulator,
  GroupManagement,
  IntegrationGuidePage,
  InvitationManagement,
  LoginThemeManagement,
  ModelGovernancePage,
  OrganizationWorkspace,
  OverviewPage,
  ProfilePage,
  RoleManagement,
  TenantAccessManagement,
  TenantManagement,
  UserManagement,
} from '@/router/loaders'
import { useReadinessPoll } from '@/composables/useReadinessPoll'
import { useTableFit } from '@/composables/useTableFit'
import { useShellAppearance } from '@/composables/useShellAppearance'
import { PAGE_COMPONENTS } from '@/layout/page-registry'

type Row = Record<string, unknown>
// tenant_slug 由 memberships 契约下发（slug=platform 为平台保留租户）；未下发时保持 undefined 兜底
type TenantMembership = { tenant_id: string; tenant_name: string; tenant_kind: 'organization' | 'consumer'; membership_status: string; tenant_status: string; tenant_slug?: string }
const route = useRoute()
const router = useRouter()

const {
  healthState,
  readinessRefreshing,
  refreshReadiness,
  startReadinessPolling,
  disposeReadinessPolling,
} = useReadinessPoll()

const { refreshTableFit, bindTableFitListeners, disposeTableFit } = useTableFit()

const {
  themePreference,
  themeMode,
  primaryColor,
  density,
  componentSize,
  isMobile,
  mobileNavOpen,
  sidebarCollapsed,
  headerSurfaceStyle,
  displayPrimary,
  antdTheme,
  toggleSidebar,
  applyPrimaryColor,
  onThemePreferenceChange,
  bindAppearanceListeners,
  disposeAppearanceListeners,
} = useShellAppearance()

// U9 外观面板受控开关：antd Popover 默认无键盘关闭路径（走查实测 Esc 无效），
// 受控后内容区与触发键都能 Esc 收起；顶栏按钮同步改 type=text（原描边 chip 在深色顶栏上常亮突兀）。
const appearanceOpen = ref(false)

const pageComponents = PAGE_COMPONENTS
// 保留目录引用，避免拆壳后组件清单被误删；模板仍按页传不同 props。
void pageComponents
// 当前页由 URL 决定，便于刷新与深链；非法路由会在 visibleNavigation 变化时被纠正。
const page = computed(() => {
  const name = route.name
  if (name === 'no_access') return 'overview'
  if (typeof name === 'string' && name in pageInfo) return name as PageKey
  return 'overview'
})
// 未访问页面不创建 DOM；访问过的页面在导航切换后保留，避免丢失草稿和筛选状态。
const visitedPages = ref(new Set<PageKey>())
const currentUser = ref<{ id?: string; email?: string; display_name?: string } | null>(null)
// 顶栏头像首字母：优先展示名，其次邮箱首字符；无登录用户时隐藏头像。
const userInitial = computed(() => (currentUser.value?.display_name || currentUser.value?.email || '').trim().charAt(0).toUpperCase() || null)
// 绿场改造：consoleMode 由 /auth/me/capabilities 决定（L1→platform；L2/L3→tenant；L4→no_access）。
const capabilities = ref<Capabilities | null>(null)
const consoleMode = ref<ConsoleMode>('no_access')
const loading = ref(false)
const overview = ref<AdminOverview | null>(null)
const dictionariesLoading = ref(false)
const dictionariesNeedRetry = ref(false)
// 平台壳字典只预拉一次；子页复用 generation 感知刷新，避免路由切换重复打 tenants/applications/roles。
const dictionariesReady = ref(false)
const platformCatalogGeneration = ref(0)

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
// 平台壳字典透传租户 slug（slug=platform 为系统保留租户），供创建类下拉排除平台引导租户。
const platformTenantOptions = computed(() => tenants.value.map(tenant => ({
  id: String(tenant.id),
  name: String(tenant.name),
  slug: typeof tenant.slug === 'string' ? tenant.slug : undefined,
})))
// 跨租户并集的管理码集合；侧栏只认对应 menu.*。
const heldCodes = computed(() => capabilities.value ? allCodes(capabilities.value) : new Set<string>())
// 绿场统一导航（11 号文档 §6.3）：平台与租户模式共用 NAV_ITEMS + 能力过滤。
// Wave 1 对齐 user-centent：「应用与权限」组以应用工作台为主入口。
// 高级管理只留平台角色 / 权限编码 / 用户组；应用与组织目录已收口到工作台。
const visibleNavigation = computed(() => {
  if (consoleMode.value === 'no_access') return []
  return NAV_ITEMS.filter(item => hasAnyCode(heldCodes.value, item.requiredPermissions))
})
// 侧栏未展示（能力不满足）的页面不可直接访问；能力满足即可达（侧栏 + 深链共用同一能力守卫）。
// 个人信息页不占侧栏、不判管理码，登录即可达（守卫与下拉入口共用该口径）。
function isPageReachable(key: PageKey): boolean {
  if (key === 'profile') return true
  const item = NAV_ITEMS.find(candidate => candidate.key === key)
  return Boolean(item && hasAnyCode(heldCodes.value, item.requiredPermissions))
}
let pageRequestSequence = 0

// 以所在卡片 body 为基准计算（骨架 flex 已把卡片拉伸到贴底，页脚不占卡片内空间）：
// maxHeight 消除内容区双滚动条；minHeight 与其同值让少数据/空态的面板也撑满卡片，
// 空态 placeholder 单元格吃到面板高度实现垂直居中（td 默认 vertical-align:middle）。
async function loadPage(force = false): Promise<void> {
  // P1-6：租户模式同样加载运营总览（后端已按操作者范围过滤计数），不再永远显示占位符。
  if (!token.value || (consoleMode.value !== 'platform' && consoleMode.value !== 'tenant') || page.value !== 'overview') return
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

// ---- 表格纵向高度自适应 ----
// scroll.y 的固定 calc 无法覆盖各页面表格上方内容的差异（如审计页大筛选区），
// 会导致内容区与表格同时出现两条纵向滚动条。表格 body 的 max-height 由上方
// fitTableBodies 以内容区底边为基准动态计算，这里只保留观察器声明。

async function loadDictionaries(force = false): Promise<void> {
  if (consoleMode.value !== 'platform' || dictionariesLoading.value) return
  if (dictionariesReady.value && !force) return
  dictionariesLoading.value = true
  try {
    const [tenantRows, applicationRows, roles] = await Promise.all([
      api<Row[]>('/admin/tenants'), api<Row[]>('/admin/applications'), api<Row[] | { items: Row[] }>('/admin/roles?limit=500'),
    ])
    tenants.value = tenantRows
    applications.value = applicationRows
    roleOptions.value = asPagedList(roles).items
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

function tenantRowFromCapabilities(capability: Capabilities['tenants'][number], name: string, kind: string, status: string, slug?: string): Row {
  // 能力响应已按租户归组管理码（menu.*/button.* 节点码）；这里换算成租户控制台历史 can_* 布尔，子页面续用。
  const tenantCodes = new Set<string>(capability.codes)
  const codes = new Set<string>(capability.codes)
  for (const application of capability.applications) {
    for (const code of application.codes) codes.add(code)
  }
  const canReadOrganizations = codes.has('menu.organization_workspace')
  const canReadApplications = codes.has('menu.application_workspace')
    || capability.applications.length > 0
  return {
    id: capability.tenant_id,
    name,
    kind,
    status,
    // 透传租户 slug（平台保留租户 slug=platform），供下游排除逻辑使用；缺失时为 undefined
    slug,
    can_read_organizations: canReadOrganizations,
    can_manage_organizations: codes.has('button.org.manage'),
    can_read_applications: canReadApplications,
    can_manage_applications: codes.has('button.apps.manage'),
    // P404：新建/删除应用只看租户域节点（L3），不要把 L2 应用级 button.apps.manage 并进来。
    can_create_applications: tenantCodes.has('button.apps.manage'),
    can_rotate_application_secret: codes.has('button.apps.secret'),
  }
}

async function loadTenantNameLookups(userId: string, tenantIds: string[]): Promise<Map<string, { name: string; kind: string; status: string; slug?: string }>> {
  // 能力响应只含 tenant_id；用本人 membership 接口补齐展示名（失败时退化为占位名）。
  const lookups = new Map<string, { name: string; kind: string; status: string; slug?: string }>()
  try {
    const memberships = await api<TenantMembership[]>(`${TENANT_ADMIN_API_PREFIX}/users/${encodeURIComponent(userId)}/memberships`).catch(() => null)
    if (memberships) {
      for (const membership of memberships) {
        lookups.set(membership.tenant_id, {
          name: membership.tenant_name, kind: membership.tenant_kind, status: membership.tenant_status,
          // 契约下发 tenant_slug 才透传，用于平台保留租户（slug=platform）排除
          slug: typeof membership.tenant_slug === 'string' ? membership.tenant_slug : undefined,
        })
      }
    }
  } catch { /* 展示名缺失不阻塞控制台；使用占位名。 */ }
  for (const tenantId of tenantIds) {
    if (!lookups.has(tenantId)) lookups.set(tenantId, { name: `租户 ${tenantId.slice(0, 8)}`, kind: 'organization', status: 'active' })
  }
  return lookups
}

async function initializeConsole(user: { id?: string; capabilities?: Capabilities | null }): Promise<void> {
  // 绿场规则：优先用 /auth/me 一次带回的 capabilities（含 roles）；否则回退 /auth/me/capabilities。
  try {
    const result = user.capabilities ?? await loadCapabilities()
    capabilities.value = result
    setCachedCapabilities(result)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '无法读取管理能力')
    consoleMode.value = 'no_access'
    await router.replace('/no-access')
    return
  }

  const mode = deriveConsoleMode(capabilities.value)
  if (mode === 'platform') {
    consoleMode.value = 'platform'
    // 登录后保留浏览器当前 path（若属于平台菜单），支持刷新与深链。
    // Wave 4：用可达性口径而非侧栏口径，侧栏降级页（应用/角色/权限列表）深链刷新不被弹回。
    const entryPage = isPageReachable(page.value) ? page.value : 'overview'
    visitedPages.value = new Set<PageKey>([entryPage])
    if (page.value !== entryPage) await router.replace(PAGE_PATHS[entryPage])
    void loadDictionaries()
    void loadPage()
    return
  }

  if (mode === 'no_access') {
    consoleMode.value = 'no_access'
    await router.replace('/no-access')
    return
  }

  const capabilityTenants = capabilities.value.tenants
  if (!capabilityTenants.length) {
    consoleMode.value = 'no_access'
    await router.replace('/no-access')
    return
  }
  consoleMode.value = 'tenant'
  const lookups = await loadTenantNameLookups(user.id || '', capabilityTenants.map(item => item.tenant_id))
  tenants.value = capabilityTenants.map(capability => {
    const lookup = lookups.get(capability.tenant_id)
    return tenantRowFromCapabilities(capability, lookup?.name || capability.tenant_id, lookup?.kind || 'organization', lookup?.status || 'active', lookup?.slug)
  })
  // 租户模式的应用字典：主题页按应用管理登录主题；P2-6 改为按全部可读租户并发拉取合并，
  // 多租户管理员在登录主题页能看到并管理所有租户的应用品牌（原先只拉首租户）。
  const firstTenantId = capabilityTenants[0]?.tenant_id
  if (capabilityTenants.length && heldCodes.value.has('menu.application_workspace')) {
    const tenantAppLists = await Promise.all(capabilityTenants.map(tenant =>
      api<Row[]>(`${TENANT_ADMIN_API_PREFIX}/applications?tenant_id=${encodeURIComponent(tenant.tenant_id)}`).catch(() => [] as Row[]),
    ))
    applications.value = tenantAppLists.flat()
    if (applications.value.length && !themeAppId.value) themeAppId.value = String(applications.value[0].id)
  }
  // 租户模式的角色字典：平台角色全局化后候选=全局平台角色+本租户应用角色，
  // 统一走 /admin/roles（不再按租户过滤平台角色）；按组织工作台菜单节点拉取。
  if (firstTenantId && heldCodes.value.has('menu.organization_workspace')) {
    // P1-5：/admin/roles 已分页化返回 {items}，兼容数组与分页对象两种形态解析，
    // 解析失败不再中断 initializeConsole（曾导致租户模式登录后首屏空白）。
    const rolesResult = await api<Row[] | { items?: Row[] }>('/admin/roles?limit=500').catch(() => [] as Row[])
    const roleRows = Array.isArray(rolesResult) ? rolesResult : rolesResult.items ?? []
    roleOptions.value = roleRows.filter(role => {
      // 未钉应用的是平台角色（全局一份，直接保留）；应用角色仅保留宿主在当前租户的
      if (!role.application_id) return true
      return String(role.tenant_id ?? '') === String(firstTenantId)
    })
  }
  // 深链保持与平台分支同口径：刷新落在可达页（含 profile 这类非侧栏页）则原地保留，只回退不可达页。
  const firstPage = isPageReachable(page.value) ? page.value : (visibleNavigation.value[0]?.key || 'organization_workspace')
  visitedPages.value = new Set<PageKey>([firstPage])
  if (page.value !== firstPage) await router.replace(PAGE_PATHS[firstPage])
  // P1-6 收尾：登录页路由即首页时同路由 replace 不触发路由 watch，需与平台分支对等显式加载总览。
  void loadPage()
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

// G02 自助改密：入口在顶栏用户下拉；成功后走 signOut 清理本地会话（服务端已撤销全部会话）。
const changePasswordOpen = ref(false)

// 个人信息入口：顶栏用户下拉受控开关（同外观面板口径，保证 Esc / 失焦可靠收起）。
const userMenuOpen = ref(false)

// Esc 全局收起：antd Dropdown 无原生键盘关闭路径，且焦点可能落在触发钮、面板项或页面任意处，
// 统一在 window 捕获，避免依赖具体焦点位置（走查实测仅绑触发钮时 CDP/真实按键均有漏路径）。
function onShellKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && userMenuOpen.value) userMenuOpen.value = false
}

// 下拉内导航：先收起面板再执行动作，避免动作后面板残留。
function openProfile(): void {
  userMenuOpen.value = false
  void router.push(PAGE_PATHS.profile)
}

function openChangePassword(): void {
  userMenuOpen.value = false
  changePasswordOpen.value = true
}

// 个人信息页保存展示名后同步壳层缓存（顶栏芯片与下拉身份卡头实时更新）
function onProfileUpdated(displayName: string): void {
  if (currentUser.value) currentUser.value.display_name = displayName
}

async function signOutFromMenu(): Promise<void> {
  userMenuOpen.value = false
  await signOut()
}

async function signOut(): Promise<void> {
  try { await api('/auth/logout', { method: 'POST' }) } catch { /* 令牌过期时本地仍须可退出。 */ }
  setToken(null); token.value = null; currentUser.value = null
  consoleMode.value = 'no_access'; tenants.value = []; applications.value = []; roleOptions.value = []
  capabilities.value = null
  clearCapabilities()
  setCachedCapabilities(null)
  dictionariesReady.value = false
  platformCatalogGeneration.value = 0
  overview.value = null
}

function setPage(next: PageKey): void {
  // Wave 4：侧栏隐藏页（应用/角色/权限列表）按能力仍可经工作台高级入口进入。
  if (!isPageReachable(next)) return
  void router.push(PAGE_PATHS[next])
  if (dictionariesNeedRetry.value) void loadDictionaries(true)
}

// 路由变化时维护 visitedPages、概览刷新与导航纠正。
function syncRoutePage(next: PageKey, previous?: PageKey): void {
  if (!token.value || sessionBootstrapping.value) return
  if (consoleMode.value !== 'no_access' && !isPageReachable(next)) {
    const fallback = visibleNavigation.value[0]?.key || 'overview'
    void router.replace(PAGE_PATHS[fallback])
    return
  }
  visitedPages.value.add(next)
  // 仅进入工作台时刷新概览，避免每次路由切换都打 /admin/overview。
  if (next === 'overview') void loadPage()
  if (previous && previous !== next) window.scrollTo({ top: 0, behavior: 'smooth' })
  // 页面切换后表格 DOM 重建，重新校准表格内建滚动高度。
  refreshTableFit()
}

watch(page, (next, previous) => { syncRoutePage(next, previous) }, { immediate: true })
watch(sessionBootstrapping, (booting) => {
  if (!booting) syncRoutePage(page.value)
  // 布局首次挂载或恢复时，重建表格高度观察器。
  if (!booting) refreshTableFit()
})

watch(visibleNavigation, () => {
  if (!token.value || sessionBootstrapping.value || consoleMode.value === 'no_access') return
  // 能力被撤销后当前页不可达则回退；侧栏降级页（能力仍在）不触发回退。
  if (!isPageReachable(page.value)) {
    const fallback = visibleNavigation.value[0]?.key || 'overview'
    void router.replace(PAGE_PATHS[fallback])
  }
})
// 登录成功（token 从无到有）时布局首次渲染，同样需要挂观察器并校准。
watch(token, (value) => { if (value) refreshTableFit() })
onMounted(async () => {
  bindAppearanceListeners()
  bindTableFitListeners()
  // 用户下拉 Esc 收起监听（同外观面板键盘可达口径）。
  window.addEventListener('keydown', onShellKeydown)
  // api.ts 已清除本标签页 token 并广播其他标签页；此处只更新 Vue 状态，避免收到远端事件后再次广播。
  window.addEventListener('iam:unauthorized', () => { token.value = null; currentUser.value = null; capabilities.value = null; clearCapabilities(); consoleMode.value = 'no_access' })
  // 状态探测与认证会话恢复并行，探针慢或失败不阻塞后台登录。
  startReadinessPolling()
  if (token.value) {
    sessionBootstrapping.value = true
    try {
      const user = await Promise.all([
        api<{ id?: string; email?: string; display_name?: string; capabilities?: Capabilities; roles?: unknown }>('/auth/me'),
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
  disposeAppearanceListeners()
  disposeTableFit()
  disposeReadinessPolling()
  window.removeEventListener('keydown', onShellKeydown)
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
    <!-- 视口内滚动：侧栏不随页面上下滚，只有右侧内容区滚。data-theme 供全局 CSS 跟随应用内主题切换。 -->
    <a-layout v-else class="h-screen w-full overflow-hidden" :data-theme="themeMode">
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
          class="mgmt-shell-header z-10 flex h-14 shrink-0 items-center justify-between gap-3 border-b px-4 leading-none"
          :style="headerSurfaceStyle"
        >
          <div class="flex min-w-0 items-center gap-3">
            <a-button v-if="isMobile" type="text" aria-label="打开导航" @click="mobileNavOpen = true">
              <MenuOutlined />
            </a-button>
            <!-- 顶栏面包屑组件：渐变模式徽章 + 页面标题 -->
            <AppBreadcrumb
              :mode-label="consoleMode === 'tenant' ? '租户工作台' : consoleMode === 'platform' ? '平台' : '访问受限'"
              :page-title="pageInfo[page]?.title ?? ''"
            />
          </div>
          <!-- UI 检查 P349：去掉 wrap——375 视口下换行会叠加溢出固定高 header；外观按钮移动端图标化省宽。 -->
          <a-space :size="8" class="shrink-0">
            <a-popover v-model:open="appearanceOpen" trigger="click" placement="bottomRight">
              <template #content>
                <div class="grid min-w-48 gap-2" @keydown.esc="appearanceOpen = false">
                  <span class="text-xs text-[var(--color-text-secondary)]">界面主题</span>
                  <a-radio-group v-model:value="themePreference" button-style="solid" @change="onThemePreferenceChange">
                    <a-radio-button value="light">浅色</a-radio-button>
                    <a-radio-button value="dark">深色</a-radio-button>
                    <a-radio-button value="system">跟随系统</a-radio-button>
                  </a-radio-group>
                  <span class="text-xs text-[var(--color-text-secondary)]">界面密度</span>
                  <a-radio-group v-model:value="density" button-style="solid" @change="onThemePreferenceChange">
                    <a-radio-button value="comfortable">舒适</a-radio-button>
                    <a-radio-button value="compact">紧凑</a-radio-button>
                  </a-radio-group>
                  <span class="text-xs text-[var(--color-text-secondary)]">品牌主色</span>
                  <AdminColorField :model-value="primaryColor" @update:model-value="applyPrimaryColor" />
                  <small class="text-xs text-[var(--color-text-muted)]">外观偏好保存在当前会话浏览器</small>
                </div>
              </template>
              <!-- 375 视口收敛宽度：移动端只留齿轮图标，桌面保留「外观」文字。
                   用 isMobile 条件渲染而非 hidden 类——antd 未分层的 .ant-btn > span{display:inline-block}
                   会压过 Tailwind @layer utilities 的 .hidden（P349 浏览器复验实测）。 -->
              <a-button aria-label="外观设置" type="text" @keydown.esc="appearanceOpen = false">
                <SettingOutlined v-if="isMobile" />
                <span v-else>外观</span>
              </a-button>
            </a-popover>
            <!-- 顶栏用户菜单：收敛原平铺用户区（头像+名字+改密+退出），提供个人信息单入口。
                 受控 open（同外观面板口径）保证 Esc / 点外可靠收起；窄屏只留头像图标防 375 溢出（P349 惯例）。 -->
            <a-dropdown v-model:open="userMenuOpen" trigger="click" placement="bottomRight">
              <button
                type="button"
                aria-label="用户菜单"
                class="flex max-w-44 shrink-0 cursor-pointer items-center gap-2 rounded-md px-1.5 py-1 transition-colors hover:bg-[var(--color-brand-subtle)] focus:bg-[var(--color-brand-subtle)] focus:outline-none"
                @keydown.esc="userMenuOpen = false"
              >
                <a-avatar
                  v-if="userInitial"
                  :size="28"
                  class="shrink-0 text-xs font-semibold"
                  :style="{ background: 'var(--color-brand)', color: 'var(--color-bg-elevated)' }"
                >{{ userInitial }}</a-avatar>
                <span class="hidden min-w-0 max-w-32 truncate text-sm sm:inline">{{ currentUser?.display_name || currentUser?.email || '平台管理员' }}</span>
                <DownOutlined class="hidden text-[10px] text-[var(--color-text-muted)] sm:inline" />
              </button>
              <template #overlay>
                <div
                  class="w-72 overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-lg)]"
                  @keydown.esc="userMenuOpen = false"
                >
                  <!-- 身份卡头：头像 + 展示名 + 邮箱，超长截断 -->
                  <div class="flex items-center gap-3 px-4 py-3">
                    <a-avatar
                      v-if="userInitial"
                      :size="40"
                      class="shrink-0 text-sm font-semibold"
                      :style="{ background: 'var(--color-brand)', color: 'var(--color-bg-elevated)' }"
                    >{{ userInitial }}</a-avatar>
                    <div class="min-w-0 flex-1">
                      <p class="m-0 truncate text-sm font-medium text-[var(--color-text-primary)]">{{ currentUser?.display_name || '平台管理员' }}</p>
                      <p class="m-0 truncate text-xs text-[var(--color-text-muted)]">{{ currentUser?.email || '未绑定邮箱' }}</p>
                    </div>
                  </div>
                  <div class="border-t border-[var(--color-border)]" />
                  <div class="flex flex-col p-1.5">
                    <button
                      type="button"
                      class="flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-bg-subtle)]"
                      @click="openProfile"
                    >
                      <IdcardOutlined class="shrink-0 text-sm text-[var(--color-text-secondary)]" />
                      个人信息
                    </button>
                    <button
                      type="button"
                      class="flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm text-[var(--color-text-primary)] transition-colors hover:bg-[var(--color-bg-subtle)]"
                      @click="openChangePassword"
                    >
                      <LockOutlined class="shrink-0 text-sm text-[var(--color-text-secondary)]" />
                      修改密码
                    </button>
                  </div>
                  <div class="border-t border-[var(--color-border)]" />
                  <!-- 退出登录：悬停转危险色（语义色为全站唯一高饱和点缀口径） -->
                  <div class="p-1.5">
                    <button
                      type="button"
                      class="flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-error)]"
                      @click="signOutFromMenu"
                    >
                      <LogoutOutlined class="shrink-0 text-sm" />
                      退出登录
                    </button>
                  </div>
                </div>
              </template>
            </a-dropdown>
          </a-space>
        </a-layout-header>

        <a-layout-content class="mgmt-shell-content mx-auto w-full min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
          <router-view aria-hidden="true" class="hidden" />
          <!-- 个人信息页：登录即可达（不占侧栏，入口在顶栏用户菜单）；置于 no_access 分支之外，L4 也能查看本人信息。 -->
          <div v-if="visitedPages.has('profile')" v-show="page === 'profile'">
            <ProfilePage
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name) }))"
              @open-change-password="openChangePassword"
              @profile-updated="onProfileUpdated"
            />
          </div>
          <a-card v-if="consoleMode === 'no_access' && page !== 'profile'" :bordered="false">
            <a-alert type="error" show-icon message="当前账号尚未获得管理权限"
              description="请联系管理员为你的角色授予管理台权限（五域管理码）；应用成员请通过业务应用入口登录。" />
          </a-card>
          <template v-else>
          <div v-if="visitedPages.has('overview')" v-show="page === 'overview'">
            <OverviewPage
              :overview="overview"
              :health-state="healthState"
              :loading="loading"
              :primary-color="displayPrimary"
              @navigate="setPage"
              @refresh="() => loadPage(true)"
            />
          </div>
          <!-- 应用工作台：左树选应用 + 角色/权限编码/资源树 Tab；新建与设置都走节点更多。 -->
          <div v-if="visitedPages.has('application_workspace')" v-show="page === 'application_workspace'">
            <ApplicationWorkspace
              :active="page === 'application_workspace'"
              :console-mode="consoleMode === 'tenant' ? 'tenant' : 'platform'"
              :api-prefix="consoleMode === 'tenant' ? TENANT_ADMIN_API_PREFIX : '/admin'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), kind: tenant.kind === 'consumer' ? 'consumer' : 'organization', can_read_applications: tenant.can_read_applications === true, can_manage_applications: tenant.can_manage_applications === true, can_create_applications: consoleMode === 'platform' || tenant.can_create_applications === true, can_rotate_application_secret: tenant.can_rotate_application_secret === true }))"
              :shell-applications="consoleMode === 'platform' ? applications : null"
              :shell-catalog-generation="platformCatalogGeneration"
              @changed="consoleMode === 'platform' ? loadDictionaries(true) : undefined"
            />
          </div>
          <div v-if="visitedPages.has('integration_guide')" v-show="page === 'integration_guide'">
            <IntegrationGuidePage />
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
            <ModelGovernancePage :active="page === 'models' || page === 'model_usage'" :view="page === 'models' ? 'catalog' : 'usage'"
              :seed-tenants="consoleMode === 'tenant' ? tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) })) : []" />
          </div>
          <div v-if="visitedPages.has('tenants')" v-show="page === 'tenants'">
            <TenantManagement
              :active="page === 'tenants'"
              :shell-catalog-generation="platformCatalogGeneration"
              :shell-tenants="consoleMode === 'platform' ? tenants : null"
              @changed="() => loadDictionaries(true)"
            />
          </div>
          <div v-if="visitedPages.has('audit')" v-show="page === 'audit'">
            <AuditLogPage :active="page === 'audit'" />
          </div>
          <div v-if="visitedPages.has('invitations')" v-show="page === 'invitations'">
            <!-- 平台角色全局化后 tenant_id 可能为空（全局角色），连同 application_id 一起透传供候选过滤 -->
            <InvitationManagement
              :active="page === 'invitations'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), slug: typeof tenant.slug === 'string' ? tenant.slug : undefined }))"
              :roles="roleOptions.map(role => ({ id: String(role.id), tenant_id: role.tenant_id ? String(role.tenant_id) : '', application_id: role.application_id ? String(role.application_id) : null, name: String(role.name), status: String(role.status) }))"
            />
          </div>
          <div v-if="visitedPages.has('roles')" v-show="page === 'roles'">
            <RoleManagement
              :active="page === 'roles'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) }))"
              :applications="applications.map(application => ({ id: String(application.id), tenant_id: String(application.tenant_id), name: String(application.name), status: String(application.status), permission_namespace: String(application.permission_namespace ?? '') }))"
              @changed="() => loadDictionaries(true)"
            />
          </div>
          <div v-if="visitedPages.has('users')" v-show="page === 'users'">
            <!-- 绿场 §6.6 用户管理融合：租户模式=租户成员与数据范围；平台模式=全局用户目录。 -->
            <TenantAccessManagement
              v-if="consoleMode === 'tenant'"
              :active="page === 'users'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), can_read_organizations: tenant.can_read_organizations === true, can_manage_organizations: tenant.can_manage_organizations === true }))"
            />
            <UserManagement
              v-else
              :active="page === 'users'"
              :current-user-id="String(currentUser?.id || '')"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) }))"
              :applications="applications.map(application => ({ id: String(application.id), name: String(application.name), tenant_id: String(application.tenant_id ?? '') }))"
              @changed="() => loadDictionaries(true)" />
          </div>
          <!-- 组织工作台：左组织树 + 成员/用户组 Tab；新建与设置都走节点更多。 -->
          <div v-if="visitedPages.has('organization_workspace')" v-show="page === 'organization_workspace'">
            <OrganizationWorkspace
              :active="page === 'organization_workspace'"
              :api-prefix="consoleMode === 'tenant' ? TENANT_ADMIN_API_PREFIX : '/admin'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), slug: typeof tenant.slug === 'string' ? tenant.slug : undefined, can_read_organizations: consoleMode === 'platform' || tenant.can_read_organizations === true, can_manage_organizations: consoleMode === 'platform' || tenant.can_manage_organizations === true }))"
            />
          </div>
          <div v-if="visitedPages.has('groups')" v-show="page === 'groups'">
            <GroupManagement
              :active="page === 'groups'"
              :api-prefix="consoleMode === 'tenant' ? TENANT_ADMIN_API_PREFIX : '/admin'"
              :tenants="consoleMode === 'platform' ? platformTenantOptions : tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), slug: typeof tenant.slug === 'string' ? tenant.slug : undefined }))"
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
              :seed-tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name) }))"
              :seed-applications="applications"
            />
          </div>
          </template>
        </a-layout-content>
        <!-- 滚动条修复：页脚从滚动流内移出，作为壳层固定底行——此前它把 main 内容顶出折叠线，
             让桌面端工作台恒现一条内部滚动条（形似页面滚动条）。内容区 flex-1 自动为其让位。 -->
        <footer class="app-footer shrink-0 border-t">
          <div class="mx-auto flex w-full max-w-[var(--content-max-width)] flex-col justify-between gap-2 px-[var(--content-padding-x)] py-2.5 text-xs sm:flex-row">
            <span class="min-w-0 shrink-0">统一身份与权限管理平台</span>
            <!-- U23：模拟器页脚免责特判移除——页面顶部「只读预演」alert 已有同义说明，页脚回归统一口径 -->
            <span class="min-w-0 break-words sm:text-right">管理变更由服务端鉴权并写入审计</span>
          </div>
        </footer>
        <!-- G02 自助改密弹窗：挂在登录态布局内；changed 后强制退出（服务端已撤销全部会话）。 -->
        <ChangePasswordModal v-model:open="changePasswordOpen" @changed="signOut" />
      </a-layout>
    </a-layout>
  </a-config-provider>
</template>
