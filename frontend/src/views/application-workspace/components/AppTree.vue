<script setup lang="ts">
// 应用工作台左树：按租户分组的应用列表，支持按名称/Client ID 过滤。
// 对齐蓝图 appTreeList 的「左树选应用」交互，数据来自工作台父组件。
import { computed, ref, watch } from 'vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'

export interface AppTreeApplication {
  id: string
  name: string
  client_id: string
  tenant_id: string
  tenant_name: string
  status: 'active' | 'disabled'
}

interface TreeDatum {
  key: string
  title: string
  isGroup: boolean
  selectable?: boolean
  status?: 'active' | 'disabled'
  /** 租户组节点：当前过滤条件下的应用计数（P397 组节点计数徽标） */
  count?: number
  children?: TreeDatum[]
}

const props = withDefaults(defineProps<{
  applications: AppTreeApplication[]
  selectedId?: string
  loading?: boolean
}>(), {
  selectedId: '',
  loading: false,
})

const emit = defineEmits<{ select: [application: AppTreeApplication] }>()

const searchText = ref('')
const expandedKeys = ref<string[]>([])

// 两级树：租户分组节点（不可选）→ 应用节点（可选）。搜索时只保留命中的应用。
const treeData = computed<TreeDatum[]>(() => {
  const keyword = searchText.value.trim().toLowerCase()
  const matched = props.applications.filter(item =>
    !keyword
    || item.name.toLowerCase().includes(keyword)
    || item.client_id.toLowerCase().includes(keyword))
  const groups = new Map<string, TreeDatum>()
  for (const item of matched) {
    const groupKey = `tenant:${item.tenant_id}`
    let group = groups.get(groupKey)
    if (!group) {
      group = { key: groupKey, title: item.tenant_name, isGroup: true, selectable: false, count: 0, children: [] }
      groups.set(groupKey, group)
    }
    group.count = (group.count || 0) + 1
    group.children!.push({ key: item.id, title: item.name, isGroup: false, status: item.status })
  }
  return [...groups.values()]
})

// 分组节点默认全部展开，数据变化（如搜索）后重置。
watch(treeData, data => {
  expandedKeys.value = data.filter(node => node.isGroup).map(node => node.key)
}, { immediate: true })

// 用 selectedKeys 反查应用，避免依赖 antd 节点内部结构；分组节点与取消选中都不响应。
function onSelect(selectedKeys: Array<string | number>): void {
  if (!selectedKeys.length) return
  const key = String(selectedKeys[0])
  if (key.startsWith('tenant:')) return
  const application = props.applications.find(item => item.id === key)
  if (application) emit('select', application)
}
</script>

<template>
  <aside class="flex min-w-0 flex-col gap-3 self-start rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
    <AdminSearchField v-model="searchText" placeholder="搜索应用名称或 Client ID" :submit-on-clear="false" />
    <a-spin :spinning="loading" class="min-h-24">
      <a-tree
        v-if="treeData.length"
        v-model:expanded-keys="expandedKeys"
        :tree-data="treeData"
        :selected-keys="selectedId ? [selectedId] : []"
        block-node
        @select="onSelect"
      >
        <template #title="{ isGroup, title, status, count }">
          <span v-if="isGroup" class="inline-flex max-w-full items-center gap-1.5">
            <span class="truncate text-xs font-medium tracking-wide text-[var(--color-text-secondary)]">{{ title }}</span>
            <span class="shrink-0 rounded-full bg-[var(--color-bg-subtle)] px-1.5 font-mono text-[10px] leading-4 text-[var(--color-text-muted)] tabular-nums">{{ count }}</span>
          </span>
          <span v-else class="inline-flex max-w-full items-center gap-2">
            <span class="truncate">{{ title }}</span>
            <a-tag v-if="status === 'disabled'" class="mr-0 shrink-0" color="default">停用</a-tag>
          </span>
        </template>
      </a-tree>
      <AdminEmpty v-else-if="!loading" emoji="🧩" description="暂无可管理的应用" />
    </a-spin>
  </aside>
</template>
