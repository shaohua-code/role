<script setup lang="ts">
import { reactive, ref } from 'vue'
import { api, setToken, getToken } from '@/api'

type RoleBrief = { key?: string; name?: string; kind?: string }
type MePayload = {
  email?: string
  display_name?: string
  roles?: RoleBrief[]
  capabilities?: {
    platform_codes?: string[]
    tenants?: { codes?: string[] }[]
    roles?: RoleBrief[]
  }
}

const form = reactive({ email: '', password: '' })
const loading = ref(false)
const error = ref('')
const me = ref<MePayload | null>(null)

function roleNames(payload: MePayload | null): string {
  const roles = payload?.roles?.length
    ? payload.roles
    : payload?.capabilities?.roles || []
  return roles
    .map((role) => role.name || role.key || '')
    .filter(Boolean)
    .join('、') || '（无角色）'
}

function permissionCodes(payload: MePayload | null): string[] {
  const caps = payload?.capabilities
  if (!caps) return []
  const set = new Set<string>()
  for (const code of caps.platform_codes || []) set.add(code)
  for (const tenant of caps.tenants || []) {
    for (const code of tenant.codes || []) set.add(code)
  }
  return Array.from(set).sort()
}

async function tryLogin(): Promise<void> {
  error.value = ''
  me.value = null
  loading.value = true
  try {
    // 与业务页同一契约：直连本平台 /auth/login，不经业务 SSO 包装
    const session = await api<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: form.email.trim(),
        password: form.password,
      }),
    })
    setToken(session.access_token)
    form.password = ''
    me.value = await api<MePayload>('/auth/me')
  } catch (err) {
    setToken(null)
    error.value = err instanceof Error ? err.message : '登录失败'
  } finally {
    loading.value = false
  }
}

function clearDemo(): void {
  me.value = null
  error.value = ''
  if (getToken()) {
    // 仅清演示态展示；不强制登出管理台当前会话（同一 token 存储）
  }
}
</script>

<template>
  <a-card :bordered="false" class="border border-[var(--color-border)]">
    <template #title>
      <div class="flex flex-col gap-1">
        <span class="text-base font-semibold text-[var(--color-text-primary)]">试用：页面直连 IAM 登录</span>
        <span class="text-sm font-normal text-[var(--color-text-secondary)]">
          请求目标为权限管理平台 <code class="rounded bg-slate-100 px-1 dark:bg-slate-800">POST /api/v1/auth/login</code>，
          再拉 <code class="rounded bg-slate-100 px-1 dark:bg-slate-800">GET /auth/me</code>（角色 / 权限编码）。不是业务后端 OIDC/SSO 包装。
        </span>
      </div>
    </template>

    <a-form layout="vertical" class="max-w-xl" @finish="tryLogin">
      <a-form-item label="邮箱" required>
        <a-input v-model:value="form.email" type="email" autocomplete="username" placeholder="例如 admin@example.com" />
      </a-form-item>
      <a-form-item label="密码" required>
        <a-input-password v-model:value="form.password" autocomplete="current-password" placeholder="平台账号密码" />
      </a-form-item>
      <a-space>
        <a-button type="primary" html-type="submit" :loading="loading">直连登录并查看 me</a-button>
        <a-button :disabled="!me" @click="clearDemo">清空结果</a-button>
      </a-space>
    </a-form>

    <a-alert v-if="error" type="error" show-icon class="mt-4" :message="error" />

    <div v-if="me" class="mt-4 grid gap-3">
      <a-descriptions bordered size="small" :column="1" title="登录结果">
        <a-descriptions-item label="显示名">{{ me.display_name || '—' }}</a-descriptions-item>
        <a-descriptions-item label="邮箱">{{ me.email || '—' }}</a-descriptions-item>
        <a-descriptions-item label="角色">{{ roleNames(me) }}</a-descriptions-item>
        <a-descriptions-item label="权限编码">
          <template v-if="permissionCodes(me).length">
            <a-tag v-for="code in permissionCodes(me).slice(0, 24)" :key="code" class="mb-1">{{ code }}</a-tag>
            <span v-if="permissionCodes(me).length > 24" class="text-[var(--color-text-secondary)]">
              等共 {{ permissionCodes(me).length }} 个
            </span>
          </template>
          <span v-else class="text-[var(--color-text-secondary)]">（无权限编码）</span>
        </a-descriptions-item>
      </a-descriptions>
      <a-typography-paragraph type="secondary" class="mb-0">
        角色名称、应用组织、权限说明在管理台请使用中文；上方「权限编码」列为稳定英文 code，供前端裁剪 UI。
      </a-typography-paragraph>
    </div>
  </a-card>
</template>
