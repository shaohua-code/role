<script setup lang="ts">
// 个人信息页（/profile）：登录即可达的自助页，不占侧栏，入口在顶栏用户菜单。
// 数据用 /auth/me 现拉（含 status / created_at / roles / capabilities，比壳层 currentUser 更全）；
// 管理码不判权——本页只展示与编辑本人资料，不触碰任何管理数据。
// 视觉口径：轻奢黑白灰，语义色仅用于状态徽标；层次靠 hairline 分割 + 信息条 + 图标锚点。
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  AppstoreOutlined,
  BankOutlined,
  EditOutlined,
  IdcardOutlined,
  LockOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from '@/plugins/icons'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminMonoValue from '@/components/AdminMonoValue.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import { api } from '@/api'
import { OPERATOR_SCOPE_LABELS, type ActorRole, type Capabilities, type OperatorScope } from '@/api/capabilities'

const emit = defineEmits<{
  openChangePassword: []
  /** 编辑保存成功后通知壳层同步顶栏展示名 */
  profileUpdated: [displayName: string]
}>()

// 租户名回查字典由壳层透传（平台模式为全量目录；租户模式为本人可达租户，必含角色挂靠租户）
const props = withDefaults(defineProps<{
  tenants?: Array<{ id: string; name: string }>
}>(), {
  tenants: () => [],
})

// /auth/me 契约（MeResponse）：roles 与 capabilities.roles 同构，复用 ActorRole 类型
interface MeProfile {
  id: string
  email?: string | null
  display_name?: string | null
  status: string
  created_at?: string | null
  roles: ActorRole[]
  capabilities?: Capabilities
}

const loading = ref(false)
const loadFailed = ref(false)
const profile = ref<MeProfile | null>(null)

// 头像首字母：优先展示名，其次邮箱首字符（与顶栏口径一致）
const userInitial = computed(() =>
  (profile.value?.display_name || profile.value?.email || '').trim().charAt(0).toUpperCase() || '·')

// 账号状态徽标：语义色是全站唯一高饱和点缀，仅此处用色
const STATUS_META: Record<string, { label: string; color: string }> = {
  active: { label: '正常', color: 'success' },
  disabled: { label: '已停用', color: 'default' },
  locked: { label: '已锁定', color: 'error' },
}
const statusMeta = computed(() => STATUS_META[profile.value?.status ?? ''] ?? { label: profile.value?.status || '—', color: 'default' })

// 角色类型徽标文案与图标锚点（roles.kind：platform / tenant / application）
const ROLE_KIND_META: Record<string, { label: string; icon: typeof BankOutlined }> = {
  platform: { label: '平台角色', icon: SafetyCertificateOutlined },
  tenant: { label: '租户角色', icon: BankOutlined },
  application: { label: '应用角色', icon: AppstoreOutlined },
}

// 有效角色摘要：无 name 时回退 key；补租户 / 应用展示名
const roleRows = computed(() => (profile.value?.roles ?? []).map(role => {
  const kindMeta = ROLE_KIND_META[role.kind] ?? { label: role.kind, icon: UserOutlined }
  return {
    ...role,
    kindLabel: kindMeta.label,
    kindIcon: kindMeta.icon,
    name: role.name || role.key,
    tenantName: props.tenants.find(tenant => tenant.id === role.tenant_id)?.name || role.tenant_id,
  }
}))

// 授权范围（capabilities.scope）与持有管理码数量：只作摘要展示，裁 UI 仍由壳层判权
const scopeLabel = computed(() => {
  const scope = profile.value?.capabilities?.scope
  return scope ? OPERATOR_SCOPE_LABELS[scope as OperatorScope] : '—'
})
const heldCodeCount = computed(() => {
  const capabilities = profile.value?.capabilities
  if (!capabilities) return 0
  const codes = new Set<string>(capabilities.platform_codes)
  for (const tenant of capabilities.tenants) {
    for (const code of tenant.codes) codes.add(code)
    for (const application of tenant.applications) {
      for (const code of application.codes) codes.add(code)
    }
  }
  return codes.size
})

// created_at 等只读字段的统一格式
function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

async function loadProfile(): Promise<void> {
  loading.value = true
  loadFailed.value = false
  try {
    profile.value = await api<MeProfile>('/auth/me')
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(loadProfile)

// ---- 编辑资料（仅展示名；邮箱 / 手机号是登录标识，变更走管理员与验证通道） ----
const editOpen = ref(false)
const saving = ref(false)
const editFormRef = ref<{ validate: () => Promise<unknown>; resetFields: () => void }>()
const editForm = reactive({ display_name: '' })

// 校验规则：strip 后非空（与服务端空白守卫同口径），长度对齐契约 1–120
const editRules = {
  display_name: [
    { required: true, whitespace: true, message: '请输入展示名', trigger: 'blur' },
    { max: 120, message: '展示名最长 120 个字符', trigger: 'blur' },
  ],
}

// 每次打开用当前展示名回填，关闭由 antd 关闭钩子重置校验状态
function openEdit(): void {
  editForm.display_name = profile.value?.display_name || ''
  editOpen.value = true
}

async function submitEdit(): Promise<void> {
  try { await editFormRef.value?.validate() } catch { return }
  saving.value = true
  try {
    const updated = await api<{ display_name: string }>('/auth/me', {
      method: 'PATCH',
      body: JSON.stringify({ display_name: editForm.display_name.trim() }),
    })
    if (profile.value) profile.value.display_name = updated.display_name
    emit('profileUpdated', updated.display_name)
    message.success('资料已更新')
    editOpen.value = false
  } catch (error) {
    message.error(error instanceof Error ? error.message : '更新资料失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="flex w-full min-w-0 flex-col gap-4">
    <AdminPageHeader
      eyebrow="ACCOUNT PROFILE"
      title="个人信息"
      subtitle="查看并维护当前登录账号的资料、角色与授权范围；登录标识（邮箱 / 手机号）变更由管理员统一管理。"
    />

    <!-- 加载失败：给出重试路径，不伪装成空态 -->
    <a-card v-if="loadFailed" :bordered="false">
      <a-alert
        type="error"
        show-icon
        message="个人信息暂时无法读取"
      >
        <template #description>
          <a-space :size="8">
            <a-button size="small" :loading="loading" @click="loadProfile">重试</a-button>
          </a-space>
        </template>
      </a-alert>
    </a-card>

    <template v-else>
      <!-- 身份卡：头像 + 姓名 / 状态 + 邮箱，右侧唯一主操作「编辑资料」；底部信息条承载只读标识 -->
      <a-card :bordered="false" :loading="loading" class="overflow-hidden" :body-style="{ padding: '0' }">
        <div class="flex flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center">
          <a-avatar
            v-if="userInitial"
            :size="72"
            shape="square"
            class="shrink-0 rounded-lg text-2xl font-semibold"
            :style="{ background: 'var(--color-brand)', color: 'var(--color-bg-elevated)' }"
          >{{ userInitial }}</a-avatar>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h4 class="m-0 min-w-0 truncate text-xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                {{ profile?.display_name || '未设置展示名' }}
              </h4>
              <a-tag :color="statusMeta.color" class="mr-0">{{ statusMeta.label }}</a-tag>
            </div>
            <p class="mb-0 mt-1.5 truncate text-sm text-[var(--color-text-secondary)]">
              {{ profile?.email || '未绑定邮箱' }}
            </p>
          </div>
          <div class="shrink-0">
            <a-button type="primary" @click="openEdit">
              <template #icon><EditOutlined /></template>
              编辑资料
            </a-button>
          </div>
        </div>
        <!-- 信息条：登录标识与建档时间，mono 值可复制（两段式结构压缩空洞留白） -->
        <div class="flex flex-wrap items-center gap-x-8 gap-y-2 border-t border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-6 py-3">
          <span class="inline-flex min-w-0 items-center gap-2 text-xs text-[var(--color-text-muted)]">
            用户 ID
            <AdminMonoValue v-if="profile?.id" :value="profile.id" max-width="240px" />
            <span v-else>—</span>
          </span>
          <span class="inline-flex min-w-0 items-center gap-2 text-xs text-[var(--color-text-muted)]">
            创建时间
            <span class="text-[var(--color-text-secondary)]">{{ formatDateTime(profile?.created_at) }}</span>
          </span>
        </div>
      </a-card>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <!-- 管理范围：范围档位 + 持有管理码数量（仅展示，不参与判权） -->
        <a-card :bordered="false" title="管理范围">
          <div class="flex flex-col">
            <div class="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2.5">
              <span class="text-sm text-[var(--color-text-secondary)]">授权范围</span>
              <a-tag class="mr-0" color="default">{{ scopeLabel }}</a-tag>
            </div>
            <div class="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2.5">
              <span class="text-sm text-[var(--color-text-secondary)]">持有管理码</span>
              <span class="text-sm font-medium text-[var(--color-text-primary)]">{{ heldCodeCount }} 项</span>
            </div>
            <div class="flex items-center justify-between gap-3 py-2.5">
              <span class="text-sm text-[var(--color-text-secondary)]">平台管理员</span>
              <span class="text-sm font-medium text-[var(--color-text-primary)]">
                {{ profile?.capabilities?.platform_admin ? '是' : '否' }}
              </span>
            </div>
          </div>
          <p class="mb-0 mt-2 border-t border-[var(--color-border)] pt-3 text-xs leading-relaxed text-[var(--color-text-muted)]">
            管理码由角色派生并按租户 / 应用隔离；实际可操作范围以服务端鉴权为准。
          </p>
        </a-card>

        <!-- 安全：改密入口（次级按钮）与会话 / 审计口径说明 -->
        <a-card :bordered="false" title="安全">
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="m-0 text-sm font-medium text-[var(--color-text-primary)]">登录密码</p>
              <p class="mb-0 mt-1 text-xs leading-relaxed text-[var(--color-text-muted)]">
                修改成功后所有登录会话将被撤销（包括当前设备），需重新登录。
              </p>
            </div>
            <a-button class="shrink-0" @click="emit('openChangePassword')">
              <template #icon><LockOutlined /></template>
              修改密码
            </a-button>
          </div>
          <p class="mb-0 mt-3 border-t border-[var(--color-border)] pt-3 text-xs leading-relaxed text-[var(--color-text-muted)]">
            登录与关键管理操作由服务端鉴权并写入审计日志，可在「审计与验证」中查询。
          </p>
        </a-card>
      </div>

      <!-- 有效角色：多角色并集生效；图标容器提供视觉锚点，行悬浮可扫描 -->
      <a-card :bordered="false">
        <template #title>
          <span class="inline-flex items-center gap-2">
            <IdcardOutlined class="text-[var(--color-text-secondary)]" />
            有效角色
            <a-tag class="mr-0" color="default">{{ roleRows.length }}</a-tag>
          </span>
        </template>
        <div v-if="roleRows.length" class="flex flex-col">
          <div
            v-for="role in roleRows"
            :key="`${role.key}-${role.tenant_id}-${role.application_id ?? ''}`"
            class="flex min-w-0 items-center gap-3 border-b border-[var(--color-border)] px-2 py-3 transition-colors last:border-b-0 hover:bg-[var(--color-row-hover)]"
          >
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--color-bg-subtle)] text-sm text-[var(--color-text-secondary)] ring-1 ring-[var(--color-border)]">
              <component :is="role.kindIcon" />
            </span>
            <span class="min-w-0 truncate text-sm font-medium text-[var(--color-text-primary)]">{{ role.name }}</span>
            <a-tag class="mr-0 shrink-0" color="default">{{ role.kindLabel }}</a-tag>
            <span class="ml-auto hidden min-w-0 truncate text-xs text-[var(--color-text-muted)] md:inline">
              租户：{{ role.tenantName }}
              <template v-if="role.application_id"> · 应用 {{ role.application_id.slice(0, 8) }}</template>
            </span>
          </div>
        </div>
        <AdminEmpty v-else emoji="🪪" description="暂无有效角色；请联系管理员分配" />
      </a-card>
    </template>

    <!-- 编辑资料弹窗：仅展示名；关闭后重置表单状态（§9 惯例） -->
    <a-modal
      v-model:open="editOpen"
      title="编辑资料"
      ok-text="保存"
      cancel-text="取消"
      :confirm-loading="saving"
      @ok="submitEdit"
      @after-close="editFormRef?.resetFields()"
    >
      <a-form ref="editFormRef" :model="editForm" :rules="editRules" layout="vertical">
        <a-form-item label="展示名" name="display_name" extra="顶栏与审计展示均使用该名称；邮箱等登录标识请联系管理员变更。">
          <a-input
            v-model:value="editForm.display_name"
            :maxlength="120"
            show-count
            placeholder="请输入展示名"
            @press-enter="submitEdit"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
