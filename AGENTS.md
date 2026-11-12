# 项目接手与进度维护

适用于 `D:\project\role`。用户当次指令优先。活文档只有四份：[产品需求](docs/产品需求.md)、[应用对接](docs/应用对接.md)、[部署与运维](docs/部署与运维.md)、[项目启动](docs/项目启动.md)。历史事实见 [CHANGELOG.md](CHANGELOG.md)。

1. 开始工作先读 [产品需求](docs/产品需求.md)；本次涉及接入、部署或本地启动时再读对应手册。项目开发遵循 `.codex/skills/iam-project/SKILL.md`。
1b. 前端 / 管理台改版与新页面必须遵守产品需求中的 UI 硬规则。工程约定：有通用组件先用通用组件（禁止重复造轮子）；模块采用 `文件夹/index` 写法；有关联关系的文件放同一文件夹。
1c. 信息架构：侧栏以**应用工作台 / 组织工作台**为主；平台角色、权限编码、用户组独立列表进「高级管理」。应用与组织的目录 CRUD 在对应工作台完成（左树新建，节点右侧「更多」打开弹窗）。资源树为正式能力。
2. 每次功能、修复、文档或验收工作结束前，向 `CHANGELOG.md` 添加本次事实记录（含验证结果；未运行的验证明确写“未运行”）。发生范围变化时同步产品需求中的验收条件。日常交接不自动触发 `--更新` 全项目审计，也不创建后台自动任务。
3. 保留任务 ID。将源码完成、隔离 / mock 验证、目标环境验收分别记录；不得仅凭历史测试或局部通过标记端到端完成。
4. 按 IAM Skill 同步根目录与前后端 README、产品需求。
5. **本阶段范围**：只维护 IAM 管理台与绿场后端；**不做** DeerFlow / 业务项目接入联调。「新项目接入」视图已归档到 `frontend/src/views/_archive/integration/`。业务对接契约见 [应用对接](docs/应用对接.md)。数据库迁移需要受保护备份和明确授权；配额 enforcement、公开注册继续遵守上线门禁。
6. 权限模型以 [方案 A 绿场重建规格](role-plan-a-tech-pack/role-iam-plan-a-greenfield.md) 为准，编码体系以 P392 为准，产品分层以 P405 为准：五级平台角色写死（L1 `platform.admin` / L3 `tenant.admin` / 多应用 `apps.admin` / L2 `app.admin` / L4 `app.member`），应用角色可挂操作者可见的租户 / 应用管理码与本应用业务码；admin 面逐路由按五域权限码判权（27 码：`platform.*` / `rbac.*` / `org.*` / `app.*` / `ops.*`，权威码表 [产品需求](docs/产品需求.md) 与 `services/rbac_guards.py`），唯一有效角色实现见 `services/effective_roles.py`；业务权限码强制 data_scope；`ALLOW_BOOTSTRAP_EMAIL_BYPASS` 生产保持 false。旧 `iam.*` 码与 `platform.super_admin` / `tenant.org_admin` 已作废，仅存于历史记录。
7. DeerFlow（若存在于 `D:\project\deer-flow`）**不在本仓库改造范围内**；本阶段不对 DeerFlow 做任何对接或清理以外的改动。配权与 IA 以 [产品需求](docs/产品需求.md) 与侧栏「工作台 / 高级管理」为准。
