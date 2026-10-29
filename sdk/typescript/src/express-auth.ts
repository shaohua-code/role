/** Express OIDC login-route plugin; structural types only, zero runtime dependency.
 *
 * 与 Python 侧 `iam_fastapi_auth.py`（P318）对称：`mountOidcAuth` 一次挂载
 * login/callback/logout/me 四条路由。登录 attempt 与身份令牌只保存在业务方提供的
 * **服务端** SessionStore 中，浏览器仅持一次性 HttpOnly attempt Cookie 与会话 Cookie。
 * CSRF 防护与代理访问日志脱敏仍由业务方负责。
 *
 * 推荐用法：
 *
 *   import { IamOIDCClient } from './oidc.js'
 *   import { InMemoryIamSessionStore, mountOidcAuth } from './express-auth.js'
 *
 *   mountOidcAuth(app, {
 *     oidcClient: new IamOIDCClient({ issuer, clientId, clientSecret, redirectUri }),
 *     sessionStore: new InMemoryIamSessionStore(), // 生产应替换为 Redis/数据库实现
 *     options: { postLoginRedirect: '/' },
 *   })
 */
import type { IamOIDCClient } from './oidc.js'

/** Web Crypto 生成 URL-safe 随机标识；与包内其余模块一致，不引入 Node 专属类型。 */
function randomToken(): string {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** 业务方实现的服务端会话存储协议；生产环境应使用 Redis/数据库并加密落盘。 */
export interface IAMAuthSessionStore {
  put(key: string, value: Record<string, unknown>, ttlSeconds: number): void
  load(key: string): Record<string, unknown> | null
  /** 原子取出并删除；用于一次性 attempt，重复消费必须失败。 */
  take(key: string): Record<string, unknown> | null
  delete(key: string): void
}

/** 线程安全的进程内存储；仅用于本地开发与测试，不提供跨实例共享或持久化。 */
export class InMemoryIamSessionStore implements IAMAuthSessionStore {
  private readonly entries = new Map<string, { value: Record<string, unknown>; expiresAt: number }>()

  put(key: string, value: Record<string, unknown>, ttlSeconds: number): void {
    this.purgeExpired()
    this.entries.set(key, { value: { ...value }, expiresAt: Date.now() + Math.max(1, Math.floor(ttlSeconds)) * 1000 })
  }

  load(key: string): Record<string, unknown> | null {
    this.purgeExpired()
    const entry = this.entries.get(key)
    return entry ? { ...entry.value } : null
  }

  take(key: string): Record<string, unknown> | null {
    this.purgeExpired()
    const entry = this.entries.get(key)
    if (!entry) return null
    this.entries.delete(key)
    return { ...entry.value }
  }

  delete(key: string): void {
    this.entries.delete(key)
  }

  private purgeExpired(): void {
    const now = Date.now()
    for (const key of this.entries.keys()) {
      if ((this.entries.get(key)?.expiresAt ?? 0) <= now) this.entries.delete(key)
    }
  }
}

export interface OidcRouteOptions {
  cookieName?: string
  attemptCookieName?: string
  sessionTtlSeconds?: number
  attemptTtlSeconds?: number
  loginPath?: string
  callbackPath?: string
  logoutPath?: string
  mePath?: string
  postLoginRedirect?: string
  postLogoutRedirect?: string | null
  cookieSecure?: boolean
  cookieDomain?: string | null
  scopes?: string[]
}

/** 最小请求结构；兼容 Express 4/5 的 Request（cookies 由适配器自行解析，不依赖 cookie-parser）。 */
export interface IAMAuthRequest {
  headers: Record<string, string | string[] | undefined>
  protocol?: string
  hostname?: string
  originalUrl?: string
}

export interface IAMAuthCookieOptions {
  httpOnly?: boolean
  sameSite?: 'lax' | 'strict' | 'none'
  secure?: boolean
  domain?: string | null
  maxAge?: number
  path?: string
}

/** 最小响应结构；兼容 Express 的 Response。 */
export interface IAMAuthResponse {
  cookie(name: string, value: string, options?: IAMAuthCookieOptions): unknown
  clearCookie(name: string, options?: IAMAuthCookieOptions): unknown
  redirect(url: string): unknown
  status(code: number): { json(body: unknown): unknown }
}

export interface IAMAuthApp {
  get(path: string, handler: (req: IAMAuthRequest, res: IAMAuthResponse) => void | Promise<void>): unknown
}

interface MountedOidcClient {
  createAuthorizationRequest(scopes?: string[]): Promise<{ authorizationUrl: string; state: string; nonce: string; codeVerifier: string; scopes: string[] }>
  completeLogin(callbackUrl: string, attempt: { authorizationUrl: string; state: string; nonce: string; codeVerifier: string; scopes: string[] }): Promise<{ subject: string; tenantId: string; profile: Record<string, unknown>; tokens: Record<string, unknown> }>
  revokeRefreshToken(refreshToken: string): Promise<void>
  revokeAccessToken(accessToken: string): Promise<void>
}

const ATTEMPT_COOKIE = 'iam_attempt'

function attemptKey(attemptId: string): string {
  return `attempt:${attemptId}`
}

function sessionKey(sessionId: string): string {
  return `session:${sessionId}`
}

function parseCookies(header: string | string[] | undefined): Record<string, string> {
  const raw = Array.isArray(header) ? header[0] : header
  const cookies: Record<string, string> = {}
  if (!raw) return cookies
  for (const pair of raw.split(';')) {
    const index = pair.indexOf('=')
    if (index <= 0) continue
    const name = pair.slice(0, index).trim()
    if (!name) continue
    try {
      cookies[name] = decodeURIComponent(pair.slice(index + 1).trim())
    } catch {
      cookies[name] = pair.slice(index + 1).trim()
    }
  }
  return cookies
}

function isOidcProtocolError(error: unknown): boolean {
  // 鸭子判别而非 instanceof：避免 src 内跨文件运行时 import（与 strip-types 兼容）。
  return error instanceof Error && error.name === 'OIDCProtocolError'
}

export function mountOidcAuth(
  app: IAMAuthApp,
  options: {
    oidcClient: IamOIDCClient | MountedOidcClient
    sessionStore: IAMAuthSessionStore
    routeOptions?: OidcRouteOptions
  },
): void {
  const oidcClient = options.oidcClient as MountedOidcClient
  const store = options.sessionStore
  const config = options.routeOptions ?? {}
  const cookieName = config.cookieName ?? 'iam_session'
  const sessionTtlSeconds = config.sessionTtlSeconds ?? 8 * 3600
  const attemptTtlSeconds = config.attemptTtlSeconds ?? 600
  const postLoginRedirect = config.postLoginRedirect ?? '/'
  const cookieBase: IAMAuthCookieOptions = {
    httpOnly: true,
    sameSite: 'lax',
    secure: config.cookieSecure ?? false,
    domain: config.cookieDomain ?? undefined,
    path: '/',
  }

  app.get(config.loginPath ?? '/auth/login', async (_req, res) => {
    const attempt = await oidcClient.createAuthorizationRequest(config.scopes ?? ['openid', 'profile', 'email'])
    const attemptId = randomToken()
    store.put(attemptKey(attemptId), { ...attempt }, attemptTtlSeconds)
    res.cookie(ATTEMPT_COOKIE, attemptId, { ...cookieBase, maxAge: attemptTtlSeconds * 1000 })
    res.redirect(attempt.authorizationUrl)
  })

  app.get(config.callbackPath ?? '/auth/callback', async (req, res) => {
    const attemptId = parseCookies(req.headers.cookie)[ATTEMPT_COOKIE] ?? ''
    // 无 attempt Cookie 意味着流程未从 /auth/login 发起或已被消费，直接拒绝。
    if (!attemptId) return respond(res, 403, 'OIDC login attempt missing or expired')
    const rawAttempt = store.take(attemptKey(attemptId))
    if (!rawAttempt) return respond(res, 403, 'OIDC login attempt missing or expired')
    const protocol = req.protocol ?? 'http'
    const hostname = req.hostname ?? ''
    const callbackUrl = `${protocol}://${hostname}${req.originalUrl ?? ''}`
    let identity: { subject: string; tenantId: string; profile: Record<string, unknown>; tokens: Record<string, unknown> }
    try {
      identity = await oidcClient.completeLogin(callbackUrl, {
        authorizationUrl: String(rawAttempt.authorizationUrl),
        state: String(rawAttempt.state),
        nonce: String(rawAttempt.nonce),
        codeVerifier: String(rawAttempt.codeVerifier),
        scopes: Array.isArray(rawAttempt.scopes) ? (rawAttempt.scopes as string[]) : [],
      })
    } catch (error) {
      if (isOidcProtocolError(error)) {
        // 不把 Provider 拒绝细节透给浏览器；完整原因留在服务端日志（由业务方记录）。
        return respond(res, 403, 'OIDC login failed')
      }
      throw error
    }
    const sessionId = randomToken()
    store.put(sessionKey(sessionId), { ...identity }, sessionTtlSeconds)
    res.cookie(cookieName, sessionId, { ...cookieBase, maxAge: sessionTtlSeconds * 1000 })
    res.clearCookie(ATTEMPT_COOKIE, { path: '/' })
    res.redirect(postLoginRedirect)
  })

  app.get(config.mePath ?? '/auth/me', async (req, res) => {
    const sessionId = parseCookies(req.headers.cookie)[cookieName] ?? ''
    const identity = sessionId ? store.load(sessionKey(sessionId)) : null
    if (!identity) return respond(res, 401, 'No active session')
    // 绝不返回 tokens；profile 只含 IdP 发布的展示声明。
    res.status(200).json({
      subject: identity.subject,
      tenantId: identity.tenantId,
      profile: identity.profile ?? {},
    })
  })

  app.get(config.logoutPath ?? '/auth/logout', async (req, res) => {
    const sessionId = parseCookies(req.headers.cookie)[cookieName] ?? ''
    const identity = sessionId ? store.take(sessionKey(sessionId)) : null
    if (identity) {
      const tokens = (identity.tokens ?? {}) as { accessToken?: string; refreshToken?: string }
      // 撤销失败不阻断本地登出；本地会话清理优先，撤销按 best-effort 幂等执行。
      try {
        if (tokens.refreshToken) await oidcClient.revokeRefreshToken(tokens.refreshToken)
        if (tokens.accessToken) await oidcClient.revokeAccessToken(tokens.accessToken)
      } catch (error) {
        if (!isOidcProtocolError(error)) throw error
      }
    }
    res.clearCookie(cookieName, { path: '/' })
    if (config.postLogoutRedirect) res.redirect(config.postLogoutRedirect)
    else res.status(200).json({ ok: true })
  })
}

function respond(res: IAMAuthResponse, statusCode: number, detail: string): void {
  res.status(statusCode).json({ detail })
}
