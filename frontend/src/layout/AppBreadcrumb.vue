<script setup lang="ts">
defineProps<{
  modeLabel: string
  pageTitle: string
}>()
</script>

<template>
  <!-- U23：面包屑统一为纯文本双段层级（次级墨模式段 + 主墨页面段），去掉「描边 chip + 纯文本」混排 -->
  <nav class="flex min-w-0 items-center gap-2 leading-none" aria-label="当前位置">
    <span class="shrink-0 text-[13px] leading-[1.4] text-[var(--color-text-secondary)]">{{ modeLabel }}</span>
    <span class="shrink-0 text-[var(--color-text-muted)]" aria-hidden="true">/</span>
    <span class="truncate text-[13px] font-medium leading-[1.4] text-[var(--color-text-primary)]">{{ pageTitle }}</span>
  </nav>
</template>
