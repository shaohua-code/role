<script setup lang="ts">
// 角色挂码编辑弹窗：资源权限 / 数据权限两 Tab，勾选可授权节点。
import { computed, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { ExclamationCircleOutlined } from '@/plugins/icons'
import { isManagementCode, permissionNamespace, resolvePermissionScope } from '@/utils/permissionGroups'
import { asPagedList } from '@/utils/paged'
import ResourceIcon from '@/views/application-workspace/components/ResourceIcon.vue'
import {
  KIND_LABELS,
  buildPermissionTrees,
  filterPermissionTree,
  flattenGrantable,
  inferPermissionKind,
  kindIconType,
  relatedApiCodes,
  type PermissionKind,
  type PermissionTreeNode,
} from '@/utils/permissionTree'

interface PermissionRecord { id: string; code: string; description?: string | null; status: 'active' | 'disabled'; catalog_namespace?: string; kind?: PermissionKind }
interface PermissionGrant { permission_id: string; resource_id: string | null }
interface PermissionImpact {
  current_permission_ids: string[]
  grant_permission_codes: string[]
  revoke_permission_codes: string[]
  data_scopes_to_delete?: { permission_id: string; permission_code: string; scope_type: string }[]
  bound_active_members?: number
  potentially_affected_members: number
  analysis_note: string
  permission_impacts: { permission_code: string; action: 'grant' | 'revoke'; eligible_members: number; covered_by_other_general_roles: number; potentially_affected_members: number }[]
}

const props = withDefaults(defineProps<{
  roleId: string
  roleName?: string
  catalogPath: string
  grantsPath: string
  disableIamCodes?: boolean
  lockAuthorityCodes?: boolean
  roleKind?: '' | 'platform' | 'tenant' | 'application'
  roleNamespace?: string
  embedded?: boolean
}>(), {
  roleName: '',
  disableIamCodes: false,
  lockAuthorityCodes: false,
  roleKind: '',
  roleNamespace: '',
  embedded: false,
})

const HIDDEN_SCOPES_BY_KIND: Record<string, Set<string>> = {
  platform: new Set(),
  tenant: new Set(['platform', 'business']),
  application: new Set(['platform', 'tenant']),
}

const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>('open', { default: false })

const loading = ref(false)
const previewing = ref(false)
const saving = ref(false)
const catalogItems = ref<PermissionRecord[]>([])
const selectedIds = ref<string[]>([])
const impact = ref<PermissionImpact | null>(null)
const impactPreviewKey = ref('')
const searchText = ref('')
const expandedKeys = ref<string[]>([])
const initialGrantedIds = ref(new Set<string>())
const activeTab = ref<'resource' | 'data'>('resource')

const optionsById = computed(() => new Map(catalogItems.value.map(item => [item.id, item])))
const selectedCodeSet = computed(() => {
  const codes = new Set<string>()
  for (const id of selectedIds.value) {
    const item = optionsById.value.get(id)
    if (item) codes.add(item.code)
  }
  return codes
})

const catalogTrees = computed(() => buildPermissionTrees(catalogItems.value.map(item => ({
  id: item.id,
  code: item.code,
  description: item.description,
  catalog_namespace: item.catalog_namespace,
  status: item.status,
  kind: item.kind,
}))))

const catalogTree = computed(() =>
  activeTab.value === 'data' ? catalogTrees.value.data : catalogTrees.value.resource)

const displayTree = computed(() => filterPermissionTree(catalogTree.value, searchText.value, []))

const lockedIds = computed(() => {
  const locked = new Set<string>()
  if (!props.disableIamCodes) return locked
  for (const item of catalogItems.value) {
    if (isManagementCode(item.code) && !initialGrantedIds.value.has(item.id)) locked.add(item.id)
  }
  return locked
})

const checkableTree = computed(() => {
  const mark = (nodes: PermissionTreeNode[]): Array<PermissionTreeNode & { disableCheckbox: boolean }> =>
    nodes.map(node => ({
      ...node,
      disableCheckbox: !node.selectable || !node.code || lockedIds.value.has(node.key),
      children: mark(node.children),
    }))
  return mark(displayTree.value)
})

function selectedCountForKind(kind: PermissionKind): number {
  return selectedIds.value.filter(id => {
    const item = optionsById.value.get(id)
    return item ? (item.kind || inferPermissionKind(item.code)) === kind : false
  }).length
}

const checkedState = computed(() => ({ checked: selectedIds.value, halfChecked: [] as string[] }))

const leafIdSet = computed(() => new Set([
  ...flattenGrantable(catalogTrees.value.resource),
  ...flattenGrantable(catalogTrees.value.data),
].map(node => node.key)))

function asTreeNode(slotNode: PermissionTreeNode & { dataRef?: PermissionTreeNode; record?: PermissionTreeNode }): PermissionTreeNode {
  return slotNode.dataRef || slotNode.record || slotNode
}

function onTreeCheck(info: string[] | { checked?: string[] }): void {
  const keys = Array.isArray(info) ? info : (info.checked || [])
  const currentGrantable = new Set(flattenGrantable(catalogTree.value).map(node => node.key))
  const kept = selectedIds.value.filter(id => !currentGrantable.has(id))
  selectedIds.value = [...kept, ...keys.filter(key => leafIdSet.value.has(key))]
}


function missingRelatedHint(code: string): string {
  const related = relatedApiCodes(code)
  if (!related.length) return ''
  if (related.some(item => selectedCodeSet.value.has(item))) return ''
  if (code.startsWith('menu.')) return '只勾菜单不勾接口时，侧栏能进页面，列表会 403'
  if (code.startsWith('button.')) return '只勾按钮不勾接口时，按钮能点，写操作会 403'
  return ''
}

const selectionOrder = ref<string[]>([])
watch(selectedIds, now => {
  const nowSet = new Set(now)
  selectionOrder.value = selectionOrder.value.filter(id => nowSet.has(id))
  for (const id of now) {
    if (!selectionOrder.value.includes(id)) selectionOrder.value.push(id)
  }
})

const recentSelected = computed(() => {
  const recent = [...selectionOrder.value].reverse()
    .map(id => optionsById.value.get(id))
    .filter((item): item is PermissionRecord => Boolean(item))
  return { items: recent.slice(0, 6), overflow: Math.max(0, recent.length - 6) }
})

function removeSelected(id: string): void {
  selectedIds.value = selectedIds.value.filter(value => value !== id)
}

function clearSelection(): void {
  selectedIds.value = []
}

const descriptionByCode = ref(new Map<string, string>())
function codeLabel(code: string): string {
  const description = descriptionByCode.value.get(code)
  return description ? `${description}（${code}）` : code
}

const selectionKey = computed(() => [...selectedIds.value].sort().join('|'))
const previewIsCurrent = computed(() => Boolean(impact.value) && impactPreviewKey.value === selectionKey.value)
const selectionChanged = computed(() => Boolean(impact.value) && !previewIsCurrent.value)
const noChanges = computed(() => {
  const current = impact.value
  return current !== null && current.grant_permission_codes.length === 0 && current.revoke_permission_codes.length === 0
})

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

watch(activeTab, () => {
  expandedKeys.value = collectExpandKeys(catalogTree.value)
})

async function loadGrants(): Promise<void> {
  if (!props.roleId || !props.catalogPath || !props.grantsPath) return
  loading.value = true
  impact.value = null
  impactPreviewKey.value = ''
  try {
    const [catalog, grants] = await Promise.all([
      api<PermissionRecord[] | { items: PermissionRecord[] }>(props.catalogPath).then(result => asPagedList(result).items),
      api<PermissionGrant[]>(props.grantsPath),
    ])
    if (!open.value) return
    let currentIds = grants.filter(grant => grant.resource_id === null).map(grant => grant.permission_id)
    const currentSet = new Set(currentIds)
    const hiddenScopes = HIDDEN_SCOPES_BY_KIND[props.roleKind || '']
    const visibleCatalog = catalog.filter(permission => {
      if (currentSet.has(permission.id)) return true
      if (!hiddenScopes || !hiddenScopes.size) return true
      const scopeKey = resolvePermissionScope(permission.code).key
      if (hiddenScopes.has(scopeKey)) return false
      if (props.roleKind === 'application' && scopeKey === 'business' && props.roleNamespace) {
        return permissionNamespace(permission.code) === props.roleNamespace
      }
      return true
    })
    const codeDescriptions = new Map<string, string>()
    catalogItems.value = visibleCatalog
      .filter(permission => permission.status === 'active' || currentSet.has(permission.id))
      .map(permission => {
        const description = (permission.description || '').trim()
        if (description) codeDescriptions.set(permission.code, description)
        return permission
      })
    descriptionByCode.value = codeDescriptions
    selectedIds.value = currentIds
    initialGrantedIds.value = new Set(currentIds)
    expandedKeys.value = collectExpandKeys(catalogTrees.value.resource)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '权限编码读取失败')
    open.value = false
  } finally {
    loading.value = false
  }
}

async function previewChanges(): Promise<void> {
  previewing.value = true
  try {
    impact.value = await api<PermissionImpact>(`${props.grantsPath}/preview`, {
      method: 'POST',
      body: JSON.stringify({ permission_ids: selectedIds.value }),
    })
    impactPreviewKey.value = selectionKey.value
  } catch (error) {
    impact.value = null
    impactPreviewKey.value = ''
    message.error(error instanceof Error ? error.message : '授权影响预览失败')
  } finally {
    previewing.value = false
  }
}

function confirmSave(): void {
  const current = impact.value
  if (!current || !previewIsCurrent.value) {
    void previewChanges()
    message.info('先预览授权影响，核对结果后再确认保存')
    return
  }
  if (noChanges.value) {
    message.info('权限集合没有变化')
    return
  }
  const summary = [
    `新增 ${current.grant_permission_codes.length} 项授权`,
    `撤销 ${current.revoke_permission_codes.length} 项授权`,
    current.data_scopes_to_delete ? `清理 ${current.data_scopes_to_delete.length} 项失去授权前置条件的数据范围` : '',
    current.bound_active_members !== undefined
      ? `当前潜在覆盖 ${current.bound_active_members} 名活动成员`
      : `潜在受影响 ${current.potentially_affected_members} 位成员`,
  ].filter(Boolean).join('；')
  Modal.confirm({
    title: `确认更新「${props.roleName || '角色'}」的授权？`,
    content: `${summary}。${current.analysis_note}`,
    okText: '确认并保存',
    cancelText: '返回检查',
    onOk: applySave,
  })
}

async function applySave(): Promise<void> {
  const current = impact.value
  if (!current) return
  saving.value = true
  try {
    await api(props.grantsPath, {
      method: 'PUT',
      body: JSON.stringify({
        permission_ids: selectedIds.value,
        expected_current_permission_ids: current.current_permission_ids,
      }),
    })
    message.success('角色权限已原子更新')
    if (!props.embedded) open.value = false
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '权限保存失败；如授权已被其他管理员更新，请重新预览')
  } finally {
    saving.value = false
  }
}

watch(open, value => {
  if (value) void loadGrants()
  else {
    catalogItems.value = []
    selectedIds.value = []
    selectionOrder.value = []
    impact.value = null
    impactPreviewKey.value = ''
    searchText.value = ''
    activeTab.value = 'resource'
    initialGrantedIds.value = new Set()
  }
}, { immediate: true })
</script>

<template>
  <component
    :is="embedded ? 'div' : 'a-modal'"
    v-bind="embedded ? { class: 'flex min-w-0 flex-col' } : { open, title: `配置角色权限${roleName ? `：${roleName}` : ''}`, width: '880px', footer: null }"
    @update:open="(value: boolean) => open = value"
  >
    <a-spin :spinning="loading">
      <div class="flex min-w-0 flex-col gap-3">
        <p class="m-0 flex flex-wrap items-center gap-1.5 text-xs text-[var(--color-text-muted)]">
          <ExclamationCircleOutlined class="text-[13px]" />
          <span>先预览再保存。菜单、按钮、接口独立勾选：只给菜单不给接口时，侧栏能进、列表会 403。</span>
        </p>
        <div class="flex flex-wrap items-center gap-2">
          <a-input v-model:value="searchText" allow-clear placeholder="搜索中文名或编码" class="max-w-xs" />
          <span class="ml-auto font-mono text-xs text-[var(--color-text-muted)]">已选 {{ selectedIds.length }}</span>
        </div>
        <div class="flex flex-wrap items-center gap-1.5 border border-dashed border-[var(--color-border)] px-2.5 py-2 rounded-[8px]">
          <span class="mr-0.5 text-[12.5px] font-semibold text-[var(--color-text-primary)]">已选 {{ selectedIds.length }} 项</span>
          <span v-if="!selectedIds.length" class="text-[12.5px] text-[var(--color-text-muted)]">尚未选择任何权限编码</span>
          <template v-else>
            <button
              v-for="item in recentSelected.items"
              :key="item.id"
              type="button"
              class="inline-flex max-w-[220px] cursor-pointer items-center gap-1 border border-solid border-[var(--color-border-strong)] bg-[var(--color-bg-container)] px-2 py-0 rounded-full text-xs leading-5 text-[var(--color-text-primary)] hover:border-[var(--color-text-secondary)]"
              :title="`${item.description || item.code}（点击取消勾选）`"
              @click="removeSelected(item.id)"
            >
              <span class="truncate">{{ item.description || item.code }}</span>
              <span class="text-[var(--color-text-muted)]">×</span>
            </button>
            <span v-if="recentSelected.overflow" class="font-mono text-xs text-[var(--color-text-muted)]">+{{ recentSelected.overflow }}</span>
            <button type="button" class="ml-auto cursor-pointer border-0 bg-transparent text-xs text-[var(--color-text-secondary)] underline underline-offset-[3px] hover:text-[var(--color-text-primary)]" @click="clearSelection">清空</button>
          </template>
        </div>
        <a-tabs v-model:activeKey="activeTab" size="small" destroy-inactive-tab-pane>
          <a-tab-pane key="resource" :tab="`资源权限 ${selectedCountForKind('menu') + selectedCountForKind('button') + selectedCountForKind('api')}`">
            <div class="max-h-[52vh] min-h-32 overflow-auto">
              <div class="min-w-0 rounded-[var(--radius-lg)] border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-3">
                <a-tree
                  v-if="checkableTree.length"
                  v-model:expanded-keys="expandedKeys"
                  checkable
                  check-strictly
                  block-node
                  :checked-keys="checkedState"
                  :tree-data="checkableTree"
                  :field-names="{ title: 'title', key: 'key', children: 'children' }"
                  @check="onTreeCheck"
                >
                  <template #title="slotNode">
                    <div class="flex min-w-0 flex-1 items-center gap-2 py-0.5">
                      <ResourceIcon
                        :type="kindIconType(asTreeNode(slotNode).kind)"
                        :icon="asTreeNode(slotNode).kind === 'api' ? 'SafetyOutlined' : ''"
                        class="shrink-0 text-[15px] text-[var(--color-text-secondary)]"
                      />
                      <span class="truncate text-sm text-[var(--color-text-primary)]">{{ asTreeNode(slotNode).title }}</span>
                      <span
                        v-if="asTreeNode(slotNode).code"
                        class="max-w-[200px] shrink truncate font-mono text-xs text-[var(--color-text-muted)]"
                      >{{ asTreeNode(slotNode).code }}</span>
                      <span
                        v-if="asTreeNode(slotNode).code"
                        class="shrink-0 border border-solid border-[var(--color-border)] px-1 rounded-[2px] text-[10px] leading-4 text-[var(--color-text-muted)]"
                      >{{ KIND_LABELS[asTreeNode(slotNode).kind] }}</span>
                      <span
                        v-if="asTreeNode(slotNode).selectable && asTreeNode(slotNode).code && missingRelatedHint(asTreeNode(slotNode).code as string) && selectedIds.includes(asTreeNode(slotNode).key)"
                        class="shrink truncate text-[11px] text-[var(--color-warning)]"
                      >{{ missingRelatedHint(asTreeNode(slotNode).code as string) }}</span>
                    </div>
                  </template>
                </a-tree>
                <p v-else class="m-0 text-xs text-[var(--color-text-muted)]">没有匹配的权限项</p>
              </div>
            </div>
          </a-tab-pane>
          <a-tab-pane key="data" :tab="`数据权限 ${selectedCountForKind('data')}`">
            <div class="max-h-[52vh] min-h-32 overflow-auto">
              <div class="min-w-0 rounded-[var(--radius-lg)] border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-3">
                <a-tree
                  v-if="checkableTree.length"
                  v-model:expanded-keys="expandedKeys"
                  checkable
                  check-strictly
                  block-node
                  :checked-keys="checkedState"
                  :tree-data="checkableTree"
                  :field-names="{ title: 'title', key: 'key', children: 'children' }"
                  @check="onTreeCheck"
                >
                  <template #title="slotNode">
                    <div class="flex min-w-0 flex-1 items-center gap-2 py-0.5">
                      <ResourceIcon type="data_rule" class="shrink-0 text-[15px] text-[var(--color-text-secondary)]" />
                      <span class="truncate text-sm text-[var(--color-text-primary)]">{{ asTreeNode(slotNode).title }}</span>
                      <span
                        v-if="asTreeNode(slotNode).code"
                        class="max-w-[200px] shrink truncate font-mono text-xs text-[var(--color-text-muted)]"
                      >{{ asTreeNode(slotNode).code }}</span>
                    </div>
                  </template>
                </a-tree>
                <p v-else class="m-0 text-xs text-[var(--color-text-muted)]">还没有数据权限叶子。管理面 27 个接口码不进这里。</p>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
        <a-alert v-if="selectionChanged" type="warning" show-icon message="选择已变化，请重新预览后再保存" />
        <template v-if="impact && previewIsCurrent">
          <a-alert
            type="warning"
            show-icon
            :message="impact.bound_active_members !== undefined
              ? `角色关联 ${impact.bound_active_members} 名活动成员（直接或用户组继承）；潜在受影响 ${impact.potentially_affected_members} 名`
              : `潜在受影响 ${impact.potentially_affected_members} 位成员（含直接绑定和用户组继承）`"
            :description="impact.analysis_note"
          />
          <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <div class="border border-solid border-[var(--color-border)] px-3 py-2.5 rounded-[8px]">
              <p class="mb-1.5 mt-0 text-[13px] font-semibold text-[var(--color-success,#166534)]">新增 {{ impact.grant_permission_codes.length }} 项</p>
              <p v-if="!impact.grant_permission_codes.length" class="m-0 text-[12.5px] text-[var(--color-text-muted)]">无新增授权</p>
              <p v-for="code in impact.grant_permission_codes" :key="code" class="mb-0.5 mt-0 break-all text-[12.5px] text-[var(--color-text-secondary)]">{{ codeLabel(code) }}</p>
            </div>
            <div class="border border-solid border-[var(--color-border)] px-3 py-2.5 rounded-[8px]">
              <p class="mb-1.5 mt-0 text-[13px] font-semibold text-[var(--color-error,#b91c1c)]">撤销 {{ impact.revoke_permission_codes.length }} 项</p>
              <p v-if="!impact.revoke_permission_codes.length" class="m-0 text-[12.5px] text-[var(--color-text-muted)]">无撤销授权</p>
              <p v-for="code in impact.revoke_permission_codes" :key="code" class="mb-0.5 mt-0 break-all text-[12.5px] text-[var(--color-text-secondary)]">{{ codeLabel(code) }}</p>
            </div>
          </div>
          <p v-for="item in impact.permission_impacts" :key="`${item.action}:${item.permission_code}`" class="m-0 text-sm">
            {{ item.action === 'grant' ? '新增' : '撤销' }} {{ codeLabel(item.permission_code) }}：潜在影响 {{ item.potentially_affected_members }} 名，其他通用角色已覆盖 {{ item.covered_by_other_general_roles }} 名
          </p>
          <p v-if="impact.data_scopes_to_delete?.length" class="m-0 text-sm">同时清理失去授权前置条件的数据范围：{{ impact.data_scopes_to_delete.map(item => `${codeLabel(item.permission_code)}（${item.scope_type}）`).join('、') }}</p>
          <p v-else-if="impact.data_scopes_to_delete" class="m-0 text-sm">无需清理数据范围策略。</p>
        </template>
        <div :class="['flex items-center justify-between border-t border-solid border-[var(--color-border)] bg-[var(--color-bg-container)] pt-3', embedded ? 'static' : 'sticky bottom-0 z-[2]']">
          <a-button v-if="!embedded" @click="open = false">取消</a-button>
          <div v-else />
          <div class="flex items-center gap-2">
            <a-button :loading="previewing" :disabled="loading || saving" @click="previewChanges">预览影响</a-button>
            <a-button type="primary" :loading="saving" :disabled="loading || previewing || !previewIsCurrent || noChanges" @click="confirmSave">保存授权</a-button>
          </div>
        </div>
      </div>
    </a-spin>
  </component>
</template>
