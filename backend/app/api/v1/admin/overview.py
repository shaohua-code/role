"""平台数据概览管理路由。"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Role
from app.models.identity import AuditEvent, Tenant, TenantMembership, User
from app.services.rbac_guards import ActorVisibility, PermissionEnforcer

router = APIRouter(tags=["平台概览"])

@router.get("/overview")
def overview(actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """概览数量从数据库读取，不使用前端硬编码统计。

    P2-2 数据边界：超管返回全域计数；租户级/应用级只统计自身管理租户内的
    租户 / 应用 / 用户 / 角色与近期审计，应用不再一次看到全平台规模。
    """
    PermissionEnforcer.ensure_codes(actor, db, "menu.overview", detail="缺少管理权限：menu.overview")
    tenant_scope = ActorVisibility.list_actor_management_tenant_ids(actor, db)
    if tenant_scope is None:
        return {"tenants": db.scalar(select(func.count()).select_from(Tenant)) or 0,
                "applications": db.scalar(select(func.count()).select_from(Application)) or 0,
                "users": db.scalar(select(func.count()).select_from(User)) or 0,
                "roles": db.scalar(select(func.count()).select_from(Role)) or 0,
                "recent_audits": db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.created_at >= func.now() - timedelta(days=7))) or 0}
    if not tenant_scope:
        return {"tenants": 0, "applications": 0, "users": 0, "roles": 0, "recent_audits": 0}
    scope_users = select(User.id).join(TenantMembership, TenantMembership.user_id == User.id).where(
        TenantMembership.tenant_id.in_(tenant_scope), TenantMembership.status == "active",
    )
    return {"tenants": len(tenant_scope),
            "applications": db.scalar(select(func.count()).select_from(Application).where(
                Application.tenant_id.in_(tenant_scope))) or 0,
            "users": db.scalar(select(func.count()).select_from(scope_users.subquery())) or 0,
            "roles": db.scalar(select(func.count()).select_from(Role).where(
                Role.tenant_id.in_(tenant_scope))) or 0,
            "recent_audits": db.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.tenant_id.in_(tenant_scope),
                AuditEvent.created_at >= func.now() - timedelta(days=7))) or 0}
