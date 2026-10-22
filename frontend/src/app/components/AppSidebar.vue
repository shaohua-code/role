<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { NavigationItem, PageKey } from '../navigation'
import { PAGE_PATHS } from '../navigation'
import { MenuFoldOutlined, MenuUnfoldOutlined } from '../icons'

const props = withDefaults(defineProps<{
  healthState: string
  items: NavigationItem[]
  modeLabel: string
  collapsed?: boolean
  isMobile?: boolean
}>(), {
  // 未传入时保持展开，避免把窄屏抽屉或未保存偏好当成折叠。
  collapsed: false,
  isMobile: false,
})

const emit = defineEmits<{
  toggleSidebar: []
}>()

// 窄屏抽屉开关由外壳控制，侧栏只负责渲染同一套菜单。
const mobileOpen = defineModel<boolean>('mobileOpen', { default: false })

const route = useRoute()
const router = useRouter()

// 当前高亮项与 vue-router 的 name（PageKey）对齐。
const activePage = computed(() => {
  const name = route.name
  return typeof name === 'string' ? name as PageKey : props.items[0]?.key || 'overview'
})

const brandTarget = computed(() => PAGE_PATHS[props.items[0]?.key || 'overview'])

const selectedKeys = computed(() => [activePage.value])

function navigateTo(key: string): void {
  const item = props.items.find(candidate => candidate.key === key)
  if (!item) return
  void router.push(PAGE_PATHS[item.key])
  // 窄屏点选后收起抽屉，避免挡住内容区。
  if (props.isMobile) mobileOpen.value = false
}

function toggleSidebar(): void {
  emit('toggleSidebar')
}

function onMenuClick(info: { key: string | number }): void {
  navigateTo(String(info.key))
}
</script>

<template>
  <a-drawer
    v-if="props.isMobile"
    v-model:open="mobileOpen"
    placement="left"
    :width="244"
    :body-style="{ padding: '0' }"
    :title="props.modeLabel"
  >
    <a-menu mode="inline" :selected-keys="selectedKeys" @click="onMenuClick">
      <a-menu-item v-for="item in props.items" :key="item.key">
        <template #icon>
          <component :is="item.icon" />
        </template>
        <span>{{ item.label }}</span>
      </a-menu-item>
    </a-menu>
  </a-drawer>
  <a-layout-sider
    v-else
    :collapsed="props.collapsed"
    :width="244"
    :collapsed-width="76"
    :trigger="null"
    collapsible
    theme="light"
    class="h-screen max-h-screen shrink-0 overflow-hidden"
  >
    <div class="flex h-full min-h-0 flex-col overflow-hidden">
      <div class="flex items-center justify-between gap-2 px-3 pt-4 pb-2">
        <router-link :to="brandTarget" class="flex min-w-0 items-center gap-2 text-inherit no-underline">
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-600 text-xs font-semibold text-white">ID</span>
          <span v-if="!props.collapsed" class="min-w-0">
            <strong class="block truncate text-sm">统一身份平台</strong>
            <small class="block text-[10px] tracking-wider text-slate-400 uppercase">Identity Control</small>
          </span>
        </router-link>
      </div>
      <div class="flex justify-end px-3 pb-2">
        <a-button
          type="text"
          :aria-expanded="!props.collapsed"
          :aria-label="props.collapsed ? '展开侧栏' : '折叠侧栏'"
          @click="toggleSidebar"
        >
          <MenuUnfoldOutlined v-if="props.collapsed" />
          <MenuFoldOutlined v-else />
        </a-button>
      </div>
      <p v-if="!props.collapsed" class="shrink-0 px-5 pb-2 text-[11px] tracking-wider text-slate-400 uppercase">{{ props.modeLabel }}</p>
      <!-- 菜单项过多时只在侧栏内部滚动，不带动整页。 -->
      <div class="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
        <a-menu mode="inline" :inline-collapsed="props.collapsed" :selected-keys="selectedKeys" @click="onMenuClick">
          <a-menu-item v-for="item in props.items" :key="item.key">
            <template #icon>
              <component :is="item.icon" />
            </template>
            <span>{{ item.label }}</span>
          </a-menu-item>
        </a-menu>
      </div>
      <div class="mt-auto shrink-0 px-4 py-3" role="status" aria-live="polite">
        <a-badge :status="props.healthState === '服务正常' ? 'success' : 'warning'" :text="props.collapsed ? undefined : `${props.healthState} · IAM`" />
      </div>
    </div>
  </a-layout-sider>
</template>
