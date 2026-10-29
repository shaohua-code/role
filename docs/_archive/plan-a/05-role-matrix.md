# 05 — 四级角色权限矩阵（终稿）

交叉引用：[role-iam-plan-a-greenfield.md](./role-iam-plan-a-greenfield.md) · [02-data-model](./02-data-model.md)

---

## 1. 四级定义

| 级 | 产品名 | 角色 key | kind | 作用域 |
|----|--------|----------|------|--------|
| L1 | 超级管理员 | `platform.super_admin` | platform | 平台租户 |
| L2 | 应用管理员 | `app.admin` | application | 单应用 |
| L3 | 管理员 | `tenant.org_admin` | tenant | 单租户 |
| L4 | 用户 | `app.member` 或纯业务角色 | application / 自定义 | 应用/业务 |

**硬规则：** L2 ⊄ L3，L3 ⊄ L2；L1 ⊇ 全部管理面码；L1/L2/L3 不默认含业务码。

## 2. 管理面权限码全表

| code | L1 | L2@A | L3@T | L4 | 备注 |
|------|----|------|------|-----|------|
| `iam.platform.overview.read` | ✓ | ✗ | ✗ | ✗ | |
| `iam.tenant.read` | ✓ | ✗ | ✗ | ✗ | |
| `iam.tenant.manage` | ✓ | ✗ | ✗ | ✗ | |
| `iam.user.read` | ✓ | ✗ | ✗ | ✗ | |
| `iam.user.manage` | ✓ | ✗ | ✗ | ✗ | |
| `iam.permission.read` | ✓ | ✗ | ✗ | ✗ | |
| `iam.permission.manage` | ✓ | ✗ | ✗ | ✗ | |
| `iam.role.read` | ✓ | ✗ | ✗ | ✗ | |
| `iam.role.manage` | ✓ | ✗ | ✗ | ✗ | 含平台侧 bind/unbind |
| `iam.group.read` | ✓ | ✗ | ✓ | ✗ | L3 限本租户 |
| `iam.group.manage` | ✓ | ✗ | ✓ | ✗ | |
| `iam.member.read` | ✓ | ✗ | ✓ | ✗ | |
| `iam.member.manage` | ✓ | ✗ | ✓ | ✗ | |
| `iam.organization.read` | ✓ | ✗ | ✓ | ✗ | |
| `iam.organization.manage` | ✓ | ✗ | ✓ | ✗ | 含 data-scopes 写 |
| `iam.application.read` | ✓ | ✓ | ✓ | ✗ | L2 钉 A；L3 本租户只读列表 |
| `iam.application.manage` | ✓ | ✓ | ✗ | ✗ | |
| `iam.application.secret.rotate` | ✓ | ✓ | ✗ | ✗ | |
| `iam.app_role.read` | ✓ | ✓ | △ | ✗ | L3 可不授；任命不需读全量也可 |
| `iam.app_role.manage` | ✓ | ✓ | ✗ | ✗ | 改角色权限集 |
| `iam.app_role.assign` | ✓ | ✓ | ✓ | ✗ | **仅** bind/unbind `app.admin` |
| `iam.invitation.manage` | ✓ | ✗ | ✓ | ✗ | |
| `iam.audit.read` | ✓ | ✗ | ✗ | ✗ | |
| `iam.authorization.simulate` | ✓ | ✗ | ✗ | ✗ | |
| `iam.model.read` | ✓ | ✗ | ✗ | ✗ | |
| `iam.model.manage` | ✓ | ✗ | ✗ | ✗ | |
| `iam.theme.manage` | ✓ | ✗ | ✗ | ✗ | |

✓ 种子授予 · ✗ 不授予 · △ 可选（默认不授）

## 3. 种子角色 → 码映射（实施用）

**L1 `platform.super_admin`：** 上表全部码。  

**L2 `app.admin`：**  
`iam.application.read|manage|secret.rotate`, `iam.app_role.read|manage|assign`  

**L3 `tenant.org_admin`：**  
`iam.organization.read|manage`, `iam.member.read|manage`, `iam.group.read|manage`, `iam.application.read`, `iam.app_role.assign`, `iam.invitation.manage`  

**L4 `app.member`：** 无管理码；若 SEED_DEMO：业务码 + `RoleDataScope(scope_type=self)`。

## 4. 前端菜单映射

| 菜单 | requiredPermissions（any-of） | 典型角色 |
|------|------------------------------|----------|
| 总览 | `iam.platform.overview.read` | L1 |
| 租户 | `iam.tenant.read` | L1 |
| 用户 | `iam.user.read` | L1 |
| 角色/权限目录 | `iam.role.read` / `iam.permission.read` | L1 |
| 审计 | `iam.audit.read` | L1 |
| 模型/主题 | 对应码 | L1 |
| 组织 | `iam.organization.read` | L1/L3 |
| 成员与数据范围 | `iam.organization.read` | L1/L3 |
| 用户组 | `iam.group.read` | L1/L3 |
| 应用 | `iam.application.read` | L1/L2/L3 |
| 应用角色 | `iam.app_role.read` 或 `assign` 或 application.manage | L1/L2（L3 仅任命入口） |

## 5. API 守卫映射原则

- 读用 `*.read`，写用 `*.manage` 或专项码。  
- 应用类：guard 传 `application_id`，与角色 `application_id` / `resource_id` 对齐。  
- L1 走平台角色权限，不依赖业务租户 membership（但代管业务租户资源时仍写正确 tenant_id）。

## 6. 反例（必须自动化）

1. L2 调用 `PATCH /admin/tenants/{id}/status` → 403  
2. L3 调用 `POST …/rotate-secret` → 403  
3. L3 无 L2 绑定时 `check(iam.application.manage)`@A → false  
4. L3 `assign` 成功后该用户成为 L2，再 rotate → 200  
5. L4 打开任意管理菜单 → 前端 no_access 且 API 403  
