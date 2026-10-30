<script setup lang="ts">
// 工作台「成员」Tab：列出直接挂接当前组织的成员（Wave 2 新增的最小只读接口）。
// 成员的组织归属调整仍在「用户管理」完成，这里只做组织上下文浏览。
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import { PAGE_PATHS } from '@/router/navigation'
import AdminTableToolbar from '@/components/AdminTableToolbar.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'

export interface MemberTabOrganization {
  id: string
  name: string
  status: 'active' | 'disabled'
}

interface MemberRecord {
  user_id: string
  membership_id: string
  email: string | null
  display_name: string
  user_status: string
  membership_status: string
  is_primary: boolean
}

const router = useRouter()

const props = withDefaults(defineProps<{
  active?: boolean
  organization: MemberTabOrganization | null
  apiPrefix?: string
}>(), {
  active: true,
  apiPrefix: '/admin',
})

const members = ref<MemberRecord[]>([])
const loading = ref(false)
const keyword = ref('')
let requestSequence = 0

const columns = [
  { title: '成员名称', dataIndex: 'display_name', key: 'display_name', width: 200, ellipsis: true },
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 260, ellipsis: true },
  { title: '主组织', dataIndex: 'is_primary', key: 'is_primary', width: 100 },
  { title: '成员状态', dataIndex: 'membership_status', key: 'membership_status', width: 110 },
  { title: '账号状态', dataIndex: 'user_status', key: 'user_status', width: 110 },
]

const MEMBERSHIP_STATUS_LABELS: Record<string, string> = {
  active: '正常',
  disabled: '已停用',
  departed: '已离职',
}

async function loadMembers(): Promise<void> {
  if (!props.active || !props.organization) {
    members.value = []
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  try {
    const query = keyword.value ? `?q=${encodeURIComponent(keyword.value)}` : ''
    const rows = await api<MemberRecord[]>(`${props.apiPrefix}/organizations/${props.organization.id}/members${query}`)
    if (sequence === requestSequence) members.value = rows
  } catch (error) {
    if (sequence === requestSequence) {
      members.value = []
      message.error(error instanceof Error ? error.message : '读取组织成员失败')
    }
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

// 搜索框回车/清空时带 q 参数重新查询。
function onSearch(value: string): void {
  keyword.value = value
  void loadMembers()
}

watch(() => [props.active, props.organization?.id] as const, ([active]) => {
  keyword.value = ''
  if (active) void loadMembers()
  else members.value = []
}, { immediate: true })
</script>

<template>
  <div class="flex flex-col gap-4">
    <AdminTableToolbar hint="仅展示直接挂接本组织的成员，不含子组织；组织归属在「用户管理」调整；新建组织见「高级管理 → 组织管理」。">
      <AdminSearchField v-model="keyword" placeholder="搜索成员名称或邮箱" @search="onSearch" />
      <template #actions>
        <a-button :loading="loading" :disabled="!organization" @click="loadMembers">刷新</a-button>
        <a-button @click="router.push(PAGE_PATHS.users)">前往用户管理</a-button>
      </template>
    </AdminTableToolbar>

    <a-table
      :data-source="members"
      :columns="columns"
      :loading="loading"
      row-key="user_id"
      :scroll="{ x: 780, y: 'calc(100vh - 560px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'is_primary'">
          <a-tag v-if="record.is_primary">主组织</a-tag>
          <span v-else class="text-xs text-[var(--color-text-muted)]">—</span>
        </template>
        <template v-else-if="column.key === 'membership_status'">
          <a-tag :color="record.membership_status === 'active' ? 'green' : 'default'">
            {{ MEMBERSHIP_STATUS_LABELS[record.membership_status] || record.membership_status }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'user_status'">
          <a-tag :color="record.user_status === 'active' ? 'green' : 'default'">
            {{ record.user_status === 'active' ? '启用' : '停用' }}
          </a-tag>
        </template>
      </template>
      <template #emptyText>
        <AdminEmpty emoji="🧍" description="该组织还没有直接挂接的成员">
          <p class="m-0 text-xs text-[var(--color-text-muted)]">到「用户管理」编辑成员的组织归属后回此查看</p>
        </AdminEmpty>
      </template>
    </a-table>
  </div>
</template>
