> **SDK 2.0.0 绿场 breaking**：旧 example/对接方式作废。业务 `check`/`require` 默认假定需要 `data_scope`；有权无范围 → `data_scope_policy_missing` 失败。管理码 `iam.*` 可不要求 scope。升级：锁定 SDK major 2.x → 按本示例重接 OIDC + `permission_map` + `require_permission`/`owner_only` → 为业务角色配置 RoleDataScope → 联调有 scope / 跨租户拒。

# IAM CRUD 示例（FastAPI）

把 SDK 的登录路由插件、授权适配层、批量判定串成一条完整接入路径的**最小可运行示例**。

| SDK 组件 | 在示例中的作用 |
| --- | --- |
| `mount_oidc_auth`（`iam_fastapi_auth`） | 挂载 `/auth/login`、`/auth/callback`、`/auth/logout`、`/auth/me` |
| `IAMFastAPI`（`iam_fastapi`） | `require_permission` / `current_user`；别名强制登记、fail closed |
| `IamAuthorizationClient.check_batch` | `/me/permissions` 批量快照（执行操作仍在线逐次判权） |
| `IamOIDCClient` | 授权码 + PKCE；令牌只存服务端会话 |
| `IamAdminClient` + `sync_permission_manifest` | `provision.py` 走 **L2** `applications/{id}/permissions` 幂等登记 |

## 文件

- `app.py` — 应用工厂：OIDC 挂载 + 权限映射 + 文档 CRUD（owner 行级）
- `test_app.py` — mock 契约测试
- `provision.py` — 真实 IAM 联调准备（幂等）：应用 `crud-demo` → L2 清单同步 → 角色 + **RoleDataScope=self** → 测试用户；凭证写入 `.env.local`
- `verify_flow.py` — 无头验收（issuer/API 均为 `http://localhost:8002`）
- `.env.example` — 变量模板（无 secret）；真实值由 `provision.py` 写入 `.env.local`

## 真实联调

前置：本机 `compose.yaml` 三容器 healthy，API `:8002`。

```powershell
$env:PYTHONPATH = '<repo>/sdk/python;<repo>/examples/iam-crud-fastapi'
python -B provision.py     # 幂等登记；secret 只写 .env.local
python -B verify_flow.py   # 全链路验收
# 浏览器：先加载 .env.local 再 uvicorn app:app --port 8000 → http://localhost:8000/auth/login
```

关键点：

1. **Host 与 issuer 一致**：OIDC issuer 为 `http://localhost:8002` 时，登录与 authorize 都走 `localhost`（勿混用 `127.0.0.1`）。
2. **owner_only 需要 RoleDataScope=self**：`provision.py` 已对三个 `crud.document.*` 配置 `scope_type: self`。
3. **SDK 2.x**：不要再传业务默认 `include_data_scope=false`；缺策略会失败。
4. **包名**：Python 仓库路径 `sdk/python`；Node 包名为 `@iam-platform/authorization-client`（勿写已废弃的 `iam-sdk`）。

## 环境变量

见 `.env.example`。`IAM_API_URL` / `IAM_ISSUER` 指向 compose API（默认 `http://localhost:8002`）。

## Express（Node）

TypeScript SDK 插件齐全（`mountOidcAuth` / `createIamExpress` / `checkBatch` / `IamAdminClient`），**可运行 CRUD 示例目前仅 Python**。最小骨架见 [`../iam-crud-express/README.md`](../iam-crud-express/README.md)。

## 测试

```powershell
$env:PYTHONPATH = '<repo>/sdk/python;<repo>/examples/iam-crud-fastapi'
python -B -m unittest test_app -v
```
