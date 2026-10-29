import { computed, onUnmounted, ref, watch } from 'vue'
import { theme as antTheme } from 'ant-design-vue'
import { applyBrandToDocument, buildManagementAntdTheme, readCssVar } from '@/styles/antd-bridge'

export type ThemePreference = 'light' | 'dark' | 'system'

const DEFAULT_PRIMARY = '#18181B'
const MOBILE_MEDIA_QUERY = '(max-width: 650px)'

function readThemePreference(): ThemePreference {
  const stored = localStorage.getItem('iam-theme')
  if (stored === 'dark' || stored === 'light' || stored === 'system') return stored
  return 'light'
}

function readPrimaryColor(): string {
  const stored = localStorage.getItem('iam-primary-color') || ''
  if (/^#[\da-f]{6}$/i.test(stored) && stored.toUpperCase() !== '#5B5BD6') return stored
  return DEFAULT_PRIMARY
}

function isDarkHexColor(hex: string): boolean {
  const match = /^#([\da-f]{6})$/i.exec(hex)
  if (!match) return false
  const value = Number.parseInt(match[1], 16)
  const r = (value >> 16) & 255
  const g = (value >> 8) & 255
  const b = value & 255
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 80
}

export function useShellAppearance() {
  const themePreference = ref<ThemePreference>(readThemePreference())
  const systemPrefersDark = ref(window.matchMedia('(prefers-color-scheme: dark)').matches)
  const themeMode = computed(() =>
    themePreference.value === 'system'
      ? (systemPrefersDark.value ? 'dark' : 'light')
      : themePreference.value,
  )
  watch(themeMode, (mode) => {
    document.documentElement.setAttribute('data-theme', mode)
  }, { immediate: true })

  const primaryColor = ref(readPrimaryColor())
  const density = ref(localStorage.getItem('iam-density') === 'compact' ? 'compact' : 'comfortable')
  const componentSize = computed(() => density.value === 'compact' ? 'small' : 'middle')

  const isMobile = ref(window.matchMedia(MOBILE_MEDIA_QUERY).matches)
  const mobileNavOpen = ref(false)
  let mobileQuery: MediaQueryList | null = null
  function onMobileViewportChange(event: MediaQueryListEvent): void {
    isMobile.value = event.matches
    if (!event.matches) mobileNavOpen.value = false
  }

  const sidebarCollapsed = ref(localStorage.getItem('iam-sidebar-collapsed') === 'collapsed')
  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem('iam-sidebar-collapsed', sidebarCollapsed.value ? 'collapsed' : 'expanded')
  }

  function onThemePreferenceChange(): void {
    localStorage.setItem('iam-theme', themePreference.value)
    localStorage.setItem('iam-primary-color', primaryColor.value)
    localStorage.setItem('iam-density', density.value)
  }

  function applyPrimaryColor(hex: string): void {
    if (/^#[\da-f]{6}$/i.test(hex)) {
      primaryColor.value = hex
      applyBrandToDocument(hex)
      onThemePreferenceChange()
    }
  }

  const headerSurfaceStyle = computed(() => (
    themeMode.value === 'dark'
      ? { color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }
      : { color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }
  ))

  const displayPrimary = computed(() => {
    if (themeMode.value !== 'dark') return primaryColor.value
    if (isDarkHexColor(primaryColor.value)) return readCssVar('--color-brand', '#fafafa')
    return primaryColor.value
  })

  const antdThemeConfig = computed(() => {
    const isDark = themeMode.value === 'dark'
    const bridged = buildManagementAntdTheme({
      primary: displayPrimary.value,
      isDark,
      controlHeight: density.value === 'compact' ? 32 : 36,
    })
    return {
      algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
      token: bridged.token,
      components: bridged.components,
    }
  })

  let systemThemeQuery: MediaQueryList | null = null
  function onSystemThemeChange(event: MediaQueryListEvent): void {
    systemPrefersDark.value = event.matches
  }

  function bindAppearanceListeners(): void {
    applyBrandToDocument(primaryColor.value)
    systemThemeQuery = window.matchMedia('(prefers-color-scheme: dark)')
    systemPrefersDark.value = systemThemeQuery.matches
    systemThemeQuery.addEventListener('change', onSystemThemeChange)
    mobileQuery = window.matchMedia(MOBILE_MEDIA_QUERY)
    isMobile.value = mobileQuery.matches
    mobileQuery.addEventListener('change', onMobileViewportChange)
  }

  function disposeAppearanceListeners(): void {
    systemThemeQuery?.removeEventListener('change', onSystemThemeChange)
    mobileQuery?.removeEventListener('change', onMobileViewportChange)
  }

  onUnmounted(disposeAppearanceListeners)

  return {
    themePreference,
    themeMode,
    primaryColor,
    density,
    componentSize,
    isMobile,
    mobileNavOpen,
    sidebarCollapsed,
    headerSurfaceStyle,
    displayPrimary,
    antdTheme: antdThemeConfig,
    toggleSidebar,
    applyPrimaryColor,
    onThemePreferenceChange,
    bindAppearanceListeners,
    disposeAppearanceListeners,
    DEFAULT_PRIMARY,
  }
}
