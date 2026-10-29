"""FastAPI thin adapter over the IAM authorization client.

边界（与技术架构与接入.md 第 3 节一致）：OIDC 验签与会话管理由业务方完成
（可用 iam_oidc），本适配层只负责授权判定的依赖注入、权限别名映射、
owner 行级过滤校验和统一错误映射；它不验签 token、不连接业务数据库。

推荐用法：

    from fastapi import Depends, FastAPI
    from iam_fastapi import IAMUserContext, IAMFastAPI

    def load_session(request: Request) -> IAMUserContext:
        # 从业务方已验签的 OIDC 会话构建；缺失时抛 401。
        ...

    iam = IAMFastAPI(
        client=IamAuthorizationClient(IAM_API_URL, application_id=IAM_APP_ID),
        session_dependency=load_session,
        permission_map={"document.read": "crm.document.read"},
        local_user_id_resolver=lambda user: identity_repo.local_user_id(user.subject_id, user.tenant_id),
    )

    @app.get("/documents/{document_id}")
    def read_documents(user: IAMUserContext = Depends(iam.require_permission("document.read", owner_only=True))):
        # user.local_user_id 可直接用于 owner 过滤查询。
        ...

    # 管理台 / 粗粒度入口主推角色门禁（会话需带 role_keys）：
    # Depends(iam.require_roles("app.member", "app.admin"))
"""
from dataclasses import dataclass
from typing import Annotated, Callable, Mapping

from fastapi import Depends, HTTPException, Request

from iam_authorization import AuthorizationDecision, AuthorizationServiceError, IamAuthorizationClient


@dataclass(frozen=True)
class IAMUserContext:
    """业务方从已验签 OIDC 会话构建的可信身份上下文；任何字段都不接受浏览器请求参数。"""

    access_token: str
    tenant_id: str
    subject_id: str
    local_user_id: str | None = None
    # 有效角色 key（来自 /auth/me.roles 或本地映射）；管理台/粗粒度业务门禁用 require_roles。
    role_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class PermissionDecision:
    """require_permission 依赖的返回值：判定结果与其使用的可信用户上下文。"""

    decision: AuthorizationDecision
    user: IAMUserContext


class IAMFastAPI:
    """把 IamAuthorizationClient 暴露为 FastAPI 依赖；所有失败路径都 fail closed。"""

    def __init__(
        self,
        client: IamAuthorizationClient,
        session_dependency: Callable[..., IAMUserContext],
        permission_map: Mapping[str, str] | None = None,
        local_user_id_resolver: Callable[[IAMUserContext], str] | None = None,
    ) -> None:
        self.client = client
        self.permission_map = dict(permission_map or {})
        self.local_user_id_resolver = local_user_id_resolver
        # 会话依赖由业务方提供；SDK 绝不从请求头猜测 tenant/subject。
        self._session_dependency = session_dependency

    def current_user(self) -> Callable[..., IAMUserContext]:
        """返回当前可信用户上下文的依赖函数（配合 Depends 使用）；会话缺失由业务方依赖抛 401。"""
        return self._session_dependency

    def require_permission(self, alias: str, *, owner_only: bool = False) -> Callable[..., PermissionDecision]:
        """构建授权依赖函数（配合 Depends 使用）；owner_only 时强制所有分支都是本人 owner 约束。

        alias 必须已在 permission_map 登记；未登记别名属于配置错误（构造依赖时即抛
        LookupError，fail closed），SDK 不按字符串猜测稳定权限码。同步 client 调用放在
        非 async 依赖中，由 FastAPI 调度到线程池，避免阻塞事件循环。
        """
        code = self.permission_map.get(alias)
        if not code or not isinstance(code, str):
            # fail closed：未登记的别名立即拒绝，绝不退化为放行或猜测映射。
            raise LookupError(
                f"Permission alias '{alias}' is not registered in the application permission map"
            )
        if owner_only and self.local_user_id_resolver is None:
            raise LookupError(
                "owner_only requires local_user_id_resolver to map the verified IAM subject "
                "to the product's local user primary key"
            )

        def dependency(user: Annotated[IAMUserContext, Depends(self._session_dependency)]) -> PermissionDecision:
            try:
                if owner_only:
                    decision = self.client.check(
                        user.access_token,
                        user.tenant_id,
                        code,
                        include_data_scope=True,
                        subject_id=user.subject_id,
                    )
                    # any_of 是 OR 语义：任何 tenant/organizations 分支都会放宽到非本人范围，必须整体拒绝。
                    _require_owner_only_scope(decision, user)
                    resolved = self.local_user_id_resolver(user)
                    if not isinstance(resolved, str) or not resolved:
                        raise AuthorizationServiceError(503, "Business identity mapping service is unavailable")
                    user = IAMUserContext(
                        access_token=user.access_token,
                        tenant_id=user.tenant_id,
                        subject_id=user.subject_id,
                        local_user_id=resolved,
                    )
                else:
                    decision = self.client.require(user.access_token, user.tenant_id, code)
            except AuthorizationServiceError as exc:
                raise _http_error(exc) from None
            return PermissionDecision(decision, user)

        return dependency

    def require_roles(self, *role_keys: str) -> Callable[..., IAMUserContext]:
        """主推：按角色 key 门禁（管理台/粗粒度业务入口）。

        会话依赖须填充 IAMUserContext.role_keys（例如登录后拉 /auth/me.roles）。
        细粒度资源授权仍用 require_permission + data_scope。
        """
        if not role_keys:
            raise ValueError("require_roles requires at least one role key")
        wanted = set(role_keys)

        def dependency(user: Annotated[IAMUserContext, Depends(self._session_dependency)]) -> IAMUserContext:
            held = set(user.role_keys or ())
            if held.isdisjoint(wanted):
                raise HTTPException(status_code=403, detail=f"Missing required role: {', '.join(role_keys)}")
            return user

        return dependency


def _require_owner_only_scope(decision: AuthorizationDecision, user: IAMUserContext) -> None:
    """owner_only 语义：allowed 且每个 any_of 分支都必须是绑定已验签 subject 的 owner 约束。"""
    scope = decision.data_scope
    if not decision.allowed or not scope or scope.get("mode") != "any_of":
        raise AuthorizationServiceError(403, "Permission denied: owner scope required")
    constraints = scope.get("constraints")
    if not isinstance(constraints, list) or not constraints:
        raise AuthorizationServiceError(403, "Permission denied: owner scope required")
    for constraint in constraints:
        if (not isinstance(constraint, dict)
                or constraint.get("kind") != "owner"
                or constraint.get("field") != "owner_user_id"
                or constraint.get("user_id") != user.subject_id):
            raise AuthorizationServiceError(403, "Permission denied: owner scope required")


def _http_error(exc: AuthorizationServiceError) -> HTTPException:
    """把 SDK 错误映射为 HTTP 状态；403/503 保留语义，其余契约错误归一为 502。"""
    if exc.status_code in (401, 403, 503):
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    return HTTPException(status_code=502, detail="IAM returned an invalid authorization response")
