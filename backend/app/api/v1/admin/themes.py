"""每个应用独立的受控登录主题管理路由。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import platform_admin
from app.db.session import get_db_session
from app.models.application import Application, ApplicationTheme
from app.models.identity import User
from app.schemas.auth import ThemeUpdate
from app.services.theme_config import validate_theme_config

router = APIRouter(tags=["登录主题"])

@router.get("/themes")
def list_themes(application_id: UUID, db: Session = Depends(get_db_session)) -> list[dict]:
    if not db.get(Application, application_id): raise HTTPException(404, "应用不存在")
    return [{"id": str(t.id), "version": t.version, "status": t.status, "config": t.config, "created_at": t.created_at}
            for t in db.scalars(select(ApplicationTheme).where(ApplicationTheme.application_id == application_id).order_by(ApplicationTheme.version.desc())).all()]


@router.put("/themes/{application_id}")
def save_theme(application_id: UUID, body: ThemeUpdate, request: Request, publish: bool = False,
               actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    if not db.get(Application, application_id): raise HTTPException(404, "应用不存在")
    try:
        validate_theme_config(body.config)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    version = (db.scalar(select(func.max(ApplicationTheme.version)).where(ApplicationTheme.application_id == application_id)) or 0) + 1
    if publish:
        db.query(ApplicationTheme).filter(ApplicationTheme.application_id == application_id, ApplicationTheme.status == "published").update({"status": "archived"})
    row = ApplicationTheme(application_id=application_id, version=version, status="published" if publish else "draft",
                           config=body.config, published_at=datetime.now(timezone.utc) if publish else None)
    db.add(row); flush_or_conflict(db); audit(db, actor, request, "theme.publish" if publish else "theme.save", "theme", str(row.id), {"application_id": str(application_id), "version": version}); commit_or_conflict(db)
    return {"id": str(row.id), "version": row.version, "status": row.status, "config": row.config}
