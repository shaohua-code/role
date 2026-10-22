<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { AdminOverview } from '../../shared/services/api'
import { PAGE_PATHS, type PageKey } from '../../app/navigation'
import AdminPageHeader from '../../shared/components/AdminPageHeader.vue'
import OverviewDashboardCharts from './OverviewDashboardCharts.vue'

const props = defineProps<{
  overview: AdminOverview | null
  healthState: string
  loading: boolean
  primaryColor?: string
}>()

const emit = defineEmits<{
  navigate: [page: 'applications']
  refresh: []
}>()

const router = useRouter()

const statCards = computed(() => {
  const o = props.overview
  return [
    { key: 'tenants', label: '租户', value: o?.tenants, tint: 'from-violet-500/15 to-violet-500/5', accent: 'text-violet-600' },
    { key: 'applications', label: '接入应用', value: o?.applications, tint: 'from-indigo-500/15 to-indigo-500/5', accent: 'text-indigo-600' },
    { key: 'users', label: '平台用户', value: o?.users, tint: 'from-sky-500/15 to-sky-500/5', accent: 'text-sky-600' },
    { key: 'roles', label: '角色', value: o?.roles, tint: 'from-fuchsia-500/15 to-fuchsia-500/5', accent: 'text-fuchsia-600' },
    { key: 'models', label: '模型目录', value: o?.models, tint: 'from-cyan-500/15 to-cyan-500/5', accent: 'text-cyan-600' },
    { key: 'audits', label: '近期审计', value: o?.recent_audits, tint: 'from-amber-500/15 to-amber-500/5', accent: 'text-amber-600' },
  ] as const
})

// 指标卡点击跳转与 PageKey 对齐
const statPageMap: Record<(typeof statCards.value)[number]['key'], PageKey> = {
  tenants: 'tenants',
  applications: 'applications',
  users: 'users',
  roles: 'roles',
  models: 'models',
  audits: 'audit',
}

const capabilityCards = [
  { title: '身份目录', desc: '租户、用户与多租户成员关系', page: 'tenants' as PageKey },
  { title: '访问控制', desc: '按资源与 Scope 维护角色授权', page: 'roles' as PageKey },
  { title: '应用接入', desc: '登记 OAuth 客户端与新项目接入向导', page: 'project_integration' as PageKey },
  { title: '应用品牌', desc: '版本化配置各系统登录页主题', page: 'themes' as PageKey },
]

// 快捷入口与侧栏路由共用 PAGE_PATHS，避免硬编码 path。
function goPage(page: PageKey): void {
  void router.push(PAGE_PATHS[page])
}
</script>

<template>
  <section class="flex w-full min-w-0 flex-col gap-6 pb-8">
    <AdminPageHeader
      eyebrow="IDENTITY & ACCESS"
      title="统一身份与权限管理"
      subtitle="集中管理租户、应用、用户和访问策略。"
    >
      <template #extra>
        <a-space wrap>
          <a-button :loading="loading" @click="emit('refresh')">刷新概览</a-button>
          <a-button type="primary" @click="emit('navigate', 'applications')">管理接入应用</a-button>
        </a-space>
      </template>
    </AdminPageHeader>

    <div
      class="relative overflow-hidden rounded-2xl border border-violet-200/80 bg-gradient-to-br from-violet-600 via-violet-500 to-indigo-600 px-6 py-8 text-white shadow-lg shadow-violet-500/25"
    >
      <div class="pointer-events-none absolute -top-16 -right-10 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
      <div class="pointer-events-none absolute -bottom-20 -left-8 h-56 w-56 rounded-full bg-indigo-300/20 blur-3xl" />
      <div class="relative flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div class="min-w-0 max-w-2xl">
          <a-badge
            :status="healthState === '服务正常' ? 'success' : 'warning'"
            :text="healthState"
            class="mb-3 [&_.ant-badge-status-text]:text-violet-100"
          />
          <h2 class="mb-2 text-2xl font-semibold tracking-tight md:text-3xl">让身份统一，让访问规则清晰可控</h2>
          <p class="mb-0 text-sm leading-relaxed text-violet-100/95 md:text-base">
            从一个控制台管理应用接入、用户身份和资源权限，并持续记录关键操作。
          </p>
          <div class="mt-4 flex flex-wrap gap-2">
            <span class="rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs">当前试点 · DeerFlow</span>
            <span class="rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs">本阶段 · 仅本人数据</span>
          </div>
        </div>
        <a-button
          type="default"
          class="shrink-0 border-white/30 bg-white/15 text-white hover:border-white/50 hover:bg-white/25 hover:text-white"
          @click="goPage('project_integration')"
        >
          新项目接入向导
        </a-button>
      </div>
    </div>

    <div>
      <div class="mb-3 flex items-end justify-between gap-3">
        <div>
          <h3 class="mb-0 text-base font-semibold text-slate-800">平台概况</h3>
          <p class="mb-0 text-xs text-slate-500">当前数据库中的管理数据快照</p>
        </div>
      </div>
      <a-spin :spinning="loading">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <button
            v-for="card in statCards"
            :key="card.key"
            type="button"
            class="flex flex-col rounded-xl border border-slate-200/80 bg-gradient-to-br p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-md"
            :class="card.tint"
            @click="goPage(statPageMap[card.key])"
          >
            <span class="text-xs text-slate-500">{{ card.label }}</span>
            <span class="mt-1 text-2xl font-semibold tabular-nums" :class="card.accent">
              {{ card.value ?? '—' }}
            </span>
            <span class="mt-1 text-[11px] text-slate-400">条记录</span>
          </button>
        </div>
      </a-spin>
    </div>

    <OverviewDashboardCharts
      :overview="overview"
      :primary-color="primaryColor"
      :loading="loading"
    />

    <div>
      <h3 class="mb-1 text-base font-semibold text-slate-800">管理能力</h3>
      <p class="mb-3 text-xs text-slate-500">选择模块进入数据管理，或从左侧菜单导航</p>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <button
          v-for="item in capabilityCards"
          :key="item.page"
          type="button"
          class="group flex flex-col rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-violet-300 hover:shadow-md"
          @click="goPage(item.page)"
        >
          <span class="mb-2 inline-flex w-fit rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">已提供管理 API</span>
          <span class="text-sm font-semibold text-slate-800 group-hover:text-violet-700">{{ item.title }}</span>
          <span class="mt-1 text-xs leading-relaxed text-slate-500">{{ item.desc }}</span>
        </button>
      </div>
    </div>
  </section>
</template>
