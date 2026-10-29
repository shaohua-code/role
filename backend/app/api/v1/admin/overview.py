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
from app.services.rbac_guards import ensure_roles
from app.services.role_provisioning import L1_ROLE_KEY, L2_ROLE_KEY, L3_ROLE_KEY

router = APIRouter(tags=["平台概览"])

@router.get("/overview")
def overview(actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """概览数量从数据库读取，不使用前端硬编码统计。"""
    ensure_roles(actor, db, [L1_ROLE_KEY], detail="缺少管理角色（原 platform.overview.read）")
    return {"tenants": db.scalar(select(func.count()).select_from(Tenant)) or 0,
            "applications": db.scalar(select(func.count()).select_from(Application)) or 0,
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "roles": db.scalar(select(func.count()).select_from(Role)) or 0,
            "recent_audits": db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.created_at >= func.now() - timedelta(days=7))) or 0}
