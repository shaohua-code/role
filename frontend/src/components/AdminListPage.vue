<script setup lang="ts">
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'
import AdminPageHeader from './AdminPageHeader.vue'
import AdminTableToolbar from './AdminTableToolbar.vue'
import AdminEmpty from './AdminEmpty.vue'

/**
 * 列表页骨架：页头 + 数据卡片（工具条 / 错误提示 / 表格 / emoji 空态）。
 * 页面只保留数据逻辑与弹窗；筛选表单等页面特有内容放 card-top 插槽，
 * 表格底部备注放 card-bottom 插槽；未声明的 a-table 属性经 $attrs 透传。
 */
defineOptions({ inheritAttrs: false })

withDefaults(defineProps<{
  /** 页头 eyebrow（不传则不渲染页头，用于卡片内嵌表格） */
  eyebrow?: string
  title?: string
  subtitle?: string
  /** 工具条说明文案；与控件/按钮插槽任一存在才渲染工具条 */
  hint?: string
  columns: TableColumnsType
  dataSource: unknown[]
  loading?: boolean
  rowKey?: string
  scroll?: { x?: number | string; y?: number | string }
  pagination?: false | TablePaginationConfig
  /** 非空时在表格上方渲染错误提示 */
  errorText?: string
  emptyEmoji?: string
  emptyText?: string
}>(), {
  eyebrow: '',
  title: '',
  subtitle: '',
  hint: '',
  loading: false,
  rowKey: 'id',
  errorText: '',
  emptyEmoji: '📋',
  emptyText: '暂无数据',
})

const emit = defineEmits<{
  'table-change': [pagination: TablePaginationConfig]
}>()
</script>

<template>
  <AdminPageHeader v-if="eyebrow || title || subtitle" :eyebrow="eyebrow" :title="title" :subtitle="subtitle">
    <template v-if="$slots['header-extra']" #extra><slot name="header-extra" /></template>
  </AdminPageHeader>

  <a-card class="data-card mgmt-data-card" :bordered="false">
    <slot name="card-top" />
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
      <template #emptyText><slot name="emptyText"><AdminEmpty :emoji="emptyEmoji" :description="emptyText" /></slot></template>
    </a-table>
    <slot name="card-bottom" />
  </a-card>
</template>
