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

# 变更日志

## 2026-10-09 · ToC 注册密码步骤对齐

- 修正注册页第一屏误显示密码框、但申请验证码后又清空密码的体验。现在第一屏只收邮箱、姓名和条款/隐私确认；用户拿到验证码后才设置新密码或输入已有 IAM 账号的当前密码。
- `/oidc/login-context` 现在提供可配置的验证码重发冷却秒数，登录页按后端值倒计时；重发时清空旧验证码但保留已输入密码，退出注册流程仍清理二者。同步 PRD、前后端 README、整体 README、架构说明和项目 Skill。
- 验证：`verify-local.ps1` 的完整隔离 PostgreSQL suite **152/152 通过**，runner 清理随机测试库；容器前端 `vue-tsc -b` 与 Vite production build 通过（3205 modules，入口 388.33 KB / gzip 120.06 KB）。未迁移开发库，也未完成真实 SMTP/浏览器注册验收。

## 2026-10-09 · Windows 本地启动与验证入口

- 新增根目录 `start-local.ps1`：解析真实 `docker.exe`、检查 Compose 配置并构建启动开发服务、探测 API readiness；不会自动迁移数据库或 bootstrap 管理员。该启动脚本只通过 PowerShell AST 解析，尚未实际重启当前服务。
- 新增 `verify-local.ps1`：以一次性 API 容器运行完整隔离 PostgreSQL suite，再构建锁定依赖的前端镜像（Dockerfile 执行 `vue-tsc -b` 与 Vite build）；显式关闭测试容器的 OIDC key 初始化，不触碰 `iam` 主库，也不依赖 Windows pnpm shim。
- 同步启动指南、PRD、前后端 README、整体 README 和项目 Skill。两个脚本通过 PowerShell AST 语法解析；`verify-local.ps1` 端到端运行成功，后端 149/149、前端 `vue-tsc -b`/Vite 构建 3205 modules（入口 388.57 KB / gzip 约 120.1 KB）。

## 2026-10-09 · ToC 自助注册与租户边界加固

- 消费租户增加 `organization/consumer` 类型，存量默认 `organization`；后端只允许 `consumer` tenant 开放 ToC 自助注册。应用开放策略前锁定并检查租户类型；租户类型变更需先关闭旗下所有应用注册并写审计，管理台支持创建/转换。
- 注册改为先申请并验证邮箱，第二步才提交新密码或已有 IAM 账号当前密码。待验证 challenge 不再存密码摘要；migration `0024_tenant_registration_audience` 清理旧摘要列并加入租户类型约束。
- 更新 PRD 注册流程、身份/租户模型、隐私和反滥用考虑、灰度与上线验收门槛；同步前后端 README、架构、运维、接入计划、用户清单、UI 走查记录和项目 Skill。
- 验证：完整隔离 PostgreSQL suite 从空库迁移至 `0024` 后 **149/149 通过**；临时测试库复核为 0 个。前端 `vue-tsc -b` 与 Vite production build 通过（3205 modules，入口 388.57 KB / gzip 120.04 KB）。未迁移开发库；仍需真实 SMTP/浏览器验收，生产注册保持关闭。

## 2026-10-09 · 用户会话目录与单会话远程退出

- 用户管理新增会话列表/远程退出入口；后端按稳定 IAM refresh session ID 与 OIDC refresh-token family 聚合，不回传凭证摘要，并在实际撤销时写 `user.session.revoke` 审计。管理员不能从该页注销当前管理员身份。新增 `backend/tests/test_session_management.py` 和 OIDC `sid` 回归用例。
- 新签发 IAM/OIDC access token 带 `sid`；IAM rotation 原位替换 hash、保留 session ID；OIDC 离线授权 family 撤销后，IAM 在线鉴权、UserInfo 和 Introspection 立即拒绝相应 access token。不需要新增 migration。
- 同步 PRD、前后端说明、架构、运维、集成计划、配置清单及 Skill。此版本不采集设备名、UA、来源 IP 或最后活动时间；未请求 `offline_access` 的 OIDC access token 不进入持久 session 目录；升级前无 `sid` token 和离线 JWT-only RP 有自然到期窗口。
- 验证：完整隔离 PostgreSQL suite 从空库迁移至 `0023_user_membership_lifecycle` 后 **143/143 通过**；测试库已清理，复核 `iam_test_*` 数据库数量为 0，开发库保持 `0021_resume_wallet_perms`。前端 `vue-tsc -b`、Vite production build（3205 modules，入口 388.46 KB / gzip 120.05 KB）及 Python AST 静态解析 96 个应用/测试文件通过。真实浏览器/API 管理写入未验收；开发 API readiness 仍为 `503 database_migration_pending`。

## 2026-10-09 · 自助注册与账号生命周期全面核对

- 将 ToC 自助注册的产品边界统一为：目标产品登录页邮箱 OTP 注册；验证前不创建活动账号/成员/会话；一个 IAM 全局身份按应用分别加入专用消费 tenant 和普通角色；IAM 管理台与企业租户仍邀请制，注册不创建 tenant/admin。旧账号进入新应用需证明原密码，不按邮箱自动合并；停用/离职成员不能经公开注册恢复。
- 将 DeerFlow 规则统一为用户已确认的决策：OIDC 首登自动 provision 普通本地用户；管理员只允许 IAM 显式授权后由 Gateway 服务端在线校验，不根据邮箱或旧 `admin_emails` 提权。身份链接必须使用可信 `(issuer, sub)`；token/tenant vault、中央授权和已有账号迁移仍待开发。
- 将全局用户状态 `active/disabled/locked` 与单 tenant 成员 `active/disabled/departed`、会话撤销边界和重新邀请规则同步到 PRD/运维/架构/前后端说明/集成计划/配置清单/Skill。补充新注册账户的模型试用与成本额度决策，明确当前配额执行关闭时不能开放可计费模型调用。
- 验证：前端 `vue-tsc -b` 与 Vite production build 通过（3205 modules；入口 388.40 KB / gzip 120.04 KB）。后端完整套件此前已在随机临时 PostgreSQL 从空库迁移至 `0023_user_membership_lifecycle` 后 137/137 通过；本轮只更新文档，没有重跑后端测试或迁移开发库。开发库仍为 `0021_resume_wallet_perms`、API readiness 503；真实 SMTP/注册浏览器流程和 lifecycle 管理页浏览器验收尚未完成。

## 2026-10-09 · ToC 自助注册产品边界与安全证据加固

- 将 ToC 自助注册规则补全为：首期邮箱 OTP + 密码，只开放产品品牌登录页；全局 IAM identity 可跨产品复用，但每个应用的 tenant membership 和普通角色独立，注册一个产品不会加入其它产品。IAM 管理台与企业租户继续邀请制，不允许匿名创建 tenant/admin。
- 注册默认角色增加 tenant/organization 数据范围拒绝，保护个人用户数据；业务系统仍须执行 owner 过滤。政策 URL 随版本进入注册请求、待验证 challenge 与 consent；发码、outbox 重试和兑换都复核当前政策链接，记录按用户/应用/版本保留，不覆盖历史同意。注册地址字段长度限制为 2048。
- 同步 PRD、用户配置清单、运维、架构、接入计划、前后端 README、项目 Skill 与本变更日志；列明多 tenant 产品、MFA、用户导出/注销、CAPTCHA/自适应风控、邮件配额/告警等决策或上线缺口。
- 验证：注册/迁移/维护聚焦测试 15/15；完整后端 suite 在随机临时 PostgreSQL 从空库迁移至 `0022_toc_public_registration` 后 129/129；前端 `npm run build`（3205 modules）通过。临时测试库由 runner 清理。开发库只读确认仍在 `0021_resume_wallet_perms`，没有应用 migration，API readiness 为 `503 database_migration_pending`；SMTP、浏览器注册验收和生产风控配置未完成。

## 2026-10-09 · 全项目状态核对与过时注册路线修正

- 重新核对 PRD、源码迁移 head 和运行工具：ToC 注册迁移 `0022` 仍未应用；后端此前 109/109 PostgreSQL 套件不覆盖注册切片，当前 Docker Linux Engine named pipe 返回 permission denied，本机 bundled Python 缺少后端运行依赖。
- 修正 PRD 路线图中把 ToC 邮箱注册列为“未实现”的过时表述，改为源码已实现、迁移/SMTP/浏览器验收未完成；同步根/后端 README、架构、接入计划、待提供清单与项目 Skill 的最新验证边界。
- 不对本地数据库执行迁移，不尝试 Docker 服务写入；前端构建和 Python 语法检查结果按既有本轮核验记录。

## 2026-10-09 · 注册验证码密钥与 JWT 密钥解耦

- 将注册邮箱、OTP 摘要/派生和注册冷却桶 HMAC 改用独立 `PUBLIC_REGISTRATION_SECRET`；全局注册开关启用时，配置校验要求该密钥至少 32 个字符。Compose 与 `.env` 示例仅把密钥注入 API，默认注册仍关闭。
- 同步 PRD 的注册流程/安全要求、架构、运维、用户输入清单、前后端 README、项目 Skill 与变更日志；注册密钥需稳定保管，轮换它会使未过期验证码失效，操作手册要求先排空待投递 outbox。
- 本轮保持 migration `0022_toc_public_registration` 未应用；前端类型检查/Vite build 与 Python `compileall` 通过，未运行后端测试或服务端注册验收。当前 bundled Python 缺少 `pydantic_settings`，因此无法执行设置对象的运行时导入检查。

## 2026-10-09 · ToC 注册实现构建核验与状态同步

- 使用前端本地已安装的 `vue-tsc -b` 和 Vite 二进制完成检查与生产构建：3205 modules，入口 388.36 KB / gzip 120.02 KB；Python `compileall -q app migrations` 通过。
- `pnpm run build` 启动器因无法联网验证 pnpm 发布签名而失败，未关闭签名校验或下载依赖；改用已安装二进制完成本地构建。
- 同步根 README、前后端 README、PRD、架构、接入计划、运维手册、待提供清单与 Skill：本地数据库最近确认在 `0021_resume_wallet_perms`，当前源码 migration `0022_toc_public_registration` 尚未迁移；109/109 后端套件是迁移前历史结果。本轮未运行后端测试、API、SMTP、浏览器注册验收或数据库迁移。

## 2026-10-09 · 实现 ToC 自助注册闭环

- 将匿名账号注册改为 ToC 产品登录页的邮箱 OTP 流程；用户验证码通过前不创建账号、租户成员、角色绑定或会话，浏览器不能提交 tenant、role 或管理员字段。新用户的 Argon2 摘要暂存在限时挑战；既有 IAM 身份需同时验证 OTP 和当前密码，不修改原密码，并可加入目标应用。
- 增加每应用 `disabled/open` 策略、同租户/同应用普通角色白名单、协议版本同意记录、HMAC 邮箱/IP 冷却、验证码尝试限制及可重试事务邮件 outbox。SMTP 全局开关默认关闭；登录主题的 `show_register` 仅作为入口展示条件。应用管理页能配置策略/角色/协议版本，登录主题可配置条款/隐私链接。
- 新增迁移 `0022_toc_public_registration` 和环境配置；它尚未应用（已核验本地开发库保持 `0021_resume_wallet_perms`）。本轮未执行前端构建、后端/接口测试、数据库 migration、SMTP 或浏览器注册验收；Production 注册保持关闭。需配置专用消费 tenant、普通角色、协议链接和邮件/WAF 额度。
- 根据实施状态同步 PRD、整体/前后端 README、架构、接入计划、操作手册、用户输入清单、项目 Skill 和本变更日志。每产品专用消费租户、只在 ToC 登录入口展示是采用的推荐默认值，尚非用户明确确认；CAPTCHA、退信看板和注册运营报表尚未实现。

## 2026-10-09 · 增加服务端 OIDC token 加密辅助

- Python SDK 新增 AES-256-GCM token 加解密 helper，envelope 带版本，认证附加数据绑定 issuer、subject、tenant 和 token type；令牌明文按 UTF-8 字节数设上限，并以固定 redacted repr 隐藏 cipher 对象。
- 新增 4 项隔离测试，覆盖加解密往返、随机 nonce、上下文错绑拒绝、畸形输入/密钥长度及多字节 UTF-8 大小边界；使用 bundled Python 运行 IAM authorization、DeerFlow adapter 与 token-vault 测试子集 25/25 通过。需要 PyJWT 的 RP 客户端测试未纳入本次运行。
- 同步 SDK、前后端、整体架构、PRD、接入计划、待输入清单和 `iam-project` Skill。此 helper 不含数据库存储、key ID/密钥轮换、refresh rotation/撤销或 DeerFlow Gateway 注入；不宣称 DeerFlow IAM 接入已完成。
- 同步 ToC 自助注册待确认项：入口范围、消费租户模型和默认普通角色需产品决策；注册开关仍关闭。

## 2026-10-09 · ToC 自助注册需求分析

- 用户确认 ToC 用户应能自行注册。PRD 新增按应用开关的邮箱 OTP 注册、待验证状态、事务化消费租户/应用普通角色分配、滥用防护、隐私/邮件运维要求和验收清单。
- 推荐每个 ToC 产品使用独立消费租户以兼容当前应用固定 `tenant_id` 的 OIDC 模型；公开注册仍未实现，当前 `/auth/register` 不满足生产安全要求。IAM 管理台/企业租户不开放匿名注册。
- 同步整体 README、前后端说明、接入计划、待决清单和项目 Skill。待确认首期消费租户模型后再落 migration/API/UI，未开放任何环境的注册开关。

## 2026-10-09 · OIDC ID Token 租户声明

- IAM OIDC Provider 在签名 ID Token 加入应用所属 `tenant_id`，Discovery 的 `claims_supported` 同步公布该声明。
- Python RP SDK 仍以签名 access token 的 tenant 为权威；ID Token 提供该 claim 时会拒绝租户不一致。该 claim 只提供可信身份上下文，不直接授予任何权限；DeerFlow token vault、在线授权和真实 OIDC 联调仍未完成。
- 增加 provider 声明/Discovery 与 SDK 登录/refresh 租户不匹配回归用例；当前 Python runtime 缺少 FastAPI/PyJWT，Docker Engine pipe 不可用，测试未能执行。
- 同步 PRD、接入计划、前后端说明、整体 README、用户待办清单和 `iam-project` Skill。

## 2026-10-09 · DeerFlow OIDC 首登禁止邮箱提权

- OIDC 新建账号现在固定为 DeerFlow 普通用户；遗留 `admin_emails` 字段继续解析以兼容配置，但不再授予管理员角色。已有账号不自动降级。
- 同步 PRD、集成计划、待提供配置清单、前后端说明和 `iam-project` Skill。该改动只关闭首登隐式提权，IAM token/tenant 服务端保管、Gateway 在线授权与现有管理员迁移尚未完成。
- DeerFlow OIDC 角色回归断言已更新；本轮未找到可用的 DeerFlow pytest/Python 项目环境，尚未运行该测试。

## 2026-10-09 · 完成角色复制纵向切片

- 增加平台管理员角色复制 API 和角色列表复制弹窗；新角色沿用源租户/应用/启停状态，可编辑标识、名称和说明。
- 每次复制默认不复制授权；显式选择后只复制仍启用权限的通用/资源级 grant 与对应数据范围。成员直接绑定和用户组角色绑定永不复制；角色、副本策略和 `role.clone` 审计同事务提交。
- 新增六项隔离 SQLite 测试，覆盖默认清空、活动授权/数据范围复制、停用权限过滤、成员绑定隔离、冲突回滚和源角色不存在，6/6 通过；连同角色更新回归共 10/10 通过，其中 PostgreSQL 用例以外层事务回滚。前端 `npm run build`（vue-tsc + Vite，3205 模块）通过。OpenAPI 已发布受保护路由；本轮未进行浏览器写入或复制并发验收。
- 更新 PRD、前后端/整体说明、待提供配置清单和 `iam-project` Skill；角色复制决策不再作为待确认项。

## 2026-10-09 · 轮换本地登录与服务凭据并确认 DeerFlow 首登策略

- 轮换本地管理员密码、PostgreSQL `iam` 角色密码和 JWT 签名密钥；凭据只保存在根 `.env`，未打印、提交或写入文档。保留 PostgreSQL 数据卷；未改 SMTP 或模型用量 API Key。
- 管理员密码通过现有一次性密码重置接口落库，递增 `auth_version`、撤销旧刷新会话并写入审计。验证管理员密码哈希匹配 `.env`、管理员活动刷新会话为 0、数据库 `SELECT 1` 成功、readiness HTTP 200，postgres/api/console 均 healthy。未执行浏览器登录。
- 用户确认 DeerFlow 首次 IAM 登录自动创建普通用户，管理员权限只由 IAM 明确授权；同步 PRD、待决清单、集成计划、运维手册、前后端说明和项目 Skill。OIDC token/tenant 保管、中央授权和 Gateway 权限映射仍未实现。


## 2026-10-07 · 明确三产品接入范围并刷新验证状态

- 前端 `vue-tsc --noEmit` 通过；Vite 生产构建转换 3205 个模块，入口 382.51 KB / gzip 118.65 KB，产物定向输出至 Windows Temp。
- Python 授权/OIDC SDK unittest 20/20 通过；后端 app/migrations/tests 共 110 个 Python 文件 AST 解析通过。
- 完整后端 unittest 本轮收集/运行 60 项，12 项因当前可用 venv 缺少已声明依赖 `pwdlib` 而导入失败，4 项 PostgreSQL 用例跳过。console `5175` 与 API OpenAPI 返回 HTTP 200；`/api/v1/ready` 报告 `503 database_migration_pending`。未连接或写数据库，未执行 migration；本地 `0017`–`0021` 仍等待用户明确授权。
- PRD 已将 AI 简历、Knowledge Base、DeerFlow 明确为分阶段交付但均属于本期完整接入范围；更新 V1.0 集成状态、生产验收缺口与三产品待接入项。
- 更新待决清单记录本机 API readiness 处于迁移待处理状态及 `0017`–`0021` 的用户授权动作。
## 2026-10-06 · AI Resume 岗位扩展 API 接入 IAM

- 浏览器扩展的本人简历回填、岗位收藏/读取/进度/历史/删除统一增加 `resume.read` / `resume.write` 在线权限；重新分析同时要求 `ai.generate`，模型调用沿用 provider 内 `model.invoke` 守卫。
- 所有用户 API 继续先验本地登录，并保留 `req.user.id` owner 查询；未绑定账号维持本地授权兼容，绑定账号遇到中央拒绝或故障 fail closed。复用已有权限码，没有 schema 或 IAM migration 变更。
- 新增 5 项扩展路由契约测试，AI Resume Node 全量测试 36/36 通过（临时目录、DB/IAM 环境变量为空）；真实 IAM/浏览器和业务数据库验收待完成。同步两项目 PRD、前后端/整体说明、IAM PRD、集成计划、架构、配置清单与 Skill。

## 2026-10-05 · AI Resume 个人模型与提示词配置权限

- 用户自选 AI 任务模型与任务提示词读取增加 `resume.read` 检查，保存和恢复默认值增加 `resume.write` 检查；仍从认证会话取本地用户 ID 执行 owner 过滤。
- 扩展 AI Resume 工作区 IAM 路由契约覆盖；沿用已有 permission code，不增加 IAM migration。Node 后端完整套件 31/31 通过（Temp 目录运行、无 DB/IAM 配置）；真实 IAM/业务数据库/浏览器联调未验收。
- 同步 PRD、集成计划、架构、权限配置清单、`iam-project` Skill，以及 AI Resume 整体、前端和后端说明。

## 2026-10-05 · AI Resume 用户工作区接入 IAM 权限

- 职业目标、个人面试题套题/任务/练习/点评读取和写入对 IAM 绑定账号执行 `resume.read` / `resume.write`；点评写入同时需要 `ai.generate`。服务端身份来自本地认证会话，owner SQL 仍按本地用户 UUID 限定。新增产品级权限动作避免将本地自增 ID 作为 IAM `resource_id`。
- 复用 IAM 已登记的 `resume.read/write` 与 `ai.generate`，没有新增权限目录或 migration。新增 5 项 Express 路由契约测试；AI Resume Node 全量测试 31/31 通过。测试在 Windows Temp 运行，数据库/IAM 环境变量清空，未连接数据库；真实 IAM/浏览器联调仍待完成。
- 同步 IAM PRD、集成计划、架构、用户配置清单、前后端/整体 README、AI Resume 前后端说明和 PRD、项目 Skill。

## 2026-10-05 · 角色权限影响预演细化

- 角色权限预览把活动用户组继承成员纳入去重统计，并按权限估算适用范围内其它活动角色通用授权的覆盖数；平台角色、应用角色 UI 显示对应明细。保留实例授权，按有效权限/应用/模型状态过滤当前不可能在线生效的变化。
- 新增 4 项内存 SQLite 测试：直接绑定与组继承去重、其它通用角色抵消、跨应用范围隔离、停用组和实例授权范围。4/4 通过；没有连库或运行迁移。前端 `vue-tsc --noEmit` 与 Vite production build（3205 modules）通过；浏览器 UI 尚未验收。
- 同步 PRD、整体/架构说明、前后端 README、UI Review 与 `iam-project` Skill。潜在人数仍不是完整有效权限净差异，实例级资源覆盖和数据范围结果未逐请求模拟。

## 2026-10-05 · 钱包授权集成隔离复核

- 重新运行 AI Resume Node 全套回归，26/26 通过；IAM `0017` 版本列扩容和 `0021` 钱包权限目录 mock 单测 2/2 通过；读取 Alembic 源码唯一 head `0021_resume_wallet_perms`。测试均在无 `.env` 的 Windows Temp 目录运行，数据库/IAM 环境变量清空；没有连接数据库。
- 修正 PRD 当前未实现清单：登录失败节流已在 `0020` 加入源码，仍未完成的是 MFA、邮箱验证、邮件持久重试等工作。补充更新整体、前端/后端说明和项目 Skill 的隔离验证结果。
- Knowledge Base 文档/集合模型目前缺少可将 IAM owner/organization 范围映射到业务行的可信字段；DeerFlow 现有 OIDC 登录只生成本地 Gateway 会话，没有可供 IAM 判权使用的用户 access token 保管映射。本轮未伪造这两项数据/身份绑定。

## 2026-10-05 · AI Resume 钱包权限接入与迁移版本列修复

- AI Resume 用户钱包余额、流水、充值信息新增中央 IAM `resume.wallet.read` 校验，充值申请单独校验 `resume.wallet.recharge`；服务端继续以认证后的本地 `user_id` 限定本人钱包。IAM Alembic `0021_resume_wallet_perms` 只登记权限码，不自动授予角色。
- 修复迁移链版本列容量：Alembic 默认 `alembic_version.version_num` 为 `VARCHAR(32)`，而既有 `0018` revision ID 超长；`0017` 现在先扩展为 `VARCHAR(128)`，再保存后续 revision。权限码迁移仍未运行，须先取得用户对本地开发库 `0017`–`0021` 的明确授权。
- AI Resume Node 全套测试 26/26 通过；IAM 迁移单测 2/2 通过；`alembic heads` 唯一 head 为 `0021_resume_wallet_perms`。未连接或迁移数据库，也未完成真实 IAM 角色授权、服务联调或浏览器验收。
- 同步 PRD、接入/运维/架构文档、用户输入清单、前后端与整体 README、AI Resume 说明及 `iam-project` Skill。

## 2026-10-05 · 清理认证链接中的一次性凭据

- Vue 启动时只解析一次 URL fragment；捕获邀请 bearer token、OIDC 同意 ticket、密码重置 token 后，立即以 `history.replaceState` 移除当前地址和历史记录项中的 fragment，降低复制、截图或浏览器历史暴露凭据的机会。一次性凭据仍只在页面内存中用于现有认证流程。
- 同步前后端 README、整体 README、PRD 和 iam-project Skill。后端/API 契约与数据库 schema 未改，未连接数据库。
- `vue-tsc -b` 与 Vite production build 均通过（3205 modules，入口 382.51 KB / gzip 118.65 KB）。本机 API/console 服务不可用，未做浏览器端链接验收或数据库操作。

## 2026-10-05 · 后端全量用例恢复与密码重置链接修复

- 修复 SMTP 密码重置 URL fragment 重复 `#` 的实际缺陷，链接现在与前端 `#password-reset=` token 消费逻辑一致，token 不会进入 query string。
- 修正应用状态契约测试对新授权守卫的 mock，以及权限撤销测试在提交后继续读取已删除 ORM 对象主键的问题；不改变权限运行策略。
- IAM 全量后端 unittest 99 项通过，28 项 PostgreSQL 集成用例因未配置 `DATABASE_URL` 跳过。为避开共享 DeerFlow venv 缺少 `pwdlib`，将项目现有锁定 `pwdlib[argon2]` 依赖放在 Windows Temp overlay 中；测试工作目录没有 `.env`，已清空数据库环境变量，未连接或迁移数据库，也未修改 DeerFlow 环境。
- 本机 `localhost:8011` API 和 `localhost:5176` console 当前不可用；生产配置、迁移授权与登录态浏览器验收仍待完成。同步根/前端/后端 README、PRD、UI Review、项目 Skill。


## 2026-10-05 · 审计日志多条件检索与分页

- 新增管理员审计搜索 API `/api/v1/admin/audit/search`，支持组合精确筛选、租户/操作者上下文、时区明确的起止范围、稳定排序、总数与服务端分页；原 `/api/v1/admin/audit` 数组响应保持兼容。前端新增结果/对象/身份/时间过滤、分页控制和只读详情弹窗，修正审计结果标签映射。target_type、target_id 和 outcome 未新增索引，需结合数据规模和查询计划评估。
- 未改数据库 schema 或迁移。同步 PRD、整体/前后端 README、架构、UI Review 和 iam-project Skill。
- `vue-tsc -b`、Vite production build（3205 modules）以及 audit API/schema/test 三个 Python 文件 AST 解析通过。新 SQLite 查询测试未能导入：复用的 DeerFlow Python venv 缺少 `pwdlib`，失败发生在管理路由聚合阶段、SQLite setUp 之前；没有连接数据库。当前未登录管理台，需后续做筛选交互与窄屏浏览器验收。


## 2026-10-05 · 非开发环境关闭未完成的公共注册

- Settings 现在拒绝非开发环境 `ALLOW_PUBLIC_REGISTRATION=true`；注册邮箱验证、租户所有权及初始角色策略完成前，仅开发环境可以验证基础注册路由。
- 增加生产配置回归覆盖，并令该测试显式禁用 `.env` 加载，避免测试取用机器上的部署配置。同步 PRD、前后端/整体 README、架构、用户清单与 IAM Skill。
- `test_deployment_configuration.py` 在隔离工作目录使用 DeerFlow 现有 Python venv 通过 7/7；测试显式禁用 `.env` 读取，没有连接数据库或启动容器。更大范围后端套件的依赖限制仍待确认。

## 2026-10-05 · 增加生产部署配置预检

- 新增 `deploy/validate-production.ps1`：静默检查 Compose 配置插值，使用 Caddy 容器校验主配置及可信代理 drop-in，使用 API 生产运行用户校验 Pydantic 配置和活动 OIDC RSA 私钥，并在已构建的 console 镜像中执行 `nginx -t`；`-IncludeKeyRotation` 可附加轮换 overlay 并校验备用 RSA 私钥。预检不启动长期服务、不连接数据库、不执行 Alembic migration。
- 运维手册将预检加入正式 bootstrap 之前；同步 PRD、整体/前后端 README、架构、接入计划、用户清单和 IAM Skill。未触碰数据库或外部业务仓库。
- PowerShell 语言解析器确认脚本语法通过；当前环境没有可用 Docker CLI，因此尚未运行 Compose、Caddy 或 Nginx 容器校验，须在具备 Docker Compose V2 与构建镜像的环境执行。

## 2026-10-05 · 生产登录来源 IP 的可信代理配置

- 生产 Caddy 现在以 `{client_ip}` 覆写专用 `X-IAM-Client-IP`；默认没有可信代理，仍按直接连接对端计数。只有运维显式放入 `deploy/caddy/trusted-proxies/*.caddy` 的 CIDR 会启用真实来源解析；Compose 以只读方式挂载 drop-in 目录。
- 新增 CDN/LB 配置示例和操作步骤，提醒仅信任代理实际出口 CIDR，并依据 X-Forwarded-For 的追加方式选择 `trusted_proxies_strict`；同步前后端/整体 README、PRD、架构、运维、接入计划、用户清单与 IAM Skill。数据库迁移和业务仓库未改动。
- 验证状态：本环境此前无可用 Docker CLI/Caddy 容器，尚不能运行 `caddy validate` 或生产 Compose 容器级验证；本次只完成源配置与文档变更，需在有 Docker/Caddy 的部署环境验证 Caddy 解析及 CDN/LB 实际来源链路。

## 2026-10-05 · IAM 核心离线定向测试通过

- 使用 DeerFlow 现有后端 Python venv 运行登录节流/维护、授权模拟、模型配额契约和生产配置定向测试，共 30 项通过、4 项 PostgreSQL 集成用例跳过。运行前确认 DATABASE_URL 和 backend .env 均不存在，没有连接 IAM/业务 PostgreSQL。
- 同步整体、前后端 README、PRD、接入计划、UI Review 和 iam-project Skill。更大范围管理 API 测试因复用环境缺少 pwdlib 无法收集；IAM 完整后端套件尚未运行，真实 HTTP 429、PostgreSQL 行锁/迁移和浏览器视觉验收仍未完成。

## 2026-10-04 · 校准知识库接入迁移状态

- 架构文档中的当前接入待办由 IAM `0017`–`0019` 补齐为 `0017`–`0020`，与当前源码 head 和其他项目说明保持一致。`验收记录.md` 中同区间文字属于 2026-10-03 的历史记录，保留原始日期语境。
- 本次只修正文档，没有改动应用代码或数据库；IAM 本地迁移仍需用户授权，KB 数据库 revision 仍未知。

## 2026-10-04 · 登录失败持久节流与重试反馈

- IAM 登录在 Argon2 校验前锁定账号/IP 与 IP HMAC 桶，失败才累加计数；未知账号继续 dummy hash，成功只重置当前账号/IP 桶。超过 8 次组合失败或 60 次同 IP 失败（默认 15 分钟窗口）后返回 429 和 Retry-After，冷却 15 分钟；不在节流表存邮箱或 IP 明文，过期行纳入维护清理。
- 新增 IAM Alembic `0020_login_attempt_throttles`、可配置阈值、生产 Caddy→Nginx 专用客户端 IP 头链路；开发环境不信任代理头。前端登录页把 Retry-After 显示为可读等待时间。同步 PRD、前后端/整体 README、架构、运维、接入清单、UI Review 与 Skill。
- 验证：9 个后端 Python 文件标准库语法编译通过；`vue-tsc -b` 和 Vite production build 通过（3205 modules，入口 382.31 KB / gzip 118.56 KB）。后端 SQLite/PostgreSQL 单测未能启动：本机 Python 无 FastAPI/SQLAlchemy，且 Docker Desktop 有进程但无 Docker CLI 可执行文件；未执行迁移、连接数据库或提交登录请求。Caddy/Nginx 配置仍待运行时镜像语法检查，真实 429 UI 待登录态浏览器验收。

## 2026-10-04 · AI Resume 管理端简历数据范围接入

- 已绑定 IAM 的 AI Resume 管理端简历列表/详情新增 `resume.read` + `include_data_scope=true` 检查；将 `tenant/self` 范围通过 OIDC 身份与会话映射成本地用户 UUID，再与既有 `admin_user_relation` 求交并在仓储查询中限制用户集合。组织范围缺少可信映射时 fail closed；没有数据库结构变化。
- 同步 AI Resume 后端守卫、管理路由、仓储和测试，更新 IAM PRD/接入计划/架构/待办/前后端说明及 Skill 状态，并校准 AI Resume PRD、README 与 Skill 引用/维护日志。
- 验证：8 个修改 JavaScript 文件 `node --check` 通过；`npm test` 23/23 通过。未运行数据库迁移、真实 IAM/PostgreSQL 或登录态浏览器验收；组织范围及简历以外资源仍待接入。

## 2026-10-04 · Knowledge Base 资源级 IAM 授权

- Knowledge Base 具体应用控制操作传入服务端应用 UUID 作为中央 IAM `resource_id`；IAM 角色页新增实例级授权查看、新增和撤销，撤销 API 精确删除目标资源，并在最后一条角色授权撤销后清理数据范围前置策略。
- 同步 Knowledge Base APP-06、API/前后端/整体指南，及 IAM PRD、架构、接入计划、用户清单、前后端指南、UI Review、Skill 和日志。
- 验证：Knowledge Base 授权定向测试 15/15、Ruff 通过；IAM 角色页 Vue 类型检查与 Vite production build 通过（3205 modules）。IAM 后端 AST 解析和 Ruff（忽略 B008）通过；unittest 因当前 Python 环境缺少 `pwdlib` 未能导入。未运行数据库迁移、完整后端套件或真实 IAM/浏览器交互；KB PostgreSQL revision 仍未知。

## 2026-10-04 · 知识库接入 IAM 在线权限检查

- 知识库 OIDC 回调现在要求 `offline_access`，校验 Access Token Introspection 的主体、租户、客户端、受众、issuer 和有效期，并把 access/refresh token 通过独立 AES-GCM vault 保存在服务端；权限请求临近过期时轮换 refresh token，中心不可用或响应异常时 fail closed。链接成员访问控制面接口时请求 `knowledge.read/write/admin`，已有本地成员角色和应用授权仍同时生效；修复无应用 grant 的普通成员误见全部应用的问题。
- IAM 新增 Alembic `0019_knowledge_core_permissions`，只登记三项 knowledge 权限，不自动授权。KB 新增 Alembic `0024_iam_oidc_token_vault` 和环境变量 `IAM_OIDC_TOKEN_ENCRYPTION_KEY`；本轮两边迁移均未运行。IAM 开发数据库最后确认 revision `0016_permission_status`，`0017`–`0019` 仍需用户明确授权；本轮尝试只读查询 Knowledge Base revision 时 PostgreSQL 连接被拒绝，因此其当前应用状态未知。
- 同步 IAM PRD、集成计划、待提供清单、整体/前后端 README 和 `iam-project` Skill；同步 Knowledge Base 执行书、API、整体/前后端 README。注明 IAM `data_scope` 尚未接入，并记录角色授权与 Secret Manager 的待办。
- 验证：知识库修改源码的 Ruff 静态检查通过（本轮修复 refresh discovery 错误映射后重跑）；没有运行测试、前端构建、数据库迁移、Docker 写入或真实 IAM/浏览器联调，也未读取任何 `.env` 内容。KB 迁移 `0024`、完整后端套件、目标角色 grant、真实 OIDC 会话与数据行隔离仍未验收。
- 后续文档复核确认接入计划应把 KB `0024` 标记为“本轮未执行、当前应用状态未知”，不能仅写成“未在数据库执行”；其余当前状态记录已明确 PostgreSQL 查询失败和 IAM `data_scope`/角色授予待办。本次未改代码、运行测试或访问数据库。

## 2026-10-03 · 为 AI Resume 中央权限守卫补回归覆盖

- 在 `resume-backend-node` 抽出依赖注入的 IAM 授权守卫逻辑并新增 6 项 Node 用例；另为 PDF 上传/识别/优化加 `resume.write/read` + `ai.generate` 门禁，已上传文件的元信息/预览检查 `resume.read`、删除检查 `resume.write`。验证绑定身份判权、未绑定账号保留本地 RBAC、AI 权限不携带本地资源 ID、中心拒绝不放行、错误信息脱敏和资源 ID 边界。
- 简历后端 `npm test` 14/14 通过；新增/修改 JS `node --check` 与 `git diff --check` 通过。跨端契约快照仍失败，因为 `resume-backend-node/database/migrations/20260927_full_workspace_upgrade.sql` 在当前工作区和该仓库 Git 历史均不存在；没有编造该业务迁移，没有运行数据库、业务 migration 或真实 IAM 联调。
- 同步 IAM README、前后端 README、PRD、集成计划、用户输入清单及 `iam-project` Skill；同步 AI Resume 工作区总览、PRD、前后端 README 和项目维护 Skill references。所有其他既有业务仓库改动均予保留。

## 2026-10-03 · 校正 AI Resume 实际工作区和 IAM 迁移状态

- 重新核实发现 AI Resume 实际位于 `D:\project\新建文件夹`，由 `resume-frontend`、`resume-backend-node`、`resume-browser-extension` 三个独立仓库构成；前后端存在大量未提交改动，均予保留。`aijj` 是 AI 基金产品，不再把简历仓库标为缺失。
- 当前简历 Node 后端工作树含 token vault、resume/AI/model 中央授权和可选用量 adapter；简历 SQL 未接入 IAM `data_scope`，真实 issuer、角色 grant 和业务库迁移仍未验收。只读数据库 revision `0016` 已包含 IAM migrations `0012`–`0015`；部署环境角色仍需显式授予，`0017`/`0018` 仍待授权。
- 同步整体 README、前后端 README、PRD、接入计划、用户输入清单及 `iam-project` Skill。没有修改三个业务仓库源码、没有运行测试/迁移或写数据库。

## 2026-10-03 · 将开发迁移和管理员引导改为显式 profile

- 开发 Compose 普通 API 启动显式关闭 Alembic 自动迁移和管理员 bootstrap；新增 one-shot `migrate`、`bootstrap-admin` profiles，首次管理员创建仍要求迁移完成并使用本地密钥环境变量。
- console 依赖 API `service_started`，让迁移尚未完成时仍可打开控制台并查看 readiness 诊断。生产迁移 job 保持独立发布流程。
- `docker compose --env-file .env.compose.example config --quiet` 解析通过；执行普通 `docker compose up -d api console` 后，console healthy/HTTP 200，API `/health` 200、`/ready` 503，数据库 revision 仍为 `0016_permission_status`。未启用 migration/bootstrap profile、未写数据库、未运行测试。同步根/前端/后端 README、PRD、架构、运维/启动指南、接入计划、用户输入清单和 `iam-project` Skill。

## 2026-10-03 · 公开认证表单增加字段级校验

- 登录与找回表单校验邮箱必填/格式/长度及密码必填；邀请密码必填但允许已有用户提交当前密码；密码重置校验 12–128 位并在确认字段提示不一致。
- 服务端 schema/认证策略仍是最终校验边界。同步根、前端、后端 README、PRD、架构、UI Review 和 `iam-project` Skill。`vue-tsc -b` 与 Vite production build 通过（3205 modules，入口 381.97 KB / gzip 118.41 KB）；本地 Vite 转换认证组件模块返回 200 并包含新规则，浏览器无障碍树确认就绪提示和必填标记共存。本轮未运行测试、未登录或提交表单、未写数据库或运行迁移；本机 API `/health` 为 200、`/ready` 为 503 `database_migration_pending`。

## 2026-10-03 · 集中整理用户待提供配置与决策

- 新增 `docs/部署与运维.md`，依据当前生产/开发 Compose、示例配置、PRD、接入计划和模型配额决策稿列出 P0 接入阻塞、P1 生产部署准备、P2 产品策略，并为每项给出推荐默认和缺少时的影响。
- 明确当前找不到 AI Resume 仓库、需单独批准本地开发库 `0017`/`0018`、知识库/DeerFlow 的账号与权限/数据映射、OIDC callback、生产域名与 Secret Manager、SMTP、备份 RPO/RTO、模型网关限额等输入；标明不得在聊天中提供凭证。同步根、前端、后端 README、PRD、架构、接入计划、运维手册和 `iam-project` Skill。本轮只读核验配置样例并编辑文档，未读取 `.env`、运行测试、执行迁移或写数据库。

## 2026-10-03 · 登录入口支持立即重查服务状态

- 就绪异常提示增加“重新检查”按钮，用户可在服务恢复或迁移处理后立即确认状态；按钮展示探针加载状态。手动操作与每 30 秒的后台轮询共用单个在途请求，避免重复请求。
- 校正文档验收边界：当前浏览器只确认 accessibility tree 中控件和提示共存，本轮未取得桌面/390px 视觉截图；同步根、前端、后端 README、PRD、架构、UI Review 和 `iam-project` Skill。`vue-tsc -b` 与 Vite production build 通过（3205 modules，入口 380.97 KB / gzip 118.19 KB）；浏览器无障碍树确认重查按钮与登录控件共存。未运行测试、未执行数据库迁移或写入。

## 2026-10-03 · 在公开认证入口展示就绪故障

- 登录页此前不接收服务状态，迁移缺口只能登录后从侧栏发现。`AuthEntry.vue` 现消费 App 共享 readiness 状态，在未就绪时显示固定高对比说明，状态恢复后自动隐藏；密码、OIDC、邀请和密码恢复表单保持可见，提示不泄露数据库 revision 或异常详情。
- 同步根、前端、后端 README、PRD、架构、UI Review、`iam-project` Skill。Vue 类型检查与 Vite production build 通过（3205 modules，入口 380.55 KB / gzip 118.04 KB）；本地浏览器 accessibility tree 确认提示与登录输入/操作同时存在，没有提交认证信息；不运行测试或数据库迁移。

## 2026-10-03 · 管理台准确展示 API 就绪状态

- 侧栏状态原先只请求 `/api/v1/health`，迁移未应用时会把活着但不能接业务请求的 API 显示为“服务正常”。改为 no-cache 请求 `/api/v1/ready`，把 migration pending、DB unavailable、migration state unavailable 和网络失败转换为稳定中文状态；探针设 5 秒超时且不阻塞会话恢复，每 30 秒刷新，卸载时清理轮询，并通过 `role=status`/`aria-live` 通知状态变化。
- 移除侧栏固定的“开发环境”文字，以免生产复用控制台时显示错误环境；后端探针和 API 契约未改变。
- 文档同步：根、前端、后端 README，PRD，架构，UI Review 和 `iam-project` Skill。最终 `vue-tsc -b` 与 Vite production build 通过（3205 modules，入口 379.73 KB / gzip 117.78 KB）；本机 pnpm shim 启动失败，直接调用已安装的 Vue/Vite 二进制完成验证。未运行测试、数据库迁移或写入；管理员登录态 UI 未验收。

## 2026-10-03 · 复核业务接入仓库与中央授权断点

- 检查当前 `D:\project` 后确认没有计划引用的 `ai-resume` 目录；`aijj` 是 AI 基金决策助手。`aiknowledge` 已有 OIDC 登录/本地成员显式绑定源码，但当前后端无 IAM `/authorization/check` 或 `data_scope` 调用；`deer-flow` 有通用 OIDC Gateway principal 与可配置首次登录自动开户/管理员邮箱提权规则。
- 知识库和 DeerFlow 工作树有大量既有未提交修改，本轮仅只读检查，未更改两边源码。接入计划补充正确的仓库路径、业务权限映射、tenant/application 映射及 provisioning 决策待提供项；简历项目此前的接入代码状态仅可视为历史审计，不能当作本次当前验证。
- 同步根、前端、后端 README、PRD、架构、接入计划和 `iam-project` Skill。验证依据为目录与 Git 状态、`rg` 源码检索及相关 OIDC 处理器读取；未运行测试、数据库迁移或外部项目服务。

## 2026-10-03 · 记录迁移差异对 Compose 启动的影响

- 复查 Docker 状态发现 API 容器因 `/ready` 的 `database_migration_pending` 连续 38 次 healthcheck 失败后处于 `unhealthy`；console 和 PostgreSQL 仍健康。Compose 将 console 启动依赖设为 `api: service_healthy`，因此新启动 console 会等待迁移完成，当前已运行实例仍可显示页面。
- 明确 API entrypoint 在启动时会自动应用 Alembic。`0017`、`0018` 尚待审查/授权期间，重启 API 或执行 `docker compose up` 可能写入数据库。同步更新启动指南、运维手册、PRD、前后端说明、根 README 和 `iam-project` Skill；没有重启容器、运行迁移、写数据库或执行测试。
- 验证依据：真实 Docker CLI 的 `compose ps` / `inspect` 和 healthcheck 日志；源码当前 head 为 `0018`，本地 DB 为 `0016`。这是开发机状态，不代表生产环境。

## 2026-10-03 · 修复 Alembic 迁移链并刷新运行状态

- 修复 `0018_tenant_application_admin_permissions.down_revision`：此前误写成 `0017` 文件名（`0017_tenant_organization_admin_permissions`），而真实 revision ID 是 `0017_tenant_org_admin_permissions`，导致 Alembic 无法解析迁移图。
- Docker Desktop CLI 只读核验 console、PostgreSQL 健康；API `/health` 返回 200，新的 `/ready` 检查返回 503 `database_migration_pending`。容器内 `alembic heads/current/history` 均成功，源码 head 为 `0018`、本地数据库为 `0016`。`alembic check` 因数据库未到 head 返回 `Target database is not up to date`，因此没有形成 schema drift 结论。`0017`、`0018` 未迁移。本轮未写数据库、未运行测试，也未验证生产部署。
- 更新 API 就绪探针：连接 PostgreSQL 后只读比较 `alembic_version` 与当前源码的全部 Alembic heads；缺迁移或 revision 不符均 fail closed，运行进程存活仍由 `/health` 单独报告。Python 3.12 AST 解析通过，实际 HTTP 结果为 `/health` 200、`/ready` 503；未执行 schema 写入。
- 重新同步 PRD、前后端指南、整体 README、架构、接入计划、运维手册、UI Review 与 `iam-project` Skill；早前 `0010` 数据库版本记载保留为历史快照。

## 2026-10-03 · 收窄应用角色权限目录的历史授权范围

- 应用权限目录读取现在必须提供当前应用内的 `role_id`；旧 `iam.*` 权限仅对该角色自己的历史授权返回，避免应用管理员从同应用其他角色目录中看到无关系统授权编码。前端编辑器同步按选中的角色请求目录，服务端继续拒绝为其新增 `iam.*`。
- 同步 PRD、前后端说明、整体架构、UI Review 与项目 Skill；没有改变数据库 schema 或迁移。
- 验证：`vue-tsc --noEmit -p tsconfig.json` 通过，Vite production build 转换 3205 modules（入口 378.96 KB / gzip 117.51 KB，应用角色 chunk 15.40 KB / gzip 5.68 KB），62 个后端应用文件 AST 解析通过。本机 API readiness 为 `ok`，OpenAPI 确认 `role_id` 为必填参数、匿名 role-list 为 401；Vite 入口与 feature SFC 均返回 200。宿主无 FastAPI/SQLAlchemy，未跑后端测试；未执行迁移和登录态授权写入。自动审查要求明确授权后才能新增/运行后端测试，目前仍待用户确认。

## 2026-10-03 · 单应用角色与成员权限委派

- 新增 `/api/v1/tenant-admin/applications/{application_id}/roles*`、应用权限目录/预览/替换、已授权成员查询及直接角色绑定/移除 API；新增 Vue `application-roles` 独立 feature。角色严格限定 tenant_id/application_id；应用管理员只能分配业务权限，服务端拒绝新加 `iam.*`，成员只包括已有应用角色的活动租户成员。用户组继承仅显示，租户成员邀请与用户组管理仍由租户管理员处理。没有新增数据库模型或迁移。
- 前端完成角色 CRUD/启停、先预览后保存业务权限、应用成员分页搜索、直接绑定/移除及继承来源显示；绑定只接受已存在活动租户成员，避免为应用管理员开放完整租户成员目录。
- 同步根/前端/后端 README、PRD、架构、接入计划、UI Review 和 `iam-project` Skill。项目总览与独立 feature 目录仍保持 frontend/、backend/ 分开。
- 验证：`vue-tsc --noEmit -p tsconfig.json` 与 Vite production build 通过（3205 modules，入口 378.96 KB / gzip 117.49 KB，应用角色 chunk 15.36 KB / gzip 5.66 KB）；Python AST 解析 62 个 `backend/app` 文件通过。本机 API 容器 readiness 为 `ok`，OpenAPI 88 paths 含新增路由，匿名 role-list 为 401；Vite 入口、App.vue、新增 SFC 均为 200。宿主缺 FastAPI/SQLAlchemy，未执行回归测试和数据库写入；未执行 migration，最后确认数据库 revision 为 `0010_tenant_user_groups`。自动审查拒绝新增后端测试，认为当前用户指令未显式授权添加或运行测试；未修改测试文件，等待明确授权。

## 2026-10-03 · 管理台登录文案与响应式走查

- 将控制台登录副标题改为“使用管理员账号登录控制台”，避免租户/应用管理员误以为只能使用平台管理员身份；邮箱示例改为通用地址。
- 本地浏览器查看桌面登录页、桌面找回页和 390px 手机找回页，确认卡片、表单和按钮未横向溢出；未提交任何认证或邮件请求。登录后管理页仍待有效管理员会话走查。
- 验证：`vue-tsc --noEmit -p tsconfig.json` 通过；Vite production build 转换 3202 个模块，入口 378.27 KB / gzip 117.37 KB；构建产物位于系统临时目录。
- 同步 PRD、前端/后端说明、根 README、UI 走查记录与项目 Skill。

## 2026-10-03 · OAuth 应用委派支持单应用范围

- 将 `iam.application.read/manage/secret.rotate` 复用于 tenant-wide 和 application-bound 角色。服务端读取时按租户、角色 application_id 和权限 grant 资源过滤；资料编辑、启停和轮换会在目标应用上下文再次执行共享 evaluator。停用应用仍可由获授权管理角色查看和重新启用。
- 应用列表在一条批量授权查询中合并直接角色和活动用户组角色，避免为每个应用执行多次授权往返；响应向前端提供每行 manage/rotate 能力。新建客户端没有应用 ID，只允许租户范围 manage。应用 rotate 权限不会开放应用目录读取。
- 租户应用目录按实际可读应用展示；只有应用范围权限的管理员不因页面授权获得全租户目录或成员目录。更新 PRD、架构、前后端指南、整体 README、接入计划、UI Review、Skill 和日志。
- 验证：`vue-tsc --noEmit` 通过；Vite production build 转换 3202 个模块，入口 378.27 KB / gzip 117.38 KB，应用管理 feature 13.02 KB / gzip 5.19 KB，最大 chunk 低于 500 KB；Python AST 解析 100 个文件通过。宿主缺少 FastAPI/Pydantic，未运行后端套件；数据库迁移和租户登录态浏览器验收未进行。

## 2026-10-03 · 租户 OAuth 应用委派管理

- 新增 Alembic `0018_tenant_application_admin_permissions`，登记应用目录读取、应用管理和密钥轮换三种租户权限；不自动授予角色，未执行迁移。
- `/tenant-admin/applications*` 复用既有应用处理器，并逐请求检查目标租户权限；应用列表必须带 tenant_id 且仅返回该租户，创建仅允许活动租户。`manage` 可读取/创建/编辑/启停；密钥轮换要求独立 `secret.rotate`；应用受信状态仍只有平台管理员可改。应用委派目前覆盖租户全目录，不支持单应用资源授权。
- 复用应用管理 Vue feature 支持按租户加载和能力过滤操作；租户入口根据组织/应用权限动态显示，并将应用只读、管理和密钥轮换分开判断。应用权限用户只能通过成员归属接口发现自己的租户，不因此获得成员目录读取权。
- 同步 PRD、前后端指南、整体 README、架构、UI 走查、运维说明和项目 Skill。验证：前端 `vue-tsc --noEmit` 通过，Vite production build 转换 3202 个模块，入口 378.13 KB / gzip 117.34 KB，最大 chunk 低于 500 KB；Python AST 解析 100 个文件通过。当前宿主缺少 FastAPI/Pydantic，未运行后端套件；未执行数据库迁移或登录态浏览器验收。

## 2026-10-03 · OAuth 应用回调约束与启停并发保护

- 将应用创建/资料/状态请求契约从认证 schema 拆至 `schemas/applications.py`；创建请求强制登记 1–20 个登录回调，URL 规则仍由后端路由验证。
- 应用启停 API 改用 JSON `expected_status`/`status` 请求体，在应用行锁下拒绝旧页面覆盖，并把会话撤销与 from/to 审计写入同一事务；管理台同步传递加载到的期望状态。
- 增加契约回归覆盖回调数量边界、状态字段校验、PostgreSQL `FOR UPDATE` SQL 和陈旧状态 409；同步 PRD、前后端说明、整体 README、架构、项目 Skill 和 UI 走查。
- 验证：Python AST 解析覆盖 backend/app 与 backend/tests 共 80 个文件；`vue-tsc --noEmit` 与 Vite production build 通过（3202 modules，入口 377.11 KB / gzip 117.14 KB，最大 chunk 低于 500 KB）。当前宿主缺少 Pydantic/FastAPI，新增后端回归用例无法执行；未安装依赖、未启动容器、未访问数据库。

## 2026-10-03 · 租户委派管理首批 API

- 新增 `/api/v1/tenant-admin/*` 组织、成员/角色清单、成员组织归属和角色数据范围 API；通过 `admin_authorization.py` 对目标租户逐请求检查 `iam.organization.read/manage`。成员查询可分页/搜索且限制 `tenant_id`，角色权限清单只返回该角色现有授权。平台管理员可跨租户；只读权限不能写，越权组织/角色按 404 隐藏。
- Vue 控制台根据受保护 `/admin/overview` 响应进入平台或租户模式。租户模式显示组织管理和成员/数据范围页，支持成员筛选、组织归属和角色范围编辑；只读角色无写入口，管理权限可改动，未获授权用户看到空状态。
- 修复租户模式启动只检查 `iam.organization.manage` 的问题：现在分别查询 read/manage，任一权限允许即可进入，并只对 manage 授权展示保存操作；避免只读管理员被误判为无权访问。
- 新增 Alembic `0017_tenant_org_admin_permissions` 登记两项稳定权限码，不自动给租户角色授权；迁移未执行。平台管理 API 仍由现有 platform-admin router 保护。应用管理员和其它委派域仍未实现。
- 同步 PRD、前端/后端指南、整体 README、架构说明、运维手册、UI 走查和项目 Skill。修正成员列表对非平台管理员的用户存在性探测，确保角色数据范围写入先授权再锁行，并抽出策略序列化函数以避免写路由错误调用带 FastAPI 依赖参数的 GET handler。
- 验证：Python 3.14 标准库 AST 语法解析覆盖后端改动；`vue-tsc --noEmit` 通过，Vite production build 转换 3202 modules（入口 377.11 KB / gzip 117.14 KB，管理注册 chunk 285.65 KB / gzip 83.80 KB）。后端依赖/数据库集成套件及 PostgreSQL 迁移未运行。最近一次确认的本地数据库 revision 为 `0010_tenant_user_groups`，本轮未重查数据库。

## 2026-10-02 · 协调管理会话续期并同步跨标签页退出

- 前端 `api.ts` 将同一页面内并行 401 请求合并为共享续期操作；支持 Web Locks 的浏览器使用同源锁串行化多个标签页的 refresh，避免多个请求同时消费一次性刷新 Cookie。`BroadcastChannel` 通知同源页面退出/认证失效并清除各自的 `sessionStorage` token，不广播凭证。
- 服务端登出仍只撤销当前 access JWT 和共享刷新会话；被复制的其他离线 JWT 在到期前仍可用。浏览器侧同步只能降低误留登录界面的风险，不能取代服务端会话级 JWT 撤销。
- 收到远端登出广播的页面只移除本地 token 并清理 Vue 会话状态，不回发登出消息，避免标签页间广播回声。
- 文档同步 PRD、前后端指南、整体 README、架构说明、UI 走查与项目 Skill。无 API、数据库、Cookie 或 migration 变更；未接触数据库或凭据。
- 验证：宿主机 `vue-tsc --noEmit -p frontend/tsconfig.json` 通过；Vite production build 转换 3199 modules，主入口 374.22 KB / gzip 116.38 KB，管理组件注册 chunk 285.63 KB / gzip 83.79 KB，所有 chunk 小于 500 KB。构建输出写入系统临时目录；尚未进行带管理员登录态的多标签页并发验收。

## 2026-09-30 · 固定前后端生产依赖安装

- `frontend/package.json` 固定 `pnpm@12.6.0`；生产 Dockerfile 复制 `pnpm-lock.yaml` 并改用 `pnpm install --frozen-lockfile`。后端新增与当前 Python 3.12 Linux API runtime 精确匹配的 `requirements.lock`，Dockerfile 安装后执行 `pip check`。
- 验证：容器内 pnpm frozen lockfile 离线检查、`vue-tsc --noEmit`、Python `pip check` 与 requirements 直接依赖的离线 dry-run 通过，requirements lock 与 `pip freeze` 完全一致；Vite 临时目录 production build 转换 3199 modules，主入口 373.66 KB / gzip 116.20 KB，管理注册 chunk 285.63 KB / gzip 83.79 KB。最新 Dockerfile 未执行完整镜像构建；本地没有缓存 `node:22-alpine` 基础镜像，生产镜像与运行状态仍未验收。
- 同步前端/后端/整体 README、PRD、架构、运维、Skill 与变更日志。

## 2026-09-30 · 当前交付状态复核与 PRD 状态修正

- 只读复核开发环境：API、console、PostgreSQL 均 healthy；API readiness 和控制台首页 HTTP 200。Alembic 当前 revision 为 `0010_tenant_user_groups`，源码 head 为 `0016_permission_status`；未执行 migration。
- 使用非密钥临时占位项对 `compose.production.yaml` 执行 `config --quiet` 通过；不提供必填 `IAM_RELEASE_TAG` 时解析失败。没有读取生产密钥文件、构建镜像、启动生产服务或迁移。
- 配置清单核对发现首次 bootstrap 需要至少 16 字符的 `IAM_BOOTSTRAP_ADMIN_PASSWORD`；该变量在 Compose 中为可选插值，但 `manage.py` 会在缺失时拒绝创建管理员，现已在运维/总览/PRD 标明一次性注入并在成功后移除。
- PRD 更正：邮箱密码重置有 API/UI 源码，但注册邮箱验证与短信仍未实现，且 `0011`、SMTP 和完整重置流程未验收；避免将部分实现误记为完全未实现。
- UI 文案：浏览器访问性树发现登录页只提到后端引导创建账号，遗漏管理员邀请；现已明确说明公开注册默认关闭及新成员邀请入口。没有登录或提交任何凭据。
- 验证：`vue-tsc --noEmit -p tsconfig.json` 通过，运行中的 Vite 模块返回更新后的文案；没有管理员态视觉验收。
- 同步根 README、前后端 README 与 PRD。完整 PostgreSQL 测试、管理员态操作、生产部署及外部业务数据过滤仍未验收。

## 2026-09-30 · OIDC 登出访问日志脱敏

- 后端新增 Uvicorn access log 过滤器，保留请求路径与状态信息，整段隐藏 query string；OIDC `id_token_hint` 不会进入 API access log。
- 生产 Nginx 使用仅记录 `$uri` 的 `iam_redacted` 格式，不记录原始 request、query、args 或 Referer；精确登出路由将 Nginx 错误日志阈值设为 `emerg`，避免低级别代理诊断输出原始 request line。
- 验证：访问日志脱敏单测 4/4 通过；本地 Nginx 1.27 镜像对生产配置执行 `nginx -t` 成功。没有重建/启动生产服务或发送真实令牌。外部 CDN、负载均衡器、Caddy 自定义访问日志及业务 RP 日志仍需各自配置脱敏。
- 同步：PRD、前后端 README、整体 README、架构、接入计划、运维手册与 IAM Skill。

## 2026-09-30 · 模型启停增加并发冲突保护

- 后端：模型状态 PATCH 改为 JSON `expected_status` + `status`；通过 `SELECT ... FOR UPDATE` 对比旧状态，陈旧页面得到 409，不产生误更新/审计；成功状态变更和审计同事务。
- 前端：启停时提交当前行状态；统一 API 错误保留 HTTP 状态码，409 时提示冲突并重新加载目录。
- 验证：`vue-tsc --noEmit` 和 4 项契约/状态单测通过（含 PostgreSQL `FOR UPDATE` SQL 断言）；Vite 模型页/共享 API 模块 HTTP 200，实时 OpenAPI 发布必需的 `expected_status` + `status` 请求体。PostgreSQL 集成用例因当前库缺少 migration `0011_password_reset_sessions` 引入的 `users.auth_version` 列失败；`alembic current` 确认数据库为 `0010_tenant_user_groups`、代码 head 为 `0016_permission_status`，未执行 migration。
- 运行状态：开发 API/控制台/PostgreSQL 容器 healthy，API readiness `ok`、控制台根页 200；这不代表数据库 schema 与当前 ORM 对齐。生产部署仍未验收。
- 文档：同步 PRD、前后端 README、整体 README、架构、运维、UI 走查、IAM Skill。

## 2026-09-30 · 复核开发 Compose 并校正 OIDC 密钥运维说明

- 运行证据：Docker Compose 当前列出 API、Vue 控制台和 PostgreSQL 三个 healthy 容器；API readiness 为 `ok`，控制台首页 HTTP 200。
- 数据库 revision 的只读查询未能完成；没有运行 migration、完整测试套件或生产部署，文档不把 Compose healthy 当作数据库/端到端验收。
- 运维更正：源码和轮换 Compose overlay 支持 active/previous 双公钥重叠与 `kid` 验签；灾备段落此前误称仅支持单把公钥，现已修正，并保留生产密钥轮换尚未演练的状态。
- 同步：更新 PRD、前后端 README、整体 README、运维手册、UI 走查与架构 Skill。

## 2026-09-30 · 扩展每应用登录主题外观配置

- 产品：补全每应用登录主题的背景裁切/遮罩、卡片外观、字体、Logo 和控件尺寸/圆角配置；管理预览和 OIDC 登录展示消费同一组受控值。
- 前端：增加主题值归一化工具，桌面/手机预览覆盖新增样式；修复可选 Logo/背景图清空后保存失败的问题。
- 后端：将配置规则集中到 `app/services/theme_config.py`，校验白名单、预设、颜色、边界和资源地址；拒绝动态 CSS/HTML 和不安全 URL。无 schema/migration 变更。
- 验证：Vue/TypeScript + Vite production build 通过；5 项独立主题校验测试及 Python AST 检查通过。未用管理员会话做编辑器浏览器验收。
- 文档：更新 PRD、前后端 README、整体 README、UI 走查、架构说明和 IAM Skill。

## 2026-09-30 · 增加稳定权限编码的安全停用与恢复

- 需求：权限目录只能新增/查看，缺少不删除历史授权而立即阻断某权限编码的治理手段。
- 代码：新增 `Permission.status` 与 Alembic `0016_permission_status`（历史目录项默认 active）；在线授权查询排除 disabled 编码。管理员 API 支持带 `expected_status` 的状态更新、显示引用角色数，并与审计事务原子提交。单项授权和批量角色授权均拒绝新增停用权限；批量编辑可以保留或撤销历史停用授权。管理台增加影响提示与停用/恢复确认。
- 安全语义：停用保留角色授予和数据范围，恢复会重新使未撤销的历史授予生效；页面在恢复前明确提示。编码仍不支持编辑或物理删除。
- 文档：同步 PRD、前后端 README、整体 README、架构、运维和 IAM Skill。
- 验证：Vue/TypeScript 检查及 Vite build 通过（3198 modules；权限页面 chunk 6.78 KB / gzip 3.13 KB）；7 个受影响 Python 文件 AST 解析通过。新增 3 个隔离 SQLite 回归用例，但宿主 Python 缺 FastAPI，测试未能导入运行。未连接 PostgreSQL、执行 `0016` migration 或部署。

## 2026-09-30 · 为租户邀请增加可选 SMTP 投递

- 需求：补全 IAM 邀请注册的交付路径，同时保留默认邀请制与管理员手动交付的安全回退。
- 代码：新增默认关闭的 `IAM_INVITATION_EMAIL_ENABLED` Compose 配置；邀请邮件复用密码重置 SMTP/TLS 发送实现。邀请事务提交后投递，响应区分 `email_sent`、`email_failed`、`manual_copy`；含明文 bearer 链接的响应维持 `no-store`。失败不撤销已创建邀请，仍向管理员返回一次性备用链接；日志不包含邮箱、Token、邮件正文或 SMTP 错误文本。前端按投递结果展示成功/失败提示，备用链接关闭后清空。
- 边界：SMTP 配置和开关默认关闭，不开放公共注册；邮件由 SMTP 接受不保证进入收件箱，真实投递、管理员登录态浏览器验收未完成。失败链接只能在创建响应时查看，管理员需当场安全保存。
- 知识：同步整体 README、PRD、运维与接入计划、后端/前端 README、IAM Skill、Compose 环境样例。
- 验证：3 个受影响 Python 文件 AST 解析通过；两份 Compose YAML 解析通过；`pnpm --dir frontend build` 通过（3198 modules，初始 chunk 371.37 KB / gzip 115.30 KB）；本地 Vite 组件模块返回 200 且包含 `email_sent`/`email_failed` 状态分支；运行中 IAM API `GET /api/v1/ready` 返回 `{"status":"ok","service":"iam-api"}`。未发送真实邮件、连接数据库、执行迁移或应用测试。

## 2026-09-30 · 接通 AI Resume 可选 IAM 模型用量

- 需求：把 IAM 已有的模型 RPM/TPM 预留和用量账本接入已受 `model.invoke` 保护的 AI Resume Provider 调用，记录失败或缺少供应商 Token 用量的估算值。
- 代码：服务端配置 `IAM_MODEL_USAGE_API_KEY` 后，文本、流式、视觉和视觉流式路径在调用前申请预留，并在调用后报告/结算；身份取自已验签的 IAM tenant/subject/application 和服务端模型映射，不向 IAM 发送提示词、响应正文或供应商凭证。新增 IAM `usage_is_estimated` 字段与 Alembic `0015_model_usage_estimation`；管理台用量页区分实测/估算。
- 边界：用量集成是可选项，启用后 IAM 用量端点不可用会 fail closed；共享密钥必须在 AI Resume `IAM_MODEL_USAGE_API_KEY` 与 IAM `MODEL_USAGE_API_KEY` 保持一致，先应用 migration `0015`。限额执行开关默认关闭，预留额度只有显式启用后才拦截；IAM ledger 不替代 AI Resume 本地钱包。数据库迁移与真实网关联调未执行。
- 知识：同步整体 README、PRD、架构、接入计划、IAM 后端/前端 README 和 Skill；同步 AI Resume README、PRD、前后端 README 与维护 Skill。
- 验证：AI Resume 5 个改动后端 JS 文件 `node --check` 通过；IAM 6 个受影响 Python 文件 AST 解析通过，migration `0015_model_usage_estimation` 正确下接 `0014_model_invoke_permission`；AI 后端 Git diff check 通过。AI 前端 diff check 仍仅因既有 README 面试题库段落第 255–260 行尾随空白失败；项目契约快照唯一失败仍是既有 `20260927_full_workspace_upgrade.sql` 缺失。未运行应用测试、连接数据库、执行迁移或部署。

## 2026-09-30 · AI 简历 Provider 调用增加模型实例权限

- 需求：在应用级 `ai.generate` 之外，按最终运行模型执行 `model.invoke`，覆盖文本、流式、视觉和视觉流式 Provider 请求。
- 代码：新增 Alembic `0014_model_invoke_permission` 登记默认权限码但不授予角色；AI 简历后端从加密 IAM 会话取得可信 tenant，并在 Provider 请求前检查实际模型目录实例。`IAM_MODEL_ID_MAP_JSON` 支持 tenant UUID → model_key → IAM model UUID 的多租户映射，并保留单租户扁平映射。修正 IAM 中间件遗漏 `settings` 导入及异常路径引用未定义变量的问题；中心身份表旧库兼容仅由授权服务处理，其他绑定/授权故障维持 fail closed。
- 文档：同步 IAM 总览、前后端 README、PRD、业务接入计划、项目 Skill；同步 AI 简历 README、PRD、`.env.example`、维护 Skill 的状态/后端/契约和变更日志。明确迁移未应用、角色未授予，配额预留/结算未接入，业务数据范围未落地。
- 验证：AI Resume 后端四个受影响 JS 文件 `node --check` 通过；IAM `0014` 迁移 Python AST 通过，revision 长度 28 且链到 `0013_ai_permission_catalog`。跨项目契约快照唯一失败仍为既有迁移 `20260927_full_workspace_upgrade.sql` 缺失；本机 Git 根检测不可用，未能运行 diff 检查。未连接数据库、执行迁移或应用测试。

## 2026-09-30 · 将 AI 简历 AI 路由纳入中心权限判定

- 需求：继续扩大已绑定 IAM 用户在 AI 简历中的服务端权限覆盖，同时保留本地账号归属与计费规则。
- 代码：新增 Alembic `0013_ai_permission_catalog`，幂等登记 `ai.generate` 且不自动授予任何角色；AI 简历配置可覆盖默认编码，`/api/ai/*` 路由在登录与邮箱验证后统一检查该应用级权限。AI 请求不将本地简历或模型 ID 当作 IAM 资源 ID。
- 文档：同步 IAM 根/前后端 README、PRD、业务接入计划和项目 Skill；同步 AI 简历根/前后端 README、PRD、维护 Skill 的状态/架构/backend/contracts 与日志。明确 `ai.generate` 不替代 `model.invoke`、IAM 配额或本地钱包计费。
- 边界：中心权限仅作用于显式绑定 IAM 的用户；未绑定用户维持本地授权路径，绑定记录仍在但 IAM 配置被移除时 fail closed。模型使用授权、租户 data_scope、上传/钱包/岗位/管理资源覆盖仍待后续实现；迁移尚未执行，管理员需在部署后授予目标角色。
- 验证：修改的 3 个后端 JS 文件 `node --check` 通过，IAM migration Python AST 解析通过，后端 `git diff --check` 未报空白错误。AI 简历前端 `git diff --check` 仍因既有面试题库 README 段落的尾随空白返回失败（本轮未改该段）。项目契约快照仍仅因缺少既有迁移 `20260927_full_workspace_upgrade.sql` 失败；未连接数据库或执行迁移。

## 2026-09-30 · 支持 OIDC 签名密钥双公钥重叠轮换

- 需求：避免直接替换 RS256 签名私钥后，仍缓存旧 JWKS 的客户端无法验证新 Token；同时保留旧 Token 的验证能力。
- 代码：新增可选备用签名密钥配置；活动密钥独占新 Token 签名，JWKS 在重叠期发布活动/备用两把公钥，验证按 kid 精确选择且未知 kid 默认拒绝。容器启动现在会校验已配置的两把 key；新增生产 Compose 轮换覆盖文件，默认部署不挂载第二把私钥。
- 文档：更新 IAM 整体/前后端 README、PRD、项目 Skill 与运维手册，说明“预发布新公钥→切换签名→等待 Token/cache 到期→移除旧 key”的操作步骤和多副本切换约束。
- 验证：新增 4 项密钥轮换单元测试源码；现有 Python 运行时缺 PyJWT、pytest 与 pydantic-settings，未能运行测试；修改的 4 个 Python 文件 AST 解析及两份 Compose YAML 的 PyYAML 解析通过。主机无 Docker CLI，未验证 Compose 合并或启动；迁移不涉及数据库，未加载生产密钥或演练真实 RP/JWKS 缓存。

## 2026-09-30 · 为 AI 简历接入补齐默认权限目录

- 需求：避免 AI 简历服务使用的稳定权限码只靠管理员手工创建，降低拼写错误造成的授权拒绝。
- 代码：新增 Alembic `0012_resume_permission_catalog`，将 `resume.read`、`resume.write`、`resume.export` 登记到全局权限目录；已存在的编码保持原记录，迁移不授予任何租户角色，降级时也不删除可能已被引用的目录项。
- 知识：同步整体 README、前后端 README、PRD、业务接入计划、IAM 项目 Skill 与 AI 简历工作区维护日志；明确迁移尚未应用、租户角色仍需管理员显式授予，且简历数据范围尚未接入。
- 验证：迁移 Python AST 解析通过；未连接或修改数据库，未运行 Alembic 升级，也未验证真实 IAM 授权和浏览器联调。

## 2026-09-30 · 为 AI 简历首批路由接入 IAM 在线权限

- AI 简历后端对已显式绑定中心身份的简历读取、创建/更新/删除、历史、数量与导出请求在线调用 `/api/v1/authorization/check`；默认权限码为 `resume.read`、`resume.write`、`resume.export`，可由部署配置覆盖。中心拒绝或不可用时不回退本地放行，未绑定用户仍保留业务本地授权。
- 简历表目前没有 tenant/organization 列，因此明确不请求 IAM `data_scope`；真实行过滤继续使用 AI 简历本地 `user_id`，不代表中心租户范围已经执行。其余 AI、钱包、上传、岗位、管理接口、知识库和 DeerFlow 仍待接入。
- 同步 IAM 与 AI 简历的 PRD、README、接入计划和项目 Skill。AI 简历 4 个改动 JavaScript 文件语法检查、后端差异检查通过；项目契约快照仍因缺少既有库迁移 `20260927_full_workspace_upgrade.sql` 失败，前端 README 的既有面试题库段落仍有尾随空白。未连接数据库、调用真实 IAM 或部署。

## 2026-09-30 · 增加邮箱密码重置与会话失效链路

- 后端加入邮箱找回申请/完成接口、一次性 token 摘要与按邮箱 HMAC 节流；SMTP 配置可选，非开发环境要求 TLS/SSL 和匹配的发件人配置。完成重置会更新认证版本、撤销 IAM/OIDC 刷新凭证及待处理授权，并保留对本地业务 session / 离线 JWT 过期窗口的边界说明。
- 新增 Alembic `0011_password_reset_sessions`，扩展身份/会话表，并更新登录页找回流程与每应用 `show_forgot_password` 开关。SMTP 参数进入 Compose/env 示例，邮件密码仅注入 API。
- 只读浏览器可访问性树确认登录找回入口、重置表单和地址栏 fragment 清理；修正用户提示和文档中的令牌有效期边界（开发 Compose 默认 30 分钟、生产默认 10 分钟）。
- 登录主题编辑器明确标注注册入口目前仅供预览，补充开放注册尚缺租户归属、默认应用角色和邮箱验证决策；未把全局注册开关默认打开。
- 临时副本中 `vue-tsc -b` 与 Vite production build 通过（3198 modules，入口 371.37 KB / gzip 115.31 KB）；Python AST 解析 70 个文件通过，运行 API OpenAPI 公布两条密码重置路由。未运行 migration、后端集成测试、真实邮件或完整浏览器重置流程；最近已确认数据库仍为 `0010_tenant_user_groups`，SMTP 需要部署者通过 Secret Manager 配置。
- 同步前后端 README、根 README、PRD、架构、运维、业务接入计划、UI 走查与项目 Skill。本机 `docker` 命令入口当前不返回版本/Compose 输出，因此未能复验 SMTP 更新后的 Compose 静态配置，也无法访问数据库确认迁移头。

## 2026-09-30 · 补齐生产控制台 CSP 与静态资源安全头

- Nginx 静态控制台增加 Content Security Policy：限制脚本/API 到同源，禁止对象嵌入，限制 base/form/frame，保留受控主题使用的 HTTPS 图片和 Ant Design Vue 内联样式。
- 修复 Nginx 1.27 的 `add_header` 继承陷阱：`/assets/*` 和 `/index.html` 含缓存头时会替换 server 级响应头，现显式补齐 CSP、MIME、防嵌入、Referrer、Permissions 头。前端、后端、根 README、PRD、运维手册和项目 Skill 已同步。
- 只读检查确认开发站点登录页面可正常加载；本机没有可用生产 Nginx 容器，本次没有运行 `nginx -t` 或检查实际 HTTP 响应头。生产镜像构建和登录主题/OIDC浏览器回归仍待验证。

## 2026-09-30 · 本地 IAM 运行环境与后端验收状态复核

- 对本地 API `8011` 做只读 smoke check：health/ready 正常，Discovery issuer 为 `http://localhost:8011`，JWKS 返回 1 把 RS256 公钥；概览、租户、应用、用户、用户组、组织、模型、审计 8 个匿名管理列表均返回 401。OpenAPI 公布 62 条路径，确认登录、组织/数据范围、OIDC 与模型配额预留/结算接口存在。开发/生产 Compose `config --quiet` 均通过，`py -m compileall -q backend/app backend/tests` 通过。
- 复核发现 Windows Docker CLI 当前没有容器/镜像，宿主 Python 缺 FastAPI、SQLAlchemy、PyJWT、Alembic、psycopg、pwdlib 且 pip 缓存为空；仅安装的 WSL 发行版是 Docker Desktop 专用环境。虽然 8011 端口由 Docker Desktop/WSL relay 转发，但无法映射到当前 Compose 项目，因此未把 smoke check 当成完整容器/数据库验收。
- 将根、前后端 README、PRD、运维手册与 IAM Skill 中的 61 项 unittest 和 PostgreSQL `0010_tenant_user_groups` 标为 2026-09-29 最近一次完整记录；本轮未重跑后端 unittest、未重验 migration head、未运行生产部署，也没有安装依赖或连接/修改数据库。

## 2026-09-30 · 认证入口拆分与管理组件按需注册

- 将公开登录、OIDC consent、邀请接受及登录主题展示职责归档至 `frontend/src/app/auth/AuthEntry.vue`；`App.vue` 保留登录后会话、当前页状态与领域页面装配，导航配置和侧栏各自留在 `navigation.ts`、`components/AppSidebar.vue`。管理专用 Ant Design Vue 组件改为登录后动态注册，已存会话启动时先完成注册再挂载；前后端目录、API 与数据库契约未变。
- 同步整体 README、前后端指南、架构、PRD、UI 走查与项目 Skill。`pnpm run build` 通过 Vue/TypeScript 检查和 Vite production build（3198 modules）；主入口 367.85 KB / gzip 114.41 KB，管理注册 chunk 285.61 KB / gzip 83.78 KB，最大 chunk 低于 500 KB，Vite 不再告警。
- 重新加载本地登录页后，浏览器可访问性树确认标题、邮箱/密码字段、登录按钮及注册说明仍存在。未输入或提交管理员凭据，因此管理页运行时、OIDC RP 互操作和登录后 UI 视觉仍待验收。

## 2026-09-29 · OIDC Provider 分域与跨项目状态同步

- 将 OIDC 路由实现拆分为授权同意、Token/UserInfo/Introspection/JWKS/Revoke、RP-Initiated Logout、Discovery、共享校验和协议常量模块；`api/v1/oidc.py` 保留兼容导出，主应用及现有测试导入路径不变。前端导航白名单/面包屑抽至 `app/navigation.ts`，桌面侧栏和窄屏选择器抽至 `app/components/AppSidebar.vue`，认证 UI 后续已拆至 `app/auth/AuthEntry.vue`。
- 同步整体/前后端 README、PRD、架构、业务接入计划和项目 Skill。AI 简历最新源码快照为 40 张表、14 项 AI 任务、60 个模板；面试题库代码已实现并待验收，面试/OIDC 迁移都未演练，既有库业务迁移文件仍缺失。
- 验证：Python `compileall` 通过；与拆分前临时备份做 AST 比对，全部 33 个函数的签名、函数体和装饰器保持一致，十个 HTTP 路由路径完全相同。未能运行后端运行时导入或集成测试，因为当前主机 Python 环境没有 FastAPI、SQLAlchemy、PyJWT，且本地 OpenAPI 服务未应答；没有连接或修改数据库，也没有真实客户端互操作。前端 `pnpm run build` 通过，转换 3194 个模块；入口 1,275.69 KB / gzip 385.74 KB，原有超过 500 KB 告警仍存在；无管理员登录态，侧栏未做登录后截图验收。

## 2026-09-29 · AI 简历 OIDC 令牌保管状态同步

- AI 简历回调现要求 offline_access；经验证的 IAM access/refresh token 仅在后端使用专用密钥 AES-GCM 加密保存，服务端已有串行 refresh rotation helper，浏览器继续只接收业务本地会话。
- OIDC 纯新增迁移 20260928_iam_oidc_sso.sql 已补入但未在 PostgreSQL 演练；既有库业务迁移 20260927_full_workspace_upgrade.sql 当前缺失。中央 permission check、权限码映射和业务数据过滤仍未接入。
- 同步 IAM 根/前后端 README、PRD、业务接入计划和项目 Skill；AI 简历项目知识已记录对应状态。没有连接或执行数据库迁移。

## 2026-09-29 · 校正文档中的数据过滤和迁移状态

- 明确区分 PostgreSQL 谓词编译与业务仓储执行，向量检索过滤由业务适配层实现；同步根、前端、后端、架构和 PRD 说明。
- 修正后端指南的当前迁移 head 为 `0010_tenant_user_groups`，将早期 SDK 测试/镜像结果标记为历史快照。
- 对照源码确认前端 13 个领域页面位于独立 `features/` 子目录，后端管理路由按领域拆分；源码继续独立在 `frontend/` 和 `backend/`。
- 复核前后端目录和迁移文件链；Python 授权测试 11/11、TypeScript 授权/OIDC 测试 8/8、TypeScript strict build 均通过。Compose 查询未提供运行服务/数据库结果，本轮未连接数据库或部署。

## 2026-09-29 · 增加数据范围 PostgreSQL 谓词编译器

- Python `compile_postgres_data_scope` 与 TypeScript `compilePostgresDataScope` 将经过 SDK 校验的 IAM `any_of` 条件编译为参数化 PostgreSQL 谓词；每个 OR 分支独立 AND tenant，owner/组织可使用服务端映射转成本地主键，SQL 列名来自调用方固定映射，空组织列表明确匹配零行。
- 更新 Python/TypeScript SDK README、PRD、架构、业务接入计划、前后端 README 与项目 Skill。AI 简历现状同步为：当时 OIDC callback 会丢弃 IAM token，且工作区缺少文档引用的两份 DB migration；DeerFlow 与知识库既有未提交改动保持原样。没有把 SDK 辅助器描述成业务仓储已集成，也没有执行任何迁移或部署。
- 验证：TypeScript 授权/OIDC 测试 8/8、Python 授权测试 11/11、TypeScript strict build 通过。Python OIDC SDK 测试因当前内置运行时缺少可选 `PyJWT[crypto]` 未重跑；SQL 仅做参数/结构级测试，未连接 PostgreSQL 验收真实查询。

## 2026-09-29 · 增加本地 Compose 启动指南

- 新增 `docs/部署与运维.md`，说明 Docker Desktop 前置条件、`.env` 初始化、Compose 首次与日常启动、服务健康检查、登录地址、端口配置和 API 502 排查；不包含本机密钥或密码。
- 在根 README、前后端 README 和 PRD 增加指南入口。文档变更未运行服务或执行测试。

## 2026-09-29 · 数据范围 SDK 绑定 IAM OIDC subject

- Python/TypeScript 授权 SDK 在 `include_data_scope=true` 时要求业务服务传入已验签 IAM 会话的 `sub`（Python `subject_id` / TypeScript `userSubject`），不是产品本地用户主键。SDK 只在本地将 subject 与 IAM `owner_user_id` 条件比较，不把它发送给 IAM；缺少身份时请求前拒绝，IAM 返回其他 subject 的本人范围时以 502 契约错误拒绝。
- 新增双语言缺身份、owner subject 不一致、租户条件和 subject 不外传回归用例。Python 授权用例 9/9、TypeScript 授权用例 5/5、TypeScript SDK strict build 通过。`sdk/typescript/pnpm-lock.yaml` 锁定已声明的 TypeScript 开发依赖；新增其 `node_modules/` 与 `dist/` 忽略规则。
- 同步双语言 SDK README、前端/后端/整体 README、PRD、架构、业务接入计划和项目 Skill。本次不改 IAM API 或业务数据库，也不宣称业务系统已完成 SQL/向量行过滤。

## 2026-09-29 · 管理台领域页面首次访问按需加载

- 将工作台、主题、模型、租户、OAuth 应用、审计、邀请、角色、权限、用户、组织、用户组及授权模拟改为异步 feature 导入；未访问页面不创建 DOM，首次导航再加载相应 JS/CSS chunk，访问后保留页面实例以延续表单草稿和筛选状态。
- 新增共享 feature loading/error 状态组件，失败提示可刷新入口资源。没有增加前后端依赖；FastAPI API、OpenAPI schema 和 PostgreSQL 模型均未变。
- 本地运行检查发现 Docker Desktop Windows bind mount 未触发 Vite 对最新 `App.vue` 的热更新；在 `vite.config.ts` 启用 `server.watch.usePolling=true`（1000ms），只重启本地 console 容器后，模块端点返回 200 且解析出 13 项异步导入和 `visitedPages` 门控。启动后再次修改宿主机文件，2.5 秒内模块响应呈现新内容，验证了轮询监听。API/PostgreSQL 未重启。
- 验证：`pnpm build` 内 Vue/TypeScript 检查通过，Vite 转换 3191 个模块，生成 13 个 feature JS chunk；入口由上一构建 1,583.67 KB / gzip 479.63 KB 降至 1,275.42 KB / gzip 385.63 KB（约降低 19%）。入口仍大于 500 KB，Ant Design Vue 当前全局注册是继续优化重点。登录态浏览器的实际 chunk 请求、失败恢复和页面状态切换尚未验收。同步根、前端、后端 README、PRD、架构、UI 走查与 IAM Skill。

## 2026-09-29 · 后端过期认证凭证分批回收

- 新增 `backend/app/services/maintenance.py`，由 FastAPI lifespan 启动周期任务，独立数据库 Session 按批回收已过期的管理刷新会话、JWT 撤销摘要、OIDC 授权码和同意票据；默认周期 3600 秒、每表每批最多 1000 行，可通过 `CREDENTIAL_CLEANUP_INTERVAL_SECONDS` 与 `CREDENTIAL_CLEANUP_BATCH_SIZE` 配置。PostgreSQL 批处理使用 `FOR UPDATE SKIP LOCKED`，异常回滚后记录错误并等待下一轮重试。
- Compose、开发/生产环境样例补充对应配置。未增加数据库迁移；OAuth 刷新令牌族、邀请、审计和模型用量幂等记录继续保留，避免丢失重放检测、审计或幂等证据。同步 PRD、架构、运行手册、前后端 README、根 README 和 IAM Skill。
- 验证：后端完整 unittest 61 项通过；过期/未过期和批次幂等边界用例通过；PostgreSQL 删除语句在外层回滚事务中执行成功且未留下删除；FastAPI lifespan 启停检查通过；开发与生产 Compose 配置静态解析通过。本地 API 容器健康且导入到新清理循环配置（3600 秒 / 1000 行）；生产部署及长期运行行为尚未验证。

## 2026-09-29 · 用户与组织管理迁入独立前端 feature

- 新增 `frontend/src/features/users/UserManagement.vue`，独立承载用户搜索/创建/启停、用户实际所属活动租户中的角色绑定，以及多组织和主组织归属；密码字段按 API 长度校验且提交后清空，已有停用组织关联保留可见，避免重存时误删。
- 新增 `frontend/src/features/organizations/OrganizationManagement.vue`，独立承载租户筛选、组织目录、父子层级创建与启停；客户端校验字段边界，服务端仍负责跨租户和循环层级校验。`App.vue` 删除用户/组织通用表格、创建弹窗和绑定状态，收敛至认证/会话、导航、外观、健康状态和共享字典协调。
- 同步根/前端/后端 README、PRD、架构说明、UI 走查、运行手册和 IAM Skill；修正本地 schema revision `0010_tenant_user_groups` 已应用、后端套件 57 项通过的过期“待确认”描述。`docs/技术架构与接入.md` 的外部接入状态及 `docs/技术架构与接入.md` 的待产品决策状态均未因本次 UI 拆分改变。
- 验证：`pnpm build` 的 Vue/TypeScript 检查和 Vite production build 通过（3185 modules；JS 1583.67 kB / gzip 479.63 kB）；本地 API readiness 返回 `ok`；开发 PostgreSQL `alembic_version` 为 `0010_tenant_user_groups`；后端 `unittest discover` 57 项通过。Vite 主 bundle 仍高于 500 KB；浏览器当前停留登录页，没有管理员会话，未执行管理页面视觉和写入验收；生产迁移/部署仍未验证。

## 2026-09-29 · 权限编码目录迁入独立前端 feature

- 新增 `frontend/src/features/permissions/PermissionCatalog.vue`，独立管理权限目录读取、跨字段搜索、新建表单校验、加载/错误/空态和刷新；字段上限对应 `PermissionCreate` Pydantic 契约，不提供后端尚未支持的编辑/删除。
- `App.vue` 去除权限目录通用表格与创建弹窗，仅保留导航和页面挂载；后端 API 和数据库 schema 未改。
- 同步根/前端/后端 README、PRD、架构说明、项目 Skill 和 UI 走查记录。
- 验证：`pnpm build` 通过，Vue/TypeScript 检查完成，Vite 转换 3179 个模块；JS 约 1.58 MB / gzip 479 KB。主 JS chunk 超过 500 KB 的提示仍在，登录态浏览器和数据库创建验收未完成。

## 2026-09-29 · 角色与数据授权管理迁入独立前端 feature

- 新增 `frontend/src/features/roles/RoleManagement.vue`，接管角色目录、租户筛选/搜索、创建、只改名称与说明、启停、通用权限影响预览与原子更新、数据范围读取/编辑；加入角色编码、字段长度和指定组织范围客户端校验。
- `App.vue` 清除角色专属表单、授权预览和数据范围状态/弹窗，Shell 仅向用户/邀请页面提供角色字典；后端路由/API、审计与 PostgreSQL schema 未改，资源实例授权保留及并发 409 重预览行为保留。
- 同步 PRD、根/前端/后端 README、架构说明、项目 Skill 和 UI 走查记录。此前两项拆分完成审计日志与邀请管理 feature；邀请创建响应额外禁止缓存一次性 bearer 链接。
- 验证：`pnpm build` 通过（Vue/TypeScript 检查通过，Vite 转换 3176 个模块）；JS 约 1.57 MB / gzip 478 KB，主 chunk 超 500 KB 警告仍在。未获得管理员登录态，角色/授权/数据范围浏览器视觉及数据库写入验收待完成。

## 2026-09-29 · 成员邀请管理迁入独立前端 feature

- 新增 `frontend/src/features/invitations/InvitationManagement.vue`，独立承载租户筛选、邀请列表、邮箱/姓名/角色/有效期校验、创建/撤销、错误态和复制邀请链接；一次性链接只在组件状态中展示，关闭后清空。
- `App.vue` 仅保留公开接受邀请的认证流程、租户/角色共享字典、导航及页面挂载；成员邀请管理 API 和数据库契约未改，邮件投递仍未配置。检查发现创建响应含一次性 bearer 链接，后端已补 `Cache-Control: no-store` 与 `Pragma: no-cache`，防止浏览器/代理缓存凭证。
- 同步 PRD、根/前端/后端 README、架构说明、项目 Skill 和 UI 走查记录。类型检查首次发现并补齐全部导航键的默认表单空映射后，最终构建结果记录如下。
- 验证：Vue/TypeScript 检查及 Vite production build 通过，最终转换 3173 个模块，JS 约 1.57 MB / gzip 477 KB；运行 API OpenAPI 确认邀请 GET/POST 与按 ID 撤销路由存在，审计 GET 仍有 `limit`/`action` 参数；工作区 Python 对修改后的 FastAPI 路由 AST 解析通过。前端主 chunk 超 500 KB 提示仍在；未用管理员会话验证实际响应头/邀请写入，也未完成登录态 UI 验收。

## 2026-09-29 · 审计日志页面迁入独立前端 feature

- 新增 `frontend/src/features/audit/AuditLogPage.vue`，接管最近 100 条审计事件的只读查询、操作编码精确筛选、错误状态及结果展示；`App.vue` 仅保留审计导航和 feature 挂载，并清理旧通用表格里的审计专用列配置。
- 审计摘要仅以文本/Tooltip 呈现；页面说明反向代理环境下来源 IP 可能是代理节点。现有 `/api/v1/admin/audit` 与 `limit`/`action` 参数保持不变，筛选长度限制为 120 字符。
- 同步 PRD、根/前端/后端 README、架构说明、项目 Skill 和 UI 走查记录；Vue/Python/PostgreSQL 工程边界及 API、数据库 schema 未改。
- 验证：前端 Vue/TypeScript 检查与 Vite production build 通过，转换 3170 个模块，JS 约 1.56 MB / gzip 476 KB；本地 API readiness 为 `ok`，OpenAPI 确认审计 GET 路由和 `limit`/`action` 参数存在。主 JS chunk 大于 500 KB 提示仍在；没有管理员登录态，未完成页面浏览器视觉验收或审计数据写入操作。

## 2026-09-29 · OAuth 应用管理迁入独立前端 feature

- 新增 `frontend/src/features/applications/ApplicationManagement.vue`，独立管理 OAuth 应用列表、创建、名称/说明编辑、信任、启停、Secret 轮换及一次性密钥展示；`App.vue` 只保留供其他领域复用的应用字典。
- 新建表单要求至少一个登录回调，最多 20 个；客户端拒绝不安全协议、URL 凭据和片段，编辑仅提交名称/说明。一次性 Secret 只驻留组件状态，弹窗关闭后清空；原后端 API/数据库契约未修改。
- 同步 PRD、前后端及根 README、架构说明、项目 Skill 和 UI 走查记录；浏览器登录态及数据库写入验收仍待完成。
- 验证：`vue-tsc --noEmit --project tsconfig.json` 通过；Vite production build 转换 3167 个模块并通过，JS 约 1.56 MB / gzip 475 KB，主 chunk 大于 500 KB 提示仍在。

## 2026-09-29 · 租户管理页面迁入独立前端 feature

- 新增 `frontend/src/features/tenants/TenantManagement.vue`，独立管理租户目录、创建表单、标识校验、刷新、启停确认与状态请求；`App.vue` 仅保持导航、面包屑和其他页面复用的租户字典。
- 租户写操作成功后，feature 刷新自身列表并通知 Shell 更新用户/角色/应用/组织/邀请等表单用到的租户字典；停用说明与后端行为一致，包含旗下 OAuth 刷新会话撤销及重新启用不恢复旧会话。
- 同步 PRD、前后端及根 README、架构说明、项目 Skill 和 UI 走查记录；未改变 API/数据库契约。管理员登录态视觉验收及真实数据库创建/启停验收仍待完成。
- 验证：`vue-tsc --noEmit --project tsconfig.json` 与 Vite production build 通过，转换 3164 个模块，JS 约 1.55 MB / gzip 473 KB，仍有主 chunk 大于 500 KB 的提示；运行 API OpenAPI 显示租户 GET/POST 与状态 PATCH 路由存在。本次未修改后端源码，也未执行管理员数据库写入。

## 2026-09-29 · 模型治理页面迁入独立前端 feature

- 新增 `frontend/src/features/models/ModelGovernancePage.vue`，由其拥有模型目录列表、新建/编辑/启停、租户筛选，以及模型用量汇总和最近 100 条计量账目；`App.vue` 只保留导航、面包屑和激活的视图类型。
- 目录保留现有安全边界：凭证引用只展示配置状态，编辑留空保持/显式勾选清除；编辑请求不提交租户和模型标识；RPM/TPM 执行仍由默认关闭的服务端开关控制。
- 同步 PRD、前后端及根 README、架构说明、模型网关决策稿、项目 Skill 和 UI 走查记录。没有修改后端 API/数据库契约；登录态浏览器与窄屏视觉验收仍待完成。
- 验证：`vue-tsc --noEmit --project tsconfig.json` 通过；Vite production build 转换 3161 个模块并通过，JS 约 1.55 MB / gzip 472 KB，保留主 chunk 大于 500 KB 的拆包提示。运行中的本地 API readiness 为 `ok`，OpenAPI 确认模型目录 GET/POST 及用量 events/summary GET 路由存在；未做管理员认证下的 CRUD 持久化验收。

## 2026-09-29 · 登录主题管理迁入独立前端 feature

- 将登录主题编辑器的草稿表单、应用版本读取、保存/发布和桌面/手机预览完整迁到 `frontend/src/features/themes/LoginThemeManagement.vue`；`App.vue` 只传应用列表、当前应用 ID、激活状态和导航事件，并让 feature 在导航切换时保持挂载。
- 主题草稿归 feature 管理：页间切换不会丢未保存内容；切换应用时立即清空上一应用配置，并通过请求序号丢弃过期响应，避免网络较慢时串用其他应用主题。
- 同步根/前后端 README、PRD、架构说明、项目 Skill 和 UI 走查记录。前后端继续以独立目录和 HTTP API 连接；其他旧管理页仍需从 `App.vue` 迁出。
- 验证：Vue/TypeScript 类型检查通过，Vite production build 转换 3158 个模块并通过；JS bundle 约 1.54 MB 未压缩/471 KB gzip，并保留当前大 chunk 提示。未完成登录态浏览器截图验收。

## 2026-09-29 · 管理端后端路由按领域拆分

- 将管理端路由从历史聚合文件迁到概览、租户、应用、用户、邀请、RBAC/授权模拟、用户组、组织/数据范围、模型目录、模型用量、登录主题和审计模块；`admin/__init__.py` 现在只装配各域 router 并统一执行平台管理员依赖。现有 API 路径没有调整。
- 将角色与授权模拟 Pydantic 契约维护在 `schemas/access_control.py`，更新业务授权、授权服务和角色更新测试的导入路径；审计和 URL 校验等共用能力留在 `admin/common.py`。
- 将工作台概览视图抽取为 `frontend/src/features/overview/OverviewPage.vue`，应用壳只传入概览 API 数据/健康状态/加载态，并通过窄化的导航和刷新事件保持交互。
- 同步架构图、根/前端/后端 README、PRD 与项目 Skill。Vue 和 FastAPI 仍分别位于 `frontend/`、`backend/`；旧管理页仍有部分留在 `frontend/src/app/App.vue`，后续继续按前端领域迁出。
- 验证：Python AST 语法解析通过（58 个后端应用与测试文件）；本地 API readiness 为 `ok`，OpenAPI 显示 39 个管理端路径仍在原 URL 下，含概览、租户、应用、用户、邀请、RBAC、主题、用量和审计标签；匿名访问角色、模拟、邀请、用户组、模型目录、组织、主题和审计接口均被拒绝（401）。Vue 类型检查通过，Vite production build 转换 3156 个模块并通过，主 JS 约 1.54 MB 未压缩/471 KB gzip。后端单元测试无法运行：当前 Python 运行时缺少 FastAPI/SQLAlchemy，且项目没有 `backend/.venv`；没有执行数据库迁移，也未验证管理员写入和持久化。

## 2026-09-29 · 前后端领域模块继续拆分

- 用户组、模型目录/网关用量与配额、组织/成员归属/数据范围 Pydantic 契约从历史 `schemas/auth.py` 拆分到领域 schema 模块；对应管理路由分别迁入独立 admin router，保留既有 API 路径与平台管理员依赖。模型目录 handler 的直接调用测试改用新模块导入。
- 用户组创建/编辑页补齐租户必选、标识字符集/长度、名称与说明长度校验；无效表单在客户端阻止提交。跨租户筛选清除后列表显示每组租户，空状态文案随筛选范围调整。
- 用户组 PATCH 对值未发生变化的字段不再写审计事件，避免重复保存产生审计噪声；新增幂等审计覆盖用例。
- 全量知识走查发现并清理整体 README 中重复的架构条目/说明，统一用户组迁移与验收状态的表述。
- 验证：Vue/TypeScript 类型检查通过，Vite production build 转换 3154 个模块并通过；仍提示约 1.54 MB 未压缩 JS chunk。Python 3.14 AST 语法检查通过（59 个 Python 文件）；隔离后端测试因当前解释器缺少 FastAPI/SQLAlchemy、项目内没有后端虚拟环境而无法导入。在线 API ready 返回 `ok`，OpenAPI 显示用户组、模型目录、组织/数据范围三组路由与新标签，匿名 `/api/v1/admin/groups`、`/models`、`/organizations` 均返回 401；Docker CLI 未能返回引擎/容器状态，本轮未确认 migration 0010，也未完成 PostgreSQL/API 管理员写入验收。
- 同步根 README、前后端 README、架构说明、PRD、UI 走查与项目 Skill。管理台无已登录管理员会话，用户组页面仅完成源码走查。

## 2026-09-28 · 管理端授权模拟

- 管理台新增授权模拟页，可指定用户、租户、应用、权限与资源并查看允许/拒绝原因、判定检查轨迹、命中角色及可选数据范围。
- 租户切换会清空旧租户应用选择，避免表单继续提交不匹配的应用上下文。
- 角色授权表单新增只读变更预览，并将多条权限增删改为单事务批量保存；预览列出直接绑定活动成员覆盖面及因最后一条授权撤销而清理的数据范围，保存校验预览版本防止管理员并发覆盖。
- 后端将线上 RBAC/数据范围计算抽取为共享服务；新增平台管理员只读 `POST /api/v1/admin/authorization/simulate`。业务 `/api/v1/authorization/check` 保持原响应形状，不输出管理诊断信息。
- SQLite 隔离用例 13 项通过，覆盖 RBAC/数据范围判定、权限变更影响统计、遗留数据范围清理、实例级授予保留和预览版本冲突拒绝；受影响后端文件的 Ruff 检查通过。未连接 PostgreSQL，API 级管理员鉴权尚未 E2E 验证。
- pnpm 离线锁文件安装后，Vue/TypeScript 类型检查和 Vite production build 通过（3151 modules）；构建提示 JavaScript chunk 约 1.53 MB。类型检查发现并修复授权模拟页面默认值映射缺项。无管理员浏览器会话，未进行管理页面截图验收。同步更新 PRD、前后端 README、整体 README、UI 走查记录与项目 Skill。

## 2026-09-28 · AI 简历首版 OIDC 登录与账号绑定

- AI 简历 Express 后端新增 OIDC Discovery、授权发起/回调、PKCE/state/nonce/issuer 验证、ID Token 验签、access token 内省、单次 code 兑换和存量账号显式绑定；新增身份、尝试记录及短时 code 表。Vue 登录页与用户资料页已接入登录/绑定流程。
- 保留 AI 简历原 UUID 主键、本地 JWT/refresh 会话、RBAC 与资源归属；禁止基于 email 自动合并。当前只完成身份联邦，中央权限码映射与业务 SQL/数据范围执行未接入。
- AI 简历后端既有 8 项测试通过、`init.sql` 定义 36 张表、前端 6015 模块生产构建通过；维护契约检查全项通过。OIDC 真实 IAM/浏览器互操作、数据库迁移 PostgreSQL 演练仍待完成。
- 补齐 AI 简历 `20260928_iam_oidc_sso.sql` IAM 纯新增迁移；按当前 `init.sql` 和业务查询重建 `20260927_full_workspace_upgrade.sql`，包含基础结构保护与事务后核验。迁移未在数据库执行，未连接/修改任何业务数据库。
- 同步 AI 简历根/前后端 README、PRD、表结构文档、Skill 参考文档与变更日志；同步 IAM PRD、接入计划、根/前后端 README、项目 Skill 和本日志。DeerFlow 与知识库本轮未改造。

## 2026-09-28 · AI Knowledge 控制台 OIDC 接入首版

- FastAPI 管理控制台增加可选 OIDC 登录/成员绑定；服务端持有 client secret 与 PKCE verifier，通过 Discovery、RS256/JWKS、iss/aud/nonce/at_hash 校验，state 单次消费，最后签发现有本地 HttpOnly Cookie。
- 新增身份映射与短时 OIDC attempt 数据模型和 Alembic 0023；本地 admin/maintainer/observer、应用 grants、会话版本仍是授权权威，runtime API Key/ApplicationContext 未改变。
- 本项目控制台为 React：登录页按后端配置显示按钮，用户菜单提供显式绑定；邮箱相同不会自动合并。
- 同步知识库 env 示例、API/前后端 README、单一执行书的架构/状态/修改记录，以及本仓库 PRD、接入计划、README/Skill 和本日志。
- 验证：项目本地 .venv 已安装 PyJWT[crypto]；6 个后端源文件 AST parse、触及文件 Ruff、12 项 OIDC helper 单测、前端生产构建（1652 modules）与 ESLint 通过，Alembic heads 返回 0023_iam_oidc_identities (head)。未运行完整后端套件、未应用迁移、未联调真实 IAM/浏览器；功能仍不可标记为可投产。
- DeerFlow 盘点确认 Gateway 已有通用 OIDC provider → 本地 User → trusted principal 链路；需配置 IAM issuer，现有本地账号显式绑定与中央权限/数据范围仍未实现。更新接入计划、PRD、README 与 Skill，避免把已有 Gateway 能力描述成完全缺失。

## 2026-09-28 · OIDC Token Introspection 与 SDK 集成

- 新增 RFC 7662 `POST /api/v1/oidc/introspect`，只允许 HTTP Basic 验证过的 confidential client 检查自己的 access/refresh token；无效、过期、撤销、跨 client 或当前身份授权失效时统一返回 `active:false`，响应禁止缓存。
- `token_type_hint` 只作查找提示。内省与 RFC 7009 撤销均会回退检查两类支持的令牌，错误 hint 不会误报无效或遗漏撤销；Discovery 公布 introspection endpoint 与 `client_secret_basic`。
- Python/TypeScript OIDC RP SDK 新增内省 helper，并验证 issuer/client 和活跃响应字段；Python Discovery 检查要求同源 introspection endpoint。README 提供仅服务端使用示例。
- 重新核实 AI 简历真实工作区为 `D:\project\新建文件夹`（前端/Express 后端/浏览器扩展三个独立仓库）；纠正此前把 `D:\project\aijj`（实际为 AI 基金项目）误列为简历项目的接入计划。记录本地用户主键/现有认证、显式身份绑定规则，以及 DeerFlow/知识库的未提交工作树保护要求；本轮未改动外部仓库。
- 后端 39 项 unittest 通过（11 项 OIDC 集成覆盖含 access/refresh、跨客户端与 hint fallback）；Python OIDC SDK 9 项测试、TypeScript SDK 5 项 mock 测试、TypeScript 5.7 strict 编译、Python `compileall` 均通过。本地 API readiness 为 `ok`，Discovery 与 OpenAPI 公布新路由；当前源码 API Docker 镜像构建通过。
- 同步整体/前后端 README、PRD、接入计划、SDK 指南、项目 Skill 和本日志。第三方真实 RP/浏览器互操作、安全评审及真实 TLS/DNS/密钥生产启动仍未完成。

## 2026-09-28 · JWT access token 即时撤销

- 新增 Alembic `0009_access_token_revocations` 与 `RevokedAccessToken`：管理及 OIDC access JWT 都包含随机 `jti`；数据库只保存 SHA-256 摘要、用途和到期时间。有效期内的新撤销写入会顺带清理过期记录。
- `/auth/logout` 在撤销刷新会话的同一事务中撤销当前管理 access token；confidential client `/oidc/revoke` 新增 access token 支持，仅接受签名有效且归属该客户端的令牌。在线授权依赖与 `/oidc/userinfo` 即时拒绝已撤销 JWT；离线只验签的接入服务仍可能接受直到到期，须改用在线判定或明确风险窗口。
- Python/TypeScript OIDC RP SDK 新增 access token 撤销 helper；业务端登出建议撤销 access/refresh token 后再完成 RP-Initiated Logout。
- Alembic `0009` 已应用到本地开发数据库。后端 38 项 unittest、Python OIDC SDK 8 项、TypeScript SDK 5 项 mock 测试通过；TypeScript 5.7 strict 编译与 Python `compileall` 通过。生产 API 镜像已用示例配置重建，但生产服务未启动；真实域名/密钥部署、离线 token 撤销传播和外部业务系统接入仍未完成。
- 同步 PRD、整体/前后端 README、接入计划、运维手册和项目 Skill。

## 2026-09-28 · 模型配额闭环与管理配置

- 完成 `POST /internal/model-usage/reservations` 与 `/settle`：同租户模型 RPM/TPM 按滚动 60 秒判断，PostgreSQL 模型行锁避免并发超卖；超限 429；10 分钟预留；request ID 幂等；超预留实际用量照常入账并回传 `overrun`。
- `MODEL_QUOTA_ENFORCEMENT_ENABLED` 默认关闭；未启用或模型没有限额时不创建预留，网关继续通过现有用量上报接口结算。用户授权检查仍由网关在 reserve 前调用，IAM 不代理供应商请求或读取凭证。
- 模型管理 PATCH/UI 支持编辑与清空 RPM/TPM，审计仅记录变更字段；租户、模型标识仍不可改。模型列表显示当前是否执行限额。
- 管理台登录页已在桌面 `1280×720` 和手机 `390×844` 视口完成截图走查；已登录管理页仍需管理员会话逐页验收。
- 同步整体/前后端 README、PRD、模型网关决策稿、接入计划、运维手册、UI 走查和项目 Skill。Python `compileall`、后端 36 项 unittest、开发 API/管理台与生产 API/静态前端镜像构建、生产 Compose 静态解析及静态 console smoke check 通过。生产服务未启动：尚缺真实域名、TLS、生产密钥与灾备配置。前端 bundle 约 1.52 MB（gzip 464 KB），需要后续拆包优化。
- 待办：产品确认配额规则与保留期，AI 简历/DeerFlow/知识库外部仓库授权与实际接入，生产域名/密钥/备份 RPO/RTO，完整登录后浏览器和移动端视觉验收。

## 2026-09-28 · 应用资料编辑

- 应用列表返回描述及退出回调信息，并增加编辑入口；编辑表单将租户、Client ID 和 OAuth 回调配置设为只读。
- 新增受平台管理员保护的 `PATCH /admin/applications/{id}`，只允许更新名称/说明，拒绝 OAuth 身份、安全回调、信任和状态字段；审计仅记录变更字段名与租户。
- 增加显式 Client Secret 即时轮换入口；旧值立即失效，新明文只在 `Cache-Control: no-store` 响应中回传，创建密钥响应也禁止缓存；审计不记录密钥。管理台二次确认并提示同步更新业务后端配置。
- 添加 schema 契约和 PostgreSQL 事务用例，覆盖客户端身份、密钥哈希轮换、回调和信任状态保持不变；同步 PRD、前后端/整体 README、项目 Skill 与 UI 走查。Python `compileall` 通过；生产 Compose 只读配置解析通过。集成用例因缺少 SQLAlchemy 未能运行，API/管理台镜像构建已启动但仍未返回终态，前端本机依赖缺失因此 TypeScript/浏览器验收未完成。

## 2026-09-27 · 角色元数据编辑

- 角色列表增加描述字段和编辑入口；编辑只允许修改名称及说明，租户、应用范围、角色标识与现有授权保持不变。
- 新增受平台管理员保护的 `PATCH /admin/roles/{id}`；拒绝额外字段和空更新，允许清空说明，审计仅记录字段名和租户。
- 添加角色更新 schema/数据库事务用例；同步 PRD、整体/前后端 README、UI 走查和项目 Skill。当前环境缺 SQLAlchemy/PostgreSQL 及前端依赖，集成用例、构建和浏览器验收待执行。

## 2026-09-27 · 单机生产部署骨架

- 新增生产 Compose：PostgreSQL 内部网络、one-shot Alembic migration 门禁、非 reload 的多 worker API、一次性管理员引导 profile、Nginx 静态 Vue/同源 API 代理和 Caddy 自动 HTTPS；生产 API 不发布宿主机端口并以 UID 10001 运行。
- 增加非开发 Settings fail-fast 校验（PostgreSQL psycopg 3、强 JWT secret、管理员 allow-list、HTTPS issuer/控制台 URL）和配置契约用例；entrypoint 保留开发热重载，新增生产启动及独立迁移模式，且非开发默认不自动迁移/引导管理员。
- 不向 API 转发未验证的 `X-Forwarded-*` 头，避免信任任意 Docker peer；代价是审计 `source_ip` 暂记 Nginx 节点，需要经验证的代理身份设计后再开放真实 IP 传递。
- 增加生产环境变量模板、OIDC key 挂载、生产数据库备份和部署/迁移说明，并同步 PRD、整体/前后端 README、项目 Skill 与运维手册。Python `compileall` 和 Git Bash 的 entrypoint `-n` 检查通过；Docker CLI/Compose 不可用，Python 当前缺少 pydantic-settings/SQLAlchemy，且没有 Docker Compose YAML parser，故容器配置、配置单测和数据库链路未执行。自动加密异地备份、监控尚未实现。

## 2026-09-27 · 模型目录元数据编辑

- 管理台模型列表增加编辑动作；可更新提供方、名称、端点、能力、价格及外部凭证引用。凭证不回显，留空保留，勾选后显式清除。
- 新增平台管理员 `PATCH /admin/models/{id}`，仅允许模型元数据字段；租户/模型标识/RPM/TPM 不接受修改，审计只记字段名和凭证是否已配置，不保存引用原文。RPM/TPM 仍不执行请求准入。
- 添加模型更新契约与 PostgreSQL 事务集成用例，覆盖不可编辑字段、审计保密和原有限额保留。后端 `compileall` 通过；集成用例导入时因当前 Python 环境缺少 SQLAlchemy 而阻断，数据库事务验证未执行。前端依赖目录不存在，前端构建和登录后交互/窄屏验收尚未完成。
- 同步 PRD、总览、前后端指南、UI 走查与项目 Skill。

## 2026-09-27 · 配额实现保持待产品确认

- 复核历史自动审批结论后，撤回本轮未获明确批准的 RPM/TPM 预留与结算路由、请求扩展及集成用例；保留此前已存在的 Alembic 0008 schema scaffold。运行数据库与模型调用准入行为均未变更。
- 增加模型网关策略决策稿，列出建议默认、替代影响和待确认项；同步根/前端/后端说明、PRD、接入计划与项目 Skill。配额强制仍未实现，待用户确认超额拒绝、预留过期、provider 超时、调用失败和结算重试语义后再继续。
- 验证：源码核对仅保留原 /internal/model-usage 计量路由；尚未运行 PostgreSQL 集成测试。

## 2026-09-27 · 管理台窄屏导航与列表工具栏

- 桌面侧栏和窄屏页面选择器改为共用单一导航清单；650px 以下不再依赖横向滚动发现管理入口，并对选择值做页面键白名单校验。
- 手机列表工具栏改为可换行布局，搜索/租户筛选占用整行，减少控件挤压和横向溢出风险。
- 基于 Vue/CSS 源码走查实施；当前浏览器无管理台登录会话，工作区缺少前端依赖，5176 转换响应未反映本轮源码，故当前版本构建、登录后逐页截图、真实 390px 触摸滚动均未验证。同步 UI 走查、PRD、前后端/整体 README 和项目 Skill；无后端行为变更。

## 2026-09-27 · 授权 SDK 数据范围 fail-closed 校验

- Python 与 TypeScript 授权 SDK 在请求数据范围时，现在校验正向响应必须带非空 `any_of`；所有分支必须绑定已验证会话租户，且 kind/字段组合需在 `tenant`、`owner_user_id`、`organization_id` 白名单。只返回归一化约束；缺失、跨租户、空集合、未知 kind/字段、未请求却返回范围均按契约错误拒绝。空组织 ID 列表保持“匹配零行”。SDK 不执行 SQL/向量查询。
- Python 授权 SDK 7 项测试通过；TypeScript 授权与 OIDC mock 测试共 5 项通过。TypeScript 本轮运行时用 Node 24 type stripping；本机 TypeScript 编译器不可用，静态类型构建尚未运行。PostgreSQL 集成测试没有变更。
- 同步 PRD、两端 SDK 指南、根/前后端 README 和项目 Skill；该 SDK 契约修复不等于三个业务仓库已接入。

## 2026-09-27 · Compose 升级与数据库恢复手册

- 按当前 Compose 服务名、API entrypoint、PostgreSQL/OIDC key 卷补充手动备份、临时库恢复演练、升级顺序和密钥恢复要求；明确生产定时备份、加密、异地副本与 RPO/RTO 尚不存在。
- 修复根 `.env.compose.example` 中重复的 `IAM_MODEL_USAGE_API_KEY` 示例，并将本地 `secure-backups/` 加入忽略规则。
- 同步 PRD、根/前后端 README 与项目 Skill；本轮只补文档/配置示例，没有执行备份或恢复操作。

## 2026-09-27 · 首批业务系统接入边界盘点

- 只读检查 AI 简历、DeerFlow Gateway 产品扩展、知识库的认证入口、数据边界和关键源码；未修改三个业务仓库。
- 新增逐项目接入计划：AI 简历先建立用户/租户数据归属；DeerFlow 通过公开 Gateway principal 扩展契约联邦身份；知识库区分控制面 OIDC 成员会话与运行面应用 API Key，并规划后续终端用户文档检索隔离。
- 同步 PRD、根/前后端 README 与 IAM Skill。IAM SDK 不等于业务系统接入完成；真实数据过滤与业务仓库验收未执行。

## 2026-09-27 · IAM 管理台 UI 走查

- 检查本地桌面登录页，并结合 Vue 路由/组件和 CSS 断点静态盘点控制台；新增 UI 走查记录并同步 PRD、根/前后端 README 与 Skill。
- 登录入口视觉层次清楚；窄屏 12 项横向导航、表格横向滚动和主题预览列为登录后优先检查项。没有可验证管理会话，尚未完成登录后页面浏览器验收或样式改动。

## 2026-09-27 · OIDC RP-Initiated Logout

- Provider 新增 `end_session_endpoint` 与 `/api/v1/oidc/logout` GET/POST：验证本平台签名的 ID Token Hint（可接受已过期但签名有效的提示），拒绝 access token 冒充；退出回跳必须精确登记、state 必须存在且不能与静态回跳 query 冲突。事务性撤销该用户/客户端 refresh token，只有浏览器 HttpOnly 会话与 hint 主体相同时才撤销并清除平台 SSO Cookie，减少 logout CSRF。
- Python/TypeScript OIDC RP SDK 新增浏览器 logout 跳转和随机 state；GET 链接按协议在 query 中携带 ID Token Hint，运维必须从代理与应用 access logs 脱敏 `id_token_hint`。跨站 POST 通常不带 SameSite=Lax Cookie，因此可能只撤销 RP 令牌而保留 IAM SSO Cookie。
- 新增 PostgreSQL logout 集成覆盖成功撤销、白名单拒绝、access token hint 拒绝、他人浏览器 Cookie 不被清除及 Discovery 公告；OIDC 9 项 + 数据范围 5 项共 14 项测试全部通过。Python SDK 12 项、TypeScript RP 1 项、TypeScript strict build 均通过；本地 API readiness `ok`，数据库保持 `0007`。
- 同步 PRD、前后端与整体文档、项目 Skill 和两个 SDK 指南；应用注册表单明确标注 HTTPS/localhost 回调规则。Vue type-check/生产 build 通过（JS bundle 约 1.51 MB，保留 Vite 分块建议）。Front/Back-Channel Logout、access token 即时撤销、真实 RP 浏览器互操作和生产日志脱敏仍待完成。

## 2026-09-27 · TypeScript/Node.js OIDC relying-party SDK

- `sdk/typescript` 新增 IAM OIDC RP 客户端：Authorization Code + S256 PKCE、state/issuer/callback 校验、RS256 ID/access token 验签、nonce/`at_hash`/tenant/client 校验、UserInfo subject 绑定、refresh rotation 与 revoke。仅适用于 Node.js 服务端，Client Secret 使用 ECMAScript 私有字段，SDK 不依赖额外运行时包。
- 新增基于 Node 内置 test runner、临时 RSA key 与 mock Fetch 的流程测试，覆盖 S256、错误 state 在兑换前拒绝、RS256/nonce/`at_hash`/UserInfo 绑定、refresh rotation 与 refresh revoke；1 项通过。容器内 TypeScript 5.7 strict 检查与 JavaScript/声明文件构建通过。
- 同步 SDK 使用说明、PRD、整体与前后端指南、项目 Skill。三项外部业务仓库尚未改动；其服务端 session、cookie/CSRF 和真实 Provider 回调仍待接入验收。

## 2026-09-27 · 模型配额预留 schema 脚手架（未启用）

- 新增 `0008_model_usage_reservations` 与 ORM/schema 类型，记录调用预留身份、Token 上限及过期时间，供后续配额执行设计使用；本地运行数据库保持 `0007`，本轮未运行迁移。
- 配额预留/结算接口改动被自动审批拒绝：审查指出这会改变现有计量和模型调用准入语义，并可能因并发与结算处理影响生产请求，需要先确认拦截策略、失败和重试边界。当前没有执行逻辑，schema 不能作为强制额度能力使用。
- 同步 PRD、前后端指南、整体说明与 Skill，明确实现边界及 Compose 下次启动可能自动升级到 `0008`。

## 2026-09-27 · Python relying-party SDK 支持业务 OIDC 接入

### 新增

- 新增 `sdk/python/iam_oidc.py` 和可选 `[oidc]` 依赖，提供 Discovery、授权码/S256 PKCE、state/nonce/issuer/callback 检查、RS256 ID/access token 验签、`at_hash` 校验、UserInfo subject 绑定、服务端 refresh rotation 和 refresh token 撤销。
- TokenSet/登录 attempt 不在 repr 中暴露 bearer 凭证或 PKCE secret；Discovery endpoint 限定在配置 issuer 的同源 HTTPS，token 请求禁止重定向并限制响应大小/超时。Client Secret 只用于服务端 HTTP Basic。
- 更新 Python SDK、PRD、根/前后端 README 和 IAM Skill，补充安全服务端 session 的接入约定。

### 验证与边界

- Python SDK 12 项单元测试通过，OIDC 用例使用本地临时 RSA key 和 mock HTTP；IAM Provider 5 项 OIDC、5 项数据范围 PostgreSQL 集成测试共 10 项通过。
- API readiness 与 Python API/test 源文件 AST 解析正常；当前 OIDC SDK 仍未写入 AI 简历、知识库、DeerFlow 外部仓库，需获准写入其工作区后分别适配 cookie/session 与业务数据过滤。
- 生产部署配置改造尝试在自动审批阶段被拒绝；理由涉及生产启动/凭证生命周期及反向代理信任设置的影响面，未修改启动脚本、Compose 或密钥处理。

## 2026-09-27 · 数据范围租户与指定组织边界补测

- 新增 PostgreSQL 集成用例验证 `tenant` 解析只使用当前成员租户；验证指定组织策略中即使包含人为构造的异租户组织 ID，解析结果也会二次按 tenant 过滤。
- 当前数据范围集成测试增至 5 项：本人、组织树、租户、指定组织异租户过滤、缺失策略默认拒绝。五项均使用外层事务回滚 fixture，通过。
- 修正 PRD 与前后端/整体说明中仍称正向数据范围未验证的状态；更新项目 Skill 的具体覆盖范围。
- 业务项目尚未接入真实业务库，IAM 响应条件的 SQL/向量检索执行仍需在各接入项目中验证。
- 按当前测试方法数更正文档和前一条日志中的 OIDC 计数：OIDC 实际 5 项，数据范围 5 项，本轮合计执行 10 项，全部通过。

## 2026-09-27 · OIDC 用户同意与受信任客户端

### 新增与安全约束

- 新增 `0007_oidc_user_consent`：新建应用默认不受信任，授权请求逐次显示 scope 同意；管理员可明确设为可信任客户端，`prompt=consent` 可强制同意，非受信任应用的 `prompt=none` 返回 `consent_required`。
- 新增哈希存储、绑定用户及原始 OIDC 上下文的短时单次同意票据；批准、授权码签发、审计和票据消费置于同一事务，拒绝返回 `access_denied`。信任降级撤销该应用的 OAuth refresh token。
- 管理台加入客户端信任确认操作和 OIDC consent UI，显示应用/租户/请求范围并套用已发布登录主题；票据经 URL fragment 交付后立即清理。Consent context/decision 响应禁用 HTTP 缓存。

### 验证与待办

- 5 项 PostgreSQL OIDC 集成测试通过，覆盖批准/拒绝、同意票据检查、trusted、`prompt=none`、`prompt=consent`、授权码交换及重放拒绝；此前 3 项数据范围集成测试、Python SDK 4 项和 TypeScript SDK 严格编译通过。之后数据范围集成测试扩展至 5 项。
- Compose API/控制台启动探针正常；控制台 Vue 类型检查和 Vite 生产构建通过。Alembic 当前为 `0007_oidc_user_consent (head)`，Discovery 公布 `login/none/consent`。
- 同步 PRD、根/前后端 README 和项目 Skill。真实 RP 浏览器互操作、外部业务项目接入、RP logout、access-token 内省/即时撤销、密钥轮换及生产安全评审仍未完成。

## 2026-09-27 · 数据范围租户边界与集成验证

### 修复与验证

- 修复 `self` 数据范围只限制全局用户 ID 的租户穿透风险：所有 `any_of` 条件现在都带 `tenant_id`，业务项目必须将租户限制 AND 到每个 OR 分支。
- 新增 PostgreSQL 集成用例，覆盖本人范围租户绑定、组织树包含后代但排除兄弟节点，以及缺少策略时默认拒绝。测试使用事务回滚 fixture；3 项均通过。
- Python 服务端授权 SDK 4 项标准库测试通过；TypeScript SDK 使用正式 `tsc` 严格编译通过。
- 同步 PRD、业务 SDK 接入说明、前后端/根 README 和项目 Skill。

## 2026-09-27 · 租户成员邀请闭环

### 新增

- 新增 `0006_user_invitations` 与邀请创建/查询/撤销、公开预览/接受、一次性复制链接和后台邀请管理页。
- 仅保存 SHA-256 token 摘要；邀请以 URL fragment 交付；已存在身份须证明当前密码。停用成员重新加入时清除旧角色绑定，仅授予当前邀请角色。
- PostgreSQL 部分唯一索引阻止同租户同邮箱并发生成多个未完成邀请；同步 PRD、根/前后端 README 和 IAM Skill。

### 验证与边界

- Docker API 镜像构建和 Vue `vue-tsc -b` / Vite 生产构建通过；运行库迁移到 `0006`。`/ready` 返回 `ok`、控制台 HTTP 200、管理员邀请列表正常、未认证列表访问 401、伪造 token 预览 404；未创建持久测试数据。邀请正向接受流程需要活动租户/角色测试 fixture；邮件投递未配置。
- 邀请失效页增加“返回登录”操作，避免链接过期后落入无继续路径的页面。首次启动因 8001 被占用，改在 8011/5176 验证。
- `alembic current` 确认为 `0006_user_invitations (head)`；Python 后端源码 `compileall` 通过。浏览器目视检查登录页和邀请失效页，返回登录操作正常。

## 2026-09-27 · 业务后端授权 SDK

### 新增

- 新增 Python 标准库 SDK 与 TypeScript/Fetch SDK，统一调用在线 `POST /api/v1/authorization/check`；支持传入应用 UUID、权限码、资源 ID 和数据范围选项。
- SDK 不保存 token、不实现 OIDC 登录/token 验签或业务数据过滤；服务异常、非法响应和拒绝决策均 fail closed。补充两个 SDK 的接入说明和 PRD 契约。

### 验证和限制

- Python SDK 的 4 个 `unittest` 用例通过：请求头/租户应用上下文、拒绝决策、网络错误和非法响应。
- TypeScript SDK 用 Node 24 的 type-stripping parser 执行语法检查通过；包的 `tsc` 类型构建尚未运行。IAM 主控制台的 `vue-tsc -b` / Vite build 仍通过。
- 尚未将 SDK 接入 AI 简历、DeerFlow 或知识库的真实业务仓库；需由用户提供代码路径、分支、用户主键及业务数据字段映射。

## 2026-09-27 · 模型调用用量账本与管理视图

### 新增

- 新增 Alembic revision `0005_model_usage_events` 与 append-only SQLAlchemy 账目，保存网关 request ID、租户/模型/应用/用户关联、输入输出 Token、调用结果、耗时和基于目录价格的估算费用。
- 新增 `POST /api/v1/internal/model-usage`，仅接受服务端 `MODEL_USAGE_API_KEY`（32+ 字符）调用；校验关联实体仍有效，重试幂等，request ID 用不同数据重用会返回 409。不接受 Prompt、模型响应正文或供应商密钥。
- 管理 API 提供模型用量汇总/最近明细；管理台增加用量导航和统计卡片/账目表；同步 PRD、前后端指南、总览和 IAM Skill。

### 验证和限制

- Compose API 镜像构建成功并启动，ready 返回 `ok`；管理员登录后成功查询 summary/events（均为 0 条），证明 `0005` 数据表已由启动迁移创建。未登录 summary 返回 401；无用量密钥且请求结构完整时内部上报返回 503。
- Console 镜像 `vue-tsc -b` 和 Vite production build 通过，页面返回 HTTP 200；bundle 约 1.50 MB（gzip 460 KB），Vite 提示主 chunk 大于 500 KB。
- 数据库没有模型和应用，且当前没有配置网关密钥，因此未验证正向上报、重复 ID/冲突处理，也未走浏览器登录后的模型用量页面交互。
- 此账本只计量已完成的模型调用，不代理供应商请求、不读取外部 Secret Manager、不执行 RPM/TPM/预算配额。网关共享密钥未提供，未写入本地环境或任何文件。

## 2026-09-27 · OIDC Access Token 接入在线授权判定

### 新增

- OIDC RS256 access token 加入签发租户声明 `tenant_id`；管理会话 HS256 与 OIDC RS256 在统一身份依赖中分开验签，且拒绝 ID token 作为 API 凭证。
- 在线校验应用、租户、用户、活动成员及租户/应用角色，确保账号或角色撤权后授权接口即刻拒绝；OIDC token 无法进入平台管理员 API。
- `/authorization/check` 将 OIDC 请求固定到 token 的租户和应用，应用 ID 可省略但无法切换；同步 PRD、前后端指南、总览和 IAM Skill。

### 验证和限制

- Compose 服务检查显示 PostgreSQL、API、console 均运行；`/api/v1/ready` 返回 200、console 返回 200，未认证调用 `/authorization/check` 返回 401。主机未安装 Python launcher，无法执行本机 py_compile；受限 shell 后续调用 Docker CLI 返回拒绝访问，因此未取得容器日志或触发显式镜像重建。
- 数据库没有可供安全清理的完整 OIDC 应用/用户/角色 fixture，未做授权码至业务鉴权完整 E2E，也没有正向验证新增的 RS256 业务鉴权路径。
- 该依赖会对 OIDC access token 在线查库验证撤权；其他接入服务离线校验签名时仍可能在 access token 短期过期前接受已签发 token。

## 2026-09-27 · 组织树与角色数据范围策略

### 新增

- 增加 `0004_organizations_data_scopes` 迁移：租户组织树、成员多组织归属/主组织、role-permission 数据范围策略。组织父节点、成员到组织、角色到数据策略使用 tenant 复合键外键，数据库层阻断跨租户拼接关系。
- 管理 API 增加组织列表/新增/修改/启停、查询用户真实租户归属、替换其组织关系、按角色读取/替换数据策略；写操作与审计在同一事务提交。
- 授权判定支持 `include_data_scope=true` 并返回 tenant/self/组织/子树/指定组织组成的 `any_of` 条件；未配置策略、或组织条件解析为空时默认拒绝。
- 管理台增加组织树维护和用户组织归属操作，并可按角色已授予权限配置数据范围；同步 PRD、前后端手册、总览和项目 Skill。

### 验证和限制

- API/console 容器镜像构建通过，`0004` migration 已由 API 启动脚本应用；API ready 返回 `ok`，管理员读取组织列表返回 200，未登录组织列表返回 401，未绑定角色的 `include_data_scope=true` 判定返回拒绝；不存在角色的数据策略查询返回 404。Vue `vue-tsc -b` 和 Vite production build 通过。
- 未创建持久测试组织/角色/权限数据，因此本人/部门/租户正向策略解析及跨租户边界场景尚未端到端验证；组织管理台具体交互尚未通过浏览器验收。
- 本轮数据范围合约约定本人字段 `owner_user_id`、组织字段 `organization_id`。AI 简历/知识库等业务项目的真实字段映射仍需由项目维护方确认；IAM 只输出查询约束，不直接过滤业务库内容。
- 业务/API 数据范围 E2E、并发组织变更与完整权限回归尚未验证。用户组、属性策略及委派管理仍待开发。

## 2026-09-27 · OIDC 授权码与品牌登录流程

### 新增

- 增加 FastAPI OAuth 2.0/OIDC Provider：Discovery、授权码、token、refresh 轮换与重放族撤销、RFC 7009 风格 refresh 撤销、UserInfo、JWKS。严格要求 `response_type=code`、S256 PKCE、已登记精确回调和 state/nonce；客户端仅支持服务端 HTTP Basic 密钥认证。
- RS256 使用持久化 RSA 私钥签发 ID/access token；开发环境生成密钥并存入独立 Compose 卷，非开发环境要求外部挂载密钥文件。停用用户、租户或应用事务性撤销对应 OAuth refresh token。
- 前端从授权请求展示目标应用及已发布登录主题，安全校验本站 return_to，登录后继续授权；支持品牌色、背景、Logo、预设布局和卡片尺寸/位置。
- 更新 PRD、前后端指南、总体 README、项目 Skill 与本地 Compose issuer/控制台地址配置。

### 验证和限制

- API 容器安装依赖、应用迁移、RSA 签名密钥准备、管理员引导及 ready 探针均通过；console 容器 `vue-tsc -b` 与 Vite production build 通过。首轮构建发现并修复 `loginReturnTo` 初始化顺序问题。API `/api/v1/ready` 返回 `ok`，Discovery/JWKS 可读，未知应用登录配置为 404、未认证 UserInfo 为 401、非表单 token 请求为 400、未知客户端授权请求为 400 且没有跳转到请求方恶意回调；管理台浏览器加载正常。
- 本地现有库没有应用和活动角色绑定，因此未创建永久测试数据，授权码 → token → refresh → revoke 完整协议 E2E 与第三方客户端互操作仍未验证。该 Provider 尚不能作为已验收的生产 SSO。
- Provider 使用自定义 FastAPI 协议实现，尚无授权同意 UI/客户端信任设置、RP logout、access token 内省/即时撤销、平滑签名密钥轮换、登录限流/MFA、邮件找回或生产安全评审。业务服务集成前需先完成协议互操作与安全测试。
- 本地 `.env` 保存的密钥不应复制进聊天或提交；生产 `IAM_OIDC_ISSUER` 与 `IAM_CONSOLE_PUBLIC_URL` 必须使用 HTTPS 对外地址，私钥必须由密钥管理器挂载。

## 2026-09-27 · OIDC 凭证存储基础

### 新增

- 添加 `OAuthAuthorizationCode` / `OAuthRefreshToken` SQLAlchemy 模型及 Alembic revision `0003_oauth_code_storage`。授权码记录绑定应用、用户、精确回调、openid nonce、PKCE challenge、过期和一次性消费状态；OAuth 刷新令牌保存摘要、token family、客户端、用户、scope、到期/撤销和替换关系。
- 同步 PRD 数据模型、前后端技术说明、整体总览、项目 Skill 与本变更记录。文档明确这些是协议持久层基础，不代表授权/令牌端点或业务系统 SSO 已可用。

### 验证与未完成范围

- API 镜像重建并重启后，启动脚本自动将 PostgreSQL 迁移升级至 `0003_oauth_code_storage`；API `/api/v1/ready` 返回 `ok`，控制台返回 HTTP 200。启动成功说明模型导入和 Alembic 链可运行，尚未通过 OAuth 端点执行协议层兑换验证。
- 当前仍无授权端点、登录中心页面、客户端认证、PKCE 验证、令牌签名密钥与 Discovery/JWKS；本次没有添加新依赖。

## 2026-09-27 · 停用账号时撤销全部刷新会话

### 调整

- 修复用户被停用后又重新启用可能复活旧 refresh Cookie 的缺口。管理员停用用户时，账号状态变更、所有未撤销刷新会话的撤销时间和审计记录在同一数据库事务提交；重新启用不重置会话状态。
- 同步 PRD、前后端指南、整体总览和项目 Skill，明确停用期间 access JWT 即时拒绝且旧刷新凭证永久失效。

### 验证与限制

- API 容器自动重载后，`/api/v1/ready` 返回 `ok`，控制台返回 HTTP 200，说明新增管理路由和 SQLAlchemy 更新语句可正常导入。没有通过真实用户做停用/重启用端到端试验，以免在没有用户删除/清理接口的开发数据库留下测试账号；该路径仅完成源码与事务边界检查。
- OAuth/OIDC 的授权码/PKCE、Discovery/JWKS、应用主题登录页、组织与细粒度数据范围等仍待开发。

## 2026-09-27 · 浏览器刷新会话轮换

### 新增

- 新增 PostgreSQL `refresh_sessions` 表与 Alembic revision `0002`。刷新令牌使用高熵随机值，数据库只存 SHA-256 摘要；每次刷新在事务行锁下撤销旧值并轮换，继承会话固定绝对过期时间。
- 登录/开放注册设置 HttpOnly、SameSite=Lax 刷新 Cookie；登出撤销当前会话并清除 Cookie。Cookie 使用 Secure 标志（非开发环境启用），并限定 `/api/v1`；其他 API 仍必须使用 Bearer，Cookie 本身不作为 API 登录凭据。
- 前端收到管理 API 401 时最多自动刷新并重试一次，刷新失败后清除当前标签页访问令牌。刷新端点与登录/注册端点不触发递归刷新。
- 同步本文件、PRD、前后端指南、根目录总览和项目 Skill，纠正此前“令牌过期即直接登出”和“无服务端刷新撤销”等过期描述。

### 验证与未完成范围

- Docker API / 前端镜像构建通过；Alembic revision 已应用。手工验证登录可收到 HttpOnly Cookie、refresh 轮换成功、新 access token 可访问 `/auth/me`、登出后再次 refresh 返回 401、数据库 ready 探针正常；没有输出或记录密码与令牌。
- OIDC 授权码与 PKCE、Discovery/JWKS、一次性授权码、客户端认证及 SSO 登录页仍未实现；该刷新 Cookie 不代表 OIDC 浏览器会话已完成。后续授权端点接入前，Cookie 路径已放宽到版本化 API，且其他 API 仍不读取 Cookie。

## 2026-09-27 · 本地运行闭环与 IAM 接入准备

### 新增

- 新增根目录 Docker Compose、PostgreSQL 16、FastAPI 和 Vite 开发容器；API 启动会等待数据库、应用 Alembic 迁移并幂等创建管理员，前后端代码通过 bind mount 支持本地热重载。
- 新增忽略提交的 `.env` 规则和 Compose 环境模板；本地 `.env` 由随机值生成，未向工具输出密码。8001/5174 已被其他 Docker 服务占用，因此该项目使用 8002/5175，未停止既有服务。
- 应用注册支持登出回调白名单；服务端创建随机 Client Secret，Argon2 哈希落库，只在创建响应中回传一次，管理台提示安全保管。
- 前端容器构建增加 Vue/TypeScript 类型检查和 Vite production build；仅批准 pnpm `core-js` 的安装构建脚本。
- 修复首轮登录验证暴露的管理员引导非幂等问题：切换引导邮箱时复用平台租户，并补齐缺失的成员关系；改用可通过邮箱校验的本地示例账号。
- PRD 增补全量开发分期，以及 AI 简历/DeerFlow/知识库接入、数据权限、邮件、模型密钥和部署等需要产品方/部署方提供的信息。

### 验证与未完成范围

- Docker 镜像构建和 `vue-tsc -b && vite build` 通过；构建时发现并修复 `display_name` 标签映射重复键。
- PostgreSQL 迁移与管理员引导已由 API 容器启动；`/api/v1/ready` 返回 `ok`，管理台首页返回 HTTP 200，管理员登录并使用 `/auth/me` 验证通过。密码与令牌未写入命令输出。
- 前端 bundle 约 1.49 MB（gzip 457 KB），Vite 提示可做代码拆分；尚未完成登录后管理全流程浏览器核验。
- OAuth/OIDC 端点、登录中心、用户邀请/恢复、组织与数据范围策略、模型代理与配额、业务系统 SDK/集成及生产安全部署仍未实现。

## 2026-09-27 · 管理台 UI 走查

### 调整

- 登录主题从原始 JSON 编辑改为表单配置，可调整文案、品牌色、背景/Logo 地址、布局、卡片宽度/位置/圆角和入口开关，并提供桌面/手机实时预览及版本历史。
- 提升后台文字与表格可读性；统计卡片、主题编辑器和导航针对窄屏重新排布；加入键盘焦点和减少动态效果样式。
- 通用列表增加刷新入口，用户搜索保留；停用记录先弹确认；401 后同步清除页面登录状态；工作台展示真实健康检查状态。
- 修正文档中有关主题 JSON 编辑器和用户角色绑定能力的过期说明；更新 PRD、前后端指南、整体 README 与项目 Skill。

### 验证与限制

- 静态检查确认已移除主题页对旧 `themeJson` 状态的引用，管理列表停用按钮调用确认流程。
- 由于 `frontend/node_modules` 缺失，尝试启动 Vite 时 pnpm 在工作区创建临时文件遇到 Windows `EPERM`；无法运行构建或浏览器视觉验证，也未发起联网安装依赖。
- 本次仅变更前端交互/样式与文档；后端 API、数据模型、迁移未修改。

## 2026-09-27 · 管理闭环开发

### 新增

- 后端新增 Argon2 邮箱密码登录、HS256 短期访问令牌、服务端用户状态检查、管理员配置保护与一次性管理员引导脚本。
- 新增租户、应用、用户、角色、权限、角色绑定、主题版本、审计查询/写入和数据驱动概览 API；新增业务端默认拒绝 RBAC 判定接口。
- 新增 `audit_events` 模型、RBAC 部分唯一索引修正和应用主题版本唯一约束；补充静态 PostgreSQL Alembic 首版迁移。
- 新增按租户隔离的模型元数据目录、外部凭证引用约束、模型启停及管理台模型页面/概览统计；供应商密钥不返回浏览器。
- 前端登录页和管理台连接真实 API；支持概览、租户/应用/用户/角色/权限/主题/审计页面、基础记录创建、用户启停与角色权限增删。
- 扩充 IAM 项目 Skill，使其包含模型关系、API 入口、安全边界和明确未完成范围；同步刷新 PRD、前后端指南与整体 README。

### 验证和未完成范围

- 使用桌面随附 Python runtime 对 25 个 Python 文件执行内存语法编译，语法检查通过；未创建 `.pyc` 文件。
- 当前缺少 FastAPI、SQLAlchemy、Pydantic Settings、Alembic、pwdlib、PyJWT、email-validator 依赖，未做后端导入、迁移运行、API/数据库或登录端到端验证。
- 前端依赖目录不存在，未运行 `vue-tsc`、Vite build 或浏览器验证；既往 `pnpm install` 遇到 Windows `EPERM`，本次没有绕过系统权限安装依赖。
- 使用 pnpm 离线模式再次检查依赖时，本机包缓存缺少 `@tailwindcss/vite` 元数据，依赖仍无法安装；没有发起联网下载。
- Skill Creator 的结构验证器因桌面 Python 缺少 PyYAML 而未能运行；仓库没有 Git 元数据，无法提供 Git diff/status 作为审查依据。
- 本版没有 OAuth 2.0/OIDC Provider/PKCE/JWKS、邮件短信服务、MFA、密码重置、组织/细粒度数据权限、模型代理与业务系统适配器，不能作为已完成 SSO 产品发布。
- 本版虽有模型元数据和授权目录，仍无外部 Secret Manager、模型代理、用量计量/限额执行；业务项目 SDK/端到端接入也未完成。
- 管理员登录令牌暂存于 sessionStorage，登录限流与远程刷新令牌撤销未实现；需完成安全评审和生产会话改造。
- 早前日志关于“管理写 API、迁移、认证未实现”的内容为当时状态记录；本节覆盖其后的本次实现状态，不删除历史记录。

## 2026-09-27

### 新增

- 初始化 Vue 3、TypeScript、Ant Design Vue、Tailwind CSS、Vite 前端工程和 IAM 管理台起始页。
- 初始化 FastAPI 后端工程、配置入口和 `/api/v1/health` 进程健康检查。
- 建立前端、后端及整体技术说明，整理产品需求文档至 `docs/产品需求.md`。
- 新建项目专用 Skill，定义 `--更新` 知识审计和每次开发同步文档的约定。

### 说明

- 本次尚未安装依赖。环境中有 Node.js 和 pnpm，但未找到 Python 命令；前端构建及后端运行验证仍待完成。
- PostgreSQL 依赖和连接配置已预留，数据库模型、迁移及真实认证/授权尚未实现。

### 技术栈调整

- 按产品负责人要求，前端组件库确定为 Ant Design Vue，样式工具确定为 Tailwind CSS。
- 后端维护文档增加中文注释要求，重点解释 API 分层、校验顺序、租户隔离和安全边界。
- 依据官方接入说明采用 Ant Design Vue 4 与 Tailwind CSS 4 的 Vite 插件方式；依赖安装和构建兼容性待验证。
- 根据当前 Vite 官方指南将构建工具调整到 Vite 8 和 Vue 插件 6；本机 Node 24 满足官方 Node 版本要求。
- 尝试执行 `pnpm install` 时遇到 Windows `EPERM`，依赖未安装；尚未运行前端构建。

### PRD 调研与主题配置

- 查阅 Keycloak、authentik、ZITADEL、Casbin 和 Ant Design 官方文档，补充成熟产品比较与项目取舍。
- PRD 明确全局用户与租户成员关系分离、租户/应用角色绑定，以及 Resource/Scope 授权模型；授权模拟和细粒度管理员委派纳入 V1.1。
- 区分 IAM 管理台外观与各业务应用登录品牌；管理台原型加入浅色/深色、主色和密度切换，当前仅本地保存。
- 按更新后的 PRD 增加 PostgreSQL 按需连接池和 `/api/v1/ready` 探针；`/health` 仍独立报告进程存活。业务读写和迁移尚未实现。
- 增加 Tenant、User、TenantMembership、Application、ApplicationTheme、Role、Permission、RolePermission 和 RoleBinding 首批 SQLAlchemy 模型，注释说明全局身份与租户授权上下文边界。
- 管理台原型默认采用成熟后台常见的浅色工作区，并保留深色偏好切换。
## 2026-09-29 · 修正 SDK 数据过滤与后端验证状态文档

- PRD 明确区分 PostgreSQL 谓词编译与业务仓储真实执行，并说明向量检索过滤仍由业务适配层完成。
- 后端指南将此前测试/镜像数据标记为历史验证快照，避免将旧 SDK 测试数和 Alembic 状态误读为本轮结果。
- 本轮为文档一致性修正；没有修改业务代码、运行测试、连接数据库或执行部署。







## 2026-10-09 · 修复公开认证输入长度属性类型

- 邀请密码、密码重置和登录/找回邮箱的 `minlength` / `maxlength` 改为数值绑定，避免 Ant Design Vue 输入组件把字符串传给数值型属性。
- Vite 生产构建通过，转换 3205 个模块，产物输出到 Windows Temp；`vue-tsc --noEmit` 未通过，当前依赖树无法解析 Vue 的 `@vue/runtime-dom`、`@vue/compiler-dom` 类型导出。离线 frozen-lockfile 修复未能启动，已中断；未联网安装、未改依赖锁文件。
- 仅修改前端登录入口；未改后端/API/数据库，未执行迁移。Docker Compose CLI 可用，但本会话连接 Docker Desktop Linux Engine 命名管道被拒绝，无法查看/启动服务；浏览器控制台告警和真实登录流程仍待运行环境验收。

## 2026-10-09 · 用户本机 Docker 启动反馈

- 用户提供的终端截图显示 `docker compose up -d` 启动 3/3：PostgreSQL healthy、console healthy（5175→5173），API 已 Started 且容器刚启动，`docker compose ps` 仍显示 health: starting（8002→8000）。这是截图证据，尚未由本会话读取 API 日志或 health/ready 接口。
- 当前不据此判断 API 故障或 ready；未执行 migration/bootstrap，数据库 revision 尚未复核。

## 2026-10-09 · 控制台数据库不可用诊断

- 当前控制台显示“数据库不可用”，前端映射码为 `database_not_ready`；后端就绪探针将数据库连接/只读查询异常统一返回该码，区别于 `database_migration_pending`。PostgreSQL `pg_isready` healthy 本身不校验 API 密码。
- Codex 会话无法访问 Docker Engine 日志；根因待用户在本机查看 API 日志确认。未修改 `.env`、未删除卷、未执行迁移/bootstrap。

## 2026-10-09 · 确认开发库凭据不一致

- 用户粘贴的 Docker 输出明确显示迁移容器 `FATAL: password authentication failed for user "iam"`；API unhealthy，readiness 连续 503。根因已确认为当前 Compose 提供的密码与持久化 PostgreSQL 中 `iam` 角色密码不一致。
- Alembic 在连接数据库阶段失败，未执行迁移 DDL。没有删除 volume 或修改凭据；后续应恢复/重置角色密码与本地 `.env` 一致，再复核连接并重跑已由用户尝试的迁移命令。

## 2026-10-09 · 修复本地 IAM 数据库认证并恢复服务

- 将持久化 PostgreSQL iam 角色密码同步到本地环境文件中 API 实际使用的值；未记录或输出密码，也未删除数据库卷。
- 在 API 容器内执行 SELECT 1 成功；重新构建并运行显式 migration profile，已应用 0017_tenant_org_admin_permissions 至 0021_resume_wallet_perms。
- docker compose ps 显示 postgres、console、api 均 healthy；API 容器内 /api/v1/ready 返回 HTTP 200、status: ok。
- 当前浏览器中的 http://localhost:5175/ 已加载公开认证页，页面无服务不可用提示。未提交登录或找回密码请求；管理员初始化及登录态后台验收尚未确认。
- 同步根目录、前后端说明、PRD、启动指南、运维记录、UI 走查及项目 Skill；测试套件未运行。
## 2026-10-09 · 轮换本地管理员与数据库凭据

- 通过密码重置完成接口更新配置管理员账号的 Argon2 密码；认证版本递增并撤销该用户现有 IAM/OIDC 刷新会话，写入密码重置审计事件。
- 轮换本地 PostgreSQL iam 角色密码及 JWT 签名密钥，并更新根目录运行配置 .env；API 容器重建后通过 Compose health check。
- 验证新管理员密码与数据库哈希匹配、容器内 SELECT 1 成功、/api/v1/ready HTTP 200 ok；Postgres、API、console 均 healthy。
- 数据库数据卷保留。示例配置不变；SMTP 密码当前为空，模型用量 API Key 因需与下游网关同步而未轮换。
- 新密码只保存在本地 .env，未写入日志、文档或聊天；未运行完整测试套件。

## 2026-10-09 · 管理台响应式与主题走查

- 修复应用和模型管理页的表格最小宽度传播问题，避免宽表格撑开整个桌面/手机视口；将深色表格背景、空状态说明和滚动条配色统一到管理台主题。
- 浏览器复核：1680px 桌面应用页与 390px 手机应用/模型页的整页横向溢出已消失，表格保留卡片内横向滚动；检查浅色/深色空状态和窄屏导航。
- 验证：Vite production build 通过（3205 modules，入口 382.49 KB / gzip 118.64 KB）。`npm run build` 中 `vue-tsc -b` 因 Vue 导入类型缺失失败；没有联网重装依赖。未运行创建/修改/停用等管理操作。
- 限制：模型页请求期间出现 HTTP 500 提示，失败接口未定位；当前会话无法启动系统 Docker CLI 读取容器日志。主题编辑器因无已登记应用未验收。
- 同步 UI 走查、前后端 README、根 README、PRD 和 `iam-project` Skill。

## 2026-10-09 · UI 走查复核与管理目录错误修复

- 后端租户目录路由补齐 SQLAlchemy `func` 和 `TenantMembership` 导入，修复此前导致管理页请求失败的 500。浏览器复核返回 1 个租户、2 个成员；模型目录正常为空态，不再弹出 500 提示。
- 前端 `App.vue` 为共享租户/应用/角色字典加载增加并发去重和失败后导航重试；用户列表显示 2 个账号，“新建用户”和“新建模型”入口均已启用。未提交创建、编辑或权限更改。
- Vite production build 通过（3205 modules，入口 382.70 KB / gzip 118.73 KB）。`vue-tsc -b` 仍因本机 Vue 类型声明依赖链解析失败；无可用 Python 解释器，未执行后端测试。
- 更新 UI 走查、前后端 README、根 README、PRD 与项目 Skill。登录主题编辑器仍因没有应用记录而未验收，中间尺寸断点仍待检查。

## 2026-10-09 · 恢复前端类型检查并锁定镜像依赖

- 将 pnpm 的 `publicHoistPattern` 放入 `frontend/pnpm-workspace.yaml`，使 Windows pnpm Junction 安装能解析 Vue runtime/compiler 和 CSS 类型；使用冻结离线安装重建依赖链接，未下载包。
- 修正 `AuthEntry.vue` 可选标题颜色 style 的 Vue 类型；完整 `npm run build` 通过，含 `vue-tsc -b` 和 Vite production build（3205 modules，入口 382.70 KB / gzip 118.73 KB）。
- 前端 Dockerfile 现在复制 `pnpm-lock.yaml` 并使用 `pnpm install --frozen-lockfile`，避免镜像构建使用浮动依赖。Docker 镜像未在本机执行构建；后端 88 个文件 AST 解析通过，但本地 Python 缺 FastAPI/SQLAlchemy，后端 unittest 未运行。
- 同步 PRD、根/前后端 README、UI 走查、运维记录、待提供配置清单及 `iam-project` Skill。


## 2026-10-09 · 管理台 UI 主题细节修复

- 工作台正常状态徽标使用绿色；服务异常仍使用警示色。
- 外观偏好弹层标签和说明改用主题次级文字色，字号由 9–10px 提升至 11px。
- 以管理员浏览器只读复查平台核心管理页面与浅/深主题；前端 `npm run build` 通过（3205 modules）。窄屏、租户管理员页面及真实登录主题编辑预览未验收。


## 2026-10-09 · 后端集成测试夹具与回归验证

- 应用更新集成测试现在构造租户成员、应用范围角色以及管理/密钥轮换权限，符合线上共享授权评估器的当前规则；密码重置邮箱夹具改用标准验证域名。
- 在迁移至 Alembic 当前 head 的隔离 PostgreSQL 临时库运行完整后端 unittest：109/109 通过，0 失败、0 跳过。临时数据库已删除，开发库未修改。

## 2026-10-09 · 修复生产预检的 Windows Docker CLI 解析

- 生产预检脚本新增 `-DockerPath`，默认解析真实 `docker.exe`，规避 Windows App Execution Alias 遮蔽 Docker Desktop CLI。
- PowerShell Parser 检查通过；生产 Compose 使用 `.env.production.example` 执行 `config --quiet` 通过。
- 未运行完整预检：缺少本机 `.env.production.local` 和 `caddy:2-alpine` 镜像。未启动生产服务、连接数据库或执行迁移；详情见 `docs/部署与运维.md`。

## 2026-10-09 · 增加 PostgreSQL 备份工具

- 新增 `deploy/backup-postgres.ps1`，支持开发/生产 Compose 配置、指定环境文件与主机归档目录；输出 custom-format dump 和 SHA-256 sidecar，并清理容器临时归档。
- `-ValidateOnly` 会检查 Compose 展开、容器内数据库认证和 `SELECT 1`，不导出数据；在当前开发 Compose 上执行通过。
- 没有创建或复制数据库归档。脚本不做加密、自动调度、异地备份或恢复演练；按 `docs/部署与运维.md` 确认 RPO/RTO、保留周期和责任人。

## 2026-10-09 · 校正当前迁移与业务数据范围状态

- 更正接入计划中的过期开发库迁移状态，并在根 README 与 PRD 顶部记录当前运行、测试及未完成的业务接入边界；历史运行记录保留并标明为历史快照。
- 复核 Knowledge Base 当前源码：控制面在线 IAM 判权仍有效，但 helper 使用 `include_data_scope=false`，文档/修订/分块模型缺成员 owner 与组织字段。同步到 PRD 和待提供清单，避免把应用级隔离误报为行级授权。
- 本轮只读 `alembic current` 与 `alembic heads` 均返回 `0021_resume_wallet_perms (head)`；API readiness HTTP 200，三个开发容器 healthy。

## 2026-10-09 · 修正审计日志日期筛选标签布局

- 管理员桌面浏览器检查工作台、应用目录、登录主题空状态和审计日志时，发现日期字段标签被压缩成竖排；改为固定标签列和可伸缩日期输入列，页面复核后标签保持单行。
- 前端 `npm run build` 通过（Vue 类型检查、3205 个 Vite 模块）。本轮未检查窄屏或已创建应用后的主题编辑/发布流程；未修改后端或管理数据。

## 2026-10-09 · 管理台窄屏表格复核与修复

- 在 503×871 管理员浏览器视口只读检查平台工作台、租户、应用、用户、邀请、用户组、组织、角色、权限、授权模拟、模型目录/用量、登录主题空状态和审计日志。角色表格 410px 固定操作列遮挡全部可见字段；应用、用户组和应用角色表格也被宽固定操作列压缩首屏数据。
- 这些宽操作表格在 650px 以下改为随表格内部横向滚动，角色/应用/用户组页复核后首屏标题恢复可见，页面没有横向溢出。应用创建弹窗可滚动到取消/保存操作；只打开并关闭，未提交。
- 修正授权模拟资源 ID 的 `maxlength` 字符串类型告警，并将其余 Vue 数值 `maxlength` 属性绑定为 Number。浏览器日志只保留修改前的告警记录，修复后重新打开授权模拟页没有新增告警。
- `frontend` 执行 `npm run build`：`vue-tsc -b` 与 Vite 成功，3205 modules，入口 382.70 KB / gzip 118.73 KB。无 Python/API/数据库变更。
- 仍待验收：390px、768/1024px 中间视口、租户管理员专属页、公开认证页、已创建应用后的登录主题编辑/发布。结论为部分验证，详见 `docs/验收记录.md`。

## 2026-10-09 · DeerFlow OIDC UserInfo 主体校验

- 修复 DeerFlow OIDC UserInfo 缺失 `sub` 时仍可能覆盖已验签 ID Token 邮箱资料的问题。UserInfo 必须携带与 ID Token 相同的 subject，否则被丢弃并回退至签名 ID Token claims。
- 新增缺失、空值、不匹配与匹配成功回归；DeerFlow `test_oidc_auth.py` 通过 20/20。仅改 DeerFlow 中此前干净的 OIDC 服务和测试文件；该仓库其它大量未提交改动未动。
- DeerFlow IAM token/tenant vault、Gateway 中央权限和真实环境联调仍未完成。IAM 后端、本机 Docker/localhost 状态本轮无法重新验证；此前的 readiness 与完整测试结果仍作为有日期的历史核验。
- 复核并校正 PRD、架构、接入计划、用户清单与 `iam-project` Skill 中仍称本地迁移停在 `0016` / `0017`–`0021` 等待授权的旧状态；旧环境记录保留为带日期历史快照。

## 2026-10-09 · 同步注册与联调验证记录

- 校正用户清单中 DeerFlow OIDC 回归仍未执行的旧记录：mock `test_oidc_auth.py` 已通过 20/20；补充 TypeScript 授权/OIDC 测试 14/14 和 strict TypeScript 检查结果。
- 根 README 将开发库状态更新为源码 head `0025_registration_role_snapshot`、开发库 `0021_resume_wallet_perms`、readiness `503 database_migration_pending`；明确 migrations `0022`–`0025` 尚未应用到开发库。
- 架构文档将“Docker Engine 当前不可访问”改为准确区分：本轮只读 Docker Desktop 检查成功，真实归档恢复演练仍待受保护备份文件；没有执行数据库恢复或迁移。
- 本轮只修正文档；未改业务代码、未运行测试、未写入数据库。

## 2026-10-09 · DeerFlow OIDC 服务端 token 回调契约

- `OIDCService.authenticate_callback()` 现返回 `OIDCAuthenticationResult`，将已验证身份与 access/refresh token、有效期元数据分开；敏感字段与整个认证结果的 repr 均脱敏。Gateway 登录路由只读取身份用于本地开户。
- 在 DeerFlow Gateway `AGENTS.md` 固化 token 不得进入浏览器、日志或 Agent run config/checkpoint 的约束；将当前代码边界同步至 PRD、架构、接入计划、待提供清单、前后端 README 和项目 Skill。Token 尚未加密入库、轮换或提供给 IAM Gateway 授权；没有把 token 写入浏览器或 Agent run config。
- 新增 OIDC 回归断言验证 token/lifetime 被保留供后端 vault、对象 repr 不含 token；`test_oidc_auth.py` 22/22 通过，三个变更 Python 文件 Ruff 检查通过。没有修改 IAM 数据库或迁移。
## 2026-10-09 · Knowledge Base IAM 文档级数据范围源码闭环

- Knowledge Base 新增可信 IAM tenant/owner/organization 归属字段与源码 migration `0025_document_iam_data_scope`；控制面文档、修订、片段、摄取/同步任务、操作证据/审计和混合检索加入显式数据范围过滤。集合归档若触及当前成员不可见文档则拒绝；重试和幂等键绑定当前 IAM 身份。运行面保留应用 API Key，并在启用 IAM OIDC 时额外要求用户 Bearer token。
- Knowledge Base 定向回归 **35/35 通过**，改动文件 Ruff 检查通过。没有对 KB 目标数据库执行迁移；隔离 PostgreSQL 跨成员负向测试、真实 IAM issuer/浏览器联调、旧数据归属治理和 collection 聚合元数据范围仍需验收。
- 同步 Knowledge Base README/API/项目重写执行书，以及 IAM PRD、集成计划、用户清单和项目 Skill。DeerFlow data_scope、上游撤销、跨产品真实环境联调与生产部署仍在剩余范围内。
## 2026-10-10 · DeerFlow Provider 分发与项目本人范围查询

- 将 IAM Python authorization client 与 DeerFlow Provider 放入 DeerFlow `deerflow.authz` 包，修复 Gateway route/model/sandbox/Agent 对外部 Provider 结果的结构兼容验证；更新 DeerFlow 示例 config，保留 Central IAM 默认关闭与 fail-closed。
- DeerFlow 项目列表、详情、项目会话列表现在请求 `projects:read` data_scope，并将实际查询显式限制为当前本地用户 owner。仅映射 IAM verified OIDC subject 的本人范围；租户/组织范围在业务归属列和 subject→local user 映射完成前拒绝。
- IAM 新增源码 migration `0026_deerflow_permission_catalog`，登记项目、会话、运行、模型、工具和沙箱权限码；不建角色、不授权、不自动执行数据库迁移。
- DeerFlow 定向 pytest **48/48** 通过，Ruff 改动文件检查通过。未连接真实 IAM、未执行 IAM/DeerFlow 数据库迁移、未做浏览器 OIDC 验收；未更改 IAM Vue 页面。
- 同步更新 PRD、整体/前后端说明、架构、接入计划、待提供清单、DeerFlow 中英文后端 README 和 `config.example.yaml`。AI Resume/Knowledge Base 历史接入代码清理仍待完成；项目 Skill 尚未同步。

## 2026-10-10 · 收敛为 DeerFlow 单系统试点并清理旧集成

- 按用户确认，仅保留 DeerFlow 作为首个业务系统试点；在 AI Resume 与 Knowledge Base 中删除 IAM/OIDC 登录与身份绑定、中央鉴权/data_scope 调用、专属配置、IAM-only ORM/migrations/tests、前端入口和旧 OpenAPI 契约。保留两套产品本地认证、成员/grant 与其它业务改动，不做全仓 restore/reset。
- Knowledge Base 重导出 OpenAPI JSON 并同步生成 TypeScript 声明；删除 5 个 IAM 路由、5 个 operation type 和 7 个终端用户 IAM header。未读取或修改真实 `.env`，未运行产品数据库迁移。
- 验证：Knowledge Base Python 源码/测试 107 个文件 AST 解析通过；不连接数据库的成员授权/API Key 回归 8/8；contracts typecheck 与 Vite production build（1652 modules）通过。
- DeerFlow 代码本轮未修改；其既有定向测试和 Ruff 结果仍按之前日志记录。真实 IAM/OIDC、IAM/DeerFlow 目标库迁移和跨资源浏览器验收仍待部署方提供环境、备份与测试身份。
- 同步 README、前后端技术说明、架构、PRD、接入计划、待提供清单和 `iam-project` Skill；Knowledge Base 项目重写执行书已追加清理说明。
## 2026-10-10 · DeerFlow 全局会话搜索数据范围闭环

- `POST /api/threads/search` 在读取线程仓储前调用 IAM `threads:read` data_scope 校验；校验不可用时以 503 失败关闭，不执行查询。结果继续与 DeerFlow 当前用户 owner 条件求交。
- 新增范围先于 owner 查询、IAM 范围不可用时不查询两项回归；`tests/test_threads_router.py` 全量 **133/133 通过**，改动路由与测试文件 Ruff check/format 通过。首次运行被 Windows 默认 pytest 临时目录权限阻断，改用工作区内新建临时目录后通过；仅有 Starlette/httpx 弃用告警。
- 进一步把 IAM data_scope 检查加到 `require_permission(..., owner_check=True)` 的线程/运行读取路径：本地 owner 校验通过后、业务 handler 之前校验 `threads:read` / `runs:read`，覆盖按 ID 获取详情及运行子资源，避免绕过集合查询的范围策略。`tests/test_auth.py` 与 `tests/test_threads_router.py` 合计 **228/228 通过**，三个改动 Python 文件 Ruff check/format 通过。
- 同步更新整体 README、PRD、业务接入计划、前后端手册和 `iam-project` Skill；本轮未更改 IAM Vue 页面、未连接或迁移 IAM/DeerFlow 数据库，也未读取或修改外部 `.env`。
- 仍待 DeerFlow 文件与其它资源范围、tenant/organization 数据映射、正式权限映射、目标库 migration `0026`、镜像分发、真实 IAM/OIDC/浏览器验收及上游 token revoke。

## 2026-10-10 · DeerFlow IAM data_scope 互操作回归

- 追加运行 `tests/test_iam_provider_interoperability.py`，中央 IAM provider 的 data_scope 互操作用例 **6/6 通过**。与前述 `test_auth.py`、`test_threads_router.py` 的 228/228 合计为本轮 234 项通过。
- 使用隔离工作区临时目录运行；没有连接真实 IAM、产品 PostgreSQL 或读取密钥，也没有执行迁移。
## 2026-10-10 · DeerFlow Agent 与记忆权限目录

- IAM 新增 append-only migration `0027_deerflow_resource_permissions`，登记 `deerflow.agent.read/write/delete/admin` 与 `deerflow.memory.read/write/delete/admin`；不自动 grant，也未迁移数据库。
- DeerFlow 自建 Agent API 增加读写删权限及匹配的本人 data_scope 检查；完整 Agent 响应的写接口额外要求 read。部署共享 `USER.md` 使用独立 `agents:admin`，PAT 路由不包含该接口。
- 修正 DeerFlow IAM 示例使用 origin，补齐 Agent/记忆 permission map。DeerFlow adapter/client 已在 harness 包内；目标镜像构建、部署和在线联通仍待验收。
- 最近只读 Docker 检查：API unhealthy、console/PostgreSQL healthy；PostgreSQL revision `0021_resume_wallet_perms`，IAM 源码 head `0027`。数据库迁移和真实 IAM/browser E2E 仍待维护窗口与外部配置。
- 授权、PAT、/auth/me 与 Agent 路由回归 **82/82 通过**；7 个修改 Python 文件 Ruff check 与 format 通过。



## 2026-10-13 文档合并归档：产品与交接旧快照

以下内容从旧产品需求/交接文档移入，仅保留历史追溯。现行规则、状态与任务以 docs 中的五份中文文档为准；旧段落中的“本轮”“当前”“已完成”均指原记录日期。

<details>
<summary>产品文档前置实施记录（原有顺序）</summary>

**2026-10-13 DeerFlow B04 更新：** 最近完整离线后端快照（本轮 Studio 测试修正前）为 17,004 passed、186 failed、349 skipped、3 deselected、5 errors；其后 Windows Studio routes 聚焦模块 **6 passed**，Ruff check/format 通过。查明此前 5 个 setup error 的根因：Studio 子进程沿用 GBK 默认编码，依赖读取 UTF-8 OpenAPI 文件失败；测试子进程现显式 `PYTHONUTF8=1`，诊断日志使用容错解码，持久化用例等到服务运行期 flush 后再模拟重启。完整套件尚未重跑，旧快照仍有 191 个未通过项；缺 `uv`、`WinError 10106` 和其他全量失败仍待分组处理。测试临时目录已清理；未做 migration、真实 IAM/Provider E2E 或 quota enforcement。

**2026-10-12 DeerFlow Provider 路径审计：** 对当前仓内 `backend/app` 与 `backend/packages/harness/deerflow` 的内置生产 Python 入口做静态搜索：共享工厂模型继承 `BaseChatModel` 并触发 LangChain 用量 callback；Gateway 单次模型端点绑定单次计量 scope；DeerMem 的直连 `init_chat_model()` 使用专用 hook；Codex Responses Provider 由共享工厂构造并回传 usage metadata。外部扩展动态加载的 Provider 未被此次搜索穷尽。用量 `request_id` 按一次 LangChain invocation 生成；Codex 内部重试不单独计量，仍须对照 Provider 计费语义。该项不代表 live IAM/Provider 验收；本轮未运行测试或数据库操作。

**2026-10-12 DeerFlow 后台计量补齐：** DeerMem 的 debounce/timer 后台模型调用现在在 provider invoke 前通过 Gateway hook 创建一次性 IAM usage callback，走现有 reservation、settle/report 与 SQL outbox；调用结束即关闭，不把 token/capability 放入排队上下文。`model_usage.enabled=false` 时保持既有不计量行为；启用时 admission 失败即不外呼。关联现有回归 20/20、Harness boundary 1/1 通过。真实 IAM/Provider、PostgreSQL/重启恢复和完整 DeerFlow 全量验收仍未完成；配额 enforcement 保持关闭。

**2026-10-12 DeerFlow 权限映射状态：** 源码层已有权限码与 adapter 配置样例；本轮形成静态映射和最小角色配置建议，详见[单试点接入计划](docs/技术架构与接入.md)。真实 tenant/application/provider、模型 UUID、工具 grants、存量身份冲突盘点仍待部署输入；PAT 不具备当前 Central IAM adapter 要求的 OIDC vault identity；另发现 IAM catalog 的 `deerflow.model.use` 未被当前样例使用，`model:use` 实际映射到 `model.invoke`，两者不可混授。源码映射不代表运行库迁移、角色授权或 E2E 完成。

**当前执行计划（2026-10-12）：** 后续任务、依赖、完成条件和阻塞统一维护在 [当前进度与后续改造交接](docs/项目总览与进度.md)，每轮同步更新；本 PRD 保留需求与验收标准。范围仍为 IAM 平台 → DeerFlow 唯一试点，首阶段 owner-only、本地登出；组织共享/其它产品后续评审。本轮补齐 DeerFlow 静态权限映射并完成后台计量接线及关联回归 20/20；A01 只读复核 Console 200、API readiness 503、Docker 容器和数据库 revision `0021_resume_wallet_perms`；未迁移或做真实 E2E。

**2026-10-12 迁移风险与发布门禁：** 审阅源码 `0022–0031`，本轮没有执行数据库变更。ToC 注册列默认 disabled，migration 不创建用户或角色授权；从最近已知 `0021` 连续迁移时，新增注册挑战表为空，后续清理旧挑战预计无行可删，但需运行前对当前 revision/数据量做只读确认。`0022` downgrade 删除注册表，`0024` 移除密码摘要列且不可恢复，`0031` 有人工核对账目时拒绝 downgrade；回滚路径应以受保护备份恢复为准。后续 A01 已恢复 Docker CLI，当前 IAM revision `0021_resume_wallet_perms`、API readiness 503；没有执行 migration。

**2026-10-12 测试临时产物清理：** 已删除并核验 7 个过期 pytest 临时根目录；测试源码保留，该次清理没有运行测试。

**2026-10-12 部署验证状态：** Console HTTP 200，API readiness 响应 `503 database_migration_pending`。该段为 Docker CLI 恢复前快照；后续 A01 已只读确认开发库 revision `0021_resume_wallet_perms` 和 readiness 503。迁移仍须完成受保护备份并取得明确授权。

**2026-10-12 DeerFlow 项目文档长路径修复：** Windows 下物理路径超出 240 个 UTF-16 单元时使用短文件名保存原始内容，同时保留用户原文件名、下载 MIME 和可转换文件后缀；历史目录仍可读取。项目/文档/线程/运行四组路由回归 **225/225**，4 个相关 Python 文件 Ruff check/format 通过；使用短 Windows 临时根目录，测试产物已删除。未改 IAM 前端、schema、migration 或开发数据库。下文 2026-10-10 关于 255-byte 文件名失败的记录是当时快照，问题现已修复。完整后端全量和真实 IAM/Provider E2E 仍未验收。

**2026-10-12 本阶段数据范围决策与验收校正：** 用户确认 DeerFlow 第一阶段的项目、线程、运行、文档均为本人私有，不开放同租户或组织共享。业务查询须同时通过 IAM owner/self data_scope 和 DeerFlow 本地 owner 条件；tenant/organization 范围在获得新决策、可信归属模型、回填方案和迁移前保持 fail closed。DeerFlow IAM/OIDC/模型/vault/data_scope 定向回归 169/169 通过（隔离/mock，非真实 IAM E2E）。当前 IAM Console 200、API unhealthy/readiness 503 `database_migration_pending`；开发库 `0021_resume_wallet_perms`，源码 head `0031_model_usage_reconciliation`。备份只读预检通过，没有生成归档或写库。Windows 全量测试的一次长路径运行 16,770 passed、422 failed、345 skipped、3 deselected；一个代表失败因深层 Windows 临时路径超过限制，缩短路径后通过该用例；短路径全量运行又于 34% 因 `WinError 10106` 终止。故全量套件和在线部署仍未验收，不能把全部失败归因于环境。

**2026-10-12 DeerFlow 模型授权补齐：** Gateway run 通过统一模型工厂创建的每个 Agent 模型档案，在每次 LangChain provider 调用前校验该档案的 `model:use`；标题、摘要、评估器和子 Agent 等辅助调用沿用相同门禁。DeerMem 后台模型另在外呼前实时重载用户与 vault 会话，核验记忆读/写范围及精确模型档案权限。Gateway 将回调注入 Harness，授权错误失败关闭。定向回归 28/28、Harness 分层边界 1/1 通过。修复前全量后端为 16,750 通过、442 失败、345 跳过、3 deselected；阻塞 I/O 为 116 通过、26 失败、1 跳过。web-fetch 的 22 项链接目标失败已在后续 Python fallback 修复中解决，现有回归 50/50 通过；随后 Windows 全量长路径运行 16,770 通过、422 失败、345 跳过、3 deselected；短路径全量重跑约 34% 因 WinError 10106 中断。全量仍未验收，剩余失败尚未完整归因。临时测试产物已清理。无 IAM migration/数据库变更，真实 IAM/Provider E2E 待完成。

**2026-10-12 DeerFlow 离线提取兼容性修复：** Node/Readability.js 不可用时，Python 回退提取保留文章正文中的安全链接和图片目标，同时剔除脚本、嵌入内容及不安全 URL。既有 web-fetch 回归修复后 50/50、Ruff 检查通过。修复前的全量测试快照仍为 442 项失败，修复后尚未重跑全量；其余失败需继续归因。

**2026-10-11 管理台与账目分页：** 用量账目和待核对队列均使用后端 total/offset/limit 分页及稳定排序，并发处置后以 409 为准刷新。`verify-local.ps1` 的隔离库迁移至 `0031_model_usage_reconciliation` 后，完整后端套件 **169/169** 通过；Vue 检查与 Vite production build（3205 modules）通过。浏览器登录仍受开发库 readiness `database_migration_pending` 阻断；开发库未迁移，真实 IAM/Provider E2E 尚未完成。

**2026-10-11 部署验收进度：** 备份只读预检通过，未生成归档或写入开发库；开发库 revision `0021_resume_wallet_perms`、源码 head `0031_model_usage_reconciliation`，readiness 503。隔离 PostgreSQL 全量套件 169/169 通过，Vue 检查和 Vite production build（3205 modules）通过。端到端试点仍需受保护备份、开发库迁移授权、DeerFlow 权限映射、角色 grant 和 owner/self 范围。登出策略已确认只清理本地 vault session。

**2026-10-11 webhook 未验证开关生产防护：** DeerFlow GitHub webhook 的显式未验证开关在 production 环境被强制忽略；没有 webhook secret 时不挂载入口，运行时也拒绝请求。浏览器与 webhook 完整聚焦回归 76/76、Ruff 通过；公网 URL SSRF 用例固定 DNS 测试结果，无需外网。本轮没有修改 IAM UI 或数据库。

**2026-10-11 首个试点浏览器实时流授权：** DeerFlow 的实时浏览器 WebSocket 在线程仓储和浏览器会话访问之前校验 `threads:read`、`threads:write` 与两项匹配的 owner/self data_scope，并继续要求本地线程 owner 精确匹配。没有新增权限码或 migration；IAM 映射与角色 grant 仍需部署管理员确认。浏览器与 webhook 合并回归 76/76、Ruff 通过；公网 URL SSRF 测试使用固定 DNS，真实 IAM/WebSocket E2E 未完成。本轮未改管理台界面、数据库或本地登出策略。

**2026-10-11 DeerFlow 个人偏好授权闭环：** 偏好读取和更新现由独立 `preferences:read/write` 路由权限控制；IAM 模式下同时校验已验证主体对应的 owner/self data_scope，且必须先于本地偏好仓储访问。IAM migration `0030_deerflow_preference_permissions` 只登记权限码，不自动 grant。DeerFlow 定向测试 19/19、Ruff check/format 通过；当前开发库仍为 0021、readiness 503，真实 IAM 与浏览器链路尚未验收。

**2026-10-11 DeerFlow 部署闭环状态：** dev Gateway 镜像打包及容器内 IAM adapter import 已通过；default runtime target 仍未生成。当前 locked uv dry-run 通过且 uv.lock 未变化，但 Docker Hub/GHCR 的 Python/uv 基础镜像元数据/匿名 token 请求返回 EOF。网络可达或配置镜像源后，需重建 runtime 镜像并启动服务完成 readiness、OIDC 与角色授权 E2E。

**2026-10-11 部署打包核验：** DeerFlow 根 .dockerignore 已补齐运行配置排除规则，避免 Docker build context 携带 config.yaml、extensions_config.json、备份文件和 .env* 变体。Docker daemon 最终生成 Gateway dev 镜像 iam-deerflow-package-check:20261011（sha256:f2203cacf14d7a324dadcaa4d803145fcd9fd48129a9e9f15751e4beb4947456），一次性容器内 uv run 成功导入 IAM adapter。此验证未启动完整服务或连接数据库，真实登录和发布仍待验收。

**2026-10-11 DeerFlow 数据范围模型核对：** 当前项目、线程、运行、文档资源按本地 user_id 归属，核心资源表没有可信 tenant_id/organization_id；IAM tenant_id 目前只在 vault/用量数据中。首个试点继续使用 owner/self 限制，tenant/organization scope fail closed。组织共享需先确定资源级共享规则、可信关系字段和历史数据回填策略，再进行 schema/migration 与跨组织隔离验收。

**2026-10-11 DeerFlow 异步授权验收：** IAM SDK provider 合约 22/22、DeerFlow IAM provider 互操作文件 12/12 通过，包含异步 authorize、run capability refresh 和 4 项 async data_scope 用例。结果来自 mock/隔离测试，不代表真实 IAM、数据库迁移、角色 grant 或浏览器端到端已验收。

**2026-10-11 运行验收与产品决策：** API readiness 仍为 503 database_migration_pending，开发数据库停在 `0021_resume_wallet_perms`，源码迁移 head 已推进至 `0031_model_usage_reconciliation`。只读备份预检通过，未生成归档或修改数据库；开发库迁移须待受保护备份、影响复核和明确授权。DeerFlow 登出采用本地清理，`/auth/logout` 不向外部 OIDC issuer 发送 vault access/refresh token。

**2026-10-11 登录页就绪状态改造：** 当只读 readiness 探针返回数据库待迁移/不可用时，登录、注册、密码重置、邀请接受和 OIDC 授权提交均禁用；状态提示给出管理员备份、审阅、迁移后的重查路径。浏览器确认登录按钮禁用，Vue 类型检查与 Vite 生产构建通过。后端探针仍为只读，开发库没有迁移，当前 readiness 仍为 503。

**2026-10-11 DeerFlow 模型用量核对决策：** 用户选择保留 Provider 完成后未收到结算的预留，禁止自动按预留上限结算或自动释放。IAM 新增管理员待核对 API/页面和 `0031_model_usage_reconciliation`，可依据 Provider 记录补记用量，或明确确认 Provider 从未被调用后释放；理由与决定写审计。该流程不能自动还原崩溃时丢失的真实 Token，需人工核对。0031 已由隔离 PostgreSQL 全量套件验证（169/169），Vue 检查与 Vite production build 通过；开发库仍为 `0021`，未升级。真实 IAM/Provider 仍待联调，配额拦截继续关闭。

**2026-10-11 开发环境数据库版本复核：** 最近只读查询确认开发库 revision 为 `0021_resume_wallet_perms`，当前源码 head 为 `0031_model_usage_reconciliation`；API `/api/v1/ready` 最近返回 503 `database_migration_pending`。当前 schema 尚无 ToC 注册 challenge 表；因此 0024/0025 对旧 challenge 的更新在此库不会影响现有记录。源码 migration `0022`–`0031` 尚未执行；恢复服务仍需受保护备份、审阅影响和明确授权。

**2026-10-11 DeerFlow Console 数据授权：** 聚合仪表盘按实际返回资源执行最小授权：`/api/console/stats` 需 `runs:read`、`threads:read`、`agents:read` 及各自 owner/self data_scope；`/api/console/runs` 需 runs 和 threads 的读取权限/范围；`/api/console/usage` 需 runs 的读取权限/范围。所有判定先于 SQL session 获取，既有 DeerFlow 本地 owner 过滤保持不变。新增权限缺失、拒绝先于数据库访问和成功 scope 调用回归，console 路由共 **25/25 通过**，Ruff check 通过。前端未改、IAM 开发库未迁移、未授予角色或运行真实 IAM/OIDC/浏览器验收。

**2026-10-11 DeerFlow memory worker 提交前复核：** after-agent/summarization 被动写入在入队后、`apply_changes/save` 前重载 active 本地用户与匹配的 OIDC vault session，再校验 `memory:read/write` 精确 owner/self data_scope；revision 冲突重试每次重查。队列只传 user/thread/agent 标识，不保存 token/capability；身份、授权服务、scope 或 Gateway loop 不可用及超时均拒绝写入。Updater、data-scope 与 commit callback 回归 **109/109 通过**，6 个 Python 文件 Ruff lint/format 通过。真实 IAM role grant 与浏览器验收尚未完成。

**2026-10-11 早期本地验收快照（已更新）：** 本条记录的是源码 head 0030 时的 161/161 结果；之后 `0031_model_usage_reconciliation` 已在隔离 PostgreSQL 全量验证，后端完整套件 169/169 通过，Vue 检查与 Vite production build（3205 modules）通过。备份预检和生产 Compose 示例解析通过，未生成归档。临时 `iam_test_*` 数据库已清理；开发库仍停留在 `0021_resume_wallet_perms`，API readiness `503 database_migration_pending`。最新隔离结果不代表真实 IAM/OIDC、浏览器、DeerFlow 部署或授权角色验收。

**2026-10-10 技能更新响应授权：** 自定义技能更新和回滚响应包含完整正文，必须在副作用前同时校验 Central IAM skills:read/read-scope 与 skills:write/write-scope。跨切片组合回归 141/141 通过；线上权限配置仍未验收。全量后端隔离验证见上方 2026-10-11 记录。

**2026-10-10 跨切片授权验证：** DeerFlow connectors、stateless run、Agent 兼容路由、skills、MCP、subagents 与 channel worker 管理联合定向回归 138/138 通过（Starlette/httpx 1 条弃用警告）；8 个 DeerFlow Python 改动文件 Ruff/format 检查通过。未迁移目标数据库，也未执行真实 IAM/OIDC 浏览器验收。

**2026-10-10 DeerFlow IM worker 管理授权：** GET /api/channels 的部署级运行状态要求 channels:read；POST /api/channels/{name}/restart 要求 channels:admin 与 DeerFlow 本地管理员。此权限不与个人 channel 连接的 self data_scope 混用。技能、MCP、托管子 Agent 与频道管理相关组合回归目前 81/81 通过。

**2026-10-10 DeerFlow 管理资源授权补齐：** 技能目录/本人自定义技能增加 read/write/delete 权限和 self data_scope；部署级技能开关/缓存刷新、托管子 Agent CRUD、MCP 配置读取/变更/缓存刷新使用独立 admin 权限，并继续要求本地 Gateway 管理员。子 Agent prompt 只有同时满足本地管理员和 Central IAM admin 时才返回。migration 0029_deerflow_agent_extension_permissions 只登记 7 个目录权限码、不授予角色。定向回归 79/79 与 Ruff 检查、格式检查通过；真实部署迁移和授权尚未执行。

**2026-10-10 DeerFlow 连接器授权补齐：** IM 连接列表/状态和个人连接变更分别受 deerflow.channel.read/write 保护，个人操作执行本人 data_scope；Lark 状态、配置与 OAuth 流程受 deerflow.integration.read/write 保护并校验本人范围。Lark 安装及部署级 runtime config 还需对应 *.admin 权限和 DeerFlow 本地管理员。IAM migration 0028_deerflow_connector_permissions 只注册 6 个权限码、不发放 grant。57 项相关 Gateway 回归与 Ruff/格式检查通过；迁移、生产角色授权和在线 E2E 未验收。

**2026-10-10 无状态运行授权补齐：** DeerFlow `POST /api/runs/stream` 与 `/api/runs/wait` 在调用统一运行创建前校验 Central IAM `runs:create` 数据范围；现有 `start_run` 本地线程 owner 检查继续负责拒绝他人线程。旧兼容 `/api/assistants/*` 的列表、详情、graph、schemas 读取也统一检查 `agents:read` 和本人 data_scope，避免绕过正式 Agent API。此次仅改 Gateway 服务端，无新增配置；新增 stateless-run 数据范围拒绝及 assistants 兼容路由权限回归后，Gateway 定向用例 28/28 通过，4 个改动 Python 文件 Ruff check/format 通过；真实 IAM/浏览器联调与数据库迁移未执行。

> **当前交付范围与运行基线（2026-10-11）：** 唯一正在验收的业务系统是 DeerFlow；AI Resume 与 Knowledge Base 的 IAM 专属代码、配置、migration、测试及登录入口已撤销清理，较早章节中的相关接入说明只保留作历史或后续规划，不代表当前仓库已有接入。IAM 源码 Alembic head 为 `0031_model_usage_reconciliation`，开发数据库仍为 `0021_resume_wallet_perms`；API readiness 为 `503 database_migration_pending`。`verify-local.ps1` 已将空隔离库迁移至 0031，后端完整套件 **169/169** 通过，Vue 检查及 3205 modules 的 Vite production build 通过；这不代表开发库已升级或真实 IAM/浏览器验收通过。数据库迁移须先完成受保护备份、迁移影响审阅和明确维护窗口授权。

**DeerFlow 模型与工具资源级授权（2026-10-10）：** 模型列表使用 `deerflow.model.list` 独立判权；模型调用映射到 IAM `model.invoke`，由部署端配置 DeerFlow `models[].name` 到同租户活动模型 UUID 的可信映射，未映射模型在访问 Provider 前拒绝。工具调用继续使用 `deerflow.tool.use`，IAM `resource_id` 绑定服务端工具名，可按工具授权；无 `resource_id` 的角色 grant 代表应用级通配授权。配置样例与 SDK 已加入映射支持，新增 4 项模型/工具回归及同步互操作选择共 8/8 通过；当日 4 项异步数据范围用例因 Windows venv event loop 挂起未完成；2026-10-11 用 DeerFlow Python 3.12.14 复验整文件 12/12 通过（mock）。真实 IAM 角色 grant、模型目录与浏览器调用仍待环境验收。

**DeerFlow 定时任务授权边界（2026-10-10）：** HTTP 任务路由在访问 owner-filtered 数据前校验 Central IAM scope：读 `threads:read`；创建 `threads:write` + `runs:create`；更新/暂停 `threads:write`；恢复/手动触发附加 `runs:create`；删除 `threads:delete`；历史 `runs:read`。调度器额外在 occurrence 入队前和队列启动前重载 active 用户与当前 grants/data_scope；Central IAM 模式仅从同一用户、OIDC provider、issuer、subject 的已存加密 session vault 解析短期 capability，并按 owner 语义将其传入 Agent run。缺少有效 session、账号停用或权限撤销会暂停任务、取消待运行 occurrence；手动触发返回 403/503。本人 data_scope 与 DeerFlow 本地 `user_id` owner 过滤共同约束。调度、token vault、路由与权限 resolver 定向回归 **126/126 通过**；开发库迁移与真实 IAM/browser E2E 尚未验收。

**DeerFlow 项目与文档数据范围补齐（2026-10-10）：** 项目创建/编辑/归档/恢复、文档上传/提升/恢复在写入前校验 `projects:write` 与完整响应所需的 `projects:read` 范围；文档删除、单项/批量永久清理与保留期清理校验 `projects:delete`；会话文件提升/挂载同时校验线程读/写范围。每次仓储变更显式绑定当前 DeerFlow 用户。项目、文档和回收站路由回归 **92/92 通过**，改动文件 Ruff 检查通过；本轮未修改 IAM 前端、未启动服务或迁移数据库。

**DeerFlow owner-bound 线程/运行变更（2026-10-10）：** 线程 `write/delete` 和运行 `create/cancel` 在本地 owner 检查后、业务 handler 前执行同权限 data_scope 检查；运行创建在生成 run ID 前校验，取消按已有 run ID 校验。鉴权回归 101/101 通过；相关线程/运行/反馈/文件/浏览器/MCP/项目资料路由选择 532 项通过，1 项公网 DNS 测试在断网容器中排除。线程数据写入继续受 DeerFlow owner 仓储过滤约束。其它 owner-bound 入口、跨租户/组织字段映射、真实 IAM 与浏览器验收待完成。

**待执行 migration 数据影响审查（2026-10-10）：** 只读审查 0024_tenant_registration_audience 的升级会清空并删除旧注册 challenge 的暂存密码摘要列；0025_registration_role_snapshot 会将所有未消费的旧邮箱 OTP challenge 标为已消费，用户需重新发起注册验证。该行为是迁移设计的一部分，执行前必须先完成受保护备份并取得明确维护窗口授权；本轮未执行 migration。

**本轮只读运行核验（2026-10-10）：** IAM Compose 的 API unhealthy、console/PostgreSQL healthy；IAM 开发库为 0021_resume_wallet_perms，源码 head 为 0027_deerflow_resource_permissions，宿主机绕过代理直连核验：console 5175 和 API 根路径 8002 均返回 HTTP 200；API /api/v1/ready 返回 503 database_migration_pending，API 容器因此 unhealthy。DeerFlow 开发 Compose 当前没有运行；根 .dockerignore 已排除 Python pytest/ruff/mypy/hypothesis 缓存，修复构建上下文读取 backend/.pytest_cache 被拒绝的问题；gateway dev 镜像 deer-flow-dev-gateway:latest 已构建成功，断网一次性容器成功导入 deerflow.authz.iam_deerflow、app.gateway.authz 与 app.gateway.routers.agents。源码 Alembic head 为 fd_0027_repair_run_change_seq（父版本为 0026_iam_oidc_token_vault），目标数据库版本尚未核验。本轮未启动服务、迁移数据库或修改环境凭据。
**此前隔离验证快照（2026-10-10，源码 head 0027）：** verify-local.ps1 的后端完整套件 161/161 通过；console 镜像内 vue-tsc -b 与 Vite production build 通过。更新的 0029 全量后端结果见本 PRD 开头。

> **DeerFlow Agent 权限补充（2026-10-10）：** 自建 Agent 管理接口要求 `agents:read/write/delete`，读写前执行 owner/self 数据范围检查并与 DeerFlow 本地用户归属求交；因创建/更新响应返回完整 Agent 定义，写接口也要求读取权限和读取范围。全局 `USER.md` 会注入本部署全部 Agent，改为独立 `agents:admin`，PAT 不可访问。IAM `0027_deerflow_resource_permissions` 追加 8 个 Agent/记忆权限码，不发放角色权限或 data_scope。样例 API origin 和路由 permission map 已修正；授权/PAT/`/auth/me`/Agent 定向回归 **90/90 通过**，8 个 Python 文件 Ruff check/format 通过。目标数据库仍为 `0021`，本轮未执行 migration。

> **DeerFlow 资源授权进展（2026-10-10 历史快照）：** 已覆盖项目、线程/运行直接读取、项目文档与内容、项目会话文件聚合、回收站和个人记忆数据。记忆 REST 路由要求 `memory:read/write/delete/admin`；所有返回完整记忆文档的接口（包含写入响应）在读取/写入存储前校验 `memory:read` data_scope，配置明细单独要求 `memory:admin`，PAT 只通过逐方法白名单访问。记忆/权限/PAT 回归 **118/118 通过**，Ruff check/format 通过。项目文档、promote/attach、回收站回归缩短 Windows 临时路径后 **72 通过、2 跳过**；当时 255-byte 文件名压力用例仍遇到 Windows `WinError 3`，该问题已于 2026-10-12 修复并通过 32/32 文档路由回归。该轮未迁移数据库；正式 permission map、跨 tenant/organization 查询和真实 IAM/browser E2E 仍待完成。

> **按 ID 读取的范围闭环（2026-10-10）：** DeerFlow 所有带本地 owner 校验的线程/运行只读路径也会在 handler 前请求 IAM `threads:read` / `runs:read` data_scope，直接按 thread ID 请求不会绕过列表范围策略。相关 `test_auth.py` 与 `test_threads_router.py` 合计 **228/228 通过**。正式 permission map、文件/其它资源、tenant/organization 范围和真实环境仍待完成。

> **当前接入核验（2026-10-10）：** 唯一活跃产品试点是 DeerFlow。项目列表/详情/项目会话读取在查询前请求 `projects:read`，全局 `POST /api/threads/search` 在查询前请求 `threads:read`；两者都与本地 owner 求交，IAM 范围不可用时失败关闭。DeerFlow `test_threads_router.py` 全量 **133/133 通过**，改动文件 Ruff check/format 通过。本文后续 AI Resume、Knowledge Base 接入内容为清理前历史记录，不能代表当前代码或验收范围。其它 DeerFlow 资源范围、tenant/organization 映射、目标库迁移、真实 IAM/OIDC 浏览器链路、镜像分发和上游 token revoke 仍待完成。

> **本轮实现与接入状态（2026-10-10）：** IAM 平台仍保留通用 OIDC、RBAC、资源授权、数据范围与 SDK；DeerFlow 是唯一活跃产品试点。DeerFlow 部分 Gateway/Agent 判权与项目本人范围查询已接入源码，真实 IAM、业务数据库迁移、跨资源/租户数据范围及浏览器验收仍未完成。AI Resume 与 Knowledge Base 的产品专属 IAM/OIDC runtime、环境配置、数据库 schema/migrations、测试、登录 UI 和生成 API 契约已在本轮清理；各产品的本地认证、成员授权和业务模块保留。Knowledge Base Python AST 107 个文件通过，非数据库回归 8/8、contracts typecheck 通过；Vite production build 通过（1652 modules）。未修改外部 `.env`，未迁移 IAM 或产品数据库。

> **交付阶段决策（用户确认，2026-10-10）：** 先交付并验收 IAM 平台自身，再只接入 DeerFlow 完成端到端试点；只有真实 IAM、业务查询隔离、目标库迁移与浏览器流程均通过后，才评估其它产品接入。AI Resume 与 Knowledge Base 的旧集成代码已从对应产品仓库移除，不作为当前接入验收范围。

> **DeerFlow 数据范围适配器更新（2026-10-10）：** IAM Python SDK 提供同步/异步 `resolve_data_scope`，基于经过验证的服务器端 subject/token 请求 `include_data_scope=true`，缺失授权或范围时失败关闭；启用资源 ID resolver 后，候选资源过滤逐项在线判权，不复用同权限码下其它资源的 allow。最新同步适配器回归 18/18、IAM 授权客户端回归 11/11；本轮修改后未运行 Ruff，异步用例未验证；2026-10-11 使用 DeerFlow Python 3.12.14 复验 SDK 22/22、互操作 12/12（mock）。该能力目前仅返回已验证范围，DeerFlow 资源仓储尚未把 tenant/self/organization 条件应用到项目、会话、文件查询，真实 IAM/目标库仍未验收。

 > **DeerFlow Gateway 与 Agent IAM 授权（2026-10-09，最新）：** 显式启用 IAM vault 且配置 `requires_iam_identity` Provider 后，Gateway 路由权限、模型目录与 sandbox-sync 会通过已验签本地 session `sid` 取回 vault token；请求和 Agent run 在 access token 临近过期时通过 vault 行锁执行 refresh rotation。Agent run 通过不可序列化的 `RunContext.authorization_credentials` 接收 repr 脱敏凭证，仅 OIDC subject 相同的 Principal 可将它用于模型选择、工具过滤及每次工具执行时的在线 IAM 检查；异步授权最长每 2 秒复核一次 vault session，登出删除行后 capability 清空并拒绝后续调用。凭证不进入 `RunnableConfig`、LangGraph context 或 checkpoint。当前 DeerFlow 鉴权/vault/Principal/模型回归 **91/91**、IAM SDK Adapter **13/13**、改动文件 Ruff 检查通过。AI Resume 与 Knowledge Base 的 IAM/OIDC 专属集成代码已从各自产品仓库清理，本 PRD 不把其旧接入能力视为当前功能；DeerFlow 自有资源数据范围、上游 revoke、SDK adapter 镜像分发和真实 IAM 互操作仍未完成。DeerFlow migration `0026_iam_oidc_token_vault` 未在目标产品库执行，密钥 `DEERFLOW_IAM_TOKEN_ENCRYPTION_KEY` 仍须由用户的 Secret Manager 配置。

> **本轮最新验证（2026-10-09）：** OTP challenge 绑定申请时的默认角色 ID 和有效授权指纹，涵盖权限目录状态、资源级授权和数据范围；兑换时重算，变化即消费旧 challenge。完整执行 `verify-local.ps1` 端到端通过：隔离 PostgreSQL 套件从空库迁移至 `0025_registration_role_snapshot` 后 **161/161 通过**，console 镜像构建、前端 `vue-tsc -b` 与 Vite build（3205 modules）通过。DeerFlow OIDC 回归 **22/22 通过**，并验证 IAM `tenant_id` 只取自 ID Token，不由 UserInfo 注入或覆盖；TypeScript 授权/OIDC 回归 14/14 与 strict 类型检查通过。新增认证、管理、OIDC 授权和登出审计来源 IP 回归 **5/5 通过**；它们与登录失败限流共用 Caddy 注入、Nginx 私有传递的可信客户端 IP 解析。开发库仍为 `0021_resume_wallet_perms`，没有执行开发库迁移；此前检查的 API readiness 为 `503 database_migration_pending`，真实浏览器/SMTP/OIDC 联调尚未验收。

> **此前验证快照（迁移至 `0024` 时）：** 当时完整隔离 PostgreSQL 套件为 152/152，前端 Vue/TypeScript 与 Vite build 通过。当前结果见上方“本轮最新注册验证”；开发库仍为 `0021_resume_wallet_perms`，API readiness 为 `503 database_migration_pending`。SMTP、真实浏览器注册、消费租户/角色正式配置及生产反滥用验收仍未完成，注册开关保持关闭。部署值与业务映射见[待提供配置清单](docs/部署与运维.md)。

> **DeerFlow 首次登录策略（2026-10-09，用户已确认）：** IAM 身份首次登录时自动创建 DeerFlow 普通用户；管理员权限不得由邮箱匹配或默认配置授予，只能由 IAM 明确授权。服务端 token/tenant vault 已有可选首版；仍须配置并验收租户与应用映射、权限码到 Gateway resource/action 的正式映射及业务数据范围；上游 refresh rotation 已接入，远程 revoke 仍待完成。

> **ToC 自助注册需求（2026-10-09，用户已确认）：** ToC 产品用户可自助创建普通账号；注册只在相应产品品牌登录页出现，不开放 IAM 管理台/企业租户匿名开户注册，也不允许创建租户或管理员。租户必须显式标记为 `consumer` 才能开放；存量租户默认 `organization`，而租户下任一应用开放时不得切换类型。全局 IAM 身份跨产品复用；每个 OAuth Application 分别建立 tenant membership 和最小普通角色，注册一个产品不会自动加入其它产品。首期用邮箱 OTP；验证前只有带 TTL 的申请，不创建身份/成员/会话，不接收或保存密码。邮箱验证后，新用户设置至少 12 位密码；已有 IAM 用户输入当前密码且原密码不变。默认角色不得包含 IAM 管理权限和租户/组织数据范围，产品接口仍须强制 owner 过滤。注册要绑定用户实际看到的政策链接/版本；版本变化使未完成挑战失效，历史同意不覆盖。全局开关与应用策略均默认关闭。DeerFlow 首次 IAM OIDC 登录可以自动创建本地普通用户，但必须以经验证的 `(issuer, sub)` 关联身份；管理员能力只能来自 IAM 明确授权，不能按邮箱或默认配置提权。当前源码 head 为 `0031_model_usage_reconciliation`，隔离 PostgreSQL 全量套件 169/169 通过；开发库仍为 `0021_resume_wallet_perms`，未迁移。SMTP、反滥用和注册浏览器闭环仍未验收。首期 CAPTCHA、供应商全局邮件配额/退信与注册分析看板、社交/手机注册、自助账户删除仍未实现；外部开放前还须确定风控、保留/删除、MFA 和新用户模型用量权益。

> **OIDC 租户声明（2026-10-09）：** IAM 签名 ID Token 增加应用所属 `tenant_id`，OIDC Discovery 同步公布该 claim。此项为资源方提供签名保护的租户上下文，不代替 access-token 验证或在线授权；DeerFlow vault 只加密保管回调令牌。

> **Token vault 加密辅助（2026-10-09，历史组件说明）：** Python SDK 新增 AES-256-GCM token 封装，AAD 绑定 issuer、subject、tenant 和 token 类型，隔离测试 4/4 通过。它只负责内存中的加解密；后续 DeerFlow 自身已实现数据库 vault、refresh rotation、请求级 Gateway 授权和 run-scoped Agent model/tool 授权，完整接入范围见本文顶部。`data_scope` 仍未完成。

> **DeerFlow OIDC 首登安全基线（2026-10-09）：** 已在 DeerFlow 开户代码中移除基于邮箱的管理员角色解析；新建账号始终为 `system_role=user`，旧 `admin_emails` 配置只为兼容而保留且不生效。既有账号不自动降级；Gateway 请求级和 Agent run-scoped central IAM 授权/refresh 已接入，data_scope 与真实 IAM 联调仍未完成，因此整体权限闭环尚未完成。

> **角色复制闭环（2026-10-09）：** 平台管理员可复制角色并修改新角色标识/名称/说明；租户、应用范围和启停状态沿用源角色。每次操作单独选择是否复制权限目录仍启用的通用/资源级授权及对应数据范围，默认不复制。直接角色成员和用户组角色绑定永不复制。后端在一个事务中创建副本、可选策略和审计记录；SQLite 隔离测试 6/6 通过，前端构建通过，浏览器管理写入及 PostgreSQL 并发仍待验收。

> **管理台窄屏 UI 复核（2026-10-09）：** 503×871 浏览器视口下检查平台管理员可见管理页面，修复宽操作列固定在右侧时遮挡角色/应用/用户组/应用角色数据的问题；现在这些表格在窄屏由内部横向滚动呈现。统一修正 Vue SFC 的静态数值 `maxlength` 绑定以消除运行时类型告警。`npm run build`（`vue-tsc -b` + Vite）通过。租户管理员专属界面、实际登录主题编辑/发布、公开登录页与 390px 视口仍待验收；没有提交管理写操作。详见[UI 走查记录](docs/验收记录.md)。

> **AI Resume 用户工作区权限（2026-10-06）：** 已绑定 IAM 的职业目标、个人面试题数据、用户自选 AI 任务模型/提示词配置，以及扩展的本人简历回填、岗位收藏/读取/进度/分析，使用通用 `resume.read` / `resume.write` 产品授权；AI 点评和岗位重新分析还需要 `ai.generate`。服务端沿用本地认证用户 UUID 与资源 owner 过滤，本地 ID 不作为 IAM `resource_id`。未新增权限码或迁移；未绑定账号保留本地认证，绑定账号在中央拒绝或故障时 fail closed。Node 全套测试 36/36 通过（Temp 目录、无数据库/IAM 配置）；登录态 IAM、真实业务数据库和浏览器流程未验收。
> **AI Resume 用户钱包授权（2026-10-05）：** 已绑定 IAM 的账户读取余额、流水和充值信息需 `resume.wallet.read`，提交充值申请需 `resume.wallet.recharge`；两码由 `0021_resume_wallet_perms` 登记且不自动授予角色。钱包仍按 AI Resume 的本地认证 `user_id` 过滤，IAM `data_scope` 不替代业务 owner 条件；管理员钱包操作和真实应用角色授权待后续接入/验收。

> **历史运行与验证快照（2026-10-07，已由 2026-10-09 验证更新）：** 当时开发库为 `0016_permission_status`，`0017`–`0021` 未应用且 readiness 为 `database_migration_pending`；后端完整套件受依赖和数据库缺失阻塞。当前迁移与测试状态以本页顶部的 2026-10-09 记录为准。

 > **历史：Knowledge Base 数据范围源码复核（2026-10-09，已被后续实现替代）：** 当时业务端固定发送 `include_data_scope=false`，没有成员 owner/组织字段。后续已实现可信 tenant/owner/organization 归属、文档/修订/片段/检索/任务/证据审计过滤，并加入源码 migration `0025_document_iam_data_scope`；KB 定向回归 35/35、Ruff 通过。目标数据库迁移、隔离 PostgreSQL 跨成员负向测试、真实 IAM/浏览器验收及历史数据归属治理仍待完成，不能把源码测试视为部署验收。

> **AI Resume 数据范围补充（2026-10-04）：** 已绑定 IAM 的 AI Resume 管理端简历列表/详情请求通用 `resume.read` 与 `include_data_scope=true`；IAM tenant/self 条件通过服务端 OIDC 会话映射到本地用户 UUID，再与原本地管理员归属取交集并在简历仓储执行。组织范围因暂无本地组织关系映射而 fail closed；个人简历 API、AI 调用、钱包、岗位、用户及其它管理资源仍待单独接入。

> **历史本地运行与迁移状态（2026-10-04）：** 最近一次只读核验的 Docker Desktop console 和 PostgreSQL healthy；API `/health` 返回 200，`/ready` 因本地数据库 `0016_permission_status` 落后于源码 head `0021_resume_wallet_perms` 返回 503 `database_migration_pending`。源码 `0017`–`0021` 均未应用，需用户明确授权后才能运行迁移；本轮未运行 IAM migration profile，也未写数据库。普通 Compose API 启动关闭自动迁移和管理员引导，显式 `migrate`、`bootstrap` profiles 分别执行一次性操作。数据库落后于 head 时 `alembic check` 不能判断 schema drift。

> **就绪状态反馈（2026-10-03）：** 管理侧栏与公开认证入口共享 `/api/v1/ready` 状态，每 30 秒刷新；登录入口可手动重查，且与定时轮询复用单个在途请求。请求 5 秒超时，探针与认证会话恢复并行。`database_migration_pending`、`database_not_ready`、`migration_state_unavailable` 显示为对应中文状态，HTTP 网络错误显示 API 未连接。后端 `/health` 保持进程存活语义。`vue-tsc -b` 和 Vite production build 通过（3205 modules，入口 380.97 KB / gzip 118.19 KB）；本地浏览器 accessibility tree 确认公开页提示、重查按钮和登录控件同时存在，未提交凭证；最新改动的管理员登录态和视觉验收仍待完成。

> **公开认证表单校验（2026-10-03）：** 登录与找回表单要求有效邮箱和密码；邀请接受要求提供密码，但不对已有账号的当前密码强加新密码长度；密码重置要求 12–128 位且二次输入一致。字段级 Ant Design Vue 规则负责即时反馈，后端 schema/认证逻辑仍为最终边界。Vue 类型检查与 Vite production build 通过（3205 modules，入口 381.97 KB / gzip 118.41 KB）；Vite 组件模块 HTTP 200 并包含新规则；浏览器无障碍树确认就绪提示、必填标记和认证控件共存，未提交任何认证请求；错误状态视觉和交互仍待验收。

> **公开入口故障提示（2026-10-03）：** 登录、OIDC、邀请和密码恢复入口在就绪状态异常时显示稳定错误码对应的中文说明，不隐藏认证表单，也不泄露数据库 revision、连接地址或内部异常。恢复到 ready 后提示自动消失；品牌登录主题使用固定高对比警告样式。浏览器 accessibility tree 已确认提示、登录输入框和找回入口共存；未提交登录、OIDC、邀请或密码请求。

> **历史接入盘点（2026-10-04，已于 2026-10-10 撤销）：** AI Resume 和 Knowledge Base 曾有 IAM/OIDC 登录、中央权限和数据范围接入代码；按用户决定，这些产品专属实现已从两套产品仓库清理。目前仅保留 DeerFlow 作为活跃试点。历史路径、功能和测试结果不代表当前运行能力。

> **管理台登录入口文案与窄屏走查（2026-10-03）：** 实际登录页将“平台管理员账号”修正为通用“管理员账号”，并把邮箱示例改为 `name@example.com`，与平台/租户管理员共用入口的授权模式一致。桌面登录页、找回密码页和 390px 手机登录/找回布局已在本地浏览器查看；未提交登录、邮件或密码请求。`vue-tsc --noEmit -p tsconfig.json` 通过，Vite production build 转换 3202 个模块（入口 378.27 KB / gzip 117.37 KB）。管理态页面仍需有效管理员会话验收。

本地开发环境启动与登录说明见[本地启动指南](docs/部署与运维.md)；生产部署与数据运维流程见[运维手册](docs/部署与运维.md)。

> **管理会话并发与跨标签页退出（2026-10-02）：** 前端将同一页面内并行 401 收敛到一个 refresh 请求；支持 Web Locks 的浏览器串行化同源标签页的 refresh。退出或认证失败时，支持 `BroadcastChannel` 的浏览器清除同源其他标签页的 access token，远端事件只更新 Vue 状态，不会再次广播。服务端只撤销当前请求的 JWT 和共享刷新会话；其他已签发的离线 JWT 到期前仍可被直接重放，浏览器广播不能替代服务端批量撤销。每个重试请求最多重放一次；数据库行锁和一次性消费校验继续作为服务端保障。未改变 API、Cookie、数据库或迁移；宿主机 Vue/TypeScript 检查通过，Vite 生产构建转换 3199 个模块（入口 374.22 KB / gzip 116.38 KB），真实登录态多标签行为仍待集成验收。

| 项目 | 内容 |
|---|---|
| 产品名称 | 统一身份与权限管理平台（IAM） |
| 文档版本 | V1.1 |
| 文档状态 | 成熟方案调研修订稿 |
| 目标用户 | 平台管理员、租户管理员、应用管理员、普通用户、审计人员 |
| 技术约束 | Vue 3 + Ant Design Vue 4 + Tailwind CSS 4 + Vite 8 前端、Python + FastAPI 后端、PostgreSQL 数据库 |
| 首批接入项目 | DeerFlow（唯一试点；端到端验收通过后再评估其它系统） |
| 后续接入项目 | 其他业务系统，复用 OIDC、权限判定 API 与 SDK |

> **角色权限影响预演细化（2026-10-05）：** 通用角色权限预览现将直接绑定与活动用户组继承的活动成员去重，并按权限估算适用范围内其它活动角色通用授权的覆盖数；平台角色和应用角色界面均展示逐权限估算。估算不模拟资源实例授权对所有具体资源的覆盖、业务资源存量或数据范围合并结果，仍不等于精确有效权限净差异。4 项内存 SQLite 回归覆盖组继承去重、其它通用角色抵消、跨应用授权范围、停用用户组和实例授权边界；API/数据库 schema 未变，无迁移。浏览器视觉与真实授权场景验收待后续完成。
> **OAuth 应用创建与启停契约加固（2026-10-03）：** 应用请求 schema 独立于认证契约，`ApplicationCreate.redirect_uris` 在 Pydantic 层强制提供 1–20 个登录回调，URL 协议仍由路由校验；应用启停 API 使用 `expected_status`，在行锁下拒绝陈旧页面，停用会话撤销与 from/to 审计保持同事务。管理台同步提交期望状态，409 后展示服务端冲突提示。Python AST 解析 backend/app 与 backend/tests 共 80 个文件通过，`vue-tsc --noEmit` 和 Vite production build 通过（3202 modules，入口 377.11 KB / gzip 117.14 KB）；宿主缺少 Pydantic/FastAPI 和运行中的 API 容器，新增后端回归用例尚未执行。

> **租户委派管理首批闭环（2026-10-03）：** `/api/v1/tenant-admin/*` 已提供组织树、租户成员/角色列表、成员组织归属、角色权限清单和数据范围查询/替换。服务端通过共享 RBAC 判定逐请求校验 `iam.organization.read` / `iam.organization.manage`；平台管理员跨租户旁路，租户角色必须显式获得对应权限，管理权限同时允许读取。Vue 登录后由受保护平台端点识别模式，并分别检查 read/manage，防止只读成员被误判为无权；租户模式提供组织、成员组织关系和角色数据范围页面，只有 manage 可写，后端仍强制授权。`vue-tsc --noEmit` 通过，Vite production build 转换 3202 个模块，入口 377.11 KB / gzip 117.14 KB。Alembic `0017_tenant_org_admin_permissions` 仅登记稳定权限码，不自动授权，且尚未应用；真实租户会话浏览器验收、应用管理员及其它委派管理域仍未完成。
> **租户应用委派扩展（2026-10-03）：** 租户管理员 API 与共享应用管理页支持 `iam.application.read`、`iam.application.manage`、`iam.application.secret.rotate`。`manage` 包含读取但不包含密钥轮换；密钥轮换需单独授权。权限可通过租户角色授权全租户应用，也可绑定 `Role.application_id` 将角色限制到单个应用；新建应用因没有应用上下文，只允许租户范围 `manage`。受信/静默授权状态仍仅平台管理员可改。Alembic `0018_tenant_application_admin_permissions` 仅登记权限码，不自动授予角色，也尚未应用；登录态浏览器验收待完成。

> **单应用角色和成员委派（2026-10-03）：** 已实现租户应用管理员工作台，按当前应用管理角色 CRUD/停用、业务权限预览与原子替换、只查看已获该应用角色的成员，并可按邮箱绑定现有活动租户成员。成员/角色对象均由 URL 应用范围和服务端 evaluator 逐请求约束；不开放租户成员目录，不支持应用管理员邀请新成员或新增 `iam.*` 管理权限；用户组继承只读展示，需租户管理员改组。未增加数据库模型或迁移。Vue/TypeScript 检查、Vite 构建和 62 个后端应用源文件 AST 解析通过；本地 API ready 为 `ok`、OpenAPI 发布 88 条路径且包含该路由，权限目录的 `role_id` 为必填参数，匿名访问返回 401；Vite 的入口/App.vue/feature SFC 均返回 200。当前仍未用登录租户管理员会话验证授权、数据读取或写入，数据库迁移未验收。

> **应用角色权限目录隔离（2026-10-03）：** 权限候选查询必须携带同一应用下的 `role_id`，用于将历史授权（包括系统管理权限）精确限定到当前角色；业务权限候选仍排除 `iam.*`，新增系统管理授权由后端拒绝。没有 schema 或 migration 改动。

> **登录主题可配置项更新（2026-09-30）：** 每个 OAuth 应用的登录主题支持受控的背景图位置/缩放/遮罩、卡片颜色/透明度/阴影/内边距、标题与正文颜色、字体预设、Logo 尺寸、输入框/按钮圆角和按钮高度，并在桌面/手机预览与 OIDC 登录页共用展示规则。服务端主题配置校验已抽到 `backend/app/services/theme_config.py`：只允许白名单字段、固定枚举/颜色/数值区间和 HTTPS/站内资源路径；可选图片地址允许清空，不接受动态 CSS/HTML。前端 `frontend/src/shared/theme.ts` 对旧版/异常主题值做安全归一化。Vue/TypeScript + Vite production build、5 项纯标准库主题校验测试和 Python AST 检查通过；无数据库 schema/migration 变更。当前没有管理员会话，未做已登录编辑器的浏览器视觉验收；图片仍使用外部 HTTPS/站内 URL，没有上传能力。

> **模型生命周期并发保护（2026-09-30）：** 模型目录启停 API 改为接收 `expected_status` 与目标 `status`，服务端在行锁下检查旧状态，仅对有效转换写状态与审计；页面过期时返回 409 并保留目录原状态。管理台同步提交读取到的状态，409 后刷新目录。4 项不访问数据库的模型目录测试通过（覆盖 PostgreSQL `FOR UPDATE` 语句）；`vue-tsc --noEmit` 通过，Vite 对模型管理页和共享请求模块转换返回 HTTP 200，当前 API OpenAPI 也发布要求两个字段的请求体。PostgreSQL 集成用例确认当前开发库缺少由 `0011_password_reset_sessions` 引入的 `users.auth_version` 列；`alembic current` 确认当前版本为 `0010_tenant_user_groups`，源码最新为 `0016_permission_status`。本轮未运行迁移，因此模型 PostgreSQL 集成用例未能完成。

> **权限目录生命周期（2026-09-30）：** 权限编码保持稳定且不可编辑/物理删除；平台管理员可显式停用或恢复。停用会使在线 RBAC 判定排除该编码、保留历史角色授予和数据范围，并阻止为新角色增加此项；管理台显示引用角色数量并二次确认。恢复会重新生效仍保留的历史授予，必须明确提示管理员。状态变化与审计记录同事务，API 使用 expected_status 拒绝并发覆盖；前端构建通过，隔离 SQLite 回归覆盖已编写，PostgreSQL migration 与登录态操作尚未验证。Alembic `0016_permission_status` 接在源码 revision `0015_model_usage_estimation` 之后，尚未应用。

> **首批业务授权状态（2026-09-30）：** AI 简历已在 Express 服务端对显式绑定 IAM 的账户执行简历 API、整个 `/api/ai/*` 路由组及 Provider 出站调用的在线权限判定：简历使用 `resume.*`，AI 入口使用 `ai.generate`，按最终运行模型 UUID 检查 `model.invoke`。Alembic `0012_resume_permission_catalog`、`0013_ai_permission_catalog`、`0014_model_invoke_permission` 登记对应编码；三迁移源码尚未应用且不自动授予租户角色，管理员须显式授予。AI 后端要求配置 `IAM_MODEL_ID_MAP_JSON`，将本地 `model_key` 映射到当前 IAM tenant 的模型目录 UUID（多租户配置按 tenant UUID 分层）。AI Resume 服务端现支持可选 IAM 模型用量适配：配置 `IAM_MODEL_USAGE_API_KEY` 后，四类 Provider 请求会尝试预留并报告/结算 Token；该值须与 IAM `MODEL_USAGE_API_KEY` 相同，先应用 `0015_model_usage_estimation`。配额执行开关默认关闭，估算用量以 `usage_is_estimated` 标记；IAM 模型账本与 AI 简历本地钱包分离。简历表缺少租户/组织字段，因此当前不请求 IAM `data_scope`，数据仍由 AI 简历本地 `user_id` 条件过滤。

> **运行环境复核（2026-09-30）：** 本轮 `docker compose ps` 显示本地 API、Vue 控制台和 PostgreSQL 均为 healthy（运行约 6 小时）；`GET http://localhost:8011/api/v1/ready` 返回 `{"status":"ok","service":"iam-api"}`，`GET http://localhost:5176/` 返回 HTTP 200。`alembic current` 确认当前库为 `0010_tenant_user_groups`，源码最新为 `0016_permission_status`；PostgreSQL 定向集成测试也确认 `users.auth_version`（由 `0011_password_reset_sessions` 添加）尚不存在。完整后端测试未运行，本轮没有运行迁移或生产部署。Windows Docker Engine 当前可访问；旧的 61 项后端套件仅是 2026-09-29 的历史记录。

> **邮箱密码重置实现补充（2026-09-30）：** 已增加 `POST /api/v1/auth/password-reset/request` 与 `/complete`，一次性 token 仅存 SHA-256 摘要，默认 30 分钟过期、邮箱 HMAC 键默认 60 秒节流；请求不泄露账号是否存在。`0011_password_reset_sessions` 为用户及管理/OIDC 一次性凭证添加 `auth_version`，密码更改后使 IAM 在线鉴权立即拒绝旧 token、撤销 IAM/OIDC refresh token 和待完成授权凭证，并标记邮箱已验证。密码重置 UI 依据每应用 `show_forgot_password` 开关显示，邮件 token 位于 URL fragment。Python AST 语法解析覆盖 70 个后端文件通过；最新 Vue/TypeScript 检查和 Vite production build 通过（3199 modules，入口 374.22 KB / gzip 116.38 KB），公开重置表单可访问性检查通过；后端集成测试、完整浏览器重置流程仍未完成。最近确认的运行数据库仍记录为 `0010_tenant_user_groups`，`0011` 尚未执行；SMTP 真实投递未配置。业务系统本地 Cookie/session 需由产品自行撤销；离线验签 OIDC access token 在到期前可能继续被接受（开发 Compose 默认 30 分钟，生产 Compose 默认 10 分钟）。请求限流目前仅按邮箱，不包含可信客户端 IP 全局限流。

> **当前实现状态（2026-09-29，基础能力快照；业务接入状态更新至 2026-09-30）：** 本地 Docker Compose 启动链路包含 PostgreSQL、迁移、管理员引导、API 和管理台。已有租户/应用/用户/角色/权限/模型目录/主题/审计管理、Argon2 密码、浏览器 HttpOnly 刷新会话、默认拒绝 RBAC、登录主题草稿/发布。应用可编辑名称和说明，但租户、Client ID、密钥、回调地址和信任状态不可通过资料编辑接口修改；Client Secret 可由管理员立即轮换，旧值立即失效、新值只回显一次，不支持宽限重叠。角色支持编辑名称和说明，租户、应用范围、角色标识不可通过此接口修改，已有授权关系保持不变；角色复制尚未实现。OAuth 2.0/OIDC 授权码 + 必需 S256 PKCE、RS256 Token、Discovery/JWKS、UserInfo、refresh rotation/revocation、RFC 7662 Token Introspection、RP-Initiated Logout 和按应用品牌登录已实现；OIDC access token 可进入独立 RS256 在线鉴权依赖，按 token 的租户/应用固定授权上下文，并即时检查当前成员与角色。基础构建与拒绝路径通过；OIDC 授权码兑换、重放拒绝、access/refresh token 撤销与内省、退出撤销和数据范围策略已有 PostgreSQL 集成验证；真实外部客户端互操作、浏览器全流程及安全评审仍未完成。**组织树、多组织成员关系和角色-权限数据范围策略已由 `0004` 迁移应用；本人数据过滤显式绑定 tenant_id，并由事务回滚的 PostgreSQL 用例验证。** `0005` 用量账本可查询；AI Resume 可选通过服务端网关密钥上报用量，配额拦截仍需显式启用默认关闭的开关，`0015` 计量标记迁移尚未应用。`0006` 提供一次性租户邀请。`0007` 增加显式 OIDC 用户授权同意：应用默认不受信任，每次授权前展示品牌、租户与请求 scope；平台管理员可经二次确认设为受信任，用户仍可用 `prompt=consent` 强制确认。`prompt=none` 对未受信任客户端返回 `consent_required`。`0008` 已提供模型调用前 RPM/TPM 预留和调用后结算 API，采用租户内模型聚合、60 秒滚动窗口、请求幂等及超限 429；`MODEL_QUOTA_ENFORCEMENT_ENABLED` 默认关闭；AI Resume 已有可选服务端适配，真实 IAM 部署联调尚未完成。预留超时 10 分钟；已发生的超预留用量照常记账并标记 overrun。AI 简历已有显式 OIDC 身份绑定及服务端 token vault：授权要求 offline_access，access/refresh token 由专用密钥 AES-GCM 加密保存并提供串行续期 helper；知识库控制台也已有首版 OIDC 登录/本地成员显式绑定，项目本地 PyJWT[crypto]、12 项 OIDC helper 测试、前端生产构建（1652 modules）与 ESLint、后端 Ruff 均通过，Alembic head 为 0023。两项目都未通过真实 IAM 浏览器互操作；知识库迁移尚未在数据库执行，完整后端套件尚未运行。AI 简历已为显式绑定用户的简历 API 接入 `resume.*`、为 `/api/ai/*` 接入应用级 `ai.generate`，并在每类实际 Provider 请求前按最终运行模型实例检查 `model.invoke`；IAM `0012`–`0015` 迁移尚未应用且角色仍须显式授权，服务端模型映射与 IAM 浏览器联调未验收。AI Resume 现有可选 quota/usage 调用链，但需服务端密钥与数据库迁移；实际限额拦截仍默认关闭。管理端简历列表/详情已接入 tenant/self data_scope SQL 并与本地归属求交；组织及其它业务数据域仍待接入。知识库本地角色/grant 仍是权限权威，中央 permission/data_scope 尚未接入；DeerFlow 仍待身份映射适配。注册邮箱验证、SMTP 邮件持久重试/投递监控、短信邀请、MFA、Front/Back-Channel Logout 和其余外部项目适配器仍未完成；OIDC 签名密钥重叠轮换已有源码，生产轮换尚未演练。

> **本轮安全补充：** Alembic `0009_access_token_revocations` 已应用到本地开发库。管理台登出与 confidential client 的 `/oidc/revoke` 可按随机 JWT `jti` 即时撤销 access token，数据库仅存摘要；在线授权与 UserInfo 检查撤销状态，离线只验签的业务服务仍可能接受到期前的令牌。

> **部署补充状态：** 已加入单机生产 Compose、独立 Alembic 迁移作业、Nginx 静态 Vue 镜像、Caddy HTTPS 入口和非开发配置启动校验；新增 `deploy/validate-production.ps1`，可静默解析 Compose、校验 Caddyfile/trusted-proxy drop-in 与 Nginx 配置，且不启动长期服务或迁移；脚本尚未在有 Docker 的环境执行。API 与静态前端生产镜像已基于示例环境构建，生产 Compose 静态解析及 console 静态健康检查通过，但真实域名/密钥下的生产服务启动和外网验收未做，因此仍属于未验收部署骨架。2026-09-30 更新 Nginx 静态控制台 CSP 与安全响应头，并为带有 location 级缓存头的 SPA HTML/静态资源重复声明，规避 Nginx 1.27 的 `add_header` 替换继承语义；CSP 允许主题 HTTPS 图片和 Ant Design Vue 内联样式，仍需生产浏览器做回归。登录节流使用的 Caddy 客户端 IP 配置已补齐：默认不信任代理并按连接对端计数；部署 CDN/LB 时可将实际出口 CIDR 写入只读挂载的 `deploy/caddy/trusted-proxies/edge.caddy`，再由 `{client_ip}` 覆写专用 `X-IAM-Client-IP`，但真实链路尚未运行验收。审计 `source_ip` 仍记录代理容器地址；自动备份/异地恢复、监控告警、RPO/RTO 和基础镜像 digest 锁定也未完成。

> **生产预检增强（2026-10-05）：** `deploy/validate-production.ps1` 现在还使用生产 API image、实际环境注入和只读 key mount 运行 Pydantic 配置校验，并加载活动 OIDC RSA 私钥确认格式与强度。OIDC 轮换时可用 `-IncludeKeyRotation` 合并 overlay 并加载备用 key。该容器命令显式覆盖 entrypoint，不调用迁移入口；预检总体仍未在 Docker 环境运行。

> 另已提供 Python 与 TypeScript 服务端 OIDC relying-party SDK（后者基于 Node Web Crypto/Fetch）；AI 简历已有显式登录/身份绑定、服务端 token vault、简历 API permission check、`/api/ai/*` 的 `ai.generate` 和 Provider 调用前按实际模型 UUID 执行的 `model.invoke` 在线检查。IAM migrations `0012`、`0013`、`0014` 登记默认 permission code，但尚未部署应用且不授予任何角色；`IAM_MODEL_ID_MAP_JSON`、租户角色 grant、真实环境互操作和 quota 配置尚未验收；AI Resume 已有可选额度/用量调用链；管理端简历列表/详情已接入 tenant/self data_scope SQL，组织及其它业务数据域尚未验收。DeerFlow 可用既有通用 OIDC Provider 指向 IAM，但尚未配置客户端或验收中央授权；知识库控制台已有可选 OIDC 登录及本地成员显式绑定首版代码，其角色/grant 和运行面 API Key 边界保留，数据库迁移、真实 IAM/浏览器联调及中央权限/数据范围仍待验收。生产部署闭环仍待安全配置评审。

> **授权管理补充（2026-09-28，业务响应扩展于 2026-09-30）：** 管理台和 `POST /api/v1/admin/authorization/simulate` 已实现平台管理员只读预演；它与业务授权接口共用判定服务，可查看检查轨迹、命中角色和数据范围，不创建或修改授权记录。角色通用权限另有变更预览和单事务批量保存；预览统计直接绑定及活动用户组继承的去重成员，并估算其它适用通用授权的覆盖；不模拟全部资源实例和数据范围结果，因此不代表最终权限净变化。业务 `POST /api/v1/authorization/check` 返回决策和数据条件；允许的 OIDC 判定还附带由已验签 token 得出的 `application_id`，供服务端用量关联，拒绝决策不暴露该上下文。管理员委派和更完整的资源级净影响分析仍未实现。
> **架构与实现状态更新（2026-09-29）：** Vue 和 FastAPI 维持独立顶层工程，工作台概览和登录主题编辑器分别位于 `frontend/src/features/overview/`、`frontend/src/features/themes/`；主题 feature 自管草稿、版本历史、预览和 API 请求。后端管理路由在 `backend/app/api/v1/admin/` 按身份、RBAC、用户组、组织/数据范围、模型目录、用量、主题和审计分文件，`admin/__init__.py` 仅作鉴权与装配；请求契约也按领域维护，RBAC 使用 `schemas/access_control.py`；OIDC Provider 按授权同意、Token/UserInfo/Introspection、登出和 Discovery 拆至 `backend/app/api/v1/oidc_provider/`，旧 `oidc.py` 保留兼容导出与统一路由入口。用户组 CRUD、成员/角色全量替换和授权继承代码已实现；在线就绪检查正常，匿名用户组列表请求返回 401。本地开发 PostgreSQL 已应用 `0010_tenant_user_groups`，本地 API readiness 正常、匿名用户组目录请求返回 401，完整后端 unittest 61 项通过；登录态管理员浏览器操作仍待验收，不能据此宣称生产验收完成。

人工运维流程已补充至 [运维手册](docs/部署与运维.md)，覆盖开发环境显式迁移 profile、生产发布 migration job、人工数据库备份、隔离恢复演练及生产备份/密钥恢复缺口；它不代表已部署定时异地备份、加密保管或灾备演练。

> **模型治理前端结构更新（2026-09-29）：** 模型目录与用量视图已迁至 `frontend/src/features/models/ModelGovernancePage.vue`，由该领域模块管理租户筛选、目录/用量请求、目录编辑与模型启停；控制台壳只根据导航传入视图和激活状态，API 路径和后端契约未变。Vue/TypeScript 类型检查与生产构建通过；尚未使用已登录管理员浏览器完成目录编辑、窄屏及用量视图验收，模型配额执行仍受服务端开关控制且默认关闭。

> **租户管理前端结构更新（2026-09-29）：** 租户目录、新建表单和启停确认已迁至 `frontend/src/features/tenants/TenantManagement.vue`；组件管理列表加载状态和表单校验，新增/启停后通知 Shell 刷新被其他表单复用的租户字典。后端 API、权限与数据库契约未变，待登录态浏览器验收和数据库写操作验收。

> **应用管理前端结构更新（2026-09-29）：** OAuth 应用目录、创建/资料编辑、信任切换、启停、Client Secret 轮换及一次性密钥展示已迁至 `frontend/src/features/applications/ApplicationManagement.vue`。新建表单要求至少一个有效登录回调，最多 20 个并按 HTTPS/本地 localhost 规则校验；Client Secret 仅在组件内暂存并于弹窗关闭后清除。API 契约没有变，类型检查及生产构建通过，待登录态浏览器与真实数据库写操作验收。

> **审计页面前端结构更新（2026-09-29）：** 审计查询从应用壳通用目录表格迁至 `frontend/src/features/audit/AuditLogPage.vue`，由审计领域模块管理加载状态、操作编码精确筛选、结果显示和错误态。页面读取最近 100 条，只读展示操作者、操作、目标、结果、来源 IP 和变更摘要；后端 `/api/v1/admin/audit` 契约未变化。须在管理员登录态进一步验收桌面宽表、长摘要、筛选空态及窄屏布局。

> **审计查询 API 与管理页扩展（2026-10-05）：** 新增 `GET /api/v1/admin/audit/search` 支持分页及操作、结果、对象、操作者、租户、时间筛选，并返回带 total/has_more 的分页 envelope；时间参数要求时区，end_at 为开区间。旧 `/api/v1/admin/audit` 数组响应保留。管理台可展开只读详情；未增加数据库迁移。登录态浏览器仍待验收；完整后端 unittest 99 项通过、28 项 PostgreSQL 用例因未设置 `DATABASE_URL` 跳过，使用临时依赖 overlay 且未连接数据库。

> **成员邀请前端结构更新（2026-09-29）：** 管理端邀请列表、按租户筛选、创建/撤销、有效期及邮箱/角色校验和一次性链接展示已迁入 `frontend/src/features/invitations/InvitationManagement.vue`；公开邀请接受流程仍属于认证入口。邀请 API 与 PostgreSQL schema 未改；创建响应含 bearer 链接时设置 `Cache-Control: no-store` 和 `Pragma: no-cache`，SMTP 邀请邮件可选启用，默认关闭；须在管理员登录态验收邮件发送、失败备用链接及页面交互。

> **角色管理前端结构更新（2026-09-29）：** 角色目录、创建/名称说明编辑/启停、通用权限影响预览与原子提交、数据范围编辑已迁至 `frontend/src/features/roles/RoleManagement.vue`；`App.vue` 仅维护供用户/邀请表单复用的角色字典。保留既有后端 API、默认拒绝、资源实例授权保留、冲突重预览及数据范围事务语义；本轮前端构建通过，登录态浏览器和角色/策略写入仍待验收。

> **权限目录前端结构更新（2026-09-29）：** 权限编码列表、检索和创建已迁至 `frontend/src/features/permissions/PermissionCatalog.vue`；校验跟随 `PermissionCreate` schema 的长度和必填约束，当前 API 只读/创建，不展示未实现的修改或删除操作。没有改变后端接口或数据库结构；登录态浏览器及真实创建仍待验收。

> **用户与组织管理前端结构更新（2026-09-29）：** 用户身份搜索/创建/停用、活动成员的租户角色绑定、多组织/主组织归属已迁至 `frontend/src/features/users/UserManagement.vue`；按租户的组织查询、层级创建与启停已迁至 `frontend/src/features/organizations/OrganizationManagement.vue`。`App.vue` 收敛到认证/会话、当前页状态、外观、健康状态和共享字典协调；页面白名单/标题位于 `app/navigation.ts`，桌面侧栏/窄屏选择器位于 `app/components/AppSidebar.vue`。前后端源码边界、API 和数据库契约未变化；`pnpm build`（Vue/TypeScript 检查 + Vite）通过，生成 3185 modules。当前本地 API readiness 正常、本地 PostgreSQL revision 为 `0010_tenant_user_groups`，57 项后端 unittest 通过；没有已登录管理员浏览器会话，因此新增页面的登录态 UI 与写入验收仍待完成。

> **公开认证入口拆分及组件按需加载（2026-09-30）：** 登录、OIDC consent、邀请接受及每应用登录主题展示迁至 `frontend/src/app/auth/AuthEntry.vue`；`App.vue` 保留已登录会话壳、页面状态和领域 feature 装配。Ant Design Vue 只在入口同步注册登录/根壳必需组件，管理员登录及已有会话恢复后再动态注册管理组件。`pnpm run build` 通过（3198 modules）；主入口 chunk 367.85 KB / gzip 114.41 KB，管理组件注册 chunk 285.61 KB / gzip 83.78 KB，最大 chunk 低于 500 KB 且 Vite 不再告警。API、OIDC 流程和数据库契约未变；真实 OIDC 客户端与已登录管理页的浏览器验收仍未完成。

> **过期认证凭证回收补充（2026-09-29）：** API lifespan 启动后台清理任务，默认每 3600 秒逐表最多回收 1000 条已过期的管理刷新会话、access-token 撤销摘要、OIDC 授权码和同意票据；配置项由 `CREDENTIAL_CLEANUP_INTERVAL_SECONDS` / `CREDENTIAL_CLEANUP_BATCH_SIZE` 控制。清理只按 `expires_at` 处理，在事务内使用 `FOR UPDATE SKIP LOCKED`，多个 worker 可并行领取批次；失败只记录错误并在下周期重试，不影响 API 启动。没有删除 OAuth refresh token 族、邀请、审计事件或模型 request_id/预留记录，因为这些数据仍承担重放检测、审计或幂等语义，留存周期待单独确认。无 schema 迁移；SQLite 隔离测试、生产配置边界和本地 PostgreSQL 回滚 SQL 验证通过。

> **控制台模块加载更新（2026-09-29）：** 工作台及 12 个其他管理领域页面通过 `defineAsyncComponent` 生成按需 chunk。未访问领域在首次导航时才挂载与加载，已访问页面保留挂载以维持表单草稿/筛选状态；共享加载与失败反馈组件位于 `frontend/src/shared/components/`。Vue/TypeScript 检查及 Vite 生产构建通过，本次构建转换 3194 个模块，初始入口为 1,275.69 KB（gzip 385.74 KB），上轮基线 1,583.67 KB / gzip 479.63 KB；入口仍超过 500 KB，原因之一是 Ant Design Vue 当前在 `main.ts` 全局注册。该改造不改变 API、认证或权限合同；登录态下首访 chunk 请求和故障恢复仍待浏览器验收。

> **开发热更新补充（2026-09-29）：** Docker Desktop Windows bind mount 未可靠触发 Vite 文件事件，开发配置已设置 `server.watch.usePolling=true`、轮询间隔 1000ms。控制台容器重启后，本地 `/src/app/App.vue` 返回 200 且包含 13 个异步 feature 导入；重启后再改宿主机源文件，2.5 秒内端点内容反映了新注释。模块响应验证了轮询监听，不替代管理员登录后的实际 UI 交互验收。

</details>

<details>
<summary>旧版本规划、评审输入及历史补充</summary>

## 14. 版本规划

### V1.0：认证与基础权限闭环

> 接入范围约束（2026-10-10）：当前仅 DeerFlow 是活跃试点。以下 AI Resume、Knowledge Base 的实现记录为撤销前历史快照；两套产品专属 IAM/OIDC 代码已清理，不作为当前源码能力或验收范围。

- [已实现开发版，类型检查/生产构建通过，待登录后 UI/数据库写验收] OAuth 应用管理迁入独立 feature，承载创建、资料编辑、受信状态、启停和 Secret 轮换；表单限制登录回调地址，服务端现有 API 安全约束保持不变。尚未在管理员登录态浏览器和实际数据库上验收交互写入。
- [已实现开发版，待登录后 UI/数据库写验收] 成员邀请管理迁入独立 feature，提供租户过滤、邀请创建/撤销和只展示一次的 bearer 链接；公开接受流程仍由认证入口处理；SMTP 邮件投递默认关闭，可选启用且失败时保留备用链接。
- [已实现开发版，待登录后 UI 验收] 审计查询位于独立 feature，支持操作/结果/目标/操作者/租户/时间多条件精确筛选、服务端分页及只读详情；新 `/admin/audit/search` API 保留旧 `/admin/audit` 数组契约，无数据库 schema 变更。前端 Vue 类型检查与生产构建通过；完整后端 unittest 99 项通过、28 项 PostgreSQL 集成用例跳过（未配置数据库），临时 `pwdlib[argon2]` overlay 未写入仓库。API 运行态与登录后浏览器验收仍待完成。
- [已实现开发版，待登录后 UI/数据库写验收] 角色管理迁入独立 feature，承载角色元数据/状态、通用授权变更预览/保存和数据范围管理；不改变角色绑定或 API/数据库契约。
- [已实现开发版，待登录后 UI/数据库写验收] 权限编码目录迁入独立 feature，支持检索、创建、显示状态/关联角色数、二次确认停用与明确恢复；停用不删除历史角色授予但会令其在线判定拒绝，恢复会重新激活未撤销授予。本地开发库已应用 `0016_permission_status` 及后续迁移至 `0021_resume_wallet_perms`；其它环境仍需迁移验收。
- [已实现开发版，待登录后 UI/数据库写验收] 租户目录 feature 独立管理列表、租户创建与状态启停；租户标识按后端规则校验。停用会撤销旗下应用现存 OAuth 刷新会话；浏览器页面已通过类型检查/生产构建，未在本轮执行数据库写入验收。
- [已实现开发版，类型检查/生产构建通过，待登录后 UI 验收] 模型治理 feature 独立维护模型目录表单、租户筛选、启停与模型用量账目/汇总；模型执行策略仍由服务端环境控制，UI 不开放配额全局开关。

- [已实现（开发版）] Docker Compose 本地 PostgreSQL/API/管理台开发栈和健康检查；迁移与首次管理员引导由显式 one-shot profiles 触发，普通 API 启动不写 schema。
- [已实现并运行验证] Windows 本地运行与验证脚本 `start-local.ps1` / `verify-local.ps1`：前者配置校验后构建启动 Compose 服务、探测 API readiness，不迁移数据库；后者在随机临时 PostgreSQL 数据库运行后端全量套件并构建锁定依赖的前端镜像。
- [已实现（开发版）] Vue 管理台登录和工作台，以及租户、应用、用户、角色、权限、主题、审计列表和基础写操作；新建应用可配置退出回调并仅显示一次客户端密钥。
- [已实现（开发版）] FastAPI/PostgreSQL 模型与 Alembic 迁移、Argon2 密码哈希、短期 JWT、摘要存储/轮换/撤销刷新会话、受保护管理 API、租户成员创建、角色绑定、资源 Scope 授予/撤销和默认拒绝判定。
- [已实现（开发版）] 应用登录主题白名单字段表单、桌面/手机预览、草稿/发布版本、模型元数据目录、审计记录及管理台本地主题切换；管理列表刷新、停用确认、令牌过期清理和基础移动布局已接入。
- [已实现，待本轮集成验收] 管理与 OIDC access JWT 含随机 `jti`；管理登出与客户端 `/oidc/revoke` 即时失效，撤销表只存摘要且在线鉴权、UserInfo 共用检查。
- [已实现开发版，待外部客户端互操作验收] RFC 7662 introspection；必须用所属 confidential client Basic 认证，令牌归属不符或当前已失效时只返回 `active:false`。活动/备用 RS256 公钥重叠和按 kid 验签已有源码，分阶段生产轮换仍待演练。Front/Back-Channel Logout 与 MFA 仍未实现；ToC 邮箱 OTP 注册已有源码，migration `0022`–`0025` 尚未应用到开发库；SMTP 和注册/生命周期浏览器端到端验收仍待完成。源码 head `0031_model_usage_reconciliation` 的完整隔离 PostgreSQL 套件 169/169 通过；开发库仍在 `0021_resume_wallet_perms`，未迁移。登录限流已加入源码 migration `0020_login_attempt_throttles`；生产 Caddy 默认不信任上游代理并覆写专用客户端来源头；前置 CDN/LB 时只配置实际出口 CIDR，真实 429、生产数据库迁移及 CDN/LB 来源解析仍待部署验证。邮箱密码重置已有源码，migration `0011_password_reset_sessions` 已包含在本地 `0021` 迁移链；SMTP 实际投递及完整邮件找回链路仍未验收。在生产化部署、安全与兼容性评审前不得宣称生产 SSO 验收。
- [已实现开发版，核心范围 PostgreSQL 集成验证通过] `0004` 已应用；组织、成员组织归属、策略 API/UI 和授权条件解析可运行。5 项事务回滚测试覆盖本人、组织树、租户范围、指定组织异租户 ID 过滤和缺失策略默认拒绝。业务项目仍需把响应的 `tenant_id`/所有者/组织条件编译进其数据查询，跨业务数据源适配及实际结果过滤仍须在各接入项目验收。
- [DeerFlow 模型用量源码实现并经隔离 PostgreSQL 验证；开发库/真实 Provider 联调待完成] 每个继承 run callbacks 的 LangChain LLM 调用先 reserve、后 Provider、结束 settle/report；关闭限额拦截时仍持久化 reserve。10 分钟未结算项保留待核对，由管理员按 Provider 记录结算或确认未调用后释放，操作进入审计；Provider 完成至 DeerFlow outbox 提交之间仍无法自动还原 Token。`0031_model_usage_reconciliation` 已在 `verify-local.ps1` 隔离库运行，完整后端套件 169/169 通过；开发库仍为 `0021_resume_wallet_perms`，readiness 503。自定义非 LangChain Provider 覆盖、真实 IAM/Provider 验收、预算控制、账本归档和生产 Secret Manager 轮换适配仍待完成。
- [当前范围外，旧接入已清理] AI Resume 与 Knowledge Base 的 IAM 专属登录、授权、data_scope、migration、测试和 UI 已撤销，不属于本阶段待接入项。首个端到端试点只做 DeerFlow；待 DeerFlow 验收后再决定是否恢复其它产品集成。通用 IAM 源码仍包含 OAuth/OIDC、RBAC、数据范围和 ToC 注册等平台能力。
- [平台核心与组织授权已实现；生产/部署验收待完成] IAM 租户用户组、组织、成员关系、角色范围与 OAuth 应用委派已进入源码，隔离 PostgreSQL 核心用例通过；业务查询仍须按 tenant/owner/organization 条件实施。源码 head `0031_model_usage_reconciliation` 的全量隔离套件 169/169 已通过，开发数据库仍停留在 `0021_resume_wallet_perms`，readiness 503。生产 Compose、独立 migration/bootstrap profiles、HTTPS 入口和备份恢复检查脚本已落盘；真实归档恢复、生产镜像运行、TLS/OIDC E2E、安全评审、监控及 RPO/RTO 尚未验收。
- [平台待办] ABAC 属性策略、非 OAuth 业务资源的进一步委派、短信邀请、注册 CAPTCHA/运营指标/退信监控、模型 Secret Manager/代理能力尚未实现。ToC OTP 注册和事务邮件重试已有源码，但 `0022`–`0025` 未迁移至开发库，真实 SMTP 与浏览器闭环未验收。DeerFlow 的正式 permission/resource/action map、data_scope 覆盖、管理员 role grant、adapter 镜像分发和真实 IAM/OIDC/Provider 联调仍待完成。

### V1.1：委派管理和可解释授权

- [部分实现] 已交付组织/数据范围和租户/应用级 OAuth 委派。组织目录、成员组织归属和角色数据范围按 `iam.organization.read/manage` 授权；OAuth 应用按 `iam.application.read/manage/secret.rotate` 分权，支持租户角色和绑定 `Role.application_id` 的应用角色；应用内业务角色/权限管理和现有租户成员绑定已实现，应用管理员不得新增 `iam.*` 管理授权，用户组继承只读可见。新建 OAuth 客户端要求租户范围 manage，密钥轮换需单独授权，受信状态仍由平台管理员控制。`0017`–`0021` 已应用到本地开发库，迁移不会自动授权角色。目标角色真实 grant、浏览器端到端和其它部署环境迁移验收待完成；非 OAuth 业务资源细分委派仍待开发。
- [部分实现] 开发版已提供授权模拟、逐项判定理由和通用角色逐权限潜在影响估算；[部分实现] 仍未模拟实例授权覆盖、业务资源存量与数据范围合并的完整有效权限净影响。
- [源码已实现/待验收] Knowledge Base 文档、向量/词法检索、异步任务、同步来源、运行证据/审计行级过滤及 migration `0025_document_iam_data_scope`；目标数据库迁移、真实 IAM/浏览器、全量 PostgreSQL 负向验收仍待完成。DeerFlow data_scope、正式权限映射、远程撤销和真实 IAM 验收待完成。
- [待开发] 用户属性条件、动态用户组规则和基于属性的策略评估；当前用户组只支持管理员显式维护成员，不自动同步 HR/目录属性。

### V1.2：数据权限深化与 DeerFlow 试点深化（后续系统另行评审）

> 范围状态：本节旧的 AI Resume / Knowledge Base 接入能力描述仅供追溯，2026-10-10 起已不属于当前代码；DeerFlow 当前已覆盖项目与全局会话搜索的本人范围校验，详见本文开头。其余资源范围及真实环境验收继续作为当前工作。

- 已实现标准角色数据范围基础（本人/组织/下级/指定组织/租户）；5 项 PostgreSQL 用例覆盖核心条件与异租户过滤。待接入业务项目后按各自真实数据字段验收行级过滤，并根据需求扩展属性规则。
- Knowledge Base 控制面 `knowledge.read/write/admin` 在线权限检查与 Application 资源授权已进入接入源码；现已请求 `include_data_scope=true`，并通过 `0025_document_iam_data_scope` 与显式仓储/检索谓词落实 owner/tenant/organization 过滤。旧文档不猜测回填，受限用户不可见；目标库迁移、真实 IAM、用户令牌双主体运行面与跨成员 PostgreSQL 验收仍待完成。
- DeerFlow OIDC 首登自动创建普通用户、UserInfo `sub` 精确校验、禁止邮箱提权和可选 AES-GCM token vault 已实现；请求级 Gateway route/model-catalog/sandbox-sync 授权已从签名 `sid` 解析服务端凭证并调用 refresh rotation。Agent 后台模型/工具在线授权、长任务 token refresh 与 memory commit 前二次授权已接入并通过定向回归。OIDC discovery 解析可选 revocation endpoint、RFC 7009 HTTPS client 原语与错误脱敏已实现并通过 41/41 mock 测试；`/auth/logout` 根据用户决策只清理本地 session，不向外部 issuer 发送 vault token。仍待正式 permission/resource/action mapping、data_scope 覆盖验收、adapter 镜像分发和真实联调。
- IAM 管理台会话查看、单会话远程撤销及 OIDC 持久会话撤销已有实现；当前源码 head `0031` 的完整隔离 PostgreSQL 套件 169/169 通过。真实管理员浏览器操作、部署环境会话撤销和离线 JWT 的剩余有效期策略仍待验收。

### V1.3：模型权限与企业能力

- 模型目录、`model.invoke` 在线授权、调用前预留/结算 API、过期调用管理员待核对 API/UI 和 DeerFlow LangChain per-call callback 已有源码；0031 已在隔离 PostgreSQL 全量验证（169/169），但开发库仍为 `0021`、readiness 503，未执行迁移。10 分钟期限不自动结算或释放；Provider 完成到本地 outbox 提交之间的 Token 缺口需人工对照 Provider 日志。配额拦截默认关闭；生产 Secret Manager/Provider、自定义非 LangChain Provider、真实 IAM 验收、预算及账本归档仍待完成。
- MFA、企业 SSO 或外部身份提供商接入仍未实现；当前 OIDC Provider 已有基础实现，但生产密钥轮换和外部 RP 互操作尚待验收。
- 登录失败限流已有源码及 `0020` migration；CAPTCHA/自适应风险策略、注册反滥用指标和增强审计分析仍未实现。

### 本轮全量开发实施顺序

1. **本地可运行基线（已完成）**：PostgreSQL、迁移、管理员引导、API、Vue 控制台和依赖健康检查。
2. **IAM 核心安全面**：应用客户端类型/密钥轮换、OAuth 2.0/OIDC 授权码 + PKCE、签名密钥与 JWKS、登录/登出与会话撤销、Discovery、应用主题登录页。
3. **管理闭环与组织数据**：组织树、多组织归属、角色数据范围、用户组、授权模拟及首批租户管理员委派源码已实现；数据范围真实查询过滤与其他管理域的权限委派仍未完成；本地开发库 `0017`–`0021` 已应用，其它环境须另行迁移验收。
4. **外部服务能力**：完成已实现 ToC 邮箱注册与用户生命周期及角色快照的 `0022`–`0025` 迁移、SMTP/浏览器验收与反滥用监控；确定注册用户的模型用量权益并由真实 Gateway 在 Provider 调用前执行授权/配额；短信通知、模型凭证 Secret Manager 适配、模型代理和用量/配额，并在 DeerFlow 试点验收后再评估其它产品接入。
5. **生产准备（未验收）**：生产 Compose 初始骨架已落盘；仍需执行镜像构建/启动、外网 TLS 与 OIDC 客户端 E2E、安全评审、双密钥轮换演练、可观测性和自动/异地备份恢复演练，并确认 RPO/RTO、性能和浏览器兼容性。

各阶段对外的“已完成”状态以端到端验证为准；当前 Provider 已有代码实现，但重建、协议 E2E 与安全评审之前仍不表示 OAuth/OIDC 可投产。

## 14.1 历史业务系统接入盘点（2026-09-27；当前唯一试点为 DeerFlow）

历史接入分析与当前边界见 [业务系统接入计划](docs/技术架构与接入.md)。本节 AI Resume、Knowledge Base 的接入描述是旧版状态快照；其 IAM 专属集成代码已删除，不代表当前能力或已验收部署。

- AI Resume 原 IAM 接入已撤销。其本地认证、用户 UUID 归属和业务 API 仍由产品自身负责；目前不调用 IAM。
- DeerFlow 有通用 OIDC 登录与 Gateway principal 的公开扩展边界；Gateway 请求 middleware 只接受签名本地 `sid`，并从已绑定用户/加密 vault 解析中央 IAM 凭证，供 Provider 检查 HTTP 路由、模型目录、sandbox-sync 及 Agent run 中的模型/工具权限。Agent 凭证通过非序列化 `RunContext` 与 run-scoped ContextVar 传递，只能附加给 subject 匹配的 Principal；异步授权复核 vault session 并刷新临期令牌，不进入可持久化运行配置。data_scope 与 production permission-map/目标镜像配置仍需接入和验收；请求参数和 UI feature flag 均不能作为授权依据。
- Knowledge Base 原 OIDC/中央权限/data_scope 接入已撤销。产品保留本地成员与应用授权，不再调用 IAM；未执行其 IAM schema migration。

管理台 UI 走查见 [验收记录.md](docs/验收记录.md)：登录入口基础布局曾完成桌面和 390px 手机截图检查；其后新增的就绪提示与手动重查按钮还需补充截图验收。窄屏导航使用完整选择器，列表工具栏支持换行，开发与生产容器构建通过。管理台功能页与窄屏体验仍需管理员会话逐页验收，不能以源码静态审查替代。

## 15. 待产品与技术评审确认

实施所需的仓库路径、IAM 迁移授权、租户/应用与业务资源映射、生产环境变量、运维目标及推荐默认值，集中维护在[待提供配置与业务决策清单](docs/部署与运维.md)。其 P0 项会阻塞当前开发恢复或首批业务接入，P1 项会阻塞生产验收；真实凭证只由用户写入部署 Secret Manager，不在聊天中提供。以下产品事项需确定：

1. 已确定 ToC 用户可自助注册，IAM 管理台和企业租户继续邀请/bootstrap；推荐每个 ToC 应用使用专用消费租户 + 普通默认角色（兼容当前应用固定 tenant 的 OIDC 契约），仍需确认多租户 ToC 应用是否要支持用户选择工作区。若采用每个个人独立 tenant，需先重构 OAuth client 多租户授权上下文。
2. 推荐首期仅邮箱 OTP 验证；需要 SMTP 服务商、发件域和是否要求验证码后立即自动登录的产品决策。验证码邮件需有投递/退信监控与队列重试。
3. 用户是否允许同时加入多个产品消费租户/企业租户，以及重复邮箱尝试注册时用统一成功提示并引导现有账号登录（推荐），需进入账户关联/租户切换设计。
4. DeerFlow 首登身份与存量账号 `(issuer, sub)` 映射、tenant/application 归属。
5. 登录主题图片的对象存储及域名方案。
6. OIDC 客户端密钥、令牌签名密钥的部署和轮换方式。
7. 首期生产部署环境、真实 IAM 域名、不可变发布 tag（`IAM_RELEASE_TAG`）、可用性要求和备份恢复目标；首次管理员 bootstrap 需提供至少 16 字符的一次性密码，成功后从部署环境移除。
8. DeerFlow IAM/OIDC 试点的 issuer、callback、测试 tenant/application、权限映射、vault key Secret Manager 配置和目标 migration 备份/执行计划。
9. 数据权限要表达的业务资源、所有权字段、跨租户边界、共享/协作者规则，以及“本人/部门/租户/自定义范围”的实际含义。
10. 邮件服务商、发件域名和对象存储/CDN；API Key、生产 JWT/OIDC 签名私钥和模型密钥应由你写入部署密钥管理器，勿在聊天中发送。
11. 模型目录要接入的提供商、模型名、预算/速率限制和审计保留周期；确定新注册账号的免费试用/付费额度、成本上限及欠费/超额处理，并确保实际 Gateway 在 Provider 调用前执行授权和配额。当前配额执行默认关闭，这项阻塞面向公网的新用户开放可计费模型能力。
12. 角色复制策略已定并实现：默认清空授权，每次复制可选择是否复制当前活动权限、资源级授权和对应数据范围；任何直接成员绑定或用户组角色绑定都不复制。用量账本与预留记录的归档/保留年限仍需确认。





## 2026-10-09 · 认证表单实现核验

登录、邀请和密码重置字段长度约束已按 Ant Design Vue 数值属性实现；认证规则、服务端校验和产品范围不变。Vite 生产构建通过；`vue-tsc` 因当前安装树无法解析 Vue 传递类型而未通过。该检查结果不替代浏览器登录/邀请/重置流程验收；当前会话连接 Docker Desktop Linux Engine 被拒绝，因此尚未启动服务进行运行时检查。

## 2026-10-09 · 开发环境启动反馈

用户终端截图显示管理台和 PostgreSQL 容器 healthy，API 刚启动且仍在健康检查阶段。该证据不代表 readiness、登录或端到端验收通过；API 状态和迁移版本仍待检查。

## 2026-10-09 · 本地运行验收阻塞

管理台可加载，但 readiness 当前提示数据库不可用（`database_not_ready`）；API 数据库连接/只读探测验收失败。PostgreSQL 容器健康不等同于 IAM API ready。API 容器日志尚未取得，当前不能确定是否为密码/连接配置或其它数据库错误；迁移状态也未验证。

## 2026-10-09 · 本机服务阻塞根因确认

Docker 日志已确认 API/迁移任务无法通过 PostgreSQL 密码认证（角色 `iam`）；迁移在建立连接前失败，未产生 schema 更新。服务验收仍阻塞，直到 `.env` 与持久化数据库角色密码对齐，并通过 API readiness。

## 2026-10-09 · 本地开发服务恢复状态

本地 Compose 数据库密码认证故障已恢复：PostgreSQL 持久化 iam 角色与 API 环境配置重新对齐，且未删除数据卷。源码迁移 0017_tenant_org_admin_permissions 至 0021_resume_wallet_perms 已在本地开发库应用。验收结果：容器内 SELECT 1 成功，API /api/v1/ready 返回 HTTP 200 status: ok，postgres、console、api 均 healthy；公开认证页面可从 http://localhost:5175/ 加载。该结果只代表本地服务就绪，不代表管理员账户已引导、登录成功或生产环境已验收。
## 本地管理员凭据轮换（2026-10-09）

管理员账号密码已通过公开密码重置完成端点更新，复用系统既有的 Argon2 哈希、auth_version 递增、刷新会话撤销和审计逻辑；PostgreSQL iam 角色密码及本地 JWT 签名密钥同步轮换。账号密码与数据库连接验证通过，API readiness 为 HTTP 200 ok。新值仅保存在本机根目录 .env，不能提交版本库或复制进示例模板。SMTP 目前为空；模型用量 API Key 是下游共享凭据，须与业务网关协同轮换，故本次保留。

## 2026-10-09 · 管理台 UI 走查结果

在现有管理员会话中走查工作台、租户、应用、用户、角色、模型和登录主题空状态，覆盖 1680px 桌面、390px 窄屏及浅色/深色主题。修复应用和模型宽表格导致整页横向溢出的问题，并统一深色表格表面与空状态对比度。复核后，应用桌面页及应用/模型手机页的横向滚动均限制在表格内。Vite 生产构建通过（3205 模块）；Vue 类型检查因本地 Vue 类型声明链解析失败。模型页仍出现 HTTP 500 请求提示，具体接口和服务端根因待查；登录主题编辑器需要应用记录，本地暂无应用，因而尚未验收编辑器和实际主题预览。详见 [UI 走查记录](docs/验收记录.md)。此轮不改变 API 契约、数据库模型或权限业务规则。

### 2026-10-09 · 走查问题复核

此前模型页 HTTP 500 已定位为租户目录 API 缺少 `func`、`TenantMembership` 导入并已修复。浏览器现可读取 1 个租户及 2 个成员，模型目录正常显示空态；用户管理的创建入口在字典恢复后可用。前端为共享字典读取增加失败后导航重试。应用/模型表格响应式和深色主题修复保持通过 Vite 构建后的页面复核。类型检查仍受本地 Vue 类型声明依赖链问题影响；完整中间断点和登录主题编辑预览仍是后续验收项。详见 [UI 走查记录](docs/验收记录.md)。

### 2026-10-09 · 标准前端构建恢复

通过 pnpm 工作区 public hoist 修复 Windows 安装链接下的 Vue 类型解析，并修正登录标题样式回退类型；`npm run build` 现通过类型检查与 Vite production build。前端 Dockerfile 改为严格按 `pnpm-lock.yaml` 安装。该项提升研发和镜像构建可重复性，不改变认证、权限或 API 行为。Docker 镜像自身及生产域名/密钥环境仍需单独验收。


### 2026-10-09 · 管理台视觉验收记录

平台管理员工作区的核心页面完成只读桌面走查；主题弹层文字和健康状态颜色已按现有设计令牌修正。未发现阻断性 UI 问题，未改变 PRD 业务流程、接口或权限规则。手机视口、租户管理员工作区和已登记应用的登录主题编辑/发布流程仍是验收项，详见 [UI 走查记录](docs/验收记录.md)。


### 2026-10-09 · 回归测试状态更新

本地前端完整构建通过；后端完整 unittest 套件在隔离 PostgreSQL 临时库中 109/109 通过，包含数据库集成用例。测试库已清理。此结果不替代生产部署、外部业务系统 OIDC/data-scope 联调和浏览器窄屏验收。

### 2026-10-09 · 生产部署预检工具复核

生产预检脚本默认解析实际 `docker.exe`，避免 Windows 应用执行别名导致 CLI 调用失败，并支持 `-DockerPath` 显式指定。PowerShell 语法检查和生产 Compose 样例配置解析已通过；完整生产预检仍待正式 `.env.production.local`、API/console/Caddy 镜像及 OIDC 私钥准备后运行。未执行生产启动、数据库连接或迁移。

### 2026-10-09 · 数据库备份预检闭环

新增单次 PostgreSQL custom-format 备份脚本：先检查 Compose、数据库认证、只读查询及归档工具，再导出、校验归档、复制至受保护目录并生成 SHA-256 sidecar。恢复脚本会验证 sidecar，并在随机隔离库执行 restore 与 revision/核心表检查；截至本轮只完成 PowerShell AST 解析，没有真实归档/恢复验收。自动调度、加密、异地保留和 RPO/RTO 仍待生产运维方案确认。

### 2026-10-09 · 审计日志筛选区视觉复核

管理员桌面浏览器检查工作台、应用目录、登录主题空状态及审计日志，发现日期筛选的“开始/结束”标签因输入控件挤压而换行，已通过网格列约束修正。前端 `npm run build` 通过。本轮未覆盖窄屏、租户管理员专属页面和已创建应用后的主题编辑/发布；不涉及 PRD 业务流程、API 或权限规则，详见 [UI 走查记录](docs/验收记录.md)。

### 2026-10-09 · 窄屏管理台复核

在 503×871 平台管理员视口复核管理目录，发现角色、应用、用户组和应用角色宽表格的固定操作列挤占首屏字段。650px 以下改为表格内部横向滚动，角色/应用/用户组页面已实机复核，页面本身无横向溢出；操作列可横向滚动访问。修正 Vue 数值 `maxlength` 类型告警，前端 `npm run build`（含 Vue 类型检查）通过。本轮不改变业务需求、API 或数据模型；390px、768/1024px、租户管理员页面、公开认证页以及真实应用主题编辑/发布仍待验收，详见 [UI 走查记录](docs/验收记录.md)。

### 2026-10-09 · DeerFlow OIDC 主体绑定加固

DeerFlow OIDC 服务现在只接受 `sub` 与已验签 ID Token 完全一致的 UserInfo；缺失或不匹配时丢弃 UserInfo，身份资料仅由已验签 ID Token 提供。该历史回归覆盖缺失 subject、空 subject、不匹配和匹配成功，测试当时为 20/20。后续已加入可选 session-scoped IAM token vault（见本 PRD 开头最新状态）；IAM 中央权限映射、数据范围或真实 OIDC 联调仍未完成，因此不代表 DeerFlow 集成验收完成。

## 2026-10-09 · 本地启动 readiness 有限重试

本地启动脚本的 readiness 探测现在最多执行 12 次，单次请求超时 2 秒、重试间隔 1 秒；连接异常与 HTTP 502 重试，API 返回 database_not_ready、database_migration_pending 等明确 503 时立即停止并显示错误码。该流程不执行数据库迁移或管理员引导。PowerShell AST 语法检查通过；本轮后续只读 Docker 检查确认 API unhealthy、PostgreSQL/console healthy，API 容器内 readiness 为 `503 {"detail":"database_migration_pending"}`、开发数据库 revision 为 `0021_resume_wallet_perms`。没有对开发库迁移或启动其它服务。

## 2026-10-09 · 注册默认角色策略快照

PRD 规定待验证注册申请在角色、租户或政策发生变化后不能沿用旧授权。challenge 记录 registration_role_id，兑换时必须与应用当前默认角色一致；不一致时消费挑战并统一返回验证码无效。migration 0025_registration_role_snapshot 会先消费所有旧待验证挑战，再添加角色外键和约束。

## 2026-10-10 · DeerFlow 授权响应强制绑定应用

DeerFlow IAM Provider 的普通权限检查和 `data_scope` 查询现在都要求 IAM 响应回显与服务端配置完全一致的 `application_id`；字段缺失或应用不匹配时默认拒绝。服务端可配置 `resource_id_resolver` 将可信资源 ID 传给 IAM；配置后 resolver 返回缺失/非法值时拒绝，不回退应用级 grant。数据范围入口接受业务服务端构造的资源 `context`。同步适配器用例 17/17、IAM 数据范围客户端用例 11/11 通过；当时完整异步适配器回归受 Python runtime event loop 挂起影响而未验证；2026-10-11 使用 DeerFlow Python 3.12.14 复验 SDK 22/22、互操作 12/12（mock）。该校验只确认授权应用/资源边界，不代表 DeerFlow 项目、会话或文件查询已经落实 tenant/self/organization 行级过滤；后者、目标库和真实 IAM 联调仍待完成。

</details>

<details>
<summary>交接文档此前执行摘要（任务基线仍保留在新入口）</summary>

## 8. 本次更新与后续同步规则
### 2026-10-13 · B04 Windows Studio route setup failures

- 修复 `tests/test_langgraph_studio_routes.py` 的 Windows 测试环境：Studio 子进程显式开启 `PYTHONUTF8=1`，解决锁定依赖以 locale 默认 GBK 打开 UTF-8 OpenAPI 资产导致的五项 setup error；失败日志用 UTF-8 replacement 解码保留诊断。
- 跨版本持久化测试现在在旧服务仍运行时等待其 10 秒周期 flush 产生 `.langgraph_api/.langgraph_ops.pckl`，再模拟服务重启；context 外等待会先强杀进程，无法触发 flush。
- `backend/tests/test_langgraph_studio_routes.py` 全模块 **6 passed**，Ruff check 和 format check 通过；pytest 临时根目录已清理。全量套件未在此修正后重跑，所以 17,004/186/349/3/5 的旧快照不作更新。
- 下一步继续分组复现剩余全量失败（包括缺 `uv` 与 `WinError 10106`），完成针对性修复后再决定是否重跑长耗时全量。未执行 migration、真实 IAM/Provider 或 quota enforcement。

### 2026-10-13 · B04 全量离线后端复跑

- DeerFlow Windows Python 3.12 完整离线运行命令：`\.venv\Scripts\python.exe -B -m pytest -q -m 'not live' --ignore=tests/blocking_io tests/ -p no:cacheprovider --basetemp <isolated-temp> --tb=short`；结果 **17,004 passed、186 failed、349 skipped、3 deselected、5 errors、99 warnings**，耗时 **35:00**。与此前快照相比 Windows 条件跳过数 +3；未通过总数（failed + errors）仍为 191，不能标记全量通过。
- 已知诊断项：extension manager 测试无法找到 `uv`；live-policy 子进程出现 Windows `WinError 10106`；5 个 LangGraph Studio setup errors 在启动失败诊断时读取日志触发 `UnicodeDecodeError`，实际 server startup root cause 仍被遮蔽。其余失败尚未完成逐项分类。
- `D:\t\iam-deerflow-full-final-20261013` 临时测试根目录已确认删除；没有删除测试源码。未运行数据库 migration、真实 IAM/Provider、quota enforcement 或部署验收。下一步先修复 Studio 诊断读取以暴露原始启动错误，再将 Windows 环境问题与真实功能失败分组复现。


### 2026-10-13 · B04 完整套件归因与测试稳定性

- DeerFlow 完整离线后端快照为 **17,007 passed、191 failed、346 skipped、3 deselected**。随后 browser automation/browserless 两模块修正环境 DNS 夹具，聚焦回归 **87 passed、1 skipped**；pnpm 路径与 checkpointer/store singleton 定向回归 **3/3 passed**，Ruff check/format 通过。完整套件尚未在这些测试调整后重跑。
- 修正 Windows pnpm 用例对扩展名大小写的断言，并把并发 singleton 测试等待阈值由 3 秒提高到 10 秒；没有修改生产 checkpointer/store 实现。缺少 `uv` 阻断 extension manager 安装测试；`test_client_live_policy` 的 Windows 子进程遇到 `WinError 10106`。其余 191 项失败并非同一原因，继续逐项归因。
- 临时 pytest 目录已删除并确认不存在；未运行 migration、数据库写入、真实 IAM/Provider 请求或 quota enforcement。下一步继续 B04 分类及 D01 同步，A01/A02/A03/C01/C02 等真实运行验收仍受目标环境和受保护备份/迁移授权限制。

### 2026-10-13 · B04 owner 数据清理与 Lark Windows 回归

- 修复全量测试复现的 `UserScopedSkillStorage.purge_custom_skills` 缺失：删除本人自定义技能包、JSONL 历史及自定义状态，保留全局 legacy/integration 技能及其用户开关；在 user projection mutation 锁内删除并重建本人投影。Gateway `GatewayOwnerDataDeleter` 新增能力探测与 `delete_custom_skills(user_id=...)`，校验存储用户与明确 owner 匹配，通过线程池清理后仅刷新该 owner 的 prompt cache。
- 将 Lark broker 测试 fake CLI 改为 Windows 可控模拟，清除 localhost 拒绝用例中的继承代理；标出三个仅适用于 POSIX `/bin/sh` runtime 的 launcher 测试在 Windows 条件跳过。browser module **87 passed、1 skipped**；Lark broker + 全量 user-scoped skill storage + owner deleter **76 passed、6 skipped**；pnpm/checkpointer/store 回归 **3/3 passed**；Ruff check/format 通过。
- 全量快照 **17,007/191 failed/346 skipped/3 deselected** 早于以上改动；未重跑全量。Gateway 技能清理还未进入公开 extension-api 或产品数据任务/UI，不对外宣称该功能已端到端可用。缺 `uv`、live-policy subprocess `WinError 10106` 仍待支持环境处理；临时测试目录已删除。未运行 migration、真实 IAM/Provider 或 quota enforcement。

### 2026-10-12 · B05 DeerMem 后台模型用量计量接线

- 改动：DeerMem 后台模型路径使用 Gateway 注册的 usage callback factory；每次调用时通过 Gateway serving loop 重载活动本地用户与匹配 OIDC vault，绑定默认或指定服务端模型档案，创建 one-call IAM usage callback。Harness 仅将 callback 附加到本次 LangChain invocation，终态后移除并关闭；debounce queue 不存 IAM 凭证/capability。计量关闭时行为不变；启用后 admission 失败即不外呼。同步 memory hook 初始化与分层文档。
- 验证：`backend/tests/test_memory_commit_authorization.py` + `backend/tests/test_iam_model_usage_callback.py`，DeerFlow `backend/` Windows Python 3.12 隔离环境 **20/20 passed**，Harness boundary **1/1 passed**；本轮短随机目录已清理并确认不存在；DeerFlow backend 6 个变更 Python 文件 Ruff check/format 通过。全量测试、镜像、数据库、真实 IAM/Provider E2E **未运行**。
- 阻塞/下一步：A01 仍无 DeerFlow runtime，IAM API readiness 503；B05 本次内置路径静态搜索已完成，尚需盘点部署实际加载的扩展 Provider、澄清 Codex 内部 HTTP retries 是否需按 attempt 计量，并等待目标 IAM/Provider 验收；随后做 C01/C02。数据库未迁移，quota enforcement 保持关闭。

### 2026-10-12 · B05 生产模型入口只读审计

- 盘点范围：DeerFlow `backend/app` 与 `backend/packages/harness/deerflow` 的内置生产 Python 源码（排除 tests/scripts）；搜索命中 DeerMem 的 `init_chat_model()` 和共享工厂动态创建 `BaseChatModel`。Codex Responses 自定义模型通过共享工厂构造、继承 `BaseChatModel`，其 usage 已回填 LangChain `ChatResult`；原始 HTTP 请求是该模型实现内部 transport，不是旁路入口。DeerMem benchmark 的原始请求位于 scripts，不属于运行时入口。本次未穷尽配置外的动态扩展 Provider。
- 验证：本轮只读静态搜索与源码阅读；**未运行测试、构建、Provider 请求、数据库写入或真实 IAM 联调**。保留当前目录下已有未提交改动。
- 未决：Codex 自定义模型内部可能重试多次 HTTP attempt，但 IAM callback 按一次 LangChain invocation 预留/结算；需评估 Provider 计费语义和重试是否要拆账。仍需 A01 目标运行环境、IAM readiness 及 live Provider 结果；quota enforcement 继续关闭。

### 2026-10-13 · B04 Windows 文档路径回归与整套复验

- 改动：DeerFlow Windows 长文档物理路径超过预算时使用项目内确定性 documents/.short/<digest> 别名，DB stored_relpath 与 schema 不变；已存在短别名优先，旧路径仍可读。回归覆盖稳定映射、项目隔离、别名复用和 legacy 兼容。
- 验证：focused regression 65 passed、2 skipped；完整 blocking-I/O 140 passed、3 skipped、0 failed；9 个改动 Python 文件 Ruff check/format 通过。路径修复后完整离线后端为 16,896 passed、302 failed、346 skipped、3 deselected。随后修订六个模块中过期的 auth/OIDC/request/owner/mock fixtures，六模块回归 301 passed、3 skipped，6 个变更测试文件 Ruff check/format 通过；该全量套件尚未在最新测试树重跑。项目 guidance 预算检查 1/1、MCP config secrets 模块 195 passed。所有本轮 pytest 临时目录均已验证清理。
- A01 只读复核：Console HTTP 200；API readiness HTTP 503 database_migration_pending；docker compose ps 显示 IAM API unhealthy、Console/Postgres healthy；只读 PostgreSQL revision 仍为 0021_resume_wallet_perms，查询确认 model_usage_reservations 存在、注册 challenge/throttle/email outbox/login-theme 表未找到；全局容器列表无 DeerFlow runtime。
- 未执行：未迁移/写入数据库、未重建或停止容器、未调用真实 IAM/Provider；quota enforcement 保持关闭。
- 下一步：继续分类 302 项全量失败并优先复现产品/权限相关项；已修复的 28 个失败只在六模块隔离复验中证实通过，需决定是否执行最新完整套件复跑。继续 D01 文档审计；A01/A02/A03/C01/C02 等部署与真实验收仍需目标 DeerFlow 环境、受保护备份及明确迁移授权。
### 2026-10-12 · B05 未知模型调用结果保留预留

- 改动：`IamModelUsageCallback.on_llm_error()` 与 `close()` 不再把缺少可确认用量的请求写成 `failed`/0 输出；保留 IAM 服务端 reservation，等待 10 分钟核对期限与管理员 review。reservation admission 成功后仍只有“确认 Provider 未被调用”才允许释放；日志只写错误类型或未结数量，不写 prompt/Provider 错误正文或凭证。
- 验证：DeerFlow `test_iam_model_usage.py`、`test_iam_model_usage_callback.py`、`test_iam_model_usage_outbox.py`、`test_memory_commit_authorization.py`、`test_harness_boundary.py` **33/33 passed**；变更的 2 个 Python 文件 Ruff check/format 通过。完整离线后端 **16,775/419 failed/346 skipped/3 deselected**（Windows 路径修复前快照，修复后未重跑）；blocking-I/O 修复后 **140 passed/3 skipped/0 failed**；全量套件失败分类仍在 B04。有效全量运行的 pytest 临时目录已清理；保留产品回归测试源文件。
- 限制/下一步：`uv`/`make` 不在此 PowerShell PATH，使用已安装 backend venv 运行等价 pytest 目标；真实开发 IAM readiness、数据库 migration、Provider 计费语义、运行镜像和 IAM/DeerFlow E2E 均未验证。优先处理 B04 并完成 C01/C02，quota enforcement 继续关闭。

### 2026-10-12 · A01 IAM 环境复核与 B01 DeerFlow 权限映射盘点

- 推进：恢复 Docker CLI 只读盘点；完成 DeerFlow `config.example.yaml`、Gateway permission constants、Harness IAM adapter 与 IAM `0026–0030` catalog 的静态映射核对。新增 B01 配置矩阵、角色草案、owner/self、OIDC/PAT 与模型/工具资源授权说明；B01 实际部署输入仍待提供。
- A01 证据：Console HTTP 200；API `/api/v1/ready` HTTP 503 `database_migration_pending`；Docker 中 IAM Console/Postgres healthy、API unhealthy；当前数据库 revision `0021_resume_wallet_perms`；注册挑战、throttle、email outbox、consent 表不存在；`docker ps -a` 未发现 DeerFlow 容器。
- 未运行：本轮未运行产品测试/构建；未启动、重建或停止容器；未备份、迁移、改数据库、配置角色 grants 或调用真实 IAM/Provider。未检查 DeerFlow 目标数据库，因为没有运行容器/目标服务。
- 当前阻塞与下一步：A01 等待 DeerFlow 目标服务/库接入；A02 仍需受保护备份目录与责任人/恢复演练，A03 需明确迁移授权；B01 需 IAM 标识、逐模型 UUID、工具 grants 和存量身份冲突清单。继续 B04 失败归因与 D01 文档校正，不把静态映射视为真实 E2E。

### 2026-10-12 · 建立交接文件

- 已完成：H00；梳理当前改造与后续依赖，建立持续更新入口，并校正部分现行文档中的过期测试、共享和登出待办表述。
- 本轮验证：源码 migration head/验证入口与 Markdown 链接静态核对；只读 HTTP 为 Console 200、API readiness 503；docker.exe 不可用。
- 未运行：产品测试/构建、数据库 revision 查询、归档/恢复、migration、正式授权配置和真实 IAM/Provider/browser E2E。第 3 节其余测试是有日期的历史证据。
- 下一步：A01。受阻时推进 B01/B04/D01；待备份及明确授权后处理 A02/A03。

</details>


# 架构与接入历史摘录

整理日期：2026-10-13（Asia/Shanghai）。本稿供根协作合并至 CHANGELOG 后移除临时目录。以下来自原架构、接入计划、模型治理的独特历史资料；**不是现行实施指南**。当前事实见技术架构与接入、项目总览与进度；同一代码路径后续已完成时，以最新交接为准。

## 历史工程与验证快照

| 日期/范围 | 历史事实与证据边界 |
|---|---|
| 2026-09-29 IAM 用户组 | 本地 revision 曾为 0010_tenant_user_groups，61 项后端 unittest 通过，ready ok，匿名组列表401；过期凭证清理在PostgreSQL外层回滚事务验证。不能当今天的revision/readiness |
| 2026-10-03 委派应用管理 | tenant-wide与单应用role管理read/manage/secret.rotate进入源码；组继承只读，不能开放全租户成员或新增iam.*；这不自动给业务API增加判权 |
| 2026-10-04–05 接入盘点 | IAM当时只读revision0016、source head0021；知识库PostgreSQL connection refused，不能断言其revision；AI简历旧库升级缺20260927_full_workspace_upgrade.sql，禁止直接用init.sql升级既有库。三个产品的当时实现后来按单试点决策撤销部分 |
| 2026-10-05 生产预检 | validate-production.ps1 加入配置/密钥/代理语法检查；当时没有Docker CLI，目标运行未验，不等于发布或恢复验收 |
| 2026-10-09 前端模块拆分 | 15个管理feature异步加载，登录公共组件先装配；当时Vite 3205 modules，主入口378.96KB/gzip117.51KB、管理注册285.65KB/gzip83.80KB、应用角色15.40KB/gzip5.68KB，最大chunk低于500KB。Docker polling改动经模块端点核验，修改App.vue后2.5秒看到更新；只重启Console，未重启API/Postgres |
| 2026-10-09 IAM注册/生命周期 | 注册加固阶段完整套件曾129/129，生命周期阶段137/137，迁移至0025的隔离PostgreSQL完整套件161/161和Vue/Vite通过；开发库仍0021，SMTP/真实浏览器未验 |
| 2026-10-09 SDK与OIDC | TypeScript授权/OIDC14/14及strict tsc通过；该次Python缺FastAPI/PyJWT未跑。Python vault helper阶段25/25仅证明加密原语；DeerFlow UserInfo subject20/20、后续vault/principal/model91/91、IAM adapter13/13均mock。callback返回token但尚未持久vault的描述已被后续源码替代 |
| 2026-10-09 本地启动 | readiness最多12次、单次2秒、间隔1秒，连接异常/502可重试，明确503立即停；AST通过。后续只读确认migration_pending，主机端口不可达；不执行迁移/bootstrap |
| 2026-10-10 单试点收敛 | AI Resume与Knowledge Base的产品专属IAM/OIDC代码、配置、schema/migration、测试和UI契约已清理；保留本地认证/授权/业务。没有对这些产品库执行迁移；它们的下述接入细节只保留历史 |
| 2026-10-10 IAM隔离运行 | 空随机库迁移至当时head0027后161/161，console镜像内vue-tsc/Vite通过；实际开发库仍0021，临时iam_test_*库为0。普通启动不迁移；Docker命令一度解析到不可启动系统路径，不能将旧探测当当前值 |
| 2026-10-10 DeerFlow镜像 | deer-flow-dev-gateway:latest断网一次性import adapter/authz/agents通过；当时Harness head fd_0027_repair_run_change_seq，目标库未知。之后dev镜像iam-deerflow-package-check:20261011 SHA f2203cacf14d7a324dadcaa4d803145fcd9fd48129a9e9f15751e4beb4947456 通过uv环境adapter import；只证明导入。runtime构建docker.io Python manifest/GHCR uv token EOF，locked dry-run通过、uv.lock未变，default runtime未产出 |
| 2026-10-10 DeerFlow数据授权 | 项目/线程读取133/133；按ID thread/run228/228；文档/回收站72 passed、2 skipped，当时Windows长文件名失败后修复；项目/文档/回收站写92/92；owner-bound mutation101/101，断网扩展路由532项（排除1公网DNS）；Agent/auth/PAT/me/provider90/90；memory/permission/PAT118/118；stateless/assistants28/28。均未目标migration/liveIAM |
| 2026-10-10 扩展与后台 | connector57/57；skills/MCP/subagent79/79，加入channel worker81/81；联合138/138、完整写响应read/write后141/141；scheduler/vault/route/resolver126/126及AST10、Ruff格式9文件通过。旧“远程revoke仍待”后来被本地登出决策取消 |
| 2026-10-10–11 adapter async | 初次sync18/18、auth client11/11，model/tool sync选择8/8；async在Windows挂起。10-11 DeerFlow Python3.12.14 SDK22/22、互操作12/12（4个asyncscope）通过，均mock，无线上IAM/DB |
| 2026-10-11 IAM0030→0031 | 0030隔离完整套件161/161；某临时Python缺pwdlib未收集。随后verify-local将空随机库升0031，完整169/169、Vue类型/Vite3205通过；实际库未升级。不能累计测试数字或把临时收集失败留作当前永续阻塞 |
| 2026-10-11 DeerFlow特殊路径 | preferences19/19；Console25/25；memory updater/data-scope/commit109/109；OIDC/revoke/vault41/41；browser/webhook76/76及Ruff通过，公网URL固定DNS。上游vault token出站接线曾被自动审批拒绝，随后用户明确只本地登出；客户端原语保留，本阶段不要求接线 |
| 2026-10-11 模型回调/outbox | 单次回调8/8覆盖async异常传播、Provider别名及缺终态；client/vault15/15；model factory+usage+outbox118/118。隔离SQLite链到fd_0028，120秒lease、重试与30天delivered保留；无法恢复Provider完成至pre-outbox提交崩溃的实际Token |
| 2026-10-12 Windows/抓取 | 路径超240个UTF-16单位改短内部名，原显示名/MIME/转换后缀与legacy读取保留；短临时根四组routes225/225；首次长basetemp自身仍失败。readabilipy无Node回退补安全链接/图片，web-fetch50/50及Ruff通过 |
| 2026-10-12 DeerFlow全量旧快照 | 授权28/28、Harness1/1；专项IAM/OIDC/model/vault/usage/data-scope169/169为DeerFlow mock，不同于IAM PostgreSQL169。完整Windows快照依次16750/442 failed/345 skipped/3 deselected、16770/422/345/3；短根全量34%遇WinError10106中断。后续16775/419/346/3仍失败；这些被10-13最新快照替代，不能归因全部为环境 |
| 2026-10-12 计量补齐 | DeerMem授权后另接单次usage callback，memory commit+usage20/20及Harness1/1；未知结果保留预留相关33/33与Ruff通过。旧MODEL_GATEWAY“DeerMem未接reserve/outbox”段不再现行；动态Provider与Codex内部HTTP retry计费仍待 |
| 2026-10-12 迁移/备份 | 0022–0031只读审阅未执行：0024删除旧challenge密码摘要列、0025消费旧未验证OTP；从0021连续升时表新建预计为空，但执行前复查revision/行数。0022/0024downgrade有破坏性，0031人工核对后拒降。ValidateOnly通过未出真实归档/恢复；7个旧pytest根目录清理核验，不删测试源码 |

技术整理保留了现行设计中的所有模型策略：按租户model滚动60秒、无显式限额不限、输入+最大输出预留、429外呼前拒绝、超预留照常记账overrun、10分钟保留待人工核对、每次调用ID幂等。失败计量、留存、网关key轮换/隔离、压测和月度预算仍未定；这些不是旧历史中的已上线能力。

## 已撤销业务接入的独特历史细节

以下段落保留撤销前产品路径、主键和迁移信息，以便未来重新评审时知道曾有何工作；**不得照此在产品重新启用IAM，也不要求这些产品提供本阶段密钥/迁移授权**。

### 曾接入：AI 简历（已撤销）

### 盘点事实

- 实际工作区由三个独立 Git 仓库组成：`resume-frontend/`（Vue 3）、`resume-backend-node/`（Express + PostgreSQL）和 `resume-browser-extension/`。`D:\project\aijj` 实际是“基遇”AI 基金决策项目，不能作为 AI 简历接入目标。
- AI 简历已有本地认证闭环：随机账号注册、账号/已验证邮箱密码登录、邮箱验证码登录、refresh token 轮换、密码找回、封禁检查，以及本地 `USER/ADMIN/SUPER_ADMIN` 角色与细粒度权限。前端 Axios 自动刷新本地 JWT。接入不能假设“无登录系统”，也不能直接替换用户主键。
- 后端以 UUID `users.id` 作为用户与简历、钱包、AI 调用、岗位、反馈等资源的归属键；管理员数据另有 `admin_user_relation`。需保留这些业务主键和既有授权边界，增加 `(issuer, sub) -> local user_id` 的身份绑定映射，不以邮箱作为永久跨系统主键。
- OIDC 回调必须由 Express 服务端完成并保管 client secret、PKCE verifier 及 IAM tokens；浏览器只保留 AI 简历自己的 HttpOnly/Secure/SameSite 会话。Chrome 扩展现有的一次性授权码登录是独立客户端流程，不能误改为读取网页 Cookie 或 IAM secret。
- 本轮开始时 AI 简历 OIDC 后端文件无未提交改动；前后端现有面试题库垂直切片改动包括个人题库、管理员只读查询和增量迁移；本轮 IAM 文档只同步其状态，不覆盖其源码。`resume-browser-extension/` 未触碰。DeerFlow 与知识库各有大量既有未提交变更，接入实施必须保留并避免覆盖。

### 已完成的首版代码

- Express 增加 `/api/auth/iam` OIDC 路由，服务端执行 Discovery、S256 PKCE、state/nonce/issuer/签名校验、访问令牌内省和一次性登录 code 兑换；Vue 登录页可发起 IAM 登录。
- 新增 `(issuer, sub) -> users.id` 显式映射；用户先以原本地会话登录，再从个人资料发起绑定。不会按邮箱自动合并账户。
- IAM callback 现已要求 `offline_access`，在完成 issuer/subject 显式绑定后将已校验 access/refresh token 使用专用 `IAM_TOKEN_ENCRYPTION_KEY` 做 AES-GCM 加密保存；`services/iam/iamSession.service.js` 提供加锁续期与 token/subject/tenant 一致性校验。浏览器仍只兑换本地 JWT/refresh session。中央 authorization client 已用于简历/PDF 资源、AI 入口和实际模型调用、用户钱包读/充值，以及用户工作区和浏览器扩展本人简历回填/岗位收藏/进度/分析；岗位分析同时检查 `ai.generate`，Provider 再检查实际模型。管理员钱包与管理端岗位、共享上传、组织范围 `data_scope` 尚未接入，目标角色授权与真实 IAM 仍待验收。
- `database/init.sql` 当前定义 42 张表，其中包含四张 IAM OIDC 表和三张面试题库表；AI 任务目录为 15 项、简历模板为 60 个。面试题生成/个人题库/管理员只读查询代码已实现，AI 简历 PRD 标记为验收中；Vite 构建 6021 modules 通过。AI Resume Node suite 的旧快照为 26/26；截至 2026-10-05，扩展用户工作区授权后的全量 suite 为 31/31。`20260928_iam_oidc_sso.sql` 与 `20260929_interview_question_bank.sql` 均未做 PostgreSQL 演练；既有业务 `20260927_full_workspace_upgrade.sql` 仍缺失。源代码规模已核对，但旧库升级快照因缺少业务增量文件仍失败；不要对既有库执行 `init.sql` 或假定缺失迁移可用。

### 接入实施顺序

1. 为首版实现创建 confidential client，登记精确 HTTPS callback；将 client secret 通过服务端 Secret Manager 注入。首版 Express 适配直接服务端完成 OIDC，后续如改用共享 SDK，再解决 CommonJS/ESM 边界。不得将 secret 注入 Vue。
2. 复用现有 iam_identity_links 的 (issuer, sub) -> local user_id 显式映射；IAM access/refresh token 服务端加密保管与串行 refresh rotation helper 已实现，仍需在登录态验收本地会话绑定、撤销与登出语义。既有账号只能在用户验证本地凭证后显式关联；禁止按 email 静默合并、覆盖或迁移账号。新 IAM 用户按 USER 最小权限创建本地资料与零余额钱包，冲突时拒绝自动开户并转人工关联。
3. 以本地登录 + IAM SSO 双轨灰度：原密码/邮箱登录保持可回滚；完成身份关联和管理员应急验证后，再决定是否收敛为 IAM 单点登录。密码重置、封禁和 IAM refresh/access token 撤销的会话语义要一致。
4. AI 简历的简历 API 在线检查 `resume.read`、`resume.write`、`resume.export`，整个 `/api/ai/*` 路由组检查 `ai.generate`，PDF 专用路由按文件读取/写入检查 `resume.read/write` 并对识别/优化检查 `ai.generate`，出站模型调用检查实际模型的 `model.invoke`；用户端钱包读取和充值申请另检查 `resume.wallet.read`、`resume.wallet.recharge`，继续按本地 `user_id` 隔离。本地开发 IAM 数据库已于 2026-10-09 迁移至 `0021_resume_wallet_perms`；`0017`–`0021` 不会自动授予角色，其它环境仍需独立审阅并迁移，管理员仍须向 AI Resume OAuth 应用角色显式授予对应权限。模型键到租户模型 UUID 的服务端映射由 `IAM_MODEL_ID_MAP_JSON` 提供。IAM 配额治理/用量结算和本地钱包扣费仍独立；个人简历和 AI 数据继续使用产品本地身份与归属过滤；管理端简历列表/详情已请求中心 tenant/self data_scope 并与本地管理员归属求交，组织和其它资源尚未接入。共享 `/api/upload/file`、钱包管理员操作、岗位、其它管理 API 及知识库、DeerFlow 尚未完成中央权限与数据过滤接入。
5. AI Resume 用户简历、岗位收藏/进度/重新分析、用户工作区及浏览器扩展回填已接入产品级在线权限；继续覆盖共享上传、钱包管理员操作/数据范围、管理端岗位和其它管理 API、反馈与后台任务。请求主体必须来自服务端会话，保持 `user_id`/`admin_user_relation` 过滤，不接受客户端提交归属覆盖。逐表完成租户字段/身份映射后，才可将 SDK scope 编译并执行到业务 SQL；扩展登录继续通过已认证网页会话换一次性 code，不把 IAM secret 或长期 token 交给扩展。
6. 在隔离数据库演练身份冲突报告、管理员映射、匿名/演示数据隔离、回滚和旧 refresh token 失效后，才切生产流量。不得直接执行现有或新增增量 SQL 到未知数据库。

### 完成验收

- IAM 新登录、已有本地账户显式关联、重复/冲突身份、停用/撤销和退出场景通过服务端集成验收；本地原认证按灰度方案可回滚。
- 两个 IAM tenant、两个本地用户的简历、上传、岗位、账单与管理员数据范围矩阵通过隔离 PostgreSQL 验收；知道他人资源 ID 不能读写，异步任务沿用同一可信 owner。
- IAM 权限码清单与本地权限路由逐项对齐，授权 API 故障/缺失策略默认拒绝；后台管理员不得由普通用户配置提升。
- 灰度/回滚开关、既有账号映射冲突报告、演示/孤儿数据处理和管理员应急步骤齐全。

### 曾接入：知识库（已撤销）

### 盘点事实

- FastAPI + SQLAlchemy async + PostgreSQL，另有 Celery worker；API 分为控制面与应用运行面。
- 控制台当前有独立签名 Cookie 会话：`/control/v1/session/login|me|logout`。成员有 admin/maintainer/observer 和应用 grant；成员停用/改密通过 session version 失效。应用运行时 API Key 解析成不可由请求覆盖的 `ApplicationContext(application_id, environment_id, scopes)`。
- 应用、环境和 scope 隔离已存在；知识/检索路由还需要保留应用 API Key 与当前 scope 的 runtime 身份语义。IAM 不能把控制面用户 OIDC token 当成应用 runtime API Key 直接使用。

### 历史实现快照（已从产品代码清理）

- 保留服务端 OIDC Authorization Code + PKCE S256、同源 Discovery、RS256/JWKS ID Token、state/nonce/at_hash、一次性回调和 issuer/sub 到本地 Member 的显式绑定。
- 授权回调内省 access token，验证 active/issuer/client/audience/subject/tenant/expiry；把 access/refresh token 用独立 AES-GCM vault 加密保管。快到期时通过 refresh-token rotation 更新密文；中心请求失败时 fail closed。
- 绑定成员访问应用控制面时，在线检查 `knowledge.read`（读取）、`knowledge.write`（修改）、`knowledge.admin`（平台级管理）；权限码彼此独立，不自动继承。知识库本地角色和 ApplicationMemberGrant 仍须通过，bootstrap admin 没有 `member_id` 仍不能绑定。用户菜单可提示已有绑定但 token vault 未准备就绪并引导重登。
- 新增 Alembic `0024_iam_oidc_token_vault` 与 `0025_document_iam_data_scope`（依赖链 `0023`→`0024`→`0025`）；迁移均未在本轮应用到目标数据库，KB 目标库 revision 未核实。另新增 `IAM_OIDC_TOKEN_ENCRYPTION_KEY` 和权限码配置。知识库 IAM 定向回归 35/35、改动文件 Ruff 通过；完整迁移演练和真实 IAM/浏览器联调仍未完成。
- 中央判权现请求并校验 `data_scope`。新文档归属从在线 IAM 身份写入；控制面 Document/Revision/Chunk、IngestionRun、Source/SyncRun、RequestTrace/Evidence/AuditEvent 与混合检索都使用显式数据范围谓词。历史未分类文档不回填，在受限成员查询下不可见。集合归档若会影响不可见文档则拒绝。启用运行面 IAM OIDC 后，还要求 `X-IAM-User-Authorization` 用户 Bearer token；API Key 仍独立决定 ApplicationContext。幂等摘要绑定 IAM 身份，重试前重新判定任务可见性。

### 接入实施顺序

1. 配置 OIDC issuer/client/secret/callback/frontend URL 和 `IAM_OIDC_TOKEN_ENCRYPTION_KEY`；登记精确 callback，令牌密钥使用 Secret Manager 注入。完成 IAM `0017`–`0021` permission/grant 和测试 issuer 准备后，在隔离 PostgreSQL 演练 KB `0023`–`0025`，再做真实 Provider/浏览器联调。
2. 对现有数据库成员先本地认证，再显式绑定 (issuer, sub) -> Member.id；不按 email 自动合并。IAM tenant、permission code、应用/环境映射仍须单独定稿，不能因此扩大现有 grants。
3. 当前已为链接成员检查 knowledge permission code，并与已有本地角色/app grant 取交集；拒绝、中心服务不可用或回包格式异常时必须拒绝。后续扩展其它权限域时继续逐个路由核实主体、租户及资源边界，不以隐藏 UI 代替 API 授权。
4. Runtime 继续由应用 API Key 建立 `ApplicationContext`，它的 application/environment/scopes 不能由用户 token 或浏览器参数改写。IAM OIDC 开启时另传 `X-IAM-User-Authorization`，服务端在线校验用户并把可信 scope 绑定到当前请求；不可仅凭应用级 API Key 推断最终用户有权读取每条文档。
5. 对索引、异步摄取、Celery 重试和向量检索传递 tenant/应用/用户权限上下文；查询必须在候选返回前执行参数化过滤。幂等响应、运行轨迹、证据、同步记录和审计也应按当前授权复核；已有数据不得通过猜测方式批量认领。

### 完成验收

- OIDC 登录/显式绑定、state 重放拒绝、错误 iss/aud/nonce、access-token introspection、refresh rotation、权限允许/拒绝、禁用成员即时失效、身份冲突、Cookie 和应急 admin 流程须通过隔离 PostgreSQL 与真实浏览器联调；Knowledge Base `0023`–`0025` 目标库 migration 和真实联调未验收。
- 应用/环境/scope 仍以 runtime API Key 服务端解析；控制面不能访问未授权 tenant/application。
- Knowledge Base 已有 35/35 定向测试和显式行级过滤源码；仍须通过隔离 PostgreSQL 真实负向用例验证 owner/tenant/organization、遗留未分类数据、幂等、同步任务与操作证据，不得把 SQL 编译测试或 IAM 控制面授权视为数据库验收。


# 运维历史摘录

本文供合并进中文历史归档，整理于 2026-10-13。以下仅为带日期的独特历史证据，不作为当前服务就绪、数据库 revision、生产部署或真实恢复结论。现行命令与门禁已合入《部署与运维》。

## 2026-09-29 · 开发环境与凭据清理

- 当时开发库 revision `0010_tenant_user_groups`，API readiness `{"status":"ok","service":"iam-api"}`；API 容器后端 unittest 61 项通过，数据库夹具回滚事务，清理服务外层回滚及 lifespan 启停检查通过；前端 vue-tsc/Vite build 通过。
- 这只代表当时开发 Compose；生产 TLS/DNS/Secret Manager、备份恢复、监控和 RPO/RTO 未验收。

## 2026-09-30 · 配置解析与分时运行复核

- 开发/生产 Compose `config --quiet` 与 `py -m compileall -q backend/app backend/tests` 通过。省略生产必填 `IAM_RELEASE_TAG` 时配置失败，未读取生产 key/构建生产镜像/启动服务/迁移。
- 当时只读 HTTP：8011 health/ready 为 ok，Discovery issuer `http://localhost:8011`，JWKS 一把 RS256 公钥，8 类匿名管理列表均 401，OpenAPI 64 路径；不代表管理 E2E 或 migration 版本。
- 同日稍后 Compose 三服务 healthy、5176 Console 200；4 项模型目录隔离契约通过，但 PostgreSQL 夹具缺 users.auth_version 失败。只读确认开发库 0010、源码 head 0016；未跑全量、未 migration/重启。healthy 不能替代 schema/E2E。
- 当时前端锁定 `pnpm@12.6.0`，冻结依赖、容器 Vue 检查及临时 Vite 3199 modules 通过；生产镜像缺 node:22-alpine 缓存，未重建。API requirements.lock 与当时 Python 3.12 runtime freeze 一致、pip check 无冲突，no-index dry-run 满足直接约束；镜像重建仍需源可达。

## 2026-10-09 · 数据库凭据恢复与本地迁移

- 用户截图显示 `up -d` 三容器 Started，随后诊断 `database_not_ready` 与 PostgreSQL password authentication failed。迁移连接阶段中止，未执行 DDL；pg_isready 不验证 API 凭据，重建 API 不修改既有数据库角色。
- 受控同步持久化 iam role 密码与本地 .env 后，API SELECT 1 成功；开发库从 `0016_permission_status` 升至 `0021_resume_wallet_perms`，当时三服务 healthy、ready 200。未删除卷、未运行 bootstrap、未确认管理登录；随后源码 head 0025、数据库仍 0021/readiness 503。
- 按用户要求轮换本地管理员密码、PostgreSQL iam 口令与 JWT secret，保留卷并同步 .env。管理员密码经重置接口、auth_version 递增、撤旧 IAM/OIDC refresh、审计 auth.password_reset.complete；哈希匹配、活动管理员 refresh 0、SELECT 1 与 ready 200 已核验。未做真实浏览器登录；SMTP_PASSWORD 为空，模型用量 key 未改，示例环境文件保持原样。不得记录真实密码。

## 2026-10-09 · 工具与构建

- Windows 离线缓存重建 pnpm Junction 依赖链接，冻结安装未下载；workspace publicHoistPattern 修复 Vue 类型解析，npm run build 通过。不是生产 Docker 镜像验收。
- production preflight 改用真实 docker.exe，并支持 -DockerPath；PowerShell Parser 与 production example config --quiet 通过。无 .env.production.local/caddy:2-alpine，未完整预检、未运行生产或连接数据库。
- backup-postgres.ps1 新增 Compose/凭据/SELECT 1/归档工具预检、custom-format dump、SHA-256 与临时文件清理。ValidateOnly 通过，未创建 archive、未改 schema；不含加密/调度/异地或恢复。

## 2026-10-10 · 源码与隔离验证

- 当时开发库 0021，源码 0027，Console/API 根路径 200，ready 503；DeerFlow Compose 未运行。根 .dockerignore 排除缓存修复 build context 读取拒绝；gateway dev 镜像可在断网一次性容器导入 adapter/authz/agents，Harness 当时 head fd_0027。未正式启动服务、migration 或改 .env。
- verify-local.ps1 当时空测试库迁至 IAM 0027，后端 161/161、Vue/Vite build 通过；主库仍 0021、iam_test_* 0。项目/文档/回收站 92/92、owner 装饰器 101/101、组合路由 532（排除 1 公网 DNS）、调度/vault 126/126 均为 DeerFlow 定向隔离证据，不代替真实 IAM/Provider/浏览器。

## 2026-10-11/12 · 最新运维基线来源

- 10-11 verify-local 随机库 head 0031、完整 IAM 后端 169/169、Vue/Vite 3205 modules 通过，runner finally 清理。首次 auth.docker.io EOF 后脚本识别该端点，重跑在线构建成功；离线回退分支未独立触发。主库未升级。
- 10-11/12 backup ValidateOnly 通过，但未创建真实受保护归档或恢复演练。Console 200、API 503 database_migration_pending、开发库 0021、源码 head 0031。
- 10-12 某 shell docker 指向 C:\Windows\System32\docker 启动拒绝、常见路径不存在，未刷新 DB；后续已恢复 CLI 并只读核验容器/revision。不可把该早期 CLI 故障覆盖后续查询证据。
- 0022–0031 只读影响审阅、不 grant、注册关闭、不可泛用 downgrade 已合入现行文档；未授权 migration。7 个旧 pytest 临时根目录安全清理确认不存在，未删除测试源码/业务数据、未跑测试。

## 2026-10-13 · 当前文档整理限制

- 最新 WORK_HANDOFF 已更新 Studio 定向修复后的 6/6 与 Ruff；完整 17,004 passed / 186 failed / 349 skipped / 3 deselected / 5 errors 是修复前快照，修正后未重跑全量，缺 uv/WinError 10106/其他失败继续归因。
- 整理会话新的 HTTP 访问被沙盒拒绝，Docker exe 路径可解析，未刷新容器/DB 或运行命令；这不会推翻 10-12/13 已有只读查询。没有 migration、真实 IAM/Provider、quota enforcement、真实归档/恢复或生产验收。


## 2026-10-13 文档合并归档：旧 API 与 SDK 表述

以下为原产品文档中的实现快照，仅供追溯。现行契约以 docs/技术架构与接入.md 和源码为准。

### 8.1 当前开发版 API 契约

所有接口位于 `/api/v1`；管理 API 需要 `Authorization: Bearer <access_token>`，且邮箱必须与服务端 `BOOTSTRAP_ADMIN_EMAIL` 一致。管理令牌仍为 HS256 短期令牌；OIDC access/ID Token 使用独立 RS256 密钥。

| 接口 | 用途 | 当前约束 |
|---|---|---|
| `POST /auth/login` | 邮箱密码登录 | Argon2 验证；未知用户执行 dummy hash；写入成功/失败审计；按账号/来源及来源 IP 的 HMAC 桶限制失败次数，超限返回 `429` 和 `Retry-After` |
| `POST /auth/password-reset/request` | 申请邮件密码重置 | SMTP 必须已配置；账号存在与否不体现在请求响应；按 HMAC 邮箱键节流；原始 token 不入库，链接 token 放在 URL fragment；前端捕获后立即从地址栏和当前历史记录项清除 |
| `POST /auth/password-reset/complete` | 使用邮件 token 设置新密码 | token 一次性且默认 30 分钟过期；密码至少 12 位；递增 auth_version 并撤销 IAM/OIDC 会话；已验证邮箱标记为已验证；离线 access token 可能活到过期，业务本地 session 由业务系统处理 |
| `POST /auth/register`、`POST /auth/register/verify` | 先申请邮箱 OTP，验证后创建账号/加入产品 | 全局 `ALLOW_PUBLIC_REGISTRATION`、应用 `open`、`tenant.kind=consumer` 三重开启；应用 `client_id` 服务端解析，浏览器不能指定租户/角色；验证前不创建活动用户/membership/会话，也不收/存密码；新用户验证后设置 12 位以上密码，既有身份须输入当前密码；政策 URL/版本随 challenge 固定，发信和兑换时复核，consent 按版本追加；创建/成员/普通角色/会话同事务提交；统一申请文案、HMAC 邮箱/IP 冷却、OTP 失败上限、可重试 outbox。隔离 PostgreSQL 完整套件从空库迁移至 `0025_registration_role_snapshot` 后 161/161 通过。开发库仍为 `0021`；只读运行复核显示 API readiness 503 `database_migration_pending`、API unhealthy、PostgreSQL/console healthy；SMTP/浏览器真实验收未完成 |
| `POST /auth/invitations/inspect`、`POST /auth/invitations/accept` | 预览并接受租户邀请 | 短期一次性 token；新账号须设 12+ 位密码，已有账号须证明当前密码；邀请角色和租户状态在接受时重新校验；前端读取 fragment 后立即清除地址栏和当前历史记录项 |
| `GET /auth/me` | 查询当前身份 | 需要短期 Bearer access JWT，并即时检查账号状态 |
| `POST /auth/refresh` | 轮换访问令牌与刷新会话 | HttpOnly/SameSite=Lax Cookie；数据库只存摘要、锁行轮换、固定绝对到期；Cookie 路径 `/api/v1` |
| `POST /auth/logout` | 撤销当前管理 access/refresh 会话并登出 | 需要 Bearer；同一事务撤销当前 refresh session 与 access JWT 的 `jti`，并清除 Cookie |
| `GET/POST/PATCH /admin/tenants` | 查询/创建租户与切换租户类型 | 平台管理员限定；新租户类型为 `organization` 或 `consumer`；切换类型前必须关闭该租户下所有应用的公开注册 |
| `GET/POST/PATCH /admin/applications`、`GET /admin/applications/{id}/registration-roles` | 查询/登记应用、配置注册策略和默认普通角色 | 创建请求必须含 1–20 个登录回调且逐项校验；PATCH 可更新资料与 `disabled/open` 注册策略；开放前服务端验证 `consumer` 租户、同租户/同应用普通角色、协议版本及已发布主题政策链接；租户、client_id、密钥、回调和信任状态仍固定；Client Secret 哈希且创建时只回显一次 |
| `PATCH /admin/applications/{id}/status` | 启停 OAuth 应用 | 请求体必须包含 `expected_status` 和 `status`；行锁下拒绝旧状态（409）；停用令牌撤销和 from/to 审计原子提交 |
| `POST /admin/applications/{id}/rotate-secret` | 轮换 confidential client Secret | 立即使旧值失效；`Cache-Control: no-store` 响应只返回一次新明文；审计不保存密钥；管理员必须协调业务端同步更新，无重叠宽限期 |
| `GET/POST /admin/users`、`PATCH /admin/users/{id}/status` | 查询/创建用户，变更全局账号状态 | 仅允许 `active/disabled/locked`；行锁 + `expected_status`，禁止操作自己的当前账号；变更递增全局 `auth_version` 并撤销所有租户的 IAM/OIDC refresh session、未兑换 authorization code 和 consent ticket |
| `GET /admin/users/{id}/sessions`、`POST /admin/users/{id}/sessions/{session_type}/{session_id}/revoke`（`session_type=management\|oidc`） | 查看 IAM 管理台和 OAuth OIDC 应用当前有效的可续期会话，并撤销单个会话 | 平台管理员限定；IAM refresh row ID 在令牌轮换期间稳定，OIDC 用 OAuth refresh-token `family_id` 识别会话；revoke 更新目标记录、撤销整个 OIDC family、写入 `user.session.revoke` 审计。目标是管理员本人时拒绝，避免远程踢掉当前管理身份；不返回 token/hash/IP/UA。在线 IAM、UserInfo/Introspection 立即拒绝新签 `sid` 会话；升级前签发的无 `sid` access token 与纯离线 JWT 验签仍有自然过期窗口。未请求 `offline_access` 的 OIDC access token 不进入持久会话列表 |
| `GET /admin/users/{id}/memberships`、`PATCH /admin/users/{id}/memberships/{tenant_id}/status`（成员变更路由同时挂载 `/tenant-admin`） | 查询成员租户关系，停用/恢复/标记当前租户成员离职 | 写操作要求目标租户 `iam.organization.manage`，授权在路由处理器内检查；状态仅 `active/disabled/departed`；行锁 + `expected_status`；成员状态递增独立 `membership_version`，不撤销同一用户其他租户会话；departed 会清理当前租户的角色/用户组/组织绑定，重新加入只能走新邀请 |
| `GET/POST /admin/groups`、`PATCH /admin/groups/{id}`、`PATCH /admin/groups/{id}/status` | 查询、创建、编辑及启停租户用户组 | 组标识/租户创建后固定；停用立即停止角色继承，成员和角色配置保留；管理员专用 |
| `GET/PUT /admin/groups/{id}/members` | 查询成员清单并全量替换组成员 | 只接受已属于该组租户的用户；写入组关系和审计为同一事务；重复提交幂等 |
| `GET/PUT /admin/groups/{id}/roles` | 查询同租户角色并全量替换组角色 | 跨租户角色返回 422；组内多个角色与成员直接角色、其他组授权一起进入默认拒绝 RBAC 判定 |
| `GET/POST /admin/invitations`、`POST /admin/invitations/{id}/revoke` | 创建、查询或撤销租户角色邀请 | 默认手动复制一次性链接；`IAM_INVITATION_EMAIL_ENABLED` 可启用共享 SMTP 邮件投递，失败时返回备用链接；只存 token 摘要；含明文链接的响应设 `Cache-Control: no-store` 和 `Pragma: no-cache`；默认有效 72 小时、最长 14 天；同租户邮箱待处理邀请由数据库唯一索引保护 |
| `GET/POST/PATCH /admin/roles`、`PUT /admin/role-bindings` | 查询/创建角色、编辑名称/说明、跨表校验后绑定 | PATCH 只接受 `name`、`description`；租户/应用/角色标识和授权关系固定；成员与角色必须在同一租户 |
| `GET/POST /admin/permissions`、`PATCH /admin/permissions/{id}/status` | 查询/创建权限编码、统计关联角色并停用或恢复 | 编码不可修改或物理删除；状态变化与审计同事务且须带 expected_status；停用保留角色授予和数据范围但在线判定默认拒绝，拒绝新增授权；恢复会重新生效保留的授予；仅平台管理员可操作 |
| `PUT/DELETE /admin/roles/{role}/permissions/{permission}` | 单项通用授权增删 | 停用编码不可新增授予；撤销仍按既有规则保留有实例级授权支撑的数据范围，否则清理失效策略 |
| `GET/POST /admin/roles/{id}/permissions`、`POST /admin/roles/{id}/permissions/preview` | 读取通用/资源级授予并预演通用授权集合变更 | 仅平台管理员；预览只读，统计直接绑定及活动用户组继承的去重活动成员，逐权限估算其它适用通用授权覆盖，并列出将清理的数据范围；不逐请求模拟实例资源和数据范围净效应 |
| `PUT /admin/roles/{id}/permissions` | 原子替换角色通用权限 | 单事务保存授权、数据范围清理和审计；资源实例级授予不变；预览版本变化时返回 409，要求重新预览 |
| `GET/PUT /admin/themes`、`PUT /admin/themes/{application_id}` | 历史版本查询及保存/发布 | 主题字段/颜色/URL 受控；暂未提供匿名主题读取或素材上传 |
| `GET /admin/audit`、`GET /admin/audit/search`、`GET /admin/overview` | 审计查询和概览统计 | 旧 `/admin/audit` 保留记录数组与 limit/action 参数；平台管理员通过 `/admin/audit/search` 进行只读筛选，limit 1–500、offset 0–100000，支持 action/target_type/target_id/outcome/actor_user_id/tenant_id 组合过滤及带时区 start_at（含）/end_at（不含），返回 `{items, limit, offset, total, has_more}` 并按 created_at 与 id 倒序稳定分页；target_type、target_id 与 outcome 当前未单独索引，数据规模增长后需按查询计划补充索引迁移；本次未增加 schema 变更。审计写入与业务写操作在同一事务提交 |
| `GET/POST /admin/models`、`PATCH /admin/models/{id}`、`PATCH /admin/models/{id}/status` | 模型目录查询、新建、非身份字段编辑及启停 | 可编辑 RPM/TPM 并清除限额；租户/模型标识不可变；状态 PATCH 需 JSON `expected_status` + 目标 `status` 并在行锁下防止过期页面覆盖；凭证引用仅接受 `vault://`/`secret://` 且响应和审计摘要不回传引用；Secret Manager 和代理未接入 |
| `POST /api/v1/internal/model-usage` | 可信模型网关上报调用计量 | 需独立 `MODEL_USAGE_API_KEY`；按唯一 request ID 幂等；检查活动租户、模型、应用、用户及成员关系；`usage_is_estimated` 标明估算值；不接收请求/响应文本 |
| `POST /api/v1/internal/model-usage/reservations` | 调用 Provider 前申请 RPM/TPM 预留 | 需网关服务密钥与租户/模型/应用/用户上下文；执行开关默认关闭，未启用或无显式限额时返回 `reservation_required=false`，完成后用普通 usage report 入账；超限 429；网关必须先执行 `model.invoke` 授权 |
| `POST /api/v1/internal/model-usage/reservations/settle` | 有效预留的调用结束后幂等结算用量并写入账本 | request ID 必须对应预留；不同载荷重用 ID 返回 409；超预留用量仍记账并标记 `overrun`；`usage_is_estimated` 标明缺少 Provider 实测用量的失败账目；不接收提示词或响应正文 |
| `GET /api/v1/admin/model-usage/summary`、`GET /api/v1/admin/model-usage/events` | 管理员查看模型请求、Token、结果、耗时及费用估算 | events 默认 limit 100，支持 `tenant_id`/`offset`，limit 限制为 1–200，返回 `{items,total,limit,offset}` 并按时间与事件 ID 稳定倒序分页；费用按目录价计算，未配置时显示未知；不等于真实账单或配额强制 |
| `POST /authorization/check` | 业务服务端 RBAC 判定 | 接受管理会话 HS256 或 Provider 的 RS256 access token；OIDC token 要求 `token_use=access_token`、`aud=client_id`，在线检查用户/租户/应用/活动成员/角色；tenant/application 被绑定到 token 上下文；允许的 OIDC 决策附带可信 `application_id`，默认拒绝 |
| `POST /admin/authorization/simulate` | 管理员只读预演指定用户授权并展示判定轨迹 | 仅平台管理员；复用线上判定服务；可选择解析数据范围；不写入角色、策略、审计或业务数据；业务判定 API 不返回诊断明细 |
| `GET/POST/PATCH /admin/organizations` | 租户部门树查看、新增、修改和启停 | 仅平台管理员；父级必须同租户，数据库复合外键防止跨租户父子关系 |
| `GET /admin/users/{id}/memberships`、`GET/PUT /admin/users/{id}/organizations` | 查询成员租户及替换组织归属 | 必须属于指定租户；支持多组织及一个主组织；关系表复合外键约束租户一致 |
| `GET/PUT /admin/roles/{id}/data-scopes` | 查询或批量替换角色对已授予权限的数据范围 | 只允许配置该角色已有权限；部门清单必须启用且属于角色租户；管理变更写审计 |
| `GET /tenant-admin/members`、`GET /tenant-admin/roles`、`GET /tenant-admin/roles/{id}/permissions` | 只读列出当前租户成员、角色及角色已授予权限 | `iam.organization.read/manage`；成员查询提供 `q/limit/offset` 并只查目标 `tenant_id`，角色和权限清单不跨租户 |
| `/tenant-admin/organizations`、`/users/{id}/memberships`、`/users/{id}/organizations`、`/roles/{id}/data-scopes` | 组织树、成员组织关系和角色数据范围查询/替换 | 组织相关数据需要目标租户 `iam.organization.read/manage`，平台管理员可跨租户。应用管理角色可通过 memberships 路由发现自己的租户关系，但不能查询其他用户或读取租户成员目录。租户工作台按权限显示读写；越权组织/角色资源按 404 隐藏。权限目录项需通过 `0017` 登记后由管理员显式授予 |
| `/tenant-admin/applications`、`/applications/{id}`、`/applications/{id}/status`、`/applications/{id}/rotate-secret` | 租户应用目录、创建/资料编辑/启停和 Client Secret 轮换 | `iam.application.read` 只读；`iam.application.manage` 允许读取和写应用资料/状态；`iam.application.secret.rotate` 单独控制密钥轮换。权限可由租户角色覆盖全租户应用，或授给绑定 `application_id` 的应用角色以限定单个应用；单独授予 rotate 不开放目录读取。新建客户端需要租户范围 manage。所有路由逐请求校验，受信状态修改仍仅允许平台管理员。权限码由 `0018_tenant_application_admin_permissions` 登记且不自动授权；本地开发库已迁移至 `0021_resume_wallet_perms`，其它环境须独立审阅并显式迁移 |
| `/tenant-admin/applications/{id}/roles*`、`/permissions?role_id=...`、`/members`、`/role-bindings`、`/members/{user_id}/roles/{role_id}` | 单应用角色、业务权限预览/替换、已授权成员查看和直接角色绑定/移除 | 每个角色查询同时限制应用与租户；权限目录必须提供同应用 `role_id`，历史系统权限仅返回该角色自身记录；写操作要求该应用 `iam.application.manage`。仅能绑定已有活动租户成员；成员查询不暴露未获该应用角色的租户用户，组继承只读显示。应用管理员不能新增 `iam.*` 权限；邀请成员由租户管理员完成。权限预览复用共享影响分析，统计直接/用户组成员并逐权限显示其它通用角色覆盖估算，仍未模拟完整实例资源和数据范围净影响；权限替换使用期望授权集避免陈旧覆盖并与审计同事务提交；无需新迁移 |
| `POST /authorization/check`（`include_data_scope=true`） | 在 RBAC 通过后解析有效数据范围 | 返回机器可读 `any_of` 条件；策略缺失/解析为空默认拒绝；业务系统负责映射并执行字段过滤 |
| `GET /.well-known/openid-configuration` | OIDC Provider Discovery | 仅公布授权码、query response、RS256、client_secret_basic 与 S256 等已实现能力 |
| `GET /api/v1/oidc/login-context?client_id=...` | 读取登录应用名称、已发布主题和可用的注册展示上下文 | 公开只读；仅全局开关、应用策略、有效普通角色、活动租户、已发布主题展示项与政策链接均有效时返回 registration，包含当前验证码冷却秒数；不返回密钥或主题草稿 |
| `GET /api/v1/oidc/authorize` | 校验 client、回调、state/nonce/PKCE 并发放一次性授权码 | 只支持 `response_type=code`、`response_mode=query`、PKCE S256；非受信任客户端先进入用户同意；`prompt=none` 不允许绕过同意 |
| `POST /api/v1/oidc/consent/context` | 校验登录会话和短时同意票据并返回应用/用户/租户/范围/主题摘要 | 票据绑定同一用户、一次性且短时有效；响应 `Cache-Control: no-store` |
| `POST /api/v1/oidc/consent/decision` | 用户批准后签发授权码，拒绝则返回 `access_denied` 回跳 | 原子消费票据；授权码和审计同事务提交；响应禁止缓存 |
| `PATCH /api/v1/admin/applications/{id}/trusted` | 管理员显式调整客户端预授权信任状态 | 新应用默认不受信任；信任降级时撤销该客户端已有 OAuth 刷新令牌 |
| `POST /api/v1/oidc/token` | 授权码兑换、OAuth 刷新令牌轮换 | URL-encoded 表单；只支持 `client_secret_basic`；短时单次 code；刷新重放撤销整族 |
| `POST /api/v1/oidc/revoke` | 撤销 OAuth refresh 或 access token | 客户端 Basic 认证；access token 仅可由所属客户端撤销，按随机 `jti` 摘要失效；无效或过期令牌返回幂等成功 |
| `POST /api/v1/oidc/introspect` | 由 confidential client 查询其 token 的实时有效状态 | RFC 7662；必须 `client_secret_basic`；只返回当前有效且属于认证客户端的 access/refresh token claims，其余统一返回 `active:false`；设置 `Cache-Control: no-store`。`token_type_hint` 仅作提示，服务端仍查找两类 token |
| `GET/POST /api/v1/oidc/logout` | OIDC RP-Initiated Logout | 要求有效签名 `id_token_hint`；只撤销该用户/客户端 refresh token，不自动定位已签发 access token；RP 应先调用 `/oidc/revoke` 撤销当前 access token；回跳 URI 精确白名单匹配且必须绑定 state，已登记 URI 不得预设 state；匹配浏览器 SSO Cookie 时一并撤销并清除。GET 的 hint 会出现在 URL；当前 Uvicorn access log 过滤器会隐藏整个 query string，生产 Nginx 只记录 `$uri`，并将此路径的错误日志阈值设为 `emerg`。外部 CDN、负载均衡器、Caddy 自定义访问日志和业务 RP 日志仍须各自配置脱敏；配置语法与 4 项脱敏单测已通过。POST 更适合避免 URL 泄露，但跨站 POST 通常不携带 SameSite=Lax Cookie，可能只完成该 RP 的令牌撤销。 |
| `GET /api/v1/oidc/userinfo` | 以 access token 读取 OIDC 用户声明 | 只返回 token scope 允许的基本 profile/email；每次确认用户、应用、租户角色仍有效 |
| `GET /api/v1/oidc/jwks` | 发布 RS256 公钥 | 不发布私钥；开发签名密钥保存于持久卷，生产须由部署密钥管理注入 |


### 9.4 服务端 SDK

- 仓库提供标准库 Python/原生 Fetch TypeScript 授权客户端，以及 Python 和 TypeScript Node.js relying-party SDK。两种 OIDC SDK 均覆盖 Discovery、授权码 + S256 PKCE、state/nonce/issuer 校验、RS256 ID/access token 验签、UserInfo subject 对比、refresh rotation、access/refresh token 撤销、RFC 7662 token introspection 及带 state 的浏览器 end-session 跳转；Python PyJWT/cryptography 由可选 `oidc` extra 引入，TypeScript RP 使用 Node Web Crypto/Fetch 且无额外运行时依赖。GET logout URL 中含 ID Token Hint，必须避免将其记入访问日志或转发 Referer。
- 授权 SDK 使用业务服务端已建立会话中的 OIDC access token；不接受 ID token。OIDC RP SDK 的 client secret、PKCE verifier、access/refresh token 必须保存在业务服务端的安全配置和会话存储，绝不交给浏览器。
- 客户端在线请求有明确超时：Python 与 TypeScript 授权 SDK 默认 3 秒，TypeScript Node.js OIDC RP 的每个 HTTP 请求默认 5 秒，均可由构造参数配置；Node 请求与响应体读取共享一个 AbortController 截止时间。授权超时/网络错误抛 `AuthorizationServiceError(503)`，OIDC RP 超时/网络错误抛 `OIDCProtocolError(503)`，授权 HTTP 拒绝保留 IAM 状态码，畸形响应按契约错误处理；调用方必须 fail closed，客户端不自动重试授权操作或状态不明的授权码兑换/refresh rotation。
- `include_data_scope=true` 且授权允许时，Python/TypeScript SDK 要求调用方提供来自本地已验签服务器会话的 tenant 和 IAM OIDC `sub`（不能传产品本地用户主键）；SDK 不把 subject 发送给 IAM，而是要求非空 `data_scope.any_of`、校验每个分支的 `tenant_id` 与本地租户相同，并校验每个 `owner.user_id` 等于当前已验证 subject。SDK 只接受固定的 `tenant`、`owner/owner_user_id`、`organizations/organization_id` 约束；缺少本地身份、跨租户、其他 subject owner、未知或结构不合法时 fail closed。`compile_postgres_data_scope` / `compilePostgresDataScope` 可将验证后的 scope 编译为参数化 PostgreSQL 谓词，每个 OR 分支独立 AND tenant，并支持业务侧把 IAM 身份映射成本地主键；SDK 不执行查询。既有 Python 授权测试 11/11；本轮 TypeScript 授权客户端测试 11/11，SDK TypeScript strict `tsc --noEmit` 通过；这不代替业务仓储过滤验收。
- SDK 可将经过结构验证的范围条件编译为参数化 PostgreSQL 谓词；SDK 不连接业务数据库，也不会替业务仓储执行该谓词。业务项目仍需完成可信主体/租户/组织 ID 映射，并在每条受保护 SQL 查询中应用谓词；向量检索等其他存储须由业务适配层实现等价过滤。空 `organization_ids` 表示无数据匹配，业务适配不得把它简化为“无限制”。
- SDK 最近一次定向回归：Python 授权测试 11/11；TypeScript 授权与 OIDC 测试合计 14/14，TypeScript strict `tsc --noEmit` 通过，包含两类客户端的请求/响应体超时、HTTP 拒绝状态保留和既有数据范围 SQL 编译场景。本轮没有运行真实 IAM 联调或 PostgreSQL 业务查询；浏览器/外部客户端验证仍需在各业务项目接入时完成。


## 2026-10-13 B04 DeerFlow baseline migration fixtures

- Updated legacy-bootstrap fixtures to create only `_BASELINE_TABLE_NAMES`, preventing test databases from pre-creating post-baseline `iam_model_usage_outbox` before its migration. No production bootstrap/runtime code changed.
- Five focused migration/bootstrap modules: **62 passed**; Ruff check and format-check passed for both modified test files. Isolated test/cache directories were removed. Full offline suite, target migration, and live IAM/Provider validation were not run.
## 2026-10-13 DeerFlow B04 migration-chain and retry follow-up
- Replaced three tests that pinned historical migration revisions as the current head with single-head ancestry checks; corrected four migration fixtures that created the later `iam_model_usage_outbox` table before replaying older revisions; aligned the first transient MCP poll retry assertion with the configured 5-second base interval. Condensed the long thread-history paragraph in `frontend/src/AGENTS.md` while retaining sequence, compaction, owner-thread anchor, and optimistic-message rules. No IAM or DeerFlow production runtime behavior changed.
- Guidance + migration-chain + migration-fixture + MCP retry selection: **27 passed**; Ruff check and format-check passed on eight Python test files. Temporary test roots were removed. The latest full offline run before these changes was 17,052 passed / 152 failed / 349 skipped / 3 deselected / 0 errors (82 warnings, 38:27); a post-fix full rerun is in progress. No target DB migration or live IAM/Provider/quota validation ran.
## 2026-10-14 快速启动指南补齐数据库待迁移处理流程

- 将本地启动命令统一为实际 `docker.exe` 路径；在 readiness 后加入 Alembic `current`/`heads` 核对，并区分迁移待执行与数据库连接故障。
- 补齐真实受保护归档、SHA-256 隔离恢复演练、迁移影响审阅、明确授权、迁移失败停止及迁移后 `ready` 复核；现有数据库不重复 bootstrap，生产迁移仍按独立发布流程。
- 同步项目进度、PRD 与根目录/前后端 README。仅静态核对文档；未运行启动、备份归档/恢复、迁移、产品测试或真实登录，开发库最近证据仍为 0021/head 0031、ready 503。

## 2026-10-14 登录页待迁移提示只读复查

- 用户截图显示数据库待迁移；直接只读请求 `/api/v1/ready` 确认 HTTP 503 `database_migration_pending`。本执行终端无可用 Docker CLI，因此未重新读取容器与 Alembic revision；0021/head 0031 保持 P284 最近成功核实值。
- 同步交接进度、PRD 与根目录/前后端 README。未运行目标数据库备份、恢复演练、迁移、构建、产品测试或真实登录；A02/A03 仍待受保护备份输入与明确迁移授权。

