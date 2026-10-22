<script setup lang="ts">
withDefaults(defineProps<{
  hint?: string
}>(), {
  hint: '',
})
</script>

<template>
  <div class="admin-table-toolbar mb-4 flex w-full min-w-0 flex-col gap-3 rounded-xl border border-violet-100/90 bg-gradient-to-r from-slate-50 via-white to-violet-50/50 px-4 py-3 shadow-sm lg:flex-row lg:items-center lg:gap-4">
    <div v-if="$slots.default" class="flex min-w-0 flex-1 flex-wrap items-center gap-3">
      <slot />
    </div>
    <div
      class="flex min-w-0 flex-1 flex-wrap items-center gap-3"
      :class="$slots.default ? 'justify-end lg:max-w-[min(100%,520px)]' : 'w-full justify-between gap-2'"
    >
      <p v-if="hint" class="m-0 min-w-0 flex-1 break-words text-xs leading-relaxed text-slate-500">{{ hint }}</p>
      <div v-if="$slots.actions" class="flex shrink-0 items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
