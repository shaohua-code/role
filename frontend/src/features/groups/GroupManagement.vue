<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '../../shared/services/api'

interface Tenant { id: string; name: string }

const props = withDefaults(defineProps<{
  active?: boolean
  tenants?: Tenant[]
}>(), {
  active: false,
  tenants: () => [],
})
interface Group {
  id: string; tenant_id: string; key: string; name: string; description?: string | null
  status: 'active' | 'disabled'; member_count: number; role_count: number; created_at?: string
}
interface Member {
  user_id: string; email?: string | null; display_name: string; user_status: string
  membership_status: string; in_group: boolean
}
interface GroupRole { id: string; key: string; name: string; status: string; assigned: boolean }

const groups = ref<Group[]>([])
const localTenants = ref<Tenant[]>([])
const tenants = computed(() => (props.tenants.length ? props.tenants : localTenants.value))
const tenantId = ref('')
const loading = ref(false)
const saving = ref(false)
const groupOpen = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({ tenant_id: '', key: '', name: '', description: '' })
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
const relationDialogOpen = ref(false)
const relationKind = ref<'members' | 'roles' | null>(null)
const relationGroupId = ref('')
const relationGroupName = ref('')
const relationSaving = ref(false)
const selectedUserIds = ref<string[]>([])
const userOptions = ref<{ value: string; label: string }[]>([])
const selectedRoleIds = ref<string[]>([])
const roleOptions = ref<{ value: string; label: string }[]>([])

const columns = computed(() => [
  { title: '用户组', dataIndex: 'name', key: 'name', width: 170 },
  { title: '所属租户', dataIndex: 'tenant_id', key: 'tenant_id', width: 180 },
  { title: '标识', dataIndex: 'key', key: 'key', width: 150 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '成员', dataIndex: 'member_count', key: 'member_count', width: 80 },
  { title: '角色', dataIndex: 'role_count', key: 'role_count', width: 80 },
  { title: '说明', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 300, fixed: 'right' as const },
])

function tenantName(id: string): string {
  return tenants.value.find(tenant => tenant.id === id)?.name || '未知租户'
}

async function loadGroups(): Promise<void> {
  loading.value = true
  try {
    const query = tenantId.value ? `?tenant_id=${encodeURIComponent(tenantId.value)}` : ''
    groups.value = await api<Group[]>(`/admin/groups${query}`)
  } catch (error) {
    groups.value = []
    message.error(error instanceof Error ? error.message : '读取用户组失败')
  } finally { loading.value = false }
}

function createGroup(): void {
  editingId.value = null
  Object.assign(form, { tenant_id: tenantId.value || tenants.value[0]?.id || '', key: '', name: '', description: '' })
  groupOpen.value = true
}

function editGroup(group: Group): void {
  editingId.value = group.id
  Object.assign(form, { tenant_id: group.tenant_id, key: group.key, name: group.name, description: group.description || '' })
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
      await api(`/admin/groups/${editingId.value}`, { method: 'PATCH', body: JSON.stringify({
        name: form.name.trim(), description: form.description.trim() || null,
      }) })
      message.success('用户组已更新')
    } else {
      await api('/admin/groups', { method: 'POST', body: JSON.stringify({
        tenant_id: form.tenant_id, key: form.key.trim(), name: form.name.trim(),
        description: form.description.trim() || null,
      }) })
      message.success('用户组已创建')
    }
    groupOpen.value = false
    await loadGroups()
  } catch (error) { message.error(error instanceof Error ? error.message : '保存用户组失败') }
  finally { saving.value = false }
}

async function openMembers(group: Group): Promise<void> {
  relationGroupId.value = group.id
  relationGroupName.value = group.name
  try {
    const members = await api<Member[]>(`/admin/groups/${group.id}/members`)
    selectedUserIds.value = members.filter(member => member.in_group).map(member => member.user_id)
    userOptions.value = members.map(member => ({ value: member.user_id,
      label: `${member.display_name} · ${member.email || '无邮箱'} · ${member.membership_status === 'active' ? '租户成员正常' : '租户成员已停用'}${member.user_status === 'active' ? '' : ' · 全局账号已停用'}` }))
    relationKind.value = 'members'
    relationDialogOpen.value = true
  } catch (error) { message.error(error instanceof Error ? error.message : '读取组成员失败') }
}

async function openRoles(group: Group): Promise<void> {
  relationGroupId.value = group.id
  relationGroupName.value = group.name
  try {
    const roles = await api<GroupRole[]>(`/admin/groups/${group.id}/roles`)
    selectedRoleIds.value = roles.filter(role => role.assigned).map(role => role.id)
    roleOptions.value = roles.map(role => ({ value: role.id,
      label: `${role.name} · ${role.key}${role.status === 'active' ? '' : ' · 角色已停用'}` }))
    relationKind.value = 'roles'
    relationDialogOpen.value = true
  } catch (error) { message.error(error instanceof Error ? error.message : '读取组角色失败') }
}

async function saveRelations(): Promise<void> {
  if (!relationKind.value) return
  relationSaving.value = true
  const isMembers = relationKind.value === 'members'
  try {
    await api(`/admin/groups/${relationGroupId.value}/${relationKind.value}`, {
      method: 'PUT', body: JSON.stringify(isMembers
        ? { user_ids: selectedUserIds.value }
        : { role_ids: selectedRoleIds.value }),
    })
    message.success(isMembers ? '组成员已保存' : '组角色已保存')
    relationDialogOpen.value = false
    relationKind.value = null
    await loadGroups()
  } catch (error) { message.error(error instanceof Error ? error.message : '保存用户组关系失败') }
  finally { relationSaving.value = false }
}

function toggleStatus(group: Group): void {
  const status = group.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(`/admin/groups/${group.id}/status?status=${status}`, { method: 'PATCH' })
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
    <header class="page-heading">
      <div><p class="eyebrow">IDENTITY GROUPS</p><h1>用户组</h1>
        <p class="subtitle">按租户组织成员并继承角色；直接角色和多个用户组角色都会参与统一授权判定。</p></div>
      <a-button type="primary" :disabled="!tenants.length" @click="createGroup">＋ 新建用户组</a-button>
    </header>

    <a-card class="data-card" :bordered="false">
      <div class="table-toolbar">
        <a-select v-model:value="tenantId" class="tenant-filter" placeholder="全部租户" allow-clear
          :options="tenants.map(tenant => ({ value: tenant.id, label: tenant.name }))" @change="loadGroups" />
        <span class="table-hint">停用用户组会暂停角色继承，重新启用后恢复。</span>
        <a-button :loading="loading" @click="loadGroups">刷新</a-button>
      </div>
      <a-table class="scroll-actions-on-mobile" :data-source="groups" :columns="columns" :loading="loading" row-key="id"
        :scroll="{ x: 980 }" :pagination="{ pageSize: 10, showSizeChanger: true }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'tenant_id'">{{ tenantName(record.tenant_id) }}</template>
          <template v-if="column.key === 'status'"><a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag></template>
          <template v-else-if="column.key === 'actions'"><a-space :size="2">
            <a-button type="link" size="small" @click="editGroup(record)">编辑</a-button>
            <a-button type="link" size="small" @click="openMembers(record)">管理成员</a-button>
            <a-button type="link" size="small" @click="openRoles(record)">分配角色</a-button>
            <a-button type="link" size="small" :danger="record.status === 'active'" @click="toggleStatus(record)">{{ record.status === 'active' ? '停用' : '启用' }}</a-button>
          </a-space></template>
          <template v-else-if="column.key === 'created_at'">{{ record.created_at ? new Date(record.created_at).toLocaleString() : '—' }}</template>
        </template>
        <template #emptyText><a-empty :description="tenantId ? '当前租户还没有用户组' : '当前筛选条件下还没有用户组'" /></template>
      </a-table>
    </a-card>

    <a-modal v-model:open="groupOpen" :title="editingId ? '编辑用户组' : '新建用户组'" ok-text="保存" cancel-text="取消" :confirm-loading="saving" @ok="saveGroup">
      <a-form ref="groupFormRef" :model="form" :rules="groupRules" layout="vertical">
        <a-form-item label="所属租户" name="tenant_id"><a-select v-model:value="form.tenant_id" :disabled="Boolean(editingId)" :options="tenants.map(tenant => ({ value: tenant.id, label: tenant.name }))" /></a-form-item>
        <a-form-item label="用户组标识" name="key"><a-input v-model:value="form.key" :disabled="Boolean(editingId)" :maxlength="100" placeholder="engineering-team" /></a-form-item>
        <a-form-item label="用户组名称" name="name"><a-input v-model:value="form.name" :maxlength="120" /></a-form-item>
        <a-form-item label="说明" name="description"><a-textarea v-model:value="form.description" :rows="3" :maxlength="500" /></a-form-item>
        <a-alert v-if="editingId" type="info" show-icon message="租户和用户组标识创建后不可修改。" />
      </a-form>
    </a-modal>

    <a-modal v-model:open="relationDialogOpen" :title="`${relationKind === 'members' ? '管理成员' : '分配角色'} · ${relationGroupName}`"
      width="720px" :ok-text="relationKind === 'members' ? '保存成员' : '保存角色'" cancel-text="取消" :confirm-loading="relationSaving" @ok="saveRelations">
      <a-alert v-if="relationKind === 'members'" class="relation-note" type="info" show-icon message="停用成员的组关系会保留，但其当前身份不会因此获得有效权限。" />
      <a-alert v-else class="relation-note" type="info" show-icon message="组角色与用户直接分配的角色叠加判定；停用的角色不会授予权限。" />
      <a-select v-if="relationKind === 'members'" v-model:value="selectedUserIds" class="relation-select" mode="multiple" show-search option-filter-prop="label" :max-tag-count="'responsive'" :options="userOptions" placeholder="选择该租户中的用户" />
      <a-select v-else v-model:value="selectedRoleIds" class="relation-select" mode="multiple" show-search option-filter-prop="label" :max-tag-count="'responsive'" :options="roleOptions" placeholder="选择该租户中的角色" />
    </a-modal>
  </section>
</template>

<style scoped>
.groups-page { display: grid; gap: 20px; }
.page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.page-heading h1 { margin: 5px 0 7px; font-size: clamp(25px, 3vw, 32px); letter-spacing: -.035em; }
.page-heading .subtitle { max-width: 760px; margin: 0; color: #7c8798; line-height: 1.65; }
.eyebrow { margin: 0; color: #766fe8; font-size: 11px; font-weight: 750; letter-spacing: .14em; }
.data-card { border-radius: 16px; }
.table-toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.tenant-filter { width: 280px; flex: 0 0 auto; }
.table-hint { flex: 1; color: #7c8798; font-size: 12px; }
.relation-note { margin-bottom: 18px; }
.relation-select { width: 100%; }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
  .table-toolbar { align-items: stretch; flex-direction: column; }
  .tenant-filter { width: 100%; }
}
</style>
