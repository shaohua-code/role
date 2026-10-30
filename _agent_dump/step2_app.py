# -*- coding: utf-8 -*-
from __future__ import annotations
import pathlib, re, textwrap

ROOT = pathlib.Path(r"D:\project\role")
SRC = ROOT / "frontend" / "src"

def write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8", newline="\n")
    print("WRITE", path.relative_to(ROOT), len(content))

def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8-sig")

write(SRC / "layout" / "page-registry.ts", textwrap.dedent("""\
import type { Component } from 'vue'
import type { PageKey } from '@/router/navigation'
import {
  ApplicationManagement,
  ApplicationWorkspace,
  ApplicationRoleManagement,
  AuditLogPage,
  AuthorizationSimulator,
  GroupManagement,
  InvitationManagement,
  LoginThemeManagement,
  ModelGovernancePage,
  OrganizationManagement,
  OrganizationWorkspace,
  OverviewPage,
  PermissionCatalog,
  RoleManagement,
  TenantAccessManagement,
  TenantManagement,
  UserManagement,
} from '@/router/loaders'

export const PAGE_COMPONENTS: Record<string, Component> = {
  overview: OverviewPage,
  organization_workspace: OrganizationWorkspace,
  users: UserManagement,
  groups: GroupManagement,
  invitations: InvitationManagement,
  application_workspace: ApplicationWorkspace,
  applications: ApplicationManagement,
  application_roles: ApplicationRoleManagement,
  roles: RoleManagement,
  permissions: PermissionCatalog,
  organizations: OrganizationManagement,
  tenants: TenantManagement,
  tenant_access: TenantAccessManagement,
  themes: LoginThemeManagement,
  models: ModelGovernancePage,
  audit: AuditLogPage,
  authorization_simulator: AuthorizationSimulator,
}

export function createVisitedPages(initial?: PageKey): Set<PageKey> {
  return new Set<PageKey>(initial ? [initial] : [])
}
"""))

app_path = SRC / "App.vue"
text = read(app_path)
bak = ROOT / "_agent_dump" / "App.vue.pre_split_backup"
if not bak.exists():
    bak.write_text(text, encoding="utf-8")
    print("BACKUP App.vue")

if "useReadinessPoll" not in text:
    inject = (
        "import { useReadinessPoll } from '@/composables/useReadinessPoll'\n"
        "import { useTableFit } from '@/composables/useTableFit'\n"
        "import { useShellAppearance } from '@/composables/useShellAppearance'\n"
        "import { PAGE_COMPONENTS } from '@/layout/page-registry'\n"
    )
    if "from '@/router/loaders'\n" in text:
        text = text.replace("from '@/router/loaders'\n", "from '@/router/loaders'\n" + inject, 1)
    else:
        raise SystemExit("loaders import missing")

wire = """
const {
  healthState,
  readinessRefreshing,
  refreshReadiness,
  startReadinessPolling,
  disposeReadinessPolling,
} = useReadinessPoll()

const { refreshTableFit, bindTableFitListeners, disposeTableFit } = useTableFit()

const {
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
  antdTheme,
  toggleSidebar,
  applyPrimaryColor,
  onThemePreferenceChange,
  bindAppearanceListeners,
  disposeAppearanceListeners,
  DEFAULT_PRIMARY,
} = useShellAppearance()

const pageComponents = PAGE_COMPONENTS
"""
if "const pageComponents = PAGE_COMPONENTS" not in text:
    text = text.replace("const router = useRouter()\n", "const router = useRouter()\n" + wire, 1)

text = re.sub(r"const healthState = ref\('[^']*'\)\n", "", text, count=1)
text = re.sub(r"const readinessRefreshing = ref\(false\)\n", "", text, count=1)
text = re.sub(r"const READINESS_POLL_OK_MS = [\s\S]*?function onReadinessVisibilityChange\(\): void \{[\s\S]*?\n\}\n", "", text, count=1)
text = re.sub(r"type ThemePreference = [\s\S]*?function onSystemThemeChange\(event: MediaQueryListEvent\): void \{\n  systemPrefersDark\.value = event\.matches\n\}\n", "", text, count=1)
text = re.sub(r"function fitTableBodies\(\): void \{[\s\S]*?function refreshTableFit\(\): void \{[\s\S]*?\n\}\n", "", text, count=1)
text = re.sub(r"let tableFitObserver: MutationObserver \| null = null\nlet tableFitTimer: number \| undefined\n", "", text)
text = re.sub(
    r"applyBrandToDocument\(primaryColor\.value\)\n  systemThemeQuery = window\.matchMedia\('\(prefers-color-scheme: dark\)'\)\n  systemPrefersDark\.value = systemThemeQuery\.matches\n  systemThemeQuery\.addEventListener\('change', onSystemThemeChange\)\n  mobileQuery = window\.matchMedia\(MOBILE_MEDIA_QUERY\)\n  isMobile\.value = mobileQuery\.matches\n  mobileQuery\.addEventListener\('change', onMobileViewportChange\)\n(?:  //[^\n]*\n)?  window\.addEventListener\('resize', onWindowResizeFit\)",
    "bindAppearanceListeners()\n  bindTableFitListeners()",
    text,
    count=1,
)
text = re.sub(
    r"document\.addEventListener\('visibilitychange', onReadinessVisibilityChange\)\n  void refreshReadiness\(\)\.then\(\(\) => \{\n    scheduleReadinessPoll\(healthState\.value === '[^']+' \? READINESS_POLL_OK_MS : READINESS_POLL_DEGRADED_MS\)\n  \}\)",
    "startReadinessPolling()",
    text,
    count=1,
)
text = re.sub(
    r"onUnmounted\(\(\) => \{\n  systemThemeQuery\?\.removeEventListener\('change', onSystemThemeChange\)\n  mobileQuery\?\.removeEventListener\('change', onMobileViewportChange\)\n  document\.removeEventListener\('visibilitychange', onReadinessVisibilityChange\)\n  window\.removeEventListener\('resize', onWindowResizeFit\)\n  tableFitObserver\?\.disconnect\(\)\n  tableFitObserver = null\n  if \(tableFitTimer !== undefined\) window\.clearTimeout\(tableFitTimer\)\n  stopReadinessPolling\(\)\n\}\)",
    "onUnmounted(() => {\n  disposeAppearanceListeners()\n  disposeTableFit()\n  disposeReadinessPolling()\n})",
    text,
    count=1,
)
if "applyBrandToDocument(" not in text:
    text = text.replace("import { applyBrandToDocument, buildManagementAntdTheme, readCssVar } from '@/styles/antd-bridge'\n", "")
if "antTheme." not in text and "theme as antTheme" in text:
    text = text.replace("import { message, theme as antTheme } from 'ant-design-vue'\n", "import { message } from 'ant-design-vue'\n")
for pat in [
    r"const DEFAULT_PRIMARY = '#18181B'\n",
    r"const MOBILE_MEDIA_QUERY = '\(max-width: 650px\)'\n",
    r"let systemThemeQuery: MediaQueryList \| null = null\n",
    r"let mobileQuery: MediaQueryList \| null = null\n",
]:
    text = re.sub(pat, "", text)

# Remove orphaned pageComponents Record if still present after PAGE_COMPONENTS
text = re.sub(
    r"const pageComponents: Record<string, Component> = \{[\s\S]*?\n\}\n",
    "",
    text,
    count=1,
)

write(app_path, text)
print("App.vue lines", text.count("\n")+1)
print("wired", "useReadinessPoll" in text, "bindAppearanceListeners" in text, "startReadinessPolling" in text)
print("orphans", "function fitTableBodies" in text, "READINESS_POLL_OK_MS" in text, "type ThemePreference" in text)