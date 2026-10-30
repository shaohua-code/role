<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { graphic } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { AdminOverview } from '@/api'

echarts.use([PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  overview: AdminOverview | null
  primaryColor?: string
  loading?: boolean
}>(), {
  primaryColor: '#18181B',
  loading: false,
})

const pieHost = ref<HTMLDivElement | null>(null)
const barHost = ref<HTMLDivElement | null>(null)
let pieChart: echarts.ECharts | null = null
let barChart: echarts.ECharts | null = null
let themeObserver: MutationObserver | null = null

// 画布色值从 CSS token 读取：黑白灰体系 + 语义点缀，暗色主题下随 data-theme 翻转。
function cssVar(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

// 色板渲染时从 token 取值：浅色墨阶三级 + 蓝/绿/琥珀语义点缀，深色主题自动翻转为近白墨阶。
function palette(): string[] {
  return [
    cssVar('--color-text-primary', '#18181b'),
    cssVar('--color-text-secondary', '#52525b'),
    cssVar('--color-text-muted', '#a1a1aa'),
    cssVar('--color-info', '#2563eb'),
    cssVar('--color-success', '#059669'),
    cssVar('--color-warning', '#d97706'),
  ]
}

// 环心总量：占比读法的锚点数字；0 时隐藏环心并展示占位切片。
// 边界防御：逐字段 ?? 0，避免后端字段漂移（如历史上的 models）导致总量 NaN。
const totalRecords = computed(() => {
  const o = props.overview
  if (!o) return 0
  return (o.tenants ?? 0) + (o.applications ?? 0) + (o.users ?? 0) + (o.roles ?? 0) + (o.recent_audits ?? 0)
})

function metricRows() {
  const o = props.overview
  return [
    { name: '租户', value: o?.tenants ?? 0 },
    { name: '接入应用', value: o?.applications ?? 0 },
    { name: '平台用户', value: o?.users ?? 0 },
    { name: '角色', value: o?.roles ?? 0 },
    { name: '近期审计', value: o?.recent_audits ?? 0 },
  ]
}

function renderPie() {
  if (!pieHost.value) return
  pieChart ??= echarts.init(pieHost.value)
  const rows = [...metricRows()].sort((a, b) => b.value - a.value).filter(row => row.value > 0)
  const data = rows.length ? rows : [{ name: '暂无数据', value: 1 }]
  pieChart.setOption({
    color: palette(),
    tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 条 ({d}%)' },
    legend: { bottom: 0, type: 'scroll', textStyle: { color: cssVar('--color-text-secondary', '#71717a'), fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['50%', '72%'],
      center: ['50%', '42%'],
      itemStyle: { borderRadius: 6, borderColor: cssVar('--color-bg-elevated', '#ffffff'), borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 13, fontWeight: 600 } },
      data,
    }],
  }, true)
}

function renderBar() {
  if (!barHost.value) return
  barChart ??= echarts.init(barHost.value)
  // 降序排列：规模对比从大到小扫读，第一名始终在最上。
  const rows = [...metricRows()].sort((a, b) => b.value - a.value)
  const primary = props.primaryColor
  const textSecondary = cssVar('--color-text-secondary', '#71717a')
  barChart.setOption({
    color: [primary],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 8, right: 40, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: cssVar('--color-border', '#e4e4e7'), type: 'dashed' } },
      axisLabel: { color: textSecondary },
    },
    yAxis: {
      type: 'category',
      data: rows.map(row => row.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: cssVar('--color-text-primary', '#18181b'), fontSize: 12 },
    },
    series: [{
      type: 'bar',
      barWidth: 14,
      // 直标数值：关键值不经悬停即可读（可视化质量门要求）。
      label: {
        show: true,
        position: 'right',
        color: textSecondary,
        fontSize: 11,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      },
      itemStyle: {
        borderRadius: [0, 6, 6, 0],
        color: new graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: primary },
          { offset: 1, color: cssVar('--color-text-secondary', '#52525b') },
        ]),
      },
      data: rows.map(row => row.value),
    }],
  }, true)
}

function renderAll() {
  renderPie()
  renderBar()
}

function onResize() {
  pieChart?.resize()
  barChart?.resize()
}

watch(() => [props.overview, props.primaryColor, props.loading] as const, () => {
  if (!props.loading) renderAll()
})

onMounted(() => {
  renderAll()
  window.addEventListener('resize', onResize)
  // 主题热切换只翻转 CSS 变量，echarts 画布色要重绘才会读取新值：
  // 监听 data-theme 属性变化立即重绘，修复「切主题后图表配色滞后」的已知限制。
  themeObserver = new MutationObserver(() => renderAll())
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  themeObserver?.disconnect()
  themeObserver = null
  pieChart?.dispose()
  barChart?.dispose()
  pieChart = null
  barChart = null
})
</script>

<template>
  <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
    <a-card :bordered="false" class="overflow-hidden shadow-sm">
      <div class="mb-2 flex items-baseline justify-between gap-3">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">A</span>
          数据构成
        </h3>
        <span class="text-xs text-[var(--color-text-muted)]">占比</span>
      </div>
      <div class="relative h-72 w-full min-w-0">
        <div ref="pieHost" class="h-full w-full" role="img" aria-label="平台资源分布环形图" />
        <!-- 环心总量：HTML 覆盖层随主题自动变色，无需 canvas 重绘 -->
        <div
          v-if="totalRecords > 0"
          class="pointer-events-none absolute left-1/2 top-[42%] -translate-x-1/2 -translate-y-1/2 text-center"
        >
          <p class="m-0 text-[22px] font-semibold leading-none tabular-nums text-[var(--color-text-primary)]">{{ totalRecords }}</p>
          <p class="m-0 mt-1 text-[11px] text-[var(--color-text-muted)]">总记录</p>
        </div>
      </div>
    </a-card>
    <a-card :bordered="false" class="overflow-hidden shadow-sm">
      <div class="mb-2 flex items-baseline justify-between gap-3">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">B</span>
          各目录记录数
        </h3>
        <span class="text-xs text-[var(--color-text-muted)]">降序</span>
      </div>
      <div ref="barHost" class="h-72 w-full min-w-0" role="img" aria-label="各目录记录数横向柱状图" />
    </a-card>
  </div>
</template>
