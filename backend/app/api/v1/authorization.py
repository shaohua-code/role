"""供已认证业务服务查询 RBAC 判定的接口，未匹配授权时一律拒绝。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db_session
from app.models.application import Application
from app.models.application_resource import ApplicationResource, RoleApplicationResource
from app.models.identity import TenantMembership, User
from app.schemas.access_control import AuthorizationCheck, AuthorizationCheckBatch
from app.services.authorization import evaluate_access
from app.services.effective_roles import list_effective_roles

router = APIRouter(prefix="/authorization", tags=["授权判定"])


def _public_decision(decision: dict, user: User) -> dict:
    """业务 API 契约只回传判定和数据条件；OIDC 调用方回传服务端验签的应用 UUID。"""
    if decision.get("allowed") and getattr(user, "_auth_protocol", None) == "oidc":
        decision["application_id"] = str(user._oidc_application_id)
    return decision


@router.post("/check")
def check_access(body: AuthorizationCheck, user: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """租户 ID 必须与当前用户真实成员关系匹配；调用方传来的租户仅是查找条件，不构成信任依据。"""
    # 业务 API 契约只回传判定和数据条件，不暴露管理模拟使用的内部解释明细。
    decision = evaluate_access(body, user, db)["decision"]
    # 用量上报需要稳定的应用 UUID；只把服务端验签 OIDC 上下文回给已允许的服务端调用方。
    # 不能把请求体中的 application_id 回显成可信身份，也不向拒绝结果附带主体信息。
    return _public_decision(decision, user)


@router.post("/check-batch")
def check_access_batch(body: AuthorizationCheckBatch, user: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """同租户多权限码一次判定；每个权限码仍走与 /check 相同的单一判定路径，语义完全一致。"""
    # 逐码独立构造校验模型，保证与单码请求走同一校验与判定逻辑，避免批量旁路。
    results = {}
    for code in body.permission_codes:
        check = AuthorizationCheck(
            tenant_id=body.tenant_id, application_id=body.application_id,
            permission_code=code, resource_id=body.resource_id,
            include_data_scope=body.include_data_scope,
        )
        results[code] = _public_decision(evaluate_access(check, user, db)["decision"], user)
    return {"results": results}


@router.get("/my-resources")
def list_my_resources(client_id: str, user: User = Depends(current_user), db: Session = Depends(get_db_session)) -> list[dict]:
    """业务前端登录后拉取当前用户在该应用可见的资源树（菜单/按钮/数据规则）。

    取用户有效角色（直连绑定 ∪ 活跃用户组继承）的资源授权并集，仅回传 active 节点；
    分配时服务端已补齐祖先，这里仍按「父节点不在集合内则上提到顶层」兜底组装。
    """
    application = db.scalars(select(Application).where(Application.client_id == client_id)).first()
    if not application or application.status != "active":
        raise HTTPException(404, "应用不存在")
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.tenant_id == application.tenant_id,
        TenantMembership.status == "active",
    )).all()
    # 逐成员累计有效角色的资源授权并集；租户级角色无资源行，天然为空不影响结果。
    granted_ids: set[UUID] = set()
    for membership in memberships:
        roles = list_effective_roles(
            db, membership_id=membership.id, tenant_id=membership.tenant_id,
            application_id=application.id,
        )
        if not roles:
            continue
        rows = db.scalars(select(RoleApplicationResource.resource_id).where(
            RoleApplicationResource.role_id.in_([role.id for role in roles]),
        )).all()
        granted_ids.update(rows)
    if not granted_ids:
        return []
    nodes = db.scalars(select(ApplicationResource).where(
        ApplicationResource.application_id == application.id,
        ApplicationResource.status == "active",
        ApplicationResource.id.in_(granted_ids),
    ).order_by(ApplicationResource.sort, ApplicationResource.code)).all()
    # 组装嵌套树：父节点被停用或缺失时子树整体上提，避免业务端丢菜单。
    node_map: dict[UUID, dict] = {}
    tree: list[dict] = []
    for node in nodes:
        node_map[node.id] = {
            "id": str(node.id), "resource_type": node.resource_type, "code": node.code,
            "name": node.name, "description": node.description, "path": node.path,
            "icon": node.icon, "sort": node.sort, "extra": node.extra, "children": [],
        }
    for node in nodes:
        item = node_map[node.id]
        parent = node_map.get(node.parent_id) if node.parent_id else None
        (parent["children"] if parent else tree).append(item)
    return tree
