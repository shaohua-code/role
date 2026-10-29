<script setup lang="ts">
import { message } from 'ant-design-vue'
import { CopyOutlined } from '@/plugins/icons'

// mono 值展示（Client ID / 租户标识 / 权限码等）：等宽字体 + hover 显示一键复制。
const props = withDefaults(defineProps<{
  value: string
  copyable?: boolean
  maxWidth?: string
}>(), {
  copyable: true,
  maxWidth: '220px',
})

// 一键复制；行内使用需 @click.stop 防触发表格行点击
async function copyValue(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.value)
    message.success('已复制')
  } catch {
    message.error('复制失败，请手动复制')
  }
}
</script>

<template>
  <span class="group/mono inline-flex max-w-full min-w-0 items-center gap-1 align-middle" :style="{ maxWidth }">
    <span class="min-w-0 truncate font-mono text-xs text-[var(--color-text-secondary)]" :title="value">{{ value }}</span>
    <CopyOutlined
      v-if="copyable"
      class="shrink-0 cursor-pointer text-xs text-[var(--color-text-muted)] opacity-0 transition-opacity duration-150 group-hover/mono:opacity-100 hover:text-[var(--color-text-primary)]"
      @click.stop="copyValue"
    />
  </span>
</template>
