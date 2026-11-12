# Tasks

- [x] Task 1: 后端契约收口（F2 后端部分）
  - [x] 1.1 `permission_kinds.py`：`button.roles.manage` 映射收敛为仅 `rbac.role.manage`；`grant_codes_skip_missing` 契约必需码缺失时抛错（保留显式跳过参数供隔离场景，跳过时计数）
  - [x] 1.2 `GET /admin/permissions/tree` 响应扩展 meta：层级可见码集（L1/L3/多应用/L2）、五级模板码数、每节点 `kind` 与映射的接口码清单（供前端零硬编码）
  - [x] 1.3 `MENU_CATALOG` 新增 `menu.permission_health`（映射接口码：读体检数据所需的 `rbac.permission.read` + `rbac.role.read`）；`seed_greenfield.py` 仅给 L1 授该菜单码
  - [x] 1.4 新增/更新隔离测试：映射唯一性（H2 判定同源）、tree meta 形状、种子后 L1 持 `menu.permission_health` 且 L3 不持
- [x] Task 2: 后端体检端点（F1 后端）
  - [x] 2.1 新增体检服务（建议 `services/permission_health.py`）：实现 H1 菜单-接口对齐（阻断）、H2 按钮映射唯一性、H4 数据范围双轨（仅旧表未映射行数）、H5 未挂载码、H6 计数一致性、H7 孤儿码，共 6 项服务端检查 + H3（读回退计数器）+ H8（静态保障常量标注）
  - [x] 2.2 `GET /admin/permissions/health`：仅平台管理员；返回 `{items:[{id,status,summary,details:[{role,menu_code,missing_apis,member_count}]}], counters:{blocked,warn,ok}, generated_at}`
  - [x] 2.3 隔离测试：构造「持菜单缺接口」角色 → H1 阻断且详情正确；干净库 → 全部通过；非 L1 → 403
- [x] Task 3: 判权可观测与豁免收紧（F3）
  - [x] 3.1 `ensure_codes` 回退命中时计数器 +1 并记 WARN 日志（用户、码、角色 key）；计数器可被体检读取
  - [x] 3.2 敏感码双检统一：`_SENSITIVE_CODE_DUAL_CHECK` 改为按「写类按钮码清单」统一处理
  - [x] 3.3 绑定豁免收紧：`access_control.py` 绑定入口删除「已存在绑定直接 return」；`grantable` 必传显式值（L1 传全量），None 视为编程错误抛异常
  - [x] 3.4 隔离测试：回退命中计数与放行行为；越权方对已存在绑定操作 → 403；L1 正常路径无回归
- [x] Task 4: 数据范围写路径与分级（F4）
  - [x] 4.1 `organizations.py` 数据范围接口：删除 `del manage` 写法；写操作要求 `org.manage` 且 L3 起（L2 只读）
  - [x] 4.2 替换保存时同步双写数据叶子码授权（复用 `ensure_data_scope_children` + 授权写入；叶子缺失则补建）
  - [x] 4.3 隔离测试：L2 写 → 403 且读正常；L3 保存后叶子码授权存在、evaluate_access 结果不变
- [x] Task 5: 后端死代码与旧词清理（F8 后端部分）
  - [x] 5.1 删除 `rbac_guards.py` 的 `ensure_management_permission` 及旧码→角色映射表（grep 确认零引用）
  - [x] 5.2 `infer_permission_kind` / `permission_kind_of` 收敛：库列优先，前缀仅在该行 kind 为空时兜底
  - [x] 5.3 清理 `seed_greenfield.py`「iam.*」等旧词文案为五域/四类口径（不改种子码集语义）
- [x] Task 6: 前端码表消费重构（F2 前端部分）
  - [x] 6.1 `utils/permissionTree.ts`：删除 MENU_RELATED_APIS / BUTTON_RELATED_APIS / MENU_BUTTONS / MENU_GROUPS 硬编码，改为消费 tree 响应（含 meta）；保留纯函数（relatedApiCodes 等改为基于传入数据）
  - [x] 6.2 `utils/permissionGroups.ts`：删除 PLATFORM_SCOPE_CODES / TENANT_SCOPE_CODES 硬编码与「四级管理员」旧表述，层级码集/标签改由 tree meta 驱动；更新全部消费方
  - [x] 6.3 `RoleManagement.vue`：统计文案（27/20/16/15）改由契约常量渲染；删除 P390 死 CSS（.scope-wizard/.scope-card/.role-kind-filter）
  - [x] 6.4 eslint + `npm run build` 通过；grep 确认前端无菜单↔接口映射硬编码残留
- [x] Task 7: 前端判权统一与入口收口（F7）
  - [x] 7.1 `api/capabilities.ts` 新增 `hasMenu(code)` / `hasButton(code)`（内部 any-of + L1 放行语义），替换 ApplicationMoreHost / OrganizationMoreHost / ApplicationPermissionPanel / RoleManagement / ModelGovernancePage 等处 `platform_admin && hasAny(...)` 双轨写法
  - [x] 7.2 API 前缀常量化：RoleMembersModal / RolesTab 删除 `/tenant-admin` 硬编码，改从会话上下文取（平台视角 `/admin`、租户视角 `/tenant-admin`）
  - [x] 7.3 `router/index.ts`：/application-roles、/applications、/organizations 重定向去重注册；`navigation.ts` PAGE_INFO 清理已收口键
  - [x] 7.4 eslint + `npm run build` 通过
- [x] Task 8: 权限体检页（F1 前端 + F5）
  - [x] 8.1 新增 `views/permission-health/`（index.vue + 子组件）：三卡统计 + H1–H8 检查项列表 + 详情抽屉（受影响角色表 + 修复指引）+「立即复检」；空/加载/失败三态齐全；可见性挂高级管理组（menu.permission_health）
  - [x] 8.2 第二 Tab「成员与生效」（F6 前端）：用户选择（本平台用户搜索）+ 租户上下文 → 有效角色（来源标注）→ 持码四类分组 → 菜单命中判定（缺码清单 + 指向体检项）
  - [x] 8.3 `navigation.ts` / `router`：新页面注册（L1 菜单码裁剪自然生效）；审计与验证组不放新项（产品裁决：并入体检页）
  - [x] 8.4 `RolePermissionGrantModal.vue`（F5）：勾选 `menu.*` 时按 tree 映射校验接口码齐全，缺失则禁用保存并列清单（与 H1 同判定）；补齐恢复
  - [x] 8.5 eslint + `npm run build` 通过；浏览器走查（有条件时）
- [x] Task 9: 成员与生效后端聚合端点（F6 后端）
  - [x] 9.1 新增只读端点（建议 `GET /admin/permissions/user-chain`）：入参 user_id + tenant_id + 可选 menu_code；输出有效角色（来源 direct/group + 组名）、持码四类分组、对 menu_code 的命中判定（缺码清单）
  - [x] 9.2 复用 `effective_roles` / holders 既有实现，不新建判权路径；仅平台管理员；隔离测试：直连 + 组继承两来源并集、缺码场景输出与 H1 一致
- [x] Task 10: 全量验证与收尾
  - [x] 10.1 后端：新增/受影响隔离测试全绿（permission_health / permission_tree / p405_layering / role_guards / platform_tenant_guards 回归）
  - [x] 10.2 前端：eslint（改动文件）+ `npm run build` exit 0
  - [x] 10.3 对照 checklist.md 逐项核验并勾选；CHANGELOG.md 添加事实记录（含「未运行」项：生产迁移执行、回退下线决策、真实环境浏览器走查视条件标注）


- [x] Task 11: 验证轮修复（Task 10 派单项）
  - [x] 11.1 修复 test_p404_visibility 4 error：按 F3「判权只认码」口径修夹具（make_tenant_role_binding 显式传模板 permission_ids），不恢复角色 key 回退
  - [x] 11.2 F7-2 收口：非归档前端剩余 /tenant-admin 字面量全部改走导出常量（仅常量定义处保留字面量）；OrganizationMoreHost.vue:65 在列
  - [x] 11.3 F8-3 补清：backend「四级管理员/前四级」旧词 8 处 + auth.py:689 iam.* docstring 改五级/五域口径（仅注释与文案）
  - [x] 11.4 复验：p404 模块测试全绿 + 改动前端文件 eslint + npm run build exit 0

# Task Dependencies

- Task 1 是 Task 2 / 6 / 8 的前置（tree meta 与契约形状）
- Task 3 / 4 / 5 相互独立，可与 Task 1 并行（均不依赖 tree meta）
- Task 8 依赖 Task 1 + 2 + 6（页面消费体检端点与 tree meta）
- Task 9 独立于 Task 1–5，可并行；Task 8.2 依赖 Task 9
- Task 10 依赖全部
- Task 11 由 Task 10 验证派单产生，依赖 10 的核验结果





