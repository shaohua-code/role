<script setup lang="ts">
/** 指标卡：账本式编号 + 巨型等宽-tabular 数字；数据本身即视觉主角（P364 与登录页区分）。
 *  P369 起通用化：clickable=false 渲染纯展示卡（无悬停箭头/无按钮语义），供模型用量页汇总复用。 */
import { ArrowRightOutlined } from '@ant-design/icons-vue'

withDefaults(defineProps<{
  /** 展示标签，如「租户」 */
  label?: string
  /** 指标数值，加载中为 undefined 显示占位符；允许字符串（百分比/费用等已格式化值） */
  value?: number | string
  /** 账本式两位编号（01–06），纯排版细节 */
  index?: string
  /** true=按钮语义 + 悬停箭头（概览跳转卡）；false=纯展示 div（模型用量汇总） */
  clickable?: boolean
}>(), {
  label: '',
  value: undefined,
  index: '',
  clickable: true,
})

defineOptions({ inheritAttrs: false })
</script>

<template>
  <component
    :is="clickable ? 'button' : 'div'"
    :type="clickable ? 'button' : undefined"
    class="group flex flex-col rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4 text-left transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
  >
    <span class="flex w-full items-center justify-between">
      <span class="font-mono text-[10px] font-medium tracking-[0.08em] text-[var(--color-text-muted)]">{{ index }}</span>
      <ArrowRightOutlined
        v-if="clickable"
        class="text-xs text-[var(--color-text-muted)] opacity-0 transition-opacity duration-150 group-hover:opacity-100"
        aria-hidden="true"
      />
    </span>
    <span class="mt-3 text-xs font-medium text-[var(--color-text-secondary)]">{{ label }}</span>
    <span class="mt-1 text-[28px] font-semibold leading-none tabular-nums tracking-tight text-[var(--color-text-primary)]">
      {{ value ?? '—' }}
    </span>
  </component>
</template>
