<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { CopyOutlined } from '@/plugins/icons'

const props = withDefaults(defineProps<{
  label?: string
  text?: string
}>(), {
  label: '',
  text: '',
})

const copied = ref(false)
const copyFailed = ref(false)
let copiedTimer: number | undefined
const copyLabel = computed(() => {
  if (copyFailed.value) return '复制失败'
  if (copied.value) return '已复制'
  return '复制'
})

// 剪贴板 API 被拒绝时再试一次选区复制。两次都失败才显示失败，避免把示例静默当成已复制。
function copyWithSelection(text: string): boolean {
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.left = '-9999px'
  document.body.appendChild(area)
  area.select()
  try {
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    area.remove()
  }
}

async function copyText(): Promise<void> {
  if (!props.text) return
  let ok = false
  try {
    await navigator.clipboard.writeText(props.text)
    ok = true
  } catch {
    ok = copyWithSelection(props.text)
  }
  copied.value = ok
  copyFailed.value = !ok
  if (copiedTimer) window.clearTimeout(copiedTimer)
  copiedTimer = window.setTimeout(() => {
    copied.value = false
    copyFailed.value = false
  }, 1600)
}

onUnmounted(() => {
  if (copiedTimer) window.clearTimeout(copiedTimer)
})
</script>

<template>
  <figure class="mt-4 min-w-0 overflow-hidden rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-sider-bg)]">
    <figcaption class="flex items-center justify-between gap-3 px-4 py-2">
      <span class="font-mono text-xs text-[var(--color-sider-text)]">{{ label }}</span>
      <button
        type="button"
        class="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs text-[var(--color-sider-text-active)] hover:bg-[var(--color-sider-item-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-sider-accent)]"
        @click="copyText"
      >
        <CopyOutlined aria-hidden="true" />
        {{ copyLabel }}
      </button>
    </figcaption>
    <pre class="overflow-x-auto px-4 pb-4 font-mono text-xs leading-6 whitespace-pre-wrap break-words text-[var(--color-sider-text-active)]">{{ text }}</pre>
  </figure>
</template>
