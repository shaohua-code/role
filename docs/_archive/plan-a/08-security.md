# 08 — 安全设计

交叉引用：[03-authz-flow](./03-authz-flow.md) · [09-bootstrap-ops](./09-bootstrap-ops.md)

---

## 1. 威胁与对策摘要

| 威胁 | 对策 |
|------|------|
| 提权（伪造租户/应用） | OIDC 钉死上下文；管理 JWT live 查码 |
| 权限变更后旧 token 继续用 | auth_version / membership_version；入场有效角色 live |
| 组继承绕过入场 | 入场与 evaluate 同 effective_roles |
| 超管邮箱被盗 | 破窗默认关；L1 靠角色；改密升版本；会话可撤 |
| 客户端密钥泄露 | hash 存储；rotate；审计 |
| 水平越权看他租户 | tenant_id 校验 + 404 隐藏策略（沿用处） |
| 有权无行级过滤 | 业务码 requires_data_scope |
| 日志泄密 | access log redaction（现有能力保留） |

## 2. 会话与版本

| Token | 校验 |
|-------|------|
| Management access | HS256、iss、jti 吊销、sid→refresh_session、user.auth_version |
| OIDC access | RS256、token_use、aud=client_id、吊销、family sid、user+membership version、有效角色非空 |
| Refresh | 旋转/吊销；version 绑定 |

**Bump 事件：** 见绿场规格 §2.3（bind/unbind/组/角色停用/权限替换/数据范围/成员状态/改密）。

## 3. 破窗（Break-glass）

| 项 | 规格 |
|----|------|
| 配置 | `ALLOW_BOOTSTRAP_EMAIL_BYPASS` 默认 **false** |
| 行为 | true 且 email==BOOTSTRAP_ADMIN_EMAIL 且非 OIDC 协议用户 → 视作拥有全部 management 码 |
| 审计 | 每次经破窗放行的**写**操作 `details.break_glass=true` |
| 生产 | 禁止长期 true；仅空库急救 |
| OIDC | **永远**不走邮箱破窗（保持现设计意图） |

种子绑定 L1 后，正常路径不依赖破窗。

## 4. 审计

保留 `audit(actor, request, action, resource_type, resource_id, details)`。  

**必须审计：** 角色/权限/绑定/解绑/组/成员状态/数据范围/应用密钥轮换/破窗写操作/租户启停。  

查询：仅 `iam.audit.read`（L1）。  
绿场可空审计表起步，无历史迁移。

## 5. 密钥与密码

| 类型 | 要求 |
|------|------|
| 用户密码 | Argon2id；登录伪哈希防枚举 |
| JWT HS256 | secret ≥ 32 字节 |
| OIDC 签名 | RSA/EC 密钥文件权限受限；支持轮换流程（现 oidc_keys 可保留加强） |
| application secret | 仅创建/轮换时回显一次；库内 hash |
| SMTP/网关 key | env；不进仓库 |

## 6. CORS 与 Cookie

- CORS 白名单精确来源；credentials 与现一致。  
- Refresh HttpOnly、Secure、SameSite 按部署域配置。  
- access token 可 sessionStorage（现管理台）；防 XSS 依赖 CSP/前端卫生。

## 7. 管理面纵深

1. 网关 TLS  
2. current_user  
3. 权限码 guard  
4. 资源级 tenant/application 校验  
5. 审计  

前端隐藏按钮 ≠ 安全控制。

## 8. 安全验收清单

- [ ] bypass=false 时无 L1 绑定不能写 admin  
- [ ] 解绑后旧 OIDC access 401  
- [ ] 业务码无 scope 策略 check 失败  
- [ ] L2 不能读他应用 secret  
- [ ] 审计含 unbind 与 break_glass  
- [ ] 密钥不出现在 access 日志  
