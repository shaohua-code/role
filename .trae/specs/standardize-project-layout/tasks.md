# Tasks

- [x] Task 1: 配置 @ 路径别名
  - [x] SubTask 1.1: `frontend/vite.config.ts` 增加 `resolve.alias`：`@` → `fileURLToPath(new URL('./src', import.meta.url))`（需 `import { fileURLToPath, URL } from 'node:url'`）
  - [x] SubTask 1.2: `frontend/tsconfig.json` 增加 `"baseUrl": "."` 与 `"paths": { "@/*": ["./src/*"] }`

- [x] Task 2: 目录迁移（仓库无 git 绑定，使用 PowerShell `Move-Item`/`New-Item` 移动，禁用 git 命令）
  - [x] SubTask 2.1: 新建 `src/router`、`src/views`、`src/layout`、`src/api`、`src/utils`、`src/plugins` 目录
  - [x] SubTask 2.2: 移动文件——`app/router.ts`→`router/index.ts`；`app/navigation.ts`→`router/navigation.ts`；`app/featureLoaders.ts`→`router/loaders.ts`；`app/App.vue`→`App.vue`；`app/auth/`→`views/auth/`；`app/components/*.vue`→`layout/`；`app/ui/*`→`plugins/`；`app/icons.ts`→`plugins/icons.ts`；`features/**`→`views/**`（保持子结构）；`shared/services/api.ts`→`api/index.ts`；`shared/services/{capabilities,authCapabilities,health}.ts`→`api/`；`shared/utils/emailValidation.ts`→`utils/`；`shared/theme.ts`→`styles/theme.ts`；`shared/ui/index.ts`→`components/index.ts`
  - [x] SubTask 2.3: 删除空目录 `src/app/`、`src/features/`、`src/shared/`、空 `src/services/`

- [x] Task 3: 导入路径全量改写（约 40 文件，纯机械替换，不改任何逻辑）
  - [x] SubTask 3.1: `main.ts`——`./app/App.vue`→`./App.vue`、`./app/router`→`./router`、`./app/ui/antd`→`@/plugins/antd`
  - [x] SubTask 3.2: `App.vue`——icons→`@/plugins/icons`、ui/antd→`@/plugins/antd`、navigation→`@/router/navigation`、featureLoaders→`@/router/loaders`、auth→`@/views/auth/AuthEntry.vue`、layout 组件→`@/layout/*`、其余 `../components`→`@/components`、`../shared/services`→`@/api`、`../styles/antd-bridge`→`@/styles/antd-bridge`
  - [x] SubTask 3.3: `router/index.ts`——`../shared/services/api`→`@/api`、`../shared/services/capabilities`→`@/api/capabilities`、`./navigation` 保持同目录；`router/loaders.ts`——`../components/*`→`@/components/*`、`../features/**`→`@/views/**`
  - [x] SubTask 3.4: `views/**` 全部页面——`shared/services/api`→`@/api`、`shared/services/capabilities`→`@/api/capabilities`、`shared/utils`→`@/utils`、`shared/theme`→`@/styles/theme`、`app/icons`→`@/plugins/icons`、`app/navigation`→`@/router/navigation`、`../components|../../components`→`@/components`、`shared/ui`→`@/components`；views 模块内部相对引用保留；额外修正 1 处跨模块引用（PermissionsTab `../../applications/...`→`@/views/applications/...`）
  - [x] SubTask 3.5: `components/**` 与 `layout/**`——`../app/icons`→`@/plugins/icons`、`../shared/services/api`→`@/api`；`components/index.ts` barrel 改指 `./`
  - [x] SubTask 3.6: `api/index.ts`、`api/capabilities.ts` 等服务层内部相对引用——capabilities.ts `from './api'`→`from '.'`

- [x] Task 4: 验证（宿主机 frontend/ 目录下执行，corepack 已知损坏，直接用 node）
  - [x] SubTask 4.1: `node node_modules\vue-tsc\bin\vue-tsc.js -b` 零错误（exit 0，主代理亲跑复核）
  - [x] SubTask 4.2: `node node_modules\vite\bin\vite.js build` 零错误（exit 0 约 9.3s，ant-design-vue / vue-vendor chunk 仍拆出；主代理亲跑复核）
  - [x] SubTask 4.3: Grep 复查 `src/` 下无旧路径残留：全部模式零命中（主代理亲跑复核）

- [x] Task 5: 文档同步
  - [x] SubTask 5.1: `frontend/README.md` 更新现存结构描述段（历史带日期条目不改）
  - [x] SubTask 5.2: `CHANGELOG.md` 追加本次条目（迁移映射、别名、验证结果、未运行项）
  - [x] SubTask 5.3: `docs/项目总览与进度.md` 更新——管理台前端行追加本次摘要、任务表新增行、最后同步时间改为本次；注明后端已符合 FastAPI 标准布局未改动
  - [x] 追加修正：本次条目原编 P359 与今日更早「双栏贴底对齐」条目撞号，三文档统一改号为 **P360**（原有 P359 内容未动）

- [x] Task 6（可选，视容器可用性）: 浏览器冒烟走查——三容器 healthy，browser_use 子代理真实登录走查：登录页渲染→登录进 /overview→用户/角色/应用工作台三页→深链刷新守卫，全 PASS；全程无 Vue warning（仅刷新时 1 条健康轮询 ERR_ABORTED 可忽略）；零写操作

# Task Dependencies
- Task 1 无前置（别名先配好，迁移后 import 立即可解析）
- Task 2 依赖 Task 1；Task 3 依赖 Task 2；Task 4 依赖 Task 3；Task 5 依赖 Task 4（验证结果写入文档）
- Task 6 依赖 Task 4，可与 Task 5 并行
