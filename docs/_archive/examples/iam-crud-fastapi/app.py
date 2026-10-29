"""IAM 多项目接入最小 CRUD 示例（FastAPI）。

把以下 SDK 组件串成完整接入路径（对应技术架构与接入.md 第 3 节）：

- P318 `mount_oidc_auth`：自动挂载 login/callback/logout/me，OIDC 流程零业务代码
- P316 `IAMFastAPI`：`require_permission` / `current_user` 授权依赖注入
- P315 `check_batch`：一次判定菜单/按钮权限快照（展示用，执行仍逐次在线判权）
- `SessionStore`：attempt 与令牌只存服务端（生产替换为 Redis/数据库）

运行前提（真实联调）：
1. 本地 IAM 平台运行中（docker compose up），并登记一个 application（callback =
   `http://localhost:8000/auth/callback`），为角色显式授予 `crud.document.*` 权限码。
2. 环境变量：IAM_API_URL / IAM_APPLICATION_ID / IAM_ISSUER / IAM_CLIENT_ID /
   IAM_CLIENT_SECRET / IAM_REDIRECT_URI。
3. `pip install -e "sdk/python[fastapi,oidc]"` 后 `uvicorn app:app --port 8000`。

生产替换点见本目录 README。
"""
import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from iam_authorization import IamAuthorizationClient
from iam_fastapi import IAMFastAPI, IAMUserContext
from iam_fastapi_auth import InMemorySessionStore, mount_oidc_auth
from iam_oidc import IamOIDCClient

# 应用权限别名 → 稳定权限码；必须在 IAM 权限目录登记并显式授予角色。
PERMISSION_MAP = {
    "document.read": "crud.document.read",
    "document.create": "crud.document.create",
    "document.delete": "crud.document.delete",
}
MENU_CODES = list(PERMISSION_MAP.values())

# 内存文档仓储；生产替换为真实数据库并保留 owner 过滤谓词。
# documents[document_id] = {"owner_subject": <IAM subject>, "title": str}


def create_app(
    oidc_client: Any = None,
    authorization_client: Any = None,
    documents: dict[str, dict[str, Any]] | None = None,
) -> FastAPI:
    """组装示例应用；client 参数仅供测试注入 mock，生产走环境变量构造。"""
    documents = documents if documents is not None else {}
    store = InMemorySessionStore()
    app = FastAPI(title="IAM CRUD example")

    oidc = oidc_client or IamOIDCClient(
        issuer=os.environ["IAM_ISSUER"],
        client_id=os.environ["IAM_CLIENT_ID"],
        client_secret=os.environ["IAM_CLIENT_SECRET"],
        redirect_uri=os.environ["IAM_REDIRECT_URI"],
    )
    mount_oidc_auth(app, oidc_client=oidc, session_store=store)

    def load_verified_session(request: Request) -> IAMUserContext:
        """从 mount_oidc_auth 写入的服务端会话构建可信上下文；无会话即 401。

        生产提示：access_token 来自会话中的 IAM 令牌；令牌过期时先走
        `IamOIDCClient.refresh` 再进入业务路由。
        """
        session_id = request.cookies.get("iam_session", "")
        identity = store.load(f"session:{session_id}") if session_id else None
        if not identity:
            raise HTTPException(status_code=401, detail="No active session")
        tokens = identity.get("tokens", {})
        return IAMUserContext(
            access_token=str(tokens.get("access_token", "")),
            tenant_id=str(identity["tenant_id"]),
            subject_id=str(identity["subject"]),
        )

    iam = IAMFastAPI(
        client=authorization_client or IamAuthorizationClient(
            os.environ["IAM_API_URL"], application_id=os.environ["IAM_APPLICATION_ID"],
        ),
        session_dependency=load_verified_session,
        permission_map=PERMISSION_MAP,
        # 示例把 IAM subject 直接当本地主键；生产必须经本地身份映射表解析。
        local_user_id_resolver=lambda user: user.subject_id,
    )

    class DocumentInput(BaseModel):
        title: str

    @app.get("/me/permissions")
    def permission_snapshot(
        user: IAMUserContext = Depends(iam.current_user()),
    ) -> Any:
        """菜单/按钮权限快照：一次批量判定（P315）；执行操作时后端仍逐次在线判权。"""
        decisions = iam.client.check_batch(user.access_token, user.tenant_id, MENU_CODES)
        return {
            "permissions": {
                alias: decisions[code].allowed
                for alias, code in PERMISSION_MAP.items()
            },
        }

    @app.post("/documents", status_code=201)
    def create_document(
        payload: DocumentInput,
        user: IAMUserContext = Depends(iam.current_user()),
        _permission: Any = Depends(iam.require_permission("document.create")),
    ) -> Any:
        # 创建只需动作权限（无 data scope）；owner 记为已验签 subject。
        # 生产中若本地主键 ≠ subject，请经本地身份映射表解析后再落库。
        document_id = f"doc-{len(documents) + 1}"
        documents[document_id] = {
            "owner_subject": user.subject_id,
            "title": payload.title,
        }
        return {"id": document_id, "title": payload.title}

    @app.get("/documents")
    def list_documents(
        permission: Any = Depends(iam.require_permission("document.read", owner_only=True)),
    ) -> Any:
        # owner_only 已校验 data scope 是本人行级约束；local_user_id 用于仓储过滤。
        user = permission.user
        mine = {
            document_id: document
            for document_id, document in documents.items()
            if document["owner_subject"] == user.local_user_id
        }
        return {"documents": mine}

    @app.get("/documents/{document_id}")
    def get_document(
        document_id: str,
        permission: Any = Depends(iam.require_permission("document.read", owner_only=True)),
    ) -> Any:
        user = permission.user
        document = documents.get(document_id)
        # 越权访问表现为 404：owner 过滤先行，不泄露他人资源存在性。
        if not document or document["owner_subject"] != user.local_user_id:
            raise HTTPException(status_code=404, detail="Document not found")
        return document

    @app.delete("/documents/{document_id}", status_code=204)
    def delete_document(
        document_id: str,
        permission: Any = Depends(iam.require_permission("document.delete", owner_only=True)),
    ):
        # 204 无响应体；越权访问表现为 404（owner 过滤先行）。
        user = permission.user
        document = documents.get(document_id)
        if not document or document["owner_subject"] != user.local_user_id:
            raise HTTPException(status_code=404, detail="Document not found")
        del documents[document_id]
        return None

    return app


# `uvicorn app:app` 前先配置环境变量（见 README）；环境缺失时不构造，便于测试注入 mock。
app = create_app() if os.environ.get("IAM_API_URL") else None
