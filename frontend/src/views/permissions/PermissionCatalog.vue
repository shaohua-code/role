<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHasAny, getCachedCapabilities } from '@/api/capabilities'
import { PlusOutlined } from '@/plugins/icons'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import AdminDetailDrawer from '@/components/AdminDetailDrawer.vue'
import AdminStatBand from '@/components/AdminStatBand.vue'
import ResourceIcon from '@/views/application-workspace/components/ResourceIcon.vue'
import { asPagedList } from '@/utils/paged'
import {
  CREATE_KIND_OPTIONS,
  KIND_LABELS,
  createPrefixForNode,
  filterPermissionTree,
  kindIconType,
  type PermissionKind,
  type PermissionTreeNode,
} from '@/utils/permissionTree'

interface TreeApiNode {
  key: string
  title: string
  kind: PermissionKind
  code: string | null
  status: string
  assigned_role_count: number
  is_leaf?: boolean
  isLeaf?: boolean
  selectable?: boolean
  prefix?: string
  parent_code?: string | null
  parent_title?: string | null
  children?: TreeApiNode[]
}

interface RefRoleRecord {
  id: string
  name: string
  key: string
  kind: string
  status: string
  permission_codes?: string[]
}

const props = defineProps<{ active: boolean }>()
const canManageCatalog = computed(() =>
  getCachedCapabilities()?.platform_admin === true
  || cachedHasAny(['button.permissions.manage']))

const loading = ref(false)
const errorText = ref('')
const resourceTree = ref<PermissionTreeNode[]>([])
const dataTree = ref<PermissionTreeNode[]>([])
const expandedKeys = ref<string[]>([])
const searchText = ref('')
const activeTab = ref<'resource' | 'data'>('resource')
const changingPermissionId = ref('')
const createOpen = ref(false)
const creating = ref(false)
const form = reactive({
  parentTitle: '',
  parentCode: '',
  prefix: '',
  tail: '',
  kind: 'button' as PermissionKind,
  description: '',
})
const refsOpen = ref(false)
const refsPermission = ref<PermissionTreeNode | null>(null)
const refsRoles = ref<RefRoleRecord[]>([])
const refsLoading = ref(false)
const refsCache = new Map<string, RefRoleRecord[]>()
let requestSequence = 0

const stats = computed(() => {
  const counts = { menu: 0, button: 0, data: 0, api: 0, active: 0 }
  const walk = (nodes: PermissionTreeNode[]) => {
    for (const node of nodes) {
      if (node.code) {
        counts[node.kind] += 1
        if (node.status === 'active') counts.active += 1
      }
      if (node.children.length) walk(node.children)
    }
  }
  walk(resourceTree.value)
  walk(dataTree.value)
  return [
    { key: 'all', label: '权限编码', count: counts.menu + counts.button + counts.data + counts.api, sub: `活动 ${counts.active}`, disabled: false },
    { key: 'menu', label: '菜单', count: counts.menu, sub: '侧栏可见', disabled: false },
    { key: 'button', label: '按钮', count: counts.button, sub: '页内写操作', disabled: false },
    { key: 'api', label: '接口', count: counts.api, sub: '路由鉴权', disabled: false },
  ]
})

function asTreeNode(slotNode: PermissionTreeNode & { dataRef?: PermissionTreeNode; record?: PermissionTreeNode }): PermissionTreeNode {
  return slotNode.dataRef || slotNode.record || slotNode
}

function hydrate(node: TreeApiNode): PermissionTreeNode {
  const children = (node.children || []).map(hydrate)
  return {
    key: node.key,
    title: node.title,
    kind: node.kind,
    code: node.code,
    status: node.status,
    assigned_role_count: node.assigned_role_count || 0,
    isLeaf: Boolean(node.is_leaf ?? node.isLeaf),
    selectable: node.selectable !== false,
    children,
    prefix: node.prefix || '',
    parentCode: node.parent_code || null,
    parentTitle: node.parent_title || null,
  }
}

const currentTree = computed(() => activeTab.value === 'data' ? dataTree.value : resourceTree.value)

const displayTree = computed(() =>
  filterPermissionTree(currentTree.value, searchText.value, [], []))

function collectExpandKeys(nodes: PermissionTreeNode[], depth = 0): string[] {
  const keys: string[] = []
  for (const node of nodes) {
    if (node.children.length && depth < 2) {
      keys.push(node.key)
      keys.push(...collectExpandKeys(node.children, depth + 1))
    }
  }
  return keys
}

async function loadPermissions(): Promise<void> {
  if (!props.active) return
  const sequence = ++requestSequence
  loading.value = true
  errorText.value = ''
  refsCache.clear()
  try {
    const result = await api<{ resource?: TreeApiNode[]; data?: TreeApiNode[]; items?: TreeApiNode[] }>('/admin/permissions/tree')
    if (sequence !== requestSequence || !props.active) return
    resourceTree.value = (result.resource || result.items || []).map(hydrate)
    dataTree.value = (result.data || []).map(hydrate)
    expandedKeys.value = collectExpandKeys(currentTree.value)
  } catch (error) {
    if (sequence !== requestSequence) return
    resourceTree.value = []
    dataTree.value = []
    errorText.value = error instanceof Error ? error.message : '读取权限编码失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

watch(activeTab, () => {
  expandedKeys.value = collectExpandKeys(currentTree.value)
})

function canCreateUnder(node: PermissionTreeNode): boolean {
  if (!canManageCatalog.value) return false
  if (node.kind === 'button' || node.kind === 'api') return false
  if (node.kind === 'data' && node.code && node.isLeaf) return false
  return true
}

function kindDefaults(kind: PermissionKind): { resource_type: string; scope: string } {
  if (kind === 'menu') return { resource_type: 'menu', scope: 'read' }
  if (kind === 'button') return { resource_type: 'button', scope: 'manage' }
  if (kind === 'data') return { resource_type: 'data', scope: 'self' }
  return { resource_type: 'api', scope: 'read' }
}

function openCreate(node: PermissionTreeNode): void {
  form.prefix = createPrefixForNode(node)
  form.parentTitle = node.title
  form.parentCode = node.code || form.prefix.replace(/\.$/, '')
  form.tail = ''
  form.kind = node.kind === 'data' ? 'data' : 'button'
  form.description = ''
  createOpen.value = true
}

function fullCreateCode(): string {
  return `${form.prefix}${form.tail}`.trim()
}

async function createPermission(): Promise<void> {
  const code = fullCreateCode()
  if (code.length < 3 || code.length > 180) {
    message.error('权限编码至少 3 个字符，最长 180')
    return
  }
  if (!form.tail.trim()) {
    message.error('请填写编码后段')
    return
  }
  creating.value = true
  const defaults = kindDefaults(form.kind)
  try {
    await api('/admin/permissions', {
      method: 'POST',
      body: JSON.stringify({
        code,
        resource_type: defaults.resource_type,
        scope: defaults.scope,
        description: form.description.trim() || null,
        kind: form.kind,
        surface: form.kind === 'data' ? 'business' : 'management',
        requires_data_scope: false,
      }),
    })
    message.success('权限项已创建')
    createOpen.value = false
    await loadPermissions()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建权限项失败')
  } finally {
    creating.value = false
  }
}

function changeStatus(node: PermissionTreeNode): void {
  if (!node.code) return
  const nextStatus = node.status === 'active' ? 'disabled' : 'active'
  Modal.confirm({
    title: nextStatus === 'active' ? '恢复该权限编码？' : '停用该权限编码？',
    content: nextStatus === 'active'
      ? `恢复后历史角色授权将重新生效（关联 ${node.assigned_role_count} 个角色）。`
      : `停用会立即让在线授权判定失败；${node.assigned_role_count} 个角色的既有授权会保留。`,
    okText: nextStatus === 'active' ? '恢复权限' : '确认停用',
    okType: nextStatus === 'active' ? 'primary' : 'danger',
    cancelText: '取消',
    onOk: async () => {
      changingPermissionId.value = node.key
      try {
        await api(`/admin/permissions/${node.key}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ expected_status: node.status, status: nextStatus }),
        })
        message.success(nextStatus === 'active' ? '权限已恢复' : '权限已停用')
        await loadPermissions()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '更新权限状态失败')
      } finally {
        changingPermissionId.value = ''
      }
    },
  })
}

async function openRefs(node: PermissionTreeNode): Promise<void> {
  if (!node.code) return
  refsPermission.value = node
  refsOpen.value = true
  const cached = refsCache.get(node.code)
  if (cached) {
    refsRoles.value = cached
    return
  }
  refsRoles.value = []
  refsLoading.value = true
  try {
    const roles = asPagedList(await api<RefRoleRecord[] | { items: RefRoleRecord[] }>('/admin/roles?role_class=platform&limit=500')).items
    const matched = roles.filter(role => Array.isArray(role.permission_codes) && role.permission_codes.includes(node.code as string))
    refsCache.set(node.code, matched)
    if (refsPermission.value?.code === node.code) refsRoles.value = matched
  } catch (error) {
    if (refsPermission.value?.code === node.code) message.error(error instanceof Error ? error.message : '读取引用角色失败')
  } finally {
    refsLoading.value = false
  }
}

watch(() => props.active, active => {
  if (active) void loadPermissions()
}, { immediate: true })
</script>

<template>
  <section class="flex w-full min-w-0 flex-col gap-4">
    <AdminStatBand numbered :stats="stats" />
    <div class="flex flex-col gap-1">
      <p class="m-0 text-xs uppercase tracking-wide text-[var(--color-text-muted)]">权限编码</p>
      <h1 class="m-0 text-xl font-semibold text-[var(--color-text-primary)]">权限编码</h1>
      <p class="m-0 text-sm text-[var(--color-text-secondary)]">资源权限按现网侧栏分组；菜单下挂按钮和接口。数据权限单独一棵树。勾选独立：只勾菜单不勾接口时侧栏能进、列表会 403。</p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <AdminSearchField v-model="searchText" placeholder="搜索中文名或编码" :submit-on-clear="false" />
      <span class="ml-auto flex items-center gap-2">
        <a-button :loading="loading" @click="loadPermissions">刷新</a-button>
      </span>
    </div>
    <p v-if="errorText" class="m-0 text-sm text-[var(--color-danger)]">{{ errorText }}</p>
    <a-tabs v-model:activeKey="activeTab" size="small" destroy-inactive-tab-pane>
      <a-tab-pane key="resource" tab="资源权限">
        <a-spin :spinning="loading" class="min-h-32">
          <div v-if="displayTree.length" class="min-w-0 rounded-[var(--radius-lg)] border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
            <a-tree
              v-model:expanded-keys="expandedKeys"
              :tree-data="displayTree"
              :field-names="{ title: 'title', key: 'key', children: 'children' }"
              block-node
            >
              <template #title="slotNode">
                <div class="group/node flex min-w-0 flex-1 items-center gap-2 py-0.5">
                  <ResourceIcon
                    :type="kindIconType(asTreeNode(slotNode).kind)"
                    :icon="asTreeNode(slotNode).kind === 'api' ? 'SafetyOutlined' : ''"
                    class="shrink-0 text-[15px] text-[var(--color-text-secondary)]"
                  />
                  <span class="truncate text-sm text-[var(--color-text-primary)]">{{ asTreeNode(slotNode).title }}</span>
                  <span
                    v-if="asTreeNode(slotNode).code"
                    class="max-w-[220px] shrink truncate font-mono text-xs text-[var(--color-text-muted)]"
                    :title="asTreeNode(slotNode).code || ''"
                  >{{ asTreeNode(slotNode).code }}</span>
                  <span
                    v-if="asTreeNode(slotNode).code"
                    class="shrink-0 border border-solid border-[var(--color-border)] px-1 rounded-[2px] text-[10px] leading-4 text-[var(--color-text-muted)]"
                  >{{ KIND_LABELS[asTreeNode(slotNode).kind] }}</span>
                  <a-tag v-if="asTreeNode(slotNode).code && asTreeNode(slotNode).status === 'active'" class="mr-0 shrink-0" color="green">启用</a-tag>
                  <a-tag v-else-if="asTreeNode(slotNode).code" class="mr-0 shrink-0">停用</a-tag>
                  <a-button
                    v-if="asTreeNode(slotNode).code"
                    type="link"
                    size="small"
                    class="px-0 text-xs"
                    @click.stop="openRefs(asTreeNode(slotNode))"
                  >{{ asTreeNode(slotNode).assigned_role_count }} 个角色</a-button>
                  <span class="ml-auto flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover/node:opacity-100">
                    <a-button
                      v-if="canCreateUnder(asTreeNode(slotNode))"
                      type="link"
                      size="small"
                      class="text-xs"
                      @click.stop="openCreate(asTreeNode(slotNode))"
                    >
                      <template #icon><PlusOutlined /></template>
                      新建
                    </a-button>
                    <a-button
                      v-if="canManageCatalog && asTreeNode(slotNode).code"
                      type="link"
                      size="small"
                      class="text-xs"
                      :danger="asTreeNode(slotNode).status === 'active'"
                      :loading="changingPermissionId === asTreeNode(slotNode).key"
                      @click.stop="changeStatus(asTreeNode(slotNode))"
                    >{{ asTreeNode(slotNode).status === 'active' ? '停用' : '恢复' }}</a-button>
                  </span>
                </div>
              </template>
            </a-tree>
          </div>
          <AdminEmpty v-else-if="!loading" emoji="🔐" :description="searchText ? '没有匹配的权限项' : '暂无资源权限'" />
        </a-spin>
      </a-tab-pane>
      <a-tab-pane key="data" tab="数据权限">
        <a-spin :spinning="loading" class="min-h-32">
          <div v-if="displayTree.length" class="min-w-0 rounded-[var(--radius-lg)] border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
            <a-tree
              v-model:expanded-keys="expandedKeys"
              :tree-data="displayTree"
              :field-names="{ title: 'title', key: 'key', children: 'children' }"
              block-node
            >
              <template #title="slotNode">
                <div class="group/node flex min-w-0 flex-1 items-center gap-2 py-0.5">
                  <ResourceIcon
                    type="data_rule"
                    class="shrink-0 text-[15px] text-[var(--color-text-secondary)]"
                  />
                  <span class="truncate text-sm text-[var(--color-text-primary)]">{{ asTreeNode(slotNode).title }}</span>
                  <span
                    v-if="asTreeNode(slotNode).code"
                    class="max-w-[220px] shrink truncate font-mono text-xs text-[var(--color-text-muted)]"
                  >{{ asTreeNode(slotNode).code }}</span>
                  <a-button
                    v-if="asTreeNode(slotNode).code"
                    type="link"
                    size="small"
                    class="px-0 text-xs"
                    @click.stop="openRefs(asTreeNode(slotNode))"
                  >{{ asTreeNode(slotNode).assigned_role_count }} 个角色</a-button>
                  <span class="ml-auto flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover/node:opacity-100">
                    <a-button
                      v-if="canCreateUnder(asTreeNode(slotNode))"
                      type="link"
                      size="small"
                      class="text-xs"
                      @click.stop="openCreate(asTreeNode(slotNode))"
                    >
                      <template #icon><PlusOutlined /></template>
                      新建
                    </a-button>
                    <a-button
                      v-if="canManageCatalog && asTreeNode(slotNode).code"
                      type="link"
                      size="small"
                      class="text-xs"
                      :danger="asTreeNode(slotNode).status === 'active'"
                      :loading="changingPermissionId === asTreeNode(slotNode).key"
                      @click.stop="changeStatus(asTreeNode(slotNode))"
                    >{{ asTreeNode(slotNode).status === 'active' ? '停用' : '恢复' }}</a-button>
                  </span>
                </div>
              </template>
            </a-tree>
          </div>
          <AdminEmpty v-else-if="!loading" emoji="📂" :description="searchText ? '没有匹配的数据权限' : '开发库还没有数据权限叶子，管理面 27 个接口码不进这里'" />
        </a-spin>
      </a-tab-pane>
    </a-tabs>
    <AdminDetailDrawer
      v-model:open="refsOpen"
      :title="`引用角色 — ${refsPermission?.title || ''}`"
      :subtitle="refsPermission?.code || ''"
      :width="560"
    >
      <a-spin :spinning="refsLoading">
        <div v-if="refsRoles.length" class="flex flex-col gap-1">
          <div
            v-for="role in refsRoles"
            :key="role.id"
            class="flex items-center gap-3 border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 rounded-[var(--radius-md)]"
          >
            <div class="flex min-w-0 flex-1 flex-col">
              <span class="truncate text-[13px] text-[var(--color-text-primary)]">{{ role.name }}</span>
              <span class="truncate font-mono text-xs text-[var(--color-text-muted)]">{{ role.key }}</span>
            </div>
            <a-tag v-if="role.status !== 'active'" class="mr-0 shrink-0">已停用</a-tag>
          </div>
        </div>
        <p v-else-if="!refsLoading" class="text-xs text-[var(--color-text-muted)]">当前没有角色引用该编码。</p>
      </a-spin>
    </AdminDetailDrawer>
    <a-modal
      v-model:open="createOpen"
      title="新建权限编码"
      ok-text="创建"
      cancel-text="取消"
      :confirm-loading="creating"
      @ok="createPermission"
    >
      <div class="flex flex-col gap-3">
        <label class="flex flex-col gap-1 text-sm text-[var(--color-text-secondary)]">
          上级名称
          <a-input :value="form.parentTitle" disabled />
        </label>
        <label class="flex flex-col gap-1 text-sm text-[var(--color-text-secondary)]">
          上级编码
          <a-input :value="form.parentCode" disabled class="font-mono" />
        </label>
        <label class="flex flex-col gap-1 text-sm text-[var(--color-text-secondary)]">
          编码后段
          <a-input
            v-model:value="form.tail"
            :maxlength="160"
            class="font-mono"
            placeholder="如 export"
          />
        </label>
        <div class="border border-solid border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2 rounded-[var(--radius-md)]">
          <span class="mr-2 text-xs text-[var(--color-text-muted)]">完整编码</span>
          <span class="break-all font-mono text-xs text-[var(--color-text-primary)]">{{ fullCreateCode() || '—' }}</span>
        </div>
        <label class="flex flex-col gap-1 text-sm text-[var(--color-text-secondary)]">
          类型
          <a-select v-model:value="form.kind">
            <a-select-option v-for="option in CREATE_KIND_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</a-select-option>
          </a-select>
        </label>
        <label class="flex flex-col gap-1 text-sm text-[var(--color-text-secondary)]">
          说明
          <a-textarea v-model:value="form.description" :rows="3" :maxlength="500" show-count />
        </label>
      </div>
    </a-modal>
  </section>
</template>
