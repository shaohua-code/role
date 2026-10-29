# 03 — 鉴权判定时序

交叉引用：[01-architecture](./01-architecture.md) · [04-api-design](./04-api-design.md) · [08-security](./08-security.md)

---

## 1. 管理台密码登录

```mermaid
sequenceDiagram
  actor U as 用户
  participant FE as 前端
  participant API as Auth API
  participant DB as PostgreSQL

  U->>FE: 提交邮箱密码
  FE->>API: POST /auth/login
  API->>DB: 查 user + 校验 Argon2
  alt 失败
    API-->>FE: 401（固定耗时/伪哈希防枚举）
  else 成功
    API->>DB: 创建/轮转 refresh_session<br/>写入 auth_version
    API-->>FE: access_token + Set-Cookie refresh
    FE->>FE: sessionStorage 存 access
    FE->>API: GET /auth/me/capabilities
    API->>DB: 有效角色 → 管理码集合
    API-->>FE: capabilities
    FE->>FE: 推导 consoleMode + 菜单
  end
```

**要点：** 登录成功 ≠ 平台超管；必须靠平台租户上 L1 绑定（或破窗，默认关）。

## 2. OIDC 授权码 + 入场

```mermaid
sequenceDiagram
  actor U as 用户
  participant App as 业务应用
  participant IAM as OIDC Provider
  participant DB as PostgreSQL

  App->>IAM: /oidc/authorize?client_id&PKCE…
  IAM->>U: 登录/同意（若需）
  IAM->>DB: 查 membership + list_effective_roles<br/>(app 上下文)
  alt 无有效角色
    IAM-->>App: 拒绝 / 错误页
  else 有有效角色
    IAM->>DB: 写 auth code（auth_version, membership_version）
    IAM-->>App: redirect ?code=
    App->>IAM: POST /oidc/token
    IAM->>DB: 校验 code + 版本仍匹配
    IAM-->>App: access_token + refresh? + id_token
  end
```

**入场判定：** `_app_membership` 使用与 `evaluate_access` 相同的有效角色（含组）；至少 1 个匹配该 `application_id` 或租户级可进应用的角色（`app.member` / `app.admin` 等）。

## 3. 业务 Authorization Check

```mermaid
sequenceDiagram
  participant Biz as 业务 API
  participant SDK as IAM SDK 2.x
  participant IAM as /authorization/check
  participant ER as effective_roles
  participant EV as evaluate_access
  participant DB as PostgreSQL

  Biz->>SDK: require(permission) / check
  SDK->>IAM: Bearer OIDC access + body
  IAM->>IAM: current_user：验签、吊销、sid、版本
  Note over IAM: OIDC 钉死 tenant_id / application_id
  IAM->>EV: AuthorizationCheck
  EV->>ER: list_effective_roles(...)
  ER->>DB: Binding ∪ Group
  EV->>DB: RolePermission ∩ Permission
  alt requires_data_scope
    EV->>DB: RoleDataScope 解析
    alt 无策略或空集
      EV-->>IAM: allowed=false
    else
      EV-->>IAM: allowed=true + data_scope
    end
  else
    EV-->>IAM: allowed 仅功能授权
  end
  IAM-->>SDK: decision
  SDK-->>Biz: 403 或放行（owner_only 再校验）
```

## 4. 管理台 / 租户台写操作

```mermaid
sequenceDiagram
  participant FE as 前端
  participant API as Admin/Tenant API
  participant G as rbac_guards
  participant EV as evaluate_access
  participant DB as DB

  FE->>API: Bearer management JWT + 写请求
  API->>G: require_permission(code, tenant?, app?)
  G->>EV: check management 码
  alt 拒绝
    API-->>FE: 403
  else 允许
    API->>DB: 业务写入
    opt 绑定/组/范围/角色变更
      API->>DB: membership.auth_version += 1
      API->>DB: audit(...)
    end
    API-->>FE: 2xx
  end
```

**L1：** 平台租户上持有对应码（种子为全码）。  
**L2/L3：** 在业务租户 membership 上持有码；应用码钉 `application_id`。

## 5. Token 刷新与废票

```mermaid
sequenceDiagram
  participant FE as 前端
  participant API as /auth/refresh
  participant DB as DB

  FE->>API: Cookie refresh
  API->>DB: 查 session + user.auth_version
  alt session 吊销或 version 不匹配
    API-->>FE: 401 → 清 token → 登录页
  else
    API->>DB: 旋转 refresh（若启用）
    API-->>FE: 新 access_token
  end
```

OIDC refresh：比对 `auth_version` 与 `membership_version`；绑定变更后旧 refresh/access 失效。

## 6. 判定伪代码（规格级）

```text
function evaluate_access(body, user, db):
  assert user.active
  tenant_id, application_id = pin_from_oidc_or_body(user, body)
  assert tenant active
  membership = active membership(user, tenant_id) or deny
  roles = list_effective_roles(membership, tenant_id, application_id)
  grants = match(roles, body.permission_code, body.resource_id)
  if not grants: deny(no_matching_grant)
  perm = grants.permission
  need_scope = perm.requires_data_scope or body.include_data_scope
  if not need_scope: allow()
  policies = RoleDataScope for matched roles × perm
  if not policies: deny(data_scope_policy_missing)
  constraints = resolve(policies, membership orgs, …)
  if empty: deny(data_scope_resolves_to_empty)
  allow(data_scope=constraints)
```
