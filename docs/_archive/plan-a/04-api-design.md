# 04 — API 设计

交叉引用：[03-authz-flow](./03-authz-flow.md) · [05-role-matrix](./05-role-matrix.md) · [08-security](./08-security.md)

约定：前缀 `/api/v1`；JSON；错误 `{ "detail": string | validation[] }`。  
鉴权：`Authorization: Bearer <token>`，除非注明。

---

## 1. 路由分组

| 前缀 | 门禁 | 主体 |
|------|------|------|
| `/auth/*` | 部分公开 | 登录注册刷新 |
| `/authorization/*` | current_user | 业务/管理主体 check |
| `/admin/*` | current_user + **按码** | 平台管理面 |
| `/tenant-admin/*` | current_user + **按码** | 租户/应用管理面 |
| `/oidc/*`、`/.well-known/*` | 按 OIDC | 客户端 |
| `/health`、`/ready` | 公开 | 探针 |

**废除：** `/admin` 路由级唯一 `Depends(platform_admin)`。

---

## 2. 能力查询（新建）

### `GET /auth/me`
返回当前用户基本信息（id、email、display_name、status）。

### `GET /auth/me/capabilities`
**目的：** 前端一次拉取管理能力，减少 N 次 check-batch。

查询参数：
- `tenant_id` optional — 若缺省：返回平台码 + 各 active membership 的租户摘要能力

响应示例：

```json
{
  "user_id": "...",
  "platform": {
    "permissions": ["iam.platform.overview.read", "iam.tenant.manage", "..."]
  },
  "tenants": [
    {
      "tenant_id": "...",
      "tenant_name": "Acme",
      "permissions": ["iam.organization.manage", "iam.app_role.assign"],
      "applications": [
        {
          "application_id": "...",
          "permissions": ["iam.application.manage", "iam.application.secret.rotate"],
          "can_manage": true,
          "can_rotate_secret": true
        }
      ]
    }
  ]
}
```

实现：对相关码跑与 `evaluate_access` 同源逻辑（可内联批量 SQL 优化，结果必须一致）。

---

## 3. 授权 Check

### `POST /authorization/check`
```json
{
  "tenant_id": "uuid",
  "application_id": "uuid|null",
  "permission_code": "string",
  "resource_id": "string|null",
  "include_data_scope": false
}
```
- OIDC：忽略/覆写为 token 钉死的 tenant/app。  
- 若权限 `requires_data_scope=true`：即便 `include_data_scope=false` 也出 scope 或拒绝。

响应：
```json
{
  "allowed": true,
  "reason": "matching_role_grant",
  "data_scope": { "mode": "any_of", "constraints": [] },
  "application_id": "uuid"
}
```

### `POST /authorization/check-batch`
同租户/应用下 `permission_codes: string[]`（上限 32，唯一）。  
`results: { [code]: decision }`。

### `POST /admin/authorization/simulate`（L1：`iam.authorization.simulate`）
可指定 `user_id`，返回完整 checks（管理诊断）；业务 check 不返回内部 checks。

---

## 4. 管理面 `/admin`（按码摘录）

| 方法 | 路径 | 权限码 | 说明 |
|------|------|--------|------|
| GET | `/admin/overview` | `iam.platform.overview.read` | |
| GET/POST/PATCH | `/admin/tenants…` | read / manage | |
| GET/POST/PATCH | `/admin/users…` | `iam.user.*` | 含会话撤销 |
| GET/POST/PATCH | `/admin/permissions…` | `iam.permission.*` | |
| GET/POST/PATCH | `/admin/roles…` | `iam.role.*` | 禁删种子 key（可 disabled） |
| **PUT** | `/admin/role-bindings` | `iam.role.manage` | body: tenant_id, user_id, role_id |
| **DELETE** | `/admin/role-bindings` | `iam.role.manage` | **同 body 或 query：解绑**；bump + audit `role.unbind` |
| GET/… | `/admin/groups…` | `iam.group.*` | 平台可跨租户；变更 bump |
| GET | `/admin/audit` `/audit/search` | `iam.audit.read` | |
| … | models / themes / invitations | 对应码 | |

写操作统一：`audit` + 需 bump 时升 `membership.auth_version`。

---

## 5. 租户面 `/tenant-admin`

| 方法 | 路径 | 权限码 | 说明 |
|------|------|--------|------|
| * | `/organizations…` | `iam.organization.*` | |
| * | `/users/…/memberships…` | `iam.member.*` | |
| * | `/users/…/organizations` | `iam.member.manage` | |
| * | `/roles/{id}/data-scopes` | read: organization.read；写: organization.manage | bump |
| * | **`/groups…`** | `iam.group.*` | **绿场首期挂载** |
| GET | `/applications` | `iam.application.read` 或 L2 范围 | |
| PATCH… | `/applications/{id}` | `iam.application.manage`@app | |
| POST | `/applications/{id}/rotate-secret` | `secret.rotate`@app | |
| * | `/applications/{id}/roles…` | `iam.app_role.manage`@app | |
| PUT/DELETE | `/applications/{id}/role-bindings`… | manage 或 **`iam.app_role.assign`** | assign 仅允许 role.key=`app.admin` |

同一套 organizations/applications handler 可双挂 `/admin` 与 `/tenant-admin`，但 **权限码路径不同**：admin 侧 L1 全码；tenant 侧 L3/L2。

---

## 6. 解绑契约（写死）

**DELETE `/admin/role-bindings`**
```json
{ "tenant_id": "uuid", "user_id": "uuid", "role_id": "uuid" }
```
- 204 幂等（不存在也 204）  
- 校验角色属于该租户；禁止解绑导致「平台最后一个 L1」时可 409（可配置）  
- `membership.auth_version += 1`；audit  

应用侧 DELETE 保持现路径风格，语义对齐。

---

## 7. 错误与限流

| 状态 | 场景 |
|------|------|
| 401 | 未登录、token 无效、version 不匹配、会话吊销 |
| 403 | 已认证但无码 |
| 404 | 资源不存在或用 404 隐藏跨租户（与现组织 API 一致处保留） |
| 409 | 乐观锁冲突（expected_status / expected_permission_ids） |
| 422 | 校验失败 |

登录/注册保持现有 throttle 思路。

## 8. OpenAPI

- Tag：`auth` / `authorization` / `admin` / `tenant-admin` / `oidc`  
- 每个需码端点在 description 写明权限码，便于生成矩阵测试。
