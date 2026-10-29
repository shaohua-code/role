# 07 — SDK 与业务接入规范（绿场 Breaking）

交叉引用：[03-authz-flow](./03-authz-flow.md) · [04-api-design](./04-api-design.md) · [08-security](./08-security.md)

---

## 1. Breaking 声明

| 旧行为 | 新行为（2.x） |
|--------|----------------|
| `include_data_scope` 默认 false，业务可能「有权无范围」 | **业务码**（或服务端 `requires_data_scope`）必须带可用 `data_scope`，否则 SDK 视为失败 |
| 可手写任意 alias 映射疏漏时行为不一 | `permission_map` 未登记 alias → **LookupError / 启动失败**（保持 fail-closed） |
| 旧 example 对接 | 作废；按本文重接 |
| 包版本 | **major：2.0.0** |

管理面集成若调用 check：管理码不要求 data_scope。

## 2. 接入步骤（业务项目）

1. 在 IAM 控制台（L1）创建租户（若无）→ 创建应用 → 拿到 `client_id` / secret / redirect。  
2. 注册业务权限码到应用 namespace（L1 或应用权限 API）。  
3. 为应用放置种子角色：`app.admin`、`app.member`（系统创建应用时自动）。  
4. 为 `app.member`（或业务角色）配置 **RoleDataScope**（默认 self）。  
5. 业务侧实现 OIDC 登录（授权码 + PKCE）；校验 `iss`/`aud`/`exp`。  
6. 引入 SDK 2.x：`IamAuthorizationClient` +（可选）`IAMFastAPI.require_permission`。  
7. 每个受保护 API：`require(permission)`；列表查询用返回的 `data_scope` 过滤（`compile_postgres_data_scope` 或等价）。  
8. 联调：用 L4 用户、缺 scope 角色、跨租户 token 各打一次，确认 403。

## 3. Python SDK 契约要点

```text
check(token, tenant_id, permission_code, application_id?=from_client,
      resource_id?=, include_data_scope?=auto, subject_id?=)

require(...) -> AuthorizationDecision  # allowed 否则抛 AuthorizationServiceError(403)

# 业务权限：若服务端返回 allowed 但缺少合法 data_scope → SDK 抛 403/502（规格：视为失败）
# owner_only：约束必须全部为 owner 且 user_id==subject_id
```

`IAMFastAPI`：session 由业务注入；**禁止** SDK 自行信任请求头里的租户。

## 4. TypeScript SDK

对齐 Python：`includeDataScope` 对业务权限默认跟随服务端强制；`compile` 辅助可选。

## 5. 推荐权限命名

```text
{app_namespace}.{resource}.{action}
例：crm.deal.read / crm.deal.write
```

- 进入 IAM 目录时 `catalog_namespace` = 应用 namespace。  
- 不要把管理码 `iam.*` 授给业务用户角色。

## 6. 数据范围消费

服务端 `data_scope`：

```json
{
  "mode": "any_of",
  "constraints": [
    { "kind": "owner", "field": "owner_user_id", "user_id": "...", "tenant_id": "..." },
    { "kind": "organizations", "field": "organization_id", "tenant_id": "...", "organization_ids": ["..."] },
    { "kind": "tenant", "tenant_id": "..." }
  ]
}
```

业务 SQL 必须 **AND 租户隔离**，再 OR 展开 constraints（与现 SDK 文档一致）。  
禁止只信前端传的 org 列表。

## 7. 秘钥与轮换

- client_secret 仅存于业务配置/密钥管理；IAM 存 hash。  
- 轮换：L1 或 L2 `secret.rotate`；业务滚动更新。  
- 泄露：L1 停用应用 + 吊销 refresh family。

## 8. 旧接入拆除清单

- 删除业务环境旧 client_id  
- 升级 SDK major  
- 重跑权限同步  
- 验证强制 scope  
- 更新对接手册链接到本文档包  

## 9. Example 仓库

`examples/iam-crud-fastapi`：按 2.x 重写最小读写 + owner_only；旧 README 顶部注明作废。
