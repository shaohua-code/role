<script setup lang="ts">
// 模型页状态点：黑白灰体系内的语义点缀 —— 8px 圆点 + 文本。
// 取代彩色 a-tag 承载状态语言（P362/P388 教训：自定义样式不走 a-tag，原生 span + token 更稳）。
withDefaults(defineProps<{
  /** ok=语义绿 / warn=语义琥珀 / err=语义红 / off=中性灰实心 / muted=浅灰实心 / hollow=空心 */
  tone?: 'ok' | 'warn' | 'err' | 'off' | 'muted' | 'hollow'
  text?: string
  /** 文字色覆盖（默认次级墨）；测试台状态行用失败红 / 警示琥珀表达状态语义。 */
  textClass?: string
}>(), {
  tone: 'muted',
  text: '',
  textClass: 'text-[var(--color-text-secondary)]',
})
</script>

<template>
  <span class="inline-flex items-center gap-2 whitespace-nowrap">
    <span class="status-dot" :class="`tone-${tone}`" aria-hidden="true" />
    <span class="text-[13px] leading-none" :class="textClass">{{ text }}</span>
  </span>
</template>

<style scoped>
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex: none;
}
.tone-ok { background: var(--color-success); }
.tone-warn { background: var(--color-warning); }
.tone-err { background: var(--color-error); }
.tone-off { background: var(--color-text-muted); }
.tone-muted { background: var(--color-border-strong); }
.tone-hollow { background: transparent; box-shadow: inset 0 0 0 1.5px var(--color-text-muted); }
</style>
