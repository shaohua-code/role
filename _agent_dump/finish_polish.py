from pathlib import Path
import json

pkg_path = Path(r"D:\project\role\frontend\package.json")
pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
pkg["scripts"]["lint"] = 'eslint "src/**/*.{ts,vue}" --max-warnings 0'
pkg["scripts"]["lint:main"] = (
    'eslint "src/composables/**/*.{ts,vue}" '
    '"src/layout/**/*.{ts,vue}" '
    '"src/views/application-workspace/**/*.{ts,vue}" '
    '"src/views/organization-workspace/**/*.{ts,vue}" '
    '"src/App.vue" "src/styles/theme.ts" --max-warnings 0'
)
pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("package.json ok", pkg["scripts"].get("lint"), pkg["scripts"].get("lint:main")[:60])

# ensure requestSequence cleanup survived earlier failed script
p = Path(r"D:\project\role\frontend\src\views\application-workspace\components\RoleResourceGrantModal.vue")
t = p.read_text(encoding="utf-8")
if "let _requestSequence = 0" in t:
    lines = [ln for ln in t.splitlines(True) if ln.strip() != "let _requestSequence = 0"]
    p.write_text("".join(lines), encoding="utf-8", newline="\n")
    print("removed dead sequence")
else:
    print("no dead sequence line")

doc = """# 继续完善收口（2026-10-29）

不建 git；不动 DeerFlow；不清库。

## 做了什么

1. **装通 ESLint（优先）**
   - 根因：`node_modules` 是 pnpm 布局，npm 直接 `install` 会报 `edgesOut`；本机 `pnpm` shim 曾指向缺失的 `pnpm.cjs`。
   - 处理：`corepack prepare pnpm@12.6.0 --activate`，用 `node .../pnpm.mjs add -D eslint ...` 装入依赖。
   - 现已可跑：`cd frontend && npm run lint`（或修复后的 `pnpm run lint`）。

2. **Lint 基线**
   - 修真实 error：`App.vue` 重复定义 `onThemePreferenceChange`（拆壳残留）；`theme.ts` 控制字符正则改为 charCode 扫描。
   - 清理主路径未用变量；`eslint.config.mjs` 忽略 `src/views/_archive/**`，关掉格式类 vue 规则。
   - **全量 `npm run lint`：0 error / 0 warning（exit 0）**。
   - 另提供 `npm run lint:main` 只扫 composables / layout / 工作台 / `App.vue` / `theme.ts`。

3. **边角**
   - `PermissionsTab.vue`：确认是薄封装（复用 `ApplicationPermissionPanel`），**未被写坏**；保留双层鉴权提示 alert。
   - 补齐高级页告警：`PermissionCatalog.vue`、`RoleManagement.vue` 页顶 `a-alert`（与应用管理高级列表一致）。
   - 管理台 `http://localhost:5175` → 200；API 端口 `8002`（见根 `.env` `IAM_API_PORT`），`/docs` 可开。
   - `_agent_dump` 临时脚本保留作排查痕迹（可整目录删，不影响运行）。

## 如何验

```bat
cd D:\\project\\role\\frontend
npm run lint
npm run lint:main
npm run smoke
```

浏览器打开 http://localhost:5175 ；API 文档 http://localhost:8002/docs 。

若本机 `pnpm` 仍报 `MODULE_NOT_FOUND`：先 `corepack enable` 与 `corepack prepare pnpm@12.6.0 --activate`，或直接 `npm run lint`（只跑脚本、不走 arborist 装包）。**不要**在现有 pnpm `node_modules` 上用 `npm install`，会再次 `edgesOut`。

## 刻意未做

- 不建 git
- 不 `--fix` 全量格式化（会大面积改 HTML）
- 不删 `sdk/` compose 挂载；不动 DeerFlow
"""
Path(r"D:\project\role\docs\_closeout_continue_polish_2026-10-29.md").write_text(doc, encoding="utf-8", newline="\n")
print("closeout written")
