// 审计事件中文标签（与后端各路由 audit()/record_event() 的 action/target_type 全集同源维护）。
// 兜底原则：未知编码原样返回——审计是只读安全数据，不允许因映射缺失而丢失原始标识。
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  // 登录与认证（auth.*）
  'auth.login': '登录',
  'auth.logout': '登出',
  'auth.refresh': '令牌刷新',
  'auth.profile.update': '个人资料更新',
  'auth.password.change': '自助修改密码',
  'auth.password.reset': '管理员重置密码',
  'auth.password_reset.request': '发起密码重置',
  'auth.password_reset.complete': '完成密码重置',
  'auth.password_reset.delivery_failed': '重置邮件发送失败',
  // OIDC
  'oidc.authorize': 'OIDC 授权请求',
  'oidc.token.exchange': '授权码换令牌',
  'oidc.token.password': '密码直登签发令牌',
  'oidc.token.refresh': '刷新令牌',
  // 租户
  'tenant.create': '创建租户',
  'tenant.kind.change': '租户类型变更',
  'tenant.status.change': '租户启停',
  'tenant.delete': '删除租户',
  // 应用
  'application.create': '创建应用',
  'application.update': '更新应用',
  'application.trust.change': '应用受信变更',
  'application.secret.rotate': '轮换应用密钥',
  'application.status.change': '应用启停',
  'application.delete': '删除应用',
  'application.role.create': '创建应用角色',
  'application.role.update': '更新应用角色',
  'application.role.status.change': '应用角色启停',
  'application.role.permissions.replace': '替换应用角色权限',
  'application.role.bind': '绑定应用角色成员',
  'application.role.unbind': '解绑应用角色成员',
  'application_resource.create': '创建资源节点',
  'application_resource.update': '更新资源节点',
  'application_resource.delete': '删除资源节点',
  'application_resource.assign': '分配角色资源授权',
  // 角色与权限
  'role.create': '创建角色',
  'role.clone': '克隆角色',
  'role.update': '更新角色',
  'role.status.change': '角色启停',
  'role.delete': '删除角色',
  'role.bind': '绑定角色',
  'role.unbind': '解绑角色',
  'role.bindings.replace': '整体替换角色绑定',
  'role.permissions.replace': '替换角色权限',
  'role.permission.grant': '授予资源权限',
  'role.permission.revoke': '撤销资源权限',
  'role.data_scopes.replace': '替换数据范围',
  'permission.create': '创建权限',
  'permission.status.change': '权限启停',
  // 用户 / 邀请 / 成员
  'user.create': '创建用户',
  'user.status.change': '用户状态变更',
  'user.password.reset': '重置用户密码',
  'user.session.revoke': '撤销用户会话',
  'user.invitation.create': '发出成员邀请',
  'user.invitation.resend': '重发成员邀请',
  'user.invitation.revoke': '撤销成员邀请',
  'membership.create': '加入租户',
  'membership.status.change': '成员状态变更',
  'membership.organizations.replace': '替换成员组织归属',
  // 组织 / 用户组
  'organization.create': '创建组织',
  'organization.update': '更新组织',
  'organization.owner.change': '组织负责人变更',
  'organization.delete': '删除组织',
  'user_group.create': '创建用户组',
  'user_group.update': '更新用户组',
  'user_group.status.change': '用户组启停',
  'user_group.delete': '删除用户组',
  'user_group.members.replace': '替换用户组成员',
  'user_group.roles.replace': '替换用户组角色',
  // 模型（三级分发）
  'model.create': '创建平台模型',
  'model.update': '更新平台模型',
  'model.status.change': '模型启停',
  'model.delete': '删除平台模型',
  'model.distribute.tenant': '模型下发租户',
  'model.revoke.tenant': '回收模型租户下发',
  'model.distribute.application': '模型下发应用',
  'model.revoke.application': '回收模型应用下发',
  // 模型用量核对
  'model_usage.review.settle': '用量核对结算',
  'model_usage.review.release': '用量核对释放',
  // 登录主题
  'theme.save': '保存登录主题草稿',
  'theme.publish': '发布登录主题',
  'theme.restore': '恢复登录主题版本',
  'theme.asset.upload': '上传主题素材',
}

export const AUDIT_TARGET_TYPE_LABELS: Record<string, string> = {
  tenant: '租户',
  application: '应用',
  role: '角色',
  user: '用户',
  user_group: '用户组',
  organization: '组织',
  permission: '权限',
  model: '模型',
  auth_session: '认证会话',
  invitation: '邀请',
  theme: '登录主题',
  password_reset: '密码重置',
}

const AUDIT_OUTCOME_LABELS: Record<string, string> = {
  success: '成功',
  denied: '拒绝',
  accepted: '已受理',
}

// 渲染用：已知编码显示中文，未知编码原样回显（安全数据不允许丢标识）。
export function formatAuditAction(code: string | null | undefined): string {
  if (!code) return '—'
  return AUDIT_ACTION_LABELS[code] ?? code
}

export function formatAuditTargetType(code: string | null | undefined): string {
  if (!code) return '—'
  return AUDIT_TARGET_TYPE_LABELS[code] ?? code
}

export function formatAuditOutcome(code: string | null | undefined): string {
  if (!code) return '未知'
  return AUDIT_OUTCOME_LABELS[code] ?? code
}
