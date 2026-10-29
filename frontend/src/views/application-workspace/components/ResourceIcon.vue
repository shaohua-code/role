<script lang="ts">
// 菜单图标解析：icon 字段由用户在表单自由配置（antd 图标名或业务自定义标识），
// 命中映射渲染对应线性图标，未命中回落应用图标；业务端可按同名自行渲染。
import {
  AppstoreOutlined, BarChartOutlined, BellOutlined, CalendarOutlined,
  CloudOutlined, ControlOutlined, DashboardOutlined, DatabaseOutlined, FileTextOutlined, FilterOutlined,
  FolderOutlined, GlobalOutlined, HomeOutlined, LineChartOutlined, LockOutlined,
  MailOutlined, OrderedListOutlined, PieChartOutlined, ProfileOutlined, SafetyOutlined,
  SettingOutlined, TableOutlined, TeamOutlined, ToolOutlined,
  UserOutlined, WalletOutlined,
} from '@ant-design/icons-vue'
import type { Component } from 'vue'

// 菜单图标解析映射：icon 字段由用户自由配置（antd 图标名或业务自定义标识），
// 命中映射则渲染对应线性图标，未命中回落应用图标；业务端可按同名自行渲染。
export const RESOURCE_ICON_MAP: Record<string, Component> = {
  AppstoreOutlined,
  HomeOutlined,
  DashboardOutlined,
  FolderOutlined,
  FileTextOutlined,
  ProfileOutlined,
  OrderedListOutlined,
  TableOutlined,
  BarChartOutlined,
  LineChartOutlined,
  PieChartOutlined,
  DatabaseOutlined,
  CloudOutlined,
  GlobalOutlined,
  UserOutlined,
  TeamOutlined,
  SettingOutlined,
  ToolOutlined,
  SafetyOutlined,
  LockOutlined,
  BellOutlined,
  MailOutlined,
  CalendarOutlined,
  WalletOutlined,
}
</script>

<script setup lang="ts">
// 资源节点图标：按钮用调节滑块、数据规则用漏斗，菜单按 icon 名解析（未命中回落应用图标）。
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  type: 'menu' | 'button' | 'data_rule'
  icon?: string | null
}>(), {
  icon: '',
})

const resolved = computed<Component>(() => {
  if (props.type === 'button') return ControlOutlined
  if (props.type === 'data_rule') return FilterOutlined
  return RESOURCE_ICON_MAP[props.icon ?? ''] ?? AppstoreOutlined
})
</script>

<template>
  <component :is="resolved" />
</template>
