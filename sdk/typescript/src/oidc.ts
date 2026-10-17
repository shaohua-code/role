/**
 * Server-side OpenID Connect relying-party client for the IAM provider.
 *
 * This class uses only Web Crypto and Fetch APIs and is intended for Node.js
 * services. Never bundle it into Vue or expose its client secret to a browser.
 */

export class OIDCProtocolError extends Error {
  readonly statusCode?: number

  constructor(message: string, statusCode?: number) {
    super(message)
    this.name = 'OIDCProtocolError'
    this.statusCode = statusCode
  }
}

export interface IamOIDCOptions {
  issuer: string
  clientId: string
  clientSecret: string
  redirectUri: string
  timeoutMs?: number
  /** Dependency seam for deterministic tests; production should use global fetch. */
  fetcher?: typeof fetch
}

export interface AuthorizationAttempt {
  /** Keep this object in a server-side session and consume it once on callback. */
  authorizationUrl: string
  state: string
  nonce: string
  codeVerifier: string
  scopes: string[]
}

export interface IamTokenSet {
  accessToken: string
  refreshToken?: string
  idToken: string
  expiresAt: number
  scopes: string[]
}

export interface IamIdentity {
  subject: string
  tenantId: string
  profile: Record<string, unknown>
  tokens: IamTokenSet
}

/** Top-level navigation; caller stores `state` in its server session before redirecting the browser. */
export interface EndSessionRequest {
  url: string
  method: 'GET'
  state: string
}

export interface TokenIntrospection {
  active: boolean
  scope?: string
  client_id?: string
  token_type?: string
  sub?: string
  aud?: string
  iss?: string
  tenant_id?: string
  exp?: number
  iat?: number
}

interface OIDCMetadata {
  issuer: string
  authorization_endpoint: string
  token_endpoint: string
  userinfo_endpoint: string
  introspection_endpoint: string
  jwks_uri: string
  revocation_endpoint: string
  end_session_endpoint: string
  authorization_response_iss_parameter_supported?: boolean
  token_endpoint_auth_methods_supported: string[]
  id_token_signing_alg_values_supported: string[]
  response_types_supported: string[]
  grant_types_supported: string[]
  code_challenge_methods_supported: string[]
}

interface JWTClaims {
  iss?: unknown
  sub?: unknown
  aud?: unknown
  azp?: unknown
  exp?: unknown
  iat?: unknown
  nbf?: unknown
  nonce?: unknown
  at_hash?: unknown
  token_use?: unknown
  client_id?: unknown
  tenant_id?: unknown
  [claim: string]: unknown
}

const MAX_RESPONSE_CHARS = 1_048_576
const encoder = new TextEncoder()

/** RP client implementing authorization code + PKCE S256 against this IAM. */
export class IamOIDCClient {
  private readonly issuer: string
  private readonly clientId: string
  private readonly redirectUri: string
  private readonly timeoutMs: number
  private readonly fetcher: typeof fetch
  readonly #clientSecret: string
  private metadata?: OIDCMetadata
  private jwks?: JsonWebKey[]

  constructor(options: IamOIDCOptions) {
    if (!options.clientId || !options.clientSecret || !options.redirectUri) {
      throw new TypeError('OIDC client id, secret, and redirect URI are required')
    }
    this.issuer = options.issuer.replace(/\/$/, '')
    this.clientId = options.clientId
    this.redirectUri = options.redirectUri
    this.#clientSecret = options.clientSecret
    this.timeoutMs = options.timeoutMs ?? 5_000
    if (!Number.isInteger(this.timeoutMs) || this.timeoutMs < 1 || this.timeoutMs > 2_147_483_647) {
      throw new RangeError('OIDC timeout must be a positive 32-bit millisecond value')
    }
    this.fetcher = options.fetcher ?? fetch
    this.validateUrl(this.issuer, 'issuer')
    this.validateUrl(this.redirectUri, 'redirect URI')
  }

  /** Create unpredictable state/nonce and an S256 verifier for server session storage. */
  async createAuthorizationRequest(
    scopes: string[] = ['openid', 'profile', 'email'],
    prompt?: 'login' | 'none' | 'consent',
  ): Promise<AuthorizationAttempt> {
    if (!scopes.includes('openid') || new Set(scopes).size !== scopes.length || scopes.length > 30) {
      throw new TypeError('OIDC scopes must include openid and contain no duplicates')
    }
    const metadata = await this.getMetadata()
    const state = this.randomToken(32)
    const nonce = this.randomToken(32)
    const codeVerifier = this.randomToken(64)
    const challengeBytes = await crypto.subtle.digest('SHA-256', encoder.encode(codeVerifier))
    const params = new URLSearchParams({
      response_type: 'code',
      client_id: this.clientId,
      redirect_uri: this.redirectUri,
      scope: scopes.join(' '),
      state,
      nonce,
      code_challenge: this.base64Url(new Uint8Array(challengeBytes)),
      code_challenge_method: 'S256',
    })
    if (prompt) params.set('prompt', prompt)
    const separator = metadata.authorization_endpoint.includes('?') ? '&' : '?'
    return {
      authorizationUrl: `${metadata.authorization_endpoint}${separator}${params.toString()}`,
      state,
      nonce,
      codeVerifier,
      scopes: [...scopes],
    }
  }

  /** Validate state/issuer, exchange the one-time code, verify JWTs, then bind UserInfo. */
  async completeLogin(callbackUrl: string, attempt: AuthorizationAttempt): Promise<IamIdentity> {
    const callback = new URL(callbackUrl)
    const configured = new URL(this.redirectUri)
    if (callback.origin !== configured.origin || callback.pathname !== configured.pathname || callback.hash) {
      throw new OIDCProtocolError('OIDC callback URL does not match the configured redirect URI')
    }
    configured.searchParams.forEach((value, name) => {
      const returned = callback.searchParams.getAll(name)
      if (returned.length !== 1 || returned[0] !== value) {
        throw new OIDCProtocolError('OIDC callback URL does not match the configured redirect URI')
      }
    })
    const params = callback.searchParams
    const state = this.single(params, 'state')
    if (!state || !this.constantTimeEqual(state, attempt.state)) {
      throw new OIDCProtocolError('OIDC callback state is missing or invalid')
    }
    const metadata = await this.getMetadata()
    const returnedIssuer = this.single(params, 'iss')
    if (metadata.authorization_response_iss_parameter_supported && returnedIssuer !== this.issuer) {
      throw new OIDCProtocolError('OIDC callback issuer is missing or invalid')
    }
    if (returnedIssuer !== null && returnedIssuer !== this.issuer) {
      throw new OIDCProtocolError('OIDC callback issuer is invalid')
    }
    if (this.single(params, 'error')) throw new OIDCProtocolError('IAM did not authorize this login')
    const code = this.single(params, 'code')
    if (!code) throw new OIDCProtocolError('OIDC callback has no authorization code')

    const token = await this.postToken(metadata, {
      grant_type: 'authorization_code',
      code,
      redirect_uri: this.redirectUri,
      code_verifier: attempt.codeVerifier,
    })
    const accessToken = this.requiredString(token.access_token, 'access token')
    const idToken = this.requiredString(token.id_token, 'ID token')
    if (String(token.token_type).toLowerCase() !== 'bearer') {
      throw new OIDCProtocolError('IAM returned an unsupported token type')
    }
    const idClaims = await this.verifyJwt(idToken, metadata, attempt.nonce, accessToken)
    const accessClaims = await this.verifyJwt(accessToken, metadata)
    const subject = this.requiredString(idClaims.sub, 'ID token subject')
    if (subject !== accessClaims.sub || accessClaims.token_use !== 'access_token'
      || accessClaims.client_id !== this.clientId) {
      throw new OIDCProtocolError('IAM access token identity or purpose is invalid')
    }
    const tenantId = this.validUuid(accessClaims.tenant_id)
    const expiresIn = this.validExpiry(token.expires_in)
    const scopes = this.parseScopes(token.scope, attempt.scopes)
    const profile = await this.getUserInfo(metadata, accessToken, subject)
    const refreshToken = token.refresh_token
    if (refreshToken !== undefined && (typeof refreshToken !== 'string' || !refreshToken)) {
      throw new OIDCProtocolError('IAM returned an invalid refresh token')
    }
    return {
      subject,
      tenantId,
      profile,
      tokens: {
        accessToken,
        ...(refreshToken ? { refreshToken } : {}),
        idToken,
        expiresAt: Math.floor(Date.now() / 1000) + expiresIn,
        scopes,
      },
    }
  }

  /** Rotate the server-side refresh credential without changing subject or tenant. */
  async refresh(identity: IamIdentity): Promise<IamIdentity> {
    const previousRefresh = identity.tokens.refreshToken
    if (!previousRefresh) throw new OIDCProtocolError('This IAM session has no refresh token')
    const metadata = await this.getMetadata()
    const token = await this.postToken(metadata, {
      grant_type: 'refresh_token', refresh_token: previousRefresh,
    })
    const accessToken = this.requiredString(token.access_token, 'access token')
    const idToken = this.requiredString(token.id_token, 'ID token')
    const nextRefresh = this.requiredString(token.refresh_token, 'rotated refresh token')
    if (this.constantTimeEqual(previousRefresh, nextRefresh)) {
      throw new OIDCProtocolError('IAM refresh token rotation did not occur')
    }
    if (String(token.token_type).toLowerCase() !== 'bearer') {
      throw new OIDCProtocolError('IAM returned an unsupported token type')
    }
    const idClaims = await this.verifyJwt(idToken, metadata, undefined, accessToken)
    const accessClaims = await this.verifyJwt(accessToken, metadata)
    if (idClaims.sub !== identity.subject || accessClaims.sub !== identity.subject
      || accessClaims.token_use !== 'access_token' || accessClaims.client_id !== this.clientId
      || this.validUuid(accessClaims.tenant_id) !== identity.tenantId) {
      throw new OIDCProtocolError('IAM refresh changed the authenticated identity context')
    }
    const scopes = this.parseScopes(token.scope ?? identity.tokens.scopes.join(' '), identity.tokens.scopes)
    const profile = await this.getUserInfo(metadata, accessToken, identity.subject)
    return {
      subject: identity.subject,
      tenantId: identity.tenantId,
      profile,
      tokens: {
        accessToken,
        refreshToken: nextRefresh,
        idToken,
        expiresAt: Math.floor(Date.now() / 1000) + this.validExpiry(token.expires_in),
        scopes,
      },
    }
  }

  private async revokeToken(token: string, tokenTypeHint: 'access_token' | 'refresh_token'): Promise<void> {
    if (!token) return
    const metadata = await this.getMetadata()
    const body = new URLSearchParams({ token, token_type_hint: tokenTypeHint })
    await this.requestJson(metadata.revocation_endpoint, {
      method: 'POST',
      headers: {
        Authorization: this.basicAuthorization(),
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
      },
      body,
    }, true)
  }

  /** Revoke a refresh credential when the business application logs the user out. */
  async revokeRefreshToken(refreshToken: string): Promise<void> {
    await this.revokeToken(refreshToken, 'refresh_token')
  }

  /** Revoke an access JWT immediately for IAM online authorization and UserInfo calls. */
  async revokeAccessToken(accessToken: string): Promise<void> {
    await this.revokeToken(accessToken, 'access_token')
  }

  /** Check a token owned by this confidential client against IAM's live revocation and account state. */
  async introspectToken(token: string, tokenTypeHint?: 'access_token' | 'refresh_token'): Promise<TokenIntrospection> {
    if (!token || token.length > 8192) throw new OIDCProtocolError('Token must be non-empty and no longer than 8192 characters')
    const metadata = await this.getMetadata()
    const body = new URLSearchParams({ token })
    if (tokenTypeHint) body.set('token_type_hint', tokenTypeHint)
    const result = await this.requestJson(metadata.introspection_endpoint, {
      method: 'POST',
      headers: {
        Authorization: this.basicAuthorization(),
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
      },
      body,
    })
    if (!this.isRecord(result) || typeof result.active !== 'boolean') {
      throw new OIDCProtocolError('IAM returned an invalid token introspection response')
    }
    if (!result.active) return { active: false }
    if (result.client_id !== this.clientId || result.iss !== this.issuer
      || typeof result.sub !== 'string' || typeof result.scope !== 'string'
      || typeof result.tenant_id !== 'string' || typeof result.exp !== 'number'
      || !Number.isInteger(result.exp) || typeof result.iat !== 'number' || !Number.isInteger(result.iat)) {
      throw new OIDCProtocolError('IAM returned active token metadata for an unexpected client or issuer')
    }
    return result as unknown as TokenIntrospection
  }

  /** Build a browser navigation for RP logout; store returned state in the server session first. */
  async createEndSessionRequest(identity: IamIdentity, postLogoutRedirectUri: string): Promise<EndSessionRequest> {
    if (!identity.tokens.idToken) throw new OIDCProtocolError('This IAM session has no ID token for logout')
    this.validateUrl(postLogoutRedirectUri, 'post-logout redirect URI')
    const metadata = await this.getMetadata()
    const state = this.randomToken(32)
    const url = new URL(metadata.end_session_endpoint)
    url.search = new URLSearchParams({
      id_token_hint: identity.tokens.idToken,
      post_logout_redirect_uri: postLogoutRedirectUri,
      state,
    }).toString()
    return {
      url: url.toString(),
      method: 'GET',
      state,
    }
  }

  private async getMetadata(): Promise<OIDCMetadata> {
    if (this.metadata) return this.metadata
    const value = await this.requestJson(`${this.issuer}/.well-known/openid-configuration`)
    if (!this.isRecord(value) || value.issuer !== this.issuer) {
      throw new OIDCProtocolError('OIDC discovery issuer does not match configuration')
    }
    const metadata = value as unknown as OIDCMetadata
    for (const key of ['authorization_endpoint', 'token_endpoint', 'userinfo_endpoint', 'introspection_endpoint', 'jwks_uri', 'revocation_endpoint', 'end_session_endpoint'] as const) {
      const endpoint = metadata[key]
      this.validateUrl(endpoint, key)
      if (new URL(endpoint).origin !== new URL(this.issuer).origin) {
        throw new OIDCProtocolError('OIDC endpoint is outside the configured issuer origin')
      }
    }
    if (!metadata.token_endpoint_auth_methods_supported?.includes('client_secret_basic')
      || !metadata.id_token_signing_alg_values_supported?.includes('RS256')
      || !metadata.response_types_supported?.includes('code')
      || !metadata.grant_types_supported?.includes('authorization_code')
      || !metadata.code_challenge_methods_supported?.includes('S256')) {
      throw new OIDCProtocolError('IAM discovery does not advertise the required secure OIDC profile')
    }
    this.metadata = metadata
    return metadata
  }

  private async getJwks(metadata: OIDCMetadata): Promise<JsonWebKey[]> {
    if (this.jwks) return this.jwks
    const response = await this.requestJson(metadata.jwks_uri)
    if (!this.isRecord(response) || !Array.isArray(response.keys)) {
      throw new OIDCProtocolError('IAM returned an invalid JWKS document')
    }
    this.jwks = response.keys.filter((key: unknown): key is JsonWebKey => this.isRecord(key)
      && key.kty === 'RSA' && typeof key.kid === 'string' && key.alg === 'RS256')
    if (!this.jwks.length) throw new OIDCProtocolError('IAM JWKS has no supported RS256 key')
    return this.jwks
  }

  private async verifyJwt(token: string, metadata: OIDCMetadata, nonce?: string, accessToken?: string): Promise<JWTClaims> {
    const pieces = token.split('.')
    if (pieces.length !== 3) throw new OIDCProtocolError('IAM returned a malformed JWT')
    let header: Record<string, unknown>
    let claims: JWTClaims
    try {
      header = JSON.parse(this.decodeText(pieces[0])) as Record<string, unknown>
      claims = JSON.parse(this.decodeText(pieces[1])) as JWTClaims
    } catch {
      throw new OIDCProtocolError('IAM returned a malformed JWT')
    }
    if (header.alg !== 'RS256' || typeof header.kid !== 'string' || header.crit !== undefined || header.b64 === false) {
      throw new OIDCProtocolError('IAM JWT uses an unsupported signing key')
    }
    let jwk = (await this.getJwks(metadata)).find(key => (key as JsonWebKey & { kid?: string }).kid === header.kid)
    // A cached set may predate a planned provider key change; refresh once for an unknown kid.
    if (!jwk) {
      this.jwks = undefined
      jwk = (await this.getJwks(metadata)).find(key => (key as JsonWebKey & { kid?: string }).kid === header.kid)
    }
    if (!jwk) throw new OIDCProtocolError('IAM JWT signing key is not present in JWKS')
    const key = await crypto.subtle.importKey('jwk', jwk, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify'])
    const signed = encoder.encode(`${pieces[0]}.${pieces[1]}`)
    const verified = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, this.fromBase64Url(pieces[2]), signed)
    const now = Math.floor(Date.now() / 1000)
    if (!verified || claims.iss !== this.issuer || !this.audienceMatches(claims.aud)
      || !Number.isInteger(claims.exp) || Number(claims.exp) <= now
      || !Number.isInteger(claims.iat) || Number(claims.iat) > now + 60
      || (claims.nbf !== undefined && (!Number.isInteger(claims.nbf) || Number(claims.nbf) > now + 60))) {
      throw new OIDCProtocolError('IAM JWT signature or standard claims are invalid')
    }
    if (Array.isArray(claims.aud) && claims.aud.length > 1 && claims.azp !== this.clientId) {
      throw new OIDCProtocolError('IAM JWT authorized party is invalid')
    }
    if (nonce !== undefined && claims.nonce !== nonce) throw new OIDCProtocolError('IAM ID token nonce is invalid')
    if (accessToken !== undefined) {
      const expected = this.base64Url(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(accessToken))).slice(0, 16))
      if (typeof claims.at_hash !== 'string' || !this.constantTimeEqual(claims.at_hash, expected)) {
        throw new OIDCProtocolError('IAM ID token access-token hash is invalid')
      }
    }
    return claims
  }

  private async getUserInfo(metadata: OIDCMetadata, accessToken: string, subject: string): Promise<Record<string, unknown>> {
    const response = await this.requestJson(metadata.userinfo_endpoint, {
      headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json' },
    })
    if (!this.isRecord(response) || response.sub !== subject) {
      throw new OIDCProtocolError('IAM UserInfo subject does not match the signed identity')
    }
    return response
  }

  private async postToken(metadata: OIDCMetadata, fields: Record<string, string>): Promise<Record<string, unknown>> {
    const body = new URLSearchParams(fields)
    const result = await this.requestJson(metadata.token_endpoint, {
      method: 'POST',
      headers: {
        Authorization: this.basicAuthorization(),
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
      },
      body,
    })
    if (!this.isRecord(result)) throw new OIDCProtocolError('IAM returned an invalid token response')
    return result
  }

  private async requestJson(url: string, init: RequestInit = {}, allowEmpty = false): Promise<unknown> {
    this.validateUrl(url, 'endpoint')
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeoutMs)
    try {
      const response = await this.fetcher(url, { ...init, redirect: 'error', signal: controller.signal })
      if (!response.ok) throw new OIDCProtocolError(`IAM endpoint returned HTTP ${response.status}`, response.status)
      const text = await this.readLimitedBody(response)
      if (!text && allowEmpty) return {}
      try {
        return JSON.parse(text) as unknown
      } catch {
        if (allowEmpty && !text) return {}
        throw new OIDCProtocolError('IAM endpoint returned invalid JSON')
      }
    } catch (error) {
      if (error instanceof OIDCProtocolError) throw error
      if (controller.signal.aborted) throw new OIDCProtocolError('IAM endpoint timed out', 503)
      throw new OIDCProtocolError('IAM endpoint is unavailable', 503)
    } finally {
      clearTimeout(timer)
    }
  }

  private async readLimitedBody(response: Response): Promise<string> {
    const length = Number(response.headers.get('content-length'))
    if (Number.isFinite(length) && length > MAX_RESPONSE_CHARS) {
      await response.body?.cancel()
      throw new OIDCProtocolError('IAM response is too large')
    }
    if (!response.body) return ''
    const reader = response.body.getReader()
    const chunks: Uint8Array[] = []
    let total = 0
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        total += value.byteLength
        if (total > MAX_RESPONSE_CHARS) {
          await reader.cancel()
          throw new OIDCProtocolError('IAM response is too large')
        }
        chunks.push(value)
      }
    } finally {
      reader.releaseLock()
    }
    const body = new Uint8Array(total)
    let offset = 0
    for (const chunk of chunks) {
      body.set(chunk, offset)
      offset += chunk.byteLength
    }
    return new TextDecoder('utf-8', { fatal: true }).decode(body)
  }

  private basicAuthorization(): string {
    // OAuth client_secret_basic applies form encoding before Base64 (RFC 6749 §2.3.1).
    const formEncode = (value: string) => encodeURIComponent(value)
      .replace(/[!'()*]/g, char => `%${char.charCodeAt(0).toString(16).toUpperCase()}`)
      .replace(/%20/g, '+')
    return `Basic ${btoa(`${formEncode(this.clientId)}:${formEncode(this.#clientSecret)}`)}`
  }

  private parseScopes(value: unknown, allowed: string[]): string[] {
    if (typeof value !== 'string') throw new OIDCProtocolError('IAM returned an invalid scope response')
    const scopes = value.split(/\s+/).filter(Boolean)
    if (!scopes.includes('openid') || scopes.some(scope => !allowed.includes(scope))) {
      throw new OIDCProtocolError('IAM returned scopes outside the original authorization request')
    }
    return scopes
  }

  private validExpiry(value: unknown): number {
    const expiry = typeof value === 'number' ? value : Number.NaN
    if (!Number.isSafeInteger(expiry) || expiry <= 0 || expiry > 31_536_000) {
      throw new OIDCProtocolError('IAM returned an invalid token expiry')
    }
    return expiry
  }

  private audienceMatches(aud: unknown): boolean {
    return aud === this.clientId || (Array.isArray(aud) && aud.includes(this.clientId))
  }

  private validUuid(value: unknown): string {
    if (typeof value !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) {
      throw new OIDCProtocolError('IAM access token has no valid tenant context')
    }
    return value.toLowerCase()
  }

  private single(params: URLSearchParams, name: string): string | null {
    const values = params.getAll(name)
    if (values.length > 1) throw new OIDCProtocolError(`OIDC callback has duplicate ${name} parameters`)
    return values[0] ?? null
  }

  private validateUrl(value: string, label: string): void {
    let url: URL
    try { url = new URL(value) } catch { throw new TypeError(`Invalid OIDC ${label} URL`) }
    if (url.username || url.password || url.hash || !['https:', 'http:'].includes(url.protocol)
      || (url.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) {
      throw new TypeError(`OIDC ${label} must use HTTPS outside localhost`)
    }
  }

  private randomToken(bytes: number): string {
    const data = crypto.getRandomValues(new Uint8Array(bytes))
    return this.base64Url(data)
  }

  private base64Url(data: Uint8Array): string {
    let binary = ''
    for (const byte of data) binary += String.fromCharCode(byte)
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  }

  private fromBase64Url(value: string): Uint8Array {
    if (!/^[A-Za-z0-9_-]+$/.test(value)) throw new OIDCProtocolError('IAM returned malformed base64url data')
    const binary = atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4))
    return Uint8Array.from(binary, char => char.charCodeAt(0))
  }

  private decodeText(value: string): string {
    return new TextDecoder('utf-8', { fatal: true }).decode(this.fromBase64Url(value))
  }

  private constantTimeEqual(left: string, right: string): boolean {
    // Compare equal-length UTF-8 buffers without data-dependent early exit.
    const a = encoder.encode(left)
    const b = encoder.encode(right)
    let diff = a.length ^ b.length
    const length = Math.max(a.length, b.length)
    for (let i = 0; i < length; i++) diff |= (a[i] ?? 0) ^ (b[i] ?? 0)
    return diff === 0
  }

  private requiredString(value: unknown, label: string): string {
    if (typeof value !== 'string' || !value) throw new OIDCProtocolError(`IAM response has no valid ${label}`)
    return value
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
  }
}
