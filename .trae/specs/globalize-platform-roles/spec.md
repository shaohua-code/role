# 平台角色全局化（角色与租户解耦）Spec

## Why

现模型中平台角色按租户各存一份（`roles.tenant_id` 必填、绑定要求角色与成员同租户），导致：用户绑定了租户 A/B，但「租户管理员」角色只作用于角色挂的那个租户——与用户心智模型冲突。用户裁决：**角色不跟着租户走；角色 = 菜单/按钮配置 + 授权范围（全局一份）；数据边界完全由用户绑定的租户/应用决定**（绑了哪些租户，租户级权限就作用到哪些租户）。另发现两个伴生缺陷：租户级管理员的 `capabilities.tenants` 未排除平台管理租户（平台租户身份会把「平台管理租户」带进租户工作台，组织/用户/应用因此看似全空）；前端 slug 未透传导致 `slug !== 'platform'` 排除失效。

## What Changes

- **BREAKING（数据模型）**：平台类角色（`application_id IS NULL`）全局唯一一份，统一宿主在平台管理租户（`tenant_id=platform`）；业务租户中不再存放平台角色。角色配置 = 菜单/按钮树 + 授权范围（`scope`），与租户无关。
- **BREAKING（绑定语义）**：`RoleBinding` 放宽「角色必须与成员同租户」校验——平台角色可绑定到任意租户的成员（绑定表达「用户 X 在租户 Y 下持角色 R」）；应用类角色（钉应用）仍要求应用与成员租户匹配（业务侧本轮不动）。
- **生效计算**：直连绑定的平台角色跨租户全局生效；应用角色仍限成员所在租户；用户组继承语义保持组所在租户。数据边界算法不变（超管全域 / 租户级=操作者绑定的全部租户 / 应用级=操作者绑定的全部应用）。
- **模板供给**：`tenant.admin` / `app.admin` / `app.member` 模板不再按业务租户预置副本——租户开通时幂等确保全局一份 `tenant.admin`；`app.admin`/`app.member` 仍钉应用（每应用一份，业务侧语义不变）。
- **平台租户隔离（伴生修复）**：`capabilities.tenants` 排除平台管理租户（租户级管理员不进平台租户工作台）；用户创建/成员绑定禁止把业务成员挂进平台管理租户（仅超管可为平台租户增删成员）。
- **前端**：新建角色弹窗移除「所属租户」必选项（保留授权范围/名称/说明/权限树）；角色列表去掉租户维度展示（标「全局」）；用户配角色的候选角色列表不再按租户过滤（全局平台角色 + 对应租户的应用角色）；`tenantRowFromCapabilities` 透传 slug（防御平台租户混入）。
- **迁移 `0007_globalize_platform_roles`**：把存量业务租户中的平台类角色合并到平台租户宿主——同 key 合并为一份（授权并集、绑定迁移、保留首份元数据），应用类角色不动；迁移前需受保护备份与用户授权。

## Impact

- Affected specs: `implement-permission-governance`（F1–F8 治理项继续有效，判权口径被本 spec 部分替换）；`segregate-platform-tenant`（防呆保留并扩展到成员绑定）
- Affected code:
  - 后端：`models/authorization.py`（无结构变更，语义收紧）、`services/effective_roles.py`（全局直连生效）、`services/rbac_guards.py`（bind 校验放宽、capabilities 排除平台租户）、`services/role_provisioning.py`（模板全局化）、`services/role_bindings.py`/相关校验、`api/v1/admin/access_control.py`（角色 CRUD/绑定/候选列表去租户维度）、`api/v1/admin/users.py`（平台租户成员防呆）、`db/seed_greenfield.py`、`migrations/versions/0007_globalize_platform_roles.py`
  - 前端：`views/roles/RoleManagement.vue`（新建弹窗去所属租户、列表列）、`components/RolePermissionGrantModal.vue`（去租户入参）、`App.vue`（slug 透传、绑定候选）、`components/RoleMembersModal.vue` 等绑定入口
- 明确不做：应用工作台业务侧（应用角色/资源树/数据叶子）；用户组继承语义变更；OIDC 签发逻辑变更（`authorized_role_ids_statement` 消费方行为由测试保障）

## ADDED Requirements

### Requirement: 平台角色全局唯一

平台类角色（`application_id IS NULL`）在系统中每 key 仅一份，宿主于平台管理租户；创建平台角色不需要选择所属租户。

#### Scenario: 超管新建全局角色
- **WHEN** 超管在平台角色页新建角色（不出现「所属租户」字段，填名称/授权范围/勾选菜单按钮树）
- **THEN** 角色落库 `tenant_id=平台管理租户`、`application_id=NULL`，列表中该角色不再显示租户归属

#### Scenario: 租户级管理员可配全局角色
- **WHEN** 租户级管理员新建自定义角色（授权范围仅租户级/应用级可选）
- **THEN** 角色同样全局宿主，且在其数据边界内的任意绑定租户生效

### Requirement: 绑定解耦（数据边界=用户绑定）

平台角色绑定到成员时不再校验角色与成员同租户；用户在哪些租户有活跃成员身份，其平台角色的数据边界就覆盖哪些租户（租户级）或哪些应用（应用级）。

#### Scenario: 一个角色管多个绑定租户
- **WHEN** 用户 X 绑定租户 A、B（TenantMembership active）并持有全局「租户管理员」角色
- **THEN** X 的租户列表/组织/用户/应用/审计等数据范围同时覆盖 A 与 B，无需再按租户分别绑定角色

#### Scenario: 应用角色保持同租户约束
- **WHEN** 尝试把钉在租户 A 应用上的应用角色绑定到租户 B 的成员
- **THEN** 拒绝（422，应用角色必须与成员同租户且应用匹配）

### Requirement: 平台管理租户对租户级管理员隔离

`capabilities.tenants` 不包含平台管理租户（除非操作者是超管）；业务成员不可被绑定进平台管理租户。

#### Scenario: 租户级管理员不进平台租户工作台
- **WHEN** 仅在业务租户有成员身份的租户级管理员读取 capabilities
- **THEN** `tenants` 数组不含平台管理租户，组织/用户/应用工作台只出现其绑定租户的数据

#### Scenario: 业务成员禁止挂平台租户
- **WHEN** 创建用户/邀请/角色绑定把成员落到平台管理租户（操作者非超管）
- **THEN** 拒绝（422，平台管理租户为系统保留租户）

## MODIFIED Requirements

### Requirement: 生效角色计算（effective_roles）

直连 `RoleBinding` 的平台类角色全局生效（不按 `role.tenant_id` 过滤成员租户）；应用类角色仍要求与成员租户一致；用户组继承的角色仍经活跃组通道生效（组在租户内）。`operator_scope` / `list_actor_management_tenant_ids` / `list_actor_visible_application_ids` 数据边界算法不变。

### Requirement: 模板角色供给（role_provisioning）

`tenant.admin` 全局一份（租户开通/种子幂等确保，不再每租户副本）；`app.admin` / `app.member` 仍按应用预置（钉应用，业务侧不变）；`platform.admin` 种子宿主不变。

## REMOVED Requirements

### Requirement: 平台角色按租户各存一份
**Reason**: 与「角色=功能配置、边界=用户绑定」的心智模型冲突，导致租户级管理员看不到自己绑定租户的数据。
**Migration**: 迁移 `0007_globalize_platform_roles` 把业务租户中的平台类角色合并到平台租户宿主（同 key 合并授权并集、绑定迁移），应用类角色与全部业务侧数据不动。
