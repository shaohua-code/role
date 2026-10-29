<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { getCachedCapabilities } from '@/api/capabilities'
import AdminListPage from '@/components/AdminListPage.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminStatBand from '@/components/AdminStatBand.vue'
import AdminDetailDrawer from '@/components/AdminDetailDrawer.vue'
import { PERMISSION_CLASSES, PERMISSION_DOMAINS, SCOPE_LEVEL_LABELS, SCOPE_LEVEL_ORDER, SCOPE_LEVEL_TIPS, isManagementCode, resolvePermissionClass, resolvePermissionDomain, resolvePermissionScope } from '@/utils/permissionGroups'

interface PermissionRecord {
  id: string
  code: string
  catalog_namespace: string
  resource_type: string
  scope: string
  description: string | null
  status: 'active' | 'disabled'
  assigned_role_count: number
  /** 绿场模型字段：管理面/业务面与数据范围强制标记（后端已回传，此处仅展示用） */
  surface?: 'management' | 'business'
  requires_data_scope?: boolean
}

const props = defineProps<{ active: boolean }>()
// 绿场 §6.5 写死：权限目录写（登记/停用）仅 L1 持 rbac.permission.manage；L2/L3 只读。
const canManageCatalog = computed(() => getCachedCapabilities()?.platform_admin === true)
const permissions = ref<PermissionRecord[]>([])
const searchText = ref('')
const namespaceFilter = ref('')
// P395 两类分组：统计卡带按「全部 / 平台编码 / 应用业务编码」筛选（'' = 全部）
const scopeFilter = ref('')
// P397 权限域筛选改为多选 chips：命中任一选中域即保留（空数组 = 不限）
const domainFilter = ref<string[]>([])
const domainChips = computed(() => {
  const counts = new Map<string, number>()
  for (const permission of permissions.value) {
    const key = resolvePermissionDomain(permission.code).key
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  return PERMISSION_DOMAINS.map(domain => ({ ...domain, count: counts.get(domain.key) || 0 }))
})

// 多选域 chips 切换：已选中再点取消
function toggleDomainChip(key: string): void {
  domainFilter.value = domainFilter.value.includes(key)
    ? domainFilter.value.filter(item => item !== key)
    : [...domainFilter.value, key]
}
const loading = ref(false)
const errorText = ref('')
const createOpen = ref(false)
const creating = ref(false)
const changingPermissionId = ref('')
const form = reactive({ domain: 'platform', code: '', resource_type: '', scope: '', description: '' })
let requestSequence = 0

const namespaceOptions = computed(() => {
  const values = new Set(permissions.value.map(item => item.catalog_namespace))
  // P393：空态文案由「全部分组」改为「全部命名空间」，消除与作用域分组的概念冲突
  return [{ value: '', label: '全部命名空间' }, ...[...values].sort().map(value => ({ value, label: value }))]
})

// P393 作用域组序（L1 专属 → L3 起 → L2 起 → 业务码）：两类分组下平台编码组内仍按层级起点聚块
const SCOPE_ORDER = SCOPE_LEVEL_ORDER

const filteredPermissions = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  const list = permissions.value.filter(permission => {
    if (namespaceFilter.value && permission.catalog_namespace !== namespaceFilter.value) return false
    if (scopeFilter.value && resolvePermissionClass(permission.code) !== scopeFilter.value) return false
    if (domainFilter.value.length && !domainFilter.value.includes(resolvePermissionDomain(permission.code).key)) return false
    if (!query) return true
    return `${permission.code} ${permission.catalog_namespace} ${permission.resource_type} ${permission.scope} ${permission.description || ''}`
      .toLocaleLowerCase().includes(query)
  })
  // 平台编码在前（组内按层级起点序 → 编码字母序），应用业务编码在后（命名空间 → 编码序）
  return [...list].sort((a, b) => {
    const scopeDelta = (SCOPE_ORDER[resolvePermissionScope(a.code).key] ?? 99) - (SCOPE_ORDER[resolvePermissionScope(b.code).key] ?? 99)
    return scopeDelta !== 0 ? scopeDelta : a.code.localeCompare(b.code)
  })
})

/** iam 码行展示所属权限域；业务码行的命名空间本身即语义分组，不重复打标。 */
function domainLabel(code: string): string {
  return resolvePermissionDomain(code).label
}

/** P395 平台编码行的层级起点标记（仅平台超管 / 租户管理员起 / 应用管理员起）；业务码行不打标。 */
function levelLabel(code: string): string {
  return SCOPE_LEVEL_LABELS[resolvePermissionScope(code).key] || ''
}

/** P396 层级起点标记的修饰类（三档视觉强度：实底黑 → 深描边 → 浅描边，呼应层级递减）。 */
function levelKey(code: string): string {
  return resolvePermissionScope(code).key
}

/** P396 层级起点 hover 解释：说明该码的持有边界。 */
function levelTip(code: string): string {
  return SCOPE_LEVEL_TIPS[resolvePermissionScope(code).key] || ''
}

/** P395 两类分组标题行：在列表中把平台编码段与应用业务编码段显式分开（业务码段为空则不显示组头）。 */
interface GroupHeaderRow { id: string; __group: 'platform' | 'business'; title: string; count: number }
function isGroupHeaderRow(row: unknown): row is GroupHeaderRow {
  return Boolean(row && typeof row === 'object' && '__group' in row)
}
const displayRows = computed<(PermissionRecord | GroupHeaderRow)[]>(() => {
  const rows: (PermissionRecord | GroupHeaderRow)[] = []
  const platform = filteredPermissions.value.filter(permission => isManagementCode(permission.code))
  const business = filteredPermissions.value.filter(permission => !isManagementCode(permission.code))
  if (platform.length) {
    rows.push({ id: '__group_platform', __group: 'platform', title: '平台编码', count: platform.length })
    rows.push(...platform)
  }
  if (business.length) {
    rows.push({ id: '__group_business', __group: 'business', title: '应用业务编码', count: business.length })
    rows.push(...business)
  }
  return rows
})

// P395 两类统计卡：全部 / 平台编码 / 应用业务编码，点击卡片即筛选（再次点击回全部）。
// 应用业务编码数量为 0 时保持概念位但置灰不可点（PRD FR-01）。P397 换用通用 AdminStatBand 渲染。
const domainStats = computed(() => {
  const stats = PERMISSION_CLASSES
    .map(clazz => {
      const list = permissions.value.filter(permission => resolvePermissionClass(permission.code) === clazz.key)
      return {
        key: clazz.key,
        label: clazz.label,
        count: list.length,
        sub: list.length === 0 && clazz.key === 'business' ? '暂无业务应用' : `活动 ${list.filter(permission => permission.status === 'active').length}`,
        disabled: clazz.key === 'business' && list.length === 0,
      }
    })
  return [
    {
      key: '',
      label: '全部',
      count: permissions.value.length,
      sub: `活动 ${permissions.value.filter(permission => permission.status === 'active').length}`,
      disabled: false,
    },
    ...stats,
  ]
})

// ===== P397 引用角色反查抽屉：前端用 roles.permission_codes 过滤，零后端改动 =====
interface RefRoleRecord { id: string; name: string; key: string; kind: string; status: string; permission_codes?: string[] }
const refsOpen = ref(false)
const refsPermission = ref<PermissionRecord | null>(null)
const refsRoles = ref<RefRoleRecord[]>([])
const refsLoading = ref(false)
// 按 code 缓存引用角色，权限目录刷新时整体失效
const refsCache = new Map<string, RefRoleRecord[]>()

async function openRefs(permission: PermissionRecord): Promise<void> {
  refsPermission.value = permission
  refsOpen.value = true
  const cached = refsCache.get(permission.code)
  if (cached) { refsRoles.value = cached; return }
  refsRoles.value = []
  refsLoading.value = true
  try {
    const roles = await api<RefRoleRecord[]>('/admin/roles')
    const matched = roles.filter(role => Array.isArray(role.permission_codes) && role.permission_codes.includes(permission.code))
    refsCache.set(permission.code, matched)
    if (refsPermission.value?.id === permission.id) refsRoles.value = matched
  } catch (error) {
    if (refsPermission.value?.id === permission.id) message.error(error instanceof Error ? error.message : '读取引用角色失败')
  } finally { refsLoading.value = false }
}

// 行点击 → 引用角色抽屉；操作列与行内链接用 @click.stop 防冒泡
function rowProps(record: unknown): Record<string, unknown> {
  // 组头行（__group 标记）不下钻
  if (isGroupHeaderRow(record)) return {}
  return { class: 'cursor-pointer', onClick: () => openRefs(record as PermissionRecord) }
}

const columns = [
  { title: '权限编码', dataIndex: 'code', key: 'code', width: 280 },
  { title: '权限域 / 命名空间', dataIndex: 'catalog_namespace', key: 'catalog_namespace', width: 170 },
  { title: '资源 · Scope', key: 'resource_scope', width: 170 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 88 },
  { title: '关联角色', dataIndex: 'assigned_role_count', key: 'assigned_role_count', width: 100 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 90, fixed: 'right' as const },
]

async function loadPermissions(): Promise<void> {
  if (!props.active) return
  const sequence = ++requestSequence
  loading.value = true
  errorText.value = ''
  // 目录刷新后引用角色缓存一并失效
  refsCache.clear()
  try {
    const result = await api<PermissionRecord[]>('/admin/permissions')
    if (sequence === requestSequence && props.active) permissions.value = result
  } catch (error) {
    if (sequence !== requestSequence) return
    permissions.value = []
    errorText.value = error instanceof Error ? error.message : '读取权限编码失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function openCreate(): void {
  form.domain = 'platform'
  form.code = ''
  form.resource_type = ''
  form.scope = ''
  form.description = ''
  createOpen.value = true
}

// 登记弹窗域切换：剥离旧首段前缀后补新前缀；业务命名空间交由用户自定义首段
function onCreateDomainChange(): void {
  const rest = form.code.replace(/^[A-Za-z][A-Za-z0-9_-]*\./, '')
  form.code = form.domain === 'business' ? rest : `${form.domain}.${rest}`
}

function validateForm(): boolean {
  const fields: [string, string, number][] = [
    ['权限编码', form.code.trim(), 180],
    ['资源类型', form.resource_type.trim(), 100],
    ['操作 Scope', form.scope.trim(), 80],
  ]
  const invalid = fields.find(([_label, value, max]) => !value || value.length > max)
  if (invalid) {
    message.error(`${invalid[0]}必填且不能超过 ${invalid[2]} 个字符`)
    return false
  }
  if (form.code.trim().length < 3) {
    message.error('权限编码至少需要 3 个字符')
    return false
  }
  // 管理面五域：编码必须以所选域前缀开头（与后端命名空间校验同口径）
  if (form.domain !== 'business' && !form.code.trim().startsWith(`${form.domain}.`)) {
    message.error(`管理面编码必须以「${form.domain}.」开头`)
    return false
  }
  if (form.description.trim().length > 500) {
    message.error('说明不能超过 500 个字符')
    return false
  }
  return true
}

async function createPermission(): Promise<void> {
  if (!validateForm()) return
  creating.value = true
  try {
    await api('/admin/permissions', {
      method: 'POST',
      body: JSON.stringify({
        code: form.code.trim(),
        resource_type: form.resource_type.trim(),
        scope: form.scope.trim(),
        description: form.description.trim() || null,
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

function changeStatus(permission: PermissionRecord): void {
  const nextStatus = permission.status === 'active' ? 'disabled' : 'active'
  const reactivating = nextStatus === 'active'
  Modal.confirm({
    title: reactivating ? '恢复该权限编码？' : '停用该权限编码？',
    content: reactivating
      ? `恢复后，该编码保留的历史角色授权将重新生效（关联 ${permission.assigned_role_count} 个角色）。如不希望恢复这些授权，请先在角色管理中撤销。`
      : `停用会立即让所有使用该编码的在线授权判定失败；${permission.assigned_role_count} 个角色的既有授权与数据范围会保留。`,
    okText: reactivating ? '恢复权限' : '确认停用',
    okType: reactivating ? 'primary' : 'danger',
    cancelText: '取消',
    onOk: async () => {
      changingPermissionId.value = permission.id
      try {
        await api(`/admin/permissions/${permission.id}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ expected_status: permission.status, status: nextStatus }),
        })
        message.success(reactivating ? '权限已恢复；历史授权已重新生效' : '权限已停用；历史授权关系已保留')
        await loadPermissions()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '更新权限状态失败')
      } finally {
        changingPermissionId.value = ''
      }
    },
  })
}

watch(() => props.active, active => {
  if (active) void loadPermissions()
}, { immediate: true })
</script>

<template>
  <div class="permission-page">
    <a-alert type="info" show-icon class="mb-3" message="高级列表：全局权限编码目录。编码裁剪菜单；接口鉴权看角色挂码。按应用维护请到「应用工作台 → 权限编码」。" />
    <!-- P395 两类统计卡（账本式）：全部 / 平台编码 / 应用业务编码；P397 换用通用 AdminStatBand -->
    <AdminStatBand v-model="scopeFilter" numbered :stats="domainStats" />

    <AdminListPage
      eyebrow="权限编码"
      title="权限编码"
      subtitle="高级列表：全局权限编码目录。按应用维护请到「应用工作台 → 权限编码」。编码裁剪菜单；接口鉴权看角色挂码。"
      hint="目录以登记为主；菜单显示不构成服务端授权。完整目录在本页；应用域编码也可在应用工作台维护。点卡片筛选平台/应用编码；点行查看引用角色。"
      :columns="columns"
      :data-source="displayRows"
      :loading="loading"
      row-key="id"
      :row-class-name="(row: unknown) => (isGroupHeaderRow(row) ? 'group-header-row' : '')"
      :custom-row="rowProps"
      :scroll="{ y: 'calc(100vh - 520px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
      :error-text="errorText"
      empty-emoji="🔐"
      :empty-text="searchText || namespaceFilter || domainFilter.length || scopeFilter ? '没有匹配的权限项' : '暂无权限项'"
    >
      <!-- P397 权限域多选 chips：色点 + 域名 + 计数，命中任一选中域即保留 -->
      <div class="flex flex-wrap items-center gap-1">
        <button
          v-for="domain in domainChips"
          :key="domain.key"
          type="button"
          :class="[
            'inline-flex cursor-pointer items-center gap-1.5 border border-solid px-2 py-1 rounded-full text-xs transition-colors duration-150',
            domainFilter.includes(domain.key)
              ? 'border-[var(--color-text-primary)] bg-[var(--color-brand-subtle)] text-[var(--color-text-primary)]'
              : 'border-[var(--color-border)] bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)]',
          ]"
          @click="toggleDomainChip(domain.key)"
        >
          <span class="domain-dot" />
          <span>{{ domain.label }}</span>
          <span class="font-mono text-[10px] text-[var(--color-text-muted)] tabular-nums">{{ domain.count }}</span>
        </button>
      </div>
      <a-select v-model:value="namespaceFilter" :options="namespaceOptions" class="admin-filter-wide" placeholder="命名空间" />
      <AdminSearchField v-model="searchText" placeholder="搜索编码、资源、Scope 或说明" :submit-on-clear="false" />
      <template #actions>
        <a-button v-if="canManageCatalog" type="link" @click="openCreate">平台直接登记</a-button>
        <a-button :loading="loading" @click="loadPermissions">刷新</a-button>
      </template>
      <template #bodyCell="{ column, record }">
        <!-- P395 两类分组标题行：横贯式组头，平台编码段与应用业务编码段在表中显式分开 -->
        <template v-if="isGroupHeaderRow(record)">
          <template v-if="column.key === 'code'">
            <div class="group-head">
              <span class="group-head-title">{{ record.title }}</span>
              <span class="group-head-count">{{ record.count }} 个编码</span>
            </div>
          </template>
        </template>
        <template v-else-if="column.key === 'code'">
          <!-- P389 双行口径（与授权弹窗一致）：中文说明主行 + mono 编码副行；P395 平台编码行附层级起点标记 -->
          <div class="code-cell">
            <span class="code-desc">
              {{ record.description || record.code }}
              <a-tooltip v-if="isManagementCode(String(record.code))" :title="levelTip(String(record.code))">
                <span :class="['level-tag', `level-${levelKey(String(record.code))}`]">{{ levelLabel(String(record.code)) }}</span>
              </a-tooltip>
            </span>
            <span class="font-mono text-xs text-[var(--color-text-muted)]">{{ record.code }}</span>
          </div>
        </template>
        <template v-else-if="column.key === 'catalog_namespace'">
          <!-- P389 全部行有归属：iam 码显域名（色点），业务码显命名空间 -->
          <div class="domain-cell">
            <span class="domain-dot" />
            <span>{{ isManagementCode(String(record.code)) ? domainLabel(String(record.code)) : record.catalog_namespace }}</span>
            <span class="domain-ns">{{ record.catalog_namespace }}</span>
          </div>
        </template>
        <template v-else-if="column.key === 'resource_scope'">
          <!-- 业务码强制数据范围标记：与授权弹窗「强制 data_scope」口径一致 -->
          <span class="inline-flex flex-wrap items-center gap-1">
            <span class="font-mono text-xs text-[var(--color-text-secondary)]">{{ record.resource_type }} · {{ record.scope }}</span>
            <a-tooltip v-if="record.requires_data_scope" title="业务码强制数据范围：角色缺少有效数据范围策略时默认拒绝">
              <span class="cursor-help border border-solid border-[var(--color-border)] px-1 rounded-[2px] text-[10px] leading-4 text-[var(--color-text-muted)]">需数据范围</span>
            </a-tooltip>
          </span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'assigned_role_count'">
          <a-button type="link" size="small" class="px-0" @click.stop="openRefs(record as PermissionRecord)">{{ record.assigned_role_count }} 个角色</a-button>
        </template>
        <template v-else-if="column.key === 'actions'">
          <!-- 红字链接代替 danger 实体按钮：整列红描边视觉噪音过重，danger 语义保留在字色与确认弹窗 -->
          <a-button v-if="canManageCatalog" type="link" size="small" class="px-0" :danger="record.status === 'active'" :loading="changingPermissionId === record.id" :disabled="Boolean(changingPermissionId)" @click.stop="changeStatus(record as PermissionRecord)">
            {{ record.status === 'active' ? '停用' : '恢复' }}
          </a-button>
        </template>
      </template>
    </AdminListPage>

    <!-- 引用角色抽屉：反查哪些角色挂载了该编码，评估停用/恢复影响面 -->
    <AdminDetailDrawer
      v-model:open="refsOpen"
      :title="`引用角色 — ${refsPermission?.description || refsPermission?.code || ''}`"
      :subtitle="refsPermission?.code || ''"
      :width="560"
    >
      <a-spin :spinning="refsLoading">
        <div v-if="refsRoles.length" class="flex flex-col gap-1">
          <div v-for="role in refsRoles" :key="role.id"
            class="flex items-center gap-3 border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 rounded-[var(--radius-md)]">
            <div class="flex min-w-0 flex-1 flex-col">
              <span class="truncate text-[13px] text-[var(--color-text-primary)]">{{ role.name }}</span>
              <span class="truncate font-mono text-xs text-[var(--color-text-muted)]">{{ role.key }}</span>
            </div>
            <a-tag v-if="role.status !== 'active'" class="mr-0 shrink-0" color="default">已停用</a-tag>
          </div>
        </div>
        <p v-else-if="!refsLoading" class="text-xs text-[var(--color-text-muted)]">当前没有角色引用该编码；停用不影响任何既有授权。</p>
      </a-spin>
    </AdminDetailDrawer>

    <a-modal v-model:open="createOpen" title="平台登记权限项（运维）" ok-text="创建" cancel-text="取消" :confirm-loading="creating" @ok="createPermission">
      <a-form layout="vertical" class="create-form">
        <a-form-item label="所属权限域" help="选择管理面五域时自动补编码前缀；业务编码使用应用命名空间作为首段。">
          <a-select
            v-model:value="form.domain"
            :options="[
              ...PERMISSION_DOMAINS.filter(domain => !['other', 'business'].includes(domain.key)).map(domain => ({ value: domain.key, label: `${domain.label}（${domain.key}.）` })),
              { value: 'business', label: '业务命名空间（自定义首段）' },
            ]"
            @change="onCreateDomainChange"
          />
        </a-form-item>
        <a-form-item label="权限编码" required help="建议使用 product.resource.action 格式；至少 3 个字符，最长 180 个字符。">
          <a-input v-model:value="form.code" :maxlength="180" placeholder="platform.tenant.read" />
        </a-form-item>
        <a-form-item label="资源类型" required><a-input v-model:value="form.resource_type" :maxlength="100" placeholder="resume" /></a-form-item>
        <a-form-item label="操作 Scope" required><a-input v-model:value="form.scope" :maxlength="80" placeholder="read" /></a-form-item>
        <a-form-item label="说明"><a-textarea v-model:value="form.description" :rows="3" :maxlength="500" show-count /></a-form-item>
        <!-- 完整编码实时预览：登记前最后确认归属与格式 -->
        <div class="mb-4 border border-solid border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2 rounded-[var(--radius-md)]">
          <span class="mr-2 text-xs text-[var(--color-text-muted)]">完整编码</span>
          <span class="font-mono text-xs text-[var(--color-text-primary)] break-all">{{ form.code.trim() || '—' }}</span>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped>
.permission-page { display: flex; flex-direction: column; }

/* 权限域 / 命名空间列：色点 + 域名（副行 mono namespace） */
.domain-cell { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.domain-dot { width: 7px; height: 7px; border-radius: 999px; border: 2px solid var(--color-text-primary); flex-shrink: 0; }
.domain-ns { font-family: var(--mono); font-size: 11px; color: var(--color-text-muted); }

/* 权限编码列：中文说明主行 + mono 码副行（与授权弹窗同口径）；P395 层级起点标记 */
.code-cell { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.code-desc { font-weight: 500; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.level-tag {
  font-size: 10px; line-height: 15px; margin-left: 8px; padding: 0 5px; border-radius: 2px;
  border: 1px solid var(--color-border); color: var(--color-text-muted);
  font-weight: 500; white-space: nowrap; cursor: help;
}
/* P396 三档轻标签（描边式，靠文字深浅区分层级；避免实底黑块满屏的视觉噪音） */
.level-tag.level-platform { color: var(--color-text-primary); border-color: var(--color-text-primary); }
.level-tag.level-tenant { color: var(--color-text-secondary); border-color: var(--color-border-strong); }
.level-tag.level-app { color: var(--color-text-muted); border-color: var(--color-border); }

/* P395 两类分组标题行：底色通栏 + 去列分隔观感，与数据行明确区隔 */
.group-head { display: flex; align-items: baseline; gap: 10px; }
.group-head-title { font-weight: 700; font-size: 13.5px; color: var(--color-text-primary); }
.group-head-count { font-family: var(--mono); font-size: 11px; color: var(--color-text-muted); }
:deep(.group-header-row) { background: var(--color-bg-subtle); }
:deep(.group-header-row) td { background: var(--color-bg-subtle) !important; border-bottom: 1px solid var(--color-border-strong); }
:deep(.group-header-row):hover td { background: var(--color-bg-subtle) !important; }
</style>
