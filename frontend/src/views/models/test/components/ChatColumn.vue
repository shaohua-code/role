<script setup lang="ts">
// 对话主列：消息流（用户 / 助手流式 / 探针报告卡）+ 输入区。
// 正文与可见思考是两条独立流（设计文档 §3.2）；停止后的答案标记为「已中止」，不伪装完成。
// 渲染规格对齐主流 AI 对话产品：markdown-it + highlight.js 富 Markdown、可折叠思考块、
// 三点加载动画、示例 prompt 空状态、贴底跟随 + 回到底部悬浮按钮（用户上滚即暂停跟随）。
import { computed, nextTick, reactive, ref, watch } from 'vue'
import {
  ArrowDownOutlined, CheckOutlined, CopyOutlined, DownOutlined, EditOutlined,
  RedoOutlined, SendOutlined, StopOutlined, ThunderboltOutlined,
} from '@/plugins/icons'
import StatusDot from '../../components/StatusDot.vue'
import { MD_BODY_CLASS, renderMarkdown } from '../markdown'
import type { TestChatMessage, TestModelSummary } from '../api'

const props = defineProps<{
  mode: 'app' | 'platform'
  selectedModel: TestModelSummary | null
  messages: TestChatMessage[]
  /** 发送禁用原因；空串 = 可发送。 */
  sendDisabledReason: string
  sending: boolean
  streaming: boolean
  contextTurnCount: number
}>()

const emit = defineEmits<{
  send: [text: string]
  stop: []
  /** 编辑重发：从该轮截断后续上下文后重发。 */
  resend: [index: number, text: string]
  regenerate: [index: number]
}>()

const inputText = ref('')
const editingIndex = ref(-1)
const editText = ref('')
const scrollHost = ref<HTMLElement | null>(null)

// 空状态示例 prompt：点击只填入输入框（不自动发送，避免误触发真实外呼费用）。
const EXAMPLE_PROMPTS = [
  { title: '解释概念', text: '用通俗的语言解释什么是三级下发，并举一个实际例子' },
  { title: '生成代码', text: '用 Python 写一个带重试与超时控制的 HTTP 请求函数，并附单元测试' },
  { title: '结构化输出', text: '列出 OAuth 2.0 四种授权模式的对比表格，含适用场景与安全性' },
  { title: '排查问题', text: '我的接口偶发 429 限流，帮我梳理排查思路和应对方案' },
]

function fillExample(text: string): void {
  inputText.value = text
}

const canSend = computed(() => !props.sendDisabledReason && inputText.value.trim().length > 0 && inputText.value.length <= 16000 && !props.sending)
const placeholder = computed(() => {
  if (!props.selectedModel) return '请先选择模型'
  if (props.sendDisabledReason) return props.sendDisabledReason
  return '输入消息，Enter 发送，Shift + Enter 换行'
})

function submit(): void {
  if (!canSend.value) return
  emit('send', inputText.value.trim())
  inputText.value = ''
}

function startEdit(index: number): void {
  editingIndex.value = index
  editText.value = props.messages[index]?.text ?? ''
}

function commitEdit(): void {
  const text = editText.value.trim()
  if (!text) return
  emit('resend', editingIndex.value, text)
  editingIndex.value = -1
  editText.value = ''
}

// ── 复制（答案 / 请求 ID / 代码块），带「已复制」瞬时反馈 ─────────────────────
const copiedKey = ref('')
let copiedTimer: ReturnType<typeof setTimeout> | null = null

function markCopied(key: string): void {
  copiedKey.value = key
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => { copiedKey.value = '' }, 1600)
}

function copyText(text: string, key: string): void {
  void navigator.clipboard?.writeText(text).then(() => markCopied(key))
}

// Markdown 代码块复制按钮在 v-html 内，走消息区 click 事件委托；文案就地反馈。
function onContentClick(event: MouseEvent): void {
  const target = (event.target as HTMLElement).closest?.('[data-md-copy]') as HTMLElement | null
  if (!target) return
  const code = target.closest('[data-md-block]')?.querySelector('code')?.textContent ?? ''
  void navigator.clipboard?.writeText(code)
  target.textContent = '已复制'
  setTimeout(() => { target.textContent = '复制' }, 1600)
}

// ── 思考块折叠：流式中默认展开，完成后默认折叠；用户点击后以其为准 ───────────
const thinkingOpen = reactive<Record<string, boolean>>({})

function isThinkingOpen(message: TestChatMessage): boolean {
  return thinkingOpen[message.id] ?? (message.status === 'streaming')
}

function toggleThinking(message: TestChatMessage): void {
  thinkingOpen[message.id] = !isThinkingOpen(message)
}

// 思考阶段判定：仍在生成且正文未开始（思考先行是 Provider 的实际行为顺序）。
function isThinkingPhase(message: TestChatMessage): boolean {
  return message.status === 'streaming' && !message.answer
}

// ── Markdown 正文：流式渲染 + 末尾光标 ───────────────────────────────────────
function renderedAnswer(message: TestChatMessage): string {
  return renderMarkdown(message.answer, { cursor: message.status === 'streaming' && Boolean(message.answer) })
}

// 消息时间戳（HH:MM:SS，24 小时制）。
function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', { hour12: false })
}

// ── 智能滚动：贴底跟随 / 上滚暂停 / 悬浮回底 ─────────────────────────────────
const atBottom = ref(true)

function onScroll(): void {
  const host = scrollHost.value
  if (!host) return
  atBottom.value = host.scrollHeight - host.scrollTop - host.clientHeight < 48
}

function scrollToBottom(smooth = false): void {
  const host = scrollHost.value
  if (!host) return
  host.scrollTo({ top: host.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
}

async function jumpToBottom(): Promise<void> {
  atBottom.value = true
  await nextTick()
  scrollToBottom(true)
}

// 流式增量（思考/正文/状态）时若用户仍在底部则跟随；新消息出现时强制回底。
watch(() => props.messages.map(m => `${m.id}:${m.answer.length}:${m.thinking.length}:${m.status}`).join('|'), async () => {
  await nextTick()
  if (atBottom.value) scrollToBottom()
})
watch(() => props.messages.length, async () => {
  await nextTick()
  atBottom.value = true
  scrollToBottom(true)
})

// 助手消息状态 chip 语言（设计文档 §4：中止/失败不伪装成完成）。
function statusChip(message: TestChatMessage): { tone: 'ok' | 'warn' | 'err' | 'hollow'; text: string } {
  switch (message.status) {
    case 'streaming': return { tone: 'hollow', text: '生成中' }
    case 'done': return { tone: 'ok', text: '已完成' }
    case 'aborted': return { tone: 'warn', text: '已中止' }
    default: return { tone: 'err', text: '失败' }
  }
}

const STATUS_TEXT_CLASS: Record<string, string> = {
  ok: 'text-[var(--color-success)]',
  warn: 'text-[var(--color-warning)]',
  err: 'text-[var(--color-error)]',
  hollow: 'text-[var(--color-text-muted)]',
}

// 头像字母（模型展示名前两字符）。
const avatarInitials = computed(() => (props.selectedModel?.display_name ?? '模型').slice(0, 2).toUpperCase())

// 用量摘要（元数据段）：↑输入 ↓输出 实测/估算 耗时（空格分隔保持紧凑）。
function usageText(message: TestChatMessage): string {
  const usage = message.usage
  if (!usage) return ''
  const parts = [
    `↑${usage.inputTokens ?? '?'}`,
    `↓${usage.outputTokens ?? '?'}`,
    usage.quality === 'actual' ? '实测' : '估算',
  ]
  if (usage.totalMs) parts.push(`${(usage.totalMs / 1000).toFixed(1)}s`)
  return parts.join(' ')
}

// 结束原因中文映射（Provider finish_reason 常见值）；本端语义（aborted 等）保留原值。
function finishReasonLabel(reason: string): string {
  return ({ stop: '完成', length: '长度截断', tool_calls: '工具调用', content_filter: '内容过滤' } as Record<string, string>)[reason] ?? reason
}

// 请求 ID 缩短展示（前 10 后 4）；悬停 title 与点击复制均为完整值。
function shortId(id: string): string {
  return id.length > 18 ? `${id.slice(0, 10)}…${id.slice(-4)}` : id
}
</script>

<template>
  <!-- lg+ 吃满分栏 Pane 高度；窄屏高度由父页固定类（h-[560px]）决定 -->
  <div class="flex min-h-0 flex-col overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)] lg:h-full">
    <div class="flex min-h-12 items-center justify-between gap-3 border-b border-[var(--color-border)] px-4">
      <div class="flex min-w-0 items-center gap-2.5">
        <span class="h-2 w-2 shrink-0 rounded-full bg-[var(--color-tech-accent)]" aria-hidden="true" />
        <span class="shrink-0 text-[13px] font-semibold text-[var(--color-text-primary)]">{{ mode === 'app' ? '对话' : '连接测试' }}</span>
        <span class="hidden truncate text-[11px] text-[var(--color-text-muted)] sm:inline">刷新后清除 · 仅存当前浏览器</span>
      </div>
      <span class="shrink-0 font-mono text-[11px] tabular-nums text-[var(--color-text-muted)]">{{ mode === 'app' ? `${messages.filter(m => m.role === 'user').length} 轮` : `${messages.filter(m => m.role === 'probe').length} 次` }}</span>
    </div>

    <!-- 消息滚动区：外层 relative 承载「回到底部」悬浮按钮 -->
    <div class="relative min-h-0 flex-1">
      <div ref="scrollHost" class="h-full overflow-y-auto px-4 py-5 sm:px-6" @scroll.passive="onScroll" @click="onContentClick">
        <!-- 空状态：未选模型给引导；已选模型给示例 prompt 卡片（点击填入，不自动发送） -->
        <div v-if="!messages.length" class="mx-auto flex min-h-full max-w-2xl flex-col items-center justify-center gap-4 py-6">
          <template v-if="!selectedModel">
            <span class="flex h-12 w-12 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--color-bg-subtle)] text-xl text-[var(--color-text-secondary)] ring-1 ring-[var(--color-border)]" aria-hidden="true"><ThunderboltOutlined /></span>
            <p class="m-0 text-[14px] font-semibold text-[var(--color-text-primary)]">选择模型开始测试</p>
            <p class="m-0 max-w-sm text-center text-xs leading-relaxed text-[var(--color-text-muted)]">在上方选择模型与应用后，可以用连续对话复现调用结果。</p>
          </template>
          <template v-else>
            <div class="flex flex-col items-center gap-2 text-center">
              <span class="flex h-12 w-12 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--color-tech-accent-subtle)] font-mono text-sm font-bold text-[var(--color-tech-accent)]">{{ avatarInitials }}</span>
              <p class="m-0 text-[15px] font-semibold text-[var(--color-text-primary)]">{{ mode === 'app' ? `与 ${selectedModel.display_name} 对话` : `验证 ${selectedModel.display_name} 的连接` }}</p>
              <p v-if="mode === 'platform'" class="m-0 max-w-md text-xs leading-relaxed text-[var(--color-text-muted)]">点击上方“连接测试”，查看凭据、网络与 Provider 响应的分阶段结果。</p>
              <p v-else-if="!sendDisabledReason" class="m-0 max-w-md text-xs leading-relaxed text-[var(--color-text-muted)]">每次发送都会真实调用 Provider；已完成的轮次会作为下一轮上下文。</p>
              <p v-if="mode === 'app' && sendDisabledReason" class="m-0 max-w-md text-xs text-[var(--color-warning)]">{{ sendDisabledReason }}</p>
            </div>
            <div v-if="mode === 'app'" class="mt-2 grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
              <button
                v-for="example in EXAMPLE_PROMPTS"
                :key="example.title"
                type="button"
                :disabled="Boolean(sendDisabledReason) || sending"
                class="group flex cursor-pointer flex-col items-start gap-1 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2.5 text-left transition-colors hover:border-[var(--color-tech-accent)] hover:bg-[var(--color-tech-accent-subtle)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-tech-accent)] disabled:cursor-not-allowed disabled:opacity-50"
                @click="fillExample(example.text)"
              >
                <span class="text-xs font-medium text-[var(--color-text-primary)]">{{ example.title }}</span>
                <span class="line-clamp-2 text-[11px] leading-relaxed text-[var(--color-text-muted)] group-hover:text-[var(--color-text-secondary)]">{{ example.text }}</span>
              </button>
            </div>
          </template>
        </div>

        <template v-for="(message, index) in messages" :key="message.id">
          <!-- 用户消息：右对齐浮层气泡 + 终端角标 -->
          <div v-if="message.role === 'user'" class="group mb-5 flex flex-col items-end">
            <template v-if="editingIndex === index">
              <div class="w-full max-w-[85%] rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-bg-subtle)] p-3 [&_.ant-input]:border-none! [&_.ant-input]:bg-transparent! [&_.ant-input]:text-[var(--color-text-primary)]! [&_.ant-input]:placeholder:text-[var(--color-text-muted)]! [&_.ant-input:focus]:shadow-none!">
                <a-textarea v-model:value="editText" :auto-size="{ minRows: 2, maxRows: 6 }" aria-label="编辑本轮输入" />
                <p class="mb-2 mt-1 text-[11px] text-[var(--color-warning)]">重发将从该轮截断后续上下文</p>
                <div class="flex justify-end gap-2">
                  <a-button size="small" @click="editingIndex = -1">取消</a-button>
                  <a-button size="small" type="primary" @click="commitEdit">重发</a-button>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="mb-0.5 flex items-center gap-2">
                <span class="font-mono text-[9px] tracking-[0.18em] text-[var(--color-text-muted)]">YOU</span>
                <span class="font-mono text-[10px] text-[var(--color-text-muted)]">{{ formatTime(message.createdAt) }}</span>
              </div>
              <div class="max-w-[92%] break-words whitespace-pre-wrap rounded-[var(--radius-lg)] rounded-br-sm border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3.5 py-2.5 text-[13.5px] leading-relaxed text-[var(--color-text-primary)] sm:max-w-[85%]">{{ message.text }}</div>
              <div class="mt-1 flex items-center gap-1.5 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
                <button type="button" class="inline-flex h-6 cursor-pointer items-center gap-1 rounded-md px-2 text-[11px] transition-colors" :class="copiedKey === `u-${message.id}` ? 'bg-[var(--color-tech-accent-subtle)] text-[var(--color-tech-accent)]' : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-tech-accent)]'" @click="copyText(message.text, `u-${message.id}`)">
                  <CopyOutlined class="text-[11px]" aria-hidden="true" />
                  {{ copiedKey === `u-${message.id}` ? '已复制' : '复制' }}
                </button>
                <button type="button" class="inline-flex h-6 cursor-pointer items-center gap-1 rounded-md px-2 text-[11px] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-tech-accent)] disabled:cursor-not-allowed disabled:opacity-40" :disabled="sending" @click="startEdit(index)">
                  <EditOutlined class="text-[11px]" aria-hidden="true" />
                  编辑重发
                </button>
              </div>
            </template>
          </div>

          <!-- 探针报告卡：分阶段结果 -->
          <div v-else-if="message.role === 'probe'" class="mb-5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-4">
            <div class="mb-2.5 flex flex-wrap items-center gap-2">
              <ThunderboltOutlined class="text-[var(--color-text-secondary)]" />
              <span class="text-[13px] font-semibold text-[var(--color-text-primary)]">连接探针报告</span>
              <span v-if="message.probe?.pending" class="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-2 py-px text-[11px] text-[var(--color-text-muted)]">测试中…</span>
              <template v-else>
                <StatusDot
                  :tone="message.probe?.report.verdict === 'ok' ? 'ok' : 'err'"
                  :text="message.probe?.report.verdict === 'ok' ? '连接可用' : '连接不可用'"
                />
              </template>
            </div>
            <table class="w-full">
              <tbody>
                <tr v-for="(stage, stageIndex) in message.probe?.report.stages" :key="stage.name" class="border-b border-[var(--color-border)] last:border-0">
                  <td class="py-1.5 pr-3 text-xs text-[var(--color-text-secondary)]">{{ stageIndex + 1 }}. {{ stage.name }}</td>
                  <td class="py-1.5 pr-3">
                    <StatusDot :tone="stage.status === 'ok' ? 'ok' : 'err'" :text="stage.status === 'ok' ? '通过' : '失败'" />
                  </td>
                  <td class="py-1.5 text-right font-mono text-[11px] tabular-nums text-[var(--color-text-muted)]">{{ stage.latency_ms != null ? `${stage.latency_ms}ms` : '—' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="message.probe?.report.error" class="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[var(--radius-md)] border border-[var(--color-error)]/30 bg-[var(--color-error)]/5 px-3 py-2 text-xs">
              <span class="font-medium text-[var(--color-error)]">{{ message.probe.report.error.code }}</span>
              <span class="text-[var(--color-text-secondary)]">{{ message.probe.report.error.message }}</span>
              <span v-if="message.probe.report.error.retry_after_seconds" class="rounded-full border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/5 px-2 py-px text-[11px] text-[var(--color-warning)]">
                建议 {{ message.probe.report.error.retry_after_seconds }}s 后重试
              </span>
            </div>
            <div class="mt-2.5 flex flex-wrap items-center gap-3 font-mono text-[11px] text-[var(--color-text-muted)]">
              <span>test_id: {{ message.probe?.report.test_id }}</span>
              <button type="button" class="cursor-pointer font-mono text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-tech-accent)]" :class="copiedKey === `probe-${message.id}` ? 'text-[var(--color-tech-accent)]' : ''" title="点击复制请求 ID" @click="copyText(message.probe?.report.request_id ?? '', `probe-${message.id}`)">
                req: {{ copiedKey === `probe-${message.id}` ? '已复制' : message.probe?.report.request_id }}
              </button>
            </div>
          </div>

          <!-- 助手消息：头像行 → 思考块（折叠）→ 错误横幅 → Markdown 正文 → 操作行 -->
          <div v-else class="mb-6">
            <div class="mb-2 flex items-center gap-2">
              <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--radius-md)] border border-[var(--color-border-strong)] bg-[var(--color-tech-accent-subtle)] font-mono text-[10px] font-bold text-[var(--color-tech-accent)]" aria-hidden="true">{{ avatarInitials }}</span>
              <span class="text-xs font-semibold text-[var(--color-text-primary)]">{{ selectedModel?.display_name ?? '模型' }}</span>
              <StatusDot
                :tone="statusChip(message).tone"
                :text="statusChip(message).text"
                :text-class="STATUS_TEXT_CLASS[statusChip(message).tone]"
              />
              <span class="ml-auto font-mono text-[10px] text-[var(--color-text-muted)]">{{ formatTime(message.createdAt) }}</span>
            </div>

            <!-- 内容块统一挂灰色左边线，构成会话流视觉锚点 -->
            <div class="border-l-2 border-[var(--color-border-strong)] pl-3">

            <!-- 可见思考块：Provider 实际返回的 reasoning，流式展开 / 完成折叠（对齐主流深度思考交互） -->
            <div v-if="message.thinking" class="mb-3 overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-subtle)]">
              <button
                type="button"
                class="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-[var(--color-row-hover)]"
                @click="toggleThinking(message)"
              >
                <span
                  class="text-xs font-medium"
                  :class="isThinkingPhase(message) ? 'text-[var(--color-text-secondary)]' : 'text-[var(--color-text-muted)]'"
                >{{ isThinkingPhase(message) ? '深度思考中…' : '已深度思考' }}</span>
                <span v-if="isThinkingPhase(message)" class="inline-flex items-center gap-0.5" aria-hidden="true">
                  <span v-for="dot in 3" :key="dot" class="h-1 w-1 animate-bounce rounded-full bg-[var(--color-tech-accent)]" :class="dot === 2 ? '[animation-delay:120ms]' : dot === 3 ? '[animation-delay:240ms]' : ''" />
                </span>
                <span v-else class="font-mono text-[10px] text-[var(--color-text-muted)]">{{ message.thinking.length }} 字</span>
                <DownOutlined
                  class="ml-auto text-[10px] text-[var(--color-text-muted)] transition-transform duration-200"
                  :class="isThinkingOpen(message) ? 'rotate-180' : ''"
                  aria-hidden="true"
                />
              </button>
              <div v-show="isThinkingOpen(message)" class="border-t border-[var(--color-border)] px-3 py-2.5">
                <p class="m-0 whitespace-pre-wrap text-xs leading-relaxed text-[var(--color-text-secondary)]">{{ message.thinking }}<span v-if="isThinkingPhase(message)" class="ml-0.5 inline-block h-3 w-[6px] animate-[tech-blink_1.1s_steps(1)_infinite] bg-[var(--color-tech-accent)]" aria-hidden="true" /></p>
              </div>
            </div>

            <!-- 错误横幅：分类展示（凭据/限流/超时/上游故障/授权拒绝） -->
            <div
              v-if="message.error"
              class="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[var(--radius-md)] border px-3 py-2 text-xs"
              :class="message.error.code === 'authz_denied' || message.error.code === 'credential_unavailable' || message.error.code === 'rate_limited'
                ? 'border-[var(--color-warning)]/40 bg-[var(--color-warning)]/5'
                : 'border-[var(--color-error)]/30 bg-[var(--color-error)]/5'"
              role="alert"
            >
              <span class="font-mono font-medium" :class="message.error.code === 'authz_denied' || message.error.code === 'credential_unavailable' || message.error.code === 'rate_limited' ? 'text-[var(--color-warning)]' : 'text-[var(--color-error)]'">{{ message.error.code }}</span>
              <span class="text-[var(--color-text-secondary)]">{{ message.error.message }}</span>
              <span v-if="message.error.retryAfterSeconds" class="rounded-full border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/5 px-2 py-px text-[11px] text-[var(--color-warning)]">
                建议 {{ message.error.retryAfterSeconds }}s 后重试
              </span>
            </div>

            <!-- 正文：markdown-it 富渲染（标题/列表/任务列表/表格/代码高亮/自动链接），流式含尾随光标 -->
            <!-- eslint-disable-next-line vue/no-v-html -- markdown-it html:false 全量转义，hljs 输出仅 class 与转义文本，无注入面 -->
            <div v-if="message.answer" :class="MD_BODY_CLASS" v-html="renderedAnswer(message)" />
            <div v-else-if="message.status === 'streaming' && !message.error && !message.thinking" class="flex items-center gap-2.5 py-1">
              <span class="inline-flex items-center gap-1" aria-hidden="true">
                <span v-for="dot in 3" :key="dot" class="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--color-tech-accent)]" :class="dot === 2 ? '[animation-delay:120ms]' : dot === 3 ? '[animation-delay:240ms]' : ''" />
              </span>
              <span class="text-[13px] text-[var(--color-text-secondary)]">正在思考…</span>
            </div>
            <p v-else-if="!message.error" class="m-0 text-[13px] text-[var(--color-text-muted)]">（本次调用未返回正文）</p>

            <!-- 完成态操作行：左侧动作 ghost 钮（重新生成/复制），右侧元数据 chips（结束原因/用量/请求 ID）一行收纳 -->
            <div v-if="message.status !== 'streaming' && (message.answer || message.usage || message.error)" class="mt-2.5 flex flex-wrap items-center gap-1.5">
              <button
                v-if="index === messages.length - 1 && mode === 'app'"
                type="button"
                class="inline-flex h-6 cursor-pointer items-center gap-1 rounded-md px-2 text-[11px] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-tech-accent)] disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="sending"
                @click="emit('regenerate', index)"
              >
                <RedoOutlined class="text-[11px]" aria-hidden="true" />
                重新生成
              </button>
              <button
                v-if="message.answer"
                type="button"
                class="inline-flex h-6 cursor-pointer items-center gap-1 rounded-md px-2 text-[11px] transition-colors"
                :class="copiedKey === `a-${message.id}` ? 'bg-[var(--color-tech-accent-subtle)] text-[var(--color-tech-accent)]' : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-tech-accent)]'"
                @click="copyText(message.answer, `a-${message.id}`)"
              >
                <CopyOutlined class="text-[11px]" aria-hidden="true" />
                {{ copiedKey === `a-${message.id}` ? '已复制' : '复制' }}
              </button>
              <!-- 元数据段：结束原因 + 用量合并为一段轻文字（不带胶囊），仅请求 ID 保留可交互 chip -->
              <div class="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-x-2 gap-y-1">
                <span
                  v-if="message.finishReason || message.usage"
                  class="truncate text-[11px] tabular-nums text-[var(--color-text-muted)]"
                  :title="message.finishReason ? `结束原因：${message.finishReason}` : ''"
                >{{ [message.finishReason ? finishReasonLabel(message.finishReason) : '', message.usage ? usageText(message) : ''].filter(Boolean).join(' · ') }}</span>
                <!-- 请求 ID chip：缩短展示，悬停看全文，点击复制 -->
                <button
                  v-if="message.requestId"
                  type="button"
                  class="inline-flex h-6 max-w-[220px] shrink-0 cursor-pointer items-center gap-1 rounded-full bg-[var(--color-bg-subtle)] px-2.5 font-mono text-[11px] transition-colors"
                  :class="copiedKey === `r-${message.id}` ? 'text-[var(--color-tech-accent)]' : 'text-[var(--color-text-secondary)] hover:text-[var(--color-tech-accent)]'"
                  :title="`请求 ID：${message.requestId}（点击复制）`"
                  @click="copyText(message.requestId, `r-${message.id}`)"
                >
                  <CopyOutlined v-if="copiedKey !== `r-${message.id}`" class="shrink-0 text-[10px]" aria-hidden="true" />
                  <CheckOutlined v-else class="shrink-0 text-[10px]" aria-hidden="true" />
                  <span class="truncate">{{ copiedKey === `r-${message.id}` ? '已复制' : shortId(message.requestId) }}</span>
                </button>
              </div>
            </div>
            </div>
          </div>
        </template>
      </div>

      <!-- 回到底部悬浮按钮：用户上滚后出现 -->
      <button
        v-show="!atBottom"
        type="button"
        aria-label="回到底部"
        class="absolute bottom-3 right-4 flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] shadow-[var(--shadow-md)] transition-colors hover:border-[var(--color-tech-accent)] hover:text-[var(--color-tech-accent)]"
        @click="jumpToBottom"
      >
        <ArrowDownOutlined />
      </button>
    </div>

    <!-- 输入区（应用对话模式）：白底输入卡 + 聚焦科技蓝描边，提示合并为一行降噪 -->
    <div v-if="mode === 'app'" class="border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 pb-3.5 pt-3 sm:px-6">
      <div
        class="rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] shadow-[var(--shadow-sm)] transition-[border-color,box-shadow] focus-within:border-[var(--color-tech-accent)] focus-within:shadow-[0_0_0_3px_var(--color-tech-accent-subtle)] [&_.ant-input]:border-none! [&_.ant-input]:bg-transparent! [&_.ant-input]:text-[13.5px]! [&_.ant-input]:text-[var(--color-text-primary)]! [&_.ant-input]:placeholder:text-[var(--color-text-muted)]! [&_.ant-input:focus]:shadow-none!"
      >
        <a-textarea
          v-model:value="inputText"
          :auto-size="{ minRows: 2, maxRows: 6 }"
          :maxlength="16000"
          :disabled="Boolean(sendDisabledReason) || sending"
          :placeholder="placeholder"
          aria-label="测试消息输入"
          class="px-3.5! pt-2.5!"
          @keydown.enter.exact.prevent="submit"
        />
        <!-- 底部操作行：上下文/快捷键提示（左）+ 字数与动作（右），原两行灰字合并为一行 -->
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 px-3.5 pb-2.5">
          <span class="min-w-0 truncate text-[11px] text-[var(--color-text-muted)]">{{ sendDisabledReason || `携带最近 ${contextTurnCount} 轮上下文 · Enter 发送 · Shift + Enter 换行` }}</span>
          <div class="ml-auto flex shrink-0 items-center gap-2">
            <span class="font-mono text-[11px] tabular-nums" :class="inputText.length > 15000 ? 'text-[var(--color-warning)]' : 'text-[var(--color-text-muted)]'">{{ inputText.length }}/16000</span>
            <!-- 停止：流式中断 -->
            <button v-if="streaming" type="button" class="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--color-error)]/60 px-3 text-xs text-[var(--color-error)] transition-colors hover:bg-[var(--color-error)]/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-error)]" @click="emit('stop')">
              <StopOutlined />
              停止
            </button>
            <!-- 发送：主题科技蓝实心（用户标注「按钮颜色适应主题」），hover 提亮；sending 且未流式时显示「发送中…」；tooltip 告知真实调用费用 -->
            <a-tooltip title="发送将真实调用 Provider 并按实际用量计入模型用量账目">
              <button type="button" class="inline-flex h-8 items-center gap-1.5 rounded-md bg-[var(--color-tech-accent)] px-3.5 text-xs font-medium text-white transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-tech-accent)] disabled:cursor-not-allowed disabled:opacity-40" :disabled="!canSend" @click="submit">
                <SendOutlined />
                {{ sending && !streaming ? '发送中…' : '发送' }}
              </button>
            </a-tooltip>
          </div>
        </div>
      </div>
    </div>

    <!-- 平台连接模式：探针动作统一在顶部工具条，此处仅保留模式提示 -->
    <div v-else class="border-t border-[var(--color-border)] px-4 py-3">
      <p class="m-0 text-xs leading-relaxed text-[var(--color-text-muted)]">
        平台连接模式不发送对话；请使用顶部「连接测试」执行探针（凭据解析 → 网络 / TLS → Provider 响应）。
      </p>
    </div>
  </div>
</template>
