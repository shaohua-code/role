<script lang="ts">
/** 模型用量聚合数据结构（后端 /admin/model-usage/timeline、/admin/model-usage/by-model） */
export interface UsageTimelinePoint {
  day: string
  requests: number
  input_tokens: number
  output_tokens: number
  failed: number
}
export interface UsageModelAggregate {
  model_id: string
  model_name: string
  requests: number
  input_tokens: number
  output_tokens: number
  estimated_cost: string | null
}
</script>

<script setup lang="ts">
/** 模型用量图表区：02 用量趋势（每日 Token 堆叠柱）+ 03 模型分布（Top N 横向柱）。
 *  复用概览图表基建：CSS token 取色、data-theme 观察重绘、动效压到 200ms。 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { graphic } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import AdminEmpty from '@/components/AdminEmpty.vue'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  /** 每日聚合数据；null=尚未加载或读取失败（配合 loadFailed 显示对应状态） */
  timeline?: UsageTimelinePoint[] | null
  /** 按模型聚合数据；null=尚未加载或读取失败 */
  byModel?: UsageModelAggregate[] | null
  /** 父级处于加载中且尚无数据时显示加载占位 */
  loading?: boolean
  /** 聚合请求失败且无历史数据时给出可操作错误提示 */
  loadFailed?: boolean
  /** 选中具体模型筛选时分布图退化为单柱，父级直接隐藏本卡 */
  showByModel?: boolean
}>(), {
  timeline: null,
  byModel: null,
  loading: false,
  loadFailed: false,
  showByModel: true,
})

const trendHost = ref<HTMLDivElement | null>(null)
const distributionHost = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null
let distributionChart: echarts.ECharts | null = null
let themeObserver: MutationObserver | null = null
// tooltip 需要请求次数等未编码为系列的数据；渲染时缓存当前补齐后的行。
let trendRows: UsageTimelinePoint[] = []

// 画布色值从 CSS token 读取：黑白灰体系，暗色主题下随 data-theme 自动翻转。
function cssVar(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

// Token 数量级跨度大（单日可达百万），轴与直标一律用紧凑缩写保证可读。
function compactTokens(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`
  return String(value)
}

// 聚合结果只含有调用记录的日期；补零中间的空日，避免柱距相等造成「时间均匀」的错觉。
function fillTimelineGaps(rows: UsageTimelinePoint[]): UsageTimelinePoint[] {
  if (rows.length <= 1) return rows
  const byDay = new Map(rows.map(row => [row.day, row]))
  const filled: UsageTimelinePoint[] = []
  const DAY_MS = 86_400_000
  const start = Date.parse(`${rows[0].day}T00:00:00Z`)
  const end = Date.parse(`${rows[rows.length - 1].day}T00:00:00Z`)
  for (let cursor = start; cursor <= end; cursor += DAY_MS) {
    const day = new Date(cursor).toISOString().slice(0, 10)
    filled.push(byDay.get(day) ?? { day, requests: 0, input_tokens: 0, output_tokens: 0, failed: 0 })
  }
  return filled
}

// 聚合图表统一的中性浮层：底色/文字/边框走 token，随主题重绘保持一致。
function tooltipStyle() {
  return {
    backgroundColor: cssVar('--color-bg-elevated', '#ffffff'),
    borderColor: cssVar('--color-border', '#e4e4e7'),
    textStyle: { color: cssVar('--color-text-primary', '#18181b') },
  }
}

function renderTrend(): void {
  if (!trendHost.value) return
  trendChart ??= echarts.init(trendHost.value)
  trendRows = fillTimelineGaps(props.timeline ?? [])
  if (!trendRows.length) return
  const ink = cssVar('--color-text-primary', '#18181b')
  const muted = cssVar('--color-text-muted', '#a1a1aa')
  const textSecondary = cssVar('--color-text-secondary', '#52525b')
  const border = cssVar('--color-border', '#e4e4e7')
  trendChart.setOption({
    animationDuration: 200,
    animationDurationUpdate: 200,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: cssVar('--color-brand-subtle', 'rgba(24,24,27,0.06)') } },
      ...tooltipStyle(),
      // 关键值直读：输入/输出/失败与请求数不经悬停以外的解码即可获得。
      formatter: (params: unknown): string => {
        const list = Array.isArray(params) ? params : [params]
        const index = (list[0] as { dataIndex?: number })?.dataIndex ?? 0
        const row = trendRows[index]
        if (!row) return ''
        const lines = [
          `<strong>${row.day}（UTC）</strong>`,
          `请求 ${row.requests.toLocaleString('zh-CN')} 次`,
          `输入 ${row.input_tokens.toLocaleString('zh-CN')} · 输出 ${row.output_tokens.toLocaleString('zh-CN')}`,
        ]
        if (row.failed > 0) lines.push(`失败 ${row.failed.toLocaleString('zh-CN')}`)
        return lines.join('<br/>')
      },
    },
    grid: { left: 8, right: 12, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: trendRows.map(row => row.day.slice(5)),
      axisLine: { lineStyle: { color: border } },
      axisTick: { show: false },
      axisLabel: { color: textSecondary, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: border, type: 'dashed' } },
      axisLabel: { color: textSecondary, fontSize: 11, formatter: (value: number) => compactTokens(value) },
    },
    series: [
      {
        name: '输入 Token',
        type: 'bar',
        stack: 'tokens',
        barMaxWidth: 18,
        itemStyle: { color: ink },
        data: trendRows.map(row => row.input_tokens),
      },
      {
        name: '输出 Token',
        type: 'bar',
        stack: 'tokens',
        barMaxWidth: 18,
        // 堆叠顶段承载圆角，整柱只出现一次顶部圆角。
        itemStyle: { color: muted, borderRadius: [2, 2, 0, 0] },
        data: trendRows.map(row => row.output_tokens),
      },
    ],
  }, true)
}

function renderDistribution(): void {
  if (!distributionHost.value || !props.byModel?.length) return
  distributionChart ??= echarts.init(distributionHost.value)
  const rows = props.byModel.map(row => ({
    ...row,
    total: row.input_tokens + row.output_tokens,
  }))
  const primary = cssVar('--color-text-primary', '#18181b')
  const secondary = cssVar('--color-text-secondary', '#52525b')
  const border = cssVar('--color-border', '#e4e4e7')
  distributionChart.setOption({
    animationDuration: 200,
    animationDurationUpdate: 200,
    tooltip: {
      trigger: 'item',
      ...tooltipStyle(),
      formatter: (params: unknown): string => {
        const index = (params as { dataIndex?: number })?.dataIndex ?? 0
        const row = rows[index]
        if (!row) return ''
        const costText = row.estimated_cost === null ? '费用未知' : `估算 ${row.estimated_cost}`
        return [
          `<strong>${row.model_name}</strong>`,
          `请求 ${row.requests.toLocaleString('zh-CN')} 次 · Token ${compactTokens(row.total)}`,
          `输入 ${row.input_tokens.toLocaleString('zh-CN')} · 输出 ${row.output_tokens.toLocaleString('zh-CN')}`,
          costText,
        ].join('<br/>')
      },
    },
    grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: border, type: 'dashed' } },
      axisLabel: { color: secondary, fontSize: 11, formatter: (value: number) => compactTokens(value) },
    },
    yAxis: {
      type: 'category',
      // 后端已按总 Token 降序；echarts 类目轴自下而上绘制，需反转让第一名始终在最上。
      data: rows.map(row => row.model_name).reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: cssVar('--color-text-primary', '#18181b'), fontSize: 12, width: 128, overflow: 'truncate' },
    },
    series: [{
      type: 'bar',
      barWidth: 14,
      // 直标数值：排名与量级不经悬停即可读（可视化质量门要求）。
      label: {
        show: true,
        position: 'right',
        color: secondary,
        fontSize: 11,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        formatter: (params: { value: number }) => compactTokens(params.value),
      },
      itemStyle: {
        borderRadius: [0, 6, 6, 0],
        color: new graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: primary },
          { offset: 1, color: secondary },
        ]),
      },
      data: rows.map(row => row.total).reverse(),
    }],
  }, true)
}

function renderAll(): void {
  renderTrend()
  renderDistribution()
}

function onResize(): void {
  trendChart?.resize()
  distributionChart?.resize()
}

// 图表空态判定：加载中、读取失败、确认无数据三态分别可辨。
function trendState(): 'loading' | 'error' | 'empty' | 'ready' {
  if (props.loading && !props.timeline) return 'loading'
  if (props.timeline?.length) return 'ready'
  if (props.loadFailed) return 'error'
  return 'empty'
}

function distributionState(): 'loading' | 'error' | 'empty' | 'ready' {
  if (props.loading && !props.byModel) return 'loading'
  if (props.byModel?.length) return 'ready'
  if (props.loadFailed) return 'error'
  return 'empty'
}

// 冷启动整段收敛：任一图有数据即渲染完整双图布局，否则渲染单条空档带。
const hasAnyData = computed(() => Boolean(props.timeline?.length || props.byModel?.length))
const chartsLoading = computed(() => props.loading && !hasAnyData.value)

// flush: 'post'——数据从空态切到有数据时宿主节点刚由 v-if 挂载，渲染必须等 DOM 更新完成。
watch(() => [props.timeline, props.byModel, props.loading, props.showByModel] as const, () => {
  // 分布卡被 v-if 移除后实例仍挂在游离 DOM 上，必须释放，否则主题重绘写入失效节点。
  if (!props.showByModel) {
    distributionChart?.dispose()
    distributionChart = null
  }
  renderAll()
}, { flush: 'post' })

onMounted(() => {
  renderAll()
  window.addEventListener('resize', onResize)
  // 主题热切换只翻转 CSS 变量，canvas 色需重绘：监听 data-theme 立即重绘（同概览图表）。
  themeObserver = new MutationObserver(() => renderAll())
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  themeObserver?.disconnect()
  themeObserver = null
  trendChart?.dispose()
  distributionChart?.dispose()
  trendChart = null
  distributionChart = null
})
</script>

<template>
  <!-- 冷启动收敛：无任何聚合数据时不渲染双图骨架，整段降为一条安静空档带（避免两张大白空框）。 -->
  <a-card v-if="!hasAnyData" class="data-card" :bordered="false">
    <div v-if="chartsLoading" class="flex min-h-[88px] items-center justify-center text-[13px] text-[var(--color-text-muted)]" role="status">正在加载用量图表…</div>
    <div v-else-if="loadFailed" class="flex items-center gap-3 py-2" role="alert">
      <span class="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-[var(--color-bg-subtle)] text-base" aria-hidden="true">⚠️</span>
      <span class="min-w-0">
        <span class="block text-sm font-medium text-[var(--color-text-primary)]">聚合图表读取失败</span>
        <span class="mt-0.5 block text-xs text-[var(--color-warning)]">当前展示可能为上次结果，请刷新重试。</span>
      </span>
    </div>
    <div v-else class="flex items-center gap-4 py-2">
      <span class="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-base" aria-hidden="true">📈</span>
      <span class="min-w-0">
        <span class="block text-sm font-medium text-[var(--color-text-primary)]">暂无模型调用记录</span>
        <span class="mt-0.5 block text-xs text-[var(--color-text-muted)]">网关上报或核对入账后，这里会展示每日 Token 消耗趋势与各模型分布。</span>
      </span>
    </div>
  </a-card>

  <div v-else class="grid grid-cols-1 gap-4 lg:grid-cols-2">
    <section class="flex min-w-0 flex-col">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">02</span>
          用量趋势
        </h3>
        <!-- 图例用药丸 chips：与两栏标题行拉开视觉层级，不再像散落的裸文本。 -->
        <span class="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
          <span class="flex items-center gap-1.5 rounded-full bg-[var(--color-bg-subtle)] px-2.5 py-1"><i class="h-2 w-2 rounded-sm bg-[var(--color-text-primary)]" aria-hidden="true" />输入</span>
          <span class="flex items-center gap-1.5 rounded-full bg-[var(--color-bg-subtle)] px-2.5 py-1"><i class="h-2 w-2 rounded-sm bg-[var(--color-text-muted)]" aria-hidden="true" />输出</span>
        </span>
      </div>
      <a-card class="data-card" :bordered="false">
        <div v-if="trendState() === 'ready'" class="h-72 w-full min-w-0">
          <div ref="trendHost" class="h-full w-full" role="img" aria-label="每日输入与输出 Token 消耗堆叠柱状图" />
        </div>
        <div v-else-if="trendState() === 'loading'" class="grid min-h-[180px] place-items-center py-6 text-[13px] text-[var(--color-text-muted)]" role="status">正在加载用量趋势…</div>
        <div v-else-if="trendState() === 'error'" class="grid min-h-[180px] place-items-center py-6 text-[13px] text-[var(--color-warning)]" role="alert">聚合数据读取失败，请刷新重试。</div>
        <AdminEmpty v-else class="grid min-h-[180px] place-items-center py-6" emoji="📈" description="所选范围内暂无调用记录" />
      </a-card>
    </section>

    <section v-if="showByModel" class="flex min-w-0 flex-col">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h3 class="mb-0 flex items-baseline gap-2 text-base font-semibold text-[var(--color-text-primary)]">
          <span class="font-mono text-[11px] font-medium text-[var(--color-text-muted)]">03</span>
          模型分布
        </h3>
        <span class="whitespace-nowrap text-xs text-[var(--color-text-muted)]">Top 8 · 总 Token 降序</span>
      </div>
      <a-card class="data-card" :bordered="false">
        <div v-if="distributionState() === 'ready'" class="h-72 w-full min-w-0">
          <div ref="distributionHost" class="h-full w-full" role="img" aria-label="各模型 Token 消耗横向柱状图" />
        </div>
        <div v-else-if="distributionState() === 'loading'" class="grid min-h-[180px] place-items-center py-6 text-[13px] text-[var(--color-text-muted)]" role="status">正在加载模型分布…</div>
        <div v-else-if="distributionState() === 'error'" class="grid min-h-[180px] place-items-center py-6 text-[13px] text-[var(--color-warning)]" role="alert">聚合数据读取失败，请刷新重试。</div>
        <AdminEmpty v-else class="grid min-h-[180px] place-items-center py-6" emoji="🧮" description="所选范围内暂无模型调用" />
      </a-card>
    </section>
  </div>
</template>
