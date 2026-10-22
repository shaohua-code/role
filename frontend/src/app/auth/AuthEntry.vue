<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, toRefs, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { Rule } from 'ant-design-vue/es/form'
import { ApiRequestError, api, setToken } from '../../shared/services/api'
import { fetchAuthPublicCapabilities, type AuthPublicCapabilities } from '../../shared/services/authCapabilities'
import { validateReservedEmailDomain } from '../../shared/utils/emailValidation'
import { resolveThemeAssetUrl, themeCardShadow, themeChoice, themeFontFamily, themeHex, themeNumber, themeRgba } from '../../shared/theme'

type AuthenticatedSession = {
  access_token: string
  user: { email?: string; display_name?: string }
}

type LoginApplication = {
  application_name: string
  client_id?: string
  theme: Record<string, unknown>
  registration?: {
    available: boolean
    resend_cooldown_seconds: number
    terms_url: string
    privacy_url: string
    terms_version: string
    privacy_version: string
  } | null
}

type InvitationPreview = {
  email: string
  display_name: string
  tenant_name: string
  role_name: string
  expires_at: string
}

type ConsentPreview = {
  application_name: string
  tenant_name: string
  email: string
  scope: string[]
  expires_at: string
  theme: Record<string, unknown>
}

const props = defineProps<{
  loginReturnTo: string
  invitationToken: string
  consentTicket: string
  passwordResetToken: string
  readinessState: string
  readinessLoading: boolean
}>()
const { loginReturnTo, invitationToken, consentTicket, passwordResetToken, readinessState } = toRefs(props)
const emit = defineEmits<{
  authenticated: [session: AuthenticatedSession, redirectTo?: string]
  'refresh-readiness': []
}>()

const loginForm = reactive({ email: '', password: '' })
const resetRequestForm = reactive({ email: '' })
const resetCompleteForm = reactive({ password: '', confirmPassword: '' })
const invitationForm = reactive({ password: '' })
const registrationForm = reactive({ email: '', display_name: '', password: '', code: '', accepted_terms: false, accepted_privacy: false })
// 表单规则只改善即时反馈；API schema 与服务端策略仍是最终校验边界。
const emailFieldRules: Rule[] = [
  { required: true, type: 'email', max: 254, message: '请输入有效邮箱', trigger: 'blur' },
  { validator: validateReservedEmailDomain, trigger: 'blur' },
]
const loginRules: Record<string, Rule[]> = {
  email: emailFieldRules,
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const resetRequestRules: Record<string, Rule[]> = {
  email: emailFieldRules,
}
const invitationRules: Record<string, Rule[]> = {
  // 被邀请人可能已有 IAM 账号，因此这里只要求填写，不强制套用新账号密码长度。
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const resetCompleteRules: Record<string, Rule[]> = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 12, max: 128, message: '新密码长度须为 12 到 128 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: async (_rule, value) => {
        if (!value || value === resetCompleteForm.password) return
        throw new Error('两次输入的新密码不一致')
      },
      trigger: ['blur', 'change'],
    },
  ],
}
const registrationRequestRules: Record<string, Rule[]> = {
  email: emailFieldRules,
  display_name: [{ required: true, whitespace: true, max: 120, message: '请输入 1–120 个字符的姓名', trigger: 'blur' }],
}
const registrationVerifyRules: Record<string, Rule[]> = {
  code: [{ required: true, len: 6, pattern: /^\d{6}$/, message: '请输入邮件中的 6 位验证码', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const loginLoading = ref(false)
const forgotPasswordMode = ref(false)
const resetRequestLoading = ref(false)
const resetCompleteLoading = ref(false)
const resetRequestSent = ref(false)
const registerMode = ref(false)
const registrationCodeRequested = ref(false)
const registrationRequestLoading = ref(false)
const registrationVerifyLoading = ref(false)
const registrationResendSeconds = ref(0)
let registrationResendTimer: number | undefined
const invitationPreview = ref<InvitationPreview | null>(null)
const invitationLoading = ref(false)
const invitationAccepting = ref(false)
const consentPreview = ref<ConsentPreview | null>(null)
const consentLoading = ref(false)
const consentSubmitting = ref(false)
const loginApplication = ref<LoginApplication | null>(null)
const authCapabilities = ref<AuthPublicCapabilities | null>(null)

const oidcClientId = computed(() => {
  if (!loginReturnTo.value) return ''
  return new URLSearchParams(loginReturnTo.value.split('?', 2)[1] || '').get('client_id') || ''
})
// 管理台可绑定独立 OAuth client，复用同一套邮箱 OTP 注册流程。
const consoleRegistrationClientId = computed(() => authCapabilities.value?.console_registration?.client_id || '')
const registrationClientId = computed(() => oidcClientId.value || consoleRegistrationClientId.value)
const oidcTheme = computed(() => loginApplication.value?.theme || {})
const oidcFlow = computed(() => Boolean(loginReturnTo.value || consentTicket.value))
const registrationAvailable = computed(() => {
  const registration = loginApplication.value?.registration
  if (!registration?.available || !registrationClientId.value) return false
  if (oidcFlow.value) return oidcTheme.value.show_register === true
  return Boolean(consoleRegistrationClientId.value)
})
const passwordResetAvailable = computed(() => authCapabilities.value?.password_reset_available ?? true)
const consoleLoginNote = computed(() => {
  if (registrationAvailable.value) {
    return '可使用邮箱注册普通账号；注册不会自动获得平台管理员权限。平台管理员仍由部署引导或邀请创建。'
  }
  return '公开注册当前未开放，新用户请联系平台管理员获取邀请；首个平台管理员由部署引导命令创建。'
})
const oidcPrimaryColor = computed(() => /^#[\da-f]{6}$/i.test(String(oidcTheme.value.primary_color || ''))
  ? String(oidcTheme.value.primary_color) : '#756df2')
const oidcLogoUrl = computed(() => resolveThemeAssetUrl(oidcTheme.value.logo_url))
const oidcLogoStyle = computed(() => {
  const size = themeNumber(oidcTheme.value.logo_size, 32, 96, 40)
  return { background: oidcPrimaryColor.value, width: `${size}px`, height: `${size}px`, flex: `0 0 ${size}px` }
})
const oidcBackgroundStyle = computed(() => {
  const image = resolveThemeAssetUrl(oidcTheme.value.background_url)
  const overlay = themeNumber(oidcTheme.value.background_overlay, 0, 70, 27) / 100
  return {
    backgroundColor: themeHex(oidcTheme.value.background_color, '#f4f6fb'),
    backgroundPosition: themeChoice(oidcTheme.value.background_position, ['center', 'top', 'bottom', 'left', 'right'], 'center'),
    backgroundSize: themeChoice(oidcTheme.value.background_size, ['cover', 'contain', 'auto'], 'cover'),
    '--login-primary': oidcPrimaryColor.value,
    ...(image ? { backgroundImage: `linear-gradient(rgba(17,24,39,${overlay}),rgba(17,24,39,${overlay})),url("${image}")` } : {}),
  }
})
const oidcCardStyle = computed(() => {
  const padding = themeNumber(oidcTheme.value.card_padding, 12, 40, 20)
  return {
    width: `${themeNumber(oidcTheme.value.card_width, 320, 720, 420)}px`,
    maxWidth: '100%',
    borderRadius: `${themeNumber(oidcTheme.value.card_radius, 0, 32, 16)}px`,
    backgroundColor: themeRgba(oidcTheme.value.card_background_color, themeNumber(oidcTheme.value.card_opacity, 60, 100, 100), '#ffffff'),
    boxShadow: themeCardShadow(oidcTheme.value.card_shadow),
    color: themeHex(oidcTheme.value.text_color, '#202a3b'),
    fontFamily: themeFontFamily(oidcTheme.value.font_family),
    '--login-font-family': themeFontFamily(oidcTheme.value.font_family),
    '--login-title-color': themeHex(oidcTheme.value.title_color, '#202a3b'),
    '--login-text-color': themeHex(oidcTheme.value.text_color, '#202a3b'),
    '--login-card-padding': `${Math.round(padding * 0.8)}px ${padding}px`,
    '--login-input-radius': `${themeNumber(oidcTheme.value.input_radius, 0, 24, 6)}px`,
    '--login-button-radius': `${themeNumber(oidcTheme.value.button_radius, 0, 24, 6)}px`,
    '--login-button-height': `${themeNumber(oidcTheme.value.button_height, 40, 60, 40)}px`,
  }
})

const consentScopeText: Record<string, string> = {
  openid: '确认你的统一身份并完成登录',
  profile: '读取你的姓名和基础个人资料',
  email: '读取你的邮箱地址及邮箱验证状态',
  offline_access: '在你离开后通过刷新令牌保持登录（可随时撤销应用会话）',
}

async function loadAuthCapabilities(): Promise<void> {
  if (!authActionsAvailable.value) return
  try {
    authCapabilities.value = await fetchAuthPublicCapabilities()
    const consoleRegistration = authCapabilities.value.console_registration
    if (!oidcClientId.value && consoleRegistration) {
      loginApplication.value = {
        application_name: consoleRegistration.application_name,
        client_id: consoleRegistration.client_id,
        theme: {},
        registration: consoleRegistration.registration,
      }
    }
  } catch {
    authCapabilities.value = null
  }
}

async function loadLoginApplication(): Promise<void> {
  if (!authActionsAvailable.value || !registrationClientId.value) return
  if (!oidcClientId.value && consoleRegistrationClientId.value) return
  try {
    loginApplication.value = await api<LoginApplication>(`/oidc/login-context?client_id=${encodeURIComponent(registrationClientId.value)}`)
  } catch {
    message.error('无法读取应用登录配置，请联系管理员')
  }
}

function openForgotPasswordMode(): void {
  // 从登录页进入找回时预填邮箱，减少重复输入。
  if (loginForm.email.trim()) resetRequestForm.email = loginForm.email.trim()
  forgotPasswordMode.value = true
}

function openRegisterMode(): void {
  registerMode.value = true
}

async function login(): Promise<void> {
  if (!requireAuthService()) return
  loginLoading.value = true
  try {
    const result = await api<AuthenticatedSession>('/auth/login', {
      method: 'POST', body: JSON.stringify(loginForm),
    })
    loginForm.password = ''
    emit('authenticated', result, loginReturnTo.value || undefined)
    if (loginReturnTo.value) { window.location.assign(loginReturnTo.value); return }
    message.success('登录成功')
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 429 && error.retryAfterSeconds) {
      const waitSeconds = error.retryAfterSeconds
      const waitLabel = waitSeconds >= 60
        ? `${Math.ceil(waitSeconds / 60)} 分钟`
        : `${waitSeconds} 秒`
      message.warning(`登录尝试过于频繁，请 ${waitLabel}后重试。`)
    } else {
      message.error(error instanceof Error ? error.message : '登录失败')
    }
  } finally {
    loginLoading.value = false
  }
}

async function requestRegistrationCode(): Promise<void> {
  if (!requireAuthService()) return
  const registration = loginApplication.value?.registration
  if (!registrationClientId.value || !registrationAvailable.value || !registration) return
  const isResend = registrationCodeRequested.value
  registrationRequestLoading.value = true
  try {
    const result = await api<{ message: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        client_id: registrationClientId.value,
        email: registrationForm.email,
        display_name: registrationForm.display_name.trim(),
        // 公开登录页不展示勾选框；发送验证码即表示同意当前版本协议（与服务端 RegisterRequest 一致）。
        accepted_terms: true,
        accepted_privacy: true,
        terms_version: registration.terms_version,
        privacy_version: registration.privacy_version,
        terms_url: registration.terms_url,
        privacy_url: registration.privacy_url,
      }),
    })
    // 首次申请进入验证码步骤时确保密码从未在第一步收集；重发时保留用户已输入的密码。
    if (!isResend) registrationForm.password = ''
    else registrationForm.code = ''
    registrationCodeRequested.value = true
    registrationResendSeconds.value = registration.resend_cooldown_seconds || 60
    if (registrationResendTimer) window.clearInterval(registrationResendTimer)
    registrationResendTimer = window.setInterval(() => {
      registrationResendSeconds.value = Math.max(0, registrationResendSeconds.value - 1)
      if (registrationResendSeconds.value === 0 && registrationResendTimer) {
        window.clearInterval(registrationResendTimer)
        registrationResendTimer = undefined
      }
    }, 1000)
    message.success(result.message)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '暂时无法申请验证码')
  } finally {
    registrationRequestLoading.value = false
  }
}

async function verifyRegistrationCode(): Promise<void> {
  if (!requireAuthService()) return
  if (!registrationClientId.value || !registrationCodeRequested.value) return
  registrationVerifyLoading.value = true
  try {
    const result = await api<AuthenticatedSession>('/auth/register/verify', {
      method: 'POST',
      body: JSON.stringify({ client_id: registrationClientId.value, email: registrationForm.email, code: registrationForm.code, password: registrationForm.password }),
    })
    registrationForm.password = ''
    registrationForm.code = ''
    emit('authenticated', result, loginReturnTo.value || undefined)
    if (loginReturnTo.value) { window.location.assign(loginReturnTo.value); return }
    message.success('注册成功')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '验证码无效或已过期')
  } finally {
    registrationVerifyLoading.value = false
  }
}

// 登录入口只展示可操作的状态说明，不泄漏数据库 revision、连接串等内部细节。
const readinessMessages: Record<string, string> = {
  '检查中': '正在检查 IAM 服务状态，请稍后重试。',
  '数据库待迁移': '数据库结构尚未升级到当前版本，登录、注册、找回密码和应用授权暂不可用。请平台管理员按启动指南完成备份、审阅和迁移，然后重新检查。',
  '数据库不可用': 'IAM 数据库当前不可用，请稍后重试。',
  '迁移状态不可用': 'IAM 服务无法确认数据库版本，请联系平台管理员。',
  '后端未连接': '暂时无法连接 IAM 服务，请稍后重试。',
  '服务未就绪': 'IAM 服务暂时不可用，请稍后重试。',
}
const readinessMessage = computed(() => readinessMessages[readinessState.value]
  || 'IAM 服务暂时无法提供完整功能，请稍后重试。')

const authActionsAvailable = computed(() => readinessState.value === '服务正常')

// 客户端状态变化时阻止无效提交；API 端仍是最终就绪与授权边界。
function requireAuthService(): boolean {
  if (authActionsAvailable.value) return true
  message.warning(readinessMessage.value)
  emit('refresh-readiness')
  return false
}

async function requestPasswordReset(): Promise<void> {
  if (!requireAuthService()) return
  resetRequestLoading.value = true
  try {
    const result = await api<{ message: string }>('/auth/password-reset/request', {
      method: 'POST', body: JSON.stringify({ email: resetRequestForm.email }),
    })
    resetRequestSent.value = true
    message.success(result.message)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '暂时无法发送重置邮件')
  } finally {
    resetRequestLoading.value = false
  }
}

async function completePasswordReset(): Promise<void> {
  if (!requireAuthService()) return
  if (resetCompleteForm.password !== resetCompleteForm.confirmPassword) {
    message.error('两次输入的新密码不一致')
    return
  }
  resetCompleteLoading.value = true
  try {
    const result = await api<{ message: string }>('/auth/password-reset/complete', {
      method: 'POST',
      body: JSON.stringify({ token: passwordResetToken.value, new_password: resetCompleteForm.password }),
    })
    resetCompleteForm.password = ''
    resetCompleteForm.confirmPassword = ''
    setToken(null)
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
    message.success(result.message)
    window.location.assign(window.location.pathname)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '密码重置链接无效或已过期')
  } finally {
    resetCompleteLoading.value = false
  }
}

async function loadInvitation(): Promise<void> {
  if (!authActionsAvailable.value || !invitationToken.value) return
  invitationLoading.value = true
  try {
    invitationPreview.value = await api<InvitationPreview>('/auth/invitations/inspect', {
      method: 'POST', body: JSON.stringify({ token: invitationToken.value }),
    })
  } catch (error) {
    invitationPreview.value = null
    message.error(error instanceof Error ? error.message : '邀请链接无效或已过期')
  } finally {
    invitationLoading.value = false
  }
}

function returnToSignIn(): void {
  // 无效/过期链接仍保留在地址栏时，不让用户陷在没有继续路径的空状态。
  window.location.assign(window.location.pathname + window.location.search)
}

async function acceptInvitation(): Promise<void> {
  if (!requireAuthService()) return
  if (!invitationToken.value || !invitationPreview.value) return
  invitationAccepting.value = true
  try {
    const result = await api<AuthenticatedSession>('/auth/invitations/accept', {
      method: 'POST', body: JSON.stringify({ token: invitationToken.value, password: invitationForm.password }),
    })
    invitationForm.password = ''
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
    message.success('已加入租户')
    emit('authenticated', result)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '接受邀请失败')
  } finally {
    invitationAccepting.value = false
  }
}

async function loadConsent(): Promise<void> {
  if (!authActionsAvailable.value || !consentTicket.value) return
  consentLoading.value = true
  try {
    const preview = await api<ConsentPreview>('/oidc/consent/context', {
      method: 'POST', body: JSON.stringify({ ticket: consentTicket.value }),
    })
    consentPreview.value = preview
    loginApplication.value = { application_name: preview.application_name, theme: preview.theme || {} }
    // 票据已进入内存和短期服务端记录，立即从浏览器地址栏移除，降低截图/历史泄漏风险。
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
  } catch (error) {
    consentPreview.value = null
    message.error(error instanceof Error ? error.message : '无法读取应用授权请求')
  } finally {
    consentLoading.value = false
  }
}

async function decideConsent(approved: boolean): Promise<void> {
  if (!requireAuthService()) return
  if (!consentTicket.value || !consentPreview.value) return
  consentSubmitting.value = true
  try {
    const result = await api<{ redirect_to: string }>('/oidc/consent/decision', {
      method: 'POST', body: JSON.stringify({ ticket: consentTicket.value, approved }),
    })
    window.location.assign(result.redirect_to)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '提交授权选择失败')
  } finally {
    consentSubmitting.value = false
  }
}

watch(readinessState, state => {
  if (state !== '服务正常') return
  if (invitationToken.value) void loadInvitation()
  void loadAuthCapabilities()
  void loadLoginApplication()
  if (consentTicket.value) void loadConsent()
}, { immediate: true })

onMounted(() => {
  // 重置凭证只经 URL fragment 进入，马上移除地址栏，避免截图/历史记录继续暴露。
  if (passwordResetToken.value) {
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
  }
})

onUnmounted(() => {
  if (registrationResendTimer) window.clearInterval(registrationResendTimer)
})
</script>

<template>
    <a-layout class="login-shell min-h-screen" :class="oidcFlow ? ['oidc-login-shell', `layout-${themeChoice(oidcTheme.layout, ['centered', 'split', 'banner'], 'centered')}`] : []" :style="oidcFlow ? oidcBackgroundStyle : undefined">
      <a-layout-content class="relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      <div v-if="loginReturnTo && oidcTheme.layout === 'split'" class="oidc-brand-copy"><strong>{{ loginApplication?.application_name }}</strong><span>{{ String(oidcTheme.welcome_text || '安全访问您的工作空间') }}</span></div>
      <div v-if="loginReturnTo && oidcTheme.layout === 'banner'" class="oidc-login-banner"><strong>{{ loginApplication?.application_name || '安全登录' }}</strong></div>
      <a-card class="login-card" :class="[{ 'oidc-login-card': oidcFlow }, oidcFlow ? `position-${themeChoice(oidcTheme.card_position, ['left', 'center', 'right'], 'center')}` : '', oidcFlow ? `layout-${themeChoice(oidcTheme.layout, ['centered', 'split', 'banner'], 'centered')}` : '']" :bordered="false" :style="oidcFlow ? oidcCardStyle : undefined">
        <div class="login-brand"><span class="brand-mark" :style="oidcFlow ? oidcLogoStyle : undefined">{{ oidcFlow ? (loginApplication?.application_name?.slice(0, 2) || 'AP') : 'ID' }}<img v-if="oidcFlow && oidcLogoUrl" :src="oidcLogoUrl" alt="应用 Logo" /></span><div><strong>{{ oidcFlow ? loginApplication?.application_name || '应用登录' : '统一身份平台' }}</strong><small>{{ oidcFlow ? 'SECURE SIGN IN' : 'IDENTITY & ACCESS' }}</small></div></div>
        <a-alert
          v-if="readinessState !== '服务正常'"
          class="mb-4"
          type="warning"
          show-icon
          :message="`IAM 服务暂未就绪：${readinessState}`"
          :description="readinessMessage"
        >
          <template #action>
            <a-button type="link" size="small" :loading="readinessLoading" @click="emit('refresh-readiness')">重新检查</a-button>
          </template>
        </a-alert>
        <template v-if="invitationToken">
          <p class="eyebrow">TENANT INVITATION</p><h1>接受租户邀请</h1>
          <a-spin :spinning="invitationLoading"><template v-if="invitationPreview"><p class="login-subtitle">加入 {{ invitationPreview.tenant_name }}，并获得 {{ invitationPreview.role_name }} 角色。</p><a-alert class="invitation-summary" type="info" show-icon :message="invitationPreview.email" :description="`邀请将于 ${new Date(invitationPreview.expires_at).toLocaleString()} 过期`" /><a-form :model="invitationForm" :rules="invitationRules" layout="vertical" @finish="acceptInvitation"><a-form-item label="密码" name="password" help="新账号请设置至少 12 位密码；已有账号请输入当前密码以绑定原身份。"><a-input-password v-model:value="invitationForm.password" size="large" autocomplete="new-password" :maxlength="128" /></a-form-item><a-button type="primary" html-type="submit" size="large" block :loading="invitationAccepting" :disabled="!authActionsAvailable">接受邀请并登录</a-button></a-form></template><template v-else-if="!invitationLoading && authActionsAvailable"><a-empty description="邀请链接无效或已过期" /><a-button type="link" block @click="returnToSignIn">返回登录</a-button></template></a-spin>
        </template>
        <template v-else-if="consentTicket">
          <p class="eyebrow">APPLICATION AUTHORIZATION</p><h1>确认应用授权</h1>
          <a-spin :spinning="consentLoading"><template v-if="consentPreview"><p class="login-subtitle"><strong>{{ consentPreview.application_name }}</strong>（{{ consentPreview.tenant_name }}）请求访问你的身份信息。</p><a-alert class="invitation-summary" type="info" show-icon :message="consentPreview.email" description="请核对应用和信息范围，再决定是否继续。" /><div class="consent-scope-list"><div v-for="scope in consentPreview.scope" :key="scope"><a-tag color="blue">{{ scope }}</a-tag><span>{{ consentScopeText[scope] || '访问此范围的信息' }}</span></div></div><div class="consent-expiry">本次授权请求将在 {{ new Date(consentPreview.expires_at).toLocaleTimeString() }} 过期。</div><div class="consent-actions"><a-button size="large" @click="decideConsent(false)" :loading="consentSubmitting" :disabled="!authActionsAvailable">拒绝</a-button><a-button type="primary" size="large" :loading="consentSubmitting" :disabled="!authActionsAvailable" @click="decideConsent(true)">同意并继续</a-button></div></template><template v-else-if="!consentLoading && authActionsAvailable"><a-empty description="授权请求无效、已过期或登录会话已失效" /><a-button type="link" block @click="returnToSignIn">返回登录中心</a-button></template></a-spin>
        </template>
        <template v-else-if="passwordResetToken">
          <p class="eyebrow">PASSWORD RECOVERY</p><h1>设置新密码</h1>
          <p class="login-subtitle">设置至少 12 位的新密码。IAM 会立即拒绝旧令牌并撤销 SSO 刷新令牌。已建立的业务系统本地会话需由该系统单独登出；未做 IAM 在线鉴权的服务可能在旧访问令牌到期前仍接受该令牌（开发默认 30 分钟，生产默认 10 分钟）。</p>
          <a-form :model="resetCompleteForm" :rules="resetCompleteRules" layout="vertical" @finish="completePasswordReset">
            <a-form-item label="新密码" name="password"><a-input-password v-model:value="resetCompleteForm.password" size="large" autocomplete="new-password" :minlength="12" :maxlength="128" /></a-form-item>
            <a-form-item label="再次输入新密码" name="confirmPassword"><a-input-password v-model:value="resetCompleteForm.confirmPassword" size="large" autocomplete="new-password" :minlength="12" :maxlength="128" /></a-form-item>
            <a-button type="primary" html-type="submit" size="large" block :loading="resetCompleteLoading" :disabled="!authActionsAvailable">重置密码</a-button>
          </a-form>
        </template>
        <template v-else-if="registerMode">
          <p class="eyebrow">{{ oidcFlow ? 'CREATE YOUR ACCOUNT' : '邮箱注册' }}</p>
          <h1 :style="{ color: themeHex(oidcTheme.title_color, '#202a3b') }">{{ oidcFlow ? `注册 ${loginApplication?.application_name || '应用'}` : '创建你的账号' }}</h1>
          <p class="login-subtitle">{{ oidcFlow ? '验证邮箱后即可创建账号，仅获得此应用配置的基础角色。' : '验证邮箱后即可登录控制台；不会自动获得平台管理员权限。' }}</p>
          <a-form v-if="!registrationCodeRequested" :model="registrationForm" :rules="registrationRequestRules" layout="vertical" @finish="requestRegistrationCode">
            <a-form-item label="邮箱地址" name="email"><a-input v-model:value="registrationForm.email" type="email" size="large" autocomplete="email" :maxlength="254" placeholder="name@example.com" /></a-form-item>
            <a-form-item label="姓名" name="display_name"><a-input v-model:value="registrationForm.display_name" size="large" autocomplete="name" :maxlength="120" placeholder="如何称呼你" /></a-form-item>
            <p v-if="loginApplication?.registration?.terms_url && loginApplication?.registration?.privacy_url" class="registration-legal-hint">
              点击发送即表示你已阅读并同意
              <a :href="loginApplication.registration.terms_url" target="_blank" rel="noopener noreferrer">用户协议</a>
              与
              <a :href="loginApplication.registration.privacy_url" target="_blank" rel="noopener noreferrer">隐私政策</a>。
            </p>
            <a-button type="primary" html-type="submit" size="large" block :loading="registrationRequestLoading" :disabled="!authActionsAvailable" :style="{ background: oidcPrimaryColor, borderColor: oidcPrimaryColor }">发送邮箱验证码</a-button>
          </a-form>
          <a-form v-else :model="registrationForm" :rules="registrationVerifyRules" layout="vertical" @finish="verifyRegistrationCode">
            <a-alert class="invitation-summary" type="info" show-icon message="如果该邮箱可用于注册，验证码会发送到邮箱。" description="请检查垃圾邮件；页面倒计时结束后可重新申请。验证邮箱后，新用户设置至少 12 位密码；已有 IAM 账号输入当前密码，原密码不会被修改。" />
            <a-form-item label="邮箱验证码" name="code"><a-input v-model:value="registrationForm.code" size="large" inputmode="numeric" autocomplete="one-time-code" :maxlength="6" placeholder="请输入 6 位验证码" /></a-form-item>
            <a-form-item label="密码" name="password" help="新用户设置至少 12 位密码；已有 IAM 账号输入当前密码，原密码不会被修改。"><a-input-password v-model:value="registrationForm.password" size="large" autocomplete="current-password" :maxlength="128" /></a-form-item>
            <a-button type="primary" html-type="submit" size="large" block :loading="registrationVerifyLoading" :disabled="!authActionsAvailable" :style="{ background: oidcPrimaryColor, borderColor: oidcPrimaryColor }">验证并创建账号</a-button>
            <a-button type="link" block :disabled="!authActionsAvailable || registrationResendSeconds > 0 || registrationRequestLoading" :loading="registrationRequestLoading" @click="requestRegistrationCode">{{ registrationResendSeconds ? `${registrationResendSeconds} 秒后重新发送` : '重新发送验证码' }}</a-button>
          </a-form>
          <a-button type="link" block @click="registerMode = false; registrationCodeRequested = false; registrationForm.password = ''; registrationForm.code = ''; registrationResendSeconds = 0">返回登录</a-button>
        </template>
        <template v-else-if="forgotPasswordMode">
          <p class="eyebrow">PASSWORD RECOVERY</p><h1>忘记密码</h1>
          <p class="login-subtitle">输入注册邮箱；如果邮箱已登记且邮件服务可用，我们会发送一次性重置链接。</p>
          <a-alert v-if="!passwordResetAvailable" class="invitation-summary" type="warning" show-icon message="密码重置邮件服务暂未配置" description="请联系平台管理员配置 SMTP 后重试。" />
          <a-alert v-if="resetRequestSent" class="invitation-summary" type="success" show-icon message="请检查邮箱及垃圾邮件文件夹。为保护账号隐私，系统不会提示该邮箱是否已注册。" />
          <a-form :model="resetRequestForm" :rules="resetRequestRules" layout="vertical" @finish="requestPasswordReset">
            <a-form-item label="邮箱地址" name="email"><a-input v-model:value="resetRequestForm.email" type="email" size="large" autocomplete="email" :maxlength="254" placeholder="name@example.com" /></a-form-item>
            <a-button type="primary" html-type="submit" size="large" block :loading="resetRequestLoading" :disabled="!authActionsAvailable || !passwordResetAvailable">发送重置链接</a-button>
          </a-form>
          <a-button type="link" block @click="forgotPasswordMode = false">返回登录</a-button>
        </template>
        <template v-else><p class="eyebrow">{{ loginReturnTo ? 'APPLICATION SIGN IN' : 'ADMIN CONSOLE' }}</p><h1 :style="oidcFlow ? { color: themeHex(oidcTheme.title_color, '#202a3b') } : {}">{{ loginReturnTo ? String(oidcTheme.title || `登录 ${loginApplication?.application_name || '应用'}`) : '欢迎回来' }}</h1><p class="login-subtitle">{{ loginReturnTo ? String(oidcTheme.welcome_text || '使用邮箱与密码登录') : '使用邮箱与密码登录控制台' }}</p>
        <a-form :model="loginForm" :rules="loginRules" layout="vertical" @finish="login">
          <a-form-item label="邮箱地址" name="email"><a-input v-model:value="loginForm.email" type="email" size="large" autocomplete="username" :maxlength="254" placeholder="name@example.com" /></a-form-item>
          <a-form-item label="密码" name="password"><a-input-password v-model:value="loginForm.password" size="large" autocomplete="current-password" placeholder="请输入密码" /></a-form-item>
          <a-button type="primary" html-type="submit" size="large" block :loading="loginLoading" :disabled="!authActionsAvailable" :style="loginReturnTo ? { background: oidcPrimaryColor, borderColor: oidcPrimaryColor } : undefined">{{ loginReturnTo ? `登录 ${loginApplication?.application_name || '应用'}` : '登录控制台' }}</a-button>
        </a-form>
        <div class="login-secondary-actions">
          <a-button v-if="!oidcFlow || oidcTheme.show_forgot_password !== false" type="link" @click="openForgotPasswordMode">忘记密码？</a-button>
          <a-button v-if="registrationAvailable" type="link" @click="openRegisterMode">{{ oidcFlow ? '创建应用账号' : '邮箱注册' }}</a-button>
        </div>
        <div class="login-note">{{ loginReturnTo ? '登录后将安全返回原应用。' : consoleLoginNote }}</div>
        </template>
      </a-card>
      </a-layout-content>
    </a-layout>
</template>
