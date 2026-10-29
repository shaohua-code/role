<script setup lang="ts">
// 详情抽屉骨架：详情/浏览类信息统一入口（替代弹窗堆叠）。
// 页面只传标题与正文插槽；操作按钮放 footer 插槽，右上角扩展放 header-extra 插槽。
const open = defineModel<boolean>('open', { default: false })

withDefaults(defineProps<{
  title: string
  /** 标题下方补充说明（如 mono 标识、状态摘要） */
  subtitle?: string
  width?: number | string
  loading?: boolean
}>(), {
  subtitle: '',
  width: 640,
  loading: false,
})
</script>

<template>
  <a-drawer v-model:open="open" :width="width" destroy-on-close>
    <template #title>
      <div class="flex min-w-0 flex-col gap-0.5">
        <span class="truncate text-[15px] font-semibold text-[var(--color-text-primary)]">{{ title }}</span>
        <span v-if="subtitle" class="truncate font-mono text-xs text-[var(--color-text-secondary)]">{{ subtitle }}</span>
      </div>
    </template>
    <template v-if="$slots['header-extra']" #extra><slot name="header-extra" /></template>
    <a-spin :spinning="loading">
      <slot />
    </a-spin>
    <template v-if="$slots.footer" #footer><slot name="footer" /></template>
  </a-drawer>
</template>
