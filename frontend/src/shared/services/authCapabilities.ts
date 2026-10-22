/** 公开认证页能力：邮件找回与管理台绑定的 ToC 注册 client（不含密钥）。 */

export type PublicRegistrationCapabilities = {
  available: boolean
  resend_cooldown_seconds: number
  terms_url: string
  privacy_url: string
  terms_version: string
  privacy_version: string
}

export type ConsoleRegistrationContext = {
  client_id: string
  application_name: string
  registration: PublicRegistrationCapabilities
}

export type AuthPublicCapabilities = {
  password_reset_available: boolean
  console_registration: ConsoleRegistrationContext | null
}

export async function fetchAuthPublicCapabilities(): Promise<AuthPublicCapabilities> {
  return apiJson<AuthPublicCapabilities>('/auth/public-capabilities')
}

async function apiJson<T>(path: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error('暂时无法读取认证服务配置')
  }
  return response.json() as Promise<T>
}
