"""平台数据概览管理路由。"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Role
from app.models.identity import AuditEvent, Tenant, TenantMembership, User

router = APIRouter(tags=["平台概览"])

@router.get("/overview")
def overview(db: Session = Depends(get_db_session)) -> dict:
    """概览数量从数据库读取，不使用前端硬编码统计。"""
    return {"tenants": db.scalar(select(func.count()).select_from(Tenant)) or 0,
            "applications": db.scalar(select(func.count()).select_from(Application)) or 0,
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "roles": db.scalar(select(func.count()).select_from(Role)) or 0,
            "recent_audits": db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.created_at >= func.now() - timedelta(days=7))) or 0}


