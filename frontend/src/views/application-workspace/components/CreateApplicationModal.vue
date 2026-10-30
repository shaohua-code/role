<script setup lang="ts">
// 应用工作台新建弹窗：从原应用管理列表抽出创建字段，不新造 API。
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'

interface TenantOption {
  id: string
  name: string
  status: string
  kind?: 'organization' | 'consumer'
}

const open = defineModel<boolean>('open', { default: false })

const props = withDefaults(defineProps<{
  apiPrefix?: string
  tenants: TenantOption[]
  presetTenantId?: string
}>(), {
  apiPrefix: '/admin',
  presetTenantId: '',
})

const emit = defineEmits<{
  created: [payload: { id: string }]
}>()

const saving = ref(false)
const formRef = ref<{ validate: () => Promise<unknown> }>()
const secretOpen = ref(false)
const oneTimeSecret = ref('')
const form = reactive({
  tenant_id: '',
  client_id: '',
  name: '',
  description: '',
  permission_namespace: '',
  redirect_uris: '',
  post_logout_redirect_uris: '',
})

const tenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.status === 'active')
  .map(tenant => ({
    value: tenant.id,
    label: `${tenant.name} · ${tenant.kind === 'consumer' ? 'ToC 消费' : '组织/企业'}`,
  })))

const rules = {
  tenant_id: [{ required: true, message: '请选择所属租户', trigger: 'change' }],
  client_id: [
    { required: true, message: '请输入 Client ID', trigger: 'blur' },
    { min: 3, max: 160, pattern: /^[A-Za-z0-9._-]+$/, message: 'Client ID 为 3–160 位字母、数字、点、下划线或连字符', trigger: 'blur' },
  ],
  name: [{ required: true, whitespace: true, max: 160, message: '请输入不超过 160 个字符的应用名称', trigger: 'blur' }],
  description: [{ max: 500, message: '说明不能超过 500 个字符', trigger: 'blur' }],
}

// 与后端 default_namespace_from_client_id 对齐：取 Client ID 首段分隔符前的字母数字段
function defaultNamespaceFromClientId(clientId: string): string {
  const raw = clientId.trim()
  if (!raw) return ''
  const segment = raw.split(/[._-]/)[0]?.toLowerCase() || ''
  return /^[a-z0-9][a-z0-9._-]{0,99}$/.test(segment) ? segment : ''
}

function parseLines(value: string): string[] {
  return value.split(/\r?\n/).map(item => item.trim()).filter(Boolean)
}

function isSafeRedirectUri(value: string): boolean {
  try {
    const url = new URL(value)
    if (url.hash || url.username || url.password) return false
    return url.protocol === 'https:' || (url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))
  } catch {
    return false
  }
}

function resetForm(): void {
  const preset = props.presetTenantId
  Object.assign(form, {
    tenant_id: tenantOptions.value.some(item => item.value === preset)
      ? preset
      : (tenantOptions.value[0]?.value || ''),
    client_id: '',
    name: '',
    description: '',
    permission_namespace: '',
    redirect_uris: '',
    post_logout_redirect_uris: '',
  })
}

async function saveApplication(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const redirectUris = parseLines(form.redirect_uris)
  const logoutUris = parseLines(form.post_logout_redirect_uris)
  if (!redirectUris.length) {
    message.warning('至少登记一个登录回调地址；应用创建后当前接口不允许修改回调白名单。')
    return
  }
  if (redirectUris.length > 20 || logoutUris.length > 20) {
    message.warning('每类回调地址最多登记 20 个')
    return
  }
  if ([...redirectUris, ...logoutUris].some(uri => !isSafeRedirectUri(uri))) {
    message.warning('回调地址必须使用 HTTPS；本地开发仅允许 localhost 或 127.0.0.1 的 HTTP 地址，且不能包含凭据或片段')
    return
  }
  saving.value = true
  try {
    const result = await api<{ id: string; client_secret?: string }>(`${props.apiPrefix}/applications`, {
      method: 'POST',
      body: JSON.stringify({
        tenant_id: form.tenant_id,
        client_id: form.client_id.trim(),
        name: form.name.trim(),
        description: form.description.trim() || null,
        redirect_uris: redirectUris,
        post_logout_redirect_uris: logoutUris,
        permission_namespace: form.permission_namespace.trim() || defaultNamespaceFromClientId(form.client_id) || undefined,
      }),
    })
    message.success('应用已创建')
    open.value = false
    emit('created', { id: result.id })
    if (result.client_secret) {
      oneTimeSecret.value = result.client_secret
      secretOpen.value = true
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建应用失败')
  } finally {
    saving.value = false
  }
}

function clearOneTimeSecret(): void {
  oneTimeSecret.value = ''
}

async function copyOneTimeSecret(): Promise<void> {
  try {
    await navigator.clipboard.writeText(oneTimeSecret.value)
    message.success('密钥已复制')
  } catch {
    message.error('复制失败，请手动复制')
  }
}

watch(() => form.client_id, clientId => {
  const derived = defaultNamespaceFromClientId(clientId)
  if (derived) form.permission_namespace = derived
})

watch(open, isOpen => {
  if (isOpen) resetForm()
})
</script>

<template>
  <a-modal
    v-model:open="open"
    title="新建应用"
    ok-text="创建"
    cancel-text="取消"
    :confirm-loading="saving"
    @ok="saveApplication"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item label="所属租户" name="tenant_id">
        <a-select v-model:value="form.tenant_id" :options="tenantOptions" placeholder="选择所属租户" />
      </a-form-item>
      <a-form-item label="Client ID" name="client_id">
        <a-input v-model:value="form.client_id" :maxlength="160" />
      </a-form-item>
      <a-form-item label="权限命名空间" required>
        <a-input v-model:value="form.permission_namespace" :maxlength="100" placeholder="默认随 Client ID 首段推导，创建后不可修改" />
      </a-form-item>
      <a-form-item label="登录回调地址（每行一个，最多 20 个）" required>
        <a-textarea v-model:value="form.redirect_uris" :rows="4" placeholder="https://app.example.com/auth/callback" />
      </a-form-item>
      <a-form-item label="退出回调地址（每行一个，最多 20 个）">
        <a-textarea v-model:value="form.post_logout_redirect_uris" :rows="3" placeholder="https://app.example.com/logout/callback" />
      </a-form-item>
      <a-form-item label="应用名称" name="name">
        <a-input v-model:value="form.name" :maxlength="160" />
      </a-form-item>
      <a-form-item label="描述" name="description">
        <a-textarea v-model:value="form.description" :rows="2" :maxlength="500" />
      </a-form-item>
      <a-alert type="warning" show-icon message="请核对回调白名单后再创建。新应用默认要求用户确认；Client Secret 只展示一次。回调地址创建后不可通过当前 API 修改。" />
    </a-form>
  </a-modal>
  <a-modal
    v-model:open="secretOpen"
    title="保存新建应用的客户端密钥"
    ok-text="我已安全保存"
    :cancel-button-props="{ style: { display: 'none' } }"
    @ok="clearOneTimeSecret"
    @after-close="clearOneTimeSecret"
  >
    <a-alert class="mb-3" type="warning" show-icon message="客户端密钥只展示这一次。请将它保存到业务系统服务端的密钥管理器，不要提交到前端代码或版本库。" />
    <a-input-password class="mb-3" :value="oneTimeSecret" readonly />
    <a-button block @click="copyOneTimeSecret">复制密钥</a-button>
  </a-modal>
</template>
