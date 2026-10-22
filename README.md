# 统一身份与权限管理平台（IAM）

**2026-10-22 P330：** 保留 antdv，全站浅色紫主色换皮；接入向导选中卡可见；宽表不再撑出页级横滚。见 [验收记录](docs/验收记录.md)。

**2026-10-22 P329：** 管理台壳层、总览、接入向导改用 Ant Design Vue Layout/Menu/Steps/Collapse。见 [验收记录](docs/验收记录.md)。

**2026-10-22 P328：** 管理台「新项目接入」改为交互向导，并给出业务仓库改造示例。见 [验收记录](docs/验收记录.md)。

**2026-10-22 P327：** 管理台「新项目接入」（`/project-integration`）改为双路径分步指南（OIDC 托管登录 / HTTP 登录+判权接口）。`vue-tsc -b` 与浏览器走查见 [验收记录](docs/验收记录.md)。

**2026-10-17 P303：** 管理台菜单路由化（vue-router）；新增「新项目接入」指引页（`/project-integration`，平台管理员）。类型检查与 Vite 生产构建通过；登录后路由/接入页走查见 P322/P327。详见 [验收记录](docs/验收记录.md) 与 [项目进度](docs/项目总览与进度.md)。

**2026-10-16 P301：** 已使用 `.env` 中的管理员密码登录。桌面侧栏折叠、刷新记忆和展开已点过，并保持展开；跟随系统后已切回浅色。模型用量为空账本，无效日期和颠倒日期有错误提示。375px 是全页选择器。两份备份仍在且 SHA-256 一致。管理写入、币种、失败原因和 DeerFlow 全量未做。详见[验收记录](docs/验收记录.md)。

**2026-10-16 P300：** 桌面端管理台侧栏可折叠为图标并展开回文字。偏好只存在当前浏览器，默认展开。类型检查和生产构建通过。登录后点击未做。详见[验收记录](docs/验收记录.md)。

**2026-10-16 P299：** 管理台可跟随系统配色；概览不再把简历和知识库写成当前接入。类型检查和生产构建通过。登录后点击未做。详见[验收记录](docs/验收记录.md)。

**2026-10-16 P298 模型用量筛选：** 汇总和账目可按模型、成功/失败、UTC 日期筛选；待核对队列仍只按租户。类型检查通过，契约测试 6/6。只读确认 ready 200、revision 0031。集成测试、生产构建和浏览器未跑。币种与失败原因仍未做。详见[验收记录](docs/验收记录.md)。

**2026-10-15 P297 模型用量错误态修复：** 接口读取失败会显示错误并保留最近成功结果；首次失败不会呈现为零值/空账本。类型检查和 3,205 模块生产构建通过，错误注入与目标运行验收待做。详见[验收记录](docs/验收记录.md)。


**2026-10-15 P296 模型用量 UI 走查：** 发现数据读取失败会被呈现为零值/空账本；费用币种、失败原因契约和更丰富的历史筛选仍待处理。只读检查，没有修改代码或运行测试；详情见[验收记录](docs/验收记录.md)。
**2026-10-15 P295 模型用量 UI 调整：** 成功率（无请求显示“—”）、可见租户标签和“全部租户”提示已补齐；表格加载/空态独立显示，窄屏不裁切；有记录时保留表格内部滚动。类型检查/Vite 构建通过，375/768/1024/1440px 无页面溢出。失败原因、费用币种、丰富筛选和非空数据验收仍待解决。

**2026-10-15 P294 模型用量 UI 复核：** 当前桌面深色空数据页空态与核对安全提示清晰；发现租户筛选提示不可见、成功率/失败原因缺失、历史筛选较少、费用未标币种、空待核对表显示横向滚动条。当前只读审查未改代码或运行测试；P292 多视口及构建结果未在本轮重跑。币种规则待用户确认。详见项目进度与验收记录。

**2026-10-15 P293：** 将部署与架构当前状态统一为“未知”：P292 Docker/API 只读探测受本机权限阻断，2026-10-14 ready 200/0031 仅为历史快照；权限受限时由用户在可访问的 PowerShell 环境提供只读、脱敏状态。未操作数据库或迁移，详见[项目进度](docs/项目总览与进度.md)。

**2026-10-15 P292：** 修复模型用量页的空费用文案与页面级横向溢出，并补齐管理端 Badge/Divider 注册。前端类型检查和 3,205 模块 Vite 构建通过；浏览器在 375/768/1024/1440px 下未见页面横向溢出。随后 Docker named pipe 和 API localhost 请求因本机权限拒绝，数据库 revision/readiness/备份可用性仍未知；非空账目与核对流程未验收，详见 [项目进度](docs/项目总览与进度.md)。

**2026-10-15 P291 模型用量 UI 走查：** 桌面暗色页面可见，当前空数据；发现页面级横向溢出和“未配置价格”文案在零请求时含义不准确。审查记录、未验收范围见 [项目进度](docs/项目总览与进度.md) 与 [验收记录](docs/验收记录.md)。仅只读检查，未改代码或运行测试；当前 UI 可见不代表数据库 revision/readiness 已核验。

**2026-10-15 P290（P291 补充）：** DeerFlow B04 Windows 未分片离线套件 17,149 passed、404 skipped、3 deselected、1 failed、82 warnings；唯一失败是 DeerFlow 前端 AGENTS 指导文件超 49,152-byte 上限 478 bytes。用户要求本轮结束后停止，未重跑，测试临时目录已清理。P288 是最近一次 Docker/API 运行态探测，因不可达未能核实 revision/readiness/备份；P291 浏览器能显示模型用量页，但未探测 API/数据库。

**2026-10-14 15:10 入口复查（迁移前历史）：** `/api/v1/ready` 当时返回 503 `database_migration_pending`。该终端无可用 Docker CLI，未重新读取数据库 revision；当时最近成功核实为开发库 0021/head 0031。本条没有数据库写入或真实登录；后续迁移结果见上方当前状态。

**2026-10-14 P284 IAM 环境复核与本地验收：** Docker Engine 已可用；Compose 显示 API unhealthy、Console/PostgreSQL healthy。/api/v1/health 为 200，/api/v1/ready 为 503 database_migration_pending；实际数据库 revision 0021_resume_wallet_perms，代码 head 0031_model_usage_reconciliation。verify-local.ps1 隔离 PostgreSQL 套件 169/169 通过，随机 iam_test_* 数据库已清理；备份 ValidateOnly 通过但未创建归档。Vue 类型检查与 Vite production build 重新执行通过（3205 modules，输出在容器 /tmp）。本轮未迁移、未改产品源码、未创建受保护备份；需备份目标和明确授权后才能迁移。

**2026-10-14 DeerFlow B04：** 后 104 文件切片最新结果 **2,368 passed、2 failed、86 skipped、4 warnings**（通知修复前）；通知/lifecycle、扩展管理器和 API pin 聚焦回归 **126 passed、40 skipped**，Ruff check/format 通过。剩余已知失败为 venv extension API metadata 0.2.16 与源码/lock 0.2.18 不一致，完整套件未在最后修复后重跑；历史完整快照仍 17,062/142/349/3/0。用户本轮提供页面“数据库待迁移”状态，本轮未执行数据库迁移。详见[项目进度](docs/项目总览与进度.md)。

**本地启动与后续迁移门禁：** 按[快速启动指南](docs/快速启动指南.md)检查当前 `current`/`heads` 和 readiness。开发库当次 0021→0031 已完成；以后任何目标库需要迁移时，重新完成受保护归档、隔离恢复演练、影响审阅及明确授权。多项目接入与验收状态见[项目进度](docs/项目总览与进度.md)。
**2026-10-13 DeerFlow B04 最新进度：** 最近完整 Windows Python 3.12 离线快照为 17,062 passed、142 failed、349 skipped、3 deselected、0 errors、82 warnings（44:15），早于最后三项测试修正。Agent API/Crawl4AI/MCP 文件 URI 聚焦套件 **171 passed、1 skipped**，3 个 Python 文件 Ruff check/format 通过；修正项包括显式测试身份及权限、离线固定公网 DNS、按临时目录实际盘符验证 URI。完整套件尚未重跑；`uv`、`make`、`WinError 10106`、venv 扩展 API metadata 版本落后及余下失败仍待归因。未改 IAM 或 DeerFlow 生产运行时、IAM 数据库或 quota enforcement；真实试点仍未验收。

**2026-10-12 DeerFlow Provider 路径审计：** 对当前仓内 `backend/app` 与 `backend/packages/harness/deerflow` 的内置生产入口做静态搜索，发现共享模型工厂、Gateway 单次调用 scope 或 DeerMem 专用 hook 均处于 LangChain callback 管道；Codex 自定义模型也继承 `BaseChatModel`。外部扩展动态加载的 Provider 未被本次范围穷尽。IAM `request_id` 为每次 invocation 生成的幂等 ID；Codex 内部 HTTP 重试仍按一次 invocation 处理，计费语义和目标环境结果待验证。本轮只读检查，未运行测试、Provider 请求或数据库操作。

**2026-10-12 DeerFlow 后台模型计量：** 修复 DeerMem 定时记忆模型路径未稳定接入用量回调的问题：启用 `model_usage` 时，每次调用前从当前有效 OIDC vault 建立单次计量 callback，完成后关闭；记忆队列只保留本地身份标识，不持有 IAM 凭证。DeerFlow 两组关联回归 20/20、Harness boundary 1/1 通过；IAM readiness 仍为 503，未做真实 Provider/IAM 验收或数据库迁移。

**2026-10-12 DeerFlow 权限映射盘点：** IAM `0026–0030` 权限目录与 DeerFlow 中央 IAM 配置样例已静态对照，permission map 和部署角色草案见[接入计划](docs/技术架构与接入.md)。Docker CLI 已恢复；IAM API 仍因数据库停在 `0021_resume_wallet_perms` 返回 readiness 503；未执行迁移或真实试点接入。

**接手与后续计划（2026-10-12）：** 切换模型先读 [当前进度与后续改造交接](docs/项目总览与进度.md)。文件集中维护当前基线、任务顺序、验证证据和阻塞；根 `AGENTS.md` 要求后续每次改动/验收同步更新。当前 Console 200、API readiness 503；Docker 已恢复，数据库 revision 为 `0021_resume_wallet_perms`，全局容器中无 DeerFlow runtime；真实试点仍待启动与联调。

**2026-10-12 迁移影响审阅：** 已逐项审阅源码 migration `0022–0031`，没有执行迁移。注册默认关闭，权限目录只追加定义、不自动给角色授权；按最近已知开发库 revision `0021`，`0022` 新建的注册挑战表在连续升级中先为空，`0024/0025` 的旧挑战清理影响行数仍须在运行前核对。`0022` downgrade 会删除注册相关表，`0024` 删除密码摘要列，`0031` 在已有释放/人工核对账目后拒绝 downgrade，失败恢复应使用备份。该段记录的是 Docker CLI 恢复前的快照；后续 A01 已用 Docker CLI 只读核实数据库 revision `0021_resume_wallet_perms` 和 API readiness 503，未执行迁移。

**2026-10-12 测试临时产物清理：** 已按用户此前要求，删除并复核 7 个过期 pytest 临时根目录（`.df-agents-tmp`、`.df-agents2-tmp`、`.t`、`.tmp-deerflow-iam-memory`、`.tmp-deerflow-iam-memory-final`、`.tmp-deerflow-scope-final`、`iam-test-5gz2bgca`）均已不存在。只清理这些测试临时输出，没有删除测试源码；该次清理未运行测试，本轮 B05 定向测试则在完成后清理了自己的临时目录。

**2026-10-12 Docker 启动诊断：** `/ready` 最新返回 `503 database_migration_pending`，Console 为 200。当前执行环境把 `docker` 解析到不可启动的 `C:\Windows\System32\docker`（拒绝访问），常见 Docker Desktop CLI 路径也不存在，因此无法读取容器/DB 最新状态；启动排障步骤已补充到 `docs/部署与运维.md`，可通过 `-DockerPath "实际 docker.exe 完整路径"` 显式指定可执行 CLI。

**2026-10-12 首次清理尝试（已被后续结果取代）：** 受限检查当时无法列出这 7 个候选目录；随后已通过受控内容核验删除并确认均不存在，详见下方“测试临时产物清理”记录。

**2026-10-12 DeerFlow Windows 文档路径修复：** 对超出 Windows 安全路径预算的项目文档使用短内部文件名，保留原始显示名及 PDF/Office 转换后缀；已有存储布局继续可读。项目/文档/线程/运行四组路由回归 **225/225 通过**（其中项目文档路由 32/32），4 个 Python 文件 Ruff check/format 通过；首次测试使用过长 basetemp 导致路径错误，短临时根目录复跑成功，临时目录已删除。未改 IAM 前端、数据库、migration 或角色授权；完整后端套件仍未验收，真实 IAM/Provider E2E 仍待完成。

**2026-10-12 运行与接入范围校正：** 用户确认 DeerFlow 第一阶段项目、线程、运行和文档仅本人可见；当前数据表仍按 `user_id` 归属，tenant/organization 范围继续 fail closed，不执行组织共享或数据迁移。IAM Console 返回 HTTP 200，API unhealthy 且 readiness 为 `503 database_migration_pending`；开发库 `0021_resume_wallet_perms` 落后源码 head `0031_model_usage_reconciliation`。只读备份预检通过，未生成归档、未修改数据库。DeerFlow IAM/OIDC/模型/vault/data_scope 专项回归 169/169 通过。另一轮 Windows 全量非 live 测试（长 basetemp）为 16,770 passed、422 failed、345 skipped、3 deselected；已确认至少一个失败由 Windows 深路径触发，短路径下同一用例通过。短路径全量重跑在 34% 因 `WinError 10106` 中断，因此全量套件尚未通过，余下失败未完全归因。`部署与运维.md`、PRD、前后端文档、Skill 和变更日志已按本次状态更新；真实 IAM/Provider/浏览器 E2E 仍未完成。

**2026-10-12 DeerFlow 全模型授权与回退提取修复：** 每次 Agent 模型 provider 调用按配置档案检查 `model:use`，含辅助模型；DeerMem 后台模型调用另核验当前用户/vault、记忆本人读写范围和目标模型权限。Gateway 注入 Harness 授权 hook，授权错误在外呼前失败关闭。定向授权回归 28/28、Harness 边界 1/1 通过；Python readabilipy fallback 现在保留安全文章链接/图片目标，既有 web-fetch 回归 50/50、Ruff 通过。全量后端快照（该修复前）为 16,750 通过、442 失败、345 跳过、3 deselected；阻塞 I/O 门禁为 116 通过、26 失败、1 跳过。当时未重跑全量；后续完整记录见本文件 2026-10-12 最新状态：长路径运行 16,770 通过、422 失败、345 跳过、3 deselected；短路径重跑约 34% 因 WinError 10106 中断。全量仍未通过，失败原因未全部归因。临时测试文件、pyc 和隔离目录已清理；IAM migration 与开发数据库未改，真实 IAM/Provider E2E 仍待完成。

**2026-10-11 模型账目分页与验证：** 用量账目与待核对列表均使用服务端 total/offset 分页和稳定排序。`verify-local.ps1` 在隔离库迁移到 `0031_model_usage_reconciliation` 后完整后端 **169/169** 通过，Vue 检查和 Vite production build（3205 modules）通过。结果不包括开发库迁移；登录页仍因 readiness `database_migration_pending` 禁用认证提交。

**2026-10-11 部署与验证状态：** 备份预检通过，没有创建归档或写入开发库。API `/api/v1/ready` 仍返回 HTTP 503 `database_migration_pending`，开发库 `0021_resume_wallet_perms` 落后源码 head `0031_model_usage_reconciliation`。本轮完整隔离后端套件 169/169、Vue 检查和 3205 模块生产构建通过；真实 IAM/Provider 联调、生产预检和开发库迁移仍未完成。DeerFlow 登出按用户决定仅清除本地 vault session，不向 OIDC issuer 发送 token。

**2026-10-11 DeerFlow webhook 生产门禁：** GitHub webhook 的未验证开发开关现在在 `DEER_FLOW_ENV` 或 `ENVIRONMENT` 明确为 production 时强制关闭，避免环境变量误配绕过 HMAC；浏览器与 webhook 完整聚焦回归 76/76、Ruff check/format 通过。公网 URL 用例现使用固定测试 DNS 结果，不依赖外网；未改 IAM 界面或数据库。

**2026-10-11 DeerFlow 浏览器实时流鉴权：** DeerFlow `/api/threads/{thread_id}/browser/stream` 在建立实时浏览器会话前同时要求 `threads:read/write` 和匹配线程的 owner/self data_scope，并保留本地用户 owner 检查；本地签名 session 的 `sid` 会用于解析中央 IAM 会话。浏览器/Webhook 合并聚焦回归 76/76、Ruff check/format 通过；公网 URL 安全用例已固定 DNS 结果，覆盖私网拒绝且不依赖外网。未改 IAM 前端、配置、数据库或登出策略；真实 IAM/WebSocket E2E 仍待运行环境就绪。

**2026-10-11 DeerFlow 个人偏好权限闭环：** `/api/v1/auth/preferences` 的 GET/PATCH 分别要求 `preferences:read/write`，并在访问用户偏好仓储前校验匹配已验证 IAM 身份的 owner/self data_scope；浏览器 session 与本地 owner 过滤继续执行。新增 migration `0030_deerflow_preference_permissions` 只登记两项权限、不自动授权。DeerFlow 定向回归 19/19、Ruff check/format 通过；开发库仍为 `0021_resume_wallet_perms`、readiness 503，未执行迁移或真实 IAM 联调。启用 Central IAM 后需管理员配置映射、对应角色权限与本人范围。

**2026-10-11 DeerFlow runtime 镜像验收：** 默认 runtime target 未生成。首轮曾报告 uv.lock 需要更新；随后用镜像内同版 uv 对当前源码执行 uv sync --dry-run --locked --extra redis 通过，uv.lock SHA-256 保持不变。其后 runtime 构建被 Docker Hub Python manifest 与 GHCR uv 镜像匿名令牌请求 EOF 阻断，即使 pull=false 也未能解析基础镜像。dev 镜像仍可用，容器内 adapter import 已通过；需 Docker Hub/GHCR 可达或镜像源后重建 runtime。没有启动完整服务或修改数据库。

**2026-10-11 DeerFlow Gateway 镜像打包核验：** 已修复 DeerFlow .dockerignore，排除 config.yaml、extensions_config.json 及备份文件，并覆盖所有 .env* 变体；三者均只检查了文件名存在性，未读取内容。Docker daemon 在两个客户端退出后仍完成 dev 镜像；iam-deerflow-package-check:20261011 的本地 image ID 为 sha256:f2203cacf14d7a324dadcaa4d803145fcd9fd48129a9e9f15751e4beb4947456，一次性容器使用 uv run 导入 deerflow.authz.iam_deerflow 通过。未启动 DeerFlow 服务或连接/修改数据库；真实服务启动、生产发布和在线 IAM 联调仍待验收。

**2026-10-11 DeerFlow 数据范围模型核对：** 当前项目、线程、运行和文档资源按本地 user_id 归属，核心资源表没有可信 tenant_id/organization_id；tenant_id 仅见于 IAM session vault 与模型用量账目。现有 owner/self 过滤继续生效，tenant/organization scope fail closed。要启用共享访问，需先定义哪些资源可组织共享、服务端归属关系和历史数据回填，再设计迁移。

**2026-10-11 DeerFlow 异步 IAM 授权回归：** 使用 DeerFlow backend Python 3.12.14 运行 IAM SDK 的 test_iam_deerflow provider 套件 **22/22 通过**，包含 async authorize 和 async data_scope capability refresh；同一环境下 DeerFlow test_iam_provider_interoperability.py **12/12 通过**，包含 4 项 async data_scope 用例。均为 mock 测试，不访问真实 IAM、数据库或 Provider；旧 Windows 运行时挂起现象在本次环境中未复现，生产联调仍待验收。

**2026-10-11 运行状态与登出决策复核：** 只读 PostgreSQL 查询确认开发库 revision 为 0021_resume_wallet_perms，源码 head 后续推进至 `0031_model_usage_reconciliation`；API /api/v1/ready 当前仍返回 HTTP 503 database_migration_pending。deploy/backup-postgres.ps1 -ValidateOnly 通过，未创建备份归档、未修改数据库；本轮未执行 migration。用户已决定 DeerFlow 保持本地登出，/auth/logout 只清除本地 vault 会话，不向 OIDC issuer 发送 access/refresh token。

**2026-10-11 登录页就绪状态改造：** 当只读 readiness 探针返回数据库待迁移/不可用时，登录、注册、密码重置、邀请接受和 OIDC 授权提交均禁用；状态提示给出管理员备份、审阅、迁移后的重查路径。浏览器确认登录按钮禁用，Vue 类型检查与 Vite 生产构建通过。后端探针仍为只读，开发库没有迁移，当前 readiness 仍为 503。

**2026-10-11 DeerFlow 模型用量待核对闭环：** IAM 调用预留现在无论配额拦截是否开启都会先持久化；10 分钟到期只进入管理员待核对队列，不自动按预留上限收费或释放。管理员可按 Provider 侧记录补记实测/估算用量，或确认 Provider 从未被调用后释放，处理人与依据写入审计。DeerFlow 的 Provider 完成到本地 outbox 提交之间仍不能自动还原实际 Token；真实 IAM/Provider 联调、迁移和恢复流程验收仍待完成，配额强制保持关闭。

**2026-10-11 开发服务 readiness 复核：** 当前 `http://localhost:5175/` 返回 HTTP 200，API `/api/v1/ready` 返回 503 `database_migration_pending`。只读查询确认开发库为 `0021_resume_wallet_perms`，当前源码 head 为 `0031_model_usage_reconciliation`；注册验证码表当前不存在。`0022`–`0031` 迁移影响需在执行前复核；本次未迁移数据库。迁移命令需要在受保护备份后由用户明确授权执行。

**2026-10-11 DeerFlow Console 聚合报表授权：** DeerFlow `/api/console/stats` 现在要求 `runs:read`、`threads:read`、`agents:read` 及三项本人 data_scope；跨会话运行列表要求 runs/threads 读取权限和范围，usage 只要求 runs 读取权限和范围。Gateway 仍执行本地 `user_id` 过滤。定向路由回归 **25/25 通过**，两处 Python 文件 Ruff check 通过；前端未修改，开发库/角色 grant/真实浏览器验收未执行。

**2026-10-11 DeerFlow OIDC 撤销原语：** DeerFlow OIDC discovery 现在保留可选 `revocation_endpoint`，并提供 RFC 7009 HTTPS token revoke 客户端，覆盖三种 OAuth client-auth 方式和脱敏错误；OIDC/vault mock 回归 41/41 通过。Gateway logout 尚未调用该客户端，仍只删除本地 vault row。用户已明确决定保持本地登出；Gateway 不会将 vault access/refresh token 发送给外部 issuer。详见 PRD、接入计划及用户输入清单。

**2026-10-11 DeerFlow memory worker 提交前复核：** 被动写入在 `apply_changes/save` 前重新加载 active 本地用户与匹配的 OIDC vault session，并校验 `memory:read/write` owner/self data_scope；冲突重试逐次重查，超时/失败拒绝，queue 不保存 token/capability。Updater、data-scope 与 commit callback 定向回归 **109/109 通过**，6 个 Python 文件 Ruff lint/format 通过。未迁移数据库或授予角色，真实 IAM/OIDC 和浏览器验收仍待环境；完整状态见 `docs/技术架构与接入.md`。

**2026-10-11 早期验收快照（已更新）：** 本条记录的是 0030 阶段的后端 161/161 结果；其后 `0031_model_usage_reconciliation` 已在隔离 PostgreSQL 完整验证，最新结果见本文件上方：169/169、Vue 检查与 Vite production build 通过。开发库仍为 `0021_resume_wallet_perms`，API readiness 为 `503 database_migration_pending`；真实 IAM/OIDC 与浏览器 E2E 尚未验收。

**2026-10-10 技能写后返回正文的二次授权：** 自定义技能更新/回滚会返回完整正文，因此必须同时具备 skills:read 与 skills:write，且在访问/修改存储前通过两项本人 data_scope。跨切片联合回归更新为 141/141 通过；Ruff/格式检查通过 8 个 DeerFlow Python 文件。

**2026-10-10 跨切片授权回归：** DeerFlow connectors、stateless run、Agent 兼容路由、skills、MCP、subagents 与 channel worker 管理合并定向回归 138/138 通过（1 条 Starlette/httpx 弃用警告）；8 个 DeerFlow Python 代码/测试文件 Ruff check 与 format check 通过。该结果不覆盖完整仓库、数据库迁移或真实 IAM/browser E2E。

**2026-10-10 DeerFlow IM worker 管理入口补齐：** /api/channels 的 worker 状态读取现在需要 channels:read，重启操作需要 channels:admin 并保留本地 Gateway 管理员校验；与个人 channel 连接/凭证路由区分。纳入 worker、技能、MCP、子 Agent 的定向组合回归为 81/81 通过。

**2026-10-10 DeerFlow 技能、子 Agent 与 MCP 管理权限补齐：** Central IAM 控制用户技能 read/write/delete 与本人 data_scope；技能全局配置、托管子 Agent 管理、MCP 配置/缓存操作分别走 admin 权限，部署级变更仍保留 DeerFlow 本地管理员校验。IAM migration 0029_deerflow_agent_extension_permissions 只登记 7 个权限码、不自动授权。定向回归 79/79 通过；未应用开发库迁移、未配置生产 role grants、未做在线 IAM E2E。

**2026-10-10 DeerFlow 连接器授权补齐：** IM channels 与 Lark integrations 路由已接入 Central IAM channels:read/write/admin、integrations:read/write/admin 权限，并在个人数据读取/写入前校验本人 data_scope；部署级运行配置和安装操作同时要求 IAM 管理权限及 DeerFlow 本地管理员。IAM migration 0028_deerflow_connector_permissions 只登记 6 个权限码，不自动授权。相关 Gateway 回归 57/57 通过；Ruff check 与 10 个变更文件的 format check 通过。开发库迁移、角色授权、真实 IAM/浏览器联调未执行。

**2026-10-10 DeerFlow 无状态运行授权补齐：** Gateway `/api/runs/stream` 与 `/api/runs/wait` 在运行创建前增加 Central IAM `runs:create` 数据范围检查，同时保留统一运行服务中的本地 thread owner 验证；旧 `/api/assistants/*` 兼容读取也要求 `agents:read` 与本人 data_scope。Gateway 定向回归 28/28、Ruff check/format 通过；真实 IAM/浏览器联调未执行。

> **当前交付基线（2026-10-11）：** 当前唯一系统接入试点为 DeerFlow；AI Resume、Knowledge Base 的 IAM 专属接入代码已撤销，历史说明不表示仍有运行时集成。IAM 源码迁移 head 为 `0031_model_usage_reconciliation`，本机开发库为 `0021_resume_wallet_perms`，API readiness 返回 `503 database_migration_pending`。空隔离库迁移至 0031 后完整后端套件 169/169 通过，Vue 检查与 Vite production build（3205 modules）通过；这不等同于开发环境升级或真实 DeerFlow 验收通过。

**DeerFlow 模型与工具授权更新（2026-10-10）：** 模型列表与模型调用已拆分权限码；`model.invoke` 绑定服务端配置的 IAM 模型 UUID，逐模型检查租户内模型是否活动且获授权。工具权限检查使用服务端工具名资源 ID，支持逐工具角色授权。4 项 adapter 回归通过；真实 UUID 映射、IAM role grants、开发库 migration 与浏览器联调待完成。

**DeerFlow 项目与文档数据范围补齐（2026-10-10）：** 项目创建/编辑/归档/恢复、文档上传/提升/恢复在写入前校验 `projects:write` 与完整响应所需的 `projects:read` 范围；文档删除、单项/批量永久清理与保留期清理校验 `projects:delete`；会话文件提升/挂载同时校验线程读/写范围。每次仓储变更显式绑定当前 DeerFlow 用户。项目、文档和回收站路由回归 **92/92 通过**，改动文件 Ruff 检查通过；本轮未修改 IAM 前端、未启动服务或迁移数据库。

**DeerFlow 线程/运行变更范围（2026-10-10）：** `require_permission(..., owner_check=True)` 在本地归属通过后，还会对线程 `write/delete` 与运行 `create/cancel` 请求校验相应 IAM data_scope；新建运行不传尚不存在的 run ID，取消运行按 run ID 判权。鉴权回归 101/101 通过；线程、运行、反馈、文件、浏览器、MCP 与项目资料路由组合回归 532 项通过，1 项公网 DNS 用例因断网容器限制被排除；Ruff 检查通过。其它 owner-bound 写入入口和真实 IAM/浏览器接入仍需继续审计验收。

**DeerFlow 定时任务授权（2026-10-10）：** 定时任务 API 在 owner-filtered repository 前校验 Central IAM 本人 data_scope。后台调度在创建 occurrence 前、从持久队列启动前，都会重载 active local user、重新计算 route grants/data_scope，并查找匹配用户、OIDC provider、issuer、subject 的现存加密 vault session；仅把本次授权 capability 传入 Gateway run 的内存上下文。会话或 grant 失效时暂停任务并取消排队 occurrence；手动触发返回 403/503。调度、token vault、路由与授权回归 **126/126 通过**；Ruff check 全部通过、Ruff format 对 9 个匹配源码/测试文件通过、10 个 Python 文件 AST 通过。IAM 前端/数据库未改，未执行迁移；真实 IAM E2E 仍受 IAM 开发库 migration pending 和 DeerFlow Compose 未启动阻塞。

**待执行 migration 数据影响审查（2026-10-10）：** 只读审查 0024_tenant_registration_audience 的升级会清空并删除旧注册 challenge 的暂存密码摘要列；0025_registration_role_snapshot 会将所有未消费的旧邮箱 OTP challenge 标为已消费，用户需重新发起注册验证。该行为是迁移设计的一部分，执行前必须先完成受保护备份并取得明确维护窗口授权；本轮未执行 migration。


## 当前开发状态（2026-10-11）

**此前只读运行核验（2026-10-10，IAM 源码 head 0027）：** 当时 IAM Compose 的 API unhealthy、console/PostgreSQL healthy；开发库为 `0021_resume_wallet_perms`，API `/api/v1/ready` 返回 503 `database_migration_pending`。DeerFlow 开发 Compose 未运行；Gateway 镜像 import smoke 通过，DeerFlow 数据库 revision 尚未核验。
**此前隔离验证快照（2026-10-10，源码 head 0027）：** verify-local.ps1 的后端完整套件 161/161 通过；console 镜像内 vue-tsc -b 与 Vite production build 通过。更新的 0029 全量后端结果见本文件顶部。

**DeerFlow Agent 管理权限补齐（2026-10-10）：** 新增自建 Agent 的 `agents:read/write/delete` 在线权限，并在本人 Agent 读写前校验匹配的 IAM data_scope；写接口返回完整 Agent 配置，因此也要求 `agents:read`。部署级共享 `USER.md` 单独使用 `agents:admin`，不允许 PAT 调用。IAM migration `0027_deerflow_resource_permissions` 只登记权限码，不授予角色；样例 API 地址已修正为 IAM origin，permission map 覆盖 Agent 与记忆资源。授权/PAT/`/auth/me`/Agent 定向回归 **90/90 通过**，8 个 Python 文件 Ruff check/format 通过。gateway dev 镜像已构建并通过断网 import smoke；真实 IAM、Compose 部署和浏览器验收尚未完成。

**按 ID 读取也执行中央范围校验：** `require_permission` 对带 `owner_check=True` 的 `threads:read` / `runs:read` 请求，在本地会话 owner 校验后、读取 handler 执行前调用 IAM data_scope。`test_auth.py` 与 `test_threads_router.py` 合计 **228/228 通过**；仍需将正式权限映射部署到目标 IAM。

**DeerFlow 最新范围状态（2026-10-11 历史快照，路径问题于 2026-10-12 修复）：** DeerFlow 现在在项目、线程/运行直读、项目文档/内容、项目会话文件聚合、回收站与个人记忆读取前检查 IAM data_scope，并继续执行本地 owner 限制。个人记忆路由另有 `memory:read/write/delete/admin` 权限；因写接口仍返回完整记忆文档，写入/删除也必须先通过 `memory:read` 数据范围校验；PAT 路由按 HTTP 方法逐条放行。记忆/权限/PAT 定向回归 **118/118 通过**，改动文件 Ruff check/format 通过。项目文档与回收站回归在缩短临时根目录后 **72 通过、2 跳过**；当时 255-byte 文件名压力用例在 Windows 上因长路径 `WinError 3` 失败，该问题已通过短内部文件名修复，文档路由回归现为 32/32 通过。跨租户/组织共享、正式 IAM permission map、真实 IAM/OIDC 浏览器验收、镜像分发仍待完成。RFC 7009 客户端原语已 mock 验证，但 logout 不发送 vault 凭证给外部 issuer，按用户决定保持本地登出。

**当前范围：** IAM 平台本身继续作为通用身份、OIDC、RBAC、资源授权、数据范围与模型治理服务；唯一业务试点是 DeerFlow。AI Resume 与 Knowledge Base 的 IAM/OIDC 专属代码、配置、schema/migrations、测试和前端入口已从各自项目移除，原有产品本地认证、成员授权和业务功能保留。

**DeerFlow 接入状态：** 服务端 token vault 与 refresh rotation、Gateway route/model/sandbox 和 Agent model/tool 的在线权限检查已进入源码并通过既有定向回归。项目列表/详情/会话读取只覆盖本人范围并与 DeerFlow 本地 owner 求交；其它资源过滤以及 tenant/organization 共享范围仍需映射并验收。真实 IAM/OIDC 联调、目标数据库迁移、镜像分发和浏览器端到端尚未完成。

**平台与本机状态快照（2026-10-11）：** 当时 IAM 源码迁移 head 为 `0030_deerflow_preference_permissions`，开发数据库为 `0021_resume_wallet_perms`；API unhealthy，console 与 PostgreSQL healthy，API readiness 为 503 `database_migration_pending`。空隔离库升级至 0030 后后端完整套件 161/161 通过，临时库已清理。之后新增 0031；本轮没有迁移主开发库、启动 DeerFlow Compose 或修改真实 `.env`。

**本轮清理验证：** Knowledge Base 的 107 个 Python 文件通过 AST 解析，非数据库回归 8/8、contracts typecheck、Vite production build（1652 modules）通过。未执行数据库迁移。详细变更见[变更日志](CHANGELOG.md)，当前需用户/部署方提供的试点输入见[接入计划](docs/技术架构与接入.md)和[配置清单](docs/部署与运维.md)。

## 历史产品集成与代码验证记录（2026-10-07）

AI Resume 用户钱包现已接入 IAM `resume.wallet.read`（余额、流水、充值信息）和 `resume.wallet.recharge`（充值申请）在线权限；服务端仍按已认证本地 `user_id` 限定本人钱包。Alembic `0021_resume_wallet_perms` 仅登记权限码，不自动授予角色。截至 2026-10-07 核验，开发库为 `0016_permission_status`，`0017`–`0021` 未应用并需用户授权后执行；当时本机 API/console 不可用。

AI Resume 用户工作区权限继续扩展至自选任务模型和任务提示词：读取检查 `resume.read`，保存/恢复默认值检查 `resume.write`。Express 从本地登录态取用户 ID 做 owner 过滤；沿用现有权限码，无新 migration。真实 IAM 角色授权、数据库和浏览器链路仍待联调。

浏览器扩展的本人简历回填、岗位收藏/读取/进度/删除现检查 `resume.read` / `resume.write`；重新分析还检查 `ai.generate`。只用业务级权限码，不把扩展提交的岗位或简历自增 ID 当作 IAM `resource_id`；AI provider 仍执行实际模型的 `model.invoke` 检查。新增扩展路由契约后 AI Resume Node 全量测试 36/36 通过。

构建与测试记录（2026-10-07）：前端 `vue-tsc --noEmit` 通过，Vite 生产构建生成 3205 个模块（入口 382.51 KB / gzip 118.65 KB，产物写入 Windows Temp）；Python 授权/OIDC SDK 标准库回归 20/20 通过，后端 110 个 Python 文件 AST 解析无语法错误。完整 IAM 后端 unittest 本轮收集/运行 60 项，其中 12 项因可用 Python 环境缺少已声明依赖 `pwdlib` 而导入失败、4 项 PostgreSQL 测试跳过；不是完整后端通过。该次核验时 console `5175` 返回 HTTP 200、API OpenAPI 返回 200，但 `/api/v1/ready` 返回 `503 database_migration_pending`；未连接或修改数据库，也未执行迁移。IAM `0017`–`0021` 在该次核验时仍待用户授权。

ToC 自助注册要求已实现邮箱 OTP、消费租户硬约束、应用角色校验、限流、事务发件箱和协议留痕；先验证邮箱再收密码。全局开关与每应用策略仍默认关闭。生产开放前须应用 migration `0022`–`0025`，配置 SMTP、专用消费租户、普通角色和协议 URL，并完成邮件/浏览器及反滥用验收；生产当前仍关闭注册。

审计管理（2026-10-05）：`GET /api/v1/admin/audit/search` 已支持多条件服务端分页、UTC 时间区间和只读详情；原 `/api/v1/admin/audit` 数组响应保持兼容；无数据库 schema 变更。审计页面 `vue-tsc -b` 与 Vite production build 通过（3205 modules）；IAM 全量后端 unittest 99 项通过、28 项 PostgreSQL 集成用例跳过，使用临时 `pwdlib[argon2]` overlay，未修改 DeerFlow venv，且没有数据库配置或连接。密码重置邮件 URL 双 `#` 已修复。当前本机 API 8011 与 console 5176 均不可用；未迁移数据库，登录态浏览器验收仍待完成。

生产部署预检入口为 `deploy/validate-production.ps1`：检查 Compose、Caddyfile、API 生产设置与 OIDC 签名密钥、Nginx 语法，不启动长期服务或迁移；轮换阶段可加 `-IncludeKeyRotation` 检查备用密钥。PowerShell 语法解析已通过；Docker/Caddy/Nginx 容器级验证仍待具备 Docker Compose V2 和镜像的部署环境。

资源级授权增量（2026-10-04）：知识库具体应用控制操作会向 IAM 传入 Knowledge Base Application UUID 作为 `resource_id`；IAM 角色页已提供实例级权限的读取、添加和撤销。通用授权仍覆盖其权限下所有资源，应用目录列表仍需租户级 `knowledge.read`。Knowledge Base 15 项定向后端授权用例、IAM Vue 类型检查与 Vite build 通过；2026-10-05 定向测试：登录限流/维护、授权模拟、模型配额契约与生产配置共 30 项通过、4 项 PostgreSQL 集成用例跳过（复用 DeerFlow 现有 Python venv）；完整后端套件、PostgreSQL 并发锁/迁移和真实浏览器联调仍未完成。

AI Resume 数据范围增量（2026-10-04）：已绑定 IAM 的管理端简历列表/详情新增 `resume.read` + `include_data_scope=true`；tenant/self 范围映射成本地用户 UUID 并与既有 ADMIN 归属取交集，在 SQL 仓储执行。Node 后端语法检查通过，测试 23/23；组织范围及用户/AI/钱包/岗位等其它资源仍待接入，真实 IAM 与数据库验收未完成。

此前只读核验曾显示本地数据库为 `0016_permission_status`；2026-10-09 凭据对齐后曾将开发库迁移至 `0021_resume_wallet_perms`，当时 readiness HTTP 200。当前源码 head 为 `0027_deerflow_resource_permissions`；2026-10-10 只读 Docker 检查确认开发库 `0021`、API readiness `503 database_migration_pending`，PostgreSQL 与 console healthy、API unhealthy。没有迁移开发库或运行 bootstrap；恢复 API readiness 前须审阅 migration、创建并验证受保护备份并安排授权维护窗口。`alembic check` 在 schema 落后于 head 时不能判断 drift。
管理台侧栏和公开认证入口共用 `/api/v1/ready` 状态，而 `/health` 只表示 API 进程存活。前端每 30 秒刷新，迁移待处理、数据库不可用、迁移状态异常与 API 未连接会显示不同提示；探针有 5 秒超时且不阻塞会话恢复。登录入口在异常提示中提供“重新检查”，与定时轮询共用单个在途探针。公开认证表单增加邮箱格式/必填、邀请密码必填、重置密码长度和二次确认校验，服务端继续执行最终校验。`vue-tsc -b` 与 Vite production build 通过（3205 modules，入口 381.97 KB / gzip 118.41 KB）。本机 pnpm shim 失效，本次直接调用已安装的项目 Vue/Vite 二进制；本地 Vite 认证组件模块返回 200 并包含新校验规则。浏览器无障碍树确认就绪提示、必填标记和登录控件同时存在，未提交凭证；最新表单校验仍缺视觉/错误状态交互验收。

登录失败防护与来源 IP（2026-10-05）：新增 PostgreSQL 持久节流，默认在 15 分钟内同一账号/来源组合失败 8 次、同一来源失败 60 次后冷却 15 分钟；数据库只保存 JWT 密钥 HMAC 摘要和计数。开发环境使用 socket peer；生产 Caddy 默认不信任上游代理，并覆写经 Nginx 传递的专用 `X-IAM-Client-IP`。若前置 CDN/LB，只将实际出口 CIDR 显式写入 `deploy/caddy/trusted-proxies/edge.caddy`，再由 Caddy `{client_ip}` 解析来源，不能使用整个私有网段。前端从 `Retry-After` 显示等待时间。Alembic `0020_login_attempt_throttles` 已加入源码，未迁移；前端类型检查和生产构建通过（3205 modules），尚未取得会话提交真实 429 请求。

业务接入复核（2026-10-09）：AI Resume 实际位于 `D:\project\新建文件夹` 的三个独立仓库；其服务端已覆盖部分简历、AI、PDF、模型权限；管理端简历列表/详情支持 tenant/self data_scope 与本地归属交集，组织、其它资源及真实 IAM 联调仍待完成。知识库本轮新增 `include_data_scope=true`、文档/修订/片段/任务/检索/证据过滤及 `0025_document_iam_data_scope` 源码；35/35 定向测试与 Ruff 通过，不代表目标数据库迁移、真实 IAM 或浏览器流程已验收。DeerFlow 请求级与 Agent 授权已接入可选服务端 token vault，资源数据范围仍需完成。`D:\project\aijj` 是 AI 基金决策助手，不是简历系统。接入细节与待定配置见[接入计划](docs/技术架构与接入.md)。

需要用户提供的迁移授权、IAM tenant/application 与业务权限/数据映射、部署配置和产品决策集中见[待提供配置与决策清单](docs/部署与运维.md)；AI Resume 仓库路径已核实。secret 只写入本地部署密钥管理器，不在聊天中传递。

## 项目文件

```text
.
├── backend/                       # FastAPI、SQLAlchemy、Alembic、认证与管理 API
├── frontend/                      # Vue 管理台
├── sdk/                            # Python/TypeScript 授权与 OIDC relying-party SDK
├── compose.yaml                   # 本地 Postgres + API + 管理台开发环境
├── start-local.ps1                # Windows PowerShell 本地 Compose 启动入口
├── verify-local.ps1               # 隔离 PostgreSQL 套件与前端构建入口
├── deploy/verify-postgres-restore.ps1 # 备份恢复到随机隔离库并检查 revision/关键表
├── compose.production.yaml        # PostgreSQL + one-shot migrations + API + static Vue + Caddy HTTPS
├── docs/项目总览与进度.md         # 当前状态、任务 ID、证据和下一步
├── docs/产品需求.md               # 产品目标、业务规则与验收标准
├── docs/技术架构与接入.md         # 架构、API/SDK、简单接入方案与模型治理
├── docs/部署与运维.md           # 启动、配置、部署、备份与恢复
├── docs/验收记录.md             # 验收矩阵、UI 走查与历史证据
├── deploy/validate-production.ps1 # 不启动服务/不迁移的生产配置预检
├── CHANGELOG.md                   # 按执行记录实现变化和验证结果
└── .codex/skills/iam-project/     # 项目领域知识与 AI 协作约定
```

## 当前可用能力

- IAM 管理控制台提供租户、OAuth 应用、用户、角色、权限目录、组织与数据范围、用户组、邀请、登录主题、审计、模型目录和用量管理。
- 平台支持 OAuth 2.0 / OpenID Connect 授权码 + PKCE、RS256/JWKS、在线 token 状态与授权检查、refresh-token 轮换和撤销；管理 API 与业务 OIDC 凭证保持不同权限边界。
- 角色授权、资源级 grant、数据范围策略与 `/authorization/check` 采用服务端默认拒绝；业务服务仍须将返回的授权约束实际应用于自己的 SQL、向量检索和异步任务。
- ToC 邮箱 OTP 自助注册、管理员邀请、密码重置、账户/成员生命周期及会话管理已有源码；注册总闸默认关闭，数据库迁移与 SMTP/浏览器发布验收仍待完成。
- DeerFlow 已有可选 IAM server-side token vault、Gateway/Agent 在线权限检查与项目本人范围查询切片；只支持已接入的本人范围和本地 owner 交集，不代表所有资源、租户/组织共享或真实环境验收完成。
- AI Resume 和 Knowledge Base 当前不调用 IAM；它们的产品本地认证及业务授权由各自项目负责。后续接入系统需在 DeerFlow 试点验收后重新评审。

## 系统边界

```text
Vue 管理台 ── Bearer API ── FastAPI ── PostgreSQL
业务系统服务端 ── 已认证用户 ── 授权判定 API
```

OIDC Provider 提供 Discovery/JWKS、同意、登出、撤销与 token introspection；真实第三方互操作仍待验收。DeerFlow 是当前唯一业务试点，现有源码覆盖 Gateway/Agent 的部分在线权限和项目本人范围查询；更多业务资源的 SQL/向量查询过滤、tenant/organization 共享策略和真实环境验收仍未完成。AI Resume 与 Knowledge Base 的 IAM 接入代码已清理，目前由各自产品本地认证和授权。IAM 返回的 data_scope 只有在业务仓储落实过滤后才构成数据隔离；RPM/TPM enforcement 默认关闭，生产密钥轮换与部署验收仍待完成。

## 启动

复制 `.env.compose.example` 为 `.env`，为数据库、JWT 和管理员密码填入随机强密钥（JWT 至少 32 字符，管理员密码至少 16 字符），然后运行：

```powershell
docker compose up -d console
```

开发控制台默认访问 `http://localhost:5175`，API 默认访问 `http://localhost:8002`。首次启动、日常启停和 502 排查见[本地启动指南](docs/部署与运维.md)。若端口被占用，修改根目录 `.env` 中 `IAM_CONSOLE_PORT` / `IAM_API_PORT`；开发 Compose 不用于生产。生产 Compose 的 DNS/TLS、密钥、管理员一次性引导、部署和迁移步骤见 [运维手册](docs/部署与运维.md)。前后端独立启动说明见 [后端指南](backend/README.md) 和 [前端指南](frontend/README.md)，业务服务接入样例见 [Python SDK](sdk/python/README.md) 与 [TypeScript SDK](sdk/typescript/README.md)。

首次生产部署需复制 `.env.production.example` 为 `.env.production.local`，填入域名、随机数据库/JWT 密钥、平台管理员邮箱、一次性初始密码、不可变镜像标签和 OIDC 私钥宿主机路径。先确认 DNS 指向部署主机且外网可访问 TCP 80/443，再按运维手册执行管理员引导与 Compose 启动。示例环境文件已加入忽略规则，真实密钥不得提交。

## 当前验证与限制

- 2026-10-03 登录页走查：文案已覆盖平台、租户与应用管理员共用入口；桌面及 390px 的登录/密码找回页面通过浏览器检查。`vue-tsc --noEmit -p tsconfig.json` 通过，Vite production build 转换 3202 个模块（入口 378.27 KB / gzip 117.37 KB）；未提交登录或邮件请求，管理页仍需有效管理员会话逐页验收。
- 2026-09-30 密码重置续审：Python AST 只读语法解析覆盖 backend/app 与 backend/tests 共 70 个文件；本地浏览器确认找回入口、新密码表单和 fragment 清理；临时副本中运行 `vue-tsc -b` 与 Vite production build 通过（3198 modules，入口 371.37 KB / gzip 115.31 KB）。未运行后端测试、SMTP 投递或 Alembic `0011`；数据库最后确认记录仍是 revision `0010_tenant_user_groups`。

- 2026-09-30 当前只读运行检查：Docker Compose 列出本地 API、控制台和 PostgreSQL 三个 healthy 容器；API `8011` readiness 为 ok，控制台 `5176` 首页 HTTP 200。`alembic current` 确认数据库为 `0010_tenant_user_groups`，源码 migration head 为 `0016_permission_status`。
- 2026-10-03 租户 OAuth 应用委派：前端 Vue/TypeScript 类型检查和 Vite production build 通过（3202 modules，入口 378.27 KB / gzip 117.38 KB，管理注册 chunk 285.65 KB / gzip 83.80 KB）；Python AST 检查 100 个文件通过。Alembic 源码 head 为 `0018_tenant_application_admin_permissions`，数据库仍以最后确认的 `0010_tenant_user_groups` 为准；没有运行后端套件、登录态浏览器或数据库迁移。
- 2026-10-03 单应用角色/成员委派：Vue/TypeScript 类型检查和 Vite production build 通过（3205 modules，入口 378.96 KB / gzip 117.51 KB，应用角色 chunk 15.40 KB / gzip 5.68 KB）；Python 标准库 AST 解析 62 个 `backend/app` 文件通过。本机 API `/api/v1/ready` 为 `ok`，OpenAPI 共 88 paths，权限目录要求 `role_id`，匿名角色列表返回 401；控制台入口、`App.vue` 和应用角色模块均返回 HTTP 200。此证据只确认服务加载与认证门槛，不覆盖租户授权/写入；宿主 Python 缺少 FastAPI/SQLAlchemy，后端测试未运行，未执行 migration，数据库最后确认版本仍为 `0010_tenant_user_groups`。新增后端测试补丁被自动审查拒绝，尚需用户明确授权。
- 模型治理补充：`vue-tsc --noEmit` 和 4 项模型目录契约/状态转换单测通过（含 PostgreSQL `FOR UPDATE` SQL 断言），Vite 模型页/共享 API 模块转换 HTTP 200，实时 OpenAPI 显示状态接口接收 `expected_status` + `status`。PostgreSQL 集成夹具运行失败，确认当前数据库缺少 `users.auth_version` 列（由迁移 `0011` 引入）；本轮未运行 migration 或完整后端套件。
- 本机 Windows Python 依赖不完整；本轮后端隔离单测通过 Docker API 容器运行。2026-09-29 完整后端 61 项与 revision `0010_tenant_user_groups` 是历史记录，不代表当前数据库状态。
- 生产 Compose 尚未在真实域名、TLS、外置签名密钥与生产 Secret 下启动；自动备份/异地恢复/监控闭环仍未完成。
- 2026-10-03 租户管理员前端扩展：`vue-tsc --noEmit` 通过；Vite production build 转换 3202 个模块，主入口 377.11 KB（gzip 117.14 KB），管理组件注册 chunk 285.65 KB（gzip 83.80 KB），最大 chunk 低于 500 KB。只读租户模式识别已修正；真实租户权限交互仍未浏览器验收。
- 登录页基础布局曾通过桌面与 390px 手机视口截图检查；其后新增的就绪提示和“重新检查”按钮目前只完成无障碍树确认，仍需重新做截图验收。登录后管理页的逐页与移动端视觉验收仍需管理员会话。
- 浏览器同意与 introspection 尚待真实 RP 客户端端到端验收；`0005` 用量正向入账与配额结算需要网关密钥及实际调用网关；当前配额执行默认关闭。租户邀请邮件可选启用 `IAM_INVITATION_EMAIL_ENABLED=true`。ToC 注册源码已到 migration `0025_registration_role_snapshot`，开发库仍为 `0021_resume_wallet_perms`，API readiness 为 `503 database_migration_pending`；`0022`–`0025` 未应用于开发库。SMTP 实际投递、退信监控、CAPTCHA/自适应防护、MFA、模型代理/Secret Manager、外部业务仓库适配和生产安全评审仍待完成。
- 本地开发配置和随机引导管理员密码存于根目录 `.env`（已忽略）；请在本地安全保管，不要粘贴进聊天或提交版本库。
- Docker Desktop 开发控制台的 Vite watcher 已启用 1000ms 文件轮询；重启 console 容器后模块接口返回 200 和 13 个首次访问异步 feature 导入，再次编辑宿主机 `App.vue` 后模块响应于 2.5 秒内更新。这个检查确认 watcher 捕获源码变化，不代表已验收全部浏览器交互。

## 文档与开发约定

每次开发同步维护本文、[前端指南](frontend/README.md)、[后端指南](backend/README.md)、[PRD](docs/产品需求.md) 和 [变更日志](CHANGELOG.md)。项目 Skill 规定跨层契约、数据模型与安全边界的同步规则。

前后端独立工程与模块职责见[项目代码架构](docs/技术架构与接入.md)。根目录 Compose 只负责服务编排；Vue 页面、FastAPI 路由、业务模型和 SDK 源码不可合并或互相导入。

新增的单应用角色控制台位于 `frontend/src/features/application-roles/`，后端接口位于 `backend/app/api/v1/tenant_admin_application_roles.py`，契约位于 `backend/app/schemas/access_control.py`。该领域模块通过 `/api/v1/tenant-admin/*` API 工作，不跨越 frontend/ 与 backend/ 工程边界；角色授权受当前应用和租户双重约束。

应用权限候选目录按目标角色读取；其他应用角色已保存的系统管理授权不会列入当前角色目录，也不能通过这个界面新建。

控制台 feature 使用 `defineAsyncComponent` 分域打包：未访问的页面不创建 DOM，首次导航时下载对应代码；访问后保持挂载，以保留主题草稿和筛选状态。共享加载/失败反馈位于 `frontend/src/shared/components/`。登录态浏览器的首次请求和失败恢复仍待验收。

后端管理 API 已按身份、RBAC、用户组、组织/数据范围、模型目录、用量、登录主题和审计拆分到 `backend/app/api/v1/admin/` 域模块；`admin/__init__.py` 只做统一管理员鉴权与路由装配。OIDC Provider 另按授权同意、Token/UserInfo/Introspection、登出和 Discovery 拆分到 `backend/app/api/v1/oidc_provider/`，`oidc.py` 只保留兼容导出及统一路由入口。Vue 源码独立位于 `frontend/`，不与 Python 工程共享目录或代码；工作台概览、登录主题、用户组、邀请管理、授权模拟、审计查询、权限目录、角色/授权、模型目录/用量、租户目录、OAuth 应用、用户和组织管理均已迁入 `frontend/src/features/<domain>/`。`frontend/src/app/auth/AuthEntry.vue` 承载公开登录、OIDC 同意和邀请接受，`App.vue` 承担登录后会话、当前页状态、外观和共享字典协调，导航白名单位于 `frontend/src/app/navigation.ts`，桌面侧栏/窄屏选择器位于 `frontend/src/app/components/AppSidebar.vue`；`frontend/src/app/ui/antd.ts` 先安装公共 UI，再在管理员登录/会话恢复时动态加载管理组件注册器。前后端源码目录保持独立，仅通过 HTTP/OpenAPI 和服务端 SDK 协作。

管理员邀请创建响应含一次性 bearer 链接，后端设置 `Cache-Control: no-store` 和 `Pragma: no-cache`；前端仅临时展示，关闭后清除。IAM 管理台及企业租户仍是邀请/bootstrap；ToC 产品登录页仅在全局总闸和应用注册策略同时开放时显示自助注册。SMTP、开发库 migration、真实邮件注册仍待验收，注册开关默认关闭。

权限目录现支持稳定编码的软停用与恢复：管理台展示引用角色数，二次确认状态变更；停用后在线判权排除该编码、禁止新增角色授予，并保留历史授权和数据范围供审计。恢复会重新激活仍保留的授予。后端以 `expected_status` 防并发覆盖并与审计同事务；新增 Alembic `0016_permission_status`；本地开发库当前 revision 已包含该迁移。模型目录启停也已采用 `expected_status`、行锁及同事务审计，避免过期管理页覆盖新状态。

当前唯一接入试点为 DeerFlow；AI Resume 与 Knowledge Base 现已从本地集成源码撤销，后续系统需在 DeerFlow 试点验收后重新决策。具体部署输入和验收边界见 [业务系统接入计划](docs/技术架构与接入.md)。

管理台视觉走查范围和待完成项见 [UI 走查记录](docs/验收记录.md)：当前已用浏览器无障碍树核对公开登录控件和就绪提示共存，但本轮没有取得桌面或 390px 视觉截图，也没有管理员登录会话。migration revision、完整后端套件、生产服务和登录后各管理页仍待分别验收。

本地 Compose 升级、备份/恢复演练步骤与生产运维缺口见 [运维手册](docs/部署与运维.md)。生产 Compose 部署骨架已编写但未经本机 Docker 构建/启动验证；该手册仍未提供自动备份、异地恢复或监控闭环。



## 最新核验（2026-10-09）

公开认证表单的长度限制已改为数值属性绑定，Vite 生产构建通过（3205 个模块，输出到 Windows Temp）。全量 `vue-tsc` 因当前 pnpm 依赖树未解析 Vue 的 `@vue/runtime-dom` / `@vue/compiler-dom` 类型而失败；没有联网安装依赖。Docker Compose CLI 可用，但本会话连接 Docker Desktop Linux Engine 命名管道被拒绝；未启动后端/数据库，也未执行迁移。请在本机启动 Docker Desktop 并确认 Engine 为 Running，再按 [本地启动指南](docs/部署与运维.md)运行。真实浏览器认证告警检查仍需可运行的 API 和浏览器环境。

### 2026-10-09 用户本机运行反馈

用户截图显示开发 Compose 服务已启动：PostgreSQL 和 console healthy，API 容器启动中（health: starting）。console 映射到 `http://localhost:5175/`，API 映射到 `http://localhost:8002/`。本会话仍不能访问 Docker Engine；当前未读取 API 日志/health/ready，也未检查数据库 revision 或执行迁移。

### 2026-10-09 服务不可用诊断

当前浏览器里的 readiness 提示为“数据库不可用”（`database_not_ready`），意味着 API 的数据库连接或只读探测失败；这不是单凭提示就能判定的迁移落后。PostgreSQL 容器 healthy 不验证 API 凭据。需在用户本机查看 `docker compose logs --tail 100 api`，再据日志确认配置；Codex 会话不能读 Docker Engine 日志。本轮没有改环境变量、数据卷或数据库。

### 2026-10-09 凭据故障确认

用户提供的日志显示 `password authentication failed for user "iam"`，因此当前 `.env` 提供给 API/迁移容器的密码与持久化 PostgreSQL 的角色密码不一致；这解释了 API unhealthy 和页面“数据库不可用”。迁移在连接阶段失败，没有应用 schema 变更。不要删除数据库卷；先恢复或安全重置 `iam` 密码，再验证连接。

## 本地服务恢复记录（2026-10-09）

修复了 PostgreSQL 持久化 iam 角色与环境配置中 API 凭据不一致的问题；数据库卷保留。迁移 0017–0021 已应用，API /api/v1/ready 返回 HTTP 200 ok，Compose 的 postgres、console、api 均 healthy。浏览器 http://localhost:5175/ 已加载公开认证页。没有验证管理员登录或登录态管理功能；启动与认证失败排查见本地启动指南（docs/部署与运维.md）。
## 本地凭据轮换记录（2026-10-09）

本地 IAM 管理员登录密码、PostgreSQL iam 角色密码及 JWT 签名密钥已轮换。管理员密码保存在根目录 .env；密码重置流程撤销了该用户现有会话。数据卷保留。Compose 的 postgres、api、console 均 healthy，数据库连接与 API readiness 验证通过。示例环境文件保留模板值；SMTP 当前未配置，模型用量 API Key 未改，避免与下游网关配置失配。

本轮按用户请求再次确认完成轮换：管理员密码哈希与 `.env` 中配置一致，管理员活动刷新会话为 0，存在 `auth.password_reset.complete` 审计记录；PostgreSQL `SELECT 1` 和 `/api/v1/ready` HTTP 200 均通过。没有在终端输出或文档保存密钥值；登录密码从本机 `.env` 的 `IAM_ADMIN_PASSWORD` 读取。未执行实际浏览器登录。

## 2026-10-09 · 管理台 UI 走查

在现有管理员会话中检查工作台、租户、应用、用户、角色、模型和登录主题空状态；覆盖 1680px 桌面、390px 窄屏及浅色/深色主题。修复应用/模型宽表格撑开整页的问题，并统一深色表格表面、空状态文字和滚动条样式；修改后复核桌面应用页及手机模型/应用页。Vite 生产构建成功（3205 模块，入口 382.49 KB / gzip 118.64 KB）；`npm run build` 中的 `vue-tsc -b` 因 Vue 类型声明链未解析而失败。模型页面加载时仍出现 HTTP 500 提示，失败接口和后端原因未定位；当前会话无法运行 Docker CLI 读取日志。登录主题编辑器需要已创建应用，本库暂无应用记录，尚未检查编辑预览。详见 [UI 走查记录](docs/验收记录.md)。

### 2026-10-09 复核更正

此前 UI 走查中的模型页 HTTP 500 已定位并修复：租户目录 API 缺少 `func` 与 `TenantMembership` 导入。浏览器复核租户目录为 1 个租户、2 个成员；模型页显示正常空态；用户页 2 个账号可见且“新建用户”入口已启用。`App.vue` 同时会在共享字典加载失败后于后续导航重试。Vite 构建通过；`vue-tsc` 仍因本地 Vue 类型声明解析失败。没有提交任何管理数据变更。细节见 [UI 走查记录](docs/验收记录.md)。

### 2026-10-09 · 前端标准构建恢复

pnpm 工作区为 Vue 类型声明增加公开 hoist，并在前端 Dockerfile 使用锁文件冻结安装。离线冻结安装未下载依赖；`npm run build` 现通过 Vue/TypeScript 检查和 Vite 生产构建（3205 modules，入口 382.70 KB / gzip 118.73 KB）。此前 `vue-tsc` 的类型错误已消除，并修复一处真实 style 类型问题。Docker 镜像本机未构建；部署范围的剩余输入与门槛见 [待提供配置清单](docs/部署与运维.md)。


## 2026-10-09 · 管理台视觉复查

以管理员会话只读浏览了平台管理核心页面，在浅色/深色主题下复核桌面界面；修正健康状态颜色与外观设置文本可读性。前端 `npm run build` 通过。手机尺寸、租户管理员专属页面和已创建应用的登录主题预览仍待验收，详见 [UI 走查记录](docs/验收记录.md)。


### 2026-10-09 · 前后端回归补充

前端 `npm run build`（含 Vue 类型检查）通过；后端在隔离 PostgreSQL 测试库中运行完整套件，109/109 通过。测试库迁移至当前 head 后创建并已清理，未修改本地开发数据库。浏览器 UI 的窄屏、租户管理员和登录主题实际发布流程仍待验收。

生产预检脚本已修复 Windows Docker CLI 别名解析；PowerShell 语法检查和使用生产示例环境文件的 Compose 配置解析通过。正式预检尚未执行，缺少 `.env.production.local` 与 Caddy 镜像；生产密钥和域名仍待部署配置。详见 [运维手册](docs/部署与运维.md)。

新增 PostgreSQL 恢复校验工具 `deploy/verify-postgres-restore.ps1`：先核对 `.sha256` sidecar，再把归档恢复至随机命名的隔离数据库，核验 Alembic revision 和关键 IAM 表；成功后清理临时库，失败时保留以便诊断，不指向现有业务库。PowerShell AST 解析通过；没有可用的真实归档/Docker 演练环境，因此恢复能力仍未验收。备份加密、自动调度、异地保存、保留策略和 RPO/RTO 仍待运维配置。

### 2026-10-09 · 审计筛选布局复核

管理员桌面浏览器复核工作台、应用目录、登录主题空状态和审计日志；修复审计日期筛选标签被压缩换行的问题。前端类型检查与生产构建通过；本轮未检查窄屏或主题编辑/发布流程，详情见 [UI 走查记录](docs/验收记录.md)。
#   r o l e 
 
 
