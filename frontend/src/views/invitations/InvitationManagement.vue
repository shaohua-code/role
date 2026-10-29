<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHas } from '@/api/capabilities'
import { isReservedEmailHost } from '@/utils/emailValidation'
import AdminListPage from '@/components/AdminListPage.vue'

interface TenantOption { id: string; name: string; status: string; slug?: string }
interface RoleOption { id: string; tenant_id: string; name: string; status: string }
interface Invitation {
  id: string
  tenant_id: string
  tenant_name: string
  email: string
  display_name: string
  role_id: string
  role_name: string
  status: 'pending' | 'accepted' | 'revoked' | 'expired'
  expires_at: string
  accepted_at: string | null
  created_at: string
}
type InvitationDelivery = 'email_sent' | 'email_failed' | 'manual_copy'

const props = defineProps<{
  active: boolean
  tenants: TenantOption[]
  roles: RoleOption[]
}>()

const invitations = ref<Invitation[]>([])
const canManageInvites = computed(() => cachedHas('org.invite.manage'))
// undefined 才能触发 Select 的 placeholder；'' 会被当作已选值导致空框无占位文案
const selectedTenantId = ref<string | undefined>(undefined)
const loading = ref(false)
const errorText = ref('')
const createOpen = ref(false)
const creating = ref(false)
const linkOpen = ref(false)
const createdUrl = ref('')
const linkDelivery = ref<InvitationDelivery>('manual_copy')
const form = reactive({ tenant_id: '', email: '', display_name: '', role_id: '', expires_in_hours: 72 })
// G21 批量邀请：一次多邮箱（换行/逗号分隔），冲突邮箱跳过不阻断。
const batchOpen = ref(false)
const batchSaving = ref(false)
const batchTenantId = ref<string>('')
const batchRoleId = ref<string>('')
const batchEmails = ref('')
const batchExpiresInHours = ref(72)
const batchResults = ref<{ email: string; status: string; reason?: string; invite_url?: string }[]>([])
// G21 重发：换发新 token 并顺延有效期，旧链接立即失效。
const resendingId = ref('')
let requestSequence = 0

const tenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.status === 'active')
  .map(tenant => ({ value: tenant.id, label: tenant.name })))
// 平台引导租户不参与业务邀请，创建下拉排除；筛选器保留以便查看其下数据
const creatableTenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.slug !== 'platform' && tenant.status === 'active')
  .map(tenant => ({ value: tenant.id, label: tenant.name })))
const roleOptions = computed(() => props.roles
  .filter(role => role.status === 'active' && role.tenant_id === form.tenant_id)
  .map(role => ({ value: role.id, label: role.name })))

const columns = [
  // 列宽合计压到 ~1330：宽视口零横向滚动，1280 视口滚动量减半（时间列 180 保单行不折行）
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '邮箱', dataIndex: 'email', key: 'email', width: 170, ellipsis: true },
  { title: '姓名', dataIndex: 'display_name', key: 'display_name', width: 140, ellipsis: true },
  { title: '租户', dataIndex: 'tenant_name', key: 'tenant_name', width: 140, ellipsis: true },
  { title: '授予角色', dataIndex: 'role_name', key: 'role_name', width: 140, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 88 },
  { title: '有效期至', dataIndex: 'expires_at', key: 'expires_at', width: 180 },
  { title: '接受时间', dataIndex: 'accepted_at', key: 'accepted_at', width: 180 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 110, fixed: 'right' as const },
]

async function loadInvitations(): Promise<void> {
  if (!props.active) return
  const sequence = ++requestSequence
  loading.value = true
  errorText.value = ''
  try {
    const query = new URLSearchParams()
    if (selectedTenantId.value) query.set('tenant_id', selectedTenantId.value)
    const suffix = query.size ? `?${query.toString()}` : ''
    const result = await api<Invitation[]>(`/admin/invitations${suffix}`)
    if (sequence === requestSequence && props.active) invitations.value = result
  } catch (error) {
    if (sequence !== requestSequence) return
    invitations.value = []
    errorText.value = error instanceof Error ? error.message : '读取成员邀请失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function openCreate(): void {
  form.tenant_id = creatableTenantOptions.value[0]?.value || ''
  form.email = ''
  form.display_name = ''
  form.role_id = ''
  form.expires_in_hours = 72
  createOpen.value = true
}

async function createInvitation(): Promise<void> {
  const email = form.email.trim().toLowerCase()
  const displayName = form.display_name.trim()
  if (!creatableTenantOptions.value.some(option => option.value === form.tenant_id)) {
    message.error('请选择活动租户')
    return
  }
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    message.error('请输入有效邮箱地址')
    return
  }
  if (isReservedEmailHost(email)) {
    message.error('该邮箱使用保留顶级域（如 .test/.localhost），服务端不接受；请改用真实域名')
    return
  }
  if (!displayName || displayName.length > 120) {
    message.error('姓名需填写且不超过 120 个字符')
    return
  }
  if (!roleOptions.value.some(option => option.value === form.role_id)) {
    message.error('请选择该租户内的活动角色')
    return
  }
  if (!Number.isInteger(form.expires_in_hours) || form.expires_in_hours < 1 || form.expires_in_hours > 336) {
    message.error('有效期须为 1 至 336 小时的整数')
    return
  }

  creating.value = true
  try {
    const result = await api<{ invite_url: string; delivery: InvitationDelivery }>('/admin/invitations', {
      method: 'POST',
      body: JSON.stringify({
        tenant_id: form.tenant_id,
        email,
        display_name: displayName,
        role_id: form.role_id,
        expires_in_hours: form.expires_in_hours,
      }),
    })
    createdUrl.value = result.invite_url
    linkDelivery.value = result.delivery
    createOpen.value = false
    linkOpen.value = true
    if (result.delivery === 'email_sent') message.success('邀请邮件已提交到 SMTP，备用链接仅展示一次')
    else if (result.delivery === 'email_failed') message.warning('邮件投递失败，请使用下方一次性备用链接')
    else message.success('邀请已创建，请通过可信渠道交付一次性链接')
    await loadInvitations()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建邀请失败')
  } finally {
    creating.value = false
  }
}

// G21 批量邀请弹窗：租户/角色/邮箱列表一次提交；单邮箱冲突跳过不阻断其余。
const batchRoleOptions = computed(() => props.roles
  .filter(role => role.status === 'active' && role.tenant_id === batchTenantId.value)
  .map(role => ({ value: role.id, label: role.name })))

function openBatch(): void {
  // 筛选器可能停留在平台租户上（不参与创建），此时回落到首个可发起邀请的租户
  const preferredTenantId = selectedTenantId.value
  batchTenantId.value = preferredTenantId && creatableTenantOptions.value.some(option => option.value === preferredTenantId)
    ? preferredTenantId
    : creatableTenantOptions.value[0]?.value || ''
  batchRoleId.value = ''
  batchEmails.value = ''
  batchExpiresInHours.value = 72
  batchResults.value = []
  batchOpen.value = true
}

async function submitBatch(): Promise<void> {
  if (!creatableTenantOptions.value.some(option => option.value === batchTenantId.value)) {
    message.error('请选择活动租户')
    return
  }
  if (!batchRoleOptions.value.some(option => option.value === batchRoleId.value)) {
    message.error('请选择该租户内的活动角色')
    return
  }
  // 换行/逗号/分号/空格均可分隔；大小写归一并去重，保持首现顺序。
  const emails = Array.from(new Set(batchEmails.value
    .split(/[\s,;，；]+/).map(email => email.trim().toLowerCase()).filter(Boolean)))
  if (!emails.length) {
    message.error('请输入至少一个邮箱')
    return
  }
  for (const email of emails) {
    if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      message.error(`邮箱格式无效：${email}`)
      return
    }
    if (isReservedEmailHost(email)) {
      message.error(`邮箱使用保留顶级域（如 .test/.localhost），服务端不接受：${email}`)
      return
    }
  }
  batchSaving.value = true
  try {
    const result = await api<{ created: number; skipped: number; items: typeof batchResults.value }>('/admin/invitations/batch', {
      method: 'POST',
      body: JSON.stringify({
        tenant_id: batchTenantId.value,
        emails,
        display_name: '批量受邀成员',
        role_id: batchRoleId.value,
        expires_in_hours: batchExpiresInHours.value,
      }),
    })
    batchResults.value = result.items
    message.success(`批量邀请完成：成功 ${result.created} 个，跳过 ${result.skipped} 个；链接仅展示这一次，请立即保存`)
    await loadInvitations()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '批量邀请失败')
  } finally { batchSaving.value = false }
}

// G21 重发：仅待接受邀请可重发；旧 token 立即失效，有效期顺延 72 小时。
function confirmResend(invitation: Invitation): void {
  Modal.confirm({
    title: '重发成员邀请',
    content: `向 ${invitation.email} 重发邀请？旧链接将立即失效，有效期顺延 72 小时。`,
    okText: '重发邀请',
    onOk: async () => {
      resendingId.value = invitation.id
      try {
        const result = await api<{ invite_url: string; delivery: InvitationDelivery }>(`/admin/invitations/${invitation.id}/resend`, {
          method: 'POST',
          body: JSON.stringify({ expires_in_hours: 72 }),
        })
        createdUrl.value = result.invite_url
        linkDelivery.value = result.delivery
        linkOpen.value = true
        await loadInvitations()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '重发邀请失败')
      } finally { resendingId.value = '' }
    },
  })
}

function confirmRevoke(invitation: Invitation): void {
  Modal.confirm({
    title: '撤销成员邀请',
    content: `撤销发往 ${invitation.email} 的待处理邀请？该链接之后将不可使用。`,
    okText: '撤销邀请',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await api(`/admin/invitations/${invitation.id}/revoke`, { method: 'POST' })
        message.success('邀请已撤销')
        await loadInvitations()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '撤销邀请失败')
        throw error
      }
    },
  })
}

async function copyInviteUrl(): Promise<void> {
  try { await navigator.clipboard.writeText(createdUrl.value); message.success('邀请链接已复制') }
  catch { message.error('复制失败，请手动复制') }
}

function formatTime(value: unknown): string {
  if (typeof value !== 'string' || !value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function statusText(status: string): string {
  return ({ pending: '待接受', accepted: '已接受', revoked: '已撤销', expired: '已过期' } as Record<string, string>)[status] || status
}

watch(() => props.active, (active) => {
  if (active) void loadInvitations()
}, { immediate: true })
</script>

<template>
  <AdminListPage
    eyebrow="TENANT MEMBERSHIP"
    title="成员邀请"
    subtitle="向指定邮箱创建有期限的租户角色邀请；系统只保存令牌摘要，邮件投递由服务端可选配置。"
    :hint="`${invitations.length} 条邀请 · 最多读取 500 条`"
    :columns="columns"
    :data-source="invitations"
    :loading="loading"
    row-key="id"
    :scroll="{ x: 1330, y: 'calc(100vh - 430px)' }"
    :pagination="{ pageSize: 10, showSizeChanger: true }"
    :error-text="errorText"
    empty-emoji="✉️"
    :empty-text="selectedTenantId ? '当前租户暂无邀请记录' : '暂无邀请记录'"
  >
    <template #header-extra>
      <a-space :size="8">
        <!-- G21 批量邀请：一次多邮箱，冲突跳过不阻断。 -->
        <a-button v-if="canManageInvites" @click="openBatch">批量邀请</a-button>
        <a-button v-if="canManageInvites" type="primary" @click="openCreate">＋ 新建邀请</a-button>
      </a-space>
    </template>
    <a-select
      v-model:value="selectedTenantId"
      allow-clear
      show-search
      option-filter-prop="label"
      placeholder="全部租户"
      :options="tenantOptions"
      @change="loadInvitations"
    />
    <template #actions>
      <a-button :loading="loading" @click="loadInvitations">刷新</a-button>
    </template>
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'created_at' || column.key === 'expires_at' || column.key === 'accepted_at'">{{ formatTime(record[column.dataIndex]) }}</template>
      <template v-else-if="column.key === 'status'">
        <a-tag :color="record.status === 'accepted' ? 'green' : record.status === 'pending' ? 'orange' : record.status === 'revoked' ? 'red' : 'default'">{{ statusText(String(record.status || '')) }}</a-tag>
      </template>
      <template v-else-if="column.key === 'actions'">
        <a-space v-if="canManageInvites" :size="0">
          <!-- G21 重发：待接受邀请可换发新链接并顺延有效期。 -->
          <a-button v-if="record.status === 'pending'" type="link" size="small" :loading="resendingId === record.id" @click="confirmResend(record)">重发</a-button>
          <a-button type="link" danger size="small" @click="confirmRevoke(record)">撤销邀请</a-button>
        </a-space>
        <span v-else class="table-hint">—</span>
      </template>
    </template>
  </AdminListPage>

  <a-modal v-model:open="createOpen" title="创建成员邀请" ok-text="生成邀请链接" cancel-text="取消" :confirm-loading="creating" @ok="createInvitation">
    <a-form layout="vertical" class="create-form">
      <a-form-item label="所属租户" required>
        <a-select v-model:value="form.tenant_id" :options="creatableTenantOptions" placeholder="选择活动租户" @change="form.role_id = ''" />
      </a-form-item>
      <a-form-item label="邮箱" required><a-input v-model:value="form.email" autocomplete="email" :maxlength="254" /></a-form-item>
      <a-form-item label="姓名" required><a-input v-model:value="form.display_name" :maxlength="120" /></a-form-item>
      <a-form-item label="加入角色" required>
        <a-select v-model:value="form.role_id" :options="roleOptions" placeholder="选择该租户中的活动角色" />
      </a-form-item>
      <a-form-item label="有效期（小时）" required>
        <a-input-number v-model:value="form.expires_in_hours" :min="1" :max="336" :precision="0" style="width:100%" />
      </a-form-item>
      <a-alert message="邀请链接只展示一次。服务端启用 SMTP 邀请邮件后会自动投递；否则请使用创建后的备用链接。" type="info" show-icon />
    </a-form>
  </a-modal>

  <!-- G21 批量邀请弹窗：多邮箱一次提交；结果区列出每邮箱状态与一次性链接。 -->
  <a-modal v-model:open="batchOpen" title="批量邀请成员" width="680px"
    ok-text="生成邀请链接" cancel-text="取消" :confirm-loading="batchSaving" @ok="submitBatch">
    <a-form layout="vertical">
      <a-form-item label="所属租户" required>
        <a-select v-model:value="batchTenantId" :options="creatableTenantOptions" placeholder="选择活动租户" @change="batchRoleId = ''" />
      </a-form-item>
      <a-form-item label="加入角色" required>
        <a-select v-model:value="batchRoleId" :options="batchRoleOptions" placeholder="选择该租户中的活动角色" />
      </a-form-item>
      <a-form-item label="邮箱列表（每行一个，也支持逗号/空格分隔；最多 50 个）" required>
        <a-textarea v-model:value="batchEmails" :rows="6" placeholder="a@example.com&#10;b@example.com" />
      </a-form-item>
      <a-form-item label="有效期（小时）" required>
        <a-input-number v-model:value="batchExpiresInHours" :min="1" :max="336" :precision="0" style="width:100%" />
      </a-form-item>
      <a-alert message="已持有有效邀请或已拥有该角色的邮箱会被跳过；所有一次性链接仅在本弹窗展示一次，请立即保存。" type="info" show-icon />
    </a-form>
    <div v-if="batchResults.length" class="mt-3">
      <a-divider class="my-2" />
      <div class="mb-2 text-xs font-semibold">本轮结果（{{ batchResults.filter(r => r.status === 'created').length }} 成功 / {{ batchResults.filter(r => r.status === 'skipped').length }} 跳过）</div>
      <div class="grid max-h-52 gap-1 overflow-y-auto">
        <div v-for="item in batchResults" :key="item.email"
          class="flex items-center justify-between rounded border border-[var(--color-border)] px-2 py-1 text-xs">
          <span class="min-w-0 truncate font-mono">{{ item.email }}</span>
          <span v-if="item.status === 'created'" class="min-w-0 flex-1 truncate pl-2 text-[var(--color-text-muted)]" :title="item.invite_url">{{ item.invite_url }}</span>
          <a-tag v-else color="default">{{ item.reason || '跳过' }}</a-tag>
        </div>
      </div>
    </div>
  </a-modal>

  <a-modal v-model:open="linkOpen" title="安全发送成员邀请" ok-text="已安全保存" :cancel-button-props="{ style: { display: 'none' } }" @ok="createdUrl = ''; linkDelivery = 'manual_copy'" @after-close="createdUrl = ''; linkDelivery = 'manual_copy'">
    <a-alert v-if="linkDelivery === 'email_sent'" message="邮件服务已接受投递；此处仅提供一次性备用链接。" description="最终入箱情况由收件方邮件服务决定。系统只保存令牌摘要，请勿将备用链接放入公开群聊或工单。" type="success" show-icon />
    <a-alert v-else-if="linkDelivery === 'email_failed'" message="邀请已创建，但邮件投递失败。" description="请使用下方一次性备用链接通过可信渠道交付；链接关闭后不会再次显示。" type="warning" show-icon />
    <a-alert v-else message="链接只展示这一次，系统仅保存令牌摘要。请通过可信渠道发送，不要放入公开群聊或工单。" type="warning" show-icon />
    <a-input class="client-secret-field invitation-link-field" :value="createdUrl" readonly />
    <a-button block @click="copyInviteUrl">复制邀请链接</a-button>
  </a-modal>
</template>

<style scoped>
.invitation-link-field { margin: 14px 0 10px; }
</style>
