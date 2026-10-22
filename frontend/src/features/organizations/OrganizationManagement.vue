<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '../../shared/services/api'
import AdminPageHeader from '../../shared/components/AdminPageHeader.vue'
import AdminTableToolbar from '../../shared/components/AdminTableToolbar.vue'

interface TenantOption { id: string; name: string; status: string; can_read_organizations?: boolean; can_manage_organizations?: boolean }
interface Organization {
  id: string
  tenant_id: string
  parent_name: string
  key: string
  name: string
  status: 'active' | 'disabled'
  created_at: string
}

const props = withDefaults(defineProps<{ active: boolean; tenants: TenantOption[]; apiPrefix?: string }>(), { apiPrefix: '/admin' })
const organizations = ref<Organization[]>([])
const tenantId = ref('')
const loading = ref(false)
const createOpen = ref(false)
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<unknown> }>()
const form = reactive({ tenant_id: '', parent_id: '', key: '', name: '' })
const createParentOrganizations = ref<Organization[]>([])
const loadingParentOrganizations = ref(false)
let requestSequence = 0
let createParentRequestSequence = 0

const tenantOptions = computed(() => props.tenants.map(tenant => ({ value: tenant.id, label: tenant.name })))
const viewableTenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.status === 'active' && (props.apiPrefix === '/admin' || tenant.can_read_organizations === true))
  .map(tenant => ({ value: tenant.id, label: tenant.name })))
const activeTenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.status === 'active' && (props.apiPrefix === '/admin' || tenant.can_manage_organizations === true))
  .map(tenant => ({ value: tenant.id, label: tenant.name })))
const canManageTenant = computed(() => props.apiPrefix === '/admin'
  || props.tenants.some(tenant => tenant.id === tenantId.value && tenant.can_manage_organizations === true))
const parentOptions = computed(() => createParentOrganizations.value
  .filter(organization => organization.tenant_id === form.tenant_id && organization.status === 'active')
  .map(organization => ({ value: organization.id, label: `${organization.name} (${organization.key})` })))

const columns = computed(() => [
  { title: '组织名称', dataIndex: 'name', key: 'name', width: 240, ellipsis: true },
  { title: '组织标识', dataIndex: 'key', key: 'key', width: 220, ellipsis: true },
  { title: '上级组织', dataIndex: 'parent_name', key: 'parent_name', width: 200, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 190 },
  ...(canManageTenant.value ? [{ title: '操作', dataIndex: 'actions', key: 'actions', width: 120, fixed: 'right' as const }] : []),
])

const rules = {
  tenant_id: [{ required: true, message: '请选择所属租户', trigger: 'change' }],
  key: [
    { required: true, min: 2, max: 100, pattern: /^[a-z0-9][a-z0-9._-]+$/, message: '使用 2–100 位小写字母、数字、点、下划线或连字符，首字符须为字母或数字', trigger: 'blur' },
  ],
  name: [
    { required: true, whitespace: true, max: 160, message: '请输入不超过 160 个字符的组织名称', trigger: 'blur' },
  ],
}

async function loadOrganizations(): Promise<void> {
  if (!props.active || !tenantId.value) {
    organizations.value = []
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  try {
    const result = await api<Organization[]>(`${props.apiPrefix}/organizations?tenant_id=${encodeURIComponent(tenantId.value)}`)
    if (sequence === requestSequence && props.active && tenantId.value) organizations.value = result
  } catch (error) {
    if (sequence !== requestSequence) return
    organizations.value = []
    message.error(error instanceof Error ? error.message : '读取组织目录失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function openCreate(): void {
  Object.assign(form, {
    tenant_id: activeTenantOptions.value.find(tenant => tenant.value === tenantId.value)?.value
      || activeTenantOptions.value[0]?.value || '',
    parent_id: '', key: '', name: '',
  })
  createOpen.value = true
  void loadCreateParentOrganizations()
}

async function loadCreateParentOrganizations(): Promise<void> {
  const selectedTenant = form.tenant_id
  const sequence = ++createParentRequestSequence
  if (!selectedTenant) {
    createParentOrganizations.value = []
    loadingParentOrganizations.value = false
    return
  }
  loadingParentOrganizations.value = true
  try {
    const result = await api<Organization[]>(`${props.apiPrefix}/organizations?tenant_id=${encodeURIComponent(selectedTenant)}`)
    if (sequence === createParentRequestSequence && form.tenant_id === selectedTenant) {
      createParentOrganizations.value = result
    }
  } catch (error) {
    if (sequence === createParentRequestSequence) {
      createParentOrganizations.value = []
      message.error(error instanceof Error ? error.message : '读取上级组织失败')
    }
  } finally {
    if (sequence === createParentRequestSequence) loadingParentOrganizations.value = false
  }
}

function changeCreateTenant(): void {
  form.parent_id = ''
  void loadCreateParentOrganizations()
}

async function createOrganization(): Promise<void> {
  try { await formRef.value?.validate() } catch { return }
  if (!activeTenantOptions.value.some(tenant => tenant.value === form.tenant_id)) {
    message.error('请选择活动租户')
    return
  }
  saving.value = true
  try {
    const payload: Record<string, string> = {
      tenant_id: form.tenant_id,
      key: form.key.trim(),
      name: form.name.trim(),
    }
    if (form.parent_id) payload.parent_id = form.parent_id
    await api(`${props.apiPrefix}/organizations`, { method: 'POST', body: JSON.stringify(payload) })
    message.success('组织已创建')
    createOpen.value = false
    if (tenantId.value !== form.tenant_id) {
      tenantId.value = form.tenant_id
      // 租户筛选的 watcher 会加载新目录，避免发起重复请求。
    } else await loadOrganizations()
  } catch (error) { message.error(error instanceof Error ? error.message : '创建组织失败') }
  finally { saving.value = false }
}

function changeStatus(organization: Organization): void {
  const status = organization.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(`${props.apiPrefix}/organizations/${organization.id}`, {
        method: 'PATCH', body: JSON.stringify({ status }),
      })
      message.success(status === 'active' ? '组织已启用' : '组织已停用')
      await loadOrganizations()
    } catch (error) { message.error(error instanceof Error ? error.message : '更新组织状态失败') }
  }
  if (status === 'disabled') Modal.confirm({
    title: '停用组织？',
    content: `停用“${organization.name}”后，成员不能再被新分配到该组织，该组织关联的数据范围也不会包含它。`,
    okText: '停用组织', cancelText: '取消', okButtonProps: { danger: true }, onOk: update,
  })
  else void update()
}

watch(() => props.active, active => {
  if (!active) return
  if (!tenantId.value) tenantId.value = viewableTenantOptions.value[0]?.value || ''
  void loadOrganizations()
}, { immediate: true })
watch(tenantId, () => { if (props.active) void loadOrganizations() })
watch(() => props.tenants, () => {
  if (props.active && !tenantId.value) tenantId.value = viewableTenantOptions.value[0]?.value || ''
}, { deep: true })
</script>

<template>
  <section class="organizations-page">
    <AdminPageHeader
      eyebrow="ORGANIZATION DIRECTORY"
      title="组织管理"
      subtitle="维护租户内的组织树，成员归属与角色数据范围会引用这里的组织关系。"
    >
      <template #extra>
        <a-button v-if="apiPrefix === '/admin' || canManageTenant" type="primary" :disabled="!activeTenantOptions.length" @click="openCreate">＋ 新建组织</a-button>
      </template>
    </AdminPageHeader>

    <a-card class="data-card" :bordered="false">
      <AdminTableToolbar :hint="canManageTenant ? '组织标识创建后不可修改；上级组织仅能选择同一租户中的启用组织。' : '当前为只读访问；组织变更需由具备 iam.organization.manage 权限的管理员执行。'">
        <a-select v-model:value="tenantId" placeholder="选择租户" :options="tenantOptions" />
        <template #actions>
          <a-button :loading="loading" :disabled="!tenantId" @click="loadOrganizations">刷新</a-button>
        </template>
      </AdminTableToolbar>
      <a-table :data-source="organizations" :columns="columns" :loading="loading" row-key="id"
        :scroll="{ x: 1040 }" :pagination="{ pageSize: 10, showSizeChanger: true }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
          </template>
          <template v-else-if="column.key === 'created_at'">{{ record.created_at ? new Date(record.created_at).toLocaleString() : '—' }}</template>
          <template v-else-if="column.key === 'actions' && canManageTenant">
            <a-button type="link" size="small" :danger="record.status === 'active'" @click="changeStatus(record)">
              {{ record.status === 'active' ? '停用' : '启用' }}
            </a-button>
          </template>
        </template>
        <template #emptyText><a-empty :description="tenantId ? '该租户还没有组织' : '请先创建租户，再维护组织结构'" /></template>
      </a-table>
    </a-card>

    <a-modal v-model:open="createOpen" title="新建组织" ok-text="创建" cancel-text="取消"
      :confirm-loading="saving" @ok="createOrganization">
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <a-form-item label="所属租户" name="tenant_id">
          <a-select v-model:value="form.tenant_id" :options="activeTenantOptions" placeholder="选择活动租户"
            @change="changeCreateTenant" />
        </a-form-item>
        <a-form-item label="组织标识" name="key">
          <a-input v-model:value="form.key" :maxlength="100" placeholder="engineering" />
        </a-form-item>
        <a-form-item label="组织名称" name="name"><a-input v-model:value="form.name" :maxlength="160" /></a-form-item>
        <a-form-item label="上级组织（可选）" name="parent_id">
          <a-select v-model:value="form.parent_id" allow-clear :loading="loadingParentOrganizations"
            :options="parentOptions" placeholder="顶层组织" />
        </a-form-item>
        <a-alert type="info" show-icon message="服务端会拒绝跨租户父组织及循环层级；更改组织结构会影响下游数据范围计算。" />
      </a-form>
    </a-modal>
  </section>
</template>

<style scoped>
.organizations-page { display: grid; gap: 20px; }
.data-card { border-radius: 16px; }
.table-toolbar { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.tenant-filter { width: min(280px, 100%); flex: 0 0 auto; }
.table-hint { flex: 1; color: #7c8798; font-size: 12px; }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
  .table-toolbar { align-items: stretch; flex-direction: column; }
  .tenant-filter { width: 100%; }
}
</style>
