<script setup lang="ts">
// 组织工作台左树：租户分组节点（不可选）→ 组织层级节点（可选），支持名称/标识过滤。
// 对齐蓝图 departmentTree 的「左树选组织」交互，数据来自工作台父组件。
import { computed, ref, watch } from 'vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'

export interface OrgTreeOrganization {
  id: string
  tenant_id: string
  tenant_name: string
  parent_id: string | null
  name: string
  key: string
  status: 'active' | 'disabled'
}

interface TreeDatum {
  key: string
  title: string
  isGroup: boolean
  selectable?: boolean
  status?: 'active' | 'disabled'
  children?: TreeDatum[]
}

const props = withDefaults(defineProps<{
  organizations: OrgTreeOrganization[]
  selectedId?: string
  loading?: boolean
}>(), {
  selectedId: '',
  loading: false,
})

const emit = defineEmits<{ select: [organization: OrgTreeOrganization] }>()

const searchText = ref('')
const expandedKeys = ref<string[]>([])

// 租户分组 + parent_id 层级拼树；父节点被搜索过滤掉时子节点上浮到分组顶层，避免丢节点。
const treeData = computed<TreeDatum[]>(() => {
  const keyword = searchText.value.trim().toLowerCase()
  const matched = props.organizations.filter(item =>
    !keyword
    || item.name.toLowerCase().includes(keyword)
    || item.key.toLowerCase().includes(keyword))
  const groups = new Map<string, TreeDatum>()
  const nodes = new Map<string, TreeDatum>()
  for (const item of matched) {
    const groupKey = `tenant:${item.tenant_id}`
    if (!groups.has(groupKey)) {
      groups.set(groupKey, { key: groupKey, title: item.tenant_name, isGroup: true, selectable: false, children: [] })
    }
    nodes.set(item.id, { key: item.id, title: item.name, isGroup: false, status: item.status })
  }
  for (const item of matched) {
    const group = groups.get(`tenant:${item.tenant_id}`)!
    const node = nodes.get(item.id)!
    const parent = item.parent_id ? nodes.get(item.parent_id) : undefined
    if (parent) {
      parent.children ??= []
      parent.children.push(node)
    } else {
      group.children!.push(node)
    }
  }
  return [...groups.values()]
})

function collectKeys(node: TreeDatum, keys: string[]): void {
  keys.push(node.key)
  for (const child of node.children ?? []) collectKeys(child, keys)
}

// 分组与组织节点默认全部展开，数据变化（如搜索）后重置。
watch(treeData, data => {
  const keys: string[] = []
  for (const group of data) {
    keys.push(group.key)
    for (const node of group.children ?? []) collectKeys(node, keys)
  }
  expandedKeys.value = keys
}, { immediate: true })

// 用 selectedKeys 反查组织；分组节点与取消选中都不响应。
function onSelect(selectedKeys: Array<string | number>): void {
  if (!selectedKeys.length) return
  const key = String(selectedKeys[0])
  if (key.startsWith('tenant:')) return
  const organization = props.organizations.find(item => item.id === key)
  if (organization) emit('select', organization)
}
</script>

<template>
  <aside class="flex min-w-0 flex-col gap-3 self-start rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
    <AdminSearchField v-model="searchText" placeholder="搜索组织名称或标识" :submit-on-clear="false" />
    <a-spin :spinning="loading" class="min-h-24">
      <a-tree
        v-if="treeData.length"
        v-model:expanded-keys="expandedKeys"
        :tree-data="treeData"
        :selected-keys="selectedId ? [selectedId] : []"
        block-node
        @select="onSelect"
      >
        <template #title="{ isGroup, title, status }">
          <span v-if="isGroup" class="text-xs font-medium tracking-wide text-[var(--color-text-secondary)]">{{ title }}</span>
          <span v-else class="inline-flex max-w-full items-center gap-2">
            <span class="truncate">{{ title }}</span>
            <a-tag v-if="status === 'disabled'" class="mr-0 shrink-0" color="default">停用</a-tag>
          </span>
        </template>
      </a-tree>
      <AdminEmpty v-else-if="!loading" emoji="🏛️" description="暂无可查看的组织" />
    </a-spin>
  </aside>
</template>
