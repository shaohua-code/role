<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/api'

// G16 用户详情聚合抽屉：单次拉取 /admin/users/{id}/profile，分区展示资料/成员关系/角色/会话/最近认证事件。
const open = defineModel<boolean>('open', { default: false })
const props = defineProps<{ userId: string }>()

interface UserProfile {
  id: string
  email: string | null
  display_name: string
  status: string
  auth_version: number
  created_at: string
  memberships: { tenant_id: string; tenant_name: string; tenant_status: string; membership_status: string; joined_at: string }[]
  role_bindings: { role_id: string; role_key: string; role_name: string; role_status: string; application_id: string | null; tenant_name: string; membership_status: string }[]
  sessions: { id: string; type: 'management' | 'oidc'; application_name: string; created_at: string; expires_at: string }[]
  recent_auth_events: { action: string; outcome: string; created_at: string }[]
}

const loading = ref(false)
const profile = ref<UserProfile | null>(null)
const errorText = ref('')

const statusLabels: Record<string, string> = { active: '启用', disabled: '停用', locked: '管理员锁定' }
const membershipLabels: Record<string, string> = { active: '在职', disabled: '已停用', departed: '已离职' }

// 每次打开按最新 userId 重新拉取；失败展示错误态而非空白。
watch([open, () => props.userId], async ([next, userId]) => {
  if (!next || !userId) return
  loading.value = true
  errorText.value = ''
  profile.value = null
  try {
    profile.value = await api<UserProfile>(`/admin/users/${userId}/profile`)
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '读取用户详情失败'
  } finally { loading.value = false }
})

// G23 联动：跳转审计页并携带 actor 深链，审计页会自动切「登录与认证」并预填查询。
function openLoginHistory(): void {
  window.location.hash = `#/audit?actor=${props.userId}`
  open.value = false
}

function formatTime(value: string): string {
  return value ? new Date(value).toLocaleString() : '—'
}
</script>

<template>
  <a-drawer v-model:open="open" title="用户详情" width="640" class="user-detail-drawer">
    <a-spin :spinning="loading">
      <a-alert v-if="errorText" type="error" show-icon :message="errorText" />
      <template v-else-if="profile">
        <!-- 基本资料 -->
        <h3 class="mb-2 mt-1 text-sm font-semibold">基本资料</h3>
        <a-descriptions bordered :column="2" size="small">
          <a-descriptions-item label="姓名" :span="2">{{ profile.display_name }}</a-descriptions-item>
          <a-descriptions-item label="邮箱" :span="2">{{ profile.email || '—' }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="profile.status === 'active' ? 'green' : profile.status === 'locked' ? 'orange' : 'default'">
              {{ statusLabels[profile.status] || profile.status }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="身份版本">v{{ profile.auth_version }}</a-descriptions-item>
          <a-descriptions-item label="创建时间" :span="2">{{ formatTime(profile.created_at) }}</a-descriptions-item>
        </a-descriptions>

        <!-- 租户成员关系 -->
        <h3 class="mb-2 mt-4 text-sm font-semibold">租户成员关系（{{ profile.memberships.length }}）</h3>
        <a-empty v-if="!profile.memberships.length" :image-style="{ height: '40px' }" description="未加入任何租户" />
        <div v-else class="grid gap-2">
          <div v-for="membership in profile.memberships" :key="membership.tenant_id"
            class="flex items-center justify-between rounded border border-[var(--color-border)] px-3 py-2 text-xs">
            <span class="min-w-0 truncate font-medium">{{ membership.tenant_name }}</span>
            <a-space :size="6">
              <a-tag :color="membership.membership_status === 'active' ? 'green' : membership.membership_status === 'departed' ? 'default' : 'orange'">
                {{ membershipLabels[membership.membership_status] || membership.membership_status }}
              </a-tag>
              <a-tag v-if="membership.tenant_status !== 'active'" color="default">租户已停用</a-tag>
            </a-space>
          </div>
        </div>

        <!-- 角色绑定 -->
        <h3 class="mb-2 mt-4 text-sm font-semibold">角色（{{ profile.role_bindings.length }}）</h3>
        <a-empty v-if="!profile.role_bindings.length" :image-style="{ height: '40px' }" description="暂无角色绑定" />
        <div v-else class="grid gap-2">
          <div v-for="binding in profile.role_bindings" :key="binding.role_id + binding.tenant_name"
            class="flex items-center justify-between rounded border border-[var(--color-border)] px-3 py-2 text-xs">
            <span class="min-w-0">
              <span class="font-medium">{{ binding.role_name }}</span>
              <span class="ml-2 font-mono text-[var(--color-text-muted)]">{{ binding.role_key }}</span>
            </span>
            <a-space :size="6">
              <span class="text-[var(--color-text-muted)]">{{ binding.tenant_name }}{{ binding.application_id ? ' · 应用角色' : '' }}</span>
              <a-tag v-if="binding.role_status !== 'active'" color="default">角色已停用</a-tag>
            </a-space>
          </div>
        </div>

        <!-- 活动会话 -->
        <h3 class="mb-2 mt-4 text-sm font-semibold">活动会话（{{ profile.sessions.length }}）</h3>
        <a-empty v-if="!profile.sessions.length" :image-style="{ height: '40px' }" description="没有可续期的活动会话" />
        <div v-else class="grid gap-2">
          <div v-for="session in profile.sessions" :key="session.id"
            class="flex items-center justify-between rounded border border-[var(--color-border)] px-3 py-2 text-xs">
            <span class="min-w-0 truncate">{{ session.application_name }}</span>
            <span class="shrink-0 text-[var(--color-text-muted)]">{{ formatTime(session.created_at) }}</span>
          </div>
        </div>

        <!-- 最近认证事件 -->
        <h3 class="mb-2 mt-4 text-sm font-semibold">最近认证事件（{{ profile.recent_auth_events.length }}）</h3>
        <a-empty v-if="!profile.recent_auth_events.length" :image-style="{ height: '40px' }" description="暂无认证事件" />
        <div v-else class="grid gap-1">
          <div v-for="(event, index) in profile.recent_auth_events" :key="index"
            class="flex items-center justify-between rounded border border-[var(--color-border)] px-3 py-1.5 text-xs">
            <a-tag class="font-mono" :color="event.outcome === 'success' ? 'green' : event.outcome === 'denied' ? 'red' : 'default'">{{ event.action }}</a-tag>
            <span class="text-[var(--color-text-muted)]">{{ formatTime(event.created_at) }}</span>
          </div>
        </div>

        <!-- G23 联动：跳审计页查看全量登录记录 -->
        <a-button class="mt-4" block @click="openLoginHistory">在审计日志中查看全部登录记录 →</a-button>
      </template>
    </a-spin>
  </a-drawer>
</template>
