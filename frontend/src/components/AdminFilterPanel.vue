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
  <div class="admin-filter-panel mb-3 rounded-xl border border-slate-200/70 bg-slate-50/60 p-4">
    <div class="grid items-end gap-3" :style="{ gridTemplateColumns: `repeat(auto-fill, minmax(${minColumnWidth}px, 1fr))` }">
      <slot />
    </div>
    <div v-if="$slots.actions" class="mt-3 flex flex-wrap items-center justify-end gap-2 border-t border-slate-200/60 pt-3">
      <slot name="actions" />
    </div>
  </div>
</template>
