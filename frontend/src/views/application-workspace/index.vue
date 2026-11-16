<script setup lang="ts">
// 应用工作台：左树选应用 + 右侧「角色 / 权限编码 / 资源权限」Tab。
// 树顶「新建应用」；节点「更多」也可新建，并承接编辑 / 密钥 / 启停 / 删除。
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import { getCachedCapabilities, TENANT_ADMIN_API_PREFIX } from '@/api/capabilities'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import AdminPathGuide from '@/components/AdminPathGuide.vue'
import AdminMonoValue from '@/components/AdminMonoValue.vue'
import { DownOutlined, InfoCircleOutlined } from '@/plugins/icons'
import AppTree, { type AppMoreAction, type AppTreeApplication } from './components/AppTree.vue'
import CreateApplicationModal from './components/CreateApplicationModal.vue'
import ApplicationMoreHost from './components/ApplicationMoreHost.vue'
import RolesTab from './tabs/RolesTab.vue'
import PermissionsTab from './tabs/PermissionsTab.vue'
import MenuTab from './tabs/MenuTab.vue'

interface TenantOption {
  id: string
  name: string
  status: string
  kind?: 'organization' | 'consumer'
  can_read_applications?: boolean
  can_manage_applications?: boolean
  can_create_applications?: boolean
  can_rotate_application_secret?: boolean
}
interface ApplicationRecord {
  id: string
  tenant_id: string
  name: string
  client_id: string
  permission_namespace: string
  description?: string | null
  trusted?: boolean
  status: 'active' | 'disabled'
  redirect_uris?: string[]
  post_logout_redirect_uris?: string[]
  registration_policy?: 'disabled' | 'open'
  registration_role_id?: string | null
  registration_terms_version?: string | null
  registration_privacy_version?: string | null
  backchannel_logout_uri?: string | null
  can_manage?: boolean
  can_rotate_secret?: boolean
}

// 三步配权主路径：页头副标题与空态引导共用；业务码由应用管理员在工作台登记，不必找 L1。
const MAIN_PATH_STEPS = [
  '在「权限编码」Tab 登记本应用业务码（应用管理员可直接新建）',
  '在「角色」Tab 新建应用角色，打开「应用权限」挂编码 / 资源树 / 数据权限',
  '在角色行「配置成员」把租户成员绑到应用角色（会同时成为该应用的平台成员）',
] as const

// R3 配权路径短版：页头下方编辑部式步骤条的数据源；点击直切对应 Tab
// （第三步「配置成员」是角色行内动作，同样落在「角色」Tab）。
const PATH_STEPS = [
  { step: '01', tab: '权限编码', action: '登记业务码', target: 'permissions' },
  { step: '02', tab: '应用角色', action: '配置应用权限', target: 'roles' },
  { step: '03', tab: '配置成员', action: '绑定租户成员', target: 'roles' },
] as const

const router = useRouter()
const createOpen = ref(false)
const createTenantId = ref('')
const moreAction = ref<AppMoreAction | ''>('')
const moreApplicationId = ref('')

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

// P404：仅 L1 / L3 可新建应用；L2 即使能管已钉住的应用也不能创建。
// 平台模式 /admin/tenants 不带 can_create_applications，用 consoleMode 判定，避免按钮被藏掉。
const canCreateApplication = computed(() => {
  if (props.consoleMode === 'platform' || getCachedCapabilities()?.platform_admin) return true
  return props.tenants.some(tenant => tenant.can_create_applications === true)
})

const emit = defineEmits<{ changed: [] }>()

const creatableTenants = computed(() => props.tenants.filter(tenant => {
  if (tenant.status !== 'active') return false
  if (props.consoleMode === 'platform' || getCachedCapabilities()?.platform_admin) return true
  return tenant.can_create_applications === true
}))

const treeTenants = computed(() => props.tenants
  .filter(tenant => tenant.can_read_applications !== false)
  .map(tenant => ({
    id: tenant.id,
    name: tenant.name,
    canCreate: creatableTenants.value.some(item => item.id === tenant.id),
  })))

function openCreate(tenantId?: string): void {
  createTenantId.value = tenantId || creatableTenants.value[0]?.id || ''
  createOpen.value = true
}

async function onApplicationCreated(payload: { id: string }): Promise<void> {
  emit('changed')
  await loadApplications()
  selectedId.value = payload.id
}

function onApplicationMore(payload: { id: string; action: AppMoreAction }): void {
  selectedId.value = payload.id
  moreApplicationId.value = payload.id
  moreAction.value = payload.action
}

function onSettingsChanged(): void {
  emit('changed')
  void loadApplications()
}

function onApplicationDeleted(): void {
  emit('changed')
  selectedId.value = ''
  moreApplicationId.value = ''
  void loadApplications()
}

const applications = ref<ApplicationRecord[]>([])
const selectedId = ref('')
const loading = ref(false)
let requestSequence = 0
let hydratedCatalogGeneration = -1

// ===== P397/D4 应用概览计数：各 Tab 加载后上报，以小徽标并入 Tab 标签（不再单设统计条与 Tab 重名） =====
const tabStats = ref<{ roles: number | null, permissions: number | null, resources: number | null }>({
  roles: null, permissions: null, resources: null,
})

// R3：Tab 激活键受控——页头配权路径条要能直切 Tab，徽章激活态也需要读取当前键
const activeTab = ref<'roles' | 'permissions' | 'menus'>('roles')

function onTabStats(key: 'roles' | 'permissions' | 'resources', count: number): void {
  tabStats.value[key] = count
}

const selectedApplication = computed(() =>
  applications.value.find(item => item.id === selectedId.value) || null)

const moreApplication = computed(() =>
  applications.value.find(item => item.id === moreApplicationId.value) || null)

// 左树展示用：补齐租户分组名（租户字典可能在应用之后就绪，computed 自动跟随）。
const treeApplications = computed<AppTreeApplication[]>(() => applications.value.map(item => ({
  id: item.id,
  tenant_id: item.tenant_id,
  name: item.name,
  client_id: item.client_id,
  status: item.status,
  trusted: item.trusted === true,
  tenant_name: props.tenants.find(tenant => tenant.id === item.tenant_id)?.name || '未知租户',
})))

// 把壳层字典行换算成工作台需要的字段，避免对 Row 的不确定类型直接断言。
function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(item => String(item)) : []
}

function toApplicationRecords(rows: Array<Record<string, unknown>>): ApplicationRecord[] {
  return rows.map(row => ({
    id: String(row.id),
    tenant_id: String(row.tenant_id),
    name: String(row.name),
    client_id: String(row.client_id ?? ''),
    permission_namespace: String(row.permission_namespace ?? ''),
    description: typeof row.description === 'string' ? row.description : null,
    trusted: row.trusted === true,
    status: row.status === 'disabled' ? 'disabled' : 'active',
    redirect_uris: asStringArray(row.redirect_uris),
    post_logout_redirect_uris: asStringArray(row.post_logout_redirect_uris),
    registration_policy: row.registration_policy === 'open' ? 'open' : 'disabled',
    registration_role_id: row.registration_role_id ? String(row.registration_role_id) : null,
    registration_terms_version: typeof row.registration_terms_version === 'string' ? row.registration_terms_version : null,
    registration_privacy_version: typeof row.registration_privacy_version === 'string' ? row.registration_privacy_version : null,
    backchannel_logout_uri: typeof row.backchannel_logout_uri === 'string' ? row.backchannel_logout_uri : null,
    can_manage: row.can_manage === true,
    can_rotate_secret: row.can_rotate_secret === true,
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
        api<Array<Record<string, unknown>>>(`${TENANT_ADMIN_API_PREFIX}/applications?tenant_id=${encodeURIComponent(tenant.id)}`).catch(() => [] as Array<Record<string, unknown>>),
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
    <!-- R3：副标题三步长文案已升格为下方可点击路径条，页头不再藏 tooltip -->
    <AdminPageHeader
      class="shrink-0"
      eyebrow="APPLICATION WORKSPACE"
      title="应用工作台"
    />
    <!-- R3 编辑部式配权路径：大编号 + Tab 名 + 动作说明，顶部 hairline 锚定；
         步骤可点击直切对应 Tab，功能与视觉合一（本页的记忆点） -->
    <div class="mb-4 flex w-full min-w-0 flex-wrap items-center gap-x-1 gap-y-2 border-t border-[var(--color-border)] pt-3 md:mb-5">
      <template v-for="(step, index) in PATH_STEPS" :key="`${step.step}-${step.tab}`">
        <button
          type="button"
          class="group flex cursor-pointer items-center gap-2.5 rounded-[var(--radius-sm)] px-2 py-1.5 transition-colors hover:bg-[var(--color-bg-subtle)] focus:bg-[var(--color-bg-subtle)] focus:outline-none"
          @click="activeTab = step.target"
        >
          <span class="font-mono text-base font-semibold leading-none text-[var(--color-text-muted)] transition-colors tabular-nums group-hover:text-[var(--color-text-secondary)]">{{ step.step }}</span>
          <span class="flex flex-col items-start gap-0.5 leading-tight">
            <span class="text-xs font-semibold text-[var(--color-text-primary)]">{{ step.tab }}</span>
            <span class="text-[11px] text-[var(--color-text-muted)]">{{ step.action }}</span>
          </span>
        </button>
        <span v-if="index < PATH_STEPS.length - 1" class="px-1 text-xs text-[var(--color-text-muted)]" aria-hidden="true">→</span>
      </template>
      <!-- 路径条右侧补权限口径微注，替代原卡内信息条的部分职责 -->
      <span class="ml-auto hidden items-center gap-1.5 pl-4 text-[11px] text-[var(--color-text-muted)] xl:inline-flex">
        <InfoCircleOutlined aria-hidden="true" />
        权限码管显隐 · 鉴权看角色并集 · 资源树管业务端
      </span>
    </div>
    <!-- Wave 4/收口：窄屏上下堆叠（树在上），lg 及以上保持左右布局（UI 检查 P348 修复）。 -->
    <!-- P358：桌面档左右两栏各自内滚、高度撑满视口底部，消除整页滚动。
         R2 高度链：section 已被壳层拉伸为弹性列，行在此 lg:flex-1 吃掉剩余高度，
         两栏才能以 h-full 真正撑到视口底，消除短内容下的页面死白。 -->
    <div class="flex w-full min-w-0 flex-col items-stretch gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
      <!-- 窄屏限高：树过长时内部滚动；桌面档两栏等高内滚。 -->
      <AppTree
        class="max-h-80 w-full shrink-0 overflow-y-auto lg:h-full lg:max-h-none lg:w-64"
        :applications="treeApplications"
        :tenants="treeTenants"
        :can-create="canCreateApplication"
        :selected-id="selectedId"
        :loading="loading"
        @select="onSelect"
        @create="openCreate"
        @more="onApplicationMore"
      />
      <div class="flex min-w-0 flex-1 flex-col lg:h-full lg:min-h-0 lg:overflow-y-auto">
        <!-- 无任何应用：给出三步主路径 + 创建出口（Wave 4 空态强化）；R3 拉伸卡内垂直居中 -->
        <a-card v-if="!selectedApplication && !loading && !applications.length" class="mgmt-data-card lg:flex-1" :bordered="false">
          <div class="flex flex-1 items-center justify-center py-10">
            <AdminEmpty emoji="🧩" description="还没有可管理的应用">
              <div class="flex flex-col items-center gap-4">
                <AdminPathGuide :steps="MAIN_PATH_STEPS" title="创建应用后，按以下三步完成日常配权" />
                <a-button v-if="canCreateApplication" type="primary" @click="openCreate()">新建应用</a-button>
                <p v-else class="m-0 text-sm text-[var(--color-text-muted)]">请联系租户管理员创建应用，并任命你为应用管理员。</p>
              </div>
            </AdminEmpty>
          </div>
        </a-card>
        <a-card v-else-if="!selectedApplication" class="mgmt-data-card lg:flex-1" :bordered="false">
          <div class="flex flex-1 items-center justify-center py-10">
            <AdminEmpty emoji="👈" description="请先选择左侧应用">
              <AdminPathGuide :steps="MAIN_PATH_STEPS" title="选中应用后" />
            </AdminEmpty>
          </div>
        </a-card>
        <!-- ws-entity-card：实体卡头标记（style.css D8）——subtle 头部带 + monogram 组成应用身份区 -->
        <a-card v-else class="mgmt-data-card ws-entity-card lg:flex-1" :bordered="false">
          <template #title>
            <!-- 应用身份卡头：石墨 monogram + 名称/状态 + 元信息行（client_id 可复制、描述截断），
                 让详情卡有「实体感」而非一行裸文字（轻奢极简：层次靠排版与灰阶，不加彩色装饰）。 -->
            <div class="flex min-w-0 items-center gap-3 py-1">
              <!-- monogram：实底墨色方块 + 反白首字母；dark 主题自动翻为白底墨字，主题安全且分量足 -->
              <span
                class="flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-text-primary)] text-lg font-semibold text-[var(--color-bg-elevated)]"
                aria-hidden="true"
              >{{ (selectedApplication.name || '?').trim().charAt(0).toUpperCase() }}</span>
              <span class="flex min-w-0 flex-col gap-0.5">
                <span class="inline-flex min-w-0 items-center gap-2">
                  <span class="truncate text-base font-semibold text-[var(--color-text-primary)]">{{ selectedApplication.name }}</span>
                  <a-tag v-if="selectedApplication.status === 'disabled'" class="mr-0 shrink-0" color="default">已停用</a-tag>
                  <!-- 受信应用标识：此前仅存在于左树菜单，详情头补齐同一事实 -->
                  <a-tag v-if="selectedApplication.trusted" class="mr-0 shrink-0" color="default">受信</a-tag>
                </span>
                <span class="inline-flex min-w-0 items-center gap-2">
                  <!-- U29 沿用：client_id 等宽灰标，悬停一键复制 -->
                  <AdminMonoValue :value="selectedApplication.client_id" max-width="180px" />
                  <template v-if="selectedApplication.description">
                    <span class="shrink-0 text-[var(--color-text-muted)]">·</span>
                    <span class="hidden min-w-0 truncate text-xs text-[var(--color-text-muted)] md:inline" :title="selectedApplication.description ?? ''">{{ selectedApplication.description }}</span>
                  </template>
                </span>
              </span>
            </div>
          </template>
          <!-- R3 卡头快捷动作：编辑资料 / 更多，动作不再只藏在左树省略号里；
               口径与左树菜单完全同源（onApplicationMore），窄屏隐藏防 375 溢出（P349 惯例） -->
          <template #extra>
            <div class="hidden shrink-0 items-center gap-1 sm:flex">
              <a-button size="small" @click="onApplicationMore({ id: selectedApplication.id, action: 'edit' })">编辑资料</a-button>
              <a-dropdown :trigger="['click']">
                <a-button size="small">
                  更多
                  <DownOutlined class="text-[10px]" />
                </a-button>
                <template #overlay>
                  <a-menu>
                    <a-menu-item key="rotateSecret" @click="onApplicationMore({ id: selectedApplication.id, action: 'rotateSecret' })">轮换密钥</a-menu-item>
                    <a-menu-item key="trust" @click="onApplicationMore({ id: selectedApplication.id, action: 'trust' })">{{ selectedApplication.trusted ? '撤销信任' : '设为受信' }}</a-menu-item>
                    <a-menu-item key="status" @click="onApplicationMore({ id: selectedApplication.id, action: 'status' })">{{ selectedApplication.status === 'active' ? '停用应用' : '启用应用' }}</a-menu-item>
                    <a-menu-item key="delete" danger @click="onApplicationMore({ id: selectedApplication.id, action: 'delete' })">删除应用</a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>
          </template>
          <!-- D4 重设计：概览计数并入 Tab 标签（小型徽标），消除「统计条胶囊与 Tab 重名」的双层混淆 -->
          <!-- R3：Tab 激活键受控（配权路径条直切）；徽章激活态反白墨底，当前 Tab 的计数一眼可辨 -->
          <a-tabs v-model:active-key="activeTab" class="ws-tabs">
            <a-tab-pane key="roles">
              <template #tab>
                <span class="inline-flex items-center gap-1.5">
                  角色
                  <span v-if="tabStats.roles != null"
                    class="inline-flex min-w-5 justify-center rounded-full px-1.5 font-mono text-[11px] leading-4 tabular-nums"
                    :class="activeTab === 'roles'
                      ? 'bg-[var(--color-text-primary)] text-[var(--color-bg-elevated)]'
                      : 'bg-[var(--color-bg-subtle)] text-[var(--color-text-secondary)]'"
                  >{{ tabStats.roles }}</span>
                </span>
              </template>
              <RolesTab
                :active="active"
                :application="selectedApplication"
                :api-prefix="apiPrefix"
                @changed="emit('changed')"
                @stats="count => onTabStats('roles', count)"
              />
            </a-tab-pane>
            <a-tab-pane key="permissions">
              <template #tab>
                <span class="inline-flex items-center gap-1.5">
                  权限编码
                  <span v-if="tabStats.permissions != null"
                    class="inline-flex min-w-5 justify-center rounded-full px-1.5 font-mono text-[11px] leading-4 tabular-nums"
                    :class="activeTab === 'permissions'
                      ? 'bg-[var(--color-text-primary)] text-[var(--color-bg-elevated)]'
                      : 'bg-[var(--color-bg-subtle)] text-[var(--color-text-secondary)]'"
                  >{{ tabStats.permissions }}</span>
                </span>
              </template>
              <PermissionsTab
                :active="active"
                :application="selectedApplication"
                :api-prefix="apiPrefix"
                @changed="emit('changed')"
                @stats="count => onTabStats('permissions', count)"
              />
            </a-tab-pane>
            <!-- P357 资源权限：应用显式资源树（菜单/按钮/数据规则），替代 P356 权限码推导视图 -->
            <a-tab-pane key="menus">
              <template #tab>
                <span class="inline-flex items-center gap-1.5">
                  资源权限
                  <span v-if="tabStats.resources != null"
                    class="inline-flex min-w-5 justify-center rounded-full px-1.5 font-mono text-[11px] leading-4 tabular-nums"
                    :class="activeTab === 'menus'
                      ? 'bg-[var(--color-text-primary)] text-[var(--color-bg-elevated)]'
                      : 'bg-[var(--color-bg-subtle)] text-[var(--color-text-secondary)]'"
                  >{{ tabStats.resources }}</span>
                </span>
              </template>
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
    <CreateApplicationModal
      v-model:open="createOpen"
      :api-prefix="apiPrefix"
      :tenants="creatableTenants"
      :preset-tenant-id="createTenantId"
      @created="onApplicationCreated"
    />
    <ApplicationMoreHost
      v-model:action="moreAction"
      :application="moreApplication"
      :tenants="tenants"
      :api-prefix="apiPrefix"
      @changed="onSettingsChanged"
      @deleted="onApplicationDeleted"
    />
  </section>
</template>

