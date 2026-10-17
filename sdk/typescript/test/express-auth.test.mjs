import assert from 'node:assert/strict'
import test from 'node:test'
import { InMemoryIamSessionStore, mountOidcAuth } from '../src/express-auth.ts'

const attempt = {
  authorizationUrl: 'https://iam.example/authorize?state=state-1',
  state: 'state-1',
  nonce: 'nonce-1',
  codeVerifier: 'verifier-1',
  scopes: ['openid', 'profile', 'email'],
}

const identity = {
  subject: 'user-1',
  tenantId: 'tenant-uuid',
  profile: { email: 'user-1@example.com' },
  tokens: { accessToken: 'at-1', refreshToken: 'rt-1', idToken: 'id-1', expiresAt: 0, scopes: [] },
}

function oidcMock() {
  return {
    createAuthorizationRequest: async () => attempt,
    completeLogin: async () => identity,
    revokeRefreshToken: async () => {},
    revokeAccessToken: async () => {},
  }
}

function makeApp() {
  const routes = new Map()
  return {
    routes,
    get(path, handler) { routes.set(path, handler) },
  }
}

function makeRes() {
  const state = {
    cookies: [],
    cleared: [],
    redirect: null,
    status: null,
    body: null,
  }
  return {
    state,
    cookie(name, value, options) { state.cookies.push({ name, value, options }) },
    clearCookie(name, options) { state.cleared.push({ name, options }) },
    redirect(url) { state.redirect = url },
    status(code) {
      state.status = code
      return { json(body) { state.body = body } }
    },
  }
}

function requestWith(cookieHeader, extra = {}) {
  return {
    headers: cookieHeader ? { cookie: cookieHeader } : {},
    protocol: 'http',
    hostname: 'testserver',
    originalUrl: '/auth/callback?code=abc&state=state-1',
    ...extra,
  }
}

async function loginFlow(oidc, extra = {}) {
  const app = makeApp()
  mountOidcAuth(app, { oidcClient: oidc, sessionStore: new InMemoryIamSessionStore(), routeOptions: { postLogoutRedirect: '/goodbye' }, ...extra })
  const res = makeRes()
  await app.routes.get('/auth/login')(requestWith(), res)
  const attemptCookie = res.state.cookies.find((entry) => entry.name === 'iam_attempt')
  return { app, res, attemptCookie }
}

test('login redirects to the IdP with an HttpOnly attempt cookie stored server-side', async () => {
  const oidc = oidcMock()
  const { res, attemptCookie } = await loginFlow(oidc)
  assert.equal(res.state.redirect, attempt.authorizationUrl)
  assert.ok(attemptCookie)
  assert.equal(attemptCookie.options.httpOnly, true)
  assert.equal(attemptCookie.options.sameSite, 'lax')
  assert.ok(attemptCookie.value.length > 20)
})

test('callback exchanges the code for a session and consumes the attempt once', async () => {
  const oidc = oidcMock()
  const callbackUrls = []
  oidc.completeLogin = async (url) => {
    callbackUrls.push(url)
    return identity
  }
  const { app, attemptCookie } = await loginFlow(oidc)
  const res = makeRes()
  await app.routes.get('/auth/callback')(
    requestWith(`iam_attempt=${attemptCookie.value}`), res,
  )
  assert.equal(res.state.redirect, '/')
  const sessionCookie = res.state.cookies.find((entry) => entry.name === 'iam_session')
  assert.ok(sessionCookie)
  assert.equal(res.state.cleared.some((entry) => entry.name === 'iam_attempt'), true)
  // completeLogin 收到完整回调 URL 供 code/state 校验。
  assert.deepEqual(callbackUrls, ['http://testserver/auth/callback?code=abc&state=state-1'])
})

test('callback attempt replay is rejected with 403', async () => {
  const oidc = oidcMock()
  const { app, attemptCookie } = await loginFlow(oidc)
  const first = makeRes()
  await app.routes.get('/auth/callback')(requestWith(`iam_attempt=${attemptCookie.value}`), first)
  assert.equal(first.state.redirect, '/')
  const replay = makeRes()
  await app.routes.get('/auth/callback')(requestWith(`iam_attempt=${attemptCookie.value}`), replay)
  assert.equal(replay.state.status, 403)
})

test('callback without an attempt cookie fails closed', async () => {
  const oidc = oidcMock()
  const { app } = await loginFlow(oidc)
  const res = makeRes()
  await app.routes.get('/auth/callback')(requestWith(), res)
  assert.equal(res.state.status, 403)
  assert.deepEqual(res.state.body, { detail: 'OIDC login attempt missing or expired' })
})

test('callback protocol failures map to 403 without provider details', async () => {
  const oidc = oidcMock()
  oidc.completeLogin = async () => {
    const error = new Error('issuer mismatch with secret detail')
    error.name = 'OIDCProtocolError'
    throw error
  }
  const { app, attemptCookie } = await loginFlow(oidc)
  const res = makeRes()
  await app.routes.get('/auth/callback')(requestWith(`iam_attempt=${attemptCookie.value}`), res)
  assert.equal(res.state.status, 403)
  assert.equal(JSON.stringify(res.state.body).includes('secret detail'), false)
})

test('me returns the identity summary without tokens', async () => {
  const oidc = oidcMock()
  const { app, attemptCookie } = await loginFlow(oidc)
  const callback = makeRes()
  await app.routes.get('/auth/callback')(requestWith(`iam_attempt=${attemptCookie.value}`), callback)
  const sessionCookie = callback.state.cookies.find((entry) => entry.name === 'iam_session')
  const me = makeRes()
  await app.routes.get('/auth/me')(requestWith(`iam_session=${sessionCookie.value}`), me)
  assert.equal(me.state.status, 200)
  assert.equal(me.state.body.subject, 'user-1')
  assert.equal(me.state.body.tenantId, 'tenant-uuid')
  assert.equal(me.state.body.profile.email, 'user-1@example.com')
  assert.equal('tokens' in me.state.body, false)
})

test('me without a session is unauthorized', async () => {
  const app = makeApp()
  mountOidcAuth(app, { oidcClient: oidcMock(), sessionStore: new InMemoryIamSessionStore() })
  const me = makeRes()
  await app.routes.get('/auth/me')(requestWith(), me)
  assert.equal(me.state.status, 401)
})

test('logout revokes both tokens and removes the server-side session', async () => {
  const revoked = []
  const oidc = oidcMock()
  oidc.revokeRefreshToken = async (token) => { revoked.push(['refresh', token]) }
  oidc.revokeAccessToken = async (token) => { revoked.push(['access', token]) }
  const { app, attemptCookie } = await loginFlow(oidc)
  const callback = makeRes()
  await app.routes.get('/auth/callback')(requestWith(`iam_attempt=${attemptCookie.value}`), callback)
  const sessionCookie = callback.state.cookies.find((entry) => entry.name === 'iam_session')
  const res = makeRes()
  await app.routes.get('/auth/logout')(requestWith(`iam_session=${sessionCookie.value}`), res)
  assert.deepEqual(revoked, [['refresh', 'rt-1'], ['access', 'at-1']])
  assert.equal(res.state.redirect, '/goodbye')
  assert.equal(res.state.cleared.some((entry) => entry.name === 'iam_session'), true)
  // 会话已删除：同一 Cookie 再访问 me 必须 401。
  const me = makeRes()
  await app.routes.get('/auth/me')(requestWith(`iam_session=${sessionCookie.value}`), me)
  assert.equal(me.state.status, 401)
})

test('logout without a session is idempotent', async () => {
  const oidc = oidcMock()
  let revoked = 0
  oidc.revokeRefreshToken = async () => { revoked += 1 }
  oidc.revokeAccessToken = async () => { revoked += 1 }
  const app = makeApp()
  mountOidcAuth(app, { oidcClient: oidc, sessionStore: new InMemoryIamSessionStore() })
  const res = makeRes()
  await app.routes.get('/auth/logout')(requestWith(), res)
  assert.equal(res.state.status, 200)
  assert.deepEqual(res.state.body, { ok: true })
  assert.equal(revoked, 0)
})
