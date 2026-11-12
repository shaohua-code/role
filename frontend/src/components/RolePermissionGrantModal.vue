<script setup lang="ts">
// 角色挂码编辑弹窗：单棵「菜单→按钮」节点树 + 授权范围下拉。
// 授权范围变更先 PATCH 角色 scope，再原子替换权限授权（保持 409 冲突处理）。
import { computed, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { OPERATOR_SCOPE_RANK, operatorScope } from '@/api/capabilities'
import { ExclamationCircleOutlined } from '@/plugins/icons'
import { asPagedList } from '@/utils/paged'
import { ensurePermissionContract } from '@/utils/permissionContract'
import ResourceIcon from '@/views/application-workspace/components/ResourceIcon.vue'
import {
  EMPTY_PERMISSION_TREE_META,
  KIND_LABELS,
  ROLE_SCOPE_RANK,
  buildPermissionTrees,
  filterPermissionTree,
  flattenGrantable,
  kindIconType,
  type PermissionKind,
  type PermissionTreeMeta,
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
  /** 角色当前授权范围（super/tenant/app/member）；空值（应用工作台内嵌场景）不展示范围编辑。 */
  roleScope?: '' | 'super' | 'tenant' | 'app' | 'member'
  /** 系统模板角色范围固定，后端拒绝修改，下拉置灰。 */
  roleIsTemplate?: boolean
  embedded?: boolean
}>(), {
  roleName: '',
  roleScope: '',
  roleIsTemplate: false,
  embedded: false,
})

const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>('open', { default: false })

const loading = ref(false)
const previewing = ref(false)
const saving = ref(false)
const catalogItems = ref<PermissionRecord[]>([])
// 契约 meta：菜单→按钮映射、min_scope 下限、授权范围下拉选项均来自 tree meta（共享缓存）。
const contractMeta = ref<PermissionTreeMeta>(EMPTY_PERMISSION_TREE_META)
const selectedIds = ref<string[]>([])
const impact = ref<PermissionImpact | null>(null)
const impactPreviewKey = ref('')
const searchText = ref('')
const expandedKeys = ref<string[]>([])
// 授权范围编辑态：打开时初始化为角色当前范围
const selectedScope = ref('')

const optionsById = computed(() => new Map(catalogItems.value.map(item => [item.id, item])))

// 组树：菜单→按钮挂载关系由契约 meta 驱动；管理面只有 menu/button 两类节点。
const catalogTrees = computed(() => buildPermissionTrees(catalogItems.value.map(item => ({
  id: item.id,
  code: item.code,
  description: item.description,
  catalog_namespace: item.catalog_namespace,
  status: item.status,
  kind: item.kind,
})), contractMeta.value))

const catalogTree = computed(() => catalogTrees.value.resource)

const displayTree = computed(() => filterPermissionTree(catalogTree.value, searchText.value, []))

// 节点授权下限映射：码 → min_scope。菜单用自身下限；按钮优先 button_scopes
// （按钮可高于宿主菜单，如任命应用管理员=租户级、菜单=应用级），缺省回落菜单下限。
const minScopeByCode = computed(() => {
  const map = new Map<string, string>()
  for (const menu of contractMeta.value.menus) {
    if (!menu.min_scope) continue
    map.set(menu.code, menu.min_scope)
    for (const btn of menu.buttons || []) map.set(btn, menu.button_scopes?.[btn] || menu.min_scope)
  }
  return map
})

// 角色 scope 的秩；未传 roleScope（内嵌场景）时为 null，不做下限判定
const roleScopeRank = computed(() => (props.roleScope ? ROLE_SCOPE_RANK[props.roleScope] ?? 0 : null))

// 节点是否落在角色当前授权范围内：内嵌无范围场景或节点无码一律放行；
// 否则比较「当前所选范围秩 >= 节点下限秩」（对包括超管在内的所有操作者一致）
function withinRoleScope(code: string | null): boolean {
  if (roleScopeRank.value === null || !code) return true
  const minScope = minScopeByCode.value.get(code)
  if (!minScope) return true
  return (ROLE_SCOPE_RANK[selectedScope.value] ?? 0) >= (ROLE_SCOPE_RANK[minScope] ?? 0)
}

// 按角色授权范围收口的树：min_scope 高于当前 selectedScope 的节点连子树一起剔除
// （父菜单被剔除时其按钮自然消失），不再走「禁用 + 勾选自动调升范围」
const scopedTree = computed(() => {
  const filter = (nodes: PermissionTreeNode[]): PermissionTreeNode[] =>
    nodes
      .filter(node => withinRoleScope(node.code))
      .map(node => ({ ...node, children: filter(node.children) }))
  return filter(displayTree.value)
})

const checkableTree = computed(() => {
  const mark = (nodes: PermissionTreeNode[]): Array<PermissionTreeNode & { disableCheckbox: boolean }> =>
    nodes.map(node => ({
      ...node,
      disableCheckbox: !node.selectable || !node.code,
      children: mark(node.children),
    }))
  return mark(scopedTree.value)
})

// 授权范围下拉选项：契约 scopes 按操作者 scope 的秩过滤（只能向下选）
const scopeOptions = computed(() => contractMeta.value.scopes
  .filter(option => option.rank <= OPERATOR_SCOPE_RANK[operatorScope()])
  .map(option => ({ value: option.value, label: option.label })))
// 范围是否可编辑：有当前范围（平台角色页传入）、非模板角色且有可选项
const scopeEditable = computed(() => Boolean(props.roleScope) && !props.roleIsTemplate && scopeOptions.value.length > 0)
// 范围发生变更：保存时先 PATCH 角色 scope 再替换授权
const scopeChanged = computed(() => Boolean(props.roleScope) && selectedScope.value !== props.roleScope)

const checkedState = computed(() => ({ checked: selectedIds.value, halfChecked: [] as string[] }))

const leafIdSet = computed(() => new Set(flattenGrantable(catalogTree.value).map(node => node.key)))

function asTreeNode(slotNode: PermissionTreeNode & { dataRef?: PermissionTreeNode; record?: PermissionTreeNode }): PermissionTreeNode {
  return slotNode.dataRef || slotNode.record || slotNode
}

function onTreeCheck(info: string[] | { checked?: string[] }): void {
  const keys = Array.isArray(info) ? info : (info.checked || [])
  const currentGrantable = new Set(flattenGrantable(catalogTree.value).map(node => node.key))
  const kept = selectedIds.value.filter(id => !currentGrantable.has(id))
  selectedIds.value = [...kept, ...keys.filter(key => leafIdSet.value.has(key))]
}

const selectionOrder = ref<string[]>([])
watch(selectedIds, now => {
  const nowSet = new Set(now)
  selectionOrder.value = selectionOrder.value.filter(id => nowSet.has(id))
  for (const id of now) {
    if (!selectionOrder.value.includes(id)) selectionOrder.value.push(id)
  }
})

// 授权范围变更联动：把 min_scope 下限高于新范围的已勾选节点剔除，
// 保证勾选集始终落在当前范围内（打开弹窗初始化 selectedScope 时也会触发一次，
// 用于清掉存量越范围授予并提示）
watch(selectedScope, () => {
  if (roleScopeRank.value === null) return
  const limit = ROLE_SCOPE_RANK[selectedScope.value] ?? 0
  const kept = selectedIds.value.filter(id => {
    const item = optionsById.value.get(id)
    if (!item) return true
    const minScope = minScopeByCode.value.get(item.code)
    // 无下限的码不受新范围约束；有下限的按秩比较，超出则剔除
    return !minScope || (ROLE_SCOPE_RANK[minScope] ?? 0) <= limit
  })
  if (kept.length === selectedIds.value.length) return
  message.info(`已按新授权范围移除 ${selectedIds.value.length - kept.length} 个超出节点`)
  selectedIds.value = kept
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
// 权限集合是否无增减（范围变更不算「无变化」）
const noPermissionChanges = computed(() => {
  const current = impact.value
  return current !== null && current.grant_permission_codes.length === 0 && current.revoke_permission_codes.length === 0
})
// 完全无保存内容：权限无增减且范围未变
const nothingToSave = computed(() => noPermissionChanges.value && !scopeChanged.value)

// 角色资源端点（PATCH scope 用）：由 grantsPath 去掉尾部 /permissions 推导
const roleApiPath = computed(() => props.grantsPath.replace(/\/permissions$/, ''))

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

async function loadGrants(): Promise<void> {
  if (!props.roleId || !props.catalogPath || !props.grantsPath) return
  loading.value = true
  impact.value = null
  impactPreviewKey.value = ''
  try {
    // 契约（tree meta）与目录/授权并行加载：范围选项与 min_scope 映射依赖 meta 就绪。
    const [catalog, grants, contract] = await Promise.all([
      api<PermissionRecord[] | { items: PermissionRecord[] }>(props.catalogPath).then(result => asPagedList(result).items),
      api<PermissionGrant[]>(props.grantsPath),
      ensurePermissionContract(),
    ])
    if (!open.value) return
    contractMeta.value = contract.meta
    const currentIds = grants.filter(grant => grant.resource_id === null).map(grant => grant.permission_id)
    const currentSet = new Set(currentIds)
    const codeDescriptions = new Map<string, string>()
    catalogItems.value = catalog
      .filter(permission => permission.status === 'active' || currentSet.has(permission.id))
      .map(permission => {
        const description = (permission.description || '').trim()
        if (description) codeDescriptions.set(permission.code, description)
        return permission
      })
    descriptionByCode.value = codeDescriptions
    selectedIds.value = currentIds
    selectedScope.value = props.roleScope
    expandedKeys.value = collectExpandKeys(catalogTree.value)
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
  if (nothingToSave.value) {
    message.info('授权内容与范围都没有变化')
    return
  }
  const scopeLine = scopeChanged.value
    ? `授权范围调整为「${scopeOptions.value.find(option => option.value === selectedScope.value)?.label || selectedScope.value}」`
    : ''
  const summary = [
    scopeLine,
    `新增 ${current.grant_permission_codes.length} 项授权`,
    `撤销 ${current.revoke_permission_codes.length} 项授权`,
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
    // 两段保存：范围变更先 PATCH 角色 scope，成功后再原子替换权限授权。
    if (scopeChanged.value) {
      await api(roleApiPath.value, {
        method: 'PATCH',
        body: JSON.stringify({ scope: selectedScope.value }),
      })
    }
    await api(props.grantsPath, {
      method: 'PUT',
      body: JSON.stringify({
        permission_ids: selectedIds.value,
        expected_current_permission_ids: current.current_permission_ids,
      }),
    })
    message.success(scopeChanged.value ? '角色授权范围与权限已更新' : '角色权限已原子更新')
    if (!props.embedded) open.value = false
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败；如授权或范围已被其他管理员更新，请重新预览')
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
    selectedScope.value = ''
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
          <span>先预览再保存。菜单与按钮独立勾选；树内节点已按角色授权范围收口，需要更高范围的能力请先调整授权范围。</span>
        </p>
        <div class="flex flex-wrap items-center gap-2">
          <div v-if="roleScope" class="flex items-center gap-1.5">
            <span class="text-xs text-[var(--color-text-secondary)]">授权范围</span>
            <a-tooltip :title="roleIsTemplate ? '系统模板角色的授权范围由平台固定，不可修改' : ''">
              <a-select
                v-model:value="selectedScope"
                :disabled="!scopeEditable"
                :options="scopeOptions"
                style="width: 128px"
                placeholder="授权范围"
              />
            </a-tooltip>
          </div>
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
                </div>
              </template>
            </a-tree>
            <p v-else class="m-0 text-xs text-[var(--color-text-muted)]">没有匹配的权限项</p>
          </div>
        </div>
        <!-- 范围变更提示：两段保存说明 -->
        <a-alert
          v-if="scopeChanged"
          type="info"
          show-icon
          message="授权范围已调整：保存时会先更新角色范围，再写入权限授权"
        />
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
            <a-button type="primary" :loading="saving" :disabled="loading || previewing || !previewIsCurrent || nothingToSave" @click="confirmSave">保存授权</a-button>
          </div>
        </div>
      </div>
    </a-spin>
  </component>
</template>
