/** 集中处理 IAM API 地址、短期令牌和统一错误提示，页面不直接拼接请求。 */
const API_BASE = '/api/v1'
const TOKEN_KEY = 'iam-access-token'
const REFRESH_LOCK_NAME = 'iam-management-session-refresh'
const SESSION_CHANNEL_NAME = 'iam-management-session'
const sessionChannel = typeof BroadcastChannel === 'undefined'
  ? null
  : new BroadcastChannel(SESSION_CHANNEL_NAME)

// 一个页面内的并行请求共用同一次续期；Web Locks 再协调同源的多个标签页。
// 服务端 refresh token 是一次性轮换的，若多个 401 同时各自续期，会让后到的请求拿旧 Cookie 撞上已撤销记录。
let refreshInFlight: Promise<string | null> | null = null

// 管理刷新 Cookie 是浏览器级共享的；退出或会话失效时清掉同源其他标签页的 access token，
// 避免它们在 JWT 到期前继续显示已退出的管理界面。消息里不传令牌或用户资料。
sessionChannel?.addEventListener('message', (event: MessageEvent<unknown>) => {
  const message = event.data as { type?: string } | null
  if (message?.type !== 'signed-out') return
  sessionStorage.removeItem(TOKEN_KEY)
  window.dispatchEvent(new Event('iam:unauthorized'))
})

/** 将 HTTP 状态码保留给需要针对冲突做恢复的管理功能，同时兼容既有 Error 提示。 */
export class ApiRequestError extends Error {
  constructor(message: string, readonly status: number, readonly retryAfterSeconds: number | null = null) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

interface ApiErrorDetailItem {
  loc?: unknown[]
  msg?: string
}

/** FastAPI 422 的 detail 是数组（loc/msg 对象），字符串化后才能在 Toast 中可读展示。 */
function extractErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      const entry = item as ApiErrorDetailItem
      const field = Array.isArray(entry.loc)
        ? entry.loc.filter((part) => part !== 'body').join('.')
        : ''
      const msg = typeof entry.msg === 'string' ? entry.msg : ''
      if (field && msg) return `${field}: ${msg}`
      return msg || JSON.stringify(item)
    }).filter(Boolean)
    if (parts.length) return `请求校验失败：${parts.join('；')}`
  }
  return `请求失败（${status}）`
}

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) sessionStorage.setItem(TOKEN_KEY, token)
  else {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionChannel?.postMessage({ type: 'signed-out' })
  }
}

async function send(path: string, init: RequestInit, token: string | null): Promise<Response> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  else headers.delete('Authorization')
  return fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'same-origin' })
}

async function refreshAccessToken(failedToken: string): Promise<string | null> {
  if (!refreshInFlight) {
    const refresh = async (): Promise<string | null> => {
      // 等跨标签页锁期间，当前页可能已从其他请求得到更新后的访问令牌。
      const latestToken = getToken()
      if (latestToken && latestToken !== failedToken) return latestToken

      const response = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'same-origin' })
      if (!response.ok) return null
      const session = await response.json() as { access_token?: string }
      if (!session.access_token) return null
      setToken(session.access_token)
      return session.access_token
    }

    const lockManager = typeof navigator === 'undefined' ? undefined : navigator.locks
    const work = lockManager
      ? lockManager.request(REFRESH_LOCK_NAME, refresh)
      : refresh()
    refreshInFlight = work.catch(() => null).finally(() => { refreshInFlight = null })
  }
  return refreshInFlight
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let token = getToken()
  let response = await send(path, init, token)

  // access JWT 短期有效；接口返回 401 时先用 HttpOnly Cookie 原子轮换 refresh token，再重放原请求一次。
  const refreshExcluded = ['/auth/login', '/auth/register', '/auth/register/verify', '/auth/refresh'].includes(path)
  if (response.status === 401 && token && !refreshExcluded) {
    const refreshedToken = await refreshAccessToken(token)
    if (refreshedToken) {
      token = refreshedToken
      response = await send(path, init, token)
    }
  }
  if (!response.ok) {
    const result = await response.json().catch(() => null) as { detail?: unknown } | null
    if (response.status === 401) {
      setToken(null)
      window.dispatchEvent(new Event('iam:unauthorized'))
    }
    const retryHeader = Number(response.headers.get('Retry-After'))
    const retryAfterSeconds = Number.isFinite(retryHeader) && retryHeader > 0 ? Math.ceil(retryHeader) : null
    throw new ApiRequestError(extractErrorMessage(result?.detail, response.status), response.status, retryAfterSeconds)
  }
  if (response.status === 204) return undefined as T
  return await response.json() as T
}

export interface AdminOverview {
  tenants: number
  applications: number
  users: number
  roles: number
  models: number
  recent_audits: number
}
