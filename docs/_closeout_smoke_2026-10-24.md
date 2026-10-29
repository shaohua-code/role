# P342 Closeout smoke (2026-10-24 17:24 Asia/Shanghai)

- OK | L1 login
- OK | /auth/me roles=['platform.super_admin']
- OK | /auth/me/capabilities platform_codes_n=27
- OK | authz check iam.member.read allowed=True
- OK | model_usage reserve+settle
- OK | DF central-iam provider
- OK | GET /admin/tenants 200（修复 L1_ROLE_KEY 漏导后）
- 不可做 | 本机浏览器 OIDC UI；第三方模型真密钥；quota 强制保持 false

## 多角色（2026-10-24）
- 库表 `role_bindings` 本就多对多；管理台「用户管理 → 配置角色」改为多选并整表替换直接绑定。
- `GET/PUT /api/v1/admin/users/{id}/role-bindings`；`/auth/me.roles` 为数组，capabilities 为各角色权限码并集。
