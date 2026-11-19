<script setup lang="ts">
// 目录概览带：账本式统计卡（对齐 P368/P369 巨号数字语言 + P389 统计卡带模式）。
// 「全部 / 启用中 / 已停用」三卡可点击即筛选状态（再点取消）；下发关系卡为纯展示。
import { computed } from 'vue'

// 结构化最小契约：与页面 ModelRecord 字段兼容（TS 结构化类型，避免循环依赖）。
interface SummaryModel {
  status: 'active' | 'disabled'
  tenant_grant_count?: number
  application_grant_count?: number
}

const props = withDefaults(defineProps<{
  /** 目录模型全集（未筛选），用于汇总计数 */
  models?: SummaryModel[]
  /** true=超管视角（统计租户下发关系）；false=只读视角（统计应用下发关系） */
  superView?: boolean
}>(), {
  models: () => [],
  superView: false,
})

// v-model:status-filter 双向绑定当前状态筛选（undefined=全部）
const statusFilter = defineModel<'active' | 'disabled' | undefined>('statusFilter', { default: undefined })

interface SummaryCard {
  key: string
  label: string
  value: number
  /** 可点击卡对应的状态筛选；undefined 且 plain=true 表示纯展示卡 */
  filter?: 'active' | 'disabled'
  plain?: boolean
}

const cards = computed<SummaryCard[]>(() => {
  const total = props.models.length
  const active = props.models.filter(model => model.status === 'active').length
  const grants = props.models.reduce(
    (sum, model) => sum + (props.superView ? model.tenant_grant_count ?? 0 : model.application_grant_count ?? 0),
    0,
  )
  return [
    { key: 'all', label: '全部模型', value: total, filter: undefined },
    { key: 'active', label: '启用中', value: active, filter: 'active' },
    { key: 'disabled', label: '已停用', value: total - active, filter: 'disabled' },
    { key: 'grants', label: props.superView ? '租户下发关系' : '应用下发关系', value: grants, plain: true },
  ]
})

// 点击可筛选卡：同卡再点取消回「全部」
function select(card: SummaryCard): void {
  if (card.plain || !card.filter) return
  statusFilter.value = statusFilter.value === card.filter ? undefined : card.filter
}
</script>

<template>
  <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
    <component
      :is="card.plain ? 'div' : 'button'"
      v-for="card in cards"
      :key="card.key"
      :type="card.plain ? undefined : 'button'"
      class="summary-card"
      :class="{ 'summary-card-click': !card.plain, 'summary-card-selected': !card.plain && statusFilter === card.filter }"
      @click="select(card)"
    >
      <span class="summary-label">{{ card.label }}</span>
      <span class="summary-value">{{ card.value.toLocaleString('zh-CN') }}</span>
    </component>
  </div>
</template>

<style scoped>
.summary-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-elevated);
  padding: 16px;
  text-align: left;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}
/* 仅可点击卡有交互态；纯展示卡保持安静 */
.summary-card-click { cursor: pointer; }
.summary-card-click:hover { border-color: var(--color-border-strong); background: var(--color-bg-subtle); }
/* 选中筛选卡：石墨黑边加重（P389 目录卡同语言） */
.summary-card-selected { border-color: var(--color-text-primary); }
.summary-label { font-size: 12px; font-weight: 500; color: var(--color-text-secondary); }
.summary-value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
  color: var(--color-text-primary);
}
</style>
