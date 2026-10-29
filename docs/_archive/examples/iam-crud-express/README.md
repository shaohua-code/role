# IAM CRUD 示例骨架（Express / TypeScript）

> **状态**：SDK 插件齐（`@iam-platform/authorization-client` 2.x），**完整可运行 CRUD 示例目前仅** [`../iam-crud-fastapi/`](../iam-crud-fastapi/)。本目录为最小接入骨架与对照表，便于 Node 项目按同构 API 落地。

## 包名

```text
@iam-platform/authorization-client   # 仓库路径 sdk/typescript，version 2.0.0
```

勿使用已废弃名称 `iam-sdk`。

## 与 Python 示例对照

| Python | TypeScript |
| --- | --- |
| `mount_oidc_auth` | `mountOidcAuth` |
| `IAMFastAPI` / `require_permission` | `createIamExpress` / `requirePermission` |
| `check_batch` | `checkBatch` |
| `IamAdminClient(application_id=...)` L2 sync | `new IamAdminClient(base, { applicationId })` |
| RoleDataScope=`self` | 同：控制台或管理 API 为业务角色配置 |

## SDK 2.x 注意

- 业务 `check`/`require` 需要有效 `data_scope`；不要默认 `includeDataScope: false`。
- 缺 RoleDataScope → `data_scope_policy_missing` / SDK fail-closed。
- Issuer 与登录 Host 一致（本机 compose 多为 `http://localhost:8002`）。

## 建议落地步骤

1. 按 [`../iam-crud-fastapi/provision.py`](../iam-crud-fastapi/provision.py) 或控制台登记应用 + L2 权限 + RoleDataScope=self。
2. `pnpm add` 本地 `sdk/typescript`（或 workspace）。
3. 挂载 OIDC → `permissionMap` → `requirePermission(..., { ownerOnly: true })`。
4. 联调路径对齐 FastAPI 的 `verify_flow.py` 断言清单。

完整契约真源：`docs/plan-a/07-sdk-integration.md`、`docs/后续项目对接手册.md`。
