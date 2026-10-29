<script setup lang="ts">
defineProps<{
  modeLabel: string
  pageTitle: string
}>()
</script>

<template>
  <nav class="flex min-w-0 items-center gap-2 leading-none" aria-label="当前位置">
    <span class="shrink-0 rounded-md bg-[var(--color-bg-subtle)] px-2 py-1 text-[11px] font-medium leading-[1.2] text-[var(--color-text-secondary)] ring-1 ring-[var(--color-border)]">
      {{ modeLabel }}
    </span>
    <span class="shrink-0 text-[var(--color-text-muted)]" aria-hidden="true">/</span>
    <span class="truncate text-sm font-medium leading-[1.4] text-[var(--color-text-primary)]">{{ pageTitle }}</span>
  </nav>
</template>
