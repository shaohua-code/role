<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'
import { resolveThemeAssetUrl, themeCardShadow, themeChoice, themeFontFamily, themeHex, themeNumber, themeRgba } from '@/styles/theme'
import AdminPageHeader from '@/components/AdminPageHeader.vue'
import AdminColorField from '@/components/AdminColorField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'

interface ThemeConfig {
  title: string
  welcome_text: string
  primary_color: string
  background_color: string
  background_url: string
  logo_url: string
  layout: string
  card_position: string
  card_width: number
  card_radius: number
  background_position: string
  background_size: string
  background_overlay: number
  card_background_color: string
  card_opacity: number
  title_color: string
  text_color: string
  font_family: string
  logo_size: number
  card_shadow: string
  card_padding: number
  input_radius: number
  button_radius: number
  button_height: number
  show_register: boolean
  show_forgot_password: boolean
  terms_url: string
  privacy_url: string
}

// 主题历史版本行：GET /admin/themes 返回项，id 用于版本恢复端点定位
interface ThemeHistoryRow {
  id: string
  version: number
  status: string
  config: Record<string, unknown>
  created_at: string
}

const props = defineProps<{
  active: boolean
  applications: Record<string, unknown>[]
  selectedApplicationId: string
}>()

const emit = defineEmits<{
  'update:selectedApplicationId': [id: string]
  navigate: [page: 'applications']
}>()

function createDefaultTheme(): ThemeConfig {
  return {
    title: '欢迎登录',
    welcome_text: '安全访问您的工作空间',
    primary_color: '#18181B',
    background_color: '#fafafa',
    background_url: '',
    logo_url: '',
    layout: 'centered',
    card_position: 'center',
    card_width: 420,
    card_radius: 16,
    background_position: 'center',
    background_size: 'cover',
    background_overlay: 27,
    card_background_color: '#ffffff',
    card_opacity: 100,
    title_color: '#202a3b',
    text_color: '#202a3b',
    font_family: 'system',
    logo_size: 40,
    card_shadow: 'medium',
    card_padding: 20,
    input_radius: 6,
    button_radius: 6,
    button_height: 40,
    show_register: false,
    show_forgot_password: true,
    terms_url: '',
    privacy_url: '',
  }
}

const themeDraft = ref<ThemeConfig>(createDefaultTheme())
const themePreviewMode = ref<'desktop' | 'mobile'>('desktop')
const themeHistory = ref<ThemeHistoryRow[]>([])
const themeSaving = ref(false)
let historyRequestSequence = 0
let loadedApplicationId = ''
let applyingLoadedConfig = false
let themeDirty = false

// 草稿由该 feature 持有；父级仅托管应用选择和路由，不让跨页切换覆盖未保存编辑。
watch(themeDraft, () => {
  if (!applyingLoadedConfig && loadedApplicationId === props.selectedApplicationId) themeDirty = true
}, { deep: true, flush: 'sync' })

function applyDraftColor(field: 'primary_color' | 'background_color' | 'card_background_color' | 'title_color' | 'text_color', hex: string): void {
  if (/^#[\da-f]{6}$/i.test(hex)) themeDraft.value[field] = hex
}

const themePreviewBackground = computed(() => {
  const draft = themeDraft.value
  const url = resolveThemeAssetUrl(draft.background_url)
  const overlay = themeNumber(draft.background_overlay, 0, 70, 27) / 100
  const backgroundPosition = themeChoice(draft.background_position, ['center', 'top', 'bottom', 'left', 'right'], 'center')
  const backgroundSize = themeChoice(draft.background_size, ['cover', 'contain', 'auto'], 'cover')
  return {
    backgroundColor: themeHex(draft.background_color, '#f5f6fa'),
    backgroundPosition,
    backgroundSize,
    ...(url ? { backgroundImage: `linear-gradient(rgba(17,24,39,${overlay}),rgba(17,24,39,${overlay})),url("${url}")` } : {}),
  }
})

const themePreviewLogo = computed(() => {
  return resolveThemeAssetUrl(themeDraft.value.logo_url)
})

const themePreviewCardStyle = computed(() => {
  const draft = themeDraft.value
  const padding = themeNumber(draft.card_padding, 12, 40, 20)
  return {
    // 手机预览壳固定 320px：卡片必须吃满壳内宽度——预览容器是 grid，内联 width 会把
    // 隐式轨道自撑大，使 maxWidth:'100%' 相对被撑大的轨道解析而失效（卡片穿出手机壳）；
    // 真机登录页卡片同样受视口约束，此处语义一致。桌面预览仍按配置宽度渲染。
    width: themePreviewMode.value === 'mobile' ? '100%' : `${themeNumber(draft.card_width, 320, 720, 420)}px`,
    maxWidth: '100%',
    borderRadius: `${themeNumber(draft.card_radius, 0, 32, 16)}px`,
    padding: `${Math.round(padding * 0.8)}px ${padding}px`,
    backgroundColor: themeRgba(draft.card_background_color, themeNumber(draft.card_opacity, 60, 100, 100), '#ffffff'),
    color: themeHex(draft.text_color, '#202a3b'),
    boxShadow: themeCardShadow(draft.card_shadow),
    fontFamily: themeFontFamily(draft.font_family),
    '--preview-input-radius': `${themeNumber(draft.input_radius, 0, 24, 6)}px`,
    '--preview-button-radius': `${themeNumber(draft.button_radius, 0, 24, 6)}px`,
    '--preview-button-height': `${themeNumber(draft.button_height, 40, 60, 40)}px`,
  }
})

// 只在主题页显示时拉取版本，切走页面不会丢失本地草稿。
watch(
  () => [props.active, props.selectedApplicationId] as const,
  ([active, applicationId]) => {
    if (!active) return
    if (!applicationId) {
      historyRequestSequence += 1
      themeHistory.value = []
      loadedApplicationId = ''
      applyingLoadedConfig = true
      themeDraft.value = createDefaultTheme()
      applyingLoadedConfig = false
      themeDirty = false
      return
    }
    if (applicationId === loadedApplicationId && themeDirty) return
    if (applicationId !== loadedApplicationId) {
      // 切换应用时立即清除上一个应用的表单，网络失败也不会误把旧主题保存给新应用。
      historyRequestSequence += 1
      loadedApplicationId = applicationId
      themeHistory.value = []
      applyingLoadedConfig = true
      themeDraft.value = createDefaultTheme()
      applyingLoadedConfig = false
      themeDirty = false
    }
    void loadThemeHistory(applicationId)
  },
  { immediate: true },
)

async function loadThemeHistory(applicationId: string): Promise<void> {
  if (applicationId !== props.selectedApplicationId) return
  const requestSequence = ++historyRequestSequence
  try {
    const versions = await api<ThemeHistoryRow[]>(`/admin/themes?application_id=${encodeURIComponent(applicationId)}`)
    // 选中应用切换很快时忽略旧请求，防止旧主题覆盖新应用表单。
    if (requestSequence !== historyRequestSequence || applicationId !== props.selectedApplicationId) return
    themeHistory.value = versions
    const selectedVersion = versions[0]
    const config = selectedVersion?.config && typeof selectedVersion.config === 'object'
      ? selectedVersion.config as Record<string, unknown>
      : {}
    if (themeDirty) return
    applyingLoadedConfig = true
    themeDraft.value = {
      title: String(config.title || '欢迎登录'),
      welcome_text: String(config.welcome_text || ''),
      primary_color: String(config.primary_color || '#18181B'),
      background_color: String(config.background_color || '#fafafa'),
      background_url: String(config.background_url || ''),
      logo_url: String(config.logo_url || ''),
      layout: String(config.layout || 'centered'),
      card_position: String(config.card_position || 'center'),
      card_width: Number(config.card_width || 420),
      card_radius: Number(config.card_radius ?? 16),
      background_position: themeChoice(config.background_position, ['center', 'top', 'bottom', 'left', 'right'], 'center'),
      background_size: themeChoice(config.background_size, ['cover', 'contain', 'auto'], 'cover'),
      background_overlay: themeNumber(config.background_overlay, 0, 70, 27),
      card_background_color: themeHex(config.card_background_color, '#ffffff'),
      card_opacity: themeNumber(config.card_opacity, 60, 100, 100),
      title_color: themeHex(config.title_color, '#202a3b'),
      text_color: themeHex(config.text_color, '#202a3b'),
      font_family: themeChoice(config.font_family, ['system', 'serif', 'rounded'], 'system'),
      logo_size: themeNumber(config.logo_size, 32, 96, 40),
      card_shadow: themeChoice(config.card_shadow, ['none', 'soft', 'medium', 'strong'], 'medium'),
      card_padding: themeNumber(config.card_padding, 12, 40, 20),
      input_radius: themeNumber(config.input_radius, 0, 24, 6),
      button_radius: themeNumber(config.button_radius, 0, 24, 6),
      button_height: themeNumber(config.button_height, 40, 60, 40),
      show_register: Boolean(config.show_register),
      show_forgot_password: config.show_forgot_password !== false,
      terms_url: String(config.terms_url || ''),
      privacy_url: String(config.privacy_url || ''),
    }
    applyingLoadedConfig = false
    themeDirty = false
  } catch (error) {
    if (requestSequence === historyRequestSequence) {
      message.error(error instanceof Error ? error.message : '主题版本读取失败')
    }
  }
}

// G17 恢复历史版本：复制目标版本为新草稿；publish=true 时同步发布并归档旧发布版。
const restoringVersionId = ref('')
async function restoreThemeVersion(row: ThemeHistoryRow, publish: boolean): Promise<void> {
  const applicationId = props.selectedApplicationId
  if (!applicationId) return
  restoringVersionId.value = row.id
  try {
    await api(`/admin/themes/${encodeURIComponent(applicationId)}/${encodeURIComponent(row.id)}/restore${publish ? '?publish=true' : ''}`, { method: 'POST' })
    message.success(publish ? `已从版本 ${row.version} 恢复并发布` : `已从版本 ${row.version} 恢复为新草稿`)
    themeDirty = false
    await loadThemeHistory(applicationId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '恢复历史版本失败')
  } finally { restoringVersionId.value = '' }
}

// G18 素材上传：原始字节直传本地盘卷（PNG/JPEG/WebP ≤2MB），成功后回填表单 URL。
const uploadingAsset = ref<'background' | 'logo' | ''>('')
async function uploadThemeAsset(file: File, target: 'background' | 'logo'): Promise<void> {
  const applicationId = props.selectedApplicationId
  if (!applicationId) {
    message.warning('请先创建并选择一个应用')
    return
  }
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    message.error('仅支持 PNG / JPEG / WebP 位图（SVG 可携带脚本，已排除）')
    return
  }
  if (file.size > 2 * 1024 * 1024) {
    message.error('素材超过 2MB 大小限制')
    return
  }
  uploadingAsset.value = target
  try {
    const buffer = await file.arrayBuffer()
    const result = await api<{ url: string }>(`/admin/uploads/theme-assets?application_id=${encodeURIComponent(applicationId)}`, {
      method: 'POST',
      headers: { 'Content-Type': file.type },
      body: buffer,
    })
    if (target === 'background') themeDraft.value.background_url = result.url
    else themeDraft.value.logo_url = result.url
    message.success('素材已上传，保存主题后生效')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '素材上传失败')
  } finally { uploadingAsset.value = '' }
}

// a-upload customRequest 适配：模板内联箭头不能带 TS 注解，抽成方法。
function onUploadBackground(options: { file: unknown }): void {
  void uploadThemeAsset(options.file as File, 'background')
}

function onUploadLogo(options: { file: unknown }): void {
  void uploadThemeAsset(options.file as File, 'logo')
}

async function saveTheme(publish: boolean): Promise<void> {
  const applicationId = props.selectedApplicationId
  if (!applicationId) {
    message.warning('请先创建并选择一个应用')
    return
  }

  themeSaving.value = true
  try {
    await api(`/admin/themes/${applicationId}?publish=${publish}`, {
      method: 'PUT',
      body: JSON.stringify({ config: { ...themeDraft.value } }),
    })
    message.success(publish ? '主题已发布' : '主题草稿已保存')
    themeDirty = false
    await loadThemeHistory(applicationId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '主题保存失败')
  } finally {
    themeSaving.value = false
  }
}
</script>

<template>
  <AdminPageHeader
    eyebrow="APPLICATION BRANDING"
    title="登录主题"
    subtitle="每个应用独立保存主题草稿、发布版本和历史记录。"
  />

  <div v-if="applications.length" class="theme-workspace">
    <a-card class="data-card theme-editor" title="主题配置">
      <a-form layout="vertical" class="theme-form">
        <a-form-item label="目标应用">
          <a-select
            :value="selectedApplicationId"
            placeholder="选择应用"
            :options="applications.map(app => ({ value: String(app.id), label: `${app.name} (${app.client_id})` }))"
            @change="emit('update:selectedApplicationId', String($event))"
          />
        </a-form-item>
        <div class="theme-field-grid">
          <a-form-item label="登录标题"><a-input v-model:value="themeDraft.title" :maxlength="60" /></a-form-item>
          <a-form-item label="品牌色"><AdminColorField :model-value="themeDraft.primary_color" aria-label="品牌色" @update:model-value="(hex) => applyDraftColor('primary_color', hex)" /></a-form-item>
        </div>
        <a-form-item label="欢迎文案"><a-input v-model:value="themeDraft.welcome_text" :maxlength="120" /></a-form-item>
        <div class="theme-field-grid">
          <a-form-item label="页面底色"><AdminColorField :model-value="themeDraft.background_color" aria-label="页面底色" @update:model-value="(hex) => applyDraftColor('background_color', hex)" /></a-form-item>
          <a-form-item label="登录卡片宽度"><a-input-number v-model:value="themeDraft.card_width" :min="320" :max="720" :step="10" addon-after="px" style="width:100%" /></a-form-item>
        </div>
        <a-form-item label="背景图片地址">
          <div class="flex w-full items-center gap-2">
            <a-input v-model:value="themeDraft.background_url" class="min-w-0 flex-1" placeholder="https://example.com/background.jpg（可选）" />
            <!-- G18 本地盘上传：服务端随机命名，成功后回填相对 URL。 -->
            <a-upload :show-upload-list="false" :disabled="uploadingAsset !== ''"
              :custom-request="onUploadBackground">
              <a-button size="small" :loading="uploadingAsset === 'background'">上传</a-button>
            </a-upload>
          </div>
        </a-form-item>
        <a-form-item label="Logo 图片地址">
          <div class="flex w-full items-center gap-2">
            <a-input v-model:value="themeDraft.logo_url" class="min-w-0 flex-1" placeholder="https://example.com/logo.svg（可选）" />
            <a-upload :show-upload-list="false" :disabled="uploadingAsset !== ''"
              :custom-request="onUploadLogo">
              <a-button size="small" :loading="uploadingAsset === 'logo'">上传</a-button>
            </a-upload>
          </div>
        </a-form-item>
        <div class="theme-field-grid">
          <a-form-item label="卡片圆角"><a-input-number v-model:value="themeDraft.card_radius" :min="0" :max="32" :step="2" addon-after="px" style="width:100%" /></a-form-item>
          <a-form-item label="卡片位置">
            <a-select v-model:value="themeDraft.card_position">
              <a-select-option value="center">居中</a-select-option>
              <a-select-option value="left">左侧</a-select-option>
              <a-select-option value="right">右侧</a-select-option>
            </a-select>
          </a-form-item>
        </div>
        <a-form-item label="页面布局">
          <a-select v-model:value="themeDraft.layout">
            <a-select-option value="centered">居中登录卡片</a-select-option>
            <a-select-option value="split">品牌介绍与登录分栏</a-select-option>
            <a-select-option value="banner">顶部品牌横幅</a-select-option>
          </a-select>
        </a-form-item>
        <div class="theme-switches">
          <a-form-item label="显示注册入口"><a-switch v-model:checked="themeDraft.show_register" /></a-form-item>
          <a-form-item label="显示忘记密码"><a-switch v-model:checked="themeDraft.show_forgot_password" /></a-form-item>
        </div>
        <p v-if="themeDraft.show_register" class="theme-help">此开关只控制登录页入口展示。实际注册还需在应用管理中开启策略、配置普通角色与协议版本，并由部署全局开关及邮件服务共同放行。</p>
        <details class="theme-advanced">
          <summary>外观细节</summary>
          <div class="theme-field-grid">
            <a-form-item label="背景图位置"><a-select v-model:value="themeDraft.background_position"><a-select-option value="center">居中</a-select-option><a-select-option value="top">顶部</a-select-option><a-select-option value="bottom">底部</a-select-option><a-select-option value="left">左侧</a-select-option><a-select-option value="right">右侧</a-select-option></a-select></a-form-item>
            <a-form-item label="背景图缩放"><a-select v-model:value="themeDraft.background_size"><a-select-option value="cover">铺满</a-select-option><a-select-option value="contain">完整显示</a-select-option><a-select-option value="auto">原始尺寸</a-select-option></a-select></a-form-item>
          </div>
          <div class="theme-field-grid">
            <a-form-item label="背景遮罩透明度"><a-input-number v-model:value="themeDraft.background_overlay" :min="0" :max="70" addon-after="%" style="width:100%" /></a-form-item>
            <a-form-item label="Logo 尺寸"><a-input-number v-model:value="themeDraft.logo_size" :min="32" :max="96" :step="2" addon-after="px" style="width:100%" /></a-form-item>
          </div>
          <div class="theme-field-grid">
            <a-form-item label="卡片背景色"><AdminColorField :model-value="themeDraft.card_background_color" aria-label="卡片背景色" @update:model-value="(hex) => applyDraftColor('card_background_color', hex)" /></a-form-item>
            <a-form-item label="卡片不透明度"><a-input-number v-model:value="themeDraft.card_opacity" :min="60" :max="100" addon-after="%" style="width:100%" /></a-form-item>
          </div>
          <div class="theme-field-grid">
            <a-form-item label="用户协议链接"><a-input v-model:value="themeDraft.terms_url" :maxlength="2048" placeholder="https://example.com/terms" /></a-form-item>
            <a-form-item label="隐私政策链接"><a-input v-model:value="themeDraft.privacy_url" :maxlength="2048" placeholder="https://example.com/privacy" /></a-form-item>
          </div>
          <div class="theme-field-grid">
            <a-form-item label="标题文字色"><AdminColorField :model-value="themeDraft.title_color" aria-label="标题文字色" @update:model-value="(hex) => applyDraftColor('title_color', hex)" /></a-form-item>
            <a-form-item label="正文文字色"><AdminColorField :model-value="themeDraft.text_color" aria-label="正文文字色" @update:model-value="(hex) => applyDraftColor('text_color', hex)" /></a-form-item>
          </div>
          <div class="theme-field-grid">
            <a-form-item label="字体风格"><a-select v-model:value="themeDraft.font_family"><a-select-option value="system">系统无衬线</a-select-option><a-select-option value="serif">衬线</a-select-option><a-select-option value="rounded">圆润无衬线</a-select-option></a-select></a-form-item>
            <a-form-item label="卡片阴影"><a-select v-model:value="themeDraft.card_shadow"><a-select-option value="none">无</a-select-option><a-select-option value="soft">柔和</a-select-option><a-select-option value="medium">标准</a-select-option><a-select-option value="strong">突出</a-select-option></a-select></a-form-item>
          </div>
          <div class="theme-field-grid">
            <a-form-item label="卡片内边距"><a-input-number v-model:value="themeDraft.card_padding" :min="12" :max="40" addon-after="px" style="width:100%" /></a-form-item>
            <a-form-item label="输入框圆角"><a-input-number v-model:value="themeDraft.input_radius" :min="0" :max="24" addon-after="px" style="width:100%" /></a-form-item>
          </div>
          <div class="theme-field-grid">
            <a-form-item label="按钮圆角"><a-input-number v-model:value="themeDraft.button_radius" :min="0" :max="24" addon-after="px" style="width:100%" /></a-form-item>
            <a-form-item label="按钮高度"><a-input-number v-model:value="themeDraft.button_height" :min="40" :max="60" addon-after="px" style="width:100%" /></a-form-item>
          </div>
        </details>
        <p class="theme-help">为安全起见，预览和发布仅接受 HTTPS/站内图片、颜色和固定样式预设；不会执行上传脚本、HTML 或任意 CSS。</p>
        <a-space>
          <a-button :loading="themeSaving" :disabled="!selectedApplicationId" @click="saveTheme(false)">保存草稿</a-button>
          <a-button type="primary" :loading="themeSaving" :disabled="!selectedApplicationId" @click="saveTheme(true)">发布主题</a-button>
        </a-space>
      </a-form>
    </a-card>

    <div class="theme-side">
      <a-card class="data-card theme-preview-card" :bordered="false">
        <div class="preview-heading">
          <div><h2>实时预览</h2><p>修改配置后即时查看效果</p></div>
          <a-radio-group v-model:value="themePreviewMode" size="small" button-style="solid">
            <a-radio-button value="desktop">桌面</a-radio-button>
            <a-radio-button value="mobile">手机</a-radio-button>
          </a-radio-group>
        </div>
        <div
          class="theme-preview-frame"
          :class="[{ mobile: themePreviewMode === 'mobile' }, `position-${themeDraft.card_position}`, `layout-${themeDraft.layout}`]"
          :style="themePreviewBackground"
        >
          <div v-if="themeDraft.layout !== 'centered' && themePreviewMode === 'desktop'" class="theme-preview-brand-copy">
            <strong>{{ themeDraft.title || '欢迎登录' }}</strong><span>{{ themeDraft.welcome_text || '安全访问您的工作空间' }}</span>
          </div>
          <div class="theme-preview-card-slot">
            <div class="theme-preview-login-card" :style="themePreviewCardStyle">
            <img v-if="themePreviewLogo" :src="themePreviewLogo" class="theme-preview-logo" :style="{ height: `${themeDraft.logo_size}px`, maxWidth: `${themeDraft.logo_size * 3}px` }" alt="品牌 Logo" />
            <div v-else class="theme-preview-mark" :style="{ background: themeDraft.primary_color, width: `${themeDraft.logo_size}px`, height: `${themeDraft.logo_size}px` }">ID</div>
            <h3 :style="{ color: themeDraft.title_color }">{{ themeDraft.title || '欢迎登录' }}</h3><p :style="{ color: themeDraft.text_color }">{{ themeDraft.welcome_text || '安全访问您的工作空间' }}</p>
            <div class="preview-input" :style="{ borderRadius: `${themeDraft.input_radius}px` }">邮箱地址</div><div class="preview-input" :style="{ borderRadius: `${themeDraft.input_radius}px` }">密码</div>
            <button class="preview-submit" :style="{ background: themeDraft.primary_color, borderRadius: `${themeDraft.button_radius}px`, height: `${themeDraft.button_height}px` }">登录</button>
            <div class="preview-links"><span v-if="themeDraft.show_register">注册账号（预览）</span><span v-if="themeDraft.show_forgot_password">忘记密码？</span></div>
            </div>
          </div>
        </div>
      </a-card>
      <a-card class="data-card history-card" title="版本历史">
        <p class="history-caption">保存草稿和发布操作都会生成版本记录。</p>
        <a-table
          :data-source="themeHistory"
          :columns="[
            { title: '版本', dataIndex: 'version', key: 'version', width: 80 },
            { title: '状态', dataIndex: 'status', key: 'status', width: 90 },
            { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
            { title: '操作', key: 'actions', width: 180 },
          ]"
          row-key="id"
          :pagination="false"
          size="small"
          :scroll="{ x: 480 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'actions'">
              <!-- G17：恢复历史版本——恢复为草稿不改变线上；恢复并发布立即生效。 -->
              <a-space :size="0">
                <a-button type="link" size="small" :loading="restoringVersionId === record.id"
                  @click="restoreThemeVersion(record, false)">恢复为草稿</a-button>
                <a-button type="link" size="small" danger :loading="restoringVersionId === record.id"
                  @click="restoreThemeVersion(record, true)">恢复并发布</a-button>
              </a-space>
            </template>
          </template>
          <template #emptyText><AdminEmpty emoji="🎨" description="暂无主题版本" /></template>
        </a-table>
      </a-card>
    </div>
  </div>
  <a-card v-else class="data-card">
    <AdminEmpty emoji="🧩" description="请先创建应用，再配置该应用的登录主题">
      <a-button type="primary" @click="emit('navigate', 'applications')">前往应用管理</a-button>
    </AdminEmpty>
  </a-card>
</template>
