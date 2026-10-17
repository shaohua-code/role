"""供已认证业务服务查询 RBAC 判定的接口，未匹配授权时一律拒绝。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db_session
from app.models.identity import User
from app.schemas.access_control import AuthorizationCheck, AuthorizationCheckBatch
from app.services.authorization import evaluate_access

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
