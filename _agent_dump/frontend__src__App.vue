<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, theme as antTheme } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { LockOutlined, MenuOutlined, SettingOutlined } from '@/plugins/icons'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminColorField from '@/components/AdminColorField.vue'
import ChangePasswordModal from '@/components/ChangePasswordModal.vue'
import { api, getToken, setToken, type AdminOverview } from '@/api'
import { getReadiness, ReadinessError } from '@/api/health'
import { allCodes, clearCapabilities, deriveConsoleMode, hasAnyCode, loadCapabilities, setCachedCapabilities, type Capabilities, type ConsoleMode } from '@/api/capabilities'
import { ensureManagementUi } from '@/plugins/antd'
import { applyBrandToDocument, buildManagementAntdTheme, readCssVar } from '@/styles/antd-bridge'
import FeatureLoading from '@/components/FeatureLoading.vue'
import AppSidebar from '@/layout/AppSidebar.vue'
import AppBreadcrumb from '@/layout/AppBreadcrumb.vue'
import AuthEntry from '@/views/auth/AuthEntry.vue'
import { NAV_ITEMS, PAGE_INFO as pageInfo, PAGE_PATHS, type PageKey } from '@/router/navigation'
import {
  ApplicationManagement,
  ApplicationWorkspace,
  ApplicationRoleManagement,
  AuditLogPage,
  AuthorizationSimulator,
  GroupManagement,
  InvitationManagement,
  LoginThemeManagement,
  ModelGovernancePage,
  OrganizationManagement,
  OrganizationWorkspace,
  OverviewPage,
  PermissionCatalog,
  RoleManagement,
  TenantAccessManagement,
  TenantManagement,
  UserManagement,
} from '@/router/loaders'

type Row = Record<string, unknown>
type TenantMembership = { tenant_id: string; tenant_name: string; tenant_kind: 'organization' | 'consumer'; membership_status: string; tenant_status: string }
const route = useRoute()
const router = useRouter()
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
// 绿场改造：consoleMode 由 /auth/me/capabilities 决定（L1→platform；L2/L3→tenant；L4→no_access）。
const capabilities = ref<Capabilities | null>(null)
const consoleMode = ref<ConsoleMode>('no_access')
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
// 平台壳字典透传租户 slug（slug=platform 为系统保留租户），供创建类下拉排除平台引导租户。
const platformTenantOptions = computed(() => tenants.value.map(tenant => ({
  id: String(tenant.id),
  name: String(tenant.name),
  slug: typeof tenant.slug === 'string' ? tenant.slug : undefined,
})))
// 跨租户并集的管理码集合；菜单按 requiredPermissions(any-of) 裁剪，不再硬编码 key 判断。
const heldCodes = computed(() => capabilities.value ? allCodes(capabilities.value) : new Set<string>())
// 绿场统一导航（11 号文档 §6.3）：平台与租户模式共用 NAV_ITEMS + 能力过滤。
// Wave 1 对齐 user-centent：「应用与权限」组以应用工作台为主入口。
// 高级管理改造：应用/角色/权限三个列表页归入侧栏「高级管理」折叠组（低频全局能力），
// 不再区分平台/租户模式做侧栏排除，能力满足即展示（租户侧 /roles 仍是「应用角色与成员」融合页入口）。
const visibleNavigation = computed(() => consoleMode.value === 'no_access'
  ? []
  : NAV_ITEMS.filter(item => hasAnyCode(heldCodes.value, item.requiredPermissions)))
// 侧栏未展示（能力不满足）的页面不可直接访问；能力满足即可达（侧栏 + 深链共用同一能力守卫）。
function isPageReachable(key: PageKey): boolean {
  const item = NAV_ITEMS.find(candidate => candidate.key === key)
  return Boolean(item && hasAnyCode(heldCodes.value, item.requiredPermissions))
}
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
// UI 检查（P347）修复：data-theme 同步到 html——tokens.css 暗色变量块（html[data-theme=dark]）
// 与 antd-bridge 的 readCssVar 都读 documentElement 层；只挂在 a-layout 上时暗色变量从不生效，
// darkAlgorithm 派生的暗色被显式浅色 token 覆盖。a-layout 上的同名属性保留供 style.css 选择器使用。
watch(themeMode, (mode) => {
  document.documentElement.setAttribute('data-theme', mode)
}, { immediate: true })
// 默认主色：石墨黑（P350 黑白灰轻奢改造）；历史默认紫 #5B5BD6 视为未设置，避免老浏览器存值把全站拉回紫色。
const DEFAULT_PRIMARY = '#18181B'
function readPrimaryColor(): string {
  const stored = localStorage.getItem('iam-primary-color') || ''
  if (/^#[\da-f]{6}$/i.test(stored) && stored.toUpperCase() !== '#5B5BD6') return stored
  return DEFAULT_PRIMARY
}
const primaryColor = ref(readPrimaryColor())
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
    applyBrandToDocument(hex)
    onThemePreferenceChange()
  }
}
// 顶栏用户徽标：取显示名或邮箱首字符，配合极光渐变头像。
const userInitial = computed(() => (currentUser.value?.display_name || currentUser.value?.email || '').trim().slice(0, 1).toUpperCase())
// 玻璃拟态顶栏：浅色为半透明白玻璃，深色用高不透明度深夜蓝保证对比度（避免半透明在深色下发灰）。
const headerSurfaceStyle = computed(() => (
  themeMode.value === 'dark'
    ? { color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }
    : { color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }
))
// 品牌展示色：暗色内容区里深色主色不可见（黑上黑）——按亮度判断而非精确匹配默认值，
// 兼容用户浏览器里存过的历史自定义深色（如实测存在的 #121112）；深色主色统一回落到
// tokens.css dark 块的 --color-brand（近白），亮色自定义（品牌红/蓝等）尊重用户选择。
function isDarkHexColor(hex: string): boolean {
  const match = /^#([\da-f]{6})$/i.exec(hex)
  if (!match) return false
  const value = Number.parseInt(match[1], 16)
  const r = (value >> 16) & 255
  const g = (value >> 8) & 255
  const b = value & 255
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 80
}
const displayPrimary = computed(() => {
  if (themeMode.value !== 'dark') return primaryColor.value
  if (isDarkHexColor(primaryColor.value)) return readCssVar('--color-brand', '#fafafa')
  return primaryColor.value
})
const antdTheme = computed(() => {
  const isDark = themeMode.value === 'dark'
  const bridged = buildManagementAntdTheme({
    primary: displayPrimary.value,
    isDark,
    controlHeight: density.value === 'compact' ? 32 : 36,
  })
  return {
    algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
    token: bridged.token,
    components: bridged.components,
  }
})
let systemThemeQuery: MediaQueryList | null = null
function onSystemThemeChange(event: MediaQueryListEvent): void {
  systemPrefersDark.value = event.matches
}
// 以所在卡片 body 为基准计算（骨架 flex 已把卡片拉伸到贴底，页脚不占卡片内空间）：
// maxHeight 消除内容区双滚动条；minHeight 与其同值让少数据/空态的面板也撑满卡片，
// 空态 placeholder 单元格吃到面板高度实现垂直居中（td 默认 vertical-align:middle）。
function fitTableBodies(): void {
  const content = document.querySelector('.ant-layout-content')
  if (!content) return
  const contentRect = content.getBoundingClientRect()
  const bodies = Array.from(document.querySelectorAll<HTMLElement>('.ant-table-body'))
  if (!bodies.length) return
  // 极矮视口保底从 120 降为 72：高 <600 的窗口下 120 会使内容区出现 ~31px 外层滚动（UI 检查 P348）。
  const minBodyHeight = 72
  for (const body of bodies) {
    const wrapper = body.closest('.ant-table-wrapper')
    if (!wrapper) continue
    // 弹窗内表格不参与页面高度分配。
    if (wrapper.closest('.ant-modal')) continue
    // 记录上一轮 fit：操作反馈（按钮 loading spinner 挂载/数据重渲染/分页瞬时测量）会让本轮
    // fit 与上轮差出几个像素，若每次都落笔新值，表格区域高度反复跳变——即表格操作时的页面抖动。
    const previousFit = parseFloat(body.style.maxHeight) || 0
    // 先清空上一轮高度约束再测量：minHeight 会把卡片撑高，不清会形成正反馈循环（卡片越量越高）。
    body.style.minHeight = ''
    body.style.maxHeight = ''
    const cardBody = wrapper.closest<HTMLElement>('.ant-card-body')
    const pagination = wrapper.querySelector('.ant-pagination')
    const reserve = (pagination?.getBoundingClientRect().height ?? 0) + 8
    let fit: number
    if (cardBody) {
      const topInCard = body.getBoundingClientRect().top - cardBody.getBoundingClientRect().top
      fit = Math.round(Math.max(minBodyHeight, cardBody.clientHeight - topInCard - reserve))
    } else {
      // 兜底：非卡片内表格退回内容区基准（老口径，预留分页与页脚）。
      const legacyReserve = (pagination?.getBoundingClientRect().height ?? 56) + 112
      const topInContent = body.getBoundingClientRect().top - contentRect.top + content.scrollTop
      fit = Math.round(Math.max(minBodyHeight, content.clientHeight - topInContent - legacyReserve))
    }
    // 噪声阈值：与上一轮差值 ≤4px（取整误差/瞬时 DOM 状态）视为同一布局，沿用旧高度不重写；
    // 真实布局变化（分页器显隐、筛选区增删等 ≥ 数十像素）仍正常跟随。
    if (previousFit > 0 && Math.abs(fit - previousFit) <= 4) fit = previousFit
    body.style.maxHeight = `${fit}px`
    body.style.minHeight = `${fit}px`
    // 空态垂直居中；td 的 padding 会叠加在 height 之外，以 body 实际可滚高度校正一次防溢出。
    const placeholderCell = wrapper.querySelector<HTMLElement>('.ant-table-placeholder .ant-table-cell')
    if (placeholderCell) {
      const headerHeight = wrapper.querySelector('.ant-table-thead')?.getBoundingClientRect().height ?? 0
      placeholderCell.style.height = `${Math.max(minBodyHeight, fit - Math.round(headerHeight) - 2)}px`
      const excess = body.scrollHeight - fit
      if (excess > 0) {
        placeholderCell.style.height = `${Math.max(minBodyHeight, fit - Math.round(headerHeight) - 2 - excess)}px`
      }
    }
  }
  // 收敛轮：估算偏差导致内容区仍溢出时，均摊扣除并再次保底。
  const overflow = content.scrollHeight - content.clientHeight
  if (overflow > 0) {
    const adjustable = bodies.filter(body => !body.closest('.ant-modal'))
    if (!adjustable.length) return
    const deduct = Math.ceil(overflow / adjustable.length)
    for (const body of adjustable) {
      const next = Math.max(minBodyHeight, Math.round(parseFloat(body.style.maxHeight) || minBodyHeight) - deduct)
      body.style.maxHeight = `${next}px`
      body.style.minHeight = `${next}px`
    }
  }
}
function onWindowResizeFit(): void {
  fitTableBodies()
}
// 内容区是固定高度弹性容器，表格插入不改变其自身尺寸，ResizeObserver 不会触发；
// 改用子树 MutationObserver 捕捉表格挂载/翻页/数据刷新，防抖后重新校准。
function scheduleTableFit(): void {
  if (tableFitTimer !== undefined) window.clearTimeout(tableFitTimer)
  tableFitTimer = window.setTimeout(fitTableBodies, 80)
}
// 内容区元素随登录态/布局挂载而出现；确保观察器挂在最新 content 上并立即校准一次。
function refreshTableFit(): void {
  nextTick(() => {
    const content = document.querySelector('.ant-layout-content')
    if (!content) return
    tableFitObserver?.disconnect()
    tableFitObserver = new MutationObserver(scheduleTableFit)
    tableFitObserver.observe(content, { childList: true, subtree: true })
    scheduleTableFit()
  })
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

// ---- 表格纵向高度自适应 ----
// scroll.y 的固定 calc 无法覆盖各页面表格上方内容的差异（如审计页大筛选区），
// 会导致内容区与表格同时出现两条纵向滚动条。表格 body 的 max-height 由上方
// fitTableBodies 以内容区底边为基准动态计算，这里只保留观察器声明。
let tableFitObserver: MutationObserver | null = null
let tableFitTimer: number | undefined

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

function tenantRowFromCapabilities(capability: Capabilities['tenants'][number], name: string, kind: string, status: string): Row {
  // 能力响应已按租户归组管理码；这里换算成租户控制台历史 can_* 布尔，子页面续用。
  const codes = new Set<string>(capability.codes)
  for (const application of capability.applications) {
    for (const code of application.codes) codes.add(code)
  }
  const canReadOrganizations = codes.has('org.read') || codes.has('org.manage')
  const canReadApplications = codes.has('app.read') || codes.has('app.manage')
    || capability.applications.length > 0
  return {
    id: capability.tenant_id,
    name,
    kind,
    status,
    can_read_organizations: canReadOrganizations,
    can_manage_organizations: codes.has('org.manage'),
    can_read_applications: canReadApplications,
    can_manage_applications: codes.has('app.manage'),
    can_rotate_application_secret: codes.has('app.secret.rotate'),
  }
}

async function loadTenantNameLookups(userId: string, tenantIds: string[]): Promise<Map<string, { name: string; kind: string; status: string }>> {
  // 能力响应只含 tenant_id；用本人 membership 接口补齐展示名（失败时退化为占位名）。
  const lookups = new Map<string, { name: string; kind: string; status: string }>()
  try {
    const memberships = await api<TenantMembership[]>(`/tenant-admin/users/${encodeURIComponent(userId)}/memberships`).catch(() => null)
    if (memberships) {
      for (const membership of memberships) {
        lookups.set(membership.tenant_id, {
          name: membership.tenant_name, kind: membership.tenant_kind, status: membership.tenant_status,
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
    return tenantRowFromCapabilities(capability, lookup?.name || capability.tenant_id, lookup?.kind || 'organization', lookup?.status || 'active')
  })
  // 租户模式的应用字典：主题页按应用管理登录主题；仅在持有应用码时拉取首租户列表。
  const firstTenantId = capabilityTenants[0]?.tenant_id
  if (firstTenantId && heldCodes.value.has('app.read')) {
    applications.value = await api<Row[]>(`/tenant-admin/applications?tenant_id=${encodeURIComponent(firstTenantId)}`).catch(() => [])
    if (applications.value.length && !themeAppId.value) themeAppId.value = String(applications.value[0].id)
  }
  // 租户模式的角色字典：邀请页预绑角色按 organization.read 从租户角色目录读取。
  if (firstTenantId && heldCodes.value.has('org.read')) {
    roleOptions.value = await api<Row[]>(`/tenant-admin/roles?tenant_id=${encodeURIComponent(firstTenantId)}`).catch(() => [])
  }
  const firstPage = visibleNavigation.value[0]?.key || 'organizations'
  visitedPages.value = new Set<PageKey>([firstPage])
  await router.replace(PAGE_PATHS[firstPage])
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

// G02 自助改密：入口在顶栏用户区；成功后走 signOut 清理本地会话（服务端已撤销全部会话）。
const changePasswordOpen = ref(false)

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
function onThemePreferenceChange(): void {
  localStorage.setItem('iam-theme', themePreference.value); localStorage.setItem('iam-primary-color', primaryColor.value); localStorage.setItem('iam-density', density.value)
}

onMounted(async () => {
  applyBrandToDocument(primaryColor.value)
  systemThemeQuery = window.matchMedia('(prefers-color-scheme: dark)')
  systemPrefersDark.value = systemThemeQuery.matches
  systemThemeQuery.addEventListener('change', onSystemThemeChange)
  mobileQuery = window.matchMedia(MOBILE_MEDIA_QUERY)
  isMobile.value = mobileQuery.matches
  mobileQuery.addEventListener('change', onMobileViewportChange)
  // 视口尺寸变化时重新校准表格内建滚动高度。
  window.addEventListener('resize', onWindowResizeFit)
  // api.ts 已清除本标签页 token 并广播其他标签页；此处只更新 Vue 状态，避免收到远端事件后再次广播。
  window.addEventListener('iam:unauthorized', () => { token.value = null; currentUser.value = null; capabilities.value = null; clearCapabilities(); consoleMode.value = 'no_access' })
  // 状态探测与认证会话恢复并行，探针慢或失败不阻塞后台登录。
  document.addEventListener('visibilitychange', onReadinessVisibilityChange)
  void refreshReadiness().then(() => {
    scheduleReadinessPoll(healthState.value === '服务正常' ? READINESS_POLL_OK_MS : READINESS_POLL_DEGRADED_MS)
  })
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
  systemThemeQuery?.removeEventListener('change', onSystemThemeChange)
  mobileQuery?.removeEventListener('change', onMobileViewportChange)
  document.removeEventListener('visibilitychange', onReadinessVisibilityChange)
  window.removeEventListener('resize', onWindowResizeFit)
  tableFitObserver?.disconnect()
  tableFitObserver = null
  if (tableFitTimer !== undefined) window.clearTimeout(tableFitTimer)
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
              :page-title="pageInfo[page].title"
            />
          </div>
          <!-- UI 检查 P349：去掉 wrap——375 视口下换行会叠加溢出固定高 header；外观按钮移动端图标化省宽。 -->
          <a-space :size="8" class="shrink-0">
            <a-popover trigger="click" placement="bottomRight">
              <template #content>
                <div class="grid min-w-48 gap-2">
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
              <a-button aria-label="外观设置">
                <SettingOutlined v-if="isMobile" />
                <span v-else>外观</span>
              </a-button>
            </a-popover>
            <a-avatar
              v-if="userInitial"
              :size="30"
              class="shrink-0 text-xs font-semibold"
              :style="{ background: 'var(--color-brand)', color: 'var(--color-bg-elevated)' }"
            >{{ userInitial }}</a-avatar>
            <span class="hidden max-w-40 truncate text-sm sm:inline">{{ currentUser?.display_name || currentUser?.email || '平台管理员' }}</span>
            <!-- G02：自助修改密码入口——移动端只留锁形图标（同 P349 isMobile 条件渲染惯例，避免 375 顶栏溢出）。 -->
            <a-button type="link" aria-label="修改密码" @click="changePasswordOpen = true">
              <LockOutlined v-if="isMobile" />
              <span v-else>修改密码</span>
            </a-button>
            <a-button type="link" @click="signOut">退出</a-button>
          </a-space>
        </a-layout-header>

        <a-layout-content class="mgmt-shell-content mx-auto w-full min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
          <router-view aria-hidden="true" class="hidden" />
          <a-card v-if="consoleMode === 'no_access'" :bordered="false">
            <a-alert type="error" show-icon message="当前账号尚未获得管理权限"
              description="请联系管理员为你的角色授予相应的 iam.* 管理权限；应用成员请通过业务应用入口登录。" />
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
          <!-- Wave 1 应用工作台：左树选应用 + 角色/权限编码 Tab，替代新项目接入成为主入口。 -->
          <div v-if="visitedPages.has('application_workspace')" v-show="page === 'application_workspace'">
            <ApplicationWorkspace
              :active="page === 'application_workspace'"
              :console-mode="consoleMode === 'tenant' ? 'tenant' : 'platform'"
              :api-prefix="consoleMode === 'tenant' ? '/tenant-admin' : '/admin'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), can_read_applications: tenant.can_read_applications === true, can_manage_applications: tenant.can_manage_applications === true }))"
              :shell-applications="consoleMode === 'platform' ? applications : null"
              :shell-catalog-generation="platformCatalogGeneration"
              @changed="consoleMode === 'platform' ? loadDictionaries(true) : undefined"
            />
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
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), slug: typeof tenant.slug === 'string' ? tenant.slug : undefined }))"
              :roles="roleOptions.map(role => ({ id: String(role.id), tenant_id: String(role.tenant_id), name: String(role.name), status: String(role.status) }))"
            />
          </div>
          <div v-if="visitedPages.has('roles')" v-show="page === 'roles'">
            <!-- 绿场 §6.6 角色管理拆标签：租户模式挂本应用角色与成员管理；平台模式挂全局角色管理。 -->
            <ApplicationRoleManagement
              v-if="consoleMode === 'tenant'"
              :active="page === 'roles'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), can_read_applications: tenant.can_read_applications === true || tenant.can_manage_applications === true }))"
            />
            <RoleManagement
              v-else
              :active="page === 'roles'"
              :shell-catalog-generation="platformCatalogGeneration"
              :shell-roles="roleOptions"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status) }))"
              :applications="applications.map(application => ({ id: String(application.id), tenant_id: String(application.tenant_id), name: String(application.name), status: String(application.status), permission_namespace: String(application.permission_namespace ?? '') }))"
              @changed="() => loadDictionaries(true)"
            />
          </div>
          <div v-if="visitedPages.has('permissions')" v-show="page === 'permissions'">
            <PermissionCatalog :active="page === 'permissions'" />
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
              @changed="() => loadDictionaries(true)" />
          </div>
          <div v-if="visitedPages.has('organizations')" v-show="page === 'organizations'">
            <OrganizationManagement :active="page === 'organizations'"
              :api-prefix="consoleMode === 'tenant' ? '/tenant-admin' : '/admin'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), slug: typeof tenant.slug === 'string' ? tenant.slug : undefined, can_read_organizations: consoleMode === 'platform' || tenant.can_read_organizations === true, can_manage_organizations: consoleMode === 'platform' || tenant.can_manage_organizations === true }))" />
          </div>
          <!-- Wave 2 组织工作台：左组织树 + 成员/用户组 Tab；组织仍挂租户，用户组仅在组织上下文展示。 -->
          <div v-if="visitedPages.has('organization_workspace')" v-show="page === 'organization_workspace'">
            <OrganizationWorkspace
              :active="page === 'organization_workspace'"
              :api-prefix="consoleMode === 'tenant' ? '/tenant-admin' : '/admin'"
              :tenants="tenants.map(tenant => ({ id: String(tenant.id), name: String(tenant.name), status: String(tenant.status), can_read_organizations: consoleMode === 'platform' || tenant.can_read_organizations === true }))"
            />
          </div>
          <div v-if="visitedPages.has('groups')" v-show="page === 'groups'">
            <GroupManagement
              :active="page === 'groups'"
              :api-prefix="consoleMode === 'tenant' ? '/tenant-admin' : '/admin'"
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
          <footer class="app-footer mt-auto flex min-w-0 max-w-full flex-col justify-between gap-2 border-t pt-3 text-xs sm:flex-row">
            <span class="min-w-0 shrink-0">统一身份与权限管理平台</span>
            <span class="min-w-0 break-words sm:text-right">{{ page === 'authorization_simulation' ? '授权模拟只读，不会修改策略' : '管理变更由服务端鉴权并写入审计' }}</span>
          </footer>
          </template>
        </a-layout-content>
        <!-- G02 自助改密弹窗：挂在登录态布局内；changed 后强制退出（服务端已撤销全部会话）。 -->
        <ChangePasswordModal v-model:open="changePasswordOpen" @changed="signOut" />
      </a-layout>
    </a-layout>
  </a-config-provider>
</template>
