<script setup lang="ts">
// 应用树「更多」动作宿主：按菜单项打开编辑 / 轮换密钥 / 受信 / 启停 / 删除弹窗，不占用右侧 Tab。
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import { cachedHasAny, getCachedCapabilities } from '@/api/capabilities'
import AdminMonoValue from '@/components/AdminMonoValue.vue'

export type ApplicationMoreAction = 'edit' | 'rotateSecret' | 'trust' | 'status' | 'delete'

interface TenantOption {
  id: string
  name: string
  kind?: 'organization' | 'consumer'
  can_create_applications?: boolean
}

export interface SettingsApplication {
  id: string
  tenant_id: string
  name: string
  client_id: string
  permission_namespace: string
  description?: string | null
  trusted?: boolean
  status: 'active' | 'disabled'
  redirect_uris?: string[]
  post_logout_redirect_uris?: string[]
  registration_policy?: 'disabled' | 'open'
  registration_role_id?: string | null
  registration_terms_version?: string | null
  registration_privacy_version?: string | null
  backchannel_logout_uri?: string | null
  can_manage?: boolean
  can_rotate_secret?: boolean
}

interface RegistrationRole {
  id: string
  key: string
  name: string
}

const action = defineModel<ApplicationMoreAction | ''>('action', { default: '' })

const props = withDefaults(defineProps<{
  application: SettingsApplication | null
  tenants: TenantOption[]
  apiPrefix?: string
}>(), {
  apiPrefix: '/admin',
})

const emit = defineEmits<{
  changed: []
  deleted: []
}>()

const editOpen = ref(false)
const saving = ref(false)
const formRef = ref<{ validate: () => Promise<unknown> }>()
const registrationRoles = ref<RegistrationRole[]>([])
const secretOpen = ref(false)
const secretTitle = ref('保存轮换后的应用客户端密钥')
const oneTimeSecret = ref('')
const form = reactive({
  name: '',
  description: '',
  registration_policy: 'disabled' as 'disabled' | 'open',
  registration_role_id: '',
  registration_terms_version: '',
  registration_privacy_version: '',
  backchannel_logout_uri: '',
})

const rules = {
  name: [{ required: true, whitespace: true, max: 160, message: '请输入不超过 160 个字符的应用名称', trigger: 'blur' }],
  description: [{ max: 500, message: '说明不能超过 500 个字符', trigger: 'blur' }],
}

const tenantName = computed(() =>
  props.tenants.find(tenant => tenant.id === props.application?.tenant_id)?.name || '未知租户')

const isConsumerTenant = computed(() =>
  props.tenants.find(tenant => tenant.id === props.application?.tenant_id)?.kind === 'consumer')

const canSetTrust = computed(() => Boolean(getCachedCapabilities()?.platform_admin) && cachedHasAny(['button.apps.manage']))

function applicationPath(path: string): string {
  return `${props.apiPrefix}${path}`
}

function canCreateOnTenant(tenantId: string): boolean {
  if (getCachedCapabilities()?.platform_admin) return true
  return props.tenants.some(tenant => tenant.id === tenantId && tenant.can_create_applications === true)
}

function canManageApplication(application: SettingsApplication): boolean {
  if (application.can_manage === true) return true
  return cachedHasAny(['button.apps.manage']) && Boolean(getCachedCapabilities()?.platform_admin)
}

function canRotateSecret(application: SettingsApplication): boolean {
  if (application.can_rotate_secret === true) return true
  return cachedHasAny(['button.apps.secret']) && Boolean(getCachedCapabilities()?.platform_admin)
}

function canDeleteApplication(application: SettingsApplication): boolean {
  return canCreateOnTenant(application.tenant_id)
}

function hydrateForm(application: SettingsApplication): void {
  Object.assign(form, {
    name: application.name,
    description: application.description || '',
    registration_policy: application.registration_policy || 'disabled',
    registration_role_id: application.registration_role_id || '',
    registration_terms_version: application.registration_terms_version || '',
    registration_privacy_version: application.registration_privacy_version || '',
    backchannel_logout_uri: application.backchannel_logout_uri || '',
  })
}

async function openEdit(application: SettingsApplication): Promise<void> {
  if (!canManageApplication(application)) {
    message.warning('没有编辑该应用的权限')
    return
  }
  hydrateForm(application)
  editOpen.value = true
  try {
    registrationRoles.value = await api<RegistrationRole[]>(applicationPath(`/applications/${application.id}/registration-roles`))
  } catch (error) {
    registrationRoles.value = []
    message.error(error instanceof Error ? error.message : '无法读取应用可用的普通角色')
  }
}

async function saveApplication(): Promise<void> {
  const application = props.application
  if (!application || !canManageApplication(application)) return
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (form.registration_policy === 'open'
      && (!form.registration_role_id || !form.registration_terms_version.trim() || !form.registration_privacy_version.trim())) {
    message.warning('开放自助注册需要选择普通角色，并配置条款与隐私政策版本')
    return
  }
  if (form.registration_policy === 'open' && !isConsumerTenant.value) {
    message.warning('只有 ToC 消费租户可以开放自助注册；请先关闭注册并转换租户类型。')
    return
  }
  saving.value = true
  try {
    await api(applicationPath(`/applications/${application.id}`), {
      method: 'PATCH',
      body: JSON.stringify({
        name: form.name.trim(),
        description: form.description.trim() || null,
        registration_policy: form.registration_policy,
        registration_role_id: form.registration_role_id || null,
        registration_terms_version: form.registration_terms_version.trim() || null,
        registration_privacy_version: form.registration_privacy_version.trim() || null,
        backchannel_logout_uri: form.backchannel_logout_uri.trim() || null,
      }),
    })
    message.success('应用已更新')
    editOpen.value = false
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存应用失败')
  } finally {
    saving.value = false
  }
}

function showOneTimeSecret(secret: string, title: string): void {
  oneTimeSecret.value = secret
  secretTitle.value = title
  secretOpen.value = true
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

function confirmSecretRotation(application: SettingsApplication): void {
  if (!canRotateSecret(application)) {
    message.warning('没有轮换该应用密钥的权限')
    return
  }
  Modal.confirm({
    title: '立即轮换 Client Secret？',
    content: '旧密钥会立即失效。确认你能同步更新业务服务端的密钥配置；新密钥只展示一次，未保存将无法再次读取。',
    okText: '立即轮换',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        const result = await api<{ client_secret: string }>(applicationPath(`/applications/${application.id}/rotate-secret`), { method: 'POST' })
        showOneTimeSecret(result.client_secret, '保存轮换后的应用客户端密钥')
        emit('changed')
      } catch (error) {
        message.error(error instanceof Error ? error.message : '客户端密钥轮换失败')
      }
    },
  })
}

function confirmTrustChange(application: SettingsApplication): void {
  if (!canSetTrust.value) {
    message.warning('只有平台管理员可以修改受信状态')
    return
  }
  const trusted = !application.trusted
  Modal.confirm({
    title: trusted ? '确认设为受信应用？' : '确认撤销应用信任？',
    content: trusted
      ? '受信应用可跳过常规用户授权确认。只对经过审核的第一方应用开启。'
      : '撤销后新的授权请求将重新要求用户确认，并撤销该应用现有刷新会话。',
    okText: trusted ? '确认受信' : '撤销信任',
    cancelText: '取消',
    okButtonProps: trusted ? { danger: true } : undefined,
    onOk: async () => {
      try {
        await api(applicationPath(`/applications/${application.id}/trusted?trusted=${trusted}`), { method: 'PATCH' })
        message.success(trusted ? '应用已设为受信' : '已撤销应用信任，活动刷新会话已撤销')
        emit('changed')
      } catch (error) {
        message.error(error instanceof Error ? error.message : '修改应用信任状态失败')
      }
    },
  })
}

function changeStatus(application: SettingsApplication): void {
  if (!canManageApplication(application)) {
    message.warning('没有启停该应用的权限')
    return
  }
  const status = application.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(applicationPath(`/applications/${application.id}/status`), {
        method: 'PATCH',
        body: JSON.stringify({ expected_status: application.status, status }),
      })
      message.success(status === 'active' ? '应用已启用' : '应用已停用，现有刷新会话已撤销')
      emit('changed')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '更新应用状态失败')
    }
  }
  if (status === 'disabled') {
    Modal.confirm({
      title: '停用应用？',
      content: `停用“${application.name}”会阻止后续登录和令牌刷新；现有刷新会话会被撤销。`,
      okText: '停用应用',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: update,
    })
  } else {
    void update()
  }
}

function deleteApplication(application: SettingsApplication): void {
  if (!canDeleteApplication(application)) {
    message.warning('没有删除该应用的权限')
    return
  }
  Modal.confirm({
    title: `删除应用“${application.name}”？`,
    content: '将永久删除该应用及其主题、OIDC 客户端凭证、授权码与刷新令牌；该应用的角色会保留并退化为租户角色。此操作不可恢复。',
    okText: '永久删除',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await api(applicationPath(`/applications/${application.id}`), { method: 'DELETE' })
        message.success('应用已删除')
        emit('deleted')
      } catch (error) {
        message.error(error instanceof Error ? error.message : '删除应用失败')
      }
    },
  })
}

// 树「更多」点选后由父级写入 action；应用记录到达同一拍或下一拍再分发到对应弹窗。
watch([action, () => props.application], ([nextAction, application]) => {
  if (!nextAction || !application) return
  action.value = ''
  if (nextAction === 'edit') void openEdit(application)
  else if (nextAction === 'rotateSecret') confirmSecretRotation(application)
  else if (nextAction === 'trust') confirmTrustChange(application)
  else if (nextAction === 'status') changeStatus(application)
  else if (nextAction === 'delete') deleteApplication(application)
})
</script>

<template>
  <a-modal
    v-model:open="editOpen"
    :title="application ? `编辑应用：${application.name}` : '编辑应用'"
    ok-text="保存"
    cancel-text="取消"
    :confirm-loading="saving"
    :width="640"
    @ok="saveApplication"
  >
    <a-descriptions v-if="application" :column="1" size="small" bordered class="mb-4">
      <a-descriptions-item label="所属租户">{{ tenantName }}</a-descriptions-item>
      <a-descriptions-item label="Client ID">
        <AdminMonoValue :value="application.client_id" />
      </a-descriptions-item>
      <a-descriptions-item label="权限命名空间">
        <span class="font-mono text-xs text-[var(--color-text-secondary)]">{{ application.permission_namespace }}</span>
      </a-descriptions-item>
    </a-descriptions>
    <div v-if="application" class="mb-4">
      <div class="mb-2 text-[13px] font-semibold text-[var(--color-text-primary)]">登录回调（{{ application.redirect_uris?.length || 0 }}）</div>
      <div class="mb-3 flex flex-col gap-1">
        <code
          v-for="uri in application.redirect_uris || []"
          :key="uri"
          class="break-all rounded-[var(--radius-sm)] border border-solid border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 py-1 font-mono text-xs text-[var(--color-text-secondary)]"
        >{{ uri }}</code>
        <span v-if="!application.redirect_uris?.length" class="text-xs text-[var(--color-text-muted)]">未配置</span>
      </div>
      <div class="mb-2 text-[13px] font-semibold text-[var(--color-text-primary)]">登出回调（{{ application.post_logout_redirect_uris?.length || 0 }}）</div>
      <div class="flex flex-col gap-1">
        <code
          v-for="uri in application.post_logout_redirect_uris || []"
          :key="uri"
          class="break-all rounded-[var(--radius-sm)] border border-solid border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 py-1 font-mono text-xs text-[var(--color-text-secondary)]"
        >{{ uri }}</code>
        <span v-if="!application.post_logout_redirect_uris?.length" class="text-xs text-[var(--color-text-muted)]">未配置</span>
      </div>
    </div>
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item label="应用名称" name="name">
        <a-input v-model:value="form.name" :maxlength="160" />
      </a-form-item>
      <a-form-item label="描述" name="description">
        <a-textarea v-model:value="form.description" :rows="2" :maxlength="500" />
      </a-form-item>
      <a-divider orientation="left">ToC 用户自助注册</a-divider>
      <a-alert
        class="mb-4"
        :message="isConsumerTenant ? '开放注册还要求全局 ALLOW_PUBLIC_REGISTRATION、SMTP、已发布登录主题的注册入口及用户协议/隐私链接同时可用。' : '当前为组织/企业租户，后端禁止公开注册。请先关闭注册，再将租户显式转换为 ToC 消费租户。'"
        type="info"
        show-icon
      />
      <a-form-item label="注册策略">
        <a-select v-model:value="form.registration_policy">
          <a-select-option value="disabled">关闭（默认）</a-select-option>
          <a-select-option value="open" :disabled="!isConsumerTenant">允许用户自助注册</a-select-option>
        </a-select>
      </a-form-item>
      <template v-if="form.registration_policy === 'open'">
        <a-form-item label="新用户默认角色">
          <a-select
            v-model:value="form.registration_role_id"
            :options="registrationRoles.map(role => ({ value: role.id, label: `${role.name}（${role.key}）` }))"
            placeholder="选择当前应用的普通角色"
          />
        </a-form-item>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <a-form-item label="用户协议版本">
            <a-input v-model:value="form.registration_terms_version" :maxlength="80" placeholder="例如 2026-10" />
          </a-form-item>
          <a-form-item label="隐私政策版本">
            <a-input v-model:value="form.registration_privacy_version" :maxlength="80" placeholder="例如 2026-10" />
          </a-form-item>
        </div>
      </template>
      <a-divider orientation="left">单点登出联动（OIDC Back-Channel Logout）</a-divider>
      <a-form-item label="Back-Channel Logout 地址">
        <a-input
          v-model:value="form.backchannel_logout_uri"
          :maxlength="500"
          placeholder="https://app.example.com/backchannel-logout（留空表示未接入）"
        />
      </a-form-item>
      <a-alert type="info" show-icon message="编辑不会修改租户、Client ID、回调白名单、密钥和信任状态。" />
    </a-form>
  </a-modal>
  <a-modal
    v-model:open="secretOpen"
    :title="secretTitle"
    ok-text="我已安全保存"
    :cancel-button-props="{ style: { display: 'none' } }"
    @ok="clearOneTimeSecret"
    @after-close="clearOneTimeSecret"
  >
    <a-alert class="mb-3" type="warning" show-icon message="客户端密钥只展示这一次。请将它保存到业务系统服务端的密钥管理器，不要提交到前端代码或版本库。轮换密钥会让旧密钥立即失效。" />
    <a-input-password class="mb-3" :value="oneTimeSecret" readonly />
    <a-button block @click="copyOneTimeSecret">复制密钥</a-button>
  </a-modal>
</template>
