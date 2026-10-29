# 00 — 总览与文档索引

> **【P392 更正（2026-10-28）】** 本规格包撰写后的 P392 将管理面编码更替为三段式五域 27 码（`platform.*`/`rbac.*`/`org.*`/`app.*`/`ops.*`），角色 key 更名为 `platform.admin`/`tenant.admin`（L2/L4 不变）。本文及包内各篇出现的 `iam.*` 码与旧角色 key 一律以 **P392 新口径**（`docs/prototypes/permission-rebrand/PRD.html`、[产品需求 §3.1](../产品需求.md)）为准；架构、判权流程与验收方法仍然有效。

> **方案：** 版本 A 绿场重建（增强型分层 RBAC + 四级角色）  
> **前提：** 允许清空数据库与旧接入；SDK 可 breaking；不做存量迁移。  
> **产品规格主文：** [role-iam-plan-a-greenfield.md](./role-iam-plan-a-greenfield.md)  
> **对比原文（演进式 A/B）：** `/workspace/role-iam-deep-refactor-two-versions.md`（冲突时以绿场规格为准）

---

## 1. 一句话目标

在空库上重建 IAM：用 **同一套有效角色判定** 支撑 OIDC、业务 check、管理台/租户台；用 **四级种子角色**（L1 超管 → L2 应用管理员 → L3 租户管理员 → L4 用户）落地分权；**L2/L3 互不包含**；去掉邮箱一刀切超管作为长期真相。

## 2. 文档地图

| 序号 | 文件 | 内容 |
|------|------|------|
| 00 | 本文件 | 总览、原则、阅读顺序、术语 |
| 01 | [01-architecture.md](./01-architecture.md) | 总体架构、模块边界、mermaid |
| 02 | [02-data-model.md](./02-data-model.md) | 表字段级 ER、约束、种子数据 |
| 03 | [03-authz-flow.md](./03-authz-flow.md) | 登录 / OIDC / check / 管理台时序 |
| 04 | [04-api-design.md](./04-api-design.md) | 管理面·租户面·授权 API（含解绑、capabilities） |
| 05 | [05-role-matrix.md](./05-role-matrix.md) | 四级权限矩阵终稿 |
| 06 | [06-frontend.md](./06-frontend.md) | 信息架构、路由守卫、能力裁剪 |
| 07 | [07-sdk-integration.md](./07-sdk-integration.md) | SDK 2.x 与业务接入规范 |
| 08 | [08-security.md](./08-security.md) | 会话版本、破窗、审计、密钥 |
| 09 | [09-bootstrap-ops.md](./09-bootstrap-ops.md) | 清库重建与部署运维 |
| 10 | [10-test-acceptance.md](./10-test-acceptance.md) | 测试策略与验收用例 |
| 11 | [11-menu-role-relation.md](./11-menu-role-relation.md) | 三图菜单定稿、关联可行性、修正模型 |
| 12 | [12-ui-design-system.md](./12-ui-design-system.md) | UI 设计系统与开发规范 |
| 12b | [12-ui-design-system-checklist.md](./12-ui-design-system-checklist.md) | UI 验收一页清单 |
| — | [role-iam-plan-a-greenfield.md](./role-iam-plan-a-greenfield.md) | 产品+实施规格（路径清单、DoD） |

## 3. 建议阅读顺序

1. 绿场规格 §0–§1（前提与四级）→ **05** 矩阵  
2. **01** 架构 → **02** 模型 → **03** 时序  
3. **04** API → **06** 前端 → **07** SDK  
4. **08** 安全 → **09** 运维 → **10** 验收  

## 4. 设计原则（全套文档共用）

1. **一套有效角色**：Binding ∪ 活跃组；OIDC 与 evaluate_access 同实现。  
2. **默认拒绝**：无授权拒绝；业务码无数据范围策略拒绝。  
3. **管理面 / 业务面分离**：`Permission.surface`；L1 不默认业务码。  
4. **L2 ⊄ L3 且 L3 ⊄ L2**；L1 ⊇ 管理面。  
5. **后端强校验，前端只裁剪**。  
6. **变更可回收、可废票**：unbind + `membership.auth_version`。  
7. **绿场优先正确性**：不背兼容包袱。

## 5. 术语

| 术语 | 含义 |
|------|------|
| 有效角色 | 某 membership 在给定租户/应用上下文下可用的 Role 集合 |
| 管理面码 | `surface=management` 的 `iam.*` |
| 业务码 | `surface=business`，默认 `requires_data_scope=true` |
| 平台租户 | 种子系统租户，承载 `kind=platform` 角色 |
| 破窗 | `ALLOW_BOOTSTRAP_EMAIL_BYPASS`，默认 false |
| capabilities | 前端/集成方一次拉取的「当前主体允许的管理码集合」 |

## 6. 与代码库路径对照（实施时）

根目录：`D:\project\role`（或仓库根）  
后端：`backend/app/**` · 前端：`frontend/src/**` · SDK：`sdk/**`  
详见绿场规格 §5。

## 7. 完成定义（总）

见 [10-test-acceptance.md](./10-test-acceptance.md) 与绿场规格 DoD：四级用例全绿、bypass=false、无邮箱-only 超管主路径、L2/L3 互斥自动化。

> **门禁演进：** 管理台主路径已切到「后端按角色 / 前端按码」，见 [../plan-frontend-codes-backend-roles.md](../plan-frontend-codes-backend-roles.md)。码级 `ensure_management_permission` 为过渡映射。

## 8. 实施状态（门禁演进 · 2026-10-24 17:21 Asia/Shanghai）

| 项 | 状态 | 说明 |
|----|------|------|
| 前端码 / 后端角色 | **已完成** | `/auth/me` 返回 roles+capabilities；管理 API `ensure_roles`；SDK `require_roles`/`requireRoles` |
| 码级 `ensure_management_permission` | **deprecated** | 过渡映射保留；新代码走角色门禁 |
| DeerFlow Central IAM | **已完成（本机）** | `require_app_roles`；provider=`central-iam`；文档 `docs/IAM_SDK2_LOCAL.md` |
| model_usage 网关 | **已完成冒烟** | `.env` 已配 `IAM_MODEL_USAGE_API_KEY`；quota 强制仍为 false（无第三方计费真密钥） |
| 浏览器完整 UI 四级走查 | **本执行器不可做** | 以 P341 既有证据 + 本轮 API 登录/me/check；人工：localhost:5175 / :3000 选 Central IAM |

详见 [plan-frontend-codes-backend-roles.md](../plan-frontend-codes-backend-roles.md)。
