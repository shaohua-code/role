# 权限闭环治理实施 Spec（基于 docs/prototypes/permission-governance/PRD.html）

## Why

权限治理 PRD（F1–F8）已评审基线：模型语义（五级模板 / 27 接口码 / 四类树 / 三层配权 / 看得见才能配）不推翻，「乱」来自实现层 16 处双轨与漂移（E1–E16）。本 spec 把 PRD 落成代码：单一口径 + 一致性体检 + 排障链路。

## What Changes

- **F1 权限体检页（P0）**：新增「高级管理 → 权限体检」（新菜单码 `menu.permission_health`，种子仅授 L1）。后端 `GET /admin/permissions/health` 输出 H1–H7 七项检查（H1 菜单-接口对齐=阻断；H2 按钮映射唯一性；H3 模板回退残留；H4 数据范围双轨；H5 未挂载码；H6 计数一致性；H7 孤儿码；H8 判权写法以「静态保障」标注呈现，由 F7 落地后置为通过态）。页面含三卡统计 + 检查项列表 + 详情抽屉 + 「立即复检」。
- **F2 码表契约单一来源（P0）**：后端 `permission_kinds.py` 为唯一源。`button.roles.manage` 映射收敛为仅 `rbac.role.manage`（org 归 `button.org.manage`）；`GET /admin/permissions/tree` 响应扩展下发「菜单→按钮→接口映射、层级可见码集、模板码数」，前端删除 `permissionTree.ts` 的 MENU_RELATED_APIS / BUTTON_RELATED_APIS / MENU_BUTTONS / MENU_GROUPS 与 `permissionGroups.ts` 的 PLATFORM_SCOPE_CODES / TENANT_SCOPE_CODES 硬编码，改为消费接口数据；RoleManagement 统计文案（27/20/16/15）改由契约常量渲染；`grant_codes_skip_missing` 缺码不再静默（报错 + 体检可见）。
- **F3 判权口径收口（P0，迁移窗口内）**：`ensure_codes` 的 `role_keys` 回退**本窗口不移除**，改为命中即计数 + WARN 日志，计数进体检 H3；敏感码双检从单码扩为统一清单；绑定豁免收紧（已存在绑定同样走判权校验；`grantable=None` 改为调用方必须显式传参，L1 传全量）。回退下线为后续决策（PRD TBD），不在本次。
- **F4 数据范围收口（P0，代码就绪）**：恢复数据范围写分级（写操作需 `org.manage` 且 L3 起，L2 只读，删除 `del manage` 写法）；数据范围替换接口增加向数据叶子码授权的双写（过渡期）；`evaluate_access` 维持「叶子码 ∪ RoleDataScope」双读不变（生产切换与存量迁移执行需数据库授权，不在本次）；体检 H4 输出「仅旧表未映射」行数。
- **F5 挂码缺口阻断（P1）**：挂码弹窗勾选 `menu.*` 而其映射接口码未全勾时，「保存授权」置灰并列出缺失码清单；提示与体检 H1 同判定。纯前端（映射来自 F2 的 tree 数据）。
- **F6 排障链路（P1）**：体检页第二 Tab「成员与生效」：按用户 + 租户上下文展示 有效角色（直绑/组继承来源）→ 持码按四类分组 → 对指定菜单的命中判定（放行 / 缺哪些接口码）。后端新增只读聚合端点（复用 effective_roles / holders 逻辑，不新建判权路径）。可见性仅 L1。
- **F7 前端判权统一（P1）**：新增 `hasMenu(code)` / `hasButton(code)` 统一工具（内部含 L1 放行语义），替换全部 `platform_admin && hasAny(...)` 双轨写法；API 前缀常量化（删除 `/tenant-admin` 硬编码）；`/applications` 等重定向去重注册；`PAGE_INFO` 清理已收口键。
- **F8 死代码与旧词清理（P1）**：删除 `ensure_management_permission` 整段及旧码映射表；`infer_permission_kind` 收敛为「库列为准、前缀仅迁移兜底」；清理 iam.* / super_admin 旧词文案与「四级管理员」表述；删除 P390 向导死 CSS。

- **BREAKING（后端契约）**：`GET /admin/permissions/tree` 响应新增字段（meta：层级码集、模板码数）；消费方仅本仓库前端。
- **BREAKING（行为）**：绑定豁免收紧后，此前「已存在绑定不再校验」的调用若传参不合法将从静默通过变为 403——属 PRD D2/F3 裁决的预期修正，配套测试覆盖。

## Impact

- Affected specs: 无既有 capability spec；本 spec 自成能力域 `permission-governance`
- Affected code:
  - 后端：`backend/app/services/permission_kinds.py`、`rbac_guards.py`、`role_provisioning.py`、`seed_greenfield.py`、`api/v1/admin/access_control.py`、`api/v1/admin/organizations.py`（数据范围写分级）、`api/v1/authorization.py`（不动双读）、`migrations/`（仅新增 `menu.permission_health` 种子，无结构迁移）
  - 前端：`frontend/src/utils/permissionTree.ts`、`utils/permissionGroups.ts`、`api/capabilities.ts`、`router/index.ts`、`router/navigation.ts`、`views/permissions/PermissionCatalog.vue`（可选复用树组件）、`components/RolePermissionGrantModal.vue`、`views/roles/RoleManagement.vue`、新增 `views/permission-health/`（体检页）、RoleMembersModal / RolesTab / ApplicationMoreHost / OrganizationMoreHost / ApplicationPermissionPanel 等判权调用点
- 明确不做：执行 RoleDataScope 存量迁移（需授权）；下线 `ensure_codes` 回退（迁移窗口观察后决策）；合并两套资源树；审批流

## ADDED Requirements

### Requirement: 权限体检页与体检端点（F1）
系统 SHALL 提供「高级管理 → 权限体检」页面与 `GET /admin/permissions/health` 端点，服务端运行 H1–H7 七项一致性检查并返回结构化结果（状态：阻断/告警/通过/提示；详情含受影响角色、成员计数、缺失码清单）。页面 SHALL 展示阻断/告警/通过三卡统计、检查项列表、详情抽屉与「立即复检」。页面与端点 SHALL 仅 L1 可见可用（菜单码 `menu.permission_health` 仅授 L1 种子；端点校验平台管理员）。

#### Scenario: 存在菜单缺接口的角色
- **WHEN** 某角色持 `menu.users` 但缺其映射的 `platform.account.read`
- **THEN** H1 状态为阻断，详情列出角色名、缺失码、影响成员数，并给出「走挂码链路修复」的指引

#### Scenario: 全部通过
- **WHEN** 七项检查均无发现
- **THEN** 页面显示 0 阻断 0 告警，各检查项为通过态

#### Scenario: 非 L1 访问
- **WHEN** L3/L2 用户直接调用体检端点或深链页面
- **THEN** 返回 403 / 跳转无权限页

### Requirement: 成员与生效排障链（F6）
体检页 SHALL 提供「成员与生效」Tab：输入用户 + 租户上下文后，展示有效角色（标注直连绑定 / 组继承来源）、按四类（菜单/按钮/接口/数据）分组的持码清单、以及对所选菜单码的命中判定（放行或缺失接口码列表）。

#### Scenario: 排查「看得见进不去」
- **WHEN** 选择持有 `menu.users` 缺 `platform.account.read` 的用户
- **THEN** 链路展示该角色来源（直绑/组继承）、持码分组、并明确指出缺失的接口码与对应体检项 H1

#### Scenario: 多角色并集
- **WHEN** 用户同时持直连角色与组继承角色
- **THEN** 持码为并集且每个角色标注来源

### Requirement: 挂码缺口阻断（F5）
挂码弹窗 SHALL 在勾选任一 `menu.*` 而其契约映射的接口码未全勾时禁用「保存授权」，并列出缺失码清单；补齐或取消菜单码后恢复。阻断判定 SHALL 与体检 H1 同源（同一契约映射）。

#### Scenario: 勾菜单缺接口
- **WHEN** 管理员勾选 `menu.users` 未勾 `platform.account.read`
- **THEN** 保存按钮置灰，展示缺失码清单与「即体检 H1 判定」提示

#### Scenario: 补齐后恢复
- **WHEN** 管理员补勾全部缺失接口码
- **THEN** 阻断提示消失，保存恢复可用

## MODIFIED Requirements

### Requirement: 码表契约单一来源（F2，改造 permission_kinds / tree / 前端映射）
`permission_kinds.py` SHALL 为菜单↔按钮↔接口映射与层级可见码集的唯一权威源；`button.roles.manage` 映射 SHALL 收敛为仅 `rbac.role.manage`；`GET /admin/permissions/tree` SHALL 在响应 meta 中下发层级可见码集与五级模板码数；前端 SHALL 删除 `permissionTree.ts` 四张硬编码映射表与 `permissionGroups.ts` 层级码集硬编码，改为消费接口数据；`grant_codes_skip_missing` SHALL 在契约要求的码缺失时抛错（隔离场景由调用方显式选择跳过并计数）。

#### Scenario: 后端改映射前端同步
- **WHEN** 契约中任一菜单的接口映射变化
- **THEN** 前端目录树、挂码弹窗、体检判定无需改代码即呈现新映射（数据来自 tree meta）

#### Scenario: 模板码缺失
- **WHEN** 种子/开通执行时模板要求存在的码不存在
- **THEN** 流程报错终止而非静默跳过；体检 H6 计数校验同源可发现

### Requirement: 判权回退可观测（F3，迁移窗口内）
`ensure_codes` 的 `role_keys` 回退 SHALL 保留但在命中时递增计数器并记 WARN 日志；计数 SHALL 进体检 H3（回退残留）；敏感码双检 SHALL 覆盖统一「写类按钮码」清单；角色绑定入口 SHALL 取消「已存在绑定直接返回」的豁免，`grantable` 参数 SHALL 为必传显式值。

#### Scenario: 回退命中被记录
- **WHEN** 某用户无所需码但持回退角色 key 并触发 `ensure_codes`
- **THEN** 请求放行（窗口内行为不变）、计数 +1、WARN 日志含用户与码，体检 H3 显示计数 > 0

#### Scenario: 已存在绑定再操作
- **WHEN** 对已持有绑定的用户再次执行绑定/解绑且调用方无判权资格
- **THEN** 返回 403（不再静默通过）

### Requirement: 数据范围写路径与分级（F4，代码就绪）
数据范围替换接口 SHALL 写入数据叶子码授权（与存量 RoleDataScope 双写过渡）；写操作 SHALL 要求 `org.manage` 且 L3 起（L2 只读）；`evaluate_access` 双读行为本窗口不变；体检 H4 SHALL 报告「仅旧表、未映射叶子码」的策略行数。

#### Scenario: L2 尝试写数据范围
- **WHEN** 仅持 L2 应用管理员的用户提交数据范围策略修改
- **THEN** 返回 403；同一用户只读查询正常

#### Scenario: 替换策略生效
- **WHEN** L3 保存某业务码的数据范围
- **THEN** 对应 `*.scope.*` 叶子码授权同步写入，evaluate_access 结果不变（双读并集语义）

## REMOVED Requirements

### Requirement: 前端硬编码权限映射表
**Reason**：与后端契约双份人工同步（E2/E16），是漂移根因。
**Migration**：消费 tree meta（F2）；删除 `permissionTree.ts` 四张表、`permissionGroups.ts` 层级码集硬编码、RoleManagement 统计文案硬编码。

### Requirement: ensure_management_permission 死代码
**Reason**：无调用方的旧码→角色映射器（E6）。
**Migration**：整段删除；全仓 grep 确认零引用。

### Requirement: P390 作用域向导残留与旧键文案
**Reason**：死 CSS 与已收口路由键（E14）、旧词（E15/E8 部分）。
**Migration**：删除 .scope-wizard/.scope-card/.role-kind-filter 死样式、PAGE_INFO 已收口键；iam.*/「四级管理员」旧词改为五级口径；`infer_permission_kind` 收敛为库列优先、前缀仅迁移兜底。
