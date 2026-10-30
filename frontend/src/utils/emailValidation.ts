/** 邮箱域名前端校验：与服务端 EmailStr（email-validator）的特殊用途顶级域口径对齐。 */

// 服务端拒绝特殊用途顶级域；example.com 等保留主机名服务端接受，这里不拦。
const RESERVED_EMAIL_TLD = /\.(?:test|example|invalid|localhost|local|onion)$/i

/** 判断邮箱（或裸域名）是否使用服务端不接受的保留顶级域。 */
export function isReservedEmailHost(emailOrHost: string): boolean {
  const host = String(emailOrHost || '').trim().toLowerCase().split('@')[1] || String(emailOrHost || '').trim().toLowerCase()
  return Boolean(host) && RESERVED_EMAIL_TLD.test(host)
}

/** antd 表单 validator 形式的保留域校验；与既有 type: 'email' 规则叠加使用。 */
export function validateReservedEmailDomain(_rule: unknown, value: string): Promise<void> {
  if (isReservedEmailHost(value)) {
    return Promise.reject('该邮箱使用保留顶级域（如 .test/.localhost），服务端不接受；请改用真实域名')
  }
  return Promise.resolve()
}
