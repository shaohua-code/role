<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { NavigationItem, PageKey } from '@/router/navigation'
import { PAGE_PATHS, buildNavGroups } from '@/router/navigation'
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@/plugins/icons'

const props = withDefaults(defineProps<{
  healthState: string
  items: NavigationItem[]
  modeLabel: string
  collapsed?: boolean
  isMobile?: boolean
}>(), {
  collapsed: false,
  isMobile: false,
})

const emit = defineEmits<{
  toggleSidebar: []
}>()

const mobileOpen = defineModel<boolean>('mobileOpen', { default: false })

const route = useRoute()
const router = useRouter()

const brandTitle = '\u7edf\u4e00\u8eab\u4efd\u5e73\u53f0'
const expandLabel = '\u5c55\u5f00\u5bfc\u822a'
const collapseLabel = '\u6298\u53e0\u5bfc\u822a'

const activePage = computed(() => {
  const name = route.name
  return typeof name === 'string' ? name as PageKey : props.items[0]?.key || 'overview'
})

const brandTarget = computed(() => PAGE_PATHS[props.items[0]?.key || 'overview'])
const selectedKeys = computed(() => [activePage.value])
const healthOk = computed(() => props.healthState.includes('\u6b63\u5e38') || props.healthState === 'ok')
const navGroups = computed(() => buildNavGroups(props.items))
const openKeys = ref<string[]>([])

// 高级管理 / 平台治理 / 审计验证属低频入口，默认折叠；日常组（身份/应用）保持展开。
// 当前路由所在组始终自动展开，保证深链/刷新后菜单可用。
const DEFAULT_COLLAPSED_GROUPS: ReadonlySet<string> = new Set(['advanced', 'platform', 'ops'])

function defaultOpenKeys(groups: Array<{ key: string; items: Array<{ key: PageKey }> }>): string[] {
  const activeGroup = groups.find(group => group.items.some(item => item.key === activePage.value))
  return groups
    .filter(group => group.key !== 'root'
      && (!DEFAULT_COLLAPSED_GROUPS.has(group.key) || group.key === activeGroup?.key))
    .map(group => 'group-' + group.key)
}

watch(
  navGroups,
  groups => {
    openKeys.value = defaultOpenKeys(groups)
  },
  { immediate: true },
)

// 菜单 openKeys 受控：切到折叠组内的页面（如平台治理）时补展开该组。
watch(activePage, () => {
  const owner = props.items.find(item => item.key === activePage.value)
  if (!owner || owner.group === 'root') return
  const groupKey = 'group-' + owner.group
  if (!openKeys.value.includes(groupKey)) {
    openKeys.value = [...openKeys.value, groupKey]
  }
})

function navigateTo(key: string): void {
  const item = props.items.find(candidate => candidate.key === key)
  if (!item) return
  void router.push(PAGE_PATHS[item.key])
  if (props.isMobile) mobileOpen.value = false
}

function toggleSidebar(): void {
  emit('toggleSidebar')
}

function onMenuClick(info: { key: string | number }): void {
  const key = String(info.key)
  if (key.startsWith('group-')) return
  navigateTo(key)
}

function onOpenChange(keys: (string | number)[]): void {
  openKeys.value = keys.map(String)
}

function groupMenuKey(groupKey: string): string {
  return 'group-' + groupKey
}
</script>

<template>
  <a-drawer
    v-if="props.isMobile"
    v-model:open="mobileOpen"
    placement="left"
    :width="240"
    :body-style="{ padding: '0', background: 'var(--color-sider-bg)' }"
    :title="props.modeLabel"
  >
    <a-menu
      mode="inline"
      theme="dark"
      :selected-keys="selectedKeys"
      :open-keys="openKeys"
      class="mgmt-sider-menu border-none bg-transparent"
      @click="onMenuClick"
      @openChange="onOpenChange"
    >
      <template v-for="group in navGroups" :key="group.key">
        <template v-if="group.key === 'root'">
          <a-menu-item v-for="item in group.items" :key="item.key">
            <template #icon>
              <component :is="item.icon" />
            </template>
            <span>{{ item.label }}</span>
          </a-menu-item>
        </template>
        <a-sub-menu v-else :key="groupMenuKey(group.key)">
          <template #title>
            <span>{{ group.label }}</span>
          </template>
          <a-menu-item v-for="item in group.items" :key="item.key">
            <template #icon>
              <component :is="item.icon" />
            </template>
            <span>{{ item.label }}</span>
          </a-menu-item>
        </a-sub-menu>
      </template>
    </a-menu>
  </a-drawer>
  <a-layout-sider
    v-else
    :collapsed="props.collapsed"
    :width="240"
    :collapsed-width="72"
    :trigger="null"
    collapsible
    class="mgmt-sider h-screen max-h-screen shrink-0 overflow-hidden !bg-[var(--color-sider-bg)]"
  >
    <div class="relative flex h-full min-h-0 flex-col overflow-hidden bg-[var(--color-sider-bg)]">
      <div class="relative flex items-center justify-between gap-2 px-3 pt-4 pb-2">
        <router-link :to="brandTarget" class="flex min-w-0 items-center gap-2 no-underline">
          <!-- 侧栏恒黑，logo 方块不能用品牌色（黑上黑/暗色翻转白后白上白）：白底黑字与侧栏底反差恒定 -->
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-sider-text-active)] text-xs font-semibold text-[var(--color-sider-bg)]">ID</span>
          <span v-if="!props.collapsed" class="min-w-0">
            <strong class="block truncate text-sm font-semibold text-[var(--color-sider-text-active)]">{{ brandTitle }}</strong>
            <small class="block text-[11px] tracking-[0.06em] text-[var(--color-sider-text)]">Identity Control</small>
          </span>
        </router-link>
      </div>
      <div class="relative flex justify-end px-3 pb-1">
        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-sider-text)] transition-colors duration-150 hover:bg-[var(--color-sider-item-hover)] hover:text-[var(--color-sider-text-active)]"
          :aria-expanded="!props.collapsed"
          :aria-label="props.collapsed ? expandLabel : collapseLabel"
          @click="toggleSidebar"
        >
          <MenuUnfoldOutlined v-if="props.collapsed" />
          <MenuFoldOutlined v-else />
        </button>
      </div>
      <p v-if="!props.collapsed" class="relative shrink-0 px-5 pb-2 text-[11px] font-medium tracking-[0.06em] text-[var(--color-sider-text)]">{{ props.modeLabel }}</p>
      <div class="relative min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-2">
        <a-menu
          mode="inline"
          theme="dark"
          :inline-collapsed="props.collapsed"
          :selected-keys="selectedKeys"
          :open-keys="props.collapsed ? [] : openKeys"
          class="mgmt-sider-menu border-none bg-transparent"
          @click="onMenuClick"
          @openChange="onOpenChange"
        >
          <template v-for="group in navGroups" :key="group.key">
            <template v-if="group.key === 'root'">
              <a-menu-item v-for="item in group.items" :key="item.key">
                <template #icon>
                  <component :is="item.icon" />
                </template>
                <span>{{ item.label }}</span>
              </a-menu-item>
            </template>
            <a-sub-menu v-else :key="groupMenuKey(group.key)">
              <template #title>
                <span>{{ group.label }}</span>
              </template>
              <a-menu-item v-for="item in group.items" :key="item.key">
                <template #icon>
                  <component :is="item.icon" />
                </template>
                <span>{{ item.label }}</span>
              </a-menu-item>
            </a-sub-menu>
          </template>
        </a-menu>
      </div>
      <div class="relative mt-auto shrink-0 px-4 py-3" role="status" aria-live="polite">
        <div class="flex items-center gap-2">
          <span
            class="h-2 w-2 shrink-0 rounded-full"
            :class="healthOk ? 'bg-[var(--color-success)]' : 'bg-[var(--color-warning)]'"
          />
          <span v-if="!props.collapsed" class="truncate text-xs text-[var(--color-sider-text)]">{{ props.healthState }} - IAM</span>
        </div>
      </div>
    </div>
  </a-layout-sider>
</template>


