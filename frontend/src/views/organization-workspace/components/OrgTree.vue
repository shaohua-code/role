<script setup lang="ts">
// 组织工作台左树：租户分组节点（不可选）→ 组织层级节点（可选），支持名称/标识过滤。
// 树顶「新建组织」打开创建弹窗；节点「更多」也可新建下级，并承接负责人 / 启停 / 删除。
import { computed, ref, watch } from 'vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import { EllipsisOutlined } from '@/plugins/icons'

export interface OrgTreeOrganization {
  id: string
  tenant_id: string
  tenant_name: string
  parent_id: string | null
  name: string
  key: string
  status: 'active' | 'disabled'
  owner_user_id?: string | null
  owner_name?: string | null
}

export type OrgMoreAction = 'owner' | 'status' | 'delete'

export interface OrgTreeTenant {
  id: string
  name: string
  canCreate?: boolean
}

interface TreeDatum {
  key: string
  title: string
  isGroup: boolean
  selectable?: boolean
  status?: 'active' | 'disabled'
  canCreate?: boolean
  tenantId?: string
  orgId?: string
  children?: TreeDatum[]
}

const props = withDefaults(defineProps<{
  organizations: OrgTreeOrganization[]
  tenants?: OrgTreeTenant[]
  selectedId?: string
  loading?: boolean
}>(), {
  tenants: () => [],
  selectedId: '',
  loading: false,
})

const emit = defineEmits<{
  select: [organization: OrgTreeOrganization]
  create: [payload: { tenantId: string; parentId?: string }]
  more: [payload: { id: string; action: OrgMoreAction }]
}>()

const searchText = ref('')
const expandedKeys = ref<string[]>([])
const firstCreatableTenantId = computed(() => props.tenants.find(tenant => tenant.canCreate)?.id || '')
const canCreateAny = computed(() => Boolean(firstCreatableTenantId.value))

const treeData = computed<TreeDatum[]>(() => {
  const keyword = searchText.value.trim().toLowerCase()
  const matched = props.organizations.filter(item =>
    !keyword
    || item.name.toLowerCase().includes(keyword)
    || item.key.toLowerCase().includes(keyword))
  const groups = new Map<string, TreeDatum>()
  const nodes = new Map<string, TreeDatum>()
  const tenantSource = props.tenants.length
    ? props.tenants
    : [...new Map(props.organizations.map(item => [item.tenant_id, { id: item.tenant_id, name: item.tenant_name, canCreate: false }])).values()]
  for (const tenant of tenantSource) {
    groups.set(`tenant:${tenant.id}`, {
      key: `tenant:${tenant.id}`,
      title: tenant.name,
      isGroup: true,
      selectable: false,
      canCreate: tenant.canCreate === true,
      tenantId: tenant.id,
      children: [],
    })
  }
  for (const item of matched) {
    const groupKey = `tenant:${item.tenant_id}`
    if (!groups.has(groupKey)) {
      groups.set(groupKey, {
        key: groupKey,
        title: item.tenant_name,
        isGroup: true,
        selectable: false,
        canCreate: false,
        tenantId: item.tenant_id,
        children: [],
      })
    }
    const tenantCanCreate = groups.get(groupKey)?.canCreate === true
    nodes.set(item.id, {
      key: item.id,
      title: item.name,
      isGroup: false,
      status: item.status,
      canCreate: tenantCanCreate && item.status === 'active',
      tenantId: item.tenant_id,
      orgId: item.id,
    })
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
  const rows = [...groups.values()]
  if (keyword) return rows.filter(group => (group.children?.length || 0) > 0)
  return rows
})

function collectKeys(node: TreeDatum, keys: string[]): void {
  keys.push(node.key)
  for (const child of node.children ?? []) collectKeys(child, keys)
}

watch(treeData, data => {
  const keys: string[] = []
  for (const group of data) {
    keys.push(group.key)
    for (const node of group.children ?? []) collectKeys(node, keys)
  }
  expandedKeys.value = keys
}, { immediate: true })

function onSelect(selectedKeys: Array<string | number>): void {
  if (!selectedKeys.length) return
  const key = String(selectedKeys[0])
  if (key.startsWith('tenant:')) return
  const organization = props.organizations.find(item => item.id === key)
  if (organization) emit('select', organization)
}

function onCreate(tenantId?: string, parentId?: string): void {
  if (!tenantId) return
  emit('create', parentId ? { tenantId, parentId } : { tenantId })
}

function onCreateFromHeader(): void {
  onCreate(firstCreatableTenantId.value)
}

function onMore(orgId: string | undefined, action: OrgMoreAction): void {
  if (!orgId) return
  emit('more', { id: orgId, action })
}
</script>

<template>
  <aside class="flex min-w-0 flex-col gap-3 self-start rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
    <AdminSearchField v-model="searchText" placeholder="搜索组织名称或标识" :submit-on-clear="false" />
    <a-button v-if="canCreateAny" type="primary" class="w-full" @click="onCreateFromHeader">新建组织</a-button>
    <a-spin :spinning="loading" class="min-h-24">
      <a-tree
        v-if="treeData.length"
        v-model:expanded-keys="expandedKeys"
        :tree-data="treeData"
        :selected-keys="selectedId ? [selectedId] : []"
        block-node
        @select="onSelect"
      >
        <template #title="{ isGroup, title, status, canCreate, tenantId, orgId }">
          <span v-if="isGroup" class="flex w-full min-w-0 items-center justify-between gap-2">
            <span class="truncate text-xs font-medium tracking-wide text-[var(--color-text-secondary)]">{{ title }}</span>
            <a-dropdown v-if="canCreate" :trigger="['click']">
              <a-button
                type="text"
                size="small"
                class="h-6 w-6 min-w-0 shrink-0 p-0 text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
                @click.stop
              >
                <EllipsisOutlined />
              </a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="create" @click="onCreate(tenantId)">新建组织</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </span>
          <span v-else class="flex w-full min-w-0 items-center justify-between gap-1">
            <span class="inline-flex min-w-0 items-center gap-2">
              <span class="truncate">{{ title }}</span>
              <a-tag v-if="status === 'disabled'" class="mr-0 shrink-0" color="default">停用</a-tag>
            </span>
            <a-dropdown :trigger="['click']">
              <a-button
                type="text"
                size="small"
                class="h-6 w-6 min-w-0 shrink-0 p-0 text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
                @click.stop
              >
                <EllipsisOutlined />
              </a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item v-if="canCreate" key="create" @click="onCreate(tenantId, orgId)">新建组织</a-menu-item>
                  <a-menu-item key="owner" @click="onMore(orgId, 'owner')">设置负责人</a-menu-item>
                  <a-menu-item key="status" @click="onMore(orgId, 'status')">{{ status === 'active' ? '停用组织' : '启用组织' }}</a-menu-item>
                  <a-menu-item key="delete" danger @click="onMore(orgId, 'delete')">删除组织</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </span>
        </template>
      </a-tree>
      <AdminEmpty v-else-if="!loading" emoji="🏛️" description="暂无可查看的组织" />
    </a-spin>
  </aside>
</template>
