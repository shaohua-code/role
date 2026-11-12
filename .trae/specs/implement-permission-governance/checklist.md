# Checklist

## F1 权限体检页
- [x] `GET /admin/permissions/health` 仅 L1 可用，返回 H1–H8 结构化检查结果
- [x] H1 菜单-接口对齐：构造「持菜单缺接口」角色时状态为阻断，详情含角色/缺失码/成员数
- [x] H2/H4/H5/H6/H7 判定与 PRD 定义一致，且与码表契约同源
- [x] H3 展示回退命中计数；H8 以静态保障标注呈现
- [x] 体检页挂高级管理组，三卡统计 / 检查项列表 / 详情抽屉 / 立即复检渲染正常，空/加载/失败三态齐全
- [x] L3/L2 直接调用体检端点返回 403；深链页面被守卫拦截

## F2 码表单一来源
- [x] `button.roles.manage` 映射仅含 `rbac.role.manage`
- [x] tree 响应 meta 含层级可见码集与五级模板码数；前端目录/挂码弹窗消费该数据
- [x] `permissionTree.ts` 四张硬编码映射表与 `permissionGroups.ts` 层级码集硬编码已删除，全仓 grep 无菜单↔接口映射硬编码残留
- [x] `grant_codes_skip_missing` 契约必需码缺失时抛错而非静默
- [x] `menu.permission_health` 已入 MENU_CATALOG 与种子，L1 持有、L3 不持有

## F3 判权可观测
- [x] `ensure_codes` 回退命中时计数 +1 且 WARN 日志含用户/码/角色 key；放行行为窗口内不变
- [x] 敏感码双检覆盖统一写类按钮码清单
- [x] 「已存在绑定直接 return」豁免已删除；越权方操作已存在绑定返回 403
- [x] `grantable` 必传显式值；L1 正常授权路径无回归

## F4 数据范围
- [x] `del manage` 写法已删除；L2 写数据范围 → 403，读正常
- [x] L3 保存策略时数据叶子码授权同步写入，`evaluate_access` 结果不变（双读并集）
- [x] H4 输出「仅旧表未映射」行数

## F5 挂码缺口阻断
- [x] 勾选 `menu.*` 缺映射接口码时保存按钮置灰并列出缺失码清单，提示与 H1 同判定
- [x] 补齐后提示消失、保存恢复；取消菜单码同样恢复

## F6 成员与生效
- [x] 聚合端点返回有效角色（直连/组继承来源标注）、四类持码分组、菜单命中判定
- [x] 多角色并集正确；缺码场景输出与 H1 一致；仅 L1 可用

## F7 前端判权统一
- [x] `hasMenu` / `hasButton` 统一工具落地，双轨写法全部替换（grep 无 `platform_admin &&` 判权残留）
- [x] `/tenant-admin` 硬编码删除，前缀从会话上下文取
- [x] 三个重定向路由无重复注册；PAGE_INFO 已收口键清理

## F8 死代码与旧词
- [x] `ensure_management_permission` 及旧码映射表删除且零引用
- [x] `infer_permission_kind` 库列优先、前缀仅兜底
- [x] P390 死 CSS、旧词（iam.* 文案、「四级管理员」）清理完毕

## 全量验证
- [x] 后端新增/受影响隔离测试全绿（permission_health / permission_tree / p405_layering / role_guards / platform_tenant_guards）
- [x] 前端 eslint（改动文件）+ `npm run build` exit 0
- [x] 未运行项如实记录到 CHANGELOG（生产迁移执行、回退下线决策、真实环境浏览器走查）

