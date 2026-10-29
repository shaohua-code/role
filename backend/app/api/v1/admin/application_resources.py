"""应用资源树管理路由：菜单/按钮/数据规则的 CRUD 与角色资源授权。

资源树是面向应用的显式授权单元：菜单挂路由与额外参数（extra JSON），
按钮与数据规则挂在菜单之下；角色通过 role_application_resources 获得资源子集，
业务端通过 GET /authorization/my-resources 拉取当前用户可见的整棵树。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import current_user
from app.db.session import get_db_session
from app.models.application import Application
from app.models.application_resource import ApplicationResource, RoleApplicationResource
from app.models.authorization import Role
from app.models.identity import User
from app.schemas.application_resources import (
    ApplicationResourceCreate,
    ApplicationResourceUpdate,
    RoleResourcesAssign,
)
from app.services.admin_authorization import has_application_admin_access
from app.services.rbac_guards import bump_memberships_holding_role

router = APIRouter(tags=["应用资源树"])


def _load_application(application_id: UUID, actor: User, db: Session, *, manage: bool) -> Application:
    """按 404 口径加载应用并校验管理访问权，避免暴露应用存在性。"""
    application = db.get(Application, application_id)
    if not application or not has_application_admin_access(
        actor, application.tenant_id, db, manage=manage, application_id=application.id,
    ):
        raise HTTPException(404, "应用不存在")
    return application


def _serialize(row: ApplicationResource) -> dict:
    """资源行转响应字典，ID 统一转字符串便于前端 JSON 消费。"""
    return {
        "id": str(row.id),
        "application_id": str(row.application_id),
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "resource_type": row.resource_type,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "path": row.path,
        "icon": row.icon,
        "sort": row.sort,
        "extra": row.extra,
        "status": row.status,
        "created_at": row.created_at,
    }


def _load_app_resource(application_id: UUID, resource_id: UUID, db: Session) -> ApplicationResource:
    """加载资源并确保属于当前应用，防止跨应用资源被路径参数绕过。"""
    row = db.get(ApplicationResource, resource_id)
    if not row or row.application_id != application_id:
        raise HTTPException(404, "资源节点不存在")
    return row


def _validate_parent(db: Session, application_id: UUID, parent_id: UUID | None,
                     resource_type: str) -> None:
    """校验父节点归属与类型：按钮/数据规则必须挂菜单，菜单只能嵌套菜单。"""
    if parent_id is None:
        if resource_type in ("button", "data_rule"):
            raise HTTPException(422, "按钮与数据规则必须挂在菜单之下")
        return
    parent = db.get(ApplicationResource, parent_id)
    if not parent or parent.application_id != application_id:
        raise HTTPException(422, "父节点必须属于同一应用")
    if resource_type in ("button", "data_rule") and parent.resource_type != "menu":
        raise HTTPException(422, "按钮与数据规则只能挂在菜单节点下")
    if resource_type == "menu" and parent.resource_type != "menu":
        raise HTTPException(422, "菜单只能嵌套在菜单节点下")


def _ensure_no_cycle(db: Session, resource: ApplicationResource, new_parent_id: UUID | None) -> None:
    """沿新父链向上走，出现自身即环形层级，直接拒绝。"""
    seen = {resource.id}
    parent_id = new_parent_id
    while parent_id is not None:
        if parent_id in seen:
            raise HTTPException(409, "父节点选择形成环形层级")
        seen.add(parent_id)
        parent = db.get(ApplicationResource, parent_id)
        if not parent or parent.application_id != resource.application_id:
            raise HTTPException(422, "父节点必须属于同一应用")
        parent_id = parent.parent_id


def _expand_with_ancestors(db: Session, application_id: UUID, resource_ids: list[UUID]) -> set[UUID]:
    """勾选集合自动补齐祖先，保证下发树中不会出现孤儿节点。"""
    rows = db.scalars(select(ApplicationResource).where(
        ApplicationResource.application_id == application_id,
    )).all()
    by_id = {row.id: row for row in rows}
    expanded: set[UUID] = set()
    for resource_id in resource_ids:
        current = by_id.get(resource_id)
        while current is not None:
            expanded.add(current.id)
            current = by_id.get(current.parent_id) if current.parent_id else None
    return expanded


@router.get("/applications/{application_id}/resources")
def list_application_resources(
    application_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """返回应用资源树平铺清单（前端组装层级）；排序 sort 升序、code 兜底。"""
    application = _load_application(application_id, actor, db, manage=False)
    rows = db.scalars(select(ApplicationResource).where(
        ApplicationResource.application_id == application.id,
    ).order_by(ApplicationResource.sort, ApplicationResource.code)).all()
    return [_serialize(row) for row in rows]


@router.post("/applications/{application_id}/resources", status_code=201)
def create_application_resource(
    application_id: UUID,
    body: ApplicationResourceCreate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """在应用资源树中登记新节点；编码在应用内唯一。"""
    application = _load_application(application_id, actor, db, manage=True)
    _validate_parent(db, application.id, body.parent_id, body.resource_type)
    row = ApplicationResource(
        application_id=application.id,
        parent_id=body.parent_id,
        resource_type=body.resource_type,
        code=body.code,
        name=body.name,
        description=body.description,
        path=body.path.strip() if body.path else None,
        icon=body.icon.strip() if body.icon else None,
        sort=body.sort,
        extra=body.extra,
        status=body.status,
    )
    db.add(row)
    flush_or_conflict(db)
    audit(db, actor, request, "application_resource.create", "application", str(application.id), {
        "application_id": str(application.id),
        "resource_id": str(row.id),
        "resource_type": row.resource_type,
        "code": row.code,
    })
    commit_or_conflict(db)
    return _serialize(row)


@router.patch("/applications/{application_id}/resources/{resource_id}")
def update_application_resource(
    application_id: UUID,
    resource_id: UUID,
    body: ApplicationResourceUpdate,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """编辑资源节点；支持移动父节点（检测环形）与启停。"""
    application = _load_application(application_id, actor, db, manage=True)
    row = _load_app_resource(application.id, resource_id, db)
    new_parent_id = body.parent_id if "parent_id" in body.model_fields_set else row.parent_id
    new_type = body.resource_type or row.resource_type
    _validate_parent(db, application.id, new_parent_id, new_type)
    _ensure_no_cycle(db, row, new_parent_id)
    if "code" in body.model_fields_set:
        row.code = body.code
    if "name" in body.model_fields_set:
        row.name = body.name
    if "description" in body.model_fields_set:
        row.description = body.description
    if "resource_type" in body.model_fields_set:
        row.resource_type = body.resource_type
    row.parent_id = new_parent_id
    if "path" in body.model_fields_set:
        row.path = body.path.strip() if body.path else None
    if "icon" in body.model_fields_set:
        row.icon = body.icon.strip() if body.icon else None
    if "sort" in body.model_fields_set:
        row.sort = body.sort
    if "extra" in body.model_fields_set:
        row.extra = body.extra or {}
    if "status" in body.model_fields_set:
        row.status = body.status
    flush_or_conflict(db)
    audit(db, actor, request, "application_resource.update", "application", str(application.id), {
        "application_id": str(application.id),
        "resource_id": str(row.id),
        "code": row.code,
    })
    commit_or_conflict(db)
    return _serialize(row)


@router.delete("/applications/{application_id}/resources/{resource_id}", status_code=204)
def delete_application_resource(
    application_id: UUID,
    resource_id: UUID,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> None:
    """删除叶子资源节点；存在子节点时要求先删子级，级联清除角色授权并刷新持有者。"""
    application = _load_application(application_id, actor, db, manage=True)
    row = _load_app_resource(application.id, resource_id, db)
    has_children = db.scalar(
        select(ApplicationResource.id).where(ApplicationResource.parent_id == row.id).limit(1)
    )
    if has_children:
        raise HTTPException(409, "存在子节点，请先删除子节点")
    # 先收集持有该资源的角色，显式清理授权行（不依赖数据库级联），
    # 删除后逐一刷新成员凭证版本，授权回收即时生效。
    holder_role_ids = list(db.scalars(select(RoleApplicationResource.role_id).where(
        RoleApplicationResource.resource_id == row.id,
    )).all())
    db.execute(sa_delete(RoleApplicationResource).where(RoleApplicationResource.resource_id == row.id))
    db.delete(row)
    db.flush()
    for role_id in holder_role_ids:
        bump_memberships_holding_role(db, role_id)
    audit(db, actor, request, "application_resource.delete", "application", str(application.id), {
        "application_id": str(application.id),
        "resource_id": str(row.id),
        "code": row.code,
    })
    commit_or_conflict(db)


@router.get("/applications/{application_id}/roles/{role_id}/resources")
def list_role_application_resources(
    application_id: UUID,
    role_id: UUID,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """返回角色在当前应用已勾选的资源 ID 集合，供分配弹窗回显。"""
    application = _load_application(application_id, actor, db, manage=False)
    role = db.get(Role, role_id)
    if not role or role.application_id != application.id:
        raise HTTPException(404, "角色不存在")
    rows = db.scalars(select(RoleApplicationResource.resource_id).where(
        RoleApplicationResource.role_id == role.id,
    )).all()
    return {"resource_ids": [str(rid) for rid in rows]}


@router.put("/applications/{application_id}/roles/{role_id}/resources")
def assign_role_application_resources(
    application_id: UUID,
    role_id: UUID,
    body: RoleResourcesAssign,
    request: Request,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """全量替换角色的应用资源授权；自动补齐祖先并刷新持有成员凭证版本。"""
    application = _load_application(application_id, actor, db, manage=True)
    role = db.get(Role, role_id)
    if not role or role.application_id != application.id:
        raise HTTPException(404, "角色不存在")
    expanded = _expand_with_ancestors(db, application.id, body.resource_ids)
    existing_rows = db.scalars(select(RoleApplicationResource).where(
        RoleApplicationResource.role_id == role.id,
    )).all()
    existing_ids = {row.resource_id for row in existing_rows}
    for row in existing_rows:
        if row.resource_id not in expanded:
            db.delete(row)
    for rid in expanded - existing_ids:
        db.add(RoleApplicationResource(role_id=role.id, resource_id=rid))
    # 资源授权即权限变化：刷新持有该角色的成员，旧业务凭证立即失效重取。
    bump_memberships_holding_role(db, role.id)
    audit(db, actor, request, "application_resource.assign", "application", str(application.id), {
        "application_id": str(application.id),
        "role_id": str(role.id),
        "role_key": role.key,
        "resource_count": len(expanded),
    })
    commit_or_conflict(db)
    return {"resource_ids": [str(rid) for rid in sorted(expanded)]}
