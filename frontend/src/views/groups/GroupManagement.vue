<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { DownOutlined } from '@/plugins/icons'
import { api } from '@/api'
import { cachedHas } from '@/api/capabilities'
import AdminListPage from '@/components/AdminListPage.vue'
import GroupRelationModal from '@/components/GroupRelationModal.vue'

interface Tenant { id: string; name: string; slug?: string }

const props = withDefaults(defineProps<{
  active?: boolean
  tenants?: Tenant[]
  /** 绿场规则：组管理同挂 /admin 与 /tenant-admin；租户控制台传 /tenant-admin。 */
  apiPrefix?: string
}>(), {
  active: false,
  tenants: () => [],
  apiPrefix: '/admin',
})
interface Group {
  id: string; tenant_id: string; key: string; name: string; description?: string | null
  parent_group_id?: string | null
  status: 'active' | 'disabled'; member_count: number; role_count: number; created_at?: string
}

const groups = ref<Group[]>([])
const localTenants = ref<Tenant[]>([])
const tenants = computed(() => (props.tenants.length ? props.tenants : localTenants.value))
// 平台引导租户（slug=platform）为系统保留租户，不参与业务用户组创建，新建弹窗的租户选择排除；列表筛选器保留
const creatableTenantOptions = computed(() => tenants.value
  .filter(tenant => tenant.slug !== 'platform')
  .map(tenant => ({ value: tenant.id, label: tenant.name })))

const canManage = computed(() => cachedHas('org.group.manage'))
const tenantId = ref('')
const loading = ref(false)
const saving = ref(false)
const groupOpen = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({ tenant_id: '', key: '', name: '', description: '', parent_group_id: '' })
const groupFormRef = ref<{ validate: () => Promise<unknown> }>()
const groupRules = {
  tenant_id: [{ required: true, message: '请选择所属租户', trigger: 'change' }],
  key: [
    { required: true, message: '请输入用户组标识', trigger: 'blur' },
    { min: 2, max: 100, message: '标识长度为 2 到 100 个字符', trigger: 'blur' },
    { pattern: /^[a-z0-9][a-z0-9._-]+$/, message: '仅允许小写字母、数字、点、下划线和连字符，且以字母或数字开头', trigger: 'blur' },
  ],
  name: [{ required: true, whitespace: true, max: 120, message: '请输入不超过 120 个字符的用户组名称', trigger: 'blur' }],
  description: [{ max: 500, message: '说明不能超过 500 个字符', trigger: 'blur' }],
}
// 组员/组角色编辑复用共享 GroupRelationModal，页面只维护弹窗上下文。
const relationOpen = ref(false)
const relationKind = ref<'members' | 'roles'>('members')
const relationGroupId = ref('')
const relationGroupName = ref('')

const columns = computed(() => [
  { title: '用户组', dataIndex: 'name', key: 'name', width: 170 },
  { title: '所属租户', dataIndex: 'tenant_id', key: 'tenant_id', width: 180 },
  { title: '标识', dataIndex: 'key', key: 'key', width: 150 },
  { title: '上级组', key: 'parent_group', width: 140, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '成员', dataIndex: 'member_count', key: 'member_count', width: 80 },
  { title: '角色', dataIndex: 'role_count', key: 'role_count', width: 80 },
  { title: '说明', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 240, fixed: 'right' as const },
])

// G24 组嵌套：父组展示名映射；编辑弹窗的父组选项排除自身（防环由服务端兜底）。
function parentGroupName(group: Group): string {
  if (!group.parent_group_id) return '—'
  return groups.value.find(item => item.id === group.parent_group_id)?.name || '未知组'
}

const parentOptions = computed(() => groups.value
  .filter(group => group.tenant_id === form.tenant_id && group.id !== editingId.value)
  .map(group => ({ value: group.id, label: group.name })))

function tenantName(id: string): string {
  return tenants.value.find(tenant => tenant.id === id)?.name || '未知租户'
}

async function loadGroups(): Promise<void> {
  loading.value = true
  try {
    const query = tenantId.value ? `?tenant_id=${encodeURIComponent(tenantId.value)}` : ''
    groups.value = await api<Group[]>(`${props.apiPrefix}/groups${query}`)
  } catch (error) {
    groups.value = []
    message.error(error instanceof Error ? error.message : '读取用户组失败')
  } finally { loading.value = false }
}

function createGroup(): void {
  editingId.value = null
  // 默认租户优先沿用当前筛选值；若筛选停在平台租户（不参与创建）则回落到首个可建租户
  const preferredTenantId = tenantId.value
  const defaultTenantId = preferredTenantId && creatableTenantOptions.value.some(option => option.value === preferredTenantId)
    ? preferredTenantId
    : creatableTenantOptions.value[0]?.value || ''
  Object.assign(form, { tenant_id: defaultTenantId, key: '', name: '', description: '', parent_group_id: '' })
  groupOpen.value = true
}

function editGroup(group: Group): void {
  editingId.value = group.id
  Object.assign(form, { tenant_id: group.tenant_id, key: group.key, name: group.name, description: group.description || '', parent_group_id: group.parent_group_id || '' })
  groupOpen.value = true
}

async function saveGroup(): Promise<void> {
  try {
    await groupFormRef.value?.validate()
  } catch {
    // Ant Design Vue 已在字段下展示校验信息；无效表单不发出写请求。
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await api(`${props.apiPrefix}/groups/${editingId.value}`, { method: 'PATCH', body: JSON.stringify({
        name: form.name.trim(), description: form.description.trim() || null,
        parent_group_id: form.parent_group_id || null,
      }) })
      message.success('用户组已更新')
    } else {
      await api(`${props.apiPrefix}/groups`, { method: 'POST', body: JSON.stringify({
        tenant_id: form.tenant_id, key: form.key.trim(), name: form.name.trim(),
        description: form.description.trim() || null, parent_group_id: form.parent_group_id || null,
      }) })
      message.success('用户组已创建')
    }
    groupOpen.value = false
    await loadGroups()
  } catch (error) { message.error(error instanceof Error ? error.message : '保存用户组失败') }
  finally { saving.value = false }
}

// 打开共享关系弹窗：成员/角色目录由弹窗自行拉取并回填已选项。
function openRelation(group: Group, kind: 'members' | 'roles'): void {
  relationGroupId.value = group.id
  relationGroupName.value = group.name
  relationKind.value = kind
  relationOpen.value = true
}

async function onRelationSaved(): Promise<void> {
  await loadGroups()
}

function toggleStatus(group: Group): void {
  const status = group.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(`${props.apiPrefix}/groups/${group.id}/status?status=${status}`, { method: 'PATCH' })
      message.success(status === 'active' ? '用户组已启用' : '用户组已停用')
      await loadGroups()
    } catch (error) { message.error(error instanceof Error ? error.message : '状态更新失败') }
  }
  if (status === 'disabled') Modal.confirm({
    title: '停用用户组？', content: `停用后「${group.name}」会立即停止向成员继承角色；成员和角色配置会保留。`,
    okText: '停用用户组', cancelText: '取消', okButtonProps: { danger: true }, onOk: update,
  })
  else void update()
}

// 组操作列「更多」菜单（P352 收敛）：编辑/停用/删除为低频动作。
type GroupRowMenuKey = 'edit' | 'toggle' | 'delete'

function onRowMenuClick(info: { key: string | number }, group: Group): void {
  const key = String(info.key) as GroupRowMenuKey
  if (key === 'edit') editGroup(group)
  else if (key === 'toggle') toggleStatus(group)
  else if (key === 'delete') deleteGroup(group)
}

// 删除用户组（P352）：成员挂接与角色分配级联清除，成员账号不受影响；后端会先 bump 组内成员凭证。
function deleteGroup(group: Group): void {
  Modal.confirm({
    title: `删除用户组“${group.name}”？`,
    content: '将永久删除该用户组并解除全部成员挂接与角色分配；成员账号本身与其直连角色绑定不受影响。此操作不可恢复。',
    okText: '永久删除', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`${props.apiPrefix}/groups/${group.id}`, { method: 'DELETE' })
        message.success('用户组已删除')
        await loadGroups()
      } catch (error) { message.error(error instanceof Error ? error.message : '删除用户组失败') }
    },
  })
}

async function ensureTenantOptions(): Promise<void> {
  if (props.tenants.length || localTenants.value.length) {
    if (!tenantId.value) tenantId.value = tenants.value[0]?.id || ''
    return
  }
  try {
    localTenants.value = await api<Tenant[]>('/admin/tenants')
    if (!tenantId.value) tenantId.value = tenants.value[0]?.id || ''
  } catch (error) { message.error(error instanceof Error ? error.message : '读取租户失败') }
}

// 仅在用户组页激活时加载数据；平台壳已注入租户目录时复用，避免重复请求 /admin/tenants。
watch(() => props.active, active => {
  if (!active) return
  void (async () => {
    await ensureTenantOptions()
    await loadGroups()
  })()
}, { immediate: true })
</script>

<template>
  <section class="groups-page">
        <a-alert type="info" show-icon class="mb-3" message="高级列表：用户组完整 CRUD。组织上下文请到「组织工作台」。" />
<AdminListPage
      eyebrow="IDENTITY GROUPS"
      title="用户组"
      subtitle="按租户组织成员并继承角色；直接角色和多个用户组角色都会参与统一授权判定。"
      hint="停用用户组会暂停角色继承，重新启用后恢复。"
      :columns="columns"
      :data-source="groups"
      :loading="loading"
      row-key="id"
      class="scroll-actions-on-mobile"
      :scroll="{ x: 980, y: 'calc(100vh - 430px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
      empty-emoji="👥"
      :empty-text="tenantId ? '当前租户还没有用户组' : '当前筛选条件下还没有用户组'"
    >
      <template #header-extra>
        <a-button v-if="canManage" type="primary" :disabled="!tenants.length" @click="createGroup">＋ 新建用户组</a-button>
      </template>
      <a-select v-model:value="tenantId" placeholder="全部租户" allow-clear class="admin-filter-wide"
        :options="tenants.map(tenant => ({ value: tenant.id, label: tenant.name }))" @change="loadGroups" />
      <template #actions>
        <a-button :loading="loading" @click="loadGroups">刷新</a-button>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'tenant_id'">{{ tenantName(record.tenant_id) }}</template>
        <template v-else-if="column.key === 'parent_group'">{{ parentGroupName(record as Group) }}</template>
        <template v-if="column.key === 'status'"><a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag></template>
        <template v-else-if="column.key === 'actions'"><a-space :size="2">
          <a-button type="link" size="small" @click="openRelation(record, 'members')">管理成员</a-button>
          <a-button type="link" size="small" @click="openRelation(record, 'roles')">分配角色</a-button>
          <a-dropdown v-if="canManage">
            <a-button type="link" size="small" class="flex items-center gap-1">
              更多
              <DownOutlined class="text-[11px]" />
            </a-button>
            <template #overlay>
              <a-menu @click="onRowMenuClick($event, record)">
                <a-menu-item key="edit">编辑</a-menu-item>
                <a-menu-item key="toggle" :danger="record.status === 'active'">{{ record.status === 'active' ? '停用' : '启用' }}</a-menu-item>
                <a-menu-divider />
                <a-menu-item key="delete" danger>删除用户组</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </a-space></template>
        <template v-else-if="column.key === 'created_at'">{{ record.created_at ? new Date(record.created_at).toLocaleString() : '—' }}</template>
      </template>
    </AdminListPage>

    <a-modal v-model:open="groupOpen" :title="editingId ? '编辑用户组' : '新建用户组'" ok-text="保存" cancel-text="取消" :ok-button-props="{ disabled: !canManage }" :confirm-loading="saving" @ok="saveGroup">
      <a-form ref="groupFormRef" :model="form" :rules="groupRules" layout="vertical">
        <a-form-item label="所属租户" name="tenant_id"><a-select v-model:value="form.tenant_id" :disabled="Boolean(editingId)" :options="creatableTenantOptions" /></a-form-item>
        <a-form-item label="用户组标识" name="key"><a-input v-model:value="form.key" :disabled="Boolean(editingId)" :maxlength="100" placeholder="engineering-team" /></a-form-item>
        <a-form-item label="用户组名称" name="name"><a-input v-model:value="form.name" :maxlength="120" /></a-form-item>
        <!-- G24 组嵌套：父组角色沿祖先链递归继承；层级由服务端防环校验。 -->
        <a-form-item label="上级组（可选）"><a-select v-model:value="form.parent_group_id" allow-clear :options="parentOptions" placeholder="不选则为顶层组" /></a-form-item>
        <a-form-item label="说明" name="description"><a-textarea v-model:value="form.description" :rows="3" :maxlength="500" /></a-form-item>
        <a-alert v-if="editingId" type="info" show-icon message="租户和用户组标识创建后不可修改。" />
      </a-form>
    </a-modal>

    <!-- 组员/组角色编辑复用共享弹窗；目录拉取与保存逻辑都在组件内部。 -->
    <GroupRelationModal
      v-model:open="relationOpen"
      :kind="relationKind"
      :group-id="relationGroupId"
      :group-name="relationGroupName"
      :api-prefix="apiPrefix"
      :can-save="canManage"
      @saved="onRelationSaved"
    />
  </section>
</template>

<style scoped>
.groups-page { display: grid; gap: 20px; }
.data-card { border-radius: 16px; }
.table-hint { flex: 1; color: var(--color-text-secondary); font-size: 12px; }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
}
</style>
