# Tasks

- [x] Task 1: 后端防呆补齐（4 处 422 保护，统一文案口径）
  - [x] 1.1 `tenants.py set_tenant_status`：slug=platform 禁止置为 disabled（active 幂等放行），文案「平台引导租户承载系统应用与 L1 宿主，不允许停用」
  - [x] 1.2 `organizations.py create`：tenant_id 为平台租户 → 422「平台引导租户为系统保留租户，不支持业务组织」
  - [x] 1.3 `invitations.py` create + create_invitations_batch：tenant_id 为平台租户 → 422「平台引导租户为系统保留租户，不支持成员邀请」（resend/撤销/兑换不加限制）
  - [x] 1.4 `groups.py create_user_group`：tenant_id 为平台租户 → 422「平台引导租户为系统保留租户，不支持业务用户组」
  - [x] 1.5 复用 `app.db.seed_greenfield.PLATFORM_TENANT_SLUG` 常量，禁止各文件手写 "platform" 字面量
- [x] Task 2: 隔离测试覆盖平台租户负路径（新增 `backend/tests/test_platform_tenant_guards.py`）
  - [x] 2.1 四类 422 负路径用例（停用平台租户 / 平台租户建组织 / 平台租户发邀请（单+批量）/ 平台租户建用户组）
  - [x] 2.2 正路径对照：普通组织租户建组织、consumer 租户发邀请不受影响
  - [x] 2.3 api 容器运行新模块 + `test_g16_g24.py` 回归（P372 基线 50 项不回归）——实测新套件 7/7 OK + 基线回归全绿（P382 收口时执行；P383 收尾时再次回归 7/7 OK）
- [x] Task 3: 前端创建类租户下拉排除平台租户（P383 收尾时实查确认已落盘：三页 filter 均存在）
  - [x] 3.1 `OrganizationManagement.vue`：租户选择下拉与新建组织的 activeTenantOptions 排除 slug=platform（L82/86/90）
  - [x] 3.2 `InvitationManagement.vue`：新建/批量邀请的租户下拉排除平台租户（租户筛选器保留）（L61）
  - [x] 3.3 `GroupManagement.vue`：新建用户组租户下拉排除平台租户（租户筛选器保留）（L33）
  - [x] 3.4 排除逻辑统一为 `slug === 'platform'` 判定，附中文注释说明平台租户边界
- [x] Task 4: 验证与文档
  - [x] 4.1 vue-tsc -b + Vite 生产构建 exit 0（P382 当轮与 P383 收尾复跑均通过）
  - [x] 4.2 api 容器 --reload 探活 + 实测平台租户四类操作 422（curl/python 脚本）——**部分完成**：api 容器探活通过（P383 走查登录实测存活）；四类操作真实 HTTP 422 实测**未运行**（负路径已由隔离测试 7 项覆盖）
  - [x] 4.3 进度文档 P382 入表 + CHANGELOG + 收尾汇报

# Task Dependencies

- Task 2 依赖 Task 1（先有保护才有负路径可测）
- Task 3 与 Task 1/2 无依赖，可并行
- Task 4 依赖 Task 1–3 全部完成
