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
      <!-- R4：品牌行 + 折叠按钮——折叠态两者垂直居中（72px 窄栏里不再一个靠左一个靠右） -->
      <div class="relative flex items-center justify-between gap-2 px-3 pt-4 pb-2" :class="props.collapsed ? 'justify-center' : ''">
        <router-link :to="brandTarget" class="flex min-w-0 items-center gap-2 no-underline">
          <!-- 侧栏恒黑，logo 方块不能用品牌色（黑上黑/暗色翻转白后白上白）：白底黑字与侧栏底反差恒定 -->
          <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-sider-text-active)] text-xs font-semibold text-[var(--color-sider-bg)]">ID</span>
          <span v-if="!props.collapsed" class="min-w-0">
            <strong class="block truncate text-sm font-semibold text-[var(--color-sider-text-active)]">{{ brandTitle }}</strong>
            <small class="block text-[11px] tracking-[0.06em] text-[var(--color-sider-text)]">Identity Control</small>
          </span>
        </router-link>
        <!-- U25：折叠图标提亮到 sider-text-strong（颜色类会被无层 reset 吃掉，改由 style.css 固定） -->
        <button
          v-if="!props.collapsed"
          type="button"
          class="sider-toggle-btn flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors duration-150 hover:bg-[var(--color-sider-item-hover)]"
          :aria-expanded="!props.collapsed"
          :aria-label="collapseLabel"
          @click="toggleSidebar"
        >
          <MenuFoldOutlined />
        </button>
      </div>
      <div v-if="props.collapsed" class="relative flex justify-center px-3 pb-1">
        <button
          type="button"
          class="sider-toggle-btn flex h-8 w-8 items-center justify-center rounded-lg transition-colors duration-150 hover:bg-[var(--color-sider-item-hover)]"
          aria-expanded="false"
          :aria-label="expandLabel"
          @click="toggleSidebar"
        >
          <MenuUnfoldOutlined />
        </button>
      </div>
      <!-- R4：模式身份 chip 化——「平台管理 / 租户管理」从裸灰字升级为描边胶囊，身份感与分隔感兼得 -->
      <p v-if="!props.collapsed" class="relative shrink-0 px-5 pb-3">
        <span class="inline-flex items-center rounded-full border border-white/10 px-2.5 py-0.5 text-[11px] font-medium tracking-[0.06em] text-[var(--color-sider-text)]">{{ props.modeLabel }}</span>
      </p>
      <!-- R6 撤销上下缘渐隐 mask（U25）：滚动条已被 D12 隐藏，渐隐失去「可滚暗示」意义；
           且菜单滚到顶部时选中胶囊上缘会落进渐隐区被「吃」掉颜色，观感像被上方遮挡。
           现为普通滚动容器，滚轮仍可滚，边缘硬裁属常规滚动行为。 -->
      <div class="sider-menu-scroll relative min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-2">
        <!-- R5 折叠态接管：antd inline-collapsed 在本壳受控 openKeys 下不会进入图标形态，
             组标题以 inline 文字形态被 72px 窄栏裁切（半残呈现）。改为自绘图标列——
             每页一个图标 + tooltip 报名，选中白块反白，组间 hairline 分节。展开态仍走 a-menu。 -->
        <div v-if="props.collapsed" class="flex flex-col items-center gap-1 py-1">
          <template v-for="(group, groupIndex) in navGroups" :key="group.key">
            <span v-if="groupIndex > 0" class="my-1 h-px w-6 shrink-0 bg-white/10" aria-hidden="true" />
            <a-tooltip v-for="item in group.items" :key="item.key" placement="right" :title="item.label">
              <!-- U25 同因：button 上的 text-* 颜色类会被无层 reset 吃掉，图标色由 style.css D11 的
                   sider-nav-btn 无层规则固定；这里只管几何与背景（bg 类不受 reset 影响）。 -->
              <button
                type="button"
                class="sider-nav-btn flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] text-base transition-colors duration-150"
                :class="activePage === item.key ? 'sider-nav-btn-active' : 'hover:bg-[var(--color-sider-item-hover)]'"
                :aria-label="item.label"
                :aria-current="activePage === item.key ? 'page' : undefined"
                @click="navigateTo(item.key)"
              >
                <component :is="item.icon" />
              </button>
            </a-tooltip>
          </template>
        </div>
        <a-menu
          v-else
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
      </div>
      <!-- R4：状态区加顶部 hairline 与菜单区收边；折叠态健康点居中对齐中轴 -->
      <div class="relative mt-auto shrink-0 border-t border-white/10 px-4 py-3" role="status" aria-live="polite">
        <div class="flex items-center gap-2" :class="props.collapsed ? 'justify-center' : ''">
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


