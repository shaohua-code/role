/** 安全消费应用登录主题；浏览器只接受显式预设值和固定类型的样式字段。 */

const FONT_STACKS: Record<string, string> = {
  system: 'Inter, "Noto Sans SC", system-ui, sans-serif',
  serif: 'Georgia, "Noto Serif SC", serif',
  rounded: '"Trebuchet MS", "Noto Sans SC", sans-serif',
}

const CARD_SHADOWS: Record<string, string> = {
  none: 'none',
  soft: '0 12px 32px rgba(16, 24, 40, 0.10)',
  medium: '0 28px 90px rgba(16, 24, 43, 0.17)',
  strong: '0 32px 96px rgba(16, 24, 43, 0.28)',
}

export function themeChoice(value: unknown, choices: readonly string[], fallback: string): string {
  return typeof value === 'string' && choices.includes(value) ? value : fallback
}

export function themeNumber(value: unknown, minimum: number, maximum: number, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  return Math.max(minimum, Math.min(maximum, Math.round(value)))
}

export function themeHex(value: unknown, fallback: string): string {
  return typeof value === 'string' && /^#[\da-f]{6}$/i.test(value) ? value : fallback
}

export function themeRgba(value: unknown, opacity: number, fallback: string): string {
  const hex = themeHex(value, fallback)
  const channels = [1, 3, 5].map(index => Number.parseInt(hex.slice(index, index + 2), 16))
  const alpha = Math.max(0, Math.min(100, opacity)) / 100
  return `rgba(${channels.join(', ')}, ${alpha})`
}

export function themeFontFamily(value: unknown): string {
  return FONT_STACKS[themeChoice(value, Object.keys(FONT_STACKS), 'system')]
}

export function themeCardShadow(value: unknown): string {
  return CARD_SHADOWS[themeChoice(value, Object.keys(CARD_SHADOWS), 'medium')]
}

/** 图片资源以 DOM URL 属性消费，不能把未编码输入拼入 CSS url()。 */
export function resolveThemeAssetUrl(value: unknown): string {
  if (typeof value !== 'string') return ''
  const raw = value.trim()
  if (!raw || raw.startsWith('//')) return ''
  for (let i = 0; i < raw.length; i += 1) {
    const code = raw.charCodeAt(i)
    if (code <= 0x1f || code === 0x7f || "\"'<>\\".includes(raw[i]!)) return ''
  }

  try {
    let parsed: URL
    if (/^https:\/\//i.test(raw)) {
      parsed = new URL(raw)
      if (parsed.protocol !== 'https:' || !parsed.hostname) return ''
    } else if (raw.startsWith('/') && !raw.startsWith('//')) {
      parsed = new URL(raw, window.location.origin)
      if (parsed.origin !== window.location.origin) return ''
    } else {
      return ''
    }
    if (parsed.username || parsed.password || parsed.hash) return ''
    return parsed.href
  } catch {
    return ''
  }
}
