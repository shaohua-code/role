<script setup lang="ts">
withDefaults(defineProps<{
  tip?: string
}>(), {
  tip: '正在加载管理模块…',
})
</script>

<template>
  <div class="flex min-h-60 w-full flex-col items-center justify-center gap-4">
    <div class="flex items-center gap-2" aria-hidden="true">
      <span class="h-2 w-2 animate-pulse rounded-full bg-[var(--color-brand)] opacity-90 [animation-delay:-0.3s]" />
      <span class="h-2 w-2 animate-pulse rounded-full bg-[var(--color-brand)] opacity-70 [animation-delay:-0.15s]" />
      <span class="h-2 w-2 animate-pulse rounded-full bg-[var(--color-brand)] opacity-50" />
    </div>
    <p class="m-0 text-sm text-[var(--color-text-muted)]">{{ tip }}</p>
  </div>
</template>
