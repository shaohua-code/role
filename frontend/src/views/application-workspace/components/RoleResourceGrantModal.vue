<script setup lang="ts">
// 角色资源分配弹窗（P357）：checkable 资源树 + 搜索，全量替换角色在当前应用的资源授权。
// 后端 PUT 会自动补齐祖先节点；这里默认父子联动（勾父带子），保存前不额外展开半选。
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import AdminEmpty from '@/components/AdminEmpty.vue'
import ResourceIcon from './ResourceIcon.vue'
import { matchResource, buildResourcePathCodes } from './resourceSearch'

interface ResourceRecord {
  id: string
  parent_id: string | null
  resource_type: 'menu' | 'button' | 'data_rule'
  code: string
  name: string
  description: string | null
  icon?: string | null
  status: 'active' | 'disabled'
}

interface ResourceNode {
  key: string
  title: string
  children?: ResourceNode[]
  record: ResourceRecord
}

const props = withDefaults(defineProps<{
  applicationId?: string
  roleId?: string
  roleName?: string
  // 嵌进应用权限抽屉时去掉外层 Modal。
  embedded?: boolean
}>(), {
  applicationId: '',
  roleId: '',
  roleName: '',
  embedded: false,
})

const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>('open', { default: false })

const resources = ref<ResourceRecord[]>([])
const checkedIds = ref<string[]>([])
const expandedKeys = ref<string[]>([])
const searchText = ref('')
const loading = ref(false)
const saving = ref(false)

// 树节点展示的路径化编码：根→当前逐级拼接，上级/上上级编码始终可见。
const resourcePathCodes = computed(() => buildResourcePathCodes(resources.value))

function applicationPath(path: string): string {
  // 资源树只挂 /admin，鉴权已按应用管理员访问权过滤，租户台同样走这条。
  return `/admin${path}`
}

// 平铺资源组装成树；排序 sort 升序、code 兜底（后端已排好，这里保持返回顺序）。
const resourceTree = computed<ResourceNode[]>(() => {
  const nodeMap = new Map<string, ResourceNode>()
  const roots: ResourceNode[] = []
  for (const record of resources.value) {
    nodeMap.set(record.id, { key: record.id, title: record.name, record, children: [] })
  }
  for (const record of resources.value) {
    const node = nodeMap.get(record.id)!
    const parent = record.parent_id ? nodeMap.get(record.parent_id) : undefined
    if (parent) parent.children!.push(node)
    else roots.push(node)
  }
  // 模糊搜索：多词 AND，命中名称/编码/描述任一字段；命中节点保留祖先链以便导航。
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return roots
  const keep = new Set<string>()
  const markWithAncestors = (record: ResourceRecord): void => {
    let cursor: ResourceRecord | undefined = record
    while (cursor && !keep.has(cursor.id)) {
      keep.add(cursor.id)
      cursor = cursor.parent_id ? resources.value.find(item => item.id === cursor!.parent_id) : undefined
    }
  }
  for (const record of resources.value) {
    if (matchResource(record, keyword)) markWithAncestors(record)
  }
  const filterNodes = (nodes: ResourceNode[]): ResourceNode[] =>
    nodes
      .filter(node => keep.has(node.record.id))
      .map(node => ({ ...node, children: node.children?.length ? filterNodes(node.children) : undefined }))
  return filterNodes(roots)
})

// 展开全部菜单层级，方便直接勾选深层按钮。
function collectMenuKeys(nodes: ResourceNode[]): string[] {
  const keys: string[] = []
  const walk = (list: ResourceNode[]): void => {
    for (const node of list) {
      if (node.children?.length) {
        keys.push(node.key)
        walk(node.children)
      }
    }
  }
  walk(nodes)
  return keys
}

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [rows, assigned] = await Promise.all([
      api<ResourceRecord[]>(applicationPath(`/applications/${props.applicationId}/resources`)),
      api<{ resource_ids: string[] }>(
        applicationPath(`/applications/${props.applicationId}/roles/${props.roleId}/resources`),
      ),
    ])
    resources.value = rows
    checkedIds.value = assigned.resource_ids
    expandedKeys.value = collectMenuKeys(buildTree(rows))
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取资源授权失败')
  } finally {
    loading.value = false
  }
}

function buildTree(rows: ResourceRecord[]): ResourceNode[] {
  const nodeMap = new Map<string, ResourceNode>()
  const roots: ResourceNode[] = []
  for (const record of rows) {
    nodeMap.set(record.id, { key: record.id, title: record.name, record, children: [] })
  }
  for (const record of rows) {
    const node = nodeMap.get(record.id)!
    const parent = record.parent_id ? nodeMap.get(record.parent_id) : undefined
    if (parent) parent.children!.push(node)
    else roots.push(node)
  }
  return roots
}

async function saveAssign(): Promise<void> {
  saving.value = true
  try {
    await api(applicationPath(`/applications/${props.applicationId}/roles/${props.roleId}/resources`), {
      method: 'PUT',
      body: JSON.stringify({ resource_ids: checkedIds.value }),
    })
    message.success(`已保存「${props.roleName}」的资源授权`)
    emit('saved')
    if (!props.embedded) open.value = false
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存资源授权失败')
  } finally {
    saving.value = false
  }
}

watch(open, visible => {
  if (visible && props.applicationId && props.roleId) {
    searchText.value = ''
    void loadData()
  }
}, { immediate: true })
</script>

<template>
  <component
    :is="embedded ? 'div' : 'a-modal'"
    v-bind="embedded ? {} : { open, title: '配置资源权限', okText: '保存授权', cancelText: '取消', confirmLoading: saving, width: 560 }"
    @ok="saveAssign"
    @cancel="open = false"
    @update:open="(value: boolean) => open = value"
  >
    <div class="flex flex-col gap-3">
      <a-alert v-if="!embedded" type="info" show-icon class="mb-0"
        :message="`为角色「${roleName}」勾选可见的菜单、按钮与数据规则；保存为全量替换，服务端自动补齐父级菜单。`"
      />
      <a-input v-model:value="searchText" placeholder="搜索名称或编码" allow-clear />
      <a-spin :spinning="loading">
        <div class="max-h-80 min-h-40 overflow-y-auto rounded-lg border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-3">
          <a-tree
            v-if="resourceTree.length"
            v-model:checked-keys="checkedIds"
            v-model:expanded-keys="expandedKeys"
            :tree-data="resourceTree"
            checkable
            block-node
          >
            <template #title="{ record }">
              <span class="inline-flex max-w-full items-center gap-2" :title="record.description || undefined">
                <ResourceIcon :type="record.resource_type" :icon="record.icon"
                  class="shrink-0 text-[15px] text-[var(--color-text-secondary)]" />
                <span class="truncate">{{ record.name }}</span>
                <span class="max-w-[100px] shrink truncate font-mono text-xs text-[var(--color-text-muted)]"
                  :title="resourcePathCodes.get(record.id)">{{ resourcePathCodes.get(record.id) }}</span>
                <a-tag v-if="record.resource_type === 'button'" class="mr-0 shrink-0" color="default">按钮</a-tag>
                <a-tag v-else-if="record.resource_type === 'data_rule'" class="mr-0 shrink-0" color="default">数据</a-tag>
                <a-tag v-if="record.status === 'disabled'" class="mr-0 shrink-0" color="default">已停用</a-tag>
              </span>
            </template>
          </a-tree>
          <AdminEmpty v-else-if="!loading" emoji="🧭" description="该应用还没有资源节点，请先到「资源权限」Tab 登记" />
        </div>
      </a-spin>
      <div class="flex items-center justify-between gap-3">
        <span class="text-xs text-[var(--color-text-muted)]">已勾选 {{ checkedIds.length }} 个节点（含自动携带的父级）</span>
        <a-button v-if="embedded" type="primary" :loading="saving" @click="saveAssign">保存资源授权</a-button>
      </div>
    </div>
  </component>
</template>
