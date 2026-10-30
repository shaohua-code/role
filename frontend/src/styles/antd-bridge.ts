/** Build Ant Design Vue ConfigProvider theme from CSS design tokens. */

/** Read a CSS design token (with fallback); exported for JS-only consumers like antdTheme. */
export function readCssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

export interface ManagementThemeInput {
  primary: string
  isDark: boolean
  controlHeight?: number
}

/** Map tokens (+ live primary override) into antd theme token/components. */
export function buildManagementAntdTheme(input: ManagementThemeInput) {
  const canvas = readCssVar('--color-bg-canvas', input.isDark ? '#0e0e10' : '#fafafa')
  const elevated = readCssVar('--color-bg-elevated', input.isDark ? '#18181b' : '#ffffff')
  const subtle = readCssVar('--color-bg-subtle', input.isDark ? '#1f1f23' : '#f4f4f5')
  const border = readCssVar('--color-border', input.isDark ? '#2e2e32' : '#e4e4e7')
  const textPrimary = readCssVar('--color-text-primary', input.isDark ? '#fafafa' : '#18181b')
  const textSecondary = readCssVar('--color-text-secondary', '#52525b')
  const brandSubtle = readCssVar('--color-brand-subtle', input.isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(24, 24, 27, 0.06)')
  const success = readCssVar('--color-success', '#059669')
  const warning = readCssVar('--color-warning', '#d97706')
  const error = readCssVar('--color-error', '#dc2626')
  const info = readCssVar('--color-info', '#2563eb')
  const fontSans = readCssVar('--font-sans', 'Inter, "Noto Sans SC", system-ui, sans-serif')
  const brandHover = readCssVar('--color-brand-hover', input.isDark ? '#ffffff' : '#3f3f46')
  const controlHeight = input.controlHeight ?? 36

  return {
    token: {
      colorPrimary: input.primary,
      // 链接色跟品牌色（antd 默认跟 colorInfo 蓝）：黑白灰体系下表格操作列/退出等 link 全部收归墨色
      colorLink: input.primary,
      colorLinkHover: brandHover,
      // 实底按钮文字色：暗色下主按钮翻转为浅底，白字会白上白，需随主题反转
      colorTextLightSolid: input.isDark ? '#18181b' : '#ffffff',
      colorSuccess: success,
      colorWarning: warning,
      colorError: error,
      colorInfo: info,
      colorBgLayout: canvas,
      colorBgContainer: elevated,
      colorBorder: border,
      colorText: textPrimary,
      colorTextSecondary: textSecondary,
      borderRadius: 8,
      fontFamily: fontSans,
      fontSize: 14,
      controlHeight,
    },
    components: {
      Layout: {
        headerBg: 'transparent',
        headerPadding: 16,
        headerHeight: 56,
        headerColor: textPrimary,
        siderBg: 'transparent',
        bodyBg: canvas,
      },
      Menu: {
        itemBorderRadius: 8,
        itemSelectedBg: brandSubtle,
        itemSelectedColor: input.primary,
        itemHoverBg: brandSubtle,
        // 纯黑侧栏：中性白叠加选中，文字灰阶分层——黑白灰轻奢，不用品牌色大面积着色
        darkItemBg: 'transparent',
        // 子菜单容器默认 #000c17 蓝黑，与纯黑侧栏冲突，一并透明化（实测根节点仍走样式层兜底）
        darkSubMenuItemBg: 'transparent',
        darkItemColor: 'rgba(250, 250, 250, 0.6)',
        darkItemHoverBg: 'rgba(255, 255, 255, 0.06)',
        darkItemSelectedBg: 'rgba(255, 255, 255, 0.1)',
        darkItemSelectedColor: '#fafafa',
        darkPopupBg: '#09090b',
      },
      Card: {
        borderRadiusLG: 12,
        paddingLG: 24,
      },
      Table: {
        headerBg: subtle,
        headerColor: textSecondary,
        // 行悬浮用不透明混合色：半透明 brandSubtle 会让 fixed 操作列（sticky）透出滚动内容
        rowHoverBg: readCssVar('--color-row-hover', input.isDark ? '#2a2b2e' : '#f2f2f3'),
      },
      Button: {
        borderRadius: 8,
        controlHeight,
        // 去掉 antd 默认的 0 2px 0 硬投影（黑色品牌下显脏），换贴地柔影
        primaryShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
      },
    },
  }
}

/** Sync document CSS variables when user picks a brand color. */
export function applyBrandToDocument(hex: string): void {
  if (!/^#[\da-f]{6}$/i.test(hex)) return
  const root = document.documentElement
  root.style.setProperty('--color-brand', hex)
  // Derive a slightly darker hover by mixing toward black in CSS is hard; keep token hover unless picker set.
  root.style.setProperty('--color-brand-subtle', hexToRgba(hex, 0.1))
}

function hexToRgba(hex: string, alpha: number): string {
  const channels = [1, 3, 5].map((index) => Number.parseInt(hex.slice(index, index + 2), 16))
  return `rgba(${channels.join(', ')}, ${alpha})`
}
