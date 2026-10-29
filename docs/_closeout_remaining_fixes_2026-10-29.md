# 收口后剩余问题修复记录（2026-10-29）

不建 git。对照「仍严重/中等」项处理结果：

| 项 | 结果 |
|---|---|
| 重启 API / CORS 仅管理台 | 已验证：`CORS_ORIGINS=["http://localhost:5175"]`；Origin 5175 有 ACAO，3000 无 |
| 授权两套真相 UX | 配权说明书加强「码管菜单、角色管接口」；应用工作台 Tabs 与高级列表加提示 |
| 拆 App.vue 巨石 | `useReadinessPoll` / `useTableFit` / `useShellAppearance` + `layout/page-registry.ts`；备份 `_agent_dump/App.vue.pre_split_backup` |
| ESLint + smoke | `frontend/eslint.config.js`；`pnpm lint` / `pnpm smoke` |
| 文档清场 | `plan-a`、`prototypes`、`examples` → `docs/_archive`；含 DeerFlow/接入旧文文首标过时 |
| sdk / examples | 示例归档；sdk README 标明非本阶段产品路径（compose 仍挂载 typescript sdk，未删包） |
| 工作台 vs 高级 | 高级列表页增加互链文案；工作台保留日常主路径 |
| 审计 Tab | 已有登录/操作拆分，确认保留 |

验收：5175 可开；CORS 生效；壳可维护；文档无「接入已落地」误导（旧文已标过时/归档）；lint/smoke 可跑。
