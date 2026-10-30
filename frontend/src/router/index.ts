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
    // Wave 1：「新项目接入」已从导航下线，旧深链重定向到应用工作台。
    { path: '/project-integration', redirect: PAGE_PATHS.application_workspace },
    // 应用角色与成员、应用目录、组织目录已收口到工作台；保留字面路径以免旧书签 404。
    { path: '/application-roles', redirect: PAGE_PATHS.application_workspace },
    { path: '/applications', redirect: PAGE_PATHS.application_workspace },
    { path: '/organizations', redirect: PAGE_PATHS.organization_workspace },
    // 租户专属旧深链重定向到融合后的统一页面。
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
  if (to.name === 'no_access') return true
  const capabilities = getCachedCapabilities()
  if (!capabilities) return true
  const held = allCodes(capabilities)
  const hasVisible = NAV_ITEMS.some(item => hasAnyCode(held, item.requiredPermissions))
  if (!hasVisible) return '/no-access'
  const permitted = NAV_ITEMS.some(item => item.key === to.name && hasAnyCode(held, item.requiredPermissions))
  if (permitted) return true
  return firstVisiblePath()
})
