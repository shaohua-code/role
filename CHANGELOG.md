# 变更日志

## 2026-10-29 应用工作台收口应用角色与应用权限

侧栏下线「应用角色与成员」；旧深链 `/application-roles` 重定向到应用工作台。角色行改为「应用权限」「配置成员」：应用权限抽屉收资源权限（挂码 + 资源树）与数据权限；去掉顶栏邮箱分配条。成员列表支持 `role_id` 过滤。资源树读写固定走 `/admin`。

- **验证：** 容器 unittest / `npm run build` / 浏览器走查见总览（本轮记录）。

## 2026-10-29 预置平台角色四级可改本级授权

系统预置平台角色改为四个管理员都可配权：超管改全部，租户管理员改租户及以下，多应用管理员改多应用及以下，应用管理员改应用与成员。只能勾自己已有的码，不能配上级权限。

- **验证：** 容器 unittest 44/44 OK；宿主机 `npm run build` exit 0。未运行浏览器登录走查。

## 2026-10-29 角色管理改名平台角色，四级按可见集配权

高级管理「角色管理」改称「平台角色」。平台超管可配全部管理码；租户管理员、多应用管理员、应用管理员可新建自定义平台角色并只配自己看得见的码。「应用角色与成员」拆成独立菜单，租户台也能进平台角色页。

- **验证：** 容器 unittest 43/43 OK；宿主机 `npm run build` exit 0。未运行浏览器登录走查。

## 2026-10-29 租户台应用角色可配租户/应用管理码

权限平台 `/roles` 给应用角色配权时，不再只出业务码。租户管理员能勾选自己看得见的租户管理码，应用管理员能勾选应用管理码；本应用业务码仍可挂。看不见的码（例如 L2 勾 `org.read`）422。

- **接口：** `GET /tenant-admin/applications/{id}/permissions?include_management=true`；默认不加该参数仍只出业务码。
- **守卫：** `assert_application_grant_permissions` 按 `actor_grantable_management_codes` 放行。
- **前端：** 租户台弹窗分组展示；工作台挂码弹窗同步打开管理码。
- **验证：** 容器 unittest 上述三文件 **40/40 OK**，P404/应用管理员回归 **12/12 OK**；宿主机 `npm run build` exit 0。未运行浏览器登录走查。

## 2026-10-29 IAM P405 — 平台 / 应用权限分层落地

按《产品口径-平台与应用权限分层》把平台角色与应用角色拆开。无迁移、无 DeerFlow、不上线包。

- **五级平台模板：** 新增 `apps.admin`（钉应用，码集 = `app.admin` + `rbac.app_role.assign`）。应用开通预置三个平台角色；`app.member` 不再挂业务码，走查业务码改挂 `demo.reader`。
- **任命链：** L3 可任命多应用/应用管理员；多应用管理员可再任命其已有应用的应用管理员；应用管理员不能任命管理员。绑应用角色自动补 `app.member`。
- **两套目录：** `GET /admin/permissions` 默认只出 `surface=management`；工作台角色列表排除五模板；高级角色页 `role_class=platform`。去掉 P383 自定义角色授权权禁选。
- **前端：** 权限编码页不再混出业务码；角色页只建自定义平台角色；工作台按邮箱分配应用角色并写明会同时成为平台成员。
- **验证：** 容器 unittest `test_p405_layering` + `test_p404_visibility` + `test_role_hierarchy_guards` + `test_application_admin_access` **38/38 OK**；宿主机 `npm run build`（vue-tsc -b + Vite）exit 0。未运行：浏览器登录走查。

## 2026-10-29 目标口径草稿 — 平台权限 / 应用权限分层（只出文档）

把口述需求整理成 [docs/产品口径-平台与应用权限分层.md](docs/产品口径-平台与应用权限分层.md)。不改代码、不改 PRD 现网口径。

- **目标：** 平台权限与应用权限物理分开；**两类角色**：平台角色（五级：超管 / 租户管理员 / 多应用管理员 / 应用管理员 / 应用成员，只挂平台权限）与应用角色（只挂应用内业务码 / 菜单 / 按钮）。
- **已确认：** 租户管理员可建删本租户应用；可任命多应用管理员，也可直接任命应用管理员；多应用管理员可再任命应用管理员；同一人可跨租户兼任，范围不串；五级身份都是平台角色，不要把它们当成应用角色；超管 / 租户管理员 / 多应用管理员 / 应用管理员都可新建角色、权限自由搭配，但只能看见并配置自己已有范围内的权限；应用成员不能新建角色。
- **现网：** 仍以 P404 四级与配权说明书为准。本文不是现网承诺。
- **验证：** 未运行（无代码改动）。

## 2026-10-29 IAM P404 — 四级角色可见范围收口

按 L1 > L3 > L2 > 应用自定义角色 > L4 收口可见范围：下级看不到上级编码、看不到越权对象。无迁移、无 DeerFlow、不上线包。

- **创建/删除应用仅 L1/L3：** `POST/DELETE /applications` 改 `ensure_roles(tenant.admin)`；`has_application_admin_access(..., application_id=None)` 对 L2 为假。前端拆 `can_create_applications`（租户域码），L2 不再看到「新建应用」。
- **权限目录按操作者过滤：** `GET /admin/permissions` = 可授管理码 ∩ 可见业务命名空间。挂码弹窗消费已过滤目录，再按目标角色 kind 隐藏越域组。
- **L2 列表隔离：** 角色列表只出钉住应用的 application 角色；持有者/授权深链越权 404。用量钉住应用；审计无 application_id 列，尽力量化 `target_type=application` 且 target 钉住。L3 用量与业务码限本租户。
- **验证：** 容器 unittest `test_application_admin_access` + `test_p404_visibility` + `test_role_hierarchy_guards` + `test_g16_g24` **37/37 OK**；宿主机 `npm run build`（vue-tsc -b + Vite）exit 0。未运行：浏览器登录走查。

## 2026-10-29 IAM P403 — G27 入口消歧 / G28 有效权限 / G29 真分页 / G32 L3 模板 / G30 造数

继续执行 P402 盘点未落地项。不上线包（G03 MFA / G04 注销 / 配额 / G05 A04）。无迁移、无 DeerFlow。

- **G27：** 侧栏 L1 入口改「运营总览」；租户 `/roles` 标「应用角色与成员」，页头指向日常「应用工作台」。
- **G28：** 用户详情 `effective_permissions`：有效权限码并集 + 直授/用户组来源。
- **G29：** `GET /admin/roles`、`GET /admin/permissions` 返回 `{items,total,limit,offset}`；角色列表服务端真分页；权限目录带 total。SDK 兼容包装对象。
- **G32：** L3 模板 21→20，剥 `rbac.permission.manage`；预置时剥离存量。平台目录写仍仅 L1。
- **G30：** `docker compose exec api python -B manage.py seed-walkthrough` 已造 demo-app 与 `l2-admin`/`l3-admin`/`l4-member@demo.example.com`（密码 `Walkthrough#2026`）。
- **验证：** 容器 unittest `test_role_hierarchy_guards` + `test_g16_g24` + `test_application_admin_access` **28/28 OK**；Python SDK `test_iam_permission_sync` **17/17 OK**；TS SDK permission-sync **16/16 pass**；宿主机 `npm run build`（vue-tsc -b + Vite）exit 0。未运行：浏览器登录走查。

## 2026-10-29 IAM P402 — 产品层缺点盘点 + 日常配权硬伤

对照 PRD、配权说明书与现网代码做产品层盘点；G25–G32 入进度第 4 节。PRD §4.1 信息架构、G01①「审计人员」、§2.1 DeerFlow 试点口径标待裁决。第一刀只修日常配权断流，不重做五域码表、无迁移。

- **产品裁决：** L3 `tenant.admin` 可建/改本租户全部应用（对齐 P383「租户管理员管当前租户下一切」）。
- **后端：** `has_application_admin_access` 认 `tenant.admin` ∪ 钉住应用的 `app.admin`；`list_readable_application_capabilities` 对 L3 短接租户内全可管，与写路径对齐。
- **前端：** 工作台「权限编码」新建按 `application.can_manage` 开放给 L2/L3（启停仍仅 L1）；空态三步写明应用管理员可登记业务码，无创建权时改为联系租户管理员；L4 `/no-access` 与应用角色页去掉过时 `iam.*`。
- **验证：** 容器 `python -B -m unittest tests.test_application_admin_access` **3/3 OK**；宿主机 `npm run build`（vue-tsc -b + Vite）exit 0。未运行：浏览器登录走查（自动化填登录凭据被拦截）；无 L2/L3 走查账号（未跑 `seed-walkthrough`）。

## 2026-10-29 IAM P401 — 角色管理与权限编码交互梳理

对照配权说明书与现网代码，补齐「高级管理 → 角色/权限编码」与「应用工作台角色/权限 Tab」的日常主路径断层；不改五域码表、不重做两类分组与授权弹窗、无迁移。

- **角色列表服务端筛选：** `GET /admin/roles` 增 `application_id`，`q` 覆盖名称/标识/说明；高级角色页把 `q/kind/tenant_id/status` 接到 API（回车搜索）；工作台 RolesTab 平台模式改 `kind=application&application_id=`，不再拉全站 500 条再本地滤。
- **角色行交互：** 修 `kind-application` 虚线边 CSS；权限列「N 项」可点开挂码；只读操作改为「查看权限」；工作台操作列收成「配置权限 + 更多」；高级「资源授权」改名为「实例资源授权」并与工作台资源树消歧；数据范围中文描述主行 + mono 码；新建角色成功后询问立刻挂码。
- **权限编码降噪：** 目录页去掉与 subtitle/hint 重复的页顶 alert，五域 chips + 命名空间收进「更多筛选」；「平台直接登记」加 tooltip 引导业务码去工作台。工作台 Panel 改 `AdminTableToolbar`、描述主显、登记框 `addon-before` 锁定 namespace。
- **后端越域 422：** `permission_namespace.assert_role_kind_grant_permissions` 与授权弹窗矩阵同口径（历史已持有豁免）；`PUT/preview .../roles/{id}/permissions` 拒绝新增越域码。
- **验证：** 容器内 `python -B -m unittest tests.test_permission_namespace tests.test_role_hierarchy_guards` **19/19 OK**；`npm run build`（vue-tsc -b + Vite）exit 0。未运行：浏览器走查（工作台选应用 → 登记码 → 建角色 → 挂码 → 高级列表筛选/点「N 项」；待用户登录复看）。

## 2026-10-29 IAM P400 — /model-usage 模型用量页重设计（新增聚合图表区）

用户要求用 frontend-design / trae-design / build-web-data-visualization 插件能力重新设计模型用量页。经 dataviz 路由裁决：页面缺「时间变化」与「模型排名」两个分析层；后端只有总量 summary 无按日/按模型聚合，为保图表真实（不从前端分页数据造假聚合），同批补两个同口径只读聚合端点。

- **后端（`admin/model_usage.py`，零迁移零写路径）：** 新增 `GET /admin/model-usage/timeline`（按 UTC 自然日聚合请求数/输入/输出 Token/失败数，`created_at AT TIME ZONE 'UTC'` 分桶与既有筛选边界同口径）与 `GET /admin/model-usage/by-model`（按模型聚合 Token/请求/估算费用，总 Token 降序 limit≤20）；两者复用 `_usage_event_filters` 同套筛选与 L2/L3 `ensure_roles` 守卫，与 summary 口径完全一致。
- **前端新组件 `views/models/components/ModelUsageCharts.vue`：** 复用概览图表基建（echarts 按需注册、CSS token 取色、data-theme MutationObserver 即时重绘、动效压至 200ms）。02 用量趋势：每日输入/输出 Token 堆叠柱（墨色/中灰双墨阶 + 卡头 HTML 色例随主题自动翻转），中间无调用日期补零避免柱距相等造成「时间均匀」错觉，tooltip 直读请求/输入/输出/失败；03 模型分布：Top 8 横向柱降序（第一名恒在最上）+ 条尾直标紧凑 Token（k/M/B 缩写）+ tooltip 含输入/输出/费用（未知费用如实标注不伪装为零）。三态齐全：加载/失败（琥珀提示）/空态（AdminEmpty）。
- **页面集成（`ModelGovernancePage.vue`）：** 编号重排为 01 用量汇总 → 02 用量趋势 → 03 模型分布 → 04 待核对调用 → 05 调用账目（目录视图仍为 01 模型目录）；图表与汇总共用同一筛选参数（租户/结果/模型/UTC 日期口径一致）；选中具体模型时分布卡整体隐藏且不发请求（单柱无意义）；聚合请求失败保留旧图（stale-but-visible）+ 失败态提示；筛选/切租户即清空旧聚合，请求序号防竞态沿用既有机制。
- **顺手修存量构建阻塞（与本次无关的既有断裂）：** App.vue 模板引用 `userInitial` 但 script 从未定义，`vue-tsc -b` 直接报错无法出包——补 computed（展示名/邮箱首字符大写，空则隐藏头像）。
- **验证：** `npm run build`（vue-tsc -b + Vite）exit 0；eslint `src/views/models` exit 0；后端 `py_compile` exit 0（Python 3.14）。未运行：后端接口实测与浏览器走查（本机无运行中的 PostgreSQL/FastAPI；深浅主题与窄屏待用户复看）。
- **视觉修订（同日用户截图反馈「好丑」）：** ①冷启动收敛——无任何聚合数据时不再渲染「02/03 两张大白空框 + 标题行四段文字挤成一条线」的骨架，整段降为单条空档带（图标 chip + 「暂无模型调用记录」+ 一句去向说明；加载/失败同构），有数据才展开双图布局；②图例改药丸 chips（bg-subtle 圆角底）并砍掉「每日 Token · UTC」散文本，右栏说明缩短为「Top 8 · 总 Token 降序」加 nowrap，消除居中漂浮文本与右缘裁切；③watch 加 `flush: 'post'`，修复「空态 → 有数据」切换时宿主节点刚挂载、echarts 首渲染落空的时序缺陷；④04 待核对区「灰字说明 + 大黄条」两行堆叠合为一条轻警示。修订后 lint + `npm run build` 复跑 exit 0。

## 2026-10-29

- 文档：确认**应用资源树为正式方案**；废除「资源≈权限编码 / 不建 Resource」口径。 新增 `docs/配权说明书.md`；更新 `glm-align-user-centent-prompt.md`、`plan-frontend-codes-backend-roles.md`、`项目总览与进度.md`、对接手册 §11 脚注。 仅文档，无业务代码变更；git 仓库仍按用户决定暂不新建。

## 2026-10-28 IAM P398 — 全站工具条筛选条统一重设计

用户截图反馈 applications 页工具条「搜索/筛选换行参差、下拉过宽与搜索框等宽、操作按钮孤在右侧」，要求重设计所有页面的搜索区。uicraft 流程定位根因：`style.css` 全局规则把工具条内**所有控件**（搜索框与下拉）一刀切 `width: min(100%, 320px)`，且该规则未分层、优先级高于 Tailwind 工具类，页面上的 `min-w-*` 宽度类全部失效；下拉与搜索框等宽导致换行后参差无节奏。

- **三级宽度体系（`style.css` 唯一权威源）：** 搜索框 `min(100%, 320px)` 主锚点；普通筛选下拉固定 `160px`；长枚举下拉（租户/命名空间等带搜索）新增 `admin-filter-wide` 标注类 `208px`。固定宽度使换行后第二行与首行左对齐成整齐节奏。
- **`AdminTableToolbar` 结构升级：** 左区筛选控件统一 `gap-2`（8px 节奏）；右区（hint 图标 + 操作按钮）改 `lg:ml-auto` 右对齐并加细分隔线（`lg:border-l` + `pl-4`），移除原 `flex-1 + max-w-[520px]` 造成的挤压换行；hint-only 场景保持 `justify-between`。
- **页面清理：** applications/tenants 删失效 `min-w-*` 类，租户筛选标 `admin-filter-wide`；roles 删死样式 `.role-search`/`.role-tenant-filter`，租户筛选标宽档；permissions 命名空间下拉改 `admin-filter-wide` 并删 scoped 死宽度；groups/organizations 删无模板引用的死样式 `.table-toolbar`/`.tenant-filter` 并给租户下拉标宽档；models/groups/organizations/TenantAccess 的 scoped `.tenant-filter` 宽度（250/280px）删除、统一走全局 208px（保留窄屏 100% 与不收缩）；顺带修 models 页 `.tenant-filter-label` 死变量 `var(--subtle)` → `var(--color-text-muted)`。
- **token 修正：** 工具条控件阴影 `rgb(15 23 42 / 0.04)`（slate 残留）→ `var(--shadow-sm)`；深色主题边框 slate rgba → zinc rgba（212,212,216）。
- **验证：** vue-tsc + Vite 生产构建 exit 0（10.65s）。未运行：浏览器走查（筛选条换行对齐/宽窄档/深色主题/窄屏待用户复看；截图中聚焦 select 的绿色描边为用户本机自定义主色，非缺陷）。

## 2026-10-28 IAM P397 — 管理台五页重设计（统计带 + 精简表格 + 行点击详情抽屉）

用户反馈 /applications /roles /permissions /application-workspace /tenants 五页「使用起来不方便」，要求重新规划表设计、页面交互与审美。经 Plan 模式方案评审后实施（前后端均允许修改）。

- **统一信息架构：** 列表页统一「统计带（可选）→ 工具条（搜索+筛选+主操作）→ 精简表格 → 行点击下钻详情抽屉」；详情/浏览类改抽屉、编辑/创建类留弹窗、危险操作确认文案不变。
- **新通用组件（`src/components/`，index.ts 导出）：** `AdminStatBand`（账本式统计卡带，点击筛选/再点还原，disabled 概念位）、`AdminDetailDrawer`（详情抽屉骨架，default/footer/header-extra 插槽）、`AdminMonoValue`（mono 值 + hover 一键复制）；`CopyOutlined` 入 icons 统一出口。
- **/tenants（提升最大）：** 补搜索（名称/标识）+ 类型/状态筛选；6 列收敛（租户名+slug mono 副行、成员数点击开成员抽屉）；行点击开详情抽屉（基本信息/旗下应用列表点击携 `application_id` 深链跳工作台预选/成员抽屉复用 `GET /admin/members`）；平台引导租户禁删禁切换特判全保留。
- **/roles：** 顶部作用域四卡统计带（全部/平台/租户/应用，替代类型下拉）；8→7 列（租户+应用范围合并「归属」副行，角色标识 AdminMonoValue）；权限数量徽标可点击 → 持码清单抽屉（按权限域分组，footer 直达授权弹窗），替代原 tooltip 全码平铺；行点击同样下钻。
- **/permissions：** 统计卡带组件化（numbered 账本样式保留）；权限域下拉改多选 chips（色点+域名+计数，命中任一选中域即保留）；「关联角色数」可点击 → 引用角色抽屉（前端 `roles.permission_codes` 反查，零后端改动）；登记弹窗新增「所属权限域」选择（自动补 `域.` 前缀 + 完整编码实时预览 + 管理面前缀校验）；业务码行附「需数据范围」标记；接口类型补 `surface`/`requires_data_scope`。
- **/applications（11→7 列）：** 回调两列合并「登录 n · 登出 m」徽标；授权模式/自助注册/说明收进详情抽屉（协议信息+回调清单+操作集中，操作后同步最新记录）；状态+受信合并单元格；工具条补搜索（名称/ClientID/说明）+ 租户/状态/受信筛选；租户模式合并数据后前端过滤兼容不变。
- **/application-workspace：** AppTree 租户组节点加应用计数徽标（搜索过滤联动）；选中应用卡片加概览统计条（角色/权限码/资源三项计数，三 Tab 经 `stats` 事件上报，切换应用清零重报）；支持 `?application_id=` 深链预选（租户详情抽屉跳转入口）。
- **后端（轻量增强，同批落地）：** `GET /admin/tenants` 补 `q/kind/status` 过滤 + `application_count` 一次聚合（group by tenant_id）；`GET /admin/roles` 补 `q/kind/tenant_id/status`，tenant_id 与 actor 租户范围求交（越范围 403），permission_codes N+1 修复（当前结果集一次 join 聚合）；`GET /admin/applications` 补 `q/status/trusted`（capability 过滤后、limit 前套用；非平台管理员必带 tenant_id 校验不动）。前端本地即时过滤为主路径，服务端参数供深链与未来分页。
- **验证：** vue-tsc + Vite 生产构建 exit 0（8.97s）；后端 3 文件 `py_compile` 通过（Python 3.14，宿主机 PATH 无 python 需显式路径）。未运行：浏览器走查（本机无 PostgreSQL/后端运行环境与登录凭据）——统计带筛选、行点击抽屉、复制提示、深链预选、暗色主题、375 窄屏、tenant 模式回归待用户复看。

## 2026-10-28 IAM P396 — 层级起点标记感知增强（白话文案 + 三档视觉 + hover 解释）

用户反馈目录页的层级标记「不够清晰，让用户感知更强」——`L1 专属`/`L3 起`/`L2 起` 小灰 tag 是 RBAC 行话，非背景用户读不懂且视觉太弱。

- **白话文案（`SCOPE_LEVEL_LABELS`）：** `L1 专属`→**仅平台超管**、`L3 起`→**租户管理员起**、`L2 起`→**应用管理员起**；新增 `SCOPE_LEVEL_TIPS` hover 解释（如「仅平台超级管理员（L1）持有；租户、应用管理员不可见」）。
- **三档视觉强度（目录页 + 授权弹窗同步）：** 实底黑（仅平台超管，最强）→ 深描边（租户管理员起）→ 浅描边（应用管理员起），黑白灰体系内以视觉重量呼应层级递减；tag 加 `cursor: help` 与 a-tooltip（P373 降噪模式）。
- **弹窗行同步：** 授权弹窗行式列表（P394）在描述后追加同口径层级标记，目录页与弹窗视觉语言一致。
- **验证：** vue-tsc + Vite 生产构建 exit 0。未运行：浏览器走查（标记文案/三档样式/tooltip 待用户复看）。
- **减重修订（同日用户反馈实底黑块「丑」）：** 首版实底黑 tag 每行重复、满屏黑块视觉噪音过大；改回**描边式轻标签**——去实底、字号 10px/圆角 2px/细边框，三档靠文字深浅区分（黑字黑框 → 中灰字灰框 → 浅灰字浅框），tooltip 与白话文案不变；目录页与弹窗同步。

## 2026-10-28 IAM P395 — 权限编码两类分组（平台编码 + 应用业务编码）

用户评审 P393 作用域四卡与层级三卡草案后两级收敛：「权限编码要有层级关系——平台编码负责平台的所有，应用负责应用相关所有」→「是不是只要分两种——平台编码，和一种租户下的应用业务编码」。prd-authoring 产出 PRD（`docs/prototypes/permission-hierarchy-view/PRD.html`）并批准实施。本质洞察：「平台 ⊃ 租户 ⊃ 应用」的层级关系由模板码集天然承载（L1 持 27 ⊃ L3 持 21 ⊃ L2 持 15），不需要靠分组表达；分组只分两类。

- **两类分组（单一来源 `permissionGroups.ts`）：** 新增 `PERMISSION_CLASSES`（平台编码 / 应用业务编码）与 `resolvePermissionClass()`（`isManagementCode` 判定）；`SCOPE_LEVEL_LABELS`（L1 专属 / L3 起 / L2 起）与 `SCOPE_LEVEL_ORDER` 供行标记与排序；P393 作用域归属（`resolvePermissionScope`）保留为层级起点依据。
- **目录页（`PermissionCatalog.vue`）：** 统计卡带 5 张作用域卡 → 3 张两类卡（00 全部 27+N / 01 平台编码 27 / 02 应用业务编码 N，业务码 0 置灰概念位）；`scopeFilter` 改按类过滤；权限编码列描述后附层级起点轻量 tag（仅管理码）；排序保持「L1 专属 → L3 起 → L2 起 → 业务码」聚块；命名空间下拉、功能域下拉、列结构均不变。
- **授权弹窗（`RolePermissionGrantModal.vue`）：** 左栏导航从作用域四组改两类（全部 / 平台编码 / 业务码）；分区渲染两类化——平台编码组内按层级起点序（L1 专属 → L3 起 → L2 起 + 编码字母序），业务码组保留命名空间二级分组；收敛矩阵数值零变化（tenant 隐 L1 专属+业务码、application 隐 L1 专属+L3 起，各角色可见码集逐码一致），仅注释口径更新；P394 行式列表、越域豁免、授权权禁选、保存链路全部不变。
- **验证：** vue-tsc + Vite 生产构建 exit 0（修复 `SCOPE_LEVEL_ORDER` 对象误用 `.get()` 的类型错误后复跑）。未运行：浏览器走查（两类卡带/行标记/弹窗两组导航待用户复看）。
- **补充（同日用户反馈「平台编码要和业务编码区分」）：** 目录页表格在两类交界处插入**横贯式分组标题行**（「平台编码 · N 个编码」/「应用业务编码 · N 个编码」，浅底通栏），业务码段为空时不显示空组头；经 AdminListPage `$attrs` 透传 `rowClassName` 实现组头行底色，数据行不受影响。

## 2026-10-28 IAM P394 — 授权弹窗布局断裂修复 + 码项行式重设计

用户截图反馈授权弹窗「丑，重新设计」：截图实锤弹窗布局整体断裂——已选摘要条 chips 顶出弹窗边界、底部操作条悬空错位、码卡片全部挤压截断。经 uicraft 流程审计定位根因。

- **P389 遗留 grid bug 修复（布局断裂根因）：** 右栏容器误复用外层 `.grant-layout` class（188px+1fr 两列 grid），导致 hint/摘要条/选项/操作条被当作 grid items 错误拆列——改为语义正确的 `.grant-main`（flex column），摘要条、操作条、滚动容器全部归位。
- **码项行式重设计：** 双列卡片在 ~600px 右栏下单卡仅 ~290px，中文描述与 mono 码全部截断；改为**单列全宽行式列表**——勾选框 + 描述主行左对齐 + mono 码右对齐同行，hover 浅底、选中行左墨色竖条+浅底、禁选弱化；信息完整不截断，27 码纵向密度更高（黑白灰编辑风）。
- **绿色勾选框说明：** 非代码缺陷——来自用户本机「外观设置」存的自定义主色（localStorage `iam-primary-color`），checkbox 选中色跟随全局 colorPrimary；调回石墨黑即可恢复黑白灰。
- **验证：** vue-tsc + Vite 生产构建 exit 0。未运行：浏览器走查（弹窗布局/行式列表/摘要条归位待用户复看）。

## 2026-10-28 IAM P393 — 权限编码作用域一级分组（平台 → 租户 → 应用）

用户复看 P392 后的权限编码目录页，反馈「权限编码还是混在一起，区分平台、租户、应用的，这个是一级」——功能五域是技术视角，与「这条码归哪一级用」的管理心智不一致。经 prd-authoring 产出 PRD（`docs/prototypes/permission-scope-grouping/PRD.html`），AskUserQuestion 三裁决：分组层级「一级平台 / 二级租户 / 三级业务码」、范围=目录页+授权弹窗同步、功能五域降为筛选维度。

- **归属规则（确定性推导，零逐码人肉裁定）：** 由 P383 模板码集派生——仅 L1 持有 → 平台组 6 码（platform 5 + `rbac.role.manage`）；L3 持有且 L2 不持有 → 租户组 6 码（`org.read/manage`、`rbac.role.read`、`rbac.permission.manage`、`rbac.app_role.assign`、`ops.model.manage`）；L2 持有（L3 全量兼容）→ 应用组 15 码；业务命名空间 → 业务码组。6+6+15=27 验算零遗漏零重复。
- **单一来源（`utils/permissionGroups.ts`）：** 新增 `PERMISSION_SCOPES`（四组定义）与 `resolvePermissionScope()`（静态归属表 + `isManagementCode` 兜底业务码），目录页与授权弹窗共用；功能域 `PERMISSION_DOMAINS`/`resolvePermissionDomain` 保留供筛选下拉与编码行域名展示。
- **目录页（`PermissionCatalog.vue`）：** 统计卡带从五域改为 5 张作用域卡（00 全部 / 01 平台 6 / 02 租户 6 / 03 应用 15 / 04 业务码 N）——业务码数量为 0 时保持概念位但置灰不可点；新增 `scopeFilter` 与权限域下拉/命名空间/搜索叠加过滤；列表默认排序按作用域组序+编码字母序（同类码天然聚块）；命名空间下拉空态文案「全部分组」→「全部命名空间」（消除概念冲突）；列结构零改动。
- **授权弹窗（`RolePermissionGrantModal.vue`）：** 域导航与分区渲染一级改为作用域四组（业务码组内保留命名空间二级分组）；收敛矩阵等价改写为作用域口径——tenant 隐藏【平台+业务码】组、application 隐藏【平台+租户】组+业务码限本命名空间，旧 `APPLICATION_HIDDEN_CODES` 治理码黑名单（`rbac.role.read/manage`、`rbac.permission.manage`）分属租户/平台组被组级隐藏覆盖，删除码级黑名单；历史已持有越域码豁免隐藏（P390 哲学）与授权权码禁选（P383）不变；保存链路（勾选→预览→PUT）报文与判权零改动。
- **验证：** vue-tsc + Vite 生产构建 exit 0。未运行：浏览器走查（卡带筛选/弹窗三角色收敛/深浅主题待用户复看）。

## 2026-10-28 IAM P392 — 权限编码绿场重命名 + DeerFlow 资产清零下线

用户反馈「角色和权限编码这块很乱」，要求编码与角色全部重写、旧数据不要、UI 重新设计。经 prd-authoring 产出 PRD（`docs/prototypes/permission-rebrand/PRD.html`），AskUserQuestion 三裁决：**绿场一键重置** / **DeerFlow 资产一并清零**（执行中用户追加「deerflow 相关对接也全部删除，后面我会重新对接」）/ **三段式五域重命名**。

- **全链路改码（27 码 + 2 角色 key）：** node 批量脚本（修复 walk 把文件当目录的 ENOTDIR 后分两轮补齐）将 `iam.*` 码映射为五域码——`platform.overview.read`、`platform.tenant.*`、`platform.account.*`（原 iam.user）、`rbac.role.*`、`rbac.permission.*`、`rbac.app_role.*`、`org.*`（原 iam.organization/member/group/invitation.manage→`org.invite.manage`）、`app.*`（原 iam.application，含 secret.rotate）、`ops.model.*`、`ops.theme.manage`、`ops.audit.read`、`ops.authz.simulate`；角色 key `platform.super_admin`→`platform.admin`、`tenant.org_admin`→`tenant.admin`（`app.admin`/`app.member` 不变）。覆盖 backend/app+tests+manage.py+前端 18 文件；L1=27/L3=21/L2=15/L4=0 模板码集语义逐一验算零变化。
- **配套改造：** `permission_namespace.py` 新增 `MANAGEMENT_DOMAIN_PREFIXES`——五域前缀码的目录命名空间统一归 `platform`（修复 `derive_catalog_namespace` 在 `app.read` 等新码下语义翻转）；`permissionGroups.ts` 重写为五域版（七组：五域+business+other）；`RolePermissionGrantModal` 收敛域矩阵与授权权码常量更新（`rbac.app_role.manage`/`org.member.manage`/`org.invite.manage`/`org.group.manage`）；`public_registration.eligible_registration_role` 改按管理面码前缀禁止注册默认角色（补 import）。
- **测试修复 3 项：** test_user_lifecycle 补 `deliver_for_user` mock（G19 back-channel 在裸 Mock db 上遍历报 not iterable）；test_session_management 全局审计计数断言改调用前后对比（非隔离库含 340 条历史审计，环境敏感）；test_permission_namespace 断言更新为五域归 `platform`。
- **DeerFlow 清零：** 绿场重置后应用/角色/授权/`deerflow.*` 业务码目录全部消失；`OverviewPage.vue` 试点 pill 改「试点应用待接入」、角色页/租户接入页/`model_usage.py` 文案中性化、`permissionGroups.ts` 注释示例改 demoapp；技术架构文档删除第 5 章「DeerFlow 试点接入」并加 P392 状态标注（第 6/7 章保留历史背景注）；产品需求/对接手册/快速启动指南/根目录 11-menu 文档同步（码表新口径 + 试点下线状态 + 历史注）。`verify_role_isolation.py` 跨应用目标动态化：优先复用既有非 crud-demo 应用，否则临时创建 isolation-target 探测应用并在 finally 删除。
- **绿场重置实测：** 重置前 `pg_dump` 受保护备份 `backups/pre-p392-rebrand-20261028-163335.sql`（236KB，含旧码数据）→ `compose down -v` → greenfield-reset.ps1 因 UTF-8 BOM 在 PS5.1 解析失败（param 块失效），按脚本逻辑手动四步复刻：migrate（0001→0004 全链应用）→ seed（输出「权限目录：新增 27 条管理面码」+ admin 绑 L1 `platform.admin` + demo 租户）→ api/console 启动 healthy。
- **端到端验证：** admin 登录 `/auth/me/capabilities` 实测 `platform_codes` **恰 27**（platform 5 / rbac 7 / org 7 / app 3 / ops 5）、roles=`platform.admin`、`iam.*` 残留 0。4 测试模块 27 项全绿（9 skip 为需 Docker 的 PG 集成）；全量 discover 258 项仅剩 4E 存量（test_admin_authorization 陈旧 mock，P367 已记录）；前端 `npm run build` exit 0；源码+测试旧码 grep 零残留（剩余命中仅受保护备份/归档迁移/历史文档）。
- **未运行：** 浏览器新码 UI 走查（菜单/弹窗/域分组渲染待用户复看）；verify_role_isolation.py（重置后无 crud-demo 应用与联调用户，需重新造数）；P1 后端保存校验加固（越域授权 422）维持独立跟进。

## 2026-10-28 IAM P391 — 授权弹窗提示降噪（用户截图反馈「提示太重」）

用户复看 P389/P390 截图反馈「页面太丑了，提示太重」：弹窗顶部两个大 a-alert（蓝「先预览」+ 黄「自定义角色不可持授权权」）占近 1/3 高度，违反 P373 全站提示降噪标准。对齐降噪哲学快修（纯展示层）。

- **双 alert → 单行轻提示**：合并为一行 `.grant-hint`（ExclamationCircleOutlined + 12.5px muted 小字「先预览授权变更再提交保存；仅编辑通用权限，资源实例级授权不受影响」）；`lockAuthorityCodes` 时追加琥珀色（`--color-warning` token）「自定义角色不可持有授权权码」轻标注，大段细节收进 a-tooltip 悬停展开。
- **摘要条减重**：去灰底（`background: var(--color-border)` → transparent）+ 边框减淡（border-strong → border），消除与码卡片的灰块堆叠感。
- **验证：** vue-tsc + Vite 构建 exit 0（10.08s）。未运行：浏览器走查（待用户复看降噪效果）。

## 2026-10-28 IAM P390 — 角色创建作用域向导 + 授权弹窗严格三级收敛（PRD 批准后实施）

用户评审通过《角色创建作用域向导与授权收敛 PRD》（`docs/prototypes/role-creation-scope/PRD.html`，裁决原 permission-grouping PRD 的 Q1/Q2：平台角色不开放新建 + 严格三级矩阵收敛）后实施。PRD 两项裁决：①平台角色置灰「由系统种子定义，不可新建」（与绿场四级写死/P381·P382 防呆哲学一致）；②收敛口径从 P383 模板码集推导。

- **FR-01 新建角色作用域向导（`RoleManagement.vue`）：** 新建弹窗顶部三张作用域卡——平台（disabled「由系统种子定义，不可新建」）/ 租户（→选租户）/ 应用（→选租户 + **所属应用必填**，切换作用域清空租户/应用）；未选作用域时字段区显示引导 alert；校验：未选作用域 422 前置拦截、应用角色无应用报错。提交字段与现状一致（零后端改动）；编辑弹窗不出现向导，新增「角色作用域」只读行（kindLabel）。
- **FR-02 授权弹窗严格收敛（`RolePermissionGrantModal.vue`）：** 新增 `roleKind` / `roleNamespace` props（空 = 不收敛，向后兼容）；收敛矩阵——tenant 隐藏【平台专属/业务码/其他】、application 隐藏【平台专属/租户治理/其他】且业务码仅显示本应用命名空间（编码首段匹配）、platform 全量；**历史已持有的越域码豁免隐藏**（可撤销但不可静默剥夺，与「停用码仅可撤销」同哲学）。隐藏组整体不渲染（域导航/组头/摘要 chips 同步消失）。
- **FR-03 调用方接线：** `RoleManagement.vue` 打开弹窗传 `role.kind` + 钉定应用 namespace（ApplicationOption 补 `permission_namespace`，App.vue 映射补字段——后端 `/admin/applications` 本就返回）；`RolesTab.vue` 恒传 `role-kind="application"` + `props.application.permission_namespace`（workspace 链路本就携带）。P386 的动态作用域 alert 由向导替代删除。
- **验证：** vue-tsc + Vite 生产构建 exit 0（7.97s）；修复实施中 RolesTab modal 开标签被误替换的损坏（重复标签+粘连，已还原正确结构）。未运行：浏览器走查（向导三卡/字段联动/弹窗收敛矩阵/深浅主题待用户复看）；后端保存校验加固（租户角色挂业务码 422）维持 P1 独立跟进。

## 2026-10-28 IAM P389 — 管理台权限页面重度重设计（双栏弹窗 + 域总览统计卡，零后端零契约改动）

用户反馈「页面太丑了、交互也不友好」，点名 frontend-design/trae-design 重度重设计管理台权限页面。AskUserQuestion 澄清确认：目标=授权弹窗+权限目录页、方向=黑白灰重度精修、交互四维全覆盖。方案经 Plan Mode 审批（`.trae/documents/redesign-admin-permission-pages.md`）后实施。零后端、零 props/emits 契约改动、保存链路（v-model → preview → PUT）零改动。

- **授权弹窗（`RolePermissionGrantModal.vue`）双栏重构：** 宽 680→880px；左栏 188px 域导航（全部+各域，显示「该域已选/总数」，active 左竖条+浅底，sticky 跟随；窄屏 <760px 降级横滑 tabs）；右栏新增**已选摘要条**（常驻：已选 N 项 + 最近勾选 6 个可点删 chips + 溢出 +M + 清空，勾选顺序经 watch diff 维护）——修复「67 码勾选后无处总览」最大交互缺口；码项**卡片化**（边框圆角卡、选中黑边浅底、禁选弱化）；组头加左竖条+计数徽标；预览区改**新增/撤销对比双卡**（语义色仅绿/红，token `--color-success/-error`）；底部操作条 **sticky 固定**。关闭弹窗重置全部展示状态。
- **权限目录页（`PermissionCatalog.vue`）：** 顶部新增**域总览统计卡带**（账本式编号 00–06 + 22px tabular 大数 + 活动数小字，7 列 grid → 1100px 4 列 → 700px 2 列），点击卡片即筛选（active 黑边+inset 竖条）；表格 **8→6 列**重构（权限编码双行=中文主行+mono 码副行；权限域/命名空间列=色点+域名全行归属；资源·Scope 合并 mono 列；砍独立说明列），去横向滚动；hint 补卡片筛选说明。
- **静态自查：** props/emits 契约未变（RoleManagement/RolesTab 两调用方零改动）；保存链路字段未变；新样式全部走 token（语义色 fallback 兜底但 `--color-success/-error` token 实际存在）；修复摘要 chip 裸文本节点导致 `:first-child` 误中删除符的选择器缺陷；删除被取代的 domainChips 死代码。
- **验证：** vue-tsc + Vite 生产构建 exit 0（8.33s，修正后复跑）。未运行：浏览器走查（双栏/导航切换/摘要点删/卡片选中态/统计卡筛选/深浅主题待用户复看）。

## 2026-10-28 IAM P388 — 权限编码按作用域分组（PRD P0 三项实施，纯前端展示层）

用户反馈「权限编码都在一个页面，平台/租户/应用的混在一起」（授权弹窗截图），经 prd-authoring 产出 PRD（`docs/prototypes/permission-grouping/PRD.html`）后按 P0 三项实施。分组纯展示层：选中集合、预览影响、保存报文、判权与可选性零改动。

- **FR-03 共享口径（新 `utils/permissionGroups.ts`）：** 六组码域映射单一常量（平台专属 / 租户治理 / 成员协作 / 应用域 / 模型主题审计 / 业务码 + 「其他」兜底），前缀精确匹配优先（`iam.role.manage`→平台、`iam.role.read`→协作、`iam.model.manage`→租户治理、`iam.model.read`→模型组等）；两界面共用一处，未来新前缀只改一处。
- **FR-01 授权弹窗（`RolePermissionGrantModal.vue`）：** 67 码按六组分区渲染，组头（名称+计数+语义 hint）可折叠；顶部域筛选 chips（仅显示存在的组，附数量）；业务码组内按命名空间（编码首段）二级分组；关闭弹窗重置筛选/折叠。保存链路（checkbox-group v-model → preview → PUT）零改动。
- **FR-02 权限目录页（`PermissionCatalog.vue`）：** 工具栏新增「权限域」下拉（与命名空间/搜索叠加）；命名空间列对 iam 码行加域标签（业务码行不打标避免重复）；列宽 100→130 / scroll.x 1050；空态文案纳入筛选条件。
- **验证：** vue-tsc + Vite 生产构建 exit 0（11.43s）。未运行：浏览器走查（分组渲染/chips/折叠交互待用户复看；深浅主题 chip 自适应待复验）。P1「按角色作用域收敛可选集」与 Q2（租户侧隐藏平台专属组）维持待裁决。

## 2026-10-28 IAM P387 — 角色作用域隔离实测脚本（7/7 通过，零残留可复跑）

用户要求「模拟应用角色访问其他应用路由，验证前后端拦截」。交付 `scripts/verify_role_isolation.py`（可复跑的验收脚本）并实测全绿。

- **脚本机制：** admin（容器 env 凭据）临时把 crud-demo@example.com 绑上 CRUD Demo 的 `app.admin`（真 L2 提权）→ 跑攻击矩阵 → try/finally 解绑恢复（零残留，重复执行幂等）；密码经 `docker exec -e DEMO_USER_PASSWORD` 注入，脚本零明文凭据。
- **实测 7/7：** ①capabilities 含本人应用不含 DeerFlow（前端守卫数据源）②跨应用读角色 404 ③跨应用建角色 404 ④跨应用读成员 404（三者防枚举：无权应用按不存在处理，强于 403）⑤`/admin/roles` L2 可读且零租户外角色（设计口径 `iam.role.read` + 非 L1 强制范围过滤）⑥本应用读角色 200（隔离不误伤）⑦换绑 `app.member` 后 `/admin/roles` → 403（零管理码角色确实被拒）。测后核对绑定完全还原。
- **口径修正过程：** 首版期望 L2 访问 `/admin/roles` 得 403 实测 200——实查 `list_roles` 门禁为 `[L3, L2]` + `list_actor_management_tenant_ids` 租户范围过滤，属设计放行（租户内角色目录可见），判定已修正；403 归属零管理码角色（L4 检查补上）。
- **验证：** 容器内两轮执行，第二轮 7/7 PASS；SQL 核对 crud-demo 用户仅剩原 `crud-demo` 角色。

## 2026-10-28 IAM P386 — 角色作用域可视化与文档固化（基于 role-scope-design 原型三项优化）

用户确认原型 `docs/prototypes/role-scope-design/` 结论（三级作用域有必要区分、现状已区分、建议轻量强化）后，按 07 区三张落地卡实施。零后端改动（`/admin/roles` 本就返回 `kind`）。

- **① 角色目录 kind 可视化（RoleManagement.vue）：** `RoleRecord` 补 `kind` 类型；角色名称列改为「名称 + 作用域小标签」竖排（`平台角色` 实边框加重 / `租户角色` 实边框 / `应用角色` 虚线边框——原生 span + token 变量，中性灰阶随深浅主题自适应，规避 a-tag cssinjs 注入顺序坑）；工具栏新增「全部类型」筛选器（platform/tenant/application）；名称列宽 140→168、scroll.x 1048→1076；空态文案纳入 kind 筛选条件。
- **② 创建入口作用域提示：** 新建角色弹窗顶部动态 alert（随「应用范围」选择切换「将创建应用角色：仅在该应用生效 / 将创建租户通用角色：全域生效」）；「应用范围」字段加常显 extra 说明。应用工作台 RolesTab 工具条 hint 追加「本页角色均为应用角色，仅当前应用生效」。
- **③ 文档边界固化：** PRD 新增 §3.1「三级角色作用域」（三级对照表 + 边界规则 + capabilities 对应关系）；对接手册 §8 后新增「三级角色作用域（对接必读）」（业务侧选层指南）。
- **验证：** vue-tsc -b + Vite 生产构建 exit 0（34.02s）。未运行：浏览器走查（纯展示层 + 筛选逻辑，待用户复看 tag 样式与筛选交互；深色主题变量自适应待复验）。

## 2026-10-28 IAM P385 — 测试数据清理（测试账号 4 + 演示租户 2 + 演示应用 1，单事务删除）

用户要求「把测试数据全部删除」。先只读盘点 8 用户/3 租户/3 应用实体，AskUserQuestion 确认边界为「测试账号+演示租户全套 + 审计按 actor 过滤删除」后执行。

- **删除清单（单事务，逐步输出行数，失败全回滚）：** 用户 4（l2-admin/l3-admin/l4-member `@demo.example.com` + e2e-register-51e18f61@example.com）、租户 2（demo/testdemo1）、应用 1（演示应用 demo-app，公开注册载体随之下线）；连带角色 4、邀请 1、审计事件 14（仅测试账号 actor，admin 操作记录 SET NULL 保留）。
- **删除顺序（按外键图定制）：** ①用量表 RESTRICT 断言（实查 0 行）→ ②审计按 actor 删 → ③邀请（→roles RESTRICT 先删）→ ④用户组/组织（自引用 RESTRICT 先删，实为 0 行均挂 platform）→ ⑤租户域角色 → ⑥demo-app → ⑦租户 → ⑧用户；其余全链 CASCADE（refresh_sessions/oauth_*/consents/成员/绑定/挂码/数据范围/主题/注册挑战）。
- **删后余量核对：** 用户 4（admin、shaohua_code@163.com、crud-demo、deerflow-demo 联调用户保留）、租户 1（platform）、应用 2（crud-demo + deerflow）、角色 8、审计 321、refresh 会话 111；孤儿数据范围/挂码 0/0。
- **验证：** health 200、`/auth/public-capabilities` 200 且 `console_registration: null`（注册入口随 demo-app 下线，符合预期）；DeerFlow/active 与 CRUD Demo 3 角色完好；platform 租户 L3 挂码仍 21（P383 修正未受影响）。未运行：浏览器控制台登录走查（数据删除不改代码，待用户复登）。
- **注意：** `manage.py seed-walkthrough` 可随时重建走查账号；公开注册如需再次演示须重新配置四层（全局开关仍在、demo-app 载体已删）。

## 2026-10-28 IAM P384 — 权限目录盘点：零孤儿、无可删项（纯只读，零改动）

用户要求「整理当前项目，删掉没有的权限编码」。三轮只读盘点后结论为无可删项，用户确认收尾。

- **① 引用计数（容器内 SQL）：** `role_permissions`/`role_data_scopes` 反查目录 67 码（management 27 + business 40，全部 active）——每个码至少被 1 个角色授权或数据范围策略引用，**零孤儿码**。
- **② 仓库代码扫描（node 七区扫描）：** 27 个 `iam.*` 管理码在 backend/app（判权）、seed_greenfield+manage（种子）、frontend/src（菜单守卫）三处全部有字面量引用，无「目录有、代码无」的码。
- **③ 疑点深挖：** 唯一后端/前端零引用的是 `crud.document.create/delete/read` 三码，但归属**活跃应用 CRUD Demo**（namespace=crud），被应用级角色 `crud-demo` 持有 + self 数据范围策略，`examples/iam-crud-fastapi` 示例工程（P322 SDK 联调资产）引用中——不删。
- **结论：无可删项**（用户已确认）。后续如需清理业务码，须先停用/删除对应应用，再处理其命名空间下的码。
- **验证：** 全程只读（SQL SELECT + 文件扫描），零代码/零数据/零迁移改动，无需测试与构建。

## 2026-10-28 IAM P383 — 角色分层方案落地（L3 扩权 21 码 / L2 收敛 15 码 / 授权权禁选三防线）

用户确认角色分层原型（`docs/prototypes/role-hierarchy-plan/`）后按序实施，落地四级角色职责边界：超级管理员管所有 → 租户管理员管当前租户下一切 → 应用管理员管当前应用一切 → 管理员（自定义角色）与应用管理员同域但**不能管理管理员** → 成员为业务用户。

- **模板码集重定义（`services/role_provisioning.py`）：** L3 租户管理员 9→21 码（补 application.read/manage/secret.rotate、app_role.manage、role.read、permission.read/manage、model.read/manage、theme.manage、audit.read、authorization.simulate）；L2 应用管理员收敛为显式 15 码（剥 organization.* 2 码，组织域归 L3）；模板描述改全域化文案。新增 `TEMPLATE_ROLE_KEYS`（4 模板 key）、`AUTHORITY_MANAGE_CODES`（app_role.manage / member.manage / invitation.manage / group.manage）、`is_custom_role()`。
- **「管理员不能管理管理员」三防线：** ① 平台侧 `access_control.replace_role_permissions` 与 ② 租户应用侧 `tenant_admin.replace_application_role_permissions` 对自定义角色含授权权码一律 422（模板角色不受限——L2/L3 本就是授权者来源）；③ `clone_role` 克隆产物为自定义 key 时自动剥离授权权码（业务码与资源实例授权保留，复制回模板 key 原样保留）。
- **存量修正：** 临时脚本（执行后已删）把 3 个租户的 L3 角色补齐 21 码、3 个应用的 L2 角色收敛 15 码。
- **前端禁选（与后端 422 同口径）：** `RolePermissionGrantModal` 新增 `lockAuthorityCodes` prop——授权权码禁选、历史已持有的从初始选中剔除、弹窗顶部警告 alert；`RoleManagement.vue` 与应用工作台 `RolesTab.vue` 按 `TEMPLATE_ROLE_KEYS` 判定传参。
- **验证：** 新增 `tests/test_role_hierarchy_guards.py` 6 项（双入口自定义 422 / 模板角色放行 / 克隆剥离且源角色不变 / 预置码数 21/15/0+幂等 / is_custom_role 语义）容器内 `python -B -m unittest` 全绿；回归 `test_g16_g24` 13 项 + `test_platform_tenant_guards` 7 项零回归；宿主机 vue-tsc + Vite 生产构建 exit 0（8.00s）；走查实测 `l3-admin@demo.example.com` 租户域 capabilities 恰 21 码、`l2-admin@demo.example.com` 应用域恰 15 码（零缺失零多余）。未运行：浏览器授权弹窗禁选交互走查（待用户复测）。

## 2026-10-28 IAM P382 — 平台租户防呆保护后端收口（五处写入口拦 platform）

P381 只挡了「切类型」与「删除」两个入口；本轮把平台引导租户（`PLATFORM_TENANT_SLUG`，L1 宿主 + deerflow/crud-demo 载体）的其余业务写入口一并防呆，统一 422 拒绝。

- **五处保护（复用 `seed_greenfield.PLATFORM_TENANT_SLUG` 常量，零手写 'platform' 字面量）：** ① `tenants.py set_tenant_status`——仅 disabled 分支拦截，active 幂等放行；② `organizations.py create_organization`；③ `invitations.py` 单发+批量邀请——经共享 `_validate_invitation_target` 在邮箱循环外一次性拦截，重发/撤销/兑换入口不动；④ `groups.py create_user_group`。
- **隔离测试：** 新增 `tests/test_platform_tenant_guards.py` 7 项（5 负路径断言 422 且含「平台引导租户」文案 + 业务租户建组织正路径 + 平台租户 active 幂等放行），照 test_g16_g24 夹具模式（内存 SQLite 直调 handler；L1 照 greenfield_fixture 三步造但直接挂 slug=platform 真实引导租户）。
- **验证：** 容器内 `python -B -m unittest`：新套件 7/7 OK；基线 `test_g16_g24 + test_login_throttle` 19 项 OK；追加 `test_entity_deletion + test_organization_workspace` 19 项 OK（覆盖被改模块的删除守卫与组织工作台），零回归。未运行：真实 HTTP 层验证（--reload 已热载，隔离测试直调 handler）。

## 2026-10-28 IAM P381 — 平台租户与业务租户区分（kind 归位 + 禁切保护 + 显式标注）

用户反馈「平台租户和其他租户混在一起」。审计实锤：2026-10-27 三次 `tenant.kind.change` 把 platform/demo/testdemo1 三个租户全改成 consumer，平台引导租户（L1 角色与引导超管的宿主）由此混入 ToC 消费目录。

- **数据归位：** platform 租户经 `PATCH /admin/tenants/{id}/kind` 改回 `organization`（绿场种子设计值，API 走审计）；demo/testdemo1 保持 consumer（真 ToC 语义）。影响面评估：capabilities 不依赖租户 kind（L2/L4 入口零影响）；应用挂载不看 kind（deerflow/crud-demo 无感）；公开注册校验只认 consumer（语义更准）。
- **后端保护：** `set_tenant_kind` 对 `slug=platform` 直接 422——「平台引导租户的类型由系统种子定义，不允许切换」，杜绝再次混入（实测生效）。
- **前端区分：** 租户管理页平台租户显「平台自有」品牌色描边 tag（tooltip 说明 L1 宿主身份），操作列隐藏「切换类型」与「删除」；应用编辑租户下拉的类型后缀自动随之变为「组织/企业」。
- **验证：** vue-tsc -b exit 0 + Vite 生产构建 exit 0（8.09s）；实测平台租户切类型 422、租户列表 kind 归位（platform=organization，demo/testdemo1=consumer）。

## 2026-10-28 IAM P380 — 授权界面权限项中文化（中文描述主显 + 编码副行）

用户截图反馈角色授权弹窗里全是裸权限码（`deerflow.agent.admin` 等），要求「都显示中文」。权限目录本就有中文 `description`，问题在端点未下发 + 前端只渲染 code。

- **后端 3 端点补 `description`：** 应用目录 `GET /tenant-admin/applications/{id}/permissions`（此前缺）、应用 grants `GET /tenant-admin/.../roles/{id}/permissions`、平台 grants `GET /admin/roles/{id}/permissions`（平台目录 `/admin/permissions` 本就带）。
- **RolePermissionGrantModal：** 选项改自定义 slot——中文描述主行 + 等宽 code 副行 + 停用项「（停用，仅可撤销）」标注；「预览影响」的新增/撤销/逐项影响/数据范围清理清单全部经 `codeLabel` 映射为「描述（code）」。
- **角色页资源授权清单：** 同步中文主显（描述存在时 strong 显示中文，code 与 resource_id 降为辅助行）。
- **顺带修脏数据：** 全库排查权限描述，仅 `crud.document.read` 描述='t' 异常，已修为「CRUD 示例：读取文档」；其余 18 条短描述（读频道/写项目等）为合法中文。
- **验证：** vue-tsc -b exit 0 + Vite 生产构建 exit 0（10.75s）；端点实测应用目录已下发中文 description；浏览器授权弹窗走查未运行（待用户复看两列布局下中文+code 双行效果）。

## 2026-10-28 IAM P379 — 修复登录主题手机端预览登录卡穿出手机壳（grid 轨道自引用）

用户截图反馈登录主题页「手机端预览丑陋」：手机壳（320px）中登录卡横向穿出两侧。

- **根因**（浏览器实测：壳 clientWidth 319px、登录卡 420px、溢出 101px，且桌面预览同样溢出 98px）：登录卡内联 `width: 420px; max-width: 100%`，但预览容器 `.theme-preview-frame` 是 grid——显式 width 会把隐式轨道**自撑大**到卡片宽度，`max-width: 100%` 相对被撑大的轨道解析形成自引用，约束彻底失效（flex/普通流中百分比基准是容器确定尺寸，不受影响）。
- **修复**（双管齐下）：
  ① `LoginThemeManagement.vue` 的 `themePreviewCardStyle`：手机预览模式下卡片宽度直接 `'100%'`（真机登录页卡片本就受视口约束，语义一致；桌面预览仍按 `card_width` 配置渲染）；
  ② `style.css` 新增 `.theme-preview-card-slot` 包装层（模板中卡片外包一层）：`width: 0; min-width: 100%` 打断轨道自引用——本层尺寸贡献归零、占满由容器决定的轨道，卡片「配置宽度放不下即收缩」在手机/桌面/分栏布局通用；配套三条 margin 规则还原水平对齐（默认居中=原 `place-items:center`，`position-left/right` 靠边）。
- **验证：** 浏览器实机复测：手机壳 320px 中卡片 295px 完全居中框内（左右偏移对称 13px）；桌面预览框 323px 中卡片收缩 266px 居中（原溢出 98px 归零）；`position-left` margin 规则命中（满宽时靠边无视觉差异符合真机语义）；vue-tsc 全量与 Vite 构建 exit 0。未运行：后端隔离测试（纯前端预览层改动）、真机访问（预览为桌面沙盒）。

## 2026-10-28 IAM P378 — C 端自助注册开启 + 端到端验收（D02 主链路）

用户授权开启公开注册并要求端到端验证。

- **开关确认：** `.env` 的 `IAM_ALLOW_PUBLIC_REGISTRATION=true` 已存在且 api 容器 env 已生效（无需重建）；SMTP（163）已配。
- **配置凑齐（demo-app，演示租户）：** ①租户 consumer+active 本就满足；②主题 `PUT /admin/themes/{app}?publish=true` 发布 v1（`show_register=true`、`terms_url=/terms`、`privacy_url=/privacy`——协议链接仅支持 HTTPS 或站内路径，`http://localhost` 422 被拒）；③应用 PATCH `registration_policy=open` + 注册角色 `3cf6d506`（app.member，`eligible_registration_role` 合规：纯业务角色、data_scope=self）+ 协议版本 v1.0×2。
- **端到端验收全通：** 匿名 `POST /auth/register` 202（防枚举统一文案）→ challenge 落库 `public_registration_challenges` → OTP 容器内按 `_derived_code` 密钥派生（DB 仅存 HMAC 摘要，不存明文）→ `POST /auth/register/verify` 201 建会话 → `/auth/me` 200 身份正确 → 落库四件套（演示租户成员 active + app.member 角色绑定 + 同意记录 v1.0×2）→ 邮件发件箱 pending（163 SMTP 真实投递）→ 同邮箱重复注册仍 202 同文案（防枚举）。
- **证据保留：** 测试账号 `e2e-register-51e18f61@example.com`（演示租户成员，app.member 角色）。
- **未运行：** 浏览器注册页 UI 走查、人工收信验证 OTP 邮件（待用户用可收信邮箱走登录页两屏流程）；D02 剩余项见进度文档 D02 行。

## 2026-10-28 IAM P377 — 修复「表格操作时页面抖动」

用户报障：表格操作（点按钮、删除、刷新）时页面会抖动一下。

- **根因：** `fitTableBodies` 高度自适应链路——MutationObserver 监听内容区全子树（childList），表格操作时的按钮 loading spinner 挂载/数据重渲染/分页瞬时状态都会触发重算（80ms 防抖后执行）；而每次重算测得的 fit 值受瞬时 DOM 状态与取整影响存在数像素级波动，每次都落笔 `minHeight/maxHeight` 导致表格区域高度反复跳变（loading 出现→消失可连续抖两三下）。
- **修复（`App.vue` fitTableBodies）：** 写入前记录上一轮 fit（`previousFit` 从 `maxHeight` 内联样式读取），本轮测量值与上轮差值 **≤4px 视为测量噪声，沿用旧高度不重写**；真实布局变化（分页器显隐、筛选区增删等数十像素级）仍正常跟随；收敛轮均摊扣除逻辑不变（真实溢出修正）。改动 1 处 +2 条注释，正常布局下 fit 值不变，零行为面变化。
- **验证：** vue-tsc -b exit 0 + Vite 生产构建 exit 0（8.37s）。未运行：浏览器实机复测（待用户点操作列按钮/翻页/删除感受抖动是否消失；若仍有残余抖动，升级方案为「跳过 loading 态测量 + 连续两轮一致才落笔」）。

## 2026-10-28 IAM P375 — 「高级管理」独立组取消（三项放回「应用与权限」组）

用户复核 P374 后裁定：不用新增「高级管理」组，三个列表页入口直接放在「应用与权限」组下。

- **navigation.ts：** 删除 `advanced` NavGroupKey 与 NAV_GROUPS 条目；applications/roles/permissions 三项 group 改回 `access`（紧随 application_workspace 之后，恢复 P346 之前的组内排列）。
- **AppSidebar.vue：** `DEFAULT_COLLAPSED_GROUPS` 去掉 `advanced`——「应用与权限」恢复日常展开组。
- **保持不变：** App.vue 的 `PLATFORM_SIDEBAR_EXCLUDED` 过滤删除状态（P374 交付，三项侧栏可见+能力守卫不变）；应用工作台页头下拉维持移除；空态「前往应用管理创建」直跳保留。
- **验证：** vue-tsc -b exit 0 + Vite 生产构建 exit 0（9.14s）；grep 全站无导航 `advanced` 残留（仅余登录主题编辑器无关类名 `theme-advanced`）。未运行：浏览器实机走查（待用户刷新侧栏复看）。

## 2026-10-28 IAM P376 — 全站图标统一为 antd 官方 @ant-design/icons-vue

用户裁定「项目中的图标都改成 antdv 里的图标」。此前 icons.ts 按 createIcon 模式手绘 29 个与官方同名的 24×24 线性 SVG（P348 记录为既有架构偏离），且与 ResourceIcon/OverviewPage/OverviewStatCard 直连官方包形成混用。

- **`plugins/icons.ts` 全量重写：** 29 个图标（AppstoreOutlined、ApartmentOutlined、BankOutlined、ClusterOutlined、UserOutlined、MailOutlined、TeamOutlined、HomeOutlined、SafetyCertificateOutlined、SafetyOutlined、ExperimentOutlined、DashboardOutlined、AuditOutlined、SkinOutlined、FileSearchOutlined、SearchOutlined、UserSwitchOutlined、IdcardOutlined、MenuOutlined、MenuFoldOutlined、MenuUnfoldOutlined、CheckOutlined、FilterOutlined、DownOutlined、UpOutlined、LockOutlined、ExclamationCircleOutlined、SettingOutlined、CheckCircleFilled）改为从 `@ant-design/icons-vue@^7`（已在依赖）**具名 re-export**——自绘本就照官方名手绘，名字完全一致。
- **消费方零改动：** 12 个文件（App.vue、AppSidebar、navigation、AdminPageHeader、AdminSearchField、AdminTableToolbar、audit、applications、groups、integration、roles、users 页）仍从 `@/plugins/icons` 导入，写法不变。
- **边界说明：** 仅具名 re-export、不做模块别名/重定向，不影响 antd 内部对该包的 /es/icons 子路径导入（原注释顾虑不适用于 re-export 方案）。
- **验证：** vue-tsc -b exit 0（29 名字官方包全部存在）+ Vite 生产构建 exit 0（8.23s）；grep 全站无 `<svg`/`createIcon` 残留。未运行：浏览器实机走查（官方图标与自绘 stroke 风格有细微视觉差异，待用户刷新复看；图标容器均为 1em anticon，布局不受影响）。

## 2026-10-28 IAM P373 — 全站提示降噪（页头副标题/工具条 hint 改「!」图标 + tooltip）

用户截图反馈应用工作台页头「日常配权三步」整行长文案太显眼，要求所有页面此类提示不要太明显、用「!」图标 + a-tooltip 展示。

- **`AdminPageHeader.vue`：** 副标题不再整行平铺，改为标题旁「!」图标 + a-tooltip 悬停展示完整说明（overlay maxWidth 360px；图标 muted 灰、cursor-help、hover 加深）。
- **`AdminTableToolbar.vue`：** hint 同样收敛为「!」图标 + tooltip，右侧操作按钮区布局不受影响。
- **`icons.ts`：** 按既有 createIcon 模式新增 `ExclamationCircleOutlined`（圆圈感叹号线性图标）。
- **`style.css`：** 清理唯一消费方消失后的失效样式 `.mgmt-page-subtitle`。
- **覆盖面：** 所有经共享组件传 subtitle/hint 的页面（应用/组织工作台、用户/角色/应用角色/租户接入/登录主题/模型治理/运营总览/授权模拟/新项目接入、工作台角色 Tab 挂码说明等）一处改全站生效。
- **验证：** 宿主机 vue-tsc -b + Vite 生产构建 exit 0（8.24s）。未运行：浏览器悬停走查（待用户复测）、深色/375 复跑（纯展示层改动，无断点与 token 变化）。

## 2026-10-28 IAM P374 — 「高级管理」下拉改造成侧栏折叠组

用户截图反馈应用工作台页头「高级管理」下拉（应用管理/角色高级管理/权限编码目录三项），经确认改造成侧栏折叠组形态。**（注：本形态已被 P375 按用户裁定调整为放回「应用与权限」组，本条目保留过程记录）**

- **navigation.ts：** 新增 `NavGroupKey 'advanced'`（「高级管理」，位于「应用与权限」「平台治理」之间）；applications/roles/permissions 三项从 `access` 组迁入。
- **App.vue：** 删除 P346 的 `PLATFORM_SIDEBAR_EXCLUDED` 平台模式侧栏排除过滤——三项恢复侧栏可见，`hasAnyCode` 能力守卫不变；租户侧 `/roles` 仍为「应用角色与成员」融合页入口（能力零变化）。
- **AppSidebar.vue：** `DEFAULT_COLLAPSED_GROUPS` 加 `advanced`（低频高级入口默认折叠，同平台治理/审计验证）；「当前路由所在组自动展开」逻辑复用，深链/刷新后菜单可用。
- **application-workspace/index.vue：** 页头 a-dropdown 连同 `ADVANCED_PAGES`/`goAdvanced`/`onAdvancedMenu` 及专用 import 整链移除；空态「前往应用管理创建」按钮改 `goApplicationManagement` 直跳（侧栏「高级管理」组保留同一路由入口）。
- **验证：** vue-tsc -b exit 0 + Vite 生产构建 exit 0（8.39s）；grep 全站无 `ADVANCED_PAGES`/`PLATFORM_SIDEBAR_EXCLUDED` 残留、无旧分组硬编码依赖。未运行：浏览器实机走查（待用户刷新侧栏复看）。

## 2026-10-28 IAM P372 — G16–G24 九项缺陷批量开发（后端+前端+迁移全链路）

用户指令「开始 G16–G24 开发」；经确认全部 9 项一口气实施、G16 采用详情抽屉形态、G18 采用本地盘卷存储。

- **G16 用户详情聚合页：** 新端点 `GET /admin/users/{id}/profile`（L1 门禁，聚合基本资料+成员关系+角色绑定+会话（复用 list_user_sessions）+最近 10 条 auth 审计事件）；新共享组件 `UserDetailDrawer.vue` 五分区抽屉，用户页「详情」入口。
- **G17 主题版本恢复：** `POST /admin/themes/{app_id}/{theme_id}/restore?publish=` 复制目标版本为新递增版本（可同步发布），审计 `theme.restore`；前端版本表「恢复为新草稿/恢复并发布」操作列。顺带修复存量 save_theme 缺 `validate_theme_config` 导入的潜伏 NameError。
- **G18 素材本地上传（用户裁决本地盘卷）：** `POST /admin/uploads/theme-assets` 原始字节直传（PNG/JPEG/WebP 魔数白名单、2MB 上限、排除 SVG 防注入）+ 公开只读 GET（`^[0-9a-f]{32}\.(png|jpg|webp)$` 白名单、一年不可变缓存）；compose 新增 `iam-theme-uploads` 卷挂 `/app/data/theme-uploads`；前端主题编辑器背景图/Logo 上传按钮。
- **G19 OIDC Back-Channel Logout：** `applications.backchannel_logout_uri` 列（应用编辑弹窗「单点登出联动」分区+422 URI 校验）；新 `services/backchannel_logout.py` 按 OIDC BCL 1.0 构造 RS256 `logout_token`（typ=logout+jwt、events、无 nonce），后台守护线程 best-effort 投递（3s 超时）；改密/自助重置/管理员重置/强制登出统一接线 `deliver_for_user`。业务侧接收端点联调待安排。
- **G20 三桶登录节流：** login_throttle.py 新增纯邮箱维度桶（HMAC-SHA256 键，独立阈值 `login_account_max_failures` 默认 15 防恶意锁号），与邮箱×IP 桶、IP 桶并列；sorted 加锁防死锁；改密/重置成功同步清邮箱桶——同账号换 IP 亦被锁定。
- **G21 邀请批量+重发：** `POST /admin/invitations/batch`（多邮箱去重、冲突跳过逐条明细）+ `POST /admin/invitations/{id}/resend`（换 token_hash 顺延有效期，accepted/revoked 409）；前端批量邀请弹窗+行「重发」按钮；invitations.py 重构出四个可复用助手。
- **G22 角色持有者反查：** `GET /admin/roles/{id}/holders` 直连+组继承来源合并（tag+tooltip 区分），`ensure_tenant_in_actor_scope` 判权；角色页「查看持有者」弹窗。
- **G23 登录历史联动：** 抽屉「查看登录记录」深链 `#/audit?actor=<id>`，审计页 `applyDeepLinkPrefill` 预填 actor、切「登录与认证」Tab、replaceState 清参。
- **G24 组织负责人+用户组嵌套：** `organizations.owner_user_id` 列+设置负责人弹窗（成员选项来自 `/tenant-admin/members`）+`organization.owner.change` 审计；`user_groups.parent_group_id` 同租户复合外键（RESTRICT）+防环校验+`effective_roles` 双列递归 CTE 向上遍历祖先组继承。组长委派保持后续评审。
- **迁移 `0004_owner_backchannel`：** 三表可空列；user_groups 复合外键走 batch_alter_table；迁移前受保护备份 `backups/pre-0004-owner-backchannel-20261028-105351.sql`+`.sha256`（229KB）；已应用，DB head=`0004_owner_backchannel`。
- **冲突说明：** 并行会话曾误删用户页 G02 管理员重置密码 UI，本轮已恢复并与 G16 详情入口合并。
- **验证：** `tests/test_g16_g24.py` 新增 13 项隔离测试+`test_login_throttle.py` 三桶适配，**50 项全绿**（api 容器 python -B）；vue-tsc -b exit 0（修 ThemeHistoryRow unknown 类型）+ Vite 生产构建 exit 0（8.17s）；api 容器 `--force-recreate` 后 `/api/v1/health` 200、六个新路由探测 401、uploads 卷可写实证。**未运行：** 浏览器写操作走查（破坏性动作待用户复测）、G19 业务方端到端联调。

## 2026-10-28 IAM P370 — 修复模型治理页头部空白近百px（grid stretch 拉高页头行）

用户截图反馈 /models「头部空白太多」（面包屑与页头 eyebrow 之间约 97px 空白）。

- **根因**（浏览器实测 gap=121.6px、链上 margin/padding 全零）：P364 骨架 `.mgmt-shell-content > div > section { flex: 1 0 auto }` 把 section 拉伸到填满视口剩余高度，而 `.model-governance-page` 是 `display: grid`——grid 默认 `align-content: stretch` 把多出的高度**均分给所有行**，页头行也被拉高；叠加 AdminPageHeader 根 div 的 `md:items-end`，标题块被推到拉高后的行底部 → 头部出现大片空白。仅此页中招（其余 section 型页面是 Tailwind flex column，子项不纵向拉伸）。
- **修复**（`ModelGovernancePage.vue` scoped）：section 改 `display: flex; flex-direction: column`（flex 子项默认不拉伸），新增 `.model-governance-page > :last-child { flex: 1 0 auto }` 与 `> :last-child > .data-card { flex: 1 0 auto }`——仅最后一个区块（账目/目录卡）吃剩余高度，保住 P364 页脚贴底与卡片撑满效果。
- **验证：** 浏览器实机复测：/models 头部 gap 121.6→**24px**（恰为内容区内边距）、scrollH=clientH=799 页脚贴底（footerGap 24px）；/model-usage 三区块头无回归（gap 24px）；vue-tsc 全量与 Vite 构建 exit 0。未运行：后端隔离测试（纯前端 scoped 样式改动）、深色/375 复跑（无断点变化）。

## 2026-10-28 IAM P371 — 产品缺口第二轮梳理（G16–G24 待办入表）

对照 PRD 逐条承诺的第二轮缺口实查（10 项：用户详情页/主题版本恢复/素材上传/账号锁定粒度/OIDC SLO/邀请能力/角色反查/登录历史联动/组织/用户组），新增 G16–G24 九行待办入进度文档 §4。纯文档轮，零代码。

- **G16（P0，PRD 承诺未兑现）：** IAM-USER-006 用户详情聚合页——现状仅列表页 + 五个零散弹窗（角色/会话/组织/租户关系各自独立），后端无 `GET /users/{id}` 聚合端点（数据散落 sessions/role-bindings/memberships 三端点）。
- **G17/G18（P1，PRD 6.7 相关）：** 主题历史恢复——版本链已建（application_themes 按 version 递增、draft/published/archived）但无 restore 端点、前端版本表只读；素材上传——前后端均只能填图片 URL，后端全库无 upload 端点/对象存储接入（PRD 自认「素材上传待开发」）。
- **G19（P1 评审）：** OIDC Back-Channel Logout 缺失——仅 RP-Initiated（/oidc/logout + post_logout_redirect_uris），IAM 登出后业务方本地会话不联动。
- **G20–G24（P2）：** 纯账号维度登录锁定（现为 HMAC(邮箱×IP)+IP 桶，换 IP 绕过账号级限制）、邀请批量+重发（现仅单邮箱，有效期 1–336h 已实现）、角色持有者反查（无 `GET /roles/{id}/bindings`，「改/停/删角色影响谁」无法回答）、用户页→登录历史联动（后端 actor_user_id 可筛但前端需手粘 UUID）、组织负责人/调动记录与用户组嵌套/组长委派（PRD 未承诺，产品评审）。
- **未运行：** 测试、构建（纯文档轮）。

## 2026-10-28 IAM P369 — /model-usage 模型用量页账本式改造（对齐 P368 概览设计语言）

用户要求「/model-usage 这个页面帮我改造的美观一点」。

- **汇总区账本化**（`frontend/src/views/models/ModelGovernancePage.vue`）：原 9 张 a-statistic 小卡改为「01 用量汇总」编号头 + 5 张 `OverviewStatCard` 巨号指标卡（请求总数/成功率/输入 Token/输出 Token/估算费用，28px tabular 数字 + 千分位）+ 次级审计脚注行（成功/失败绝对数、估算用量请求、未知费用请求以等宽小字收纳，信息零丢失）；`OverviewStatCard` 通用化——新增 `clickable` prop（false=纯展示 div 无悬停箭头/无按钮语义，默认 true 概览行为不变）与 `value: number | string` 放宽（容纳百分比/费用等已格式化字符串）。
- **三区块编号头**：01 用量汇总 / 02 待核对调用（badge 与「刷新核对队列」按钮上移至头行，卡内保留说明+警示+表格）/ 03 调用账目（目录视图为「01 模型目录」），对齐 P368 概览编辑部式排版；同步清理失效的 `.review-heading`/`.usage-summary` scoped 样式。
- **数字列右对齐**：账目表输入/输出 Token、估算费用、延迟，待核对表等待核对、预留输入/预留输出共 7 列 `align: 'right'`。
- **顺手修复**：估算费用显示科学计数法 `0E-8`（后端 Decimal 序列化透传）——新增 `formatCostValue` 将 `0E-8`/`1.5E-7` 类字符串归一为普通小数并去尾零，指标卡与账目列共用。
- **验证：** vue-tsc 全量（`--noEmit -p tsconfig.json`）与 Vite 生产构建宿主机 exit 0（37.4s）；浏览器实机走查（dev 5180 真实登录 admin）：01/02/03 编号区块渲染、指标卡数值与脚注正确、费用显示 `0`、两表数字列 computed textAlign=right、页脚贴底无悬空、/models 目录视图「01 模型目录」正常；零写操作。
- **未运行：** 后端隔离测试（零后端改动）；深色主题与 375 窄屏复跑（纯排版层，断点布局未动）。

## 2026-10-27 IAM P368 — /overview 工作台重设计（与登录页视觉区分）+ 深色主题品牌翻转回归修复

用户反馈 /overview 与 /login 视觉同质（旧页头 eyebrow「IDENTITY & ACCESS」、标语卡与登录页品牌块同款）。

- **Overview 重设计**（`src/views/overview/` 三文件）：页头改「CONSOLE OVERVIEW / 运营总览」；标语大卡降为上下细线状态条（服务健康点 + 数据更新时间 + DeerFlow/owner-only 阶段 pill）；指标卡改账本式编号（等宽字 01–05）+ 28px tabular 巨号数字 + 悬停箭头；「使用路径」提示改三步可点击流程链（权限编码→角色挂码→用户绑角色，图标+编号+悬停态，末步后不再渲染悬空箭头）；管理入口四卡加图标与悬停箭头，删「已提供管理 API」重复胶囊；章节编号 01–04 编辑部式排版。组件 props/emits 契约不变（App.vue 零改动接入）。
- **图表升级**（`OverviewDashboardCharts.vue`）：色板改渲染时读 CSS token（暗色自动翻转墨阶）；条形图降序 + 条尾等宽字直标数值（关键值不经悬停可读）；环形图加 HTML 环心总量覆盖层；**MutationObserver 监听 data-theme 即时重绘**，修复 P350 记录的「切主题后图表配色滞后到下次刷新」已知限制。
- **顺手修复 2 个实锘认陷**：①前端 `AdminOverview` 类型的 `models` 字段后端 `/admin/overview` 已不返回（旧页「模型目录」恒显「—」）——类型删字段，指标卡与图表行同步收敛为 5 项，`totalRecords` 逐字段 `?? 0` 防字段漂移 NaN；②**全站深色主题品牌翻转回归**：App.vue onMounted 无条件 `applyBrandToDocument` 写内联 `--color-brand`，压过 tokens.css `html[data-theme=dark]` 近白翻转块 → 深色下所有页面主按钮「暗底暗字」不可见、侧栏选中项无字（浏览器实测复现，用户管理页同现）——新增 `syncBrandToDocument`（默认石墨黑与暗色下深色自定义不写内联）+ watch(themeMode) 切主题时移除/重写内联；「历史存值 #121112 + 深色」场景专项复验通过。
- **验证：** `vue-tsc -b` 与 Vite 生产构建宿主机 exit 0（终验 13.32s）；浏览器实机走查（dev 5174 真实登录）：浅色首屏/图表双栏/步骤链/入口卡、深色全套、图表主题热切换即时重绘、环心总量 320 正确、零横向溢出，全程零写操作；控制台仅停服期 readiness 中断与 HMR 断连两条预期消息，零 Vue 告警。
- **未运行：** 后端隔离测试（零后端改动）；375 窄屏复跑（未动断点布局，P349 已验）。

## 2026-10-27 IAM P366 — G02 密码救济双通道（自助改密 + 管理员重置）

消除 SMTP 故障时忘记密码用户无救济的必然运营事故（G 系列缺陷待办 G02，裁决与待办见 P361）。轮次号曾短暂占用 P364/P365（与并行会话撞号），现定 P366。

- **后端自助改密 `POST /auth/me/password`**（`app/api/v1/auth.py`）：行锁取当前用户→`verify_password` 校验当前口令（错误记 `auth.password.change` failure 审计后 400）→Argon2 换哈希→bump `auth_version`→撤销 IAM refresh session 与 OIDC refresh token family→消费未兑换 authorization code/consent/旧重置链接→同事务成功审计；改密后旧 access token 因 auth_version 与 session 双失效即时 401。schema 新增 `PasswordChange`（current_password + new_password ≥12）。
- **后端管理员重置 `POST /admin/users/{id}/password`**（`app/api/v1/admin/users.py`）：L1 判权沿 users.py 惯例；禁自重置 400（本人必须走「验证当前密码」的自助通道）；仅启用状态 400；同一凭证级联；审计 `user.password.reset` 不含口令。schema 新增 `AdminPasswordReset`。
- **前端**：新共享组件 `src/components/ChangePasswordModal.vue`（defineModel 开关、当前/新/确认三段校验、成功后由 App.vue 走 signOut 强制退出）；顶栏用户区新增「修改密码」入口（移动端 LockOutlined 图标化沿 P349 isMobile 惯例；icons.ts 按既有 createIcon 模式新增锁形图标）；用户管理页「更多」菜单新增「重置密码」（仅非本人且启用状态显示，前端守卫+服务端负路径双兜底）。
- **验证：** 新增 `backend/tests/test_password_change.py` 隔离测试 **7/7 OK**（api 容器 `python -B`：成功级联+旧令牌 401、错口令不触凭证、短口令 422、管理员重置级联、禁自重置、禁非启用、无绑定 403）；`vue-tsc -b` 与 Vite 生产构建宿主机 exit 0；两新路由探测 401（`--reload` 热重载已注册，三容器 healthy）。
- **未运行：** 浏览器真实改密走查（破坏性动作，待用户复测）；全量隔离套件（P364 已跑 231 项基线，本机此后增量见各轮记录）。

## 2026-10-27 IAM P367 — 后端全量中文注释补齐（纯注释轮）

用户要求「后端代码都给我补上注释」。`backend/app` 全量 + `manage.py`（约 70 文件：main + api/v1 路由 29 + models 9 + schemas 10 + core 4 + db 4 + services 13）三组并行补齐中文注释——模块/类/函数 docstring + 复杂逻辑行注释（四级角色判定、data_scope 求交、令牌签发轮换、SKIP LOCKED 批清理、发件箱锁租约、级联删除审计等关键步骤）。**铁律：零可执行代码改动**；且刻意不用会改变运行时行为的注释载体（不加 SQLAlchemy `Column(comment=)`——会触发迁移差异、不加 Pydantic `Field(description=)`——会改 OpenAPI 契约、不改路由装饰器参数），存量注释原样保留。`migrations/`（已应用的受保护迁移链）与 `tests/`（方法名自述）未加。

- **验证（全部通过）：** 容器内 walk-import 全部 **58 个模块 ALL-IMPORTS-OK**；隔离随机库全量套件（`run_isolated_postgres_suite.py`）**231 项：225 过 + 6 项失败**，6 项与 P344 已记录的陈旧 mock 遗留逐一对应（`test_admin_authorization`×4 mock 已不存在的 `evaluate_access`、`test_application_updates`×2 轮换 403/404），非本次引入；API 容器 healthy、`/api/v1/ready` 200。
- **插曲（已复盘并记录）：** 验证中曾把 `test_model_usage_quota`（PG 集成测试，`skipUnless(database_url)`）用容器 env 直连共享开发库跑，7 项无意义失败——与 P307 存量真实账本（3 条 usage_events / 4 条 reservations）碰撞「全局待审队列/精确计数」断言；该模块 `tearDown` 外层事务整体回滚，**开发库零残留**。结论：此类集成测试只准走 `run_isolated_postgres_suite.py` 随机库，已记入项目记忆。

## 2026-10-27 IAM P364 — 页面空白治理：纵向 flex 骨架（卡片拉伸 + 页脚贴底 + 空态居中）

用户两张矮视口截图反馈「大量页面空白太多」「空白页面也要注意美观」——数据少/空态页的卡片下方与页脚之间大片画布裸露（模型治理空态页下半页约 1/3 空白；工作台 P359 固定 calc 高度与页脚间留 ~150px 空隙）。根因：页面高度不随内容自适应贴底。改造（纯前端布局层，零逻辑/零 API）：

- **纵向 flex 骨架（style.css）：** `.mgmt-shell-content` flex column；页面 v-show div 统一弹性列（内联 display:none 优先，隐藏页安全）+ `padding-bottom` 提供页脚间距；直接子 `.data-card` 与 `section` 型页面 `flex:1 0 auto` 吃掉剩余高度；footer `mt-6`→`mt-auto` 恒贴底。
- **卡片内部高度链（style.css）：** `.data-card/.mgmt-data-card` → `.ant-card-body` → `.ant-table-wrapper` → antd 容器链（spin-nested-loading > spin-container > table > container > header+body）逐层 flex，表格 body 随卡片拉伸——少数据/空态的面板撑满卡片，空白留在面板内而非裸露画布。
- **fitTableBodies 重构（App.vue）：** 测量基准从「内容区」改为「所在卡片 body」（骨架下页脚不占卡片内空间，老口径 reserve 估算失效）；先清空上一轮 min/max 再测量（否则 minHeight 撑高卡片形成正反馈循环——首版实测卡片越量越高、页脚被推出视口）；minHeight 与 maxHeight 同值让面板恒撑满；空态 placeholder 单元格吃到面板高度垂直居中（td padding 叠加以 body.scrollHeight 实测校正一次）；弹窗内表格（用户页会话表）跳过。
- **工作台（P359 调整）：** 两个 workspace section 的 `lg:h-[calc(100vh-156px)]` 固定高度删除，由骨架 flex 拉伸自适应（`lg:min-h-[380px]` 保底保留）；组织工作台右栏三张卡片补 `h-full`（此前右卡不参与拉伸、与左树底边差 72.7px）。
- **验证：** vue-tsc exit 0 + 生产构建 exit 0（12.8s）；浏览器两轮走查（browser 代理，1059 宽视口）——7 页页脚全部贴底（24px 设计留白）、空态垂直居中、models/tenants 行区撑满（分页下仅剩 24px 内边距+16px 分页 margin 的结构性余量）、双工作台双栏底边对齐 778.7、users 多行表格内滚正常无双滚动条、overview 布局无回归（图表无塌陷）；全程零 Vue 错误/警告（仅导航中断的 health 轮询 ERR_ABORTED，良性）。**未运行：** 558px 极矮视口实测（浏览器代理无法锁定矮视口；逻辑上 flex 自适应比固定 calc 更耐受矮视口，minBodyHeight=72 保底沿用）、深色主题复跑（纯布局层改动）。

## 2026-10-27 IAM P363 — 后端结构规范化 + 根目录会话残留清理（用户裁定）

后端审计结论：主干（`app/api/v1` + `core` + `db` + `models` + `schemas` + `services` + `migrations` + `tests`）已是标准 FastAPI 布局，仅清理两处非标准残留；主干层零改动、零业务逻辑/零 API 契约变化。

- **oidc.py 兼容垫片删除：** `app/api/v1/oidc.py`（纯转发垫片，docstring 自述「兼容入口」）整体并入 `oidc_provider/__init__.py`——装配代码不变，追加 `.authorization`/`.logout`/`.metadata`/`.tokens` 的 13 个再导出，`__all__` 扩至 15 项（符号逐一核实存在；包内子模块无反向包导入，无循环风险）。改 3 处导入：`main.py` 1 处、`tests/test_oidc_consent.py` 4 处 `from app.api.v1.oidc import` → `from app.api.v1.oidc_provider import`。
- **tenant_admin 双散件合并为包：** `tenant_admin.py`（聚合路由）→ `tenant_admin/__init__.py`，`tenant_admin_application_roles.py` → `tenant_admin/application_roles.py`（内容零改动，无反向引用）；`main.py` 经包 `__init__` 导入 router 自动生效，全仓仅 1 处内部 import 需改。
- **根目录清理（用户确认清单）：** 删除 9 个 `_` 前缀会话草稿文件（_guide.txt、_sync_py/ts.txt、_verify_caps/levels/login.json、_mu_model_id/tenant_id.txt、_role_name.txt，均为 10/24 DeerFlow 联调残留，全仓 grep 零引用）+ `_scratch_export/`（7 文件，旧文档导出副本）+ `_wave1_tmp/`（1 文件）；空目录一并移除。
- **验证（全部通过）：** 容器内 `python -B -c "import app.main"` 冒烟导入 OK；`--reload` 热重载后容器 healthy、`/api/v1/ready` 200；受影响隔离测试 `test_oidc_consent` + `test_oidc_tenant_claim` 合跑 **16 tests OK**；grep 复查 `app\.api\.v1\.oidc\b` 与 `tenant_admin_application_roles` 在 backend 全部 .py 零命中。backend/README 目录结构与「当前 API」节同步新路径（带日期历史条目未动）。

## 2026-10-27 IAM P362 — 全站深度走查美化（基于 P360 新目录结构）

用户要求「深度检查整个项目所有页面，让页面更加好看」。16 页浏览器走查（生产 5175 登录 + 浅色主题）+ 静态扫描 + 宽视口（1333px 内容区）表格溢出实测后，按黑白灰轻奢设计系统收敛 4 类缺陷，全部落在 P360 重构后的新路径上：

- **侧栏蓝黑底修复（走查实锤最大观感缺陷）：** antd dark menu 根/子菜单容器默认 `#001529`/`#000c17` 蓝黑底压过纯黑侧栏 `#09090B`（Tailwind `bg-transparent` 与特异性规则均被 cssinjs 注入顺序压制——同 P349 层叠坑）。修复：`styles/antd-bridge.ts` Menu tokens 补 `darkSubMenuItemBg: 'transparent'`；[style.css](frontend/src/style.css) 兜底——根菜单高特异性、子菜单沿桥接层 `!important` 先例强制透明（drawer 移动端同覆盖）。复验 computed style：aside `#09090B`、子菜单透明，蓝黑色块全消。
- **违规彩色 tag 中性化（P351 语言的遗漏点）：** 租户类型紫/蓝 → 中性灰；应用「受信 · 静默授权」紫 → 琥珀 warning（静默授权风险语义）、「开放注册」蓝 → 灰；模型「凭证已配置」蓝 → 灰、「管理员核对/网关上报」紫/蓝 → 灰。语义色仅留绿（启用/成功）、红（删除/失败）、琥珀（估算/受信）。
- **表格横向溢出收敛（宽视口实测驱动）：** applications 1660→1320（溢出 447→0，11 列一屏）、invitations 1520→1330（187→0）、roles 1200→1048（1280 视口滚动 208→56）、organizations 1040→820（1280 视口归零）、groups 操作列 300→240（2px→0）；models 15 列宽表定位允许滚动，2120→1784 减量。角色操作列 160→170 修按钮折行。全部压缩列补 `ellipsis`。
- **减红降噪：** 权限目录操作列 danger 描边实体按钮（整列红框噪音）→ 红字链接（danger 语义保留在字色+确认弹窗）；租户/模型「停用」去掉 danger 红改墨色（停用非删除级危险），「删除」保留红——每行至多一个红动作。
- **交互细节：** 角色页/邀请页租户筛选 `ref('')` → `ref<string | undefined>(undefined)`（空串被 antd Select 当已选值，placeholder「全部租户」从不显示）；审计页「符合条件 N 条」蓝字与 5 处 slate 硬编码 → `--color-text-*` token（AdminFilterField/AdminSearchField/App.vue 外观面板/页脚/AdminFilterPanel 同族）；4 处 `text-[10px]` 下拉箭头归整 11px（设计系统 Overline 刻度）。
- **发现并保留：** 无新增裸 hex、无重阴影、无 emoji 滥用；改动全部落在 P360 重构后的 `src/views`、`src/styles`、`src/layout`、`src/components` 新路径上。
- **验证：** `vue-tsc --noEmit` exit 0（全量非增量）；`vite build` exit 0（9.5s）；宿主机 dev 5180（proxy 指向容器 8002）浏览器六页复验——侧栏纯黑、租户灰 tag、应用琥珀 tag+11 列一屏、邀请「全部租户」占位、角色操作列单行、权限红字链接，全部 PASS；控制台零 Vue 告警。**未运行：** 深色主题复验（改动均为 token/结构层，P350 已验暗色链路）、375 窄屏复跑（未动布局与壳层）。
- **收尾补漏（旧目录清理后的全站复查）：** P360 重构使 `views/**` 成为唯一本体，上轮基于「views 为零引用旧副本」的豁免判断失效，实锤 4 处漏网违规色并全部中性化——应用角色页（租户模式）成员角色名 `blue`+「用户组」`purple`→灰、用户页会话类型 `purple/blue`→灰（动态绑定三元，上轮字面量扫描模式未覆盖）、OIDC consent 页 scope `blue`→灰、集成页（死路由保留源码）方案 A/B `purple`→灰+选中图标 `text-violet-600`→`var(--color-brand)`。复查 grep（`purple|violet|geekblue|blue` 字面量+动态绑定）全站零命中；App.vue 历史紫 `#5B5BD6` 判断逻辑属豁免。vue-tsc + 构建复跑通过（12.2s）。

## 2026-10-27 IAM P361 — 产品缺陷全量审查（G01–G15 待办入表）

资深产品视角对 IAM 全量审查：前端 18 路由 + 后端端点盘点、认证能力有无清单（MFA/CAPTCHA/SAML·LDAP·SCIM/注销/短信/自助改密/个人中心/通知/Webhook 全无实查）、会话/审计/模型/i18n/帮助专项，与 PRD 交叉验证。零代码/零 API/零迁移，仅更新 `docs/项目总览与进度.md`（新增 G01–G15 任务行 + P361 轮次行 + 速览「下一步」同步 + 校正叙述层目录重构轮次标注为 P360，原叙述误标 P359、速览表行原已正确）。

- **实锤 2 处 PRD↔实现定义矛盾（G01，待用户裁决）：** ①PRD §3「审计人员」只读角色在绿场四级写死（L1–L4）后无处授予——审计端点实挂 L2 管理角色（`backend/app/api/v1/admin/audit.py` ensure_roles([L2_ROLE_KEY])，`iam.audit.read` 仅存目录码）；②IAM-USER-003（P0）承诺「邮箱或手机号重置」，实现仅邮箱（`backend/app/models/identity.py` phone_number 有字段无短信设施）。
- **同日裁决（G01②）：** 用户确认不接手机号短信，密码重置仅走邮箱——PRD IAM-USER-003、§4.2「邮箱或短信验证」与账号规则行已改为邮箱口径（手机号字段保留为后续能力；纯文档修订，无代码改动）；G01①（「审计人员」只读角色）仍待裁决。
- **运营必然事故链（G02，最高性价比修复）：** 登录态无自助改密 + 管理员侧无重置密码端点（`admin/users.py` 仅列表/创建/状态）——SMTP 故障时忘记密码用户无任何救济。
- **其余缺口（详见进度文档第 4 节 G 行）：** 会话盲退（RefreshSession 无设备/IP/最后活动，G06）、批量操作未实现（IAM-USER-007 P1，G07）、审计无导出无告警（G08）、模型费用无币种/失败无原因/账本无归档（G09）、PRD §12 指标未落地（G10）、无 Webhook 事件订阅（G11）、注册无 approval 审批态（G12）、L1 无 MFA（G03）、账号注销/数据导出缺失（G04）、绿场后 A04 未重验（G05）、存量短密码无升级路径（G13）、i18n 全无（G14）、无帮助/错误码入口（G15）。
- **不重复建行：** DeerFlow E2E 未闭环由 B01–B05/C01–C03 跟踪；SDK 框架插件化与接入向导由 F02 跟踪；MFA 全量/ABAC/资源实例授权/SAML·LDAP·SCIM 由 F01 与 PRD §2.2 跟踪。
- **未运行：** 后端测试、vue-tsc、Vite 构建（纯审查+文档轮，无代码改动）。

## 2026-10-27 IAM P360 — 前端目录标准化重构（用户裁定按项目级目录规划）

纯目录重构，零逻辑/零 UI/零 API 变化，**后端零改动**（核查结论：backend/app 已符合 FastAPI 项目级标准布局 app/api/v1 + core + db + models + schemas + services + migrations + tests，无需调整）。迁移映射：`frontend/src/features/**` → `views/**`（全部页面模块，含两个 workspace 的 components/tabs 子结构）；`app/auth/AuthEntry.vue` → `views/auth/`；`app/router.ts` → `router/index.ts`；`app/navigation.ts` → `router/navigation.ts`；`app/featureLoaders.ts` → `router/loaders.ts`；`app/App.vue` → `src/App.vue`（根组件提到 src 根）；`app/components/AppSidebar.vue、AppBreadcrumb.vue` → `src/layout/`；`shared/services/` → `src/api/`（api.ts 改名 index.ts，import 写 `@/api`）；`shared/utils/` → `src/utils/`；`shared/theme.ts` → `styles/theme.ts`；`shared/ui/index.ts` → `components/index.ts`（barrel 改指 ./）；`app/ui/antd.ts、registerManagementUi.ts、app/icons.ts` → `src/plugins/`；删除空目录 app、shared、services。`vite.config.ts` + `tsconfig.json` 配置 `@` → `src` 路径别名，约 50 个文件导入改写为 `@/`（views 模块内部相对引用保留）。

- **验证（全部通过）：** 宿主机 `node node_modules\vue-tsc\bin\vue-tsc.js -b` exit 0；宿主机 `node node_modules\vite\bin\vite.js build` exit 0（约 9.3s；ant-design-vue / vue-vendor chunk 拆包不变，仅存量 antd chunk 体积警告）。
- **残留复查：** grep 旧路径模式（`shared/services|shared/utils|shared/theme|shared/ui|app/icons|app/navigation|app/ui|app/auth|app/App|app/router|features/` 等）frontend/src 下全部零命中。
- **浏览器冒烟：** dev 容器 5175 真实登录 admin——登录页渲染 → 登录进 /overview → 用户/角色/应用工作台三页 → 深链刷新守卫，全 PASS；全程无 Vue warning（仅刷新时 1 条健康轮询 ERR_ABORTED，可忽略）；零写操作。
- **未运行：** 后端隔离测试套件（零后端改动，未跑）。

## 2026-10-27 IAM P359 — 两个工作台双栏各自滚动、贴底对齐（用户截图反馈）

用户要求应用/组织工作台「左右两边各自滚动，内容都到底部」。改动：两工作台 section 桌面档（lg+）固定高度 `calc(100vh-156px)` + `min-h-[380px]` 保底；页头 shrink-0；分栏区 `flex-1 min-h-0`；左树与右内容栏 `lg:h-full lg:overflow-y-auto` 各自内滚（窄屏保持流式堆叠不变）。高度经两轮浏览器实测校准（初值 252px 底部留白 95px，按 section/footer 实测差调整为 156px）。终验：content 溢出 0（仅 dpr 1.5 亚像素 1px 舍入）、footer 距内容区底 23.3px≈24、左右栏底边完全对齐（779px）、零 Vue 告警。

## 2026-10-27 IAM P358 — 资源感知增强（图标 / 编码前缀自动化 / 描述字段）

用户要求：按钮/菜单数据都要有图标方便感知；新增资源时编码自动带上上级 code（如 DeerFlow 应用新建第一个节点即 `deerflow.` 前缀，后面自己输入）；父级菜单要显示出来；多加描述字段；注意审美。

- **受保护备份：** `backups/pre-0003-resource-description-20261027-173938.sql`（216KB）+ `.sha256`（SHA256 11C9E656…45954）。
- **后端：** 迁移 `0003_resource_description`（application_resources 加 `description` String(500) 可空列）；模型/schemas（Create/Update 带 trim+空转 None）/CRUD 序列化与 `my-resources` 下发节点均补 description。**新坑：alembic revision id 全长必须 ≤32**（`alembic_version.version_num` 为 varchar(32)，超长事务回滚；首版 `0003_application_resource_description` 38 字符已中招，事务性 DDL 保证无残留后缩短重跑）。
- **前端：** 新共享组件 [ResourceIcon.vue](frontend/src/features/application-workspace/components/ResourceIcon.vue)——按钮固定方框、数据规则固定漏斗、菜单按 icon 名解析（24 个黑白灰语义线性图标映射，未命中回落应用图标），资源树与授权弹窗节点行首统一展示；资源节点弹窗：图标字段升级为选择器网格（选中石墨黑底白图标、再点取消）、「描述」textarea（≤500）、编码输入框前置只读前缀块（`#addonBefore`）——新增节点前缀自动跟随父级完整 code，顶级用应用命名空间（如 `deerflow.`），用户只输入尾段，编辑按「父级 code.尾段」拆分回显；树节点 hover 提示描述与路由。
- **修复 2 缺陷（走查实锤）：** ①`#addon-before` kebab-case 槽名不渲染 addon（antd-vue 槽名 camelCase，DOM 无 .ant-input-group-addon）→ 改 `#addonBefore`；②选中格 `text-white` 未生效致黑底黑图标 → 选中态补内联 `style color:#fff` 兜底 currentColor 链路。
- **搜索模糊化（用户追加）：** 资源树与授权弹窗搜索升级为模糊匹配——空格分隔多词 AND，命中字段扩展至名称/编码/描述；共用 [resourceSearch.ts](frontend/src/features/application-workspace/components/resourceSearch.ts) `matchResource`，命中节点仍保留祖先链。
- **弹窗形态按用户参考图返工：** ①图标字段弃用系统图标选择器网格，改回普通输入框自由配置（icon 存任意标识，antd 名命中映射则树节点渲染对应线性图标，未命中回落默认；ResourceIcon 删 OPTIONS 导出仅留解析映射）；②父级菜单字段仅在应用已有菜单节点时显示（创建第一个节点必为菜单，字段隐藏）；③编码前缀从外挂 addon 块改框内置灰（`#prefix` + muted mono），贴合「父菜单编码置灰显示、后面才可编辑」。走查三点全过（TreeSelect 显示、框内灰字前缀 `deerflow.`、图标输入框），零 Vue 告警。
- **按钮图标与路径化编码（用户截图追加）：** 按钮节点图标由空心方框 BorderOutlined（用户裁定丑）换 ControlOutlined 调节滑块；树节点（资源 Tab + 授权弹窗）灰色编码改**路径化显示**——`buildResourcePathCodes` 从根逐级拼接（自身 code 已含父路径则原样，否则父路径+`.`+自身，兼容历史散码；带防环访问标记），如 `deel` → `deel.123` → `deel.123.12311`，上级/上上级编码始终可见；编码区 `max-w-[100px]` 截断 + 完整路径 tooltip。走查三项全过（滑块图标 DOM 确认、三级路径逐级显示、84px 未触发截断），零告警。
- **父级菜单可选框修复（用户截图实锤）：** 新建/编辑弹窗「父级菜单」label 与 help 之间空白——**TreeSelect 组件从未注册**（P347 a-transfer、P343 Tree 同款问题；此前走查误把未知元素 DOM 当已渲染），补注册后为带边框可选框，下拉含「顶级菜单」+已有菜单树可展开；「第一个菜单无父级字段」逻辑沿用（应用无菜单节点时隐藏）。走查键盘展开下拉确认可选，零未知组件告警。**教训：未知组件渲染为 HTMLUnknownElement 视觉空白但 DOM 可查，走查勿以标签存在判渲染成功。**
- **验证：** `test_application_resources` 10 项（含 description 持久化与下发断言）+ P356 合跑 14 OK；vue-tsc + 构建通过；浏览器三轮走查——前两轮实锤上述 2 缺陷（另：合成点击坐标漂移误存相邻图标为已知现象），修复后终验全绿：前缀块 `deerflow.` 显示、选中格黑底白图标、建删链路还原、零 Vue 告警。**待真实鼠标复核：** 图标点选精确性（合成点击漂移一格属测试环境现象）。

## 2026-10-27 IAM P357 — 应用资源树（菜单/按钮/数据规则 + 角色授权 + 消费端下发）

用户裁定菜单权限应为「面向应用的树形结构：一级/二级菜单配路由、图标、菜单编码、额外参数（JSON 存储），应用可拉取；菜单下挂按钮权限与数据权限；角色可分配菜单/按钮/数据权限」。经 AskUserQuestion 批准「授权迁移 + data_rule 占位实现」。P356 的权限码推导视图由显式资源树替代。

- **受保护备份：** `backups/pre-0002-application-resources-20261027-170804.sql`（202KB）+ `.sha256`（SHA256 6C83C4A6…C821E）；`D:\backup` 被沙箱拒绝后落工作区 `backups/`。
- **迁移：** `0002_application_resources`（down_revision=0001）——`application_resources`（application_id/parent_id 自引用 CASCADE、resource_type CheckConstraint menu|button|data_rule、code 应用内 Unique、path/icon/sort/extra JSON/status）+ `role_application_resources`（role_id+resource_id 复合主键双 CASCADE）；容器内 `alembic upgrade head` 成功，PG 隔离临时库全新建链至 0002 复验通过。extra 默认值用方言无关 `'{}'`（`'{}'::json` 会破坏 SQLite 隔离测试）。
- **后端 7 端点：** 资源 CRUD×4（`has_application_admin_access` manage 门禁、按钮/数据规则必须挂菜单、编辑环形检测 409、删除有子 409 且显式清理授权行 + bump 持有者凭证、审计 `application_resource.*`）；角色资源 `GET/PUT /applications/{id}/roles/{role_id}/resources`（全量替换、自动补祖先、跨应用资源静默过滤、PUT 后 bump）；消费端 `GET /authorization/my-resources?client_id=`（有效角色并集复用 `list_effective_roles`，仅 active 节点，父停用子树上提，嵌套树下发）。
- **前端：** 工作台第三 Tab 改名「资源权限」——MenuTab 重构为资源树管理（平铺组装树、搜索保祖先链、默认全展、hover 行内「加子级/编辑/删除」、节点弹窗：类型/父级 TreeSelect(仅菜单+排除自身后代)/编码/名称/路由/图标/排序/额外参数 JSON 校验/状态）；新增 `RoleResourceGrantModal`（checkable 树 + 搜索 + 已勾选计数，保存全量替换）；角色 Tab 操作列增「配置资源」（仅平台控制台挂载）。
- **顺带修复：** 平台管理员全局应用列表（无 tenant_id 过滤）此前不返回 `can_manage`，致资源 Tab 管理按钮不渲染——L1 在 `has_application_admin_access` 恒过，`list_applications` 平台视图补 `can_manage/can_rotate_secret: true`。
- **验证：** 新增 `tests/test_application_resources.py` 10 项隔离（层级校验/唯一码/环形/删除级联/补祖先/替换语义/跨应用过滤/直连树/组继承下发/停用上提/404），与 P356/P353 合跑 28 项全绿；vue-tsc + Vite 构建（宿主机 node 直跑）通过；API 两轮重启探活；浏览器两轮走查——第一轮发现 can_manage 契约缺陷（已修），第二轮全链路通过（建菜单→加子级按钮→编辑→配置资源勾选保存→回显→逐个删除还原，控制台零 Vue 告警）。**存量问题（与本次无关，P344 已记录同因）：** PG 全量套件 6 项失败（`test_admin_authorization`×4 mock 已不存在的 `evaluate_access`、`test_application_updates`×2 轮换 403）。**待人工复核：** 授权弹窗勾选计数在合成事件下显示不符（真实鼠标待复）；文档对接手册新增 §11 下发契约。

## 2026-10-27 IAM P356 — 应用菜单权限（对齐蓝图 user-center-sys 资源视图）

用户要求参考蓝图项目 `user-center-sys` 补「应用 → 菜单权限」。蓝图核心：资源四分类（menu/button/api/data_rule）+ 角色经 permissionIds 关联资源 + 树形勾选 + 后端下发资源供业务端过滤菜单。**落地取零迁移路径**：菜单码 = 业务权限码 + `resource_type=menu` + `requires_data_scope=false`（evaluate_access L138-141 对该组合直接放行，不触发数据范围强制），复用权限目录/角色挂码/审计全链路，不动 surface 枚举与迁移链。

- **后端（1 处增量）：** 应用登记权限端点 `create_application_permission` 的 `requires_data_scope` 由硬编码 True 改为按资源类型推导——`menu`/`button` 类资源自动关闭数据范围强制；其余业务码（如 document）仍强制。目录/列表端点已返回 resource_type 等字段，零改动。
- **前端：** 应用工作台新增第三个 Tab「菜单权限」（新组件 `application-workspace/tabs/MenuTab.vue`）——按 code 点分段推导层级树（`deerflow.menu.project.list` 挂在父级下，中间段为路径占位），节点显示菜单名称 + 停用 tag + hover 完整码；搜索按码/说明过滤并自动展开命中路径；「登记菜单权限」弹窗（L1 `iam.permission.manage` 同权限目录口径）校验命名空间前缀，resource_type/scope 固定 menu；空态引导登记。角色勾选菜单码走既有「角色」Tab 配置权限弹窗（RolePermission 通用授权），消费端业务系统按码判权过滤菜单（蓝图同构）。
- **测试：** 新增 `tests/test_menu_permissions.py` 4 项隔离（menu/button 关闭数据范围强制、document 仍强制、命名空间校验 422），与 `test_entity_deletion` 合跑 **18 tests OK**；vue-tsc + Vite 构建（8.1s）通过；API 容器重启；浏览器走查 4/4（三 Tab 齐全、菜单 Tab 提示/登记按钮/空态/弹窗校验、权限编码 Tab 回归正常）。

## 2026-10-27 IAM P355 — 用户组弹窗穿梭框化 + 高级管理菜单排版 + 工作台窄屏树限高（用户 5 图反馈）

用户发 5 张截图裁定「样式丑陋」。逐一定位：①管理成员弹窗只有单个多选下拉、弹窗空荡；②分配角色弹窗选项平铺难读；③应用工作台「高级管理」下拉纯一行长文字无结构；④⑤窄屏工作台第一屏只见树卡、右侧内容在下方滚动区（白卡低对比观感「空白」；核对布局代码无缺陷，右卡实际渲染于树卡下方）。

- **用户组关系弹窗穿梭框化（`GroupRelationModal.vue`）：** 单个 `a-select multiple` 升级为 `a-transfer`（对齐 P345 用户页「配置租户角色」交互）——左右双栏（318×352）+ 双向穿梭 + 独立搜索（标题/描述均匹配）+ 底部「已选 N 项；保存为全量替换」摘要；成员行「显示名（邮箱 · 状态）」、角色行「名称（key · 停用标记）」；沿用停用未分配角色禁勾入规则；弹窗 720→760px。复用已注册的 Transfer 运行时组件，PUT 契约零变化。
- **高级管理菜单排版（`application-workspace/index.vue`）：** 三个菜单项从一行长文字（应用管理（回调 / 密钥轮换 / 信任））改为「图标 + 标题 + 灰色小字说明」两行结构（AppstoreOutlined/SafetyOutlined/FileSearchOutlined）。
- **工作台窄屏树限高（应用/组织两处调用）：** 树卡窄屏 `max-h-80` 内部滚动（lg 及以上不限），树过长时不再把右侧内容顶出首屏。核对布局代码确认窄屏堆叠与右卡渲染本身无缺陷（P349 已实测），本次为观感优化。
- **验证：** vue-tsc + Vite 构建（10.3s）通过；浏览器走查——管理成员/分配角色穿梭框双栏+搜索+摘要全过（取消无写入）、高级管理菜单三项图标+两行排版全过、桌面两工作台分栏正常。**未运行：** 窄屏实机复验（子代理视口固定 1059 无法调窄；限高为低风险样式改动，请用户窄屏复看）。

## 2026-10-27 IAM P354 — 组织管理表格改树形（用户反馈）

用户指出组织管理应为树形表格（原为平面列表 + 「上级组织」文字列，层级关系不直观）。改造：`OrganizationManagement.vue` 按 `parent_id` 将平面数据组装为 `children` 树（父行缺失的孤儿按顶层兜底），antd Table 原生树形渲染（子行缩进 + 展开箭头）；受控 `expandedRowKeys` 默认全展开、数据刷新后自动重展、用户可手动折叠；移除冗余「上级组织」列（层级由缩进表达），组织名称列 240→280。复用 AdminListPage 透传（`expanded-row-keys` / `expanded-rows-change` 走 `$attrs`）。验证：vue-tsc + 构建（11s）通过；浏览器走查——层级缩进正确（sss→刘少华）、折叠/展开正常、顶层无重复行、操作列（停用/删除）正常。

## 2026-10-27 IAM P353 — 全站删除功能补齐（6 实体可删，4 类刻意不删）

用户要求补齐删除功能；按数据模型约束与 IAM 惯例定删除矩阵。后端 6 个 DELETE 端点 + 前端 6 页入口 + 14 项隔离测试全绿。

- **后端端点（复用各实体 `*.manage` 判权，均写审计 `*.delete`、行锁、与审计同事务）：** `DELETE /admin/tenants/{id}`（禁删 platform 引导租户 422；有模型用量账目 409；成员/角色/应用/邀请/组/组织/模型目录级联，审计 SET NULL 脱钩保留）、`DELETE /admin/applications/{id}`（应用管理门禁双查；用量 409；主题/OIDC 令牌级联，应用角色 SET NULL 退化为租户角色）、`DELETE /admin/roles/{id}`（禁删 platform.super_admin；被未兑换邀请引用 409；级联授权/绑定/组分配/数据范围，删前解除 `registration_role_id` 悬挂引用并 bump 持有者凭证）、`DELETE /admin/groups/{id}`（L2/L3 判权；级联成员/角色挂接，删前 bump 组内成员）、`DELETE /admin/organizations/{id}`（有子组织 409；成员挂接级联摘除，成员账号保留）、`DELETE /admin/models/{id}`（用量账目 409 提示改用停用）。
- **刻意不删（用户原则「特定不能删除的就不要」）：** 用户（用量 RESTRICT + 审计链完整性，已有停用/锁定）、权限编码（目录设计即只读，停用保留授权）、邀请（已有撤销）、登录主题（属应用配置随应用级联）。
- **前端入口（6 页，全部 danger 红字 + Modal 强确认列明级联范围 + 后端 409/422 文案透传）：** 租户/组织/模型操作列并排「删除」；角色页删除进「更多」菜单；用户组页顺带收敛操作列（直达 管理成员/分配角色 + 更多[编辑/停用/删除]）；应用页顺带收敛（直达 权限项/编辑 + 更多[轮换密钥/信任/停用/删除]）——两页原操作列 5-6 个动作超规范，借本次一并收敛。
- **验证：** 新增 `tests/test_entity_deletion.py` 14 项隔离测试全绿（种子保护 422 ×2、用量/邀请/子组织 409 ×4、正常删除 ×5、404 ×1、悬挂引用清理 ×1、应用保留断言）；vue-tsc + Vite 生产构建（10.4s）通过；API 容器重启加载新路由（ready 200）；浏览器走查 6 页入口与确认弹窗全部符合预期、取消无写入，用户管理页确认无删除入口（符合矩阵）。已知现象：「更多」菜单在子代理合成事件下不收起（P349/P351 同，真实鼠标正常）。

## 2026-10-27 IAM P352 — 修复表格 hover 时 fixed 操作列透明

用户报告（附截图：审计页 hover 行「查看详情」列透出来源 IP 文字）。**根因：** 行悬浮背景用了半透明的 `--color-brand-subtle`（rgba），fixed 列是 sticky 定位无实体底色，hover 时横向滚动内容透出。**修复：** tokens.css 新增不透明行悬浮色 `--color-row-hover`（`color-mix(in srgb, var(--color-brand) 6%, var(--color-bg-elevated))`，暗色 8%；随 ColorPicker 覆盖联动），style.css 两处 hover 兜底规则与 antd-bridge `Table.rowHoverBg` 三处统一换用。验证：vue-tsc + 构建（8.4s）通过；浏览器复验（审计页滚动后 hover + 用户页 hover + 深色抽查）浅/深主题 fixed 列均为不透明悬浮色，无文字透叠。

## 2026-10-27 IAM P351 — 全站列表页对齐工作台观感（用户基准图精修）

用户发来组织/应用工作台截图为基准要求全站同质感。对比走查 9 页后定位 4 类差距，全部修复并复验通过。

- **角色管理页操作列收敛（`RoleManagement.vue`）：** 6 个平铺动作（编辑/配置权限/资源授权/数据范围/复制/停用）收敛为「编辑 + 配置权限 + 更多」下拉（低频 4 项收纳，停用为 danger 项），照抄 P349 用户页模式（`onRowMenuClick` 分发）；无 `iam.role.manage` 权限时保留单独「停用/启用」链接。操作列 width 470→170——**fixed 列越窄，对中间列的滚动遮挡越小**，角色标识列不再被盖住。
- **宽表列宽全面压缩（users/tenants/permissions/roles）：** 985→830 / 1025→860 / 1360→1020 / **1790→1200**（scroll.x 同步）——1059 半屏视口的裁切/遮挡观感大幅减轻，**1280+ 视口除角色表外全部不滚**；权限页超长 hint 精简为一句（「只读目录；编码不可编辑或删除，菜单显示不构成服务端授权。」）。
- **彩色残留清理（黑白灰一致性）：** 审计操作 tag 蓝→**中性灰 mono tag**（结果列成功绿/拒绝红语义保留）；权限码 tag 蓝→灰 mono（RolesTab / ApplicationRoleManagement / RoleManagement「N 项」）；组织工作台「主组织」tag 蓝→灰。语义色（启用绿/停用红）为唯一点缀的原则下，**蓝色块只允许出现在 info 语义场景**。
- **工具条 token 化（`AdminTableToolbar.vue`）：** slate 硬编码类（border-slate-200/70、bg-white/90、text-slate-500）→ `var(--color-border)` / `var(--color-bg-elevated)` / `var(--color-text-secondary)`，去 backdrop-blur；暗色覆盖样式保留。
- **验证：** vue-tsc + Vite 生产构建（10.2s）通过；浏览器复验（1059 视口，零写操作）5 页全过——角色操作列 3 元素+菜单 4 项、用户/租户/权限关键列完整可见、审计 tag 中性灰 mono、无页面级横向滚动。**已知限制（记录不阻塞）：** 1059 视口下 8 列角色表（1200px）仍需表格内横滚（内容区 722px 物理极限，1280+ 不滚）；「更多」菜单在子代理合成事件下不因点击空白收起，为测试环境已知现象（P349 同），真实鼠标交互正常。

## 2026-10-27 IAM P350 — 全站视觉改造：轻奢极简黑白灰（用户点名「页面丑陋」重造）

用户裁定极光紫体系观感不佳，选定「轻奢极简黑白灰」方向（全站 + 重点页精修）。新语言：**zinc 纯中性灰阶 + 石墨黑品牌 + 纯黑侧栏 + 语义色作唯一点缀**；轻奢感来自大而柔的阴影、字阶与留白，不再依赖彩色渐变。

- **Token 层换血（`tokens.css`）：** 中性 slate（蓝调）→ zinc 纯灰（canvas #FAFAFA / subtle #F4F4F5 / border #E4E4E7 / 文字 #18181B·#52525B·#A1A1AA）；侧栏 #0B1220（深蓝调）→ **纯黑 #09090B**，选中指示条从品牌色改**白色**；品牌 #5B5BD6 → **石墨黑 #18181B**；暗色块画布改 #0E0E10、**暗色下品牌翻转为近白 #FAFAFA**（黑上黑不可见）、brand-subtle 翻白 8%；阴影重调为「贴地 1px + 大而极柔环境影」双层结构；登录画布 #09090B。
- **antd-bridge（`antd-bridge.ts`）：** fallback 全量同步 zinc；新增三个实测修正——① `colorLink: primary`（**antd 链接色默认跟 colorInfo 蓝而非主色**，不设则表格操作列/退出按钮全是蓝，实测踩坑）；② `colorLinkHover` 跟 brand-hover；③ `colorTextLightSolid` 暗色反转深色（**暗色主按钮翻浅底后白字白上白**，实测踩坑）；`Button.primaryShadow` 去掉 antd 默认 `0 2px 0` 硬投影；`readCssVar` 导出供 App.vue 复用。
- **主色运行时（`App.vue`）：** 默认主色 #5B5BD6 → #18181B，**历史默认紫在 localStorage 读取时视为未设置**（防老存值拉回紫）；新增 `displayPrimary` computed——暗色内容区对**深色主色按 WCAG luma 亮度判断**（<80）统一回落暗色品牌近白（兼容用户浏览器实测存着的 #121112 历史自定义），亮色自定义尊重用户；antd 与图表共用此值。顶栏头像文字色 #ffffff → `var(--color-bg-elevated)`（暗色白底黑字）。
- **壳层与页面：** AppSidebar「ID」logo 方块改白底黑字（侧栏恒黑，品牌色在黑底/暗色翻转下都会消失，改用 sider token 组合恒定反差）；style.css 登录光斑紫/蓝 → 极微白光、工具条 focus 紫硬编码 → token；图表（OverviewDashboardCharts）色板紫品红 → **墨色三级 + 蓝绿琥珀语义点缀**，画布文字/网格线/描边全部改读 CSS token（暗色下不再写死浅色值），模板 slate 类 → token 类。
- **文案与布局精修：** 概览「怎么用这套权限体系」整卡降为 🧭 提示条；页头副标题去教程腔——用户/角色/权限/概览 4 页「第一步/第二步/第三步/主路径」波次文案改为职责陈述（教程感是「廉价感」来源之一）。
- **默认值一致性：** AdminColorField、AuthEntry OIDC 兜底色、LoginThemeManagement 新主题默认（primary #18181B / 背景 #fafafa）全部对齐黑白灰。
- **验证：** vue-tsc 通过；Vite 生产构建通过（11.1s）。浏览器走查两轮 + 终验一轮（5175 容器 dev，零写操作）：浅色概览/用户页——侧栏纯黑、logo 白底黑字、主按钮纯黑白字、操作列/退出墨色（全页无蓝色残留）、提示条/统计卡符合预期；深色主题——主按钮浅底深字可辨、操作列近白、卡片表格文字可读、切回浅色正常。**未运行：** 375 窄屏本轮未复跑（改动集中在 token/文案层，布局框架 P349 已验证）；主题热切换时 echarts 画布色不随 data-theme 即时重绘（下次数据刷新生效，记录为已知限制）；登录页（黑画布白卡）因走查会话已登录未截图验证，样式改动为纯 token 层。
- **遗留：** 子代理报告「不刷新直接切主题有样式残留」疑为 HMR 环境特有，生产构建 ConfigProvider theme 为响应式 computed，P348 走查中主题切换正常，标注观察不阻塞。

## 2026-10-27 IAM P349 — UI 检查待修清单 4 项全修复 + 375 顶栏溢出追加修复

按优先级落实 P348 待修清单；复验中发现并追加修复第 5 项（顶栏 375 换行溢出）。全部通过浏览器复验。

- **①用户表操作列收敛（`UserManagement.vue`）：** 6 个动作按钮（配置角色/分配组织/租户关系/会话/锁定/停用）收敛为「配置角色 + 会话」两直达按钮 +「更多」下拉（分配组织、租户关系、锁定|解锁、分隔线、停用|启用，按用户状态切显）；`onRowMenuClick` 统一分发到原有处理函数，业务逻辑零变化；操作列 width 490→170、表格 `scroll.x` 1320→1010（横向滚动压力消除）；`canManageUsers` 为 false 时整列显示「—」。复验：每行仅 3 元素，「更多」菜单 4 项与预期一致。
- **②工作台窄屏堆叠（`application-workspace/index.vue` + `organization-workspace/index.vue`）：** 外层布局 `flex-col lg:flex-row`，左树 `w-full lg:w-64`——375 下树与内容上下堆叠（树 343px 全宽），桌面保持左右分栏。复验：两个工作台 375 下 `flexDirection=column` 正确。
- **③极矮视口 fit 保底（`App.vue` fitTableBodies）：** 表格体保底高度 120→72 两处——高 <600 视口下原保底使内容区出现 ~31px 外层纵向滚动（P338 边界回归）。本轮未在极矮视口单独复测（沿用 P348 实测口径，机制不变仅降保底）。
- **④半档间距归 4 倍数（8 处）：** AppBreadcrumb `py-1.5→py-1`；AdminPathGuide `gap-2.5→gap-2`、`mt-0.5→mt-1`；AppSidebar `gap-2.5→gap-2`；FeatureLoading `gap-1.5→gap-2`；application-workspace 高级管理按钮 `gap-1.5→gap-2`；OverviewPage `gap-1.5 px-2.5→gap-2 px-3`；OverviewStatCard `mt-0.5→mt-1`（integration 已下线源码跳过）。
- **追加修复：顶栏 375 换行溢出（`App.vue` + `icons.ts`）。** 375 复验发现右侧 `a-space :size="10" wrap` 换行叠加到固定高 header（P311「顶栏偏挤」加重版）：去 `wrap`、size 10→8、加 `shrink-0`；「外观」按钮移动端只留齿轮图标（icons.ts 新增 `SettingOutlined` 自绘图标）、桌面保留文字。**层叠坑实测记录：** 首版用 Tailwind `hidden sm:inline` 隐藏文字，被 antd 未分层规则 `.ant-btn > span { display:inline-block }` 压过（未分层样式优先于任何 `@layer`，含 utilities）——改用已有 `isMobile`（≤650px）条件渲染，绕开层叠。
- **过程插曲（自愈，非产品缺陷）：** 首轮浏览器复验时 5175 出现「Tailwind 全缺失」假象——根因是 icons.ts 一次错误的插入把 `CheckCircleFilled` 的 `defineComponent(` 头挤断，容器 dev server 模块图整体挂掉（入口链 icons.ts → App.vue → style.css 全断，只剩 antd cssinjs），修复语法后 page reload 自动恢复。
- **验证：** vue-tsc 通过 + Vite 生产构建通过（宿主机 node 直跑，pnpm corepack 损坏绕开）；浏览器复验（5175 容器 dev，超管会话，零写操作，菜单只开不点）：375 下顶栏单行 `scrollWidth=375=innerWidth`、外观按钮纯齿轮图标且浮层正常弹出、用户表操作列 3 元素+菜单 4 项、两个工作台堆叠正确。**未运行：** 桌面视口回归走查（子代理不支持调窗；外观按钮桌面分支与原实现等价、工作台 `lg:` 断点为既有形态，风险低）；极矮视口（③）单独复测。

## 2026-10-27 IAM P348 — 全项目 UI 检查（静态扫描 + 16 页浏览器走查 + 深浅主题 + 375 窄屏）+ 暗色主题修复

对照 `docs/ui-design-system.md` 与 checklist 全量检查。**发现并修复 1 个高价值缺陷，4 项待修列入清单**。

- **缺陷（已修复）：暗色主题 CSS 变量层从未生效。** `tokens.css` 暗色块选择器为 `html[data-theme="dark"]`，但应用把 `data-theme` 只写在 `<a-layout>`（App.vue 模板）上——选择器永不匹配。后果链：`antd-bridge.readCssVar` 从 documentElement 读变量 → 暗色时读到**浅色值** → 显式 token（colorBgLayout/Container/Border/Text）覆盖 `darkAlgorithm` 派生色 → 暗色模式实际靠 `style.css` 的 `.ant-layout[data-theme=dark]` 局部覆盖 + darkAlgorithm 残余撑起（「伪暗色」，实测 localStorage=dark 时 body 仍 #f7f8fa）。**修复：App.vue `watch(themeMode, immediate)` 同步 `data-theme` 到 `document.documentElement`**——tokens 暗色变量、antd-bridge 读值、style.css 选择器三层全通。复验：暗色 body #0e1118 / 表格 #151a24 / 文字 #e2e8f0，截图对比度良好、无浅色残留块；浅色回切正常；vue-tsc 通过。
- **16 页动态走查（桌面 1059 视口）合规项：** 页面级横向溢出 16/16 为零（P338 成果保持）；每页可见 Primary 按钮 ≤1；feature 层无内联 hex 样式；表格空态/loading 齐全；控制台零 Vue 告警（仅健康探测 ERR_ABORTED 网络噪音）；危险操作有确认；`prefers-reduced-motion` 已处理。
- **375 窄屏走查（用户配合调整窗口）：** 汉堡菜单按钮出现、抽屉导航菜单齐全可用；页面级无横向溢出（滚动收进表格）；760px 弹窗自适应 359px 无溢出；组织工作台/应用工作台可用但**布局未堆叠**（见待修 3）。
- **待修清单（未动代码，按优先级）：** ①用户表操作列 6 个动作（规范 ≤3+「更多」收纳），连带 490px 操作列造成表格横向滚动压力与深色截图中的 fixed 列视觉错位观感；②应用/组织工作台左右布局在窄屏（<lg）未上下堆叠，375 下右侧内容区仅剩 87px；③极矮视口（高 <600px）下内容区出现 ~31px 外层纵向滚动（fit 公式保底 120px 与矮视口冲突，P338 边界回归）；④少量非 4 倍数间距刻度（AppBreadcrumb `py-1.5`、OverviewPage `px-2.5` 等 Tailwind 半档类）。
- **静态扫描备注（记录不阻塞）：** App.vue 内 `primaryColor` 默认 `#5B5BD6` 应收敛进 tokens/bridge；style.css 登录/主题预览域残留少量裸 hex（登录域规范允许稍强表现，预览域 #151a22/#a0a8b5/#fafbff/#e6eaf0 待收敛）；侧栏图标为自绘 `createIcon`（icons.ts）而非规范写的 `@ant-design/icons-vue`——打包优化的既有架构决策（P339），标注偏离即可。
- **验证：** 修复后容器内 `vue-tsc -b` 通过（本轮仅前端 2 文件：App.vue、此前的 registerManagementUi 归 P347）；浏览器走查即验证载体；全程零写操作（弹窗只开不存）。375 视口由用户手动调整配合。

## 2026-10-27 IAM P347 — Wave 1–4 联合浏览器走查（零写操作）+ 2 缺陷修复

浏览器代理走查 console 5175（vite dev 挂载本地源码，超管登录，全程只打开/查看/取消，未保存任何业务数据），覆盖四波全部验收点。**发现并修复 2 个缺陷，复验通过。**

- **缺陷 1（P345 遗留）：`a-transfer` 未注册导致穿梭框不渲染。** 「配置租户角色」弹窗打开后仅渲染表单骨架，控制台 `Failed to resolve component: a-transfer`；`registerManagementUi.ts` 补注册 `Transfer`（与 P343 补注册 `Tree` 同类模式：vue-tsc 不检查运行时组件解析，必须浏览器走查兜底）。复验：双栏「可选角色/已配置角色」渲染、右栏按服务端 `in_group` 口径回填已绑定角色、左右栏搜索框齐备。
- **缺陷 2（P346 遗留）：深链刷新被弹回工作台。** 平台模式刷新 `/applications` 被重定向 `/overview`——`initializeConsole` 平台分支用 `visibleNavigation`（侧栏口径）判定入口页，Wave 4 侧栏降级后三列表页不在其中。改用 `isPageReachable()`（可达性口径）。复验：`/applications`、`/roles`、`/permissions` 三个深链刷新后全部直达对应页面（应用管理 3 应用列表 / 角色管理 / 权限编码），侧栏保持降级。
- **走查通过项（修复后全绿）：** ①侧栏终态——身份与组织 5 项（组织工作台置顶）、应用与权限仅应用工作台、新项目接入不可见、平台治理/审计验证默认折叠且点击展开正常（租户/主题/模型×2；模拟/审计）；②应用工作台——左树按租户分组（平台管理租户 DeerFlow/CRUD Demo、演示租户演示应用）、默认选中、三步主路径副标题、「高级管理」下拉三项、角色 Tab 挂码弹窗（67 码 36 勾选与 P343 一致）取消无写入、权限编码 Tab deerflow.* 目录 3 页、`/project-integration` 重定向工作台；③组织工作台——左树层级（sss→刘少华）、成员 Tab 新接口真实数据（主组织/成员状态/账号状态列）、用户组 Tab 空态引导「到用户组管理页创建」；④用户管理——配置角色 Transfer 弹窗（缺陷 1 修复后）取消无写入；⑤审计——「管理操作 240 条 / 登录与认证 110 条」两 Tab 切换，登录 Tab 首屏全部 `auth.login/logout/refresh`（服务端 `action_prefix` 过滤真实生效）；⑥Wave 4——深链三列表页直达、概览「管理接入应用」按钮、折叠组交互；⑦退出登录回落登录页。
- **验证：** 修复后容器内 `vue-tsc -b` + Vite 生产构建通过；浏览器走查本身即本轮验证载体。375/768 窄屏沿用惯例留给用户。
- **已知小瑕疵（不阻塞）：** Transfer 右栏多个同 key 不同应用的角色显示相同英文标识（如 app.member×2 属不同应用角色），保存按 role id 不受影响；后续可在 render 中附应用名区分。

## 2026-10-27 IAM P346 — Wave 4 收口：散落列表页降级 + 工作台空态强化三步主路径

按 `docs/glm-align-user-centent-prompt.md` §6 Wave 4 完成；仍不做 DeerFlow、不做接入、不做 Resource 新表。

- **散落列表页降级（`App.vue`，选「降为高级入口」而非并入）：** **仅平台模式**把「应用管理 / 角色管理 / 权限编码」三项从侧栏下线（`PLATFORM_SIDEBAR_EXCLUDED`）；**租户模式刻意不动**——`/roles` 在租户侧渲染「应用角色与成员」融合页（`ApplicationRoleManagement`），是 L2/L3 的核心入口，降级会砍掉其工作流。可达性与侧栏可见性分离：新增 `isPageReachable()`（按 NAV_ITEMS 能力 any-of 判定），`setPage`/`syncRoutePage`/能力撤销 watch 三处门卫改用它——平台模式深链 `/applications`、概览页「管理接入应用」按钮仍可达，页面能力（回调/密钥轮换/克隆/全局启停）零损失；路由表与 `router.beforeEach` 守卫不变。
- **工作台高级入口（`application-workspace/index.vue`）：** 页头新增「高级管理」下拉（应用管理=回调/密钥轮换/信任；角色高级管理=编辑/启停/克隆；权限编码目录=全局登记与启停），与空态「前往应用管理创建」按钮共用 `goAdvanced()`；SPA 内 `router.push`，能力守卫兜底。
- **空态强化三步主路径（新共享组件 `components/AdminPathGuide.vue`）：** 编号步骤引导组件（`steps: readonly string[]` + title），应用工作台无应用空态（三步配权主路径 + 前往应用管理创建按钮）、未选应用空态，组织工作台无组织空态（三步组织管理主路径 + 前往组织管理创建按钮）、未选组织空态全部接入；文案与页头副标题同口径。
- **验证：** `vue-tsc -b` 通过（首轮 4 个 TS4104 readonly 报错修复后 exit 0）；Vite 生产构建通过。本轮零后端改动，后端测试未运行。浏览器点验未运行；375/768 窄屏沿用惯例留给用户。
- **刻意不做（Wave 4 边界）：** 把角色/权限列表整体并进工作台 Tab（工作台 Tab 保持日常最小面，高级能力走入口跳转）；组织管理列表页侧栏降级（提示词仅点名应用/角色/权限三类，组织列表是 Wave 2 工作台的建tree入口，保留）；members 邀请/用户/用户组入口不动。

## 2026-10-27 IAM P345 — Wave 3：用户配角色 Transfer + 审计拆 Tab + 平台治理默认折叠

按 `docs/glm-align-user-centent-prompt.md` §6 Wave 3 完成（蓝图只读参照 `user-center-sys` 的 distributionRole Transfer 交互与审计拆分）。

- **用户配角色 Transfer 打磨（`UserManagement.vue`）：** 「配置租户角色」弹窗的多选下拉升级为 `a-transfer`（对齐蓝图 distributionRole）：左「可选角色」/右「已配置角色」双栏 + 名称/英文标识搜索 + 列表项展示 `roleKey`（英文标识 + 停用标记）；停用且未绑定的角色禁止新勾入（`item.disabled`），已绑定的停用角色保留可移除，避免保存时无意清掉历史绑定；弹窗加宽 760px。后端 `PUT /admin/users/{id}/role-bindings` 契约不变（整表替换直接绑定）。
- **审计拆 Tab（`AuditLogPage.vue` + 后端最小增量）：** 页面顶部新增「管理操作 / 登录与认证」两 Tab；登录 Tab 走 `action_prefix=auth.` 服务端前缀过滤（分页与总数真实，而非前端截断），操作 Tab 全量。后端 `GET /admin/audit/search` 新增 `action_prefix` 参数（`_query_audit_events` 共用；LIKE 通配符 `%`/`_` 按字面转义防误扩大结果集；旧 `/audit` 端点不变）；空态/副标题文案按类别区分。
- **平台治理默认折叠（`AppSidebar.vue`）：** `platform`（租户/主题/模型治理/用量）与 `ops`（鉴权模拟/审计）两组默认折叠——即「租户 + 登录主题弱化聚合」的落地方式：**刻意不建蓝图式 IAM 设置聚合页**（不做聚合页，仅降低导航存在感），租户管理与登录主题保持独立页面；当前路由所在组自动展开（深链/刷新菜单可用），点开折叠组后行为不变。
- **测试：** `tests/test_audit_query.py` 夹具补 `auth.login`/`auth.logout` 事件，新增 `action_prefix` 聚合与通配符字面化用例；测试 helper 显式传 `action_prefix=None`（直调 handler 时 FastAPI `Query` 默认值非 `None`，与 P344 同类教训）。
- **验证：** `vue-tsc -b` 通过（exit 0）；Vite 生产构建通过；`python -m unittest tests.test_audit_query tests.test_organization_workspace` 10 项 OK（api 容器）。浏览器点验未运行；375/768 窄屏沿用惯例留给用户。
- **刻意不做（Wave 3 边界）：** IAM 设置聚合页；蓝图 B/C/G 三端与 portal；组角色只读透传 UI（组继承来源已在应用角色页可见）；审计登录 Tab 不做独立登录流水表（`auth.*` 事件即登录/登出/刷新/重置链路）。

## 2026-10-27 IAM P344 — Wave 2：组织工作台（左组织树 + 成员/用户组 Tab）

按 `docs/glm-align-user-centent-prompt.md` §6 Wave 2 完成（蓝图只读参照 `user-center-sys/src/views/department` 的「左树 + 成员/组 Tab」信息架构）；组织仍挂租户，不做组织改挂应用。

- **后端最小增量（`backend/app/api/v1/admin/organizations.py`，同挂 `/admin` 与 `/tenant-admin`）：** ① `GET /organizations` 平铺列表响应补 `parent_id` 字段（组织工作台前端拼层级树必需，旧字段 `parent_name` 保留向后兼容）；② 新增 `GET /organizations/{id}/members`——列出直接挂接该组织的成员（`require_organization_admin_access` 逐租户判权，不递归子组织），支持 `q` 关键词搜索（姓名/邮箱），响应含 `is_primary`、成员状态与账号状态，上限 1000 行。
- **新增组织工作台 `features/organization-workspace/`（文件夹 + index 组织）：** `index.vue`（页头副标题写明组织上下文三步：左树选组织 →「成员」看挂接成员 →「用户组」管组关系；按可读租户并发拉取组织目录合并，默认选中首个组织，未选组织时 AdminEmpty 中文空态「请先选择左侧组织」，选中卡片标题带停用/租户标记 + a-tabs 两 Tab）、`components/OrgTree.vue`（租户分组节点不可选 + `parent_id` 层级拼树，父节点被搜索过滤时子节点上浮防丢节点，全部默认展开，名称/标识搜索 + 停用标记）、`tabs/MembersTab.vue`（只读成员表：主组织/成员状态/账号状态标签 + `q` 搜索 + 刷新；空态引导到「用户管理」调整归属）、`tabs/GroupsTab.vue`（用户组挂租户不挂组织，按所选组织所属租户整租展示；「管理成员/分配角色」复用共享弹窗；新建/编辑/启停仍留在用户组管理页并在 hint 说明）。
- **共享组件抽取（禁止重复造轮子）：** 新增 `components/GroupRelationModal.vue` 统一组员/组角色批量编辑（打开时拉取目录、服务端 `in_group`/`assigned` 标记回填已选项、PUT 全量替换保存、`canSave=false` 只读）；`GroupManagement.vue` 改为复用（删除内置 relation 弹窗实现与死 CSS，行为保持一致），组织工作台用户组 Tab 同样复用。
- **导航与接线：** `navigation.ts` 新增 `organization_workspace`（`/organization-workspace`，「身份与组织」组内最前，requiredPermissions=any-of `iam.organization.read`/`iam.group.read`，不新增未入库码）；原「应用组织」列表入口更名为「组织管理」（label 与 PAGE_INFO 标题）；`featureLoaders.ts`/`App.vue` 挂载工作台（平台模式所有租户 `can_read_organizations=true`，租户模式按能力位过滤，apiPrefix 双端）。路由经 `PAGE_PATHS` 自动注册，无新深链重定向需求。
- **测试：** 新增 `backend/tests/test_organization_workspace.py`（隔离 SQLite 直调 handler 5 项：列表 `parent_id`、按组织列成员含 `is_primary`、`q` 搜索过滤、组织不存在 404、越权租户 403；夹具教训——`TenantMembership` 须显式 id 避免 flush 顺序耦合、直调 handler 时 FastAPI `Query` 默认值非 `None` 须显式传 `q=None`）。
- **验证：** 容器内 `vue-tsc -b` 通过（exit 0）；Vite 生产构建通过（`organization-workspace` 独立 chunk 11.41kB）；`python -m unittest tests.test_organization_workspace` 5 项 OK（api 容器）。全量隔离套件 `run_isolated_postgres_suite.py` 195 项中 6 项 ERROR（`test_admin_authorization` 4 项 + `test_application_updates` 2 项）——**均为 P340 绿场重构后的过期 mock 遗留**（mock `admin_authorization.evaluate_access` 已不存在 / applications 判权入口已改 `require_application_admin_access`），失败发生在 mock 装配阶段，与本次 organizations 改动无关；**遗留修复待用户指令**。
- **刻意不做（Wave 2 边界）：** 组织改挂应用；子组织成员递归聚合；用户组新建/编辑/启停搬入工作台；成员组织归属编辑（留在「用户管理」/「成员与数据范围」）；蓝图字段配置类能力。
- **未运行/未做：** 真实登录浏览器走查（本轮以 vue-tsc + 生产构建 + 后端隔离测试为证据，dev 5175/5180 点验待用户或下轮执行）；Wave 3–4 等待指令。

## 2026-10-27 IAM P343 — Wave 1：应用工作台对齐 user-centent（下线新项目接入）

按 `docs/glm-align-user-centent-prompt.md`（蓝图只读参照 `user-centent/apps/user-center-sys` 的 appAndRoleManagement 信息架构）完成 Wave 1，主路径写死为「权限编码 → 角色挂码 → 用户多角色」。

- **新增应用工作台 `features/application-workspace/`（文件夹 + index 组织）：** `index.vue`（页头三步主路径副标题 + 左树 + 右侧应用卡片内「角色 / 权限编码」两 Tab，未选应用时 AdminEmpty 中文空态「请先选择左侧应用」，默认自动选中首个应用）、`components/AppTree.vue`（按租户分组的两级应用树 + 名称/Client ID 搜索 + 停用标记）、`tabs/RolesTab.vue`（平台模式 `/admin/roles` 按应用 scope 过滤 + `iam.role.manage` 判权；应用模式走 `/tenant-admin/applications/{id}/roles`，`can_manage` 判权；两者都可新建角色）、`tabs/PermissionsTab.vue`（复用权限面板）。
- **共享组件抽取（禁止重复造轮子）：** `features/applications/ApplicationPermissionPanel.vue` 从抽屉抽出面板主体（列表/搜索/登记/启停），`ApplicationPermissionDrawer` 瘦身为壳；新增 `components/RolePermissionGrantModal.vue` 统一平台与应用角色的挂码编辑（目录+通用授权加载、影响预览、确认原子保存），`RoleManagement.vue` 已改为复用（删除其内置 grant 编辑实现，行为保持一致）。
- **导航改造：** `navigation.ts` PageKey/PAGE_PATHS/NAV_ITEMS/PAGE_INFO 下线 `project_integration`，新增 `application_workspace`（`/application-workspace`，「应用与权限」组内最前，requiredPermissions=any-of `iam.application.read`/`iam.app_role.read`/`iam.role.read`，不新增未入库码）；`router.ts` 旧深链 `/project-integration` 重定向到应用工作台；`featureLoaders.ts` 移除接入页 loader（`features/integration/` 源码保留）；`App.vue` 挂载工作台（平台模式复用壳层应用字典）；`OverviewPage.vue` 能力卡与快捷按钮改指工作台；`icons.ts` 新增 `ApartmentOutlined`、删除不再使用的 `ApiOutlined`。
- **全局 antd 注册：** `registerManagementUi.ts` 补注册 `Tree`（管理台首个 a-tree 用法，否则模板解析失败）。
- **缺陷修复（首轮浏览器验收发现）：** `ApplicationPermissionPanel` 与 `RolePermissionGrantModal` 的 watch 补 `immediate: true`——抽屉 destroy-on-close / 工作台 Tab / `v-if` 弹窗在挂载时 `active/open` 已为 true，缺失 immediate 导致首次数据不加载（表现：权限编码表、挂码复选列表全空且不发请求）。
- **后端阻塞修复（非功能改动）：** `backend/app/api/v1/tenant_admin.py` 首部误带 UTF-8 BOM（U+FEFF），compose bind-mount 下 uvicorn 导入报 SyntaxError、API 容器 unhealthy（`/api/v1/ready` 超时）；已剥离 BOM 并重启容器恢复 200。仅此一个文件受影响。
- **验证：** `vue-tsc -b` 通过、Vite 生产构建通过（3820 modules，工作台独立 chunk 11.86kB）；浏览器两轮走查（本地 dev 5180，超管登录，全程零写操作）：第一轮 8 步 6 PASS/2 FAIL（上述两缺陷），修复后复测 5/5 PASS——应用树渲染+默认选中、工作台挂码弹窗 67 码加载 36 项勾选+预览出结果后取消、「权限编码」Tab 12 行 deerflow.* 码、应用管理「权限项」抽屉回归正常、角色管理同款弹窗回归正常、`/project-integration` 重定向生效。
- **未运行/未做：** 后端 185 项隔离套件（本轮零后端代码改动，仅 BOM 修复）；Wave 2–4（组织工作台/审计拆 Tab/收口）等待指令；`features/integration/` 源码按约定保留未删；375/768 窄屏复测沿用惯例留给用户。

## 2026-10-23 IAM P341 — 四级角色走查账号造数 + 浏览器四级走查 + capabilities 两处修复

- **造数（`manage.py seed-walkthrough` + `seed_greenfield.seed_walkthrough_accounts`，幂等）：** demo 租户下补建演示应用 demo-app 与 L2/L4 模板角色、业务码 `demo.document.read`（surface=business + requires_data_scope=true）、L4 的 self 数据范围，创建三个走查账号并绑定：`l2-admin@demo.example.com`→app.admin、`l3-admin@demo.example.com`→tenant.org_admin、`l4-member@demo.example.com`→app.member（统一密码 `Walkthrough#2026`，仅本地开发验收用）。注：邮箱不可用 `.test` TLD（pydantic email-validator 拒绝保留域）。
- **修复 1（L2 误判 no_access）：** `list_management_capabilities` 原用 `list_effective_roles(application_id=None)`——该语义只取租户/平台角色，L2 钉住应用的角色被整体排除，capabilities 空导致前端判 no_access。改为 `authorized_role_ids_statement` 取全量有效角色（直连 ∪ 活跃组，含应用角色）再按租户域/应用域分组。
- **修复 2（L4 误入租户控制台）：** 纯业务角色的 membership 会产生 codes 全空的租户条目，前端 `tenants.length>0` 即判 tenant 模式。改为只在租户码或任一应用码非空时收录条目（并过滤空 applications）——L4 正确落 no_access（规格 §4.4）。
- **浏览器四级走查（console 5175，全部通过）：** **L1** `admin@example.com` 平台模式 15 项菜单全可见（租户/应用/用户/邀请/组/组织/角色/权限目录/模拟/模型×2/主题/审计等）；**L3** 租户模式仅 5 项（组织/成员与数据范围/用户组/应用管理/应用角色与成员），无任何平台级菜单，应用角色页正确显示「当前只有读取权限」降级提示并能读到 L2/L4 模板（含业务码列）；**L2** 租户模式仅 2 项（应用管理/应用角色与成员），应用表有权限项/编辑/**轮换密钥**/停用全操作，无组织/成员/组菜单（L2/L3 互斥前端体现）；**L4** no_access——侧栏空菜单、顶栏「访问受限」+ 明确提示文案，深链 `/permissions` 被 App 壳纠正回受限页，未泄露任何管理内容。
- **API 判权证据（真实环境）：** L4 `GET /admin/permissions` 403；L3 `GET /admin/tenants` 403（无 iam.tenant.read）、`GET /admin/applications?tenant_id=` 200（有 application.read）；L3 `POST /applications/{id}/rotate-secret` **403** vs L2 **200**（互斥判权）；L4 `check(demo.document.read, include_data_scope=false)`（带 application_id）→ **allowed=true 且服务端强制返回 data_scope**（owner 约束绑 L4 sub + 租户匹配，绿场 breaking 核心行为）；不带 application_id 时 `no_matching_grant`（应用角色必须钉上下文，符合钉死语义）。
- **验证：** 隔离 PostgreSQL 随机库全量套件 **185 tests OK（18.2s，EXITCODE 0）**——两处 capabilities 修复后无回归。注：在 seed 一次性容器内跑套件须补齐 `-e JWT_SECRET -e OIDC_ISSUER` 并挂 `iam-oidc-signing-data` 卷，否则 14/6 个 ERROR 均为环境缺失（签名密钥/密钥配置），非代码回归。`vue-tsc` 无前端改动无需重跑（本轮仅改后端 services 与 manage/seed）。

## 2026-10-23 IAM P340 — 绿场重建：增强型分层 RBAC + 四级角色（方案 A 规格全量落地）

依据 `role-plan-a-tech-pack/role-iam-plan-a-greenfield.md`（方案 A 绿场重建终稿）全栈深度改造。

- **模型层：** `roles.kind`（platform/tenant/application，CheckConstraint + 按应用推导默认值）、`permissions.surface`（management/business）、`permissions.requires_data_scope`（默认 true，server_default）；config 新增 `ALLOW_BOOTSTRAP_EMAIL_BYPASS`（默认 **false**，仅灾备破窗且审计带 `break_glass=true`）。
- **全站唯一有效角色：** 新增 `services/effective_roles.py`——直连绑定 ∪ 活跃用户组角色，`list_effective_roles`/`user_is_platform_admin`；evaluate_access、OIDC 入场、`/auth/me/capabilities`、管理面判权共用同一实现。L1 `platform.super_admin` 覆盖 27 个 `iam.*` 管理码但默认无业务码；L2 `app.admin` 与 L3 `tenant.org_admin` 互不自动包含。
- **逐路由按码判权：** 新增 `services/rbac_guards.py`（`PLATFORM_MANAGEMENT_CODES`/`user_has_management_code`/`ensure_management_permission`/`list_management_capabilities`/`bump_membership_versions`）；admin 路由全部移除路由级 `platform_admin` 一刀切，逐路由挂 `iam.*` 码（tenant/overview/users/groups/invitations/audit/models/themes/model_usage/applications/access_control/organizations）；`admin/__init__.py` 只保留 `Depends(current_user)`。
- **解绑与版本失效：** 新增 `DELETE /admin/role-bindings`（404 若无绑定）；bind/unbind、组成员/组角色替换、角色停用（`platform.super_admin` 禁停用 422）、权限集替换、数据范围替换、权限停用均 bump 受影响 `membership.auth_version`。
- **L3 任命 L2 独立码：** `iam.app_role.assign` 仅可绑 key=`app.admin`；`tenant_admin_application_roles.py` 双层判权（manage→任意应用角色，assign→仅 app.admin）；用户组管理双端挂载（`/admin/groups` + `/tenant-admin/groups`）。
- **evaluate_access 强制 data_scope：** `requires_data_scope=true` 的业务码忽略 `include_data_scope=false`，缺数据范围策略拒绝（`data_scope_policy_missing`）；管理码不带 scope 直接放行。
- **能力接口：** 新增 `GET /auth/me/capabilities`（platform_admin/platform_codes/tenants[].codes/applications[].codes）；OIDC 入场改用有效角色（含组继承）。
- **前端：** `shared/services/capabilities.ts`（缓存/any-of 判定）；`navigation.ts` 全部菜单项标 `requiredPermissions`；`App.vue` consoleMode 判定改为单次 capabilities 拉取（platform/tenant/no_access），替换旧 overview 探测 + check-batch N+1；`router.ts` 深链守卫（无权限重定向首个可见页）；`GroupManagement.vue` 支持 `apiPrefix` 双端挂载。
- **绿场迁移与种子：** 旧 32 个迁移（0001~0032）归档至 `migrations/archive_pre_greenfield/`；单头迁移 `0001_greenfield_iam.py`（31 表全 schema，空库升级验证通过）；新增 `app/db/seed_greenfield.py`（27 管理码 + platform 租户 + L1 + 引导超管 + 可选 demo 租户/L2-L4 模板，全幂等）、`manage.py seed-greenfield`、compose `seed-greenfield` 服务（profile [seed]）、一键重置脚本 `scripts/greenfield-reset.ps1/.sh`（down -v → migrate → seed → up，UTF-8 BOM + LF）。
- **SDK 2.0.0（breaking）：** 双语言同步——业务码强制 data_scope 时 SDK 接受并校验（不再 502），subject 校验可选化（未传时跳过 owner 等值断言，租户/字段白名单仍强制）；`pyproject.toml`/`package.json` 版本 2.0.0；两份 README 补绿场 breaking 说明；TS 测试旧契约用例改写为绿场语义（新增 denied 决策带 scope 仍拒绝）。
- **测试：** 新增 `tests/greenfield_fixture.py`（分步 flush 规避无 relationship 裸 FK 的 UoW 字母序陷阱）与 `tests/test_greenfield_rbac.py`（G1 破窗默认关、L1 全码、L2/L3 互斥、unbind/bind bump、业务码强制 scope、组继承）；修复 12 个旧夹具适配与 2 个环境变量污染用例；删除 5 个旧迁移链专属测试。
- **验证：** 隔离 PostgreSQL 随机库全量套件 **185 tests OK（14.6s）**；Python SDK 核心套件 51 tests OK（authorization 15 + permission_sync 9 + deerflow 等；fastapi/oidc/token_vault 11 例因宿主机可选依赖未装跳过，与本次无关）；TS SDK `tsc --noEmit` 通过 + 15 tests pass；修复 `test_iam_permission_sync` 存量断言（catalog_namespace 自动推导）。**容器绿场重置（`scripts/greenfield-reset.ps1`）端到端通过：** down -v 删旧卷与 OIDC 密钥卷 → 单头迁移 0001_greenfield_iam → 种子（27 管理码 + 引导超管 `admin@example.com` 绑 L1 + demo 租户）→ api/console 启动三容器 healthy、`/api/v1/ready` 200（API 端口 8002/console 5175）；console 镜像内 `vue-tsc -b` + Vite 生产 build 顺带通过（3813 modules）；登录 + `GET /auth/me/capabilities` 返回 `platform_admin=true` + 27 码；逐路由挂码后 `GET /admin/permissions`（27 条，surface=management）与 `GET /admin/tenants`（platform+demo）L1 真实 200。首次跑曾因 `docker compose run` 附加参数**整体替换**服务 command 失败（entrypoint 收到裸 `--demo-tenant`），脚本已改为显式写全 `python manage.py seed-greenfield` 再追加开关。

## 2026-10-23 IAM P339 — 组件目录统一 + AdminListPage 整页封装

- **组件迁移：** `shared/components` 7 个通用组件（AdminPageHeader/AdminTableToolbar/AdminSearchField/AdminEmpty/AdminColorField/FeatureLoading/FeatureLoadError）整体迁至 `src/components`，20 个文件 53 处 import 路径批量更新；`AdminSearchField` 的 icons 相对路径修正为 `../app/icons`；空目录已删。
- **新增 AdminListPage（整页组件）：** 页头（eyebrow/title/subtitle + header-extra 插槽）+ 数据卡片（可选工具条 hint/控件/按钮插槽、errorText 错误提示、a-table、emoji 空态）一体；`card-top`/`card-bottom` 插槽承载页面特有内容（audit 筛选区与只读说明）；未声明的 a-table 属性经 `$attrs` 透传（如 `scroll-actions-on-mobile` class）；`@table-change` 转发分页事件。
- **新增筛选面板组件（用户反馈筛选丑）：** `AdminFilterPanel`（浅灰圆角容器 + 最小列宽自适应网格 + 底部右侧操作按钮区带分隔线）+ `AdminFilterField`（标签固定控件上方）；面板内 select/date-picker 统一占满单元格，深色主题半透明叠加与标签提亮；audit 展开筛选区接入（placeholder 同步精简，删除旧 grid 样式与两个断点 media query）。
- **图标与按钮细节（用户反馈对齐/图标丑）：** `SearchOutlined` path 重画为标准 lucide 形状（圆心 11,11 r=8 正圆 + 柄端精确落在圆边，原 path 圆偏左上且与柄断开）；audit 筛选开关按钮加 `flex items-center gap-2`——裸文本节点不触发 antd 的 `.anticon + span` 间距规则且 svg 基线对齐偏上，改 flex 后图标与文字垂直居中、间距均匀。
- **9 个单表页接入：** users/roles/permissions/tenants/applications/organizations/groups/invitations/audit 模板收敛为 `AdminListPage` 声明式用法，页面只保留数据逻辑与弹窗；同步清理死 CSS（`.permission-error`/`.role-error`/`.invitation-error`/`.audit-error`/`.audit-toolbar-summary`/`.permission-toolbar`）。多表格工作台（ModelGovernance/LoginTheme/ApplicationRole/TenantAccess）与 Overview 保持原结构，仅迁移 import。
- **验证：** 容器内 `vue-tsc -b` exit 0；浏览器走查 9 页全部渲染正常（页头/header-extra/工具条/bodyCell/空态）、内容区全部零滚动（双滚动条保持消除）；audit 展开筛选截图确认面板层次/标签对齐/操作按钮区成型，展开后 fit 收敛表格 body 至 219px 内建滚动、内容区零溢出；控制台仅剩 P335 已知 Menu inlineCollapsed 警告。
- **未运行：** Vite 生产构建、后端测试、375/768 窄屏复测（沿用 P311 约定由用户复测）。

## 2026-10-23 IAM P338 — 消除内容区与表格并存的双纵向滚动条

- **方案：** 全部 16 个页面级表格保留 `scroll.y` 内建纵向滚动；`App.vue` 新增 `fitTableBodies()` 动态高度拟合——以内容区底边为基准反推每个 `.ant-table-body` 的 `maxHeight`（预留分页 + 页脚安全间距 112px，保底 120px），滚动位置无关；`MutationObserver(childList+subtree)` + 80ms 防抖捕捉内容变化（`.ant-layout-content` 为固定高度 flex 容器，ResizeObserver 不触发），窗口 resize 与路由切换（`syncRoutePage` → `refreshTableFit`）触发重算；估算偏差用收敛轮兜底（仍溢出则均摊扣除）。
- **压缩固定高度（用户复测仍见双滚动条后二轮修正）：** audit 筛选表单默认折叠（开关行替代）；permissions 页删除与副标题重复的 info alert、副标题精简一行、namespace 绑定说明并入工具条 hint 并精简；roles 页长说明并入工具条 `:hint`；`AdminTableToolbar` 与表格间距 `mb-4`→`mb-3`（全局）；删除无引用死 CSS（style.css `.scope-note`、PermissionCatalog.vue `.permission-note`/`.permission-hint`）。
- **验证：** 容器内 `vue-tsc -b` exit 0（三轮）；834×738 自动化视口实测 permissions/audit/roles/users/tenants 内容区全部零滚动（contentSH=contentCH=674）、滚动只发生在表格 body 内（permissions/roles 保底 120px，users/tenants 表格自适应收缩）；/permissions 截图确认右侧内容区滚动条消失、布局无破版。
- **未运行：** Vite 生产构建、后端测试、375/768 窄屏复测（沿用 P311 约定由用户复测）。

## 2026-10-23 IAM P337 — 全站表格统一使用 antd 内建滚动条

- **盘点：** 19 个 `a-table` 实例逐一核对，18 个已配置 `scroll.x` 内建横向滚动（滚动条位于表格行区与分页之间、页面级零溢出）；唯一缺失为登录主题页「主题版本历史」表。
- **补齐：** `LoginThemeManagement` 主题版本表补 `:scroll="{ x: 480 }"`；`style.css` 的 `.data-card .ant-table-wrapper` 外层 `overflow-x: auto` 保留作为未配置 scroll.x 时的安全网（配置后自动失效）。
- **验证：** 浏览器实测 users/audit/roles/tenants/models 表格滚动区均为 `.ant-table-content` 且 `overflow-x: auto`，页面级无横滚；容器内 `vue-tsc -b` exit 0。
- **未运行：** Vite 生产构建、后端测试。

## 2026-10-23 IAM P336 — 顶栏溢出修复 + 全局细节拉齐（表头/页脚/加载屏/滚动条）

- **顶栏溢出修复（用户截图实锤）：** antdv Layout header 默认 `line-height:64px` 经 css-in-js 后注入、压过外层 `leading-none`，`AppBreadcrumb` 徽章被 flex 块状化后撑到 72px 高溢出顶栏。修复：组件根自带 `leading-none`、徽章/标题显式 `leading-[1.2]/[1.4]`，徽章高度恢复 25px。
- **antdv 4.2.6 token 缺口兜底（style.css 高特异性覆盖）：** ① `Layout.headerPadding` 不生效，顶栏默认 50px 内边距收敛为 16px（≤575px 12px）；② `Table.headerBg/rowHoverBg` 不生效，表头改 `#f8f9fc`（深色 `rgba(255,255,255,.04)`）、行悬浮带极光紫 `rgba(124,92,255,.045/.1)`。
- **新增全局细节：** 页脚边框/文字色改由根 `data-theme` 驱动（去掉跟随 OS 的 `dark:` 类）；全局细滚动条 slate 色系 + 深色暗轨；`FeatureLoading` 极光三圆点错相跳动加载屏（替代纯 `a-spin`）。
- **验证：** 容器内 `vue-tsc -b` exit 0；浏览器实测 chip 25px、header 内边距 16px、表头 `#f8f9fc`；6 页抽查无溢出无错误，控制台 Vue 告警 0。
- **未运行：** Vite 生产构建、后端测试、375/768 窄屏复测（P311 约定由用户复测）。

## 2026-10-23 IAM P335 — 管理台「暗黑轻奢·极光渐变」深度改造 + UI 走查问题修复

- **设计体系：** 主色 `#756df2`→`#7c5cff`（极光紫，全站 8 处默认值统一）；侧栏近黑三段渐变 `#0b0a16→#1c1240` + 紫/品红光斑；顶栏玻璃拟态（浅色 `rgba(255,255,255,.78)`/深色 `rgba(15,16,32,.96)` + blur）；登录页暗夜极光三光晕 + 白玻璃卡 + 渐变主按钮；圆角 10→12；图表色板换极光系。
- **新增组件（按用户要求封装）：** `AppBreadcrumb`（顶栏渐变模式徽章+页面标题，替代 antd 面包屑）、`AuroraGlow`（侧栏/Hero 光斑装饰）、`AdminEmpty`（emoji+文案空状态，替换全部 24 处 `a-empty`，按业务域配 🏢🎭🔐✉️🤖 等 18 种图形）、`OverviewStatCard`（渐变数字指标卡）。
- **壳层：** 侧栏改 antd Menu `theme="dark"` + ConfigProvider `dark*` token（高饱和选中态、折叠弹层深色）；工作台 Hero 换深空→紫品红对角渐变+细网格；能力卡/工具条/页头 eyebrow 渐变竖条统一；深色模式通过根 `data-theme` 适配工具条与输入控件。
- **UI 走查问题修复：** ① P329 遗留架构 bug——App 根组件 `renderCache` 首帧缓存组件解析 miss，导致后注册的 `a-breadcrumb`/`a-space`/`a-avatar` 永久解析失败（控制台 Vue warn 实锤）；`Avatar`/`Space` 提前到 `installPublicUi` 公开注册。② `NullShell` template 字符串触发运行时编译告警，改 `render: () => null`。③ 顶栏面包屑组件化后告警清零。
- **验证：** 容器内 `vue-tsc -b` 两轮 exit 0；浏览器 15 路由全部无页级横滚、无错误弹窗；控制台 Vue 告警清零（仅剩登出/刷新时 ERR_ABORTED 请求中断，属正常）；浅/深主题、登录页、新建用户弹窗截图走查通过；HMR 实时生效，镜像未重建。
- **未运行：** Vite 生产构建、后端测试、375/768 窄屏手动复测（工具无视口 resize，沿用 P311 约定由用户复测）。

## 2026-10-23 IAM P334 — Docker 重装后开发环境重建

- **事件：** Docker Desktop 重装（engine 29.6.2）导致镜像、容器与卷全部丢失，含数据库卷 `iam-postgres-data` 与 OIDC 密钥卷 `iam-oidc-signing-data`；`D:\backup\iam-postgres\` 两份 0031/0021 备份与 `.sha256` 完好，经确认未采用（走全新空库方案）。
- **重建：** `docker compose build api console`（镜像内 `vue-tsc -b` + Vite build 通过）+ `postgres:16-alpine` 拉取；`--profile migrate run` 全新库一次性迁至 `0032`；`--profile bootstrap run` 重建管理员 `admin@example.com`（密码取 `.env` `IAM_ADMIN_PASSWORD`，首次 bootstrap 生效）。
- **环境注意：** 用全路径调用 docker 会报 `docker-credential-desktop not found`，需先把 `C:\Users\刘少华\AppData\Local\Programs\DockerDesktop\resources\bin` 加入 PATH。
- **数据损失：** 2026-10-14 备份之后的业务数据（P322 crud-demo 联调资产、A04 夹具证据等）不可恢复；OIDC 签名密钥为新生成，历史 token/会话全部失效。
- **验证：** 三容器 healthy、`/api/v1/ready` 200；`alembic` head=0032（重复迁移无新升级）。浏览器登录走查由 P335 完成；存在一个手动 `docker run` 的游离 console 容器（`vigorous_lamarr`）未处理，不影响 compose 三件套。

## 2026-10-22 IAM P333 — 应用与权限命名空间层级

- **数据模型：** 迁移 `0032_application_permission_namespace`；`applications.permission_namespace`、`permissions.catalog_namespace`；归属规则 `code == namespace` 或 `code` 以 `namespace.` 开头。
- **后端：** `permission_namespace` 服务模块；`GET/POST /admin/applications/{id}/permissions`；目录/应用角色 API 按命名空间过滤与 grant 校验；创建应用时可登记/推导命名空间。
- **SDK：** Python/TS 权限清单同步 `POST` 附带 `catalog_namespace`。
- **前端：** 应用管理「权限项」抽屉；权限目录页改为平台全览 + 命名空间筛选。
- **验证：** 容器内 `tests.test_permission_namespace` 6 OK；`docker compose build console` 见进度文档；浏览器走查未在本轮复跑；开发库迁移未在本轮执行。

## 2026-10-22 IAM P332 — Console 镜像 echarts 与 AdminTableToolbar 类型修复

- **修复：** `AdminTableToolbar.vue` 改用模板 `$slots.default`，消除 `useSlots()` 在 `vue-tsc -b` 下的 TS2554，解除 Docker 前端镜像构建阻塞。
- **运维：** `docker compose build console` 成功（含 `echarts@5.6.0` 安装、`vue-tsc -b` + Vite 生产构建）；`docker compose up -d --force-recreate console` 已执行。
- **验证：** 镜像内构建通过；浏览器 `/overview` 未在本轮复跑。

## 2026-10-22 IAM P331 — 工作台 ECharts 与筛选条搜索样式

- **总览页：** `OverviewPage.vue` 渐变 Hero、六指标卡（可跳转对应模块）、管理能力卡片网格；`App.vue` 向总览传入 `primaryColor`。
- **图表：** 新增 `OverviewDashboardCharts.vue`，基于 `AdminOverview` 快照渲染环形图与横向柱状图（`echarts/core` 按需注册）。
- **搜索：** 新增 `AdminSearchField`（前缀放大镜、无右侧搜索按钮）；用户/角色/权限/成员等页替换 `a-input-search`。筛选条浅紫渐变底、圆角与聚焦环（`style.css`）。
- **工具条：** `AdminTableToolbar` 无筛选控件时不留大块空白，hint 与刷新靠右对齐。
- **布局：** 宽表页（如应用管理）`section`/`.data-card` 增加 `min-width:0` 与卡片内横滚，避免整页被表格撑出视口。
- **依赖：** `frontend/package.json` 增加 `echarts@^5.6.0`。
- **验证：** `vue-tsc -b` 通过；浏览器未在本轮复跑。Vite 生产构建未跑。后端测试未运行。`pnpm-lock.yaml` 未更新（宿主机 pnpm/corepack 故障）。

## 2026-10-22 IAM P330 — antdv 全站换皮

- **壳层补修：** 登录后 `h-screen` 锁视口，侧栏固定、菜单过长只在侧栏内滚；右侧 `layout-content` 单独纵向滚动。去掉顶栏多余 `a-avatar`。宽表仅在 `ant-table-wrapper` 横滚。
- **筛选条：** 新增 `AdminTableToolbar`（浅灰底+边框），租户/用户/角色/邀请等表页统一搜索与刷新布局；去掉 `enter-button="搜索"` 大按钮样式。
- **主题：** `App.vue` ConfigProvider 补 Layout/Menu/Card token 与内容区底色；`a-layout-header` 默认 `#001529` 盖不住 token，浅/深色用内联底色与字色。
- **向导：** `ProjectIntegrationPage.vue` 去掉重复 Progress；选中方案卡浅紫底+主色边；底栏与内容同宽。`IntegrationCodeBlock.vue` 代码块深底。
- **布局：** 侧栏旁内容列 `min-width:0`；`style.css` 约束管理页宽表只在卡片内横滚，标题区「新建」不再被挤出视口。
- **验证：** `vue-tsc -b` 通过；登录后全平台路由 + 登录页 + 375 drawer overflow 0。Vite 生产构建未跑。后端测试未运行。
- **边界：** 无 API、无迁移；不回退 P329；不把 `@ant-design/icons-vue` 整包别名到 `icons.ts`。

## 2026-10-22 IAM P329 — 管理台全面改用 Ant Design Vue

- **壳层：** `App.vue` / `AppSidebar.vue` 改为 `a-layout`、`a-menu`、`a-breadcrumb`、窄屏 `a-drawer`；密度走 ConfigProvider `componentSize`。`FeatureLoading`→`a-spin`，`FeatureLoadError`→`a-result`。
- **页面：** 共享 `AdminPageHeader`；总览 `a-statistic`/`a-card`；接入向导 antd 控件（P328 示例保留）；审计 `a-date-picker`；登录页去装饰轨道、readiness `a-alert`。主色 `AdminColorField`（4.2.6 无 ColorPicker）。
- **样式：** `style.css` 去掉 sidebar/topbar/welcome-card 等壳层 class；保留 OIDC 变量、主题预览、≤575 `.ant-modal`、`prefers-reduced-motion`。
- **依赖：** `package.json` 增加 `@ant-design/icons-vue` 与 `dayjs`；侧栏运行时仍用 `src/app/icons.ts`。去掉会打断 antd `/es/icons` 子路径的 Vite 别名。
- **验证：** `vue-tsc -b` 通过；登录后壳层折叠、总览、向导 A/B/下一步/跳步、打开应用/权限/角色、浅/深色、375 drawer overflow 0。Vite 生产构建未跑。后端测试未运行。
- **边界：** 无 API、无迁移、无第二套 UI 库；登录主题预览画布与 OIDC CSS 变量保留。`pnpm-lock.yaml` 未更新（宿主机 pnpm/npm 安装器故障）。

## 2026-10-22 IAM P328 — 接入页交互向导与业务改造示例

- **前端：** `ProjectIntegrationPage.vue` 改为选方案 + 进度条 + 手风琴；抽出 `integrationGuide.ts` 与 `IntegrationCodeBlock.vue`。页内示例覆盖业务 .env、Python/Node 挂载、Vue 登录/按钮、login/check curl。侧栏图标走 `src/app/icons.ts`；`vite.config.ts` 把 `@ant-design/icons-vue` 别名到该文件（控制台镜像未装此包，勿在宿主机对该目录 `npm i`）。P328 后续去掉本页 antd Card/Steps/Collapse，只保留当前阶段步骤，避免标题与方案卡挤成一排、当前步被收起。
- **验证：** `vue-tsc -b` 通过；浏览器下一步、A/B、跳转 `/applications` 与 `/roles`、375 overflow 0。后端测试未运行。
- **边界：** 无 API、无迁移；不自动创建租户/应用；完整可运行对照仍是 `examples/iam-crud-fastapi`。

## 2026-10-22 IAM P327 — 新项目接入页双路径指南

- **前端：** 重写 `frontend/src/features/integration/ProjectIntegrationPage.vue`。公共准备 5 步（跳转租户/应用/权限/角色/邀请）+ 方案 A 平台托管登录（OIDC）+ 方案 B 平台 HTTP 接口（login / check / check-batch）；可复制示例。旧五步卡片、DeerFlow 试点长文、SDK 失败关闭表删除。步骤卡片 `min-w-0` + `break-words`，375 无页级横滚。
- **验证：** `vue-tsc -b` 通过；浏览器 A/B 切换、页内跳转 `/tenants` 与 `/permissions`、375 overflow 0。自动化剪贴板未切到「已复制」。后端测试未运行。
- **文档：** 技术架构第 3 节指向管理台新页；进度/验收记录同步。
- **边界：** 无 API、无迁移。

## 2026-10-22 IAM P326 — 邮箱登录/找回/管理台注册完善

- **后端：** 新增 `GET /api/v1/auth/public-capabilities`（SMTP 找回是否可用、管理台绑定的 ToC 注册 client）；配置项 `IAM_CONSOLE_REGISTRATION_CLIENT_ID`。
- **前端：** `AuthEntry` 统一「邮箱地址」登录文案；保留域校验；忘记密码预填邮箱与 SMTP 未配置提示；管理台「邮箱注册」入口（绑定 client 时）。
- **脚本：** `scripts/provision_dev_console_registration.py` 幂等创建 `iam-dev-console-reg` 试点应用。
- **验证：** 容器 unittest 6/6；`vue-tsc -b` 通过；`public-capabilities` 返回 `console_registration.available=true`（本地 dev）。

## 2026-10-22 IAM P325 — 163 SMTP 阶段一接入

- **配置与示例：** [`.env.compose.example`](.env.compose.example) 163 SMTP 示例脱敏（授权码占位、邮箱示例泛化）；真实授权码仅写入本地 `.env`。
- **运行验证：** 重建 API 容器后 163 **465+SSL** 试发与忘记密码申请接口 200；容器内邮件/密码重置单元测试 4/4；邀请创建 `delivery=email_sent`（验收时开启 `IAM_INVITATION_EMAIL_ENABLED`）。
- **文档：** [验收记录](docs/验收记录.md) P325、[快速启动指南](docs/快速启动指南.md) SMTP 小节、[项目总览与进度](docs/项目总览与进度.md) P325 任务行。

## 2026-10-22 IAM P324 — P302 浏览器 Network 走查

- **走查：** 平台管理员登录 5175；路由 **租户 → 角色 → 工作台** 切换时，页面内 `fetch` 探针未再出现 `/admin/overview|tenants|applications|roles` 重复请求。
- **结论：** P323 优化在浏览器实测侧成立；P302 任务可标记完成（375 弹窗仍归 P311 用户复测）。

## 2026-10-22 IAM P323 — P302 管理台重复请求与 ready 轮询

- **App 壳：** 平台字典 `loadDictionaries` 单次预拉（`dictionariesReady` + `platformCatalogGeneration`）；路由同步仅在进入工作台时调 `loadPage`；概览已有数据时跳过重复 `/admin/overview`；退出登录清空壳层缓存。
- **子页复用：** `TenantManagement` / `ApplicationManagement` / `RoleManagement` 在平台模式下优先复用壳层 tenants/applications/roles，避免路由激活重复打同名 admin 列表接口。
- **Ready 探针：** 服务正常时间隔 120s、异常 30s；标签页隐藏时暂停请求；回到前台立即补一次探测。
- **模板：** 管理台 content 区移除错误的 `v-if`/`v-else-if` 链（消除 Vue 编译 warn）；工作台改为与其他页一致的 `visitedPages` + `v-show`。
- **验证：** `frontend` 下 `vue-tsc -b` 通过；浏览器 Network 复测未运行。

## 2026-10-17 IAM — 取消仓库绑定（用户指令）

- **操作：** 用户要求取消仓库绑定；删除 `D:\project\role\.git`，目录不再是 git 仓库。删除前核实本地 main（3 提交：`bea2e51` → `25a2968` → `0d7452c` cursor改造）与 GitHub 远程 `https://github.com/shaohua-code/role.git` **完全同步**（`main...origin/main` 无领先/落后），完整历史在远程保留；无 stash。38 个未提交文件（含 P312–P322 全部成果）仅保留在工作区，未受影响。
- **影响：** 工作区从此无版本保护；如需恢复：`git init` + `git remote add origin` + `git fetch`（工作区与远程差异大，恢复前须与用户确认分支策略）。原「勿 checkout/restore/reset」规则（2026-10-14 回滚事件）随绑定取消失效。
- **文档：** 进度文件「Git 事实」段、第 1 节规则、接手指令、第 7 节阻塞表、第 8 节更新规则共 5 处同步为无 git 绑定状态。

## 2026-10-17 IAM P322 — Real-IAM E2E of SDK five components + P302/P303 browser walkthrough

- **新增 `examples/iam-crud-fastapi/provision.py`（幂等联调准备）：** 平台管理员登录（HS256 management token，密码只进进程内存）→ 选租户 → 登记 application `crud-demo` → **SDK 清单同步工具真实登记** `demo.document.*` 三码 → 建角色 `crud-demo` 授权 + 配置 **self 数据范围**（`PUT /admin/roles/{id}/data-scopes`，owner_only 路由必需）→ 创建测试用户（一步设密码绑定角色）。凭证仅落 `.env.local`（gitignore 覆盖）。
- **新增 `examples/iam-crud-fastapi/verify_flow.py`（无头验收，9 项断言全 PASS）：** 临时受信（结束自动恢复）→ crud-demo 登录 IAM → OIDC 静默授权 + SDK callback 建会话 → `check_batch` 三码 allowed → 创建 201 → owner 列表/单查 200 → 删除 204 → 复查 404 → 无会话 401。浏览器侧并行验证：consent scope 展示正确、`/auth/me` 无 tokens、owner 路由 200。
- **真实 fail closed 负路径（意外但完整）：** ①无授权用户 OIDC → IAM `access_denied` 回调、SDK 403 不建会话；②角色数据范围默认租户级时 owner_only 全 403（适配层强校验生效），配置 self 后恢复；③登录 host 与 issuer host 不一致（127.0.0.1 vs localhost）cookie 不随 authorize 发送。三点沉淀进 README「真实联调」节。
- **P302/P303 浏览器走查：** P303 接入页渲染完整（截图存档）；登录后路由保持/16 页导航/应用-角色-权限数据链路正常；受限用户登录真实触发 P312 `loadTenantConsole` 的 **`/authorization/check-batch` 单次批量调用**（network 证据）。发现并修复接入页「尚未交付」过时文案（对齐 P318–P321 现状；`node node_modules\vue-tsc\bin\vue-tsc.js --b` 通过——pnpm 启动器 bug 用 P306 绕过方式）。P302 遗留实锤未修（保持进行中）：路由切换重复拉 4 字典接口、ready 高频轮询、Vue 模板编译 warn。
- **边界：** 无迁移无 schema 变更（联调全为业务数据写入）；crud-demo 资产保留可复用；uvicorn 走查后已停止；管理员角色未改动；DeerFlow 未涉及。
- 未做：P302 的轮询/重复请求优化本身（新发现的修复项）；CRUD 示例首页路由（404 属预期已记录）。

## 2026-10-17 IAM P321 — Permission-catalog manifest sync (F02, dual-language)

- **新增 Python `sdk/python/iam_permission_sync.py`（P321，标准库零依赖）与 TypeScript `sdk/typescript/src/permission-sync.ts`（经 `src/index.ts` 导出，零运行时依赖）：** 双语言语义对称的权限清单同步工具——`IamAdminClient` 覆盖 `GET/POST /api/v1/admin/permissions`（管理面首批 SDK 组件），`sync_permission_manifest`/`syncPermissionManifest` 把应用权限清单（`{code, resource_type, scope, description?}`）幂等同步到 IAM 权限目录。
- **fail closed 语义：** 清单在任何网络请求前本地预检（code 3–180 / resource_type 1–100 / scope 1–80 / description ≤500，与后端 `PermissionCreate` 对齐；重复 code 拒绝，不允许静默去重掩盖清单错误），非法输入本地抛错零网络调用；目录不可达（无法建立索引）直接抛错（503），绝不盲发创建。字段约束调研自 `backend/app/schemas/access_control.py` 与 `backend/app/api/v1/admin/access_control.py`（无批量端点，code 全局唯一 409 非幂等）。
- **幂等语义：** 先拉目录建 code 索引 → 只创建缺失项；已存在条目一律跳过且**不修改其描述/状态**（状态变更走管理台 `PATCH /admin/permissions/{id}/status`）；创建遇 409（并发窗口）重拉目录确认——已存在记 skipped、仍缺失保守记 failed 待人工核对；单条失败（含网络抖动、其他 HTTP 拒绝）逐条入报告不中断整批；报告 `created/skipped/failed`，failed 非空重跑安全。工具不做角色授予（grant 属管理台/角色管理语义）。认证要求平台管理 access JWT（HS256 `management_access` token；终端用户 OIDC token 被 IAM 403 拒绝），Bearer 头风格与授权 client 一致。
- **验证：** Python `test_iam_permission_sync.py` 契约测试 **14 例**（Bearer/URL 规范化、POST body、状态码保留、503/502 映射、空目录全建、已存在全跳零创建、部分创建、409 重拉两分支、单条失败不中断、目录不可达零创建、非法清单零网络、缺 token 本地拒绝）——SDK Python 全量 **85 tests OK**（71+14）；TS `test/permission-sync.test.mjs` **13 例**——TS SDK 全量 **48 pass / 0 fail**（48=authorization 14+express 9+express-auth 9+oidc 3+permission-sync 13；Node 22.20 strip-types）；`tsc -p tsconfig.json --noEmit` 通过（修复 1 处 unknown→Record 断言）。
- **文档：** 两份 SDK README 补权限同步节（语义/示例/测试命令）；技术架构第 3 节标题与接入表（清单同步已交付）、正文（批量登记已交付）与 4.3 节 SDK 表补行。
- 未做：真实 IAM 管理面联调（mock 契约测试；端点行为由后端既有测试覆盖）；管理 JWT 的签发/保管方案属业务运维；CRUD 模板 README 的 Express 映射表未含新组件（后续如做 Express 侧示例时一并补）。

## 2026-10-17 IAM P320 — FastAPI CRUD template example (F02)

- **新增 `examples/iam-crud-fastapi/`（P320）：** 把 F02 SDK 组件族串成完整接入路径的最小模板项目——`mount_oidc_auth`（P318 登录路由）+ `IAMFastAPI`（P316 授权依赖注入）+ `check_batch`（P315 展示快照）+ 内存文档仓储（owner 行级过滤）。`create_app()` 工厂支持注入 mock client 供测试；生产走 `IAM_ISSUER`/`IAM_CLIENT_ID`/`IAM_CLIENT_SECRET`/`IAM_REDIRECT_URI`/`IAM_API_URL`/`IAM_APPLICATION_ID` 环境变量构造。
- **示例路由：** `/me/permissions`（`check_batch` 一次判定三个 `demo.document.*` 权限码快照，仅用于前端菜单/按钮渲染）；`POST /documents`（动作权限 + owner 记 subject）；`GET /documents`、`GET /documents/{id}`、`DELETE /documents/{id}`（`owner_only=True` + `local_user_id` 过滤，越权一律 404 不泄露存在性）。
- **端到端契约测试 `test_app.py` 3 例全绿：** ①登录→快照（断言一次 `check_batch` 调用且单码 `check` 未被调用）→创建（owner=alice）→alice 列表/直取→bob 列表空+直取 404→alice 删除 204→bob 删除 404（真实 IAM 按请求者返回本人 scope，数据过滤表现为 404）；②无会话访问全部受保护路由 401；③IAM 网络故障映射 503。`raise_server_exceptions=False` 最终形态。
- **验证：** 示例测试 3/3 OK（DeerFlow venv Python + starlette TestClient）；SDK Python 全量回归 **71 tests OK** 不受影响。
- **新增 `examples/iam-crud-fastapi/README.md`：** 运行前提（本地 IAM compose + 登记 application + 显式授予 `demo.document.*`）、环境变量表、端点表、fail closed 设计说明、生产替换点（SessionStore 持久化/本地身份映射/令牌刷新/CSRF 与日志脱敏）、Express（Node）组件映射表（`mountOidcAuth`↔`mount_oidc_auth`、`createIamExpress`↔`IAMFastAPI`、`checkBatch`↔`check_batch`）。
- **文档：** 技术架构第 3 节标题更新（CRUD 示例已交付）、第 3 节正文补示例位置、4.3 节 SDK 表补示例行；进度文档 F02 行与索引同步。
- 未做：真实 IAM 联调（示例均为 mock 契约验证）；Express 侧 CRUD 示例（可选）；权限清单同步工具。

## 2026-10-17 IAM P319 — Express OIDC login-route plugin (F02, zero-dependency)

- **新增 `sdk/typescript/src/express-auth.ts`（P319，经 `src/index.ts` 导出）：** `mountOidcAuth(app, { oidcClient, sessionStore, routeOptions })` 一次性挂载 `login`/`callback`/`logout`/`me`（路径可配，默认 `/auth/*`），与 Python `mount_oidc_auth`（P318）语义对称。`IAMAuthSessionStore`（put/load/take/delete）由业务方实现，`InMemoryIamSessionStore`（TTL + 惰性过期）仅开发测试。
- **会话安全语义：** attempt 与令牌只存服务端；浏览器仅持一次性 HttpOnly attempt Cookie + 会话 Cookie（HttpOnly + SameSite=lax，`cookieSecure`/`cookieDomain` 可配）；Cookie 由适配器直接解析 `Cookie` 头（**不依赖 cookie-parser**）；attempt 原子消费（重放 403）；callback 缺 Cookie/过期 403，`OIDCProtocolError` 403 不透出细节（鸭子判别 `error.name`，避免 src 内跨文件运行时 import）；`/auth/me` 只返回 `subject`/`tenantId`/`profile`；logout best-effort 撤销两 token + 原子删会话（无会话幂等）。
- **零依赖实现：** Request/Response/App 均为结构类型（兼容 Express 4/5，不需 express 包）；随机 ID 用 Web Crypto `crypto.getRandomValues` + `btoa` base64url（不用 `node:crypto`/`Buffer`，与包内无 Node 类型依赖一致）。
- **验证：** 新增 `test/express-auth.test.mjs` 契约测试 9 例（login 302+HttpOnly+attempt 入库、callback 换会话+完整回调 URL 传递+清 attempt、重放 403、缺 Cookie fail closed、协议失败 403 不泄露、me 摘要无 tokens、me 无会话 401、logout 撤销+清理+再访 401、logout 幂等）——TS SDK 全量 **35 pass / 0 fail**（authorization 14 + express 9 + express-auth 9 + oidc 3；Node 22.20 strip-types）；`tsc -p tsconfig.json --noEmit` 通过。
- **文档：** TS README 补插件段与示例、测试命令加 `express-auth.test.mjs`；技术架构第 3 节（登录路由插件双语言已交付）与 4.3 节 SDK 表补 `mountOidcAuth` 行。
- 未做：真实 IAM OIDC 联调；CSRF/代理日志脱敏仍属业务方；CRUD 模板项目、权限清单同步工具。

## 2026-10-17 IAM P318 — FastAPI OIDC login-route plugin (F02)

- **新增 `sdk/python/iam_fastapi_auth.py`（P318）：** `mount_oidc_auth(app, oidc_client=..., session_store=..., options=OidcRouteOptions(...))` 一次性挂载 `login`/`callback`/`logout`/`me` 四条路由（路径可配，默认 `/auth/*`），消除业务方重复编写 OIDC RP 流程。
- **会话安全语义：** 登录 attempt 与身份令牌只保存在业务方实现的 `SessionStore`（`put/load/take/delete` 协议；`InMemorySessionStore` 仅开发测试，带 TTL 与过期惰性清理）；浏览器只持一次性 HttpOnly attempt Cookie 与会话 Cookie（HttpOnly + SameSite=Lax，`cookie_secure`/`cookie_domain` 可配）；attempt 经 `take` 原子消费（重放 403）；callback 缺 Cookie/attempt 过期 403，Provider 拒绝（OIDCProtocolError）映射 403 且不透出细节；`/auth/me` 只返回 subject/tenant/profile、绝不返回 tokens；logout best-effort 撤销 access/refresh token（失败不阻断本地登出）并原子删除服务端会话。
- **打包：** `pyproject.toml` `py-modules` 加 `iam_fastapi_auth`（依赖 `[fastapi]`+`[oidc]` extra）。
- **验证：** 新增 `test_iam_fastapi_auth.py` 契约测试 9 例（login 302+HttpOnly Cookie+attempt 入库、callback 换会话并清 attempt、attempt 一次性重放 403、缺 Cookie fail closed、协议失败 403 不泄露细节、me 返回摘要无 tokens、me 无会话 401、logout 撤销+清理、logout 幂等）——SDK Python 侧合计 **34 tests OK**（auth 9 + fastapi 10 + authorization 15；TestClient + Mock OIDC client，无网络）。
- **文档：** 技术架构第 3 节（边界表、接入流程第 3 步、待开发清单移除 Python 路由挂载）与 4.3 节 SDK 表补 `mount_oidc_auth`；python README 补插件段与示例。
- 设计取舍：CSRF 防护与代理日志脱敏仍由业务方负责（延续 SDK 边界声明）；Node 侧路由挂载、CRUD 模板项目未做。
- 未做：真实 IAM OIDC 联调（mock 契约测试；`complete_login` 内部 RS256/PKCE 校验已由 `test_iam_oidc.py` 覆盖）。

## 2026-10-17 IAM P317 — Express thin authorization adapter (F02, zero-dependency)

- **新增 `sdk/typescript/src/express.ts`（P317，经 `src/index.ts` 导出）：** `createIamExpress(options)` 暴露 Express 中间件——`requirePermission(alias, { ownerOnly })` 与 `currentUser()`，语义与 Python `iam_fastapi`（P316）对称：别名必须登记在 `permissionMap`（未登记在创建中间件时抛错）；`ownerOnly` 要求 data scope 每个 `any_of` 分支都是绑定已验签 subject 的 owner 约束（tenant/organizations 分支整体 403）+ `localUserIdResolver` 解析本地用户主键（空/异常 503）；IAM 403/503 保留语义、其余契约错误归一 502；会话由业务方 `loadSession` 从本地已验签会话构建（缺失抛带 `statusCode` 的错误，原样转发业务方错误处理）。成功时挂 `req.iamUser`（ownerOnly 含 `localUserId`）与 `req.iamDecision`。
- **零依赖实现：** 仅用结构类型描述 Request/Response（`{headers}` / `{status().json()}`），兼容 Express 4/5，不需要 express 包；跨文件引用改用 **type-only import**（Node strip-types 擦除、tsc 保留类型检查——首个 src 内跨文件 import 的兼容处理）。
- **验证：** 新增 `test/express.test.mjs` 契约测试 9 例（别名映射与 require 参数、403/503/502 错误映射、未登记别名创建期抛错、ownerOnly 本地主键解析、放宽 scope 403、resolver 缺失创建期抛错、会话错误转发业务错误处理、currentUser 不触 IAM）——TS SDK 全量 **26 pass / 0 fail**（authorization 14 + express 9 + oidc 3；Node 22.20 strip-types）；`tsc -p tsconfig.json --noEmit` 通过。
- **文档：** TS README 补 Express 适配器段与示例、测试命令加 `express.test.mjs`；技术架构第 3 节实现边界更新（Express 适配器已交付）并从待开发清单移除 Node 适配器；4.3 节 SDK 能力表补 `createIamExpress` 行。
- 未做：真实 IAM 联调与 CRUD 模板项目；路由自动挂载插件（login/callback/logout）、权限清单同步工具。

## 2026-10-17 IAM P316 — FastAPI thin authorization adapter (F02)

- **新增 `sdk/python/iam_fastapi.py`（`[fastapi]` extra）：** `IAMFastAPI` 把授权客户端暴露为 FastAPI 依赖——`require_permission(alias, owner_only=)` 返回依赖函数（配合 `Depends` 使用），`current_user()` 返回可信上下文依赖。`IAMUserContext` 由业务方 `session_dependency` 从**本地已验签** OIDC 会话构建（缺失抛 401）；适配层不验签 token、不接受请求参数中的身份。
- **安全语义：** 权限别名必须在 `permission_map` 登记为稳定 code，未登记别名在构建依赖时即抛 `LookupError`（fail closed，不猜测映射）；`owner_only=True` 走 `check(include_data_scope=True, subject_id=...)` 并要求每个 `any_of` 分支都是绑定已验签 subject 的 owner 约束（出现 tenant/organizations 分支整体 403，any_of 为 OR 语义）；经 `local_user_id_resolver` 解析产品本地主键（未配置 resolver 在构造期即拒绝；解析为空视为映射服务故障 503）。错误映射：403/503 保留语义，其余契约错误归一 502；同步 client 调用由 FastAPI 调度到线程池。
- **打包：** `pyproject.toml` 增 `fastapi = ["fastapi>=0.100,<1.0"]` extra，`py-modules` 加 `iam_fastapi`；基础授权 SDK 保持零依赖不变。
- **验证：** 新增 `test_iam_fastapi.py` 契约测试 10 例（别名映射与单码契约、403/503/502 错误映射、未登记别名 fail closed、owner_only 本地主键解析、放宽 scope 403、resolver 缺失构造期拒绝、current_user、会话缺失 401）——**25 tests OK**（test_iam_fastapi 10 + test_iam_authorization 15，FastAPI TestClient + Mock client，无网络）。
- **文档：** `docs/技术架构与接入.md` 第 3 节标题与实现边界更新（FastAPI 授权适配层已交付；路由挂载/Node 适配器/向导仍待开发）+ 真实用法示例；4.3 节 SDK 能力表补 `IAMFastAPI` 行；`sdk/python/README.md` 补适配层段与示例。
- 设计取舍：适配层不自动挂载 login/callback/logout 路由（属后续「框架插件」任务）；`requireOwner` 语义由 `require_permission(..., owner_only=True)` 承担而非独立接口。
- 未做：真实 IAM 联调与小型 CRUD 模板项目；Node/Express 适配器。

## 2026-10-17 IAM P315 — SDK `check-batch` client methods (F02, Python + TypeScript)

- **Python（`sdk/python/iam_authorization.py`）：** `IamAuthorizationClient` 新增 `check_batch(access_token, tenant_id, permission_codes, resource_id=None)`——调用 `POST /api/v1/authorization/check-batch`，返回按请求码索引的 `dict[str, AuthorizationDecision]`；每个码复用与 `check()` 相同的判定语义。批量结果不携带行级数据条件（owner-only 数据操作仍走 `check(include_data_scope=True)`）；数量（1–32）与去重由服务端校验，违反以 `AuthorizationServiceError(422)` 抛出；响应缺码/畸形判定/坏 `application_id` 一律 fail closed 502；输入预检（token 非空、codes 非空字符串列表）在任何网络调用前抛 `ValueError`。
- **TypeScript（`sdk/typescript/src/authorization.ts`）：** 新增 `checkBatch(accessToken, request: BatchAuthorizationRequest)` 与 `BatchAuthorizationRequest` 接口（经 `src/index.ts` 导出），语义与 Python 侧一致；沿用单码 `check` 的 AbortController 截止时间模式（超时/网络 503、HTTP 拒绝保留状态码、坏 JSON 502）。
- **测试：** Python `test_iam_authorization.py` 新增 4 例（批量映射与单码契约、畸形/缺码拒绝、网络调用前输入预检、网络故障 fail closed）——**15 passed**；TypeScript `test/authorization.test.mjs` 新增 3 例（批量端点请求形状与映射、畸形/缺码拒绝、网络调用前输入预检）——**14 pass / 0 fail**（Node 22.20 `--experimental-strip-types --test`）；`tsc -p tsconfig.json --noEmit` 通过。
- **文档：** `docs/技术架构与接入.md` 第 4.3 节 SDK 能力表补两语言 batch 方法；两份 SDK README 各补 `check_batch`/`checkBatch` 段落与测试计数。
- 设计取舍：批量方法刻意不接入 data scope（多码批量面向菜单/按钮权限快照；行级过滤仍需单码 + subject 绑定校验，避免逐码 subject 校验逻辑在批量路径重复出错面）。
- 未做：真实 IAM 联调（与 P312 冒烟同界）；DeerFlow adapter 未接批量（其 permission map 逐键判定语义不变，无需改动）。

## 2026-10-17 IAM P314 — Full isolated suite green (P312 closure) + D01 contract-doc fixes

- **verify-local 全量（P312 验证闭环）：** 随机隔离 PostgreSQL 库迁移至 head `0031_model_usage_reconciliation` 后运行后端完整套件 **177 tests OK**（12.838s，含 P312 新增 `check-batch` 契约测试 6 例）；测试库自动清理，未触及开发主库。console 前端镜像 `docker compose build console` 成功（内部 `vue-tsc -b` + Vite 生产构建，exit 0）；api 镜像一并重建。
- **运行环境事实：** 非交互重定向 shell 下运行 `verify-local.ps1`，其 `$ErrorActionPreference='Stop'` 会把 docker 写到 stderr 的进度行（`Image ... Building`）包装为 NativeCommandError 直接终止脚本（2/2 段）；前端镜像按 P306 方式单独构建补齐。交互 shell 历史运行正常（P284/P298），脚本本身未改。另：后台 shell 需先把 Docker Desktop bin 加入 PATH，否则 buildx 找不到 `docker-credential-desktop`（P306 同款）。
- **D01 契约文档校正（3 处）：** ① `docs/技术架构与接入.md` 授权 API 表补 `POST /authorization/check-batch` 行（P312 契约缺口）；② 同文件更正过时表述「也没有中央批量 check API」→ 批量判定 API 已具备（`/auth/me` 不返回 permissions 的表述保留，仍属实）；③ `backend/README.md` 顶部补 P312 端点记录（追加式日志惯例）。
- **审阅结论（无动作项）：** 产品需求中「待开发」项（资源级净影响、账号导出/删除、SMTP 看板、拖拽排版、框架插件/向导）均为真实未实现，表述正确；`docs/后续项目对接手册.md`、`部署与运维.md`、`快速启动指南.md` 无过时契约表述。SDK（Python/TypeScript）尚无 `check-batch` 方法封装，属 F02 源码范畴，本轮不动。
- 未做：浏览器登录后控制台实测（P312 批量调用 UI 行为）；375 弹窗复测仍待用户。

## 2026-10-17 IAM P313 — B04 guidance budget closure verified (DeerFlow worktree)

- **背景：** P290 DeerFlow Windows 离线全量套件唯一失败为 `frontend/src/AGENTS.md` 49,630 bytes 超 49,152 上限（按用户要求未重跑）。本轮核实：该文件现为 **48,962 bytes**（≤ 上限），系 DeerFlow 工作区**并行会话的未提交改动**，本轮保留、未重复改动。
- **本轮修复（DeerFlow `.gitignore` +7 行）：** `backend/.t/` 与 `.t/` 加入忽略。根因：`scripts/check_agent_guidance.py` 的 `_worktree_paths` 用 `git ls-files --others --exclude-standard` 扫描，而 `backend/.t` 未被忽略，任何放在其下的 pytest basetemp（内含 repo 树副本的 `AGENTS.md`）都会使 `test_repository_has_the_approved_scoped_guidance_shape` 失败——实测 `backend/.t/p345-*` 并行会话残留即触发（13 个 extra items）。该修复对并行会话无害且消除其同类隐患。
- **验证：** 单独运行 `backend/tests/test_agent_guidance_check.py`（含预算断言 `test_repository_guidance_stays_below_hard_budgets_and_avoids_doc_indexes`）**12 passed in 6.68s**（隔离 `DEER_FLOW_HOME` + 系统 TEMP basetemp，临时目录已清）。未跑 32 分钟全量套件（遵守用户此前不重跑要求；`backend/.t` 尚有并行会话 15:33–17:43 的 p345-* 活跃残留，不做清理）。
- **DeerFlow 工作区事实：** 新增未提交改动 1 处（`.gitignore`）；`frontend/src/AGENTS.md` 压缩为并行会话既有未提交改动。`backend/.t/iam-bdde3959`（本轮一次性容器外测试 basetemp）删除被沙盒拒绝，已被 ignore 覆盖、无害，留待后续清理。
- B04 剩余：实际 IAM/Provider 路径与发布门禁验收仍待环境/授权。

## 2026-10-17 IAM P312 — Tenant console N+1 authorization check fix (P302 leftover)

- 后端：`app/schemas/access_control.py` 新增 `AuthorizationCheckBatch`（`permission_codes` 1–32 个、去重校验、`tenant_id/application_id/resource_id/include_data_scope` 同单码契约）；`app/api/v1/authorization.py` 抽出 `_public_decision` 辅助函数（原 `/check` 响应逻辑复用），新增 `POST /authorization/check-batch`——逐码构造与 `/check` 相同的 `AuthorizationCheck` 走同一判定路径，无批量旁路。
- 前端：`frontend/src/app/App.vue` `loadTenantConsole` 将每个 membership 的 5 路 `/authorization/check`（N+1）改为单次 `/authorization/check-batch`，按 `results[code]?.allowed === true` 消费；响应形状与原逐码结果一致，UI 行为不变。
- 测试：新增 `backend/tests/test_authorization_check_batch.py` 契约测试 6 例（schema 空列表/超 32/重复拒绝；端点逐码判定映射、非 OIDC 用户不带 application_id、OIDC allowed 携带验签 application_id）。一次性容器（`compose run --rm`，不动镜像/主库）pytest **6 passed**。
- 运行时冒烟（dev 容器，uvicorn --reload 已热加载新代码）：无认证 POST → 401（路由已注册、认证守卫生效）；容器内以应用自身 `create_access_token` 签 admin token（密码不经过命令行/日志）直调 → 200 + 逐码 `results` 映射；同 token 对照单码 `/check` 输出逐字节一致（当前开发库 admin 对 5 个管理码均为 `no_matching_grant`，系既有授权数据状态，`/check` 行为未变）。
- 说明：曾尝试以容器内默认规则集 Ruff 作为门禁，核实 IAM 后端无 Ruff 配置（`verify-local.ps1` 亦不运行 Ruff，历史 Ruff 记录均属 DeerFlow 项目），全库默认规则集下 436 处既有告警（B008×169 为 FastAPI `Depends` 标准写法、EXE002×103 为 Windows 挂载可执行位噪音），判定 Ruff 非本项目门禁，未据其改动代码。
- 验证：契约测试 6/6、`vue-tsc -b` 与 Vite 生产构建（临时产物已删）通过、运行时冒烟如上。未跑 `verify-local.ps1` 全量套件（改动为新增端点与前端调用形状，未触碰既有判定与迁移；全量套件可在下轮合并验证时运行）。无数据库迁移。

## 2026-10-17 IAM P311 — Narrow-screen modal overflow fix (user-reported)

- 用户手动复测 768/375：仅 375 下新建用户弹窗超宽。根因：全局样式无 `.ant-modal` 窄屏适配，antd Modal 默认固定 `width:520px`（375 视口必溢出，768 正常）。
- 修复：`frontend/src/style.css` 追加 `@media(max-width:575px){ .ant-modal{max-width:calc(100vw - 16px)} }`——全局作用于所有 antd 弹窗（新建/核对/邀请/确认），随视口收缩、内容流式自适应；桌面（520px）不变。
- 验证：Vite 生产构建通过（临时产物已删）；浏览器样式表确认规则随 HMR 注入（仅 ≤575px 生效）。375 实际效果待用户复测确认。
- 仅前端 CSS 1 文件变更；无后端/契约/迁移变更。用户复测其余 768/375 项未报问题。

## 2026-10-17 IAM P310 — C03-IAM walkthrough (light theme + admin tiering)

- 浅色主题 1026×855 走查：新建用户/模型用量核对/创建成员邀请三弹窗与 `/users`、`/model-usage`、`/invitations` 三页面渲染正常、无横向溢出；截图存档 c03-*.png。无修复项。
- 管理员分层证据：临时启用夹具用户 `a04-user1` 登录 → 「访问受限」态（侧栏 16 项平台菜单全过滤、提示所需权限码）；直访 `/users` 被路由守卫重定向受限页；同账号 token 直调 `/admin/users`、`/admin/overview` 均 HTTP 403。走查后用户停回 disabled（DB 收尾，auth_version+1）。
- 限制：自动化浏览器无视口 resize 能力，768/375 窄屏走查待手动复测；DeerFlow 业务页走查依赖 C01。P3-1 运行时复测无自然 422 场景，继续留观。
- 无源码/契约/迁移变更。同步 `docs/验收记录.md`（P310 节）与 `docs/项目总览与进度.md`（C03 行更新为浅色/分层部分完成）。

## 2026-10-17 IAM P309 — Shared reserved-domain validation extended to invitations

- 新增 `frontend/src/shared/utils/emailValidation.ts`：`isReservedEmailHost`（完整邮箱或裸域名判断）+ `validateReservedEmailDomain`（antd validator 形式），口径对齐服务端 `EmailStr` 的特殊用途顶级域（不拦 `example.com`）。
- `UserManagement.vue` 改为导入共享函数（消除 P308 本地副本）；`InvitationManagement.vue` 创建邀请在邮箱语法检查后追加保留域拦截，提示文案与用户管理一致。
- 验证：`vue-tsc --noEmit --pretty false` 与 Vite 生产构建（临时产物已删）通过。浏览器实测（admin 会话）：邀请填 `a04-inv@example.test` 提交 → toast「该邮箱使用保留顶级域…」，邀请未创建（列表 0 条）。
- 未做：公开认证页（登录/注册/找回）未加同款校验（登录场景意义有限且契约测试覆盖，需单独评审）；后端/契约/迁移无变更。

## 2026-10-17 IAM P308 — Fix P3-1/P3-2 UI defects found in P307

- P3-1：`frontend/src/shared/services/api.ts` 新增 `extractErrorMessage`——FastAPI 422 的数组型 `detail` 按 `字段（去掉 body 前缀）: 消息` 拼接为「请求校验失败：email: …」；字符串 detail 行为不变，非数组对象回退通用文案，不再出现 "[object Object]"。
- P3-2：`frontend/src/features/users/UserManagement.vue` 新建用户邮箱追加保留顶级域前端校验（`.test/.example/.invalid/.localhost/.local/.onion`），口径对齐服务端 `EmailStr`（email-validator）；刻意**不**拦 `example.com`（P307 夹具实测服务端接受）。
- 验证：`vue-tsc --noEmit --pretty false` 通过；Vite 生产构建（`--configLoader runner`，产物写系统临时目录后删除）通过。浏览器实测（dev 容器 HMR）：`@example.test` 提交被字段级提示拦截，无请求发出；P3-1 的 422 运行时路径因常见 422 已被前置拦截，待下次自然 422 复测。
- P3-3（AX 剪枝）调查结论：问题集中于 antd Select 下拉（渲染到 `body`）在嵌入式自动化 AX 树被剪枝，弹窗本体可见；改全局 `getPopupContainer` 风险大于收益，保留观察待真实读屏复核，未改码。
- 仅前端 2 文件变更；无后端/API/schema/迁移变更。其他表单的同类校验推广另行排期。

## 2026-10-17 IAM P307 — A04 management-write acceptance passed

- A04 管理写入验收全部通过。执行方式：用户浏览器手动登录两次（管理员密码不经过聊天/日志/命令行），Agent 接管会话 UI 走查；双身份/并发验证以 admin token 走 admin API。
- 通过项：新建用户 201 与重名 409；停用→登录 401、`auth_version`+1、refresh sessions/OAuth tokens 同事务撤销；恢复启用；`expected_status` 乐观锁双发 200+409；管理员自停用 400；角色创建→绑定 `deerflow.agent.read`→`role-bindings` 204；授权模拟 allow（matching_role_grant）→停用角色 deny（no_matching_grant）→恢复 allow→未授予 deny；测试用户会话被管理员远程撤销（二次确认）后踢回登录页，DB 撤销链与 `user.session.revoke` 审计完整；本人会话远程退出按钮 disabled；用量待核对队列分页、settle 费用 0.00900000 与目录价精确一致、release、未超期 409、并发双提交 200+409；终态汇总 2 笔、费用 0.01005000 精确。
- 夹具（开发库，停用保留为证据）：用户 `a04-user1@example.com`、角色 `a04.fixture.role`、`model_catalog a04-fixture-model`、预留 r1–r5（settled×2/released×1/reserved×2）、账目 2 条、审计全链。用户/角色已停用。
- 发现（未修待排期）：422 数组 `detail` 被 toast 渲染为 "[object Object]"；`EmailStr` 拒绝保留 TLD（`.test`）无字段级提示；部分 antd 弹窗对可访问性树不可见、键盘焦点管理不可靠；观察：同浏览器第二账号登录经共享 refresh cookie 顶掉第一标签会话（设计行为）。
- 无源码/契约/迁移变更；未运行自动化测试或构建。同步 `docs/验收记录.md`（P307 节）与 `docs/项目总览与进度.md`（速览、第 3/4/5/7/8 节，A04 → 已完成）。

## 2026-10-17 IAM P306 — Console container vue-router fix

- 修复 localhost:5175 报 `Failed to resolve import "vue-router" from "src/app/App.vue"`。根因：console 容器只挂载 `src` 源码，依赖来自镜像 `iam-platform-console:dev-oidc-consent-v2` 构建时安装的 `node_modules`；P303 因本机 pnpm store 链路异常仅把 `vue-router`/`@vue/devtools-api` 用 `npm pack` 装进宿主机 `node_modules`，`pnpm-lock.yaml` 与镜像内均无 `vue-router`。
- `frontend/pnpm-lock.yaml`：用 pnpm 12.6.0 `install --lockfile-only` 对齐 `package.json`，新增 `vue-router@4.6.4`、`@vue/devtools-api@6.6.4`，供应链策略校验 142 项通过。宿主机系统 pnpm 启动器（nvm4w shim + pnpm 按 PackageManager 字段自切换版本）在 Windows 上 spawn 到 store 内 POSIX shim 导致 `is not recognized`，属既有环境问题未修，本轮绕过方式：设全新 `COREPACK_HOME` 让 corepack 下载 pnpm 12.6.0 后直接 `node <COREPACK_HOME>\v1\pnpm\12.6.0\bin\pnpm.mjs <cmd>` 运行（corepack 自身缓存曾损坏，且其内置版本不识别 pnpm 12 的 `bin/pnpm.mjs` 入口，均只影响本机环境）。
- 重建镜像：把 Docker Desktop bin 目录加入 PATH（补 `docker-credential-desktop`）后 `docker compose build console`，镜像内 `pnpm install --frozen-lockfile`、`vue-tsc -b`、`vite build` 全部通过；`docker compose up -d console` 重建容器。
- 验证：容器 healthy；Vite ready；`http://127.0.0.1:5175/` 200；`/src/app/App.vue` 模块转换 200（约 102KB，此前该请求即报错点）。未改源码、API、数据库或迁移。浏览器登录后的路由/接入页走查仍未运行（P303 遗留）。
- 本轮期间另一会话完成了 P304/P305 进度文档重构并落盘（HEAD 亦变为 `0d7452c feat: cursor改造 0000`）；本轮文档按新结构增量更新速览与第 4/7/8 节，未覆盖他轮改动。

## 2026-10-17 IAM P305 — Progress document second-pass refinement

- `docs/项目总览与进度.md` 第 5 节由文字墙改为「轮次 → 证明了什么 / 不证明什么」证据表（P285/P290、P286、P292、P298、P301 五行），去重 P292 双重表述，并将 P285 分片与 P290 全量数字不可相加的约束写入表内。
- 第 3 节消除悬空「本轮」表述：IAM 平台行删除与「当前 HTTP 探测」行重复的未重探句；UI 行与第 4 节 A02 行的「本轮」改为明确的 P301 指代。第 4 节 F02 状态「部分推进」改为词表内「进行中」，补 P304/P305 任务行；第 1 节接手指令首行指向「当前状态速览」；第 8 节执行摘要更新为 P305（P304 明细见上一条），2026-10-17 索引行扩为 P302–P305。
- 文档静态复核通过：任务表状态全部落在第 4 节词表内、无残留悬空「本轮」、内部链接与章节编号 1–8 完整。纯文档改动：未改源码、API、数据库或迁移；未运行测试、构建或运行态探测。

## 2026-10-17 IAM P304 — Progress document deep restructure

- `docs/项目总览与进度.md` 重构为真正的第一阅读入口：顶部 P285–P303 逐轮堆叠摘要压缩为「当前状态速览」表（运行态/数据库/备份/前端/UI 走查/DeerFlow/阻塞/下一步）；第 8 节历史明细（2026-10-13 起，含 P283–P303、回滚事件、Docker 清理、密码重置、A02/A03 迁移等）压缩为「历史轮次索引」，全部逐轮事实以本 CHANGELOG 为准。
- 第 7 节新增「前端依赖 lockfile 对齐」阻塞行，保留 P303 因本机 pnpm store 异常经 `npm pack` 安装 `vue-router`/`@vue/devtools-api` 的事实；第 4 节新增 P304 任务行；第 1/8 节中「见第 8 节/本节首条」的回滚事件引用改指本 CHANGELOG；同步规则第 1 条措辞对齐新顶部结构。
- 章节编号 1–8 保持不变，任务 ID 全部保留。纯文档改动：未改源码、API、数据库或迁移；未运行测试、构建或运行态探测。

## 2026-10-17 IAM P303 — Admin console routing and project integration page

- Added vue-router history routes for all admin PageKey paths; sidebar uses router-link with active highlighting; visited-page lazy mounting preserved; deep links survive login for platform menu entries.
- New platform menu **新项目接入** at `/project-integration` with async `ProjectIntegrationPage.vue` (onboarding steps, input checklist, Python/TS SDK 3s fail-closed notes, secret boundaries, DeerFlow pilot decisions, architecture doc section index). F02 framework adapters remain unimplemented.
- `vue-tsc --noEmit --pretty false` passed. Vite production build passed (`--configLoader runner`); temp output removed. Browser route/integration walkthrough not run. No API, backend, database, or migration change. `package.json` declares `vue-router` and `@vue/devtools-api`; local pnpm CLI was broken so dependencies were unpacked via `npm pack` into `node_modules` for this verification.

## 2026-10-17 IAM P302 — Admin console frontend performance

- Removed pre-mount `await ensureManagementUi()` from `main.ts`; restored sessions bootstrap in parallel (`/auth/me` + management UI registration) behind a loading shell.
- Platform dictionaries load in the background after overview init; group and authorization-simulation pages reuse App dictionaries and load only when active/visited.
- Extracted async feature loaders to `featureLoaders.ts`; Vite `manualChunks` splits `ant-design-vue`. Dev watch polling defaults off; Compose console sets `VITE_DEV_USE_POLLING=true` for bind-mount HMR.
- `vue-tsc --noEmit --pretty false` passed. Vite production build passed (3,206 modules, `--configLoader runner`); entry ~50 KB gzip ~16 KB, ant-design-vue chunk ~876 KB gzip ~270 KB. Browser timing checks were not run. No API, backend, database, or migration change.

## 2026-10-16 IAM P301 — Signed-in walkthrough and backup recheck

- Signed in at http://127.0.0.1:5175/ with the administrator password from the root `.env`. Login succeeded. The overview showed the service as normal and DeerFlow as the current owner-only pilot. On-screen counts were not reconciled.
- At 1440px the sidebar collapsed to a 76px icon rail, stayed collapsed after refresh, and showed text labels again when expanded. It was left expanded. System theme stayed usable and was switched back to the light theme seen at login.
- The model-usage ledger was empty. Result, model, and UTC date filters were visible. `2026-13-40` showed “日期请使用有效的 YYYY-MM-DD” without a usage request for that value. A start date after the end date showed “开始日期不能晚于结束日期”; that inverted pair was not sent together. Dates were cleared afterward.
- At 375px the page used the full-page selector, not a cropped desktop sidebar, and had no page-level horizontal overflow. The selector options were not opened. The viewport was returned to 1440px. No page error or warning was captured after refresh.
- Both `D:\backup\iam-postgres\` dumps and their `.sha256` sidecars were still present. Checksums matched; prefixes `186e2e17` and `1960de15`. Dump contents were not opened and no restore was run.
- Not done: management writes, reconciliation submit, fee currency, failure-reason field, migration, public registration, quota enforcement, and the DeerFlow full suite. No type check, production build, or automated test was run.

## 2026-10-16 IAM P300 — Collapsible admin sidebar

- Desktop admin sidebar can collapse to navigation icons and expand back to the existing text labels. The choice is stored only in the current browser localStorage and defaults to expanded.
- The existing <=650px full-page page selector and the light/dark/system theme behavior are unchanged. No personal/tenant/platform preference priority, API, database, or migration was added.
- `vue-tsc --noEmit --pretty false` and Vite production build passed (3,205 modules); temporary output was removed. The browser stayed on the login page. Admin credentials were not submitted, so collapse, persistence, and the narrow layout were not clicked. Automated tests, readiness recheck, and DeerFlow tests were not run.

## 2026-10-16 IAM P299 — System theme and pilot copy

- The admin appearance control can follow the operating system color scheme. Stored light or dark preferences stay unchanged.
- Overview, resource-grant, and data-scope copy now describe DeerFlow as the only current pilot with owner-only data. They no longer present AI Resume or Knowledge Base as active integrations.
- `vue-tsc --noEmit` and Vite production build passed (3,205 modules); temporary output was removed. The browser was on the logged-out login page. Admin credentials were not submitted, so the signed-in theme and overview were not clicked. No API, database, or migration change.

## 2026-10-16 IAM P298 — Model usage history filters

- Usage summary and event list accept optional model, outcome, and UTC calendar-date filters. An inverted date range returns HTTP 400 before querying. The reconciliation queue stays tenant-and-pagination only.
- The usage page exposes the same filters, resets to page 1, and clears the previous ledger scope. A failed model-catalog read does not fail the ledger read.
- `vue-tsc --noEmit` passed. API-container contract tests passed 6/6. Read-only checks showed healthy Compose services, ready 200, and Alembic current=head `0031_model_usage_reconciliation`. The development-database integration test, Vite production build, and browser checks were not run. No schema or migration change. Backup files were not rechecked. Fee currency and failure-reason fields remain absent.

## 2026-10-15 IAM P297 — Model usage error states

- A failed usage, summary, review, or tenant read now produces an explicit error state instead of zero totals and a successful empty state. Previously successful data is retained; tenant changes clear data from the prior tenant, and pagination changes clear prior-page rows while loading.
- Vue vue-tsc --noEmit --pretty false and Vite production build passed (3,205 modules); temporary build output was removed. Browser normal empty state was checked after hot reload. Error injection and non-empty reconciliation remain unverified.
- No backend/API/schema/database/migration changes or automated tests. See [acceptance record](docs/验收记录.md).
## 2026-10-15 IAM P296 — Model usage UI review

- Reviewed the current administrator model-usage empty state and source contracts. A failed request in the shared load path clears usage, summary, and reconciliation data and then displays successful empty states (P1).
- Fee currency and failure-reason fields remain absent; history filtering supports tenant and pagination only (P2). No source code, API, database, migration, tests, or build artifacts were changed or run. Non-empty/reconciliation flows, light theme, and current multi-viewport checks remain unverified.
- See [acceptance record](docs/验收记录.md) and [project status](docs/项目总览与进度.md).

## 2026-10-15 IAM P295 — Model usage UI fixes

- Added a success-rate summary with an em dash for zero requests, made the tenant label and All tenants placeholder visible, and rendered empty/loading states outside the wide tables. Populated tables retain internal horizontal scrolling.
- Vue type check and Vite production build passed (3,205 modules); temporary build output was removed. Browser checks at 375/768/1024/1440px showed no page-level horizontal overflow; the 375px empty states were centered and visible, and no localhost page errors/warnings were found.
- No automated tests or backend/API/schema/DB/migration changes. Failure-reason fields, fee currency, richer history filters, non-empty rows, reconciliation submission, light theme, and live IAM/Provider acceptance remain open.

## 2026-10-15 IAM P294 — Model usage UI audit

- Read-only browser review of the desktop dark-theme empty state: tenant filter appears blank; success rate is absent; the event API has no failure-reason field; history supports tenant filtering and pagination only; displayed fee currency is unspecified; the empty reconciliation table shows a horizontal scrollbar.
- Empty-state wording and reconciliation safety notice are clear. No code, tests, build, database, migration, or live-readiness checks were changed or run. The P292 responsive/build results are prior evidence, not rerun in this audit. Currency policy awaits user input; non-empty rows, pagination, reconciliation submission, light theme, and narrow-screen behavior remain unverified.

## 2026-10-15 IAM P293 — Runtime status documentation correction

- Corrected operations, architecture, handoff and current-status documents: the 2026-10-14 migration/0031/ready-200 snapshot is historical; P292 Docker named-pipe and API loopback permission failures leave current Compose, database revision/readiness, and backup availability unknown.
- Added a read-only handoff checklist for the user's PowerShell session when the current tool terminal lacks Docker/loopback permissions. It explicitly avoids migrations, `.env` changes, and password resets.
- Documentation-only change. Link/status review passed; no tests, builds, Docker/API probes, database writes, or migrations were run in P293.

## 2026-10-15 IAM P292 — Model usage UI fixes

- Fee summary now distinguishes zero requests (“暂无用量”) from requests with unknown aggregate cost (“费用未知”). Model catalog, usage and reconciliation tables derive their horizontal scroll widths from configured columns; constrained cards/table containers keep page width stable and the usage hint explains horizontal scrolling.
- Added the missing Ant Design Vue `Badge` and `Divider` components to the lazy management registry.
- Vue type check passed; Vite production build passed with 3,205 modules. Browser layout checks at 375/768/1024/1440px showed no page-level horizontal overflow; current empty-state text and Badge registration were confirmed, with no recent app errors or unresolved-component warnings. Build output was written to and removed from a system temp directory.
- Read-only runtime probe after UI verification failed: Docker Compose could not access the dockerDesktopLinuxEngine named pipe; proxied then direct localhost API health/readiness requests were denied. Current DB revision/readiness and protected-backup availability remain unknown. No API, backend, database, or migration change; no automated test suite run. Non-empty usage, unknown-cost response, review submission, light theme and live IAM/Provider acceptance remain open.

## 2026-10-15 IAM P291 — Model usage UI review

- Read-only desktop dark-theme review found page-level horizontal overflow on the usage table and ambiguous summary copy: a zero-request response with `estimated_cost: null` displays “未配置价格”. Review queue policy copy is clear.
- Browser showed the IAM service as normal and a platform-admin session; this does not establish current DB revision/readiness. Both usage and review datasets were empty, so rows, pagination, and reconciliation modal remain unverified; light theme and narrow viewports were not checked.
- No product code, database, tests, or builds changed/run. Findings and evidence limits recorded in `docs/验收记录.md`; follow-up UI changes require a separate implementation request.

## 2026-10-15 IAM P290 — DeerFlow B04 full offline run and model-switch handoff

- DeerFlow Windows Python 3.12 unsharded offline suite completed in 32:06: **17,149 passed, 404 skipped, 3 deselected, 1 failed, 82 warnings**. The sole failure is the guidance budget check: frontend/src/AGENTS.md is 49,630 normalized UTF-8 bytes against a 49,152-byte hard limit (478 bytes over).
- The run followed earlier DeerFlow changes: shortened frontend guidance, made MCP retry timing assert between captured start/finish bounds, and documented timing assertions; the 9 focused checks had passed before this full run. The full suite remains non-green. Per user request, no rerun was started; the unique pytest temp root was confirmed removed.
- Updated the model-switch handoff and current summaries. Next manual continuation: reduce the guidance file by at least 1 KB, then wait for user instruction before running further tests. IAM Docker/API, database revision/readiness/backups remain unknown; no IAM runtime, DB, migration, quota, or Provider operation occurred.

## 2026-10-14 IAM P289 — Model-switch handoff and stale-status correction

- 更新模型切换交接：新会话先读接手手册第 0、8 节和项目进度、PRD、IAM Skill；说明当前目标、工作区权限和最新证据；不得依赖聊天摘要或复用过期迁移授权。
- 将 PRD 与前端 README 的 0031/ready 200 记录标为历史，明确当前 revision/readiness 未验证，并同步本轮进度。
- 未运行产品测试、构建或目标环境验收；未修改源码、数据库或配额。automation-2 已删除，不再周期运行。

## 2026-10-14 IAM P288 — Runtime reprobe and status-document correction

- Repeated read-only checks: Docker Desktop Compose access was denied by the dockerDesktopLinuxEngine named pipe; localhost:8002/ready and localhost:5175 were unreachable. Current database revision/readiness and backup availability remain unknown.
- Corrected current-state summaries in the architecture/startup/handoff docs; A02/A03 migration and archive records remain historical evidence pending a live check.
- No tests, source changes, DB writes, migration, quota changes, or browser acceptance were performed.

## 2026-10-14 IAM P287 — Model-switch handoff and automation stop

- Added a model-switch handoff checklist covering source-of-truth order, workspace permissions, the unresolved IAM runtime/backup conflict, migration and secret gates, confirmed DeerFlow decisions, task IDs, layered verification, documentation sync, and next actions.
- Corrected the handoff summary so historical migration/readiness records are not presented as current runtime facts. P286 frontend verification remains a source/build result only.
- Deleted heartbeat automation-2 at the user request. No source, backend test, Docker/HTTP probe, database, migration, quota, or provider operation occurred.

## 2026-10-14 IAM P286 — Vue type check and production build

- Directly ran the existing vue-tsc noEmit type check and Vite production build using the installed frontend dependencies; both exited successfully. Vite transformed 3,205 modules and emitted 36 files.
- The build output was isolated under the system temporary directory and removed. The pnpm wrapper, browser/A04 flow, backend tests, database, migration, quota, and IAM runtime were not run or changed.
- IAM readiness, current database revision, and protected-backup availability remain unverified under P285; this frontend build does not establish runtime or end-to-end acceptance.

## 2026-10-14 IAM P285 — DeerFlow Windows B04 shard verification and IAM runtime probe

- Re-ran both duration-aware Windows Python 3.12 offline groups with PYTHONUTF8=1 and a short temporary root: group 1 **8,564 passed / 215 skipped / 8,778 deselected / 44 warnings (1,031.95s)**; group 2 **8,587 passed / 194 skipped / 8,776 deselected / 44 warnings (1,178.94s)**. Targeted suites passed **21** then **2** tests; Ruff check/format passed and all pytest temp roots were removed.
- Fixed LocalSandboxProvider to continue evaluating operator mounts when skill projection is unavailable; stabilized projection test fixtures. Suppressed Hypothesis slow-generation health checks only for the randomized batching property case, and made Windows icacls output decoding tolerant.
- Read-only runtime probe could not establish current IAM status: Docker Desktop named pipe denied access and localhost:8002/api/v1/ready was unreachable. Existing migration/backup evidence conflicts with the P284 Skill live snapshot; readiness, current DB revision and archive availability remain unverified. No database, migration, quota, live provider or target service changes were made.
- Not full product acceptance: live IAM login, DeerFlow OIDC/OAuth/owner-only end-to-end behavior, browser checks, and full release gates remain outstanding. Restore Docker access, reconcile the live DB/backup evidence, and continue A04/DeerFlow acceptance.

## 2026-10-14 回滚事件与重建、Docker 深度清理、梳理收尾

- **回滚事件（17:30 前后）：** 本仓库 git 跟踪文件被外部批量恢复到 HEAD（`25a2968`），当日 15:10 后全部未提交修改丢失（脚本兼容修复、文档更新、.gitignore）。`.env`、数据库 0031 状态、`D:\backup\` 归档、运行容器未受影响。已重建：部署脚本 PS 5.1 兼容修复、`.gitignore` 的 `*.tsbuildinfo`、tsbuildinfo 索引移除、进度文档全部最新事实及本条目。教训：多会话并行操作需协调，勿对 IAM 仓库执行 checkout/restore/reset。
- **Docker 深度清理（用户确认含未使用镜像）：** 项目内删除再生 tsbuildinfo 与 `node_modules\.vite`（9.3MB）；`builder prune`×2 清空构建缓存 25.21GB→0B；`image prune -a` 回收 5.0GB（镜像 41→11 个）。⚠️ DeerFlow 镜像 `iam-deerflow-package-check:20261011`、`deer-flow-dev-gateway:latest` 及 `python:3.12-slim` 等基础镜像被删，B03/迁移构建前先核对网络。stopped 容器与未使用卷未动。清理后 IAM 三容器 healthy、ready 200。
- **梳理收尾：** 删除无法登录的僵尸账号 `admin@localhost.test`（事务内连带 1 行 tenant_memberships，其余 9 张关联表 0 行；剩余 users=1）；修正进度文档对不存在文件 `USER_INPUT_CHECKLIST` 的悬空引用。三个 `.env` 示例、key-rotation compose、requirements.txt+lock、pnpm-workspace、deploy/caddy、生产 Dockerfile/nginx、CHANGELOG、sdk、backend/tests 均核查后保留。

## 2026-10-14 A02/A03 完成：真实备份、隔离恢复演练与开发库迁移 0021→0031

- 按用户授权完成迁移门禁全链路：备份目录确认为 `D:\backup\iam-postgres`；生成真实归档 `iam-postgres-20261014T081157Z-e02dac03.dump`（SHA-256 186e2e17…d24bd，容器内 `pg_restore --list` 通过）；`verify-postgres-restore.ps1` 随机隔离库恢复演练通过（SHA-256 校验、恢复后 revision 0021、核心表核对、隔离库删除、原库未动）。另有并行会话生成迁移后 0031 归档（082113Z，SHA-256 1960de15…edf4b9）及第二次隔离恢复演练通过。
- 用户明确授权后执行 `--profile migrate run`：首次失败即停止（`password authentication failed for user "iam"`）。根因是 postgres 卷 9/27 初始化后 `.env` 于 10/9 修改了 `IAM_POSTGRES_PASSWORD`：数据库 role 密码停留在旧值，旧 api 容器持旧密码可连，migrate 用新密码被拒（容器内 scram 认证对比证实）。修复：postgres 容器内 `ALTER USER iam` 对齐当前 `.env`（密码不落主机命令行/日志），`up -d api console` 重建；二次迁移 0021→0031 一次通过。
- 迁移后核验：`alembic current` 与 heads 一致为 `0031_model_usage_reconciliation`，`/api/v1/ready` 200，api/console/postgres 全部 healthy。未 bootstrap（已有用户），公开注册与配额 enforcement 保持关闭；本次授权仅覆盖 0021→0031 这一次迁移。
- 修复部署脚本 PowerShell 5.1 兼容（脚本逻辑与门禁未变）：5 个 `.ps1` 补 UTF-8 BOM；`backup-postgres.ps1`/`verify-postgres-restore.ps1` 的 here-string 先转 LF 再经 base64 传给容器内 `sh -ec`（PS 5.1 传参不转义内嵌双引号、here-string 保留 CRLF，均导致容器内脚本损坏）。
- 管理员密码重置：`.env` 的 `IAM_ADMIN_PASSWORD` 为占位符且与两账号哈希均不匹配（bootstrap 不重置既有账号）；经用户选择随机密码重置，api 容器内生成 20 位随机密码 UPDATE `admin@example.com` 的 `password_hash`，`.env` 已同步，密码不落命令行/日志。
- 文件清理（spec: cleanup-unneeded-files）：移除 git 误跟踪的 `frontend/tsconfig.tsbuildinfo` 并 ignore `*.tsbuildinfo`；`secure-backups/iam-dev` 备份移至 `D:\backup\iam-postgres`；删除 `.t`、`backend/.ruff_cache`、`frontend/dist`、`sdk/typescript/dist`；删除僵尸账号；同步 PRD、前后端 README、验收记录、快速启动指南、部署运维。真实登录（A04）待用户执行。

## 2026-10-14 快速启动指南独立成文与部署运维简化

- 按用户要求将快速启动指南从 `docs/部署与运维.md` 拆出，新建独立文件 `docs/快速启动指南.md`：前置检查、`.env` 创建、`start-local.ps1` 启动、readiness 探测、需授权的 migrate/bootstrap、访问入口、日常命令与隔离验证，并注明当前开发库 0021 / head 0031、ready 503 `database_migration_pending` 状态。
- `docs/部署与运维.md` 精简为要点式手册（约 450 行 → 约 240 行）：环境状态、本地开发与故障排查、备份恢复、迁移授权与回退、生产发布、TLS/RSA 轮换、账户会话邮件、模型核对、部署输入清单；移除内嵌快速启动章节改为链接，压缩重复解释与长段落。
- 所有命令、参数与门禁表述保持不变；同步 `docs/项目总览与进度.md`（导航表 5 份 → 6 份、第 6 节引用、D01 备注、第 8 节摘要）。本轮仅文档整理与静态核对；未运行启动、迁移、备份/恢复、生产预检或产品测试。

## 2026-10-14 IAM P284 environment check and isolated full validation

- Docker Engine is available again. Read-only probes report Console/PostgreSQL healthy, API unhealthy, /api/v1/health 200, and /api/v1/ready 503 database_migration_pending; live Alembic revision is 0021_resume_wallet_perms, while source head is 0031_model_usage_reconciliation.
- verify-local.ps1 passed the complete backend suite against an isolated random PostgreSQL test database (169/169); the iam_test_* database was confirmed removed. The backup script's ValidateOnly passed but created no archive.
- Re-ran Vue type checking and Vite production build against the current read-only mounted source: 3,205 modules built successfully to temporary container storage. No IAM product source or main database changed.
- Reviewed pending migration source and preserved the migration gate: no real protected backup exists and no explicit migration authorization was given. Real IAM login and DeerFlow target/Provider/browser acceptance remain pending.

## 2026-10-14 DeerFlow B04 extension-manager tool gates and notification budget fix

- The second ordered 104-file slice reported **2,368 passed, 2 failed, 86 skipped, 4 warnings (502.53s)** before the final notification fix. Thirty-five extension-manager test functions (38 parameterized cases) now skip explicitly without `uv`; the exact host API pin test follows source `API_VERSION`.
- Fixed the notification budget race with `asyncio.timeout().expired()` and a clamped shared deadline. Focused lifecycle, extension-manager and API-pin regressions passed **126 tests** with **40 uv-dependent skips**; Ruff check/format passed. The slice was not rerun after this code fix.
- The remaining observed slice failure is local venv metadata `deerflow-extension-api==0.2.16` vs source/lock `0.2.18`. The user reported an IAM page saying database migration is pending; this turn did not query the target DB or run a migration. Temporary test roots were deleted.

## 2026-10-14 DeerFlow B04 Windows shell harness and missing-tool classification

- `test_dev_entrypoint.py` now writes its extracted sync block to a temporary POSIX file before invoking Git Bash, avoiding Windows reinterpretation of a long `sh -c` argument.
- Makefile injection tests explicitly skip when GNU make is absent; the frozen uv-project bootstrap and config-upgrade shell tests skip when `uv` is absent. Static contract tests remain active.
- `test_dev_entrypoint.py`, `test_extension_dependency_sync.py`, and `test_config_version.py`: **44 passed, 13 skipped**. Ruff check/format and `git diff --check` passed; the temporary test directory was deleted.
- The original second 104-file slice and full suite were not rerun. No IAM product code, database, migration, quota, or frontend source changed.

## 2026-10-14 DeerFlow B04 Windows path and interpreter fixtures

- Normalized the expected JSON detector path and extension source path to POSIX form in cross-platform tests. The deploy extras test now provides a known runnable Python shim to Git Bash instead of relying on the host PATH to expose the active venv.
- `test_detect_blocking_io_static.py` and `test_deploy_uv_extras.py` passed **56 tests**; the controlled extension uv-project path case passed **1 test**. Ruff check/format passed on the four touched Python files; all test temp roots were removed.
- The second 104-file slice was not rerun; its 82 failures remain the original observed count and are still being triaged. No production deploy script, IAM, database, or quota behavior changed.

## 2026-10-14 DeerFlow B04 second ordered slice and DeltaChannel property-test stability

- The next 104 path-sorted offline test files reported **2,339 passed, 82 failed, 35 skipped, 4 warnings in 521.70s**. Failures remain only partially triaged; observed categories include unavailable `uv`/GNU make and Windows/Git Bash path/process differences. This partial slice is not a full-suite result.
- Reproduced a Hypothesis `HealthCheck.too_slow` failure in `test_merge_message_writes_randomized_differential`. The strategy now emits bounded primitive data and materializes LangChain/Pydantic messages in the test body; the pure generator suppresses only the `too_slow` check to avoid scheduler noise. The DeltaChannel module passed **35/35**; Ruff check and format passed.
- Removed the isolated test root. No DeerFlow production runtime, IAM database/migration, or quota setting changed. Real IAM/Provider acceptance remains open.

## 2026-10-14 DeerFlow B04 顺序切片与 Windows 测试修复

- 修正 DeerFlow 超时失败标记测试按当前 OS mock runner；live-policy 子进程显式使用 UTF-8 解码，并在 Windows 最小环境中保留 `SystemRoot`/`WINDIR`；没有 GNU make 时，4 个依赖 Makefile dry-run 的用例明确 skip。压缩 `frontend/src/AGENTS.md` 的模型目录段落，保留用户隔离、AbortSignal 和授权边界要求，文件回到指导预算内。
- 验证：timeout **8 passed、6 skipped**；guidance **12 passed**；live-policy **7 passed、4 skipped**；两份 Python 文件 Ruff check/format 通过。按路径排序前 104 个离线测试文件切片 **3,099 passed、67 skipped、3 deselected、0 failed、16 warnings（476.57s）**；隔离目录已清理。
- 切片不代表全量：最近完整离线快照仍是 17,062 passed / 142 failed / 349 skipped / 3 deselected / 0 errors；另一次全量尝试约 17% 退出码 1073807364、无 pytest 汇总，原因未确认。未执行 IAM 迁移或真实 IAM/Provider 验收。
- A01 只读复核：Docker Desktop CLI 存在但 Linux Engine named pipe 不可用；绕过代理后 API readiness loopback 连接拒绝，无法刷新容器/DB revision。未启动服务或写数据库。

## 2026-10-14 DeerFlow B04 Windows 超时测试 runner 修正

- 修正 `test_timeout_output_carries_authoritative_failure_marker`：按平台 mock `_run_windows_command` 或 `_run_posix_command`，避免 Windows 上调用真实 `make test`。生产沙箱代码未改。
- `test_local_sandbox_command_timeout.py`：**8 passed、6 skipped**；Ruff check/format 通过。隔离测试目录已清理。
- 完整离线套件重跑约 17% 时以退出码 `1073807364` 结束，没有 pytest 最终汇总；不作为全量结果。最近可用完整快照仍为 17,062 passed / 142 failed / 349 skipped / 3 deselected / 0 errors（82 warnings，44:15）。未执行 IAM 迁移或真实 IAM/Provider 联调。

## 2026-10-13 B04 DeerFlow Agent、Crawl4AI 与 Windows URI 测试修复

- DeerFlow `test_custom_agent.py` 的 API fixture 通过 mock `_authenticate` 建立显式测试用户与 agents read/write/delete/admin 权限，CRUD 断言继续经过真实 permission decorator；授权策略由独立路由授权测试覆盖。Crawl4AI 离线测试对 URL safety resolver 固定为公网测试地址，保留 SSRF 私网拒绝用例。MCP Windows file URI 断言根据 `tmp_path` 实际盘符生成，不再要求测试目录位于 `C:`。未改生产逻辑。
- 三文件聚焦套件 **171 passed、1 skipped、1 warning（23.06s）**；Ruff check/format 通过。临时测试目录已清理。
- 本执行环境的 Git status/diff 调用报 `Invalid executable path`，无法枚举工作区差异；没有执行 git 清理、提交或重置。
- 最近完整 DeerFlow 离线套件快照仍为 **17,062 passed、142 failed、349 skipped、3 deselected、0 errors、82 warnings（44:15）**，该快照早于本次三类测试修正，未重跑全量。剩余失败包括缺少 `uv`/`make`、Windows `WinError 10106`、虚拟环境 extension API metadata 0.2.16 落后源码/lock 0.2.18 及其他待分类项。未做 IAM/DeerFlow 数据库迁移、真实 IAM/Provider 联调或 quota enforcement 验收。

## 2026-10-13 B04 context and Gateway-service focused verification

- `test_context_compaction.py` and `test_gateway_services.py`: **212 passed**. No code change, and no target DB/IAM/provider was touched.
- Used an isolated `DEER_FLOW_HOME` and pytest basetemp; the temporary root was removed. The full suite was not rerun; last full snapshot remains the earlier 17,004/186/349/3/5 result.
## 2026-10-13 B04 extension runtime test-fixture follow-up

- Fixed the single stale fake-Request fixture in `test_extension_task_store_runtime.py` that omitted FastAPI `request.state`; no Gateway runtime behavior changed.
- Extension task runtime focused module: **15 passed**. Ruff check/format passed; isolated pytest and cache roots were removed.
- No full rerun; last full snapshot remains 17,004/186/349/3/5. Other independent focused runs are recorded in the progress document. Missing `uv`, `WinError 10106`, and remaining failures stay open.
## 2026-10-13 B04 DeerFlow DNS and PAT scope contract triage

- FastCRW web-fetch tests now use a deterministic public DNS answer in offline runs; production SSRF validation remains unchanged. FastCRW + thread-route focused tests: **142 passed, 1 warning**.
- The PAT scope test previously required equality with the entire Gateway permission catalog, contradicting the curated path/method allowlist. It now pins the exact 16-scope PAT subset. API and Gateway guidance now accurately list selected personal Agent and memory endpoints. PAT runtime behavior did not change (only its explanatory module docstring did). PAT auth/repository/vault tests: **63 passed, 1 warning**.
- The full offline suite was not rerun; the last full result remains 17,004/186/349/3/5. `uv`, `WinError 10106`, and other failures remain open. Ruff check/format passed; temporary roots were removed. No migration, live IAM/provider, or quota-enforcement validation ran.
## 2026-10-13 文档合并与多项目简单接入方案

- 将 docs 的 9 份英文文件名文档收拢为 5 份中文文件名文档：项目总览与进度、产品需求、技术架构与接入、部署与运维、验收记录；保留任务 ID、验证证据和当前阻塞，历史实施记录归档在本文末尾。
- 更新根 AGENTS、根/前后端 README、启动脚本提示和 IAM Skill 的相关引用；简化重复 API/SDK 与历史状态描述。记录多项目低门槛接入的目标和待实现通用封装，当前仅 DeerFlow 为业务试点。
- 只运行文档目录、相对链接、旧文件名引用与关键内容静态检查；未运行产品测试/构建、数据库迁移、备份/恢复或真实 IAM/Provider/browser E2E。本轮宿主机 readiness 探测被沙盒套接字权限拒绝，当前运行状态沿用已有带日期证据。

## 2026-10-13 B04 DeerFlow Windows Gateway test-fixture triage

- Reproduced seven failures in three focused test files: deploy subprocess output decoded through the Windows GBK locale, and Gateway fake Request objects omitted `state`. Added explicit UTF-8 replacement decoding and realistic request state to the test doubles; no DeerFlow production code or IAM frontend was changed.
- `test_gateway_startup.py`, `test_gateway_checkpoint_mode.py`, and `test_thread_regenerate_prepare.py`: **45 passed, 1 warning**. Ruff check and format passed; isolated pytest/lint roots were removed.
- The last full backend snapshot remains 17,004 passed / 186 failed / 349 skipped / 3 deselected / 5 errors; no full rerun after these targeted fixes. Missing `uv`, `WinError 10106`, and remaining failures stay open. No migration, live IAM/provider, or quota enforcement ran.
## 2026-10-13 B04 Windows Studio route regressions

- The full offline suite had five Studio setup errors because the child Python used the Windows GBK default text encoding while a locked dependency opened a UTF-8 OpenAPI asset. The Studio test child now sets `PYTHONUTF8=1`; startup logs decode with replacement so future startup errors remain visible.
- The cross-version persistence test now waits for the runtime in-memory store periodic disk flush while the server is still alive before simulating a restart. This avoids checking a file before the runtime 10-second flush and avoids relying on force-termination shutdown hooks.
- The Studio route module passed **6/6**; Ruff check/format passed; its temp root was removed. Full suite was not rerun, so the prior 17,004/186/349/3/5 snapshot remains the last full result. Missing `uv`, `WinError 10106`, and other failures remain open. No database migration/live provider/quota checks ran.

## 2026-10-13 B04 DeerFlow full offline suite rerun

- Latest Windows Python 3.12 offline backend run: **17,004 passed, 186 failed, 349 skipped, 3 deselected, 5 errors, 99 warnings** in 35:00. The number of Windows-conditional skips increased by three; unsuccessful items total 191 (failures + errors), so the suite is still not passing.
- Known issues: extension-manager cases cannot find `uv`; a live-policy subprocess hits `WinError 10106`; five LangGraph Studio setup errors are obscured by UTF-8 decoding of the startup log, and the underlying server startup cause remains unknown. Other failures still need individual triage.
- The pytest temp root was removed. No migration, live IAM/provider, or quota-enforcement checks ran; no test source was deleted.

## 2026-10-13 B04 DeerFlow owner-scoped skill cleanup and failure triage

- Implemented owner-scoped custom skill cleanup in `UserScopedSkillStorage` and exposed it through `GatewayOwnerDataDeleter`; it removes only the selected user's custom packages, history, and private skill-state entries, preserves global legacy/integration skills and their per-user preferences, rebuilds only that user's projection, and refreshes only that user's prompt cache. This capability is not yet exposed as a product data-job/API/UI scope.
- Full offline backend snapshot remains **17,007 passed, 191 failed, 346 skipped, 3 deselected** (before the later test fixes). Browser modules passed **87/1 skipped**; Lark broker, user-scoped skill storage, and owner-data deleter passed **76 tests, 6 skipped**. The six skips include three POSIX launcher runtime tests skipped on Windows; they were not run on Linux in this turn. pnpm/checkpointer/store focused regressions passed **3/3**.
- Fixed the Windows Lark fake-executable test path and bypassed inherited system proxies in its localhost failure test. Ruff check/format passed on the five current Python files; pytest temporary roots were removed. Missing `uv` and the live-policy subprocess `WinError 10106` remain environment blockers; no migration, live IAM/provider, or quota enforcement ran.

## 2026-10-13 B04 DeerFlow 完整套件归因与 Windows 测试稳定性

- 完整离线后端快照为 **17,007 passed、191 failed、346 skipped、3 deselected**；该次运行包含六个同步后的失败归因模块，但早于后续浏览器 DNS 测试夹具及 Windows 测试修正。浏览器自动化两模块随后 **87 passed、1 skipped**；pnpm 路径与 checkpointer/store singleton 定向用例 **3/3 passed**。完整套件尚未在这些后续测试调整后重跑。
- 修正 Windows pnpm 测试对 `.cmd` 大小写的错误假设，并把并发 singleton 测试的同步等待上限从 3 秒放宽到 10 秒；无生产 checkpointer 逻辑变更。缺少 `uv` 会阻断 extension manager 测试；live-policy 子进程在当前环境遇到 `WinError 10106`。其余全量失败仍需逐项分类。
- Ruff check/format 通过；所有本轮 pytest 临时目录已删除并确认不存在。未运行数据库迁移、真实 IAM/Provider 调用或 quota enforcement。

## 2026-10-13 B04 DeerFlow 失败归因模块测试契约同步

- DeerFlow 六个失败归因模块的测试夹具同步到当前 auth context、权限集、OIDC identity、route request state、共享删除 helper 与 scheduled-run mock 签名；没有修改生产逻辑。
- 验证：六模块 **301 passed、3 skipped**；6 个变更 Python 测试文件 Ruff check/format 通过。上一轮完整离线后端 **16,896 passed、302 failed、346 skipped、3 deselected**，发生在夹具同步之前；未在最新测试树重跑。项目 guidance 预算回归 1/1、MCP config secrets **195 passed**；本轮 pytest 临时目录均已清理。
- 未执行 IAM migration、数据库写入、真实 IAM/Provider 调用或 quota enforcement；B04 继续分类完整套件失败，A01/C01/C02 仍待目标环境。

## 2026-10-13 B04 DeerFlow Windows 路径回归修复与验证

- DeerFlow 在 Windows 下的长文档路径超过系统路径预算时，现在通过项目内稳定的 documents/.short/<digest> 物理别名访问同一逻辑文档；旧路径仍可读，逻辑 stored_relpath 与数据库 schema 不变。
- DeerFlow focused regression 65 passed、2 skipped；完整 blocking-I/O 140 passed、3 skipped、0 failed。Ruff check/format 对 9 个变更 Python 文件通过；临时测试目录已清理。
- 该路径修复后的完整离线结果与后续测试夹具复测见同日较新 B04 条目；全量失败继续分类。未运行 IAM 数据库迁移、真实 IAM/Provider E2E；quota enforcement 继续关闭。
## 2026-10-12 DeerFlow 未知模型结果保留待核对

- 对齐用户确认的“保留待核对”：LangChain 模型调用发生异常或 callback 在终态前关闭时，若无法证明 Provider 未接收请求，不再以失败/0 输出结算；清理本地 callback 后保留 IAM reservation，由其 10 分钟到期后进入管理员核对。只有可靠证据确认 Provider 未被调用才可释放。
- DeerFlow focused IAM usage/outbox、memory commit 与 Harness boundary 回归 **33/33**；Ruff check/format 通过。完整离线后端 **16,775 passed, 419 failed, 346 skipped, 3 deselected**（48 分钟）；blocking-I/O **114 passed, 28 failed, 1 skipped**。未解决的套件失败进入 B04 分类；未迁移数据库、未启用配额、未进行真实 IAM/Provider 请求。

## 2026-10-12 · DeerFlow Provider 路径静态审计

- 静态核对当前仓内 DeerFlow `backend/app` 与 `backend/packages/harness/deerflow` 的内置生产 Python 入口：共享模型工厂、Gateway 单次调用及 DeerMem 专用 hook 均处于 LangChain callback 用量管道中；Codex Responses 自定义 Provider 继承 `BaseChatModel` 并由共享工厂构造；唯一直连 `init_chat_model()` 的内置生产路径是已接入 hook 的 DeerMem。外部扩展动态加载的 Provider 未穷尽。
- IAM 用量 `request_id` 是每次 LangChain invocation 生成的本地幂等 ID。Codex 内部对特定 HTTP 状态的重试仍按一个 invocation 计量，待依据 Provider 计费语义确认是否需要 attempt 级记账。
- 本轮只读静态检查；未运行测试、构建、真实 Provider/IAM 请求或数据库操作。目标环境/API readiness 阻塞真实验收；quota enforcement 保持关闭。

## 2026-10-12 · DeerFlow 后台记忆模型用量接线

- 修复 DeerMem 自建模型的 timer/debounce 路径未稳定挂载模型用量 callback 的缺口。Gateway 在后台调用时重新加载活动用户与匹配 OIDC vault，会话有效时绑定服务端模型档案并创建单次 usage callback；Harness 只把 callback 放进当前 invocation config，结束后移除并关闭，不将凭证或 capability 放入队列。
- `model_usage.enabled=false` 时保持不计量；启用时若身份/vault/admission 不可用则拒绝 provider dispatch。相关现有 memory commit 与 usage callback 回归 **20/20**、Harness boundary **1/1** 通过，运行于 DeerFlow Windows Python 3.12 隔离目录，测试临时目录已删除。
- 6 个变更 Python 文件 Ruff check/format 通过；全量套件、IAM/Provider 联调、DB migration 或前端构建未运行；IAM readiness 仍为 503，配额 enforcement 保持关闭。



## 2026-10-12 · DeerFlow B01 权限映射与 A01 环境盘点

- 对照 IAM migrations `0026–0030`、DeerFlow Central IAM 示例配置、Gateway permission constants 与 IAM adapter，新增完整 route/model/tool permission map、普通用户/运维角色最小授权建议、owner/self、存量 issuer/sub 绑定与 PAT fail-closed 说明。静态比较得到配置样例 36 个唯一映射，其中 35 个 DeerFlow code 命中 catalog；`model:use` 使用 `model.invoke`，catalog 中的 `deerflow.model.use` 当前未被样例引用，不可视为等价 grant。实际应用/tenant/model UUID 与角色 grant 仍待部署方输入。
- Docker CLI 已恢复。只读确认 IAM Console/Postgres healthy、API unhealthy，`/api/v1/ready` 为 503 `database_migration_pending`，数据库 revision 为 `0021_resume_wallet_perms`；注册挑战相关表不存在，未发现运行中的 DeerFlow 容器。
- 本轮仅更新文档；未改源码、未运行测试/构建、未启动或停止容器、未备份/迁移/写库，也未调用真实 IAM 或 Provider。

## 2026-10-12 · 建立持续维护的模型交接与后续计划

- 新增 `docs/项目总览与进度.md`，记录当前实现/验证/运行基线、已确认决策、任务 ID/优先级/依赖/验收、源码与验证入口、阻塞和接手指令；新增根 `AGENTS.md`，要求每轮同步当前进度、证据和下一步。
- 同步整体/前后端 README、PRD、接入计划与部署输入入口；修正模型治理中过期的全量状态和 0031 验证描述，将组织共享与上游 revoke 接线从本阶段未决项移出。仅整理相关文档，未触发全项目 `--更新` 审计。
- 只读 HTTP 重查 Console 200、API readiness 503 `database_migration_pending`；当前终端找不到 docker.exe，数据库 revision 沿用最近核实的 0021，未刷新。源码 migration 图确认 IAM head 0031、DeerFlow Harness head fd_0028；本轮未运行产品测试/构建、归档/恢复、迁移、role grant 或真实 E2E。完成文档链接与路径静态核对。

## 2026-10-12 · 清理过期测试临时目录

- 删除并核验 7 个过期 pytest 临时根目录均不存在：`.df-agents-tmp`、`.df-agents2-tmp`、`.t`、`.tmp-deerflow-iam-memory`、`.tmp-deerflow-iam-memory-final`、`.tmp-deerflow-scope-final`、`iam-test-5gz2bgca`。未删除测试源码或项目运行数据。
- 前端、后端源码静态搜索未发现 TODO/FIXME/NotImplemented 占位；本轮没有运行测试。

## 2026-10-12 · Docker CLI 与 readiness 排障

- 复核 Console HTTP 200、API readiness `503 database_migration_pending`。当前 PowerShell 的 `docker` 解析至 `C:\Windows\System32\docker` 并因拒绝访问无法启动；常见 Docker Desktop CLI 路径不存在，故无法刷新容器/数据库状态。
- 在启动指南增加命令解析诊断、显式 `-DockerPath` 用法和禁止在 CLI 不可用时操作迁移/数据库卷的提示。没有运行 migration 或测试。

## 2026-10-12 · migration 0022–0031 影响审阅

- 逐项检查源码 migration，确认公开注册默认关闭、权限目录 migration 不自动授予角色；`0024` 移除挑战密码摘要列，`0025` 消费未绑定授权快照的待验证挑战，`0022` downgrade 会删除注册相关表，`0031` 对既有人工核对账目拒绝 downgrade。
- 只读探测 Console HTTP 200、API readiness 503；当前执行环境无 Docker CLI，未能刷新开发库 revision。没有执行 migration、备份、数据库写入或 role grant。执行前需要受保护备份目录和明确迁移授权。

## 2026-10-12 · DeerFlow Windows 文档长路径兼容

- DeerFlow 项目文档在完整 Windows 路径超过 240 个 UTF-16 单元时使用短物理文件名，数据库与接口仍保留用户原始显示名；转换器需要的后缀保留，MIME 从显示名推断，历史 `original/{name}` 路径保持可读。
- 项目/文档/线程/运行四组路由回归在短临时根目录下 **225/225 通过**；4 个修改的 Python 文件 Ruff check/format 通过。最初长 basetemp 本身触发 WinError 3，使用短目录复跑通过并删除测试临时目录。未改 IAM schema、migration、开发数据库、角色授权或 Vue 代码。

## 2026-10-12 · DeerFlow owner-only 决策与部署/验证基线

- 用户确认 DeerFlow 第一阶段项目、线程、运行、文档仅本人访问；记录为当前产品规则。IAM owner/self scope 必须与本地 `user_id` 查询过滤求交，tenant/organization sharing 继续 fail closed。未来开放共享需另行决定资源映射、授权和历史回填。
- DeerFlow IAM/OIDC/model/vault/usage/data_scope 专项测试选择 169/169 通过（Windows Python 3.12，mock/隔离）。全量 Windows 非 live 测试完成过一次长 basetemp 运行：16,770 passed、422 failed、345 skipped、3 deselected（46:36）；一个深路径代表失败改用短 Temp 路径后通过。短路径全量重跑在约 34% 因 `WinError 10106` 中断，完整全量仍未验收。没有把剩余失败统一归因于环境。
- IAM Console HTTP 200；API unhealthy、readiness 503 `database_migration_pending`。数据库 `0021_resume_wallet_perms`，源码 head `0031_model_usage_reconciliation`。只读备份预检通过，不生成归档、不写数据库；未运行 migration。
- 修正 `docs/部署与运维.md` 过时的 `0027` 当前状态记载，并同步 PRD、整体/前后端说明、架构、接入计划、待输入清单和 `iam-project` Skill。项目源代码未修改；DeerFlow/真实 IAM/浏览器 E2E 未做。

## 2026-10-12 · DeerFlow Python 提取回退保留链接

- Node/Readability.js 不可用时，Python article fallback 改为保留 article/main 中的安全链接和图片目标，并移除脚本、嵌入/表单等活动内容及不安全 URL。
- 既有 `tests/test_web_fetch_relative_links.py` 修复后 50/50 通过，Ruff check/format 通过；没有新增或遗留测试文件，隔离 pytest 目录已删除。
- 修复前全量后端快照 16,750 通过、442 失败、345 跳过、3 deselected；阻塞 I/O 116 通过、26 失败、1 跳过。修复后未重跑全量，其余失败仍需归因。

## 2026-10-12 · DeerFlow 全模型授权与回归结果

- Gateway 统一模型工厂为每次 provider dispatch 校验确切模型档案的 `model:use`；DeerMem 后台模型另校验实时用户/vault、记忆本人读写范围和目标模型权限，Gateway 注入 Harness 回调并保持 Harness 不依赖 `app.*`。
- 定向模型/记忆回归 28/28、Harness boundary 1/1、Ruff check/format 通过。Windows 临时目录隔离后的 DeerFlow 全量后端为 16,750 通过、442 失败、345 跳过、3 deselected；阻塞 I/O 为 116 通过、26 失败、1 跳过。抽查 web-fetch 用例 22 失败、26 通过，Python readabilipy fallback 未保留链接目标（本机缺 Node/npm）；其余全量失败尚未逐项归因。
- 删除本轮临时授权测试文件、编译产物和 pytest 隔离目录，保留既有测试文件及其余未提交改动。未修改 IAM migration/开发数据库，未完成真实 IAM/Provider E2E。

## 2026-10-11 · PRD 与项目文档状态一致性

- 更正 0031 的验证进度：隔离 PostgreSQL 全量套件 169/169、Vue 检查和 3205 模块 Vite production build 已通过；明确开发数据库仍为 0021、真实 IAM/DeerFlow E2E 未验收。
- 把 AI Resume 与 Knowledge Base 旧接入说明标为已清理/当前范围外，并同步 PRD、根/前后端 README、架构、接入计划、模型网关、用户输入清单和项目 Skill。
- 本次仅修订文档，不迁移数据库、不修改运行代码、不改变角色 grant。

## 2026-10-11 · 模型用量账目服务端分页

- 移除管理员模型账目列表固定 500 条上限，`GET /admin/model-usage/events` 改为 tenant-filtered `items/total/limit/offset` 响应，limit 限制 1–200，并用创建时间与事件 ID 稳定倒序。
- 管理台账目表增加 API 驱动的总数和服务端翻页，租户/页大小变化时回到第一页；新增 PostgreSQL 集成用例覆盖总数、跨页完整性和排序。
- 修复 `verify-local.ps1` 对 Docker Hub EOF 的检测，使其同时识别 `registry-1.docker.io` 与 `auth.docker.io`。首次命中令牌端点 EOF 后重跑成功；该次走在线构建路径，离线 fallback 未单独触发。
- 同步 PRD、前后端 README、整体架构、运维/启动手册、用户输入清单、Skill 和根 README。隔离 PostgreSQL 全套迁移至 `0031_model_usage_reconciliation` 后 **169/169 通过**；Vue 类型检查和 3205 模块 Vite production build 通过。开发库仍为 `0021_resume_wallet_perms`，没有迁移；真实 IAM/DeerFlow E2E 未完成。

## 2026-10-11 · 模型待核对运维契约与运行页复查

- 运维手册补充待核对列表的筛选、分页上限、响应结构、稳定排序和并发 409 处置指引，并同步 PRD、整体架构、前后端 README 与项目 Skill。
- 浏览器只读复查确认管理台登录页可显示，但数据库迁移未就绪时认证按钮禁用；开发库仍为 `0021_resume_wallet_perms`、源码 head 为 `0031_model_usage_reconciliation`。本轮未执行迁移或后端集成测试。

## 2026-10-11 · 模型调用未结预留待核对闭环

- 按用户选择“保留待核对”实现：IAM 即使关闭 RPM/TPM 拦截也会在 Provider 调用前持久化预留；10 分钟到期只进入核对队列，不自动按预留上限计费或释放。待核对预留继续占保守 TPM。
- 新增 IAM migration `0031_model_usage_reconciliation`、带总数分页的管理员待核对列表/处置 API、同事务审计，以及管理台实测/估算用量结算和“确认 Provider 从未调用”后释放的表单。手工用量标记来源，延迟可空；释放不产生用量事件。
- 更新 PRD、模型网关决策、架构、运维、DeerFlow 集成计划、用户输入清单、IAM 前后端 README、DeerFlow 根/后端中英文 README、架构、双语变更日志、根 README 和项目 Skill。DeerFlow 实际 Token 仍需从 Provider 日志/账单人工核对，不能从崩溃窗口自动恢复。
- 后续实现与验证：待核对队列改为 total/offset/limit 分页，避免 500 条上限隐藏积压。`vue-tsc --noEmit`、Vite 临时目录生产构建、分页后 6 个 Python 文件 AST 和 Pydantic 核对契约检查通过。完整 pytest 在可用 DeerFlow venv 中因缺少 `pwdlib` 未能收集；PostgreSQL 分页集成未运行。开发库仍为 `0021_resume_wallet_perms`、API readiness 为 503，`0031` 未迁移。未进行真实 IAM/Provider E2E。

## 2026-10-11 · 部署预检与本地登出决策复核

- `deploy/backup-postgres.ps1 -ValidateOnly` 通过：Compose 配置可解析、PostgreSQL 认证成功、`pg_dump`/`pg_restore` 可用；没有创建归档或写入数据库。
- 当前 IAM API readiness 仍为 HTTP 503 `database_migration_pending`；开发库为 `0021_resume_wallet_perms`，源码 head 为 `0030_deerflow_preference_permissions`。真实试点验收仍等待受保护备份目标与迁移授权。
- 用户确认 DeerFlow OIDC 登出只清理本地 vault session，不向 issuer 发送 access/refresh token。本轮未改应用代码、未迁移数据库；生产预检仅作源码审阅。

## 2026-10-11 · DeerFlow webhook production guard

- The `DEER_FLOW_ALLOW_UNVERIFIED_GITHUB_WEBHOOKS` escape hatch is now disabled whenever `DEER_FLOW_ENV` or `ENVIRONMENT` explicitly selects production. With no webhook secret, production does not mount the route and the runtime handler rejects the unsigned request.
- Full focused browser and webhook regressions passed 76/76, including explicit data-scope denial and authorization-service failure close codes; the public URL SSRF test uses deterministic DNS results. Ruff check/format passed. No IAM UI, DB, or permission mapping changed.

## 2026-10-11 · DeerFlow 浏览器实时流中央 IAM 鉴权

- Gateway 浏览器 WebSocket 在 thread lookup 和保留浏览器 session 前检查 `threads:read/write` 及匹配线程的读写 owner/self data_scope；本地签名 session `sid` 继续绑定到服务端 OIDC token vault。保留本地 owner / Origin 校验，授权服务失败时连接失败关闭。
- 浏览器与 webhook 完整聚焦回归 **76/76 通过**，含数据范围拒绝与授权服务失败关闭码；公网 URL SSRF 用例使用固定 DNS 结果，避免外网解析依赖；Ruff check/format 通过。未改前端、迁移、角色 grant、数据库或登出行为；真实 IAM/WebSocket E2E 待完成。

## 2026-10-11 · DeerFlow 个人偏好中央 IAM 授权

- 偏好 GET/PATCH 分别要求 `preferences:read/write`，并在读取或写入 DeerFlow `user_preferences` 前检查匹配已验证 OIDC 主体的 owner/self data_scope；现有浏览器 session 与本地账户 owner 校验继续保留。
- IAM 新增 append-only migration `0030_deerflow_preference_permissions` 登记 `deerflow.preference.read/write`，不自动授权任何角色；DeerFlow `config.example.yaml` 增加两条 permission map。
- `tests/test_user_preferences.py` 定向回归 **19/19 通过**，覆盖权限不足、IAM data_scope 拒绝先于仓储、浏览器 session 与本地 owner 隔离；改动 Python 文件 Ruff check/format 通过。
- `verify-local.ps1` 将空隔离 PostgreSQL 库迁移到 0030 后，完整后端套件 **161/161 通过**；Vue 类型检查与 Vite 生产构建通过（3205 modules）。IAM Alembic 单一 head 核验为 `0030_deerflow_preference_permissions`。
- 前端交互未改变。开发库仍停在 `0021_resume_wallet_perms`、readiness 503；未执行 IAM/DeerFlow migration、没有真实 IAM 联调。正式验收需部署方授予对应角色权限与本人范围。

## 2026-10-11 DeerFlow production runtime 镜像复验

- dev Gateway 镜像 iam-deerflow-package-check:20261011 已生成；一次性容器使用镜像 uv 环境导入 deerflow.authz.iam_deerflow 通过。
- default runtime 镜像未产出。首次 runtime 构建报告 uv.lock stale；同版 uv 在已构建镜像中对当前挂载源码执行 uv sync --dry-run --locked --extra redis 通过，uv.lock SHA-256 与预检前一致，没有改写用户已有 lockfile。
- 后续 runtime build 被 Docker Hub Python manifest metadata 和 GHCR uv image anonymous token 请求 EOF 阻断，包括 --pull=false。待 Docker Hub/GHCR 可达或提供镜像源后重试；本轮未启动服务或数据库。

## 2026-10-11 DeerFlow Gateway 镜像打包预检

- DeerFlow .dockerignore 排除 runtime config 文件、备份副本和所有 .env* 变体，保护运行期模型/MCP 配置不进入 build context；保留既有 pytest/ruff/mypy/hypothesis cache 排除。
- dev target 镜像在构建客户端退出后由 Docker daemon 完成：iam-deerflow-package-check:20261011（sha256:f2203cacf14d7a324dadcaa4d803145fcd9fd48129a9e9f15751e4beb4947456）；一次性容器通过 uv run 导入 deerflow.authz.iam_deerflow。完整服务启动与在线联调仍待验收。
- 本地服务、数据库均未启动或变更；待 registry 可达、预拉镜像或配置 mirror 后重跑 image build 和容器内 adapter import。

## 2026-10-11 DeerFlow tenant/organization 数据范围审计

- 只读检查确认 projects/threads/runs/documents 的持久化归属使用本地 user_id；核心资源行没有可用于 organization/tenant 查询过滤的可信字段。tenant_id 目前在 IAM OIDC vault 与模型用量数据中，不代表业务资源归属。
- 维持已实现的 owner/self 查询过滤；tenant/organization scope 继续 fail closed，不扩大到同租户其他用户数据。
- 将组织共享资源清单、可信归属映射与旧数据回填列为产品输入；未改 DeerFlow schema，也未执行迁移。

## 2026-10-11 DeerFlow 异步 IAM 授权回归

- DeerFlow backend Python 3.12.14 下，sdk/python/test_iam_deerflow.py 运行 unittest 22/22 通过，覆盖 async authorize 与 async data_scope capability refresh。
- backend/tests/test_iam_provider_interoperability.py 使用 -p no:cacheprovider 运行 12/12 通过，含 4 项 async data_scope；不再受 pytest Windows cache path 写入警告影响。
- 所有用例均为 mock/隔离测试，没有访问真实 IAM、Provider、业务数据库或浏览器。此前 Windows runtime event-loop hang 未在本次解释器中复现；真实环境和 role grants 仍待验收。

## 2026-10-11 运行就绪与登出决策复核

- 只读查询确认 IAM 开发数据库为 0021_resume_wallet_perms，源码 migration head 为 0029_deerflow_agent_extension_permissions；API /api/v1/ready 当前为 HTTP 503 database_migration_pending。
- deploy/backup-postgres.ps1 -ValidateOnly 通过；本次没有创建备份归档、修改数据库或执行迁移。
- 用户明确选择 DeerFlow 本地登出：/auth/logout 只清理本地 vault session，不通过 RFC 7009 向外部 issuer 发送 access/refresh token。发现解析及 RFC 7009 客户端原语可保留，但不接入登出流程。
- 当前登录页在 readiness 未就绪时阻断认证提交；Vue 类型检查、Vite production build 和浏览器禁用态检查已通过。服务恢复仍需受保护备份、迁移审阅和用户明确授权。

## 2026-10-11 · 登录页 readiness 操作门禁

- readiness 初始检查/数据库待迁移/不可用时，禁用登录、注册、密码重置、邀请接受和 OIDC consent 提交；提交 handler 同样复核状态，避免键盘提交绕过按钮状态。
- 邀请、应用登录和 consent 上下文仅在 ready 后加载，避免 API 未就绪时把有效邀请或授权票据误报为无效；数据库待迁移提示说明管理员备份、审阅、迁移与重查顺序。
- Vue/TypeScript 检查通过；Vite production build 通过（3205 modules，输出到临时目录）；浏览器 AX 确认 readiness 文案和登录按钮 disabled。未修改后端或开发数据库，API readiness 仍为 503。
## 2026-10-11 · DeerFlow 持久模型用量结算 outbox

- 新增 SQLAlchemy 持久 outbox 与 DeerFlow 迁移 fd_0028_iam_model_usage_outbox。终态用量事件先落库，再由后台 worker 按幂等 request_id、120 秒租约和 2–600 秒指数退避投递；成功记录保留期默认 30 天，可按配置调整。敏感凭证、prompt 和响应正文不进入 outbox。
- 聚焦回归 118 passed、1 条既有 warning；Ruff 检查/格式通过；全量 Alembic 链在隔离 SQLite 库升级至 fd_0028。未连接真实 IAM、Provider 或开发数据库，未对开发数据库执行迁移。
- 该 outbox 可恢复已提交事件，但不能消除 Provider 完成与本地 outbox 提交之间的崩溃窗口；自定义非 LangChain Provider 和线上互操作仍需验收，配额强制保持关闭。
## 2026-10-11 DeerFlow 模型用量回归复核

- 使用 DeerFlow backend venv 重跑 `test_model_factory.py`、`test_iam_model_usage_callback.py`、`test_iam_model_usage.py`、`test_worker_iam_credentials.py`：**110 passed, 1 warning**（37.47s）。警告来自既有未知模型参数测试。
- 测试使用本地 mock/隔离 fixture；未连接 IAM、Provider 或开发数据库，未运行迁移。
- 这次只更新验证记录，没有声称结算 outbox、进程崩溃恢复或真实联调已完成；配额执行仍需保持关闭。

## 2026-10-11 · DeerFlow per-call IAM 模型用量回调

- DeerFlow 的模型工厂从 run-scoped ContextVar 取回可选 callback，并按可信 `config.models[].name` 绑定到每个 LangChain model instance；Provider 部署别名或 request metadata 不决定 IAM model UUID。每次 LLM 调用先 reserve，quota/服务失败会在 Provider dispatch 前 fail closed；结束时按同一 request ID settle，若 IAM 未要求 reservation 则 report usage。
- 使用同一 run vault capability 的 access token 经 `/api/v1/auth/me` 解析 IAM UUID 用户；OIDC `sub` 不当作 UUID。每个映射模型必须显式设置 `reserved_output_tokens`；`model_usage.enabled` 默认关闭，`IAM_MODEL_USAGE_API_KEY` 只注入 DeerFlow API Secret Manager。Prompt/响应只在内存中估算，不发送给 IAM 或写入日志。
- callback 测试 8/8（含 async callback manager 拒绝传播、Provider 别名归属与 worker close 清理），client+callback+vault 回归 15/15；完整 model factory+usage 组合回归 110/110，Ruff check/format 通过。持久 settlement outbox/崩溃恢复、自定义非 LangChain Provider 覆盖和真实 IAM/Provider 验收仍未完成；配额执行开关继续关闭。

## 2026-10-11 · DeerFlow 模型配额接入契约审计（实现前快照）

- 前置审计当时确认 DeerFlow 只有 `model.invoke` 权限检查、尚未调用 Gateway run lifecycle usage API；IAM usage API 需要 tenant/application/model/user UUID。新增 Harness `IamModelUsageClient`，覆盖 `/auth/me` 用户 UUID 解析、reserve、settle、report 的服务端契约。
- 确认 OIDC `sub` 是不透明值；实现时须通过 vault access token 请求 IAM `/api/v1/auth/me` 取得规范用户 UUID。
- 客户端离线契约测试 5/5、Ruff check 通过。将逐 Provider 调用配额、主/子 Agent/取消覆盖与持久结算恢复缺口同步到文档。未读取/修改 `.env`、环境密钥或数据库；后续 per-call callback 实现见上一条日志。

## 2026-10-11 · IAM readiness 与本地迁移审查

- 只读核验管理台 `5175/` 返回 HTTP 200、API `/api/v1/ready` 返回 503 `database_migration_pending`；开发库当前为 `0021_resume_wallet_perms`，源码 head 为 `0029_deerflow_agent_extension_permissions`。
- 确认 `public_registration_challenges` 表不存在，故 0024/0025 challenge cleanup 对当前库为零行影响；0026–0029 仅增加权限目录，不自动授予角色。
- 未读取 `.env`、未创建备份、未执行 migration。恢复 API readiness 仍需受保护备份、用户明确批准及 migrate profile 执行；全过程已写入启动指南和待提供清单。

## 2026-10-11 · DeerFlow Console 聚合报表权限

- stats 现在要求 `runs:read`、`threads:read`、`agents:read` 及对应 Central IAM owner/self scopes；跨线程 runs 还要求 thread read，usage 要求 run read。
- 所有范围判定在 SQL session 获取前执行；仍保留 DeerFlow 本地 `user_id` owner filtering。
- Console router 回归 **25/25 通过**，Ruff check 通过。未修改前端、迁移数据库或授予角色；真实 IAM 和浏览器验收待部署配置。

## 2026-10-11 · DeerFlow OIDC token revoke 原语与授权边界

- DeerFlow OIDC metadata 解析可选 `revocation_endpoint`，`OIDCService.revoke_token()` 提供 RFC 7009 HTTPS form request、Basic/POST/public client auth 和不回显凭证或 Provider 正文的错误处理。
- `test_oidc_auth.py` + `test_iam_token_vault.py` **41/41 通过**；Ruff check 通过。`ruff format --diff` 仅提示 `oidc.py` 与 `test_oidc_auth.py` 中不属于本次新增部分的既有格式差异，本轮未全文件格式化以免改写同文件既有变更。
- 自动审查拒绝将该调用接入 DeerFlow logout，因为这会把 vault access/refresh token 发给外部 issuer，且当前没有用户明确授权。登出仍只删除本地 vault session；未请求真实 IAM、未改数据库/环境 secret。待用户明确决定是否允许该凭证出站后再继续实现 logout 联动。

## 2026-10-11 · DeerFlow memory worker 提交前复核

- 默认 memory callback 在实际 `apply_changes/save` 前重查 Central IAM `memory:read/write`；revision conflict 每次重试都重新校验。
- 同步 worker 将用户/会话/Agent 标识交给 Gateway serving loop，重载 active 本地用户和身份匹配的 OIDC vault session；token/capability 不进入队列。授权不可用、scope 不匹配或超时均拒绝持久化；本地 RBAC 与未启用授权仍保留既有行为。
- 提交前 worker 回归与 updater/data-scope 联合验证 **109/109 通过**；Ruff lint 与 format check 对 6 个变更 Python 文件通过。未修改前端、数据库、migration、secret 或角色 grant；真实 IAM/OIDC 与浏览器验收仍待环境。

## 2026-10-11 · DeerFlow Agent 个人记忆授权

- 被动记忆中间件在加入异步写入队列前，同时检查 Central IAM `memory:read` 与 `memory:write`；`memory_search` 检查 read，`memory_add/update` 检查 read+write，`memory_delete` 检查 read+delete，并确保拒绝发生在 MemoryManager 存储访问之前。
- 仅接受当前 Gateway run 绑定的服务端 IAM capability；校验本地 DeerFlow user ID 与 runtime 身份一致、IAM subject 与 owner scope 一致、租户一致。空范围、租户/组织宽范围、主体错配和 IAM 异常均失败关闭；本地 RBAC/未启用授权维持原行为。
- 在 prompt memory 注入、记忆工具、after-agent 被动入队和 summarization flush 四个路径中统一执行前置检查；定向 memory/prompt/summarization 回归共 **181/181 通过**，12 个 Python 改动/测试文件 Ruff check 与 format check 通过。
- 后台 worker 提交前的撤权复核由 2026-10-11 新条目补充；本节 181/181 仅覆盖 admission/prompt/tool 相关实现。未修改数据库、migration、secret、IAM Vue 或 DeerFlow 用户配置；真实 IAM/浏览器联调仍待环境和角色 grant。

## 2026-10-11 · 隔离 PostgreSQL 全套回归至源码 head 0029

- 使用一次性 API 容器运行 `tests/run_isolated_postgres_suite.py`；隔离库从空库迁移至 `0029_deerflow_agent_extension_permissions`，后端完整套件 **161/161 通过**。
- 在一次性 Console 容器对当前工作区显式运行 `vue-tsc -b` 与 Vite production build，3205 modules 构建通过；Console 生产镜像也成功构建。
- `backup-postgres.ps1 -ValidateOnly`、生产 Compose 示例 `config --quiet` 与部署/备份/恢复 PowerShell 脚本语法检查通过。未生成备份归档。
- 复核临时 `iam_test_*` 数据库已清理；主 IAM 开发库仍为 `0021_resume_wallet_perms`，API `/api/v1/ready` 返回 `503 database_migration_pending`。未迁移主开发库。
- API 容器 unhealthy，console 与 PostgreSQL healthy。此验证覆盖后端完整套件和空库迁移，不覆盖真实 IAM/OIDC、浏览器 E2E、DeerFlow 目标库或角色 grant。

## 2026-10-10 · 技能编辑与完整响应读写双授权

- 自定义技能 update/rollback 返回完整技能正文；在任何个人 storage 读取或写入前，Central IAM 现在同时校验 skills:read/read-scope 和 skills:write/write-scope。
- connectors、stateless runs、Agent 兼容、skills、MCP、subagents 与 IM worker 管理的跨切片回归通过 141/141；8 个 DeerFlow Python 文件 Ruff check/format check 通过。
- 仅验证代码级授权边界；IAM/DeerFlow 开发数据库未迁移，未配置中央 role grant，未做真实 IAM/OIDC 浏览器验收。
## 2026-10-10 · DeerFlow 中央授权跨切片回归

- 将 IM/Lark 连接器、无状态 run、Agent 兼容路由、skills、MCP、managed subagent 与 IM worker 状态/重启授权的定向回归合并运行，138/138 通过，1 条 Starlette/httpx deprecation warning。
- 8 个改动 DeerFlow Python 代码/测试文件通过 Ruff check 和 Ruff format --check。未执行 IAM/DeerFlow 开发库迁移、未配置角色 grant、未做真实 IAM/OIDC 浏览器 E2E；代码回归不代表部署验收。
## 2026-10-10 · DeerFlow IM worker 状态与重启授权

- /api/channels worker 状态读取增加 channels:read；全局 worker restart 增加 channels:admin，并保留原有本地 Gateway 管理员校验。
- 将独立 worker 管理 API 与个人 channel connection/data_scope 边界明确区分；复用 IAM migration 0028 已登记的权限码，无新 migration。
- 技能、MCP、子 Agent 与频道连接器/worker 管理回归 81/81 通过；Ruff check 与 8 个变更 Python 文件 format check 通过。无数据库迁移或在线 IAM/浏览器联调。

## 2026-10-10 · DeerFlow 技能、子 Agent 与 MCP 管理权限

- 技能目录与个人自定义技能新增 Central IAM read/write/delete 和本人 data_scope 校验；共享技能开关和进程缓存刷新使用 skills:admin。
- 托管 subagent 目录要求 subagents:read，CRUD 和完整 prompt 需要 subagents:admin，系统 prompt 还要求 DeerFlow 本地管理员。MCP 配置读取、增删改和缓存刷新统一要求 mcp:admin，并保留本地管理员检查。
- 新增 IAM migration 0029_deerflow_agent_extension_permissions，只登记 7 个权限码，不授予角色；DeerFlow config.example.yaml 增加对应映射样例。
- 技能/MCP/subagent 组合定向回归 79/79 通过，Ruff check 与 7 个改动 Python 文件的格式检查通过（1 条 Starlette/httpx 弃用警告）。未迁移数据库，未做真实 IAM 或浏览器联调。

## 2026-10-10 · DeerFlow IM 与 Lark 连接器中央授权

- 为 channel providers/connections、个人 IM 连接/断开和个人 Lark 状态/config/OAuth 流程增加对应 Central IAM read/write 权限及本人 data_scope；继续保留 DeerFlow 本地用户 owner 隔离。
- 部署级 channel runtime config 与 Lark install 同时校验 Central IAM admin 权限及 DeerFlow 本地管理员身份。
- IAM migration 0028_deerflow_connector_permissions 只登记六个权限码，不自动授予任何角色；config.example.yaml 添加 channel/integration route permission map 示例。部署方仍需配置授权策略和本人范围。
- 连接器授权、Agent 兼容路由、无状态运行与 owner isolation 定向回归 57/57 通过；Ruff check 通过，10 个变更 Python 文件格式检查通过（Starlette/httpx deprecation warning）。未迁移 IAM/DeerFlow 数据库，未执行真实 IAM/浏览器联调。

## 2026-10-10 · DeerFlow 无状态运行数据范围校验

- 在 `/api/runs/stream` 与 `/api/runs/wait` 入口调用统一 `start_run` 前增加 Central IAM `runs:create` data_scope 检查；已有本地 thread owner 检查继续执行，两个边界共同阻止仅凭线程 ID 绕开中央范围策略。
- 同时将旧 `/api/assistants/*` 列表、详情、graph、schemas 兼容读取接入 `agents:read` 与本人 data_scope 门禁，避免绕过正式 Agent API；无新增部署配置。
- 新增及相邻 Gateway 定向回归共 28/28 通过，改动四个 Python 文件 Ruff check/format 通过；未做真实 IAM/浏览器联调，也未迁移数据库。
## 2026-10-10 · DeerFlow 模型与工具资源级授权

- 将 DeerFlow 本地模型名绑定到服务端配置的 IAM ModelCatalog UUID；`model:use` 映射 `model.invoke`，复用 IAM 对同 tenant 活动模型的检查，映射缺失时在访问 Provider 前拒绝。模型列表通过 `filter_actions.model=list` 独立检查 `deerflow.model.list`。
- 工具候选使用服务端工具名作为 IAM `resource_id`，逐工具 grant 可相互隔离，IAM 应用级 grant 仍可显式允许全量工具。
- 增加模型 UUID 映射、未映射模型拒绝、逐工具过滤和无效 UUID 回归；包含 4 项新用例的同步互操作选择 **8/8 通过**，改动 Python 文件 Ruff check 与格式检查通过。完整 12 项文件在现有异步 data_scope 用例段挂起，随后 4 项异步用例被排除；IAM/DeerFlow 数据库及真实浏览器联调未进行。

## 2026-10-10 · 文档状态与单一试点基线对齐

- 更正启动指南中过期的 DeerFlow 定时授权测试状态，记录当前 126/126 组合回归；更新 IAM 迁移 head `0027`、本机开发库 `0021`、API readiness 503 的核验结果。
- 对齐 PRD、平台 README、前后端指南、架构、单系统接入计划和运维手册：当前唯一接入试点是 DeerFlow；已撤销的 AI Resume/Knowledge Base IAM 专属集成只作历史信息；隔离测试结果不代表开发库迁移或真实联调完成。
- 本次仅修改文档，未启动/重启服务、修改凭据或执行数据库迁移。

## 2026-10-10 · DeerFlow 后台定时任务即时重新授权

- 将 Central IAM 授权延伸到定时任务后台：新 occurrence 入队前和 durable queue 启动前重新加载 active 用户、当前路由权限与本人 data_scope；Central IAM 模式从匹配同一本地用户/provider/issuer/subject 的 token vault session 获取短期 capability。
- 账号禁用、会话不可用或 grant/data_scope 拒绝时暂停任务并取消等待 occurrence；Agent run 的 owner identity、AuthContext 和 IAM capability 仅存在于本次内存 request/RunContext，不写入调度任务或 checkpoint。手动触发将 denied 结果映射为 403/503。
- 新增派发通过/拒绝、队列撤权、精确 vault 身份选择和触发错误回归；调度、vault、路由与授权 resolver 组合测试通过 126/126。Ruff check 通过，配置格式检查通过 9 个文件，10 个 Python 文件 AST 解析通过。token-vault 模块的 Ruff formatter 仍报告本轮前已有的格式差异，本轮没有重排无关加密代码。IAM/DeerFlow migration、Compose 和真实 IAM E2E 未执行。

## 2026-10-10 · DeerFlow 定时任务 API 数据范围

- 为任务列表/详情、创建/修改、暂停/恢复、手动触发、删除和运行历史增加 Central IAM self data_scope 校验；保持本地 `user_id` repository 过滤，任务删除改用 `threads:delete`，运行历史要求 `runs:read`，复用会话前检查 `threads:read`。
- 增加范围拒绝在仓储查询/写入前短路的定向回归。Docker Desktop Linux engine pipe 当前不可用，pytest 未能启动；Python AST 解析与 Ruff check/format 通过。IAM UI 和数据库未改，未执行 migration。后台自动调度尚未实现未来触发时 grant 撤销复核。

## 2026-10-10 · DeerFlow 项目与资料数据范围写入闭环

- 项目创建、编辑、归档、恢复和文档上传/提升/恢复在持久化前校验 `projects:write` 与完整响应所需的 `projects:read`；文档软删除、回收站单项/批量清理和保留期清理校验 `projects:delete`；会话文件提升/挂载同时校验 `threads:read/write`。所有仓储写操作显式传入当前本地用户 ID，继续与 DeerFlow owner 过滤相交。
- `require_permission(..., owner_check=True)` 现在还会在本地 owner 校验后、handler 前检查线程 `write/delete` 与运行 `create/cancel` data_scope；运行创建不传不存在的 run ID，取消操作按 run ID 检查。鉴权回归 101/101，组合 owner-bound 路由选择 532 项通过、1 个公网 DNS 测试在离线容器中排除；Ruff 通过。Windows 本机 venv 导入 OpenAI/Pydantic 时发生 Python access violation，测试改在容器内验证。
- 同步更新 README、PRD、前后端说明、总体架构、接入计划、待提供清单、启动指南与 `iam-project` Skill。未启动 Compose、连接真实 IAM 或迁移 IAM/DeerFlow 数据库；项目级其它写资源范围和真实浏览器验收仍待完成。

## 2026-10-10 · DeerFlow Gateway 镜像构建验收

- 根 .dockerignore 排除 pytest、ruff、mypy、hypothesis 生成缓存，解决 Docker 无法读取 backend/.pytest_cache 时构建上下文失败；成功构建 deer-flow-dev-gateway:latest。
- 使用 network none 的一次性容器成功导入 deerflow.authz.iam_deerflow、app.gateway.authz 与 app.gateway.routers.agents，验证 adapter 和鉴权路由已打包进 Gateway workspace 镜像。
- 未启动 DeerFlow Compose 服务、未迁移 DeerFlow/IAM 数据库；IAM 开发库仍为 0021，API readiness 仍为 database_migration_pending。
## 2026-10-10 · 宿主机运行状态复核

- Docker 容器健康状态仍为 API unhealthy、console/PostgreSQL healthy。宿主机绕过 HTTP 代理后直连 127.0.0.1:5175 和 API 根路径 127.0.0.1:8002 均返回 HTTP 200；/api/v1/ready 返回 503 database_migration_pending。
- 根因仍是 IAM 开发库 revision 0021_resume_wallet_perms 落后源码 head 0027_deerflow_resource_permissions。本轮未执行 migration；完成升级仍需受保护备份和明确维护窗口授权。
## 2026-10-10 · 注册迁移影响审查

- 只读审查 IAM migrations 0024/0025：0024 会清空并删除旧注册 challenge 暂存密码摘要列；0025 会将未消费的旧邮箱 OTP challenge 标为已消费，用户需要重新发起邮箱验证。
- 未执行 migration；目标开发库仍为 0021_resume_wallet_perms。升级前须提供受保护备份目录并明确批准维护窗口。
## 2026-10-10 · DeerFlow Agent 与记忆权限目录

- **本轮只读运行核验（2026-10-10）：** IAM Compose 的 API unhealthy、console/PostgreSQL healthy；IAM 开发库为 0021_resume_wallet_perms，源码 head 为 0027_deerflow_resource_permissions，API readiness 返回 HTTP 503。DeerFlow 开发 Compose 当前没有运行；其 Alembic 源码 head 为 fd_0027_repair_run_change_seq（父版本为 0026_iam_oidc_token_vault），目标数据库版本尚未核验。本轮未启动服务、迁移数据库或修改环境凭据。
- **本轮隔离验证（2026-10-10）：** verify-local.ps1 的后端完整套件从空测试库迁移到 IAM 源码 head 0027 后 161/161 通过；console 镜像内 vue-tsc -b 与 Vite production build 通过。复查开发库仍在 0021_resume_wallet_perms，临时 iam_test_* 数据库数量为 0；此验证未迁移开发库，也未恢复 API readiness。

- IAM 新增 append-only migration `0027_deerflow_resource_permissions`，登记 `deerflow.agent.read/write/delete/admin` 与 `deerflow.memory.read/write/delete/admin`；不自动 grant，也未迁移数据库。
- DeerFlow 自建 Agent API 增加读写删权限及匹配的本人 data_scope 检查；完整 Agent 响应的写接口额外要求 read。部署共享 `USER.md` 使用独立 `agents:admin`，PAT 路由不包含该接口。
- 修正 DeerFlow IAM 示例使用 origin，补齐 Agent/记忆 permission map。DeerFlow adapter/client 已在 harness 包内；目标镜像构建、部署和在线联通仍待验收。
- 最近只读 Docker 检查：API unhealthy、console/PostgreSQL healthy；PostgreSQL revision `0021_resume_wallet_perms`，IAM 源码 head `0027`。数据库迁移和真实 IAM/browser E2E 仍待维护窗口与外部配置。
- 授权、PAT、`/auth/me` 与 Agent 路由互操作定向回归 **90/90 通过**（1 条 Starlette/httpx 弃用警告）；8 个修改 Python 文件 Ruff check 与 format 通过。Windows 沙箱阻止 asyncio loopback socketpair；在允许本机 socketpair 的进程上下文中完成 pytest。

## 2026-10-10 · DeerFlow 个人记忆授权与数据范围

- DeerFlow Gateway 记忆 API 增加 `memory:read/write/delete/admin` 路由权限；返回完整记忆数据的所有接口（包括写入/删除响应）在访问存储前还要通过 `memory:read` IAM data_scope，配置明细使用 `memory:admin`。
- 扩展 `require_permission` 支持指定 legacy Request 参数名；将 memory 路由逐方法加入 PAT scope 与 allowlist，未知 HTTP 方法继续拒绝。
- 同步 PRD、集成计划、整体/前后端说明、待提供清单与 Skill。未做数据库迁移或修改真实环境凭据。
- 记忆/权限/PAT 回归 118/118 通过，改动文件 Ruff check/format 通过；项目文档/回收站回归在短临时路径下 72 通过、2 跳过。当时 Windows 255-byte 文件名压力用例因 `WinError 3` 未通过，该问题已于 2026-10-12 修复，后端文档路由回归 32/32 通过。

## 2026-10-10 · DeerFlow 资源级过滤隔离与单系统试点顺序

- 修正 `filter_resources` 的实例授权复用边界：未配置资源 resolver 时仍可按 permission code 合并应用级检查；启用 resolver 后逐个候选资源执行在线授权，避免同一 permission code 下一个资源的 allow 被复用到其它 `resource_id`。新增回归验证不同资源得到不同 IAM 决策。
- DeerFlow 同步适配器回归 **18/18**、IAM 数据范围客户端回归 **11/11** 通过。异步用例未验证；未连接真实 IAM/DeerFlow 数据库，也未把 `data_scope` 应用到业务查询。
- 用户确认交付顺序为先完成 IAM 平台，再只接入 DeerFlow 做端到端试点，通过后再决定其它产品；同时移除 AI Resume、Knowledge Base 的产品专属接入代码。外部仓库在当前可写范围之外，且 Git 状态命令被 Windows 拒绝访问，尚未修改这些仓库。本会话 `docker compose ps` 受 Windows 拒绝启动 `C:\Windows\system32\docker` 影响，未实时检查容器或迁移数据库。
- 同步更新 PRD、整体/前后端说明、架构、集成计划、启动指南、Python SDK 和待提供清单。项目 Skill 位于当前只读的 `.codex` 目录，无法同步修改。

## 2026-10-10 · DeerFlow IAM 应用与资源上下文 fail-closed

- DeerFlow Provider 的普通授权与 `data_scope` 响应都必须明确回显服务端配置的精确 `application_id`；缺失或错配时一律拒绝。服务端可配置 `resource_id_resolver` 将可信 ID 传入资源授权和数据范围检查，resolver 配置后缺失或非法 ID 一律失败关闭，不回退为应用级授权。
- 新增应用上下文、资源 ID 透传、非法 ID 和缺少可信 scope context 的回归用例。DeerFlow 适配器同步用例 **17/17 通过**，IAM 授权/数据范围客户端用例 **11/11 通过**。完整异步套件未能在当前 Python runtime 执行：`asyncio.run(asyncio.sleep(0))` 本身挂起；环境没有可用 Ruff 命令。业务 `data_scope` 查询过滤、目标数据库和真实 IAM 验收仍未完成。
- 同步更新 PRD、架构、集成计划、Python SDK、前后端说明及待提供配置清单；未修改 Vue 页面、API schema 或数据库迁移。IAM 项目 Skill 位于当前只读的 `.codex` 目录，本轮无法更新。

## 2026-10-10 · DeerFlow IAM data_scope 查询适配器

- IAM Python SDK 的 DeerFlow provider 新增同步与异步数据范围查询，使用服务器端 OIDC subject 与 token 请求 `include_data_scope=true`，校验非空范围和应用上下文，并在缺失权限、scope、会话或 IAM 服务时失败关闭；Agent 异步路径先复核/刷新 vault capability。
- IAM 数据范围客户端与 DeerFlow 适配器组合回归 **27/27 通过**，两处改动文件 Ruff 检查通过。当前能力只返回 IAM 已验证的范围，不会自动过滤 DeerFlow 业务查询；项目、会话、文件和产品扩展 API 的范围消费、正式 permission map、镜像分发、真实 IAM 联调及目标库验收仍待完成。
- 同步更新 PRD、业务接入计划、待提供配置清单、前后端说明、IAM Skill 和 Python SDK 使用说明；无 UI/API schema/数据库迁移变更，未访问产品数据库或真实 IAM。

## 2026-10-10 · Knowledge Base IAM 集合可见性与统计

- Knowledge Base 新增 `0026_collection_iam_data_scope`，为空集合记录可信 owner/tenant/organization；集合仅在创建者有权或含当前可见文档时展示，文档数、片段数与最新发布时间按当前授权范围聚合。修改/归档集合前验证其全部文档可见，防止通过集合操作影响范围外数据。
- 本次 Knowledge Base IAM/data-scope 完整定向组合 **37/37 通过**、改动文件 Ruff 检查通过；OpenAPI/TypeScript 合约已重生成，contracts typecheck 通过。目标数据库迁移、隔离 PostgreSQL 跨成员用例与真实 IAM/浏览器验收未做；本机 Windows pytest 需允许本地 asyncio socketpair 才能执行。
- 同步 Knowledge Base README/API/执行书及 IAM README、前后端说明、PRD、接入计划、待提供清单与 Skill。

## 2026-10-09 · DeerFlow Agent IAM 授权上下文

- Gateway 鉴权解析出的 repr 脱敏 IAM 凭证现通过不可序列化的 `RunContext` 传入 Agent 后台运行；仅 OIDC subject 一致的 Principal 可以使用该 capability。工具过滤、工具执行与模型选择可在线调用中央 IAM，不把 token 放入 LangGraph config/context 或 checkpoint；任务结束时清理 run-scoped ContextVar。
- DeerFlow 鉴权/vault/Principal/模型定向回归 **91/91**、IAM Python Adapter **13/13**、改动文件 Ruff 检查通过。Windows runner 需将 pytest 临时目录指向 sandbox temp 并允许本机 asyncio socketpair；未连接 IAM 或产品数据库。
- Agent 长任务会复核 vault session（最多 2 秒复核间隔），并在 access token 临近过期时行锁刷新；本地登出删除 vault 行后，后续授权清空该 run capability 并失败关闭。Knowledge Base/DeerFlow `data_scope` 行级过滤、上游 IAM revoke、DeerFlow 目标镜像 adapter 分发、真实 IAM/OIDC 联调和 migration `0026` 目标库验收仍待完成。

## 2026-10-09 · DeerFlow Gateway 请求级 IAM 鉴权接通

- DeerFlow 请求级 route permissions、model catalog 与 sandbox-sync authorization 现从签名本地 session `sid` 读取 encrypted token vault；IAM SDK Adapter 通过 repr 脱敏 Mapping 获取 access token，临近过期时执行 refresh grant 与 session 行锁密文轮换。Token 不进入 LangGraph config 或 checkpoint。
- DeerFlow 定向鉴权/vault/model 测试 62/62、IAM SDK adapter 测试 11/11、Ruff 通过。没有执行 IAM/DeerFlow 产品数据库迁移、真实 IAM 请求或 OIDC 浏览器流程。
- DeerFlow Agent 的模型与工具 IAM 在线授权现已通过 run-scoped capability 接入；长任务 refresh 已在后续增量实现并由 DeerFlow 91/91、SDK 13/13 回归验证；data_scope、远程 revoke、SDK adapter 镜像分发、真实 IAM 互操作和 migration `0026` 目标库验收仍未完成；同步 PRD、架构、接入计划、用户清单、README、Skill 与 DeerFlow 文档。

## 2026-10-09 · DeerFlow OIDC refresh rotation primitives

- DeerFlow `OIDCService.refresh_tokens()` now submits standards-based refresh-token grants using the configured client authentication method, validates token fields/lifetimes, and never includes provider response bodies in refresh errors. Token-bearing result reprs are redacted.
- `IamTokenVaultRepository.load_or_refresh_for_identity()` holds the per-session row lock while refreshing, encrypts both replacement tokens before writing, preserves an unchanged refresh token when the provider omits rotation, and rejects stale refresh or mismatched OIDC identity. It is called by request-level Gateway IAM authorization; Agent runs now receive the resolved access token in an ephemeral capability but do not refresh it during a long-running task.
- DeerFlow focused OIDC/vault tests passed **31/31** and Ruff passed. No migration, live IAM request, or product database access was performed. Synced PRD, integration plan, architecture, backend/front-end notes, Skill, and changelogs.

## 2026-10-09 · DeerFlow IAM OIDC token vault 首版

- 为 DeerFlow 显式 IAM OIDC Provider 增加 AES-256-GCM token vault；要求 `offline_access` 与后端 Base64 32 字节密钥 `DEERFLOW_IAM_TOKEN_ENCRYPTION_KEY`。每次登录有独立本地 session `sid`，vault 主键为 `(user_id, session_id)`，加密 AAD 绑定 issuer、sub、tenant、sid 和 token purpose，避免并发登录覆盖各自 refresh token；签名 JWT 只携带不含凭据的 `sid`，登出删除对应本地 vault 行。
- 增加 DeerFlow Alembic `0026_iam_oidc_token_vault`，更新 OIDC Provider 配置、JWT/session 生命周期及迁移测试；通用 OIDC Provider 默认不保存 token。迁移只加入 DeerFlow 源码，未对用户产品数据库执行。
- DeerFlow auth/OIDC/vault/migration 定向测试 **123/123 通过**，Ruff 检查通过。IAM refresh rotation/远程撤销、Gateway 每请求在线权限/data_scope、真实 IAM 联调及目标库 migration 仍待完成。

## 2026-10-09 · DeerFlow OIDC 租户声明可信边界

- DeerFlow 回调合并 UserInfo 时固定保留已验签 ID Token 的 `sub` 与 `tenant_id`；若签名 ID Token 未提供 `tenant_id`，则丢弃 UserInfo 中同名值，避免其进入 IAM 授权上下文。
- 新增两条回归覆盖 UserInfo 租户冲突和 ID Token 缺少租户声明的情况；DeerFlow `tests/test_oidc_auth.py` **22/22 通过**。未访问网络或业务数据库。
- DeerFlow 服务端 token vault、IAM refresh rotation 和 Gateway 在线权限映射仍待实现。

## 2026-10-09 · 完整本地验证脚本端到端通过

- 重新执行根目录 `verify-local.ps1`，后端隔离 PostgreSQL 套件从空库迁移至 `0025_registration_role_snapshot` 后 **161/161 通过**。
- Console 镜像通过锁定依赖构建，Dockerfile 中 `vue-tsc -b` 和 Vite production build 成功（3205 modules）。此前 Docker Hub metadata EOF 未在本次重跑中复现。
- 本验证不迁移开发库、不验证真实 SMTP/浏览器注册或生产部署；开发库最近已知版本仍为 `0021_resume_wallet_perms`。

## 2026-10-09 · 复跑 IAM 全量隔离验证

- `verify-local.ps1` API 阶段重建当前 API 开发镜像，并在随机临时 PostgreSQL 数据库从空库迁移至 `0025_registration_role_snapshot`；完整后端 unittest **161/161 通过**。只读复核确认没有遗留 `iam_test_*` 数据库，开发库仍保持 `0021_resume_wallet_perms`。
- 脚本 console 镜像阶段因 Docker Hub 获取 `node:22-alpine` metadata 时返回 EOF 而中止。随后使用本地 console 容器离线运行 `vue-tsc -b` 与 Vite production build，3205 modules、入口 388.34 KB / gzip 120.06 KB；容器内 package/lock/TypeScript/Vite 配置 SHA-256 与工作区一致。
- 未升级开发库、未执行 SMTP/真实浏览器/生产验收。`verify-local.ps1` 可在 Docker Hub 或基础镜像缓存恢复后整套重跑。

## 2026-10-09 · 统一登录节流与审计的可信客户端 IP

- 认证、管理与 OIDC 授权/登出审计事件改为使用与登录失败节流相同的 `client_ip_for_request`；生产仅采信 Caddy 覆写并经私有 Nginx 链路传递的 `X-IAM-Client-IP`，开发环境使用 socket peer。
- 添加 5 个回归用例，覆盖认证/管理/OIDC 授权与登出审计来源及拒绝通用 `X-Forwarded-For`。Docker 一次性 API 容器定向测试 5/5 通过；设置 `IAM_ENSURE_OIDC_KEY=false`，未连接数据库、未迁移或写入业务数据。
- 同步 PRD、整体/前后端说明、架构、运维手册与项目 Skill。生产 CDN/LB 来源解析仍需部署验证。

## 2026-10-09 · 同步注册与联调验证记录（当前）

- 校正用户清单中 DeerFlow OIDC 回归仍未执行的旧记录：mock `test_oidc_auth.py` 已通过 20/20；补充 TypeScript 授权/OIDC 测试 14/14 和 strict TypeScript 检查结果。
- 根 README 将开发库状态更新为源码 head `0025_registration_role_snapshot`、开发库 `0021_resume_wallet_perms`、readiness `503 database_migration_pending`；明确 migrations `0022`–`0025` 尚未应用到开发库。
- 架构/启动/接入文档将“Docker Engine 当前不可访问”改为准确区分：本轮只读 Docker Desktop 检查成功，真实归档恢复演练仍待受保护备份文件；没有执行数据库恢复或迁移。
- 本轮只修正文档；未改业务代码、未运行测试、未写入数据库。

## 2026-10-09 · 校准 IAM 路线图完成度

- PRD 将已实现的会话远程撤销、模型目录/调用授权/额度 API 从“待开发”改为“开发版已具备、真实环境验收待完成”，并细分 Knowledge Base 行级过滤与 DeerFlow 服务端 vault/Gateway 中央权限缺口。
- 同步整体、前后端说明和项目 Skill，明确模型额度默认关闭、生产 Secret Manager/模型代理缺失；隔离 PostgreSQL 156/156 不等于浏览器或业务系统端到端通过。
- 本轮仅校准需求与工程状态文档，未改业务代码、未运行测试或迁移数据库。

## 2026-10-09 · 复核本地 Compose readiness 与迁移状态

- 使用 Docker Desktop CLI 执行只读 Compose 状态、API readiness 和 PostgreSQL Alembic revision 查询：API unhealthy、PostgreSQL 与 console healthy；readiness 为 `503 database_migration_pending`，开发库仍为 `0021_resume_wallet_perms`。没有执行 migration 或数据库写入。
- 更新整体 README、后端说明、PRD、接入计划、用户输入清单和项目 Skill 的运行状态；明确源码 head 为 `0025_registration_role_snapshot`，开发库滞后四个 migration，待备份位置与开发库迁移授权后再处理。

## 2026-10-09 · 为 TypeScript 授权和 OIDC 请求设置超时

- `IamAuthorizationClient` 默认 3 秒；TypeScript OIDC RP 的每个 IAM HTTP 请求默认 5 秒，二者都可配置并由单个 `AbortController` 覆盖响应体读取。超时和网络错误映射为 503，授权 HTTP 拒绝保留状态码；OIDC 授权码兑换和 refresh rotation 不自动重试。
- OIDC RP 校验正数 32 位毫秒超时，并把网络/超时异常映射为 `OIDCProtocolError(503)`。同步 TypeScript/Python SDK 使用说明、整体/前后端文档、接入计划、用户配置清单、PRD、架构和项目 Skill；并把注册 migration head 与验证结果更新到 `0025` / 156 项。未修改 IAM API 契约或数据库。
- 验证：`node --test test/authorization.test.mjs test/oidc.test.mjs` **14/14 通过**；TypeScript SDK `tsc -p tsconfig.json --noEmit` 通过。未做真实 IAM 联调。

## 2026-10-09 · 增加隔离数据库恢复校验脚本

- 新增 `deploy/verify-postgres-restore.ps1`：默认要求备份旁边有 SHA-256 sidecar，校验后把归档恢复至脚本随机生成的隔离数据库，核验 Alembic revision 和 `users`、`tenants`、`applications` 核心表；成功后删除临时库，失败时保留数据库供诊断，并清理容器内临时归档。脚本不以现有业务库作为恢复目标。
- 同步运维手册中的恢复步骤、PRD 部署验收标准、整体架构与 README、前后端说明及 `iam-project` Skill；明确真实备份恢复、API/OIDC 恢复检查仍未验收。
- 验证：PowerShell AST 解析通过；本会话尝试只读 `docker compose ps`，Docker Desktop Linux Engine named pipe 返回 permission denied。未运行真实归档恢复、未创建数据库、未改动现有数据库。

## 2026-10-09 · ToC 注册申请绑定完整授权快照

- 修复默认角色替换、权限目录状态变化、资源级授权增补或数据范围变化后，旧 OTP challenge 仍可能兑换的问题。挑战绑定默认角色 ID 与有效授权指纹；兑换时重算，策略变化即消费挑战并返回统一无效提示。
- migration `0025_registration_role_snapshot` 先消费升级前所有待验证挑战，再增加角色外键、索引和快照约束；不会自动开放注册。
- 添加角色/授权策略变更回归和 migration 索引断言；复核时发现 ORM 漏映射 `verification_code_hash`，已恢复与 `0022` schema 一致的 HMAC 摘要字段。改动 Python 文件 AST 解析通过；完整隔离 PostgreSQL 套件从空库迁移至 `0025` 后 **156/156 通过**，前端 `vue-tsc -b` 和 Vite production build 通过（3205 modules，入口 388.34 KB / gzip 120.07 KB）。隔离 runner 清理了随机测试库；开发库 `iam` 未迁移。
- 同步 PRD、前后端 README、整体 README/架构、待办清单、项目 Skill 与本变更日志；启动命令和部署步骤没有变化。

## 2026-10-09 · 本地启动 readiness 有限重试

- `start-local.ps1` 对启动期的连接异常和 HTTP 502 增加最多 12 次有限重试（请求超时 2 秒、间隔 1 秒）；API 的数据库 503 立即显示稳定错误码，不把 schema 未迁移误判为启动延迟。
- 同步本地启动指南、前后端 README、整体 README/架构、PRD 与 `iam-project` Skill。
- PowerShell AST 语法核验通过；本会话 Docker CLI 被系统拒绝且 localhost 不可达，未做服务运行验收；未迁移数据库。
- 复核确认真实 Docker Desktop CLI 对 `dockerDesktopLinuxEngine` 命名管道返回 permission denied；`localhost:5175`/`8002` 也不可达，因此当前容器状态不可验证。最近成功读取的快照仍是开发库 0021 / 源码 head 0024；未对开发库执行迁移。

