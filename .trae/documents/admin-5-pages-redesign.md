# 管理台 5 页面重设计方案（applications / roles / permissions / application-workspace / tenants）

## Context（背景与目标）

用户反馈 5 个管理页面"使用起来不方便"，要求重新规划：表设计、页面交互更便捷，审美提升。已确认：**方案评审后直接改代码，前后端都允许修改**。

### 现状核实（探索 + 规划代理已验证）

| 页面 | 核心痛点 |
|---|---|
| /applications（519 行） | 11 列过宽，回调地址靠 Popover 藏；无搜索/筛选；密钥/受信/状态操作分散 |
| /roles（847 行） | 纯前端过滤；权限数量 tag 只能 tooltip 看全码，不可读；5 个弹窗堆叠 |
| /permissions（407 行） | 统计卡仅 3 张硬编码；域筛选是下拉；"关联角色数"不可点击；登记弹窗无域选择器（域校验仅在后端） |
| /application-workspace（213 行+tabs） | AppTree 已有搜索但组节点无计数；缺应用维度概览统计 |
| /tenants（216 行） | **无搜索无筛选**；6 列信息薄；无下钻；操作仅转类型/停用/删除 |

后端现状：`GET /admin/applications` 仅 `tenant_id` 参数；`GET /admin/roles`、`GET /admin/tenants` 无任何过滤参数；`GET /admin/permissions` 已支持 `catalog_namespace/application_id` 且响应含 `assigned_role_count`。列表均全量拉取（≤500）+ 壳层水合（`hydrateFromShell`）。

## 设计原则（全 5 页统一）

1. **列表页统一信息架构**：统计带（可选）→ 工具条（搜索 + 筛选 + 主操作）→ 表格 → 行点击开详情抽屉
2. **弹窗收敛**：详情/浏览类 → 抽屉（AdminDetailDrawer）；编辑/创建类 → 弹窗；危险操作 → 确认弹窗（文案不动）
3. **严守设计系统**：只用 `styles/tokens.css` 变量（禁止裸 hex）、石墨黑白灰、间距 4 的倍数、动效 ≤200ms、暗色主题适配
4. 筛选保持**前端 computed 过滤**（数据 ≤500，即时无感），后端过滤参数作为轻量增强同批落地
5. 壳层水合机制（`shellCatalogGeneration` 代次）不破坏；双模式 apiPrefix（/admin 与 /tenant-admin）不破坏；L2/L3 数据范围过滤不放松

## 新增通用组件（3 个，`frontend/src/components/`，追加进 index.ts 导出）

1. **AdminStatBand.vue**（从 PermissionCatalog 统计卡抽象）：`defineModel<string>('modelValue')`（''=全部）；props `stats: { key, label, count, sub?, disabled? }[]`、`numbered?`；active 态内嵌 3px 左条 + token 变量
2. **AdminDetailDrawer.vue**：`defineModel<boolean>('open')`；props `title/subtitle?/width?=640/loading?`；插槽 `default/footer/header-extra`
3. **AdminMonoValue.vue**：props `value/copyable?=true/maxWidth?`；mono 字体 + hover 复制图标（`navigator.clipboard` + message.success，逻辑可从 ApplicationManagement.vue L277-280 抽用）

## 逐页改造方案

### 1. /applications — `views/applications/ApplicationManagement.vue`（改动最重）

- **11 列 → 7 列**：应用（名称+说明副行）/ 所属租户 / Client ID（AdminMonoValue）/ 权限命名空间 / 回调（"登录 n · 登出 m"徽标，点击开详情抽屉）/ 状态+受信合并 Tag / 操作（fixed right）
- **工具条**：AdminSearchField（名称/ClientID）+ 租户/状态/受信 Select（前端 computed 过滤，模式照抄 RoleManagement 的 filteredRoles）
- **行点击 → 应用详情抽屉**（AdminDetailDrawer）：基本信息（含 registration_policy）、回调清单（只读）、密钥轮换/受信入口（复用现有 confirm 逻辑）、权限项入口（复用 ApplicationPermissionDrawer）、危险区（停用/删除）
- 所有操作单元格 `@click.stop` 防行点击冲突；一次性密钥弹窗、乐观锁、回调创建后只读规则不动

### 2. /roles — `views/roles/RoleManagement.vue`

- 顶部插入 **AdminStatBand**（平台/租户/应用三卡，v-model 绑定 kindFilter，替换现有类型 Select 主入口）
- 8 列 → 7 列：租户+应用范围合并为"归属"副行
- **权限数量徽标可点击** → AdminDetailDrawer 按域分组展示码清单（复用 resolvePermissionDomain），footer 放"配置权限"按钮（复用 openGrantEditor）；tooltip 全码移除
- 持有者/复制/数据范围/资源授权维持"更多"下拉

### 3. /permissions — `views/permissions/PermissionCatalog.vue`

- `.domain-stats` 段替换为 AdminStatBand（`numbered` 保留账本样式）
- 域筛选下拉 → **多选 chips**（五域色点）
- **"关联角色数"可点击** → AdminDetailDrawer 列引用角色：前端反查（加载 /admin/roles 建 code→roles Map，零后端改动）
- **登记弹窗加"所属域"Select**（来自 utils/permissionGroups.ts 域定义），选域自动补 code 前缀 + 底部实时预览完整码
- 接口类型补 `surface/requires_data_scope` 字段声明

### 4. /application-workspace — `views/application-workspace/index.vue` + `components/AppTree.vue`

- AppTree 租户组节点标题右侧加**应用计数徽标**（搜索已有，不重复做）
- 页头下加**应用概览统计条**：选中应用的角色数/权限码数/资源数（用 Tab 已有端点计数，懒加载缓存一次）

### 5. /tenants — `views/tenants/TenantManagement.vue`（提升最大）

- **工具条**：AdminSearchField + 类型/状态 Select（前端过滤）
- 列收敛：租户（名称+slug mono 副行）/ 类型（平台自有特判保留）/ 成员数（点击开成员抽屉）/ 应用数 / 状态 / 操作
- **行点击 → 租户详情抽屉**：基本信息、统计、该租户应用列表（点击跳应用工作台，`router.push(PAGE_PATHS...)`）、危险区（转类型/停用/删除）
- **成员抽屉**：优先复用 `GET /admin/organizations/members?tenant_id=`（新式分页）；若 L1 守卫不可达则在后端补 `GET /admin/tenants/{tenant_id}/members`
- 平台引导租户（slug=platform）禁删禁切换的特判全部保留

## 后端改动（轻量，独立批次）

1. `backend/app/api/v1/admin/tenants.py` `list_tenants`：加 `q/kind/status` 参数 + `application_count` 聚合（Application 按 tenant_id group by 子查询外联）
2. `backend/app/api/v1/admin/access_control.py` `list_roles`：加 `q/kind/tenant_id/status`；**tenant_id 必须与 tenant_scope 求交集**；顺带修 permission_codes N+1（一次 join 分组）
3. `backend/app/api/v1/admin/applications.py` `list_applications`：加 `q/status/trusted`，在 capability 过滤后、limit 前套用；"非平台管理员必须带 tenant_id"校验（L46-47）不动

## 实施顺序

1. 通用组件 3 个 + index.ts 导出
2. /tenants（最小页面先验证组件）→ /roles → /permissions → /applications → /application-workspace
3. 后端 3 个端点参数
4. 文档同步：`docs/项目总览与进度.md`（分段读，>64KB）、`CHANGELOG.md`、`frontend/README.md`

## 风险点

- 双模式：applications 租户模式逐租户并发请求（L149-157），筛选必须作用于合并后数据；RoleManagement/PermissionCatalog 硬编码 /admin，不加 apiPrefix
- 行点击 vs 操作列冒泡（customRow + @click.stop）
- 暗色主题：新组件只用 token 变量，dark 下走查
- 回归面：一次性密钥弹窗、乐观锁（expected_status/expected_kind）、回调只读、平台租户保护文案不变

## 验证方案

1. `cd frontend && npm run build` 零错误；后端改动跑现有测试/启动自检
2. Chrome DevTools 走查 5 页：统计卡点击筛选/还原；搜索即时过滤；行点击开抽屉且操作按钮不冒泡；ClientID 复制提示；roles 权限抽屉分组正确且能打开授权弹窗；permissions 登记弹窗选域自动补前缀+预览；workspace 统计条计数与 Tab 一致；tenants 成员/应用抽屉数据正确、platform 租户保护生效；375px 移动端；暗色切换；tenant 模式（/tenant-admin）登录回归
