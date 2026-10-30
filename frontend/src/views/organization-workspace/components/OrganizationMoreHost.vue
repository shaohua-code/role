<script setup lang="ts">
// 组织树「更多」动作宿主：按菜单项打开负责人 / 启停 / 删除弹窗，不占用右侧 Tab。
import { ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHasAny, getCachedCapabilities } from '@/api/capabilities'

export type OrganizationMoreAction = 'owner' | 'status' | 'delete'

export interface SettingsOrganization {
  id: string
  tenant_id: string
  tenant_name: string
  parent_id: string | null
  name: string
  key: string
  status: 'active' | 'disabled'
  owner_user_id?: string | null
  owner_name?: string | null
}

interface TenantOption {
  id: string
  can_manage_organizations?: boolean
}

const action = defineModel<OrganizationMoreAction | ''>('action', { default: '' })

const props = withDefaults(defineProps<{
  organization: SettingsOrganization | null
  tenants: TenantOption[]
  apiPrefix?: string
}>(), {
  apiPrefix: '/admin',
})

const emit = defineEmits<{
  changed: []
  deleted: []
}>()

const ownerOpen = ref(false)
const ownerSaving = ref(false)
const ownerMembersLoading = ref(false)
const ownerUserId = ref<string | undefined>(undefined)
const ownerMemberOptions = ref<{ value: string; label: string }[]>([])

function canManageOrganization(organization: SettingsOrganization): boolean {
  if (cachedHasAny(['button.org.manage']) && getCachedCapabilities()?.platform_admin) return true
  return props.tenants.some(tenant => tenant.id === organization.tenant_id && tenant.can_manage_organizations === true)
}

async function openOwnerEditor(organization: SettingsOrganization): Promise<void> {
  if (!canManageOrganization(organization)) {
    message.warning('没有管理该组织的权限')
    return
  }
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
  } finally {
    ownerMembersLoading.value = false
  }
}

async function saveOwner(): Promise<void> {
  const organization = props.organization
  if (!organization) return
  ownerSaving.value = true
  try {
    await api(`${props.apiPrefix}/organizations/${organization.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ owner_user_id: ownerUserId.value || null }),
    })
    message.success('负责人已更新')
    ownerOpen.value = false
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '更新负责人失败')
  } finally {
    ownerSaving.value = false
  }
}

function changeStatus(organization: SettingsOrganization): void {
  if (!canManageOrganization(organization)) {
    message.warning('没有管理该组织的权限')
    return
  }
  const status = organization.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(`${props.apiPrefix}/organizations/${organization.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      })
      message.success(status === 'active' ? '组织已启用' : '组织已停用')
      emit('changed')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '更新组织状态失败')
    }
  }
  if (status === 'disabled') {
    Modal.confirm({
      title: '停用组织？',
      content: `停用“${organization.name}”后，成员不能再被新分配到该组织，该组织关联的数据范围也不会包含它。`,
      okText: '停用组织',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: update,
    })
  } else {
    void update()
  }
}

function deleteOrganization(organization: SettingsOrganization): void {
  if (!canManageOrganization(organization)) {
    message.warning('没有管理该组织的权限')
    return
  }
  Modal.confirm({
    title: `删除组织“${organization.name}”？`,
    content: '将永久删除该组织并解除全部成员挂接（成员账号本身保留）；关联数据范围中的该组织将不再生效。存在子组织时需先删除或移动子组织。',
    okText: '永久删除',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(`${props.apiPrefix}/organizations/${organization.id}`, { method: 'DELETE' })
        message.success('组织已删除')
        emit('deleted')
      } catch (error) {
        message.error(error instanceof Error ? error.message : '删除组织失败')
      }
    },
  })
}

watch([action, () => props.organization], ([nextAction, organization]) => {
  if (!nextAction || !organization) return
  action.value = ''
  if (nextAction === 'owner') void openOwnerEditor(organization)
  else if (nextAction === 'status') changeStatus(organization)
  else if (nextAction === 'delete') deleteOrganization(organization)
})
</script>

<template>
  <a-modal
    v-model:open="ownerOpen"
    title="设置部门负责人"
    ok-text="保存"
    cancel-text="取消"
    :confirm-loading="ownerSaving"
    @ok="saveOwner"
  >
    <a-form layout="vertical">
      <a-form-item label="组织">
        <a-input :value="organization?.name" disabled />
      </a-form-item>
      <a-form-item label="负责人（可选）">
        <a-select
          v-model:value="ownerUserId"
          allow-clear
          show-search
          option-filter-prop="label"
          :loading="ownerMembersLoading"
          :options="ownerMemberOptions"
          placeholder="选择该租户内的活动成员"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>
