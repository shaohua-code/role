<script setup lang="ts">
// 工作台「用户组」Tab：用户组仍挂租户，这里仅在组织上下文浏览该租户的用户组，
// 并复用共享 GroupRelationModal 快速管理成员/角色；新建、编辑、启停仍在「用户组管理」页。
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHas } from '@/api/capabilities'
import { PAGE_PATHS } from '@/router/navigation'
import AdminTableToolbar from '@/components/AdminTableToolbar.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import GroupRelationModal from '@/components/GroupRelationModal.vue'

export interface GroupsTabOrganization {
  id: string
  tenant_id: string
  name: string
  status: 'active' | 'disabled'
}

interface GroupRecord {
  id: string
  tenant_id: string
  key: string
  name: string
  description: string | null
  status: 'active' | 'disabled'
  member_count: number
  role_count: number
}

const router = useRouter()

const props = withDefaults(defineProps<{
  active?: boolean
  organization: GroupsTabOrganization | null
  apiPrefix?: string
}>(), {
  active: true,
  apiPrefix: '/admin',
})

const groups = ref<GroupRecord[]>([])
const loading = ref(false)
// 组员/组角色编辑复用共享弹窗，这里只维护弹窗上下文。
const relationOpen = ref(false)
const relationKind = ref<'members' | 'roles'>('members')
const relationGroupId = ref('')
const relationGroupName = ref('')
let requestSequence = 0

const canManage = computed(() => cachedHas('org.group.manage'))

const columns = [
  { title: '用户组', dataIndex: 'name', key: 'name', width: 180, ellipsis: true },
  { title: '标识', dataIndex: 'key', key: 'key', width: 200, ellipsis: true },
  { title: '成员', dataIndex: 'member_count', key: 'member_count', width: 90 },
  { title: '角色', dataIndex: 'role_count', key: 'role_count', width: 90 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
  { title: '说明', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 170, fixed: 'right' as const },
]

async function loadGroups(): Promise<void> {
  if (!props.active || !props.organization) {
    groups.value = []
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  try {
    // 用户组挂租户不挂组织：按所选组织所属租户整租展示。
    const rows = await api<GroupRecord[]>(`${props.apiPrefix}/groups?tenant_id=${encodeURIComponent(props.organization.tenant_id)}`)
    if (sequence === requestSequence) groups.value = rows
  } catch (error) {
    if (sequence === requestSequence) {
      groups.value = []
      message.error(error instanceof Error ? error.message : '读取用户组失败')
    }
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function openRelation(group: GroupRecord, kind: 'members' | 'roles'): void {
  relationGroupId.value = group.id
  relationGroupName.value = group.name
  relationKind.value = kind
  relationOpen.value = true
}

function onRelationSaved(): void {
  void loadGroups()
}

watch(() => [props.active, props.organization?.id] as const, ([active]) => {
  if (active) void loadGroups()
  else groups.value = []
}, { immediate: true })
</script>

<template>
  <div class="flex flex-col gap-4">
    <AdminTableToolbar :hint="canManage
      ? '用户组归属租户，不直接挂组织；成员变更会即时影响有效角色。新建与启停请到「高级管理 → 用户组」。'
      : '当前只有读取权限；如需编辑组关系请联系管理员授予 org.group.manage。'">
      <template #actions>
        <a-button :loading="loading" :disabled="!organization" @click="loadGroups">刷新</a-button>
        <a-button @click="router.push(PAGE_PATHS.groups)">高级用户组列表</a-button>
      </template>
    </AdminTableToolbar>

    <a-table
      :data-source="groups"
      :columns="columns"
      :loading="loading"
      row-key="id"
      :scroll="{ x: 900, y: 'calc(100vh - 560px)' }"
      :pagination="{ pageSize: 10, showSizeChanger: true }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag>
        </template>
        <template v-else-if="column.key === 'description'">
          <span v-if="record.description">{{ record.description }}</span>
          <span v-else class="text-xs text-[var(--color-text-muted)]">—</span>
        </template>
        <template v-else-if="column.key === 'actions'">
          <a-space :size="2">
            <a-button type="link" size="small" @click="openRelation(record as GroupRecord, 'members')">管理成员</a-button>
            <a-button type="link" size="small" @click="openRelation(record as GroupRecord, 'roles')">分配角色</a-button>
          </a-space>
        </template>
      </template>
      <template #emptyText>
        <AdminEmpty emoji="👥" description="该租户还没有用户组">
          <p class="m-0 text-xs text-[var(--color-text-muted)]">到「用户组管理」页创建用户组后回此查看</p>
        </AdminEmpty>
      </template>
    </a-table>

    <GroupRelationModal
      v-model:open="relationOpen"
      :kind="relationKind"
      :group-id="relationGroupId"
      :group-name="relationGroupName"
      :api-prefix="apiPrefix"
      :can-save="canManage"
      @saved="onRelationSaved"
    />
  </div>
</template>
