# 变更日志

## 2026-10-17 IAM — 取消仓库绑定（用户指令）

- **操作：** 用户要求取消仓库绑定；删除 `D:\project\role\.git`，目录不再是 git 仓库。删除前核实本地 main（3 提交：`bea2e51` → `25a2968` → `0d7452c` cursor改造）与 GitHub 远程 `https://github.com/shaohua-code/role.git` **完全同步**（`main...origin/main` 无领先/落后），完整历史在远程保留；无 stash。38 个未提交文件（含 P312–P322 全部成果）仅保留在工作区，未受影响。
- **影响：** 工作区从此无版本保护；如需恢复：`git init` + `git remote add origin` + `git fetch`（工作区与远程差异大，恢复前须与用户确认分支策略）。原「勿 checkout/restore/reset」规则（2026-10-14 回滚事件）随绑定取消失效。
- **文档：** 进度文件「Git 事实」段、第 1 节规则、接手指令、第 7 节阻塞表、第 8 节更新规则共 5 处同步为无 git 绑定状态。

## 2026-10-17 IAM P322 — Real-IAM E2E of SDK five components + P302/P303 browser walkthrough

- **新增 `examples/iam-crud-fastapi/provision.py`（幂等联调准备）：** 平台管理员登录（HS256 management token，密码只进进程内存）→ 选租户 → 登记 application `crud-demo` → **SDK 清单同步工具真实登记** `demo.document.*` 三码 → 建角色 `crud-demo` 授权 + 配置 **self 数据范围**（`PUT /admin/roles/{id}/data-scopes`，owner_only 路由必需）→ 创建测试用户（一步设密码绑定角色）。凭证仅落 `.env.local`（gitignore 覆盖）。
- **新增 `examples/iam-crud-fastapi/verify_flow.py`（无头验收，9 项断言全 PASS）：** 临时受信（结束自动恢复）→ crud-demo 登录 IAM → OIDC 静默授权 + SDK callback 建会话 → `check_batch` 三码 allowed → 创建 201 → owner 列表/单查 200 → 删除 204 → 复查 404 → 无会话 401。浏览器侧并行验证：consent scope 展示正确、`/auth/me` 无 tokens、owner 路由 200。
- **真实 fail closed 负路径（意外但完整）：** ①无授权用户 OIDC → IAM `access_denied` 回调、SDK 403 不建会话；②角色数据范围默认租户级时 owner_only 全 403（适配层强校验生效），配置 self 后恢复；③登录 host 与 issuer host 不一致（127.0.0.1 vs localhost）cookie 不随 authorize 发送。三点沉淀进 README「真实联调」节。
- **P302/P303 浏览器走查：** P303 接入页渲染完整（截图存档）；登录后路由保持/16 页导航/应用-角色-权限数据链路正常；受限用户登录真实触发 P312 `loadTenantConsole` 的 **`/authorization/check-batch` 单次批量调用**（network 证据）。发现并修复接入页「尚未交付」过时文案（对齐 P318–P321 现状；`node node_modules\vue-tsc\bin\vue-tsc.js --b` 通过——pnpm 启动器 bug 用 P306 绕过方式）。P302 遗留实锤未修（保持进行中）：路由切换重复拉 4 字典接口、ready 高频轮询、Vue 模板编译 warn。
- **边界：** 无迁移无 schema 变更（联调全为业务数据写入）；crud-demo 资产保留可复用；uvicorn 走查后已停止；管理员角色未改动；DeerFlow 未涉及。
- 未做：P302 的轮询/重复请求优化本身（新发现的修复项）；CRUD 示例首页路由（404 属预期已记录）。

## 2026-10-17 IAM P321 — Permission-catalog manifest sync (F02, dual-language)

- **新增 Python `sdk/python/iam_permission_sync.py`（P321，标准库零依赖）与 TypeScript `sdk/typescript/src/permission-sync.ts`（经 `src/index.ts` 导出，零运行时依赖）：** 双语言语义对称的权限清单同步工具——`IamAdminClient` 覆盖 `GET/POST /api/v1/admin/permissions`（管理面首批 SDK 组件），`sync_permission_manifest`/`syncPermissionManifest` 把应用权限清单（`{code, resource_type, scope, description?}`）幂等同步到 IAM 权限目录。
- **fail closed 语义：** 清单在任何网络请求前本地预检（code 3–180 / resource_type 1–100 / scope 1–80 / description ≤500，与后端 `PermissionCreate` 对齐；重复 code 拒绝，不允许静默去重掩盖清单错误），非法输入本地抛错零网络调用；目录不可达（无法建立索引）直接抛错（503），绝不盲发创建。字段约束调研自 `backend/app/schemas/access_control.py` 与 `backend/app/api/v1/admin/access_control.py`（无批量端点，code 全局唯一 409 非幂等）。
- **幂等语义：** 先拉目录建 code 索引 → 只创建缺失项；已存在条目一律跳过且**不修改其描述/状态**（状态变更走管理台 `PATCH /admin/permissions/{id}/status`）；创建遇 409（并发窗口）重拉目录确认——已存在记 skipped、仍缺失保守记 failed 待人工核对；单条失败（含网络抖动、其他 HTTP 拒绝）逐条入报告不中断整批；报告 `created/skipped/failed`，failed 非空重跑安全。工具不做角色授予（grant 属管理台/角色管理语义）。认证要求平台管理 access JWT（HS256 `management_access` token；终端用户 OIDC token 被 IAM 403 拒绝），Bearer 头风格与授权 client 一致。
- **验证：** Python `test_iam_permission_sync.py` 契约测试 **14 例**（Bearer/URL 规范化、POST body、状态码保留、503/502 映射、空目录全建、已存在全跳零创建、部分创建、409 重拉两分支、单条失败不中断、目录不可达零创建、非法清单零网络、缺 token 本地拒绝）——SDK Python 全量 **85 tests OK**（71+14）；TS `test/permission-sync.test.mjs` **13 例**——TS SDK 全量 **48 pass / 0 fail**（48=authorization 14+express 9+express-auth 9+oidc 3+permission-sync 13；Node 22.20 strip-types）；`tsc -p tsconfig.json --noEmit` 通过（修复 1 处 unknown→Record 断言）。
- **文档：** 两份 SDK README 补权限同步节（语义/示例/测试命令）；技术架构第 3 节标题与接入表（清单同步已交付）、正文（批量登记已交付）与 4.3 节 SDK 表补行。
- 未做：真实 IAM 管理面联调（mock 契约测试；端点行为由后端既有测试覆盖）；管理 JWT 的签发/保管方案属业务运维；CRUD 模板 README 的 Express 映射表未含新组件（后续如做 Express 侧示例时一并补）。

## 2026-10-17 IAM P320 — FastAPI CRUD template example (F02)

- **新增 `examples/iam-crud-fastapi/`（P320）：** 把 F02 SDK 组件族串成完整接入路径的最小模板项目——`mount_oidc_auth`（P318 登录路由）+ `IAMFastAPI`（P316 授权依赖注入）+ `check_batch`（P315 展示快照）+ 内存文档仓储（owner 行级过滤）。`create_app()` 工厂支持注入 mock client 供测试；生产走 `IAM_ISSUER`/`IAM_CLIENT_ID`/`IAM_CLIENT_SECRET`/`IAM_REDIRECT_URI`/`IAM_API_URL`/`IAM_APPLICATION_ID` 环境变量构造。
- **示例路由：** `/me/permissions`（`check_batch` 一次判定三个 `demo.document.*` 权限码快照，仅用于前端菜单/按钮渲染）；`POST /documents`（动作权限 + owner 记 subject）；`GET /documents`、`GET /documents/{id}`、`DELETE /documents/{id}`（`owner_only=True` + `local_user_id` 过滤，越权一律 404 不泄露存在性）。
- **端到端契约测试 `test_app.py` 3 例全绿：** ①登录→快照（断言一次 `check_batch` 调用且单码 `check` 未被调用）→创建（owner=alice）→alice 列表/直取→bob 列表空+直取 404→alice 删除 204→bob 删除 404（真实 IAM 按请求者返回本人 scope，数据过滤表现为 404）；②无会话访问全部受保护路由 401；③IAM 网络故障映射 503。`raise_server_exceptions=False` 最终形态。
- **验证：** 示例测试 3/3 OK（DeerFlow venv Python + starlette TestClient）；SDK Python 全量回归 **71 tests OK** 不受影响。
- **新增 `examples/iam-crud-fastapi/README.md`：** 运行前提（本地 IAM compose + 登记 application + 显式授予 `demo.document.*`）、环境变量表、端点表、fail closed 设计说明、生产替换点（SessionStore 持久化/本地身份映射/令牌刷新/CSRF 与日志脱敏）、Express（Node）组件映射表（`mountOidcAuth`↔`mount_oidc_auth`、`createIamExpress`↔`IAMFastAPI`、`checkBatch`↔`check_batch`）。
- **文档：** 技术架构第 3 节标题更新（CRUD 示例已交付）、第 3 节正文补示例位置、4.3 节 SDK 表补示例行；进度文档 F02 行与索引同步。
- 未做：真实 IAM 联调（示例均为 mock 契约验证）；Express 侧 CRUD 示例（可选）；权限清单同步工具。

## 2026-10-17 IAM P319 — Express OIDC login-route plugin (F02, zero-dependency)

- **新增 `sdk/typescript/src/express-auth.ts`（P319，经 `src/index.ts` 导出）：** `mountOidcAuth(app, { oidcClient, sessionStore, routeOptions })` 一次性挂载 `login`/`callback`/`logout`/`me`（路径可配，默认 `/auth/*`），与 Python `mount_oidc_auth`（P318）语义对称。`IAMAuthSessionStore`（put/load/take/delete）由业务方实现，`InMemoryIamSessionStore`（TTL + 惰性过期）仅开发测试。
- **会话安全语义：** attempt 与令牌只存服务端；浏览器仅持一次性 HttpOnly attempt Cookie + 会话 Cookie（HttpOnly + SameSite=lax，`cookieSecure`/`cookieDomain` 可配）；Cookie 由适配器直接解析 `Cookie` 头（**不依赖 cookie-parser**）；attempt 原子消费（重放 403）；callback 缺 Cookie/过期 403，`OIDCProtocolError` 403 不透出细节（鸭子判别 `error.name`，避免 src 内跨文件运行时 import）；`/auth/me` 只返回 `subject`/`tenantId`/`profile`；logout best-effort 撤销两 token + 原子删会话（无会话幂等）。
- **零依赖实现：** Request/Response/App 均为结构类型（兼容 Express 4/5，不需 express 包）；随机 ID 用 Web Crypto `crypto.getRandomValues` + `btoa` base64url（不用 `node:crypto`/`Buffer`，与包内无 Node 类型依赖一致）。
- **验证：** 新增 `test/express-auth.test.mjs` 契约测试 9 例（login 302+HttpOnly+attempt 入库、callback 换会话+完整回调 URL 传递+清 attempt、重放 403、缺 Cookie fail closed、协议失败 403 不泄露、me 摘要无 tokens、me 无会话 401、logout 撤销+清理+再访 401、logout 幂等）——TS SDK 全量 **35 pass / 0 fail**（authorization 14 + express 9 + express-auth 9 + oidc 3；Node 22.20 strip-types）；`tsc -p tsconfig.json --noEmit` 通过。
- **文档：** TS README 补插件段与示例、测试命令加 `express-auth.test.mjs`；技术架构第 3 节（登录路由插件双语言已交付）与 4.3 节 SDK 表补 `mountOidcAuth` 行。
- 未做：真实 IAM OIDC 联调；CSRF/代理日志脱敏仍属业务方；CRUD 模板项目、权限清单同步工具。

## 2026-10-17 IAM P318 — FastAPI OIDC login-route plugin (F02)

- **新增 `sdk/python/iam_fastapi_auth.py`（P318）：** `mount_oidc_auth(app, oidc_client=..., session_store=..., options=OidcRouteOptions(...))` 一次性挂载 `login`/`callback`/`logout`/`me` 四条路由（路径可配，默认 `/auth/*`），消除业务方重复编写 OIDC RP 流程。
- **会话安全语义：** 登录 attempt 与身份令牌只保存在业务方实现的 `SessionStore`（`put/load/take/delete` 协议；`InMemorySessionStore` 仅开发测试，带 TTL 与过期惰性清理）；浏览器只持一次性 HttpOnly attempt Cookie 与会话 Cookie（HttpOnly + SameSite=Lax，`cookie_secure`/`cookie_domain` 可配）；attempt 经 `take` 原子消费（重放 403）；callback 缺 Cookie/attempt 过期 403，Provider 拒绝（OIDCProtocolError）映射 403 且不透出细节；`/auth/me` 只返回 subject/tenant/profile、绝不返回 tokens；logout best-effort 撤销 access/refresh token（失败不阻断本地登出）并原子删除服务端会话。
- **打包：** `pyproject.toml` `py-modules` 加 `iam_fastapi_auth`（依赖 `[fastapi]`+`[oidc]` extra）。
- **验证：** 新增 `test_iam_fastapi_auth.py` 契约测试 9 例（login 302+HttpOnly Cookie+attempt 入库、callback 换会话并清 attempt、attempt 一次性重放 403、缺 Cookie fail closed、协议失败 403 不泄露细节、me 返回摘要无 tokens、me 无会话 401、logout 撤销+清理、logout 幂等）——SDK Python 侧合计 **34 tests OK**（auth 9 + fastapi 10 + authorization 15；TestClient + Mock OIDC client，无网络）。
- **文档：** 技术架构第 3 节（边界表、接入流程第 3 步、待开发清单移除 Python 路由挂载）与 4.3 节 SDK 表补 `mount_oidc_auth`；python README 补插件段与示例。
- 设计取舍：CSRF 防护与代理日志脱敏仍由业务方负责（延续 SDK 边界声明）；Node 侧路由挂载、CRUD 模板项目未做。
- 未做：真实 IAM OIDC 联调（mock 契约测试；`complete_login` 内部 RS256/PKCE 校验已由 `test_iam_oidc.py` 覆盖）。

## 2026-10-17 IAM P317 — Express thin authorization adapter (F02, zero-dependency)

- **新增 `sdk/typescript/src/express.ts`（P317，经 `src/index.ts` 导出）：** `createIamExpress(options)` 暴露 Express 中间件——`requirePermission(alias, { ownerOnly })` 与 `currentUser()`，语义与 Python `iam_fastapi`（P316）对称：别名必须登记在 `permissionMap`（未登记在创建中间件时抛错）；`ownerOnly` 要求 data scope 每个 `any_of` 分支都是绑定已验签 subject 的 owner 约束（tenant/organizations 分支整体 403）+ `localUserIdResolver` 解析本地用户主键（空/异常 503）；IAM 403/503 保留语义、其余契约错误归一 502；会话由业务方 `loadSession` 从本地已验签会话构建（缺失抛带 `statusCode` 的错误，原样转发业务方错误处理）。成功时挂 `req.iamUser`（ownerOnly 含 `localUserId`）与 `req.iamDecision`。
- **零依赖实现：** 仅用结构类型描述 Request/Response（`{headers}` / `{status().json()}`），兼容 Express 4/5，不需要 express 包；跨文件引用改用 **type-only import**（Node strip-types 擦除、tsc 保留类型检查——首个 src 内跨文件 import 的兼容处理）。
- **验证：** 新增 `test/express.test.mjs` 契约测试 9 例（别名映射与 require 参数、403/503/502 错误映射、未登记别名创建期抛错、ownerOnly 本地主键解析、放宽 scope 403、resolver 缺失创建期抛错、会话错误转发业务错误处理、currentUser 不触 IAM）——TS SDK 全量 **26 pass / 0 fail**（authorization 14 + express 9 + oidc 3；Node 22.20 strip-types）；`tsc -p tsconfig.json --noEmit` 通过。
- **文档：** TS README 补 Express 适配器段与示例、测试命令加 `express.test.mjs`；技术架构第 3 节实现边界更新（Express 适配器已交付）并从待开发清单移除 Node 适配器；4.3 节 SDK 能力表补 `createIamExpress` 行。
- 未做：真实 IAM 联调与 CRUD 模板项目；路由自动挂载插件（login/callback/logout）、权限清单同步工具。

## 2026-10-17 IAM P316 — FastAPI thin authorization adapter (F02)

- **新增 `sdk/python/iam_fastapi.py`（`[fastapi]` extra）：** `IAMFastAPI` 把授权客户端暴露为 FastAPI 依赖——`require_permission(alias, owner_only=)` 返回依赖函数（配合 `Depends` 使用），`current_user()` 返回可信上下文依赖。`IAMUserContext` 由业务方 `session_dependency` 从**本地已验签** OIDC 会话构建（缺失抛 401）；适配层不验签 token、不接受请求参数中的身份。
- **安全语义：** 权限别名必须在 `permission_map` 登记为稳定 code，未登记别名在构建依赖时即抛 `LookupError`（fail closed，不猜测映射）；`owner_only=True` 走 `check(include_data_scope=True, subject_id=...)` 并要求每个 `any_of` 分支都是绑定已验签 subject 的 owner 约束（出现 tenant/organizations 分支整体 403，any_of 为 OR 语义）；经 `local_user_id_resolver` 解析产品本地主键（未配置 resolver 在构造期即拒绝；解析为空视为映射服务故障 503）。错误映射：403/503 保留语义，其余契约错误归一 502；同步 client 调用由 FastAPI 调度到线程池。
- **打包：** `pyproject.toml` 增 `fastapi = ["fastapi>=0.100,<1.0"]` extra，`py-modules` 加 `iam_fastapi`；基础授权 SDK 保持零依赖不变。
- **验证：** 新增 `test_iam_fastapi.py` 契约测试 10 例（别名映射与单码契约、403/503/502 错误映射、未登记别名 fail closed、owner_only 本地主键解析、放宽 scope 403、resolver 缺失构造期拒绝、current_user、会话缺失 401）——**25 tests OK**（test_iam_fastapi 10 + test_iam_authorization 15，FastAPI TestClient + Mock client，无网络）。
- **文档：** `docs/技术架构与接入.md` 第 3 节标题与实现边界更新（FastAPI 授权适配层已交付；路由挂载/Node 适配器/向导仍待开发）+ 真实用法示例；4.3 节 SDK 能力表补 `IAMFastAPI` 行；`sdk/python/README.md` 补适配层段与示例。
- 设计取舍：适配层不自动挂载 login/callback/logout 路由（属后续「框架插件」任务）；`requireOwner` 语义由 `require_permission(..., owner_only=True)` 承担而非独立接口。
- 未做：真实 IAM 联调与小型 CRUD 模板项目；Node/Express 适配器。

## 2026-10-17 IAM P315 — SDK `check-batch` client methods (F02, Python + TypeScript)

- **Python（`sdk/python/iam_authorization.py`）：** `IamAuthorizationClient` 新增 `check_batch(access_token, tenant_id, permission_codes, resource_id=None)`——调用 `POST /api/v1/authorization/check-batch`，返回按请求码索引的 `dict[str, AuthorizationDecision]`；每个码复用与 `check()` 相同的判定语义。批量结果不携带行级数据条件（owner-only 数据操作仍走 `check(include_data_scope=True)`）；数量（1–32）与去重由服务端校验，违反以 `AuthorizationServiceError(422)` 抛出；响应缺码/畸形判定/坏 `application_id` 一律 fail closed 502；输入预检（token 非空、codes 非空字符串列表）在任何网络调用前抛 `ValueError`。
- **TypeScript（`sdk/typescript/src/authorization.ts`）：** 新增 `checkBatch(accessToken, request: BatchAuthorizationRequest)` 与 `BatchAuthorizationRequest` 接口（经 `src/index.ts` 导出），语义与 Python 侧一致；沿用单码 `check` 的 AbortController 截止时间模式（超时/网络 503、HTTP 拒绝保留状态码、坏 JSON 502）。
- **测试：** Python `test_iam_authorization.py` 新增 4 例（批量映射与单码契约、畸形/缺码拒绝、网络调用前输入预检、网络故障 fail closed）——**15 passed**；TypeScript `test/authorization.test.mjs` 新增 3 例（批量端点请求形状与映射、畸形/缺码拒绝、网络调用前输入预检）——**14 pass / 0 fail**（Node 22.20 `--experimental-strip-types --test`）；`tsc -p tsconfig.json --noEmit` 通过。
- **文档：** `docs/技术架构与接入.md` 第 4.3 节 SDK 能力表补两语言 batch 方法；两份 SDK README 各补 `check_batch`/`checkBatch` 段落与测试计数。
- 设计取舍：批量方法刻意不接入 data scope（多码批量面向菜单/按钮权限快照；行级过滤仍需单码 + subject 绑定校验，避免逐码 subject 校验逻辑在批量路径重复出错面）。
- 未做：真实 IAM 联调（与 P312 冒烟同界）；DeerFlow adapter 未接批量（其 permission map 逐键判定语义不变，无需改动）。

## 2026-10-17 IAM P314 — Full isolated suite green (P312 closure) + D01 contract-doc fixes

- **verify-local 全量（P312 验证闭环）：** 随机隔离 PostgreSQL 库迁移至 head `0031_model_usage_reconciliation` 后运行后端完整套件 **177 tests OK**（12.838s，含 P312 新增 `check-batch` 契约测试 6 例）；测试库自动清理，未触及开发主库。console 前端镜像 `docker compose build console` 成功（内部 `vue-tsc -b` + Vite 生产构建，exit 0）；api 镜像一并重建。
- **运行环境事实：** 非交互重定向 shell 下运行 `verify-local.ps1`，其 `$ErrorActionPreference='Stop'` 会把 docker 写到 stderr 的进度行（`Image ... Building`）包装为 NativeCommandError 直接终止脚本（2/2 段）；前端镜像按 P306 方式单独构建补齐。交互 shell 历史运行正常（P284/P298），脚本本身未改。另：后台 shell 需先把 Docker Desktop bin 加入 PATH，否则 buildx 找不到 `docker-credential-desktop`（P306 同款）。
- **D01 契约文档校正（3 处）：** ① `docs/技术架构与接入.md` 授权 API 表补 `POST /authorization/check-batch` 行（P312 契约缺口）；② 同文件更正过时表述「也没有中央批量 check API」→ 批量判定 API 已具备（`/auth/me` 不返回 permissions 的表述保留，仍属实）；③ `backend/README.md` 顶部补 P312 端点记录（追加式日志惯例）。
- **审阅结论（无动作项）：** 产品需求中「待开发」项（资源级净影响、账号导出/删除、SMTP 看板、拖拽排版、框架插件/向导）均为真实未实现，表述正确；`docs/后续项目对接手册.md`、`部署与运维.md`、`快速启动指南.md` 无过时契约表述。SDK（Python/TypeScript）尚无 `check-batch` 方法封装，属 F02 源码范畴，本轮不动。
- 未做：浏览器登录后控制台实测（P312 批量调用 UI 行为）；375 弹窗复测仍待用户。

## 2026-10-17 IAM P313 — B04 guidance budget closure verified (DeerFlow worktree)

- **背景：** P290 DeerFlow Windows 离线全量套件唯一失败为 `frontend/src/AGENTS.md` 49,630 bytes 超 49,152 上限（按用户要求未重跑）。本轮核实：该文件现为 **48,962 bytes**（≤ 上限），系 DeerFlow 工作区**并行会话的未提交改动**，本轮保留、未重复改动。
- **本轮修复（DeerFlow `.gitignore` +7 行）：** `backend/.t/` 与 `.t/` 加入忽略。根因：`scripts/check_agent_guidance.py` 的 `_worktree_paths` 用 `git ls-files --others --exclude-standard` 扫描，而 `backend/.t` 未被忽略，任何放在其下的 pytest basetemp（内含 repo 树副本的 `AGENTS.md`）都会使 `test_repository_has_the_approved_scoped_guidance_shape` 失败——实测 `backend/.t/p345-*` 并行会话残留即触发（13 个 extra items）。该修复对并行会话无害且消除其同类隐患。
- **验证：** 单独运行 `backend/tests/test_agent_guidance_check.py`（含预算断言 `test_repository_guidance_stays_below_hard_budgets_and_avoids_doc_indexes`）**12 passed in 6.68s**（隔离 `DEER_FLOW_HOME` + 系统 TEMP basetemp，临时目录已清）。未跑 32 分钟全量套件（遵守用户此前不重跑要求；`backend/.t` 尚有并行会话 15:33–17:43 的 p345-* 活跃残留，不做清理）。
- **DeerFlow 工作区事实：** 新增未提交改动 1 处（`.gitignore`）；`frontend/src/AGENTS.md` 压缩为并行会话既有未提交改动。`backend/.t/iam-bdde3959`（本轮一次性容器外测试 basetemp）删除被沙盒拒绝，已被 ignore 覆盖、无害，留待后续清理。
- B04 剩余：实际 IAM/Provider 路径与发布门禁验收仍待环境/授权。

## 2026-10-17 IAM P312 — Tenant console N+1 authorization check fix (P302 leftover)

- 后端：`app/schemas/access_control.py` 新增 `AuthorizationCheckBatch`（`permission_codes` 1–32 个、去重校验、`tenant_id/application_id/resource_id/include_data_scope` 同单码契约）；`app/api/v1/authorization.py` 抽出 `_public_decision` 辅助函数（原 `/check` 响应逻辑复用），新增 `POST /authorization/check-batch`——逐码构造与 `/check` 相同的 `AuthorizationCheck` 走同一判定路径，无批量旁路。
- 前端：`frontend/src/app/App.vue` `loadTenantConsole` 将每个 membership 的 5 路 `/authorization/check`（N+1）改为单次 `/authorization/check-batch`，按 `results[code]?.allowed === true` 消费；响应形状与原逐码结果一致，UI 行为不变。
- 测试：新增 `backend/tests/test_authorization_check_batch.py` 契约测试 6 例（schema 空列表/超 32/重复拒绝；端点逐码判定映射、非 OIDC 用户不带 application_id、OIDC allowed 携带验签 application_id）。一次性容器（`compose run --rm`，不动镜像/主库）pytest **6 passed**。
- 运行时冒烟（dev 容器，uvicorn --reload 已热加载新代码）：无认证 POST → 401（路由已注册、认证守卫生效）；容器内以应用自身 `create_access_token` 签 admin token（密码不经过命令行/日志）直调 → 200 + 逐码 `results` 映射；同 token 对照单码 `/check` 输出逐字节一致（当前开发库 admin 对 5 个管理码均为 `no_matching_grant`，系既有授权数据状态，`/check` 行为未变）。
- 说明：曾尝试以容器内默认规则集 Ruff 作为门禁，核实 IAM 后端无 Ruff 配置（`verify-local.ps1` 亦不运行 Ruff，历史 Ruff 记录均属 DeerFlow 项目），全库默认规则集下 436 处既有告警（B008×169 为 FastAPI `Depends` 标准写法、EXE002×103 为 Windows 挂载可执行位噪音），判定 Ruff 非本项目门禁，未据其改动代码。
- 验证：契约测试 6/6、`vue-tsc -b` 与 Vite 生产构建（临时产物已删）通过、运行时冒烟如上。未跑 `verify-local.ps1` 全量套件（改动为新增端点与前端调用形状，未触碰既有判定与迁移；全量套件可在下轮合并验证时运行）。无数据库迁移。

## 2026-10-17 IAM P311 — Narrow-screen modal overflow fix (user-reported)

- 用户手动复测 768/375：仅 375 下新建用户弹窗超宽。根因：全局样式无 `.ant-modal` 窄屏适配，antd Modal 默认固定 `width:520px`（375 视口必溢出，768 正常）。
- 修复：`frontend/src/style.css` 追加 `@media(max-width:575px){ .ant-modal{max-width:calc(100vw - 16px)} }`——全局作用于所有 antd 弹窗（新建/核对/邀请/确认），随视口收缩、内容流式自适应；桌面（520px）不变。
- 验证：Vite 生产构建通过（临时产物已删）；浏览器样式表确认规则随 HMR 注入（仅 ≤575px 生效）。375 实际效果待用户复测确认。
- 仅前端 CSS 1 文件变更；无后端/契约/迁移变更。用户复测其余 768/375 项未报问题。

## 2026-10-17 IAM P310 — C03-IAM walkthrough (light theme + admin tiering)

- 浅色主题 1026×855 走查：新建用户/模型用量核对/创建成员邀请三弹窗与 `/users`、`/model-usage`、`/invitations` 三页面渲染正常、无横向溢出；截图存档 c03-*.png。无修复项。
- 管理员分层证据：临时启用夹具用户 `a04-user1` 登录 → 「访问受限」态（侧栏 16 项平台菜单全过滤、提示所需权限码）；直访 `/users` 被路由守卫重定向受限页；同账号 token 直调 `/admin/users`、`/admin/overview` 均 HTTP 403。走查后用户停回 disabled（DB 收尾，auth_version+1）。
- 限制：自动化浏览器无视口 resize 能力，768/375 窄屏走查待手动复测；DeerFlow 业务页走查依赖 C01。P3-1 运行时复测无自然 422 场景，继续留观。
- 无源码/契约/迁移变更。同步 `docs/验收记录.md`（P310 节）与 `docs/项目总览与进度.md`（C03 行更新为浅色/分层部分完成）。

## 2026-10-17 IAM P309 — Shared reserved-domain validation extended to invitations

- 新增 `frontend/src/shared/utils/emailValidation.ts`：`isReservedEmailHost`（完整邮箱或裸域名判断）+ `validateReservedEmailDomain`（antd validator 形式），口径对齐服务端 `EmailStr` 的特殊用途顶级域（不拦 `example.com`）。
- `UserManagement.vue` 改为导入共享函数（消除 P308 本地副本）；`InvitationManagement.vue` 创建邀请在邮箱语法检查后追加保留域拦截，提示文案与用户管理一致。
- 验证：`vue-tsc --noEmit --pretty false` 与 Vite 生产构建（临时产物已删）通过。浏览器实测（admin 会话）：邀请填 `a04-inv@example.test` 提交 → toast「该邮箱使用保留顶级域…」，邀请未创建（列表 0 条）。
- 未做：公开认证页（登录/注册/找回）未加同款校验（登录场景意义有限且契约测试覆盖，需单独评审）；后端/契约/迁移无变更。

## 2026-10-17 IAM P308 — Fix P3-1/P3-2 UI defects found in P307

- P3-1：`frontend/src/shared/services/api.ts` 新增 `extractErrorMessage`——FastAPI 422 的数组型 `detail` 按 `字段（去掉 body 前缀）: 消息` 拼接为「请求校验失败：email: …」；字符串 detail 行为不变，非数组对象回退通用文案，不再出现 "[object Object]"。
- P3-2：`frontend/src/features/users/UserManagement.vue` 新建用户邮箱追加保留顶级域前端校验（`.test/.example/.invalid/.localhost/.local/.onion`），口径对齐服务端 `EmailStr`（email-validator）；刻意**不**拦 `example.com`（P307 夹具实测服务端接受）。
- 验证：`vue-tsc --noEmit --pretty false` 通过；Vite 生产构建（`--configLoader runner`，产物写系统临时目录后删除）通过。浏览器实测（dev 容器 HMR）：`@example.test` 提交被字段级提示拦截，无请求发出；P3-1 的 422 运行时路径因常见 422 已被前置拦截，待下次自然 422 复测。
- P3-3（AX 剪枝）调查结论：问题集中于 antd Select 下拉（渲染到 `body`）在嵌入式自动化 AX 树被剪枝，弹窗本体可见；改全局 `getPopupContainer` 风险大于收益，保留观察待真实读屏复核，未改码。
- 仅前端 2 文件变更；无后端/API/schema/迁移变更。其他表单的同类校验推广另行排期。

## 2026-10-17 IAM P307 — A04 management-write acceptance passed

- A04 管理写入验收全部通过。执行方式：用户浏览器手动登录两次（管理员密码不经过聊天/日志/命令行），Agent 接管会话 UI 走查；双身份/并发验证以 admin token 走 admin API。
- 通过项：新建用户 201 与重名 409；停用→登录 401、`auth_version`+1、refresh sessions/OAuth tokens 同事务撤销；恢复启用；`expected_status` 乐观锁双发 200+409；管理员自停用 400；角色创建→绑定 `deerflow.agent.read`→`role-bindings` 204；授权模拟 allow（matching_role_grant）→停用角色 deny（no_matching_grant）→恢复 allow→未授予 deny；测试用户会话被管理员远程撤销（二次确认）后踢回登录页，DB 撤销链与 `user.session.revoke` 审计完整；本人会话远程退出按钮 disabled；用量待核对队列分页、settle 费用 0.00900000 与目录价精确一致、release、未超期 409、并发双提交 200+409；终态汇总 2 笔、费用 0.01005000 精确。
- 夹具（开发库，停用保留为证据）：用户 `a04-user1@example.com`、角色 `a04.fixture.role`、`model_catalog a04-fixture-model`、预留 r1–r5（settled×2/released×1/reserved×2）、账目 2 条、审计全链。用户/角色已停用。
- 发现（未修待排期）：422 数组 `detail` 被 toast 渲染为 "[object Object]"；`EmailStr` 拒绝保留 TLD（`.test`）无字段级提示；部分 antd 弹窗对可访问性树不可见、键盘焦点管理不可靠；观察：同浏览器第二账号登录经共享 refresh cookie 顶掉第一标签会话（设计行为）。
- 无源码/契约/迁移变更；未运行自动化测试或构建。同步 `docs/验收记录.md`（P307 节）与 `docs/项目总览与进度.md`（速览、第 3/4/5/7/8 节，A04 → 已完成）。

## 2026-10-17 IAM P306 — Console container vue-router fix

- 修复 localhost:5175 报 `Failed to resolve import "vue-router" from "src/app/App.vue"`。根因：console 容器只挂载 `src` 源码，依赖来自镜像 `iam-platform-console:dev-oidc-consent-v2` 构建时安装的 `node_modules`；P303 因本机 pnpm store 链路异常仅把 `vue-router`/`@vue/devtools-api` 用 `npm pack` 装进宿主机 `node_modules`，`pnpm-lock.yaml` 与镜像内均无 `vue-router`。
- `frontend/pnpm-lock.yaml`：用 pnpm 12.6.0 `install --lockfile-only` 对齐 `package.json`，新增 `vue-router@4.6.4`、`@vue/devtools-api@6.6.4`，供应链策略校验 142 项通过。宿主机系统 pnpm 启动器（nvm4w shim + pnpm 按 PackageManager 字段自切换版本）在 Windows 上 spawn 到 store 内 POSIX shim 导致 `is not recognized`，属既有环境问题未修，本轮绕过方式：设全新 `COREPACK_HOME` 让 corepack 下载 pnpm 12.6.0 后直接 `node <COREPACK_HOME>\v1\pnpm\12.6.0\bin\pnpm.mjs <cmd>` 运行（corepack 自身缓存曾损坏，且其内置版本不识别 pnpm 12 的 `bin/pnpm.mjs` 入口，均只影响本机环境）。
- 重建镜像：把 Docker Desktop bin 目录加入 PATH（补 `docker-credential-desktop`）后 `docker compose build console`，镜像内 `pnpm install --frozen-lockfile`、`vue-tsc -b`、`vite build` 全部通过；`docker compose up -d console` 重建容器。
- 验证：容器 healthy；Vite ready；`http://127.0.0.1:5175/` 200；`/src/app/App.vue` 模块转换 200（约 102KB，此前该请求即报错点）。未改源码、API、数据库或迁移。浏览器登录后的路由/接入页走查仍未运行（P303 遗留）。
- 本轮期间另一会话完成了 P304/P305 进度文档重构并落盘（HEAD 亦变为 `0d7452c feat: cursor改造 0000`）；本轮文档按新结构增量更新速览与第 4/7/8 节，未覆盖他轮改动。

## 2026-10-17 IAM P305 — Progress document second-pass refinement

- `docs/项目总览与进度.md` 第 5 节由文字墙改为「轮次 → 证明了什么 / 不证明什么」证据表（P285/P290、P286、P292、P298、P301 五行），去重 P292 双重表述，并将 P285 分片与 P290 全量数字不可相加的约束写入表内。
- 第 3 节消除悬空「本轮」表述：IAM 平台行删除与「当前 HTTP 探测」行重复的未重探句；UI 行与第 4 节 A02 行的「本轮」改为明确的 P301 指代。第 4 节 F02 状态「部分推进」改为词表内「进行中」，补 P304/P305 任务行；第 1 节接手指令首行指向「当前状态速览」；第 8 节执行摘要更新为 P305（P304 明细见上一条），2026-10-17 索引行扩为 P302–P305。
- 文档静态复核通过：任务表状态全部落在第 4 节词表内、无残留悬空「本轮」、内部链接与章节编号 1–8 完整。纯文档改动：未改源码、API、数据库或迁移；未运行测试、构建或运行态探测。

## 2026-10-17 IAM P304 — Progress document deep restructure

- `docs/项目总览与进度.md` 重构为真正的第一阅读入口：顶部 P285–P303 逐轮堆叠摘要压缩为「当前状态速览」表（运行态/数据库/备份/前端/UI 走查/DeerFlow/阻塞/下一步）；第 8 节历史明细（2026-10-13 起，含 P283–P303、回滚事件、Docker 清理、密码重置、A02/A03 迁移等）压缩为「历史轮次索引」，全部逐轮事实以本 CHANGELOG 为准。
- 第 7 节新增「前端依赖 lockfile 对齐」阻塞行，保留 P303 因本机 pnpm store 异常经 `npm pack` 安装 `vue-router`/`@vue/devtools-api` 的事实；第 4 节新增 P304 任务行；第 1/8 节中「见第 8 节/本节首条」的回滚事件引用改指本 CHANGELOG；同步规则第 1 条措辞对齐新顶部结构。
- 章节编号 1–8 保持不变，任务 ID 全部保留。纯文档改动：未改源码、API、数据库或迁移；未运行测试、构建或运行态探测。

## 2026-10-17 IAM P303 — Admin console routing and project integration page

- Added vue-router history routes for all admin PageKey paths; sidebar uses router-link with active highlighting; visited-page lazy mounting preserved; deep links survive login for platform menu entries.
- New platform menu **新项目接入** at `/project-integration` with async `ProjectIntegrationPage.vue` (onboarding steps, input checklist, Python/TS SDK 3s fail-closed notes, secret boundaries, DeerFlow pilot decisions, architecture doc section index). F02 framework adapters remain unimplemented.
- `vue-tsc --noEmit --pretty false` passed. Vite production build passed (`--configLoader runner`); temp output removed. Browser route/integration walkthrough not run. No API, backend, database, or migration change. `package.json` declares `vue-router` and `@vue/devtools-api`; local pnpm CLI was broken so dependencies were unpacked via `npm pack` into `node_modules` for this verification.

## 2026-10-17 IAM P302 — Admin console frontend performance

- Removed pre-mount `await ensureManagementUi()` from `main.ts`; restored sessions bootstrap in parallel (`/auth/me` + management UI registration) behind a loading shell.
- Platform dictionaries load in the background after overview init; group and authorization-simulation pages reuse App dictionaries and load only when active/visited.
- Extracted async feature loaders to `featureLoaders.ts`; Vite `manualChunks` splits `ant-design-vue`. Dev watch polling defaults off; Compose console sets `VITE_DEV_USE_POLLING=true` for bind-mount HMR.
- `vue-tsc --noEmit --pretty false` passed. Vite production build passed (3,206 modules, `--configLoader runner`); entry ~50 KB gzip ~16 KB, ant-design-vue chunk ~876 KB gzip ~270 KB. Browser timing checks were not run. No API, backend, database, or migration change.

## 2026-10-16 IAM P301 — Signed-in walkthrough and backup recheck

- Signed in at http://127.0.0.1:5175/ with the administrator password from the root `.env`. Login succeeded. The overview showed the service as normal and DeerFlow as the current owner-only pilot. On-screen counts were not reconciled.
- At 1440px the sidebar collapsed to a 76px icon rail, stayed collapsed after refresh, and showed text labels again when expanded. It was left expanded. System theme stayed usable and was switched back to the light theme seen at login.
- The model-usage ledger was empty. Result, model, and UTC date filters were visible. `2026-13-40` showed “日期请使用有效的 YYYY-MM-DD” without a usage request for that value. A start date after the end date showed “开始日期不能晚于结束日期”; that inverted pair was not sent together. Dates were cleared afterward.
- At 375px the page used the full-page selector, not a cropped desktop sidebar, and had no page-level horizontal overflow. The selector options were not opened. The viewport was returned to 1440px. No page error or warning was captured after refresh.
- Both `D:\backup\iam-postgres\` dumps and their `.sha256` sidecars were still present. Checksums matched; prefixes `186e2e17` and `1960de15`. Dump contents were not opened and no restore was run.
- Not done: management writes, reconciliation submit, fee currency, failure-reason field, migration, public registration, quota enforcement, and the DeerFlow full suite. No type check, production build, or automated test was run.

## 2026-10-16 IAM P300 — Collapsible admin sidebar

- Desktop admin sidebar can collapse to navigation icons and expand back to the existing text labels. The choice is stored only in the current browser localStorage and defaults to expanded.
- The existing <=650px full-page page selector and the light/dark/system theme behavior are unchanged. No personal/tenant/platform preference priority, API, database, or migration was added.
- `vue-tsc --noEmit --pretty false` and Vite production build passed (3,205 modules); temporary output was removed. The browser stayed on the login page. Admin credentials were not submitted, so collapse, persistence, and the narrow layout were not clicked. Automated tests, readiness recheck, and DeerFlow tests were not run.

## 2026-10-16 IAM P299 — System theme and pilot copy

- The admin appearance control can follow the operating system color scheme. Stored light or dark preferences stay unchanged.
- Overview, resource-grant, and data-scope copy now describe DeerFlow as the only current pilot with owner-only data. They no longer present AI Resume or Knowledge Base as active integrations.
- `vue-tsc --noEmit` and Vite production build passed (3,205 modules); temporary output was removed. The browser was on the logged-out login page. Admin credentials were not submitted, so the signed-in theme and overview were not clicked. No API, database, or migration change.

## 2026-10-16 IAM P298 — Model usage history filters

- Usage summary and event list accept optional model, outcome, and UTC calendar-date filters. An inverted date range returns HTTP 400 before querying. The reconciliation queue stays tenant-and-pagination only.
- The usage page exposes the same filters, resets to page 1, and clears the previous ledger scope. A failed model-catalog read does not fail the ledger read.
- `vue-tsc --noEmit` passed. API-container contract tests passed 6/6. Read-only checks showed healthy Compose services, ready 200, and Alembic current=head `0031_model_usage_reconciliation`. The development-database integration test, Vite production build, and browser checks were not run. No schema or migration change. Backup files were not rechecked. Fee currency and failure-reason fields remain absent.

## 2026-10-15 IAM P297 — Model usage error states

- A failed usage, summary, review, or tenant read now produces an explicit error state instead of zero totals and a successful empty state. Previously successful data is retained; tenant changes clear data from the prior tenant, and pagination changes clear prior-page rows while loading.
- Vue vue-tsc --noEmit --pretty false and Vite production build passed (3,205 modules); temporary build output was removed. Browser normal empty state was checked after hot reload. Error injection and non-empty reconciliation remain unverified.
- No backend/API/schema/database/migration changes or automated tests. See [acceptance record](docs/验收记录.md).
## 2026-10-15 IAM P296 — Model usage UI review

- Reviewed the current administrator model-usage empty state and source contracts. A failed request in the shared load path clears usage, summary, and reconciliation data and then displays successful empty states (P1).
- Fee currency and failure-reason fields remain absent; history filtering supports tenant and pagination only (P2). No source code, API, database, migration, tests, or build artifacts were changed or run. Non-empty/reconciliation flows, light theme, and current multi-viewport checks remain unverified.
- See [acceptance record](docs/验收记录.md) and [project status](docs/项目总览与进度.md).

## 2026-10-15 IAM P295 — Model usage UI fixes

- Added a success-rate summary with an em dash for zero requests, made the tenant label and All tenants placeholder visible, and rendered empty/loading states outside the wide tables. Populated tables retain internal horizontal scrolling.
- Vue type check and Vite production build passed (3,205 modules); temporary build output was removed. Browser checks at 375/768/1024/1440px showed no page-level horizontal overflow; the 375px empty states were centered and visible, and no localhost page errors/warnings were found.
- No automated tests or backend/API/schema/DB/migration changes. Failure-reason fields, fee currency, richer history filters, non-empty rows, reconciliation submission, light theme, and live IAM/Provider acceptance remain open.

## 2026-10-15 IAM P294 — Model usage UI audit

- Read-only browser review of the desktop dark-theme empty state: tenant filter appears blank; success rate is absent; the event API has no failure-reason field; history supports tenant filtering and pagination only; displayed fee currency is unspecified; the empty reconciliation table shows a horizontal scrollbar.
- Empty-state wording and reconciliation safety notice are clear. No code, tests, build, database, migration, or live-readiness checks were changed or run. The P292 responsive/build results are prior evidence, not rerun in this audit. Currency policy awaits user input; non-empty rows, pagination, reconciliation submission, light theme, and narrow-screen behavior remain unverified.

## 2026-10-15 IAM P293 — Runtime status documentation correction

- Corrected operations, architecture, handoff and current-status documents: the 2026-10-14 migration/0031/ready-200 snapshot is historical; P292 Docker named-pipe and API loopback permission failures leave current Compose, database revision/readiness, and backup availability unknown.
- Added a read-only handoff checklist for the user's PowerShell session when the current tool terminal lacks Docker/loopback permissions. It explicitly avoids migrations, `.env` changes, and password resets.
- Documentation-only change. Link/status review passed; no tests, builds, Docker/API probes, database writes, or migrations were run in P293.

## 2026-10-15 IAM P292 — Model usage UI fixes

- Fee summary now distinguishes zero requests (“暂无用量”) from requests with unknown aggregate cost (“费用未知”). Model catalog, usage and reconciliation tables derive their horizontal scroll widths from configured columns; constrained cards/table containers keep page width stable and the usage hint explains horizontal scrolling.
- Added the missing Ant Design Vue `Badge` and `Divider` components to the lazy management registry.
- Vue type check passed; Vite production build passed with 3,205 modules. Browser layout checks at 375/768/1024/1440px showed no page-level horizontal overflow; current empty-state text and Badge registration were confirmed, with no recent app errors or unresolved-component warnings. Build output was written to and removed from a system temp directory.
- Read-only runtime probe after UI verification failed: Docker Compose could not access the dockerDesktopLinuxEngine named pipe; proxied then direct localhost API health/readiness requests were denied. Current DB revision/readiness and protected-backup availability remain unknown. No API, backend, database, or migration change; no automated test suite run. Non-empty usage, unknown-cost response, review submission, light theme and live IAM/Provider acceptance remain open.

## 2026-10-15 IAM P291 — Model usage UI review

- Read-only desktop dark-theme review found page-level horizontal overflow on the usage table and ambiguous summary copy: a zero-request response with `estimated_cost: null` displays “未配置价格”. Review queue policy copy is clear.
- Browser showed the IAM service as normal and a platform-admin session; this does not establish current DB revision/readiness. Both usage and review datasets were empty, so rows, pagination, and reconciliation modal remain unverified; light theme and narrow viewports were not checked.
- No product code, database, tests, or builds changed/run. Findings and evidence limits recorded in `docs/验收记录.md`; follow-up UI changes require a separate implementation request.

## 2026-10-15 IAM P290 — DeerFlow B04 full offline run and model-switch handoff

- DeerFlow Windows Python 3.12 unsharded offline suite completed in 32:06: **17,149 passed, 404 skipped, 3 deselected, 1 failed, 82 warnings**. The sole failure is the guidance budget check: frontend/src/AGENTS.md is 49,630 normalized UTF-8 bytes against a 49,152-byte hard limit (478 bytes over).
- The run followed earlier DeerFlow changes: shortened frontend guidance, made MCP retry timing assert between captured start/finish bounds, and documented timing assertions; the 9 focused checks had passed before this full run. The full suite remains non-green. Per user request, no rerun was started; the unique pytest temp root was confirmed removed.
- Updated the model-switch handoff and current summaries. Next manual continuation: reduce the guidance file by at least 1 KB, then wait for user instruction before running further tests. IAM Docker/API, database revision/readiness/backups remain unknown; no IAM runtime, DB, migration, quota, or Provider operation occurred.

## 2026-10-14 IAM P289 — Model-switch handoff and stale-status correction

- 更新模型切换交接：新会话先读接手手册第 0、8 节和项目进度、PRD、IAM Skill；说明当前目标、工作区权限和最新证据；不得依赖聊天摘要或复用过期迁移授权。
- 将 PRD 与前端 README 的 0031/ready 200 记录标为历史，明确当前 revision/readiness 未验证，并同步本轮进度。
- 未运行产品测试、构建或目标环境验收；未修改源码、数据库或配额。automation-2 已删除，不再周期运行。

## 2026-10-14 IAM P288 — Runtime reprobe and status-document correction

- Repeated read-only checks: Docker Desktop Compose access was denied by the dockerDesktopLinuxEngine named pipe; localhost:8002/ready and localhost:5175 were unreachable. Current database revision/readiness and backup availability remain unknown.
- Corrected current-state summaries in the architecture/startup/handoff docs; A02/A03 migration and archive records remain historical evidence pending a live check.
- No tests, source changes, DB writes, migration, quota changes, or browser acceptance were performed.

## 2026-10-14 IAM P287 — Model-switch handoff and automation stop

- Added a model-switch handoff checklist covering source-of-truth order, workspace permissions, the unresolved IAM runtime/backup conflict, migration and secret gates, confirmed DeerFlow decisions, task IDs, layered verification, documentation sync, and next actions.
- Corrected the handoff summary so historical migration/readiness records are not presented as current runtime facts. P286 frontend verification remains a source/build result only.
- Deleted heartbeat automation-2 at the user request. No source, backend test, Docker/HTTP probe, database, migration, quota, or provider operation occurred.

## 2026-10-14 IAM P286 — Vue type check and production build

- Directly ran the existing vue-tsc noEmit type check and Vite production build using the installed frontend dependencies; both exited successfully. Vite transformed 3,205 modules and emitted 36 files.
- The build output was isolated under the system temporary directory and removed. The pnpm wrapper, browser/A04 flow, backend tests, database, migration, quota, and IAM runtime were not run or changed.
- IAM readiness, current database revision, and protected-backup availability remain unverified under P285; this frontend build does not establish runtime or end-to-end acceptance.

## 2026-10-14 IAM P285 — DeerFlow Windows B04 shard verification and IAM runtime probe

- Re-ran both duration-aware Windows Python 3.12 offline groups with PYTHONUTF8=1 and a short temporary root: group 1 **8,564 passed / 215 skipped / 8,778 deselected / 44 warnings (1,031.95s)**; group 2 **8,587 passed / 194 skipped / 8,776 deselected / 44 warnings (1,178.94s)**. Targeted suites passed **21** then **2** tests; Ruff check/format passed and all pytest temp roots were removed.
- Fixed LocalSandboxProvider to continue evaluating operator mounts when skill projection is unavailable; stabilized projection test fixtures. Suppressed Hypothesis slow-generation health checks only for the randomized batching property case, and made Windows icacls output decoding tolerant.
- Read-only runtime probe could not establish current IAM status: Docker Desktop named pipe denied access and localhost:8002/api/v1/ready was unreachable. Existing migration/backup evidence conflicts with the P284 Skill live snapshot; readiness, current DB revision and archive availability remain unverified. No database, migration, quota, live provider or target service changes were made.
- Not full product acceptance: live IAM login, DeerFlow OIDC/OAuth/owner-only end-to-end behavior, browser checks, and full release gates remain outstanding. Restore Docker access, reconcile the live DB/backup evidence, and continue A04/DeerFlow acceptance.

## 2026-10-14 回滚事件与重建、Docker 深度清理、梳理收尾

- **回滚事件（17:30 前后）：** 本仓库 git 跟踪文件被外部批量恢复到 HEAD（`25a2968`），当日 15:10 后全部未提交修改丢失（脚本兼容修复、文档更新、.gitignore）。`.env`、数据库 0031 状态、`D:\backup\` 归档、运行容器未受影响。已重建：部署脚本 PS 5.1 兼容修复、`.gitignore` 的 `*.tsbuildinfo`、tsbuildinfo 索引移除、进度文档全部最新事实及本条目。教训：多会话并行操作需协调，勿对 IAM 仓库执行 checkout/restore/reset。
- **Docker 深度清理（用户确认含未使用镜像）：** 项目内删除再生 tsbuildinfo 与 `node_modules\.vite`（9.3MB）；`builder prune`×2 清空构建缓存 25.21GB→0B；`image prune -a` 回收 5.0GB（镜像 41→11 个）。⚠️ DeerFlow 镜像 `iam-deerflow-package-check:20261011`、`deer-flow-dev-gateway:latest` 及 `python:3.12-slim` 等基础镜像被删，B03/迁移构建前先核对网络。stopped 容器与未使用卷未动。清理后 IAM 三容器 healthy、ready 200。
- **梳理收尾：** 删除无法登录的僵尸账号 `admin@localhost.test`（事务内连带 1 行 tenant_memberships，其余 9 张关联表 0 行；剩余 users=1）；修正进度文档对不存在文件 `USER_INPUT_CHECKLIST` 的悬空引用。三个 `.env` 示例、key-rotation compose、requirements.txt+lock、pnpm-workspace、deploy/caddy、生产 Dockerfile/nginx、CHANGELOG、sdk、backend/tests 均核查后保留。

## 2026-10-14 A02/A03 完成：真实备份、隔离恢复演练与开发库迁移 0021→0031

- 按用户授权完成迁移门禁全链路：备份目录确认为 `D:\backup\iam-postgres`；生成真实归档 `iam-postgres-20261014T081157Z-e02dac03.dump`（SHA-256 186e2e17…d24bd，容器内 `pg_restore --list` 通过）；`verify-postgres-restore.ps1` 随机隔离库恢复演练通过（SHA-256 校验、恢复后 revision 0021、核心表核对、隔离库删除、原库未动）。另有并行会话生成迁移后 0031 归档（082113Z，SHA-256 1960de15…edf4b9）及第二次隔离恢复演练通过。
- 用户明确授权后执行 `--profile migrate run`：首次失败即停止（`password authentication failed for user "iam"`）。根因是 postgres 卷 9/27 初始化后 `.env` 于 10/9 修改了 `IAM_POSTGRES_PASSWORD`：数据库 role 密码停留在旧值，旧 api 容器持旧密码可连，migrate 用新密码被拒（容器内 scram 认证对比证实）。修复：postgres 容器内 `ALTER USER iam` 对齐当前 `.env`（密码不落主机命令行/日志），`up -d api console` 重建；二次迁移 0021→0031 一次通过。
- 迁移后核验：`alembic current` 与 heads 一致为 `0031_model_usage_reconciliation`，`/api/v1/ready` 200，api/console/postgres 全部 healthy。未 bootstrap（已有用户），公开注册与配额 enforcement 保持关闭；本次授权仅覆盖 0021→0031 这一次迁移。
- 修复部署脚本 PowerShell 5.1 兼容（脚本逻辑与门禁未变）：5 个 `.ps1` 补 UTF-8 BOM；`backup-postgres.ps1`/`verify-postgres-restore.ps1` 的 here-string 先转 LF 再经 base64 传给容器内 `sh -ec`（PS 5.1 传参不转义内嵌双引号、here-string 保留 CRLF，均导致容器内脚本损坏）。
- 管理员密码重置：`.env` 的 `IAM_ADMIN_PASSWORD` 为占位符且与两账号哈希均不匹配（bootstrap 不重置既有账号）；经用户选择随机密码重置，api 容器内生成 20 位随机密码 UPDATE `admin@example.com` 的 `password_hash`，`.env` 已同步，密码不落命令行/日志。
- 文件清理（spec: cleanup-unneeded-files）：移除 git 误跟踪的 `frontend/tsconfig.tsbuildinfo` 并 ignore `*.tsbuildinfo`；`secure-backups/iam-dev` 备份移至 `D:\backup\iam-postgres`；删除 `.t`、`backend/.ruff_cache`、`frontend/dist`、`sdk/typescript/dist`；删除僵尸账号；同步 PRD、前后端 README、验收记录、快速启动指南、部署运维。真实登录（A04）待用户执行。

## 2026-10-14 快速启动指南独立成文与部署运维简化

- 按用户要求将快速启动指南从 `docs/部署与运维.md` 拆出，新建独立文件 `docs/快速启动指南.md`：前置检查、`.env` 创建、`start-local.ps1` 启动、readiness 探测、需授权的 migrate/bootstrap、访问入口、日常命令与隔离验证，并注明当前开发库 0021 / head 0031、ready 503 `database_migration_pending` 状态。
- `docs/部署与运维.md` 精简为要点式手册（约 450 行 → 约 240 行）：环境状态、本地开发与故障排查、备份恢复、迁移授权与回退、生产发布、TLS/RSA 轮换、账户会话邮件、模型核对、部署输入清单；移除内嵌快速启动章节改为链接，压缩重复解释与长段落。
- 所有命令、参数与门禁表述保持不变；同步 `docs/项目总览与进度.md`（导航表 5 份 → 6 份、第 6 节引用、D01 备注、第 8 节摘要）。本轮仅文档整理与静态核对；未运行启动、迁移、备份/恢复、生产预检或产品测试。

## 2026-10-14 IAM P284 environment check and isolated full validation

- Docker Engine is available again. Read-only probes report Console/PostgreSQL healthy, API unhealthy, /api/v1/health 200, and /api/v1/ready 503 database_migration_pending; live Alembic revision is 0021_resume_wallet_perms, while source head is 0031_model_usage_reconciliation.
- verify-local.ps1 passed the complete backend suite against an isolated random PostgreSQL test database (169/169); the iam_test_* database was confirmed removed. The backup script's ValidateOnly passed but created no archive.
- Re-ran Vue type checking and Vite production build against the current read-only mounted source: 3,205 modules built successfully to temporary container storage. No IAM product source or main database changed.
- Reviewed pending migration source and preserved the migration gate: no real protected backup exists and no explicit migration authorization was given. Real IAM login and DeerFlow target/Provider/browser acceptance remain pending.

## 2026-10-14 DeerFlow B04 extension-manager tool gates and notification budget fix

- The second ordered 104-file slice reported **2,368 passed, 2 failed, 86 skipped, 4 warnings (502.53s)** before the final notification fix. Thirty-five extension-manager test functions (38 parameterized cases) now skip explicitly without `uv`; the exact host API pin test follows source `API_VERSION`.
- Fixed the notification budget race with `asyncio.timeout().expired()` and a clamped shared deadline. Focused lifecycle, extension-manager and API-pin regressions passed **126 tests** with **40 uv-dependent skips**; Ruff check/format passed. The slice was not rerun after this code fix.
- The remaining observed slice failure is local venv metadata `deerflow-extension-api==0.2.16` vs source/lock `0.2.18`. The user reported an IAM page saying database migration is pending; this turn did not query the target DB or run a migration. Temporary test roots were deleted.

## 2026-10-14 DeerFlow B04 Windows shell harness and missing-tool classification

- `test_dev_entrypoint.py` now writes its extracted sync block to a temporary POSIX file before invoking Git Bash, avoiding Windows reinterpretation of a long `sh -c` argument.
- Makefile injection tests explicitly skip when GNU make is absent; the frozen uv-project bootstrap and config-upgrade shell tests skip when `uv` is absent. Static contract tests remain active.
- `test_dev_entrypoint.py`, `test_extension_dependency_sync.py`, and `test_config_version.py`: **44 passed, 13 skipped**. Ruff check/format and `git diff --check` passed; the temporary test directory was deleted.
- The original second 104-file slice and full suite were not rerun. No IAM product code, database, migration, quota, or frontend source changed.

## 2026-10-14 DeerFlow B04 Windows path and interpreter fixtures

- Normalized the expected JSON detector path and extension source path to POSIX form in cross-platform tests. The deploy extras test now provides a known runnable Python shim to Git Bash instead of relying on the host PATH to expose the active venv.
- `test_detect_blocking_io_static.py` and `test_deploy_uv_extras.py` passed **56 tests**; the controlled extension uv-project path case passed **1 test**. Ruff check/format passed on the four touched Python files; all test temp roots were removed.
- The second 104-file slice was not rerun; its 82 failures remain the original observed count and are still being triaged. No production deploy script, IAM, database, or quota behavior changed.

## 2026-10-14 DeerFlow B04 second ordered slice and DeltaChannel property-test stability

- The next 104 path-sorted offline test files reported **2,339 passed, 82 failed, 35 skipped, 4 warnings in 521.70s**. Failures remain only partially triaged; observed categories include unavailable `uv`/GNU make and Windows/Git Bash path/process differences. This partial slice is not a full-suite result.
- Reproduced a Hypothesis `HealthCheck.too_slow` failure in `test_merge_message_writes_randomized_differential`. The strategy now emits bounded primitive data and materializes LangChain/Pydantic messages in the test body; the pure generator suppresses only the `too_slow` check to avoid scheduler noise. The DeltaChannel module passed **35/35**; Ruff check and format passed.
- Removed the isolated test root. No DeerFlow production runtime, IAM database/migration, or quota setting changed. Real IAM/Provider acceptance remains open.

## 2026-10-14 DeerFlow B04 顺序切片与 Windows 测试修复

- 修正 DeerFlow 超时失败标记测试按当前 OS mock runner；live-policy 子进程显式使用 UTF-8 解码，并在 Windows 最小环境中保留 `SystemRoot`/`WINDIR`；没有 GNU make 时，4 个依赖 Makefile dry-run 的用例明确 skip。压缩 `frontend/src/AGENTS.md` 的模型目录段落，保留用户隔离、AbortSignal 和授权边界要求，文件回到指导预算内。
- 验证：timeout **8 passed、6 skipped**；guidance **12 passed**；live-policy **7 passed、4 skipped**；两份 Python 文件 Ruff check/format 通过。按路径排序前 104 个离线测试文件切片 **3,099 passed、67 skipped、3 deselected、0 failed、16 warnings（476.57s）**；隔离目录已清理。
- 切片不代表全量：最近完整离线快照仍是 17,062 passed / 142 failed / 349 skipped / 3 deselected / 0 errors；另一次全量尝试约 17% 退出码 1073807364、无 pytest 汇总，原因未确认。未执行 IAM 迁移或真实 IAM/Provider 验收。
- A01 只读复核：Docker Desktop CLI 存在但 Linux Engine named pipe 不可用；绕过代理后 API readiness loopback 连接拒绝，无法刷新容器/DB revision。未启动服务或写数据库。

## 2026-10-14 DeerFlow B04 Windows 超时测试 runner 修正

- 修正 `test_timeout_output_carries_authoritative_failure_marker`：按平台 mock `_run_windows_command` 或 `_run_posix_command`，避免 Windows 上调用真实 `make test`。生产沙箱代码未改。
- `test_local_sandbox_command_timeout.py`：**8 passed、6 skipped**；Ruff check/format 通过。隔离测试目录已清理。
- 完整离线套件重跑约 17% 时以退出码 `1073807364` 结束，没有 pytest 最终汇总；不作为全量结果。最近可用完整快照仍为 17,062 passed / 142 failed / 349 skipped / 3 deselected / 0 errors（82 warnings，44:15）。未执行 IAM 迁移或真实 IAM/Provider 联调。

## 2026-10-13 B04 DeerFlow Agent、Crawl4AI 与 Windows URI 测试修复

- DeerFlow `test_custom_agent.py` 的 API fixture 通过 mock `_authenticate` 建立显式测试用户与 agents read/write/delete/admin 权限，CRUD 断言继续经过真实 permission decorator；授权策略由独立路由授权测试覆盖。Crawl4AI 离线测试对 URL safety resolver 固定为公网测试地址，保留 SSRF 私网拒绝用例。MCP Windows file URI 断言根据 `tmp_path` 实际盘符生成，不再要求测试目录位于 `C:`。未改生产逻辑。
- 三文件聚焦套件 **171 passed、1 skipped、1 warning（23.06s）**；Ruff check/format 通过。临时测试目录已清理。
- 本执行环境的 Git status/diff 调用报 `Invalid executable path`，无法枚举工作区差异；没有执行 git 清理、提交或重置。
- 最近完整 DeerFlow 离线套件快照仍为 **17,062 passed、142 failed、349 skipped、3 deselected、0 errors、82 warnings（44:15）**，该快照早于本次三类测试修正，未重跑全量。剩余失败包括缺少 `uv`/`make`、Windows `WinError 10106`、虚拟环境 extension API metadata 0.2.16 落后源码/lock 0.2.18 及其他待分类项。未做 IAM/DeerFlow 数据库迁移、真实 IAM/Provider 联调或 quota enforcement 验收。

## 2026-10-13 B04 context and Gateway-service focused verification

- `test_context_compaction.py` and `test_gateway_services.py`: **212 passed**. No code change, and no target DB/IAM/provider was touched.
- Used an isolated `DEER_FLOW_HOME` and pytest basetemp; the temporary root was removed. The full suite was not rerun; last full snapshot remains the earlier 17,004/186/349/3/5 result.
## 2026-10-13 B04 extension runtime test-fixture follow-up

- Fixed the single stale fake-Request fixture in `test_extension_task_store_runtime.py` that omitted FastAPI `request.state`; no Gateway runtime behavior changed.
- Extension task runtime focused module: **15 passed**. Ruff check/format passed; isolated pytest and cache roots were removed.
- No full rerun; last full snapshot remains 17,004/186/349/3/5. Other independent focused runs are recorded in the progress document. Missing `uv`, `WinError 10106`, and remaining failures stay open.
## 2026-10-13 B04 DeerFlow DNS and PAT scope contract triage

- FastCRW web-fetch tests now use a deterministic public DNS answer in offline runs; production SSRF validation remains unchanged. FastCRW + thread-route focused tests: **142 passed, 1 warning**.
- The PAT scope test previously required equality with the entire Gateway permission catalog, contradicting the curated path/method allowlist. It now pins the exact 16-scope PAT subset. API and Gateway guidance now accurately list selected personal Agent and memory endpoints. PAT runtime behavior did not change (only its explanatory module docstring did). PAT auth/repository/vault tests: **63 passed, 1 warning**.
- The full offline suite was not rerun; the last full result remains 17,004/186/349/3/5. `uv`, `WinError 10106`, and other failures remain open. Ruff check/format passed; temporary roots were removed. No migration, live IAM/provider, or quota-enforcement validation ran.
## 2026-10-13 文档合并与多项目简单接入方案

- 将 docs 的 9 份英文文件名文档收拢为 5 份中文文件名文档：项目总览与进度、产品需求、技术架构与接入、部署与运维、验收记录；保留任务 ID、验证证据和当前阻塞，历史实施记录归档在本文末尾。
- 更新根 AGENTS、根/前后端 README、启动脚本提示和 IAM Skill 的相关引用；简化重复 API/SDK 与历史状态描述。记录多项目低门槛接入的目标和待实现通用封装，当前仅 DeerFlow 为业务试点。
- 只运行文档目录、相对链接、旧文件名引用与关键内容静态检查；未运行产品测试/构建、数据库迁移、备份/恢复或真实 IAM/Provider/browser E2E。本轮宿主机 readiness 探测被沙盒套接字权限拒绝，当前运行状态沿用已有带日期证据。

## 2026-10-13 B04 DeerFlow Windows Gateway test-fixture triage

- Reproduced seven failures in three focused test files: deploy subprocess output decoded through the Windows GBK locale, and Gateway fake Request objects omitted `state`. Added explicit UTF-8 replacement decoding and realistic request state to the test doubles; no DeerFlow production code or IAM frontend was changed.
- `test_gateway_startup.py`, `test_gateway_checkpoint_mode.py`, and `test_thread_regenerate_prepare.py`: **45 passed, 1 warning**. Ruff check and format passed; isolated pytest/lint roots were removed.
- The last full backend snapshot remains 17,004 passed / 186 failed / 349 skipped / 3 deselected / 5 errors; no full rerun after these targeted fixes. Missing `uv`, `WinError 10106`, and remaining failures stay open. No migration, live IAM/provider, or quota enforcement ran.
## 2026-10-13 B04 Windows Studio route regressions

- The full offline suite had five Studio setup errors because the child Python used the Windows GBK default text encoding while a locked dependency opened a UTF-8 OpenAPI asset. The Studio test child now sets `PYTHONUTF8=1`; startup logs decode with replacement so future startup errors remain visible.
- The cross-version persistence test now waits for the runtime in-memory store periodic disk flush while the server is still alive before simulating a restart. This avoids checking a file before the runtime 10-second flush and avoids relying on force-termination shutdown hooks.
- The Studio route module passed **6/6**; Ruff check/format passed; its temp root was removed. Full suite was not rerun, so the prior 17,004/186/349/3/5 snapshot remains the last full result. Missing `uv`, `WinError 10106`, and other failures remain open. No database migration/live provider/quota checks ran.

## 2026-10-13 B04 DeerFlow full offline suite rerun

- Latest Windows Python 3.12 offline backend run: **17,004 passed, 186 failed, 349 skipped, 3 deselected, 5 errors, 99 warnings** in 35:00. The number of Windows-conditional skips increased by three; unsuccessful items total 191 (failures + errors), so the suite is still not passing.
- Known issues: extension-manager cases cannot find `uv`; a live-policy subprocess hits `WinError 10106`; five LangGraph Studio setup errors are obscured by UTF-8 decoding of the startup log, and the underlying server startup cause remains unknown. Other failures still need individual triage.
- The pytest temp root was removed. No migration, live IAM/provider, or quota-enforcement checks ran; no test source was deleted.

## 2026-10-13 B04 DeerFlow owner-scoped skill cleanup and failure triage

- Implemented owner-scoped custom skill cleanup in `UserScopedSkillStorage` and exposed it through `GatewayOwnerDataDeleter`; it removes only the selected user's custom packages, history, and private skill-state entries, preserves global legacy/integration skills and their per-user preferences, rebuilds only that user's projection, and refreshes only that user's prompt cache. This capability is not yet exposed as a product data-job/API/UI scope.
- Full offline backend snapshot remains **17,007 passed, 191 failed, 346 skipped, 3 deselected** (before the later test fixes). Browser modules passed **87/1 skipped**; Lark broker, user-scoped skill storage, and owner-data deleter passed **76 tests, 6 skipped**. The six skips include three POSIX launcher runtime tests skipped on Windows; they were not run on Linux in this turn. pnpm/checkpointer/store focused regressions passed **3/3**.
- Fixed the Windows Lark fake-executable test path and bypassed inherited system proxies in its localhost failure test. Ruff check/format passed on the five current Python files; pytest temporary roots were removed. Missing `uv` and the live-policy subprocess `WinError 10106` remain environment blockers; no migration, live IAM/provider, or quota enforcement ran.

## 2026-10-13 B04 DeerFlow 完整套件归因与 Windows 测试稳定性

- 完整离线后端快照为 **17,007 passed、191 failed、346 skipped、3 deselected**；该次运行包含六个同步后的失败归因模块，但早于后续浏览器 DNS 测试夹具及 Windows 测试修正。浏览器自动化两模块随后 **87 passed、1 skipped**；pnpm 路径与 checkpointer/store singleton 定向用例 **3/3 passed**。完整套件尚未在这些后续测试调整后重跑。
- 修正 Windows pnpm 测试对 `.cmd` 大小写的错误假设，并把并发 singleton 测试的同步等待上限从 3 秒放宽到 10 秒；无生产 checkpointer 逻辑变更。缺少 `uv` 会阻断 extension manager 测试；live-policy 子进程在当前环境遇到 `WinError 10106`。其余全量失败仍需逐项分类。
- Ruff check/format 通过；所有本轮 pytest 临时目录已删除并确认不存在。未运行数据库迁移、真实 IAM/Provider 调用或 quota enforcement。

## 2026-10-13 B04 DeerFlow 失败归因模块测试契约同步

- DeerFlow 六个失败归因模块的测试夹具同步到当前 auth context、权限集、OIDC identity、route request state、共享删除 helper 与 scheduled-run mock 签名；没有修改生产逻辑。
- 验证：六模块 **301 passed、3 skipped**；6 个变更 Python 测试文件 Ruff check/format 通过。上一轮完整离线后端 **16,896 passed、302 failed、346 skipped、3 deselected**，发生在夹具同步之前；未在最新测试树重跑。项目 guidance 预算回归 1/1、MCP config secrets **195 passed**；本轮 pytest 临时目录均已清理。
- 未执行 IAM migration、数据库写入、真实 IAM/Provider 调用或 quota enforcement；B04 继续分类完整套件失败，A01/C01/C02 仍待目标环境。

## 2026-10-13 B04 DeerFlow Windows 路径回归修复与验证

- DeerFlow 在 Windows 下的长文档路径超过系统路径预算时，现在通过项目内稳定的 documents/.short/<digest> 物理别名访问同一逻辑文档；旧路径仍可读，逻辑 stored_relpath 与数据库 schema 不变。
- DeerFlow focused regression 65 passed、2 skipped；完整 blocking-I/O 140 passed、3 skipped、0 failed。Ruff check/format 对 9 个变更 Python 文件通过；临时测试目录已清理。
- 该路径修复后的完整离线结果与后续测试夹具复测见同日较新 B04 条目；全量失败继续分类。未运行 IAM 数据库迁移、真实 IAM/Provider E2E；quota enforcement 继续关闭。
## 2026-10-12 DeerFlow 未知模型结果保留待核对

- 对齐用户确认的“保留待核对”：LangChain 模型调用发生异常或 callback 在终态前关闭时，若无法证明 Provider 未接收请求，不再以失败/0 输出结算；清理本地 callback 后保留 IAM reservation，由其 10 分钟到期后进入管理员核对。只有可靠证据确认 Provider 未被调用才可释放。
- DeerFlow focused IAM usage/outbox、memory commit 与 Harness boundary 回归 **33/33**；Ruff check/format 通过。完整离线后端 **16,775 passed, 419 failed, 346 skipped, 3 deselected**（48 分钟）；blocking-I/O **114 passed, 28 failed, 1 skipped**。未解决的套件失败进入 B04 分类；未迁移数据库、未启用配额、未进行真实 IAM/Provider 请求。

## 2026-10-12 · DeerFlow Provider 路径静态审计

- 静态核对当前仓内 DeerFlow `backend/app` 与 `backend/packages/harness/deerflow` 的内置生产 Python 入口：共享模型工厂、Gateway 单次调用及 DeerMem 专用 hook 均处于 LangChain callback 用量管道中；Codex Responses 自定义 Provider 继承 `BaseChatModel` 并由共享工厂构造；唯一直连 `init_chat_model()` 的内置生产路径是已接入 hook 的 DeerMem。外部扩展动态加载的 Provider 未穷尽。
- IAM 用量 `request_id` 是每次 LangChain invocation 生成的本地幂等 ID。Codex 内部对特定 HTTP 状态的重试仍按一个 invocation 计量，待依据 Provider 计费语义确认是否需要 attempt 级记账。
- 本轮只读静态检查；未运行测试、构建、真实 Provider/IAM 请求或数据库操作。目标环境/API readiness 阻塞真实验收；quota enforcement 保持关闭。

## 2026-10-12 · DeerFlow 后台记忆模型用量接线

- 修复 DeerMem 自建模型的 timer/debounce 路径未稳定挂载模型用量 callback 的缺口。Gateway 在后台调用时重新加载活动用户与匹配 OIDC vault，会话有效时绑定服务端模型档案并创建单次 usage callback；Harness 只把 callback 放进当前 invocation config，结束后移除并关闭，不将凭证或 capability 放入队列。
- `model_usage.enabled=false` 时保持不计量；启用时若身份/vault/admission 不可用则拒绝 provider dispatch。相关现有 memory commit 与 usage callback 回归 **20/20**、Harness boundary **1/1** 通过，运行于 DeerFlow Windows Python 3.12 隔离目录，测试临时目录已删除。
- 6 个变更 Python 文件 Ruff check/format 通过；全量套件、IAM/Provider 联调、DB migration 或前端构建未运行；IAM readiness 仍为 503，配额 enforcement 保持关闭。



## 2026-10-12 · DeerFlow B01 权限映射与 A01 环境盘点

- 对照 IAM migrations `0026–0030`、DeerFlow Central IAM 示例配置、Gateway permission constants 与 IAM adapter，新增完整 route/model/tool permission map、普通用户/运维角色最小授权建议、owner/self、存量 issuer/sub 绑定与 PAT fail-closed 说明。静态比较得到配置样例 36 个唯一映射，其中 35 个 DeerFlow code 命中 catalog；`model:use` 使用 `model.invoke`，catalog 中的 `deerflow.model.use` 当前未被样例引用，不可视为等价 grant。实际应用/tenant/model UUID 与角色 grant 仍待部署方输入。
- Docker CLI 已恢复。只读确认 IAM Console/Postgres healthy、API unhealthy，`/api/v1/ready` 为 503 `database_migration_pending`，数据库 revision 为 `0021_resume_wallet_perms`；注册挑战相关表不存在，未发现运行中的 DeerFlow 容器。
- 本轮仅更新文档；未改源码、未运行测试/构建、未启动或停止容器、未备份/迁移/写库，也未调用真实 IAM 或 Provider。

## 2026-10-12 · 建立持续维护的模型交接与后续计划

- 新增 `docs/项目总览与进度.md`，记录当前实现/验证/运行基线、已确认决策、任务 ID/优先级/依赖/验收、源码与验证入口、阻塞和接手指令；新增根 `AGENTS.md`，要求每轮同步当前进度、证据和下一步。
- 同步整体/前后端 README、PRD、接入计划与部署输入入口；修正模型治理中过期的全量状态和 0031 验证描述，将组织共享与上游 revoke 接线从本阶段未决项移出。仅整理相关文档，未触发全项目 `--更新` 审计。
- 只读 HTTP 重查 Console 200、API readiness 503 `database_migration_pending`；当前终端找不到 docker.exe，数据库 revision 沿用最近核实的 0021，未刷新。源码 migration 图确认 IAM head 0031、DeerFlow Harness head fd_0028；本轮未运行产品测试/构建、归档/恢复、迁移、role grant 或真实 E2E。完成文档链接与路径静态核对。

## 2026-10-12 · 清理过期测试临时目录

- 删除并核验 7 个过期 pytest 临时根目录均不存在：`.df-agents-tmp`、`.df-agents2-tmp`、`.t`、`.tmp-deerflow-iam-memory`、`.tmp-deerflow-iam-memory-final`、`.tmp-deerflow-scope-final`、`iam-test-5gz2bgca`。未删除测试源码或项目运行数据。
- 前端、后端源码静态搜索未发现 TODO/FIXME/NotImplemented 占位；本轮没有运行测试。

## 2026-10-12 · Docker CLI 与 readiness 排障

- 复核 Console HTTP 200、API readiness `503 database_migration_pending`。当前 PowerShell 的 `docker` 解析至 `C:\Windows\System32\docker` 并因拒绝访问无法启动；常见 Docker Desktop CLI 路径不存在，故无法刷新容器/数据库状态。
- 在启动指南增加命令解析诊断、显式 `-DockerPath` 用法和禁止在 CLI 不可用时操作迁移/数据库卷的提示。没有运行 migration 或测试。

## 2026-10-12 · migration 0022–0031 影响审阅

- 逐项检查源码 migration，确认公开注册默认关闭、权限目录 migration 不自动授予角色；`0024` 移除挑战密码摘要列，`0025` 消费未绑定授权快照的待验证挑战，`0022` downgrade 会删除注册相关表，`0031` 对既有人工核对账目拒绝 downgrade。
- 只读探测 Console HTTP 200、API readiness 503；当前执行环境无 Docker CLI，未能刷新开发库 revision。没有执行 migration、备份、数据库写入或 role grant。执行前需要受保护备份目录和明确迁移授权。

## 2026-10-12 · DeerFlow Windows 文档长路径兼容

- DeerFlow 项目文档在完整 Windows 路径超过 240 个 UTF-16 单元时使用短物理文件名，数据库与接口仍保留用户原始显示名；转换器需要的后缀保留，MIME 从显示名推断，历史 `original/{name}` 路径保持可读。
- 项目/文档/线程/运行四组路由回归在短临时根目录下 **225/225 通过**；4 个修改的 Python 文件 Ruff check/format 通过。最初长 basetemp 本身触发 WinError 3，使用短目录复跑通过并删除测试临时目录。未改 IAM schema、migration、开发数据库、角色授权或 Vue 代码。

## 2026-10-12 · DeerFlow owner-only 决策与部署/验证基线

- 用户确认 DeerFlow 第一阶段项目、线程、运行、文档仅本人访问；记录为当前产品规则。IAM owner/self scope 必须与本地 `user_id` 查询过滤求交，tenant/organization sharing 继续 fail closed。未来开放共享需另行决定资源映射、授权和历史回填。
- DeerFlow IAM/OIDC/model/vault/usage/data_scope 专项测试选择 169/169 通过（Windows Python 3.12，mock/隔离）。全量 Windows 非 live 测试完成过一次长 basetemp 运行：16,770 passed、422 failed、345 skipped、3 deselected（46:36）；一个深路径代表失败改用短 Temp 路径后通过。短路径全量重跑在约 34% 因 `WinError 10106` 中断，完整全量仍未验收。没有把剩余失败统一归因于环境。
- IAM Console HTTP 200；API unhealthy、readiness 503 `database_migration_pending`。数据库 `0021_resume_wallet_perms`，源码 head `0031_model_usage_reconciliation`。只读备份预检通过，不生成归档、不写数据库；未运行 migration。
- 修正 `docs/部署与运维.md` 过时的 `0027` 当前状态记载，并同步 PRD、整体/前后端说明、架构、接入计划、待输入清单和 `iam-project` Skill。项目源代码未修改；DeerFlow/真实 IAM/浏览器 E2E 未做。

## 2026-10-12 · DeerFlow Python 提取回退保留链接

- Node/Readability.js 不可用时，Python article fallback 改为保留 article/main 中的安全链接和图片目标，并移除脚本、嵌入/表单等活动内容及不安全 URL。
- 既有 `tests/test_web_fetch_relative_links.py` 修复后 50/50 通过，Ruff check/format 通过；没有新增或遗留测试文件，隔离 pytest 目录已删除。
- 修复前全量后端快照 16,750 通过、442 失败、345 跳过、3 deselected；阻塞 I/O 116 通过、26 失败、1 跳过。修复后未重跑全量，其余失败仍需归因。

## 2026-10-12 · DeerFlow 全模型授权与回归结果

- Gateway 统一模型工厂为每次 provider dispatch 校验确切模型档案的 `model:use`；DeerMem 后台模型另校验实时用户/vault、记忆本人读写范围和目标模型权限，Gateway 注入 Harness 回调并保持 Harness 不依赖 `app.*`。
- 定向模型/记忆回归 28/28、Harness boundary 1/1、Ruff check/format 通过。Windows 临时目录隔离后的 DeerFlow 全量后端为 16,750 通过、442 失败、345 跳过、3 deselected；阻塞 I/O 为 116 通过、26 失败、1 跳过。抽查 web-fetch 用例 22 失败、26 通过，Python readabilipy fallback 未保留链接目标（本机缺 Node/npm）；其余全量失败尚未逐项归因。
- 删除本轮临时授权测试文件、编译产物和 pytest 隔离目录，保留既有测试文件及其余未提交改动。未修改 IAM migration/开发数据库，未完成真实 IAM/Provider E2E。

## 2026-10-11 · PRD 与项目文档状态一致性

- 更正 0031 的验证进度：隔离 PostgreSQL 全量套件 169/169、Vue 检查和 3205 模块 Vite production build 已通过；明确开发数据库仍为 0021、真实 IAM/DeerFlow E2E 未验收。
- 把 AI Resume 与 Knowledge Base 旧接入说明标为已清理/当前范围外，并同步 PRD、根/前后端 README、架构、接入计划、模型网关、用户输入清单和项目 Skill。
- 本次仅修订文档，不迁移数据库、不修改运行代码、不改变角色 grant。

## 2026-10-11 · 模型用量账目服务端分页

- 移除管理员模型账目列表固定 500 条上限，`GET /admin/model-usage/events` 改为 tenant-filtered `items/total/limit/offset` 响应，limit 限制 1–200，并用创建时间与事件 ID 稳定倒序。
- 管理台账目表增加 API 驱动的总数和服务端翻页，租户/页大小变化时回到第一页；新增 PostgreSQL 集成用例覆盖总数、跨页完整性和排序。
- 修复 `verify-local.ps1` 对 Docker Hub EOF 的检测，使其同时识别 `registry-1.docker.io` 与 `auth.docker.io`。首次命中令牌端点 EOF 后重跑成功；该次走在线构建路径，离线 fallback 未单独触发。
- 同步 PRD、前后端 README、整体架构、运维/启动手册、用户输入清单、Skill 和根 README。隔离 PostgreSQL 全套迁移至 `0031_model_usage_reconciliation` 后 **169/169 通过**；Vue 类型检查和 3205 模块 Vite production build 通过。开发库仍为 `0021_resume_wallet_perms`，没有迁移；真实 IAM/DeerFlow E2E 未完成。

## 2026-10-11 · 模型待核对运维契约与运行页复查

- 运维手册补充待核对列表的筛选、分页上限、响应结构、稳定排序和并发 409 处置指引，并同步 PRD、整体架构、前后端 README 与项目 Skill。
- 浏览器只读复查确认管理台登录页可显示，但数据库迁移未就绪时认证按钮禁用；开发库仍为 `0021_resume_wallet_perms`、源码 head 为 `0031_model_usage_reconciliation`。本轮未执行迁移或后端集成测试。

## 2026-10-11 · 模型调用未结预留待核对闭环

- 按用户选择“保留待核对”实现：IAM 即使关闭 RPM/TPM 拦截也会在 Provider 调用前持久化预留；10 分钟到期只进入核对队列，不自动按预留上限计费或释放。待核对预留继续占保守 TPM。
- 新增 IAM migration `0031_model_usage_reconciliation`、带总数分页的管理员待核对列表/处置 API、同事务审计，以及管理台实测/估算用量结算和“确认 Provider 从未调用”后释放的表单。手工用量标记来源，延迟可空；释放不产生用量事件。
- 更新 PRD、模型网关决策、架构、运维、DeerFlow 集成计划、用户输入清单、IAM 前后端 README、DeerFlow 根/后端中英文 README、架构、双语变更日志、根 README 和项目 Skill。DeerFlow 实际 Token 仍需从 Provider 日志/账单人工核对，不能从崩溃窗口自动恢复。
- 后续实现与验证：待核对队列改为 total/offset/limit 分页，避免 500 条上限隐藏积压。`vue-tsc --noEmit`、Vite 临时目录生产构建、分页后 6 个 Python 文件 AST 和 Pydantic 核对契约检查通过。完整 pytest 在可用 DeerFlow venv 中因缺少 `pwdlib` 未能收集；PostgreSQL 分页集成未运行。开发库仍为 `0021_resume_wallet_perms`、API readiness 为 503，`0031` 未迁移。未进行真实 IAM/Provider E2E。

## 2026-10-11 · 部署预检与本地登出决策复核

- `deploy/backup-postgres.ps1 -ValidateOnly` 通过：Compose 配置可解析、PostgreSQL 认证成功、`pg_dump`/`pg_restore` 可用；没有创建归档或写入数据库。
- 当前 IAM API readiness 仍为 HTTP 503 `database_migration_pending`；开发库为 `0021_resume_wallet_perms`，源码 head 为 `0030_deerflow_preference_permissions`。真实试点验收仍等待受保护备份目标与迁移授权。
- 用户确认 DeerFlow OIDC 登出只清理本地 vault session，不向 issuer 发送 access/refresh token。本轮未改应用代码、未迁移数据库；生产预检仅作源码审阅。

## 2026-10-11 · DeerFlow webhook production guard

- The `DEER_FLOW_ALLOW_UNVERIFIED_GITHUB_WEBHOOKS` escape hatch is now disabled whenever `DEER_FLOW_ENV` or `ENVIRONMENT` explicitly selects production. With no webhook secret, production does not mount the route and the runtime handler rejects the unsigned request.
- Full focused browser and webhook regressions passed 76/76, including explicit data-scope denial and authorization-service failure close codes; the public URL SSRF test uses deterministic DNS results. Ruff check/format passed. No IAM UI, DB, or permission mapping changed.

## 2026-10-11 · DeerFlow 浏览器实时流中央 IAM 鉴权

- Gateway 浏览器 WebSocket 在 thread lookup 和保留浏览器 session 前检查 `threads:read/write` 及匹配线程的读写 owner/self data_scope；本地签名 session `sid` 继续绑定到服务端 OIDC token vault。保留本地 owner / Origin 校验，授权服务失败时连接失败关闭。
- 浏览器与 webhook 完整聚焦回归 **76/76 通过**，含数据范围拒绝与授权服务失败关闭码；公网 URL SSRF 用例使用固定 DNS 结果，避免外网解析依赖；Ruff check/format 通过。未改前端、迁移、角色 grant、数据库或登出行为；真实 IAM/WebSocket E2E 待完成。

## 2026-10-11 · DeerFlow 个人偏好中央 IAM 授权

- 偏好 GET/PATCH 分别要求 `preferences:read/write`，并在读取或写入 DeerFlow `user_preferences` 前检查匹配已验证 OIDC 主体的 owner/self data_scope；现有浏览器 session 与本地账户 owner 校验继续保留。
- IAM 新增 append-only migration `0030_deerflow_preference_permissions` 登记 `deerflow.preference.read/write`，不自动授权任何角色；DeerFlow `config.example.yaml` 增加两条 permission map。
- `tests/test_user_preferences.py` 定向回归 **19/19 通过**，覆盖权限不足、IAM data_scope 拒绝先于仓储、浏览器 session 与本地 owner 隔离；改动 Python 文件 Ruff check/format 通过。
- `verify-local.ps1` 将空隔离 PostgreSQL 库迁移到 0030 后，完整后端套件 **161/161 通过**；Vue 类型检查与 Vite 生产构建通过（3205 modules）。IAM Alembic 单一 head 核验为 `0030_deerflow_preference_permissions`。
- 前端交互未改变。开发库仍停在 `0021_resume_wallet_perms`、readiness 503；未执行 IAM/DeerFlow migration、没有真实 IAM 联调。正式验收需部署方授予对应角色权限与本人范围。

## 2026-10-11 DeerFlow production runtime 镜像复验

- dev Gateway 镜像 iam-deerflow-package-check:20261011 已生成；一次性容器使用镜像 uv 环境导入 deerflow.authz.iam_deerflow 通过。
- default runtime 镜像未产出。首次 runtime 构建报告 uv.lock stale；同版 uv 在已构建镜像中对当前挂载源码执行 uv sync --dry-run --locked --extra redis 通过，uv.lock SHA-256 与预检前一致，没有改写用户已有 lockfile。
- 后续 runtime build 被 Docker Hub Python manifest metadata 和 GHCR uv image anonymous token 请求 EOF 阻断，包括 --pull=false。待 Docker Hub/GHCR 可达或提供镜像源后重试；本轮未启动服务或数据库。

## 2026-10-11 DeerFlow Gateway 镜像打包预检

- DeerFlow .dockerignore 排除 runtime config 文件、备份副本和所有 .env* 变体，保护运行期模型/MCP 配置不进入 build context；保留既有 pytest/ruff/mypy/hypothesis cache 排除。
- dev target 镜像在构建客户端退出后由 Docker daemon 完成：iam-deerflow-package-check:20261011（sha256:f2203cacf14d7a324dadcaa4d803145fcd9fd48129a9e9f15751e4beb4947456）；一次性容器通过 uv run 导入 deerflow.authz.iam_deerflow。完整服务启动与在线联调仍待验收。
- 本地服务、数据库均未启动或变更；待 registry 可达、预拉镜像或配置 mirror 后重跑 image build 和容器内 adapter import。

## 2026-10-11 DeerFlow tenant/organization 数据范围审计

- 只读检查确认 projects/threads/runs/documents 的持久化归属使用本地 user_id；核心资源行没有可用于 organization/tenant 查询过滤的可信字段。tenant_id 目前在 IAM OIDC vault 与模型用量数据中，不代表业务资源归属。
- 维持已实现的 owner/self 查询过滤；tenant/organization scope 继续 fail closed，不扩大到同租户其他用户数据。
- 将组织共享资源清单、可信归属映射与旧数据回填列为产品输入；未改 DeerFlow schema，也未执行迁移。

## 2026-10-11 DeerFlow 异步 IAM 授权回归

- DeerFlow backend Python 3.12.14 下，sdk/python/test_iam_deerflow.py 运行 unittest 22/22 通过，覆盖 async authorize 与 async data_scope capability refresh。
- backend/tests/test_iam_provider_interoperability.py 使用 -p no:cacheprovider 运行 12/12 通过，含 4 项 async data_scope；不再受 pytest Windows cache path 写入警告影响。
- 所有用例均为 mock/隔离测试，没有访问真实 IAM、Provider、业务数据库或浏览器。此前 Windows runtime event-loop hang 未在本次解释器中复现；真实环境和 role grants 仍待验收。

## 2026-10-11 运行就绪与登出决策复核

- 只读查询确认 IAM 开发数据库为 0021_resume_wallet_perms，源码 migration head 为 0029_deerflow_agent_extension_permissions；API /api/v1/ready 当前为 HTTP 503 database_migration_pending。
- deploy/backup-postgres.ps1 -ValidateOnly 通过；本次没有创建备份归档、修改数据库或执行迁移。
- 用户明确选择 DeerFlow 本地登出：/auth/logout 只清理本地 vault session，不通过 RFC 7009 向外部 issuer 发送 access/refresh token。发现解析及 RFC 7009 客户端原语可保留，但不接入登出流程。
- 当前登录页在 readiness 未就绪时阻断认证提交；Vue 类型检查、Vite production build 和浏览器禁用态检查已通过。服务恢复仍需受保护备份、迁移审阅和用户明确授权。

## 2026-10-11 · 登录页 readiness 操作门禁

- readiness 初始检查/数据库待迁移/不可用时，禁用登录、注册、密码重置、邀请接受和 OIDC consent 提交；提交 handler 同样复核状态，避免键盘提交绕过按钮状态。
- 邀请、应用登录和 consent 上下文仅在 ready 后加载，避免 API 未就绪时把有效邀请或授权票据误报为无效；数据库待迁移提示说明管理员备份、审阅、迁移与重查顺序。
- Vue/TypeScript 检查通过；Vite production build 通过（3205 modules，输出到临时目录）；浏览器 AX 确认 readiness 文案和登录按钮 disabled。未修改后端或开发数据库，API readiness 仍为 503。
## 2026-10-11 · DeerFlow 持久模型用量结算 outbox

- 新增 SQLAlchemy 持久 outbox 与 DeerFlow 迁移 fd_0028_iam_model_usage_outbox。终态用量事件先落库，再由后台 worker 按幂等 request_id、120 秒租约和 2–600 秒指数退避投递；成功记录保留期默认 30 天，可按配置调整。敏感凭证、prompt 和响应正文不进入 outbox。
- 聚焦回归 118 passed、1 条既有 warning；Ruff 检查/格式通过；全量 Alembic 链在隔离 SQLite 库升级至 fd_0028。未连接真实 IAM、Provider 或开发数据库，未对开发数据库执行迁移。
- 该 outbox 可恢复已提交事件，但不能消除 Provider 完成与本地 outbox 提交之间的崩溃窗口；自定义非 LangChain Provider 和线上互操作仍需验收，配额强制保持关闭。
## 2026-10-11 DeerFlow 模型用量回归复核

- 使用 DeerFlow backend venv 重跑 `test_model_factory.py`、`test_iam_model_usage_callback.py`、`test_iam_model_usage.py`、`test_worker_iam_credentials.py`：**110 passed, 1 warning**（37.47s）。警告来自既有未知模型参数测试。
- 测试使用本地 mock/隔离 fixture；未连接 IAM、Provider 或开发数据库，未运行迁移。
- 这次只更新验证记录，没有声称结算 outbox、进程崩溃恢复或真实联调已完成；配额执行仍需保持关闭。

## 2026-10-11 · DeerFlow per-call IAM 模型用量回调

- DeerFlow 的模型工厂从 run-scoped ContextVar 取回可选 callback，并按可信 `config.models[].name` 绑定到每个 LangChain model instance；Provider 部署别名或 request metadata 不决定 IAM model UUID。每次 LLM 调用先 reserve，quota/服务失败会在 Provider dispatch 前 fail closed；结束时按同一 request ID settle，若 IAM 未要求 reservation 则 report usage。
- 使用同一 run vault capability 的 access token 经 `/api/v1/auth/me` 解析 IAM UUID 用户；OIDC `sub` 不当作 UUID。每个映射模型必须显式设置 `reserved_output_tokens`；`model_usage.enabled` 默认关闭，`IAM_MODEL_USAGE_API_KEY` 只注入 DeerFlow API Secret Manager。Prompt/响应只在内存中估算，不发送给 IAM 或写入日志。
- callback 测试 8/8（含 async callback manager 拒绝传播、Provider 别名归属与 worker close 清理），client+callback+vault 回归 15/15；完整 model factory+usage 组合回归 110/110，Ruff check/format 通过。持久 settlement outbox/崩溃恢复、自定义非 LangChain Provider 覆盖和真实 IAM/Provider 验收仍未完成；配额执行开关继续关闭。

## 2026-10-11 · DeerFlow 模型配额接入契约审计（实现前快照）

- 前置审计当时确认 DeerFlow 只有 `model.invoke` 权限检查、尚未调用 Gateway run lifecycle usage API；IAM usage API 需要 tenant/application/model/user UUID。新增 Harness `IamModelUsageClient`，覆盖 `/auth/me` 用户 UUID 解析、reserve、settle、report 的服务端契约。
- 确认 OIDC `sub` 是不透明值；实现时须通过 vault access token 请求 IAM `/api/v1/auth/me` 取得规范用户 UUID。
- 客户端离线契约测试 5/5、Ruff check 通过。将逐 Provider 调用配额、主/子 Agent/取消覆盖与持久结算恢复缺口同步到文档。未读取/修改 `.env`、环境密钥或数据库；后续 per-call callback 实现见上一条日志。

## 2026-10-11 · IAM readiness 与本地迁移审查

- 只读核验管理台 `5175/` 返回 HTTP 200、API `/api/v1/ready` 返回 503 `database_migration_pending`；开发库当前为 `0021_resume_wallet_perms`，源码 head 为 `0029_deerflow_agent_extension_permissions`。
- 确认 `public_registration_challenges` 表不存在，故 0024/0025 challenge cleanup 对当前库为零行影响；0026–0029 仅增加权限目录，不自动授予角色。
- 未读取 `.env`、未创建备份、未执行 migration。恢复 API readiness 仍需受保护备份、用户明确批准及 migrate profile 执行；全过程已写入启动指南和待提供清单。

## 2026-10-11 · DeerFlow Console 聚合报表权限

- stats 现在要求 `runs:read`、`threads:read`、`agents:read` 及对应 Central IAM owner/self scopes；跨线程 runs 还要求 thread read，usage 要求 run read。
- 所有范围判定在 SQL session 获取前执行；仍保留 DeerFlow 本地 `user_id` owner filtering。
- Console router 回归 **25/25 通过**，Ruff check 通过。未修改前端、迁移数据库或授予角色；真实 IAM 和浏览器验收待部署配置。

## 2026-10-11 · DeerFlow OIDC token revoke 原语与授权边界

- DeerFlow OIDC metadata 解析可选 `revocation_endpoint`，`OIDCService.revoke_token()` 提供 RFC 7009 HTTPS form request、Basic/POST/public client auth 和不回显凭证或 Provider 正文的错误处理。
- `test_oidc_auth.py` + `test_iam_token_vault.py` **41/41 通过**；Ruff check 通过。`ruff format --diff` 仅提示 `oidc.py` 与 `test_oidc_auth.py` 中不属于本次新增部分的既有格式差异，本轮未全文件格式化以免改写同文件既有变更。
- 自动审查拒绝将该调用接入 DeerFlow logout，因为这会把 vault access/refresh token 发给外部 issuer，且当前没有用户明确授权。登出仍只删除本地 vault session；未请求真实 IAM、未改数据库/环境 secret。待用户明确决定是否允许该凭证出站后再继续实现 logout 联动。

## 2026-10-11 · DeerFlow memory worker 提交前复核

- 默认 memory callback 在实际 `apply_changes/save` 前重查 Central IAM `memory:read/write`；revision conflict 每次重试都重新校验。
- 同步 worker 将用户/会话/Agent 标识交给 Gateway serving loop，重载 active 本地用户和身份匹配的 OIDC vault session；token/capability 不进入队列。授权不可用、scope 不匹配或超时均拒绝持久化；本地 RBAC 与未启用授权仍保留既有行为。
- 提交前 worker 回归与 updater/data-scope 联合验证 **109/109 通过**；Ruff lint 与 format check 对 6 个变更 Python 文件通过。未修改前端、数据库、migration、secret 或角色 grant；真实 IAM/OIDC 与浏览器验收仍待环境。

## 2026-10-11 · DeerFlow Agent 个人记忆授权

- 被动记忆中间件在加入异步写入队列前，同时检查 Central IAM `memory:read` 与 `memory:write`；`memory_search` 检查 read，`memory_add/update` 检查 read+write，`memory_delete` 检查 read+delete，并确保拒绝发生在 MemoryManager 存储访问之前。
- 仅接受当前 Gateway run 绑定的服务端 IAM capability；校验本地 DeerFlow user ID 与 runtime 身份一致、IAM subject 与 owner scope 一致、租户一致。空范围、租户/组织宽范围、主体错配和 IAM 异常均失败关闭；本地 RBAC/未启用授权维持原行为。
- 在 prompt memory 注入、记忆工具、after-agent 被动入队和 summarization flush 四个路径中统一执行前置检查；定向 memory/prompt/summarization 回归共 **181/181 通过**，12 个 Python 改动/测试文件 Ruff check 与 format check 通过。
- 后台 worker 提交前的撤权复核由 2026-10-11 新条目补充；本节 181/181 仅覆盖 admission/prompt/tool 相关实现。未修改数据库、migration、secret、IAM Vue 或 DeerFlow 用户配置；真实 IAM/浏览器联调仍待环境和角色 grant。

## 2026-10-11 · 隔离 PostgreSQL 全套回归至源码 head 0029

- 使用一次性 API 容器运行 `tests/run_isolated_postgres_suite.py`；隔离库从空库迁移至 `0029_deerflow_agent_extension_permissions`，后端完整套件 **161/161 通过**。
- 在一次性 Console 容器对当前工作区显式运行 `vue-tsc -b` 与 Vite production build，3205 modules 构建通过；Console 生产镜像也成功构建。
- `backup-postgres.ps1 -ValidateOnly`、生产 Compose 示例 `config --quiet` 与部署/备份/恢复 PowerShell 脚本语法检查通过。未生成备份归档。
- 复核临时 `iam_test_*` 数据库已清理；主 IAM 开发库仍为 `0021_resume_wallet_perms`，API `/api/v1/ready` 返回 `503 database_migration_pending`。未迁移主开发库。
- API 容器 unhealthy，console 与 PostgreSQL healthy。此验证覆盖后端完整套件和空库迁移，不覆盖真实 IAM/OIDC、浏览器 E2E、DeerFlow 目标库或角色 grant。

## 2026-10-10 · 技能编辑与完整响应读写双授权

- 自定义技能 update/rollback 返回完整技能正文；在任何个人 storage 读取或写入前，Central IAM 现在同时校验 skills:read/read-scope 和 skills:write/write-scope。
- connectors、stateless runs、Agent 兼容、skills、MCP、subagents 与 IM worker 管理的跨切片回归通过 141/141；8 个 DeerFlow Python 文件 Ruff check/format check 通过。
- 仅验证代码级授权边界；IAM/DeerFlow 开发数据库未迁移，未配置中央 role grant，未做真实 IAM/OIDC 浏览器验收。
## 2026-10-10 · DeerFlow 中央授权跨切片回归

- 将 IM/Lark 连接器、无状态 run、Agent 兼容路由、skills、MCP、managed subagent 与 IM worker 状态/重启授权的定向回归合并运行，138/138 通过，1 条 Starlette/httpx deprecation warning。
- 8 个改动 DeerFlow Python 代码/测试文件通过 Ruff check 和 Ruff format --check。未执行 IAM/DeerFlow 开发库迁移、未配置角色 grant、未做真实 IAM/OIDC 浏览器 E2E；代码回归不代表部署验收。
## 2026-10-10 · DeerFlow IM worker 状态与重启授权

- /api/channels worker 状态读取增加 channels:read；全局 worker restart 增加 channels:admin，并保留原有本地 Gateway 管理员校验。
- 将独立 worker 管理 API 与个人 channel connection/data_scope 边界明确区分；复用 IAM migration 0028 已登记的权限码，无新 migration。
- 技能、MCP、子 Agent 与频道连接器/worker 管理回归 81/81 通过；Ruff check 与 8 个变更 Python 文件 format check 通过。无数据库迁移或在线 IAM/浏览器联调。

## 2026-10-10 · DeerFlow 技能、子 Agent 与 MCP 管理权限

- 技能目录与个人自定义技能新增 Central IAM read/write/delete 和本人 data_scope 校验；共享技能开关和进程缓存刷新使用 skills:admin。
- 托管 subagent 目录要求 subagents:read，CRUD 和完整 prompt 需要 subagents:admin，系统 prompt 还要求 DeerFlow 本地管理员。MCP 配置读取、增删改和缓存刷新统一要求 mcp:admin，并保留本地管理员检查。
- 新增 IAM migration 0029_deerflow_agent_extension_permissions，只登记 7 个权限码，不授予角色；DeerFlow config.example.yaml 增加对应映射样例。
- 技能/MCP/subagent 组合定向回归 79/79 通过，Ruff check 与 7 个改动 Python 文件的格式检查通过（1 条 Starlette/httpx 弃用警告）。未迁移数据库，未做真实 IAM 或浏览器联调。

## 2026-10-10 · DeerFlow IM 与 Lark 连接器中央授权

- 为 channel providers/connections、个人 IM 连接/断开和个人 Lark 状态/config/OAuth 流程增加对应 Central IAM read/write 权限及本人 data_scope；继续保留 DeerFlow 本地用户 owner 隔离。
- 部署级 channel runtime config 与 Lark install 同时校验 Central IAM admin 权限及 DeerFlow 本地管理员身份。
- IAM migration 0028_deerflow_connector_permissions 只登记六个权限码，不自动授予任何角色；config.example.yaml 添加 channel/integration route permission map 示例。部署方仍需配置授权策略和本人范围。
- 连接器授权、Agent 兼容路由、无状态运行与 owner isolation 定向回归 57/57 通过；Ruff check 通过，10 个变更 Python 文件格式检查通过（Starlette/httpx deprecation warning）。未迁移 IAM/DeerFlow 数据库，未执行真实 IAM/浏览器联调。

## 2026-10-10 · DeerFlow 无状态运行数据范围校验

- 在 `/api/runs/stream` 与 `/api/runs/wait` 入口调用统一 `start_run` 前增加 Central IAM `runs:create` data_scope 检查；已有本地 thread owner 检查继续执行，两个边界共同阻止仅凭线程 ID 绕开中央范围策略。
- 同时将旧 `/api/assistants/*` 列表、详情、graph、schemas 兼容读取接入 `agents:read` 与本人 data_scope 门禁，避免绕过正式 Agent API；无新增部署配置。
- 新增及相邻 Gateway 定向回归共 28/28 通过，改动四个 Python 文件 Ruff check/format 通过；未做真实 IAM/浏览器联调，也未迁移数据库。
## 2026-10-10 · DeerFlow 模型与工具资源级授权

- 将 DeerFlow 本地模型名绑定到服务端配置的 IAM ModelCatalog UUID；`model:use` 映射 `model.invoke`，复用 IAM 对同 tenant 活动模型的检查，映射缺失时在访问 Provider 前拒绝。模型列表通过 `filter_actions.model=list` 独立检查 `deerflow.model.list`。
- 工具候选使用服务端工具名作为 IAM `resource_id`，逐工具 grant 可相互隔离，IAM 应用级 grant 仍可显式允许全量工具。
- 增加模型 UUID 映射、未映射模型拒绝、逐工具过滤和无效 UUID 回归；包含 4 项新用例的同步互操作选择 **8/8 通过**，改动 Python 文件 Ruff check 与格式检查通过。完整 12 项文件在现有异步 data_scope 用例段挂起，随后 4 项异步用例被排除；IAM/DeerFlow 数据库及真实浏览器联调未进行。

## 2026-10-10 · 文档状态与单一试点基线对齐

- 更正启动指南中过期的 DeerFlow 定时授权测试状态，记录当前 126/126 组合回归；更新 IAM 迁移 head `0027`、本机开发库 `0021`、API readiness 503 的核验结果。
- 对齐 PRD、平台 README、前后端指南、架构、单系统接入计划和运维手册：当前唯一接入试点是 DeerFlow；已撤销的 AI Resume/Knowledge Base IAM 专属集成只作历史信息；隔离测试结果不代表开发库迁移或真实联调完成。
- 本次仅修改文档，未启动/重启服务、修改凭据或执行数据库迁移。

## 2026-10-10 · DeerFlow 后台定时任务即时重新授权

- 将 Central IAM 授权延伸到定时任务后台：新 occurrence 入队前和 durable queue 启动前重新加载 active 用户、当前路由权限与本人 data_scope；Central IAM 模式从匹配同一本地用户/provider/issuer/subject 的 token vault session 获取短期 capability。
- 账号禁用、会话不可用或 grant/data_scope 拒绝时暂停任务并取消等待 occurrence；Agent run 的 owner identity、AuthContext 和 IAM capability 仅存在于本次内存 request/RunContext，不写入调度任务或 checkpoint。手动触发将 denied 结果映射为 403/503。
- 新增派发通过/拒绝、队列撤权、精确 vault 身份选择和触发错误回归；调度、vault、路由与授权 resolver 组合测试通过 126/126。Ruff check 通过，配置格式检查通过 9 个文件，10 个 Python 文件 AST 解析通过。token-vault 模块的 Ruff formatter 仍报告本轮前已有的格式差异，本轮没有重排无关加密代码。IAM/DeerFlow migration、Compose 和真实 IAM E2E 未执行。

## 2026-10-10 · DeerFlow 定时任务 API 数据范围

- 为任务列表/详情、创建/修改、暂停/恢复、手动触发、删除和运行历史增加 Central IAM self data_scope 校验；保持本地 `user_id` repository 过滤，任务删除改用 `threads:delete`，运行历史要求 `runs:read`，复用会话前检查 `threads:read`。
- 增加范围拒绝在仓储查询/写入前短路的定向回归。Docker Desktop Linux engine pipe 当前不可用，pytest 未能启动；Python AST 解析与 Ruff check/format 通过。IAM UI 和数据库未改，未执行 migration。后台自动调度尚未实现未来触发时 grant 撤销复核。

## 2026-10-10 · DeerFlow 项目与资料数据范围写入闭环

- 项目创建、编辑、归档、恢复和文档上传/提升/恢复在持久化前校验 `projects:write` 与完整响应所需的 `projects:read`；文档软删除、回收站单项/批量清理和保留期清理校验 `projects:delete`；会话文件提升/挂载同时校验 `threads:read/write`。所有仓储写操作显式传入当前本地用户 ID，继续与 DeerFlow owner 过滤相交。
- `require_permission(..., owner_check=True)` 现在还会在本地 owner 校验后、handler 前检查线程 `write/delete` 与运行 `create/cancel` data_scope；运行创建不传不存在的 run ID，取消操作按 run ID 检查。鉴权回归 101/101，组合 owner-bound 路由选择 532 项通过、1 个公网 DNS 测试在离线容器中排除；Ruff 通过。Windows 本机 venv 导入 OpenAI/Pydantic 时发生 Python access violation，测试改在容器内验证。
- 同步更新 README、PRD、前后端说明、总体架构、接入计划、待提供清单、启动指南与 `iam-project` Skill。未启动 Compose、连接真实 IAM 或迁移 IAM/DeerFlow 数据库；项目级其它写资源范围和真实浏览器验收仍待完成。

## 2026-10-10 · DeerFlow Gateway 镜像构建验收

- 根 .dockerignore 排除 pytest、ruff、mypy、hypothesis 生成缓存，解决 Docker 无法读取 backend/.pytest_cache 时构建上下文失败；成功构建 deer-flow-dev-gateway:latest。
- 使用 network none 的一次性容器成功导入 deerflow.authz.iam_deerflow、app.gateway.authz 与 app.gateway.routers.agents，验证 adapter 和鉴权路由已打包进 Gateway workspace 镜像。
- 未启动 DeerFlow Compose 服务、未迁移 DeerFlow/IAM 数据库；IAM 开发库仍为 0021，API readiness 仍为 database_migration_pending。
## 2026-10-10 · 宿主机运行状态复核

- Docker 容器健康状态仍为 API unhealthy、console/PostgreSQL healthy。宿主机绕过 HTTP 代理后直连 127.0.0.1:5175 和 API 根路径 127.0.0.1:8002 均返回 HTTP 200；/api/v1/ready 返回 503 database_migration_pending。
- 根因仍是 IAM 开发库 revision 0021_resume_wallet_perms 落后源码 head 0027_deerflow_resource_permissions。本轮未执行 migration；完成升级仍需受保护备份和明确维护窗口授权。
## 2026-10-10 · 注册迁移影响审查

- 只读审查 IAM migrations 0024/0025：0024 会清空并删除旧注册 challenge 暂存密码摘要列；0025 会将未消费的旧邮箱 OTP challenge 标为已消费，用户需要重新发起邮箱验证。
- 未执行 migration；目标开发库仍为 0021_resume_wallet_perms。升级前须提供受保护备份目录并明确批准维护窗口。
## 2026-10-10 · DeerFlow Agent 与记忆权限目录

- **本轮只读运行核验（2026-10-10）：** IAM Compose 的 API unhealthy、console/PostgreSQL healthy；IAM 开发库为 0021_resume_wallet_perms，源码 head 为 0027_deerflow_resource_permissions，API readiness 返回 HTTP 503。DeerFlow 开发 Compose 当前没有运行；其 Alembic 源码 head 为 fd_0027_repair_run_change_seq（父版本为 0026_iam_oidc_token_vault），目标数据库版本尚未核验。本轮未启动服务、迁移数据库或修改环境凭据。
- **本轮隔离验证（2026-10-10）：** verify-local.ps1 的后端完整套件从空测试库迁移到 IAM 源码 head 0027 后 161/161 通过；console 镜像内 vue-tsc -b 与 Vite production build 通过。复查开发库仍在 0021_resume_wallet_perms，临时 iam_test_* 数据库数量为 0；此验证未迁移开发库，也未恢复 API readiness。

- IAM 新增 append-only migration `0027_deerflow_resource_permissions`，登记 `deerflow.agent.read/write/delete/admin` 与 `deerflow.memory.read/write/delete/admin`；不自动 grant，也未迁移数据库。
- DeerFlow 自建 Agent API 增加读写删权限及匹配的本人 data_scope 检查；完整 Agent 响应的写接口额外要求 read。部署共享 `USER.md` 使用独立 `agents:admin`，PAT 路由不包含该接口。
- 修正 DeerFlow IAM 示例使用 origin，补齐 Agent/记忆 permission map。DeerFlow adapter/client 已在 harness 包内；目标镜像构建、部署和在线联通仍待验收。
- 最近只读 Docker 检查：API unhealthy、console/PostgreSQL healthy；PostgreSQL revision `0021_resume_wallet_perms`，IAM 源码 head `0027`。数据库迁移和真实 IAM/browser E2E 仍待维护窗口与外部配置。
- 授权、PAT、`/auth/me` 与 Agent 路由互操作定向回归 **90/90 通过**（1 条 Starlette/httpx 弃用警告）；8 个修改 Python 文件 Ruff check 与 format 通过。Windows 沙箱阻止 asyncio loopback socketpair；在允许本机 socketpair 的进程上下文中完成 pytest。

## 2026-10-10 · DeerFlow 个人记忆授权与数据范围

- DeerFlow Gateway 记忆 API 增加 `memory:read/write/delete/admin` 路由权限；返回完整记忆数据的所有接口（包括写入/删除响应）在访问存储前还要通过 `memory:read` IAM data_scope，配置明细使用 `memory:admin`。
- 扩展 `require_permission` 支持指定 legacy Request 参数名；将 memory 路由逐方法加入 PAT scope 与 allowlist，未知 HTTP 方法继续拒绝。
- 同步 PRD、集成计划、整体/前后端说明、待提供清单与 Skill。未做数据库迁移或修改真实环境凭据。
- 记忆/权限/PAT 回归 118/118 通过，改动文件 Ruff check/format 通过；项目文档/回收站回归在短临时路径下 72 通过、2 跳过。当时 Windows 255-byte 文件名压力用例因 `WinError 3` 未通过，该问题已于 2026-10-12 修复，后端文档路由回归 32/32 通过。

## 2026-10-10 · DeerFlow 资源级过滤隔离与单系统试点顺序

- 修正 `filter_resources` 的实例授权复用边界：未配置资源 resolver 时仍可按 permission code 合并应用级检查；启用 resolver 后逐个候选资源执行在线授权，避免同一 permission code 下一个资源的 allow 被复用到其它 `resource_id`。新增回归验证不同资源得到不同 IAM 决策。
- DeerFlow 同步适配器回归 **18/18**、IAM 数据范围客户端回归 **11/11** 通过。异步用例未验证；未连接真实 IAM/DeerFlow 数据库，也未把 `data_scope` 应用到业务查询。
- 用户确认交付顺序为先完成 IAM 平台，再只接入 DeerFlow 做端到端试点，通过后再决定其它产品；同时移除 AI Resume、Knowledge Base 的产品专属接入代码。外部仓库在当前可写范围之外，且 Git 状态命令被 Windows 拒绝访问，尚未修改这些仓库。本会话 `docker compose ps` 受 Windows 拒绝启动 `C:\Windows\system32\docker` 影响，未实时检查容器或迁移数据库。
- 同步更新 PRD、整体/前后端说明、架构、集成计划、启动指南、Python SDK 和待提供清单。项目 Skill 位于当前只读的 `.codex` 目录，无法同步修改。

## 2026-10-10 · DeerFlow IAM 应用与资源上下文 fail-closed

- DeerFlow Provider 的普通授权与 `data_scope` 响应都必须明确回显服务端配置的精确 `application_id`；缺失或错配时一律拒绝。服务端可配置 `resource_id_resolver` 将可信 ID 传入资源授权和数据范围检查，resolver 配置后缺失或非法 ID 一律失败关闭，不回退为应用级授权。
- 新增应用上下文、资源 ID 透传、非法 ID 和缺少可信 scope context 的回归用例。DeerFlow 适配器同步用例 **17/17 通过**，IAM 授权/数据范围客户端用例 **11/11 通过**。完整异步套件未能在当前 Python runtime 执行：`asyncio.run(asyncio.sleep(0))` 本身挂起；环境没有可用 Ruff 命令。业务 `data_scope` 查询过滤、目标数据库和真实 IAM 验收仍未完成。
- 同步更新 PRD、架构、集成计划、Python SDK、前后端说明及待提供配置清单；未修改 Vue 页面、API schema 或数据库迁移。IAM 项目 Skill 位于当前只读的 `.codex` 目录，本轮无法更新。

## 2026-10-10 · DeerFlow IAM data_scope 查询适配器

- IAM Python SDK 的 DeerFlow provider 新增同步与异步数据范围查询，使用服务器端 OIDC subject 与 token 请求 `include_data_scope=true`，校验非空范围和应用上下文，并在缺失权限、scope、会话或 IAM 服务时失败关闭；Agent 异步路径先复核/刷新 vault capability。
- IAM 数据范围客户端与 DeerFlow 适配器组合回归 **27/27 通过**，两处改动文件 Ruff 检查通过。当前能力只返回 IAM 已验证的范围，不会自动过滤 DeerFlow 业务查询；项目、会话、文件和产品扩展 API 的范围消费、正式 permission map、镜像分发、真实 IAM 联调及目标库验收仍待完成。
- 同步更新 PRD、业务接入计划、待提供配置清单、前后端说明、IAM Skill 和 Python SDK 使用说明；无 UI/API schema/数据库迁移变更，未访问产品数据库或真实 IAM。

## 2026-10-10 · Knowledge Base IAM 集合可见性与统计

- Knowledge Base 新增 `0026_collection_iam_data_scope`，为空集合记录可信 owner/tenant/organization；集合仅在创建者有权或含当前可见文档时展示，文档数、片段数与最新发布时间按当前授权范围聚合。修改/归档集合前验证其全部文档可见，防止通过集合操作影响范围外数据。
- 本次 Knowledge Base IAM/data-scope 完整定向组合 **37/37 通过**、改动文件 Ruff 检查通过；OpenAPI/TypeScript 合约已重生成，contracts typecheck 通过。目标数据库迁移、隔离 PostgreSQL 跨成员用例与真实 IAM/浏览器验收未做；本机 Windows pytest 需允许本地 asyncio socketpair 才能执行。
- 同步 Knowledge Base README/API/执行书及 IAM README、前后端说明、PRD、接入计划、待提供清单与 Skill。

## 2026-10-09 · DeerFlow Agent IAM 授权上下文

- Gateway 鉴权解析出的 repr 脱敏 IAM 凭证现通过不可序列化的 `RunContext` 传入 Agent 后台运行；仅 OIDC subject 一致的 Principal 可以使用该 capability。工具过滤、工具执行与模型选择可在线调用中央 IAM，不把 token 放入 LangGraph config/context 或 checkpoint；任务结束时清理 run-scoped ContextVar。
- DeerFlow 鉴权/vault/Principal/模型定向回归 **91/91**、IAM Python Adapter **13/13**、改动文件 Ruff 检查通过。Windows runner 需将 pytest 临时目录指向 sandbox temp 并允许本机 asyncio socketpair；未连接 IAM 或产品数据库。
- Agent 长任务会复核 vault session（最多 2 秒复核间隔），并在 access token 临近过期时行锁刷新；本地登出删除 vault 行后，后续授权清空该 run capability 并失败关闭。Knowledge Base/DeerFlow `data_scope` 行级过滤、上游 IAM revoke、DeerFlow 目标镜像 adapter 分发、真实 IAM/OIDC 联调和 migration `0026` 目标库验收仍待完成。

## 2026-10-09 · DeerFlow Gateway 请求级 IAM 鉴权接通

- DeerFlow 请求级 route permissions、model catalog 与 sandbox-sync authorization 现从签名本地 session `sid` 读取 encrypted token vault；IAM SDK Adapter 通过 repr 脱敏 Mapping 获取 access token，临近过期时执行 refresh grant 与 session 行锁密文轮换。Token 不进入 LangGraph config 或 checkpoint。
- DeerFlow 定向鉴权/vault/model 测试 62/62、IAM SDK adapter 测试 11/11、Ruff 通过。没有执行 IAM/DeerFlow 产品数据库迁移、真实 IAM 请求或 OIDC 浏览器流程。
- DeerFlow Agent 的模型与工具 IAM 在线授权现已通过 run-scoped capability 接入；长任务 refresh 已在后续增量实现并由 DeerFlow 91/91、SDK 13/13 回归验证；data_scope、远程 revoke、SDK adapter 镜像分发、真实 IAM 互操作和 migration `0026` 目标库验收仍未完成；同步 PRD、架构、接入计划、用户清单、README、Skill 与 DeerFlow 文档。

## 2026-10-09 · DeerFlow OIDC refresh rotation primitives

- DeerFlow `OIDCService.refresh_tokens()` now submits standards-based refresh-token grants using the configured client authentication method, validates token fields/lifetimes, and never includes provider response bodies in refresh errors. Token-bearing result reprs are redacted.
- `IamTokenVaultRepository.load_or_refresh_for_identity()` holds the per-session row lock while refreshing, encrypts both replacement tokens before writing, preserves an unchanged refresh token when the provider omits rotation, and rejects stale refresh or mismatched OIDC identity. It is called by request-level Gateway IAM authorization; Agent runs now receive the resolved access token in an ephemeral capability but do not refresh it during a long-running task.
- DeerFlow focused OIDC/vault tests passed **31/31** and Ruff passed. No migration, live IAM request, or product database access was performed. Synced PRD, integration plan, architecture, backend/front-end notes, Skill, and changelogs.

## 2026-10-09 · DeerFlow IAM OIDC token vault 首版

- 为 DeerFlow 显式 IAM OIDC Provider 增加 AES-256-GCM token vault；要求 `offline_access` 与后端 Base64 32 字节密钥 `DEERFLOW_IAM_TOKEN_ENCRYPTION_KEY`。每次登录有独立本地 session `sid`，vault 主键为 `(user_id, session_id)`，加密 AAD 绑定 issuer、sub、tenant、sid 和 token purpose，避免并发登录覆盖各自 refresh token；签名 JWT 只携带不含凭据的 `sid`，登出删除对应本地 vault 行。
- 增加 DeerFlow Alembic `0026_iam_oidc_token_vault`，更新 OIDC Provider 配置、JWT/session 生命周期及迁移测试；通用 OIDC Provider 默认不保存 token。迁移只加入 DeerFlow 源码，未对用户产品数据库执行。
- DeerFlow auth/OIDC/vault/migration 定向测试 **123/123 通过**，Ruff 检查通过。IAM refresh rotation/远程撤销、Gateway 每请求在线权限/data_scope、真实 IAM 联调及目标库 migration 仍待完成。

## 2026-10-09 · DeerFlow OIDC 租户声明可信边界

- DeerFlow 回调合并 UserInfo 时固定保留已验签 ID Token 的 `sub` 与 `tenant_id`；若签名 ID Token 未提供 `tenant_id`，则丢弃 UserInfo 中同名值，避免其进入 IAM 授权上下文。
- 新增两条回归覆盖 UserInfo 租户冲突和 ID Token 缺少租户声明的情况；DeerFlow `tests/test_oidc_auth.py` **22/22 通过**。未访问网络或业务数据库。
- DeerFlow 服务端 token vault、IAM refresh rotation 和 Gateway 在线权限映射仍待实现。

## 2026-10-09 · 完整本地验证脚本端到端通过

- 重新执行根目录 `verify-local.ps1`，后端隔离 PostgreSQL 套件从空库迁移至 `0025_registration_role_snapshot` 后 **161/161 通过**。
- Console 镜像通过锁定依赖构建，Dockerfile 中 `vue-tsc -b` 和 Vite production build 成功（3205 modules）。此前 Docker Hub metadata EOF 未在本次重跑中复现。
- 本验证不迁移开发库、不验证真实 SMTP/浏览器注册或生产部署；开发库最近已知版本仍为 `0021_resume_wallet_perms`。

## 2026-10-09 · 复跑 IAM 全量隔离验证

- `verify-local.ps1` API 阶段重建当前 API 开发镜像，并在随机临时 PostgreSQL 数据库从空库迁移至 `0025_registration_role_snapshot`；完整后端 unittest **161/161 通过**。只读复核确认没有遗留 `iam_test_*` 数据库，开发库仍保持 `0021_resume_wallet_perms`。
- 脚本 console 镜像阶段因 Docker Hub 获取 `node:22-alpine` metadata 时返回 EOF 而中止。随后使用本地 console 容器离线运行 `vue-tsc -b` 与 Vite production build，3205 modules、入口 388.34 KB / gzip 120.06 KB；容器内 package/lock/TypeScript/Vite 配置 SHA-256 与工作区一致。
- 未升级开发库、未执行 SMTP/真实浏览器/生产验收。`verify-local.ps1` 可在 Docker Hub 或基础镜像缓存恢复后整套重跑。

## 2026-10-09 · 统一登录节流与审计的可信客户端 IP

- 认证、管理与 OIDC 授权/登出审计事件改为使用与登录失败节流相同的 `client_ip_for_request`；生产仅采信 Caddy 覆写并经私有 Nginx 链路传递的 `X-IAM-Client-IP`，开发环境使用 socket peer。
- 添加 5 个回归用例，覆盖认证/管理/OIDC 授权与登出审计来源及拒绝通用 `X-Forwarded-For`。Docker 一次性 API 容器定向测试 5/5 通过；设置 `IAM_ENSURE_OIDC_KEY=false`，未连接数据库、未迁移或写入业务数据。
- 同步 PRD、整体/前后端说明、架构、运维手册与项目 Skill。生产 CDN/LB 来源解析仍需部署验证。

## 2026-10-09 · 同步注册与联调验证记录（当前）

- 校正用户清单中 DeerFlow OIDC 回归仍未执行的旧记录：mock `test_oidc_auth.py` 已通过 20/20；补充 TypeScript 授权/OIDC 测试 14/14 和 strict TypeScript 检查结果。
- 根 README 将开发库状态更新为源码 head `0025_registration_role_snapshot`、开发库 `0021_resume_wallet_perms`、readiness `503 database_migration_pending`；明确 migrations `0022`–`0025` 尚未应用到开发库。
- 架构/启动/接入文档将“Docker Engine 当前不可访问”改为准确区分：本轮只读 Docker Desktop 检查成功，真实归档恢复演练仍待受保护备份文件；没有执行数据库恢复或迁移。
- 本轮只修正文档；未改业务代码、未运行测试、未写入数据库。

## 2026-10-09 · 校准 IAM 路线图完成度

- PRD 将已实现的会话远程撤销、模型目录/调用授权/额度 API 从“待开发”改为“开发版已具备、真实环境验收待完成”，并细分 Knowledge Base 行级过滤与 DeerFlow 服务端 vault/Gateway 中央权限缺口。
- 同步整体、前后端说明和项目 Skill，明确模型额度默认关闭、生产 Secret Manager/模型代理缺失；隔离 PostgreSQL 156/156 不等于浏览器或业务系统端到端通过。
- 本轮仅校准需求与工程状态文档，未改业务代码、未运行测试或迁移数据库。

## 2026-10-09 · 复核本地 Compose readiness 与迁移状态

- 使用 Docker Desktop CLI 执行只读 Compose 状态、API readiness 和 PostgreSQL Alembic revision 查询：API unhealthy、PostgreSQL 与 console healthy；readiness 为 `503 database_migration_pending`，开发库仍为 `0021_resume_wallet_perms`。没有执行 migration 或数据库写入。
- 更新整体 README、后端说明、PRD、接入计划、用户输入清单和项目 Skill 的运行状态；明确源码 head 为 `0025_registration_role_snapshot`，开发库滞后四个 migration，待备份位置与开发库迁移授权后再处理。

## 2026-10-09 · 为 TypeScript 授权和 OIDC 请求设置超时

- `IamAuthorizationClient` 默认 3 秒；TypeScript OIDC RP 的每个 IAM HTTP 请求默认 5 秒，二者都可配置并由单个 `AbortController` 覆盖响应体读取。超时和网络错误映射为 503，授权 HTTP 拒绝保留状态码；OIDC 授权码兑换和 refresh rotation 不自动重试。
- OIDC RP 校验正数 32 位毫秒超时，并把网络/超时异常映射为 `OIDCProtocolError(503)`。同步 TypeScript/Python SDK 使用说明、整体/前后端文档、接入计划、用户配置清单、PRD、架构和项目 Skill；并把注册 migration head 与验证结果更新到 `0025` / 156 项。未修改 IAM API 契约或数据库。
- 验证：`node --test test/authorization.test.mjs test/oidc.test.mjs` **14/14 通过**；TypeScript SDK `tsc -p tsconfig.json --noEmit` 通过。未做真实 IAM 联调。

## 2026-10-09 · 增加隔离数据库恢复校验脚本

- 新增 `deploy/verify-postgres-restore.ps1`：默认要求备份旁边有 SHA-256 sidecar，校验后把归档恢复至脚本随机生成的隔离数据库，核验 Alembic revision 和 `users`、`tenants`、`applications` 核心表；成功后删除临时库，失败时保留数据库供诊断，并清理容器内临时归档。脚本不以现有业务库作为恢复目标。
- 同步运维手册中的恢复步骤、PRD 部署验收标准、整体架构与 README、前后端说明及 `iam-project` Skill；明确真实备份恢复、API/OIDC 恢复检查仍未验收。
- 验证：PowerShell AST 解析通过；本会话尝试只读 `docker compose ps`，Docker Desktop Linux Engine named pipe 返回 permission denied。未运行真实归档恢复、未创建数据库、未改动现有数据库。

## 2026-10-09 · ToC 注册申请绑定完整授权快照

- 修复默认角色替换、权限目录状态变化、资源级授权增补或数据范围变化后，旧 OTP challenge 仍可能兑换的问题。挑战绑定默认角色 ID 与有效授权指纹；兑换时重算，策略变化即消费挑战并返回统一无效提示。
- migration `0025_registration_role_snapshot` 先消费升级前所有待验证挑战，再增加角色外键、索引和快照约束；不会自动开放注册。
- 添加角色/授权策略变更回归和 migration 索引断言；复核时发现 ORM 漏映射 `verification_code_hash`，已恢复与 `0022` schema 一致的 HMAC 摘要字段。改动 Python 文件 AST 解析通过；完整隔离 PostgreSQL 套件从空库迁移至 `0025` 后 **156/156 通过**，前端 `vue-tsc -b` 和 Vite production build 通过（3205 modules，入口 388.34 KB / gzip 120.07 KB）。隔离 runner 清理了随机测试库；开发库 `iam` 未迁移。
- 同步 PRD、前后端 README、整体 README/架构、待办清单、项目 Skill 与本变更日志；启动命令和部署步骤没有变化。

## 2026-10-09 · 本地启动 readiness 有限重试

- `start-local.ps1` 对启动期的连接异常和 HTTP 502 增加最多 12 次有限重试（请求超时 2 秒、间隔 1 秒）；API 的数据库 503 立即显示稳定错误码，不把 schema 未迁移误判为启动延迟。
- 同步本地启动指南、前后端 README、整体 README/架构、PRD 与 `iam-project` Skill。
- PowerShell AST 语法核验通过；本会话 Docker CLI 被系统拒绝且 localhost 不可达，未做服务运行验收；未迁移数据库。
- 复核确认真实 Docker Desktop CLI 对 `dockerDesktopLinuxEngine` 命名管道返回 permission denied；`localhost:5175`/`8002` 也不可达，因此当前容器状态不可验证。最近成功读取的快照仍是开发库 0021 / 源码 head 0024；未对开发库执行迁移。

