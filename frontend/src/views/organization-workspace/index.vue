<script setup lang="ts">
// 组织工作台：左树选组织 + 右侧「成员 / 用户组」Tab。
// 树顶「新建组织」；节点「更多」也可新建下级，并承接负责人 / 启停 / 删除。
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import { getCachedCapabilities } from '@/api/capabilities'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import AdminPathGuide from '@/components/AdminPathGuide.vue'
import OrgTree, { type OrgMoreAction, type OrgTreeOrganization } from './components/OrgTree.vue'
import CreateOrganizationModal from './components/CreateOrganizationModal.vue'
import OrganizationMoreHost from './components/OrganizationMoreHost.vue'
import MembersTab from './tabs/MembersTab.vue'
import GroupsTab from './tabs/GroupsTab.vue'

interface TenantOption {
  id: string
  name: string
  status: string
  slug?: string
  can_read_organizations?: boolean
  can_manage_organizations?: boolean
}

const MAIN_PATH_STEPS = [
  '在左树顶部点「新建组织」，或在节点「更多」里新建下级',
  '在左侧选中组织，在「成员」查看直接挂接的成员',
  '在「用户组」查看租户用户组并管理成员/角色',
] as const

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
const createOpen = ref(false)
const createTenantId = ref('')
const createParentId = ref('')
const moreAction = ref<OrgMoreAction | ''>('')
const moreOrganizationId = ref('')
let requestSequence = 0

const selectedOrganization = computed(() =>
  organizations.value.find(item => item.id === selectedId.value) || null)

const moreOrganization = computed(() =>
  organizations.value.find(item => item.id === moreOrganizationId.value) || null)

const readableTenants = computed(() => props.tenants.filter(tenant =>
  tenant.slug !== 'platform' && tenant.can_read_organizations === true))

const creatableTenants = computed(() => props.tenants.filter(tenant => {
  if (tenant.slug === 'platform' || tenant.status !== 'active') return false
  if (getCachedCapabilities()?.platform_admin) return true
  return tenant.can_manage_organizations === true
}))

const canCreateOrganization = computed(() => creatableTenants.value.length > 0)

const treeTenants = computed(() => readableTenants.value.map(tenant => ({
  id: tenant.id,
  name: tenant.name,
  canCreate: creatableTenants.value.some(item => item.id === tenant.id),
})))

function ensureSelection(): void {
  if (!organizations.value.some(item => item.id === selectedId.value)) {
    selectedId.value = organizations.value[0]?.id || ''
  }
}

async function loadOrganizations(): Promise<void> {
  const readable = readableTenants.value
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
      owner_user_id: row.owner_user_id ? String(row.owner_user_id) : null,
      owner_name: typeof row.owner_name === 'string' ? row.owner_name : null,
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

function onOrganizationMore(payload: { id: string; action: OrgMoreAction }): void {
  selectedId.value = payload.id
  moreOrganizationId.value = payload.id
  moreAction.value = payload.action
}

function openCreate(payload?: { tenantId: string; parentId?: string }): void {
  createTenantId.value = payload?.tenantId || creatableTenants.value[0]?.id || ''
  createParentId.value = payload?.parentId || ''
  createOpen.value = true
}

async function onOrganizationCreated(payload: { id: string }): Promise<void> {
  await loadOrganizations()
  selectedId.value = payload.id
}

function onSettingsChanged(): void {
  void loadOrganizations()
}

function onOrganizationDeleted(): void {
  selectedId.value = ''
  moreOrganizationId.value = ''
  void loadOrganizations()
}

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
      subtitle="组织归属租户：① 左侧选择或新建组织；② 在「成员」查看直接挂接的成员；③ 在「用户组」查看租户用户组。启停与负责人在「设置」。"
    />
    <div class="flex w-full min-w-0 flex-col items-stretch gap-4 lg:min-h-0 lg:flex-1 lg:flex-row">
      <OrgTree
        class="max-h-80 w-full shrink-0 overflow-y-auto lg:h-full lg:max-h-none lg:w-64"
        :organizations="organizations"
        :tenants="treeTenants"
        :selected-id="selectedId"
        :loading="loading"
        @select="onSelect"
        @create="openCreate"
        @more="onOrganizationMore"
      />
      <div class="min-w-0 flex-1 lg:h-full lg:min-h-0 lg:overflow-y-auto">
        <a-card v-if="!selectedOrganization && !loading && !organizations.length" class="mgmt-data-card h-full" :bordered="false">
          <AdminEmpty emoji="🏛️" description="还没有可查看的组织">
            <div class="flex flex-col items-center gap-4">
              <AdminPathGuide :steps="MAIN_PATH_STEPS" title="创建组织后，按以下三步完成日常管理" />
              <a-button v-if="canCreateOrganization" type="primary" @click="openCreate()">新建组织</a-button>
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
    <CreateOrganizationModal
      v-model:open="createOpen"
      :api-prefix="apiPrefix"
      :tenants="creatableTenants"
      :organizations="organizations"
      :preset-tenant-id="createTenantId"
      :preset-parent-id="createParentId"
      @created="onOrganizationCreated"
    />
    <OrganizationMoreHost
      v-model:action="moreAction"
      :organization="moreOrganization"
      :tenants="tenants"
      :api-prefix="apiPrefix"
      @changed="onSettingsChanged"
      @deleted="onOrganizationDeleted"
    />
  </section>
</template>
