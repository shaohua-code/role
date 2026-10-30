# -*- coding: utf-8 -*-
from __future__ import annotations
import json, pathlib, re, shutil, textwrap, base64

ROOT = pathlib.Path(r"D:\project\role")
SRC = ROOT / "frontend" / "src"
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"
ARCHIVE = DOCS / "_archive"

def write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8", newline="\n")
    print("WRITE", path.relative_to(ROOT), len(content))

def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def move_tree(src: pathlib.Path, dest: pathlib.Path) -> None:
    if not src.exists():
        print("SKIP move", src)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(src), str(dest))
    print("MOVE", src.relative_to(ROOT), "->", dest.relative_to(ROOT))

def extract_composables_from_app():
    """Build useTableFit / useShellAppearance from App.vue bodies if missing."""
    app = read(SRC / "App.vue")
    # useReadinessPoll may already exist from earlier write
    ready_path = SRC / "composables" / "useReadinessPoll.ts"
    if not ready_path.exists():
        raise SystemExit("useReadinessPoll.ts missing; abort")

    # Extract fitTableBodies..refreshTableFit from App if needed
    fit_path = SRC / "composables" / "useTableFit.ts"
    if not fit_path.exists():
        m = re.search(r"function fitTableBodies\(\): void \{[\s\S]*?function refreshTableFit\(\): void \{[\s\S]*?\n\}", app)
        if not m:
            raise SystemExit("cannot extract fitTableBodies")
        body = m.group(0)
        # wrap
        content = (
            "import { nextTick, onUnmounted } from 'vue'\n\n"
            "export function useTableFit() {\n"
            "  let tableFitObserver: MutationObserver | null = null\n"
            "  let tableFitTimer: number | undefined\n\n"
            + textwrap.indent(body, "  ")
            + "\n\n  function onWindowResizeFit(): void { fitTableBodies() }\n"
            "  function scheduleTableFit(): void {\n"
            "    if (tableFitTimer !== undefined) window.clearTimeout(tableFitTimer)\n"
            "    tableFitTimer = window.setTimeout(fitTableBodies, 80)\n"
            "  }\n"
            # refreshTableFit already extracted includes scheduleTableFit usage - may duplicate
            # Actually body already has scheduleTableFit and refreshTableFit. Remove dup helpers if present in body.
        )
        # Better rewrite: body already contains fitTableBodies, scheduleTableFit?, refreshTableFit
        # Check
        has_sched = "function scheduleTableFit" in body
        has_refresh = "function refreshTableFit" in body
        content = "import { nextTick, onUnmounted } from 'vue'\n\nexport function useTableFit() {\n  let tableFitObserver: MutationObserver | null = null\n  let tableFitTimer: number | undefined\n\n"
        content += textwrap.indent(body, "  ") + "\n"
        if "function onWindowResizeFit" not in body:
            content += "\n  function onWindowResizeFit(): void {\n    fitTableBodies()\n  }\n"
        content += """
  function bindTableFitListeners(): void {
    window.addEventListener('resize', onWindowResizeFit)
  }

  function disposeTableFit(): void {
    window.removeEventListener('resize', onWindowResizeFit)
    tableFitObserver?.disconnect()
    tableFitObserver = null
    if (tableFitTimer !== undefined) window.clearTimeout(tableFitTimer)
  }

  onUnmounted(disposeTableFit)

  return {
    fitTableBodies,
    refreshTableFit,
    scheduleTableFit,
    bindTableFitListeners,
    disposeTableFit,
  }
}
"""
        # If scheduleTableFit not in body, the indent body from App includes scheduleTableFit - yes from earlier dump
        write(fit_path, content)

    appear_path = SRC / "composables" / "useShellAppearance.ts"
    if not appear_path.exists():
        # Extract from type ThemePreference through onSystemThemeChange, plus related consts
        m = re.search(
            r"type ThemePreference = [\s\S]*?function onSystemThemeChange\(event: MediaQueryListEvent\): void \{\n  systemPrefersDark\.value = event\.matches\n\}",
            app,
        )
        if not m:
            raise SystemExit("cannot extract theme block")
        block = m.group(0)
        # Also need onThemePreferenceChange, applyPrimaryColor, toggleSidebar etc. - they're in the block
        content = (
            "import { computed, onUnmounted, ref, watch } from 'vue'\n"
            "import { theme as antTheme } from 'ant-design-vue'\n"
            "import { applyBrandToDocument, buildManagementAntdTheme, readCssVar } from '@/styles/antd-bridge'\n\n"
            "export " + block.replace("const antdTheme = computed", "const antdThemeConfig = computed", 1)
            + "\n\n"
        )
        # This approach is messy because block uses local consts. Write a clean known-good file instead using App logic rewritten.
        content = r'''import { computed, onUnmounted, ref, watch } from 'vue'
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
'''
        write(appear_path, content)

    # Fix useTableFit if we wrote a broken duplicate schedule - rewrite cleanly from App extract
    if fit_path.exists():
        # Always rewrite clean extract
        m = re.search(r"(function fitTableBodies\(\): void \{[\s\S]*?\n\})\n(function onWindowResizeFit\(\): void \{[\s\S]*?\n\})\n(?://[^\n]*\n)*(function scheduleTableFit\(\): void \{[\s\S]*?\n\})\n(?://[^\n]*\n)*(function refreshTableFit\(\): void \{[\s\S]*?\n\})", app)
        if not m:
            m2 = re.search(r"function fitTableBodies\(\): void \{[\s\S]*?function refreshTableFit\(\): void \{[\s\S]*?\n\}", app)
            funcs = m2.group(0) if m2 else None
        else:
            funcs = "\n".join(m.groups())
        if funcs:
            # Remove nested schedule/onWindow if duplicated wrongly - App has all four
            content = (
                "import { nextTick, onUnmounted } from 'vue'\n\n"
                "export function useTableFit() {\n"
                "  let tableFitObserver: MutationObserver | null = null\n"
                "  let tableFitTimer: number | undefined\n\n"
                + textwrap.indent(funcs, "  ")
                + """

  function bindTableFitListeners(): void {
    window.addEventListener('resize', onWindowResizeFit)
  }

  function disposeTableFit(): void {
    window.removeEventListener('resize', onWindowResizeFit)
    tableFitObserver?.disconnect()
    tableFitObserver = null
    if (tableFitTimer !== undefined) window.clearTimeout(tableFitTimer)
  }

  onUnmounted(disposeTableFit)

  return {
    fitTableBodies,
    refreshTableFit,
    scheduleTableFit,
    bindTableFitListeners,
    disposeTableFit,
  }
}
"""
            )
            write(fit_path, content)

print("composables step start")
extract_composables_from_app()
print("composables ok", list((SRC/"composables").glob("*.ts")))
