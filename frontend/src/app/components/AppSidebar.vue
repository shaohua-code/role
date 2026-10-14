<script setup lang="ts">
import type { NavigationItem, PageKey } from '../navigation'

const props = defineProps<{
  page: PageKey
  healthState: string
  items: NavigationItem[]
  modeLabel: string
}>()

const emit = defineEmits<{
  navigate: [page: PageKey]
}>()

const mobileNavOptions = props.items.map(item => ({ value: item.key, label: item.label }))

function navigateTo(value: string | number): void {
  // Select 的值来自用户输入，先校验导航白名单，再向应用壳层发出页面切换事件。
  const item = props.items.find(candidate => candidate.key === value)
  if (item) emit('navigate', item.key)
}
</script>

<template>
  <aside class="sidebar">
    <a class="brand" href="#" @click.prevent="emit('navigate', props.items[0]?.key || 'overview')"><span class="brand-mark">ID</span><span><strong>统一身份平台</strong><small>IDENTITY CONTROL</small></span></a>
    <div class="nav-caption">{{ props.modeLabel }}</div>
    <nav :aria-label="`${props.modeLabel}导航`">
      <button v-for="item in props.items" :key="item.key" class="nav-item" :class="{ active: props.page === item.key }" @click="emit('navigate', item.key)"><span class="nav-icon">{{ item.icon }}</span>{{ item.label }}</button>
    </nav>
    <a-select class="mobile-nav-select" :value="props.page" :options="mobileNavOptions" aria-label="选择管理页面" @change="navigateTo" />
    <div class="sidebar-footer" role="status" aria-live="polite"><span class="status-dot" :class="{ offline: props.healthState !== '服务正常' }"></span>{{ props.healthState }} · IAM</div>
  </aside>
</template>
