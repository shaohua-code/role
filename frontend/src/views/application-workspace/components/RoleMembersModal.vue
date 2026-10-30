<script setup lang="ts">
// 角色行「配置成员」：已绑定列表 + 「增加成员」多选弹窗；绑定仍走租户台 PUT。
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import AdminEmpty from '@/components/AdminEmpty.vue'
import AdminSearchField from '@/components/AdminSearchField.vue'
import { asPagedList } from '@/utils/paged'

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
interface CandidateRecord {
  user_id: string
  email: string | null
  display_name: string
  already_bound: boolean
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

const saving = ref(false)
const loading = ref(false)
const removingUserId = ref('')
const members = ref<MemberRecord[]>([])
const total = ref(0)
const page = ref(1)
const PAGE_SIZE = 20

const pickerOpen = ref(false)
const pickerLoading = ref(false)
const pickerKeyword = ref('')
const pickerQuery = ref('')
const pickerPage = ref(1)
const pickerTotal = ref(0)
const candidates = ref<CandidateRecord[]>([])
const selectedKeys = ref<string[]>([])
const selectedById = ref<Record<string, CandidateRecord>>({})
const PICKER_PAGE_SIZE = 20

const columns = [
  { title: '成员', dataIndex: 'display_name', key: 'display_name', ellipsis: true },
  { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
  { title: '来源', dataIndex: 'sources', key: 'sources', width: 120 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 96 },
]

const pickerColumns = [
  { title: '成员', dataIndex: 'display_name', key: 'display_name', ellipsis: true },
  { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
  { title: '状态', dataIndex: 'already_bound', key: 'already_bound', width: 120 },
]

const selectedCount = computed(() => Object.keys(selectedById.value).length)

// 表格多选：已在该角色中的人禁用勾选；跨页保留已选项。
const pickerRowSelection = computed(() => ({
  selectedRowKeys: selectedKeys.value,
  preserveSelectedRowKeys: true,
  onChange: onPickerSelectChange,
  getCheckboxProps: (record: CandidateRecord) => ({
    disabled: record.already_bound || !record.email,
  }),
}))

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

async function loadCandidates(nextPage = pickerPage.value): Promise<void> {
  if (!props.applicationId || !props.roleId) {
    candidates.value = []
    pickerTotal.value = 0
    return
  }
  pickerLoading.value = true
  try {
    const params = new URLSearchParams({
      role_id: props.roleId,
      limit: String(PICKER_PAGE_SIZE),
      offset: String((nextPage - 1) * PICKER_PAGE_SIZE),
    })
    if (pickerQuery.value) params.set('q', pickerQuery.value)
    const result = asPagedList(await api<CandidateRecord[] | { items: CandidateRecord[] }>(
      `/tenant-admin/applications/${props.applicationId}/member-candidates?${params}`,
    ))
    candidates.value = result.items
    pickerTotal.value = result.total
    pickerPage.value = nextPage
  } catch (error) {
    candidates.value = []
    pickerTotal.value = 0
    message.error(error instanceof Error ? error.message : '读取租户成员失败')
  } finally {
    pickerLoading.value = false
  }
}

function onPickerSelectChange(keys: (string | number)[], rows: CandidateRecord[]): void {
  const next: Record<string, CandidateRecord> = {}
  for (const key of keys.map(String)) {
    const fromRow = rows.find(item => item.user_id === key)
    const previous = selectedById.value[key]
    const record = fromRow || previous
    if (record && !record.already_bound && record.email) next[key] = record
  }
  selectedById.value = next
  selectedKeys.value = Object.keys(next)
}

function openPicker(): void {
  pickerKeyword.value = ''
  pickerQuery.value = ''
  selectedKeys.value = []
  selectedById.value = {}
  pickerOpen.value = true
  void loadCandidates(1)
}

function onPickerSearch(query: string): void {
  pickerQuery.value = query
  void loadCandidates(1)
}

async function confirmPicker(): Promise<void> {
  const toBind = Object.values(selectedById.value).filter(item => item.email && !item.already_bound)
  if (!toBind.length) {
    message.warning('请选择要增加的成员')
    return
  }
  if (!props.canManage || !props.applicationId || !props.roleId) return
  saving.value = true
  let ok = 0
  let fail = 0
  try {
    for (const member of toBind) {
      try {
        await api(`/tenant-admin/applications/${props.applicationId}/role-bindings`, {
          method: 'PUT',
          body: JSON.stringify({ email: member.email, role_id: props.roleId }),
        })
        ok += 1
      } catch {
        fail += 1
      }
    }
    if (ok) message.success(`已绑定 ${ok} 名成员，并同时成为该应用的平台成员`)
    if (fail) message.error(`${fail} 名成员绑定失败`)
    if (ok) {
      pickerOpen.value = false
      await loadMembers(1)
    }
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

function onPickerTableChange(pagination: { current?: number }): void {
  void loadCandidates(pagination.current || 1)
}

watch(() => [open.value, props.applicationId, props.roleId] as const, ([visible]) => {
  if (visible) {
    void loadMembers(1)
  } else {
    members.value = []
    total.value = 0
    page.value = 1
    pickerOpen.value = false
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
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p class="m-0 text-xs text-[var(--color-text-muted)]">
          会同时成为该应用的平台成员；已有则跳过。用户组继承的角色只能改用户组，不能在这里移除。
        </p>
        <a-button
          v-if="canManage"
          type="primary"
          class="shrink-0"
          @click="openPicker"
        >增加成员</a-button>
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

  <a-modal
    v-model:open="pickerOpen"
    :title="`增加成员 — ${roleName || '应用角色'}`"
    ok-text="确定"
    cancel-text="取消"
    :confirm-loading="saving"
    :ok-button-props="{ disabled: selectedCount === 0 }"
    :width="640"
    :destroy-on-close="true"
    @ok="confirmPicker"
  >
    <div class="flex flex-col gap-3">
      <AdminSearchField
        v-model="pickerKeyword"
        placeholder="搜索姓名或邮箱"
        @search="onPickerSearch"
      />
      <p class="m-0 text-xs text-[var(--color-text-muted)]">
        列出本租户成员；已在该角色中的不可再选。已选 {{ selectedCount }} 人。
      </p>
      <a-table
        :data-source="candidates"
        :columns="pickerColumns"
        :loading="pickerLoading"
        :row-selection="pickerRowSelection"
        row-key="user_id"
        size="small"
        :pagination="{ current: pickerPage, pageSize: PICKER_PAGE_SIZE, total: pickerTotal, showSizeChanger: false }"
        @change="onPickerTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'already_bound'">
            <a-tag v-if="(record as CandidateRecord).already_bound">已在角色中</a-tag>
            <span v-else class="text-xs text-[var(--color-text-muted)]">可添加</span>
          </template>
        </template>
        <template #emptyText>
          <AdminEmpty emoji="👥" description="没有可添加的租户成员" />
        </template>
      </a-table>
    </div>
  </a-modal>
</template>
