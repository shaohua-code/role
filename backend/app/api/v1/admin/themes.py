"""每个应用独立的受控登录主题管理路由。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user
from app.db.session import get_db_session
from app.models.application import Application, ApplicationTheme
from app.models.identity import User
from app.schemas.auth import ThemeUpdate
from app.services.theme_config import validate_theme_config
from app.services.rbac_guards import ensure_codes, ensure_roles
from app.services.role_provisioning import CONSOLE_ADMIN_ROLE_KEYS, L1_ROLE_KEY, L3_ROLE_KEY

router = APIRouter(tags=["登录主题"])


@router.get("/themes")
def list_themes(application_id: UUID, actor: User = Depends(current_user),
                db: Session = Depends(get_db_session)) -> list[dict]:
    """按版本倒序列出应用全部主题草稿/发布记录（配置含品牌与条款链接）。"""
    tenant_id = _require_application_tenant(db, application_id)
    ensure_codes(actor, db, "ops.theme.manage", tenant_id=tenant_id, application_id=application_id, detail="缺少管理权限：ops.theme.manage")
    return [{"id": str(t.id), "version": t.version, "status": t.status, "config": t.config, "created_at": t.created_at}
            for t in db.scalars(select(ApplicationTheme).where(ApplicationTheme.application_id == application_id).order_by(ApplicationTheme.version.desc())).all()]


@router.put("/themes/{application_id}")
def save_theme(application_id: UUID, body: ThemeUpdate, request: Request, publish: bool = False,
               actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """保存主题新版本（版本号递增）；publish=true 时归档旧发布版本并发布新版本。"""
    tenant_id = _require_application_tenant(db, application_id)
    # L2 的主题管理钉在本应用（11 号文档 §4.4）：判权带应用上下文，他应用角色默认拒绝。
    ensure_codes(actor, db, "ops.theme.manage", tenant_id=tenant_id, application_id=application_id, detail="缺少管理权限：ops.theme.manage")
    try:
        validate_theme_config(body.config)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    version = (db.scalar(select(func.max(ApplicationTheme.version)).where(ApplicationTheme.application_id == application_id)) or 0) + 1
    if publish:
        db.query(ApplicationTheme).filter(ApplicationTheme.application_id == application_id, ApplicationTheme.status == "published").update({"status": "archived"})
    row = ApplicationTheme(application_id=application_id, version=version, status="published" if publish else "draft",
                           config=body.config, published_at=datetime.now(timezone.utc) if publish else None)
    db.add(row); flush_or_conflict(db); audit(db, actor, request, "theme.publish" if publish else "theme.save", "theme", str(row.id), {"application_id": str(application_id), "tenant_id": str(tenant_id), "version": version}); commit_or_conflict(db)
    return {"id": str(row.id), "version": row.version, "status": row.status, "config": row.config}


@router.post("/themes/{application_id}/{theme_id}/restore")
def restore_theme(application_id: UUID, theme_id: UUID, request: Request, publish: bool = False,
                  actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """恢复历史主题版本（G17）：复制目标版本配置为新递增版本；publish=true 时同步发布。

    历史行保持原样（审计可追溯），恢复动作本身生成新版本记录，避免覆盖历史。
    """
    tenant_id = _require_application_tenant(db, application_id)
    ensure_codes(actor, db, "ops.theme.manage", tenant_id=tenant_id, application_id=application_id, detail="缺少管理权限：ops.theme.manage")
    target = db.scalar(select(ApplicationTheme).where(
        ApplicationTheme.id == theme_id, ApplicationTheme.application_id == application_id))
    if not target:
        raise HTTPException(404, "历史版本不存在")
    try:
        validate_theme_config(target.config)
    except ValueError as error:
        raise HTTPException(422, f"历史版本配置校验未通过：{error}") from error
    version = (db.scalar(select(func.max(ApplicationTheme.version)).where(ApplicationTheme.application_id == application_id)) or 0) + 1
    if publish:
        db.query(ApplicationTheme).filter(ApplicationTheme.application_id == application_id, ApplicationTheme.status == "published").update({"status": "archived"})
    row = ApplicationTheme(application_id=application_id, version=version,
                           status="published" if publish else "draft", config=target.config,
                           published_at=datetime.now(timezone.utc) if publish else None)
    db.add(row); flush_or_conflict(db)
    audit(db, actor, request, "theme.restore", "theme", str(row.id),
          {"application_id": str(application_id), "tenant_id": str(tenant_id), "version": version,
           "restored_from_version": target.version})
    commit_or_conflict(db)
    return {"id": str(row.id), "version": row.version, "status": row.status, "config": row.config,
            "restored_from_version": target.version}


def _require_application_tenant(db: Session, application_id: UUID) -> UUID:
    """解析应用归属租户；应用不存在时统一 404（供租户锚定判权使用）。"""
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "应用不存在")
    return application.tenant_id
