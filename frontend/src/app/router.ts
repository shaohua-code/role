import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { PAGE_PATHS, type PageKey } from './navigation'

// 路由只负责 URL 与 PageKey 映射；具体 feature 仍由 App 壳按 visitedPages 懒挂载。
const NullShell = { template: '<div />' }

const adminRoutes: RouteRecordRaw[] = (Object.entries(PAGE_PATHS) as [PageKey, string][]).map(([key, path]) => ({
  path,
  name: key,
  component: NullShell,
}))

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/overview' },
    ...adminRoutes,
    { path: '/:pathMatch(.*)*', redirect: '/overview' },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})
