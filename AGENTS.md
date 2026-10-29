# 项目接手与进度维护

适用于 `D:\project\role`。用户当次指令优先。

1. 开始工作先读 [当前进度与后续计划](docs/项目总览与进度.md)，再读 [PRD](docs/产品需求.md) 和本次相关技术文档。项目开发遵循 `.codex/skills/iam-project/SKILL.md`；其中历史快照不能覆盖交接文件中的最新证据和已确认决策。

1b. 前端/管理台改版与新页面必须遵守 [UI 设计系统](docs/ui-design-system.md)，验收用 [checklist](docs/ui-design-system-checklist.md)。工程约定：有通用组件先用通用组件（禁止重复造轮子）；模块采用 `文件夹/index` 写法；有关联关系的文件放同一文件夹。
1c. 信息架构：侧栏以**应用工作台 / 组织工作台**为主；应用·角色·权限编码·组织·用户组独立列表进「高级管理」。资源树为正式能力（勿再写「不建 Resource」）。
2. 每次功能、修复、文档或验收工作结束前，同步更新 `docs/项目总览与进度.md`：更新时间、当前任务状态、本次改动、实际验证结果、阻塞原因和下一步。发生范围变化时同步任务依赖及验收条件；未运行的验证明确写“未运行”。
3. 保留任务 ID，避免换模型后丢失跟踪关系。将源码完成、隔离/mock 验证、目标环境验收分别记录；不得仅凭历史测试或局部通过标记端到端完成。
4. 按 IAM Skill 同步根目录与前后端 README、PRD，向 `CHANGELOG.md` 添加本次事实记录。日常交接更新不自动触发 `--更新` 全项目审计，也不创建后台自动任务。
5. **本阶段范围**：只维护 IAM 管理台与绿场后端；**不做** DeerFlow / 业务项目接入联调。「新项目接入」视图已归档到 `frontend/src/views/_archive/integration/`。业务对接文档见 [对接手册](docs/后续项目对接手册.md)（顶部已标「本阶段不做」）。数据库迁移需要受保护备份和明确授权；配额 enforcement、公开注册继续遵守交接文件的上线门禁。
6. 权限模型以 [方案 A 绿场重建规格](role-plan-a-tech-pack/role-iam-plan-a-greenfield.md) 为准，编码体系以 P392 为准：四级角色写死（L1 `platform.admin`/L2 `app.admin`/L3 `tenant.admin`/L4 `app.member`），admin 面逐路由按五域权限码判权（27 码：`platform.*`/`rbac.*`/`org.*`/`app.*`/`ops.*`，权威码表 `docs/prototypes/permission-rebrand/PRD.html` 与 PRD §3.1；`services/rbac_guards.py`），唯一有效角色实现见 `services/effective_roles.py`；业务权限码强制 data_scope；`ALLOW_BOOTSTRAP_EMAIL_BYPASS` 生产保持 false。旧 `iam.*` 码与 `platform.super_admin`/`tenant.org_admin` 已作废，仅存于历史记录。
7. DeerFlow（若存在于 `D:\project\deer-flow`）**不在本仓库改造范围内**；本阶段不对 DeerFlow 做任何对接或清理以外的改动。配权与 IA 以 [配权说明书](docs/配权说明书.md) 与侧栏「工作台 / 高级管理」为准。
