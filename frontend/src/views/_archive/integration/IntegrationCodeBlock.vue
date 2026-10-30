<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { CodeTab } from './integrationGuide'

const props = withDefaults(defineProps<{
  tabs: CodeTab[]
}>(), {
  tabs: () => [],
})

const activeKey = ref('')
const copied = ref(false)
let copiedTimer: number | undefined

const currentTab = computed(() => props.tabs.find(tab => tab.label === activeKey.value) ?? props.tabs[0])

// 切换方案后示例从第一项重新开始。
watch(() => props.tabs, (tabs) => {
  activeKey.value = tabs[0]?.label ?? ''
}, { immediate: true })

async function copyCurrent(): Promise<void> {
  if (!currentTab.value) {
    return
  }
  try {
    await navigator.clipboard.writeText(currentTab.value.text)
    copied.value = true
    if (copiedTimer) window.clearTimeout(copiedTimer)
    copiedTimer = window.setTimeout(() => {
      copied.value = false
    }, 1600)
  } catch {
    copied.value = false
  }
}

onUnmounted(() => {
  if (copiedTimer) window.clearTimeout(copiedTimer)
})
</script>

<template>
  <div v-if="tabs.length" class="mt-4 min-w-0 overflow-hidden">
    <a-tabs v-model:activeKey="activeKey" size="small">
      <template #rightExtra>
        <a-button size="small" @click="copyCurrent">{{ copied ? '已复制' : '复制' }}</a-button>
      </template>
      <a-tab-pane v-for="tab in tabs" :key="tab.label" :tab="tab.label">
        <pre class="overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs leading-6 break-words whitespace-pre-wrap text-slate-100">{{ tab.text }}</pre>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>
