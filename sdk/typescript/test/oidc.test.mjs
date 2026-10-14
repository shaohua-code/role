import assert from 'node:assert/strict'
import { test } from 'node:test'
import { IamOIDCClient, OIDCProtocolError } from '../src/oidc.ts'

const issuer = 'https://iam.example.test'
const clientId = 'resume-backend'
const tenantId = '5a8f1998-1eab-42c5-9d64-b71cd1f53116'
const subject = '1ef0cf42-4ba2-4607-a877-99a2270cf843'
const encoder = new TextEncoder()

test('OIDC timeouts are bounded and transport failures report 503', async () => {
  const options = {
    issuer, clientId, clientSecret: 'test-secret',
    redirectUri: 'https://resume.example.test/auth/callback',
  }
  assert.throws(() => new IamOIDCClient({ ...options, timeoutMs: 0 }), RangeError)
  assert.throws(() => new IamOIDCClient({ ...options, timeoutMs: 1.5 }), RangeError)
  assert.throws(() => new IamOIDCClient({ ...options, timeoutMs: 2_147_483_648 }), RangeError)

  let observedSignal
  const client = new IamOIDCClient({
    ...options,
    timeoutMs: 10,
    fetcher: async (_url, init) => {
      observedSignal = init.signal
      return new Promise((_resolve, reject) => {
        init.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
      })
    },
  })
  await assert.rejects(
    () => client.createAuthorizationRequest(),
    (error) => error instanceof OIDCProtocolError && error.statusCode === 503
      && error.message === 'IAM endpoint timed out',
  )
  assert.equal(observedSignal.aborted, true)
})

test('OIDC timeout remains active while a response body is read', async () => {
  const client = new IamOIDCClient({
    issuer, clientId, clientSecret: 'test-secret',
    redirectUri: 'https://resume.example.test/auth/callback',
    timeoutMs: 10,
    fetcher: async (_url, init) => new Response(new ReadableStream({
      start(controller) {
        init.signal.addEventListener('abort', () => controller.error(new DOMException('aborted', 'AbortError')), { once: true })
      },
    }), { status: 200 }),
  })
  await assert.rejects(
    () => client.createAuthorizationRequest(),
    (error) => error instanceof OIDCProtocolError && error.statusCode === 503
      && error.message === 'IAM endpoint timed out',
  )
})

function base64url(bytes) {
  return Buffer.from(bytes).toString('base64url')
}

function jwtPart(value) {
  return base64url(encoder.encode(JSON.stringify(value)))
}

test('IAM RP creates PKCE S256 and verifies state, RS256 tokens, at_hash and UserInfo', async () => {
  const pair = await crypto.subtle.generateKey({
    name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256',
  }, true, ['sign', 'verify'])
  const jwk = await crypto.subtle.exportKey('jwk', pair.publicKey)
  jwk.kid = 'test-signing-key'
  jwk.alg = 'RS256'
  jwk.use = 'sig'
  let tokenCalls = 0
  let revokeBody
  let introspectionBody
  let introspectionPayload = { active: false }
  const metadata = {
    issuer,
    authorization_endpoint: `${issuer}/api/v1/oidc/authorize`,
    token_endpoint: `${issuer}/api/v1/oidc/token`,
    userinfo_endpoint: `${issuer}/api/v1/oidc/userinfo`,
    introspection_endpoint: `${issuer}/api/v1/oidc/introspect`,
    jwks_uri: `${issuer}/api/v1/oidc/jwks`,
    revocation_endpoint: `${issuer}/api/v1/oidc/revoke`,
    end_session_endpoint: `${issuer}/api/v1/oidc/logout`,
    authorization_response_iss_parameter_supported: true,
    token_endpoint_auth_methods_supported: ['client_secret_basic'],
    id_token_signing_alg_values_supported: ['RS256'],
    response_types_supported: ['code'],
    grant_types_supported: ['authorization_code', 'refresh_token'],
    code_challenge_methods_supported: ['S256'],
  }

  const sign = async (claims) => {
    const header = jwtPart({ alg: 'RS256', kid: jwk.kid, typ: 'JWT' })
    const body = jwtPart(claims)
    const input = `${header}.${body}`
    const signature = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', pair.privateKey, encoder.encode(input))
    return `${input}.${base64url(signature)}`
  }
  const fetcher = async (url, init = {}) => {
    const parsed = new URL(url)
    if (parsed.pathname.endsWith('/.well-known/openid-configuration')) return Response.json(metadata)
    if (parsed.pathname.endsWith('/jwks')) return Response.json({ keys: [jwk] })
    if (parsed.pathname.endsWith('/token')) {
      tokenCalls++
      const form = new URLSearchParams(init.body)
      assert.match(init.headers.Authorization, /^Basic /, 'client authentication must use HTTP Basic')
      assert.equal(form.get('code_verifier') !== null, form.get('grant_type') === 'authorization_code')
      const accessToken = await sign({
        iss: issuer, sub: subject, aud: clientId, client_id: clientId,
        tenant_id: tenantId, token_use: 'access_token',
        iat: Math.floor(Date.now() / 1000), exp: Math.floor(Date.now() / 1000) + 600,
      })
      const atHash = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(accessToken))).slice(0, 16))
      const idToken = await sign({
        iss: issuer, sub: subject, aud: clientId,
        iat: Math.floor(Date.now() / 1000), exp: Math.floor(Date.now() / 1000) + 600,
        nonce: form.get('code_verifier') ? currentAttempt.nonce : undefined,
        at_hash: atHash,
      })
      return Response.json({ access_token: accessToken, id_token: idToken,
        refresh_token: form.get('grant_type') === 'refresh_token' ? 'refresh-rotated' : 'refresh-secret',
        token_type: 'Bearer', expires_in: 600, scope: 'openid profile' })
    }
    if (parsed.pathname.endsWith('/userinfo')) return Response.json({ sub: subject, name: 'Test User' })
    if (parsed.pathname.endsWith('/revoke')) {
      revokeBody = new URLSearchParams(init.body)
      return new Response(null, { status: 200 })
    }
    if (parsed.pathname.endsWith('/introspect')) {
      introspectionBody = new URLSearchParams(init.body)
      assert.match(init.headers.Authorization, /^Basic /, 'introspection must use client authentication')
      return Response.json(introspectionPayload, { headers: { 'Cache-Control': 'no-store' } })
    }
    throw new Error(`unexpected request: ${url}`)
  }

  const client = new IamOIDCClient({
    issuer, clientId, clientSecret: 'test-secret',
    redirectUri: 'https://resume.example.test/auth/callback', fetcher,
  })
  const currentAttempt = await client.createAuthorizationRequest(['openid', 'profile'])
  const auth = new URL(currentAttempt.authorizationUrl)
  assert.equal(auth.searchParams.get('code_challenge_method'), 'S256')
  assert.equal(auth.searchParams.get('state'), currentAttempt.state)

  await assert.rejects(
    client.completeLogin(`https://resume.example.test/auth/callback?code=x&state=wrong&iss=${encodeURIComponent(issuer)}`, currentAttempt),
    OIDCProtocolError,
  )
  assert.equal(tokenCalls, 0, 'an invalid state must fail before sending the one-time code')

  const callback = new URL('https://resume.example.test/auth/callback')
  callback.search = new URLSearchParams({ code: 'one-time-code', state: currentAttempt.state, iss: issuer }).toString()
  const identity = await client.completeLogin(callback.toString(), currentAttempt)
  assert.equal(identity.subject, subject)
  assert.equal(identity.tenantId, tenantId)
  assert.equal(identity.profile.name, 'Test User')
  assert.equal(identity.tokens.refreshToken, 'refresh-secret')
  assert.equal(tokenCalls, 1)

  const refreshed = await client.refresh(identity)
  assert.equal(refreshed.subject, subject)
  assert.equal(refreshed.tenantId, tenantId)
  assert.equal(refreshed.tokens.refreshToken, 'refresh-rotated')
  const endSession = await client.createEndSessionRequest(refreshed, 'https://resume.example.test/signed-out')
  assert.equal(new URL(endSession.url).origin, issuer)
  assert.equal(new URL(endSession.url).pathname, '/api/v1/oidc/logout')
  assert.equal(endSession.method, 'GET')
  assert.equal(new URL(endSession.url).searchParams.get('id_token_hint'), refreshed.tokens.idToken)
  assert.equal(new URL(endSession.url).searchParams.get('state'), endSession.state)
  await client.revokeRefreshToken(refreshed.tokens.refreshToken)
  assert.equal(revokeBody.get('token'), 'refresh-rotated')
  assert.equal(revokeBody.get('token_type_hint'), 'refresh_token')
  await client.revokeAccessToken(refreshed.tokens.accessToken)
  assert.equal(revokeBody.get('token'), refreshed.tokens.accessToken)
  assert.equal(revokeBody.get('token_type_hint'), 'access_token')
  const now = Math.floor(Date.now() / 1000)
  introspectionPayload = {
    active: true, client_id: clientId, iss: issuer, sub: subject, scope: 'openid profile',
    tenant_id: tenantId, exp: now + 300, iat: now,
  }
  const introspected = await client.introspectToken(refreshed.tokens.accessToken, 'access_token')
  assert.equal(introspected.active, true)
  assert.equal(introspectionBody.get('token'), refreshed.tokens.accessToken)
  assert.equal(introspectionBody.get('token_type_hint'), 'access_token')
  introspectionPayload = { active: false }
  assert.deepEqual(await client.introspectToken('unknown-token'), { active: false })
  assert.equal(tokenCalls, 2)
})
