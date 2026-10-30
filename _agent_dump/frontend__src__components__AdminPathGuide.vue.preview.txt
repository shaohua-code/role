<script setup lang="ts">
// 共享「主路径引导」空态组件：按编号步骤展示产品主路径（Wave 4 收口）。
// 应用/组织工作台空态复用，文案由使用方传入，保持克制的排版。
withDefaults(defineProps<{
  /** 允许传入 as const 的只读步骤数组 */
  steps: readonly string[]
  /** 标题行前缀，例如「开始前请先」；不传则显示「按以下步骤开始」 */
  title?: string
}>(), {
  title: '按以下步骤开始',
})
</script>

<template>
  <div class="mx-auto w-full max-w-md text-left">
    <p class="mb-2 mt-0 text-xs font-medium tracking-wide text-[var(--color-text-secondary)]">{{ title }}</p>
    <ol class="m-0 list-none space-y-2 p-0">
      <li v-for="(step, index) in steps" :key="index" class="flex items-start gap-2 text-sm leading-relaxed">
        <span
          class="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-brand)] text-[11px] font-semibold text-white"
        >{{ index + 1 }}</span>
        <span class="min-w-0 text-[var(--color-text)]">{{ step }}</span>
      </li>
    </ol>
  </div>
</template>
