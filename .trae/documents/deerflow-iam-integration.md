# DeerFlow 对接 IAM：SSO 登录 + 资源树菜单/按钮显隐

## Context

用户要求对接 DeerFlow（D:\project\deer-flow），范围限定：**只配菜单和按钮（资源树显隐），其他权限（check 判权、数据范围、模型用量）先不控制**。已确认决策：
- **IAM 资源树真控制** DeerFlow 菜单/按钮显隐（非仅登记）；
- 应用挂**新建专用租户**。

两边现状（已侦察核实）：
- IAM（D:\project\role）：OIDC Provider 完整（issuer=`http://localhost:8002`，discovery 根级 `/.well-known/openid-configuration`，token 端点仅 client_secret_basic，grant 仅 authorization_code+refresh_token，强制 PKCE S256+nonce，scopes 白名单 openid/profile/email/offline_access）；token 恒带 `tenant_id` claim（应用所属租户，非空 ✓）；资源树 `GET /api/v1/authorization/my-resources?client_id=` 返回嵌套树。
- DeerFlow：OIDC SSO 代码已预留（`backend/app/gateway/auth/oidc.py` 支持 client_secret_basic，PKCE/nonce/JWKS 全有；配置位 `config.yaml → auth.oidc.providers.<name>`；回调 `{gateway}/api/v1/auth/callback/{provider}`；`iam_token_vault` 支持保管+自动刷新 IAM token）；前端菜单由 `frontend/src/product/navigation.ts` 驱动。但 **真实 IAM E2E 从未跑通**（其文档自述「真实 IAM/Provider E2E 尚待完成」）。

已排除的风险：DeerFlow vault 要求 token 含非空 `tenant_id`（IAM 满足）；`revoke_token` 的 HTTPS 强制仅在预留 API 上、登出路径不调用（观察项）；DeerFlow 顶层 `authorization:` 段不启用时本地权限体系零改动（「其他权限不控制」天然成立）。

---

## 阶段一：IAM 侧配置（本仓库，管理台 API 自动化）

用 admin 会话（curl 登录拿 JWT）按序创建，结果留档：

1. **建专用租户**：`POST /api/v1/admin/tenants`（name=DeerFlow，slug=deerflow）。
2. **建应用**：`POST /api/v1/admin/applications`（tenant_id=上步、name=DeerFlow、client_id=`deerflow`、permission_namespace=`deerflow`、redirect_uris=`["http://localhost:8001/api/v1/auth/callback/iam"]`、post_logout_redirect_uris 按需）——**保存一次性 client_secret**；创建后 PATCH `trusted=true`（跳过 consent）。redirect_uri 以阶段二浏览器实际跳转的 authorize URL 为准修正（DeerFlow Gateway dev 默认 8001）。
3. **建资源树**：`POST /api/v1/admin/applications/{id}/resources`：
   - 6 个菜单（resource_type=menu）：code 与 path 对齐 DeerFlow 实际路由——
     `deerflow.overview`(/workspace)、`deerflow.chats`(/workspace/chats)、`deerflow.agents`(/workspace/agents)、`deerflow.scheduled-tasks`(/workspace/scheduled-tasks)、`deerflow.files`(/workspace/files)、`deerflow.capabilities`(/workspace/capabilities)
   - 2 个按钮（挂菜单下，对齐前端已确认的两个接入点）：`deerflow.chats.new`（挂 chats）、`deerflow.runs.cancel`（挂 chats）。
4. **建应用角色**：创建角色「DeerFlow 用户」（应用级）→ `PUT /admin/applications/{id}/roles/{role_id}/resources` 勾选全部资源。
5. **建测试用户**：新建用户（初始角色选该角色）绑入 DeerFlow 租户。

## 阶段二：DeerFlow SSO 打通（配置为主，零代码）

文件：`D:\project\deer-flow\config.yaml`（不存在则从 config.example.yaml 复制）+ `.env`：

```yaml
auth:
  local:
    allow_registration: false
  oidc:
    enabled: true
    providers:
      iam:
        display_name: 统一身份平台
        issuer: http://localhost:8002
        client_id: deerflow
        client_secret: ${DEERFLOW_IAM_CLIENT_SECRET}
        token_endpoint_auth_method: client_secret_basic   # IAM 仅支持 basic，必须显式覆盖默认 post
        scopes: [openid, profile, email, offline_access]  # offline_access 供 vault 刷新
        iam_token_vault_enabled: true
        redirect_uri: http://localhost:8001/api/v1/auth/callback/iam
        pkce_enabled: true
        nonce_enabled: true
        auto_create_users: true
        require_verified_email: false   # 首验先关（IAM 管理员直建用户可能无 email_verified_at）
```

环境变量：`DEERFLOW_IAM_CLIENT_SECRET=<阶段一密钥>`、`DEERFLOW_IAM_TOKEN_ENCRYPTION_KEY=<Base64 32 字节随机>`。

验证：`curl http://localhost:8002/.well-known/openid-configuration`；浏览器 `http://localhost:3000/login`（DeerFlow 前端）出现 SSO 按钮 → 跳 IAM 登录 → 回调进 `/workspace`；`uv run pytest backend/tests/test_oidc_auth.py -q`、`uv run ruff check backend/app/gateway`。

## 阶段三：IAM 资源树真控制（DeerFlow 前后端小改）

**DeerFlow 后端**（token 不出后端，IAM CORS 不动）：
- 新建 `backend/app/gateway/auth/iam_resources.py`：复用 `load_iam_authorization_attributes`（iam_token_vault.py:510，内置 <60s 自动刷新）取 access token → `httpx.AsyncClient`（timeout 5s/connect 2s）调 `GET {issuer}/api/v1/authorization/my-resources?client_id=deerflow` → 展平为 code 集合 → 进程内 TTL 缓存 60s（键 user_id+session_id）。
- 降级策略（fail-open 全显）：本地登录用户/PAT/vault 未启用 → `{"source":"unavailable","codes":null}`；超时/IAM 5xx → `{"source":"degraded","codes":null}`。UI 显隐层全显无安全损失（授权仍在本地 Gateway，本次不动）。
- `backend/app/gateway/routers/auth.py` 加 `GET /api/v1/auth/iam/resources`（`@require_auth`，取 `request.state.iam_session_id`）。
- 新建 `backend/tests/test_iam_resources.py`。

**DeerFlow 前端**：
- 新建 `frontend/src/core/auth/iam-resources.tsx`：`IamResourcesProvider` + `useIamResources()`，挂 `frontend/src/app/workspace/layout.tsx`（AuthProvider 内层）；拉取条件 `user.oauth_provider === "iam"`（本地用户直接 unavailable）；失败 60s 内不重试。
- `frontend/src/product/navigation.ts`：`ProductNavigationItem` 加可选 `iamCode`（映射：overview→deerflow.overview、chats→deerflow.chats、agents→deerflow.agents、scheduledTasks→deerflow.scheduled-tasks、files→deerflow.files、capabilities→deerflow.capabilities）；`getVisibleProductNavigation` 加第 4 个可选参数 `iamCodes?: ReadonlySet<string> | null`（null=全显，向后兼容）。
- 按钮接入两处：`frontend/src/components/workspace/workspace-header.tsx:71-83` 新建对话按钮加 `deerflow.chats.new`；`frontend/src/components/workspace/chats/chat-page.tsx:84` 停止按钮加 `deerflow.runs.cancel`（与本地 RUNS_CANCEL 双条件）。
- 空态：`source==="iam" && codes` 空集时侧栏渲染「当前账号未获授权功能」卡片（`workspace-sidebar.tsx`），不重定向。

**验证**：`uv run pytest backend/tests/test_iam_resources.py`；`pnpm -C frontend lint && pnpm -C frontend build`；浏览器端到端：SSO 用户菜单与 IAM 勾选一致 → IAM 撤一个菜单 60s 后刷新消失 → 本地密码用户全显 → 停 IAM 容器验证 degraded 全显。

## 收尾

- 本仓库 CHANGELOG 记录（含「本阶段范围外的用户明确指令」说明）；DeerFlow 侧不写文档（其仓库有自有记录体系）。
- 观察项：多 worker 下 refresh 轮换重放窗口；redirect_uri 实际端口以浏览器跳转为准。

## 关键文件清单

| 仓库 | 文件 |
|---|---|
| IAM | 无代码改动（管理台 API 配置）；`docs/应用对接.md` 可选补一段 DeerFlow 试点备注 |
| DeerFlow 后端 | `backend/app/gateway/auth/iam_resources.py`(新)、`backend/app/gateway/routers/auth.py`、`backend/tests/test_iam_resources.py`(新)、`config.yaml`、`.env` |
| DeerFlow 前端 | `frontend/src/core/auth/iam-resources.tsx`(新)、`frontend/src/app/workspace/layout.tsx`、`frontend/src/product/navigation.ts`、`frontend/src/components/workspace/workspace-header.tsx`、`frontend/src/components/workspace/chats/chat-page.tsx`、`frontend/src/components/workspace/workspace-sidebar.tsx` |
