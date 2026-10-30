# 前端技术与目录说明

**2026-10-29 工作台收口：** 侧栏去掉「应用角色与成员」；角色行「应用权限」「配置成员」。旧深链 `/application-roles` 重定向到应用工作台。验证见根 CHANGELOG。

**2026-10-29 P405：** 权限编码页只展示平台管理面码；高级角色页只列平台角色；工作台只列应用角色，分配时自动成为该应用平台成员。挂码弹窗去掉授权权禁选。验证见根 CHANGELOG。

**2026-10-29 P404：** 拆 `can_create_applications`（只认租户域 `app.manage`）；L2 隐藏新建/删除应用。挂码弹窗消费后端已按操作者级别过滤的目录。验证见根 CHANGELOG。

**2026-10-29 P403：** 侧栏 L1 入口改「运营总览」；租户 `/roles` 标「应用角色与成员」。用户详情抽屉展示有效权限码并集+来源。角色列表服务端真分页；权限目录带 total，超出加载上限时提示。验证见根 CHANGELOG。

**2026-10-29 P402：** 工作台业务码「新建」按 `application.can_manage` 开放给 L2/L3（`ApplicationPermissionPanel`）；启停仍仅 L1。空态三步与无创建权文案、L4 `/no-access` 及应用角色页去掉过时 `iam.*`。验证见根 CHANGELOG；浏览器走查未运行。

## UI 设计规范

- 完整规范与验收要点：[产品需求](../docs/产品需求.md) 第 9 节。
- 新页面必须套 List / Detail / Settings 模板；禁止新增裸 hex 色值。
- **通用组件优先**：有则复用，禁止重复造轮子。
- **目录约定**：`文件夹/index` 写法；有关联关系的文件放同一文件夹。

**2026-10-28 P398 全站工具条筛选条统一重设计：** 全局 `.admin-table-toolbar` 控件宽度改三级体系（搜索 `min(100%,320px)` / 普通下拉 160px / `admin-filter-wide` 长枚举 208px），style.css 为唯一权威源（原一刀切 320px 未分层规则曾压过页面 Tailwind 宽度类致换行参差）；`AdminTableToolbar` 左区 gap-2、右区 `lg:ml-auto` + 细分隔线；清理 8 个页面的失效宽度类与死 scoped 样式；工具条阴影/深色边框 slate 残留改 token。新筛选下拉宽度**不要再写页面级宽度类**，长枚举加 `admin-filter-wide` 即可。验证：`vue-tsc -b` + `vite build` exit 0（10.65s）；浏览器走查未运行（待用户复看）。

**2026-10-28 P397 管理台五页重设计：** 统一「统计带→工具条（搜索+筛选）→精简表格→行点击详情抽屉」信息架构，覆盖 /tenants /roles /permissions /applications /application-workspace。新通用组件：`components/AdminStatBand.vue`（账本式统计卡带，v-model 点击筛选）、`components/AdminDetailDrawer.vue`（详情抽屉骨架）、`components/AdminMonoValue.vue`（mono 值 + hover 一键复制）；`CopyOutlined` 加入 `plugins/icons.ts` 出口。交互约定：详情/浏览类用抽屉、编辑类留弹窗；行点击经 `customRow` 下钻，操作列与行内链接 `@click.stop` 防冒泡；工作台三 Tab 经 `stats` 事件向父级上报计数渲染概览统计条；`/application-workspace?application_id=` 深链预选应用。验证：`vue-tsc -b` + `vite build` exit 0（8.97s）；浏览器走查未运行（本机无后端运行环境，待用户复看）。

**2026-10-27 P360 前端目录标准化（用户裁定按项目级目录规划）：** 纯目录重构，零逻辑/零 UI/零 API 变化，后端零改动（核查已符合 FastAPI 标准布局）。`features/**` → `views/**`（含两个 workspace 的 components/tabs 子结构，`app/auth/AuthEntry.vue` → `views/auth/`）；`app/router.ts` → `router/index.ts`，`navigation.ts`、`featureLoaders.ts`（改名 loaders.ts）归 `router/`；`app/App.vue` 提到 `src/` 根；壳层 `AppSidebar/AppBreadcrumb` → `layout/`；`shared/services/` → `api/`（api.ts 改名 index.ts）、`shared/utils/` → `utils/`、`shared/theme.ts` → `styles/`、`shared/ui/index.ts` → `components/index.ts`；`app/ui/antd.ts、registerManagementUi.ts` 与 `icons.ts` → `plugins/`；删除空目录 app、shared、services。`vite.config.ts` + `tsconfig.json` 配置 `@` → `src` 路径别名，约 50 个文件导入改写为 `@/`（views 模块内部相对引用保留）。新目录结构：

```text
src/
├── App.vue        # 根组件（原 app/App.vue）
├── router/        # index.ts 路由表 + navigation.ts 页面白名单/侧栏项 + loaders.ts 异步页加载
├── views/         # 页面模块（原 features/，含 auth/AuthEntry.vue 与两个 workspace 子结构）
├── layout/        # AppSidebar.vue、AppBreadcrumb.vue 壳层布局
├── api/           # index.ts（原 shared/services/api.ts）+ health/capabilities 探针
├── utils/         # 共享工具（原 shared/utils/）
├── styles/        # theme.ts、tokens.css、antd-bridge.ts
├── plugins/       # antd.ts、registerManagementUi.ts、icons.ts
├── components/    # index.ts barrel（原 shared/ui/）+ AdminXxx 通用组件
└── main.ts / style.css / appearance.css
```

验证：宿主机 `vue-tsc -b` 与 `vite build` exit 0（约 9.3s，antd/vue-vendor 拆包不变，仅存量 antd chunk 体积警告）；grep 旧路径（shared/services、app/icons、features/ 等）frontend/src 零残留；浏览器冒烟（dev 5175 真实登录 admin：登录 → /overview → 用户/角色/应用工作台 → 深链刷新守卫）全 PASS 零 Vue 告警、零写操作；后端隔离套件未运行（零后端改动）。

**2026-10-22 P330 全站换皮：** ConfigProvider 补 Layout/Menu/Card token；顶栏浅色（默认黑底用内联色盖住）；向导选中卡/单组 Steps；内容列 `min-width:0` 避免宽表页级横滚。`vue-tsc -b` 与全路由走查见[验收记录](../docs/验收记录.md)。Vite 生产构建未跑。

**2026-10-22 P329 管理台 antd：** 壳层 `a-layout`/`a-menu`/`a-drawer`/`a-breadcrumb`；总览 `a-statistic`；CRUD 页头 `AdminPageHeader`；接入向导 antd 控件（P328 示例保留）；审计 DatePicker；登录页 readiness `a-alert`。侧栏图标 `src/app/icons.ts`，不要把 `@ant-design/icons-vue` 别名到该文件。`vue-tsc -b` 与登录后走查见[验收记录](../docs/验收记录.md)。Vite 生产构建未跑。

**2026-10-22 P328 接入页向导：** `/project-integration` 改为一次一步手风琴，并补业务侧 env / Python·Node / Vue / curl 示例。验证见[验收记录](../docs/验收记录.md)。

**2026-10-22 P327 接入页双路径：** `/project-integration` 改为公共准备 + 方案 A（OIDC 托管登录）/ 方案 B（HTTP login + check）；可复制示例。`vue-tsc -b` 通过；浏览器走查 A/B、跳转与 375 无页级横滚，见[验收记录](../docs/验收记录.md)。

**2026-10-17 P303 路由与接入页：** 管理台菜单改为 vue-router（history）；`src/app/navigation.ts` 的 `PAGE_PATHS` 映射各 PageKey（如 `/overview`、`/project-integration`）；侧栏 `router-link` 高亮；新增平台页「新项目接入」（Tailwind 步骤指引，F02 部分）。登录前仍 `AuthEntry`；登录后保留 visitedPages 懒加载。`vue-tsc --noEmit` 与 Vite build（`--configLoader runner`）通过；登录后走查见后续 P322/P327。

**2026-10-17 P302 性能：** 有 token 时不再阻塞 `main.ts` mount；App 并行恢复会话并注册管理组件。平台字典后台加载；用户组/授权模拟复用 App 字典。异步页在 `src/app/featureLoaders.ts`；生产构建拆出 `ant-design-vue` chunk。本地 dev 默认不用 watch polling，Docker Compose console 设 `VITE_DEV_USE_POLLING=true`。`vue-tsc --noEmit --pretty false` 与 Vite build（3206 modules）通过；浏览器耗时未运行。

**2026-10-16 P301：** 已登录管理台。1440px 下侧栏折叠为图标，刷新后仍折叠，展开后文字恢复，结束时保持展开。跟随系统后页面可用，已切回浅色。模型用量为空账本，结果/模型/日期筛选可见；无效日期和开始晚于结束有错误提示，日期已清空。375px 使用全页选择器，无页面级横向溢出，下拉选项未点开。刷新后的页面 error/warn 为 0。未跑类型检查或生产构建。详见[验收记录](../docs/验收记录.md)。

**2026-10-16 P300：** 桌面侧栏可折叠为图标、展开后恢复文字导航。偏好只写当前浏览器 localStorage，默认展开；650px 及以下仍用全页选择器。类型检查与 3,205 模块生产构建通过，临时产物已清理。浏览器未登录，未代填密码，折叠和窄屏未点选。详见[验收记录](../docs/验收记录.md)。

**2026-10-16 P299：** 外观增加跟随系统；概览和授权说明改为 DeerFlow 唯一试点、仅本人数据。类型检查与 3,205 模块生产构建通过，临时产物已清理。浏览器未登录，未代填密码。详见[验收记录](../docs/验收记录.md)。

**2026-10-16 P298 模型用量筛选：** 用量页可按结果、模型、UTC 日期筛选汇总和账目；条件变化回到第 1 页并清掉上一范围账本，待核对队列不跟着筛。`vue-tsc --noEmit` 通过。未跑生产构建和浏览器。详见[验收记录](../docs/验收记录.md)。

**2026-10-15 P297 模型用量错误态修复：** 读取失败保留最近成功数据并显示错误；首载失败用“—”和读取错误态，不显示成功空账本；租户切换清理旧范围数据，翻页清理旧页。Vue vue-tsc --noEmit 与 3,205 模块 Vite 构建通过，临时输出已清理；浏览器热更新后正常空态可见，错误注入和多视口未验。详见[验收记录](../docs/验收记录.md)。
**2026-10-15 P296 模型用量 UI 走查：** 当前暗色桌面空态可读；静态检查发现读取失败会清空并显示成功空态（P1），费用无币种且无失败原因字段（P2）。本轮未改源码、未运行构建；详见[验收记录](../docs/验收记录.md)。
**2026-10-15 P295 模型用量 UI：** 新增成功率卡片（0 请求显示“—”）、可见租户标签/全部租户占位；空待核对和用量表分离为加载/空状态，窄屏不裁切，有记录时启用内部滚动。Vue 类型检查、3,205 模块 Vite 生产构建通过，临时产物已清理；浏览器 375/768/1024/1440px 页面无横向溢出，桌面深色空态及 375px 空态布局通过。非空、浅色、核对提交未验；未运行自动化测试。

**2026-10-15 P294 模型用量 UI 复核：** 桌面深色空数据页只读检查发现租户筛选提示不可见，缺少成功率，空待核对表仍显示横向滚动条；账目行、分页、核对提交、浅色主题与窄屏本轮未验。未改前端源码、未运行构建或测试。

**2026-10-15 P293 运行态记录：** 本轮只校正后端运行状态文档，没有修改前端源码或构建。P292 前端类型检查、生产构建及模型用量多视口检查仍是最近验证；IAM 当前 API/database revision/readiness 无法从受限终端核实。详见[验收记录](../docs/验收记录.md)。

**2026-10-15 P292：** 模型用量的零请求/费用未知文案已区分，宽表滚动被限制在卡片内；Ant 管理组件懒加载注册补齐 Badge/Divider。`vue-tsc --noEmit` 与 Vite 生产构建（3,205 modules）通过；浏览器 375/768/1024/1440px 检查无页面级横向溢出。Docker named pipe 与 API localhost 检查因本机权限失败，故数据库 revision/readiness 未知。非空表格/核对提交、浅色主题未验；构建临时目录已清理。详见 [验收记录](../docs/验收记录.md)。

**2026-10-15 P291 模型用量 UI 走查：** 桌面暗色空数据页只读检查发现页面级横向溢出；费用为 `null` 且请求数为 0 时显示“未配置价格”，文案有歧义。未改 Vue 源码，未运行类型检查、构建或测试；浅色/窄屏、分页、非空账目与核对弹窗未验。详见 [验收记录](../docs/验收记录.md)。

**2026-10-15 P290（P291 补充）：** IAM 前端源码本轮未修改；P286 的 vue-tsc/Vite build 是历史源码验证，不代表当前浏览器登录验收。P291 浏览器可见模型用量页，但未核验 API/数据库；P288 的 Docker/API 不可达仍是最近一次运行态探测，revision/readiness 未知。DeerFlow B04 的未分片 Windows 离线套件为 17,149 passed、404 skipped、3 deselected、1 failed；唯一失败是 DeerFlow guidance 预算超 478 bytes，按用户要求未重跑。

**2026-10-14 16:40 迁移完成（历史操作记录；当前运行态未知）：** 开发库已迁移至 0031、`/api/v1/ready` 200，登录页"数据库待迁移"门禁应随 readiness 轮询自动解除（或点击"重新检查"），登录/注册/找回密码/应用授权入口解锁。管理员 `admin@example.com`（密码在根 `.env`，已随机重置）。Vue 源码未修改；真实登录与管理页面走查（A04）待用户以管理员凭据执行。

**2026-10-14 15:10 登录入口复查（历史）：** 用户截图显示“数据库待迁移”，同轮 API `/api/v1/ready` 只读请求返回 503 `database_migration_pending`。登录控件继续禁用符合当前门禁；未修改 Vue 源码，也未运行前端构建或真实登录。

**2026-10-14 P284：** IAM Vue 源码未改；Compose console 内对当前只读挂载源码重新运行 vue-tsc -b 与 Vite production build，3205 modules 通过，构建输出留在容器 /tmp。当前 API readiness 为 503 database_migration_pending（DB 0021、源码 head 0031）；真实登录/浏览器认证仍未验收，且本轮未迁移数据库。

**待迁移提示的操作入口：** [快速启动指南](../docs/快速启动指南.md)现列出管理员核对版本、备份、恢复演练及授权后迁移的步骤。本文档更新不改变登录页行为；本次未运行 Vue 构建或浏览器验收。

**2026-10-14 DeerFlow B04 验证同步：** 后 104 文件切片最新结果 **2,368 passed、2 failed、86 skipped、4 warnings**（通知超时修复前）；后续通知/lifecycle + 扩展管理器/API pin 定向回归 **126 passed、40 skipped**。本轮未改 IAM Vue 源码/API；IAM Vue 类型检查、Vite 构建和浏览器验收未运行。用户提供的登录页提示数据库待迁移，本轮没有执行 migration；部分 DeerFlow 测试结果不代表全量或目标环境验收。当前状态见[项目进度](../docs/项目总览与进度.md)。

**2026-10-13 文档整理：** 管理台需求及接入侧 UI 边界见 [产品需求](../docs/产品需求.md)，UI 历次记录见 [验收记录](../docs/验收记录.md)，最新状态见 [项目总览与进度](../docs/项目总览与进度.md)。本轮只改文档引用，未运行前端构建或浏览器验收。
**2026-10-13 DeerFlow B04 状态：** 本轮未改 Vue 源码/API；前端 `src/AGENTS.md` 历史数据流说明已压缩并通过 guidance 体积门槛。DeerFlow 最新三组后端测试 171 passed、1 skipped，Ruff check/format 通过；IAM Vue 类型检查/Vite 构建本轮未运行，最近通过证据仍为 2026-10-11。最近完整 DeerFlow 后端 suite 为 17,062/142/349/3/0（82 warnings，44:15），早于该轮测试夹具修正，完整重跑待后续；IAM readiness 和真实浏览器登录仍未验收。

**2026-10-12 DeerFlow Provider 路径审计：** 本轮只读审计 DeerFlow 后端模型调用入口，未改 IAM Vue 源码、页面或 API 契约，也未运行前端检查；IAM readiness 仍为 503，真实登录与浏览器联调未验收。

**2026-10-12 试点同步：** 本轮改动在 DeerFlow 后端记忆模型计量路径，未修改 IAM Vue 源码、页面或 API 契约，也未运行前端检查；最近前端类型检查与 Vite build 证据仍为 2026-10-11。IAM API readiness 503，真实登录与浏览器联调仍待环境恢复。

**2026-10-12 DeerFlow B01 映射状态：** 本轮只读核对了后端 permission map/catalog，没有修改 Vue、前端 API 或 UI；最近前端构建证据仍为 2026-10-11。模型/工具资源 grant 与角色配置待 IAM 数据库升级及部署输入，浏览器真实登录未验收。

**后续验收入口（2026-10-12）：** [当前进度与后续计划](../docs/项目总览与进度.md) 的 A04/C03 跟踪 IAM 管理操作、权限分层、主题发布与响应式验收。当前 API readiness 503，最近 Vue 类型检查/Vite 构建通过记录为 2026-10-11；本轮仅整理交接文档，未改 Vue 源码或重跑构建。后续修改须同步交接进度。

**2026-10-12 迁移门禁复核：** 本轮未修改前端代码，也未重跑构建。只读探测 Console HTTP 200、API readiness 503；Docker CLI 已恢复并只读核实开发库 revision `0021_resume_wallet_perms`，但 API readiness 仍为 503，真实登录仍未验收。迁移 `0022–0031` 不会自动开启 ToC 注册或授予角色；详情和不可逆回滚点见 `docs/部署与运维.md`。最近一次前端类型检查和生产构建仍是 2026-10-11。

**2026-10-12 清理复核：** 前端代码未发现 TODO/FIXME/NotImplemented 占位。工作区 7 个过期 pytest 临时根目录已删除并逐项验证不存在；没有删除测试源码，也没有运行测试。

**2026-10-12 启动状态：** Console HTTP 200，API readiness 最新为 503 `database_migration_pending`。执行终端的 Docker 命令解析到无法启动的系统路径，不能读取容器或 DB 版本；Vue 源码未修改，真实登录仍未验收。

**2026-10-12 DeerFlow 文件名兼容复验：** 本轮没有改 IAM Vue 源码或 API 契约，因此没有重跑前端构建。DeerFlow 项目/文档/线程/运行四组后端路由回归在 Windows 短临时根目录下 **225/225 通过**，Ruff check/format 通过；长显示名由后端映射到短内部磁盘名，前端继续使用原始文件名。IAM 登录仍受 API readiness `503 database_migration_pending` 阻断，完整全量后端套件未通过。

**2026-10-12 运行状态与数据规则：** DeerFlow 首阶段按用户决定只允许本人读取和修改自己的项目、线程、运行与文档；当前 IAM Console HTTP 200，但 API readiness 为 `503 database_migration_pending`，登录/真实 OIDC 验收仍受迁移门禁阻断。本轮没有修改 Vue 源码或 API 契约；最近一次 Vue type-check 和 3205 模块 Vite production build 仍是 2026-10-11 的结果。本轮 DeerFlow IAM 后端专项回归 169/169 通过；全量 Windows 重跑中途因 `WinError 10106` 退出，不能据此声称前端或全系统端到端通过。

**2026-10-12 集成状态：** 本轮未改变 IAM Vue 页面或 API 契约，因此未重跑前端构建。最近一次 Vue type-check 与 Vite production build（3205 modules）通过；DeerFlow Python readability fallback 修复后的 web-fetch 回归 50/50 通过，Ruff 通过。修复前全量后端快照为 16,750 passed、442 failed、345 skipped、3 deselected，阻塞 I/O 为 116 passed、26 failed、1 skipped；后续全量结果见本文件 2026-10-12 最新状态；全量仍未通过，短路径重跑中断，失败原因未全部归因。真实 IAM/DeerFlow 在线授权与浏览器端到端验收仍待开发库迁移和部署角色配置。

**2026-10-11 模型治理分页 UI：** 待核对队列与历史用量账目均从服务端分页接口读取真实总数；租户/页大小变化后回到第一页，账目使用稳定倒序。`verify-local.ps1` 的 Vue 类型检查与 Vite production build（3205 modules）通过。页面认证仍受开发 IAM 库 `0021` 落后于源码 `0031` 的 readiness 门禁阻断。

**2026-10-11 模型治理分页：** 历史用量账目改为服务端 total/offset 分页；租户或页大小变化后回到第一页，账目总数和当前页由 API 响应驱动。待核对列表继续显示真实总数并处理最后一页记录。完整 `verify-local.ps1` 的 Vue 检查与 3205 模块生产构建通过。浏览器运行复查显示“数据库待迁移”，登录按钮保持禁用。

**2026-10-11 本轮部署核验：** 未改 Vue 页面或前端 API，因此本轮没有重跑前端构建；最近一次全量前端类型检查及生产构建通过（3205 modules）。只读备份预检通过，但 API readiness 仍为 HTTP 503 `database_migration_pending`；DeerFlow 登出继续采用本地清理策略。

**2026-10-11 DeerFlow 浏览器实时流鉴权：** 本轮没有改 IAM Vue 页面或前端 API；DeerFlow 后端 WebSocket 建连前新增 `threads:read/write` 与当前线程 owner/self data_scope 检查。前端构建未重跑，因为前端代码没有变化；真实浏览器 IAM/WebSocket E2E 仍待运行环境就绪。

**2026-10-11 DeerFlow 个人偏好授权：** 本轮未改前端交互；现有偏好 API 在 Central IAM 模式下要求 `preferences:read/write` 与本人 data_scope。部署方需在 IAM 注册 `deerflow.preference.read/write` 并映射到 DeerFlow、显式分配角色 grant 与本人范围；该权限由 migration `0030_deerflow_preference_permissions` 登记，当前源码 head 已为 `0031_model_usage_reconciliation`，开发库未迁移，真实登录联调未验收。

**2026-10-11 DeerFlow runtime 构建状态：** dev 镜像与 adapter import smoke 通过；runtime/生产镜像未生成，Docker Hub/GHCR 元数据请求 EOF，需 registry/mirror 后复验。本轮未修改前端代码。

**2026-10-11 DeerFlow 打包状态：** 本轮未改前端。IAM Vue readiness 门禁构建结果保持通过；DeerFlow Gateway dev 镜像最终生成，uv 虚拟环境中的 IAM adapter import smoke 通过；本轮未改 Vue，也未启动服务。

**2026-10-11 数据范围边界：** 本轮未改 Vue；后端模型核对确认 DeerFlow tenant/organization 字段不足以映射共享资源，当前 owner/self UI 与权限行为保持不变，越界范围由后端 fail closed。

**2026-10-11 前端状态：** 本轮未修改前端；补充验证的是 IAM SDK 与 DeerFlow 后端的异步授权回归：SDK 22/22、互操作 12/12 通过。

**2026-10-11 readiness 核验：** API /api/v1/ready 返回 503 database_migration_pending，开发库 revision 0021_resume_wallet_perms，当前源码 head `0031_model_usage_reconciliation`。备份预检通过但未创建归档或写数据库；当前 readiness 未恢复。

**2026-10-11 登录页 readiness 交互：** 初始检查/数据库待迁移/数据库不可用时显示状态提示，阻断登录、注册、重置密码、邀请接受及 OIDC 授权提交；有效邀请/授权票据在 IAM 恢复前不误报过期，并于 ready 后重载上下文。Vue 类型检查与 3205 模块生产构建通过；浏览器 AX 确认数据库待迁移提示和禁用登录按钮。

**2026-10-11 模型用量核对 UI：** 模型用量页增加 10 分钟未结调用队列和管理员核对表单。核对可记录 Provider 侧实测/估算用量，或在明确确认 Provider 未被调用后释放；队列不会自动收费或释放。DeerFlow Provider 完成到 outbox 提交之间仍无法自动还原 Token，真实 IAM/Provider 和迁移验收未完成，配额强制继续关闭。

**2026-10-11 模型治理界面边界：** DeerFlow Gateway 已接入逐次 LangChain 模型调用 reserve/settle callback；IAM 管理台现展示未结预留并提供管理员核对、审计和手动结算/释放入口。IAM 数据结构新增 `0031_model_usage_reconciliation`，当前开发库仍为 `0021_resume_wallet_perms`、readiness 503，未迁移或验证新功能。真实 IAM/Provider 及配额验收未完成；`MODEL_QUOTA_ENFORCEMENT_ENABLED` 继续关闭。

**2026-10-11 服务就绪状态复核（登录页门禁改造前）：** 当前 Console 根页 HTTP 200，API readiness 返回 503 `database_migration_pending`；登录页已将该稳定错误码映射为“数据库待迁移”，显示重查入口。该次复核发生在本次 readiness 门禁改造前；服务恢复需管理员先完成受保护备份并获准将开发库从 `0021_resume_wallet_perms` 迁移到当前源码 head `0030_deerflow_preference_permissions`。

**2026-10-11 DeerFlow Console API 授权契约：** 后端聚合报表现在按返回内容分别要求 `deerflow.run.read`、`deerflow.thread.read`、`deerflow.agent.read` 对应的 Gateway permission 和 owner/self data_scope；IAM Vue 页面与前端代码未修改。本次只验证后端 25/25 路由回归和 Ruff，没有做浏览器验收或前端构建。部署管理员需在 DeerFlow 对应应用角色中显式配置所需授权，migration 不自动发 grant。

**2026-10-11 DeerFlow memory worker 提交前复核：** 仅更新 DeerFlow 后端 worker 的写入前权限复查；IAM Vue 页面、SDK 和前端 API 契约没有变更。后端 updater/data-scope/commit callback 回归 109/109 通过；本轮没有执行前端构建或浏览器验收，真实 IAM 页面联调仍待部署环境及角色 grant。

**2026-10-11 DeerFlow OIDC 登出状态：** 本次补充的是后端 RFC 7009 客户端和 Discovery metadata 单元回归，未改变 IAM Vue、浏览器 API 或 DeerFlow 前端。用户已确认登出仅清理本地会话，不向 issuer 发送服务端 vault token。OIDC/vault mock 回归 41/41 通过，未做浏览器或真实 IAM 验收。

**2026-10-11 前后端隔离验收更新：** Console Vue/TypeScript 检查与 Vite production build（3205 modules）通过，模型治理页包含账目与待核对队列的服务端分页。后端完整套件在空隔离 PostgreSQL 数据库迁移至源码 head `0031_model_usage_reconciliation` 后 **169/169 通过**。主开发库仍为 `0021_resume_wallet_perms`，API readiness 503；真实浏览器与 IAM/Provider E2E 尚未完成。

**2026-10-10 技能更新响应授权：** 自定义技能编辑和回滚返回完整正文，后端要求同时拥有技能读/写权限与本人数据范围；前端没有改动。跨切片后端联合回归 141/141 通过；全量后端隔离验证见上方 2026-10-11 记录。

**2026-10-10 联合验证结果：** 本轮未改前端代码；后端 connectors、runs、Agent 兼容路由、skills、MCP、subagents 与 channel worker 授权合并回归 138/138 通过。IAM Vue 类型/构建和真实浏览器链路未在本轮验证。

**2026-10-10 Gateway 管理入口授权同步：** 本轮仍未修改 IAM Vue 页面；DeerFlow IM worker 状态与重启入口也已接入 channels:read/admin，界面需按当前 IAM grant 显示状态或管理员操作结果。后端管理资源组合回归 81/81 通过。

**2026-10-10 DeerFlow 管理资源授权同步：** 本轮未改 IAM Vue 页面或浏览器组件。Gateway 已把技能读写/删除、共享子 Agent 目录、MCP 管理入口纳入 Central IAM；个人技能读取与变更还检查本人范围。回归 79/79 通过，真实 IAM 权限配置与浏览器验收仍待部署方完成。

**2026-10-10 DeerFlow 连接器权限边界：** 本轮只修改 DeerFlow Gateway 服务端与配置示例，没有改 IAM Vue 页面、组件或浏览器接口。个人 IM/Lark 路由现在需要中央功能权限及本人 data_scope；部署级设置/安装需本地管理员和中央管理员双重授权。后端 57/57 回归通过，浏览器与真实 IAM 联调仍待部署配置和 migration 就绪。

**2026-10-10 无状态运行授权同步：** 本轮只修改 DeerFlow Gateway，在 `/api/runs/stream` 和 `/api/runs/wait` 的运行创建前补 Central IAM `runs:create` 数据范围检查，未改 IAM Vue 页面或浏览器接口；旧 `/api/assistants/*` 读取已复用 `agents:read`/本人 data_scope。真实浏览器联调仍待部署配置就绪；后端定向回归 28/28、Ruff check/format 通过。

**2026-10-10 DeerFlow 定时任务授权同步：** 本轮改动仅在 DeerFlow Gateway；IAM Vue 页面、组件与接口未修改。DeerFlow 手动触发在当前 IAM 会话/授权失效时会收到 403 或 503，客户端应保留错误提示；调度器后台因撤权暂停任务并停止排队执行。真实 IAM/API 与浏览器联调仍受 IAM migration/readiness、DeerFlow Compose 和部署配置阻塞。

**当前平台联调状态（2026-10-10）：** IAM 开发库为 `0021_resume_wallet_perms`，源码 head 为 `0027_deerflow_resource_permissions`；API `/api/v1/ready` 返回 `503 database_migration_pending`。DeerFlow 调度授权组合回归 126/126 通过属于隔离代码验证，不能作为真实浏览器联调通过的依据。

**DeerFlow 模型权限同步（2026-10-10）：** 本轮调整的是服务端 IAM adapter 和配置样例，没有修改 Vue 页面或前端接口。服务端现支持按 IAM 模型 UUID 判定 `model.invoke`、按模型列表权限独立过滤，并允许按工具名授权；真实用户的模型选择、拒绝态和调用仍须在 IAM migration/角色 grant 配置完成后做浏览器验收。

**DeerFlow 项目资料范围补齐（2026-10-10）：** 本轮只修改 DeerFlow Gateway 服务端项目/文档/回收站路由与测试，未修改 IAM Vue 页面、组件或接口；相关服务端路由回归 92/92 通过，Ruff 检查通过。

本轮扩展了 DeerFlow 服务端 owner-bound 线程/运行操作的数据范围门禁，没有改动前端；鉴权回归 101/101 通过，组合后端路由回归 532 项通过（1 个公网 DNS 用例受断网环境限制而排除）。

**待执行 migration 数据影响审查（2026-10-10）：** 只读审查 0024_tenant_registration_audience 的升级会清空并删除旧注册 challenge 的暂存密码摘要列；0025_registration_role_snapshot 会将所有未消费的旧邮箱 OTP challenge 标为已消费，用户需重新发起注册验证。该行为是迁移设计的一部分，执行前必须先完成受保护备份并取得明确维护窗口授权；本轮未执行 migration。

**本轮只读运行核验（2026-10-10）：** IAM Compose 的 API unhealthy、console/PostgreSQL healthy；IAM 开发库为 0021_resume_wallet_perms，源码 head 为 0027_deerflow_resource_permissions，宿主机绕过代理直连核验：console 5175 和 API 根路径 8002 均返回 HTTP 200；API /api/v1/ready 返回 503 database_migration_pending，API 容器因此 unhealthy。DeerFlow 开发 Compose 当前没有运行；根 .dockerignore 已排除 Python pytest/ruff/mypy/hypothesis 缓存，修复构建上下文读取 backend/.pytest_cache 被拒绝的问题；gateway dev 镜像 deer-flow-dev-gateway:latest 已构建成功，断网一次性容器成功导入 deerflow.authz.iam_deerflow、app.gateway.authz 与 app.gateway.routers.agents。源码 Alembic head 为 fd_0027_repair_run_change_seq（父版本为 0026_iam_oidc_token_vault），目标数据库版本尚未核验。本轮未启动服务、迁移数据库或修改环境凭据。
**此前隔离验证快照（2026-10-10，源码 head 0027）：** verify-local.ps1 的后端完整套件 161/161 通过；console 镜像内 vue-tsc -b 与 Vite production build 通过。更新的 0029 后端结果和本轮前端未改动状态见本文件顶部。

本轮新增的是 DeerFlow Gateway Agent API 权限边界，不涉及 IAM Vue 页面或组件。自建 Agent 读、写、删分别要求 `agents:read/write/delete`；创建/更新还需要读取权限，因为响应包含完整 Agent 配置。部署级共享 `USER.md` 使用 `agents:admin`。UI 入口展示不构成授权，最终权限由 Gateway 判定；真实 IAM 管理页授权与浏览器闭环待验收。

2026-10-10 后端授权、PAT、`/auth/me` 与 Agent 路由互操作回归 **90/90 通过**，本轮未修改 Vue 代码，因此未重跑前端构建。

本轮 DeerFlow 接入改动仅涉及 Gateway 资源授权，没有修改 IAM 管理台 Vue 页面，也没有向浏览器暴露 IAM token。IAM 管理员需按 [接入清单](../docs/部署与运维.md) 配置 DeerFlow 资源权限映射。

> 本轮没有修改 IAM 管理台 Vue 页面。当前唯一业务试点为 DeerFlow；AI Resume 与 Knowledge Base 的产品专属 IAM 登录入口和调用代码已清理。本文中旧产品集成/构建记录仅作历史追溯，不代表当前产品接入状态。

更新时间：2026-10-11。此目录只包含 IAM 管理控制台 Vue 3 前端，不包含任何外部产品登录或鉴权代码。

DeerFlow 是唯一首个产品接入试点；本轮没有修改 IAM 管理台 Vue 页面、组件或接口。AI Resume 与 Knowledge Base 的产品专属 IAM 登录、鉴权及数据范围调用已从对应仓库移除。

已验证：Knowledge Base console 的 TypeScript contracts 类型检查通过；Vite production build 通过（1652 modules）。IAM 管理台最近一次完整 build 为 2026-10-09（vue-tsc 与 Vite），本轮未修改其源码。

## 2026-10-09 · 用户会话管理

用户管理表格新增“会话”入口，可查看该用户当前可续期的 IAM 管理台与 OIDC 业务应用会话，并确认后远程退出单条会话。列表显示应用、client ID、会话起始和刷新凭证到期时间；当前没有浏览器/设备名、UA、来源 IP 和最后活动时间。管理员不能在用户管理中远程退出当前自己的账号，会提示使用页面右上角的安全退出。该 UI 已连到 `GET /admin/users/{id}/sessions` 和 `POST /admin/users/{id}/sessions/{type}/{session_id}/revoke`。`vue-tsc -b` 与 Vite production build 通过；会话实现阶段在 `0024` 上的隔离套件为 152/152，后续含 `0025` 的完整套件为 161/161。真实浏览器 API 写入与会话弹窗视觉验收尚未做。

## 2026-10-09 · ToC 自助注册界面

注册页第一屏只提交邮箱、姓名及用户协议/隐私确认，不显示或收集密码；验证码发送后进入第二屏，新用户设置至少 12 位密码，已有 IAM 用户输入当前密码。重发验证码会清空旧验证码、保留第二屏已输入密码，并依服务端冷却时间显示倒计时；离开注册流程时清除。后端核对用户当前看到的政策 URL 与版本，管理员更新链接或版本后旧验证码申请失效；默认角色、权限目录、资源级授权或数据范围变化时，旧挑战也会失效，用户需重新申请验证码。租户管理区分 `organization` 和 `consumer`；只有消费租户允许逐应用开放自助注册，切换类型前必须先关闭旗下所有应用。前端冻结依赖构建 `vue-tsc -b` 与 Vite production build 通过（3205 modules）；后端完整隔离 PostgreSQL 套件迁移至 `0025` 后 161/161 通过。没有提交真实浏览器注册或 SMTP；开发库仍为 `0021`，API readiness 为 503。

ToC OIDC 登录页现在只在 `/oidc/login-context` 返回注册可用且已发布主题 `show_register=true` 时显示注册入口。用户先提交邮箱、姓名和条款确认，再输入邮件验证码与新密码/已有账号当前密码；第一屏没有密码控件，重发验证码清空旧验证码并保留第二屏密码，离开注册页时清除，成功后恢复原 OIDC authorize URL。重发倒计时读取 login-context 的服务端冷却秒数，不固定假设为 60 秒。前端不提交 tenant、role 或管理员标志。已有账户加入应用时仍须证明原密码。

应用管理表单可配置该应用的 `disabled/open` 策略、默认普通角色及协议版本；登录主题编辑器可设置用户协议/隐私 URL 和注册入口展示。`show_register` 只是展示条件，不能绕过全局 `ALLOW_PUBLIC_REGISTRATION`、应用策略或后端资格检查。注册开关默认关闭；源码 migration head 为 `0027_deerflow_resource_permissions`，最近确认开发库为 `0021_resume_wallet_perms`、API readiness 因 schema 落后返回 503。开发库未迁移，隔离 suite 161/161 只覆盖至 `0025`；没有浏览器邮件注册验收。

## 2026-10-09 · OIDC 租户声明接口变化

本轮未改 Vue 源码。IAM OIDC 签名 ID Token 新增 `tenant_id` 声明，Discovery 已公布该 claim；浏览器不得据此自行决定管理员身份或权限，权限仍由服务端判定。

## 2026-10-09 · DeerFlow OIDC 账号权限约定

DeerFlow 的 OIDC 首次登录账号由后端以普通用户创建；前端不得根据邮箱、provider 配置或按钮状态推断管理员身份。管理员能力须由后端接入 IAM 后按显式授权结果下发，IAM access/refresh token 不进入浏览器状态；浏览器只持有本地 HttpOnly 会话 cookie。IAM permission 映射与真实浏览器联调仍未完成。

## 2026-10-09 · 本地登录凭据更新

本轮未改前端源码。IAM 管理员密码已在服务端重置，旧刷新会话已撤销；开发环境新密码保存在仓库根目录被 Git 忽略的 `.env` 中（`IAM_ADMIN_PASSWORD`），登录后需重新建立会话。Compose 健康检查及 API readiness 已通过；没有执行浏览器登录验收。前端配置与构建产物不保存账号密码或服务端密钥。

## 最新 UI 走查（2026-10-09）

管理员浏览器在 503×871 窄屏只读检查工作台、租户、应用、用户、邀请、用户组、组织、角色、权限、授权模拟、模型目录/用量、登录主题空状态和审计日志。角色页 410px 固定操作列曾盖住首屏数据；应用、用户组和应用角色也有宽操作列压缩信息。窄屏下这些表格改由表格本身横向滚动，角色、应用和用户组页复核后字段标题重新可见，未产生整页横向溢出。打开应用创建弹窗并滚动到底确认取消/保存按钮可达，未提交。

修正授权模拟资源 ID 输入的静态字符串 `maxlength`，并将其余 Vue SFC 的数值 `maxlength` 属性统一改为数值绑定。完整 `npm run build`（`vue-tsc -b` + Vite）通过，3205 modules，入口 382.70 KB / gzip 118.73 KB。平台管理员会话无法验收租户管理员专属页面；当前无 OAuth 应用记录，登录主题编辑/发布及实际登录预览仍无法验收。本轮结论：**部分验证，待验收**。

历史集成快照（2026-10-09；2026-10-10 已撤销）：当时权限目录包含 AI Resume 钱包/工作区权限码与前端呈现说明；该产品 IAM adapter 与对应 IAM 权限入口均已清理。

历史集成快照（2026-10-09；2026-10-10 已撤销）：当时简历工作区由后端调用 IAM 检查；该产品当前使用自身本地认证与授权。

认证入口仅解析一次 `invite`、`consent`、`password-reset` URL fragment；捕获凭据后立即使用 `history.replaceState` 清除地址栏与当前历史记录项，token 只留在当前页面内存以完成原有流程。

生产配置预检会在 `nginx -t` 外同时校验 Compose、Caddyfile 和 API 生产配置；执行入口与镜像前置条件见[运维手册](../docs/部署与运维.md)。该检查只验证配置解析，不代表真实域名、TLS 或浏览器流程已经验收。

登录主题中的 `show_register` 控制入口可见性，但服务端还要求全局注册总闸、当前 OAuth 应用 `open` 策略、活动租户、合格普通角色、SMTP、已发布主题与协议链接全部有效。任何前端显示都只是体验层；后端 `/auth/register` 和 `/auth/register/verify` 会独立复核。

## 登录失败限流反馈（2026-10-04）

共享 API 错误保留 `Retry-After` 秒数；公开登录页收到 IAM `429` 时显示可读等待时间。其他请求继续使用通用状态码错误，不自动重试登录，也不保存邮箱或密码。2026-10-04 `vue-tsc -b` 与 Vite production build 通过（3205 modules，入口 382.31 KB / gzip 118.56 KB）；2026-10-05 服务端登录节流/维护、授权模拟、模型配额契约和生产配置离线定向测试共 30 项通过，4 项 PostgreSQL 集成用例跳过（复用 DeerFlow 现有 Python venv）；仍未提交真实超限登录，429 等待提示的视觉和读屏验收待真实 API/浏览器环境。

认证、管理、OIDC 审计列表中的 `source_ip` 由服务端按照与登录节流相同的可信代理解析器生成，覆盖 OIDC 授权和登出事件。浏览器不发送或推断审计来源地址；本次没有改动前端行为。相关后端回归 5/5 通过，生产 CDN/LB 实际来源解析仍待部署验收。

本地登录台通过根目录 Docker Compose 启动；首次启动和访问地址见[快速启动指南](../docs/快速启动指南.md)，API 502 排查见[部署与运维](../docs/部署与运维.md)。

## 前端构建与服务历史核验（2026-10-07）

本轮 `vue-tsc --noEmit` 通过，Vite 生产构建生成 3205 个模块（入口 382.51 KB / gzip 118.65 KB），产物写入 Windows Temp。console `5175` 返回 HTTP 200、API OpenAPI 返回 HTTP 200；`/api/v1/ready` 在该次核验时返回 `503 database_migration_pending`，因此不能进行登录态管理页面或数据库业务验收。该次核验时最近一次成功的只读数据库版本为 `0016_permission_status`，源码 head 为 `0021_resume_wallet_perms`。`0017`–`0021` 当时迁移尚未执行；该次未提交认证请求或写数据库。开发 Compose 普通启动不会迁移或引导管理员，显式 `migrate`、`bootstrap` profiles 执行对应一次性操作。

管理侧栏使用 `/api/v1/ready` 判断数据库和 Alembic 状态，不再把 `/health` 的进程存活当成业务已就绪；每 30 秒刷新，并把迁移待处理、数据库异常、迁移状态异常和 API 连接失败映射为中文状态。当前 API 迁移未完成时会显示“数据库待迁移”。

探针请求有 5 秒超时，并与认证会话恢复并行；公开认证页和已登录侧栏共享一个状态。异常提示提供手动重查，手动操作与 30 秒轮询使用同一个在途请求。登录、邀请、密码重置和找回表单通过 Ant Design Vue 字段规则提前校验必填、邮箱格式、密码长度和确认密码；找回邮件通过 `#password-reset=` URL fragment 交付一次性 token，不放入 query string；邀请只要求输入密码，以保留已有账号使用当前密码接受邀请的路径。最终 Vue 类型检查与 Vite production build 通过（3205 modules，入口 381.97 KB / gzip 118.41 KB）；由于本机 `pnpm` shim 无法启动，使用 `node_modules/.bin` 中已安装的 `vue-tsc`、`vite` 二进制直接执行。Vite 已返回包含新规则的认证组件模块 HTTP 200；新浏览器标签的无障碍树确认就绪提示、必填标记与登录控件可见，未提交请求；错误态视觉/交互尚未验收。

首批系统接入所需登录主题素材域、租户/应用映射和登录开通策略见[待提供配置与决策清单](../docs/部署与运维.md)。

公开认证入口在就绪状态异常时显示稳定原因码对应的中文提示，不隐藏密码/OIDC/邀请/重置表单，也不展示数据库 revision 或底层异常；状态恢复后提示自动消失。定制登录主题使用固定高对比警告样式，确保应用主题文字色不会降低诊断提示的可读性。

历史跨产品接入快照（2026-10-07；2026-10-10 已撤销）：当时 Resume 与 Knowledge Base 曾有 IAM/OIDC 权限及 data_scope 代码；相关集成已从对应产品仓库清理。DeerFlow 是当前唯一 IAM 业务试点，接入状态与剩余验收见[接入计划](../docs/技术架构与接入.md)。

## 认证入口浏览器走查（2026-10-03）

控制台登录入口同时面向平台管理员和已获授权的租户/应用管理员；登录后的可见工作台仍由服务端授权决定。公开登录页和找回密码页已在桌面及 390px 视口检查，提交登录、邮件或密码请求需要可用的用户凭证。修正文案后 `vue-tsc --noEmit -p tsconfig.json` 通过；Vite production build 转换 3202 个模块，入口 378.27 KB / gzip 117.37 KB。

## 技术栈

- Vue 3 Composition API、TypeScript 5、Vite 8、Vue SFC。
- 依赖由 `pnpm-lock.yaml` 完整锁定，仓库声明 `pnpm@12.6.0`；生产镜像在安装前复制 lockfile 并使用 `pnpm install --frozen-lockfile`。
- Ant Design Vue 4 提供表单、表格、弹窗、Layout/Menu/Drawer、向导 Steps/Collapse、消息、主题令牌和 ConfigProvider。
- Tailwind CSS 4 通过 Vite 插件接入；`src/style.css` 只保留 OIDC 登录主题变量、主题预览画布、≤575 弹窗宽度和减少动效，管理台交互不再靠自定义壳层 class。
- 管理 API 使用短期 Bearer 访问令牌，令牌只保存在当前标签页的 `sessionStorage`；服务端另发 HttpOnly、SameSite=Lax 刷新 Cookie。并行 401 请求共用当前页面的续期 Promise；支持 Web Locks 的浏览器还会串行化同源标签页续期，避免一次性 refresh token 被并发消费。退出或认证失败时，`BroadcastChannel` 会通知同源其他标签页清除 access token；不支持该 API 的浏览器只清除当前标签页。续期后原请求最多重放一次。服务端撤销当前 JWT 和刷新会话；其他已签发的离线 JWT 最长仍可被直接重放至到期。非开发环境 Cookie 使用 Secure；Cookie 路径限定为 `/api/v1`，普通 API 仍必须显式提供 Bearer。

## 目录

```text
frontend/
├── index.html
├── package.json
├── pnpm-lock.yaml           # pnpm 12.6.0 依赖锁
├── pnpm-workspace.yaml       # 显式批准 core-js 安装构建脚本
├── Dockerfile                # 依赖安装、Vue 类型检查和生产构建
├── Dockerfile.production     # 构建 Vue 静态资源并交给 Nginx 托管
├── nginx.production.conf     # SPA 回退、同源 API/Discovery 反向代理、安全响应头
├── vite.config.ts
└── src/
    ├── App.vue                # 登录后会话、a-layout 壳层和页面装配（P360 起位于 src 根）
    ├── router/
    │   ├── index.ts           # vue-router 路由表（原 app/router.ts）
    │   ├── navigation.ts      # 页面白名单、侧栏项和面包屑标题
    │   └── loaders.ts         # 异步页面加载器（原 app/featureLoaders.ts）
    ├── views/                 # 页面模块（原 features/）：access-control、applications、
    │                          #   application-roles、application-workspace、audit、auth、groups、
    │                          #   integration、invitations、models、overview、organizations、
    │                          #   organization-workspace、permissions、roles、tenant-admin、
    │                          #   tenants、themes、users
    ├── layout/                # AppSidebar.vue（桌面 a-menu 与窄屏 a-drawer）、AppBreadcrumb.vue
    ├── api/                   # index.ts 认证 API 请求、health/capabilities 探针（原 shared/services/）
    ├── utils/                 # 共享工具（原 shared/utils/）
    ├── styles/                # theme.ts、tokens.css、antd-bridge.ts
    ├── plugins/               # antd.ts 公共组件注册、registerManagementUi.ts、icons.ts
    ├── components/            # index.ts barrel + AdminPageHeader、加载/错误反馈等通用组件
    ├── main.ts                # Vue/Ant Design Vue 启动
    ├── style.css              # OIDC 主题变量、预览画布、窄屏弹窗
    └── appearance.css         # 外观覆盖（P329 后基本清空）
```

`frontend/` 是独立 Vue 工程，只包含 Vue、TypeScript 和浏览器侧 API 调用；Python 路由、ORM 模型和迁移仅存在于同级的 `backend/` 工程。两边不共享源码，通过 `@/api`（`src/api/index.ts`）和 HTTP/OpenAPI 契约协作。OIDC 授权、令牌、用户信息和登出协议实现仅位于后端 `app/api/v1/oidc_provider/`，前端不持有客户端密钥、签名私钥或服务端 SDK 凭证；签名公钥重叠由 API 的 JWKS 端点发布给 OIDC relying party。工作台、每应用登录主题、用户组、成员邀请、授权模拟、审计查询、模型治理、权限目录、角色授权、租户目录、OAuth 应用、单应用角色、用户、组织管理和租户委派管理分别由 `views/overview/`、`views/themes/`、`views/groups/`、`views/invitations/`、`views/access-control/`、`views/audit/`、`views/models/`、`views/permissions/`、`views/roles/`、`views/tenants/`、`views/applications/`、`views/application-roles/`、`views/users/`、`views/organizations/` 和 `views/tenant-admin/` 管理。用户 feature 自管用户查询/创建/启停、活动租户角色绑定及成员组织归属，并在组织归属保存时保留已有停用组织；组织 feature 自管租户过滤、组织创建/层级和启停；租户委派 feature 自管当前授权租户中的成员搜索、组织归属读取/替换、角色权限读取和角色数据范围读取/替换。应用角色 feature 自管单应用角色 CRUD/启停、业务权限预览与原子替换、已授权成员查询和直接绑定移除；权限预览展示直接绑定/用户组继承成员去重数及逐权限的通用授权覆盖估算，不能新增 `iam.*` 权限。仅允许绑定现有活动租户成员，用户组关系仍只读显示。只读身份可以查看允许范围内的租户资源，修改入口仅在 manage 权限下开放，服务端逐请求重新授权。模型 feature 自管目录/用量请求，租户 feature 自管租户生命周期，应用 feature 自管 OAuth 客户端列表、回调校验、资料编辑、信任策略、密钥轮换及一次性密钥展示，邀请 feature 自管列表筛选、表单校验、创建/撤销和只展示一次的邀请链接，审计 feature 自管只读查询和操作编码筛选，角色 feature 自管角色 CRUD/启停、权限变更预览与数据范围编辑，权限 feature 自管稳定编码目录的检索、创建、停用/恢复确认及关联角色影响提示。`views/auth/AuthEntry.vue` 负责公开登录、OIDC consent、邀请接受与登录主题展示；`src/App.vue` 负责登录后会话、当前页状态和页面装配。`router/navigation.ts` 是页面键/标题/导航项的单一来源，`layout/AppSidebar.vue` 负责桌面 `a-menu`、窄屏 `a-drawer` 与健康状态展示。前后端项目与代码目录继续分离。完整工程边界见[架构说明](../docs/技术架构与接入.md)。

管理页面使用 `defineAsyncComponent` 做领域级代码拆分；15 个管理 feature 仅在首次导航时创建并请求自身 chunk，创建后以 `v-show` 保持挂载，避免离开页面时丢失表单草稿和筛选状态。共享加载提示与错误刷新提示位于 `components/FeatureLoading.vue` 和 `components/FeatureLoadError.vue`。Ant Design Vue 公共组件在 `plugins/antd.ts` 先行注册，管理专用组件位于异步导入的 `plugins/registerManagementUi.ts`，管理员登录或恢复标签页会话后才完成注册；当前宿主机临时目录构建转换 3205 modules，主入口 chunk 为 378.96 KB（gzip 117.51 KB)，管理注册 chunk 为 285.65 KB（gzip 83.80 KB)，应用角色 chunk 为 15.40 KB（gzip 5.68 KB），最大 chunk 低于 500 KB 且 Vite 无体积告警。

## 已实现页面

应用角色权限候选请求携带当前 `role_id`；服务端只返回该角色自己的历史 `iam.*` grant，避免权限弹窗展示同一应用其他角色的系统授权记录。

- 管理员登录：`POST /api/v1/auth/login`；身份查询 `GET /api/v1/auth/me`；401 时调用 `/api/v1/auth/refresh` 轮换 HttpOnly 刷新会话。共享续期 Promise 与 Web Locks 分别处理页面内并发和支持 Web Locks 浏览器的同源标签页并发；退出撤销当前刷新会话及管理 access JWT、删除 Cookie 并清除当前标签页访问令牌。
- API 后台周期任务只回收已到期、不能再用于认证的会话/JWT 撤销摘要/OIDC 授权码/同意票据；不改前端会话协议或页面行为，也不触碰 OAuth 刷新族与其重放检测记录。
- 工作台：从 API 读取租户、应用、用户和角色统计。
- 租户目录独立位于 `views/tenants/TenantManagement.vue`，支持创建、启停、成员数查看和租户标识即时校验；停用确认说明其会撤销旗下 OAuth 刷新会话，创建/启停后 Shell 会刷新给其他表单使用的租户字典。
- OAuth 应用目录收口到 `views/application-workspace/`：左树租户 / 应用节点「⋯」菜单第一项「新建应用」（至少一个合法登录回调，最多 20 个；HTTPS 或 localhost HTTP），其余为编辑 / 密钥 / 受信 / 启停 / 删除。租户、Client ID、回调白名单创建后只读。Client Secret 只展示一次。侧栏「高级管理」只留平台角色 / 权限编码 / 用户组。应用角色与成员只在应用工作台配置。
- 审计日志位于 `views/audit/AuditLogPage.vue`，使用 `/admin/audit/search` 只读服务端分页，顶部按「管理操作 / 登录与认证」两 Tab 分类（登录 Tab 传 `action_prefix=auth.` 由服务端前缀过滤，分页计数真实）；支持按操作、结果、目标类型/ID、操作者 UUID、租户 UUID 和带时区的起止时间精确筛选；详情弹窗展示租户上下文和变更摘要。页面每页 10–100 条，后端最多 500 条、offset 上限 100000。
- 成员邀请位于 `views/invitations/InvitationManagement.vue`，独立管理租户筛选、邀请创建/撤销、角色与有效期校验及一次性 bearer 链接；服务端创建响应使用 `Cache-Control: no-store`，链接仅在组件状态短暂展示，关闭展示框时清空。SMTP 邀请邮件由服务端可选启用、默认关闭；发送状态明确展示，失败时保留一次性备用链接。公开接受流程仍由认证入口处理。
- 用户管理位于 `views/users/UserManagement.vue`，支持邮箱/姓名查询、限长校验的用户创建、停用时会话影响确认、用户所属活动租户中的角色绑定（P345 起为 a-transfer 穿梭框：列表展示中文名称，应用角色附带应用名，仍可按英文标识搜索；停用且未绑定的角色禁止新勾入，已绑定的停用角色保留可移除）、活动成员的多组织/主组织归属；服务器端仍验证租户边界。组织目录收口到 `views/organization-workspace/`：左树租户 / 组织节点「⋯」菜单第一项「新建组织」（组织节点预填上级），其余为负责人 / 启停 / 删除。选中后「成员 / 用户组」Tab。成员 Tab 走 `GET /admin/organizations/{id}/members` 只读浏览，用户组 Tab 按所选组织所属租户整租展示并复用共享 `GroupRelationModal`。独立列表已归档到 `views/_archive/organizations/`。
- 租户委派工作台按每个租户分别发现组织和应用能力，并过滤侧栏入口。`views/tenant-admin/TenantAccessManagement.vue` 继续提供成员组织归属和角色数据范围；应用工作台按 `apiPrefix` 读取平台全局目录或逐租户目录。应用权限既可授给租户范围角色，也可由绑定 `application_id` 的应用角色限定到单个应用；应用目录响应携带逐行 manage/secret.rotate 能力。新建客户端要求租户级 manage，已登记客户端的资料/启停按该应用 manage 控制，密钥轮换还需独立权限；受信状态仅平台管理员可修改。按钮权限只改善操作呈现，服务端仍逐请求鉴权。
- 应用角色与成员在 `views/application-workspace/` 的「角色」Tab 配置：行内「应用权限」抽屉（权限编码 + 资源树 + 数据权限）和「配置成员」抽屉。「配置成员」用「增加成员」弹窗从本租户成员多选绑定，走 `GET .../member-candidates` + 现有 PUT bind。独立页已归档到 `views/_archive/application-roles/`。
- 登录后由 `GET /auth/me/capabilities` 单次判定 consoleMode（platform/tenant/no_access，P340）；平台模式侧栏以运营总览为 L1 入口、应用/组织工作台为日常主路径。成员页支持租户成员搜索、组织归属替换、读取角色已授予权限并配置数据范围；用户详情抽屉展示有效权限码并集与来源。后端仍逐请求复核权限。没有获授权租户的用户看到 403 空状态。
- 模型目录和用量独立位于 `views/models/ModelGovernancePage.vue`。模型页支持按租户筛选、目录新建/编辑/启停，配置端点、能力、价格、RPM/TPM 和外部 Secret Manager 引用；凭证不回显，更新时留空保留、显式清除需勾选。启停请求提交当前读取到的 `expected_status`，遇到并发修改会提示冲突并重载目录，避免过期表单覆盖新状态。用量页展示按租户汇总和最近 100 条调用账目，均不含 Prompt/响应正文。
- 登录主题位于 `views/themes/LoginThemeManagement.vue`，每个应用单独保存/发布并保留版本历史。除布局、品牌色、卡片位置/宽度/圆角和可选背景/Logo 地址外，外观细节可配置背景图位置、缩放和遮罩、卡片背景色/透明度、文字颜色、字体预设、Logo 尺寸、卡片阴影/内边距、输入框与按钮圆角及按钮高度；桌面/手机预览即时响应。可选图片地址可清空。`styles/theme.ts` 将历史或异常值限制到安全颜色、数值和预设；后端仍是最终校验权威。素材只支持 HTTPS 或站内地址，不支持上传、任意 CSS/HTML。
- 角色管理位于 `views/roles/RoleManagement.vue`，独立负责角色目录、租户/应用/状态服务端筛选、**真分页**（`limit/offset` + `total`）、创建、名称/说明编辑和启停；身份字段创建后只读。权限列「N 项」打开挂码弹窗；只读账号仅能查看权限。用户角色绑定仍由用户页面处理。应用工作台角色 Tab 按当前应用拉目录（平台模式带 `kind=application&application_id`）。
- 权限目录位于 `views/permissions/PermissionCatalog.vue`，独立管理稳定权限编码、资源类型、Scope、说明、搜索/创建、启停和关联角色数。日常筛选用平台/业务卡带 + 搜索，五域与命名空间在「更多筛选」。编码不支持编辑或物理删除；停用保留授予与数据范围并让服务端判权拒绝，恢复会重新激活仍保留的历史授予，页面需二次确认并提示影响。应用工作台权限 Panel 以中文描述为主列，登记时锁定应用命名空间前缀。
- 角色复制在角色列表操作中提供：新角色标识/名称可修改，租户、应用范围和启停状态沿用源角色。默认不复制权限；每次可显式勾选复制目录仍启用的通用/资源级授权与对应数据范围；直接成员绑定和用户组角色绑定绝不复制。复制完成后可在新角色上独立编辑授权。`POST /api/v1/admin/roles/{role_id}/clone` 与隔离后端用例 6/6、前端 `npm run build` 已验证，真实浏览器提交尚未验收。
- 角色通用权限修改先读取真实授予列表，再预览新增/撤销、直接绑定活动成员覆盖面和关联数据范围清理项；保存前需确认预览，后端以一个事务原子提交。资源实例授权与通用授权分开显示和维护，相关编辑状态均归角色 feature。
- 成员邀请页可选租户/活动角色和 1 小时至 14 天有效期，创建链接只展示一次且可复制；可按租户查看邀请状态并撤销待处理邀请。默认由管理员经可信渠道发送；启用 SMTP 投递时显示发送结果，失败仍可使用创建响应中的一次性链接。
- 邀请接受页显示邮箱、租户、角色及过期时间；新账号设置 12+ 位密码，已有账号输入当前密码以安全绑定原身份。token 使用 URL fragment，接受后清除地址栏片段。
- 登录页可按当前应用的 `show_forgot_password` 主题开关展示忘记密码入口；邮件找回通过已发布主题展示，token 从 URL fragment 读取后移除。ToC 产品登录页在服务端注册策略开放时提供 OTP 自助注册；IAM 管理台仍显示邀请/管理员引导说明。注册成功后清理表单中的密码与验证码并返回原 OIDC 流程。
- 组织管理页可按租户维护部门树、父级及启停；用户可在实际所属租户内绑定多个组织并指定主组织；角色的每个已授予权限可配置本人/组织/下级/指定组织/租户数据范围。
- 数据范围编辑由受保护管理 API 保存；业务接口请求 `include_data_scope=true` 后会得到服务端解析的 `any_of` 条件，每个条件均包含 `tenant_id`，本人范围额外含 owner 字段。PostgreSQL 集成覆盖本人、组织树、租户范围、指定组织并过滤异租户组织 ID、缺失策略拒绝；业务项目仍必须将 tenant 条件 AND 到每个 OR 分支，并在各自真实数据源验收过滤。
- 授权模拟页可按用户、租户、应用、权限码和资源 ID 只读预演线上规则；结果显示判定原因、逐项检查、命中角色和数据过滤约束。数据范围解析可单独关闭，模拟不会写入权限或业务数据。
- 用户组独立页面支持按租户建组、批量添加成员、批量分配同租户角色和停用/启用；建组/编辑表单在客户端校验租户、组标识与字段长度，避免无效提交。清除租户过滤查看全量数据时，表格仍显示每组所属租户。停用组立即停止继承角色但保留配置；最近一次开发 PostgreSQL revision `0010_tenant_user_groups` 与相关后端集成用例记录为 2026-09-29，登录态浏览器管理交互仍需验收。
- 模型目录支持编辑提供方、名称、端点、能力、价格、RPM/TPM 和外部 Secret Manager 引用；编辑时凭证默认保留，可显式清除。租户与模型标识不可更改；清空 RPM/TPM 可移除相应阈值。限额是否生效由后端 `MODEL_QUOTA_ENFORCEMENT_ENABLED` 开关决定，并在模型列表标注当前是否拦截，见 [模型网关决策稿](../docs/技术架构与接入.md)。
- 模型用量页展示网关账目及过期未结调用的核对队列；管理员核对动作写入审计，手工账目标记来源与估算状态。用量记录不含 Prompt 或响应内容。RPM/TPM 拦截仍由默认关闭的服务环境开关控制；管理台没有配额执行开关，模型供应商代理和实际网关接入仍未完成。
- 应用登录主题配置：管理表单维护文案、品牌色、背景/Logo 地址、布局/卡片细节、条款和隐私 URL，并提供桌面/手机预览、草稿和发布版本。OIDC 登录页只读取已发布主题；`show_forgot_password` 控制找回入口，`show_register` 控制注册入口是否展示，但必须同时满足服务端应用策略与全局总闸。默认租户由应用 tenant 绑定、普通角色由应用策略绑定；migration、SMTP 实际投递和浏览器注册全链路尚未验收。
- OIDC 登录请求会显示对应应用品牌，登录后回到经过本站路径校验的授权请求。非受信任客户端展示同意页，列出应用、租户与请求范围，并提供拒绝/批准；管理员可在应用列表明确设置受信任状态，受信任客户端仍可通过 `prompt=consent` 展示同意页。页面应用已发布主题，票据只从 URL fragment 短暂读取并立即移除。11 项后端 PostgreSQL OIDC 集成通过，覆盖 token introspection 与撤销；真实客户端完整浏览器 E2E 尚待配置。图片只接受 HTTPS 或本站绝对路径。
- 接入业务的 OIDC RS256 access token 可用于授权判定接口；IAM 后端在线校验 token 用途、租户、应用、用户、成员与角色，令牌的租户/应用上下文不可由请求体切换。ID Token 不可代替 access token。
- 仓库 `sdk/` 中的 TypeScript/Python 授权客户端和 PostgreSQL scope 编译器仅供业务服务端使用；请求数据范围必须提供服务端已验签 session 的 tenant 和 IAM OIDC `sub`，不是产品本地用户主键。SDK 逐分支校验 tenant/owner 条件，并将固定业务列映射与身份解析回调交给服务端仓储；值使用查询参数，空组织列表生成零行条件。subject 只用于 SDK 本地校验，不发送给 IAM；缺失/畸形条件 fail closed。Node 在线授权请求默认 3 秒、TypeScript OIDC RP 网络请求默认 5 秒，超时返回服务端 503，绝不允许因此放行或重试授权码/refresh rotation。Vue 浏览器代码不得传入可信身份、持有 client secret/网关密钥或调用授权接口。
- 历史业务 SDK 安全边界（Resume IAM adapter 于 2026-10-10 已移除）：业务产品的 IAM/OIDC client secret、PKCE verifier 和 refresh token 只能保存在服务端；前端不得承载密钥或长效令牌。当前唯一业务接入示例为 DeerFlow，实际集成范围见接入计划。
- Python 数据范围测试 11 项、TypeScript 授权测试 7 项和 TypeScript strict build 已通过；业务仓储仍须完成租户、所有者与组织映射，并在真实 SQL 查询中执行 PostgreSQL 谓词。向量检索需要业务适配层实现等价过滤，现有业务系统尚未完成真实数据查询验收。
- Python 后端项目可复用 [IAM OIDC relying-party/授权 SDK](../sdk/python/README.md)；登录回调、PKCE verifier、Client Secret 与 refresh token 均必须在业务后端和服务端 session 中处理，浏览器只持有本业务站点的 HttpOnly session cookie。
- Node.js 后端项目可复用 [TypeScript IAM OIDC relying-party SDK](../sdk/typescript/README.md)，该模块仅用于服务端；前端 bundle 不得加载 Client Secret、PKCE verifier 或 IAM refresh token。end-session helper 返回含 `id_token_hint` 的短时浏览器跳转 URL，IAM Uvicorn access log 已隐藏整个 query string，生产 Nginx 只记录 `$uri`；业务 RP、CDN、负载均衡器及其他代理访问日志仍需脱敏。Nginx 语法检查与后端 4 项脱敏单测已通过。
- RP SDK 也提供使用同一个 confidential client 凭据的 `introspectToken`/`introspect_token` 实时令牌状态查询；这只能由业务后端调用，浏览器不能获得 client secret 或令牌 introspection 权限。
- TypeScript SDK 有独立 `tsconfig`/build script；主控制台 Compose 构建不会打包或类型检查该独立 SDK 包。
- Docker Compose 升级会在 API entrypoint 中自动先执行 Alembic migration；升级前备份、隔离恢复演练和回退边界见 [运维手册](../docs/部署与运维.md)。
- 管理台外观：浅色/深色、品牌主色和紧凑/舒适密度，当前偏好只保存在浏览器本地。
- 管理页面提供统一刷新入口；停用记录前二次确认；401 事件会同步清空 Vue 登录态，避免令牌过期后仍展示后台。
- 用户停用由服务端立即阻断现有访问令牌并撤销所有刷新会话；重新启用后用户须重新登录，旧 Cookie 不会恢复访问。
- UI 样式保持表格/表单易读字号，工作台统计卡片按屏幕宽度重排；桌面使用 `a-layout-sider`+`a-menu`，650px 以下改为汉堡 + `a-drawer` 同一套菜单，列表工具栏在窄屏换行，主题预览适配手机布局。

## API 服务约定

开发环境普通 `docker compose up` 不再运行 Alembic 或引导管理员；有审查和授权后，使用 `docker compose --profile migrate run --rm migrate` 单独迁移、使用 `docker compose --profile bootstrap run --rm bootstrap-admin` 首次创建管理员。生产发布仍由独立 migration job 控制。早期运行复核记录保留为历史快照，不代表当前 readiness 或 schema 对齐状态。

2026-09-30 本地浏览器只读检查确认公开找回入口和密码重置表单可呈现，并确认打开带预览 fragment 的链接后地址栏片段已移除；没有提交表单或调用邮件/重置服务。本轮将源码复制到系统临时目录，复用本地依赖直接运行 `vue-tsc -b` 和 Vite production build，通过（3198 modules；入口 371.37 KB / gzip 115.31 KB；管理注册 chunk 285.61 KB / gzip 83.78 KB）；项目工作区未生成构建产物。

页面统一调用 `@/api`（`src/api/index.ts`），不得各自拼接请求头或读取令牌。服务端返回 401 时客户端先尝试刷新一次；续期失败后清除当前令牌并同步登录态。无权、校验失败和服务错误通过 Ant Design Vue message 显示。控制台包含平台/租户两种界面模式；菜单裁剪只改善导航体验，服务端逐请求授权才是访问控制。

Vite 开发代理将 `/api` 转发至 `http://127.0.0.1:8000`；可通过 `VITE_API_PROXY_TARGET` 修改。`pnpm build` 是本项目构建命令。2026-10-03 `vue-tsc --noEmit` 与 Vite production build 通过，转换 3205 个模块。平台管理员保留完整导航；租户导航按 `org.read/manage` 与 `app.read/manage/secret.rotate` 能力显示组织、成员/数据范围和应用页。单应用角色工作台由独立 `application-roles` feature 提供，应用管理员只能维护当前应用业务角色/权限并分配已有活动租户成员；新授予管理面码（五域前缀）被服务端拒绝。应用权限候选按当前 `role_id` 查询，应用权限可为租户范围或单应用范围，新建需租户级 manage，已登记客户端的操作按逐应用能力控制，密钥轮换使用独立权限，受信状态保留平台管理员专属。最新主入口 chunk 为 378.96 KB（gzip 117.51 KB），应用角色 chunk 15.40 KB（gzip 5.68 KB），管理组件注册 chunk 285.65 KB（gzip 83.80 KB）；最大 chunk 小于 500 KB。Vite 本地页、`App.vue` 和新增应用角色 SFC 模块都返回 HTTP 200；本机 API OpenAPI 确认目录接口要求 `role_id`，匿名 role-list 返回 401；未登录租户管理员会话，故菜单授权、数据状态、弹窗写入和移动端真实渲染尚未验收。

Docker 开发环境通过根目录 `compose.yaml` 启动；默认浏览器地址为 `http://localhost:5175`，API 由 Vite 代理到 `api:8000`。开发镜像构建会先运行 `vue-tsc -b` 和 Vite production build，之后容器使用 Vite 热重载服务。为兼容 Docker Desktop/Windows bind mount 的文件事件传播，Vite 开发服务器每 1000ms 轮询一次源码；重启 console 容器后，`/src/App.vue` 返回 200 且含 13 个动态页面导入，再次修改宿主机源码后 2.5 秒内模块响应也反映新内容。领域页面已按需拆包，Ant Design Vue 组件仍由主入口全局注册，后续优化方向为组件级按需导入。

生产镜像由 `Dockerfile.production` 构建 Vue 静态站点并在 Nginx 8080 端口提供服务。Nginx 将 `/api/*` 与 OIDC Discovery 转给内部 API，并设置 CSP、MIME、防嵌入、Referrer、Permissions 与缓存响应头；由于 Nginx 1.27 的 location 级 `add_header` 会替换 server 级列表，`/assets/*` 和 `/index.html` 显式重复安全头，避免 SPA 入口或静态 chunk 漏头。同源部署不需要浏览器跨域配置。CSP 允许受控主题所需的 HTTPS 图片和 Ant Design Vue 的内联样式，不允许脚本内联、对象嵌入或跨站 API 连接。Nginx 不采信浏览器转发头；登录来源 IP 由 Caddy 覆写的专用头提供，前置 CDN/LB 时仅在 Caddy 显式配置可信 CIDR 后启用真实客户端解析。生产部署前可通过 `../deploy/validate-production.ps1` 同时预检 Compose、Caddyfile 与 Nginx 配置；完整步骤见[运维手册](../docs/部署与运维.md)。此前本机已构建生产静态管理台镜像并检查 `/healthz` 与 SPA 根页响应；本次响应头配置尚未通过生产镜像或真实浏览器重验，真实域名、TLS 和登录后的页面验收仍未完成。

## 本地运行

业务控制台可以使用 IAM OIDC RP SDK，浏览器不得持有 client secret。各项目现有登录边界、数据隔离约束和接入验收见 [业务系统接入计划](../docs/技术架构与接入.md)。

IAM 登录入口基础布局曾做桌面与 390px 手机截图走查；后续新增的 readiness 提示和手动重查按钮只完成无障碍树确认，需重新做截图验收。开发与生产容器的 Vue/TypeScript 构建通过。2026-09-30 当前开发控制台 `http://localhost:5176/` 返回 HTTP 200，只证明 SPA 首页可访问；本轮没有管理员登录态，登录后的管理页逐页/窄屏浏览器验收仍待完成。模型限额编辑与执行状态标记受后端服务配置控制；管理员资料字段和 OAuth/角色身份字段受后端白名单约束，详见 [UI 走查记录](../docs/验收记录.md)。

```powershell
pnpm install
pnpm dev
```

运行要求 Node.js 20.19+ 或 22.12+；当前环境 Node 24 满足版本要求。依赖安装须在具有可写临时目录和 pnpm 包缓存的环境执行。

## 外部业务系统接入状态（2026-10-10）

DeerFlow 是唯一活跃的产品接入试点，IAM 管理控制台不代理产品认证或判权。AI Resume 和 Knowledge Base 旧有的 IAM/OIDC 登录、中央权限/data_scope 调用、专属配置、测试与 API 契约已从对应产品仓库删除；保留各产品自己的本地认证与业务功能。此前本节记录的逐系统实现细节均为已撤销接入的历史快照。

## 业务端权限界面边界

IAM 管理台只管理平台身份、角色和授权，不把界面隐藏当作业务系统的后端权限检查。DeerFlow 是当前唯一试点；AI Resume 与 Knowledge Base 当前不持有或调用 IAM token。

## 2026-10-09 · 登录字段属性类型与验证状态

邀请密码、重置密码及邮箱输入框的长度约束改用数值绑定，符合 Ant Design Vue 输入组件属性类型。Vite 生产构建通过（3205 个模块，输出到 Windows Temp）；`vue-tsc --noEmit` 被依赖树类型解析问题阻塞（Vue 的 `@vue/runtime-dom`、`@vue/compiler-dom` 类型未解析）。未联网安装包；本会话无法连接 Docker Desktop Linux Engine，浏览器控制台和实际表单校验仍待运行时验收。

### 2026-10-09 · 用户本机服务状态

用户终端截图显示 console 容器 healthy，端口映射为 5175→5173。尚无浏览器页面/控制台证据，不能据此确认登录 UI 或认证流程可用；API 容器在截图时仍处于启动健康检查阶段。

### 2026-10-09 · 控制台服务状态

浏览器当前 readiness 提示“数据库不可用”，对应 `database_not_ready`。管理台页面可加载，但 API/数据库端到端不可用；没有提交认证表单或业务请求。需结合 API 日志确认数据库连接原因。

### 2026-10-09 · 服务不可用根因

容器日志确认数据库密码认证失败（用户 `iam`）；前端显示的数据库不可用来自 API readiness，不是登录组件错误。迁移未连接数据库、未执行 schema 变更。密码修复后再验证 UI 状态。

## 本地服务状态（2026-10-09）

本地 console 容器 healthy，浏览器 http://localhost:5175/ 可加载公开认证入口；API readiness 已恢复为 HTTP 200 ok。本轮只确认页面可达及服务提示消失，没有提交认证请求或验收登录态页面。数据库认证及迁移结果见本地启动指南（../docs/部署与运维.md）。
## 本地登录凭据轮换（2026-10-09）

配置管理员密码已重置，并由后端密码重置流程撤销旧 IAM/OIDC 刷新会话；此前登录状态需要重新登录。新密码只保存在根目录 .env，本轮未修改认证界面或提交登录请求。console 保持 healthy，公开认证入口继续使用 http://localhost:5175/。

## 2026-10-09 · 管理台 UI 响应式修复

`style.css` 限制管理 feature 网格、卡片和表格容器的最小宽度，避免应用/模型宽表格把整页撑出视口；横向滚动保留在表格区域。深色主题表格表面与卡片令牌统一，空状态文字对比度提高，表格滚动条使用深色配色。管理员浏览器在 1680px 桌面与 390px 窄屏复核了应用/模型页面；模型请求期间仍见 HTTP 500 提示，接口根因未定位。Vite 生产构建通过（3205 模块，入口 382.49 KB / gzip 118.64 KB）；`npm run build` 的 Vue 类型检查因本地 Vue 类型声明链解析问题失败，未联网安装依赖。登录主题编辑器因当前无应用记录未覆盖。验证范围和缺口见 [UI 走查记录](../docs/验收记录.md)。

### 2026-10-09 · 字典失败恢复与页面复核

`App.vue` 对平台端租户、应用和角色字典请求增加并发去重及失败后的导航重试，避免首次加载失败后创建入口一直禁用。浏览器复核用户页显示 2 个账号、“新建用户”可用；模型页正常显示空目录态且“新建模型”可用。后端租户目录 500 已修复，原因和服务端状态见 [UI 走查记录](../docs/验收记录.md)。Vite 构建通过；`vue-tsc -b` 仍因本地 Vue 类型声明依赖链无法解析而失败。

### 2026-10-09 · 标准构建与可复现安装

Windows pnpm 安装通过工作区 `publicHoistPattern` 暴露 Vue 声明依赖；冻结离线重装后 `npm run build` 的 `vue-tsc -b` 与 Vite 均通过（3205 modules，入口 382.70 KB / gzip 118.73 KB）。`AuthEntry.vue` 将可选标题样式回退为空对象，满足 Vue `StyleValue` 类型。Dockerfile 复制 `pnpm-lock.yaml` 并使用 `--frozen-lockfile`；仅本机前端构建已验证，Docker 镜像尚未构建。


### 2026-10-09 · 管理台视觉复查

对平台管理员可见的核心目录、授权模拟、模型、主题和审计页面做了桌面浏览器只读走查，并检查两种主题。健康状态徽标改用正确成功色；外观弹层文本改用主题次级文字令牌并提高字号。`npm run build`（Vue 类型检查 + Vite）通过；手机视口及登录主题实际预览尚未验收，记录见 [UI 走查](../docs/验收记录.md)。


### 2026-10-09 · 联合验收补充

前端类型检查与生产构建通过；配套后端完整 unittest 套件在迁移至当前 head 的隔离 PostgreSQL 数据库中通过 109/109。临时测试库已清理，开发库未改动。完整 UI 验收缺口见 [UI 走查](../docs/验收记录.md)。

### 2026-10-09 · 生产预检工具状态

前端源码/依赖构建没有变化。生产部署预检脚本现可在 Windows 自动选择真实 `docker.exe`，避免系统应用执行别名冲突；PowerShell 语法和 Compose 示例配置解析通过。生产环境文件、Caddy 镜像及登录主题发布验收仍待准备，完整预检尚未运行。

### 2026-10-09 · 部署备份工具

前端代码不变。根目录新增 PostgreSQL 单次备份脚本及只读 `-ValidateOnly`，当前 IAM 开发 Compose 的数据库认证和 `SELECT 1` 检查通过；未生成包含账号数据的归档。正式导出需显式指定受保护的主机目录；生产环境加密、保留和恢复演练仍由部署流程配置，详见 [运维手册](../docs/部署与运维.md)。

### 2026-10-09 · 审计筛选布局复核

审计日期筛选使用固定标签列与可收缩输入列，避免桌面宽度下“开始/结束”标签竖排。`npm run build`（Vue 类型检查 + Vite）通过；当前管理员浏览器复核了桌面审计列表，窄屏需另行验收。

### 2026-10-09 · 窄屏管理表格复核

角色、应用、用户组和应用角色宽表格在 650px 以下将固定操作列还原为表格内部横向滚动；503×871 视口已复核角色、应用、用户组表头，首屏关键字段可见，整页无横向溢出。操作列需滚动表格访问。同步修正 Vue SFC 中静态数值 `maxlength` 的类型绑定。`npm run build` 的 `vue-tsc -b` 与 Vite 均通过（3205 modules，入口 382.70 KB / gzip 118.73 KB）。本轮未覆盖 390px/768px/1024px、租户管理员专属页、公开认证页或已有应用主题编辑/发布，详见 [UI 走查记录](../docs/验收记录.md)。

### 2026-10-09 · DeerFlow OIDC 集成状态同步

本轮 Vue 源码未变化。关联的 DeerFlow OIDC UserInfo 已要求 subject 与签名 ID Token 一致，回归 20/20 通过；该修复不实现 Gateway token/tenant vault 或中央权限映射，详情见[接入计划](../docs/技术架构与接入.md)。
