<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { Component } from 'vue'
import { ArrowRightOutlined, AppstoreOutlined, KeyOutlined, SafetyOutlined, UserOutlined } from '@ant-design/icons-vue'
import type { AdminOverview } from '@/api'
import { PAGE_PATHS, type PageKey } from '@/router/navigation'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import OverviewDashboardCharts from './OverviewDashboardCharts.vue'
import OverviewStatCard from './components/OverviewStatCard.vue'

const props = defineProps<{
  overview: AdminOverview | null
  healthState: string
  loading: boolean
  primaryColor?: string
}>()

const emit = defineEmits<{
  navigate: [page: 'application_workspace']
  refresh: []
}>()

const router = useRouter()

// 数据新鲜度标注：运营台以数据为主角，需让「快照何时生成」一眼可见。
const lastRefreshedAt = ref('')
watch(() => props.overview, snapshot => {
  if (snapshot) lastRefreshedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}, { immediate: true })

// 指标卡配置：账本式编号 + 点击跳转（编号仅供排版，与数据无关）。
// 与后端 /admin/overview 返回对齐（P364 修正：models 字段后端已不存在，旧页恒显示「—」）。
const statCards = computed(() => {
  const o = props.overview
  return [
    { key: 'tenants' as const, index: '01', label: '租户', value: o?.tenants },
    { key: 'applications' as const, index: '02', label: '应用', value: o?.applications },
    { key: 'users' as const, index: '03', label: '平台用户', value: o?.users },
    { key: 'roles' as const, index: '04', label: '角色', value: o?.roles },
    { key: 'audits' as const, index: '05', label: '近期审计', value: o?.recent_audits },
  ]
})

// 指标卡点击跳转与 PageKey 对齐
const statPageMap: Record<(typeof statCards.value)[number]['key'], PageKey> = {
  tenants: 'tenants',
  applications: 'application_workspace',
  users: 'users',
  roles: 'application_workspace',
  audits: 'audit',
}

// 快速上手三步流程：与「使用路径」提示等价，但改为可点击的步骤链。
const setupSteps: Array<{ key: PageKey, index: string, icon: Component, title: string, desc: string }> = [
  { key: 'application_workspace', index: '01', icon: KeyOutlined, title: '权限编码', desc: '在应用工作台维护本应用权限码' },
  { key: 'application_workspace', index: '02', icon: SafetyOutlined, title: '角色挂码', desc: '在应用工作台为角色挂码 / 资源 / 数据范围' },
  { key: 'users', index: '03', icon: UserOutlined, title: '用户绑角色', desc: '在用户管理给用户勾多个角色' },
]

const capabilityCards: Array<{ title: string, desc: string, icon: Component, page: PageKey }> = [
  { title: '应用工作台', desc: '左树新建或选中应用后维护角色、权限编码、资源树与应用设置', icon: AppstoreOutlined, page: 'application_workspace' },
  { title: '组织工作台', desc: '左树新建或选中组织后维护成员、用户组与组织设置', icon: AppstoreOutlined, page: 'organization_workspace' },
  { title: '用户管理', desc: '给用户绑定多个角色，权限按角色并集', icon: UserOutlined, page: 'users' },
  { title: '高级管理', desc: '平台角色 / 权限编码 / 用户组（默认折叠）', icon: SafetyOutlined, page: 'roles' },
]

// 快捷入口与侧栏路由共用 PAGE_PATHS，避免硬编码 path。
function goPage(page: PageKey): void {
  void router.push(PAGE_PATHS[page])
}
</script>

<template>
  <section class="flex w-full min-w-0 flex-col gap-8 pb-8">
    <!-- 页头：与登录页品牌区（IDENTITY & ACCESS）刻意区分，采用运营台口吻 -->
    <AdminPageHeader
      eyebrow="CONSOLE OVERVIEW"
      title="运营总览"
      subtitle="平台资源规模、服务状态与管理入口一览。"
    >
      <template #extra>
        <a-space wrap>
          <a-button :loading="loading" @click="emit('refresh')">刷新概览</a-button>
          <a-button type="primary" @click="emit('navigate', 'application_workspace')">打开应用工作台</a-button>
        </a-space>
      </template>
    </AdminPageHeader>

    <!-- 状态条：服务健康 + 快照时间 + 阶段标签，账本式上下细线替代大标语卡 -->
    <div class="flex flex-wrap items-center gap-x-4 gap-y-2 border-y border-[var(--color-border)] py-3 text-xs text-[var(--color-text-secondary)]">
      <span class="inline-flex items-center gap-2">
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="healthState === '服务正常' ? 'bg-[var(--color-success)]' : 'bg-[var(--color-warning)]'"
          aria-hidden="true"
        />
        {{ healthState }}
      </span>
      <span class="text-[var(--color-text-muted)]">数据更新于 {{ lastRefreshedAt || '—' }}</span>
      <span class="hidden h-3 w-px bg-[var(--color-border)] sm:block" aria-hidden="true" />
      <span class="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-text-muted)]">主路径 · 应用/组织工作台</span>
      <span class="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-text-muted)]">三层配权 · 码 / 角色 / 资源树</span>
    </div>

    <!-- 01 指标快照：巨型 tabular 数字是页面视觉主角 -->
    <div>
      <div class="mb-3 flex items-baseline justify-between gap-3">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">01</span>
          指标快照
        </h3>
        <p class="mb-0 text-xs text-[var(--color-text-muted)]">点击卡片进入对应模块</p>
      </div>
      <a-spin :spinning="loading">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
          <OverviewStatCard
            v-for="card in statCards"
            :key="card.key"
            :label="card.label"
            :value="card.value"
            :index="card.index"
            @click="goPage(statPageMap[card.key])"
          />
        </div>
      </a-spin>
    </div>

    <!-- 02 规模与构成：同一快照的两种读法（条形比规模，环形看占比） -->
    <div>
      <div class="mb-3 flex items-baseline justify-between gap-3">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">02</span>
          规模与构成
        </h3>
        <p class="mb-0 text-xs text-[var(--color-text-muted)]">条形比规模 · 环形看占比</p>
      </div>
      <OverviewDashboardCharts
        :overview="overview"
        :primary-color="primaryColor"
        :loading="loading"
      />
    </div>

    <!-- 03 快速上手：三步权限配置流程，步骤可点击直达 -->
    <div>
      <div class="mb-3 flex items-baseline justify-between gap-3">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">03</span>
          快速上手
        </h3>
        <p class="mb-0 text-xs text-[var(--color-text-muted)]">日常配权走应用工作台；列表页在「高级管理」</p>
      </div>
      <div class="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <template v-for="(step, i) in setupSteps" :key="step.key">
            <button
              type="button"
              class="group flex min-w-0 flex-1 items-center gap-3 rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-2 text-left transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
              @click="goPage(step.key)"
            >
              <span
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-bg-subtle)] text-sm text-[var(--color-text-primary)] transition-colors duration-150 group-hover:bg-[var(--color-brand-subtle)]"
                aria-hidden="true"
              >
                <component :is="step.icon" />
              </span>
              <span class="flex min-w-0 flex-col">
                <span class="flex items-baseline gap-2">
                  <span class="font-mono text-[10px] text-[var(--color-text-muted)]">{{ step.index }}</span>
                  <span class="text-sm font-semibold text-[var(--color-text-primary)]">{{ step.title }}</span>
                </span>
                <span class="truncate text-xs text-[var(--color-text-secondary)]">{{ step.desc }}</span>
              </span>
            </button>
            <!-- 步骤间箭头：最后一步之后不渲染，避免悬空指向 -->
            <ArrowRightOutlined
              v-if="i < setupSteps.length - 1"
              class="mx-1 shrink-0 rotate-90 text-xs text-[var(--color-text-muted)] sm:rotate-0"
              aria-hidden="true"
            />
          </template>
        </div>
      </div>
    </div>

    <!-- 04 管理入口：图标 + 编号的模块卡，替代原「已提供管理 API」胶囊 -->
    <div>
      <div class="mb-3 flex items-baseline justify-between gap-3">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">04</span>
          管理入口
        </h3>
        <p class="mb-0 text-xs text-[var(--color-text-muted)]">或从左侧菜单导航</p>
      </div>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <button
          v-for="item in capabilityCards"
          :key="item.page"
          type="button"
          class="group flex flex-col rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4 text-left transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
          @click="goPage(item.page)"
        >
          <span class="flex w-full items-center justify-between">
            <span
              class="flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-bg-subtle)] text-base text-[var(--color-text-primary)]"
              aria-hidden="true"
            >
              <component :is="item.icon" />
            </span>
            <ArrowRightOutlined
              class="text-xs text-[var(--color-text-muted)] opacity-0 transition-all duration-150 group-hover:translate-x-0.5 group-hover:opacity-100"
              aria-hidden="true"
            />
          </span>
          <span class="mt-3 text-sm font-semibold text-[var(--color-text-primary)]">{{ item.title }}</span>
          <span class="mt-1 text-xs leading-relaxed text-[var(--color-text-secondary)]">{{ item.desc }}</span>
        </button>
      </div>
    </div>
  </section>
</template>
