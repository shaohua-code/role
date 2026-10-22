<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { graphic } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { AdminOverview } from '../../shared/services/api'

echarts.use([PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  overview: AdminOverview | null
  primaryColor?: string
  loading?: boolean
}>(), {
  primaryColor: '#756df2',
  loading: false,
})

const pieHost = ref<HTMLDivElement | null>(null)
const barHost = ref<HTMLDivElement | null>(null)
let pieChart: echarts.ECharts | null = null
let barChart: echarts.ECharts | null = null

const palette = ['#756df2', '#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#38bdf8']

function metricRows() {
  const o = props.overview
  return [
    { name: '租户', value: o?.tenants ?? 0 },
    { name: '接入应用', value: o?.applications ?? 0 },
    { name: '平台用户', value: o?.users ?? 0 },
    { name: '角色', value: o?.roles ?? 0 },
    { name: '模型目录', value: o?.models ?? 0 },
    { name: '近期审计', value: o?.recent_audits ?? 0 },
  ]
}

function renderPie() {
  if (!pieHost.value) return
  pieChart ??= echarts.init(pieHost.value)
  const rows = metricRows().filter(row => row.value > 0)
  const data = rows.length ? rows : [{ name: '暂无数据', value: 1 }]
  pieChart.setOption({
    color: palette,
    tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 条 ({d}%)' },
    legend: { bottom: 0, type: 'scroll', textStyle: { color: '#64748b', fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 13, fontWeight: 600 } },
      data,
    }],
  }, true)
}

function renderBar() {
  if (!barHost.value) return
  barChart ??= echarts.init(barHost.value)
  const rows = metricRows()
  const primary = props.primaryColor
  barChart.setOption({
    color: [primary],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'category',
      data: rows.map(row => row.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#475569', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      barWidth: 14,
      itemStyle: {
        borderRadius: [0, 8, 8, 0],
        color: new graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: primary },
          { offset: 1, color: '#a78bfa' },
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
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  pieChart?.dispose()
  barChart?.dispose()
  pieChart = null
  barChart = null
})
</script>

<template>
  <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
    <a-card :bordered="false" class="overflow-hidden shadow-sm">
      <p class="mb-1 text-xs tracking-widest text-slate-400 uppercase">资源分布</p>
      <h3 class="mb-2 text-base font-semibold text-slate-800">平台数据构成</h3>
      <div ref="pieHost" class="h-72 w-full min-w-0" role="img" aria-label="平台资源分布环形图" />
    </a-card>
    <a-card :bordered="false" class="overflow-hidden shadow-sm">
      <p class="mb-1 text-xs tracking-widest text-slate-400 uppercase">规模对比</p>
      <h3 class="mb-2 text-base font-semibold text-slate-800">各目录记录数</h3>
      <div ref="barHost" class="h-72 w-full min-w-0" role="img" aria-label="各目录记录数横向柱状图" />
    </a-card>
  </div>
</template>
