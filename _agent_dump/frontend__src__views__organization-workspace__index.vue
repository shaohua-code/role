<script setup lang="ts">
// 组织工作台（对齐 user-center-sys department 信息架构）：
// 左树选组织 + 右侧「成员 / 用户组」两个 Tab；组织仍挂租户，用户组仅在组织上下文展示。
// Wave 4 收口：空态强化组织上下文三步引导，并提供前往组织管理创建的出口。
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import { PAGE_PATHS } from '@/router/navigation'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import AdminPathGuide from '@/components/AdminPathGuide.vue'
import OrgTree, { type OrgTreeOrganization } from './components/OrgTree.vue'
import MembersTab from './tabs/MembersTab.vue'
import GroupsTab from './tabs/GroupsTab.vue'

interface TenantOption {
  id: string
  name: string
  status: string
  can_read_organizations?: boolean
}

// 组织上下文三步（空态引导与页头副标题共用口径）。
const MAIN_PATH_STEPS = [
  '在「组织管理」创建组织并挂到租户',
  '在左侧选中组织，在「成员」查看直接挂接的成员',
  '在「用户组」查看租户用户组并管理成员/角色',
] as const

const router = useRouter()

function goOrganizationManagement(): void {
  void router.push(PAGE_PATHS.organizations)
}

const props = withDefaults(defineProps<{
  active: boolean
  apiPrefix?: string
  tenants: TenantOption[]
}>(), {
  apiPrefix: '/admin',
})

const organizations = ref<OrgTreeOrganization[]>([])
const selectedId = ref('')
const loading = ref(false)
let requestSequence = 0

const selectedOrganization = computed(() =>
  organizations.value.find(item => item.id === selectedId.value) || null)

// 默认选中首个组织；列表为空或原选择被删时回退。
function ensureSelection(): void {
  if (!organizations.value.some(item => item.id === selectedId.value)) {
    selectedId.value = organizations.value[0]?.id || ''
  }
}

// 组织目录按可读租户并发拉取后合并；个别租户权限刚被撤销不影响其余目录。
async function loadOrganizations(): Promise<void> {
  const readable = props.tenants.filter(tenant => tenant.can_read_organizations)
  if (!props.active || !readable.length) {
    organizations.value = []
    selectedId.value = ''
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  try {
    const responses = await Promise.all(readable.map(tenant =>
      api<Array<Record<string, unknown>>>(`${props.apiPrefix}/organizations?tenant_id=${encodeURIComponent(tenant.id)}`)
        .catch(() => [] as Array<Record<string, unknown>>)))
    if (sequence !== requestSequence) return
    organizations.value = responses.flatMap(rows => rows.map(row => ({
      id: String(row.id),
      tenant_id: String(row.tenant_id),
      tenant_name: readable.find(tenant => tenant.id === String(row.tenant_id))?.name || '未知租户',
      parent_id: row.parent_id ? String(row.parent_id) : null,
      name: String(row.name),
      key: String(row.key ?? ''),
      status: row.status === 'disabled' ? 'disabled' : 'active',
    })))
    ensureSelection()
  } catch (error) {
    if (sequence !== requestSequence) return
    organizations.value = []
    selectedId.value = ''
    message.error(error instanceof Error ? error.message : '读取组织目录失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function onSelect(organization: OrgTreeOrganization): void {
  selectedId.value = organization.id
}

// 激活时加载；租户字典晚于页面就绪时（平台壳异步拉取）自动补载。
watch(() => props.active, active => {
  if (active) void loadOrganizations()
}, { immediate: true })

watch(() => props.tenants, () => {
  if (props.active) void loadOrganizations()
}, { deep: true })
</script>

<template>
  <section class="flex w-full min-w-0 flex-col lg:min-h-[380px]">
    <AdminPageHeader
      class="shrink-0"
      eyebrow="ORGANIZATION WORKSPACE"
      title="组织工作台"
      subtitle="组织归属租户：① 左侧选择组织；② 在「成员」查看直接挂接的成员；③ 在「用户组」查看租户用户组并管理成员/角色。成员的组织归属在「用户管理」中维护。"
    />
    <!-- UI 检查（P348）修复：窄屏上下堆叠（树在上），lg 及以上保持左右布局。 -->
    <!-- P358：桌面档左右两栏各自内滚、高度撑满视口底部，消除整页滚动。 -->
    <div class="flex w-full min-w-0 flex-col items-stretch gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
      <!-- 窄屏限高：树过长时内部滚动；桌面档两栏等高内滚。 -->
      <OrgTree
        class="max-h-80 w-full shrink-0 overflow-y-auto lg:h-full lg:max-h-none lg:w-64"
        :organizations="organizations"
        :selected-id="selectedId"
        :loading="loading"
        @select="onSelect"
      />
      <div class="min-w-0 flex-1 lg:h-full lg:min-h-0 lg:overflow-y-auto">
        <!-- 无任何组织：给出三步引导 + 创建出口（Wave 4 空态强化）。 -->
        <a-card v-if="!selectedOrganization && !loading && !organizations.length" class="mgmt-data-card h-full" :bordered="false">
          <AdminEmpty emoji="🏛️" description="还没有可查看的组织">
            <div class="flex flex-col items-center gap-4">
              <AdminPathGuide :steps="MAIN_PATH_STEPS" title="创建组织后，按以下三步完成日常管理" />
              <a-button type="primary" @click="goOrganizationManagement">前往组织管理创建</a-button>
            </div>
          </AdminEmpty>
        </a-card>
        <a-card v-else-if="!selectedOrganization" class="mgmt-data-card h-full" :bordered="false">
          <AdminEmpty emoji="👈" description="请先选择左侧组织">
            <AdminPathGuide :steps="MAIN_PATH_STEPS" title="选中组织后" />
          </AdminEmpty>
        </a-card>
        <a-card v-else class="mgmt-data-card h-full" :bordered="false">
          <template #title>
            <span class="inline-flex min-w-0 items-center gap-2">
              <span class="truncate">{{ selectedOrganization.name }}</span>
              <a-tag v-if="selectedOrganization.status === 'disabled'" color="default">已停用</a-tag>
              <a-tag color="default">{{ selectedOrganization.tenant_name }}</a-tag>
            </span>
          </template>
          <a-tabs>
            <a-tab-pane key="members" tab="成员">
              <MembersTab
                :active="active"
                :organization="selectedOrganization"
                :api-prefix="apiPrefix"
              />
            </a-tab-pane>
            <a-tab-pane key="groups" tab="用户组">
              <GroupsTab
                :active="active"
                :organization="selectedOrganization"
                :api-prefix="apiPrefix"
              />
            </a-tab-pane>
          </a-tabs>
        </a-card>
      </div>
    </div>
  </section>
</template>
