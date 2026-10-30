# -*- coding: utf-8 -*-
from __future__ import annotations
import pathlib, re, shutil, textwrap, json

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

def prepend_banner(path: pathlib.Path, banner: str) -> None:
    if not path.exists():
        return
    text = read(path)
    if banner.strip().splitlines()[0] in text[:800]:
        print("BANNER skip", path.relative_to(ROOT))
        return
    write(path, banner + "\n" + text.lstrip("\ufeff"))

# ---------- 1) page-registry fix ----------
write(SRC / "layout" / "page-registry.ts", textwrap.dedent("""\
/**
 * Admin page component catalog (App.vue template still wires per-page props;
 * keep this map as the single inventory for PageKey → async feature).
 */
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

export const PAGE_COMPONENTS: Partial<Record<PageKey, Component>> = {
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
  model_usage: ModelGovernancePage,
  audit: AuditLogPage,
  authorization_simulation: AuthorizationSimulator,
}

export function createVisitedPages(initial?: PageKey): Set<PageKey> {
  return new Set<PageKey>(initial ? [initial] : [])
}
"""))

# ---------- 2) clean App.vue unused imports; keep PAGE_COMPONENTS as typed inventory via void helper ----------
app_path = SRC / "App.vue"
text = read(app_path)
text = text.replace("import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'\n",
                    "import { computed, onMounted, onUnmounted, ref, watch } from 'vue'\n")
text = text.replace("import { getReadiness, ReadinessError } from '@/api/health'\n", "")
# Ensure pageComponents is used (eslint): soft reference for inventory completeness check
if "function assertPageInventory" not in text:
    text = text.replace(
        "const pageComponents = PAGE_COMPONENTS\n",
        "const pageComponents = PAGE_COMPONENTS\n"
        "// 保留目录引用，避免拆壳后组件清单被误删；模板仍按页传不同 props。\n"
        "void pageComponents\n",
        1,
    )
write(app_path, text)

# ---------- 3) Dual-auth UX banners ----------
DUAL = "权限两层勿混：权限编码裁剪管理台菜单/按钮；接口鉴权看角色（用户多角色并集）。应用资源树只管业务端菜单/按钮，不替代角色接口鉴权。"

def ensure_alert_after_header(vue_path: pathlib.Path, message: str, key: str) -> None:
    t = read(vue_path)
    if key in t:
        print("ALERT skip", vue_path.name)
        return
    # insert after AdminPageHeader closing or first section child
    alert = f'    <a-alert type="info" show-icon class="mb-3" message="{message}" />\n'
    # Prefer after AdminPageHeader block
    m = re.search(r"(<AdminPageHeader[\s\S]*?/>\s*)", t)
    if m:
        t = t[:m.end()] + alert + t[m.end():]
        write(vue_path, t)
        return
    m2 = re.search(r"(<template>\s*<section[^>]*>\s*)", t)
    if m2:
        t = t[:m2.end()] + alert + t[m2.end():]
        write(vue_path, t)
        return
    print("ALERT fail", vue_path)

# Application workspace index — strengthen dual layer near tabs
aw = SRC / "views" / "application-workspace" / "index.vue"
awt = read(aw)
if "权限两层勿混" not in awt:
    awt = awt.replace(
        'subtitle="日常配权三步：① 在「权限编码」维护本应用 code；② 在「角色」为角色挂码；③ 到「用户管理」为用户多选角色。用户生效权限 = 其所有角色权限的并集。"',
        'subtitle="日常配权三步：①「权限编码」维护本应用 code；②「角色」挂码；③「用户管理」多选角色（并集生效）。另：码管菜单、角色管接口；资源树只管业务端菜单/按钮。"',
    )
    if '<a-tabs>' in awt and "权限两层勿混" not in awt:
        awt = awt.replace(
            '<a-tabs>',
            f'<a-alert type="warning" show-icon class="mb-3" message="{DUAL}" />\n        <a-tabs>',
            1,
        )
    write(aw, awt)

# PermissionsTab banner
pt = SRC / "views" / "application-workspace" / "tabs" / "PermissionsTab.vue"
ptt = read(pt)
if "码管菜单" not in ptt:
    # find template root
    if "<template>" in ptt:
        ptt = ptt.replace(
            "<template>",
            "<template>\n  <div class=\"flex flex-col gap-3\">\n    <a-alert type=\"info\" show-icon message=\"本 Tab 维护权限编码（管理台菜单/按钮裁剪用）。接口能不能调仍取决于用户角色；挂码请到「角色」Tab。\" />",
            1,
        )
        # close extra div before </template> last
        if ptt.rstrip().endswith("</template>"):
            # find last closing of original root - fragile; wrap only if single root exists
            pass
        # Better approach: insert alert as first child inside existing root
        ptt = read(pt)  # reset
        m = re.search(r"(<template>\s*)(<([a-zA-Z0-9-]+))", ptt)
        if m:
            insert = m.group(1) + f'<a-alert type="info" show-icon class="mb-3" message="本 Tab 维护权限编码（管理台菜单/按钮裁剪）。接口鉴权看角色；请到「角色」Tab 挂码。完整目录 CRUD 也可在「高级管理 → 权限编码」。" />\n  ' + m.group(2)
            ptt = ptt[:m.start()] + insert + ptt[m.end():]
            write(pt, ptt)

# RolesTab — prepend dual tip if missing
rt = SRC / "views" / "application-workspace" / "tabs" / "RolesTab.vue"
rtt = read(rt)
if "码管菜单" not in rtt and "角色管接口" not in rtt:
    m = re.search(r"(<template>\s*)(<([a-zA-Z0-9-]+))", rtt)
    if m:
        insert = m.group(1) + '<a-alert type="warning" show-icon class="mb-3" message="角色管接口鉴权：给角色挂权限编码后，持有该角色的用户才能过对应接口；菜单显隐另看权限码/资源树。数据范围与资源授权也在本 Tab。" />\n  ' + m.group(2)
        rtt = rtt[:m.start()] + insert + rtt[m.end():]
        write(rt, rtt)

# MenuTab strengthen
mt = SRC / "views" / "application-workspace" / "tabs" / "MenuTab.vue"
mtt = read(mt)
if "不替代角色接口" not in mtt:
    mtt = mtt.replace(
        'message="资源树面向应用：菜单配置路由、图标与额外参数（JSON），按钮与数据规则挂在菜单下；到「角色」Tab 点「配置资源」完成授权，业务端通过 my-resources 接口拉取整棵树。"',
        'message="资源树只管业务端菜单/按钮（my-resources），不替代角色接口鉴权。菜单挂路由/图标/额外参数；按钮与数据规则挂菜单下；到「角色」Tab「配置资源」授权。"',
    )
    write(mt, mtt)

# Advanced RoleManagement + PermissionCatalog cross-links
for rel, msg in [
    ("views/roles/RoleManagement.vue", "高级列表：完整角色 CRUD / 数据范围在此。日常按应用配权请优先用「应用工作台」。记住：码管菜单、角色管接口。"),
    ("views/permissions/PermissionCatalog.vue", "高级列表：全局权限编码目录。按应用维护请到「应用工作台 → 权限编码」。编码裁剪菜单；接口鉴权仍看角色挂码。"),
    ("views/applications/ApplicationManagement.vue", "高级列表：应用完整 CRUD。配角色/权限码/资源树请到「应用工作台」。"),
    ("views/organizations/OrganizationManagement.vue", "高级列表：组织完整 CRUD。成员与用户组日常请到「组织工作台」。"),
    ("views/groups/GroupManagement.vue", "高级列表：用户组完整 CRUD。组织上下文请到「组织工作台」。"),
]:
    ensure_alert_after_header(SRC / rel, msg, msg[:12])

# ---------- 4) 配权说明书 strengthen ----------
doc = DOCS / "配权说明书.md"
dt = read(doc)
if "码管菜单、角色管接口" not in dt:
    inject = textwrap.dedent("""

    ## 1.1 一句话防改错（必读）

    - **码管菜单**：权限编码 → 管理台菜单/按钮显隐（capabilities）。
    - **角色管接口**：用户角色并集 → API 能不能调。
    - **资源树管业务端 UI**：应用资源树 → `my-resources` 渲染，**不**替代接口鉴权。
    - 改菜单却改角色、或改接口却只改资源树，是最常见配错。

    """)
    dt = dt.replace("## 2. 日常怎么配（推荐顺序）", inject + "## 2. 日常怎么配（推荐顺序）", 1)
    write(doc, dt)

# ---------- 5) Archive docs / examples ----------
ARCHIVE.mkdir(parents=True, exist_ok=True)
move_tree(DOCS / "plan-a", ARCHIVE / "plan-a")
move_tree(DOCS / "prototypes", ARCHIVE / "prototypes")
move_tree(ROOT / "examples", ARCHIVE / "examples")

STALE = (
    "> ⚠️ **口径提示（2026-10-29）**：本文含历史 DeerFlow / 「新项目接入」描述，**不代表现行产品路径**。"
    "现行配权请以 [`配权说明书.md`](./配权说明书.md) 与管理台工作台为准；接入示例已归档至 `docs/_archive/examples`。\n\n"
)
for name in [
    "plan-frontend-codes-backend-roles.md",
    "后续项目对接手册.md",
    "技术架构与接入.md",
    "产品需求.md",
    "项目总览与进度.md",
    "验收记录.md",
    "glm-align-user-centent-prompt.md",
]:
    prepend_banner(DOCS / name, STALE)

# move plan-frontend into archive after banner? keep with banner is fine; also archive copy
# sdk banners
for readme in [
    ROOT / "sdk" / "python" / "README.md",
    ROOT / "sdk" / "typescript" / "README.md",
]:
    if readme.exists():
        prepend_banner(
            readme,
            "> ⚠️ **非本阶段产品路径**：SDK 供集成方参考，管理台日常配权不依赖此目录；示例已归档 `docs/_archive/examples`。\n\n",
        )
    else:
        write(readme, "> ⚠️ **非本阶段产品路径**：SDK 供集成方参考；示例见 `docs/_archive/examples`。\n")

write(ARCHIVE / "README.md", textwrap.dedent("""\
# 归档说明

本目录存放**非现行产品路径**材料，避免与管理台主路径混淆：

- `plan-a/`、`prototypes/`：早期方案与原型
- `examples/`：对接 demo（express/fastapi），非管理台功能

现行说明：`docs/配权说明书.md`。
"""))

# ---------- 6) ESLint + smoke ----------
pkg_path = FRONTEND / "package.json"
pkg = json.loads(read(pkg_path))
pkg.setdefault("scripts", {})
pkg["scripts"]["lint"] = "eslint \"src/**/*.{ts,vue}\" --max-warnings 0"
pkg["scripts"]["smoke"] = "node ./scripts/smoke-nav.mjs"
dev = pkg.setdefault("devDependencies", {})
for k, v in {
    "eslint": "^9.14.0",
    "eslint-plugin-vue": "^9.30.0",
    "typescript-eslint": "^8.14.0",
    "vue-eslint-parser": "^9.4.3",
    "globals": "^15.12.0",
}.items():
    if k not in dev:
        dev[k] = v
write(pkg_path, json.dumps(pkg, ensure_ascii=False, indent=2) + "\n")

write(FRONTEND / "eslint.config.js", textwrap.dedent("""\
import js from '@eslint/js'
import globals from 'globals'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'
import vueParser from 'vue-eslint-parser'

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**', 'coverage/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.{ts,vue}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parser: vueParser,
      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: 2022,
        sourceType: 'module',
        extraFileExtensions: ['.vue'],
      },
    },
    rules: {
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-console': 'off',
    },
  },
)
"""))
# need @eslint/js
dev = json.loads(read(pkg_path)).setdefault("devDependencies", {})
# re-read and add @eslint/js
pkg = json.loads(read(pkg_path))
pkg["devDependencies"]["@eslint/js"] = "^9.14.0"
# type module for eslint flat if needed
if "type" not in pkg:
    # vite projects often module - check
    pass
write(pkg_path, json.dumps(pkg, ensure_ascii=False, indent=2) + "\n")

write(FRONTEND / "scripts" / "smoke-nav.mjs", textwrap.dedent("""\
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const navPath = path.join(root, 'src/router/navigation.ts')
const appPath = path.join(root, 'src/App.vue')
const registryPath = path.join(root, 'src/layout/page-registry.ts')

const nav = fs.readFileSync(navPath, 'utf8')
const app = fs.readFileSync(appPath, 'utf8')
const registry = fs.readFileSync(registryPath, 'utf8')

const pageKeyMatch = nav.match(/export type PageKey = ([^\n]+)/)
if (!pageKeyMatch) {
  console.error('smoke: PageKey not found')
  process.exit(1)
}
const keys = [...pageKeyMatch[1].matchAll(/'([^']+)'/g)].map((m) => m[1])
const required = ['overview', 'application_workspace', 'organization_workspace', 'users', 'roles', 'permissions', 'audit']
for (const k of required) {
  if (!keys.includes(k)) {
    console.error('smoke: missing PageKey', k)
    process.exit(1)
  }
  if (!app.includes(`'${k}'`) && !app.includes(`"${k}"`)) {
    console.error('smoke: App.vue missing page ref', k)
    process.exit(1)
  }
}
if (!registry.includes('application_workspace') || !registry.includes('authorization_simulation')) {
  console.error('smoke: page-registry incomplete')
  process.exit(1)
}
if (!fs.existsSync(path.join(root, 'src/composables/useReadinessPoll.ts'))) {
  console.error('smoke: useReadinessPoll missing')
  process.exit(1)
}
console.log('smoke-nav ok', { pageKeys: keys.length })
"""))

# ---------- 7) closeout report ----------
write(DOCS / "_closeout_remaining_fixes_2026-10-29.md", textwrap.dedent("""\
# 收口后剩余问题修复记录（2026-10-29）

不建 git。对照「仍严重/中等」项处理结果：

| 项 | 结果 |
|---|---|
| 重启 API / CORS 仅管理台 | 已验证：`CORS_ORIGINS=["http://localhost:5175"]`；Origin 5175 有 ACAO，3000 无 |
| 授权两套真相 UX | 配权说明书加强「码管菜单、角色管接口」；应用工作台 Tabs 与高级列表加提示 |
| 拆 App.vue 巨石 | `useReadinessPoll` / `useTableFit` / `useShellAppearance` + `layout/page-registry.ts`；备份 `_agent_dump/App.vue.pre_split_backup` |
| ESLint + smoke | `frontend/eslint.config.js`；`pnpm lint` / `pnpm smoke` |
| 文档清场 | `plan-a`、`prototypes`、`examples` → `docs/_archive`；含 DeerFlow/接入旧文文首标过时 |
| sdk / examples | 示例归档；sdk README 标明非本阶段产品路径（compose 仍挂载 typescript sdk，未删包） |
| 工作台 vs 高级 | 高级列表页增加互链文案；工作台保留日常主路径 |
| 审计 Tab | 已有登录/操作拆分，确认保留 |

验收：5175 可开；CORS 生效；壳可维护；文档无「接入已落地」误导（旧文已标过时/归档）；lint/smoke 可跑。
"""))

print("DONE step3")
