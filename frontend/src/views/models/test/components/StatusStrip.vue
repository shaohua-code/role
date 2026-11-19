<script setup lang="ts">
// 状态遥测（右栏信息面板内）：四段状态（CONFIG/AUTHZ/PROVIDER/GENERATION）2×2 排布。
// 未测试 ≠ 成功；成功/失败/告警=静态语义色点，未测试/不适用=空心描边降噪。
// 探针动作已上移至页面顶部工具条，本组件只负责状态呈现。

/** 单段状态：state 为色点语义，hint 悬停给出原因（如缺失层级）。 */
export interface StripCell {
  state: 'pending' | 'ok' | 'fail' | 'warn' | 'na'
  hint?: string
}

const props = defineProps<{
  config: StripCell
  auth: StripCell
  provider: StripCell
  generation: StripCell
}>()

// 各段在不同状态下的展示词；na=平台连接模式下授权不适用。
const LABELS: Record<'config' | 'auth' | 'provider' | 'generation', Record<StripCell['state'], string>> = {
  config: { ok: '有效', fail: '失败', warn: '无法判定', pending: '未测试', na: '—' },
  auth: { ok: '可用', fail: '不可用', warn: '无法判定', pending: '未测试', na: '不适用' },
  provider: { ok: '可达', fail: '不可达', warn: '无法判定', pending: '未测试', na: '—' },
  generation: { ok: '成功', fail: '未成功', warn: '未完成 / 已中止', pending: '未测试', na: '—' },
}

const CELLS = [
  { key: 'config', code: 'CONFIG', label: '配置' },
  { key: 'auth', code: 'AUTHZ', label: '授权' },
  { key: 'provider', code: 'PROVIDER', label: 'Provider' },
  { key: 'generation', code: 'GENERATION', label: '本次生成' },
] as const

function cellOf(key: (typeof CELLS)[number]['key']): StripCell {
  return props[key]
}

// 标签悬停提示：中文模块名 + 状态原因（hint 可能为空则只显示模块名）。
function tooltipOf(cell: (typeof CELLS)[number]): string {
  const hint = cellOf(cell.key).hint
  return hint ? `${cell.label} · ${hint}` : cell.label
}

// 状态点四态：静态语义色，无呼吸/发光；未测试/不适用=空心描边。
function dotClass(state: StripCell['state']): string {
  if (state === 'ok') return 'bg-[var(--color-success)]'
  if (state === 'fail') return 'bg-[var(--color-error)]'
  if (state === 'warn') return 'bg-[var(--color-warning)]'
  return 'border border-[var(--color-border-strong)] bg-transparent'
}

// 状态词配色：成功绿、失败红、告警琥珀、未测试/不适用降噪。
function wordClass(state: StripCell['state']): string {
  if (state === 'ok') return 'text-[var(--color-success)]'
  if (state === 'fail') return 'text-[var(--color-error)]'
  if (state === 'warn') return 'text-[var(--color-warning)]'
  return 'text-[var(--color-text-muted)]'
}
</script>

<template>
  <div class="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-border)]">
    <div
      v-for="cell in CELLS"
      :key="cell.key"
      class="flex flex-col justify-center gap-1 bg-[var(--color-bg-elevated)] px-3 py-2.5"
    >
      <!-- 模块标签：英文 mono 编码，悬停 tooltip 展示中文名与状态原因 -->
      <a-tooltip :title="tooltipOf(cell)">
        <span class="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">{{ cell.code }}</span>
      </a-tooltip>
      <div class="flex items-center gap-2">
        <span class="h-2 w-2 shrink-0 rounded-full" :class="dotClass(cellOf(cell.key).state)" aria-hidden="true" />
        <span class="text-[13px] font-semibold" :class="wordClass(cellOf(cell.key).state)">{{ LABELS[cell.key][cellOf(cell.key).state] }}</span>
      </div>
    </div>
  </div>
</template>
