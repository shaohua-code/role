# 项目级目录规划梳理（前端结构标准化）Spec

## Why
当前前端结构为自创布局（页面在 `src/features/`、路由散在 `src/app/`、服务层在 `src/shared/services/`），与 Vue 生态标准目录规划不一致，新接手者需要额外学习成本；深层相对导入（`../../..`）在目录调整时脆弱。后端已符合 FastAPI 标准布局（`app/api/v1` + `core` + `db` + `models` + `schemas` + `services` + `migrations` + `tests`），本次不动。

## What Changes
- **前端目录标准化**（用户已确认命名：`router/` + `views/`，并引入 `@` 路径别名）：
  - `src/app/router.ts` → `src/router/index.ts`（路由定义与守卫）
  - `src/app/navigation.ts` → `src/router/navigation.ts`（与路由强关联，同文件夹存放）
  - `src/app/featureLoaders.ts` → `src/router/loaders.ts`（页面异步加载器）
  - `src/features/**` → `src/views/**`（全部 16 个页面模块，含 workspace 的 components/tabs 子结构，内部相对层级不变）
  - `src/app/auth/AuthEntry.vue` → `src/views/auth/AuthEntry.vue`（登录页也是视图）
  - `src/app/App.vue` → `src/App.vue`（根组件提到 src 根，Vue 标准位置）
  - `src/app/components/AppSidebar.vue` / `AppBreadcrumb.vue` → `src/layout/`（仅壳层使用的布局组件）
  - `src/shared/services/` → `src/api/`（`api.ts` 改名 `index.ts`，import 写 `@/api`；`capabilities.ts`、`authCapabilities.ts`、`health.ts` 保持文件名）
  - `src/shared/utils/emailValidation.ts` → `src/utils/emailValidation.ts`
  - `src/shared/theme.ts` → `src/styles/theme.ts`（主题工具与样式强关联）
  - `src/shared/ui/index.ts` → `src/components/index.ts`（共享组件 barrel，改指本地 `./`）
  - `src/app/ui/antd.ts` / `registerManagementUi.ts`、`src/app/icons.ts` → `src/plugins/`（全局 UI 注册与图标）
- **删除**：迁移完成后删除空目录 `src/app/`、`src/features/`、`src/shared/`、空的 `src/services/`
- **配置**：`vite.config.ts` 与 `tsconfig.json` 增加 `@` → `src` 别名
- **导入改写**：全部约 40 个文件的相对导入改为 `@/` 别名导入；`main.ts` 入口同步更新
- **文档同步**：`frontend/README.md` 现存结构描述、`docs/项目总览与进度.md`（P359）、`CHANGELOG.md`（P359 条目）；历史 CHANGELOG 条目与 SKILL.md 历史快照不改
- 后端：**无改动**（已符合项目级目录规划，仅在进度文档记录结论）
- 无业务逻辑、无 UI 行为、无 API 契约变化；**非 BREAKING**（仓库已无 git 绑定，无外部包消费 src 路径）

## Impact
- Affected specs: 无既有 spec；本次为纯结构重构
- Affected code:
  - `frontend/vite.config.ts`、`frontend/tsconfig.json`（别名配置）
  - `frontend/src/**` 全量约 40 个含相对导入的 `.ts`/`.vue` 文件
  - `frontend/README.md`（结构描述段落）
  - `docs/项目总览与进度.md`、`CHANGELOG.md`（交接记录）
- 明确不受影响：`backend/**`、`sdk/**`、`examples/**`、`deploy/**`、Dockerfile（整目录 COPY `src`，无路径级引用）、index.html（入口仍 `/src/main.ts`）

## ADDED Requirements

### Requirement: 标准目录布局
前端源码 SHALL 遵循以下项目级目录规划：

```
frontend/src/
├── main.ts                 # 入口（不变）
├── App.vue                 # 根组件与管理台壳（← app/App.vue）
├── style.css / appearance.css
├── router/                 # 路由层：index.ts（原 router.ts）+ navigation.ts + loaders.ts
├── views/                  # 页面视图：原 features/** 全量 + auth/AuthEntry.vue
├── layout/                 # 壳层布局组件：AppSidebar.vue、AppBreadcrumb.vue
├── components/             # 共享组件（不变）+ index.ts barrel（原 shared/ui）
├── api/                    # 服务层：index.ts（原 services/api.ts）+ capabilities + authCapabilities + health
├── utils/                  # 工具：emailValidation.ts
├── plugins/                # 全局注册：antd.ts、registerManagementUi.ts、icons.ts
└── styles/                 # antd-bridge.ts、tokens.css（不变）+ theme.ts（原 shared/theme.ts）
```

#### Scenario: 页面模块归位
- **WHEN** 打开 `src/views/` 目录
- **THEN** 原 `src/features/` 下 16 个页面模块（含 application-workspace / organization-workspace 的 components、tabs 子目录）与 `auth/AuthEntry.vue` 全部存在且内部层级不变

#### Scenario: 旧目录清除
- **WHEN** 迁移与导入改写完成
- **THEN** `src/app/`、`src/features/`、`src/shared/`、`src/services/` 目录不存在

### Requirement: @ 路径别名
`vite.config.ts` SHALL 通过 `resolve.alias` 将 `@` 映射到 `src`（`fileURLToPath(new URL('./src', import.meta.url))`）；`tsconfig.json` SHALL 声明 `"paths": { "@/*": ["./src/*"] }`。业务代码中的跨目录导入 SHALL 一律使用 `@/` 别名，不再出现跨目录深层相对导入（同文件夹内 `./` 相对导入保留）。

#### Scenario: 别名生效
- **WHEN** 执行 `vue-tsc -b` 与 `vite build`
- **THEN** 所有 `@/` 导入解析通过，构建产物正常拆包（ant-design-vue / vue-vendor chunk 规则不受影响）

### Requirement: 行为零变化
重构 SHALL 不改变任何业务逻辑、路由行为、权限守卫、懒加载拆包与视觉表现；`router/index.ts` 的守卫逻辑、`loaders.ts` 的 `defineAsyncComponent`（loading/error 组件、delay、timeout）配置保持原样。

#### Scenario: 回归验证
- **WHEN** 完成迁移后执行宿主机类型检查与生产构建（`node node_modules\vue-tsc\bin\vue-tsc.js -b`、`node node_modules\vite\bin\vite.js build`，在 `frontend/` 下）
- **THEN** 两者零错误通过；grep 全量检查无旧路径残留（`from '../features`、`shared/services`、`app/icons`、`app/navigation`、`app/router`、`features/`、`shared/ui` 等模式在 `src/` 下零命中）

## MODIFIED Requirements
（无——不修改任何既有功能需求）

## REMOVED Requirements
（无）
