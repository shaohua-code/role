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
  platform_codes: string[]
  tenants: CapabilityTenant[]
  /** 有效角色摘要；仅展示/调试，裁 UI 仍用 codes。 */
  roles?: ActorRole[]
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
