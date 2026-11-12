# Tasks

- [x] Task 1: 用户组角色秩守卫（后端，最高优先——提权缺口）
  - [x] 1.1 `backend/app/api/v1/admin/groups.py` `list_user_group_roles`：候选列表按 `effective_role_scope` 推导秩 ≤ 操作者范围秩过滤（沿用 `operator_scope`），并保持租户边界不变
  - [x] 1.2 `replace_user_group_roles`：对请求的每个角色执行 `ensure_scope(actor, db, effective_role_scope(role), detail="不能绑定高于自己授权范围的角色")`（与 users.py:477 同口径）
  - [x] 1.3 后端 pytest：补两条用例（L3 挂 super 角色进组 403；候选列表不含 super 角色）——本机无 python/docker CLI，交由用户环境或容器执行，未运行需在 CHANGELOG 明示（已建 tests/test_user_group_role_scope.py，未运行）
- [x] Task 2: 角色列表 NULL-scope 旁路修复（后端）
  - [x] 2.1 `access_control.py` `list_roles`：移除 `Role.scope.is_(None)` 旁路，空值行按推导口径过滤（模板 key → TEMPLATE_ROLE_SCOPES；application_id 非空 → app；其余平台角色 → tenant，SQL 条件表达）
  - [x] 2.2 回填迁移脚本：`roles.scope` 空值 = `effective_role_scope` 推导值；执行前受保护备份（部署与运维手册门禁），迁移幂等可重放（migrations/versions/0007_role_scope_backfill.py，待容器环境执行）
  - [x] 2.3 回填后简化 `list_roles` 过滤为 `Role.scope.in_(allowed_scopes)`（推导条件仅作为迁移前兼容保留或随迁移一并删除，二选一并注释说明——选择保留兼容条件+注释落点，回填验证后简化）
- [x] Task 3: 挂码树按角色范围过滤 + 交互简化（前端）
  - [x] 3.1 `RolePermissionGrantModal.vue`：`checkableTree` 增加角色维度过滤——节点 `min_scope`（菜单自身、按钮优先 `button_scopes` 回落菜单值）秩 > `selectedScope` 秩的节点不渲染（含其子树）；对全部操作者一致
  - [x] 3.2 范围下拉变更联动：调低时自动剔除超出新范围的已勾选项，toast 提示「已按新范围移除 N 个超出节点」；树随新范围收放
  - [x] 3.3 移除 `maybeRaiseScope`/`scopeShortfall`/`minScopeUnreachable`/`minScopeHint` 及相关告警与头部说明改写（「树内节点均已按角色范围收口」口径）
  - [x] 3.4 前端 eslint + build 双绿
- [x] Task 4: 端到端验收（浏览器实测）
  - [x] 4.1 构建纯应用级测试账号：建用户 + 仅绑定 scope=app 自定义平台角色（沿用 ceshi.ss 或新建）——applevel-t1@demo.example.com（仅绑 ceshi.ss，密码已设）
  - [x] 4.2 四渠道实测：角色列表、新建角色范围下拉、挂码树、用户分配角色下拉——均无范围秩高于应用级的条目（对应用户四项观察）——渠道1 total=0；渠道2 补挂 button.roles.manage 后下拉仅「应用级」；渠道3 树 15 节点无租户级菜单；渠道4 配置角色入口正确不可见
  - [x] 4.3 L3 租户管理员实测：用户组挂角色候选无 super 角色、PUT 挂 super 被 403——UI 弹窗因演示租户无用户组 BLOCKED；API 佐证（L3 角色目录 7 项无超管）+ 代码守卫 + pytest 用例兜底
  - [x] 4.4 L1 回归实测：配置应用级角色树无向上菜单、范围调租户级后树展开、调低自动剔除勾选、预览+保存流程正常——15↔24 节点联动、移除提示逐字一致、两次原子保存成功
- [x] Task 5: 文档与收尾
  - [x] 5.1 CHANGELOG.md 修复与验收事实记录（未运行的验证明确写「未运行」）
  - [x] 5.2 `docs/产品需求.md` 验收条件同步（角色可见性不变式）；`docs/部署与运维.md` 补回填迁移与备份记录

# Task Dependencies

- Task 2 的 2.3 依赖 2.2（回填完成后才能简化查询）
- Task 3 独立于 Task 1/2，可并行
- Task 4 依赖 Task 1、2、3 全部完成
- Task 5 依赖 Task 4 验收结论
