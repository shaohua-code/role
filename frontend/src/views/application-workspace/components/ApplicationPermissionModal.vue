<script setup lang="ts">
// 应用角色「应用权限」抽屉：资源权限（挂码 + 资源树）与数据权限（原数据范围）收在同一处。
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import { asPagedList } from '@/utils/paged'
import RolePermissionGrantModal from '@/components/RolePermissionGrantModal.vue'
import RoleResourceGrantModal from './RoleResourceGrantModal.vue'

interface PermissionRecord {
  id: string
  code: string
  description?: string | null
  status: 'active' | 'disabled'
}
interface PermissionGrant {
  permission_id: string
  code?: string
  description?: string | null
  resource_id: string | null
}
interface DataScopePolicy {
  permission_id: string
  scope_type: string
  organization_ids: string[]
}
interface DataScopeEntry {
  permission_id: string
  permission_code: string
  permission_description: string
  scope_type: string
  organization_ids: string[]
}

const props = withDefaults(defineProps<{
  applicationId?: string
  tenantId?: string
  roleId?: string
  roleName?: string
  roleNamespace?: string
  catalogPath?: string
  grantsPath?: string
  canManage?: boolean
}>(), {
  applicationId: '',
  tenantId: '',
  roleId: '',
  roleName: '',
  roleNamespace: '',
  catalogPath: '',
  grantsPath: '',
  canManage: false,
})

const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>('open', { default: false })

const activePane = ref<'resource' | 'data'>('resource')
const dataScopeEntries = ref<DataScopeEntry[]>([])
const dataScopeOrganizationOptions = ref<{ label: string; value: string }[]>([])
const loadingDataScopes = ref(false)
const savingDataScopes = ref(false)

const DATA_SCOPE_OPTIONS = [
  { value: 'tenant', label: '当前租户全部数据' },
  { value: 'self', label: '仅本人数据' },
  { value: 'organization', label: '所属组织' },
  { value: 'organization_tree', label: '所属组织及下级' },
  { value: 'selected_organizations', label: '指定组织' },
]
const grantReady = computed(() => Boolean(props.catalogPath && props.grantsPath && props.roleId))

async function loadDataScopes(): Promise<void> {
  if (!props.applicationId || !props.roleId || !props.tenantId) {
    dataScopeEntries.value = []
    return
  }
  loadingDataScopes.value = true
  try {
    const catalogPath = props.catalogPath
      || `/tenant-admin/applications/${props.applicationId}/permissions?role_id=${encodeURIComponent(props.roleId)}&include_management=true`
    const grantsPath = props.grantsPath
      || `/tenant-admin/applications/${props.applicationId}/roles/${props.roleId}/permissions`
    const [catalog, grants, organizations, configured] = await Promise.all([
      api<PermissionRecord[] | { items: PermissionRecord[] }>(catalogPath).then(result => asPagedList(result).items),
      api<PermissionGrant[]>(grantsPath),
      api<{ id: string; key: string; name: string; status: string }[]>(
        `/admin/organizations?tenant_id=${encodeURIComponent(props.tenantId)}`,
      ),
      api<{ permission_id: string; scope_type: string; organization_ids: string[] }[]>(
        `/admin/roles/${props.roleId}/data-scopes`,
      ),
    ])
    dataScopeOrganizationOptions.value = organizations
      .filter(organization => organization.status === 'active')
      .map(organization => ({ label: `${organization.name} (${organization.key})`, value: organization.id }))
    const grantedIds = new Set(
      grants.filter(grant => grant.resource_id === null).map(grant => grant.permission_id),
    )
    const byId = new Map(catalog.map(permission => [permission.id, permission]))
    dataScopeEntries.value = [...grantedIds].map(permissionId => {
      const permission = byId.get(permissionId)
      const grant = grants.find(item => item.permission_id === permissionId)
      const policy = configured.find(item => item.permission_id === permissionId)
      return {
        permission_id: permissionId,
        permission_code: permission?.code || grant?.code || '',
        permission_description: permission?.description?.trim() || grant?.description?.trim() || '',
        scope_type: policy?.scope_type || '',
        organization_ids: policy?.organization_ids || [],
      }
    })
  } catch (error) {
    dataScopeEntries.value = []
    message.error(error instanceof Error ? error.message : '读取数据权限失败')
  } finally {
    loadingDataScopes.value = false
  }
}

async function saveDataScopes(): Promise<void> {
  if (!props.canManage || !props.roleId) return
  const invalidSelectedScope = dataScopeEntries.value.some(
    entry => entry.scope_type === 'selected_organizations' && !entry.organization_ids.length,
  )
  if (invalidSelectedScope) {
    message.error('指定组织范围至少选择一个组织')
    return
  }
  savingDataScopes.value = true
  try {
    const policies: DataScopePolicy[] = dataScopeEntries.value
      .filter(entry => entry.scope_type)
      .map(entry => ({
        permission_id: entry.permission_id,
        scope_type: entry.scope_type,
        organization_ids: entry.scope_type === 'selected_organizations' ? entry.organization_ids : [],
      }))
    await api(`/admin/roles/${props.roleId}/data-scopes`, {
      method: 'PUT',
      body: JSON.stringify({ policies }),
    })
    message.success('数据权限已保存')
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存数据权限失败')
  } finally {
    savingDataScopes.value = false
  }
}

function onGrantsSaved(): void {
  emit('saved')
  if (activePane.value === 'data') void loadDataScopes()
}

watch(() => [open.value, props.roleId] as const, ([visible]) => {
  if (visible) {
    activePane.value = 'resource'
  } else {
    dataScopeEntries.value = []
    dataScopeOrganizationOptions.value = []
  }
})

watch(activePane, pane => {
  if (open.value && pane === 'data') void loadDataScopes()
})
</script>

<template>
  <a-drawer
    v-model:open="open"
    :title="`应用权限 — ${roleName || '应用角色'}`"
    :width="720"
    :destroy-on-close="true"
  >
    <a-tabs v-model:activeKey="activePane" size="small">
      <a-tab-pane key="resource" tab="资源权限">
        <div class="flex flex-col gap-4 pt-1">
          <p class="m-0 text-xs text-[var(--color-text-muted)]">
            权限编码与业务端菜单树各自保存，互不影响。
          </p>
          <section class="flex flex-col gap-3 rounded-lg border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
            <div class="flex flex-col gap-1">
              <h3 class="m-0 text-sm font-medium text-[var(--color-text-primary)]">权限编码</h3>
              <p class="m-0 text-xs text-[var(--color-text-muted)]">勾选你看得见的租户 / 应用管理码与本应用业务码。</p>
            </div>
            <RolePermissionGrantModal
              v-if="open && grantReady"
              :open="true"
              embedded
              :role-id="roleId"
              :role-name="roleName"
              :lock-authority-codes="false"
              role-kind=""
              :role-namespace="roleNamespace"
              :catalog-path="catalogPath"
              :grants-path="grantsPath"
              :disable-iam-codes="false"
              @saved="onGrantsSaved"
            />
          </section>
          <section class="flex flex-col gap-3 rounded-lg border border-solid border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
            <div class="flex flex-col gap-1">
              <h3 class="m-0 text-sm font-medium text-[var(--color-text-primary)]">资源树</h3>
              <p class="m-0 text-xs text-[var(--color-text-muted)]">勾选该角色可见的菜单、按钮与数据规则；保存为全量替换。</p>
            </div>
            <RoleResourceGrantModal
              v-if="open && applicationId && roleId"
              :open="true"
              embedded
              :application-id="applicationId"
              :role-id="roleId"
              :role-name="roleName"
              @saved="emit('saved')"
            />
          </section>
        </div>
      </a-tab-pane>
      <a-tab-pane key="data" tab="数据权限">
        <a-spin :spinning="loadingDataScopes">
          <div class="flex flex-col gap-3 pt-1">
            <p class="m-0 text-xs text-[var(--color-text-muted)]">
              数据范围按同权限多角色取并集；未配置有效范围的权限默认拒绝访问。
            </p>
            <div v-if="!dataScopeEntries.length" class="py-8 text-center text-sm text-[var(--color-text-muted)]">
              请先在资源权限中勾选权限编码，再配置数据权限。
            </div>
            <div
              v-for="entry in dataScopeEntries"
              :key="entry.permission_id"
              class="grid gap-2 rounded-lg border border-solid border-[var(--color-border)] p-3 sm:grid-cols-[minmax(0,1fr)_220px] sm:items-start"
            >
              <div class="flex min-w-0 flex-col">
                <strong class="truncate text-sm text-[var(--color-text-primary)]">{{ entry.permission_description || entry.permission_code }}</strong>
                <span class="font-mono text-xs text-[var(--color-text-muted)]">{{ entry.permission_code }}</span>
              </div>
              <div class="flex flex-col gap-2">
                <a-select
                  v-model:value="entry.scope_type"
                  allow-clear
                  placeholder="不授予数据范围"
                  :disabled="!canManage"
                  :options="DATA_SCOPE_OPTIONS"
                />
                <a-select
                  v-if="entry.scope_type === 'selected_organizations'"
                  v-model:value="entry.organization_ids"
                  mode="multiple"
                  :disabled="!canManage"
                  :options="dataScopeOrganizationOptions"
                  placeholder="选择允许访问的组织"
                />
              </div>
            </div>
            <div v-if="canManage && dataScopeEntries.length" class="flex justify-end">
              <a-button type="primary" :loading="savingDataScopes" @click="saveDataScopes">保存数据权限</a-button>
            </div>
          </div>
        </a-spin>
      </a-tab-pane>
    </a-tabs>
  </a-drawer>
</template>
