<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { NavigationItem, PageKey } from '../navigation'
import { PAGE_PATHS } from '../navigation'

const props = withDefaults(defineProps<{
  healthState: string
  items: NavigationItem[]
  modeLabel: string
  collapsed?: boolean
}>(), {
  // 未传入时保持展开，避免把窄屏选择器或未保存偏好当成折叠。
  collapsed: false,
})

const emit = defineEmits<{
  toggleSidebar: []
}>()

const route = useRoute()
const router = useRouter()

// 当前高亮项与 vue-router 的 name（PageKey）对齐。
const activePage = computed(() => {
  const name = route.name
  return typeof name === 'string' ? name as PageKey : props.items[0]?.key || 'overview'
})

const mobileNavOptions = computed(() => props.items.map(item => ({ value: item.key, label: item.label })))

const brandTarget = computed(() => PAGE_PATHS[props.items[0]?.key || 'overview'])

function navigateTo(value: string | number): void {
  // Select 的值来自用户输入，先校验导航白名单，再走路由切换。
  const item = props.items.find(candidate => candidate.key === value)
  if (item) void router.push(PAGE_PATHS[item.key])
}

function toggleSidebar(): void {
  // 折叠状态由外壳写入当前浏览器；这里只发出切换，不访问后端。
  emit('toggleSidebar')
}

function isActive(key: PageKey): boolean {
  return activePage.value === key
}
</script>

<template>
  <aside class="sidebar">
    <router-link class="brand" :to="brandTarget"><span class="brand-mark">ID</span><span class="brand-copy"><strong>统一身份平台</strong><small>IDENTITY CONTROL</small></span></router-link>
    <button type="button" class="sidebar-toggle" :aria-expanded="!props.collapsed" :aria-label="props.collapsed ? '展开侧栏' : '折叠侧栏'" @click="toggleSidebar">{{ props.collapsed ? '»' : '«' }}</button>
    <div class="nav-caption">{{ props.modeLabel }}</div>
    <nav :aria-label="`${props.modeLabel}导航`">
      <router-link
        v-for="item in props.items"
        :key="item.key"
        :to="PAGE_PATHS[item.key]"
        class="nav-item"
        :class="{ active: isActive(item.key) }"
        :title="props.collapsed ? item.label : undefined"
        :aria-label="props.collapsed ? item.label : undefined"
        :aria-current="isActive(item.key) ? 'page' : undefined"
      >
        <span class="nav-icon">{{ item.icon }}</span><span class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>
    <a-select class="mobile-nav-select" :value="activePage" :options="mobileNavOptions" aria-label="选择管理页面" @change="navigateTo" />
    <div class="sidebar-footer" role="status" aria-live="polite" :title="props.collapsed ? `${props.healthState} · IAM` : undefined"><span class="status-dot" :class="{ offline: props.healthState !== '服务正常' }"></span><span class="sidebar-footer-text">{{ props.healthState }} · IAM</span></div>
  </aside>
</template>
