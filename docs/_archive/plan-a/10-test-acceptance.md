# 10 — 测试与验收用例

交叉引用：[05-role-matrix](./05-role-matrix.md) · [08-security](./08-security.md) · 绿场规格 §6

---

## 1. 测试策略

| 层 | 内容 | 工具建议 |
|----|------|----------|
| 单元 | effective_roles、data_scope 解析、破窗开关 | pytest |
| API | 四级矩阵、解绑 bump、OIDC 入场含组 | pytest + httpx AsyncClient |
| SDK | 强制 scope、owner_only、错误映射 | sdk 内 pytest / vitest |
| 前端 | capabilities 裁剪、beforeEach | vitest + 少量 e2e |
| 验收 | §3 手工/自动化清单 | reset 后脚本 |

绿场：**不**保留依赖旧迁移数据的测试夹具；用 seed fixture 建 L1–L4。

## 2. Fixture 建议

```text
seed_min:
  platform tenant + L1 user
  tenant T1 + org_admin U3
  app A1 + app.admin U2 + app.member U4
  group G 含 U4 仅组继承角色（无直连 binding）测 OIDC
```

## 3. 验收用例表（DoD）

### 3.1 重建与种子

| ID | 步骤 | 期望 |
|----|------|------|
| A-01 | greenfield-reset --i-understand | upgrade+seed 成功 |
| A-02 | bypass=false，删除 L1 绑定后同邮箱登录调 tenants POST | 403 |
| A-03 | seed 幂等跑两次 | 无重复权限码/绑定错误 |

### 3.2 有效角色与 OIDC

| ID | 步骤 | 期望 |
|----|------|------|
| B-01 | U4 仅组继承 app.member 走 OIDC | 拿到 token |
| B-02 | 去掉组角色后再 token/refresh | 401 |
| B-03 | evaluate_access 与入场对同一用户结论一致 | 一致 |

### 3.3 L1

| ID | 步骤 | 期望 |
|----|------|------|
| C-01 | 全管理码操作抽样 | 200 |
| C-02 | 无业务角色 check demo.document.read | allowed=false |
| C-03 | DELETE role-bindings | 204 + version+1 + 审计 |

### 3.4 L2

| ID | 步骤 | 期望 |
|----|------|------|
| D-01 | U2 管 A1 | 200 |
| D-02 | U2 管 A2 / 组织 manage / tenant manage | 403 |
| D-03 | 前端菜单无租户开通 | 通过 |

### 3.5 L3

| ID | 步骤 | 期望 |
|----|------|------|
| E-01 | 组织/成员/组/data-scopes | 200 |
| E-02 | assign U→app.admin@A1 | 200 |
| E-03 | rotate-secret、permission.manage | 403 |
| E-04 | assign 前 check application.manage@A1 | false |

### 3.6 L4 与数据范围

| ID | 步骤 | 期望 |
|----|------|------|
| F-01 | 有业务码+self | allowed + data_scope |
| F-02 | 有业务码无策略 | false / data_scope_policy_missing |
| F-03 | 管理台 | no_access + API 403 |

### 3.7 安全

| ID | 步骤 | 期望 |
|----|------|------|
| S-01 | OIDC body 伪造成其他 tenant_id | 仍按 token 钉死 / 拒绝 |
| S-02 | bypass true 写操作 | 审计 break_glass |
| S-03 | 日志无 secret/password | 抽样通过 |

## 4. 自动化门禁（CI 建议）

```text
pytest backend/tests -q
pytest sdk/python -q
pnpm -C frontend test / vue-tsc -b
（可选）playwright: login L1/L3/L2 菜单可见性
```

合并条件：矩阵测试文件覆盖 C/D/E/F 主路径；B-01 组继承必过。

## 5. 签字

| 角色 | 签字项 |
|------|--------|
| 后端 | API+OIDC+seed |
| 前端 | 守卫+菜单 |
| 安全/负责人 | bypass 默认 false、破窗流程 |
| 业务对接 | SDK 2.x 样例跑通 |

**全部 §3 用例通过 ⇒ 绿场方案 A 可宣布落地完成。**
