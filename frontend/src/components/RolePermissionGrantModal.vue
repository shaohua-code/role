<script setup lang="ts">
// 角色挂码编辑弹窗（共享）：目录 + 当前通用授权加载、变更影响预览、确认保存。
// 平台角色走 /admin/roles/{id}/permissions；应用角色走 /tenant-admin/.../roles/{id}/permissions，
// 由 catalogPath / grantsPath 注入，角色管理页与应用工作台「角色」Tab 共用。
import { computed, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { ExclamationCircleOutlined } from '@/plugins/icons'
import { isManagementCode, PERMISSION_CLASSES, SCOPE_LEVEL_LABELS, SCOPE_LEVEL_ORDER, SCOPE_LEVEL_TIPS, permissionNamespace, resolvePermissionClass, resolvePermissionScope } from '@/utils/permissionGroups'
import { asPagedList } from '@/utils/paged'

interface PermissionRecord { id: string; code: string; description?: string | null; status: 'active' | 'disabled' }
interface PermissionGrant { permission_id: string; resource_id: string | null }
/** 平台与应用两个预览接口的联合视图；差异字段全部可选。 */
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
  // 应用侧规则：五域管理码禁止新增（只能保留/撤销）；平台侧规则：仅停用码禁选
  disableIamCodes?: boolean
  // 管理员不能管理管理员：自定义角色禁选授权权码（已持有的也会被强制取消，后端同口径 422 兜底）
  lockAuthorityCodes?: boolean
  // P390 作用域收敛：按角色 kind 隐藏越域码组（'' = 不收敛，展示全量目录）
  roleKind?: '' | 'platform' | 'tenant' | 'application'
  // 应用角色的业务码命名空间（编码首段匹配）；仅 roleKind='application' 时生效
  roleNamespace?: string
}>(), {
  roleName: '',
  disableIamCodes: false,
  lockAuthorityCodes: false,
  roleKind: '',
  roleNamespace: '',
})

// P395 收敛矩阵（两类分组口径）：各 kind 隐藏的作用域组（组值沿用 P393，逐码结果不变）。
// tenant 排除 L1 专属 6 码 + 业务码（业务码随应用，租户全域角色不配）；
// application 排除 L1 专属 + L3 起共 12 码（治理码 rbac.role.read / rbac.role.manage / rbac.permission.manage
// 分属两层被覆盖），业务码组仅显示本应用命名空间。
// 已持有的码始终豁免隐藏（可撤销，不静默剥夺）。
const HIDDEN_SCOPES_BY_KIND: Record<string, Set<string>> = {
  platform: new Set(),
  tenant: new Set(['platform', 'business']),
  application: new Set(['platform', 'tenant']),
}

// 与后端 role_provisioning.AUTHORITY_MANAGE_CODES 对齐的授权权码集合。
const AUTHORITY_MANAGE_CODES = new Set([
  'rbac.app_role.manage', 'org.member.manage', 'org.invite.manage', 'org.group.manage',
])

const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>('open', { default: false })

const loading = ref(false)
const previewing = ref(false)
const saving = ref(false)
// 中文描述与编码并列展示：description 来自权限目录（授权弹窗主文案），code 保留可辨识性。
const options = ref<{ label: string; code: string; description: string; value: string; scope: string; disabled?: boolean }[]>([])
const selectedIds = ref<string[]>([])
const impact = ref<PermissionImpact | null>(null)
const impactPreviewKey = ref('')

// P388 分组展示（P393 起按作用域组）：组筛选（'all' = 全部）与组折叠状态，纯展示层不影响选择与保存。
const scopeFilter = ref('all')
const collapsedScopes = ref(new Set<string>())

interface OptionItem { label: string; code: string; description: string; value: string; scope: string; disabled?: boolean }
interface RenderSubGroup { namespace: string; options: OptionItem[] }
interface RenderGroup { key: string; label: string; hint: string; count: number; subGroups: RenderSubGroup[] }

/** 按两类口径（P395：平台编码 / 业务码）分桶；平台编码组内按层级起点序排，业务码组按命名空间二级分组。 */
const groupedOptions = computed<RenderGroup[]>(() => {
  const platformList: OptionItem[] = []
  const businessList: OptionItem[] = []
  for (const option of options.value) {
    if (resolvePermissionClass(option.code) === 'platform-class') platformList.push(option)
    else businessList.push(option)
  }
  // 平台编码组内按层级起点序（L1 专属 → L3 起 → L2 起）+ 编码字母序
  platformList.sort((a, b) => {
    const delta = (SCOPE_LEVEL_ORDER[resolvePermissionScope(a.code).key] ?? 99) - (SCOPE_LEVEL_ORDER[resolvePermissionScope(b.code).key] ?? 99)
    return delta !== 0 ? delta : a.code.localeCompare(b.code)
  })
  const groups: RenderGroup[] = []
  if (scopeFilter.value === 'all' || scopeFilter.value === 'platform-class') {
    if (platformList.length) {
      groups.push({
        key: 'platform-class', label: '平台编码', hint: '平台统一管理的管理面码，四级管理员分层持有',
        count: platformList.length, subGroups: [{ namespace: '', options: platformList }],
      })
    }
  }
  if (scopeFilter.value === 'all' || scopeFilter.value === 'business') {
    if (businessList.length) {
      // 业务码：按命名空间（编码首段）二级分组，保持目录顺序
      const namespaces: string[] = []
      const byNamespace = new Map<string, OptionItem[]>()
      for (const option of businessList) {
        const namespace = permissionNamespace(option.code)
        if (!byNamespace.has(namespace)) {
          byNamespace.set(namespace, [])
          namespaces.push(namespace)
        }
        byNamespace.get(namespace)!.push(option)
      }
      groups.push({
        key: 'business', label: '业务码', hint: '应用命名空间业务码，强制数据范围',
        count: businessList.length,
        subGroups: namespaces.map(namespace => ({ namespace, options: byNamespace.get(namespace)! })),
      })
    }
  }
  return groups
})

function toggleDomain(key: string): void {
  const next = new Set(collapsedScopes.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsedScopes.value = next
}

// P389 双栏重构：勾选顺序追踪（摘要条「最近勾选」按此序展示）。
const selectionOrder = ref<string[]>([])
watch(selectedIds, now => {
  const nowSet = new Set(now)
  selectionOrder.value = selectionOrder.value.filter(id => nowSet.has(id))
  for (const id of now) {
    if (!selectionOrder.value.includes(id)) selectionOrder.value.push(id)
  }
})

const optionsByValue = computed(() => new Map(options.value.map(option => [option.value, option])))

/** 已选摘要条：按勾选时间倒序的最近 6 个码 + 溢出数。 */
const recentSelected = computed(() => {
  const recent = [...selectionOrder.value].reverse()
    .map(id => optionsByValue.value.get(id))
    .filter((option): option is OptionItem => Boolean(option))
  return { items: recent.slice(0, 6), overflow: Math.max(0, recent.length - 6) }
})

/** 左栏两类导航（P395）：全部 / 平台编码 / 业务码（含该组已选数），仅列出当前目录存在的组。 */
const domainNav = computed(() => {
  const selectedSet = new Set(selectedIds.value)
  const items = PERMISSION_CLASSES
    .map(clazz => {
      const list = options.value.filter(option =>
        clazz.key === 'platform-class' ? resolvePermissionClass(option.code) === 'platform-class' : resolvePermissionClass(option.code) !== 'platform-class')
      return { key: clazz.key, label: clazz.label, count: list.length, selected: list.filter(option => selectedSet.has(option.value)).length }
    })
    .filter(item => item.count > 0)
  return [{ key: 'all', label: '全部', count: options.value.length, selected: selectedIds.value.length }, ...items]
})

/** 取消单个已选码（摘要条 chip 点击）。 */
function removeSelected(id: string): void {
  selectedIds.value = selectedIds.value.filter(value => value !== id)
}

/** 清空全部选择：走既有「选择已变化需重新预览」警戒，无需新增状态。 */
function clearSelection(): void {
  selectedIds.value = []
}

// 预览影响区的增撤清单由后端返回裸编码，这里按目录映射回中文描述。
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
    // 只编辑通用授权（resource_id 为空），避免多选框覆盖资源实例授权。
    let currentIds = grants.filter(grant => grant.resource_id === null).map(grant => grant.permission_id)
    const currentSet = new Set(currentIds)
    // P390/P393 作用域收敛：按角色 kind 隐藏越域作用域组；历史已持有的码豁免（可撤销但不可静默剥夺）。
    const hiddenScopes = HIDDEN_SCOPES_BY_KIND[props.roleKind || '']
    const visibleCatalog = catalog.filter(permission => {
      if (currentSet.has(permission.id)) return true
      if (!hiddenScopes || !hiddenScopes.size) return true
      const scopeKey = resolvePermissionScope(permission.code).key
      if (hiddenScopes.has(scopeKey)) return false
      // 应用角色：业务码仅显示本应用命名空间（编码首段匹配）
      if (props.roleKind === 'application' && scopeKey === 'business' && props.roleNamespace) {
        return permissionNamespace(permission.code) === props.roleNamespace
      }
      return true
    })
    // 自定义角色 + 授权权禁选：选项置灰，且历史已持有的授权权一并从初始选中剔除（保存即剥离）。
    const authorityIds = new Set(visibleCatalog.filter(p => AUTHORITY_MANAGE_CODES.has(p.code)).map(p => p.id))
    if (props.lockAuthorityCodes) currentIds = currentIds.filter(id => !authorityIds.has(id))
    const codeDescriptions = new Map<string, string>()
    options.value = visibleCatalog
      .filter(permission => permission.status === 'active' || currentSet.has(permission.id))
      .map(permission => {
        const description = (permission.description || '').trim()
        // 描述可用时以中文为主文案，编码保留在副行与预览清单里。
        const label = description ? `${description}（${permission.code}）` : permission.code
        if (description) codeDescriptions.set(permission.code, description)
        const authorityLocked = props.lockAuthorityCodes && AUTHORITY_MANAGE_CODES.has(permission.code)
        return {
          label,
          code: permission.code,
          description,
          value: permission.id,
          // P393 作用域归属（共享映射），仅用于分组渲染
          scope: resolvePermissionScope(permission.code).key,
          disabled: authorityLocked || (props.disableIamCodes
            ? isManagementCode(permission.code) && !currentSet.has(permission.id)
            : permission.status !== 'active' && !currentSet.has(permission.id)),
        }
      })
    descriptionByCode.value = codeDescriptions
    selectedIds.value = currentIds
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

// 保存前强制预览；确认弹窗复述增减授权与影响成员数，避免误改线上授权。
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
    open.value = false
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '权限保存失败；如授权已被其他管理员更新，请重新预览')
  } finally {
    saving.value = false
  }
}

// immediate：工作台里弹窗经 v-if 挂载时 open 已为 true，必须补首次加载。
watch(open, value => {
  if (value) void loadGrants()
  else {
    options.value = []
    selectedIds.value = []
    selectionOrder.value = []
    impact.value = null
    impactPreviewKey.value = ''
    // 关闭时重置分组展示状态，下次打开回到全部展开
    scopeFilter.value = 'all'
    collapsedScopes.value = new Set()
  }
}, { immediate: true })
</script>

<template>
  <a-modal v-model:open="open" :title="`配置角色权限${roleName ? `：${roleName}` : ''}`" width="880px" :footer="null">
    <a-spin :spinning="loading">
      <div class="grant-layout">
        <!-- P389 左栏导航（P393 起按作用域组）：全部 + 平台/租户/应用/业务码（含该组已选数），点击切换右栏内容 -->
        <aside class="grant-nav">
          <button
            v-for="item in domainNav"
            :key="item.key"
            type="button"
            :class="['grant-nav-item', { active: scopeFilter === item.key }]"
            @click="scopeFilter = item.key"
          >
            <span class="grant-nav-label">{{ item.label }}</span>
            <span class="grant-nav-count">{{ item.selected }}/{{ item.count }}</span>
          </button>
          <p class="grant-nav-total">已选合计 <strong>{{ selectedIds.length }}</strong> 项</p>
        </aside>

        <div class="grant-main">
        <!-- P391 提示降噪：大 alert 收敛为单行轻提示（对齐 P373 全站降噪标准），细节收进 tooltip -->
        <p class="grant-hint">
          <ExclamationCircleOutlined class="grant-hint-icon" />
          <span>先预览授权变更再提交保存；仅编辑通用权限，资源实例级授权不受影响。</span>
          <a-tooltip v-if="lockAuthorityCodes" title="「角色管理 / 成员进出 / 邀请 / 用户组管理」四类授权权已禁选；历史已持有的授权权会在保存时剥离——管理员不能管理管理员。">
            <span class="grant-hint-warn"><ExclamationCircleOutlined /> 自定义角色不可持有授权权码</span>
          </a-tooltip>
        </p>

          <!-- P389 已选摘要条（常驻）：最近勾选可点删，清空走既有「需重新预览」警戒 -->
          <div class="selected-summary">
            <span class="selected-summary-title">已选 {{ selectedIds.length }} 项</span>
            <span v-if="!selectedIds.length" class="selected-summary-empty">尚未选择任何权限编码</span>
            <template v-else>
              <button
                v-for="option in recentSelected.items"
                :key="option.value"
                type="button"
                class="selected-chip"
                :title="`${option.description || option.code}（点击取消勾选）`"
                @click="removeSelected(option.value)"
              ><span class="selected-chip-text">{{ option.description || option.code }}</span><span class="selected-chip-x">×</span></button>
              <span v-if="recentSelected.overflow" class="selected-more">+{{ recentSelected.overflow }}</span>
              <button type="button" class="selected-clear" @click="clearSelection">清空</button>
            </template>
          </div>

          <a-checkbox-group v-model:value="selectedIds" class="grant-option-list" :disabled="loading || previewing || saving">
            <!-- P395 两类分区渲染：平台编码（内按层级起点序）/ 业务码（命名空间二级分组）；口径见 utils/permissionGroups.ts -->
            <section v-for="group in groupedOptions" :key="group.key" class="domain-group">
              <button type="button" class="domain-group-head" @click="toggleDomain(group.key)">
                <span class="domain-group-caret">{{ collapsedScopes.has(group.key) ? '▸' : '▾' }}</span>
                <span class="domain-group-label">{{ group.label }}</span>
                <span class="domain-group-count">{{ group.count }}</span>
                <span class="domain-group-hint">{{ group.hint }}</span>
              </button>
              <template v-if="!collapsedScopes.has(group.key)">
                <div v-for="sub in group.subGroups" :key="sub.namespace || group.key">
                  <p v-if="sub.namespace" class="domain-namespace">{{ sub.namespace }}</p>
                  <div class="grant-option-rows">
                    <!-- P394 码项行式列表：单列全宽，描述主行 + mono 码右对齐，彻底解决双列卡片截断 -->
                    <a-checkbox
                      v-for="option in sub.options"
                      :key="option.value"
                      :value="option.value"
                      :disabled="option.disabled"
                      :class="['option-row', { checked: selectedIds.includes(option.value), 'option-disabled': option.disabled }]"
                    >
                      <span class="option-row-body" :title="option.label">
                        <span class="option-row-desc">
                          {{ option.description || option.code }}<template v-if="option.disabled">（停用，仅可撤销）</template>
                          <a-tooltip v-if="isManagementCode(option.code)" :title="SCOPE_LEVEL_TIPS[option.scope]">
                            <span :class="['level-tag', `level-${option.scope}`]">{{ SCOPE_LEVEL_LABELS[option.scope] }}</span>
                          </a-tooltip>
                        </span>
                        <span class="option-row-code">{{ option.code }}</span>
                      </span>
                    </a-checkbox>
                  </div>
                </div>
              </template>
            </section>
          </a-checkbox-group>

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
            <!-- P389 新增/撤销对比双卡：语义色仅绿/红两处 -->
            <div class="impact-grid">
              <div class="impact-card impact-grant">
                <p class="impact-head">新增 {{ impact.grant_permission_codes.length }} 项</p>
                <p v-if="!impact.grant_permission_codes.length" class="impact-empty">无新增授权</p>
                <p v-for="code in impact.grant_permission_codes" :key="code" class="impact-item">{{ codeLabel(code) }}</p>
              </div>
              <div class="impact-card impact-revoke">
                <p class="impact-head">撤销 {{ impact.revoke_permission_codes.length }} 项</p>
                <p v-if="!impact.revoke_permission_codes.length" class="impact-empty">无撤销授权</p>
                <p v-for="code in impact.revoke_permission_codes" :key="code" class="impact-item">{{ codeLabel(code) }}</p>
              </div>
            </div>
            <p v-for="item in impact.permission_impacts" :key="`${item.action}:${item.permission_code}`" class="m-0 text-sm">
              {{ item.action === 'grant' ? '新增' : '撤销' }} {{ codeLabel(item.permission_code) }}：潜在影响 {{ item.potentially_affected_members }} 名，其他通用角色已覆盖 {{ item.covered_by_other_general_roles }} 名
            </p>
            <p v-if="impact.data_scopes_to_delete?.length" class="m-0 text-sm">同时清理失去授权前置条件的数据范围：{{ impact.data_scopes_to_delete.map(item => `${codeLabel(item.permission_code)}（${item.scope_type}）`).join('、') }}</p>
            <p v-else-if="impact.data_scopes_to_delete" class="m-0 text-sm">无需清理数据范围策略。</p>
          </template>

          <!-- P389 固定操作条：滚动时始终可见 -->
          <div class="grant-footer">
            <a-button @click="open = false">取消</a-button>
            <div class="flex items-center gap-2">
              <a-button :loading="previewing" :disabled="loading || saving" @click="previewChanges">预览影响</a-button>
              <a-button type="primary" :loading="saving" :disabled="loading || previewing || !previewIsCurrent || noChanges" @click="confirmSave">保存授权</a-button>
            </div>
          </div>
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>

<style scoped>
/* ===== P389 双栏布局：左域导航 188px + 右码区；窄屏（<760px）降级单列 ===== */
.grant-layout { display: grid; grid-template-columns: 188px minmax(0, 1fr); gap: 16px; }
.grant-nav { display: flex; flex-direction: column; gap: 4px; align-self: start; position: sticky; top: 0; }
.grant-nav-item {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 8px 10px; border: 0; border-left: 3px solid transparent; border-radius: 6px;
  background: transparent; cursor: pointer; text-align: left; font-size: 13px;
  color: var(--color-text-secondary); transition: background .15s, color .15s, border-color .15s;
}
.grant-nav-item:hover { background: var(--color-border); color: var(--color-text-primary); }
.grant-nav-item.active {
  background: var(--color-border); border-left-color: var(--color-text-primary);
  color: var(--color-text-primary); font-weight: 600;
}
.grant-nav-count { font-family: var(--mono); font-size: 11px; color: var(--color-text-muted); }
.grant-nav-item.active .grant-nav-count { color: var(--color-text-primary); }
.grant-nav-total { margin: 10px 0 0; padding: 10px 10px 0; border-top: 1px dashed var(--color-border); font-size: 12px; color: var(--color-text-muted); }
.grant-nav-total strong { font-family: var(--mono); color: var(--color-text-primary); }

.grant-main { display: flex; flex-direction: column; gap: 12px; min-width: 0; }

/* P391 单行轻提示：替代原双 alert（对齐 P373 降噪标准），警示变体琥珀色 + tooltip 展开 */
.grant-hint { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 0; font-size: 12.5px; color: var(--color-text-muted); }
.grant-hint-icon { font-size: 13px; }
.grant-hint-warn { display: inline-flex; align-items: center; gap: 4px; color: var(--color-warning); cursor: help; }

/* 已选摘要条：常驻总览，chip 点击即取消勾选（P391 去灰底减重） */
.selected-summary {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  padding: 8px 10px; border: 1px dashed var(--color-border);
  border-radius: 8px;
}
.selected-summary-title { font-size: 12.5px; font-weight: 600; color: var(--color-text-primary); margin-right: 2px; }
.selected-summary-empty { font-size: 12.5px; color: var(--color-text-muted); }
.selected-chip {
  display: inline-flex; align-items: center; gap: 4px; max-width: 220px;
  font-size: 12px; line-height: 20px; padding: 0 8px;
  border: 1px solid var(--color-border-strong); border-radius: 999px;
  background: var(--color-bg-container); color: var(--color-text-primary); cursor: pointer;
}
.selected-chip:hover { border-color: var(--color-text-secondary); }
.selected-chip-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.selected-chip-x { color: var(--color-text-muted); font-size: 13px; }
.selected-chip:hover .selected-chip-x { color: var(--color-text-primary); }
.selected-more { font-family: var(--mono); font-size: 12px; color: var(--color-text-muted); }
.selected-clear { margin-left: auto; border: 0; background: transparent; font-size: 12px; color: var(--color-text-secondary); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.selected-clear:hover { color: var(--color-text-primary); }

/* 码区：右栏独立滚动 */
.grant-option-list { max-height: 52vh; overflow: auto; padding: 2px; }

/* 组头：左竖条 + 计数徽标 + hint；hairline 分隔 */
.domain-group { border-bottom: 1px dashed var(--color-border); padding: 6px 0 10px; }
.domain-group:last-child { border-bottom: 0; }
.domain-group-head {
  display: flex; align-items: baseline; gap: 8px; width: 100%;
  padding: 6px 2px; border: 0; background: transparent; cursor: pointer; text-align: left;
}
.domain-group-caret { color: var(--color-text-muted); font-size: 11px; width: 12px; }
.domain-group-label { font-weight: 600; font-size: 13.5px; color: var(--color-text-primary); border-left: 3px solid var(--color-text-primary); padding-left: 8px; }
.domain-group-count {
  font-family: var(--mono); font-size: 11px; padding: 0 7px; border-radius: 999px;
  background: var(--color-border); color: var(--color-text-secondary);
}
.domain-group-hint { margin-left: auto; font-size: 11.5px; color: var(--color-text-muted); }
.domain-namespace { margin: 8px 0 2px; font-family: var(--mono); font-size: 11px; letter-spacing: .08em; color: var(--color-text-muted); }

/* P394 码项行式列表：单列全宽行（替代 P389 双列卡片——右栏窄时描述全被截断）。
   行 hover 浅底、选中行左墨色竖条 + 浅底、禁选弱化；描述主行左对齐 + mono 码右对齐。 */
.grant-option-rows { display: flex; flex-direction: column; gap: 2px; padding: 4px 0; }
.option-row {
  display: flex !important; align-items: center; gap: 2px;
  margin: 0; padding: 7px 10px;
  border: 0; border-left: 2px solid transparent; border-radius: 6px;
  transition: background .12s, border-color .12s;
}
.option-row:hover { background: var(--color-border); }
.option-row.checked { background: var(--color-border); border-left-color: var(--color-text-primary); }
.option-row.option-disabled { opacity: .5; }
.option-row :deep(.ant-checkbox) { margin-top: 0; }
.option-row :deep(.ant-checkbox + span) { flex: 1; min-width: 0; padding-inline-start: 10px; padding-inline-end: 0; }
.option-row-body { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; min-width: 0; width: 100%; }
.option-row-desc { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; color: var(--color-text-primary); }
.option-row-code { flex-shrink: 0; font-family: var(--mono); font-size: 11px; color: var(--color-text-muted); }

/* P396 层级起点标记：白话文案 + 三档描边轻标签（靠文字深浅区分层级），与目录页同口径 */
.level-tag {
  font-size: 10px; line-height: 15px; margin-left: 8px; padding: 0 5px; border-radius: 2px;
  border: 1px solid var(--color-border); color: var(--color-text-muted);
  font-weight: 500; white-space: nowrap; cursor: help;
}
.level-tag.level-platform { color: var(--color-text-primary); border-color: var(--color-text-primary); }
.level-tag.level-tenant { color: var(--color-text-secondary); border-color: var(--color-border-strong); }
.level-tag.level-app { color: var(--color-text-muted); border-color: var(--color-border); }

/* 预览对比双卡：语义色仅绿/红两处 */
.impact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.impact-card { border: 1px solid var(--color-border); border-radius: 8px; padding: 10px 12px; }
.impact-head { margin: 0 0 6px; font-size: 13px; font-weight: 600; }
.impact-grant .impact-head { color: var(--color-success, #166534); }
.impact-revoke .impact-head { color: var(--color-error, #b91c1c); }
.impact-empty { margin: 0; font-size: 12.5px; color: var(--color-text-muted); }
.impact-item { margin: 0 0 2px; font-size: 12.5px; color: var(--color-text-secondary); overflow-wrap: anywhere; }

/* 固定操作条：滚动时始终可见 */
.grant-footer {
  position: sticky; bottom: -24px; z-index: 2;
  display: flex; align-items: center; justify-content: space-between;
  margin: 4px -24px -24px; padding: 12px 24px;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-container);
}
@media (max-width: 760px) {
  .grant-layout { grid-template-columns: 1fr; }
  .grant-nav { position: static; flex-direction: row; overflow-x: auto; padding-bottom: 4px; border-bottom: 1px dashed var(--color-border); }
  .grant-nav-item { border-left: 0; border-bottom: 2px solid transparent; border-radius: 6px 6px 0 0; white-space: nowrap; }
  .grant-nav-item.active { border-bottom-color: var(--color-text-primary); }
  .grant-nav-total { display: none; }
  .impact-grid { grid-template-columns: 1fr; }
  .grant-footer { bottom: 0; margin: 0; border-radius: 0 0 8px 8px; }
}
</style>
