# 平台租户与业务租户全面区分 Spec

## Why

开发库审计发现 2026-10-27 三次 `tenant.kind.change` 曾把 platform/demo/testdemo1 全改成 consumer，平台引导租户（L1 角色与引导超管的宿主）混入 ToC 消费目录。P381 已做数据归位（platform=organization）、禁切 kind、租户页平台 tag。但「平台租户」作为系统保留租户的边界仍不完整：它仍可被停用（会打断 DeerFlow OIDC 授权与模型用量上报）、仍可在其下创建业务组织/用户组、仍可向其发送业务成员邀请，前端多个创建类下拉也未排除它。

## What Changes

- 后端防呆补齐（slug=platform 一律 422，统一文案口径「平台引导租户为系统保留租户，不支持……」）：
  - `PATCH /admin/tenants/{id}/status`：禁止将平台租户置为 disabled（停用会撤销旗下应用 OAuth 刷新令牌并打断 DeerFlow OIDC/模型用量上报的租户 active 前置）
  - `POST /admin/organizations`：tenant_id 指向平台租户 → 422（平台租户不承载业务组织树）
  - `POST /admin/invitations` 与 `POST /admin/invitations/batch`：tenant_id 指向平台租户 → 422（L1 宿主不走业务邀请流程；重发/撤销/兑换不动）
  - `POST /admin/groups`：tenant_id 指向平台租户 → 422（平台租户权限管理靠角色，不需要业务用户组）
- 前端创建类租户下拉排除平台租户（筛选器保留——平台租户下有真实角色/应用/审计数据）：
  - 组织管理页：租户选择与「新建组织」租户下拉排除平台租户
  - 邀请管理页：「新建/批量邀请」租户下拉排除平台租户；租户筛选器保留
  - 用户组管理页：「新建用户组」租户下拉排除平台租户；租户筛选器保留
- 前端已到位项保持：租户页「平台自有」tag、应用编辑下拉的租户类型后缀（自动显示「组织/企业」）、平台租户操作列隐藏切换/删除
- 明确不做：平台租户承载应用（deerflow/crud-demo 属平台自有应用，语义成立，保留）；角色/权限/审计页的平台租户筛选；testdemo1 等业务租户的 kind

## Impact

- Affected specs: 无既有 spec 依赖；P381 已交付项为本 spec 的前置
- Affected code:
  - 后端：`backend/app/api/v1/admin/tenants.py`（status 保护）、`organizations.py`、`invitations.py`、`groups.py`
  - 前端：`frontend/src/views/organizations/OrganizationManagement.vue`、`frontend/src/views/invitations/InvitationManagement.vue`、`frontend/src/views/groups/GroupManagement.vue`
  - 测试：`backend/tests/`（新增平台租户负路径隔离测试）

## ADDED Requirements

### Requirement: 平台租户不可停用
系统 SHALL 拒绝将 slug=platform 的租户置为 disabled。

#### Scenario: 停用平台租户被拒
- **WHEN** L1 管理员调用 `PATCH /admin/tenants/{platform_id}/status?status=disabled`
- **THEN** 返回 422，文案说明平台引导租户承载系统应用与 L1 宿主不允许停用
- **THEN** deerflow/crud-demo 的 OIDC 授权与模型用量上报不受影响

#### Scenario: 启用幂等
- **WHEN** 对平台租户调用 status=active
- **THEN** 正常返回（幂等，无行为变化）

### Requirement: 平台租户不承载业务组织
组织创建接口 SHALL 拒绝 tenant_id 指向平台租户。

#### Scenario: 平台租户下建组织被拒
- **WHEN** 创建组织时 tenant_id 为平台租户
- **THEN** 返回 422「平台引导租户为系统保留租户，不支持业务组织」
- **THEN** 组织管理页租户下拉不再出现平台管理租户

### Requirement: 平台租户不参与业务邀请
邀请创建（单个与批量）SHALL 拒绝 tenant_id 指向平台租户。

#### Scenario: 平台租户下发邀请被拒
- **WHEN** 创建或批量创建邀请时 tenant_id 为平台租户
- **THEN** 返回 422「平台引导租户为系统保留租户，不支持成员邀请」
- **THEN** 邀请管理页的创建租户下拉不再出现平台管理租户（筛选器保留）

### Requirement: 平台租户不承载业务用户组
用户组创建 SHALL 拒绝 tenant_id 指向平台租户。

#### Scenario: 平台租户下建用户组被拒
- **WHEN** 创建用户组时 tenant_id 为平台租户
- **THEN** 返回 422「平台引导租户为系统保留租户，不支持业务用户组」
- **THEN** 用户组页新建租户下拉不再出现平台管理租户（筛选器保留）

### Requirement: 隔离测试覆盖平台租户负路径
测试套件 SHALL 新增隔离用例覆盖上述四类 422 负路径，且全量隔离套件维持基线（225 过 + 6 已知陈旧失败，P367 基线）。

#### Scenario: 负路径测试全绿
- **WHEN** 在 api 容器运行新增测试模块
- **THEN** 全部通过；既有 50 项（P372 基线）不回归
