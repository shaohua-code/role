<script setup lang="ts">
// 右栏信息面板（Splitpanes 右侧）：单一卡片纵向三区——
// ① 测试范围（模式/租户/应用/模型选择）② 连接遥测 2×2 ③ 诊断三 Tab（思考/事件/用量）。
// 范围区默认折叠为一行摘要（用户标注「加上折叠，默认收起」），把纵向空间让给诊断区；
// 未选择模型时自动展开引导切换。摘要随选择实时更新，收起状态也可确认当前范围。
import { computed, ref, watch } from 'vue'
import { DownOutlined } from '@/plugins/icons'
import ContextBar from './ContextBar.vue'
import StatusStrip, { type StripCell } from './StatusStrip.vue'
import DiagnosticPanel from './DiagnosticPanel.vue'
import type { TestEventItem, TestModelSummary } from '../api'

const mode = defineModel<'app' | 'platform'>('mode', { default: 'app' })
const modelId = defineModel<string>('modelId', { default: '' })
const tenantId = defineModel<string>('tenantId', { default: '' })
const applicationId = defineModel<string>('applicationId', { default: '' })
const tab = defineModel<'thinking' | 'events' | 'usage'>('tab', { default: 'thinking' })

const props = defineProps<{
  models: TestModelSummary[]
  tenants: Array<{ id: string; name: string; status: string }>
  applications: Array<{ id: string; name: string; tenant_id: string; status: string }>
  config: StripCell
  auth: StripCell
  provider: StripCell
  generation: StripCell
  events: TestEventItem[]
  thinkingText: string
  thinkingReason: string
  thinkingDetail: string
  usage: {
    requestId: string
    httpStatus: string
    quality: 'actual' | 'estimated' | 'unknown'
    inputTokens: number | null
    outputTokens: number | null
    reasoningTokens: number | null
    note: string
  } | null
  paramsSummary: string
}>()

// 测试范围折叠态：默认收起；模型被清空（如切换上下文重置）时自动展开引导重新选择。
const scopeCollapsed = ref(true)
watch(modelId, (value) => {
  if (!value) scopeCollapsed.value = false
})

// 收起态摘要：模式 · 租户 · 应用 · 模型（应用对话模式）；平台连接省略租户/应用两段。
const scopeSummary = computed(() => {
  const modeText = mode.value === 'app' ? '应用对话' : '平台连接'
  const tenant = props.tenants.find(item => item.id === tenantId.value)?.name ?? '—'
  const application = props.applications.find(item => item.id === applicationId.value)?.name ?? '—'
  const model = props.models.find(item => item.id === modelId.value)?.display_name ?? '未选择模型'
  return [modeText, mode.value === 'app' ? tenant : null, mode.value === 'app' ? application : null, model]
    .filter(Boolean)
    .join(' · ')
})
</script>

<template>
  <!-- lg+ 吃满分栏 Pane 高度（h-full 收窄到 lg 档，避免覆盖父页窄屏固定高度 h-[520px]） -->
  <div class="flex min-h-0 flex-col lg:h-full">
    <!-- 统一信息卡：范围 + 遥测 + 诊断融合为一张卡片（内部各自分区，Tab 区吃满剩余并独立滚动） -->
    <div class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)]">
      <!-- ① 测试范围：默认折叠为一行摘要，点击展开模式/租户/应用/模型选择 -->
      <div class="shrink-0 border-b border-[var(--color-border)] px-3.5 py-2.5">
        <button
          type="button"
          class="flex w-full cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] px-1 py-1 text-left transition-colors hover:bg-[var(--color-row-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-tech-accent)]"
          :aria-expanded="!scopeCollapsed"
          @click="scopeCollapsed = !scopeCollapsed"
        >
          <span class="shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">测试范围 / Scope</span>
          <span class="min-w-0 flex-1 truncate text-[11px] text-[var(--color-text-secondary)]">{{ scopeSummary }}</span>
          <DownOutlined
            class="shrink-0 text-[10px] text-[var(--color-text-muted)] transition-transform duration-200"
            :class="scopeCollapsed ? '' : 'rotate-180'"
            aria-hidden="true"
          />
        </button>
        <div v-show="!scopeCollapsed" class="pt-2.5">
          <ContextBar
            v-model:mode="mode"
            v-model:model-id="modelId"
            v-model:tenant-id="tenantId"
            v-model:application-id="applicationId"
            :models="models"
            :tenants="tenants"
            :applications="applications"
          />
        </div>
      </div>

      <!-- ② 连接遥测：2×2 状态格（CONFIG / AUTHZ / PROVIDER / GENERATION） -->
      <div class="shrink-0 border-b border-[var(--color-border)] px-3.5 py-3">
        <p class="mb-2 mt-0 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">连接遥测 / Telemetry</p>
        <StatusStrip :config="config" :auth="auth" :provider="provider" :generation="generation" />
      </div>

      <!-- ③ 诊断面板：吃满剩余高度，内部 Tab 内容区独立滚动 -->
      <DiagnosticPanel
        v-model:tab="tab"
        class="min-h-0 flex-1"
        :events="events"
        :thinking-text="thinkingText"
        :thinking-reason="thinkingReason"
        :thinking-detail="thinkingDetail"
        :usage="usage"
        :params-summary="paramsSummary"
      />
    </div>
  </div>
</template>
