# 方案 A 绿场重建终稿：增强型分层 RBAC + 四级角色

> **选型：** 版本 A（增强型分层 RBAC）  
> **前提：** 允许清空一切存量——数据库、迁移链、旧租户/应用/绑定、业务接入配置；SDK 可 breaking；**不做存量数据迁移**。  
> **范围：** 本文件为实施规格（规格书），代码落地由后续云端 agent 执行。  
> **关联：** 相对 `/workspace/role-iam-deep-refactor-two-versions.md` 中版本 A 的「演进式」表述，本稿改为 **绿场重建**。


> **技术方案包：** 同目录 `00-overview.md` … `10-test-acceptance.md`（架构/模型/时序/API/矩阵/前端/SDK/安全/运维/验收）。  
> 本文侧重产品规则与实施路径清单；细节以分册为准，冲突时 **产品四级与绿场前提以本文 §0–§1 为准**，API/字段以 02/04 为准。

---

## 0. 前提与硬约束

### 0.1 允许丢弃的内容

| 类别 | 处理 |
|------|------|
| PostgreSQL 业务库全部表数据 | DROP / 删卷重建 |
| Alembic 历史 revision 语义 | **允许重写成一条（或少数几条）绿场初始迁移**；旧 migration 文件可归档删除 |
| 租户、应用、用户（除种子超管）、角色绑定、用户组、邀请、OIDC client 密钥、审计历史 | 全部不要 |
| 已接入业务项目的 client_id / redirect / 权限同步状态 | 作废；按新契约重新接入 |
| 前端 local/session 中旧 token 假设 | 忽略；发版后强制重新登录 |
| SDK 旧默认行为（如 data_scope 默认 false 导致「有权无范围」） | 允许 breaking change |

### 0.2 不允许含糊的产品规则

1. **四级写死（称谓顺序按产品）：**
   - **L1** `platform.super_admin` — 超级管理员（平台）
   - **L2** `app.admin` — 应用管理员（单应用）
   - **L3** `tenant.org_admin` — 管理员（单租户组织/成员）
   - **L4** `user`（或应用模板 `app.member`）— 用户（无管理码，可有业务码）
2. **L2 与 L3 互不自动包含**（应用管理员 ≠ 租户管理员）。
3. **L1 覆盖全部管理面权限码**；**不**默认绑定任何业务权限码。
4. **OIDC 入场与 `evaluate_access` 共用「有效角色」**（直连绑定 ∪ 活跃用户组）。
5. **有 bind 必有 unbind**；绑定/组变更必 bump `membership.auth_version`。
6. **管理类写操作必须后端按权限码校验**；前端裁剪不可替代。
7. 绿场后 **禁止** 以「邮箱 == BOOTSTRAP」作为唯一长期超管真相；bootstrap 仅用于 **首次种子** 与可选 **灾备破窗开关**（默认生产关闭）。

### 0.3 非目标（本期不做）

- 不上 SpiceDB / OpenFGA / OPA 作为主判定器。
- 不做跨环境数据搬家、不做双写兼容旧 JWT claim 形态（可直接换 claim 名若需要）。
- 不保留「路由级一刀切 platform_admin 且无权限码」的旧 admin 模型。

---

## 1. 四级语义（实施验收以本节为准）

| 级 | Key | `roles.kind` | 作用域 | 能 | 不能 |
|----|-----|--------------|--------|----|------|
| L1 | `platform.super_admin` | `platform` | 全站 | 所有 `iam.*` **管理面**码；代管任意租户/应用 | 默认无业务码；不能靠邮箱旁路代替角色（破窗除外） |
| L2 | `app.admin` | `application` | `tenant_id` + `application_id` | 该应用 read/manage、应用角色成员、可选 secret.rotate | 跨应用；租户开通；组织/成员/组整盘；平台目录 |
| L3 | `tenant.org_admin` | `tenant` | `tenant_id`，`application_id IS NULL` | 组织、成员、本租户组、数据范围策略；可按 API 权限「任命」L2 | 默认无 secret.rotate；无平台码；不自动成为各应用 L2 |
| L4 | `app.member` 或仅业务角色 | `application` 或业务自定义 | 应用/业务资源 | 被授予的业务权限 + 数据范围 | 任何管理面写能力；无管理台（`no_access`） |

**继承关系（写死）：**

```text
L1 ⊇ (L2 管理能力 ∪ L3 管理能力)     # 仅管理面
L2 ⊄ L3 且 L3 ⊄ L2
L1 / L2 / L3 都不默认 ⊇ 全部业务码（L4）
```

---

## 2. 目标模型

### 2.1 核心表（绿场建议形态）

在现有概念上 **定稿字段**（名称可微调，语义不可少）：

#### `permissions`
| 字段 | 说明 |
|------|------|
| `id`, `code` (unique), `catalog_namespace`, `resource_type`, `scope`, `description` | 同现思路 |
| `status` | `active` \| `disabled` |
| `surface` | `management` \| `business`（绿场直接加，避免管理码与业务码混授失控） |
| `requires_data_scope` | bool；`true` 时判定强制走数据范围，缺策略则拒绝 |

#### `roles`
| 字段 | 说明 |
|------|------|
| `id`, `tenant_id`, `key`, `name`, `description`, `status` | |
| `application_id` | L2/业务应用角色非空；L1/L3 为空 |
| **`kind`** | **`platform` \| `tenant` \| `application`**（绿场必加） |
| 唯一约束 | platform：全局或平台租户内 `key` 唯一；tenant：`(tenant_id, key)` where kind=tenant；application：`(tenant_id, application_id, key)` |

**平台角色归属：** 使用 **专用平台租户**（种子 `tenants.key=platform` 或 `kind=system`），所有 `roles.kind=platform` 的 `tenant_id` 指向它，避免「application_id 为空」语义过载。

#### `role_permissions`
- `role_id`, `permission_id`, `resource_id`（可选；应用级管理码可把 `resource_id=application_id` 字符串）

#### `role_bindings`
- `membership_id`, `role_id`；unique `(membership_id, role_id)`
- **必须提供 DELETE/解绑 API**

#### `user_groups` / `user_group_memberships` / `user_group_roles`
- 保留；组角色计入有效角色；变更 bump 版本

#### `role_data_scopes`
- 保留 scope_type 枚举；绿场种子策略见 2.4

#### `users` / `tenant_memberships`
- 保留 `user.auth_version`、`membership.auth_version`
- 触发 bump 的事件见 2.3

### 2.2 有效角色（唯一实现）

```text
list_effective_roles(membership_id, tenant_id, application_id | None) -> Role[]
  条件：Role.status=active，租户匹配，
        application_id 参数为 None 时只取 kind in (platform, tenant) 且 application_id IS NULL
        为 A 时取 application_id IS NULL 的租户角色 ∪ application_id=A 的应用角色
        （平台角色仅在「平台租户 membership」或显式平台判定路径使用）
  来源：RoleBinding ∪ (UserGroupMembership ▷ active UserGroup ▷ UserGroupRole)
```

**所有**下列路径必须调用同一实现：

- `evaluate_access`
- OIDC `_app_membership` / `current_user` OIDC 分支
- 应用可读能力列表
- （可选）签发前预检

### 2.3 `auth_version` 规则

| 事件 | `user.auth_version` | `membership.auth_version` |
|------|---------------------|---------------------------|
| 改密、用户全局停用 | +1 | — |
| 成员启停/离职 | — | +1（离职清绑定/组/组织同现逻辑可保留） |
| 角色 bind / unbind | — | +1 |
| 用户组成员替换、组角色替换 | — | 每个受影响 membership +1 |
| 角色 status→disabled、角色权限替换 | — | 所有持有该角色的 active membership +1 |
| 数据范围替换 | — | 建议 +1（绿场直接做） |

OIDC access token 继续携带 `auth_version` + `membership_version`；不匹配则 401。

### 2.4 数据范围默认策略（绿场）

| 权限类型 | `requires_data_scope` | 种子时 |
|----------|----------------------|--------|
| 纯管理面码（iam.tenant.*、iam.role.*…） | `false` | 不配 RoleDataScope |
| 业务码（surface=business） | **`true`（默认）** | 角色授予业务码时 **必须** 同时写 RoleDataScope；模板 `app.member` 默认 `self` 或 `organization`（产品二选一，**写死为 `self`** 除非产品改口） |
| 组织管理码 | `false` | 管的是 IAM 自身组织实体，靠租户边界 |

`evaluate_access`：若权限 `requires_data_scope=true`，**忽略**调用方 `include_data_scope=false`，强制解析；无策略 → `allowed=false`, `reason=data_scope_policy_missing`。

SDK：`check` / `require` 对管理码可不带 scope；对业务码自动按响应使用 `data_scope`（breaking：不再静默「有权无范围」）。

### 2.5 解绑

- 平台/租户角色：`DELETE` 级 API（见 §5）
- 应用角色：保留并与平台侧语义对齐（均 bump + audit）
- 禁止「只能 PUT 绑定、不能解绑」的缺口再现

---

## 3. 完整权限码表 + 四级矩阵

### 3.1 权限码表（绿场种子，`surface=management` 除非注明）

| code | 说明 | requires_data_scope |
|------|------|---------------------|
| `iam.platform.overview.read` | 平台总览 | false |
| `iam.tenant.read` | 租户列表 | false |
| `iam.tenant.manage` | 租户创建/启停/类型 | false |
| `iam.user.read` | 全局用户列表 | false |
| `iam.user.manage` | 创建用户/改状态/撤会话 | false |
| `iam.permission.read` | 权限目录读 | false |
| `iam.permission.manage` | 权限目录写/启停 | false |
| `iam.role.read` | 角色读 | false |
| `iam.role.manage` | 角色写、绑定/解绑（平台视角） | false |
| `iam.group.read` | 用户组读 | false |
| `iam.group.manage` | 用户组写 | false |
| `iam.member.read` | 租户成员读 | false |
| `iam.member.manage` | 成员状态/组织归属 | false |
| `iam.organization.read` | 组织树读 | false |
| `iam.organization.manage` | 组织写、数据范围策略写 | false |
| `iam.application.read` | 应用读 | false |
| `iam.application.manage` | 应用写（非密钥） | false |
| `iam.application.secret.rotate` | 轮换客户端密钥 | false |
| `iam.app_role.read` | 应用角色与成员读 | false |
| `iam.app_role.manage` | 应用角色 CRUD、成员 bind/unbind | false |
| `iam.invitation.manage` | 邀请创建/撤销 | false |
| `iam.audit.read` | 审计查询 | false |
| `iam.authorization.simulate` | 鉴权模拟 | false |
| `iam.model.read` | 模型目录/用量读 | false |
| `iam.model.manage` | 模型写/用量复核 | false |
| `iam.theme.manage` | 登录主题 | false |

业务码 **不进** 上述种子全集；由应用接入时注册，`surface=business`，`requires_data_scope=true`。  
示例（文档级，非必须种子）：`demo.document.read` / `demo.document.write`。

### 3.2 种子角色授权

| 角色 | 拥有的权限码 |
|------|----------------|
| L1 `platform.super_admin` | **上表全部 management 码** |
| L2 `app.admin` | `iam.application.read`, `iam.application.manage`, `iam.application.secret.rotate`, `iam.app_role.read`, `iam.app_role.manage`（授予时带 `resource_id=该 application_id` 或角色已钉 `application_id`） |
| L3 `tenant.org_admin` | `iam.organization.read/manage`, `iam.member.read/manage`, `iam.group.read/manage`, `iam.application.read`（本租户应用列表只读）, `iam.invitation.manage`；**不含** secret.rotate、**不含** app_role.manage（任命 L2 走「受限委托」见下） |
| L4 `app.member` | 无 management 码；可挂演示业务码 + `RoleDataScope=self` |

**L3 任命 L2（绿场写死）：**  
单独权限码 **`iam.app_role.assign_admin`**（可选精简：复用 `iam.app_role.manage` 但 API 仅允许「把已有 `app.admin` 角色绑给成员」，禁止改权限集/轮密钥）。  
为减少码数量，绿场采用：

- L3 **默认没有** `iam.app_role.manage`
- 增加码 **`iam.app_role.assign`**：仅允许对 `key=app.admin` 且本租户应用做 bind/unbind  
- L2 拥有完整 `iam.app_role.manage`  
- L1 两者都有  

将 `iam.app_role.assign` 加入 §3.1 种子，并授予 L3 与 L1。

### 3.3 四级 × 能力矩阵（验收用）

| 能力 | L1 | L2@A | L3@T | L4 |
|------|----|------|------|-----|
| 开/停租户 | ✓ | ✗ | ✗ | ✗ |
| 权限目录写 | ✓ | ✗ | ✗ | ✗ |
| 全局用户/会话 | ✓ | ✗ | ✗ | ✗ |
| 审计/模拟 | ✓ | ✗ | ✗ | ✗ |
| 管应用 A 配置/密钥/应用角色 | ✓ | ✓ | ✗ | ✗ |
| 任命 A 的 app.admin | ✓ | ✓（manage） | ✓（仅 assign） | ✗ |
| 管租户 T 组织/成员/组/数据范围 | ✓ | ✗ | ✓ | ✗ |
| 进管理台 | ✓ 全平台菜单（按码裁剪后仍近乎全） | ✓ 应用相关 | ✓ 组织/成员/组 | ✗ |
| 业务 API | 仅显式业务角色 | 仅显式 | 仅显式 | ✓ 若有业务角色 |

---

## 4. API / 前端 / OIDC / SDK 目标行为

### 4.1 认证与入口

| 入口 | 行为 |
|------|------|
| 管理台登录 | 发 management JWT；`auth_version`；refresh cookie 机制可保留 |
| OIDC | 标准授权码 + PKCE；access 含 `tenant_id`, `client_id`/`aud`, `auth_version`, `membership_version`, `sid`；**钉死**上下文，check 不得信 body 越权改租户/应用 |
| 入场条件 | 对应该应用：有效角色非空（member 或 admin 等），**含组继承** |

### 4.2 授权 API

- `POST /authorization/check`、`/check-batch`：保留路径；语义按新 `evaluate_access`（强制 data_scope 规则）。
- 响应建议稳定字段：`allowed`, `reason`, `data_scope?`, `application_id?`（OIDC 成功时）。
- **Breaking 允许：** `reason` 枚举可清理；batch 上限可调整；禁止返回内部 checks 细节给业务（管理模拟接口除外）。

### 4.3 管理 API 结构

**废除：** `APIRouter(..., dependencies=[Depends(platform_admin)])` 作为唯一门禁。

**改为：**

- `/api/v1/admin/*`：`Depends(current_user)` + 各路由 `require_management_permission(code, ...)`  
  - 平台码：在平台租户角色上判定（L1）  
  - 同时允许 L1 代管：对租户/应用资源先过平台码或显式「代管」逻辑（L1 拥有全部码即可）
- `/api/v1/tenant-admin/*`：`Depends(current_user)` + 租户域码（L3/L2）  
  - 组管理 **挂在 tenant-admin**（绿场不做「仅 admin 可管组」）

**必须暴露的绑定 API：**

| 方法 | 路径（建议） | 权限 |
|------|--------------|------|
| PUT | `/admin/role-bindings` | `iam.role.manage` |
| DELETE | `/admin/role-bindings` 或 `/admin/memberships/{id}/roles/{role_id}` | `iam.role.manage` |
| PUT/DELETE | `/tenant-admin/applications/{id}/role-bindings` … | `iam.app_role.manage` 或 `assign` |
| PUT/DELETE | 组角色/成员 | `iam.group.manage` |

### 4.4 前端

- 登录后 `GET /auth/me/capabilities`（**新建推荐**）或 `check-batch` 拉齐管理码。
- `consoleMode`：  
  - 持有任一平台码 → `platform`（菜单按码）  
  - 否则持有租户/应用管理码 → `tenant`  
  - 否则 → `no_access`（L4）
- `navigation`：每项 `requiredPermissions: string[]`（any-of）。
- `router.beforeEach`：无能力则打到无权限页。
- 按钮：L2 `can_manage` / `can_rotate_secret`；L3 `can_manage_organizations` 等，全部对齐码表。

### 4.5 SDK（breaking）

- 业务权限默认假定需要 data_scope；`require()` 若返回无 scope 则失败。
- 管理类集成若使用 check，显式传管理码且不要求 scope。
- 文档与 example 按绿场重写；旧 example 可删。
- 版本号：**major bump**（如 2.0.0）。

### 4.6 Bootstrap / 破窗

1. 环境变量仍可有 `BOOTSTRAP_ADMIN_EMAIL` / `PASSWORD`：仅 **seed 脚本** 创建用户并绑定 L1。  
2. 运行时 `ALLOW_BOOTSTRAP_EMAIL_BYPASS` 默认 **false**。  
3. true 时：邮箱匹配且无平台角色也可进 admin，但每条写审计 `break_glass=true`（仅灾备）。

---

## 5. 实施清单（按路径）

### 5.1 清库与种子（先做）

| 步骤 | 动作 |
|------|------|
| 1 | 停止 API/worker；备份仅作归档（可不恢复） |
| 2 | `docker compose down -v` 或 DROP DATABASE + 重建空库 |
| 3 | 删除或归档 `backend/migrations/versions/*.py` 旧链；新增 **单头迁移** `0001_greenfield_iam.py`（全 schema） |
| 4 | 新增种子模块 `backend/app/db/seed_greenfield.py`（或 `backend/manage.py seed`）：平台租户、权限码、L1/L2 模板定义、演示租户可选、bootstrap 用户+L1 绑定 |
| 5 | `alembic upgrade head` && `python -m app.db.seed_greenfield` |
| 6 | 清理 `.env` 中旧 client 密钥；按 `compose.yaml` / `.env.example` 重发 |
| 7 | 文档：标注所有旧接入作废；`docs/*` 接入手册改链到新契约 |

**建议脚本路径：**

- `scripts/greenfield-reset.ps1`（Windows）/ `scripts/greenfield-reset.sh`：down -v、upgrade、seed、打印 bootstrap 登录提示  
- `backend/app/db/seed_greenfield.py`  
- `backend/migrations/versions/0001_greenfield_iam.py`

### 5.2 后端 — 要改

| 路径 | 改什么 |
|------|--------|
| `backend/app/models/authorization.py` | `Role.kind`；Permission.`surface`/`requires_data_scope` |
| `backend/app/models/organization.py` | 保持 RoleDataScope；必要时校验与种子一致 |
| `backend/app/models/identity.py` | 保持 auth_version 字段；注释对齐 bump 表 |
| `backend/app/services/authorization.py` | `list_effective_roles`；强制 data_scope；platform kind 路径 |
| `backend/app/services/admin_authorization.py` | 按码 require；删除「仅邮箱即 True」作为主路径 |
| `backend/app/core/security.py` | OIDC 用有效角色；破窗开关；削弱 `platform_admin` 为「require 平台码」的依赖别名 |
| `backend/app/core/config.py` | `allow_bootstrap_email_bypass` 默认 false |
| `backend/app/api/v1/admin/__init__.py` | `dependencies=[Depends(current_user)]` |
| `backend/app/api/v1/admin/access_control.py` | 按码；**新增 unbind**；bump；种子角色保护（禁删 L1 key） |
| `backend/app/api/v1/admin/groups.py` | bump；权限码 |
| `backend/app/api/v1/admin/organizations.py` | member/org 码；data scope bump |
| `backend/app/api/v1/admin/tenants.py` / `users.py` / `applications.py` / `audit.py` / `models.py` / `invitations.py` / `themes.py` / `overview.py` / `model_usage.py` | 逐路由挂码 |
| `backend/app/api/v1/tenant_admin.py` | include groups |
| `backend/app/api/v1/tenant_admin_application_roles.py` | manage vs assign |
| `backend/app/api/v1/oidc_provider/common.py` | 有效角色入场 |
| `backend/app/api/v1/authorization.py` | 对齐新 evaluate 语义 |
| `backend/app/api/v1/auth.py` | me/capabilities；bootstrap 仅 seed |
| `backend/app/schemas/access_control.py` | 如有 surface 字段 |
| `backend/tests/**` | 按 §6 四级用例重写（旧数据假设全删） |

### 5.3 后端 — 要新建

| 路径 | 职责 |
|------|------|
| `backend/app/services/effective_roles.py` | 唯一有效角色实现（也可放在 authorization.py，但建议独立便于 OIDC import） |
| `backend/app/services/rbac_guards.py` | `require_permission(code, tenant_id=..., application_id=...)` |
| `backend/app/db/seed_greenfield.py` | 种子 |
| `backend/migrations/versions/0001_greenfield_iam.py` | 绿场 schema |
| `scripts/greenfield-reset.ps1` | 一键重建 |

### 5.4 后端 — 要删 / 归档

| 路径 | 处理 |
|------|------|
| 旧 `migrations/versions/0xxx_*.py`（除新 0001） | 移到 `migrations/archive_pre_greenfield/` 或直接删 |
| 依赖「邮箱即超管」且无角色的测试样例 | 删 |
| 过时接入 example 若与 breaking SDK 冲突 | 改或删：`examples/**` |
| 任何「兼容旧 membership_version 缺失则放行」逻辑 | 删（绿场 token 必须带齐） |

### 5.5 前端 — 要改

| 路径 | 改什么 |
|------|--------|
| `frontend/src/app/App.vue` | capabilities；consoleMode；去掉「overview 200=全平台」唯一判定 |
| `frontend/src/app/navigation.ts` | requiredPermissions；四级菜单映射 |
| `frontend/src/app/router.ts` | beforeEach |
| `frontend/src/shared/services/api.ts` | 如有 capabilities API |
| `frontend/src/features/**` | 按钮与 api-prefix 对齐 L2/L3；GroupManagement 走 tenant-admin |
| `frontend/src/features/roles/*`、`permissions/*` | 仅 L1 码可见写操作 |

### 5.6 前端 — 要新建

| 路径 | 职责 |
|------|------|
| `frontend/src/shared/services/capabilities.ts` | batch/capabilities 缓存 |

### 5.7 SDK — 要改

| 路径 | 改什么 |
|------|--------|
| `sdk/python/iam_authorization.py` | 业务码强制 scope；major |
| `sdk/python/iam_fastapi.py` | 对齐 |
| `sdk/typescript/src/authorization.ts` | 对齐 |
| `sdk/*/README.md`、`examples/**` | 重写 |
| 测试 | 全量按新语义 |

### 5.8 部署 / 文档

| 路径 | 改什么 |
|------|--------|
| `compose.yaml`、`.env.example` | bypass 默认 false；种子说明 |
| `README.md`、`docs/业务项目对接手册.md` 等 | 绿场接入；旧对接声明作废 |
| `AGENTS.md` | 指向本稿为权限规格 |

---

## 6. 验收用例（按四级）

### 6.1 基础设施

| ID | 用例 | 期望 |
|----|------|------|
| G0 | greenfield-reset 后 DB 仅有种子 | 平台租户、权限码、L1 用户可登录 |
| G1 | bypass=false，未绑 L1 的同名邮箱 | 不能靠邮箱进 `/admin` 写接口 |
| G2 | 有效角色含仅组继承的 `app.member` | OIDC 可登录该应用；直连绑定为空仍可 |

### 6.2 L1

| ID | 用例 | 期望 |
|----|------|------|
| L1-1 | 持 L1 调租户创建、权限目录写、审计读 | 200 |
| L1-2 | L1 解绑某用户租户角色 | 204；对方 membership_version+1；旧 access 401 |
| L1-3 | L1 无业务角色调业务 check `demo.document.read` | allowed=false |

### 6.3 L2

| ID | 用例 | 期望 |
|----|------|------|
| L2-1 | app.admin@A 改 A 配置、轮密钥、绑成员 | 200 |
| L2-2 | 同用户访问应用 B 管理 API | 403 |
| L2-3 | 调组织 manage / 租户 manage | 403 |
| L2-4 | 前端仅见应用相关菜单 | 无租户开通、无权限目录写 |

### 6.4 L3

| ID | 用例 | 期望 |
|----|------|------|
| L3-1 | 改组织、成员、组、数据范围 | 200 |
| L3-2 | `iam.app_role.assign` 将用户设为 A 的 app.admin | 200 |
| L3-3 | 轮换 A 密钥 / 改权限目录 | 403 |
| L3-4 | 不自动通过 `application:A#admin` 类管理 check（无 L2 绑定） | 应用 manage allowed=false |

### 6.5 L4

| ID | 用例 | 期望 |
|----|------|------|
| L4-1 | 仅 app.member + 业务码+self scope | 业务 check 带 data_scope 通过；管理台 no_access |
| L4-2 | 业务码无 RoleDataScope | allowed=false / data_scope_policy_missing |
| L4-3 | 调任意 `/admin` 或 `/tenant-admin` 写 | 401/403 |

### 6.6 闭环回归

| ID | 用例 | 期望 |
|----|------|------|
| C1 | unbind 全部应用角色且无组角色 | 下一 OIDC 请求失败 |
| C2 | 组角色替换 | 成员 version+1；权限 live 变化 |
| C3 | 角色 disabled | 持有者 check 失败并 version+1 |

---

## 7. 与旧文档差异（相对 `role-iam-deep-refactor-two-versions.md` 版本 A）

| 维度 | 演进式版本 A（旧文） | **本绿场终稿** |
|------|----------------------|----------------|
| 数据 | 双轨、bootstrap 过渡、存量 bump 兼容 | **全部可丢；单头迁移；不做存量迁移** |
| SDK | 尽量保持契约 | **允许 major breaking**（业务强制 scope） |
| 破窗 | 较长双轨 | **默认关闭**；仅灾备 |
| `roles.kind` / `surface` / `requires_data_scope` | 推荐/P3 | **绿场必做** |
| 组管理 | P2 再挂 tenant-admin | **首期就挂 tenant-admin** |
| L3 任命 L2 | 叙述性 | **独立码 `iam.app_role.assign` 写死** |
| 平台租户 | 可选 | **专用平台租户种子写死** |
| 兼容包袱 | OIDC 旧无 sid、缺 version 放行等 | **一律删除** |
| 加强项 | — | 一键 reset 脚本、capabilities API、验收用例表、解绑+bump 为首期必达、业务码默认 requires_data_scope |
| 版本 B | 并列选项 | **不实施**；本稿不留 ReBAC 双写 |

---

## 8. 建议实施顺序（给云端 agent）

```text
1. 落地 greenfield 迁移 + seed + reset 脚本
2. effective_roles + OIDC + evaluate_access（含强制 data_scope）
3. rbac_guards + admin/tenant-admin 挂码 + unbind + bump
4. 前端 capabilities + 菜单/路由
5. SDK major + examples
6. 按 §6 跑通验收；关闭 bypass；更新 README/对接文档
```

**完成定义（DoD）：** §6 全部用例绿；生产配置 `ALLOW_BOOTSTRAP_EMAIL_BYPASS=false`；无邮箱-only 超管路径；L2/L3 互斥用例自动化。

---

*本文件为方案 A 绿场重建唯一实施规格；与 `role-iam-deep-refactor-two-versions.md` 冲突时，以本稿为准。*
