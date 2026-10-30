export interface HealthResponse {
  status: string
  service: string
}

/** 将 API 存活与业务依赖就绪区分开，供管理台展示可操作的服务状态。 */
export class ReadinessError extends Error {
  constructor(readonly statusCode: number, readonly reason: string) {
    super(`就绪检查失败（${reason}）`)
    this.name = 'ReadinessError'
  }
}

/** 只在数据库与当前 Alembic heads 匹配时报告服务就绪。 */
export async function getReadiness(): Promise<HealthResponse> {
  // 健康状态探测有短超时，网络悬挂时不无限占用页面初始化请求。
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 5_000)
  let response: Response
  try {
    response = await fetch('/api/v1/ready', { cache: 'no-store', signal: controller.signal })
  } finally {
    window.clearTimeout(timeout)
  }
  if (!response.ok) {
    // 只读取 FastAPI 的稳定错误码，不把连接地址或内部错误回显到控制台 UI。
    const body: unknown = await response.json().catch(() => null)
    const reason = typeof body === 'object' && body !== null
      && 'detail' in body && typeof body.detail === 'string'
      ? body.detail
      : `http_${response.status}`
    throw new ReadinessError(response.status, reason)
  }
  return response.json() as Promise<HealthResponse>
}
