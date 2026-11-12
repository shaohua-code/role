<script setup lang="ts">
withDefaults(defineProps<{
  description?: string
  emoji?: string
}>(), {
  description: '暂无数据',
  emoji: '📭',
})
</script>

<template>
  <div class="flex flex-col items-center gap-2 px-4 py-8 text-center">
    <!-- U18：emoji 统一灰阶（grayscale）——保留图形语言、去除彩色对黑白轻奢体系的干扰；底衬圆环提供稳定对比 -->
    <span
      class="flex h-12 w-12 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--color-bg-subtle)] text-2xl opacity-90 ring-1 ring-[var(--color-border)] grayscale"
      aria-hidden="true"
    >{{ emoji }}</span>
    <p class="m-0 max-w-72 text-sm leading-relaxed text-[var(--color-text-muted)]">{{ description }}</p>
    <slot />
  </div>
</template>
