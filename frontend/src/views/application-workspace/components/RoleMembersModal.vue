<script setup lang="ts">
// 角色行「配置成员」：只操作当前应用角色的绑定，复用租户台 bind / unbind 接口。
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import AdminEmpty from '@/components/AdminEmpty.vue'

interface RoleAssignment {
  id: string
  key: string
  name: string
  status: string
  sources: ('direct' | 'group')[]
}
interface MemberRecord {
  user_id: string
  email: string | null
  display_name: string
  roles: RoleAssignment[]
}

const props = withDefaults(defineProps<{
  applicationId?: string
  roleId?: string
  roleName?: string
  canManage?: boolean
}>(), {
  applicationId: '',
  roleId: '',
  roleName: '',
  canManage: false,
})

const open = defineModel<boolean>('open', { default: false })

const email = ref('')
const saving = ref(false)
const loading = ref(false)
const removingUserId = ref('')
const members = ref<MemberRecord[]>([])
const total = ref(0)
const page = ref(1)
const PAGE_SIZE = 20

const columns = [
  { title: '成员', dataIndex: 'display_name', key: 'display_name', ellipsis: true },
  { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
  { title: '来源', dataIndex: 'sources', key: 'sources', width: 120 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 96 },
]

function currentAssignment(record: MemberRecord): RoleAssignment | undefined {
  return record.roles.find(role => role.id === props.roleId)
}

async function loadMembers(nextPage = page.value): Promise<void> {
  if (!props.applicationId || !props.roleId) {
    members.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const params = new URLSearchParams({
      role_id: props.roleId,
      limit: String(PAGE_SIZE),
      offset: String((nextPage - 1) * PAGE_SIZE),
    })
    const result = await api<{ items: MemberRecord[]; total: number }>(
      `/tenant-admin/applications/${props.applicationId}/members?${params}`,
    )
    members.value = result.items
    total.value = result.total
    page.value = nextPage
  } catch (error) {
    members.value = []
    total.value = 0
    message.error(error instanceof Error ? error.message : '读取角色成员失败')
  } finally {
    loading.value = false
  }
}

async function bindMember(): Promise<void> {
  if (!props.canManage || !props.applicationId || !props.roleId) return
  if (!email.value.trim()) {
    message.error('请填写租户成员邮箱')
    return
  }
  saving.value = true
  try {
    await api(`/tenant-admin/applications/${props.applicationId}/role-bindings`, {
      method: 'PUT',
      body: JSON.stringify({ email: email.value.trim(), role_id: props.roleId }),
    })
    email.value = ''
    message.success('已绑定该应用角色，并同时成为该应用的平台成员')
    await loadMembers(1)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '绑定失败；请确认对方已是本租户成员')
  } finally {
    saving.value = false
  }
}

async function unbindMember(record: MemberRecord): Promise<void> {
  if (!props.canManage || !props.applicationId || !props.roleId) return
  removingUserId.value = record.user_id
  try {
    await api(
      `/tenant-admin/applications/${props.applicationId}/members/${record.user_id}/roles/${props.roleId}`,
      { method: 'DELETE' },
    )
    message.success('已移除直接绑定')
    const nextPage = members.value.length === 1 && page.value > 1 ? page.value - 1 : page.value
    await loadMembers(nextPage)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '移除绑定失败')
  } finally {
    removingUserId.value = ''
  }
}

function onTableChange(pagination: { current?: number }): void {
  void loadMembers(pagination.current || 1)
}

watch(() => [open.value, props.applicationId, props.roleId] as const, ([visible]) => {
  if (visible) {
    email.value = ''
    void loadMembers(1)
  } else {
    members.value = []
    total.value = 0
    page.value = 1
  }
})
</script>

<template>
  <a-drawer
    v-model:open="open"
    :title="`配置成员 — ${roleName || '应用角色'}`"
    :width="560"
    :destroy-on-close="true"
  >
    <div class="flex flex-col gap-4">
      <p class="m-0 text-xs text-[var(--color-text-muted)]">
        会同时成为该应用的平台成员；已有则跳过。用户组继承的角色只能改用户组，不能在这里移除。
      </p>
      <div v-if="canManage" class="flex flex-col gap-2 sm:flex-row sm:items-center">
        <a-input
          v-model:value="email"
          type="email"
          autocomplete="off"
          class="min-w-0 flex-1"
          placeholder="租户成员邮箱"
          @press-enter="bindMember"
        />
        <a-button type="primary" :loading="saving" :disabled="!email.trim()" @click="bindMember">绑定</a-button>
      </div>
      <a-table
        :data-source="members"
        :columns="columns"
        :loading="loading"
        row-key="user_id"
        size="small"
        :pagination="{ current: page, pageSize: PAGE_SIZE, total, showSizeChanger: false }"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'sources'">
            <a-tag v-if="currentAssignment(record as MemberRecord)?.sources.includes('direct')">直接</a-tag>
            <a-tag v-if="currentAssignment(record as MemberRecord)?.sources.includes('group')">用户组</a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button
              v-if="canManage && currentAssignment(record as MemberRecord)?.sources.includes('direct')"
              type="link"
              size="small"
              danger
              :loading="removingUserId === (record as MemberRecord).user_id"
              @click="unbindMember(record as MemberRecord)"
            >移除</a-button>
            <span v-else class="text-xs text-[var(--color-text-muted)]">—</span>
          </template>
        </template>
        <template #emptyText>
          <AdminEmpty emoji="👥" description="还没有成员持有这个角色" />
        </template>
      </a-table>
    </div>
  </a-drawer>
</template>
