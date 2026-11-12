// 绿场 RBAC：管理台能力来自 GET /auth/me 或 /auth/me/capabilities（角色派生的 codes）。
// consoleMode、菜单裁剪与按钮显隐基于 codes；roles 可选展示。后端安全边界是角色。

import { api } from '.'

export interface CapabilityApplication {
  application_id: string
  codes: string[]
}

export interface CapabilityTenant {
  tenant_id: string
  codes: string[]
  applications: CapabilityApplication[]
}

export interface ActorRole {
  key: string
  kind: string
  name?: string | null
  tenant_id: string
  application_id?: string | null
}

export interface Capabilities {
  platform_admin: boolean
  /** 只含菜单/按钮节点码（menu.* / button.*）；27 个接口码已从契约删除。 */
  platform_codes: string[]
  /** 操作者授权范围：超管 > 租户级 > 应用级 > 成员（取最高秩有效角色）。 */
  scope?: OperatorScope
  tenants: CapabilityTenant[]
  /** 有效角色摘要；仅展示/调试，裁 UI 仍用 codes。 */
  roles?: ActorRole[]
}

/** 操作者授权范围四档；rank 数值越大权限越大。 */
export type OperatorScope = 'super' | 'tenant' | 'app' | 'member'

/** 授权范围秩表：范围比较一律用秩，与后端 ROLE_SCOPE_RANK 同源。 */
export const OPERATOR_SCOPE_RANK: Record<OperatorScope, number> = {
  member: 0,
  app: 1,
  tenant: 2,
  super: 3,
}

/** 操作者授权范围中文标签。 */
export const OPERATOR_SCOPE_LABELS: Record<OperatorScope, string> = {
  super: '超管',
  tenant: '租户级',
  app: '应用级',
  member: '成员',
}

export type ConsoleMode = 'platform' | 'tenant' | 'no_access'

let cached: Capabilities | null = null

export function setCachedCapabilities(value: Capabilities | null): void {
  cached = value
}

export function getCachedCapabilities(): Capabilities | null {
  return cached
}

export function clearCapabilities(): void {
  cached = null
}

/** 拉取并缓存管理能力；登出 / 401 后须 clearCapabilities。 */
export async function loadCapabilities(): Promise<Capabilities> {
  const result = await api<Capabilities>('/auth/me/capabilities')
  cached = result
  return result
}

/** 当前操作者授权范围（读缓存 capabilities.scope）；无缓存/缺字段按 member 兜底。 */
export function operatorScope(): OperatorScope {
  return cached?.scope ?? 'member'
}

/** any-of：持有 codes 中任一码即可见/可点。 */
export function hasAnyCode(held: ReadonlySet<string>, codes: readonly string[]): boolean {
  return codes.some(code => held.has(code))
}

export function hasCode(held: ReadonlySet<string>, code: string): boolean {
  return held.has(code)
}

/** 汇总某租户（含其应用）持有的全部管理码。 */
export function tenantCodes(capabilities: Capabilities, tenantId: string): Set<string> {
  const held = new Set<string>(capabilities.platform_codes)
  const tenant = capabilities.tenants.find(item => item.tenant_id === tenantId)
  if (!tenant) return held
  for (const code of tenant.codes) held.add(code)
  for (const application of tenant.applications) {
    for (const code of application.codes) held.add(code)
  }
  return held
}

/** 全局（跨租户并集）持有的管理码，用于菜单裁剪与按钮判权。 */
export function allCodes(capabilities: Capabilities): Set<string> {
  const held = new Set<string>(capabilities.platform_codes)
  for (const tenant of capabilities.tenants) {
    for (const code of tenant.codes) held.add(code)
    for (const application of tenant.applications) {
      for (const code of application.codes) held.add(code)
    }
  }
  return held
}

/**
 * 规格 §4.4 / 06-frontend：
 * - 持有平台码（或 platform_admin）→ platform
 * - 否则持有任一租户/应用管理码 → tenant
 * - 否则 → no_access（L4）
 */
export function deriveConsoleMode(capabilities: Capabilities): ConsoleMode {
  if (capabilities.platform_admin || capabilities.platform_codes.length > 0) {
    return 'platform'
  }
  const hasTenantManagement = capabilities.tenants.some(tenant => {
    if (tenant.codes.length > 0) return true
    return tenant.applications.some(application => application.codes.length > 0)
  })
  return hasTenantManagement ? 'tenant' : 'no_access'
}

/** 当前缓存上的便捷 hasAny（无缓存则 false）。 */
export function cachedHasAny(codes: readonly string[]): boolean {
  if (!cached) return false
  return hasAnyCode(allCodes(cached), codes)
}

export function cachedHas(code: string): boolean {
  return cachedHasAny([code])
}

/**
 * 统一判权口径（F7）：菜单/按钮显隐只走这一处，替代散落的
 * `platform_admin && hasAny(...)` / `platform_admin || hasAny(...)` 双轨写法。
 * 基于「当前缓存能力」做同步判断（与原用法一致，无缓存一律 false）：
 * L1（platform_admin）直接放行；其余角色 any-of 命中对应码域（menu.* / button.*）。
 */
function hasKindCode(kind: 'menu' | 'button', code: string): boolean {
  const capabilities = cached
  if (!capabilities) return false
  // L1 平台管理员放行全部菜单与按钮
  if (capabilities.platform_admin) return true
  // 仅接受本码域的码，域外码视为未持有，避免跨域误判
  if (!code.startsWith(`${kind}.`)) return false
  return hasAnyCode(allCodes(capabilities), [code])
}

/** 菜单可见判权：L1 放行，否则需持有该 menu.* 码。 */
export function hasMenu(code: string): boolean {
  return hasKindCode('menu', code)
}

/** 按钮显隐判权：L1 放行，否则需持有该 button.* 码。 */
export function hasButton(code: string): boolean {
  return hasKindCode('button', code)
}

/**
 * 租户台端点通用前缀：组织/成员/用户组/应用列表等域同时挂 /admin 与
 * /tenant-admin，租户控制台（L3/L2 视角）统一走本前缀按角色门禁判权；
 * 散落字面量统一收敛至此，后端挂载调整只需改这一处。
 */
export const TENANT_ADMIN_API_PREFIX = '/tenant-admin'

/**
 * 平台管理端点通用前缀：审计 / 鉴权模拟 / 模型治理 / 登录主题等仅在 /admin
 * 挂载的域，租户模式（L2/L3 同样持对应菜单码）也走该前缀由后端按码判权；
 * 散落字面量统一收敛至此，后端挂载调整只需改这一处。
 */
export const ADMIN_API_PREFIX = '/admin'

/**
 * 应用角色 / 成员域端点前缀：后端 application_roles 路由仅挂在 /tenant-admin，
 * 平台（L1）与租户（L2/L3）管理员都经该挂载点按角色门禁判权，故不以
 * consoleMode 切换为 /admin（切了会 404），只把散落字面量收敛为单一常量；
 * 后端未来若双挂 /admin，只需改这一处。
 */
export const APPLICATION_ROLE_API_PREFIX = TENANT_ADMIN_API_PREFIX
