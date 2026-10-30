<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHas, getCachedCapabilities } from '@/api/capabilities'
import AdminListPage from '@/components/AdminListPage.vue'

interface TenantOption { id: string; name: string; status: string; slug?: string; can_read_organizations?: boolean; can_manage_organizations?: boolean }
interface Organization {
  id: string
  tenant_id: string
  parent_id: string | null
  parent_name: string
  owner_user_id?: string | null
  owner_name?: string | null
  key: string
  name: string
  status: 'active' | 'disabled'
  created_at: string
}

/** 树形表格行：平面组织记录 + 子组织（antd Table 以 children 键渲染层级缩进）。 */
type OrganizationTreeRow = Organization & { children?: OrganizationTreeRow[] }

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

// G24 设置部门负责人：成员选项来自该租户活动成员；清空即移除负责人，变更写审计。
const ownerOpen = ref(false)
const ownerSaving = ref(false)
const ownerMembersLoading = ref(false)
const ownerTarget = ref<Organization | null>(null)
const ownerUserId = ref<string | undefined>(undefined)
const ownerMemberOptions = ref<{ value: string; label: string }[]>([])

async function openOwnerEditor(organization: Organization): Promise<void> {
  ownerTarget.value = organization
  ownerUserId.value = organization.owner_user_id || undefined
  ownerMemberOptions.value = []
  ownerOpen.value = true
  ownerMembersLoading.value = true
  try {
    const page = await api<{ items: { user_id: string; display_name: string; email: string }[] }>(
      `/tenant-admin/members?tenant_id=${encodeURIComponent(organization.tenant_id)}&limit=500`)
    ownerMemberOptions.value = page.items.map(member => ({
      value: member.user_id,
      label: `${member.display_name}（${member.email}）`,
    }))
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取租户成员失败')
  } finally { ownerMembersLoading.value = false }
}

async function saveOwner(): Promise<void> {
  if (!ownerTarget.value) return
  ownerSaving.value = true
  try {
    await api(`/admin/organizations/${ownerTarget.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ owner_user_id: ownerUserId.value || null }),
    })
    message.success('负责人已更新')
    ownerOpen.value = false
    await loadOrganizations()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '更新负责人失败')
  } finally { ownerSaving.value = false }
}

// 平台引导租户（slug=platform）为系统保留租户，不承载业务组织，创建与查看下拉均排除
const tenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.slug !== 'platform')
  .map(tenant => ({ value: tenant.id, label: tenant.name })))
// 平台引导租户（slug=platform）为系统保留租户，不承载业务组织，创建与查看下拉均排除
const viewableTenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.slug !== 'platform' && tenant.status === 'active' && (getCachedCapabilities()?.platform_admin === true || tenant.can_read_organizations === true || cachedHas('org.read')))
  .map(tenant => ({ value: tenant.id, label: tenant.name })))
// 平台引导租户（slug=platform）为系统保留租户，不承载业务组织，创建与查看下拉均排除
const activeTenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.slug !== 'platform' && tenant.status === 'active' && (getCachedCapabilities()?.platform_admin === true || tenant.can_manage_organizations === true))
  .map(tenant => ({ value: tenant.id, label: tenant.name })))
const canManageTenant = computed(() => {
  if (cachedHas('org.manage') && getCachedCapabilities()?.platform_admin) return true
  return props.tenants.some(tenant => tenant.id === tenantId.value && tenant.can_manage_organizations === true)
})
const parentOptions = computed(() => createParentOrganizations.value
  .filter(organization => organization.tenant_id === form.tenant_id && organization.status === 'active')
  .map(organization => ({ value: organization.id, label: `${organization.name} (${organization.key})` })))

// 树形表格（用户反馈：组织管理应为树形）：按 parent_id 组装层级；父行缺失的孤儿按顶层兜底。
const organizationTree = computed<OrganizationTreeRow[]>(() => {
  const rows = organizations.value
  const byId = new Map<string, OrganizationTreeRow>(rows.map(row => [row.id, { ...row }]))
  const roots: OrganizationTreeRow[] = []
  for (const row of byId.values()) {
    const parent = row.parent_id ? byId.get(row.parent_id) : undefined
    if (parent && parent !== row) {
      parent.children = parent.children || []
      parent.children.push(row)
    } else {
      roots.push(row)
    }
  }
  return roots
})
// 受控展开：新数据默认全部展开，用户仍可手动折叠。
const expandedRowKeys = ref<string[]>([])
watch(organizations, rows => { expandedRowKeys.value = rows.map(row => row.id) }, { immediate: true })

function onExpandedRowsChange(keys: readonly (string | number)[]): void {
  expandedRowKeys.value = keys.map(String)
}

const columns = computed(() => [
  // 列宽合计压到 ~820：1280 视口（内容 ~992px）不再横向滚动（原 1040）
  { title: '组织名称', dataIndex: 'name', key: 'name', width: 240, ellipsis: true },
  { title: '组织标识', dataIndex: 'key', key: 'key', width: 200, ellipsis: true },
  // G24 部门负责人：列表展示 + 「设置负责人」行内入口。
  { title: '负责人', key: 'owner', width: 130, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 88 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  ...(canManageTenant.value ? [{ title: '操作', dataIndex: 'actions', key: 'actions', width: 110, fixed: 'right' as const }] : []),
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

// 删除组织（P352）：成员挂接级联摘除（成员账号保留）；存在子组织时后端 409 提示先处理子级。
function deleteOrganization(organization: Organization): void {
  Modal.confirm({
    title: `删除组织“${organization.name}”？`,
    content: '将永久删除该组织并解除全部成员挂接（成员账号本身保留）；关联数据范围中的该组织将不再生效。存在子组织时需先删除或移动子组织。',
    okText: '永久删除', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`${props.apiPrefix}/organizations/${organization.id}`, { method: 'DELETE' })
        message.success('组织已删除')
        await loadOrganizations()
      } catch (error) { message.error(error instanceof Error ? error.message : '删除组织失败') }
    },
  })
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
        <a-alert type="info" show-icon class="mb-3" message="高级列表：组织完整 CRUD。成员与用户组日常请到「组织工作台」。" />
<AdminListPage
      eyebrow="应用组织"
      title="应用组织"
      subtitle="维护租户内的组织树，成员归属与角色数据范围会引用这里的组织关系。"
      :hint="canManageTenant ? '组织标识创建后不可修改；上级组织仅能选择同一租户中的启用组织。' : '当前为只读访问；组织变更需由具备 org.manage 权限的管理员执行。'"
      :columns="columns"
      :data-source="organizationTree"
      :expanded-row-keys="expandedRowKeys"
      @expanded-rows-change="onExpandedRowsChange"
      :loading="loading"
      row-key="id"
      :scroll="{ x: 820, y: 'calc(100vh - 430px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
      empty-emoji="🏛️"
      :empty-text="tenantId ? '该租户还没有组织' : '请先创建租户，再维护组织结构'"
    >
      <template #header-extra>
        <a-button v-if="canManageTenant" type="primary" :disabled="!activeTenantOptions.length" @click="openCreate">＋ 新建组织</a-button>
      </template>
      <a-select v-model:value="tenantId" placeholder="选择租户" :options="tenantOptions" class="admin-filter-wide" />
      <template #actions>
        <a-button :loading="loading" :disabled="!tenantId" @click="loadOrganizations">刷新</a-button>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'owner'">{{ record.owner_name || '—' }}</template>
        <template v-else-if="column.key === 'created_at'">{{ record.created_at ? new Date(record.created_at).toLocaleString() : '—' }}</template>
        <template v-else-if="column.key === 'actions' && canManageTenant">
          <a-space :size="2">
            <a-button type="link" size="small" @click="openOwnerEditor(record)">负责人</a-button>
            <a-button type="link" size="small" :danger="record.status === 'active'" @click="changeStatus(record)">
              {{ record.status === 'active' ? '停用' : '启用' }}
            </a-button>
            <a-button type="link" size="small" danger @click="deleteOrganization(record)">删除</a-button>
          </a-space>
        </template>
      </template>
    </AdminListPage>

    <!-- G24 设置部门负责人：成员选项来自该租户活动成员；清空即移除负责人，变更写审计。 -->
    <a-modal v-model:open="ownerOpen" title="设置部门负责人" ok-text="保存" cancel-text="取消"
      :confirm-loading="ownerSaving" @ok="saveOwner">
      <a-form layout="vertical">
        <a-form-item label="组织"><a-input :value="ownerTarget?.name" disabled /></a-form-item>
        <a-form-item label="负责人（可选）">
          <a-select v-model:value="ownerUserId" allow-clear show-search option-filter-prop="label"
            :loading="ownerMembersLoading" :options="ownerMemberOptions" placeholder="选择该租户内的活动成员" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="createOpen" title="新建组织" ok-text="创建" cancel-text="取消"
      :confirm-loading="saving" @ok="createOrganization">
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <a-form-item label="所属租户" name="tenant_id">
          <a-select v-model:value="form.tenant_id" :options="activeTenantOptions" placeholder="选择活动租户"
            @change="changeCreateTenant" />
        </a-form-item>
        <a-form-item label="组织标识" name="key">
          <a-input v-model:value="form.key" :maxlength="100" placeholder="例如 eng（英文标识，名称另填中文）" />
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
.table-hint { flex: 1; color: var(--color-text-secondary); font-size: 12px; }
@media (max-width: 700px) {
  .page-heading { align-items: flex-start; flex-direction: column; }
}
</style>
