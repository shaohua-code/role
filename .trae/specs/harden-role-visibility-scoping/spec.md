# 角色配置越权可见性收口 Spec

## Why

用户实测反馈：以应用级角色身份操作时，能看到平台的所有角色（含更高级范围）、新建角色可选超管/租户级、配置角色权限的挂码树能看到向上的菜单、给用户分配角色时也能看到所有角色。调查确认其中两处为真实代码缺口（用户组挂角色无秩校验可提权、角色列表 NULL-scope 旁路），其余渠道需按「可见 ⊆ 可授 ⊆ 秩以下」不变量收口并端到端验收。

## 根因调查结论（2026-11-11 代码走查）

| # | 渠道 | 现状 | 结论 |
|---|---|---|---|
| 1 | 用户组挂角色 `GET/PUT /user-groups/{id}/roles` | 仅校验角色租户归属，**无操作者秩过滤/校验** | **实锤缺口**：L3 可见并可挂 super 角色进组，全组成员获超管（提权） |
| 2 | 角色列表 `GET /admin/roles`（`list_roles`） | 秩过滤已存在，但 `or_(Role.scope.in_(allowed), Role.scope.is_(None))` 让 NULL-scope 存量行绕过；响应 `scope_label` 按推导显示「租户级」 | **实锤缺口**：应用级操作者可见全部 NULL-scope 存量角色（观察「看到所有角色」的最可能根因） |
| 3 | 挂码树 `/admin/permissions/tree` + 挂码弹窗 | 后端按操作者可授集截断（非 L1=持有节点并集）；弹窗树按**操作者**维度，未按**被配角色范围**过滤——配置应用级角色时树里出现租户级/超管节点（禁用或自动调升） | 需按用户决策收口：**向上的菜单按角色范围直接不可见**（取代禁用+自动调升交互） |
| 4 | 新建/克隆角色 scope 选项 | 前端下拉按 `capabilities.scope` 秩过滤、后端 `ensure_scope`/`assert_actor_can_manage_role` 双守 | 防线已在，列端到端验收固化（不新增改动，验收不通过再补） |
| 5 | 用户绑角色 / 邀请选角色 | 后端 `ensure_scope(effective_role_scope(role))` 已守；下拉复用 `/admin/roles?limit=500` 字典 | 随 #2 修复自动收口 |
| 6 | 存量 `roles.scope` 空值 | 未回填，推导口径散落各查询 | 用户已授权回填（需受保护备份） |

## What Changes

- **后端·用户组角色秩守卫（R1，最高优先）**：`GET /user-groups/{id}/roles` 候选列表按操作者范围秩过滤（`effective_role_scope(role)` 秩 ≤ 操作者秩，租户边界不变）；`PUT` 逐角色 `ensure_scope(actor, effective_role_scope(role))`，越秩返回 403（与 users/invitations 同口径）。
- **后端·角色列表 NULL 旁路修复（R2）**：`list_roles` 移除 `Role.scope.is_(None)` 旁路，空值行改按 `effective_role_scope` 推导口径过滤（SQL 侧用模板 key / application_id 等价条件表达）。
- **后端·存量回填迁移（R3，已授权）**：回填 `roles.scope` 空值 = `effective_role_scope` 推导值（模板 key → TEMPLATE_ROLE_SCOPES；钉应用 → app；其余平台角色 → tenant）；执行前受保护备份（遵循部署与运维手册的备份门禁）；回填后 `list_roles` 查询简化回 `Role.scope.in_(allowed_scopes)`。
- **前端·挂码树按角色范围过滤（R4）**：`RolePermissionGrantModal` 树渲染增加角色维度过滤——节点（菜单/按钮）的 `min_scope`（菜单用自身、按钮优先 `button_scopes`）秩 **> 角色当前范围秩时整个节点不渲染**（对包括超管在内的所有操作者一致）；角色范围下拉变更时树联动收放，调低范围自动剔除超出新范围的已勾选项并 toast 提示移除数量。
- **前端·交互简化（R5）**：移除上一轮引入的「勾选自动调升范围」（`maybeRaiseScope`）、「范围缺口告警」（`scopeShortfall`）与节点「需租户级范围」提示——树按范围过滤后不存在范围缺口；`minScopeUnreachable`/禁用逻辑一并移除（可见即可勾）。保留按钮级 `button_scopes` 精确映射（过滤的数据源）。
- **不变式（验收总纲）**：任意操作者在任意角色配置入口可见/可选/可授的集合 ⊆ 操作者范围秩以下的角色 ∩ 自身数据边界，且挂码树可见节点 ⊆ 被配角色范围可达节点。

不涉及 **BREAKING** API 变更；`button_scopes` 为上一轮已上线的加法契约字段，继续沿用。

## Impact

- Affected specs: 无既有 spec 变更；与 `.trae/specs/globalize-platform-roles`（平台角色全局化）、`implement-permission-governance`（配权治理）互补，均为其安全收口深化。
- Affected code:
  - 后端：`backend/app/api/v1/admin/groups.py`（list/replace group roles）、`backend/app/api/v1/admin/access_control.py`（`list_roles`）、`backend/app/services/rbac_guards.py`（如需抽取推导过滤 SQL 助手）、数据库迁移脚本（新增，roles.scope 回填）
  - 前端：`frontend/src/components/RolePermissionGrantModal.vue`（树过滤 + 交互简化）
  - 文档：`docs/产品需求.md` 验收条件同步、`CHANGELOG.md`、`docs/部署与运维.md`（迁移与备份记录）

## ADDED Requirements

### Requirement: 用户组角色挂载的秩校验
系统 SHALL 在用户组角色候选列表与替换写入两处强制「范围只能向下」：候选列表仅含 `effective_role_scope` 秩 ≤ 操作者范围秩的角色；替换写入时对每个请求的角色执行 `ensure_scope`，操作者范围秩低于角色范围秩时返回 403。

#### Scenario: 租户级管理员挂超管角色进组被拒
- **WHEN** L3 租户管理员调用 `PUT /user-groups/{id}/roles`，body 含任意 scope=super 的角色 id
- **THEN** 返回 403（提示不能绑定高于自己授权范围的角色），组成员有效角色不变，审计记录该拒绝不产生（沿用现有失败不审计口径）

#### Scenario: 候选列表不出现向上角色
- **WHEN** L3 租户管理员打开用户组「分配角色」弹窗
- **THEN** 候选列表不含 scope=super 的角色（含 NULL-scope 平台角色按推导口径）

### Requirement: 角色列表无 NULL-scope 旁路
系统 SHALL 对 `roles.scope` 为空的存量行按 `effective_role_scope` 推导口径参与秩过滤：操作者可见集合 = 推导范围秩 ≤ 操作者范围秩的角色；且提供回填迁移消除空值（回填后查询按 scope 列直滤）。

#### Scenario: 应用级操作者不可见推导租户级角色
- **WHEN** 仅持有 scope=app 角色的操作者请求 `GET /admin/roles?limit=500`
- **THEN** 响应不含推导范围为 tenant/super 的角色（无论 scope 列是否为空）

#### Scenario: 回填迁移幂等且留痕
- **WHEN** 执行回填迁移（执行前已完成受保护备份）
- **THEN** 全部 `roles.scope` 空值被填为 `effective_role_scope` 推导值，重复执行零变更，迁移记录写入部署文档

### Requirement: 挂码树按角色范围收口
配置角色权限弹窗 SHALL 按「被配角色有效范围」过滤挂码树：节点授权下限（菜单自身 `min_scope`，按钮优先 `button_scopes`，缺省回落菜单值）秩高于角色当前范围秩的节点不渲染；角色范围下拉变更时树联动，范围调低时自动剔除超出新范围的已勾选项并提示移除数量。

#### Scenario: 配置应用级角色不见向上菜单
- **WHEN** 超管打开一个 scope=app 角色的「配置角色权限」弹窗
- **THEN** 树中不出现 `menu.organization_workspace`（租户级）等下限高于应用级的菜单及其按钮；「用户管理」「应用工作台」等应用级可达节点正常可见可勾

#### Scenario: 范围调低联动剔除
- **WHEN** 在配置弹窗中把授权范围从「租户级」调低为「应用级」，且已勾选「组织写操作」（需租户级）
- **THEN** 树收窄且该勾选被自动移除，toast 提示移除数量；保存负载不含超范围节点

### Requirement: 角色配置四渠道端到端验收
以上修复 SHALL 用一个纯应用级测试账号（仅绑定 scope=app 自定义平台角色）端到端实测四个用户观察渠道并全部通过：角色列表无向上角色、新建角色范围下拉仅「应用级」、挂码树无向上菜单、用户分配角色下拉无向上角色。

#### Scenario: 纯应用级账号四渠道复测
- **WHEN** 以纯应用级测试账号登录管理台并逐一访问角色列表、新建角色弹窗、挂码弹窗、用户分配角色弹窗
- **THEN** 四个界面均不出现任何范围秩高于「应用级」的角色、范围选项或菜单节点

## MODIFIED Requirements

### Requirement: 挂码弹窗范围交互（取代 2026-11-11「勾选自动调升范围」）
挂码弹窗 SHALL 取消「勾选自动调升范围」与「范围缺口告警」交互：树节点可见性由角色范围唯一决定（见上），可见节点不再存在范围缺口；保留两段保存（先 PATCH 角色范围再替换授权）与「先预览再保存」流程；`button_scopes` 按钮级下限契约继续作为过滤数据源。

#### Scenario: 交互回归
- **WHEN** 在配置弹窗中勾选任意可见节点
- **THEN** 不再触发范围自动调升 toast；节点勾选即刻稳定生效于预览与保存负载
