<script setup lang="ts">
// 统计卡带：从权限编码页账本式统计卡抽象的通用组件。
// 点击卡片切换筛选（再次点击已选卡片还原为「全部」），数量为 0 的概念位可置灰禁用。
interface AdminStatItem {
  /** 筛选键；'' 约定为「全部」 */
  key: string
  label: string
  count: number
  /** 卡片底部补充文案（如「活动 12」「暂无业务应用」） */
  sub?: string
  disabled?: boolean
}

const model = defineModel<string>({ default: '' })

withDefaults(defineProps<{
  stats: AdminStatItem[]
  /** 账本式编号（00/01/02…），对齐概览页设计语言 */
  numbered?: boolean
}>(), {
  numbered: false,
})

// 点击卡片：disabled 不可点；已选中卡片再点一次还原为「全部」（''）
function toggleStat(key: string, disabled?: boolean): void {
  if (disabled) return
  model.value = model.value === key ? '' : key
}
</script>

<template>
  <div class="mb-4 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-[repeat(auto-fill,minmax(200px,1fr))]">
    <button
      v-for="(stat, index) in stats"
      :key="stat.key || 'all'"
      type="button"
      :class="[
        'flex flex-col items-start gap-0.5 border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-3 text-left rounded-[10px] cursor-pointer transition-[border-color,box-shadow] duration-150 hover:border-[var(--color-border-strong)] hover:shadow-[var(--shadow-md)]',
        { 'border-[var(--color-text-primary)] shadow-[inset_3px_0_0_var(--color-text-primary)]': model === stat.key },
        { 'opacity-55 cursor-not-allowed hover:border-[var(--color-border)] hover:shadow-none': stat.disabled },
      ]"
      @click="toggleStat(stat.key, stat.disabled)"
    >
      <span v-if="numbered" class="font-mono text-[10px] tracking-[0.18em] text-[var(--color-text-muted)]">{{ stat.key ? String(index).padStart(2, '0') : '00' }}</span>
      <span class="font-mono text-[22px] leading-[1.2] font-semibold text-[var(--color-text-primary)] tabular-nums">{{ stat.count }}</span>
      <span class="text-[12.5px] text-[var(--color-text-secondary)]">{{ stat.label }}</span>
      <span v-if="stat.sub" class="text-[11px] text-[var(--color-text-muted)]">{{ stat.sub }}</span>
    </button>
  </div>
</template>
