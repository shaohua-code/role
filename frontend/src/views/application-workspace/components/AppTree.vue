<script setup lang="ts">
// 应用工作台左树：按租户分组的应用列表，支持按名称/Client ID 过滤。
// 树顶「新建应用」打开创建弹窗；节点「更多」也可新建，并承接编辑 / 密钥 / 启停 / 删除。
import { computed, ref, watch } from 'vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import { EllipsisOutlined } from '@/plugins/icons'

export interface AppTreeApplication {
  id: string
  name: string
  client_id: string
  tenant_id: string
  tenant_name: string
  status: 'active' | 'disabled'
  trusted?: boolean
}

export type AppMoreAction = 'edit' | 'rotateSecret' | 'trust' | 'status' | 'delete'

export interface AppTreeTenant {
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
  count?: number
  canCreate?: boolean
  tenantId?: string
  appId?: string
  trusted?: boolean
  children?: TreeDatum[]
}

const props = withDefaults(defineProps<{
  applications: AppTreeApplication[]
  tenants?: AppTreeTenant[]
  canCreate?: boolean
  selectedId?: string
  loading?: boolean
}>(), {
  tenants: () => [],
  canCreate: false,
  selectedId: '',
  loading: false,
})

const emit = defineEmits<{
  select: [application: AppTreeApplication]
  create: [tenantId: string]
  more: [payload: { id: string; action: AppMoreAction }]
}>()

const searchText = ref('')
const expandedKeys = ref<string[]>([])
const firstCreatableTenantId = computed(() =>
  props.tenants.find(tenant => tenant.canCreate)?.id || (props.canCreate ? props.tenants[0]?.id : '') || '')
const canCreateAny = computed(() => props.canCreate || props.tenants.some(tenant => tenant.canCreate === true))

// 两级树：租户分组节点（不可选）→ 应用节点（可选）。无应用的租户仍展示分组，便于从「更多」新建。
const treeData = computed<TreeDatum[]>(() => {
  const keyword = searchText.value.trim().toLowerCase()
  const matched = props.applications.filter(item =>
    !keyword
    || item.name.toLowerCase().includes(keyword)
    || item.client_id.toLowerCase().includes(keyword))
  const groups = new Map<string, TreeDatum>()
  const tenantSource = props.tenants.length
    ? props.tenants
    : [...new Map(props.applications.map(item => [item.tenant_id, { id: item.tenant_id, name: item.tenant_name, canCreate: false }])).values()]
  for (const tenant of tenantSource) {
    groups.set(`tenant:${tenant.id}`, {
      key: `tenant:${tenant.id}`,
      title: tenant.name,
      isGroup: true,
      selectable: false,
      count: 0,
      canCreate: tenant.canCreate === true || props.canCreate,
      tenantId: tenant.id,
      children: [],
    })
  }
  for (const item of matched) {
    const groupKey = `tenant:${item.tenant_id}`
    let group = groups.get(groupKey)
    if (!group) {
      group = {
        key: groupKey,
        title: item.tenant_name,
        isGroup: true,
        selectable: false,
        count: 0,
        canCreate: props.canCreate,
        tenantId: item.tenant_id,
        children: [],
      }
      groups.set(groupKey, group)
    }
    group.count = (group.count || 0) + 1
    group.children!.push({
      key: item.id,
      title: item.name,
      isGroup: false,
      status: item.status,
      appId: item.id,
      tenantId: item.tenant_id,
      trusted: item.trusted === true,
      canCreate: group.canCreate === true,
    })
  }
  const rows = [...groups.values()]
  if (keyword) return rows.filter(group => (group.count || 0) > 0)
  return rows
})

watch(treeData, data => {
  expandedKeys.value = data.filter(node => node.isGroup).map(node => node.key)
}, { immediate: true })

function onSelect(selectedKeys: Array<string | number>): void {
  if (!selectedKeys.length) return
  const key = String(selectedKeys[0])
  if (key.startsWith('tenant:')) return
  const application = props.applications.find(item => item.id === key)
  if (application) emit('select', application)
}

function onCreate(tenantId?: string): void {
  if (!tenantId) return
  emit('create', tenantId)
}

function onCreateFromHeader(): void {
  onCreate(firstCreatableTenantId.value)
}

function onMore(appId: string | undefined, action: AppMoreAction): void {
  if (!appId) return
  emit('more', { id: appId, action })
}
</script>

<template>
  <aside class="flex min-w-0 flex-col gap-3 self-start rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
    <AdminSearchField v-model="searchText" placeholder="搜索应用名称或 Client ID" :submit-on-clear="false" />
    <a-button v-if="canCreateAny" type="primary" class="w-full" @click="onCreateFromHeader">新建应用</a-button>
    <a-spin :spinning="loading" class="min-h-24">
      <a-tree
        v-if="treeData.length"
        v-model:expanded-keys="expandedKeys"
        :tree-data="treeData"
        :selected-keys="selectedId ? [selectedId] : []"
        block-node
        @select="onSelect"
      >
        <template #title="{ isGroup, title, status, count, canCreate, tenantId, appId, trusted }">
          <span v-if="isGroup" class="flex w-full min-w-0 items-center justify-between gap-2">
            <span class="inline-flex min-w-0 items-center gap-1.5">
              <span class="truncate text-xs font-medium tracking-wide text-[var(--color-text-secondary)]">{{ title }}</span>
              <span class="shrink-0 rounded-full bg-[var(--color-bg-subtle)] px-1.5 font-mono text-[10px] leading-4 text-[var(--color-text-muted)] tabular-nums">{{ count }}</span>
            </span>
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
                  <a-menu-item key="create" @click="onCreate(tenantId)">新建应用</a-menu-item>
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
                  <a-menu-item v-if="canCreate" key="create" @click="onCreate(tenantId)">新建应用</a-menu-item>
                  <a-menu-item key="edit" @click="onMore(appId, 'edit')">编辑资料</a-menu-item>
                  <a-menu-item key="rotateSecret" @click="onMore(appId, 'rotateSecret')">轮换密钥</a-menu-item>
                  <a-menu-item key="trust" @click="onMore(appId, 'trust')">{{ trusted ? '撤销信任' : '设为受信' }}</a-menu-item>
                  <a-menu-item key="status" @click="onMore(appId, 'status')">{{ status === 'active' ? '停用应用' : '启用应用' }}</a-menu-item>
                  <a-menu-item key="delete" danger @click="onMore(appId, 'delete')">删除应用</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </span>
        </template>
      </a-tree>
      <AdminEmpty v-else-if="!loading" emoji="🧩" description="暂无可管理的应用" />
    </a-spin>
  </aside>
</template>
