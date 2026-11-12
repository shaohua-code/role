# Tasks

- [x] Task 1: 迁移 `0007_globalize_platform_roles`：平台角色全局化数据合并
  - [x] 1.1 平台租户 id 解析（slug=platform）为宿主；业务租户中 `application_id IS NULL` 的角色逐 key 合并到宿主：同 key 保留首份（name/description/scope 取秩最高）、`role_permissions` 并集去重、`role_bindings` 全量迁到宿主角色（membership 不动，冲突绑定去重）
  - [x] 1.2 无 key 冲突的角色整行改 `tenant_id=平台租户`；应用类角色（`application_id IS NOT NULL`）不动
  - [x] 1.3 迁移含回滚说明（仅结构回退、数据合并不可逆）；离线 `alembic upgrade head --sql` 编译验证
  - [x] **用户裁决（2026-10-31）：迁移文件已删除**——开发库当前无业务租户平台角色存量（全库仅 platform.admin 宿主平台租户），全局化由代码语义直接落地（provision 全局化 + create_role 宿主），无数据迁移；未来生产库若出现业务租户平台角色存量，再行裁决合并方案。
- [x] Task 2: 生效链路放宽（`effective_roles.py` + `rbac_guards.py`）
  - [x] 2.1 `authorized_role_ids_statement`：直连分支平台类角色不再过滤 `role.tenant_id == membership.tenant_id`（应用类保留同租户过滤）；组继承分支保持现状
  - [x] 2.2 `bind_role` / `unbind_role` / `replace_user_role_bindings` / `list_user_role_bindings`：平台角色跳过「角色与成员同租户」校验与租户过滤；应用角色保持；候选角色查询改「全局平台角色 ∪ 该租户应用角色」
  - [x] 2.3 任命天花板语义回归：`platform.admin`/`tenant.admin` 仅超管可绑，`app.admin` 需租户级（现有逻辑在新全局语义下用例更新）
- [x] Task 3: 模板供给全局化（`role_provisioning.py` + `seed_greenfield.py`）
  - [x] 3.1 `provision_tenant_admin_role` 改为幂等确保全局一份（宿主平台租户）；`create_tenant` 调用点与种子走查（`seed_walkthrough_accounts` 的 L3/L2 绑定）适配
  - [x] 3.2 `is_platform_class_role` / `is_custom_role` / `TEMPLATE_ROLE_KEYS` 消费点复核（不再隐含「角色属于业务租户」）
- [x] Task 4: 平台租户隔离（伴生修复）
  - [x] 4.1 `list_management_capabilities`：非超管时 `tenants` 排除平台管理租户（join tenants 按 slug=platform 过滤）
  - [x] 4.2 `create_user` / `bind_role`：非超管禁止把成员/绑定落到平台管理租户（422，复用 `PLATFORM_TENANT_SLUG` 常量）；超管不受限
- [x] Task 5: 角色 API 去租户维度（`access_control.py`）
  - [x] 5.1 `create_role`：移除 tenant_id 必填（平台类角色强制宿主平台租户）；应用角色入口保持应用工作台约束
  - [x] 5.2 `list_roles`：平台类角色全局可见性按范围秩（不再按 tenant_scope 过滤平台角色）；`clone_role`/`update_role`/`delete_role`/`set_role_status` 同步
  - [x] 5.3 `assert_actor_can_see_role` / `assert_actor_can_manage_role`：去掉租户归属校验对平台角色的适用（保留范围秩 + 应用可见性）
- [x] Task 6: 前端适配
  - [x] 6.1 `RoleManagement.vue`：新建弹窗移除「所属租户」；列表租户列改「全局」标记或移除；编辑/克隆同口径
  - [x] 6.2 `App.vue`：`tenantRowFromCapabilities` 透传 slug（membership 字典接口含 slug 或单独映射）；绑定候选/成员弹窗（`RoleMembersModal.vue` 等）候选角色改全局口径
  - [x] 6.3 用户管理「按租户配角色」候选列表改「全局平台角色 + 该租户应用角色」
- [ ] Task 7: 测试与全量验证
  - [ ] 7.1 测试适配：`test_role_hierarchy_guards` / `test_p405_layering` / `test_p404_visibility` / `test_greenfield_rbac` / `test_role_updates` / `test_user_lifecycle` 中同租户绑定断言改全局语义；新增「一角色多租户生效」与「平台租户隔离」用例
  - [ ] 7.2 全量 unittest discover 0 failures；隔离 Postgres 套件（含 0007）通过
  - [ ] 7.3 前端 `npm run build` + `lint:main` 通过
  - [ ] 7.4 主栈迁移演练（0007 需用户授权后执行）：备份 → 迁移 → seed → 浏览器走查「用户绑 A/B 两租户 + 全局租户管理员角色 → 两租户数据均可见」

# Task Dependencies

- Task 2 依赖 Task 1（先有全局宿主数据形态）
- Task 3 依赖 Task 1；Task 4 依赖 Task 2（capabilities/绑定校验在放宽后收口）
- Task 5 依赖 Task 1/2；Task 6 依赖 Task 5（契约先行）；Task 7 依赖全部
- Task 6 与 Task 4/5 后端就绪后可并行
