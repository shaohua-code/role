/** Express thin adapter over the IAM authorization client; structural types only, zero runtime dependency.
 *
 * 边界与 Python 侧 `iam_fastapi.py`（P316）对称：OIDC 验签与会话管理由业务方完成
 * （可用 IamOIDCClient），本适配层只负责授权判定的中间件注入、权限别名映射、
 * owner 行级过滤校验和统一错误映射；它不验签 token、不读取请求参数中的身份。
 *
 * 推荐用法：
 *
 *   const iam = createIamExpress({
 *     client: new IamAuthorizationClient(IAM_API_URL, IAM_APPLICATION_ID),
 *     loadSession: (req) => loadVerifiedSession(req),   // 业务方从已验签 OIDC 会话构建；缺失时抛带 status 的错误
 *     permissionMap: { 'document.read': 'crm.document.read' },
 *     localUserIdResolver: (user) => identityRepo.getLocalUserId(user.iamSubject, user.tenantId),
 *   })
 *
 *   app.get('/documents/:id', iam.requirePermission('document.read', { ownerOnly: true }), (req, res) => {
 *     // req.iamUser.localUserId 可直接用于 owner 过滤查询。
 *   })
 */
// type-only import：Node strip-types 直接擦除（不解析 .js 后缀），tsc 保留类型检查。
import type { AuthorizationDecision, IamAuthorizationClient } from './authorization.js'

/** 业务方从已验签 OIDC 会话构建的可信身份上下文；任何字段都不接受浏览器请求参数。 */
export interface IAMSessionContext {
  accessToken: string
  tenantId: string
  /** IAM token 的 sub；与产品本地用户主键是两种不同标识。 */
  iamSubject: string
}

/** 最小请求结构；兼容 Express 4/5 的 Request（只依赖 headers）。 */
export interface IAMAdapterRequest {
  headers: Record<string, string | string[] | undefined>
}

/** 最小响应结构；兼容 Express 的 Response（只依赖 status().json() 链）。 */
export interface IAMAdapterResponse {
  status(code: number): { json(body: unknown): unknown }
}

export type IAMAdapterNext = (err?: unknown) => void

export type IAMMiddleware = (req: IAMAdapterRequest, res: IAMAdapterResponse, next: IAMAdapterNext) => void | Promise<void>

/** 业务方提供的会话加载器：从已验签会话构建 IAMSessionContext；缺失时抛带 status 属性的错误。 */
export type IAMSessionLoader = (req: IAMAdapterRequest) => IAMSessionContext | Promise<IAMSessionContext>

export interface IAMExpressOptions {
  client: IamAuthorizationClient
  loadSession: IAMSessionLoader
  /** 短别名 → 稳定权限码的登记表；未登记别名在创建中间件时即抛错，SDK 不猜测映射。 */
  permissionMap?: Record<string, string>
  /** ownerOnly 时把已验签 IAM subject 解析为产品本地用户主键；解析为空按映射服务故障 503 处理。 */
  localUserIdResolver?: (user: IAMSessionContext) => string | Promise<string>
}

export interface IAMRequirePermissionOptions {
  ownerOnly?: boolean
}

export function createIamExpress(options: IAMExpressOptions): {
  requirePermission: (alias: string, middlewareOptions?: IAMRequirePermissionOptions) => IAMMiddleware
  currentUser: () => IAMMiddleware
} {
  const permissionMap = options.permissionMap ?? {}
  const localUserIdResolver = options.localUserIdResolver

  const currentUser = (): IAMMiddleware => {
    return async (req, _res, next) => {
      try {
        const user = await options.loadSession(req)
        ;(req as IAMAdapterRequest & { iamUser?: IAMSessionContext }).iamUser = user
        next()
      } catch (error) {
        // 会话缺失/无效属于业务方语义（通常 401），原样交给业务方错误处理。
        next(error)
      }
    }
  }

  const requirePermission = (alias: string, middlewareOptions?: IAMRequirePermissionOptions): IAMMiddleware => {
    const ownerOnly = middlewareOptions?.ownerOnly === true
    const code = permissionMap[alias]
    if (!code || typeof code !== 'string') {
      // fail closed：未登记的别名在路由注册时立即抛出，绝不退化为放行或猜测映射。
      throw new Error(`Permission alias '${alias}' is not registered in the application permission map`)
    }
    if (ownerOnly && !localUserIdResolver) {
      throw new Error('ownerOnly requires localUserIdResolver to map the verified IAM subject to the product local user key')
    }

    return async (req, res, next) => {
      let user: IAMSessionContext
      try {
        user = await options.loadSession(req)
      } catch (error) {
        next(error)
        return
      }
      let decision: AuthorizationDecision
      try {
        if (ownerOnly) {
          decision = await options.client.check(user.accessToken, {
            tenantId: user.tenantId,
            userSubject: user.iamSubject,
            permissionCode: code,
            includeDataScope: true,
          })
          // any_of 是 OR 语义：任何 tenant/organizations 分支都会放宽到非本人范围，必须整体拒绝。
          if (!isOwnerOnlyScope(decision, user.iamSubject)) {
            respond(res, 403, 'Permission denied: owner scope required')
            return
          }
        } else {
          decision = await options.client.require(user.accessToken, {
            tenantId: user.tenantId,
            permissionCode: code,
          })
        }
      } catch (error) {
        respondAuthorizationError(res, error)
        return
      }
      if (ownerOnly) {
        let localUserId: string
        try {
          localUserId = await localUserIdResolver!(user)
        } catch {
          // 本地身份映射故障必须终止请求，且不能透出仓储异常原文。
          respond(res, 503, 'Business identity mapping service is unavailable')
          return
        }
        if (typeof localUserId !== 'string' || localUserId.length === 0) {
          respond(res, 503, 'Business identity mapping service is unavailable')
          return
        }
        ;(req as IAMAdapterRequest & { iamUser?: IAMSessionContext & { localUserId?: string } }).iamUser = {
          ...user,
          localUserId,
        }
      } else {
        ;(req as IAMAdapterRequest & { iamUser?: IAMSessionContext }).iamUser = user
      }
      ;(req as IAMAdapterRequest & { iamDecision?: AuthorizationDecision }).iamDecision = decision
      next()
    }
  }

  return { requirePermission, currentUser }
}

function isOwnerOnlyScope(decision: AuthorizationDecision, iamSubject: string): boolean {
  if (!decision.allowed || !decision.data_scope || decision.data_scope.mode !== 'any_of') return false
  const constraints = decision.data_scope.constraints
  if (!Array.isArray(constraints) || constraints.length === 0) return false
  return constraints.every((constraint) =>
    constraint.kind === 'owner' && constraint.field === 'owner_user_id' && constraint.user_id === iamSubject)
}

function respond(res: IAMAdapterResponse, statusCode: number, detail: string): void {
  res.status(statusCode).json({ detail })
}

function respondAuthorizationError(res: IAMAdapterResponse, error: unknown): void {
  // IAM 拒绝/不可用直接映射为 HTTP 响应（403/503 保留语义，其余契约错误归一 502）；
  // 调用方按拒绝处理，网络故障永远不等于允许。
  const statusCode = typeof (error as { statusCode?: unknown })?.statusCode === 'number'
    ? (error as { statusCode: number }).statusCode
    : 502
  const normalized = statusCode === 403 || statusCode === 503 || statusCode === 422 ? statusCode : 502
  const message = error instanceof Error ? error.message : 'IAM rejected the authorization request'
  respond(res, normalized, message)
}
