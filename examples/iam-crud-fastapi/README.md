# IAM CRUD 示例（FastAPI）

把 SDK 的登录路由插件、授权适配层、批量判定串成一条完整接入路径的**最小可运行示例**：

| SDK 组件 | 轮次 | 在示例中的作用 |
| --- | --- | --- |
| `mount_oidc_auth`（iam_fastapi_auth） | P318 | 自动挂载 `/auth/login`、`/auth/callback`、`/auth/logout`、`/auth/me`，OIDC 流程零业务代码 |
| `IAMFastAPI`（iam_fastapi） | P316 | `require_permission` / `current_user` 依赖注入；别名强制登记、fail closed |
| `IamAuthorizationClient.check_batch` | P315 | `/me/permissions` 一次批量判定菜单/按钮快照（执行操作仍逐次在线判权） |
| `IamOIDCClient` | 基础 | 授权码 + PKCE 登录；令牌只存服务端会话 |

## 文件

- `app.py` — 应用工厂 `create_app()`：登录路由挂载 → 会话依赖 → 权限映射 → 4 个文档路由（owner 行级隔离）
- `test_app.py` — 端到端契约测试（mock 双 client）：登录 → 批量快照 → 创建 → owner 列表 → 越权 404 → 删除；另覆盖无会话 401 与 IAM 故障 503
- `provision.py` — 面向真实 IAM 的联调准备（幂等可重跑）：管理员登录 → 选租户 → 登记 application（`crud-demo`）→ **SDK 清单同步工具**登记 `demo.document.*` → 建角色并授权 + 配置 **self 数据范围** → 创建测试用户（一步设密码并绑定角色）；凭证写入 `.env.local`（已被 `.gitignore` 覆盖，管理员密码只进进程内存）
- `verify_flow.py` — 无头验收：临时受信（结束自动恢复）→ crud-demo 账号登录 IAM → OIDC 静默授权换 CRUD 会话 → 批量快照 → 创建/读/删（在线判权 + owner 过滤）→ 无会话 401

## 真实联调（P322 已验证）

前置：本地 IAM 三容器运行中。依次执行：

```powershell
$env:PYTHONPATH = '<repo>/sdk/python;<repo>/examples/iam-crud-fastapi'
python -B provision.py     # 幂等登记应用/权限/角色/用户
python -B verify_flow.py   # 全链路验收，9 项断言
# 浏览器路径：uvicorn app:app --port 8000 → 访问 http://localhost:8000/auth/login
```

真实联调沉淀的三个关键点（也是新项目接入最常见的坑）：

1. **Host 必须与 issuer 一致**：登录 cookie 绑定具体 host；OIDC issuer 是 `http://localhost:8002` 时，登录与 authorize 请求都必须走 `localhost`——用 `127.0.0.1` 登录的 cookie 不会随 authorize 发送，表现为永远跳回登录页。
2. **owner_only 需要显式 self 数据范围**：角色数据范围默认租户级；`require_permission(..., owner_only=True)` 强校验 IAM scope 全部分支为 owner/self，租户分支直接 403（fail closed）。角色建好后必须经「数据范围」（`PUT /admin/roles/{id}/data-scopes`，`scope_type: "self"`）逐权限配置。
3. **逐次用户确认 vs 静默授权**：新登记应用默认「逐次用户确认」（每次登录都在 IAM 页面点同意）；服务端无头验收可临时把应用设为受信（静默授权），用完恢复。

其余行为记录：`/auth/login` 成功后默认落地 `/`（示例无首页路由，返回 404 属预期，会话已建立）；无授权用户访问时 IAM 回调 `error=access_denied`，SDK 插件 fail closed 返回 403 且不建立会话。

## 运行前提（真实联调）

1. 本地 IAM 平台已运行（`docker compose up`），三容器 healthy。
2. 在 IAM 控制台登记一个 application，callback 填 `http://localhost:8000/auth/callback`，得到 client id/secret。
3. 在权限目录登记 `demo.document.read`、`demo.document.create`、`demo.document.delete`，并把它们**显式授予**目标角色（owner 数据 scope 由 IAM 返回）。
4. 安装 SDK 并启动：

```powershell
pip install -e "sdk/python[fastapi,oidc]"
cd examples/iam-crud-fastapi
uvicorn app:app --port 8000
```

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `IAM_ISSUER` | IAM issuer 地址（如 `http://localhost:9000`），SDK 会拉取 discovery 元数据 |
| `IAM_CLIENT_ID` / `IAM_CLIENT_SECRET` | 登记 application 得到的凭证 |
| `IAM_REDIRECT_URI` | 回调地址，必须与登记一致（`http://localhost:8000/auth/callback`） |
| `IAM_API_URL` | 授权判定 API 地址；存在时才在模块底部构造 `app`（测试注入 mock 时不设） |
| `IAM_APPLICATION_ID` | 授权判定的应用标识（权限码归属的应用） |

## 端点

| 端点 | 鉴权 | 说明 |
| --- | --- | --- |
| `GET /auth/login` → `/auth/callback` → `/auth/logout` → `/auth/me` | — | 由 `mount_oidc_auth` 提供；HttpOnly + SameSite=Lax cookie |
| `GET /me/permissions` | 登录 | `check_batch` 一次返回三个权限码判定，前端只用于渲染菜单/按钮 |
| `POST /documents` | `document.create` | 只需动作权限；owner 记为已验签 subject |
| `GET /documents`、`GET /documents/{id}`、`DELETE /documents/{id}` | `document.read` / `document.delete` + owner_only | IAM 返回本人 owner data scope 后，仓储按 `local_user_id` 过滤；越权表现为 404 |

## 关键设计（fail closed）

- **别名强制登记**：路由用 `document.read` 这类应用别名，`PERMISSION_MAP` 必须登记到稳定权限码；未登记在创建期即抛 `LookupError`。
- **owner_only**：适配层校验 IAM 返回的 data scope 是本人行级约束（any_of 中出现 tenant/organizations 分支直接 403），通过后业务代码再用 `permission.user.local_user_id` 过滤数据。
- **错误映射**：deny → 403；IAM 网络故障 → 503；其余上游异常 → 502。业务路由不感知差异。
- **批量只做展示快照**：`/me/permissions` 用 `check_batch` 减少请求数，但创建/删除等执行操作始终在线逐次判权，不消费快照。

## 生产替换点

1. **SessionStore**：`InMemorySessionStore` 仅适合单进程演示；多实例部署替换为 Redis/数据库实现（`put` / `load` / `take` / `delete` 四个方法）。attempt 原子消费语义（`take` 重放 403）必须保留。
2. **本地身份映射**：示例把 IAM `subject` 直接当本地主键（`local_user_id_resolver=lambda user: user.subject_id`）。生产必须经本地用户表解析真实主键后再落库/过滤。
3. **令牌刷新**：会话中令牌过期时，先走 `IamOIDCClient.refresh` 再进入业务路由（见 `load_verified_session` 注释）。
4. **CSRF 与日志**：写操作 CSRF 防护、访问日志脱敏（URL 含 code/state、Authorization 头）属业务方职责，示例未实现。

## 测试

```powershell
$env:PYTHONPATH = '<repo>/sdk/python;<repo>/examples/iam-crud-fastapi'
python -B -m unittest test_app -v   # 3 tests OK
```

## Express（Node）对应组件

TypeScript SDK 提供同构组件，接入思路完全一致（见 `sdk/typescript/README.md`）：

| Python（本示例） | TypeScript |
| --- | --- |
| `mount_oidc_auth(app, ...)` | `mountOidcAuth(app, ...)` |
| `IAMFastAPI` 依赖注入 | `createIamExpress()` → `requirePermission` / `currentUser` |
| `check_batch(...)` | `checkBatch(...)` |
| `InMemorySessionStore` | `InMemoryIamSessionStore` |
