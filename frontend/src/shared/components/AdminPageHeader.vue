<script setup lang="ts">
withDefaults(defineProps<{
  eyebrow?: string
  title?: string
  subtitle?: string
}>(), {
  eyebrow: '',
  title: '',
  subtitle: '',
})
</script>

<template>
  <div class="mb-6 flex w-full min-w-0 flex-col items-start justify-between gap-4 md:flex-row md:items-end">
    <div class="min-w-0 max-w-3xl">
      <a-typography-text v-if="eyebrow" type="secondary" class="text-xs tracking-widest uppercase">{{ eyebrow }}</a-typography-text>
      <a-typography-title :level="3" class="mt-1 mb-1">{{ title }}</a-typography-title>
      <a-typography-paragraph v-if="subtitle" type="secondary" class="mb-0">{{ subtitle }}</a-typography-paragraph>
    </div>
    <div v-if="$slots.extra" class="shrink-0">
      <slot name="extra" />
    </div>
  </div>
</template>
