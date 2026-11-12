<script setup lang="ts">
// 筛选面板：浅灰圆角容器统一收纳展开的筛选表单；筛选项按最小列宽自适应换列，操作按钮固定在底部右侧。
withDefaults(defineProps<{
  /** 筛选项网格最小列宽（px），窄屏自动减列 */
  minColumnWidth?: number
}>(), {
  minColumnWidth: 220,
})
</script>

<template>
  <!-- U4 token 化：原 slate 蓝灰色板混入 zinc 中性体系且浅色下近乎隐形，改设计 token（暗色自动翻转） -->
  <div class="admin-filter-panel mb-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-4">
    <div class="grid items-end gap-3" :style="{ gridTemplateColumns: `repeat(auto-fill, minmax(${minColumnWidth}px, 1fr))` }">
      <slot />
    </div>
    <div v-if="$slots.actions" class="mt-3 flex flex-wrap items-center justify-end gap-2 border-t border-[var(--color-border)] pt-3">
      <slot name="actions" />
    </div>
  </div>
</template>
