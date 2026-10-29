// P392 权限编码重规划：唯一的「码 → 域」映射（五域：platform / rbac / org / app / ops）。
// 授权弹窗与权限目录页共用本模块；域与控制台菜单分组对齐，格式 <域>.<对象>.<动作> 三段式。
// 分组仅服务展示与收敛，不影响判权、可选性与保存校验。

export interface PermissionDomain {
  key: string
  label: string
  hint: string
}

/** 域定义：key 为稳定标识（筛选/折叠状态用），label 为展示名。 */
export const PERMISSION_DOMAINS: PermissionDomain[] = [
  { key: 'platform', label: '平台', hint: '总览 / 租户 / 账号（L1）' },
  { key: 'rbac', label: '角色与授权', hint: '角色目录 / 权限目录 / 应用角色任命' },
  { key: 'org', label: '组织与成员', hint: '组织 / 成员 / 用户组 / 邀请' },
  { key: 'app', label: '应用', hint: '应用配置与密钥' },
  { key: 'ops', label: '资源与运营', hint: '模型 / 主题 / 审计 / 授权模拟' },
  { key: 'other', label: '其他', hint: '未归类管理面码' },
  { key: 'business', label: '业务码', hint: '应用命名空间业务码，强制数据范围' },
]

const DOMAIN_BY_KEY = new Map(PERMISSION_DOMAINS.map(domain => [domain.key, domain]))

/** 管理面五域前缀（业务码与「其他」不属于五域）。 */
export const MANAGEMENT_DOMAIN_PREFIXES = ['platform.', 'rbac.', 'org.', 'app.', 'ops.'] as const

/** 管理面码判定：五域前缀任一命中即管理码（替代旧 iam. 前缀判断）。 */
export function isManagementCode(code: string): boolean {
  return MANAGEMENT_DOMAIN_PREFIXES.some(prefix => code.startsWith(prefix))
}

/** 解析权限编码所属域：五域前缀直接映射；管理面孤儿码归「其他」；业务码归「业务码」。 */
export function resolvePermissionDomain(code: string): PermissionDomain {
  if (code.startsWith('platform.')) return DOMAIN_BY_KEY.get('platform')!
  if (code.startsWith('rbac.')) return DOMAIN_BY_KEY.get('rbac')!
  if (code.startsWith('org.')) return DOMAIN_BY_KEY.get('org')!
  if (code.startsWith('app.')) return DOMAIN_BY_KEY.get('app')!
  if (code.startsWith('ops.')) return DOMAIN_BY_KEY.get('ops')!
  if (isManagementCode(code)) return DOMAIN_BY_KEY.get('other')!
  return DOMAIN_BY_KEY.get('business')!
}

/** 业务码二级分组键：命名空间即编码首段（如 demoapp.item.read → demoapp）。 */
export function permissionNamespace(code: string): string {
  return code.split('.')[0] || code
}

// ===== P393 作用域一级分组（PRD docs/prototypes/permission-scope-grouping）：=====
// 一级分类从功能域改为「平台 → 租户 → 应用 → 业务码」；归属规则由 P383 模板码集确定性推导：
// 仅 L1 模板持有 → 平台；L3 持有且 L2 不持有 → 租户；L2 模板持有（L3 全量兼容）→ 应用；
// catalog_namespace 非 platform 的码 → 业务码。目录页与授权弹窗共用本口径（FR-03 单一来源）。

export interface PermissionScope {
  key: 'platform' | 'tenant' | 'app' | 'business'
  label: string
  hint: string
}

/** 作用域组定义：组序即展示序（平台 → 租户 → 应用 → 业务码）。 */
export const PERMISSION_SCOPES: PermissionScope[] = [
  { key: 'platform', label: '平台', hint: '租户与全局账号治理 / 平台总览 / 平台角色写 / 权限目录写（仅 L1）' },
  { key: 'tenant', label: '租户', hint: '组织架构 / 角色目录读 / 任命应用管理员 / 模型目录写（L3）' },
  { key: 'app', label: '应用', hint: '应用与成员日常管理（L2 起，租户管理员全量兼容）' },
  { key: 'business', label: '业务码', hint: '应用命名空间业务码，强制数据范围' },
]

const SCOPE_BY_KEY = new Map(PERMISSION_SCOPES.map(scope => [scope.key, scope]))

/** 平台组 7 码：仅 L1（platform.admin）模板持有（含权限目录写）。 */
const PLATFORM_SCOPE_CODES = new Set([
  'platform.overview.read', 'platform.tenant.read', 'platform.tenant.manage',
  'platform.account.read', 'platform.account.manage', 'rbac.role.manage', 'rbac.permission.manage',
])

/** 租户组 5 码：L3（tenant.admin）持有且 L2（app.admin）不持有。 */
const TENANT_SCOPE_CODES = new Set([
  'org.read', 'org.manage', 'rbac.role.read', 'rbac.app_role.assign', 'ops.model.manage',
])

/** 解析权限编码所属作用域组：平台/租户按静态归属表，其余管理码归应用，业务命名空间归业务码。 */
export function resolvePermissionScope(code: string): PermissionScope {
  if (!isManagementCode(code)) return SCOPE_BY_KEY.get('business')!
  if (PLATFORM_SCOPE_CODES.has(code)) return SCOPE_BY_KEY.get('platform')!
  if (TENANT_SCOPE_CODES.has(code)) return SCOPE_BY_KEY.get('tenant')!
  return SCOPE_BY_KEY.get('app')!
}

// ===== P395 两类分组（PRD docs/prototypes/permission-hierarchy-view）：=====
// 分类只有两种——「平台编码」（27 个管理面码，平台统一管理）与「应用业务编码」（应用命名空间业务码）。
// 「平台 ⊃ 租户 ⊃ 应用」的层级关系不靠分组表达：它由模板码集天然承载（L1 持 27 ⊃ L3 持 20 ⊃ L2 持 15），
// 在行级以「层级起点」标记呈现（复用 resolvePermissionScope 的互斥归属）。

export type PermissionClass = 'platform-class' | 'business'

/** 两类分组定义（目录页卡带与授权弹窗导航共用，组序即展示序）。 */
export const PERMISSION_CLASSES: { key: PermissionClass; label: string; hint: string }[] = [
  { key: 'platform-class', label: '平台编码', hint: '平台统一管理的管理面码，四级管理员分层持有' },
  { key: 'business', label: '应用业务编码', hint: '租户下各应用命名空间的业务码，强制数据范围' },
]

/** 解析权限编码所属类：五域管理面码 → 平台编码；其余 → 应用业务编码。 */
export function resolvePermissionClass(code: string): PermissionClass {
  return isManagementCode(code) ? 'platform-class' : 'business'
}

/** 层级起点标记（行级展示用）：作用域组 → 白话标签（P396：让非 RBAC 背景用户直接读懂）。 */
export const SCOPE_LEVEL_LABELS: Record<string, string> = {
  platform: '仅平台超管',
  tenant: '租户管理员起',
  app: '应用管理员起',
}

/** 层级起点 hover 解释：说明该码的持有边界。 */
export const SCOPE_LEVEL_TIPS: Record<string, string> = {
  platform: '仅平台超级管理员（L1）持有；租户、应用管理员不可见',
  tenant: '租户管理员（L3）开始持有；应用管理员（L2）不可见',
  app: '应用管理员（L2）即可持有；租户管理员（L3）全量兼容',
}

/** 平台编码组内的层级起点排序（L1 专属 → L3 起 → L2 起，与 PERMISSION_SCOPES 组序一致）。 */
export const SCOPE_LEVEL_ORDER: Record<string, number> = { platform: 0, tenant: 1, app: 2, business: 3 }
