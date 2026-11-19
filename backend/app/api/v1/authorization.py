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
from app.services.authorization import AuthorizationEvaluator
from app.services.effective_roles import EffectiveRoleResolver
from app.services.model_distribution import ModelDistribution

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
    decision = AuthorizationEvaluator.evaluate_access(body, user, db)["decision"]
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
        results[code] = _public_decision(AuthorizationEvaluator.evaluate_access(check, user, db)["decision"], user)
    return {"results": results}


@router.get("/my-models")
def list_my_models(client_id: str, user: User = Depends(current_user), db: Session = Depends(get_db_session)) -> list[dict]:
    """业务应用按登录身份拉取本应用可见模型（产品需求 §6.4 三级可见性唯一口径）。

    返回 = 平台目录 active ∩ 租户下发 active ∩ 应用下发 active。下发关系即授权：
    清单未返回的模型不得调用；用量上报的 model_id 必须来自本清单。
    要求调用者是应用所属租户的活跃成员；凭证与端点永不回读（业务自持调用凭证）。
    P1 收口：目标应用以服务端验签的 OIDC 上下文（_oidc_application_id）为准，
    不信任客户端传入的 client_id——同租户持应用 A token 查应用 B 一律拒绝；
    管理会话无已定义的应用可见性边界，fail-closed 拒绝（另行定义前不开放）。
    """
    if getattr(user, "_auth_protocol", None) != "oidc" or not getattr(user, "_oidc_application_id", None):
        # 本端点只服务业务应用 OIDC 会话；管理台用模型治理 / 应用工作台页查模型。
        raise HTTPException(403, "模型清单仅向业务应用 OIDC 会话开放")
    application = db.get(Application, user._oidc_application_id)
    if not application or application.status != "active":
        raise HTTPException(404, "应用不存在")
    if client_id != application.client_id:
        # client_id 只作一致性校验：与已验证应用不符即拒绝，杜绝跨应用读取清单。
        raise HTTPException(403, "client_id 与登录应用不一致")
    membership_exists = db.scalar(select(TenantMembership.id).where(
        TenantMembership.user_id == user.id,
        TenantMembership.tenant_id == application.tenant_id,
        TenantMembership.status == "active",
    ).limit(1))
    if not membership_exists:
        # 非本租户活跃成员不暴露任何目录信息（与跨租户不可区分，防枚举）。
        return []
    models = ModelDistribution.list_models_for_application(db, application)
    return [{
        "id": str(model.id),
        "key": model.key,
        "provider": model.provider,
        "model_name": model.model_name,
        "display_name": model.display_name,
        "capabilities": model.capabilities,
        "rpm_limit": model.rpm_limit,
        "tpm_limit": model.tpm_limit,
        "input_cost_per_million": float(model.input_cost_per_million)
        if model.input_cost_per_million is not None else None,
        "output_cost_per_million": float(model.output_cost_per_million)
        if model.output_cost_per_million is not None else None,
    } for model in models]


@router.get("/my-resources")
def list_my_resources(client_id: str, user: User = Depends(current_user), db: Session = Depends(get_db_session)) -> list[dict]:
    """业务前端登录后拉取当前用户在该应用可见的资源树（菜单/按钮/数据规则）。

    取用户有效角色（直连绑定 ∪ 活跃用户组继承）的资源授权并集，仅回传 active 节点；
    分配时服务端已补齐祖先，这里仍按「父节点不在集合内则上提到顶层」兜底组装。
    P1 收口：与 my-models 同口径——目标应用以服务端验签的 OIDC 上下文
    （_oidc_application_id）为准，不信任客户端传入的 client_id，同租户持应用 A
    token 查应用 B 一律拒绝；管理会话无已定义的应用可见性边界，fail-closed 拒绝。
    """
    if getattr(user, "_auth_protocol", None) != "oidc" or not getattr(user, "_oidc_application_id", None):
        # 本端点只服务业务应用 OIDC 会话；管理台在应用工作台资源页查看资源树。
        raise HTTPException(403, "资源树仅向业务应用 OIDC 会话开放")
    application = db.get(Application, user._oidc_application_id)
    if not application or application.status != "active":
        raise HTTPException(404, "应用不存在")
    if client_id != application.client_id:
        # client_id 只作一致性校验：与已验证应用不符即拒绝，杜绝跨应用读取资源树。
        raise HTTPException(403, "client_id 与登录应用不一致")
    memberships = db.scalars(select(TenantMembership).where(
        TenantMembership.user_id == user.id,
        TenantMembership.tenant_id == application.tenant_id,
        TenantMembership.status == "active",
    )).all()
    # 逐成员累计有效角色的资源授权并集；租户级角色无资源行，天然为空不影响结果。
    granted_ids: set[UUID] = set()
    for membership in memberships:
        roles = EffectiveRoleResolver.list_effective_roles(
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
