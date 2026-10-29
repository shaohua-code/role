# Checklist

- [x] `vite.config.ts` 与 `tsconfig.json` 均已配置 `@` → `src` 别名，且不影响既有 proxy/manualChunks 配置
- [x] 目录迁移完整：`src/router/`（index.ts + navigation.ts + loaders.ts）、`src/views/`（16 个页面模块 + auth）、`src/layout/`（AppSidebar + AppBreadcrumb）、`src/api/`（index.ts + capabilities + authCapabilities + health）、`src/utils/`、`src/plugins/`（antd + registerManagementUi + icons）、`src/styles/theme.ts`、`src/components/index.ts` 全部就位
- [x] 旧目录已删除：`src/app/`、`src/features/`、`src/shared/`、空 `src/services/` 不存在（Test-Path 全 False）
- [x] `main.ts` 与 `App.vue` 导入路径全部更新且程序可正常启动引用链（dev server `/src/main.ts`、`/src/App.vue`、`/src/router/index.ts` 均 200）
- [x] 全部约 50 个文件导入改写为 `@/` 别名（views 模块内部 `./`、`../components` 相对导入保留），无逻辑改动
- [x] `router/loaders.ts` 异步加载配置（loading/error 组件、delay 120、timeout 30s）与守卫逻辑原样保留（抽查确认）
- [x] `node node_modules\vue-tsc\bin\vue-tsc.js -b` 零错误通过（exit 0）
- [x] `node node_modules\vite\bin\vite.js build` 零错误通过（exit 0 约 9.3s，ant-design-vue 1,220KB / vue-vendor chunk 拆包规则不变）
- [x] Grep 复查 `src/` 下无任何旧路径残留（`shared/services|shared/utils|shared/theme|shared/ui|app/icons|app/navigation|app/ui|app/auth|app/App|app/router|features/` 等模式零命中）
- [x] `frontend/README.md`、`CHANGELOG.md`（P360）、`docs/项目总览与进度.md` 已同步本次事实与验证结果；未运行的验证（后端隔离测试套件）明确标注「未运行」；编号冲突已修正为 P360（原 P359 为今日更早「双栏贴底对齐」条目，内容未动）
- [x] 后端零改动确认：`backend/**` 文件最后修改时间均在本次会话开始之前（属更早会话 P353–P358），本次未触碰
