/** Minimal server-side IAM authorization client; it deliberately stores no token. */
export interface DataScopeConstraint {
  kind: 'tenant' | 'owner' | 'organizations'
  /** Required for every mode; business tables may contain the same global user in multiple tenants. */
  tenant_id: string
  field?: string
  user_id?: string
  organization_ids?: string[]
}

export interface AuthorizationDecision {
  allowed: boolean
  reason: string
  /** Present on allowed OIDC decisions; sourced from the signed token context. */
  application_id?: string
  data_scope?: { mode: 'any_of'; constraints: DataScopeConstraint[] }
}

export interface AuthorizationRequest {
  /** tenant_id must come from a locally verified identity token/session. */
  tenantId: string
  /** Required for data scopes; IAM OIDC sub from the verified server session, not the product's local user primary key. */
  userSubject?: string
  permissionCode: string
  resourceId?: string
  includeDataScope?: boolean
}

/** 应用侧固定列映射；这些标识符由业务代码提供，不能从 IAM 响应或 HTTP 参数取得。 */
export interface PostgresScopeColumns {
  tenantId: string
  ownerUserId?: string
  organizationId?: string
}

/** 为使用本地用户/组织主键的系统提供显式映射，避免把 IAM subject 错当成本地数据库主键。 */
export interface PostgresScopeOptions {
  tenantId: string
  userSubject: string
  columns: PostgresScopeColumns
  mapTenantId?: (iamTenantId: string) => string | number | Promise<string | number>
  mapOwnerUserId?: (iamSubject: string, tenantId: string) => string | number | Promise<string | number>
  mapOrganizationIds?: (iamOrganizationIds: string[], tenantId: string) => Array<string | number> | Promise<Array<string | number>>
}

/** 可直接传给 node-postgres 的参数化 WHERE 片段。 */
export interface PostgresScopeFilter {
  sql: string
  params: Array<string | number | Array<string | number>>
}

export class AuthorizationServiceError extends Error {
  readonly statusCode: number

  constructor(statusCode: number, message: string) {
    super(message)
    this.statusCode = statusCode
    this.name = 'AuthorizationServiceError'
  }
}

/**
 * Calls the IAM decision API with the end-user OIDC access token. Validate the OIDC
 * token locally through a maintained OIDC library before creating this request context;
 * never use an ID token or a browser supplied tenant ID as a trusted claim.
 */
export class IamAuthorizationClient {
  private readonly endpoint: string
  private readonly applicationId?: string
  private readonly timeoutMilliseconds: number

  /** timeoutMilliseconds 限制授权请求和响应体读取的总时长，默认 3000 毫秒。 */
  constructor(apiBaseUrl: string, applicationId?: string, timeoutMilliseconds = 3000) {
    if (!Number.isInteger(timeoutMilliseconds) || timeoutMilliseconds < 1 || timeoutMilliseconds > 2_147_483_647) {
      throw new RangeError('IAM authorization timeout must be a positive 32-bit millisecond value')
    }
    this.endpoint = `${apiBaseUrl.replace(/\/+$/, '')}/api/v1/authorization/check`
    this.applicationId = applicationId
    this.timeoutMilliseconds = timeoutMilliseconds
  }

  async check(accessToken: string, request: AuthorizationRequest): Promise<AuthorizationDecision> {
    if (!accessToken) throw new Error('An end-user OIDC access token is required')
    const verifiedUserSubject = request.userSubject
    if (request.includeDataScope === true && (!verifiedUserSubject || !verifiedUserSubject.trim())) {
      throw new Error('A locally verified IAM userSubject is required when requesting a data scope')
    }
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), this.timeoutMilliseconds)
    let decision: unknown
    try {
      const response = await fetch(this.endpoint, {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          tenant_id: request.tenantId,
          ...(this.applicationId ? { application_id: this.applicationId } : {}),
          permission_code: request.permissionCode,
          ...(request.resourceId ? { resource_id: request.resourceId } : {}),
          include_data_scope: request.includeDataScope ?? false,
        }),
      })
      if (!response.ok) throw new AuthorizationServiceError(response.status, 'IAM rejected the authorization request')
      try {
        // Fetch 可能先返回响应头再读取响应体；JSON 解析也必须受同一截止时间限制。
        decision = await response.json()
      } catch {
        if (controller.signal.aborted) {
          throw new AuthorizationServiceError(503, 'IAM authorization service timed out')
        }
        throw new AuthorizationServiceError(502, 'IAM returned invalid JSON')
      }
    } catch (error) {
      if (error instanceof AuthorizationServiceError) throw error
      if (controller.signal.aborted) {
        throw new AuthorizationServiceError(503, 'IAM authorization service timed out')
      }
      // A network outage is not an allow decision. Callers should fail closed.
      throw new AuthorizationServiceError(503, 'IAM authorization service is unavailable')
    } finally {
      clearTimeout(timeout)
    }
    if (!decision || typeof decision !== 'object' || Array.isArray(decision)) {
      throw new AuthorizationServiceError(502, 'IAM returned an invalid authorization decision')
    }
    const result = decision as Record<string, unknown>
    if (typeof result.allowed !== 'boolean' || typeof result.reason !== 'string') {
      throw new AuthorizationServiceError(502, 'IAM returned an invalid authorization decision')
    }
    let dataScope: AuthorizationDecision['data_scope'] = undefined
    if (result.data_scope !== undefined && result.data_scope !== null) {
      if (!result.allowed || request.includeDataScope !== true) {
        throw new AuthorizationServiceError(502, 'IAM returned an unexpected data scope')
      }
      dataScope = validateDataScope(result.data_scope, request.tenantId, verifiedUserSubject ?? '')
    } else if (result.allowed && request.includeDataScope === true) {
      throw new AuthorizationServiceError(502, 'IAM omitted the required data scope')
    }
    const applicationId = result.application_id
    if (applicationId !== undefined && (typeof applicationId !== 'string' || !applicationId.trim())) {
      throw new AuthorizationServiceError(502, 'IAM returned an invalid application context')
    }
    return {
      allowed: result.allowed,
      reason: result.reason,
      ...(applicationId ? { application_id: applicationId } : {}),
      ...(dataScope ? { data_scope: dataScope } : {}),
    }
  }

  async require(accessToken: string, request: AuthorizationRequest): Promise<AuthorizationDecision> {
    const decision = await this.check(accessToken, request)
    if (!decision.allowed) throw new AuthorizationServiceError(403, `Permission denied: ${decision.reason}`)
    return decision
  }
}

/**
 * 把已经过授权 SDK 校验的 any_of 策略编译为 PostgreSQL 谓词。
 * 每个 OR 分支都独立绑定 tenant，所有数据值都作为参数传递；业务列只接受开发者定义的映射。
 */
export async function compilePostgresDataScope(
  dataScope: NonNullable<AuthorizationDecision['data_scope']>,
  options: PostgresScopeOptions,
): Promise<PostgresScopeFilter> {
  const fail = (message: string): never => { throw new AuthorizationServiceError(502, message) }
  if (!options.tenantId?.trim() || !options.userSubject?.trim()
      || dataScope?.mode !== 'any_of' || !Array.isArray(dataScope.constraints) || dataScope.constraints.length === 0) {
    return fail('Cannot compile an empty or unverified IAM data scope')
  }

  // 列名只允许由业务开发者配置的简单标识符或限定标识符，避免把响应内容拼进 SQL。
  const quoteColumn = (value: string | undefined): string => {
    if (!value || !value.split('.').every((part) => /^[A-Za-z_][A-Za-z0-9_]*$/.test(part))) {
      return fail('IAM data-scope column mapping is missing or invalid')
    }
    return value.split('.').map((part) => `"${part}"`).join('.')
  }
  const toScalar = (value: unknown): string | number => {
    if (typeof value === 'string' && value.trim() && !value.includes('\0')) return value
    if (typeof value === 'number' && Number.isFinite(value)) return value
    return fail('IAM data-scope identity mapping returned an invalid key')
  }
  const invokeMapping = async <T>(resolve: () => T | Promise<T>): Promise<T> => {
    try {
      return await resolve()
    } catch {
      // 本地映射故障也必须终止查询，且不能把数据库异常原文带到业务响应。
      throw new AuthorizationServiceError(503, 'Business identity mapping service is unavailable')
    }
  }

  const tenantValue = toScalar(options.mapTenantId
    ? await invokeMapping(() => options.mapTenantId!(options.tenantId))
    : options.tenantId)
  const tenantColumn = quoteColumn(options.columns.tenantId)
  const params: PostgresScopeFilter['params'] = []
  const branches: string[] = []
  const bind = (value: string | number | Array<string | number>): string => {
    params.push(value)
    return `$${params.length}`
  }

  for (const constraint of dataScope.constraints) {
    if (!constraint || typeof constraint.tenant_id !== 'string'
        || constraint.tenant_id.toLowerCase() !== options.tenantId.toLowerCase()) {
      return fail('IAM data-scope branch does not match the verified tenant')
    }
    const tenantPredicate = `${tenantColumn} = ${bind(tenantValue)}`
    if (constraint.kind === 'tenant') {
      branches.push(`(${tenantPredicate})`)
      continue
    }
    if (constraint.kind === 'owner') {
      if (constraint.field !== 'owner_user_id' || constraint.user_id !== options.userSubject) {
        return fail('IAM owner scope does not match the verified subject')
      }
      const ownerSubject = constraint.user_id
      const ownerValue = toScalar(options.mapOwnerUserId
        ? await invokeMapping(() => options.mapOwnerUserId!(ownerSubject, options.tenantId))
        : ownerSubject)
      branches.push(`(${tenantPredicate} AND ${quoteColumn(options.columns.ownerUserId)} = ${bind(ownerValue)})`)
      continue
    }
    if (constraint.kind === 'organizations') {
      if (constraint.field !== 'organization_id' || !Array.isArray(constraint.organization_ids)
          || constraint.organization_ids.some((id) => typeof id !== 'string' || !id.trim())) {
        return fail('IAM organization scope is invalid')
      }
      const iamOrganizationIds = constraint.organization_ids
      const mappedIds = options.mapOrganizationIds
        ? await invokeMapping(() => options.mapOrganizationIds!(iamOrganizationIds, options.tenantId))
        : iamOrganizationIds
      if (!Array.isArray(mappedIds)) return fail('IAM organization mapping returned an invalid list')
      const organizationIds = [...new Set(mappedIds.map(toScalar))]
      if (organizationIds.length === 0) {
        // 空组织范围必须明确匹配零行，不能退化成仅按租户查询。
        branches.push(`(${tenantPredicate} AND FALSE)`)
        continue
      }
      branches.push(`(${tenantPredicate} AND ${quoteColumn(options.columns.organizationId)} = ANY(${bind(organizationIds)}))`)
      continue
    }
    return fail('IAM data scope contains an unsupported constraint')
  }

  if (branches.length === 0) return fail('IAM data scope produced no query branches')
  return { sql: `(${branches.join(' OR ')})`, params }
}

function validateDataScope(value: unknown, expectedTenantId: string, expectedUserSubject: string): NonNullable<AuthorizationDecision['data_scope']> {
  if (!expectedTenantId || !expectedUserSubject || !value || typeof value !== 'object' || Array.isArray(value)) {
    throw new AuthorizationServiceError(502, 'IAM returned an invalid data scope')
  }
  const scope = value as Record<string, unknown>
  if (scope.mode !== 'any_of' || !Array.isArray(scope.constraints) || scope.constraints.length === 0) {
    throw new AuthorizationServiceError(502, 'IAM returned an empty or invalid data scope')
  }
  const constraints = scope.constraints.map((value): DataScopeConstraint => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new AuthorizationServiceError(502, 'IAM returned an invalid data constraint')
    }
    const item = value as Record<string, unknown>
    if (typeof item.tenant_id !== 'string' || item.tenant_id.toLowerCase() !== expectedTenantId.toLowerCase()) {
      throw new AuthorizationServiceError(502, 'IAM returned a cross-tenant data constraint')
    }
    if (item.kind === 'tenant') return { kind: 'tenant', tenant_id: expectedTenantId }
    if (item.kind === 'owner' && item.field === 'owner_user_id'
      && typeof item.user_id === 'string' && item.user_id.length > 0 && item.user_id === expectedUserSubject) {
      return { kind: 'owner', tenant_id: expectedTenantId, field: 'owner_user_id', user_id: item.user_id }
    }
    if (item.kind === 'organizations' && item.field === 'organization_id'
      && Array.isArray(item.organization_ids)
      && item.organization_ids.every((id) => typeof id === 'string' && id.length > 0)) {
      return { kind: 'organizations', tenant_id: expectedTenantId, field: 'organization_id',
        organization_ids: item.organization_ids as string[] }
    }
    throw new AuthorizationServiceError(502, 'IAM returned an unknown or invalid data constraint')
  })
  return { mode: 'any_of', constraints }
}
