# 后端技术、目录与接口说明

**2026-10-17 P312 授权批量判定端点：** 新增 `POST /api/v1/authorization/check-batch`——`AuthorizationCheckBatch` schema（`permission_codes` 1–32 个、去重校验）+ 逐码复用 `/check` 同一判定路径（抽出 `_public_decision` 共享响应逻辑，无批量旁路）；配套契约测试 `tests/test_authorization_check_batch.py` 6 例。前端管理台租户控制台改为单次批量调用（消除每 membership 5 路逐码请求）。验证：一次性容器契约测试 6/6；dev 容器运行时冒烟 401/200 且与单码 `/check` 输出逐字节一致；`vue-tsc`/Vite build 通过；`verify-local.ps1` 全量套件见 [CHANGELOG](../CHANGELOG.md) 2026-10-17 P312/P314。无 schema/迁移。

**2026-10-16 P298 模型用量筛选：** `summary` 与 `events` 增加可选 `model_id`、`outcome`、`created_from`、`created_to`（UTC 自然日，结束日含当天；开始晚于结束返回 400）。待核对列表不变。无 schema/迁移。API 容器契约测试 6/6；开发库集成测试未跑。只读确认 current=head=0031、ready 200。币种和失败原因字段仍没有。详见[验收记录](../docs/验收记录.md)。

**2026-10-15 P297 模型用量前端修复：** 本轮只修复前端 API 读取失败时把账目显示成空态的问题；后端契约、数据库、迁移未改，未运行后端测试。币种规则和失败原因字段仍待决策/设计；详见[验收记录](../docs/验收记录.md)。
**2026-10-15 P296 模型用量契约走查：** 账目 API 目前仅支持租户和分页筛选，不返回失败原因；费用币种规则未体现在契约中。前端任一相关读取接口失败会掩盖所有区域的有效数据。本轮未改 API/schema/数据库、未运行测试或迁移；详见[验收记录](../docs/验收记录.md)。
**2026-10-15 P295 模型用量后端状态：** 本轮只改前端展示；后端/API/schema/migration、数据库均未变更，未运行后端测试。账目 API 仍无失败原因字段；当前没有目标 readiness/revision 证据。

**2026-10-15 P294 模型用量契约复核：** 只读检查确认账目查询目前仅支持 tenant_id、limit、offset；响应包含 outcome 但没有失败原因字段，前端因此无法显示失败诊断。没有修改 API/schema/数据库，未运行后端测试或迁移。费用币种待产品确认。

**2026-10-15 P293 运行态记录：** 本轮仅更正运维/架构文档：P292 Docker named pipe 与 API loopback 只读探测受权限阻断，因此当前 Compose、数据库 revision/readiness、备份状态均未知；2026-10-14 的 ready 200/0031 是历史快照。未改后端/API/schema/数据库，未运行测试或迁移。由有权限的 PowerShell 环境交付只读脱敏输出后再进行 A04。

**2026-10-15 P292：** 本轮只改前端模型用量展示和 Ant 管理组件注册；后端/API/schema/数据库未改，未运行后端测试、迁移或写库。前端静态类型检查与生产构建通过；只读 Docker named pipe 和 API localhost 探测因权限失败，IAM 当前数据库 revision/readiness/备份状态、非空用量记账和真实 Provider 路径仍未核验。

**2026-10-15 P291 模型用量 UI 走查：** 后端源码、API 与数据库均未改，未运行后端测试或迁移。静态核对发现汇总 API 对零行返回 `estimated_cost: null`；前端将其直接显示为“未配置价格”，需在后续 UI 修复时结合请求数区分空数据与未知费用。浏览器显示服务正常不等于 revision/readiness 探测，本轮没有做 API/数据库访问。

**2026-10-15 P290：** IAM 后端与数据库本轮未改，未运行 IAM 后端测试、迁移或写库；Docker/API 运行态、revision/readiness 和备份可用性仍按 P288 记为未知。DeerFlow B04 未分片 Windows 离线套件为 17,149 passed、404 skipped、3 deselected、1 failed、82 warnings；失败是 DeerFlow guidance 文件超预算，不是 IAM 后端失败。A04 与 DeerFlow 目标环境仍待验。

**2026-10-14 16:40 迁移完成：** 经用户授权完成受保护备份（`D:\backup\iam-postgres`，含 SHA-256）、随机隔离库恢复演练，开发库从 0021 迁移至 `0031_model_usage_reconciliation`；`/api/v1/ready` 200，api/console/postgres healthy。首次迁移尝试曾因数据库 role 密码与 `.env` 不一致失败即停止（卷 9/27 初始化后 `.env` 10/9 改过 `IAM_POSTGRES_PASSWORD`），已在 postgres 容器内 ALTER 对齐并重建 api，方法见 `docs/部署与运维.md` 第 2 节。管理员 `admin@example.com` 密码已重置（`.env`），僵尸账号 `admin@localhost.test` 已删除。后端源码与迁移文件未修改；真实登录/管理操作验收（A04）待用户执行。注意：`deploy/*.ps1` 已修复 PowerShell 5.1 兼容（UTF-8 BOM + base64 传参）；本仓库曾于 17:30 被外部 checkout 回滚一次并已重建，勿执行 checkout/restore/reset。

**2026-10-14 15:10 只读复查（历史）：** API `/api/v1/ready` 返回 503 `database_migration_pending`；当前终端 Docker CLI 不可用，未重新读取 Alembic revision。开发库 0021/head 0031 是 P284 最近成功核实值，本轮未运行迁移、备份或后端测试。

**2026-10-14 P284：** verify-local.ps1 在随机隔离 PostgreSQL 测试库运行后端完整套件 169/169 通过，测试库迁移到 head 并自动清理，未触及 IAM 开发库。当前开发库 0021_resume_wallet_perms、源码 head 0031_model_usage_reconciliation、readiness 503；本轮未运行目标库迁移或更改后端源码。

**本地迁移操作入口：** [快速启动指南](../docs/快速启动指南.md)现列出版本核对、受保护备份、隔离恢复演练、迁移授权及迁移后复核顺序；本次仅改文档，未运行目标库迁移或后端测试。

**2026-10-14 DeerFlow B04：** 后 104 文件切片 **2,368 passed、2 failed、86 skipped、4 warnings**（通知预算修复前）；扩展管理器、通知生命周期、API pin 定向回归 **126 passed、40 skipped**，Ruff check/format 通过。缺少 `uv` 的 38 个 manager 集成用例现显式 skip；剩余 package metadata 为 `0.2.16`，源码/lock 为 `0.2.18`，后切片未在最终修复后重跑。完整快照仍是历史 17,062/142/349/3/0。用户报告 IAM UI 数据库待迁移，本轮未运行 migration 或改 quota。

**2026-10-13 文档整理：** 后端接口、OIDC/授权 SDK 与多项目简单接入方案统一见 [技术架构与接入](../docs/技术架构与接入.md)；当前任务/目标环境证据见 [项目总览与进度](../docs/项目总览与进度.md)。本轮只改文档引用，未运行后端测试、迁移或真实联调。
**2026-10-13 DeerFlow B04 最新进度：** 最近完整 Windows Python 3.12 离线快照 **17,062 passed / 142 failed / 349 skipped / 3 deselected / 0 errors**（82 warnings，44:15），早于最后三项聚焦测试修正。`test_custom_agent.py`、`test_crawl4ai_tools.py`、`test_mcp_file_migration.py` **171 passed、1 skipped**，3 文件 Ruff check/format 通过。已补显式测试身份和 agents grants、固定公网 DNS 响应及盘符无关 URI 断言；无生产运行时变更。全量未在此后重跑；`uv`、`make`、`WinError 10106`、venv API metadata 版本不匹配及余下失败仍待处理。

**2026-10-12 DeerFlow Provider 路径审计：** 对当前仓内已知内置模型入口做静态搜索，发现共享工厂、Gateway 单次调用 scope 或 DeerMem hook 均处于 LangChain `BaseChatModel` callback 管道；直接 `init_chat_model()` 路径为已覆盖的 DeerMem；Codex Responses 自定义实现由共享工厂构造。外部扩展动态 Provider 未被本次范围穷尽。`request_id` 是每次 LangChain invocation 的本地幂等 ID；Codex 内部 HTTP retries 仍只形成一次结算。本轮为只读静态检查，未运行测试/Provider/IAM 联调或迁移。

**2026-10-12 DeerFlow 后台模型用量：** Gateway 为 DeerMem 后台定时模型调用新增单次 usage callback 工厂：调用时在 Gateway loop 重载当前用户和 OIDC vault，绑定模型档案并计量；缺少活动身份或启用计量但 admission 不可用时 fail closed；结束后立即关闭 callback。关联现有回归 20/20、Harness boundary 1/1 通过，6 个变更 Python 文件 Ruff check/format 通过。未运行全量测试、真实 IAM/Provider E2E 或迁移。

**2026-10-12 DeerFlow B01 映射状态：** 静态核对 `0026–0030` IAM permission catalog、DeerFlow `config.example.yaml` 与 Harness adapter：模型调用映射 `model.invoke` + IAM 模型 UUID，工具按服务端工具名授权；迁移只登记权限，不授予角色。未改业务源码；Docker 下 IAM 当前 revision `0021`，readiness 503；无 DeerFlow 运行容器。

**后续开发与部署入口（2026-10-12）：** [当前进度与后续计划](../docs/项目总览与进度.md) 区分源码完成、隔离验证和实际部署。IAM head 0031 已有隔离 PostgreSQL 169/169 证据，开发库本轮只读复核为 `0021_resume_wallet_perms`；Docker CLI 已恢复，IAM readiness 503、API unhealthy、Console/Postgres healthy，未运行测试或迁移；全局容器中无 DeerFlow runtime。A01 仍待目标业务环境，B04/B05 跟踪 DeerFlow 失败归因/计量覆盖。

**2026-10-12 migration 0022–0031 影响审阅：** 未运行 migration。`0022` 将现有应用注册策略默认设为 disabled、创建注册/OTP/outbox/consent 表；`0023` 为已有租户成员及 OAuth 记录补 `auth_version=1` / `membership_version=1`；`0024` 将租户默认分类设为 organization，并移除暂存密码摘要列；`0025` 消费缺少角色授权快照的待验证挑战；`0026–0030` 只追加 DeerFlow 权限目录项，不授予角色；`0031` 扩展用量预留和账目状态/来源字段。按上次已知 DB `0021` 连续升级时，注册表由 `0022` 新建，`0024/0025` 清理应影响零条；实际运行前仍要核对 revision/行数。`0022`/`0024` downgrade 会丢注册相关数据，`0023` downgrade 会把 locked/departed 归一成 disabled，`0031` 在人工核对数据存在后拒绝降级。后续 A01 已恢复 Docker CLI 并只读核实 revision `0021_resume_wallet_perms`、readiness 503；本轮未执行迁移。

**2026-10-12 清理复核：** 后端源码未发现 TODO/FIXME/NotImplemented 占位。7 个过期 pytest 临时根目录已删除并逐项验证不存在；未删除测试源码，也未运行测试。

**2026-10-12 Docker/DB 复核：** API readiness 返回 503 `database_migration_pending`；该 shell 的 `docker` 命令在 `C:\Windows\System32\docker` 启动时被拒绝，Docker Desktop CLI 标准路径不存在，无法重新查询容器或 revision。最近已知开发库 `0021_resume_wallet_perms`，源码 head `0031_model_usage_reconciliation`；未运行迁移。

**2026-10-12 DeerFlow Windows 长文件名复验：** 项目文档保留数据库中的用户显示名；Windows 完整路径超过 240 个 UTF-16 单元时改用短内部文件名，MIME 按显示名识别，历史 `original/{name}` 仍可读取。项目/文档/线程/运行四组路由回归 **225/225 通过**，4 个修改 Python 文件 Ruff check/format 通过。长测试根目录自身会触发 Windows 路径错误，改用短根目录复跑成功并删除临时产物。未改 IAM schema、migration、开发数据库或角色 grant；真实 IAM/Provider E2E 与全量后端验收未完成。

**2026-10-12 运行与数据范围状态：** 用户确认 DeerFlow 首阶段业务数据为 owner-only；IAM provider 的 owner/self data_scope 与本地 `user_id` 过滤必须同时成立，tenant/organization 范围继续拒绝。DeerFlow IAM/OIDC、模型调用、token vault、用量账本和数据范围专项回归 169/169 通过（Python 3.12 Windows，本地 mock/隔离测试，不代表线上 IAM 联调）。开发 IAM 库仍为 `0021_resume_wallet_perms`，源码迁移 head `0031_model_usage_reconciliation`；API readiness 503。Windows 全量非 live 快照 16,770/422/345/3 仅作未通过快照；短 basetemp 重跑于 34% 遇 `WinError 10106` 中断，失败尚未完成分类。

**2026-10-12 DeerFlow 模型授权边界与提取回退修复：** Gateway worker 在 Agent 装配前绑定服务端授权上下文；模型工厂给所有 run 内档案附加逐调用 `model:use` 检查。记忆提取模型通过启动期注入的 Gateway callback 重验 active user/vault、本人记忆读写范围和精确模型档案。拒绝发生在供应商调用前。定向授权回归 28/28、Harness import boundary 1/1 通过；Python readabilipy fallback 已保留安全链接/图片目标，现有 web-fetch 回归 50/50、Ruff 通过。修复前全量后端快照为 16,750 passed、442 failed、345 skipped、3 deselected；阻塞 I/O 为 116 passed、26 failed、1 skipped。后续全量结果见本文件 2026-10-12 最新状态；全量仍未通过，短路径重跑中断，失败原因未全部归因。临时新增测试和隔离目录已清理。未改 IAM schema、角色 grant 或开发数据库。

**2026-10-11 部署与验证状态：** `verify-local.ps1` 在随机隔离 PostgreSQL 库迁移至源码 head `0031_model_usage_reconciliation` 后运行完整后端套件 **169/169 通过**；开发库未迁移。Vue 类型检查与前端 production build（3205 modules）通过。开发 API readiness 仍为 503 `database_migration_pending`（开发库 `0021_resume_wallet_perms`）；真实 IAM、DeerFlow 和生产部署尚未验收。

**2026-10-11 模型用量账目分页：** `GET /api/v1/admin/model-usage/events` 与待核对列表均支持 `tenant_id`、`limit`、`offset` 并返回 `{items,total,limit,offset}`；账目按创建时间和事件 ID 倒序，待核对项按超时刻和 request ID 顺序稳定分页。处置并发冲突返回 409，管理台重载后再核对。隔离 PostgreSQL 全量套件 169/169 通过，覆盖 0031 migration 与新增的账目分页跨页用例；开发库仍未迁移。

**2026-10-11 DeerFlow webhook 生产门禁：** `DEER_FLOW_ALLOW_UNVERIFIED_GITHUB_WEBHOOKS` 现仅在非生产环境生效；`DEER_FLOW_ENV` 或 `ENVIRONMENT` 明确标记 production 时，secret 缺失即不挂载 webhook 路由、运行时也拒绝未签名请求。浏览器与 webhook 完整聚焦回归共 76/76，Ruff check/format 通过；公网 URL 用例使用固定 DNS 结果，无需外网。无 migration 或角色 grant。

**2026-10-11 DeerFlow 浏览器实时流鉴权：** Gateway WebSocket 复用请求级中央 IAM 判权，需同时拥有 `threads:read/write`，并在打开浏览器会话前核验当前 thread 的读写 owner/self data_scope；本地 owner 与 origin 检查继续生效，中央授权异常时连接失败关闭。浏览器与 webhook 合并回归 76/76，Ruff check/format 通过；公网 URL 测试固定 DNS，不依赖网络。未新增 migration 或自动角色 grant，真实 IAM/WebSocket E2E 未完成。

**2026-10-11 DeerFlow 个人偏好权限闭环：** `/api/v1/auth/preferences` 的 GET/PATCH 分别要求 `preferences:read/write`，并在访问用户偏好仓储前校验匹配已验证 IAM 身份的 owner/self data_scope；新增 IAM migration `0030_deerflow_preference_permissions` 仅登记权限、不授予角色。DeerFlow 19/19 定向测试和 Ruff check/format 通过；开发库仍为 `0021_resume_wallet_perms`，未执行迁移或真实 IAM 联调。启用 Central IAM 时必须补充权限映射、角色 grant 和本人范围。

**2026-10-11 DeerFlow runtime 镜像验收：** 默认 runtime target 未生成。首轮曾报告 uv.lock 需要更新；随后用镜像内同版 uv 对当前源码执行 uv sync --dry-run --locked --extra redis 通过，uv.lock SHA-256 保持不变。其后 runtime 构建被 Docker Hub Python manifest 与 GHCR uv 镜像匿名令牌请求 EOF 阻断，即使 pull=false 也未能解析基础镜像。dev 镜像仍可用，容器内 adapter import 已通过；需 Docker Hub/GHCR 可达或镜像源后重建 runtime。没有启动完整服务或修改数据库。

**2026-10-11 DeerFlow Gateway 镜像打包核验：** 已修复 DeerFlow .dockerignore，排除 config.yaml、extensions_config.json 及备份文件，并覆盖所有 .env* 变体；三者均只检查了文件名存在性，未读取内容。Docker daemon 在两个客户端退出后仍完成 dev 镜像；iam-deerflow-package-check:20261011 的本地 image ID 为 sha256:f2203cacf14d7a324dadcaa4d803145fcd9fd48129a9e9f15751e4beb4947456，一次性容器使用 uv run 导入 deerflow.authz.iam_deerflow 通过。未启动 DeerFlow 服务或连接/修改数据库；真实服务启动、生产发布和在线 IAM 联调仍待验收。

**2026-10-11 DeerFlow 数据范围模型核对：** 当前项目、线程、运行和文档资源按本地 user_id 归属，核心资源表没有可信 tenant_id/organization_id；tenant_id 仅见于 IAM session vault 与模型用量账目。现有 owner/self 过滤继续生效，tenant/organization scope fail closed。要启用共享访问，需先定义哪些资源可组织共享、服务端归属关系和历史数据回填，再设计迁移。

**2026-10-11 DeerFlow 异步 IAM 授权回归：** DeerFlow Python 3.12.14 虚拟环境运行 IAM SDK provider 合约 22/22 通过，互操作文件 12/12 通过（含 4 项 async data_scope）；mock-only，无真实 IAM/DB 请求。此前记录的 Windows 异步测试挂起在本次解释器中未复现。

**2026-10-11 运行状态与登出决策：** 只读查询确认开发库 revision 0021_resume_wallet_perms，源码 head 后续推进至 `0031_model_usage_reconciliation`，API /api/v1/ready 为 503 database_migration_pending；deploy/backup-postgres.ps1 -ValidateOnly 通过且不创建归档。用户决定 DeerFlow logout 保持本地清理，不把 vault access/refresh token 发给 issuer；RFC 7009 客户端原语不由 /auth/logout 调用。未迁移开发库。

**2026-10-11 登录页就绪拦截说明：** 后端接口与 readiness 契约未改；API 仍以只读方式比较数据库 Alembic revisions，不会自动迁移。Vue 登录页仅在 readiness 为服务正常时提交认证操作，并在服务恢复后再请求 OIDC 登录上下文。开发库当前 readiness 仍为 503，修复需按启动指南备份、审阅并获准迁移。

**2026-10-11 模型用量核对闭环：** IAM 新增 `0031_model_usage_reconciliation`，把 10 分钟预留期限作为管理员核对提醒；所有网关调用都会留下预留，即使配额拦截关闭。过期未结项保留在待核对队列并继续占用保守 TPM 额度，管理员可按 Provider 记录结算实测/估算 Token，或确认 Provider 从未被调用后释放。手工入账标记 `admin_reconciliation`，原因与决定同事务写审计。0031 已由隔离 PostgreSQL 全量套件验证；开发库仍停在 `0021_resume_wallet_perms`，真实服务联调尚未完成。

**2026-10-11 当前数据库迁移差距：** API `/api/v1/ready` 实测 HTTP 503 `database_migration_pending`；PostgreSQL 只读 revision 查询为 `0021_resume_wallet_perms`，源码 head 为 `0031_model_usage_reconciliation`。`public_registration_challenges` 表不存在，故 0024/0025 对旧 challenge 的更新在当前库无行可改；0026–0030 仅登记 DeerFlow permission codes，不授予角色，0031 扩展模型用量核对结构。不要让 `start-local.ps1` 自动迁移；需先生成受保护备份、完成审阅并取得显式授权，再按 `docs/部署与运维.md` 的独立 migrate profile 执行。本轮未写入数据库。

**2026-10-11 DeerFlow Console 聚合报表授权：** `GET /api/console/stats` 需要 Central IAM `runs:read`、`threads:read`、`agents:read` 及对应 owner/self data_scope；`/runs` 需要 runs/threads 读取权限与范围，`/usage` 需要 runs 读取权限与范围。所有 scope 检查发生在 SQL session/查询前，继续叠加本地 `user_id` 过滤。console router 回归 **25/25 通过**，两个修改 Python 文件 Ruff check 通过；未改 IAM 前端、数据库、迁移、角色授权或运行中的服务。

**2026-10-11 DeerFlow memory worker 提交前复核：** 被动写入在 `apply_changes/save` 前经 Gateway loop 重载 active local user 与匹配 OIDC vault session，再次校验 `memory:read/write` owner/self data_scope；每次冲突重试也复核。vault/session、loop、scope、IAM 异常或 30 秒超时都拒绝写入；queue 不存 token/capability。Updater、data-scope 与 commit callback 定向回归 **109/109 通过**，6 个 Python 文件 Ruff lint/format 通过；真实 IAM 与浏览器验收未完成。

**2026-10-11 DeerFlow OIDC 撤销客户端：** 后端 discovery 解析可选 `revocation_endpoint`，RFC 7009 客户端只对 HTTPS 发起 token revoke，并支持 Basic、POST secret、public client 和脱敏失败。该客户端目前不由 `/auth/logout` 调用；登出仍删除本地 vault 会话，不向外部 issuer 发送 access/refresh token；用户已确认保持本地登出。OIDC/vault mock 回归 41/41 通过。

**2026-10-11 早期验收快照（已更新）：** 本记录对应 0030 阶段的完整后端套件 161/161；随后 `verify-local.ps1` 已将随机隔离 PostgreSQL 库迁移到 0031，完整套件 169/169 通过，并完成 Vue 检查和 3205 模块 Vite production build。备份预检通过但未生成归档；临时库已清理，主开发库仍为 `0021_resume_wallet_perms`，API readiness 为 `503 database_migration_pending`；未做真实 IAM/OIDC 或浏览器 E2E。

**2026-10-10 技能写后返回正文的二次授权：** 自定义技能更新/回滚会返回完整正文，因此必须同时具备 skills:read 与 skills:write，且在访问/修改存储前通过两项本人 data_scope。跨切片联合回归更新为 141/141 通过；Ruff/格式检查通过 8 个 DeerFlow Python 文件。

**2026-10-10 跨切片授权回归：** DeerFlow connectors、stateless run、Agent 兼容路由、skills、MCP、subagents 与 channel worker 管理合并定向回归 138/138 通过（1 条 Starlette/httpx 弃用警告）；8 个 DeerFlow Python 代码/测试文件 Ruff check 与 format check 通过。数据库迁移与真实 IAM/browser E2E 未执行。

**2026-10-10 DeerFlow IM worker 管理入口补齐：** /api/channels 的 worker 状态读取现在需要 channels:read，重启操作需要 channels:admin 并保留本地 Gateway 管理员校验；与个人 channel 连接/凭证路由区分。纳入 worker、技能、MCP、子 Agent 的定向组合回归为 81/81 通过。

**2026-10-10 DeerFlow 技能、子 Agent 与 MCP 管理权限补齐：** Central IAM 控制用户技能 read/write/delete 与本人 data_scope；技能全局配置、托管子 Agent 管理、MCP 配置/缓存操作分别走 admin 权限，部署级变更仍保留 DeerFlow 本地管理员校验。IAM migration 0029_deerflow_agent_extension_permissions 只登记 7 个权限码、不自动授权。定向回归 79/79 通过；未应用开发库迁移、未配置生产 role grants、未做在线 IAM E2E。

**2026-10-10 DeerFlow 连接器授权补齐：** IM channels 与 Lark integrations 路由已接入 Central IAM channels:read/write/admin、integrations:read/write/admin 权限，并在个人数据读取/写入前校验本人 data_scope；部署级运行配置和安装操作同时要求 IAM 管理权限及 DeerFlow 本地管理员。IAM migration 0028_deerflow_connector_permissions 只登记 6 个权限码，不自动授权。相关 Gateway 回归 57/57 通过；Ruff check 与 10 个变更文件的 format check 通过。开发库迁移、角色授权、真实 IAM/浏览器联调未执行。

**2026-10-10 DeerFlow 无状态运行范围检查：** Gateway `/api/runs/stream` 与 `/api/runs/wait` 在 `start_run` 之前检查 Central IAM `runs:create` self data_scope；随后由 `start_run` 验证线程本地归属；旧 `/api/assistants/*` 兼容读取同样检查 `agents:read` 与本人 data_scope。Gateway 定向回归 28/28、Ruff check/format 通过；线上 IAM 联调未执行。

**DeerFlow 项目与资料授权（2026-10-10）：** 项目创建/编辑/归档/恢复和文档上传/提升/恢复先校验 `projects:write`（`action=write`）及完整响应所需的 `projects:read` 范围；文档软删除、回收站单项/批量清理及保留期清理先校验 `projects:delete`（`action=delete`）；线程文件提升/挂载也校验匹配的 `threads:read/write` 范围。检查都位于副作用前，仓储写入显式传入当前本地 `user_id`。项目/文档/回收站路由 92/92 通过，Ruff 检查通过。

owner-checked thread/run mutations also check Central IAM data scopes after local ownership and before handlers: `threads:write/delete`, `runs:create/cancel`. A run-create check has no run ID yet; cancellation binds the scope to its existing `run_id`. Auth decorator tests passed 101/101. The broader auth/thread/run/feedback/artifact/browser/MCP/upload/project selection passed 532 tests; the public-DNS browser URL case was deselected in the network-disabled container. Owner-bound write domains outside these decorators remain in the integration audit.

**DeerFlow scheduled-task authorization (2026-10-10):** HTTP task routes check Central IAM self data scopes before owner-filtered repository access (`threads:read/write/delete`, `runs:create/read`). The scheduler rechecks the active owner, route grants, data scopes, and a matching encrypted OIDC vault session before admission and again before launching a durable queued occurrence. It pauses and cancels queued work when authorization is gone; the ephemeral credential context is passed only to the Agent run and is never stored in the scheduled task. Combined scheduler/vault/router/authz regressions passed **126/126**; Ruff check passed and configured format checks passed for 9 files. IAM/DeerFlow migrations and live IAM/browser acceptance remain pending.

**当前部署边界（2026-10-11）：** IAM 源码迁移 head 为 `0031_model_usage_reconciliation`，开发数据库仍为 `0021_resume_wallet_perms`，API readiness 为 `503 database_migration_pending`。完整隔离 PostgreSQL 套件已迁移到 0031 并 169/169 通过；这不能推断开发库已迁移或 API 已恢复。

**DeerFlow 模型/工具授权（2026-10-10）：** IAM adapter 支持 `model:list`→`deerflow.model.list`，`model:use`→`model.invoke`，并要求服务端模型名到 IAM 活动模型 UUID 的 `model_resource_ids`；`tool:use`→`deerflow.tool.use` 将服务器构建的工具名作为资源 ID，IAM 角色可逐工具 grant。4 项适配器定向回归通过；仍需部署方提供模型 UUID 映射与角色 grant，完成 IAM/DeerFlow 实际联调。

**待执行 migration 数据影响审查（2026-10-10）：** 只读审查 0024_tenant_registration_audience 的升级会清空并删除旧注册 challenge 的暂存密码摘要列；0025_registration_role_snapshot 会将所有未消费的旧邮箱 OTP challenge 标为已消费，用户需重新发起注册验证。该行为是迁移设计的一部分，执行前必须先完成受保护备份并取得明确维护窗口授权；本轮未执行 migration。

**本轮只读运行核验（2026-10-10）：** IAM Compose 的 API unhealthy、console/PostgreSQL healthy；IAM 开发库为 0021_resume_wallet_perms，源码 head 为 0027_deerflow_resource_permissions，宿主机绕过代理直连核验：console 5175 和 API 根路径 8002 均返回 HTTP 200；API /api/v1/ready 返回 503 database_migration_pending，API 容器因此 unhealthy。DeerFlow 开发 Compose 当前没有运行；根 .dockerignore 已排除 Python pytest/ruff/mypy/hypothesis 缓存，修复构建上下文读取 backend/.pytest_cache 被拒绝的问题；gateway dev 镜像 deer-flow-dev-gateway:latest 已构建成功，断网一次性容器成功导入 deerflow.authz.iam_deerflow、app.gateway.authz 与 app.gateway.routers.agents。源码 Alembic head 为 fd_0027_repair_run_change_seq（父版本为 0026_iam_oidc_token_vault），目标数据库版本尚未核验。本轮未启动服务、迁移数据库或修改环境凭据。
**此前隔离验证快照（2026-10-10，源码 head 0027）：** verify-local.ps1 的后端完整套件 161/161 通过；console 镜像内 vue-tsc -b 与 Vite production build 通过。更新的 0029 全量后端结果见本文件顶部。

> 当前唯一业务试点为 DeerFlow。本文较早的 AI Resume / Knowledge Base IAM 集成段落属于撤销前历史快照；相关产品专属代码、配置、migration、测试与登录入口已清理，不代表当前仓库能力。DeerFlow 项目及全局会话读取范围状态以[接入计划](../docs/技术架构与接入.md)为准。

更新时间：2026-10-11。IAM 后端仍提供通用 OIDC、RBAC、资源授权、数据范围、会话与服务端 SDK；当前唯一业务系统试点为 DeerFlow。

DeerFlow 自建 Agent 管理使用 `agents:read/write/delete` 与对应本人 data_scope，并继续按 DeerFlow 本地 `user_id` 限定数据。创建/更新响应包含完整 Agent 定义，故写请求还要求 `agents:read` 权限和范围。部署级共享 `USER.md` 仅由 `agents:admin` 读写，PAT 不可调用。IAM migration `0027_deerflow_resource_permissions` 只登记 Agent/记忆权限码，不自动 grant；开发库仍为 `0021_resume_wallet_perms`，未迁移。

本次 Agent 授权、PAT、`/auth/me` 与路由互操作定向回归 **90/90 通过**（1 条 Starlette/httpx 弃用警告）；8 个变更 Python 文件 Ruff check/format 通过。Windows 受限进程不能创建 asyncio loopback socketpair，pytest 在允许本机 socketpair 的进程上下文中完成。

**DeerFlow 范围检查（2026-10-10 历史快照）：** 已覆盖项目/线程/运行读取、项目文档/内容、项目线程文件聚合、回收站和个人记忆数据；中央拒绝或 data_scope 不可用时 handler 不会读取数据。记忆 API 权限为 `memory:read/write/delete/admin`，完整记忆响应的变更接口还要先通过 `memory:read` data_scope。记忆/权限/PAT 回归 118/118 通过；文档/回收站回归 72 通过、2 跳过，当时 Windows 长路径压力测试有 1 项受 `WinError 3` 阻塞，该问题已于 2026-10-12 修复并在路由回归中复验通过。正式 IAM 映射和真实部署仍待验收。

本轮已清理 AI Resume 与 Knowledge Base 仓库中的产品专属 IAM/OIDC runtime、数据范围适配、专属 migration/测试/配置和前端登录入口；两套产品保留原有本地认证、成员管理和业务模块。未修改产品 `.env`，未对任何产品数据库执行迁移。

DeerFlow 的 IAM Provider、Gateway/Agent 授权与资源数据范围进展见 [集成计划](../docs/技术架构与接入.md)。Knowledge Base 改动验证：107 个 Python 文件 AST 解析通过，非数据库相关回归 8/8、前端 contracts typecheck 通过；PostgreSQL 迁移/生产联调未执行。

## 2026-10-09 · 用户会话目录与远程退出

新增平台管理员会话接口 `GET /admin/users/{user_id}/sessions` 和 `POST /admin/users/{user_id}/sessions/{session_type}/{session_id}/revoke`。接口列出有效的 IAM `RefreshSession.id` 与 OIDC `OAuthRefreshToken.family_id`，不回传 token hash；目标为当前管理员本人时远程撤销返回 400。IAM refresh rotation 在原记录替换 token hash、保留 session UUID 与绝对到期时间；新 IAM access JWT 带该 `sid`。带 `offline_access` 的新 OIDC token 使用 family ID 作为 `sid`，IAM 在线鉴权、UserInfo 和 Introspection 检查 family 状态。无需数据库迁移；旧无 `sid` access token 继续自然过期。当前没有记录 UA/IP/last-seen，未请求 `offline_access` 的 OIDC 短期 access token 不进入会话目录。完整隔离 PostgreSQL 套件从空库迁移至源码 `0025` 后 161/161 通过。最近只读复核开发库为 `0021`、API readiness `503 database_migration_pending`、API unhealthy 且 PostgreSQL/console healthy；没有对开发库迁移。

## 2026-10-09 · ToC 自助注册实现

`POST /auth/register` 只创建短期验证码申请和邮件 outbox，不接收/保存密码；前端第一屏也不显示密码框。`POST /auth/register/verify` 验证 OTP 后才设置新用户 12 位以上密码，或验证已有 IAM 用户的当前密码，然后原子创建/关联身份、加入 OAuth Application 所属租户、绑定服务端指定的同应用普通角色、记录条款/隐私 URL 与版本并签发会话。旧 URL 或版本变更会使 challenge 不能发信/兑换，同意证据按用户、应用、版本保存且不会被后续版本覆盖。`/oidc/login-context` 只在注册可用时返回后端配置的验证码重发冷却秒数，前端按该值显示倒计时。migration `0024` 清除旧待验证 challenge 的密码摘要。全局 `ALLOW_PUBLIC_REGISTRATION`、逐应用 `registration_policy=open` 和 `tenant.kind=consumer` 缺一不可，默认关闭；主题 `show_register` 只控制入口展示。开放注册时必须配置独立于 JWT 的至少 32 字符 `PUBLIC_REGISTRATION_SECRET`，稳定密钥用于邮箱/验证码 HMAC 与 outbox 重试。默认角色拒绝 IAM/管理 scope 和 tenant/organization 数据范围；产品 API 仍必须按 owner 过滤。

源码 migration head 为 `0025_registration_role_snapshot`。本次完整执行 `verify-local.ps1` 端到端通过：随机临时 PostgreSQL 库从空库迁移至 `0025` 后完整 suite **161/161**，console 锁定依赖镜像构建及 Vue/TypeScript、Vite production build 均通过。开发库仍为 `0021_resume_wallet_perms`，API readiness 为 `503 database_migration_pending`；真实 SMTP、浏览器注册/管理状态变更和开发库 migration 未验收。普通角色拒绝 `iam.*`/管理 scope 与 tenant/organization 数据范围；同意留痕绑定版本及链接，挑战会绑定角色授权快照。公开注册仅允许 `consumer` tenant，迁移将所有存量 tenant 默认归为 `organization`。生产开放前还须配置专用 ToC tenant、应用普通角色、版本化政策链接、SMTP、WAF/邮件额度；CAPTCHA、退信/配额看板和注册分析仍待建设。

根目录 `verify-local.ps1` 是 Windows 本地完整验证入口：一次性 API 容器运行 `tests/run_isolated_postgres_suite.py`，随后构建前端 `console` 镜像，在 Dockerfile 内执行锁文件安装、Vue/TypeScript 检查和 Vite build。后端 runner 只创建和删除随机 `iam_test_<uuid>` 数据库，不触碰开发库 `iam`；启动运行环境使用根目录 `start-local.ps1`，它以最多 12 次有限探测等待 API readiness，重试连接异常/502，并立即报告数据库迁移或连接类 503；它不会自动升级 schema 或引导管理员。

部署备份和恢复演练脚本位于根目录 `deploy/`，不属于 API 启动流程。`verify-postgres-restore.ps1` 校验备份 SHA-256 后，仅在随机隔离数据库恢复并检查 revision/关键表；它不会升级或改写开发库 `iam`，真实归档恢复、API readiness 和 OIDC 联调需在具备相应环境的部署窗口单独验收。

API 后台凭证清理和注册验证码发件箱先检查 `/api/v1/ready`。开发库尚未迁移到源码 head 时，任务会等待下一个周期，不查询缺失的新表；迁移完成后自动继续。API readiness 仍如实返回 `503 database_migration_pending`，该等待逻辑不会代替迁移。

## 2026-10-09 · 全局账号与租户成员生命周期

全局 `User.status` 限定为 `active/disabled/locked`，租户 `TenantMembership.status` 限定为 `active/disabled/departed`。全局停用/锁定递增用户 `auth_version` 并撤销所有 IAM/OIDC refresh sessions；租户成员变化递增成员 `auth_version`，使该租户 token 上的 `membership_version` 不再有效。停用成员保留当前租户角色供恢复；离职清除该租户 role/group/organization 绑定并保留历史 membership，重新加入需要新邀请。其它产品的 membership 与会话不因单租户离职而退出。

`PATCH /admin/users/{user_id}/memberships/{tenant_id}/status` 也挂载在 tenant-admin 路由下；处理器必须先验证当前操作者对目标 tenant 的 `iam.organization.manage`，然后才锁定和更新成员。本人不能停用/离职自己的当前成员。离线只校验 JWT 的资源方无法即时看到撤销，当前 OIDC access token 最长可存活到其 10 分钟有效期结束；敏感授权需要在线 UserInfo/introspection/authorization。源码 migration head 为 `0025_registration_role_snapshot`；本地开发库仍停留在 `0021_resume_wallet_perms`。

## 2026-10-09 · OIDC 租户身份声明

OIDC Provider 的签名 ID Token 现在包含所属应用的 `tenant_id`，Discovery `claims_supported` 同步公布此声明。Python RP SDK 仍以签名 access token 的 tenant 为权威；若 ID Token 也包含 tenant claim，则拒绝两者不一致。回归代码位于 `tests/test_oidc_tenant_claim.py` 与 `sdk/python/test_iam_oidc.py`；本地 Python runtime 缺少 FastAPI/PyJWT，因此 Python provider/RP 用例未运行。TypeScript 授权与 OIDC SDK 回归 14/14、strict TypeScript 检查通过。资源方仍须验证签名、issuer、audience、expiry 和 subject；租户声明只提供可信上下文，不授予角色或权限。DeerFlow 的服务端 token vault 已有可选实现，在线 IAM 授权仍待接入。

## 2026-10-09 · 服务端 token vault 加密 SDK

`sdk/python/iam_token_vault.py` 新增可选 AES-256-GCM token 加解密 helper，附加认证数据绑定可信 issuer、OIDC subject、tenant 和 token 类型，并对 UTF-8 明文大小及密文 envelope 做上限校验。IAM authorization、DeerFlow adapter 与 token-vault SDK 测试子集共 25/25 通过（不含需要 PyJWT 的 OIDC RP 客户端测试）。该 helper 不访问数据库；调用方仍须实现密文持久化、独立 key ID/密钥轮换、token expiry 与 refresh rotation、登出撤销和 session 授权。DeerFlow 尚未使用它，不能据此标记 Gateway IAM 集成完成。

## 2026-10-09 · DeerFlow OIDC 账号权限约定

DeerFlow 新 OIDC 账号固定创建为 `system_role=user`；为兼容旧配置，`admin_emails` 字段仍可解析，但不再按邮箱授予管理员。既有账号不会被自动降级。要授予 DeerFlow 管理能力，仍需完成服务端 token vault、可信 tenant 上下文和 IAM 权限映射；在此之前不能视为中心化授权已接通。

## 2026-10-09 · 本地凭据轮换

按用户请求轮换了开发环境管理员密码、PostgreSQL `iam` 角色密码和 `JWT_SECRET`；新值仅写在仓库根目录被 Git 忽略的 `.env`。管理员密码通过现有 `/api/v1/auth/password-reset/complete` 流程落库，递增 `auth_version`、撤销管理员 IAM/OIDC 刷新凭证并写入审计事件。PostgreSQL 数据卷保留；管理员哈希与配置匹配、`SELECT 1`、readiness HTTP 200 和三个 Compose 健康检查均已通过。未改 SMTP 或模型用量 API Key，也未在文档记录任何密钥值。

## 2026-10-09 · 前端 UI 走查影响范围

本次 UI 走查与修复仅改 `frontend/` 的响应式表格和 Vue 输入属性；Python API、OpenAPI 契约、数据库模型与 Alembic 迁移均未改。前端 `npm run build`（Vue 类型检查与 Vite）通过；没有重跑后端 unittest，因为本轮没有后端代码变更。

## 隔离验证记录（2026-10-07）

IAM 后端本轮完整 unittest 运行 60 项，12 项在导入时因当前可用 Python venv 缺少项目依赖 `pwdlib` 失败，4 项 PostgreSQL 测试因测试进程未设置 `DATABASE_URL` 而跳过；因此当前没有完整后端测试通过结论。标准库 AST 静态解析 `backend/app`、`backend/migrations` 和 `backend/tests` 共 110 个 Python 文件，无语法错误；Python 授权/OIDC SDK 回归 20/20 通过。测试未连接数据库，未执行 migration。后续需在项目隔离 Python 环境安装锁定依赖，并为数据库集成测试配置独立测试库后重跑完整套件。

AI Resume 用户钱包接口由 IAM `resume.wallet.read` 和 `resume.wallet.recharge` 分别控制读取与提交充值申请；仅对已有显式 IAM 身份绑定的本地账号启用中央检查，未绑定账号保持兼容。余额、流水、充值资料和申请都继续从认证会话取得本地 `user_id`，不接受客户端用户 ID；管理员钱包接口仍走原本地 ADMIN/SUPER_ADMIN 授权。权限码由 IAM `0021_resume_wallet_perms` 登记，不自动授予租户角色。

个人工作区中的职业目标、面试套题/任务/练习/点评，以及自选 AI 任务模型和提示词配置，都由绑定用户的 `resume.read` / `resume.write` 在线检查保护；点评还要求 `ai.generate`。配置服务按认证会话 `req.user.id` 过滤本人记录，workspace 操作不传本地自增 ID 给 IAM。

认证邮件与邀请链接将一次性凭据放在 URL fragment；Vue 认证入口读取后立即清理地址栏及当前历史记录项。此为客户端泄露面控制，不改变服务端 token 哈希、校验、有效期和一次性消费契约。

根目录 Compose 的本地启动、API readiness 检查和 502 排查见[本地启动指南](../docs/部署与运维.md)。

非开发环境允许在 SMTP 已配置时设置 `ALLOW_PUBLIC_REGISTRATION=true`，但全局开关默认关闭，且不会自动开放任何应用。注册 schema 需要先升级到 migration `0022`–`0025`；仅 `consumer` tenant 下的应用可以开放注册。生产 Compose 将 `IAM_ALLOW_PUBLIC_REGISTRATION` 和 `IAM_PUBLIC_REGISTRATION_*` 仅映射给 API，migrate 容器保持开关关闭。实际邮件发件域、退信和公网风控仍待部署验收。

生产发布前运行 `../deploy/validate-production.ps1`，使用生产容器 UID 加载实际注入的 Pydantic 设置和 OIDC RSA key；轮换阶段加 `-IncludeKeyRotation` 检查备用 key。它不会连接 PostgreSQL 或执行迁移。PowerShell 语法解析已通过，Docker 容器级执行待部署环境验证。

## 历史本地迁移核验（2026-10-04）

最近一次只读运行核验显示数据库为 revision `0016_permission_status`，本机 API/console 当前不可用；源码 head 为 `0021_resume_wallet_perms`。修复 `0018.down_revision` 后 Alembic history 可解析；`0017`–`0021` 尚未应用且待用户明确授权。开发 Compose 普通 API 启动关闭迁移和管理员引导，分别通过显式 `migrate`、`bootstrap` profile 操作；本轮未迁移或写数据库。生产迁移仍通过发布流程的一次性 migration job 执行。

2026-10-05 隔离验证：IAM 迁移 revision capacity 与 `0021` 钱包权限目录单测 2/2 通过，Alembic 源码唯一 head 为 `0021_resume_wallet_perms`；测试未连接数据库。AI Resume Node 全套 36/36 通过，使用 `C:\Windows\Temp` 工作目录和清空的数据库/IAM 环境变量。此结果不代表数据库迁移或角色授权已验收。

管理台服务状态依赖 `/api/v1/ready`：`/health` 仅表示 API 进程存活，不能证明 Postgres 和 Alembic schema 可用；当前不匹配会通过稳定错误码 `database_migration_pending` 返回，前端据此展示迁移待处理。

## 登录失败限流（2026-10-04）

`POST /api/v1/auth/login` 在验证口令前以事务锁定两个短期桶：HMAC(`email + IP`) 与 HMAC(IP)。默认 15 分钟内前者 8 次、后者 60 次失败后暂拒请求 15 分钟，并返回 `429` + `Retry-After`；未知用户仍执行 dummy Argon2 验证，认证失败响应不暴露账号是否存在。数据库不存邮箱/IP 明文，桶到期由维护任务分批清理。成功登录仅清零当前账号/IP 组合桶，不删除同 IP 其他账号的失败轨迹。

开发默认不信任代理头，直接按 socket peer 计数。生产 API 不发布宿主机端口；Caddy 覆写专用 `X-IAM-Client-IP`，Nginx 只传递该头，FastAPI 仅在 `TRUST_PROXY_CLIENT_IP=true` 时采信并验证为 IP 地址。登录失败节流以及认证、管理、OIDC 审计事件共用此解析器；代理头缺失或非法时不会回退信任通用转发头。Caddy 默认也不信任任何上游代理，使用直接连接对端地址；若 Caddy 前有 CDN/LB，部署方须只把实际代理出口 CIDR 写入 `deploy/caddy/trusted-proxies/edge.caddy`，由 Caddy 的 `{client_ip}` 解析后再交给 API。示例位于 `deploy/caddy/trusted-proxies.example`；需要符合代理商的 X-Forwarded-For 追加行为时，再启用 `trusted_proxies_strict`。生产配置预检入口是 `deploy/validate-production.ps1`，它调用 Compose 静默解析、Caddy `validate` 与 Nginx `-t`，不会启动迁移或长期服务；需在 Docker Compose V2 和生产 console 镜像可用时运行。迁移 `0020_login_attempt_throttles` 从 `0019` 后新增表；本地开发库最近核验为 `0021_resume_wallet_perms`，源码 head 为 `0025_registration_role_snapshot`，未得到授权前不可迁移 `0022`–`0025`。

关联前端验证：管理侧栏和公开认证入口共享 `/ready` 状态并区分数据库/迁移故障；登录入口可手动重查，手动检查与 30 秒轮询不会并发重复请求；登录、邀请及密码重置表单增加必填/邮箱/密码长度与确认规则。探针有 5 秒超时，不阻塞会话恢复。Vue 类型检查与 Vite production build 通过（3205 modules，入口 381.97 KB / gzip 118.41 KB），本地 Vite 认证组件模块含新规则并返回 HTTP 200；浏览器无障碍树确认必填标记和就绪状态提示。后端 schema/API 未改变且仍为最终校验边界；未执行后端测试、迁移或数据库写入。

公开认证页也读取前端共享就绪状态并显示稳定中文提示；后端只提供既有 `/ready` 结果，不新增诊断接口或披露 revision/数据库异常。

外部授权适配复核（2026-10-09）：AI Resume 后端已有 IAM 绑定 token vault、简历/AI/model 中央权限检查与可选模型用量适配，管理端简历列表/详情已执行 tenant/self data_scope 并与本地归属求交；组织与其它数据域仍待接入 `data_scope`。知识库后端现有 OIDC 回调会内省 access token、加密保存并轮换 access/refresh token；绑定成员的控制面已请求 `include_data_scope=true` 并保留本地角色/应用授权为第二道门禁。知识库本轮新增文档 owner/tenant/organization 字段、`0025_document_iam_data_scope` 和控制面/运行面 SQL 检索、任务与操作记录过滤源码，35/35 定向回归与 Ruff 通过；数据库迁移未执行，真实 IAM/浏览器/跨成员 PostgreSQL 验收仍待完成。DeerFlow 的 token vault 与部分 Gateway/Agent 在线授权已实现，数据范围/真实环境仍待完成。逐项状态见[接入计划](../docs/技术架构与接入.md)。

部署环境变量、安全配置和业务授权映射的用户输入见[待提供配置与决策清单](../docs/部署与运维.md)；外部产品适配应由各自后端使用服务端 secret，不能将凭证放到 Vue。

## 技术栈

- Python 3.11+、FastAPI、Uvicorn、Pydantic Settings。
- SQLAlchemy 2、psycopg 3、PostgreSQL、Alembic 静态 schema 迁移。
- `requirements.txt` 保留本地开发依赖范围；Docker 镜像通过 `requirements.lock` 安装当前已验证 Python 3.12 Linux runtime 的精确包版本。当前锁与 `pip freeze` 完全一致，`pip check` 及 `pip install --dry-run --no-index -r requirements.txt` 通过。更新直接依赖时同步刷新 lock，并检查约束兼容性与后端测试。

## 控制台登录授权边界（2026-10-03）

`POST /api/v1/auth/login` 使用统一账号口令验证；平台管理员、租户管理员和应用管理员共用入口，平台或租户模式在登录后由受保护管理 API 判定。前端文案不应暗示该入口只接受平台管理员；服务端仍逐个管理接口检查相应范围权限。本轮只改认证入口文案，未改 API、数据库模型或迁移，也未提交认证请求。

## 本轮模型治理与本地状态验证（2026-09-30）

模型状态接口使用 `ModelCatalogStatusUpdate` 携带期望状态；当前 API OpenAPI 已发布必需请求体。PostgreSQL 集成夹具的当前数据库写入失败，错误指出 `users.auth_version` 列不存在（迁移 `0011_password_reset_sessions` 添加）。`alembic current` 确认为 `0010_tenant_user_groups`，源码 head 为 `0016_permission_status`。4 项独立模型合同/并发用例通过，含 PostgreSQL `FOR UPDATE` SQL 断言；没有运行 migration，完整后端测试仍未通过/未验收。开发 API readiness 和控制台首页可达不代表 ORM 与数据库 schema 已同步。

再次复核本地 Compose：API、console、PostgreSQL 均 healthy，API readiness 与控制台首页 HTTP 200。另有 4 项独立访问日志脱敏测试通过，Nginx 1.27 对生产配置执行 `nginx -t` 通过；未运行迁移或完整后端套件，数据库写入验收仍受 0010/0016 schema 差异阻断。

## 登录主题配置校验（2026-09-30）

`app/services/theme_config.py` 是登录主题 JSON 配置的单一白名单与边界校验层，供管理主题 API 调用。颜色为六位十六进制，尺寸/透明度有固定整数区间，布局/字体/阴影/背景行为使用固定枚举，文案有长度上限；图片/帮助/隐私/条款地址仅接受空值、HTTPS 或单斜线站内路径。清空可选素材地址是合法更新。拒绝未知字段、任意 CSS/HTML、可执行 scheme、协议相对 URL、凭据、片段和控制字符，不执行或注入动态样式。该能力只修改主题 JSON，不增加表或数据库迁移。独立主题校验测试 5 项通过；FastAPI 管理端完整集成仍需现有后端依赖环境下验证。
- pwdlib Argon2id 哈希口令；PyJWT HS256 用于管理会话、PyJWT + cryptography RSA/RS256 用于 OIDC；私钥只从配置的密钥路径读取。刷新会话使用高熵 opaque token，数据库只存 SHA-256 摘要并在 HttpOnly Cookie 中交给浏览器，刷新时行锁轮换、登出时撤销。

前端控制台位于同级 `frontend/`，由 Vue 工程独立安装和构建；后端不导入或托管 Vue 源码。控制台按领域首次访问加载独立 JS chunk，Docker Desktop 开发容器通过 Vite 1000ms 轮询挂载源码以保证 HMR；这些策略只影响浏览器资源请求和开发热更新，不改变 FastAPI 路由、OpenAPI schema、认证会话或数据库模型。

## 目录结构

```text
backend/
├── app/
│   ├── api/v1/               # 按认证协议和业务域组织的 HTTP adapter
│   │   ├── oidc.py           # 稳定兼容导出与 OIDC 总路由入口
│   │   ├── oidc_provider/
│   │   │   ├── authorization.py # 登录上下文、PKCE 授权和用户同意
│   │   │   ├── tokens.py     # Token、UserInfo、Introspection、JWKS、Revoke
│   │   │   ├── logout.py     # RP-Initiated Logout
│   │   │   ├── metadata.py   # Discovery 文档
│   │   │   ├── common.py     # 共享校验、审计和 HTTP 响应
│   │   │   └── constants.py  # OIDC 协议常量
│   │   ├── auth.py           # 管理会话认证与公开邀请
│   │   ├── authorization.py  # 业务端在线授权判定
│   │   ├── tenant_admin.py   # 租户委派管理入口（逐租户鉴权）
│   │   ├── model_usage.py    # 模型网关用量与配额
│   │   ├── health.py         # 健康与就绪检查
│   │   └── admin/
│   │       ├── __init__.py   # 统一平台管理员依赖和域路由装配
│   │       ├── access_control.py # 角色、权限、绑定和授权模拟
│   │       ├── audit.py      # 审计查询
│   │       ├── common.py     # 管理审计、事务冲突和受控 URL 校验
│   │       ├── groups.py     # 用户组、组成员和组角色管理路由
│   │       ├── applications.py # 应用登记和 OAuth 客户端
│   │       ├── invitations.py # 租户成员邀请
│   │       ├── model_usage.py # 模型用量管理查询
│   │       ├── models.py     # 模型目录管理路由
│   │       ├── organizations.py # 组织、成员归属和数据范围管理路由
│   │       ├── overview.py   # 平台统计概览
│   │       ├── tenants.py    # 租户生命周期
│   │       ├── themes.py     # 每应用登录主题
│   │       └── users.py      # 用户身份与状态管理
│   ├── services/             # 共享授权、租户管理授权及领域策略
│   │   ├── authorization.py       # 默认拒绝 RBAC 与数据范围解析
│   │   ├── admin_authorization.py # 租户管理员 read/manage 复核
│   │   ├── maintenance.py         # 认证凭证到期清理
│   │   └── theme_config.py        # 登录主题白名单和边界校验
│   ├── core/                 # 配置、密码哈希、身份依赖、OIDC RSA key/JWKS
│   ├── db/                   # SQLAlchemy Base、连接池和请求会话
│   ├── models/               # 按身份、组织、用户组、RBAC/数据范围、OIDC、模型等领域分文件
│   ├── schemas/              # 按领域维护的 Pydantic 请求/响应契约
│   │   ├── groups.py         # 用户组、成员和组角色管理契约
│   │   ├── applications.py   # OAuth 应用创建、资料和并发状态契约
│   │   ├── access_control.py # RBAC 和授权模拟请求契约
│   │   ├── models.py         # 模型目录、网关计量和配额契约
│   │   └── organizations.py  # 组织、成员归属和数据范围契约
│   └── main.py               # FastAPI 路由/CORS 装配
├── migrations/               # Alembic 环境与静态 PostgreSQL 迁移
├── manage.py                 # 引导管理员、开发签名密钥初始化命令
├── tests/                    # PostgreSQL 集成测试；随机 fixtures 在事务回滚
├── alembic.ini
├── Dockerfile
├── docker-entrypoint.sh      # 独立迁移模式、开发初始化及环境匹配的 API 启动
├── requirements.txt
├── requirements.lock         # Docker 镜像使用的精确版本锁
└── .env.example
```

前端 Vue 代码独立放在仓库根目录 `frontend/`，后端不导入前端模块；API 请求和响应通过 PRD/OpenAPI 契约连接。登录主题 API 位于 `api/v1/admin/themes.py`，由前端 `features/themes/LoginThemeManagement.vue` 调用；模型目录及用量 API 由 `features/models/ModelGovernancePage.vue` 消费，租户生命周期由 `features/tenants/TenantManagement.vue` 消费，应用列表/资料/信任/密钥操作由 `features/applications/ApplicationManagement.vue` 消费，成员邀请管理由 `features/invitations/InvitationManagement.vue` 消费，审计查询由 `features/audit/AuditLogPage.vue` 消费，角色及通用权限/数据范围管理由 `features/roles/RoleManagement.vue` 消费，权限目录由 `features/permissions/PermissionCatalog.vue` 消费。角色 feature 通过既有 `/api/v1/admin/roles*`、`/permissions` 和 `/organizations` 契约工作；权限目录支持读取、创建和带 `expected_status` 的软停用/恢复，返回关联角色数，稳定编码不能编辑或物理删除。Alembic `0016_permission_status` 为旧目录项补默认 `active` 状态；停用保留授权与数据范围、判权时排除，并拒绝新增停用权限授权；角色批量编辑可保留或撤销已存在的停用权限，但不能新增。状态更新锁定权限目录项并与审计同事务，恢复会重新激活仍保留的授予。邀请页面调用既有 `GET/POST /api/v1/admin/invitations` 和撤销接口，创建响应中的 bearer 链接只在页面内展示一次；服务端以 `Cache-Control: no-store`、`Pragma: no-cache` 禁止响应缓存，邀请接受仍属于公开认证路由。审计响应契约位于 `app/schemas/audit.py`，路由 `app/api/v1/admin/audit.py` 由管理路由聚合器统一执行平台管理员保护；新管理页调用 `GET /api/v1/admin/audit/search`，支持 `limit`（1–500）、`offset`（0–100000）、`action`、`target_type`、`target_id`、`outcome`、`actor_user_id`、`tenant_id`、`start_at` 和 `end_at` 精确/范围筛选。时间必须携带时区，开始时间包含、结束时间不包含；响应为 `{items, limit, offset, total, has_more}`，按 `created_at DESC, id DESC` 稳定排序。详情字段只读返回，未新增表或迁移。旧 `GET /api/v1/admin/audit` 仍返回原有记录数组并继续接受 limit/action，供已有调用方兼容。`tests/test_audit_query.py` 覆盖组合筛选、分页边界、时间校验及旧数组响应；2026-10-05 后端完整 unittest 共 99 项通过、28 项 PostgreSQL 集成用例因未提供 `DATABASE_URL` 跳过；审计查询、时间范围和旧列表契约均有隔离 SQLite 覆盖。运行使用位于系统临时目录的锁定 `pwdlib[argon2]` 依赖 overlay；没有连接数据库，也没有修改 DeerFlow 的 Python 环境。领域状态和表单均留在 Vue 工程。管理端路由按领域放在 `api/v1/admin/<domain>.py`，`admin/__init__.py` 只负责统一管理员保护和路由装配。新管理功能继续维持该边界，将可复用策略放入 `services/`、表结构放入领域模型文件；模块职责和依赖方向见[架构说明](../docs/技术架构与接入.md)。

前端用户管理由 `features/users/UserManagement.vue` 消费现有 `/admin/users`、`/admin/users/{id}/memberships`、`/admin/role-bindings` 与 `/admin/users/{id}/organizations` 契约；组织目录由 `features/organizations/OrganizationManagement.vue` 消费 `/admin/organizations` 契约。创建密码只随受保护请求提交且不回显；成员角色和组织关联仍由后端校验租户边界，未增加 API 或 schema。前端 `app/auth/AuthEntry.vue` 管理公开登录、OIDC 同意和邀请接受，`app/App.vue` 管理已登录会话及页面装配；公共 Ant Design Vue 组件先加载，管理组件注册器 `app/ui/registerManagementUi.ts` 由 `app/ui/antd.ts` 在登录/会话恢复时动态加载。认证 UI、导航/侧栏和各领域管理页面均位于独立 Vue 工程，后端只通过 HTTP/OpenAPI 契约与其集成，不导入前端源码。

FastAPI lifespan 会启动 `app/services/maintenance.py` 的认证凭证清理循环：默认每 3600 秒对每类到期记录最多回收 1000 行，参数由 `CREDENTIAL_CLEANUP_INTERVAL_SECONDS` 和 `CREDENTIAL_CLEANUP_BATCH_SIZE` 控制。仅清理已过期的 `refresh_sessions`、`revoked_access_tokens`、`oauth_authorization_codes`、`oauth_consent_requests`；数据库并发批次使用 `FOR UPDATE SKIP LOCKED`，删除和提交在独立 Session 的事务中完成。维护失败只记录错误并下周期重试，不中断 HTTP 服务。OAuth refresh token 家族必须保留旧摘要以检测重放；邀请/审计保留可查询历史；模型 usage reservation/request ID 还承担幂等，均不由此任务清理。

业务服务端集成客户端位于仓库根目录 [sdk/python](../sdk/python/README.md) 和 [sdk/typescript](../sdk/typescript/README.md)：授权客户端封装在线判定，并在请求数据范围时要求服务端已验签 session 的 tenant 与 IAM OIDC `sub`（非产品本地用户主键），校验每个 `any_of` 分支绑定当前 tenant、owner 条件匹配该 subject 且字段 kind 在白名单内；本地 subject 不发给 IAM。Python/TypeScript 授权请求默认 3 秒超时；Node 授权客户端的请求与响应体读取共用一个 AbortController 截止时间。TypeScript OIDC RP 每个 IAM HTTP 请求默认 5 秒超时，也覆盖响应体读取；超时/网络错误以 503 失败关闭，不自动重试授权码兑换或 refresh rotation。`compile_postgres_data_scope` / `compilePostgresDataScope` 生成参数化 PostgreSQL 条件，但不连接业务数据库；本地身份/租户映射与真实查询执行由业务仓储负责。此次 TypeScript 授权与 OIDC 回归合计 14/14 通过，SDK TypeScript strict `tsc --noEmit` 通过。既有 Python 授权测试 11/11；Python OIDC RP 使用可选 `[oidc]` extra，TypeScript OIDC RP 使用 Node Web Crypto/Fetch；SDK 均不接管 Cookie/session 存储或 CSRF 防护。

AI 简历 Express 是首个接入服务：已显式绑定 IAM 的账户在简历读/写/历史/数量/导出路由在线检查 `resume.read`、`resume.write`、`resume.export`，整个 `/api/ai/*` 路由组检查应用级 `ai.generate`，四类 Provider 请求在发出前还按最终运行模型检查 `model.invoke`。IAM migration `0012_resume_permission_catalog`、`0013_ai_permission_catalog` 和 `0014_model_invoke_permission` 源码登记默认权限编码，`0015_model_usage_estimation` 增加用量估算标记字段；本地开发库 `0016` 已应用这些迁移；权限迁移不自动授予角色，管理员仍需显式授予目标角色。AI 后端必须以 `IAM_MODEL_ID_MAP_JSON` 将本地 `model_key` 映射到 IAM 模型目录 UUID；多租户环境使用 tenant UUID 分层映射。AI Resume 可选配置 `IAM_MODEL_USAGE_API_KEY` 后会预留并报告/结算用量，需与 IAM 密钥一致并确保目标 IAM 环境已包含 `0015_model_usage_estimation`；IAM 配额拦截仍默认关闭，缺失 Provider 用量会标记为估算，本地钱包单独计费；个人简历 API 仍不请求 data_scope 并以本地 user_id 过滤；管理端简历列表/详情请求 tenant/self scope 并映射成本地用户 ID 后过滤，仍沿用本地 user_id 归属查询，不能视为已完成租户数据隔离。

## 2026-10-03 租户应用委派

新增 `0018_tenant_application_admin_permissions`，源码迁移 head 到 `0018`。本机最后确认数据库 revision 仍为 `0010_tenant_user_groups`，本轮没有连接数据库或执行迁移；主机 Python 缺少 FastAPI/Pydantic，因此后端测试未运行。改动相关 Python 源码和迁移通过标准库 AST 解析（100 个文件）。前端类型检查和 production build 通过，真实租户角色与浏览器互操作尚待验收。

## 2026-10-03 单应用角色和成员委派

`api/v1/tenant_admin_application_roles.py` 增加应用范围角色 CRUD/启停、业务权限目录与授权预览/替换、已授权成员查询和直接角色绑定/移除；`schemas/access_control.py` 增加应用角色和成员绑定请求契约。每个路径先复核目标应用权限，再将角色查询约束到同一 `tenant_id` 与 `application_id`；不存在或越权的应用角色按 404 处理。应用管理员只能绑定同租户已存在且启用的用户，不能检索完整租户成员目录，也不能发送邀请；组继承角色只显示来源，须由租户管理员维护组关系。新授予 `iam.*` 会被服务端拒绝，既有此类授权仍可保留或撤销。授权写入使用现有预览/原子替换服务，并把变更审计和数据更新放入同一事务。无数据库模型或迁移变更。

本轮 Python 3.12 标准库 AST 解析覆盖 62 个 `backend/app` 文件通过；宿主运行时缺少 FastAPI/SQLAlchemy，不能在本机导入后端或执行回归测试。本地 API 容器 `/api/v1/ready` 返回 `ok`，OpenAPI 发布 88 条路径并包含本路由；匿名读取应用角色列表返回 401。控制台对应 Vue 模块也能被本地 Vite 服务加载。上述只读运行证据未覆盖应用授权或数据库写入。未执行迁移，数据库仍以最后确认的 `0010_tenant_user_groups` 为准。新增回归测试补丁遭自动审查拒绝；当前目标需明确获批后再添加/运行测试。

应用权限候选目录要求 `GET /tenant-admin/applications/{application_id}/permissions?role_id=...`；服务端验证 role 属于目标应用，并只附带该角色自己的历史授权，避免读取同应用其他角色的历史 `iam.*` grants。候选业务权限仍可浏览，新增任何 `iam.*` 由预览和保存路由拒绝。

## 当前 API

租户委派 API 由 `api/v1/tenant_admin.py` 单独挂载；它复用组织和应用领域路由，并通过 `services/admin_authorization.py` 及共享 `evaluate_access` 校验目标租户/应用。组织/数据范围使用 `iam.organization.read/manage`；应用目录使用 `iam.application.read/manage/secret.rotate`，manage 包含读取，密钥轮换单独授权。应用权限可授给无 application_id 的租户角色，也可授给由 `Role.application_id` 限定的应用角色；目录按授权过滤，单项写操作再逐请求鉴权。单应用角色管理由 `api/v1/tenant_admin_application_roles.py` 承载，严格限定租户/应用角色并只列出已有应用角色成员；应用管理员可维护业务权限但不能新增 `iam.*`，只能绑定已有活动租户成员，不能发邀请或维护用户组。创建新应用只接受租户范围 manage。受信/静默授权仍由 `platform_admin` 依赖保护。平台 `/api/v1/admin/*` 继续由 `admin/__init__.py` 统一强制平台管理员身份。

完整的开发版 API 路径、行为和边界在 [PRD 当前 API 契约](../docs/产品需求.md) 中。重要接口：

- `GET /api/v1/health`：不依赖数据库的进程存活检查。
- `GET /api/v1/ready`：PostgreSQL `SELECT 1` 就绪探针。
- `POST /api/v1/auth/password-reset/request`、`POST /api/v1/auth/password-reset/complete`：SMTP 已配置时向已登记邮箱发送一次性重置链接；请求响应不泄露账号是否存在，按 HMAC 邮箱键节流；完成操作要求 12+ 位密码并递增认证版本，立即拒绝 IAM 在线管理/OIDC 请求中的旧令牌、撤销 IAM/OIDC 刷新凭证。业务产品自己的本地 Cookie/session 仍由产品负责失效；离线验签的 OIDC access token 在到期前仍可能被接受（开发 Compose 默认 30 分钟，生产 Compose 默认 10 分钟）。
- `POST /api/v1/auth/register`、`POST /api/v1/auth/register/verify`：申请和兑换 6 位邮箱 OTP；前端第一屏和 API 第一请求都不接收或存储密码，验证邮箱后新用户设置 12+ 位密码，已存在全局身份的用户输入当前密码且原密码不变。重发验证码保留验证页已输入的密码。应用 client_id 由服务端解析，不能提交 tenant/role/admin 字段；账号、membership、角色、同意记录与会话在验码后同事务提交。仅全局开关、应用 `open` 策略及 `consumer` tenant 同时有效时开放。申请提交已展示的条款/隐私链接与版本并与当前发布主题校验；outbox 重试和验证码兑换再次校验，避免陈旧政策 challenge 完成注册；challenge 绑定当时的默认角色 ID，角色变化后旧申请会失效并要求重发。consent 按用户/应用/版本保留地址、版本、时间与来源，不覆盖历史。按 HMAC(email/app) 与可信来源 IP 冷却、限制错误次数；OTP HMAC 摘要，outbox 不保存 OTP 明文并可重试。重复邮箱和节流请求统一提示。全局开关与应用 policy 默认关闭。本地 DB 仍是 `0021`；隔离 PostgreSQL 从空库迁移至 `0024_tenant_registration_audience` 的完整套件 152/152 通过。
- `POST /api/v1/auth/login`、`GET /api/v1/auth/me`、`POST /api/v1/auth/refresh`、`POST /api/v1/auth/logout`：短期访问令牌与服务端可撤销刷新会话；登出会撤销当前 management access JWT。刷新 Cookie 为 HttpOnly、SameSite=Lax，路径限定 `/api/v1` 供 OIDC authorize 读取；其他普通 API 仍要求 Bearer。非开发环境需 HTTPS 并设置 Secure。
- `/api/v1/admin/*`：平台管理员保护的租户、应用、用户、角色、权限、主题、审计和概览 API；应用与角色只可编辑名称/说明，租户/应用归属、OAuth 客户端与角色标识配置固定。`POST /api/v1/admin/roles/{role_id}/clone` 原子创建角色副本，默认不复制授权；请求可显式选择复制当前活动权限/资源授权及对应数据范围。租户、应用范围和禁用状态沿用源角色；直接成员及用户组角色绑定不复制，审计与复制事务一致。
- `/api/v1/admin/groups*`：平台管理员管理租户组、组成员和组角色；同租户校验由 API 与复合外键双重约束，组启停即时影响角色继承。
- `/api/v1/admin/invitations`：创建、列出、撤销租户成员邀请；创建响应含原始一次性 bearer 链接，设置 `Cache-Control: no-store` 与 `Pragma: no-cache`，数据库只存 token SHA-256 摘要；`/api/v1/auth/invitations/inspect` 和 `/accept` 为公开预览/一次性接受接口。迁移 `0006_user_invitations` 存储邀请生命周期；默认由管理员手动复制交付；可通过 `INVITATION_EMAIL_ENABLED`（Compose 中为 `IAM_INVITATION_EMAIL_ENABLED`）启用现有 SMTP 投递，邮件失败时仍返回一次性备用链接。
- `/api/v1/admin/models`：模型元数据目录；支持新建、启停和编辑提供方/端点/能力/价格/外部凭证引用/RPM/TPM。PATCH 不允许修改租户和模型标识，响应及审计摘要均不含凭证引用原文；模型授权使用 `model.invoke` 权限编码与模型 ID 资源范围。
- 模型状态 PATCH 使用 JSON `expected_status` + `status`；服务端在行锁下校验旧状态，陈旧页面得到 409，只有成功状态转换才在同一事务记录审计。
- `POST /api/v1/internal/model-usage`：供受信模型网关上报已完成调用的计数账目，需 `X-IAM-Model-Gateway-Key` 服务端密钥（配置 `MODEL_USAGE_API_KEY`，至少 32 字符）；request ID 幂等，冲突重用返回 409。接口仅写 Token/结果/耗时/`usage_is_estimated` 和身份关联，不接收提示词、响应文本或供应商密钥。迁移 `0015_model_usage_estimation` 前不要部署新请求字段。
- `POST /api/v1/internal/model-usage/reservations`：模型网关先调用 `/authorization/check` 验证 `model.invoke`，再提交租户/模型/应用/用户 ID 和预估输入/最大输出 Token。每次调用都会先持久化 10 分钟预留；`enforced` 表示是否实际启用 RPM/TPM 拦截，`reservation_required` 表示网关必须在结束后调用 settle。按租户内模型聚合 60 秒 RPM/TPM，启用且有阈值时同模型行锁串行化判断，超限返回 429；过期但未核对的预留不会自动释放，仍占用 TPM。
- `POST /api/v1/internal/model-usage/reservations/settle`：使用同一 request ID 提交 Token/结果/耗时和实测标记；同一事务把预留改为 settled 并写用量事件，重复相同载荷幂等确认，不同载荷返回 409。超出预留的真实用量照常记账并标记 `overrun`，过期预留也可结算。接口不接收 Prompt/响应正文。旧 `/internal/model-usage` 上报若有关联预留也会同步结算。
- `GET /api/v1/admin/model-usage/reviews`、`POST /api/v1/admin/model-usage/reviews`：平台管理员分页查看超过 10 分钟未结算的调用，列表返回真实待核对总数；可依据 Provider 侧记录补记实测/估算用量，或在明确确认 Provider 从未被调用后释放。原因、处理人、决定和计量信息与变更在同一事务审计；手工用量来源为 `admin_reconciliation`。手工释放不生成用量事件。
- `GET /api/v1/admin/model-usage/summary` 与 `/events`：平台管理员读取全租户或单租户用量汇总/最近明细；事件区分网关上报/管理员核对，费用从目录单价估算，未配置价格时记为未知，不作为供应商结算账单。
- 租户、应用、角色和模型状态均可由受保护管理端点启停并写入审计；应用 PATCH 只更新名称/说明，不触碰租户、client_id、密钥、回调或信任配置；角色 PATCH 仅更新名称/说明，保留现有授权关系；模型和应用仍无全字段编辑/删除。
- 角色复制通过 `RoleCloneRequest.copy_authorizations` 逐次选择授权策略，默认 `false`；启用时只复制状态为 active 的权限授予（保留 `resource_id`）及同权限数据范围，停用权限的历史授予不进入新副本。源角色状态为 disabled 时副本继续 disabled。六项隔离 SQLite 测试覆盖默认清空、显式复制、停用权限过滤、成员/组绑定隔离、重复 key 事务回滚及源角色不存在；真实 PostgreSQL 并发及浏览器写入仍待专项验收。
- `POST /api/v1/authorization/check`：认证用户在其有效租户成员关系下执行默认拒绝 RBAC 判定；仅对允许的 OIDC 请求附带已验签上下文 `application_id`，供受信业务服务关联用量，不能从请求体伪造。
- `POST /api/v1/admin/authorization/simulate`：仅平台管理员可调用；指定成员与授权请求后，调用共享 `app/services/authorization.py` 规则评估器，返回判定、检查原因、命中角色与可选数据范围。此接口不写授权/审计数据；业务 `/authorization/check` 仍仅返回 `decision`，不泄露诊断明细。
- `GET /api/v1/admin/roles/{id}/permissions` 返回角色通用及资源实例授权；`POST /api/v1/admin/roles/{id}/permissions/preview` 只读比较拟保存的通用权限，统计直接绑定及活动用户组继承的去重活动成员，逐权限扣除适用范围内其它活动角色的通用授权覆盖，并列出失去最后一条授权时将删除的数据范围策略。实例级授权、逐业务资源和数据范围没有逐项求值，人数仍是潜在覆盖估算，不代表精确净差异。
- `PUT /api/v1/admin/roles/{id}/permissions` 锁定角色并原子替换通用授权、清理已无任何授权依托的数据范围，单事务写审计；必须带预览时的 `expected_current_permission_ids`，若预览后并发变更则返回 409。资源实例授权保留。旧单项 PUT/DELETE API 仍兼容。
- `GET/POST /api/v1/admin/permissions` 返回稳定编码、状态及引用角色数；`PATCH /api/v1/admin/permissions/{id}/status` 要求 `expected_status` 并在同事务写审计。停用权限被在线 RBAC 判定排除，新角色不能授予；已有授权和数据范围保留。恢复会使剩余历史授权重新生效。
- 鉴权依赖严格分开验证管理会话 HS256 和 OIDC RS256 access token；两种 JWT 都必须带唯一随机 `jti` 且未在撤销表中。OIDC token 必须为 `token_use=access_token` 且 `aud == client_id`，并在线检查用户、活动租户/应用、租户成员和至少一个匹配角色。停用、撤销角色或撤销 token 会立即拒绝后续在线授权接口请求；OIDC token 不能调用平台管理员接口。
- OIDC access token 包含 `tenant_id`，授权检查中的 tenant/application 被绑定到签发上下文；`application_id` 可省略（后端使用 token 对应应用），提交其它应用或租户会默认拒绝。允许结果会回传该 token 绑定的 `application_id`，便于受信业务后端向内部模型用量 API 提交可信关联。HS256 管理令牌保留现有管理 API 行为。
- `GET/POST/PATCH /api/v1/admin/organizations`：按租户维护组织父子关系和启停；父节点、成员组织关系有数据库复合外键确保同租户。
- `/api/v1/admin/users/{id}/organizations`：读取或替换指定租户成员的多组织归属，可指定唯一主组织；只允许选择启用组织。
- `/api/v1/admin/roles/{id}/data-scopes`：为角色已拥有的单项权限配置 `tenant`、`self`、`organization`、`organization_tree` 或 `selected_organizations` 策略。
- 租户委派 API 位于 `/api/v1/tenant-admin/*`，组织/成员归属/角色数据范围复用 `admin/organizations.py`，OAuth 应用管理复用 `admin/applications.py`。应用权限 `iam.application.read/manage/secret.rotate` 仍由角色显式授予。源码迁移 0017–0021 已于 2026-10-09 应用到本地开发库；这些迁移不自动授予权限。真实租户登录态浏览器验收待完成。
- `/api/v1/authorization/check` 请求 `include_data_scope=true` 时先执行 RBAC，再返回机器可读 `data_scope.mode=any_of` 条件；范围策略缺失或解析后没有有效条件则默认拒绝。所有子句都带 `tenant_id`；本人条件额外匹配 `owner_user_id`，组织条件额外匹配 `organization_id`。Python/TypeScript SDK 还要求每次数据范围请求携带来自本地可信 session 的 user subject 并校验本人条件一致；该 subject 不传输到 IAM。业务服务必须把租户条件 AND 到每条 OR 子句中，不能只采信 UI 或在结果页隐藏数据。
- `sdk/python` 与 `sdk/typescript` 提供参数化 PostgreSQL 数据范围编译器；每个 OR 分支都包含 tenant 条件，owner 和 organization 约束使用参数值，列名来自业务代码固定映射。SDK 不访问业务数据库，也不推断业务表字段；本地用户/组织主键不同于 IAM ID 时由业务仓储传入可信映射。空组织范围明确编译为零行谓词，无法映射租户/资源列时必须 fail closed。真实业务查询仍需在 AI 简历、DeerFlow、知识库逐项目集成验收。
- 停用用户时在同一数据库事务撤销其全部刷新会话，随后重新启用账号也不会复活旧浏览器凭据；access JWT 仍由每次请求的账号状态查询立即阻断。
- `POST /api/v1/admin/applications`：`schemas/applications.py` 强制提供 1–20 个登录回调，路由再按 HTTPS/localhost 规则逐项验证；创建应用时生成一次性 Client Secret，仅保存 Argon2 哈希并在 `Cache-Control: no-store` 响应中回传一次。`POST /api/v1/admin/applications/{id}/rotate-secret` 立即替换旧密钥且仅回传新值一次，同样禁止缓存；审计不包含明文或哈希。OIDC 仅允许 confidential client 在服务端使用 Basic 认证。
- `PATCH /api/v1/admin/applications/{id}/status`：请求体必须带 `expected_status` 和目标 `status`；服务端在应用行锁下拒绝过期页面（409），并在同一事务撤销停用应用的刷新会话和写入 from/to 状态审计。
- OIDC Discovery：`GET /.well-known/openid-configuration`。Provider 路由位于 `/api/v1/oidc/*`：`authorize`、`token`、`introspect`、`revoke`、`userinfo`、`jwks`、公开的 `login-context` 以及需登录会话的 `consent/context`、`consent/decision`。只启用 Authorization Code + 必须 S256 PKCE；禁止 Implicit/Hybrid，回调必须精确登记，token/introspect/revoke 使用 `client_secret_basic`。
- `0007_oidc_user_consent` 增加客户端 trust 和一次性同意票据表。应用默认不受信任，每次请求授权均显示同意页；平台管理员可经确认显式信任一方客户端，信任应用仍可由用户指定 `prompt=consent` 强制展示同意。未受信任客户端请求 `prompt=none` 时返回标准 `consent_required` 错误。票据摘要绑定用户、回调、state、scope、nonce 与 PKCE，短时有效、单次消费；context/decision 禁止缓存。信任降级会撤销该应用刷新令牌。
- OIDC refresh token 只存摘要，刷新时轮换；旧值重放会撤销同一令牌族。管理员停用用户、租户或应用时会事务性撤销对应 OIDC 刷新令牌。Access token 为 10 分钟 RS256 JWT；`/oidc/revoke` 和管理台 `/auth/logout` 会按 JWT 随机 `jti` 立即撤销，在线鉴权与 `/userinfo` 共用数据库拒绝表。离线只验 JWT 签名的接入服务无法感知实时撤销，必须使用 IAM 在线授权接口或自行缩短本地缓存窗口。
- `POST /oidc/introspect` 依 RFC 7662 对认证 client 的 access/refresh token 做在线检查；JWT 与 opaque refresh token 均须属于 Basic 认证 client 且用户/租户/应用/成员/角色仍有效。无效、撤销、过期或其他 client 的 token 统一只返回 `active:false`，成功和 inactive 响应均禁止缓存；`token_type_hint` 仅为提示，服务端会尝试识别两种 token。离线只验 JWT 签名的接入服务无法感知实时撤销，必须使用 introspection/授权接口或自行缩短本地缓存窗口。
- `/api/v1/oidc/login-context` 只读当前发布主题；登录页 return_to 仅接受本站 `/api/v1/oidc/authorize` 路径，登录后回放原请求。主题图片仅限 HTTPS 或站内绝对路径，颜色/布局等配置由管理 API allow-list 验证。

## 初始运行

```powershell
cd backend
Copy-Item .env.example .env
# 编辑 DATABASE_URL、JWT_SECRET（随机至少 32 字符）和管理员账号/密码
py -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
alembic upgrade head
py manage.py bootstrap-admin
uvicorn app.main:app --reload
```

示例密码仅是占位符，部署前必须替换。Alembic 初始 revision 适用于空数据库；严禁在生产环境运行 `downgrade`。当前应用启动不会自动建表。

## 集成测试

Docker Compose 开发 API 容器挂载 `backend/tests`。运行 `docker compose exec api python -m unittest discover -s tests -v` 执行配置契约与 PostgreSQL 集成用例；数据库用例以独立连接事务隔离并在结束时回滚随机 fixtures，不创建持久账号或授权记录。

## Docker 本地开发

API Docker 镜像由 `requirements.lock` 固定 Python 包版本，并在镜像构建时执行 `pip check`；该锁与当前 API 容器 `pip freeze` 完全匹配，本机 `pip check` 无冲突。生产 Vue 控制台镜像位于独立 `frontend/Dockerfile.production`；其依赖安装固定使用前端 `pnpm-lock.yaml` 与 `pnpm@12.6.0`。离线 frozen-lockfile、`vue-tsc` 和 Vite production build（3202 modules）通过；由于当前主机没有缓存 `node:22-alpine` 基础镜像，最新前后端 Dockerfile 尚未做生产镜像重建。

仓库根目录的 `compose.yaml` 编排 PostgreSQL、API 和 Vue 控制台。将根目录 `.env.compose.example` 复制为 `.env` 并替换全部占位密钥，然后从仓库根目录运行 `docker compose up -d console`。普通开发启动只启动服务，不执行迁移或管理员引导；console 依赖 API 进程启动即可提供前端和诊断界面。确认迁移差异并获准后，使用 `docker compose --profile migrate run --rm migrate` 执行迁移；仅首次初始化且迁移完成后，使用 `docker compose --profile bootstrap run --rm bootstrap-admin` 创建管理员。生产仍由独立发布 migration job 管理。

生产部署使用根目录 `compose.production.yaml`：one-shot `migrate` 服务负责 schema 升级；API 关闭启动迁移和管理员引导，校验挂载的 RSA key 后以多 worker、无 reload 模式启动。非开发配置启动时拒绝缺失/非 PostgreSQL psycopg 数据库、弱 JWT 密钥、管理员 allow-list 或非 HTTPS OIDC/控制台地址；entrypoint 在非开发环境默认不迁移/引导管理员。生产 API 与静态管理台镜像已构建，生产 Compose 示例通过静态解析，静态 console 的健康端点和 SPA 根页已 smoke check；生产服务尚未使用真实 DNS/TLS/密钥启动。部署顺序、密钥挂载和外部备份责任见 [运维手册](../docs/部署与运维.md)。

## 鉴权、数据边界与事务

- 平台管理接口由 `platform_admin` 依赖保护；当前平台管理员来自 `BOOTSTRAP_ADMIN_EMAIL` 配置，浏览器不能通过提交角色名提权。
- 租户上下文必须匹配数据库中当前用户有效的 `TenantMembership`。角色绑定时强制检查成员和角色属于同一租户；应用角色需对应同租户应用。
- RBAC 采用 `RoleBinding → Role → RolePermission → Permission`。授权检查匹配权限编码及资源 ID，未匹配一律拒绝。前端的可见性不构成授权。
- 用户组请求契约位于 `app/schemas/groups.py`，路由位于 `app/api/v1/admin/groups.py`，表结构位于 `app/models/groups.py`。用户组通过 `UserGroupMembership` 加入租户成员、通过 `UserGroupRole` 继承同租户角色；授权服务合并直接角色与活动组角色，组停用后不再授予继承权限，组配置保留。最近一次本地开发 PostgreSQL revision `0010_tenant_user_groups`、61 项后端 unittest、API readiness 与匿名 401 快照日期为 2026-09-29。2026-09-30 再次验证本地 API `8011` readiness，以及匿名访问概览、租户、应用、用户、用户组、组织、模型、审计列表全部返回 401；本轮未能连接测试运行环境或重验数据库 revision/完整 unittest。已登录管理员浏览器操作和生产迁移仍需单独验收。
- 模型目录路由位于 `app/api/v1/admin/models.py`，模型目录与内部用量/配额契约位于 `app/schemas/models.py`；内部 `/api/v1/internal/model-usage/*` 路由保持独立。模型端点继续只接受 HTTPS 或开发 localhost，供应商凭证只保存 Secret Manager 引用。
- 组织树、成员目录/归属与角色数据范围处理器位于 `app/api/v1/admin/organizations.py`，请求契约位于 `app/schemas/organizations.py`；平台管理路径保持 `/admin/*`，委派租户管理入口由 `app/api/v1/tenant_admin.py` 暴露 `/tenant-admin/*` 并使用 `app/services/admin_authorization.py` 执行租户级 RBAC。两条路由复用相同数据校验与写入审计事务。
- 管理修改和审计事件在相同数据库事务提交；审计摘要不得记录口令、JWT、客户端秘密或供应商密钥。
- 登录主题只接收白名单 JSON 字段、十六进制颜色以及 HTTPS/站内资源地址；不执行 HTML、脚本或任意 CSS。
- 模型目录只存供应方、模型名、能力、RPM/TPM 限额元数据和 `vault://`/`secret://` 外部凭证引用。平台管理员可用 `PATCH /api/v1/admin/models/{id}` 更新非身份字段（含 RPM/TPM）；tenant/key 不属于 PATCH 契约。API 响应与审计摘要均不返回/记录凭证引用原文。当前没有 Secret Manager 读取或模型代理调用；配额限额仅在显式启用服务端开关时由 reserve API 强制。
- 用量账本 (`0005_model_usage_events`) 只允许共享密钥保护的受信模型网关上报；如 `MODEL_USAGE_API_KEY` 未配置或短于 32 字符，接口关闭并返回 503。该 key 是 gateway 到 IAM 的服务凭证，必须部署到网关服务端 Secret Manager，绝不能放 SPA。日常上报密钥当前为静态共享值，尚无多网关身份、签名轮换或细粒度服务账户。
- Alembic `0008_model_usage_reservations` 提供预留表，新增 `0031_model_usage_reconciliation` 扩展释放状态与管理员核对来源/接口。`MODEL_QUOTA_ENFORCEMENT_ENABLED` 默认 `false` 只关闭限额拒绝，不关闭调用预留持久化。10 分钟后仍未结算的行进入管理员核对；它们不会自动按上限收费或释放，并会一直占用保守 TPM 额度，直至管理员结算或在确认未调用 Provider 后释放。历史账本/预留保留周期和归档策略仍需设计。开发库目前仍为 `0021`，`0031` 未应用。
- 开发 Compose 的普通 API 启动显式设置 `IAM_RUN_MIGRATIONS=false`、`IAM_BOOTSTRAP_ADMIN=false`；Alembic 仅由 `migrate` profile 执行，首次管理员创建仅由 `bootstrap` profile 执行。生产 API 也关闭启动迁移，由独立 `migrate` 作业执行。升级前数据库备份、隔离恢复和私钥/JWT 密钥保管见 [运维手册](../docs/部署与运维.md)。
- 口令仅保存 Argon2 哈希；JWT 密钥必须至少 32 字符。刷新会话在 PostgreSQL 中只存 SHA-256 摘要、可撤销且具有固定绝对过期时间；每次续期会在行锁事务中轮换 token，重复使用旧 token 将被拒绝。管理台客户端通过共享续期 Promise 与浏览器 Web Locks 协调并发请求，服务端仍以行锁保证单次消费。登出撤销当前浏览器刷新会话及本次管理 access JWT；前端在支持 `BroadcastChannel` 的浏览器同步清除其他标签页的 token，但已复制的其他离线 JWT 在服务端到期前仍可用。管理及 OIDC access JWT 均含随机 `jti`；数据库只保存 `jti` 的 SHA-256 摘要和到期时间。OAuth revoke 支持撤销本客户端 refresh 或 access token。新撤销写入时会顺带删除已过期的黑名单行；过期前的签名与状态仍须在线检查。

## OIDC 配置与安全边界

- `app/services/access_log_redaction.py` 在 `main.py` 装配时为 `uvicorn.access` 安装过滤器：保留请求路径和状态日志，隐藏整个 query string，避免 `id_token_hint` 或以后新增的敏感 query 参数泄漏。生产静态控制台 Nginx 使用 `iam_redacted` 格式，仅记录 `$uri` 等非凭证诊断字段；精确 `/api/v1/oidc/logout` 路径将 Nginx 错误日志阈值设为 `emerg`。访问日志脱敏单测 4/4 通过，Nginx 1.27 配置语法检查通过。部署使用的 CDN、负载均衡器、开启的 Caddy access log 及业务 RP 自己的日志仍须单独脱敏。

- `OIDC_ISSUER` 必须是面向客户端的 HTTPS issuer；本地开发可为 `http://localhost` / `http://127.0.0.1`。生产 `CONSOLE_PUBLIC_URL`、API issuer、反向代理外部地址和 CORS 必须按实际域名设置，不能沿用 localhost。
- 开发 Compose 在独立命名卷初始化 RSA-3072 私钥；`APP_ENV` 非 development 时若密钥文件缺失，API 启动前必须失败。生产需从 Secret Manager 挂载至少 2048 位 RSA PEM，配置只读挂载和备份/轮换策略；当前单密钥 JWKS 还不支持平滑多 key 轮换。
- 客户端创建和显式轮换均只回传一次 Client Secret；轮换立即使旧值失效，不提供重叠宽限期，管理员须协调更新业务后端 Secret Manager。禁止将其放入 SPA；OIDC 客户端应为有安全后端的 confidential client。应用默认非受信任并逐次要求用户授权；仅平台管理员能明确设为受信任客户端，用户可用 `prompt=consent` 覆盖静默授权。
- SMTP 邮箱密码重置的源码接口、一次性 token/hash、按邮箱节流和认证版本失效逻辑已加入；生产投递依赖 `SMTP_HOST`、`SMTP_FROM`、安全传输和可选的认证配置。邮件链接只把 token 放在 `#password-reset=` fragment；2026-10-05 修复了 URL 构造中重复 `#` 的问题，纯文本邮件回归通过。此处尚未验证 SMTP 实际投递、迁移或完整重置链路。短信验证、Front/Back-Channel Logout、MFA 与 refresh token family 定时清理仍未实现。RP-Initiated Logout 已校验已签名 ID Token Hint、客户端登记的退出回跳和 state，并撤销对应用户/客户端刷新令牌；匹配时同步清除 IAM 浏览器 SSO 会话。GET 请求日志必须脱敏 `id_token_hint` 查询参数。Discovery 只公布代码中真实实现的能力。

## 关键未完成边界

源码 Alembic 迁移链已新增 `0011_password_reset_sessions`；2026-10-03 的只读 Alembic 查询确认本地开发库为 `0016_permission_status`；`0011` 已应用。生产环境仍需独立核实迁移版本。迁移为用户、管理刷新会话及 OIDC 一次性凭证增加 `auth_version`，并增加密码重置 token 与节流表。`0009_access_token_revocations` 的管理登出和 OAuth revoke 即时 access JWT 撤销链路继续生效。配额 API 已实现但执行开关默认关闭；本地无真实业务网关接入。

密码重置续审对 `backend/app` 和 `backend/tests` 的 70 个 Python 文件执行只读 AST 语法解析，通过；当前 API OpenAPI 已公布 request/complete 两个找回路由，未调用会发送邮件或变更账号状态的 POST。没有运行 unittest、DB migration 或 SMTP 投递，也未确认当前运行数据库头。账号找回链路仍需在启用邮件配置后进行 PostgreSQL 与 SMTP 集成验收。

`sdk/typescript` 现在同时提供 Node.js OIDC RP 登录和授权判定客户端；RP 模块使用 Node Web Crypto/Fetch，不依赖额外运行时包。TypeScript 服务仍须自行实现安全 session、HttpOnly Cookie、CSRF 防护及 refresh token 原子替换。

截至 2026-09-29 的 SDK 验证记录：Python 授权测试 11/11；TypeScript 授权/OIDC mock 测试 8/8；TypeScript strict build 通过。Python OIDC 测试在该轮未执行：工作区内置 Python 没有可选 `PyJWT[crypto]` extra；此前有该 extra 的项目环境测试结果仅作为历史记录，不作为当前验证依据。本次文档修订没有重跑测试。

历史验证快照（此前轮次）：Docker Desktop CLI 曾构建 API/管理台开发镜像及生产 API/静态管理台镜像；后端 39 项 unittest、Python OIDC SDK 9 项、TypeScript SDK mock 5 项通过，TypeScript strict build 通过。该组数字不代表本轮重验；当前项目进度以本文上方的近期验证和 [变更日志](../CHANGELOG.md) 为准。生产服务未在真实 TLS/DNS/密钥下启动；真实 RP 客户端/浏览器互操作、业务数据库过滤、邀请投递、网关计量和配额接入仍待完成。Nginx 静态入口新增 CSP 等浏览器安全响应头；2026-09-30 另用本地 Nginx 1.27 镜像对生产配置执行 `nginx -t` 并通过，但生产静态镜像启动后的实际响应头尚未验收。登录节流和认证/管理/OIDC 授权、登出审计现共用专用可信客户端 IP 解析，回归 5/5 通过；生产 CDN/LB 头链路、SMTP 真实投递和外部业务适配器仍待验收。

## 中文注释约定

OIDC 登录只建立可信用户身份，不会自动保护业务数据。业务服务必须在服务端校验主体、调用授权检查，并把含 `tenant_id` 的 `data_scope.any_of` 条件编译到 SQL 后执行；向量检索需实现等价过滤，具体接入差异和验收要求见 [业务系统接入计划](../docs/技术架构与接入.md)。

UI 浏览器检查状态见 [UI 走查记录](../docs/验收记录.md)；登录入口基础布局曾完成桌面/手机截图检查，后续新增的 readiness 提示和手动重查按钮还需截图验收，已登录功能页仍需本地管理员会话。2026-09-30 当前 API readiness 返回 `ok`；migration revision 与完整后端套件未确认，本轮未执行迁移或生产部署。SDK PostgreSQL 谓词编译器、映射要求与测试状态见本文上方和 [变更日志](../CHANGELOG.md)。真实域名/密钥部署、浏览器逐页视觉验收、业务查询行过滤和外部网关互操作仍未完成。

新增复杂后端逻辑时说明数据来源、校验顺序、拒绝条件、事务边界和安全原因。身份、租户、授权和令牌代码必须解释哪些数据来自服务端可信记录及为何拒绝越权输入；避免只逐行翻译简单赋值。

## 最近一次跨层开发

新增 OIDC access token 在线授权上下文、`0005` 模型用量账本、服务端 SDK、`0006` 一次性租户邀请、`0007` OIDC 用户同意/受信任客户端及 RP-Initiated Logout；测试及迁移状态见 `CHANGELOG.md`。正向数据范围、授权码兑换和退出边界已有事务回滚 PostgreSQL 集成验证；真实客户端互操作、正向用量上报待网关配置。OIDC 支持活动/备用 RSA 公钥重叠发布和按 kid 验签，轮换手册见 docs/部署与运维.md；生产仍需 SMTP 提供方配置及邀请/重置邮件真实投递验收、注册邮箱验证、MFA/限流、Front/Back-Channel Logout、真实 RP 缓存轮换演练和安全评审。

## 历史外部业务接入实现快照（2026-09-30，现已撤销）

### 2026-10-04 · AI Resume 管理端简历数据范围

管理端 `GET /api/admin/resumes` 与 `GET /api/admin/resumes/:id` 对显式链接 IAM 的管理员请求通用 `resume.read` 和 `include_data_scope=true`。服务端只接受同 tenant/self 条件：tenant 通过 `iam_oidc_sessions` join `iam_identity_links` 转成本地用户 UUID，self 通过当前已验签 IAM subject 查身份链接；解析出的用户集合与 `admin_user_relation` 求交，并传入 `resume` 仓储的列表/详情 SQL 过滤。组织范围暂时没有本地可信映射，返回拒绝；无 IAM 绑定的管理端用户继续使用既有权限与归属规则。未修改数据库结构。验证：`node --check` 8 个相关 JS 文件通过，`npm test` 23/23；未验真实 IAM、PostgreSQL 或浏览器流程。

### 2026-10-04 · Knowledge Base 资源级授权执行

知识库应用详情、应用域请求和平台管理员的应用级变更会向 IAM 传入 Knowledge Base Application UUID 作为 `resource_id`；IAM 使用 `RolePermission` 实例 grant 进行在线匹配。角色 grant revoke API 现能精确撤销该 resource ID，并且仅当同权限不再有通用或实例 grant 时才清理数据范围策略。Knowledge Base 定向测试 15 项通过。IAM 后端 AST 和 Ruff（忽略 FastAPI `Depends` 默认参数规则 B008）通过；unittest 无法启动，当前可用环境缺少 `pwdlib`。

AI 简历 Express 后端已有 OIDC Authorization Code + PKCE 登录、显式本地身份绑定和一次性 code 兑换；回调要求 offline_access，服务端以独立 IAM_TOKEN_ENCRYPTION_KEY 对 access/refresh token 做 AES-GCM 加密并保存到 iam_oidc_sessions，iamSession 服务通过行锁串行轮换 refresh token、校验 subject/tenant 不变，浏览器只获得 AI 简历本地会话。已绑定用户的简历读、写、历史、数量和导出路由在线检查 `resume.read`、`resume.write`、`resume.export`，整个 `/api/ai/*` 路由组在线检查应用级 `ai.generate`；文本、流式、视觉与视觉流式 Provider 调用均在请求前检查实际运行模型的 `model.invoke`，并通过 `IAM_MODEL_ID_MAP_JSON` 将服务端模型键映射到 IAM 模型 UUID。IAM migration `0012_resume_permission_catalog`、`0013_ai_permission_catalog`、`0014_model_invoke_permission` 登记默认编码，本地开发库 `0016` 已应用相关迁移，但租户角色仍须显式授权；AI Resume 可选配置 `IAM_MODEL_USAGE_API_KEY` 后会请求预留、报告/结算；该值须与 IAM `MODEL_USAGE_API_KEY` 相同，且目标环境须包含 `0015_model_usage_estimation`。执行配额的开关仍默认关闭。普通简历 API 仍按本地 user_id 过滤；管理端简历列表/详情另请求 `resume.read` 与 tenant/self `data_scope`，映射到本地用户 ID 后限制 SQL 结果，组织范围因缺少本地权威映射而拒绝。init.sql 当前定义 42 张表；AI Resume 旧库业务迁移 `20260927_full_workspace_upgrade.sql` 缺失，须依据真实历史 schema 重建并在隔离 PostgreSQL 演练前不得升级旧库。AI 任务目录为 15 项、模板为 60 个；面试题库代码已实现，题库迁移 `20261002_interview_question_bank_complete.sql` 于 2026-10-02 在本地数据库执行并核验，真实 IAM/浏览器和隔离数据库验收仍待完成。AI Resume 后端当前测试 23/23 通过；其他业务 API 与租户数据范围仍待接入，详见 [接入计划](../docs/技术架构与接入.md)。DeerFlow 的首登开户决策已确认并写入代码：新 OIDC 用户固定为普通用户，管理员能力只由 IAM 显式授权，不按邮箱或旧 `admin_emails` 提权；IAM token/tenant vault 与 Gateway route/Agent model-tool 中央授权已实现并通过定向回归；存量账号关联、正式 permission mapping 与真实 IAM 验收仍待完成。知识库控制台 OIDC 首版已通过 helper 测试、Ruff、前端构建和 ESLint，Alembic head 为 0023，迁移、完整后端套件与真实 IAM 验收待完成。


## 外部系统接入范围（2026-10-10）

DeerFlow 是当前唯一活跃试点。AI Resume 和 Knowledge Base 的 IAM/OIDC 产品接入代码已经从对应仓库移除；不再调用 `resume.*` 或 `knowledge.*` 中央权限，不再请求产品级 IAM data_scope。两套产品继续使用原有本地认证、成员/grant 与业务数据归属。此处此前记录的 Resume 工作区授权为历史快照。

## 2026-10-09 · 本轮变更边界

本轮只调整前端公开认证输入的数值长度属性，没有改 Python API、数据库模型或迁移；未启动后端服务，也未连接数据库（Docker Desktop Linux Engine 命名管道当前拒绝连接）。前端 Vite 生产构建通过，完整 Vue 类型检查受当前 pnpm 依赖树的类型解析故障阻塞。

### 2026-10-09 · 用户本机服务启动反馈

用户截图显示 API 容器已启动，端口映射 8002→8000，但 `docker compose ps` 当时仍为 health: starting。PostgreSQL healthy；本会话未能连接 Docker Engine，因此没有读取 API 日志、`/health`、`/ready` 或数据库 revision。未执行 migration/bootstrap。

### 2026-10-09 · API 数据库就绪状态

当前前端观察到 `database_not_ready`。`backend/app/api/v1/health.py` 的 readiness 检查在数据库 connect/SELECT/版本读取失败时返回该状态；本会话因 Docker Engine 命名管道权限无法读取容器日志或直接调用宿主 API。PostgreSQL 健康探针成功不能证明 API 凭据可用。原因未确认；未改配置、数据卷或 schema。

### 2026-10-09 · 已确认数据库认证失败

用户日志中的迁移 traceback 以 `FATAL: password authentication failed for user "iam"` 结束；API readiness 因此持续 503。迁移脚本在 SQLAlchemy 建立连接时失败，未触及 schema。当前 `.env` 密码与持久化 PostgreSQL 角色密码不同；需先对齐，再复核 API 与迁移任务。

## 本地数据库认证恢复（2026-10-09）

此前 API 与持久化 PostgreSQL iam 角色密码不一致，连接在迁移和 readiness 探测阶段失败。已将数据库角色密码对齐到本地环境配置中的 API 凭据（不在日志或文档中记录值），容器内 SELECT 1 成功；开发迁移 0017–0021 已应用，/api/v1/ready 返回 HTTP 200 ok。Postgres、API 容器均 healthy。没有执行 bootstrap，也未验收登录态功能。日常检查见本地启动指南（../docs/部署与运维.md）。
## 本地管理员与数据库密码轮换（2026-10-09）

已通过现有 password-reset completion 服务更新配置管理员密码，服务端递增 auth_version、撤销现有 IAM/OIDC 刷新会话并写入审计事件。PostgreSQL iam 角色密码同步更新；根目录 .env 已保存新凭据；JWT_SECRET 已轮换，因此旧签名访问令牌也会失效。API 容器重建后通过健康检查，管理员密码哈希校验、数据库 SELECT 1 和 /api/v1/ready 均通过。没有修改 SMTP（当前为空）或模型用量共享 API Key。

## 2026-10-09 · 管理台 UI 走查状态

本轮没有修改 Python API、数据模型或迁移。管理员浏览器走查模型管理时出现通用 HTTP 500 提示，未能从容器日志定位请求端点或异常；当前会话里的 Docker 可执行文件被系统拒绝启动。IAM 本地迁移 `0017`–`0021` 已在 2026-10-09 应用，API readiness 曾核验为 HTTP 200 `ok`；该健康状态不能替代模型目录 API 的单独验收。后端接口故障仍待读取 API 日志后确认。

### 2026-10-09 · 租户目录 500 修复

后续浏览器复核将此前的管理台 500 定位到 `GET /api/v1/admin/tenants`：路由引用了但未导入 SQLAlchemy `func` 和 `TenantMembership`。已补齐导入，运行中的 API 热重载后租户目录返回 1 个租户、2 个成员；模型管理页不再出现此前的请求失败提示。改动不涉及数据库、迁移或 API 契约。当前宿主没有可用 Python 解释器，尚未做 Python AST/测试验证；详见 [UI 走查记录](../docs/验收记录.md)。

### 2026-10-09 · 后端验证器状态

使用工作区随附的 Python 3.12 标准库 AST 检查通过 backend/app、backend/alembic 与 backend/tests 下共 88 个 Python 文件。该 Python 环境没有 FastAPI/SQLAlchemy 等后端依赖，故未运行 unittest；开发容器 readiness 由此前本地运行记录核验，本轮没有读取容器日志或执行容器内测试。


### 2026-10-09 · UI 复查同步

本轮只调整前端状态颜色与外观偏好面板的可读性，没有修改 Python API、OpenAPI 契约、数据模型、迁移或权限行为。此前本地 readiness 已核验；本轮未重跑后端集成测试。


### 2026-10-09 · 完整 PostgreSQL 回归结果

在迁移到当前 Alembic head 的隔离临时数据库中运行 `unittest discover`，109 项通过，0 项失败或跳过。之前两个应用更新测试因没有真实的应用角色权限夹具而失败，已补齐权限、角色、成员关系；密码重置的 EmailStr 测试地址改为普通测试域名。测试数据库已删除，开发数据库/卷保持原样。此前“本地缺依赖所以未运行”的记录是本次容器执行前的历史状态。

### 2026-10-09 · 生产预检工具状态

Python API、数据库 schema 和权限行为本轮未改变。`deploy/validate-production.ps1` 改为解析 Windows Docker Desktop 的真实 `docker.exe`，并支持 `-DockerPath` 显式覆盖；PowerShell 语法检查与生产 Compose 示例配置解析通过。完整生产预检仍待 `.env.production.local`、API/console/Caddy 镜像及生产 OIDC 私钥，未启动生产服务或执行迁移。

### 2026-10-09 · PostgreSQL 备份工具

新增运维脚本 `deploy/backup-postgres.ps1`，通过容器内 `pg_dump` 生成 custom-format 归档、`pg_restore --list` 校验并输出 SHA-256 sidecar；正式导出要求显式指定受保护的主机目录。`-ValidateOnly` 只解析配置并验证数据库连接，不导出数据。当前开发库的预检通过。脚本不修改 API/schema，也不负责加密、定时任务和恢复演练。

### 2026-10-09 · 管理台审计页复核

本轮修正只涉及前端审计日期筛选的 CSS；Python API、OpenAPI 契约、数据库模型、迁移和授权行为均未改变，也未重跑后端集成测试。

### 2026-10-09 · 窄屏 UI 走查同步

本轮修复限于 Vue 表格布局与数值属性绑定，没有修改 Python API、OpenAPI 契约、数据库模型、迁移或鉴权行为。前端 `npm run build`（含 Vue 类型检查）通过；本轮没有重跑后端测试。平台管理员窄屏实机检查范围和待验收项见 [UI 走查记录](../docs/验收记录.md)。

### 2026-10-09 · DeerFlow OIDC 接入安全状态（较早快照）

该轮只验证了 UserInfo subject 绑定（20/20），当时 access/refresh token vault 仍待实现；后续已增加可选 session-scoped vault，当前状态见本文开头和[接入计划](../docs/技术架构与接入.md)。Gateway 中央授权仍未完成。IAM Python API、OpenAPI 和数据库在该轮未改变，也没有重跑 IAM Docker/PostgreSQL 套件。

## 2026-10-09 · 注册默认角色快照

ToC 注册挑战现在保存申请时的默认角色 ID；若管理员在验证码兑换前更换默认角色，旧 challenge 会被消费，用户需重新申请验证码。新增 migration 0025_registration_role_snapshot 会先消费所有旧待验证挑战，再加角色外键/非空约束；注册总开关仍默认关闭。上一轮完整 PostgreSQL 套件 152/152 只覆盖 0024，0025 尚未完成运行时测试，也没有应用到开发库。
