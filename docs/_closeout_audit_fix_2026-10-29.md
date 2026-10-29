# 审计不足补齐 · 收口报告（2026-10-29 Asia/Shanghai）

## 结论
已在 `D:\project\role` 落地深度审计 P0–P2 的**产品收口**项（不建 git、不清库、不动 DeerFlow、不做业务接入联调）。管理台主路径改为工作台；文档口径与三层配权一致。

## 文件清单（本轮改动）

### 前端
| 路径 | 动作 |
|---|---|
| `frontend/src/router/navigation.ts` | 新增侧栏组「高级管理」；列表页降级；工作台为主 |
| `frontend/src/layout/AppSidebar.vue` | `advanced` 默认折叠 |
| `frontend/src/views/application-workspace/index.vue` | 注释对齐高级组 |
| `frontend/src/views/application-workspace/tabs/RolesTab.vue` | **补数据范围**弹窗 + 高级角色列表互链 |
| `frontend/src/views/organization-workspace/tabs/MembersTab.vue` | 互链「用户管理」 |
| `frontend/src/views/organization-workspace/tabs/GroupsTab.vue` | 互链「高级用户组列表」 |
| `frontend/src/views/overview/OverviewPage.vue` | CTA/快速上手指向工作台；去掉「试点待接入」文案 |
| `frontend/src/views/integration/*` | **归档** → `frontend/src/views/_archive/integration/` |
| `frontend/src/router/index.ts` | 未改（保留 `/project-integration` → 应用工作台） |

### 后端 / 部署
| 路径 | 动作 |
|---|---|
| `backend/app/core/config.py` | CORS 默认仅 `http://localhost:5175`（去掉 `:3000`） |
| `compose.yaml` | `CORS_ORIGINS` 同步去掉 `:3000` |

### 文档
| 路径 | 动作 |
|---|---|
| `README.md` | 顶部现行口径 |
| `AGENTS.md` | 1c IA；5/7 范围（不做接入/DeerFlow） |
| `docs/配权说明书.md` | §3 入口表 + 归档说明 |
| `docs/后续项目对接手册.md` | 顶部「本阶段不做」声明 |
| `docs/技术架构与接入.md` | 归档补充 |
| `docs/项目总览与进度.md` | 本轮收口段 |
| `docs/glm-align-user-centent-prompt.md` | 勘误横幅（若需） |

### 临时脚本（可删）
`scripts/_patch_roles_tab.py`、`_patch_overview.py`、`_patch_org_tabs.py`、`_patch_docs.py`、`_patch_docs2.py`、`_patch_progress.py`

## 如何验收
1. 启动管理台（`start-local.ps1` 或已有 compose），打开 http://localhost:5175 登录。
2. 侧栏：**身份与组织**应见组织工作台 / 用户 / 邀请；**应用与权限**应见应用工作台；**高级管理**默认折叠，展开可见应用/角色/权限编码/组织/用户组。无「新项目接入」。
3. 应用工作台 → 选应用 → **角色** Tab：有「配置权限 / 配置资源 / 数据范围」；可点「高级角色列表」。
4. 组织工作台 → 成员/用户组 Tab 有前往用户管理或高级用户组按钮。
5. 审计日志页有「管理操作 / 登录与认证」Tab。
6. 访问 `/project-integration` 应跳到应用工作台。
7. 读 README / 配权说明书 / 对接手册顶部，口径一致：不做接入/DeerFlow；三层配权；工作台为主。

## 未做 / 明确不做
- git init
- App.vue 大拆路由
- 推倒 L1–L4 / 资源树
- 前端 lint/测试全量（非本轮必须）
- DeerFlow 与业务接入联调
- 若 API 容器已在跑，需**重启 api** 后 CORS 新默认才生效（或依赖 compose 环境变量覆盖）

## 保留能力
前端码 + 后端角色、用户多角色、应用/组织工作台、应用资源树、审计双 Tab。