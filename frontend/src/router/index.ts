import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { getToken } from '@/api'
import { allCodes, getCachedCapabilities, hasAnyCode } from '@/api/capabilities'
import { NAV_ITEMS, PAGE_PATHS, TENANT_MERGED_PAGES, type PageKey } from './navigation'

// 路由只负责 URL ↔ PageKey 映射；具体 feature 仍由 App 壳按 visitedPages 懒挂载。
// 用 render 函数而非 template 字符串，避免触发 Vue 运行时模板编译告警。
const NullShell = { render: () => null }

// 绿场 §6.6 页面融合：租户专属旧键不再注册独立路由，仅保留旧深链重定向。
const activePageKeys = (Object.keys(PAGE_PATHS) as PageKey[]).filter(key => !(key in TENANT_MERGED_PAGES))

const adminRoutes: RouteRecordRaw[] = activePageKeys.map(key => ({
  path: PAGE_PATHS[key],
  name: key,
  component: NullShell,
  meta: { requiresCapability: true },
}))

function firstVisiblePath(): string {
  const capabilities = getCachedCapabilities()
  if (!capabilities) return PAGE_PATHS.overview
  const held = allCodes(capabilities)
  const fallback = NAV_ITEMS.find(item => hasAnyCode(held, item.requiredPermissions))
  return fallback ? PAGE_PATHS[fallback.key] : '/no-access'
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: () => firstVisiblePath() },
    {
      path: '/no-access',
      name: 'no_access',
      component: NullShell,
      meta: { requiresCapability: false },
    },
    ...adminRoutes,
    // 旧向导地址改到只读对接指南；向导本身仍留在归档目录。
    { path: '/project-integration', redirect: PAGE_PATHS.integration_guide },
    // 权限编码页已下线（menu.permissions 已删除）：旧深链重定向到平台角色页。
    { path: '/permissions', redirect: PAGE_PATHS.roles },
    // 旧深链重定向统一由 TENANT_MERGED_PAGES 注册（含已收口的应用角色 / 应用目录 /
    // 组织目录与租户专属页），此处不再重复注册同一路径。
    ...Object.entries(TENANT_MERGED_PAGES).map(([from, to]): RouteRecordRaw => ({
      path: PAGE_PATHS[from as PageKey],
      redirect: PAGE_PATHS[to as PageKey],
    })),
    { path: '/:pathMatch(.*)*', redirect: () => firstVisiblePath() },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

// 绿场守卫：已登录且能力缓存就绪时，深链无权限页 → 首个可见页；
// 无任何管理码（L4）→ /no-access；能力尚未加载（刷新首跳）时放行，由 App 纠正。
router.beforeEach(to => {
  if (!getToken()) return true
  // 个人信息页：自助数据，不依赖管理码，所有登录用户可达（含 L4 / no_access 场景）。
  if (to.name === 'profile') return true
  if (to.name === 'no_access') {
    // P2-8：能力就绪且存在可见页时不滞留 /no-access（URL/内容/侧栏高亮三态一致）；
    // 能力未加载（刷新首跳，由 App 纠正）或确无可见页（L4）才放行。
    if (!getCachedCapabilities()) return true
    const fallback = firstVisiblePath()
    return fallback === '/no-access' ? true : fallback
  }
  const capabilities = getCachedCapabilities()
  if (!capabilities) return true
  const held = allCodes(capabilities)
  const hasVisible = NAV_ITEMS.some(item => hasAnyCode(held, item.requiredPermissions))
  if (!hasVisible) return '/no-access'
  const permitted = NAV_ITEMS.some(item => item.key === to.name && hasAnyCode(held, item.requiredPermissions))
  if (permitted) return true
  return firstVisiblePath()
})
