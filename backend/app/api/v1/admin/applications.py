"""租户应用与 OAuth 客户端登记管理路由。"""

import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict, valid_redirect_uri
from app.core.security import current_user, hash_password, is_platform_admin_user, platform_admin
from app.db.session import get_db_session
from app.models.application import Application, ApplicationTheme
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import Tenant, User
from app.models.oidc import OAuthRefreshToken
from app.schemas.access_control import PermissionCreate
from app.schemas.applications import ApplicationCreate, ApplicationStatusUpdate, ApplicationUpdate
from app.services.permission_namespace import (
    default_namespace_from_client_id,
    normalize_namespace,
    permission_matches_namespace,
    resolve_permission_namespace,
)
from app.services.admin_authorization import (
    has_application_admin_access,
    list_readable_application_capabilities,
    require_application_admin_access,
)
from app.services.public_registration import eligible_registration_role

router = APIRouter(tags=["应用管理"])

@router.get("/applications")
def list_applications(tenant_id: UUID | None = None, actor: User = Depends(current_user),
                      db: Session = Depends(get_db_session)) -> list[dict]:
    """平台管理员可看全局目录；租户管理员只能看通过租户/应用资源授权的客户端。"""
    platform_admin_access = is_platform_admin_user(actor)
    if not platform_admin_access and tenant_id is None:
        raise HTTPException(status_code=422, detail="租户管理员查询应用时必须提供 tenant_id")

    capabilities = list_readable_application_capabilities(actor, tenant_id, db) if tenant_id else None
    stmt = select(Application)
    if tenant_id is not None:
        stmt = stmt.where(Application.tenant_id == tenant_id)
    if capabilities is not None:
        if not capabilities:
            return []
        # 在 LIMIT 前先套用授权清单，避免用户获准的应用恰好排在前 500 条之外。
        stmt = stmt.where(Application.id.in_(capabilities.keys()))
    stmt = stmt.order_by(Application.created_at.desc()).limit(500)
    rows = db.scalars(stmt).all()
    return [{"id": str(a.id), "tenant_id": str(a.tenant_id), "name": a.name, "client_id": a.client_id,
             "permission_namespace": a.permission_namespace,
             "description": a.description, "trusted": a.trusted, "status": a.status,
             "registration_policy": a.registration_policy,
             "registration_role_id": str(a.registration_role_id) if a.registration_role_id else None,
             "registration_terms_version": a.registration_terms_version,
             "registration_privacy_version": a.registration_privacy_version,
             "redirect_uris": a.redirect_uris, "post_logout_redirect_uris": a.post_logout_redirect_uris,
             "created_at": a.created_at,
             **({"can_manage": capabilities[a.id]["can_manage"],
                 "can_rotate_secret": capabilities[a.id]["can_rotate_secret"]}
                if capabilities is not None and a.id in capabilities else {})}
            for a in rows if capabilities is None or a.id in capabilities]


@router.post("/applications", status_code=201)
def create_application(body: ApplicationCreate, request: Request, response: Response,
                       actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    require_application_admin_access(actor, body.tenant_id, db, manage=True)
    tenant = db.get(Tenant, body.tenant_id)
    if not tenant or tenant.status != "active": raise HTTPException(404, "活动租户不存在")
    if any(not valid_redirect_uri(uri) for uri in [*body.redirect_uris, *body.post_logout_redirect_uris]):
        raise HTTPException(422, "登录和退出回调地址必须使用 HTTPS；本地开发可使用 localhost")
    # 客户端密钥只生成并回传一次；持久化仅保存 Argon2 哈希，避免明文密钥泄露。
    client_secret = secrets.token_urlsafe(48)
    permission_namespace = (
        normalize_namespace(body.permission_namespace)
        if body.permission_namespace
        else default_namespace_from_client_id(body.client_id)
    )
    row = Application(tenant_id=body.tenant_id, name=body.name, client_id=body.client_id,
                      permission_namespace=permission_namespace,
                      description=body.description, redirect_uris=body.redirect_uris,
                      post_logout_redirect_uris=body.post_logout_redirect_uris,
                      trusted=False, client_secret_hash=hash_password(client_secret))
    db.add(row); flush_or_conflict(db); audit(db, actor, request, "application.create", "application", str(row.id), {"client_id": row.client_id, "tenant_id": str(body.tenant_id), "trusted": False}); commit_or_conflict(db)
    # 一次性返回的客户端密钥不得进入共享缓存或代理缓存。
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "name": row.name, "client_id": row.client_id,
            "permission_namespace": row.permission_namespace,
            "client_secret": client_secret, "trusted": row.trusted, "status": row.status,
            "post_logout_redirect_uris": row.post_logout_redirect_uris}


@router.get("/applications/{application_id}/permissions")
def list_application_permission_catalog(
    application_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """返回与应用 permission_namespace 对齐的权限目录条目。"""
    application = db.get(Application, application_id)
    if not application or not has_application_admin_access(
        actor, application.tenant_id, db, application_id=application.id,
    ):
        raise HTTPException(404, "应用不存在")
    assigned_roles = (
        select(
            RolePermission.permission_id.label("permission_id"),
            func.count(func.distinct(RolePermission.role_id)).label("assigned_role_count"),
        )
        .join(Role, Role.id == RolePermission.role_id)
        .where(Role.application_id == application.id)
        .group_by(RolePermission.permission_id)
        .subquery()
    )
    rows = db.execute(
        select(Permission, func.coalesce(assigned_roles.c.assigned_role_count, 0))
        .outerjoin(assigned_roles, assigned_roles.c.permission_id == Permission.id)
        .where(Permission.catalog_namespace == application.permission_namespace)
        .order_by(Permission.code)
        .limit(1000)
    ).all()
    return [
        {
            "id": str(permission.id),
            "code": permission.code,
            "catalog_namespace": permission.catalog_namespace,
            "resource_type": permission.resource_type,
            "scope": permission.scope,
            "description": permission.description,
            "status": permission.status,
            "assigned_role_count": int(assigned_role_count),
        }
        for permission, assigned_role_count in rows
    ]


@router.post("/applications/{application_id}/permissions", status_code=201)
def create_application_permission(
    application_id: UUID,
    body: PermissionCreate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """在应用命名空间下登记权限；catalog_namespace 由服务端锁定。"""
    application = db.get(Application, application_id)
    if not application or not has_application_admin_access(
        actor, application.tenant_id, db, manage=True, application_id=application.id,
    ):
        raise HTTPException(404, "应用不存在")
    if not permission_matches_namespace(body.code, application.permission_namespace):
        raise HTTPException(422, "权限编码必须属于当前应用的命名空间")
    catalog_namespace = resolve_permission_namespace(
        code=body.code,
        catalog_namespace=application.permission_namespace,
    )
    row = Permission(
        code=body.code.strip(),
        catalog_namespace=catalog_namespace,
        resource_type=body.resource_type.strip(),
        scope=body.scope.strip(),
        description=body.description.strip() if body.description else None,
    )
    db.add(row)
    flush_or_conflict(db)
    audit(db, actor, request, "permission.create", "permission", str(row.id), {
        "code": row.code,
        "catalog_namespace": row.catalog_namespace,
        "application_id": str(application.id),
    })
    commit_or_conflict(db)
    return {
        "id": str(row.id),
        "code": row.code,
        "catalog_namespace": row.catalog_namespace,
        "resource_type": row.resource_type,
        "scope": row.scope,
        "status": row.status,
        "assigned_role_count": 0,
    }


@router.patch("/applications/{application_id}")
def update_application(application_id: UUID, body: ApplicationUpdate, request: Request,
                       actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """只改应用资料与 ToC 注册策略；密钥、回调和 OAuth 信任策略保持独立。"""
    candidate = db.get(Application, application_id)
    if not candidate:
        raise HTTPException(404, "应用不存在")
    if not has_application_admin_access(actor, candidate.tenant_id, db, manage=True, application_id=candidate.id):
        raise HTTPException(404, "应用不存在")
    row = db.scalar(select(Application).where(Application.id == application_id).with_for_update())
    if not row or not has_application_admin_access(actor, row.tenant_id, db, manage=True, application_id=row.id):
        raise HTTPException(404, "应用不存在")
    changes = body.model_dump(exclude_unset=True)
    registration_policy = changes.get("registration_policy", row.registration_policy)
    registration_role_id = changes.get("registration_role_id", row.registration_role_id)
    terms_version = changes.get("registration_terms_version", row.registration_terms_version)
    privacy_version = changes.get("registration_privacy_version", row.registration_privacy_version)
    if registration_policy == "open":
        tenant = db.scalar(select(Tenant).where(Tenant.id == row.tenant_id).with_for_update())
        if not tenant or tenant.kind != "consumer":
            raise HTTPException(422, "只有 ToC 消费租户可以开放公开注册")
        if (eligible_registration_role(db, row, registration_role_id, lock=True) is None
                or not terms_version or not privacy_version):
            raise HTTPException(422, "开放自助注册必须选择当前应用的活动普通角色，并配置条款与隐私版本")
        published_theme = db.scalar(select(ApplicationTheme).where(
            ApplicationTheme.application_id == row.id,
            ApplicationTheme.status == "published",
        ).order_by(ApplicationTheme.version.desc()).limit(1))
        theme_config = published_theme.config if published_theme and isinstance(published_theme.config, dict) else {}
        if not theme_config.get("terms_url") or not theme_config.get("privacy_url"):
            raise HTTPException(422, "开放自助注册前，必须在已发布登录主题中配置用户协议和隐私政策链接")
    for field, value in changes.items():
        setattr(row, field, value)
    audit(db, actor, request, "application.update", "application", str(row.id),
          {"tenant_id": str(row.tenant_id), "updated_fields": sorted(changes)})
    commit_or_conflict(db)
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "client_id": row.client_id,
            "name": row.name, "description": row.description,
            "registration_policy": row.registration_policy,
            "registration_role_id": str(row.registration_role_id) if row.registration_role_id else None,
            "registration_terms_version": row.registration_terms_version,
            "registration_privacy_version": row.registration_privacy_version,
            "updated_fields": sorted(changes)}


@router.get("/applications/{application_id}/registration-roles")
def list_application_registration_roles(application_id: UUID, actor: User = Depends(current_user),
                                        db: Session = Depends(get_db_session)) -> list[dict]:
    """只列出当前应用可作为注册默认角色的活动普通角色，不提供跨应用角色选项。"""
    application = db.get(Application, application_id)
    if not application or not has_application_admin_access(
        actor, application.tenant_id, db, manage=True, application_id=application.id,
    ):
        raise HTTPException(404, "应用不存在")
    roles = db.scalars(select(Role).where(
        Role.tenant_id == application.tenant_id,
        Role.application_id == application.id,
        Role.status == "active",
    ).order_by(Role.name)).all()
    tenant = db.get(Tenant, application.tenant_id)
    if not tenant or tenant.kind != "consumer":
        return []
    return [{"id": str(role.id), "key": role.key, "name": role.name}
            for role in roles if eligible_registration_role(db, application, role.id) is not None]


@router.patch("/applications/{application_id}/trusted")
def set_application_trusted(application_id: UUID, trusted: bool, request: Request,
                            actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """只由平台管理员显式设置信任；撤销信任时同时撤销可静默续期的 OAuth 刷新会话。"""
    row = db.get(Application, application_id)
    if not row:
        raise HTTPException(404, "应用不存在")
    if row.trusted == trusted:
        return {"id": str(row.id), "trusted": row.trusted}
    if not trusted:
        db.execute(update(OAuthRefreshToken).where(
            OAuthRefreshToken.application_id == row.id, OAuthRefreshToken.revoked_at.is_(None),
        ).values(revoked_at=datetime.now(timezone.utc)))
    row.trusted = trusted
    audit(db, actor, request, "application.trust.change", "application", str(row.id),
          {"trusted": trusted, "tenant_id": str(row.tenant_id)})
    commit_or_conflict(db)
    return {"id": str(row.id), "trusted": row.trusted}


@router.post("/applications/{application_id}/rotate-secret")
def rotate_application_secret(application_id: UUID, request: Request, response: Response,
                              actor: User = Depends(current_user), db: Session = Depends(get_db_session)) -> dict:
    """管理员确认后立即替换 confidential client 密钥，只在本次响应中回传明文。"""
    # 先在普通读查询上判权，避免无权身份用拒绝请求锁住任意应用行。
    candidate = db.get(Application, application_id)
    if not candidate:
        raise HTTPException(404, "应用不存在")
    require_application_admin_access(
        actor, candidate.tenant_id, db, rotate_secret=True, application_id=candidate.id,
    )
    # 锁定应用行，确保并发轮换的哈希更新和审计按同一串行事务提交。
    row = db.scalar(select(Application).where(Application.id == application_id).with_for_update())
    if not row:
        raise HTTPException(404, "应用不存在")
    client_secret = secrets.token_urlsafe(48)
    row.client_secret_hash = hash_password(client_secret)
    audit(db, actor, request, "application.secret.rotate", "application", str(row.id),
          {"tenant_id": str(row.tenant_id)})
    commit_or_conflict(db)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {"id": str(row.id), "client_id": row.client_id, "client_secret": client_secret,
            "rotated_at": datetime.now(timezone.utc)}


@router.patch("/applications/{application_id}/status")
def set_application_status(
    application_id: UUID,
    body: ApplicationStatusUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """行锁保护状态转换，过期页面不能覆盖另一位管理员的启停操作。"""
    # 拒绝越权请求后再获取写锁，避免无权调用占用 OAuth 应用状态行。
    candidate = db.get(Application, application_id)
    if not candidate:
        raise HTTPException(404, "应用不存在")
    if not has_application_admin_access(actor, candidate.tenant_id, db, manage=True,
                                        application_id=candidate.id):
        raise HTTPException(404, "应用不存在")
    row = db.scalar(select(Application).where(Application.id == application_id).with_for_update())
    if not row:
        raise HTTPException(404, "应用不存在")
    if not has_application_admin_access(actor, row.tenant_id, db, manage=True,
                                        application_id=row.id):
        raise HTTPException(404, "应用不存在")
    if row.status != body.expected_status:
        raise HTTPException(status_code=409, detail="应用状态已被其他管理员修改，请刷新后重试")
    if row.status == body.status:
        return {"id": str(row.id), "status": row.status}

    if body.status == "disabled":
        db.execute(update(OAuthRefreshToken).where(
            OAuthRefreshToken.application_id == row.id, OAuthRefreshToken.revoked_at.is_(None),
        ).values(revoked_at=datetime.now(timezone.utc)))
    previous_status = row.status
    row.status = body.status
    audit(db, actor, request, "application.status.change", "application", str(row.id), {
        "tenant_id": str(row.tenant_id), "from_status": previous_status, "to_status": body.status,
    })
    commit_or_conflict(db)
    return {"id": str(row.id), "status": row.status}
