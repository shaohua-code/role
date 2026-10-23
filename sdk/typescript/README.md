# TypeScript IAM server-side SDK

`IamAuthorizationClient` is a dependency-free server-side helper for business API routes. It calls the online IAM authorization endpoint with the end-user **OIDC access token** and fails closed for network, HTTP, timeout, or malformed-response errors. The request and response-body read share a 3,000 ms default deadline; pass a positive 32-bit millisecond value as the third constructor argument to tune it for the business service. Timeout/network errors raise `AuthorizationServiceError(503)`, an IAM HTTP denial preserves its status code, and malformed responses return 502. This authorization helper does not store or refresh credentials; the separate `IamOIDCClient` below handles the OIDC relying-party flow. `compilePostgresDataScope` compiles a validated scope into a parameterized PostgreSQL `WHERE` fragment, but the business service still owns the trusted column/key mappings and must execute that fragment in the protected resource query.

When `includeDataScope` is `true` and IAM allows the request, pass `tenantId` and `userSubject` from the server's locally verified IAM OIDC session. `userSubject` must be the IAM token's `sub`, not the business product's local user primary key. The client does not send `userSubject` to IAM; it requires a non-empty `any_of` constraint set, checks every branch's `tenant_id` against the verified tenant, checks every `owner.user_id` against the verified IAM subject, accepts only known constraint kinds and their fixed field names, and returns a normalized allow-listed scope. Missing local identity, malformed, empty, cross-tenant, other-subject or unknown scope data fail closed (`Error` before the request or `AuthorizationServiceError(502)` for malformed IAM responses). An empty `organization_ids` list means no rows and must remain an empty match set in the business query.

`checkBatch(accessToken, request)` calls `POST /api/v1/authorization/check-batch` to decide multiple permission codes of the same tenant in one request; every code follows exactly the same decision semantics as `check()`, and the result is a `Record<string, AuthorizationDecision>` keyed by the requested code. The batch result never carries row-level data conditions, so owner-only data operations must still go through `check` with `includeDataScope: true`. IAM validates 1–32 unique codes server-side; a violation surfaces as `AuthorizationServiceError(422)` and must be treated as a denial. A missing code, malformed decision, or invalid `application_id` in the response fails closed with `AuthorizationServiceError(502)`.

```ts
import { IamAuthorizationClient, compilePostgresDataScope } from './src/index.js'

const iam = new IamAuthorizationClient(process.env.IAM_API_URL!, process.env.IAM_APPLICATION_ID)

// `tenantId` and `accessToken` must come from the application server's verified OIDC session.
const decision = await iam.require(session.accessToken, {
  tenantId: session.tenantId,
  userSubject: session.iamSubject, // IAM token sub; distinct from any product-local user ID
  permissionCode: 'resume.resume.export',
  resourceId: resumeId,
  includeDataScope: true,
})

if (!decision.data_scope) throw new Error('IAM omitted the required data filter')
const filter = await compilePostgresDataScope(decision.data_scope, {
  tenantId: session.tenantId,
  userSubject: session.iamSubject,
  columns: { tenantId: 'r.tenant_id', ownerUserId: 'r.owner_user_id', organizationId: 'r.organization_id' },
  // IAM subject/tenant/organization 与本地 ID 不同时必须从可信映射表解析。
  mapOwnerUserId: (subject, tenant) => identityRepository.getLocalUserId(subject, tenant),
  mapTenantId: (tenant) => tenantRepository.getLocalTenantId(tenant),
  mapOrganizationIds: (ids, tenant) => organizationRepository.getLocalOrganizationIds(ids, tenant),
})
const result = await pg.query(`SELECT r.* FROM resumes r WHERE ${filter.sql}`, filter.params)
```

编译器固定每个 OR 分支内的 tenant AND 条件，对 owner/organization 映射显式调用业务仓储；数据值只进入参数数组，列标识符只接受业务代码配置的固定名称。空 `organization_ids` 编译为 `tenant AND FALSE`。若资源表没有租户列、身份映射缺失或组织范围无法映射，业务适配必须 fail closed 或先完成 schema 映射，不能删掉租户谓词。SDK 不执行 SQL，也不会自动转换 IAM UUID。

**Express thin adapter（`src/express.ts`，P317，零运行时依赖）:** `createIamExpress(options)` 暴露 Express 中间件——`requirePermission(alias, { ownerOnly })` 与 `currentUser()`。语义与 Python `iam_fastapi`（P316）对称：别名必须登记在 `permissionMap`（未登记在创建中间件时抛错，不猜测稳定码）；`ownerOnly` 要求 data scope 的每个 `any_of` 分支都是绑定已验签 subject 的 owner 约束（出现 tenant/organizations 分支即 403），并经 `localUserIdResolver` 解析产品本地用户主键；IAM 403/503 保留语义，其余契约错误归一 502；会话由业务方 `loadSession` 从**本地已验签** OIDC 会话构建（缺失时抛带 `statusCode` 的错误，原样转发给业务方错误处理）。成功时中间件把 `req.iamUser`（ownerOnly 含 `localUserId`）与 `req.iamDecision` 挂到请求上。仅用结构类型描述 Request/Response（`{headers}` / `{status().json()}`），兼容 Express 4/5，不需要 express 包作为依赖。

```ts
import { createIamExpress, IamAuthorizationClient } from '@iam-platform/authorization-client'

const iam = createIamExpress({
  client: new IamAuthorizationClient(process.env.IAM_API_URL!, process.env.IAM_APPLICATION_ID),
  loadSession: (req) => loadVerifiedSession(req), // 业务方已验签会话；缺失时抛 { statusCode: 401 }
  permissionMap: { 'document.read': 'crm.document.read' },
  localUserIdResolver: (user) => identityRepository.getLocalUserId(user.iamSubject, user.tenantId),
})

app.get('/documents/:id', iam.requirePermission('document.read', { ownerOnly: true }), (req, res) => {
  res.json(listDocumentsForOwner(req.iamUser.localUserId, req.params.id))
})
```

**Express OIDC login-route plugin（`src/express-auth.ts`，P319，零运行时依赖）:** `mountOidcAuth(app, { oidcClient, sessionStore, routeOptions })` 一次挂载 `login`/`callback`/`logout`/`me`（路径可配，默认 `/auth/*`），与 Python `mount_oidc_auth`（P318）语义对称。登录 attempt 与身份令牌只保存在业务方实现的服务端 `IAMAuthSessionStore`（`put/load/take/delete`；`InMemoryIamSessionStore` 仅限开发测试，生产用 Redis/数据库）；浏览器只持一次性 HttpOnly attempt Cookie 与会话 Cookie（HttpOnly + SameSite=lax，`cookieSecure`/`cookieDomain` 可配）。Cookies 由适配器直接解析 `Cookie` 头（不依赖 cookie-parser）。attempt 经 `take` 原子消费（重放 403）；callback 的 Provider 拒绝映射为 403 且不透出细节；`/auth/me` 只返回 `subject`/`tenantId`/`profile`（绝不返回 tokens）；logout 撤销 access/refresh token（best-effort，失败不阻断本地登出）并删除服务端会话。CSRF 防护与代理日志脱敏仍由业务方负责。

```ts
import { createIamExpress, IamAuthorizationClient, InMemoryIamSessionStore, IamOIDCClient, mountOidcAuth } from '@iam-platform/authorization-client'

mountOidcAuth(app, {
  oidcClient: new IamOIDCClient({ issuer: IAM_ISSUER, clientId: ..., clientSecret: ..., redirectUri: ... }),
  sessionStore: new InMemoryIamSessionStore(), // 生产替换为 Redis/数据库实现
  routeOptions: { postLoginRedirect: '/' },
})
```

**Permission-catalog sync（`src/permission-sync.ts`，P321，零运行时依赖）:** 管理面组件——调用方必须持有**平台管理 access JWT**（HS256 management token）；终端用户 OIDC access token 会被 IAM 以 403 拒绝。`IamAdminClient` 覆盖 `GET/POST /api/v1/admin/permissions`（AbortController 超时、错误归一 `IamAdminError` 保留状态码）；`syncPermissionManifest` 把应用权限清单幂等同步到权限目录：清单先本地预检（字段/长度/重复码，非法即 `Error` 且零网络请求）→ 拉目录建 code 索引 → 只创建缺失项；已存在条目一律跳过，**不修改其描述或状态**。`POST` 创建时会附带 `catalog_namespace`（与 `code` 首段一致）；清单可显式传 `catalog_namespace` 做预检。创建遇 409（并发窗口）重拉目录确认（已存在记 skipped，仍缺失保守记 failed）；单条失败不中断整批；目录不可达直接抛 `IamAdminError(503)`。与 Python `sync_permission_manifest`（P321）语义对称；工具不做角色授予。

```ts
import { IamAdminClient, syncPermissionManifest } from '@iam-platform/authorization-client'

const report = await syncPermissionManifest([
  { code: 'demo.document.read', resource_type: 'document', scope: 'read', description: '读取文档' },
], { client: new IamAdminClient(IAM_API_URL), managementToken: MGMT_JWT })
// report.created / report.skipped / report.failed（failed 非空时人工核对后重跑，幂等安全）
```

Run the authorization contract tests and SDK type build with:

```powershell
node --experimental-strip-types --test test/authorization.test.mjs test/express.test.mjs test/express-auth.test.mjs test/oidc.test.mjs test/permission-sync.test.mjs
pnpm build
```

For OIDC tokens, IAM binds checks to the tenant and application in the signed token. The optional configured application ID must be the matching IAM Application UUID. An omitted value uses the token-bound application. Never pass an ID Token, never put the client secret in frontend code, and never treat a timeout as permission.

## Node.js OIDC relying-party client

`IamOIDCClient` in this package implements the IAM authorization-code + PKCE S256 relying-party flow for a **Node.js server only**. It validates same-origin Discovery endpoints, callback state/issuer, RS256 ID/access token signatures and claims, ID-token nonce/`at_hash`, tenant and client binding, UserInfo subject, and returned scopes. It can rotate a refresh token, revoke either access or refresh tokens, and query RFC 7662 token status with `introspectToken`. Every IAM HTTP request defaults to a 5,000 ms deadline (`timeoutMs` configures it); the same AbortController remains active through response-body reads. Timeout and network failures raise `OIDCProtocolError` with status 503, while IAM HTTP responses retain their status code. The RP client does not retry authorization-code exchange or refresh-token rotation.

```ts
import { IamOIDCClient } from '@iam-platform/authorization-client'

const oidc = new IamOIDCClient({
  issuer: process.env.IAM_OIDC_ISSUER!,
  clientId: process.env.IAM_CLIENT_ID!,
  clientSecret: process.env.IAM_CLIENT_SECRET!,
  redirectUri: process.env.IAM_CALLBACK_URL!,
})

// /auth/login: put the complete attempt in a one-time server-side session, then redirect.
const attempt = await oidc.createAuthorizationRequest(['openid', 'profile', 'email', 'offline_access'])
// /auth/callback: atomically take and delete that attempt before completing the callback.
const identity = await oidc.completeLogin(callbackUrl, attempt)
// Save identity/tokens only in a protected server session; browser gets an HttpOnly app cookie.
```

Use `identity.tokens.accessToken` with `IamAuthorizationClient`; call `refresh` and atomically replace the session before the expiry. On logout, revoke the current access token and refresh token from the server, create an `EndSessionRequest`, save its state in the server session, then navigate the browser to its URL; verify and consume returned state before clearing the local session. OIDC end-session clears the browser SSO cookie and refresh sessions but cannot identify every previously issued access token, so revoke the current access token explicitly. The request's `id_token_hint` is in the OIDC logout URL, so access logs must redact this query parameter. Access/refresh tokens and authorization attempts must never be logged or placed in URLs/browser storage. The application must implement CSRF protections, secure HttpOnly/SameSite cookies, one-time callback/logout state, and server-side token storage. This module uses Web Crypto and Fetch and has no runtime dependency; it is not suitable for Vue/browser bundles.

For a security-sensitive backend route that needs a fresh token-state decision, call `await oidc.introspectToken(accessToken, 'access_token')`; the method authenticates with this confidential client's Basic credentials and returns only `{ active: false }` for invalid/inactive tokens. Treat network/protocol errors as denial. `tokenTypeHint` is a hint and does not restrict which token type the provider searches. Do not call introspection from browser code or send the client secret there.

The deterministic Node test uses Node 22.6+ (for TypeScript type stripping), Node's built-in test runner, and Web Crypto:

```powershell
node --experimental-strip-types --test test/authorization.test.mjs test/oidc.test.mjs
```

For production builds run the package TypeScript compiler with the provided `tsconfig.json`.
