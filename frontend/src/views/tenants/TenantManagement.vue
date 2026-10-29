<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHas } from '@/api/capabilities'
import { PAGE_PATHS } from '@/router/navigation'
import AdminListPage from '@/components/AdminListPage.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminDetailDrawer from '@/components/AdminDetailDrawer.vue'
import AdminMonoValue from '@/components/AdminMonoValue.vue'

interface Tenant {
  id: string
  name: string
  slug: string
  kind: 'organization' | 'consumer'
  status: 'active' | 'disabled'
  member_count: number
  /** 后端聚合字段（list_tenants 的 application_count）；字段缺失时列内显示 — */
  application_count?: number
}
interface TenantApplication {
  id: string; name: string; client_id: string
  status: 'active' | 'disabled'
}
interface TenantMember {
  user_id: string; email: string; display_name: string
  user_status: string; membership_status: string
}

const props = defineProps<{
  active: boolean
  shellTenants?: Tenant[] | null
  shellCatalogGeneration?: number
}>()
const emit = defineEmits<{ changed: [] }>()
const router = useRouter()
const canManageTenants = computed(() => cachedHas('platform.tenant.manage'))

let hydratedCatalogGeneration = -1

const tenants = ref<Tenant[]>([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const formRef = ref<{ validate: () => Promise<unknown> }>()
const form = reactive({ name: '', slug: '', kind: 'organization' as 'organization' | 'consumer' })
let requestSequence = 0
const rules = {
  name: [{ required: true, whitespace: true, max: 120, message: '请输入不超过 120 个字符的租户名称', trigger: 'blur' }],
  slug: [
    { required: true, message: '请输入租户标识', trigger: 'blur' },
    { pattern: /^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$/, message: '使用 3–80 位小写字母、数字或连字符，首尾必须为字母或数字', trigger: 'blur' },
  ],
}

// ===== 工具条筛选：搜索 + 类型/状态（数据 ≤500，前端即时过滤） =====
const searchText = ref('')
const kindFilter = ref('')
const statusFilter = ref('')
const kindOptions = [
  { value: '', label: '全部类型' },
  { value: 'organization', label: '组织/企业' },
  { value: 'consumer', label: 'ToC 消费' },
]
const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'active', label: '启用' },
  { value: 'disabled', label: '停用' },
]
const filteredTenants = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return tenants.value.filter(tenant => {
    if (kindFilter.value && tenant.kind !== kindFilter.value) return false
    if (statusFilter.value && tenant.status !== statusFilter.value) return false
    if (!query) return true
    return `${tenant.name} ${tenant.slug}`.toLocaleLowerCase().includes(query)
  })
})

const columns = [
  { title: '租户', dataIndex: 'name', key: 'name', width: 210 },
  { title: '类型', dataIndex: 'kind', key: 'kind', width: 110 },
  { title: '成员', dataIndex: 'member_count', key: 'member_count', width: 90 },
  { title: '应用', dataIndex: 'application_count', key: 'application_count', width: 90 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 88 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 190, fixed: 'right' as const },
]

function hydrateFromShell(): boolean {
  if (props.shellTenants == null) return false
  const generation = props.shellCatalogGeneration ?? -1
  if (generation < 0 || generation === hydratedCatalogGeneration) return false
  tenants.value = props.shellTenants
  hydratedCatalogGeneration = generation
  return true
}

async function loadTenants(): Promise<void> {
  const sequence = ++requestSequence
  loading.value = true
  // 目录刷新后子资源缓存一并失效，避免抽屉展示过期数据
  appsCache.clear()
  membersCache.clear()
  try {
    const result = await api<Tenant[]>('/admin/tenants')
    if (sequence === requestSequence) tenants.value = result
  } catch (error) {
    if (sequence === requestSequence) {
      tenants.value = []
      message.error(error instanceof Error ? error.message : '读取租户失败')
    }
  } finally { if (sequence === requestSequence) loading.value = false }
}

function createTenant(): void {
  Object.assign(form, { name: '', slug: '', kind: 'organization' })
  modalOpen.value = true
}

async function saveTenant(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    // Ant Design Vue 已展示字段错误；校验失败时不向 API 发送请求。
    return
  }
  saving.value = true
  try {
    await api('/admin/tenants', {
      method: 'POST',
      body: JSON.stringify({ name: form.name.trim(), slug: form.slug.trim(), kind: form.kind }),
    })
    message.success('租户已创建')
    modalOpen.value = false
    await loadTenants()
    emit('changed')
  } catch (error) { message.error(error instanceof Error ? error.message : '创建租户失败') }
  finally { saving.value = false }
}

function changeKind(tenant: Tenant): void {
  const kind = tenant.kind === 'consumer' ? 'organization' : 'consumer'
  const label = kind === 'consumer' ? 'ToC 消费租户' : '组织租户'
  Modal.confirm({
    title: `将“${tenant.name}”转为${label}？`,
    content: '转换前必须先关闭该租户下所有应用的自助注册。组织租户中的应用不能开放匿名注册；切换后仍需逐应用配置普通角色和协议，再单独开启注册。',
    okText: '确认切换', cancelText: '取消',
    onOk: async () => {
      try {
        await api(`/admin/tenants/${tenant.id}/kind`, {
          method: 'PATCH', body: JSON.stringify({ expected_kind: tenant.kind, kind }),
        })
        message.success('租户类型已更新')
        await loadTenants()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '更新租户类型失败') }
    },
  })
}

function changeStatus(tenant: Tenant): void {
  const status = tenant.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(`/admin/tenants/${tenant.id}/status?status=${status}`, { method: 'PATCH' })
      message.success(status === 'active' ? '租户已启用' : '租户已停用')
      await loadTenants()
      emit('changed')
    } catch (error) { message.error(error instanceof Error ? error.message : '更新租户状态失败') }
  }
  if (status === 'disabled') Modal.confirm({
    title: '停用租户？',
    content: `停用“${tenant.name}”会阻止旗下成员和应用继续使用，并撤销其 OAuth 刷新会话；重新启用不会恢复旧会话。`,
    okText: '停用租户', cancelText: '取消', okButtonProps: { danger: true }, onOk: update,
  })
  else void update()
}

// 删除租户（P352）：级联清除成员/角色/应用/邀请/用户组/组织/模型目录，不可恢复。
function deleteTenant(tenant: Tenant): void {
  Modal.confirm({
    title: `删除租户“${tenant.name}”？`,
    content: '将永久删除该租户及其全部成员关系、角色、应用、邀请、用户组、组织和模型目录，历史审计保留但不再关联该租户。此操作不可恢复。',
    okText: '永久删除', cancelText: '取消', okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`/admin/tenants/${tenant.id}`, { method: 'DELETE' })
        message.success('租户已删除')
        await loadTenants()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '删除租户失败') }
    },
  })
}

// ===== 行点击 → 租户详情抽屉（旗下应用点击跳工作台预选） =====
const detailOpen = ref(false)
const detailTenant = ref<Tenant | null>(null)
const detailApps = ref<TenantApplication[]>([])
const detailAppsLoading = ref(false)
// 已拉取过的租户应用缓存：同一会话内不重复请求；目录刷新/变更后整体失效
const appsCache = new Map<string, TenantApplication[]>()

async function openDetail(tenant: Tenant): Promise<void> {
  detailTenant.value = tenant
  detailOpen.value = true
  const cached = appsCache.get(tenant.id)
  if (cached) { detailApps.value = cached; return }
  detailApps.value = []
  detailAppsLoading.value = true
  try {
    const rows = await api<TenantApplication[]>(`/admin/applications?tenant_id=${encodeURIComponent(tenant.id)}`)
    appsCache.set(tenant.id, rows)
    if (detailTenant.value?.id === tenant.id) detailApps.value = rows
  } catch (error) {
    if (detailTenant.value?.id === tenant.id) message.error(error instanceof Error ? error.message : '读取租户应用失败')
  } finally { detailAppsLoading.value = false }
}

// ===== 成员抽屉：复用 /admin/members 租户成员分页端点 =====
const membersOpen = ref(false)
const membersTenant = ref<Tenant | null>(null)
const membersList = ref<TenantMember[]>([])
const membersLoading = ref(false)
const membersCache = new Map<string, TenantMember[]>()

async function openMembers(tenant: Tenant): Promise<void> {
  membersTenant.value = tenant
  membersOpen.value = true
  const cached = membersCache.get(tenant.id)
  if (cached) { membersList.value = cached; return }
  membersList.value = []
  membersLoading.value = true
  try {
    const page = await api<{ items: TenantMember[] }>(`/admin/members?tenant_id=${encodeURIComponent(tenant.id)}&limit=500`)
    membersCache.set(tenant.id, page.items)
    if (membersTenant.value?.id === tenant.id) membersList.value = page.items
  } catch (error) {
    if (membersTenant.value?.id === tenant.id) message.error(error instanceof Error ? error.message : '读取租户成员失败')
  } finally { membersLoading.value = false }
}

// 详情抽屉内点击应用 → 关抽屉并携带 application_id 跳工作台预选
function goToWorkspace(application: TenantApplication): void {
  detailOpen.value = false
  void router.push({ path: PAGE_PATHS.application_workspace, query: { application_id: application.id } })
}

// 租户类型展示文案（平台引导租户固定为「平台自有」）
function kindLabel(tenant: Tenant): string {
  if (tenant.slug === 'platform') return '平台自有'
  return tenant.kind === 'consumer' ? 'ToC 消费租户' : '组织/企业租户'
}

// 行点击下钻；操作列与行内链接用 @click.stop 防冒泡
function rowProps(record: Tenant): Record<string, unknown> {
  return { class: 'cursor-pointer', onClick: () => openDetail(record) }
}

watch(() => props.active, active => {
  if (!active) return
  // 平台壳已预拉租户目录时复用，避免路由激活重复请求 /admin/tenants。
  if (hydrateFromShell()) return
  void loadTenants()
}, { immediate: true })

watch(() => [props.shellCatalogGeneration, props.shellTenants?.length] as const, () => {
  if (props.active) hydrateFromShell()
})
</script>

<template>
  <section class="flex w-full min-w-0 max-w-full flex-col gap-5">
    <AdminListPage
      eyebrow="TENANT DIRECTORY"
      title="租户管理"
      subtitle="管理业务隔离边界。租户停用会阻止旗下应用续期登录会话，并立即影响成员访问。"
      :hint="`共 ${tenants.length} 个租户；点击行查看租户详情与旗下应用，租户标识创建后不可修改。`"
      :columns="columns"
      :data-source="filteredTenants"
      :loading="loading"
      row-key="id"
      :custom-row="rowProps"
      :scroll="{ x: 860, y: 'calc(100vh - 430px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
      empty-emoji="🏢"
      :empty-text="searchText || kindFilter || statusFilter ? '没有匹配的租户' : '暂无租户，可点击新建租户创建隔离空间'"
    >
      <AdminSearchField v-model="searchText" placeholder="搜索租户名称或标识" :submit-on-clear="false" />
      <a-select v-model:value="kindFilter" :options="kindOptions" placeholder="类型" />
      <a-select v-model:value="statusFilter" :options="statusOptions" placeholder="状态" />
      <template #header-extra>
        <a-button type="primary" @click="createTenant">＋ 新建租户</a-button>
      </template>
      <template #actions>
        <a-button :loading="loading" @click="loadTenants">刷新</a-button>
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <div class="flex min-w-0 flex-col gap-0.5">
            <span class="truncate font-medium text-[var(--color-text-primary)]">{{ record.name }}</span>
            <AdminMonoValue :value="record.slug" max-width="180px" />
          </div>
        </template>
        <template v-else-if="column.key === 'kind'">
          <!-- 平台引导租户（slug=platform）是 L1 角色与引导超管的宿主：类型固定、禁删禁切换，显式标注与业务租户区分。 -->
          <a-tooltip v-if="record.slug === 'platform'" title="平台引导租户：L1 角色与引导超管的宿主，类型由系统种子固定，不参与 ToC 注册">
            <a-tag class="border-solid border-[var(--color-brand)] text-[var(--color-brand)]">平台自有</a-tag>
          </a-tooltip>
          <a-tag v-else>{{ record.kind === 'consumer' ? 'ToC 消费' : '组织/企业' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'member_count'">
          <a-button type="link" size="small" class="px-0" @click.stop="openMembers(record)">{{ record.member_count }}</a-button>
        </template>
        <template v-else-if="column.key === 'application_count'">
          <span class="font-mono text-[13px] text-[var(--color-text-secondary)] tabular-nums">{{ record.application_count ?? '—' }}</span>
        </template>
        <template v-else-if="column.key === 'status'"><a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag></template>
        <template v-else-if="column.key === 'actions'"><a-space :size="2" @click.stop>
          <a-button v-if="record.slug !== 'platform'" type="link" size="small" @click="changeKind(record)">{{ record.kind === 'consumer' ? '转为组织租户' : '转为 ToC 消费' }}</a-button>
          <a-button v-if="canManageTenants" type="link" size="small" @click="changeStatus(record)">{{ record.status === 'active' ? '停用' : '启用' }}</a-button>
          <a-button v-if="canManageTenants && record.slug !== 'platform'" type="link" size="small" danger @click="deleteTenant(record)">删除</a-button>
        </a-space></template>
      </template>
    </AdminListPage>

    <!-- 租户详情抽屉：基本信息 + 旗下应用（点击跳工作台预选该应用） -->
    <AdminDetailDrawer v-model:open="detailOpen" :title="detailTenant?.name || ''" :subtitle="detailTenant?.slug || ''">
      <a-descriptions :column="1" size="small" bordered class="mb-4">
        <a-descriptions-item label="类型">{{ detailTenant ? kindLabel(detailTenant) : '' }}</a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="detailTenant?.status === 'active' ? 'green' : 'default'">{{ detailTenant?.status === 'active' ? '启用' : '停用' }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="成员">
          <a-button v-if="detailTenant" type="link" size="small" class="px-0" @click="openMembers(detailTenant)">{{ detailTenant.member_count }} 个成员</a-button>
        </a-descriptions-item>
      </a-descriptions>
      <div class="mb-2 flex items-baseline justify-between gap-2">
        <span class="text-[13px] font-semibold text-[var(--color-text-primary)]">旗下应用（{{ detailApps.length }}）</span>
        <span class="text-xs text-[var(--color-text-muted)]">点击应用前往工作台配置角色与权限</span>
      </div>
      <a-spin :spinning="detailAppsLoading">
        <div v-if="detailApps.length" class="flex flex-col gap-1">
          <button v-for="app in detailApps" :key="app.id" type="button"
            class="flex w-full cursor-pointer items-center gap-2 border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 text-left rounded-[var(--radius-md)] transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
            @click="goToWorkspace(app)">
            <span class="min-w-0 flex-1 truncate text-[13px] text-[var(--color-text-primary)]">{{ app.name }}</span>
            <span class="hidden shrink-0 font-mono text-xs text-[var(--color-text-muted)] sm:inline">{{ app.client_id }}</span>
            <a-tag v-if="app.status === 'disabled'" class="mr-0 shrink-0" color="default">停用</a-tag>
          </button>
        </div>
        <p v-else-if="!detailAppsLoading" class="text-xs text-[var(--color-text-muted)]">该租户下暂无应用</p>
      </a-spin>
    </AdminDetailDrawer>

    <!-- 成员抽屉：展示成员身份与状态（成员/用户两级状态分离） -->
    <AdminDetailDrawer v-model:open="membersOpen" :title="`${membersTenant?.name || ''} · 成员`" :subtitle="membersTenant?.slug || ''" :width="560">
      <a-spin :spinning="membersLoading">
        <div v-if="membersList.length" class="flex flex-col gap-1">
          <div v-for="member in membersList" :key="member.user_id"
            class="flex items-center gap-3 border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-3 py-2 rounded-[var(--radius-md)]">
            <div class="flex min-w-0 flex-1 flex-col">
              <span class="truncate text-[13px] text-[var(--color-text-primary)]">{{ member.display_name || member.email }}</span>
              <span class="truncate font-mono text-xs text-[var(--color-text-muted)]">{{ member.email }}</span>
            </div>
            <a-tag v-if="member.membership_status !== 'active'" class="mr-0 shrink-0" color="default">{{ member.membership_status === 'disabled' ? '成员停用' : '已离职' }}</a-tag>
            <a-tag v-else-if="member.user_status !== 'active'" class="mr-0 shrink-0" color="warning">用户{{ member.user_status === 'locked' ? '已锁定' : '已停用' }}</a-tag>
          </div>
        </div>
        <p v-else-if="!membersLoading" class="text-xs text-[var(--color-text-muted)]">该租户暂无成员</p>
      </a-spin>
    </AdminDetailDrawer>

    <a-modal v-model:open="modalOpen" title="新建租户" ok-text="创建" cancel-text="取消"
      :confirm-loading="saving" @ok="saveTenant">
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <a-form-item label="租户名称" name="name"><a-input v-model:value="form.name" :maxlength="120" /></a-form-item>
        <a-form-item label="租户标识" name="slug"><a-input v-model:value="form.slug" :maxlength="80" placeholder="example-team" /></a-form-item>
        <a-form-item label="租户类型" name="kind"><a-radio-group v-model:value="form.kind"><a-radio value="organization">组织/企业租户</a-radio><a-radio value="consumer">ToC 消费租户</a-radio></a-radio-group></a-form-item>
        <a-alert type="info" show-icon message="ToC 自助注册只允许绑定消费租户。创建组织租户不会开放匿名注册；转换类型前需要关闭租户内所有应用的自助注册。" />
      </a-form>
    </a-modal>
  </section>
</template>
