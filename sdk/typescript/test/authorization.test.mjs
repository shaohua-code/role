import assert from 'node:assert/strict'
import test from 'node:test'
import { IamAuthorizationClient, AuthorizationServiceError, compilePostgresDataScope } from '../src/authorization.ts'

const tenantId = '8f741d4f-16f9-4e22-94a1-d3f1c031d7ab'
const iamSubject = 'user-1'

function clientWith() {
  return new IamAuthorizationClient('https://iam.example', 'client-1')
}

test('rejects invalid timeout values before sending a request', () => {
  assert.throws(() => new IamAuthorizationClient('https://iam.example', 'client-1', 0), RangeError)
  assert.throws(() => new IamAuthorizationClient('https://iam.example', 'client-1', 1.5), RangeError)
  assert.throws(() => new IamAuthorizationClient('https://iam.example', 'client-1', 2_147_483_648), RangeError)
})

test('aborts a stalled IAM request at the configured deadline and fails closed', async () => {
  const originalFetch = globalThis.fetch
  let requestSignal
  globalThis.fetch = async (_url, init) => {
    requestSignal = init.signal
    return new Promise((_resolve, reject) => {
      init.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
    })
  }
  try {
    await assert.rejects(
      () => new IamAuthorizationClient('https://iam.example', 'client-1', 10)
        .check('access-token', { tenantId, permissionCode: 'resume.read' }),
      (error) => error instanceof AuthorizationServiceError
        && error.statusCode === 503
        && error.message === 'IAM authorization service timed out',
    )
    assert.equal(requestSignal.aborted, true)
  } finally { globalThis.fetch = originalFetch }
})

test('keeps the authorization deadline active while reading the response body', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (_url, init) => ({
    ok: true,
    status: 200,
    json: () => new Promise((_resolve, reject) => {
      init.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
    }),
  })
  try {
    await assert.rejects(
      () => new IamAuthorizationClient('https://iam.example', 'client-1', 10)
        .check('access-token', { tenantId, permissionCode: 'resume.read' }),
      (error) => error instanceof AuthorizationServiceError
        && error.statusCode === 503
        && error.message === 'IAM authorization service timed out',
    )
  } finally { globalThis.fetch = originalFetch }
})

test('preserves an IAM HTTP denial status instead of converting it to a timeout', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response('', { status: 429 })
  try {
    await assert.rejects(
      () => new IamAuthorizationClient('https://iam.example', 'client-1', 1000)
        .check('access-token', { tenantId, permissionCode: 'resume.read' }),
      (error) => error instanceof AuthorizationServiceError && error.statusCode === 429,
    )
  } finally { globalThis.fetch = originalFetch }
})

test('accepts scoped decisions only when every OR clause is tenant-bound', async () => {
  const originalFetch = globalThis.fetch
  let requestBody
  globalThis.fetch = async (_url, init) => {
    requestBody = JSON.parse(init.body)
    return new Response(JSON.stringify({
      allowed: true,
      reason: 'matching_role_grant',
      data_scope: { mode: 'any_of', constraints: [
        { kind: 'owner', field: 'owner_user_id', user_id: 'user-1', tenant_id: tenantId },
        { kind: 'organizations', field: 'organization_id', organization_ids: [], tenant_id: tenantId },
      ] },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
  try {
    const result = await clientWith().check('access-token', {
      tenantId, userSubject: iamSubject, permissionCode: 'resume.read', includeDataScope: true,
    })
    assert.equal(result.data_scope.constraints.length, 2)
    assert.equal(requestBody.user_id, undefined)
    assert.equal(requestBody.userSubject, undefined)
  } finally { globalThis.fetch = originalFetch }
})

test('rejects cross-tenant, empty, unknown and missing data-scope responses', async () => {
  const originalFetch = globalThis.fetch
  const invalidScopes = [
    { mode: 'any_of', constraints: [{ kind: 'owner', field: 'owner_user_id', user_id: 'u', tenant_id: 'other' }] },
    { mode: 'any_of', constraints: [{ kind: 'owner', field: 'owner_user_id', user_id: 'user-2', tenant_id: tenantId }] },
    { mode: 'any_of', constraints: [] },
    { mode: 'any_of', constraints: [{ kind: 'raw_sql', tenant_id: tenantId }] },
    undefined,
  ]
  try {
    for (const dataScope of invalidScopes) {
      globalThis.fetch = async () => new Response(JSON.stringify({
        allowed: true, reason: 'matching_role_grant', ...(dataScope === undefined ? {} : { data_scope: dataScope }),
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      await assert.rejects(
        () => clientWith().check('access-token', { tenantId, userSubject: iamSubject, permissionCode: 'resume.read', includeDataScope: true }),
        (error) => error instanceof AuthorizationServiceError && error.statusCode === 502,
      )
    }
  } finally { globalThis.fetch = originalFetch }
})

test('rejects a data scope returned when no scoped decision was requested', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify({
    allowed: true, reason: 'matching_role_grant',
    data_scope: { mode: 'any_of', constraints: [{ kind: 'tenant', tenant_id: tenantId }] },
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  try {
    await assert.rejects(
      () => clientWith().check('access-token', { tenantId, permissionCode: 'resume.read' }),
      (error) => error instanceof AuthorizationServiceError && error.statusCode === 502,
    )
  } finally { globalThis.fetch = originalFetch }
})

test('converts invalid JSON responses into a 502 contract error', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response('not-json', { status: 200 })
  try {
    await assert.rejects(
      () => clientWith().check('access-token', { tenantId, permissionCode: 'resume.read' }),
      (error) => error instanceof AuthorizationServiceError && error.statusCode === 502,
    )
  } finally { globalThis.fetch = originalFetch }
})

test('requires the verified IAM subject before requesting data scopes', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => { throw new Error('fetch must not be called') }
  try {
    await assert.rejects(
      () => clientWith().check('access-token', { tenantId, permissionCode: 'resume.read', includeDataScope: true }),
      (error) => error instanceof Error && error.message.includes('locally verified IAM userSubject'),
    )
  } finally { globalThis.fetch = originalFetch }
})

// 编译回归覆盖 OR 分支租户约束、本地用户主键映射和参数化数据值。
test('compiles each any_of branch with its own tenant predicate and mapped owner id', async () => {
  const filter = await compilePostgresDataScope({ mode: 'any_of', constraints: [
    { kind: 'owner', field: 'owner_user_id', user_id: iamSubject, tenant_id: tenantId },
    { kind: 'organizations', field: 'organization_id', organization_ids: ['org-1', 'org-2'], tenant_id: tenantId },
  ] }, {
    tenantId,
    userSubject: iamSubject,
    columns: { tenantId: 'r.tenant_id', ownerUserId: 'r.user_id', organizationId: 'r.organization_id' },
    mapTenantId: () => 'business-tenant',
    mapOwnerUserId: (subject) => `local-${subject}`,
    mapOrganizationIds: (ids) => ids.map((id) => `mapped-${id}`),
  })

  assert.equal(filter.sql, '(("r"."tenant_id" = $1 AND "r"."user_id" = $2) OR ("r"."tenant_id" = $3 AND "r"."organization_id" = ANY($4)))')
  assert.deepEqual(filter.params, ['business-tenant', 'local-user-1', 'business-tenant', ['mapped-org-1', 'mapped-org-2']])
  assert.equal((filter.sql.match(/"r"\."tenant_id" =/g) || []).length, 2)
  assert.equal(filter.sql.includes(iamSubject), false)
})

// 空组织范围必须保持为 false，并拦截来自不可信响应的租户或列名篡改。
test('compiles empty organization scope to zero rows and rejects unsafe scope mappings', async () => {
  const emptyFilter = await compilePostgresDataScope({ mode: 'any_of', constraints: [
    { kind: 'organizations', field: 'organization_id', organization_ids: [], tenant_id: tenantId },
  ] }, {
    tenantId, userSubject: iamSubject,
    columns: { tenantId: 'r.tenant_id', organizationId: 'r.organization_id' },
  })
  assert.equal(emptyFilter.sql, '(("r"."tenant_id" = $1 AND FALSE))')
  assert.deepEqual(emptyFilter.params, [tenantId])

  await assert.rejects(() => compilePostgresDataScope({ mode: 'any_of', constraints: [
    { kind: 'owner', field: 'owner_user_id', user_id: iamSubject, tenant_id: 'other-tenant' },
  ] }, {
    tenantId, userSubject: iamSubject, columns: { tenantId: 'r.tenant_id', ownerUserId: 'r.user_id' },
  }), (error) => error instanceof AuthorizationServiceError && error.statusCode === 502)

  await assert.rejects(() => compilePostgresDataScope({ mode: 'any_of', constraints: [
    { kind: 'tenant', tenant_id: tenantId },
  ] }, {
    tenantId, userSubject: iamSubject, columns: { tenantId: 'r.tenant_id OR TRUE' },
  }), (error) => error instanceof AuthorizationServiceError && error.statusCode === 502)

  await assert.rejects(() => compilePostgresDataScope({ mode: 'any_of', constraints: [
    { kind: 'owner', field: 'owner_user_id', user_id: iamSubject, tenant_id: tenantId },
  ] }, {
    tenantId, userSubject: iamSubject, columns: { tenantId: 'r.tenant_id', ownerUserId: 'r.user_id' },
    mapOwnerUserId: () => { throw new Error('internal database detail') },
  }), (error) => error instanceof AuthorizationServiceError && error.statusCode === 503
    && !error.message.includes('internal database detail'))
})

// 批量判定：请求形状与单码契约一致，每个请求码都必须有明确判定结果。
test('checkBatch maps every requested code on the batch endpoint', async () => {
  const originalFetch = globalThis.fetch
  let requestUrl
  let requestBody
  globalThis.fetch = async (url, init) => {
    requestUrl = String(url)
    requestBody = JSON.parse(init.body)
    return new Response(JSON.stringify({ results: {
      'resume.read': { allowed: true, reason: 'matching_role_grant', application_id: 'client-1' },
      'resume.delete': { allowed: false, reason: 'no_matching_grant' },
    } }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
  try {
    const decisions = await clientWith().checkBatch('access-token', {
      tenantId, permissionCodes: ['resume.read', 'resume.delete'],
    })
    assert.equal(requestUrl, 'https://iam.example/api/v1/authorization/check-batch')
    assert.deepEqual(requestBody, {
      tenant_id: tenantId, application_id: 'client-1', permission_codes: ['resume.read', 'resume.delete'],
    })
    assert.equal(decisions['resume.read'].allowed, true)
    assert.equal(decisions['resume.read'].application_id, 'client-1')
    assert.equal(decisions['resume.read'].data_scope, undefined)
    assert.equal(decisions['resume.delete'].allowed, false)
    assert.equal(decisions['resume.delete'].reason, 'no_matching_grant')
  } finally { globalThis.fetch = originalFetch }
})

// 缺码、坏 allowed、坏 application_id 都必须 fail closed，不允许静默补默认判定。
test('checkBatch rejects incomplete or malformed batch results', async () => {
  const originalFetch = globalThis.fetch
  const invalidBodies = [
    { results: { 'resume.read': { allowed: true, reason: 'matching_role_grant' } } },
    { results: {
      'resume.read': { allowed: true, reason: 'matching_role_grant' },
      'resume.delete': { allowed: 'yes', reason: 'forged' },
    } },
    { results: {
      'resume.read': { allowed: true, reason: 'matching_role_grant' },
      'resume.delete': { allowed: false, reason: 'no_matching_grant', application_id: ' ' },
    } },
    { unexpected: {} },
  ]
  try {
    for (const body of invalidBodies) {
      globalThis.fetch = async () => new Response(JSON.stringify(body), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      })
      await assert.rejects(
        () => clientWith().checkBatch('access-token', { tenantId, permissionCodes: ['resume.read', 'resume.delete'] }),
        (error) => error instanceof AuthorizationServiceError && error.statusCode === 502,
      )
    }
  } finally { globalThis.fetch = originalFetch }
})

test('checkBatch validates inputs before any network call', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => { throw new Error('fetch must not be called') }
  try {
    for (const permissionCodes of [[], ['resume.read', ''], 'resume.read', [null]]) {
      await assert.rejects(
        () => clientWith().checkBatch('access-token', { tenantId, permissionCodes }),
        (error) => error instanceof Error && error.message.includes('permissionCodes'),
      )
    }
    await assert.rejects(
      () => clientWith().checkBatch('', { tenantId, permissionCodes: ['resume.read'] }),
      (error) => error instanceof Error && error.message.includes('access token is required'),
    )
  } finally { globalThis.fetch = originalFetch }
})
