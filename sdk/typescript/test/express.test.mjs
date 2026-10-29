import assert from 'node:assert/strict'
import test from 'node:test'
import { AuthorizationServiceError, IamAuthorizationClient } from '../src/authorization.ts'
import { createIamExpress } from '../src/express.ts'

const tenantId = '8f741d4f-16f9-4e22-94a1-d3f1c031d7ab'
const iamSubject = 'user-1'
const accessToken = 'access-token'

function clientMock() {
  return new IamAuthorizationClient('https://iam.example', 'client-1')
}

function fakeSessionLoader() {
  return (req) => {
    const token = req.headers['x-access-token']
    if (!token) {
      const error = new Error('Missing session')
      error.statusCode = 401
      throw error
    }
    return { accessToken: token, tenantId: req.headers['x-tenant'], iamSubject: req.headers['x-subject'] }
  }
}

function makeIam(client, overrides = {}) {
  return createIamExpress({
    client,
    loadSession: fakeSessionLoader(),
    permissionMap: { 'document.read': 'crm.document.read' },
    localUserIdResolver: (user) => `local-${user.iamSubject}`,
    ...overrides,
  })
}

function makeRes() {
  const calls = { status: null, body: null }
  return {
    calls,
    status(code) {
      calls.status = code
      return { json(body) { calls.body = body } }
    },
  }
}

function requestWith(headers = {}) {
  return { headers: { 'x-access-token': accessToken, 'x-tenant': tenantId, 'x-subject': iamSubject, ...headers } }
}

function ownerScope(subject) {
  return { mode: 'any_of', constraints: [
    { kind: 'owner', field: 'owner_user_id', user_id: subject, tenant_id: tenantId },
  ] }
}

test('requirePermission maps the alias to the stable code and fills res.locals', async () => {
  const client = clientMock()
  client.require = async (_token, request) => {
    assert.deepEqual(request, { tenantId, permissionCode: 'crm.document.read' })
    return { allowed: true, reason: 'matching_role_grant' }
  }
  const iam = makeIam(client)
  const middleware = iam.requirePermission('document.read')
  const req = requestWith()
  const res = makeRes()
  let nextCalled = false
  await middleware(req, res, () => { nextCalled = true })
  assert.equal(nextCalled, true)
  assert.equal(req.iamUser.iamSubject, iamSubject)
  assert.equal(req.iamDecision.allowed, true)
  assert.equal(res.calls.status, null)
})

test('maps an IAM denial to 403 and never calls next', async () => {
  const client = clientMock()
  client.require = async () => { throw new AuthorizationServiceError(403, 'Permission denied: no_matching_grant') }
  const iam = makeIam(client)
  const req = requestWith()
  const res = makeRes()
  let nextCalled = false
  await iam.requirePermission('document.read')(req, res, () => { nextCalled = true })
  assert.equal(nextCalled, false)
  assert.equal(res.calls.status, 403)
  assert.deepEqual(res.calls.body, { detail: 'Permission denied: no_matching_grant' })
})

test('maps IAM unavailability to 503 and contract errors to 502', async () => {
  for (const [thrown, expected] of [
    [new AuthorizationServiceError(503, 'IAM authorization service is unavailable'), 503],
    [new AuthorizationServiceError(502, 'IAM returned an invalid authorization decision'), 502],
    [new AuthorizationServiceError(429, 'IAM rejected the authorization request'), 502],
  ]) {
    const client = clientMock()
    client.require = async () => { throw thrown }
    const iam = makeIam(client)
    const req = requestWith()
    const res = makeRes()
    let nextCalled = false
    await iam.requirePermission('document.read')(req, res, () => { nextCalled = true })
    assert.equal(nextCalled, false, expected)
    assert.equal(res.calls.status, expected, expected)
  }
})

test('unregistered aliases fail closed when the middleware is created', () => {
  const iam = makeIam(clientMock())
  assert.throws(() => iam.requirePermission('resume.export'), /not registered/)
})

test('ownerOnly checks the scoped decision and resolves the local user key', async () => {
  const client = clientMock()
  let seenRequest
  client.check = async (_token, request) => {
    seenRequest = request
    return { allowed: true, reason: 'matching_role_grant', data_scope: ownerScope(iamSubject) }
  }
  const iam = makeIam(client)
  const req = requestWith()
  const res = makeRes()
  let nextCalled = false
  await iam.requirePermission('document.read', { ownerOnly: true })(req, res, () => { nextCalled = true })
  assert.deepEqual(seenRequest, {
    tenantId, userSubject: iamSubject, permissionCode: 'crm.document.read', includeDataScope: true,
  })
  assert.equal(nextCalled, true)
  assert.equal(req.iamUser.localUserId, `local-${iamSubject}`)
})

test('ownerOnly rejects a widened any_of scope with 403', async () => {
  const client = clientMock()
  client.check = async () => ({
    allowed: true,
    reason: 'matching_role_grant',
    data_scope: { mode: 'any_of', constraints: [
      { kind: 'owner', field: 'owner_user_id', user_id: iamSubject, tenant_id: tenantId },
      { kind: 'tenant', tenant_id: tenantId },
    ] },
  })
  const iam = makeIam(client)
  const req = requestWith()
  const res = makeRes()
  let nextCalled = false
  await iam.requirePermission('document.read', { ownerOnly: true })(req, res, () => { nextCalled = true })
  assert.equal(nextCalled, false)
  assert.equal(res.calls.status, 403)
})

test('ownerOnly without a local user resolver fails at creation time', () => {
  const iam = makeIam(clientMock(), { localUserIdResolver: undefined })
  assert.throws(() => iam.requirePermission('document.read', { ownerOnly: true }), /localUserIdResolver/)
})

test('session loader failures are forwarded to the business error handler', async () => {
  const client = clientMock()
  let requireCalled = false
  client.require = async () => { requireCalled = true }
  const iam = makeIam(client, { loadSession: fakeSessionLoader() })
  const req = requestWith({ 'x-access-token': '' })
  const res = makeRes()
  const forwarded = []
  await iam.requirePermission('document.read')(req, res, (err) => { forwarded.push(err) })
  assert.equal(forwarded.length, 1)
  assert.equal(forwarded[0].statusCode, 401)
  assert.equal(requireCalled, false)
})

test('currentUser exposes the verified session without contacting IAM', async () => {
  const client = clientMock()
  let requireCalled = false
  client.require = async () => { requireCalled = true }
  const iam = makeIam(client)
  const req = requestWith()
  const res = makeRes()
  let nextCalled = false
  await iam.currentUser()(req, res, () => { nextCalled = true })
  assert.equal(nextCalled, true)
  assert.equal(req.iamUser.tenantId, tenantId)
  assert.equal(requireCalled, false)
})


test('requireRoles allows when session holds any listed role', async () => {
  const client = clientMock()
  const iam = createIamExpress({
    client,
    loadSession: async () => ({
      accessToken,
      tenantId,
      iamSubject,
      roleKeys: ['app.member', 'deerflow_member'],
    }),
  })
  const req = { headers: {} }
  const res = makeRes()
  let nextCalled = false
  await iam.requireRoles('app.admin', 'app.member')(req, res, () => { nextCalled = true })
  assert.equal(nextCalled, true)
  assert.equal(req.iamUser.iamSubject, iamSubject)
  assert.equal(res.calls.status, null)
})

test('requireRoles denies when session lacks all listed roles', async () => {
  const client = clientMock()
  const iam = createIamExpress({
    client,
    loadSession: async () => ({
      accessToken,
      tenantId,
      iamSubject,
      roleKeys: ['app.member'],
    }),
  })
  const req = { headers: {} }
  const res = makeRes()
  let nextCalled = false
  await iam.requireRoles('app.admin')(req, res, () => { nextCalled = true })
  assert.equal(nextCalled, false)
  assert.equal(res.calls.status, 403)
  assert.deepEqual(res.calls.body, { detail: 'Missing required role: app.admin' })
})

test('requireRoles fails closed when created with no role keys', () => {
  const iam = makeIam(clientMock())
  assert.throws(() => iam.requireRoles(), /at least one role key/)
})


test('requireRoles fetches /auth/me when roleKeys missing and apiBaseUrl set', async () => {
  const client = clientMock()
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, init) => {
    assert.equal(String(url), 'https://iam.example/api/v1/auth/me')
    assert.equal(init.headers.Authorization, `Bearer ${accessToken}`)
    return {
      ok: true,
      async json() {
        return { roles: [{ key: 'app.member' }, { key: 'deerflow_member' }] }
      },
    }
  }
  try {
    const iam = createIamExpress({
      client,
      apiBaseUrl: 'https://iam.example',
      loadSession: async () => ({ accessToken, tenantId, iamSubject }),
    })
    const req = { headers: {} }
    const res = makeRes()
    let nextCalled = false
    await iam.requireRoles('app.member')(req, res, () => { nextCalled = true })
    assert.equal(nextCalled, true)
    assert.deepEqual(req.iamUser.roleKeys, ['app.member', 'deerflow_member'])
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('requireRoles uses custom fetchRoles and skips network', async () => {
  const client = clientMock()
  let fetched = false
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => { fetched = true; throw new Error('network should not run') }
  try {
    const iam = createIamExpress({
      client,
      apiBaseUrl: 'https://iam.example',
      fetchRoles: async () => ['app.admin'],
      loadSession: async () => ({ accessToken, tenantId, iamSubject }),
    })
    const req = { headers: {} }
    const res = makeRes()
    let nextCalled = false
    await iam.requireRoles('app.admin')(req, res, () => { nextCalled = true })
    assert.equal(nextCalled, true)
    assert.equal(fetched, false)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('requireRoles with fetchRoles false does not fetch and denies empty roles', async () => {
  const client = clientMock()
  let fetched = false
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => { fetched = true; return { ok: true, async json() { return { roles: [{ key: 'app.member' }] } } } }
  try {
    const iam = createIamExpress({
      client,
      apiBaseUrl: 'https://iam.example',
      fetchRoles: false,
      loadSession: async () => ({ accessToken, tenantId, iamSubject }),
    })
    const req = { headers: {} }
    const res = makeRes()
    let nextCalled = false
    await iam.requireRoles('app.member')(req, res, () => { nextCalled = true })
    assert.equal(nextCalled, false)
    assert.equal(fetched, false)
    assert.equal(res.calls.status, 403)
  } finally {
    globalThis.fetch = originalFetch
  }
})
