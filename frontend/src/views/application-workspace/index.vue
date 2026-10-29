<script setup lang="ts">
// 应用工作台（对齐 user-center-sys appAndRoleManagement 信息架构）：
// 左树选应用 + 右侧「角色 / 权限编码」两个 Tab；未选应用时展示中文空态与配权三步主路径。
// 列表页入口在侧栏「高级管理」组（默认折叠）；本页是日常配权主入口。
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import { getCachedCapabilities } from '@/api/capabilities'
import { PAGE_PATHS } from '@/router/navigation'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import AdminPathGuide from '@/components/AdminPathGuide.vue'
import AppTree, { type AppTreeApplication } from './components/AppTree.vue'
import RolesTab from './tabs/RolesTab.vue'
import PermissionsTab from './tabs/PermissionsTab.vue'
import MenuTab from './tabs/MenuTab.vue'

interface TenantOption {
  id: string
  name: string
  status: string
  can_read_applications?: boolean
  can_manage_applications?: boolean
}
interface ApplicationRecord {
  id: string
  tenant_id: string
  name: string
  client_id: string
  permission_namespace: string
  status: 'active' | 'disabled'
  can_manage?: boolean
}

// 三步配权主路径：页头副标题与空态引导共用；业务码由应用管理员在工作台登记，不必找 L1。
const MAIN_PATH_STEPS = [
  '在「权限编码」Tab 登记本应用业务码（应用管理员可直接新建）',
  '在「角色」Tab 为角色挂权限编码',
  '到「用户管理」为用户多选角色（生效权限 = 角色并集）',
] as const

const router = useRouter()

const props = withDefaults(defineProps<{
  active: boolean
  consoleMode: 'platform' | 'tenant'
  apiPrefix?: string
  tenants: TenantOption[]
  // 平台模式复用壳层应用字典避免重复请求；租户模式自行按租户拉取。
  shellApplications?: Array<Record<string, unknown>> | null
  shellCatalogGeneration?: number
}>(), {
  apiPrefix: '/admin',
  shellApplications: null,
  shellCatalogGeneration: -1,
})

// L1 或持 app.manage 的租户/应用管理员可去应用管理创建；否则引导联系租户管理员，避免空态死路。
const canCreateApplication = computed(() => {
  if (getCachedCapabilities()?.platform_admin) return true
  return props.tenants.some(tenant => tenant.can_manage_applications === true)
})

function goApplicationManagement(): void {
  void router.push(PAGE_PATHS.applications)
}

const emit = defineEmits<{ changed: [] }>()

const applications = ref<ApplicationRecord[]>([])
const selectedId = ref('')
const loading = ref(false)
let requestSequence = 0
let hydratedCatalogGeneration = -1

// ===== P397 应用概览统计条：三个 Tab 加载后各自上报计数，父级聚合展示 =====
const tabStats = ref<{ roles: number | null, permissions: number | null, resources: number | null }>({
  roles: null, permissions: null, resources: null,
})

function onTabStats(key: 'roles' | 'permissions' | 'resources', count: number): void {
  tabStats.value[key] = count
}

const overviewItems = computed(() => [
  { key: 'roles', label: '角色', count: tabStats.value.roles },
  { key: 'permissions', label: '权限码', count: tabStats.value.permissions },
  { key: 'resources', label: '资源', count: tabStats.value.resources },
] as const)

const selectedApplication = computed(() =>
  applications.value.find(item => item.id === selectedId.value) || null)

// 左树展示用：补齐租户分组名（租户字典可能在应用之后就绪，computed 自动跟随）。
const treeApplications = computed<AppTreeApplication[]>(() => applications.value.map(item => ({
  id: item.id,
  tenant_id: item.tenant_id,
  name: item.name,
  client_id: item.client_id,
  status: item.status,
  tenant_name: props.tenants.find(tenant => tenant.id === item.tenant_id)?.name || '未知租户',
})))

// 把壳层字典行换算成工作台需要的字段，避免对 Row 的不确定类型直接断言。
function toApplicationRecords(rows: Array<Record<string, unknown>>): ApplicationRecord[] {
  return rows.map(row => ({
    id: String(row.id),
    tenant_id: String(row.tenant_id),
    name: String(row.name),
    client_id: String(row.client_id ?? ''),
    permission_namespace: String(row.permission_namespace ?? ''),
    status: row.status === 'disabled' ? 'disabled' : 'active',
    can_manage: row.can_manage === true,
  }))
}

// 平台壳字典代次变化时复用，避免路由激活重复请求 /admin/applications。
function hydrateFromShell(): boolean {
  if (props.apiPrefix !== '/admin' || props.shellApplications == null) return false
  const generation = props.shellCatalogGeneration ?? -1
  if (generation < 0 || generation === hydratedCatalogGeneration) return false
  applications.value = toApplicationRecords(props.shellApplications)
  hydratedCatalogGeneration = generation
  ensureSelection()
  return true
}

// 默认选中第一个应用（对齐蓝图）；列表为空或原选择被删时回退。
// P397 支持 ?application_id= 深链预选（租户详情抽屉等入口跳转）。
function ensureSelection(): void {
  const wanted = String(router.currentRoute.value.query.application_id || '')
  if (wanted && applications.value.some(item => item.id === wanted)) {
    selectedId.value = wanted
    return
  }
  if (!applications.value.some(item => item.id === selectedId.value)) {
    selectedId.value = applications.value[0]?.id || ''
  }
}

async function loadApplications(): Promise<void> {
  const sequence = ++requestSequence
  loading.value = true
  try {
    let result: ApplicationRecord[]
    if (props.apiPrefix === '/admin') {
      result = toApplicationRecords(await api<Array<Record<string, unknown>>>('/admin/applications'))
    } else {
      // 租户模式：逐个可读租户请求并合并；个别租户权限刚被撤销不影响其它目录。
      const readable = props.tenants.filter(tenant => tenant.can_read_applications)
      const responses = await Promise.all(readable.map(tenant =>
        api<Array<Record<string, unknown>>>(`/tenant-admin/applications?tenant_id=${encodeURIComponent(tenant.id)}`).catch(() => [] as Array<Record<string, unknown>>),
      ))
      result = responses.flatMap(rows => toApplicationRecords(rows))
    }
    if (sequence !== requestSequence) return
    applications.value = result
    ensureSelection()
  } catch (error) {
    if (sequence !== requestSequence) return
    applications.value = []
    selectedId.value = ''
    message.error(error instanceof Error ? error.message : '读取应用列表失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function onSelect(application: AppTreeApplication): void {
  selectedId.value = application.id
}

// 切换应用后清空概览计数，等各 Tab 重新上报
watch(selectedId, () => {
  tabStats.value = { roles: null, permissions: null, resources: null }
})

// 停留本页时路由 query 深链变化（如再次从租户详情跳转）→ 跟随预选
watch(() => router.currentRoute.value.query.application_id, id => {
  if (!props.active || !id) return
  const wanted = String(id)
  if (applications.value.some(item => item.id === wanted)) selectedId.value = wanted
})

watch(() => props.active, active => {
  if (!active) return
  if (hydrateFromShell()) return
  void loadApplications()
}, { immediate: true })

watch(() => [props.shellCatalogGeneration, props.shellApplications?.length] as const, () => {
  if (props.active) hydrateFromShell()
})
</script>

<template>
  <section class="flex w-full min-w-0 flex-col lg:min-h-[380px]">
    <AdminPageHeader
      class="shrink-0"
      eyebrow="APPLICATION WORKSPACE"
      title="应用工作台"
      subtitle="配权三步：①「权限编码」登记业务码（应用管理员可新建）→ ②「角色」挂码 → ③「用户管理」多选角色（并集生效）"
    />
    <!-- Wave 4/收口：窄屏上下堆叠（树在上），lg 及以上保持左右布局（UI 检查 P348 修复）。 -->
    <!-- P358：桌面档左右两栏各自内滚、高度撑满视口底部，消除整页滚动。 -->
    <div class="flex w-full min-w-0 flex-col items-stretch gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
      <!-- 窄屏限高：树过长时内部滚动；桌面档两栏等高内滚。 -->
      <AppTree
        class="max-h-80 w-full shrink-0 overflow-y-auto lg:h-full lg:max-h-none lg:w-64"
        :applications="treeApplications"
        :selected-id="selectedId"
        :loading="loading"
        @select="onSelect"
      />
      <div class="min-w-0 flex-1 lg:h-full lg:min-h-0 lg:overflow-y-auto">
        <!-- 无任何应用：给出三步主路径 + 创建出口（Wave 4 空态强化）。 -->
        <a-card v-if="!selectedApplication && !loading && !applications.length" class="mgmt-data-card" :bordered="false">
          <AdminEmpty emoji="🧩" description="还没有可管理的应用">
            <div class="flex flex-col items-center gap-4">
              <AdminPathGuide :steps="MAIN_PATH_STEPS" title="创建应用后，按以下三步完成日常配权" />
              <a-button v-if="canCreateApplication" type="primary" @click="goApplicationManagement">前往应用管理创建</a-button>
              <p v-else class="m-0 text-sm text-[var(--color-text-muted)]">请联系租户管理员创建应用，并任命你为应用管理员。</p>
            </div>
          </AdminEmpty>
        </a-card>
        <a-card v-else-if="!selectedApplication" class="mgmt-data-card" :bordered="false">
          <AdminEmpty emoji="👈" description="请先选择左侧应用">
            <AdminPathGuide :steps="MAIN_PATH_STEPS" title="选中应用后" />
          </AdminEmpty>
        </a-card>
        <a-card v-else class="mgmt-data-card" :bordered="false">
          <template #title>
            <span class="inline-flex min-w-0 items-center gap-2">
              <span class="truncate">{{ selectedApplication.name }}</span>
              <a-tag v-if="selectedApplication.status === 'disabled'" color="default">已停用</a-tag>
            </span>
          </template>
          <!-- P397 应用概览统计条：角色 / 权限码 / 资源 三项计数，由各 Tab 加载后上报 -->
          <div class="mb-3 flex flex-wrap items-center gap-2">
            <span class="text-xs text-[var(--color-text-muted)]">应用概览</span>
            <span v-for="item in overviewItems" :key="item.key"
              class="inline-flex items-center gap-1.5 border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-2.5 py-0.5 rounded-full text-xs text-[var(--color-text-secondary)]">
              {{ item.label }}
              <span class="font-mono font-medium text-[var(--color-text-primary)] tabular-nums">{{ item.count ?? '—' }}</span>
            </span>
          </div>
          <!-- 提示降噪 P399：两层权限规则全文只保留这一处弱化小字，Tab 内不再重复横幅 -->
          <p class="mb-3 text-xs text-[var(--color-text-muted)]">
            权限码管管理台菜单/按钮显隐 · 接口鉴权看角色（多角色并集） · 资源树只管业务端菜单/按钮
          </p>
        <a-tabs>
            <a-tab-pane key="roles" tab="角色">
              <RolesTab
                :active="active"
                :application="selectedApplication"
                :api-prefix="apiPrefix"
                @changed="emit('changed')"
                @stats="count => onTabStats('roles', count)"
              />
            </a-tab-pane>
            <a-tab-pane key="permissions" tab="权限编码">
              <PermissionsTab
                :active="active"
                :application="selectedApplication"
                :api-prefix="apiPrefix"
                @changed="emit('changed')"
                @stats="count => onTabStats('permissions', count)"
              />
            </a-tab-pane>
            <!-- P357 资源权限：应用显式资源树（菜单/按钮/数据规则），替代 P356 权限码推导视图 -->
            <a-tab-pane key="menus" tab="资源权限">
              <MenuTab
                :active="active"
                :application="selectedApplication"
                :api-prefix="apiPrefix"
                @changed="emit('changed')"
                @stats="count => onTabStats('resources', count)"
              />
            </a-tab-pane>
          </a-tabs>
        </a-card>
      </div>
    </div>
  </section>
</template>

