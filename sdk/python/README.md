# Python IAM server-side SDK

**2026-10-11 production packaging follow-up：** dev target 镜像 iam-deerflow-package-check:20261011 的 adapter import 已通过。default runtime image 未产出：第一次构建提示 uv.lock stale，之后同版 uv 的 locked dry-run 通过且 uv.lock SHA 未变；重试被 docker.io 的 Python manifest HEAD 与 ghcr.io 的 uv 匿名 token EOF 阻断（包括 pull=false）。待 Docker Hub/GHCR 可达或配置镜像源后重建 runtime 并执行服务级 E2E；本轮未启动服务/数据库。

**2026-10-11 DeerFlow 镜像构建状态：** 已在 DeerFlow .dockerignore 排除 config.yaml、extensions_config.json、备份文件及所有 .env* 变体。三种构建基础镜像当前不在本地缓存；dev target 构建无日志/无镜像超过 3 分钟，两个本次构建进程已终止，具体 registry/daemon 原因未确认。测试服务和数据库没有启动或变更；待 registry 可达/提供镜像源后验证实际构建及容器内 adapter import。

**2026-10-11 async IAM adapter regression:** With DeerFlow backend Python 3.12.14, the IAM SDK provider suite passed 22/22 and DeerFlow provider interoperability passed 12/12, including all four async data-scope cases. These were mock-only runs with no live IAM or database calls; the earlier Windows event-loop hang was not reproduced in this interpreter. Tenant/organization row mapping, production role grants, image release, and live E2E remain open.

`iam_authorization.py` uses only the Python standard library to call `POST /api/v1/authorization/check` from a business backend. It accepts an end-user OIDC access token, passes no browser credentials through, and raises on network/HTTP/contract errors so an unavailable IAM cannot become an allow decision. `compile_postgres_data_scope` turns its validated `any_of` result into a named-parameter PostgreSQL predicate that can be bound through SQLAlchemy `text()` or a compatible PostgreSQL adapter; the caller remains responsible for executing it against the protected query.

The authorization HTTP timeout defaults to 3 seconds (`timeout_seconds=3.0`). Timeout and transport failures raise `AuthorizationServiceError(503)` and never produce an allow decision.

If `include_data_scope=True` and IAM allows the request, pass `tenant_id` and `subject_id` from the server's locally verified IAM OIDC session. `subject_id` must be that IAM token's `sub`, not the business product's local user primary key. The SDK does not send `subject_id` to IAM; it requires a non-empty `any_of` constraint set, validates every clause's `tenant_id` against the verified tenant, validates each `owner.user_id` against the verified IAM subject, accepts only `tenant`/`owner`/`organizations` kinds with their fixed business field names, and returns a normalized allow-listed scope. Missing local identity, cross-tenant or other-subject owner branches, empty, or unknown scope data fails closed (`ValueError` before the request or `AuthorizationServiceError(502)` for a malformed IAM response). Empty organization ID lists are valid and must compile to match no rows.

```python
from iam_authorization import IamAuthorizationClient, compile_postgres_data_scope

iam = IamAuthorizationClient(IAM_API_URL, application_id=IAM_APPLICATION_ID)
decision = iam.require(
    session.access_token,  # issued by IAM and stored in the server-side application session
    session.tenant_id,     # derived from a verified identity token, never request JSON
    "knowledge.document.read",
    resource_id=document_id,
    include_data_scope=True,
    subject_id=session.iam_subject,  # exact OIDC sub; separate from the product's local user id
)
from sqlalchemy import text

if decision.data_scope is None:
    raise PermissionError("IAM omitted the required data filter")
row_filter = compile_postgres_data_scope(
    decision.data_scope,
    tenant_id=session.tenant_id,
    subject_id=session.iam_subject,
    columns={"tenant_id": "d.tenant_id", "owner_user_id": "d.owner_user_id", "organization_id": "d.organization_id"},
    # IAM subject/tenant/organization 与本地 ID 不同时，使用可信服务端映射。
    map_owner_user_id=lambda sub, tenant: identity_repository.local_user_id(sub, tenant),
    map_tenant_id=lambda tenant: tenant_repository.local_tenant_id(tenant),
    map_organization_ids=lambda ids, tenant: organization_repository.local_ids(ids, tenant),
)
rows = session.execute(text(f"SELECT d.* FROM documents d WHERE {row_filter.sql}"), row_filter.parameters)
```

编译器将每个 OR 分支的 tenant 约束与 owner/organization 约束合并，数据值使用独立参数；列标识符仅接受业务代码配置的固定映射，空组织列表编译为 `tenant AND FALSE`。身份映射缺失、资源表没有 tenant 列或 SQL 查询无法应用该谓词时必须拒绝请求，不能删掉过滤条件。SDK 不访问业务数据库，也不会替换产品本地用户或组织主键。

Run the dependency-free authorization contract tests with:

```powershell
python -m unittest discover -s . -p 'test_iam_authorization.py' -v
```

Current data-scope tests: 11 passed, including missing local IAM subject, owner-subject mismatch, tenant branch binding, confirmation that the subject is not sent to IAM, SQL parameterization, mapping and empty-organization behavior.

## DeerFlow Gateway authorization adapter

`iam_deerflow.py` provides a duck-typed DeerFlow `AuthorizationProvider` named `DeerFlowIamAuthorizationProvider`. It maps an explicit `resource:action` or `resource:action:target` key to an IAM permission code, then calls the existing online authorization client with the configured application ID. Unknown mappings, internal principals, missing/mismatched IAM subject, missing tenant/token, IAM errors, and missing or nonmatching application context deny access. Both regular permission checks and data-scope resolution require the decision to echo the exact configured application ID; an omitted value is not treated as a compatible response. Application-level `filter_resources` checks may share one decision per permission code in a single assembly call; when `resource_id_resolver` is configured, every candidate is checked independently so a resource-scoped allow cannot expose a different instance. Execution checks still contact IAM again.

The dependency-free synchronous provider subset previously passed 18 tests; the authorization-client data-scope suite passed 11 tests. On 2026-10-11, the complete SDK provider suite passed 22/22 under DeerFlow backend Python 3.12.14, including all asyncio.run cases. This verifies that interpreter; it does not prove the IAM project bundled runtime behaves the same.

For IAM resource-scoped grants, an application may configure `resource_id_resolver` with a server-side callback that maps the provider request to a trusted IAM resource ID. The value is sent as `resource_id` for both permission and data-scope checks. The resolver must return a non-empty string of at most 180 characters for every mapped request; an exception or invalid/missing value denies the check and never falls back to an application-wide grant. When configured, `filter_resources` checks each candidate independently and does not reuse an allow result across resource IDs. `resolve_data_scope` / `aresolve_data_scope` accept an optional `context` mapping for server-constructed resource metadata. Never populate that mapping from browser request data without validating ownership and tenant membership.

The Gateway must populate `principal.attributes` only from its verified server-side OIDC session. Prefer a redacted Mapping under `iam_credentials` containing `iam_access_token`, `iam_subject`, and `iam_tenant_id`; the older flat server-owned mapping remains supported. `iam_subject` must equal the same principal's `oauth_id`. Never accept these values from the browser, API request context, or feature flags. DeerFlow resolves the mapping from the signed local session `sid` and encrypted token vault for one authorization operation; it must not copy the plaintext token into `RunnableConfig`, checkpoints, or Agent context. Example configuration:

```yaml
authorization:
  enabled: true
  fail_closed: true
  provider:
    use: deerflow.authz.iam_deerflow:DeerFlowIamAuthorizationProvider
    config:
      api_base_url: https://iam.example.com
      application_id: "<IAM DeerFlow application UUID>"
      oidc_provider: iam-prod
      permission_map:
        "route:read:threads:read": deerflow.thread.read
        "route:read:agents:read": deerflow.agent.read
        "route:write:agents:write": deerflow.agent.write
        "route:delete:agents:delete": deerflow.agent.delete
        "route:admin:agents:admin": deerflow.agent.admin
        "route:read:memory:read": deerflow.memory.read
        "route:write:memory:write": deerflow.memory.write
        "route:delete:memory:delete": deerflow.memory.delete
        "route:admin:memory:admin": deerflow.memory.admin
        "model:list": deerflow.model.list
        "model:use": model.invoke
        "tool:use": deerflow.tool.use
      filter_actions:
        model: list
      model_resource_ids:
        gpt-4o: "<tenant IAM model UUID>"
```

**2026-10-10 adapter update:** model listing is mapped separately to `deerflow.model.list`; model invocation maps to IAM `model.invoke` and requires a server-side name-to-model-UUID map; tool checks bind the server-built tool name as `resource_id`. The sync-only interoperability selection, including four focused model/tool regressions, passed 8/8; Ruff check plus format checks passed on the two changed Python files. At that time, the full 12-case file stalled during async data-scope tests under the Windows venv; a 2026-10-11 follow-up passed the complete file 12/12 under DeerFlow backend Python 3.12.14. The adapter does not seed or grant permissions. DeerFlow's remaining tenant/organization row filtering, target database migration, release image and live IAM/browser acceptance are still incomplete. The earlier test-count paragraph below is a dated 2026-10-09 snapshot.

The IAM permission codes must exist and be explicitly granted to the intended application roles; this adapter does not seed codes or grant roles. Map model listing to `deerflow.model.list` with `filter_actions.model=list`; map invocation to the IAM `model.invoke` code and configure `model_resource_ids` from each exact DeerFlow `models[].name` to its active tenant model UUID. An unmapped model is denied before provider use. Tool candidates use their server-built tool name as `resource_id`, allowing per-tool role grants; an application-wide grant remains possible by granting the same permission without a resource ID. `authorize()` sends `include_data_scope=false` for ordinary permission checks. `resolve_data_scope()` and `aresolve_data_scope()` request `include_data_scope=true`, bind the request to the locally verified OIDC subject, and fail closed if IAM omits a non-empty `any_of` scope or returns a different application. They return the validated scope in `decision.metadata["data_scope"]`; they do not execute a business query. The consuming repository must apply it to every relevant read/write path, intersecting it with local ownership rules. DeerFlow currently checks owner-only IAM data scope for selected project, thread, run, document, trash, Agent, and personal-memory operations; tenant/organization row filtering remains incomplete. The dependency-free synchronous adapter subset previously passed 18 tests and the IAM authorization-client suite passed 11 tests. DeerFlow resolves the redacted `iam_credentials` Mapping from its signed local session and encrypted vault for HTTP route, model-catalog, sandbox-sync, and Agent run model/tool authorization. An Agent run receives the capability through a non-serializable `RunContext`; Principal construction only attaches it to a matching OIDC subject and never stores it in graph config/context or checkpoints. Async data-scope lookup refreshes that run capability before making the IAM request. Candidate decisions are cached only when both permission code and resolved IAM resource ID match. The adapter and client are included in DeerFlow's `deerflow.authz` harness package and API image build context; the target image still needs to be built and deployed with the real IAM application and permission map. Upstream session revocation and live IAM interoperability remain unverified.

`iam_authorization.py` 基础授权客户端保持 Python 标准库零依赖，不验证登录令牌或连接业务数据库。业务服务必须从签名验证过的会话取 tenant、IAM OIDC `sub` 和 app；该 `sub` 与产品本地 user primary key 是两种不同标识。数据范围请求传 `subject_id=session.iam_subject`，SDK 用它拒绝不匹配的 `owner_user_id` 条件，但不会把 `subject_id` 发给 IAM。`compile_postgres_data_scope` 只生成参数化查询谓词；业务仓储必须先配置并验证本地身份映射，再在实际资源查询中执行该谓词。

## OIDC 登录 relying-party 客户端

Python 后端项目可以安装 OIDC 可选依赖，复用 `iam_oidc.py` 的 IAM 授权码 + PKCE 流程和令牌校验：

```powershell
pip install -e "path/to/iam-platform/sdk/python[oidc]"
```

```python
from iam_oidc import IamOIDCClient

# 所有配置从后端 Secret Manager/环境配置读取；绝不将 client_secret 暴露给 Vue/React。
oidc = IamOIDCClient(
    issuer=IAM_OIDC_ISSUER,
    client_id=IAM_CLIENT_ID,
    client_secret=IAM_CLIENT_SECRET,
    redirect_uri=IAM_CALLBACK_URL,
)

# /auth/login: 保存 attempt 到服务端 session (DB/Redis)，随后 302 跳转 authorization_url。
attempt = oidc.create_authorization_request(scopes=("openid", "profile", "email", "offline_access"))

# /auth/callback: 先从服务端 session 取出并删除 attempt，再交由 SDK 校验回调。
identity = oidc.complete_login(callback_url, attempt)
# identity.subject 与 identity.tenant_id 来源于验签后的 ID/access token；
# tokens.access_token 用于 IAM 授权 SDK；refresh_token 只能放在受保护的服务端 session。

# 访问令牌过期前原子更新 session，替换已轮换的 refresh token。
identity = oidc.refresh(identity)

# /auth/logout: 服务端退出时撤销当前 IAM access/refresh token，再清理本地 session 和 HttpOnly cookie。
oidc.revoke_access_token(identity.tokens.access_token)
oidc.revoke_refresh_token(identity.tokens.refresh_token or "")

# 可选：在线检查本客户端令牌。active=False 时必须拒绝当前请求。
status = oidc.introspect_token(identity.tokens.access_token, "access_token")
if not status["active"]:
    raise PermissionError("IAM token is inactive")
```

RP-Initiated Logout 会结束浏览器 SSO Cookie 并撤销该客户端的 refresh token；IAM 不会从该请求推断当前 access token 的 `jti`。退出时应先分别调用 `revoke_access_token` 与 `revoke_refresh_token`，再发起浏览器 logout；业务服务使用在线授权 SDK 时，access token 撤销会即时生效。

若需要结束浏览器中的 IAM 单点登录会话，生成 RP-Initiated Logout 跳转，并在业务服务端保存 `state` 后让浏览器顶层访问：

```python
end_session = oidc.create_end_session_request(identity, IAM_POST_LOGOUT_CALLBACK_URL)
session["oidc_logout_state"] = end_session.state
return redirect(end_session.url)
```

回到业务站点后，先对比并消费 session 中的 `oidc_logout_state` 再清理本地登录态。OIDC logout GET 请求按协议把 `id_token_hint` 放在 URL 参数中；边缘代理/应用访问日志必须脱敏该参数。只撤销 refresh token 而未访问 end-session endpoint 会结束业务本地会话，但 IAM SSO Cookie 仍可能继续有效。

客户端执行 Discovery 并验证 issuer/同源 HTTPS endpoints、RS256 签名、issuer/audience、callback `state`/`iss`、ID-token nonce 和 `at_hash`、access-token client/tenant/purpose、UserInfo subject。`introspect_token` 以 confidential client Basic 认证在线查询，仅接受同一 client 当前有效的 access/refresh token；异常时抛错，未知/失效令牌以 `{"active": false}` 返回，调用方必须 fail closed。刷新时检查主体/租户未切换、权限 scope 未扩大且 refresh token 确实轮换。调用方必须将一次性 attempt 和令牌放入 Redis/数据库等服务端 session，不得用仅签名未加密的前端 cookie 存储 PKCE verifier 或令牌；退出时即使撤销失败，也应清除本地会话，并记录安全审计。SDK 不负责浏览器 Cookie、CSRF 防护或自动 SQL/向量数据过滤。

核心 OIDC 流程测试可在 Python 安装了 `[oidc]` 依赖时运行：

```powershell
python -m unittest discover -s . -p 'test_*.py'
```

OIDC 测试使用临时 RSA 密钥和 mock HTTP；不会访问网络或创建真实 IAM 应用。接入项目仍需使用其正式数据库会话存储与真实 Provider client/callback 做浏览器端到端验收。

## 服务端 OIDC Token 加密辅助

`iam_token_vault.py` 提供可选的 AES-256-GCM 加密封装，用于业务后端将 IAM access/refresh/ID token 写入其服务端 vault。需要安装 SDK 的 `[oidc]` extra（该 extra 包含 `cryptography`）。令牌密文使用带版本前缀的 URL-safe envelope；认证附加数据绑定 `issuer`、已验证的 OIDC `subject`、`tenant_id` 和 token 类型，密文不能被复制到另一个身份、租户或用途下解密。

```python
from iam_token_vault import IamTokenVaultCipher

# 从 Secret Manager 读取恰好 32 字节的 AES key；不要从浏览器或普通业务请求取得。
cipher = IamTokenVaultCipher(secret_manager.read_bytes("iam-oidc-vault-key-v1"))
encrypted_access_token = cipher.encrypt(
    verified_tokens.access_token,
    issuer=verified_identity.issuer,
    subject=verified_identity.subject,
    tenant_id=verified_identity.tenant_id,
    token_type="access_token",
)
# 只把 encrypted_access_token 和服务端 session 元数据交给持久化层。
```

调用方仍须实现数据库事务/访问控制、保存独立的 key identifier、按需解密、token expiry 与 refresh rotation、IAM 撤销/本地登出、过期记录清理和审计。此 helper 不存储或缓存明文、不会输出令牌日志，也不提供密钥轮换、数据库 repository、Gateway principal 注入或完整 OIDC session；它本身不表示 DeerFlow 或其它业务后端已接入 IAM。SDK 基础 authorization extra 保持零依赖；不要把解密结果放到 Vue、浏览器 Cookie、流程图配置或普通日志中。

若更换密钥，接入方应在自己的受控存储中记录 `key_id`，使用受保护的旧 key 解密并用新 key 重新加密，完成并验证后再撤销旧 key；本 helper 不会自动识别或轮换 key。隔离测试（需已安装 `[oidc]`）：

```powershell
python -m unittest discover -s . -p 'test_iam_token_vault.py' -v
```
