"""主题素材上传（G18）：本地盘卷存储，管理面上传、登录页公开只读。

- 上传走 /admin/uploads/theme-assets：L2 应用上下文判权（同主题管理门禁），
  原始字节体直传（不引入 multipart 依赖），服务端随机命名防路径穿越。
- 读取走公开 GET：登录页加载 Logo/背景不需要登录；文件名白名单校验。
- 只接受 PNG/JPEG/WebP 位图——SVG 可内嵌脚本，按 PRD「不允许向登录页注入脚本」排除。
"""

import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict
from app.core.config import get_settings
from app.core.security import current_user
from app.db.session import get_db_session
from app.models.application import Application
from app.models.identity import User
from app.services.rbac_guards import ensure_codes, ensure_roles
from app.services.role_provisioning import CONSOLE_ADMIN_ROLE_KEYS

ALLOWED_CONTENT_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}
# 服务端生成的文件名永远是 32 位 hex + 受控扩展名；白名单同时阻断路径穿越。
_FILENAME_PATTERN = re.compile(r"^[0-9a-f]{32}\.(png|jpg|webp)$")

admin_router = APIRouter(tags=["主题素材"])
public_router = APIRouter(tags=["主题素材"])


def _storage_dir() -> Path:
    """素材存储目录；容器内挂载命名卷，首次上传自动创建。"""
    directory = Path(get_settings().theme_upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@admin_router.post("/uploads/theme-assets", status_code=201)
async def upload_theme_asset(request: Request, application_id: UUID,
                             actor: User = Depends(current_user),
                             db: Session = Depends(get_db_session)) -> dict:
    """上传主题位图素材：判权与主题管理一致，成功后返回相对 URL 供主题配置引用。"""
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(404, "应用不存在")
    ensure_codes(actor, db, "ops.theme.manage", tenant_id=application.tenant_id, application_id=application.id, detail="缺少管理权限：ops.theme.manage")
    settings = get_settings()
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    extension = ALLOWED_CONTENT_TYPES.get(content_type)
    if not extension:
        raise HTTPException(415, "仅支持 PNG / JPEG / WebP 位图（SVG 可携带脚本，已排除）")
    declared_length = request.headers.get("content-length")
    if declared_length and int(declared_length) > settings.theme_upload_max_bytes:
        raise HTTPException(413, f"素材超过大小限制（{settings.theme_upload_max_bytes} 字节）")
    payload = await request.body()
    if not payload:
        raise HTTPException(422, "素材内容为空")
    if len(payload) > settings.theme_upload_max_bytes:
        raise HTTPException(413, f"素材超过大小限制（{settings.theme_upload_max_bytes} 字节）")
    filename = uuid4().hex + extension
    (_storage_dir() / filename).write_bytes(payload)
    audit(db, actor, request, "theme.asset.upload", "application", str(application.id),
          {"tenant_id": str(application.tenant_id), "filename": filename, "bytes": len(payload)})
    commit_or_conflict(db)
    return {"url": f"{get_settings().api_v1_prefix}/uploads/theme-assets/{filename}",
            "bytes": len(payload), "content_type": content_type}


@public_router.get("/uploads/theme-assets/{filename}")
def get_theme_asset(filename: str) -> FileResponse:
    """公开只读素材：登录页免登录加载品牌资源；一年不可变缓存（文件名内容绑定）。"""
    if not _FILENAME_PATTERN.fullmatch(filename):
        raise HTTPException(404, "素材不存在")
    path = _storage_dir() / filename
    if not path.is_file():
        raise HTTPException(404, "素材不存在")
    return FileResponse(path, media_type=_MEDIA_TYPES[path.suffix],
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})
