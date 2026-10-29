<script setup lang="ts">
// 共享「用户组关系」弹窗：按类型批量编辑组成员或组角色。
// 自用户组管理页抽取，供用户组页与组织工作台「用户组」Tab 复用，避免重复造轮子。
// P355：多选下拉升级为穿梭框（对齐用户页「配置租户角色」交互）——左右双栏 + 搜索 + 勾选，
// 解决单 Select 弹窗空荡、选项平铺难读的观感问题。
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'

const props = withDefaults(defineProps<{
  open: boolean
  /** members = 编辑组成员；roles = 分配组角色 */
  kind: 'members' | 'roles'
  groupId: string
  groupName: string
  apiPrefix?: string
  /** 无组管理码时只读查看，保存按钮禁用 */
  canSave?: boolean
}>(), {
  apiPrefix: '/admin',
  canSave: false,
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  saved: []
}>()

const saving = ref(false)
const loading = ref(false)
const selectedIds = ref<string[]>([])

/** 穿梭框数据项：title 主文本，description 次要信息（参与搜索）。 */
interface TransferItem { key: string; title: string; description: string; disabled: boolean }
const items = ref<TransferItem[]>([])

// 弹窗打开时拉取目录：服务端已用 in_group/assigned 标记当前关系，前端换算已选项。
watch(() => props.open, async open => {
  if (!open || !props.groupId) return
  loading.value = true
  try {
    if (props.kind === 'members') {
      const members = await api<Array<{ user_id: string; email?: string | null; display_name: string; user_status: string; membership_status: string; in_group: boolean }>>(
        `${props.apiPrefix}/groups/${props.groupId}/members`)
      selectedIds.value = members.filter(item => item.in_group).map(item => item.user_id)
      items.value = members.map(item => ({
        key: item.user_id,
        title: item.display_name,
        description: `${item.email || '无邮箱'} · ${item.membership_status === 'active' ? '租户成员正常' : '租户成员已停用'}${item.user_status === 'active' ? '' : ' · 全局账号已停用'}`,
        disabled: false,
      }))
    } else {
      const roles = await api<Array<{ id: string; key: string; name: string; status: string; assigned: boolean }>>(
        `${props.apiPrefix}/groups/${props.groupId}/roles`)
      selectedIds.value = roles.filter(item => item.assigned).map(item => item.id)
      items.value = roles.map(item => ({
        key: item.id,
        title: item.name,
        description: `${item.key}${item.status === 'active' ? '' : ' · 角色已停用'}`,
        // 停用且未分配的角色禁止新勾入；已分配的停用角色保留可移除。
        disabled: item.status !== 'active' && !item.assigned,
      }))
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : (props.kind === 'members' ? '读取组成员失败' : '读取组角色失败'))
    emit('update:open', false)
  } finally {
    loading.value = false
  }
})

// 穿梭框行主文本：主名称 + 次要信息一行展示，次要信息供搜索但不喧宾夺主。
function renderItem(item: TransferItem): string {
  return item.description ? `${item.title}（${item.description}）` : item.title
}

function filterItem(inputValue: string, item: TransferItem): boolean {
  const keyword = inputValue.trim().toLowerCase()
  return !keyword
    || item.title.toLowerCase().includes(keyword)
    || item.description.toLowerCase().includes(keyword)
}

// 底部摘要：让管理员保存前能确认改动规模。
const selectedSummary = computed(() => {
  const selected = new Set(selectedIds.value)
  const picked = items.value.filter(item => selected.has(item.key))
  const disabledCount = picked.filter(item => item.disabled).length
  const suffix = props.kind === 'roles' && disabledCount ? `，含 ${disabledCount} 个已停用角色` : ''
  return `已选 ${picked.length} 项${suffix}`
})

// 全量替换保存，与用户组管理页共用同一 PUT 契约。
async function saveRelations(): Promise<void> {
  if (!props.canSave) return
  saving.value = true
  try {
    await api(`${props.apiPrefix}/groups/${props.groupId}/${props.kind}`, {
      method: 'PUT',
      body: JSON.stringify(props.kind === 'members'
        ? { user_ids: selectedIds.value }
        : { role_ids: selectedIds.value }),
    })
    message.success(props.kind === 'members' ? '组成员已保存' : '组角色已保存')
    emit('update:open', false)
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存用户组关系失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <a-modal
    :open="open"
    :title="`${kind === 'members' ? '管理成员' : '分配角色'} · ${groupName}`"
    width="760px"
    :ok-text="kind === 'members' ? '保存成员' : '保存角色'"
    cancel-text="取消"
    :ok-button-props="{ disabled: !canSave }"
    :confirm-loading="saving"
    @ok="saveRelations"
    @update:open="emit('update:open', $event)"
  >
    <a-spin :spinning="loading">
      <a-alert
        class="mb-4"
        type="info"
        show-icon
        :message="kind === 'members'
          ? '停用成员的组关系会保留，但其当前身份不会因此获得有效权限。'
          : '组角色与用户直接分配的角色叠加判定；停用的角色不会授予权限。'"
      />
      <a-transfer
        v-model:target-keys="selectedIds"
        :data-source="items"
        :render="renderItem"
        :filter-option="filterItem"
        show-search
        :list-style="{ width: '318px', height: '352px' }"
        :locale="{ itemsUnit: '项' }"
      />
      <p class="mb-0 mt-3 text-xs text-[var(--color-text-secondary)]">{{ selectedSummary }}；保存为全量替换。</p>
    </a-spin>
  </a-modal>
</template>
