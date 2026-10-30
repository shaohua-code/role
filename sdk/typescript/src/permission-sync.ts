/**
 * Idempotent permission-catalog sync for application permission manifests.
 *
 * 管理面组件——调用方必须持有平台管理 access JWT（HS256 management token）；
 * 终端用户 OIDC access token 会被 IAM 以 403 拒绝。工具只登记缺失的权限码，
 * 不修改已存在条目（状态变更走管理台 PATCH /admin/permissions/{id}/status）。
 */

export class IamAdminError extends Error {
  readonly statusCode: number

  constructor(statusCode: number, message: string) {
    super(message)
    this.statusCode = statusCode
    this.name = 'IamAdminError'
  }
}

/** 清单条目；字段约束与后端 PermissionCreate 对齐（code 3–180 / resourceType 1–100 / scope 1–80 / description ≤500）。 */
export interface PermissionManifestEntry {
  code: string
  resource_type: string
  scope: string
  description?: string
  /** 可选；缺省时从 code 首段推导，须与 IAM catalog_namespace 规则一致 */
  catalog_namespace?: string
}

function deriveCatalogNamespace(code: string): string {
  const cleaned = code.trim()
  if (cleaned.startsWith('iam.')) return 'platform'
  const dot = cleaned.indexOf('.')
  if (dot < 1) throw new Error(`permission code must contain a namespace segment: ${code}`)
  return cleaned.slice(0, dot).toLowerCase()
}

/** 一次同步的结果分类；failed 非空时调用方应人工核对后重跑（幂等安全）。 */
export interface PermissionSyncReport {
  created: string[]
  skipped: string[]
  failed: Array<{ code: string; reason: string }>
}

export interface IamAdminClientOptions {
  /** Optional request timeout in milliseconds; default 3000. */
  timeoutMs?: number
  /** Dependency seam for deterministic tests; production should use global fetch. */
  fetcher?: typeof fetch
  /**
   * Application UUID. When set, sync uses
   * /api/v1/{apiSurface}/applications/{id}/permissions (L2).
   * When omitted, uses /api/v1/{apiSurface}/permissions (L1 catalog).
   */
  applicationId?: string
  /** 'admin' (default) or 'tenant-admin' */
  apiSurface?: 'admin' | 'tenant-admin'
}

/** IAM 管理面最小客户端；仅覆盖权限目录 list/create 两个端点。 */
export class IamAdminClient {
  private readonly permissionsEndpoint: string
  private readonly timeoutMs: number
  private readonly fetcher: typeof fetch

  constructor(apiBaseUrl: string, options: IamAdminClientOptions = {}) {
    if (options.timeoutMs !== undefined
        && (!Number.isInteger(options.timeoutMs) || options.timeoutMs < 1 || options.timeoutMs > 2_147_483_647)) {
      throw new RangeError('IAM admin timeout must be a positive 32-bit millisecond value')
    }
    const base = apiBaseUrl.replace(/\/+$/, '')
    const surface = options.apiSurface ?? 'admin'
    if (surface !== 'admin' && surface !== 'tenant-admin') {
      throw new RangeError("apiSurface must be 'admin' or 'tenant-admin'")
    }
    const applicationId = options.applicationId?.trim()
    this.permissionsEndpoint = applicationId
      ? `${base}/api/v1/${surface}/applications/${applicationId}/permissions`
      : `${base}/api/v1/${surface}/permissions`
    this.timeoutMs = options.timeoutMs ?? 3_000
    this.fetcher = options.fetcher ?? fetch
  }

  /** 返回权限目录条目列表；响应不是数组或缺 code 即契约错误（502）。 */
  async listPermissions(managementToken: string): Promise<Array<Record<string, unknown>>> {
    const body = await this.request('GET', managementToken)
    // G29：平台目录改为 {items,total,limit,offset}；应用侧与旧裸数组仍兼容。
    const items = Array.isArray(body)
      ? body
      : (body && typeof body === 'object' && Array.isArray((body as { items?: unknown }).items)
        ? (body as { items: unknown[] }).items
        : null)
    if (!Array.isArray(items) || items.some((item) => {
      const record = item as Record<string, unknown> | null
      return !record || typeof record !== 'object'
        || typeof record.code !== 'string' || record.code.length === 0
    })) {
      throw new IamAdminError(502, 'IAM returned an invalid permission catalog response')
    }
    return items as Array<Record<string, unknown>>
  }

  /** 创建一条权限码；201 返回目录条目，409/422 等按 IamAdminError 抛出。 */
  async createPermission(managementToken: string, entry: PermissionManifestEntry): Promise<Record<string, unknown>> {
    const catalogNamespace = entry.catalog_namespace?.trim().toLowerCase()
      ?? deriveCatalogNamespace(entry.code)
    const payload: Record<string, unknown> = {
      code: entry.code,
      catalog_namespace: catalogNamespace,
      resource_type: entry.resource_type,
      scope: entry.scope,
      surface: 'business',
      requires_data_scope: true,
      ...(entry.description !== undefined ? { description: entry.description } : {}),
    }
    return this.request('POST', managementToken, payload) as Promise<Record<string, unknown>>
  }

  /** 统一传输层：HS256 管理 JWT 走 Bearer 头；错误语义与授权 client 一致。 */
  private async request(method: 'GET' | 'POST', managementToken: string, payload?: Record<string, unknown>): Promise<unknown> {
    if (!managementToken) throw new Error('A management access token is required (L1 catalog or L2 app admin)')
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs)
    try {
      const response = await this.fetcher(this.permissionsEndpoint, {
        method,
        headers: { Authorization: `Bearer ${managementToken}`, 'Content-Type': 'application/json' },
        signal: controller.signal,
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      })
      if (!response.ok) {
        // 保留 IAM 状态码（409 冲突/422 校验/401 未认证/403 非平台管理员），供同步循环按码分类处理。
        throw new IamAdminError(response.status, 'IAM rejected the management request')
      }
      try {
        return await response.json()
      } catch {
        if (controller.signal.aborted) {
          throw new IamAdminError(503, 'IAM management API timed out')
        }
        throw new IamAdminError(502, 'IAM returned invalid JSON')
      }
    } catch (error) {
      if (error instanceof IamAdminError) throw error
      if (controller.signal.aborted) {
        throw new IamAdminError(503, 'IAM management API timed out')
      }
      throw new IamAdminError(503, 'IAM management API is unavailable')
    } finally {
      clearTimeout(timeout)
    }
  }
}

export interface PermissionSyncOptions {
  client: IamAdminClient
  managementToken: string
}

/**
 * 把权限清单幂等同步到目录：缺失的创建、已存在的跳过、失败逐条入报告。
 * 清单在发起任何网络请求前本地预检（字段/长度/重复码），非法即 Error，绝不猜测。
 */
export async function syncPermissionManifest(
  manifest: PermissionManifestEntry[],
  options: PermissionSyncOptions,
): Promise<PermissionSyncReport> {
  const entries = validateManifest(manifest)
  // 先建目录索引；这一步失败意味着无法判断哪些码已存在，直接抛错而不是盲发创建。
  const existing = new Set((await options.client.listPermissions(options.managementToken))
    .map((item) => item.code as string))
  const report: PermissionSyncReport = { created: [], skipped: [], failed: [] }
  for (const entry of entries) {
    if (existing.has(entry.code)) {
      report.skipped.push(entry.code)
      continue
    }
    try {
      await options.client.createPermission(options.managementToken, entry)
      report.created.push(entry.code)
    } catch (error) {
      const adminError = error as IamAdminError
      if (adminError.name === 'IamAdminError' && adminError.statusCode === 409) {
        // 并发窗口：索引建立后他人可能已登记同码；重拉目录确认，
        // 无法确认（网络故障/响应异常）时保守记为 failed 待人工核对。
        try {
          const current = new Set((await options.client.listPermissions(options.managementToken))
            .map((item) => item.code as string))
          if (current.has(entry.code)) {
            report.skipped.push(entry.code)
          } else {
            report.failed.push({ code: entry.code, reason: 'conflict but code missing from catalog' })
          }
        } catch {
          report.failed.push({ code: entry.code, reason: 'conflict but catalog recheck failed' })
        }
      } else if (adminError.name === 'IamAdminError') {
        report.failed.push({ code: entry.code, reason: `iam error ${adminError.statusCode}` })
      } else {
        throw error
      }
    }
  }
  return report
}

/** 清单本地预检：任何网络请求前拦截非法输入（fail closed，不猜测字段）。 */
function validateManifest(manifest: PermissionManifestEntry[]): PermissionManifestEntry[] {
  if (!Array.isArray(manifest) || manifest.length === 0) {
    throw new Error('manifest must be a non-empty array')
  }
  const seen = new Set<string>()
  const entries: PermissionManifestEntry[] = []
  for (const item of manifest) {
    if (!item || typeof item !== 'object') {
      throw new Error('each manifest entry must be an object')
    }
    const { code, resource_type: resourceType, scope, description, catalog_namespace: catalogNamespace } = item
    // 长度约束与后端 PermissionCreate 完全对齐，提前拦截无谓的 422。
    if (typeof code !== 'string' || code.length < 3 || code.length > 180) {
      throw new Error(`permission code must be a 3-180 char string: ${String(code)}`)
    }
    if (typeof resourceType !== 'string' || resourceType.length < 1 || resourceType.length > 100) {
      throw new Error(`resource_type must be a 1-100 char string for ${code}`)
    }
    if (typeof scope !== 'string' || scope.length < 1 || scope.length > 80) {
      throw new Error(`scope must be a 1-80 char string for ${code}`)
    }
    if (description !== undefined && (typeof description !== 'string' || description.length > 500)) {
      throw new Error(`description must be a string of at most 500 chars for ${code}`)
    }
    const derivedNamespace = deriveCatalogNamespace(code)
    if (catalogNamespace !== undefined) {
      if (typeof catalogNamespace !== 'string' || catalogNamespace.length < 1 || catalogNamespace.length > 100) {
        throw new Error(`catalog_namespace must be a 1-100 char string for ${code}`)
      }
      if (catalogNamespace.trim().toLowerCase() !== derivedNamespace) {
        throw new Error(`catalog_namespace must match code prefix for ${code}`)
      }
    }
    if (seen.has(code)) {
      // 同一码出现两次属清单自相矛盾；不允许静默去重掩盖清单错误。
      throw new Error(`duplicate permission code in manifest: ${code}`)
    }
    seen.add(code)
    entries.push({
      code,
      resource_type: resourceType,
      scope,
      catalog_namespace: catalogNamespace?.trim().toLowerCase() ?? derivedNamespace,
      ...(description !== undefined ? { description } : {}),
    })
  }
  return entries
}
