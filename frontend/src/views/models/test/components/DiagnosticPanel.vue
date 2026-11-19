<script setup lang="ts">
// 诊断次列：思考过程 / 事件 / 请求与用量 三个 Tab（设计文档 §3.2）。
// 只渲染 Provider 实际返回的内容与真实发生的事件；未返回/未执行显示明确空态，不编造数据。
import { computed, ref } from 'vue'
import type { TestEventItem } from '../api'

const tab = defineModel<'thinking' | 'events' | 'usage'>('tab', { default: 'thinking' })

const props = defineProps<{
  events: TestEventItem[]
  /** 最近一次助手回复的可见思考（reasoning_visible 增量拼接的连续文本；仅 Provider 实际返回内容）。 */
  thinkingText: string
  /** 无可见思考时的缺失原因分类（能力/参数/Provider 驱动，由父页计算）。 */
  thinkingReason: string
  thinkingDetail: string
  /** 最近一次请求的用量快照；null = 尚未执行调用。 */
  usage: {
    requestId: string
    httpStatus: string
    quality: 'actual' | 'estimated' | 'unknown'
    inputTokens: number | null
    outputTokens: number | null
    reasoningTokens: number | null
    note: string
  } | null
  /** 生效参数摘要行。 */
  paramsSummary: string
}>()

// 不同请求的 sequence 都从 1 开始，展开键须包含请求 ID。
const expanded = ref(new Set<string>())

function eventKey(requestId: string, seq: number): string {
  return `${requestId}:${seq}`
}

function toggleEvent(requestId: string, seq: number): void {
  const next = new Set(expanded.value)
  const key = eventKey(requestId, seq)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expanded.value = next
}

const hasEvents = computed(() => props.events.length > 0)
const hasThinking = computed(() => props.thinkingText.length > 0)
const qualityText = computed(() => ({
  unknown: 'unknown · 待核对',
  actual: 'actual · 可信',
  estimated: 'estimated · 估算',
})[props.usage?.quality ?? 'unknown'])
</script>

<template>
  <!-- 右栏统一卡第③区：无独立卡片外壳，吃满剩余高度；Tab 内容区独立滚动 -->
  <div class="flex min-h-0 flex-col">
    <a-tabs v-model:active-key="tab" size="small" class="shrink-0 px-2 pt-1 [&_.ant-tabs-nav]:mb-0 [&_.ant-tabs-tab]:text-[var(--color-text-muted)]! [&_.ant-tabs-tab-active_.ant-tabs-tab-btn]:text-[var(--color-text-primary)]! [&_.ant-tabs-ink-bar]:bg-[var(--color-tech-accent)]! [&_.ant-tabs-nav]:border-[var(--color-border)]!">
      <a-tab-pane key="thinking" tab="思考过程" />
      <a-tab-pane key="events">
        <template #tab>
          <!-- 事件计数徽标：有事件时一眼可见规模，无需切 Tab -->
          <span class="inline-flex items-center gap-1.5">
            事件
            <span
              v-if="events.length"
              class="inline-flex h-[15px] min-w-[15px] items-center justify-center rounded-full bg-[var(--color-tech-accent-subtle)] px-1 font-mono text-[10px] leading-none text-[var(--color-tech-accent)]"
            >{{ events.length > 99 ? '99+' : events.length }}</span>
          </span>
        </template>
      </a-tab-pane>
      <a-tab-pane key="usage" tab="请求与用量" />
    </a-tabs>

    <div class="min-h-0 flex-1 overflow-y-auto px-4 py-3">
      <!-- 思考过程：只呈现 Provider 实际返回的 reasoning 连续文本 -->
      <template v-if="tab === 'thinking'">
        <div v-if="hasThinking" class="space-y-2.5">
          <div class="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-3">
            <div class="mb-1.5 flex items-center gap-2 text-[10px] text-[var(--color-text-muted)]">
              <span class="rounded bg-[var(--color-tech-accent-subtle)] px-1.5 py-px font-mono text-[var(--color-tech-accent)]">reasoning_visible</span>
              <span>Provider 实际返回 · {{ thinkingText.length }} 字</span>
            </div>
            <p class="mb-0 whitespace-pre-wrap text-xs leading-relaxed text-[var(--color-text-secondary)]">{{ thinkingText }}</p>
          </div>
          <p class="mb-0 px-1 pt-1 text-[10px] leading-relaxed text-[var(--color-text-muted)]">
            仅展示 Provider 允许公开的 reasoning 摘要，不代表模型内部完整推理；正文与思考不串流。
          </p>
        </div>
        <div v-else class="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-4 text-center">
          <p class="m-0 text-xs font-medium text-[var(--color-text-secondary)]">{{ thinkingReason === '生成中' ? '等待可见思考过程' : '本次调用未返回可见思考过程' }}</p>
          <p class="mb-0 mt-1.5 text-[11px] leading-relaxed text-[var(--color-text-muted)]">
            原因判定：<span class="font-medium text-[var(--color-text-secondary)]">{{ thinkingReason }}</span> — {{ thinkingDetail }}
          </p>
          <p class="mb-0 mt-2 border-t border-[var(--color-border)] pt-2 text-[10px] leading-relaxed text-[var(--color-text-muted)]">
            reasoning 仅表示可启用深度思考；thinking_output 才表示预期可能返回可见过程，两者不等同
          </p>
        </div>
      </template>

      <!-- 事件：真实事件时间线，按服务端单调 sequence；单项可展开脱敏 payload -->
      <template v-else-if="tab === 'events'">
        <p v-if="!hasEvents" class="py-8 text-center text-xs text-[var(--color-text-muted)]">暂无事件 — 事件按服务端单调 sequence 展示</p>
        <div v-for="event in events" :key="eventKey(event.requestId, event.seq)" class="relative pb-3 pl-5 last:pb-0">
          <span
            class="absolute left-0 top-1.5 h-2 w-2 rounded-full ring-4 ring-[var(--color-bg-elevated)]"
            :class="{
              'bg-[var(--color-success)]': event.type === 'authz' || event.type === 'done',
              'bg-[var(--color-error)]': event.type === 'error',
              'bg-[var(--color-info)]': event.type === 'usage',
              'bg-[var(--color-border-strong)]': event.type === 'status' || event.type === 'reasoning_visible' || event.type === 'answer_delta',
            }"
            aria-hidden="true"
          />
          <span v-if="event !== events[events.length - 1]" class="absolute bottom-0 left-[3.5px] top-4 w-px bg-[var(--color-border)]" aria-hidden="true" />
          <button
            type="button"
            class="w-full cursor-pointer rounded-[var(--radius-sm)] p-1 text-left transition-colors hover:bg-[var(--color-bg-subtle)]"
            @click="toggleEvent(event.requestId, event.seq)"
          >
            <span class="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span class="font-mono text-[10px] text-[var(--color-text-muted)]">#{{ String(event.seq).padStart(2, '0') }}</span>
              <span class="font-mono text-[10px] text-[var(--color-text-muted)]">{{ new Date(event.at).toLocaleTimeString('zh-CN', { hour12: false }) }}</span>
              <span class="font-mono text-[10px] font-medium text-[var(--color-text-secondary)]">{{ event.type }}</span>
              <span class="min-w-0 flex-1 truncate text-[11px] text-[var(--color-text-secondary)]">{{ event.summary }}</span>
            </span>
            <pre v-if="expanded.has(eventKey(event.requestId, event.seq))" class="mt-1.5 overflow-x-auto rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-2 font-mono text-[11px] leading-relaxed text-[var(--color-text-secondary)]">{{ JSON.stringify(event.payload, null, 2) }}</pre>
          </button>
        </div>
        <p v-if="hasEvents" class="mb-0 mt-3 border-t border-[var(--color-border)] pt-2.5 text-[10px] leading-relaxed text-[var(--color-text-muted)]">
          answer_delta 逐片下发、按服务端序号去重展示；断线重连按最后 sequence 续传，不会重复插入。
        </p>
      </template>

      <!-- 请求与用量：真实计量；未知值显示「未知」，不显示 0（设计文档 §3.2） -->
      <template v-else>
        <div v-if="!usage" class="py-8 text-center text-xs text-[var(--color-text-muted)]">尚未执行调用</div>
        <template v-else>
          <div class="mb-3 grid grid-cols-3 gap-2">
            <div v-for="stat in [
              { label: 'HTTP 状态', value: usage.httpStatus },
              { label: '输入 Token', value: usage.inputTokens == null ? '未知' : usage.inputTokens },
              { label: '输出 Token', value: usage.outputTokens == null ? '未知' : usage.outputTokens },
            ]" :key="stat.label" class="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-2.5">
              <p class="m-0 text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">{{ stat.label }}</p>
              <p class="mb-0 mt-1 font-mono text-[14px] font-medium text-[var(--color-text-primary)]">{{ stat.value }}</p>
            </div>
          </div>
          <div class="flex items-start justify-between gap-4 border-b border-[var(--color-border)] py-2">
            <span class="shrink-0 text-xs text-[var(--color-text-muted)]">请求 ID</span>
            <span class="break-all text-right font-mono text-xs text-[var(--color-text-secondary)]">{{ usage.requestId }}</span>
          </div>
          <div class="flex items-start justify-between gap-4 border-b border-[var(--color-border)] py-2">
            <span class="shrink-0 text-xs text-[var(--color-text-muted)]">推理 Token</span>
            <span class="text-right font-mono text-xs text-[var(--color-text-secondary)]">{{ usage.reasoningTokens == null ? '未返回' : usage.reasoningTokens }}</span>
          </div>
          <div class="flex items-start justify-between gap-4 border-b border-[var(--color-border)] py-2">
            <span class="shrink-0 text-xs text-[var(--color-text-muted)]">用量质量</span>
            <span class="text-right text-xs font-medium" :class="usage.quality === 'unknown' ? 'text-[var(--color-warning)]' : 'text-[var(--color-success)]'">{{ qualityText }}</span>
          </div>
          <div class="flex items-start justify-between gap-4 py-2">
            <span class="shrink-0 text-xs text-[var(--color-text-muted)]">生效参数</span>
            <span class="text-right text-[11px] leading-relaxed text-[var(--color-text-secondary)]">{{ paramsSummary }}</span>
          </div>
          <p
            v-if="usage.note"
            class="mb-0 mt-2 rounded-[var(--radius-md)] border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/5 px-3 py-2 text-[11px] leading-relaxed text-[var(--color-warning)]"
          >{{ usage.note }}</p>
        </template>
      </template>
    </div>
  </div>
</template>
