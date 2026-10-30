<script setup lang="ts">
// 列表页工具条：左侧筛选控件（默认插槽）+ 右侧提示/操作按钮。
// 提示降噪：hint 不再整行平铺长文案，改为「!」图标 + a-tooltip 悬停展示完整说明。
import { ExclamationCircleOutlined } from '@/plugins/icons'

withDefaults(defineProps<{
  hint?: string
}>(), {
  hint: '',
})
</script>

<template>
  <!-- P398 统一筛选条：左区筛选控件（统一 8px 间距节奏）+ 右区提示/操作（桌面端细分隔线 + 右对齐） -->
  <div class="admin-table-toolbar mb-3 flex w-full min-w-0 flex-col gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3 shadow-sm lg:flex-row lg:items-center lg:gap-0">
    <div v-if="$slots.default" class="flex min-w-0 flex-1 flex-wrap items-center gap-2">
      <slot />
    </div>
    <div
      class="flex min-w-0 flex-wrap items-center gap-2 lg:shrink-0 lg:flex-nowrap"
      :class="$slots.default ? 'lg:ml-auto lg:justify-end lg:border-l lg:border-[var(--color-border)] lg:pl-4' : 'w-full justify-between gap-2'"
    >
      <!-- 悬停「!」图标弹出完整提示说明 -->
      <a-tooltip v-if="hint" :title="hint" :overlay-style="{ maxWidth: '360px' }">
        <ExclamationCircleOutlined
          class="shrink-0 text-sm text-[var(--color-text-muted)] cursor-help transition-colors hover:text-[var(--color-text-secondary)]"
          aria-label="查看说明"
        />
      </a-tooltip>
      <div v-if="$slots.actions" class="flex shrink-0 items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
