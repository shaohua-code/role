<script setup lang="ts">
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import AdminTableToolbar from './AdminTableToolbar.vue'
import AdminEmpty from './AdminEmpty.vue'

/**
 * AdminTable：可复用表格核心（工具条 / 错误提示 / 表格 / emoji 空态）。
 * 不含页头与卡片外壳，适合工作台 Tab、弹窗、卡片内嵌等任意场景；
 * 整页列表用 AdminListPage（页头 + 卡片 + 本组件组合）。
 * 未声明的 a-table 属性经 $attrs 透传；hint / 默认插槽 / actions 任一存在才渲染工具条。
 */
defineOptions({ inheritAttrs: false })

withDefaults(defineProps<{
  columns: TableColumnsType
  dataSource: unknown[]
  loading?: boolean
  rowKey?: string
  scroll?: { x?: number | string; y?: number | string }
  pagination?: false | TablePaginationConfig
  /** 工具条说明文案；与控件/按钮插槽任一存在才渲染工具条 */
  hint?: string
  /** 非空时在表格上方渲染错误提示 */
  errorText?: string
  emptyEmoji?: string
  emptyText?: string
}>(), {
  loading: false,
  rowKey: 'id',
  hint: '',
  errorText: '',
  emptyEmoji: '📋',
  emptyText: '暂无数据',
})

const emit = defineEmits<{
  'table-change': [pagination: TablePaginationConfig]
}>()
</script>

<template>
  <AdminTableToolbar v-if="hint || $slots.default || $slots.actions" :hint="hint">
    <slot />
    <template v-if="$slots.actions" #actions><slot name="actions" /></template>
  </AdminTableToolbar>
  <a-alert v-if="errorText" type="error" show-icon :message="errorText" class="mb-4" />
  <a-table
    v-bind="$attrs"
    :data-source="dataSource"
    :columns="columns"
    :loading="loading"
    :row-key="rowKey"
    :scroll="scroll"
    :pagination="pagination"
    @change="emit('table-change', $event)"
  >
    <template v-if="$slots.bodyCell" #bodyCell="cell"><slot name="bodyCell" v-bind="cell" /></template>
    <template v-if="$slots.headerCell" #headerCell="cell"><slot name="headerCell" v-bind="cell" /></template>
    <template v-if="$slots.summary" #summary><slot name="summary" /></template>
    <template #emptyText><slot name="emptyText"><AdminEmpty :emoji="emptyEmoji" :description="emptyText" /></slot></template>
  </a-table>
</template>
