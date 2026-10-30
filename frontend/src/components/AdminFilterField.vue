<script setup lang="ts">
// 带标签的筛选项：标签固定在控件上方，保证筛选面板内表单语义一致、视觉对齐。
defineProps<{
  label: string
}>()
</script>

<template>
  <label class="flex min-w-0 flex-col gap-1">
    <span class="admin-filter-label text-xs font-medium text-[var(--color-text-secondary)]">{{ label }}</span>
    <slot />
  </label>
</template>
