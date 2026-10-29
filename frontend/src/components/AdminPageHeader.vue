<script setup lang="ts">
// 管理页统一页头：eyebrow + 标题 + 右侧操作区。
// 副标题提示降噪：不再整行平铺长文案，改为标题旁「!」图标 + a-tooltip 悬停展示完整说明。
import { ExclamationCircleOutlined } from '@/plugins/icons'

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
  <div class="mb-4 flex w-full min-w-0 flex-col items-start justify-between gap-4 md:mb-6 md:flex-row md:items-end">
    <div class="min-w-0 max-w-3xl">
      <p v-if="eyebrow" class="mgmt-eyebrow">
        <span class="mgmt-eyebrow-bar" aria-hidden="true" />
        {{ eyebrow }}
      </p>
      <h3 class="mgmt-page-title mt-1">
        <!-- 标题与「!」提示图标同行；悬停图标弹出完整副标题说明 -->
        <span class="inline-flex min-w-0 items-center gap-2">
          <span class="min-w-0 truncate">{{ title }}</span>
          <a-tooltip v-if="subtitle" :title="subtitle" :overlay-style="{ maxWidth: '360px' }">
            <ExclamationCircleOutlined
              class="shrink-0 text-sm text-[var(--color-text-muted)] cursor-help transition-colors hover:text-[var(--color-text-secondary)]"
              aria-label="查看说明"
            />
          </a-tooltip>
        </span>
      </h3>
    </div>
    <div v-if="$slots.extra" class="shrink-0">
      <slot name="extra" />
    </div>
  </div>
</template>
