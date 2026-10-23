"""角色、权限、绑定与授权模拟管理路由；所有写入受平台管理员策略保护。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.v1.admin.common import audit, commit_or_conflict, flush_or_conflict
from app.core.security import platform_admin
from app.db.session import get_db_session
from app.models.application import Application
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.models.organization import RoleDataScope
from app.schemas.access_control import (
    AuthorizationCheck,
    AuthorizationSimulation,
    PermissionCreate,
    PermissionStatusUpdate,
    RoleBindingCreate,
    RoleCloneRequest,
    RoleCreate,
    RolePermissionsPreview,
    RolePermissionsUpdate,
    RoleUpdate,
)
from app.services.authorization import evaluate_access
from app.services.permission_impact import (
    StaleRolePermissionPreview,
    apply_role_permissions,
    preview_role_permissions,
)
from app.services.permission_namespace import (
    normalize_namespace,
    permission_matches_namespace,
    resolve_permission_namespace,
)

router = APIRouter(tags=["RBAC 权限管理"])


@router.post("/authorization/simulate")
def simulate_authorization(body: AuthorizationSimulation, db: Session = Depends(get_db_session)) -> dict:
    """以当前策略只读预演用户授权；该管理 API 不创建授权记录或审计变更。"""
    target_user = db.get(User, body.user_id)
    if not target_user:
        raise HTTPException(404, "模拟用户不存在")
    check = AuthorizationCheck(**body.model_dump(exclude={"user_id"}))
    evaluation = evaluate_access(check, target_user, db, enforce_token_context=False)
    return {
        "subject": {"user_id": str(target_user.id), "email": target_user.email,
                    "display_name": target_user.display_name, "status": target_user.status},
        "request": {"tenant_id": str(check.tenant_id),
                    "application_id": str(check.application_id) if check.application_id else None,
                    "permission_code": check.permission_code, "resource_id": check.resource_id,
                    "include_data_scope": check.include_data_scope},
        **evaluation,
    }


@router.get("/roles")
def list_roles(db: Session = Depends(get_db_session)) -> list[dict]:
    rows = db.scalars(select(Role).order_by(Role.created_at.desc()).limit(500)).all()
    return [{"id": str(r.id), "tenant_id": str(r.tenant_id), "application_id": str(r.application_id) if r.application_id else None,
             "key": r.key, "name": r.name, "description": r.description, "status": r.status,
             "permission_codes": [p.code for p in db.scalars(select(Permission).join(RolePermission).where(RolePermission.role_id == r.id)).all()]}
            for r in rows]


@router.post("/roles", status_code=201)
def create_role(body: RoleCreate, request: Request, actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    if not db.get(Tenant, body.tenant_id): raise HTTPException(404, "租户不存在")
    if body.application_id:
        app = db.get(Application, body.application_id)
        if not app or app.tenant_id != body.tenant_id: raise HTTPException(422, "应用必须属于所选租户")
    role = Role(tenant_id=body.tenant_id, application_id=body.application_id, key=body.key, name=body.name, description=body.description)
    db.add(role); flush_or_conflict(db); audit(db, actor, request, "role.create", "role", str(role.id), {"tenant_id": str(role.tenant_id)}); commit_or_conflict(db)
    return {"id": str(role.id), "key": role.key, "name": role.name, "tenant_id": str(role.tenant_id)}


@router.post("/roles/{role_id}/clone", status_code=201)
def clone_role(role_id: UUID, body: RoleCloneRequest, request: Request,
               actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """在源租户和应用范围内原子复制角色；成员绑定和组绑定始终留在源角色。"""
    # 锁定源角色，使其状态/范围在复制事务中保持稳定，并与角色权限维护采用相同锁顺序。
    source = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    if not source:
        raise HTTPException(404, "角色不存在")

    clone = Role(
        tenant_id=source.tenant_id,
        application_id=source.application_id,
        key=body.key,
        name=body.name,
        description=body.description,
        # 复制停用角色时不意外恢复访问；管理员可在确认影响后单独启用副本。
        status=source.status,
    )
    db.add(clone)
    flush_or_conflict(db)

    copied_permission_count = 0
    copied_data_scope_count = 0
    if body.copy_authorizations:
        # 仅复制目录当前启用的权限。停用权限的历史授予/数据策略保留在源角色，
        # 但不应被新副本重新引入。锁定权限行可串行化与权限停用操作。
        active_permissions = db.scalars(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == source.id, Permission.status == "active")
            .order_by(Permission.id)
            .with_for_update()
        ).all()
        active_permission_ids = {permission.id for permission in active_permissions}
        if active_permission_ids:
            source_grants = db.scalars(
                select(RolePermission)
                .where(RolePermission.role_id == source.id,
                       RolePermission.permission_id.in_(active_permission_ids))
                .order_by(RolePermission.permission_id, RolePermission.resource_id, RolePermission.id)
            ).all()
            # 资源实例 ID 也是授权的一部分，需逐条复制，不能合并成通用授权。
            db.add_all([
                RolePermission(role_id=clone.id, permission_id=grant.permission_id,
                               resource_id=grant.resource_id)
                for grant in source_grants
            ])
            copied_permission_count = len(source_grants)

            source_scopes = db.scalars(
                select(RoleDataScope)
                .where(RoleDataScope.role_id == source.id,
                       RoleDataScope.permission_id.in_(active_permission_ids))
                .order_by(RoleDataScope.permission_id)
            ).all()
            # JSON 列使用新列表，避免 ORM 对象之间共享可变组织 ID 集合。
            db.add_all([
                RoleDataScope(
                    tenant_id=clone.tenant_id,
                    role_id=clone.id,
                    permission_id=scope.permission_id,
                    scope_type=scope.scope_type,
                    organization_ids=list(scope.organization_ids or []),
                )
                for scope in source_scopes
            ])
            copied_data_scope_count = len(source_scopes)

    audit(db, actor, request, "role.clone", "role", str(clone.id), {
        "tenant_id": str(clone.tenant_id),
        "application_id": str(clone.application_id) if clone.application_id else None,
        "source_role_id": str(source.id),
        "copy_authorizations": body.copy_authorizations,
        "copied_permission_grant_count": copied_permission_count,
        "copied_data_scope_count": copied_data_scope_count,
        "copied_member_bindings": False,
        "status": clone.status,
    })
    # 角色、授权、数据范围和审计事件在同一事务提交，避免出现半成品副本。
    flush_or_conflict(db)
    commit_or_conflict(db)
    return {
        "id": str(clone.id),
        "source_role_id": str(source.id),
        "tenant_id": str(clone.tenant_id),
        "application_id": str(clone.application_id) if clone.application_id else None,
        "key": clone.key,
        "name": clone.name,
        "status": clone.status,
        "copied_permission_grant_count": copied_permission_count,
        "copied_data_scope_count": copied_data_scope_count,
        "copied_member_bindings": False,
    }


@router.patch("/roles/{role_id}")
def update_role(role_id: UUID, body: RoleUpdate, request: Request,
                actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """只改角色名称和说明，保持 tenant/application/key 与现有授权绑定不变。"""
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "角色不存在")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(role, field, value)
    audit(db, actor, request, "role.update", "role", str(role.id),
          {"tenant_id": str(role.tenant_id), "updated_fields": sorted(changes)})
    commit_or_conflict(db)
    return {"id": str(role.id), "tenant_id": str(role.tenant_id), "application_id": str(role.application_id) if role.application_id else None,
            "key": role.key, "name": role.name, "description": role.description,
            "updated_fields": sorted(changes)}


@router.patch("/roles/{role_id}/status")
def set_role_status(role_id: UUID, status: str, request: Request, actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    if status not in {"active", "disabled"}: raise HTTPException(422, "状态仅支持 active 或 disabled")
    role = db.get(Role, role_id)
    if not role: raise HTTPException(404, "角色不存在")
    role.status = status; audit(db, actor, request, "role.status.change", "role", str(role.id), {"status": status, "tenant_id": str(role.tenant_id)}); commit_or_conflict(db)
    return {"id": str(role.id), "status": role.status}


@router.put("/role-bindings", status_code=204)
def bind_role(body: RoleBindingCreate, request: Request, actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> None:
    """绑定前同时校验成员与角色的租户归属，阻断跨租户拼接 ID 的越权请求。"""
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == body.user_id,
                                                           TenantMembership.tenant_id == body.tenant_id,
                                                           TenantMembership.status == "active"))
    role = db.get(Role, body.role_id)
    if not membership or not role or role.tenant_id != body.tenant_id or role.status != "active":
        raise HTTPException(422, "用户成员关系和角色必须有效且属于同一租户")
    if role.application_id:
        role_app = db.get(Application, role.application_id)
        if not role_app or role_app.tenant_id != body.tenant_id:
            raise HTTPException(422, "角色应用必须属于所选租户")
    if db.scalar(select(RoleBinding.id).where(RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id)):
        return
    db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
    audit(db, actor, request, "role.bind", "user", str(body.user_id), {"tenant_id": str(body.tenant_id), "role_id": str(role.id)})
    commit_or_conflict(db)


@router.get("/permissions")
def list_permissions(
    catalog_namespace: Annotated[str | None, Query(max_length=100)] = None,
    application_id: UUID | None = None,
    db: Session = Depends(get_db_session),
) -> list[dict]:
    namespace_filter: str | None = None
    if application_id is not None:
        application = db.get(Application, application_id)
        if not application:
            raise HTTPException(404, "应用不存在")
        namespace_filter = application.permission_namespace
    elif catalog_namespace:
        namespace_filter = normalize_namespace(catalog_namespace)

    assigned_roles = (
        select(
            RolePermission.permission_id.label("permission_id"),
            func.count(func.distinct(RolePermission.role_id)).label("assigned_role_count"),
        )
        .group_by(RolePermission.permission_id)
        .subquery()
    )
    statement = (
        select(Permission, func.coalesce(assigned_roles.c.assigned_role_count, 0))
        .outerjoin(assigned_roles, assigned_roles.c.permission_id == Permission.id)
        .order_by(Permission.catalog_namespace, Permission.code)
        .limit(1000)
    )
    if namespace_filter is not None:
        statement = statement.where(Permission.catalog_namespace == namespace_filter)
    rows = db.execute(statement).all()
    return [{"id": str(permission.id), "code": permission.code,
             "catalog_namespace": permission.catalog_namespace,
             "resource_type": permission.resource_type, "scope": permission.scope,
             "description": permission.description, "status": permission.status,
             "assigned_role_count": int(assigned_role_count)}
            for permission, assigned_role_count in rows]


@router.post("/permissions", status_code=201)
def create_permission(body: PermissionCreate, request: Request, actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    catalog_namespace = resolve_permission_namespace(
        code=body.code,
        catalog_namespace=body.catalog_namespace,
    )
    if not permission_matches_namespace(body.code, catalog_namespace):
        raise HTTPException(422, "权限编码与 catalog_namespace 不匹配")
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
    })
    commit_or_conflict(db)
    return {"id": str(row.id), "code": row.code, "catalog_namespace": row.catalog_namespace,
            "resource_type": row.resource_type,
            "scope": row.scope, "status": row.status, "assigned_role_count": 0}


@router.patch("/permissions/{permission_id}/status")
def set_permission_status(permission_id: UUID, body: PermissionStatusUpdate, request: Request,
                           actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """停用/恢复稳定权限编码；停用保留历史角色授权并立即从在线判定中排除。"""
    permission = db.scalar(select(Permission).where(Permission.id == permission_id).with_for_update())
    if not permission:
        raise HTTPException(404, "权限项不存在")
    if permission.status != body.expected_status:
        raise HTTPException(409, "权限状态已被其他管理员修改，请刷新后重试")

    assigned_role_count = int(db.scalar(
        select(func.count(func.distinct(RolePermission.role_id))).where(
            RolePermission.permission_id == permission.id,
        )
    ) or 0)
    if permission.status == body.status:
        return {"id": str(permission.id), "status": permission.status,
                "assigned_role_count": assigned_role_count,
                "reactivates_existing_grants": permission.status == "active" and assigned_role_count > 0}

    old_status = permission.status
    permission.status = body.status
    audit(db, actor, request, "permission.status.change", "permission", str(permission.id), {
        "code": permission.code,
        "from_status": old_status,
        "to_status": permission.status,
        "retained_role_count": assigned_role_count,
    })
    commit_or_conflict(db)
    return {"id": str(permission.id), "status": permission.status,
            "assigned_role_count": assigned_role_count,
            "reactivates_existing_grants": permission.status == "active" and assigned_role_count > 0}


@router.get("/roles/{role_id}/permissions")
def list_role_permissions(role_id: UUID, db: Session = Depends(get_db_session)) -> list[dict]:
    """返回角色的通用与资源实例级授权，供管理员准确编辑通用授权集合。"""
    if not db.get(Role, role_id):
        raise HTTPException(404, "角色不存在")
    rows = db.execute(
        select(RolePermission, Permission)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == role_id)
        .order_by(Permission.code, RolePermission.resource_id)
    ).all()
    return [{"id": str(grant.id), "permission_id": str(permission.id), "code": permission.code,
             "resource_id": grant.resource_id}
            for grant, permission in rows]


@router.post("/roles/{role_id}/permissions/preview")
def preview_role_permission_update(role_id: UUID, body: RolePermissionsPreview,
                                   db: Session = Depends(get_db_session)) -> dict:
    """在保存前预演通用授权增删及可能清理的数据范围策略；该接口只读。"""
    # 读取锁避免预览正在被其它管理请求变更的角色授权集合。
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update(read=True))
    if not role:
        raise HTTPException(404, "角色不存在")
    try:
        return preview_role_permissions(role_id, body.permission_ids, db)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.put("/roles/{role_id}/permissions")
def replace_role_permissions(role_id: UUID, body: RolePermissionsUpdate, request: Request,
                              actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> dict:
    """事务性替换角色通用权限；资源实例级授权不受本表单影响。"""
    try:
        impact = apply_role_permissions(
            role_id, body.permission_ids, body.expected_current_permission_ids, db,
        )
    except StaleRolePermissionPreview as error:
        raise HTTPException(409, str(error)) from error
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if not impact["changed"]:
        return impact

    audit(db, actor, request, "role.permissions.replace", "role", str(role_id), {
        "tenant_id": impact["role"]["tenant_id"],
        "granted_permissions": impact["grant_permission_codes"],
        "revoked_permissions": impact["revoke_permission_codes"],
        "removed_data_scope_policy_count": len(impact["data_scopes_to_delete"]),
    })
    commit_or_conflict(db)
    return {"changed": True, **impact}


@router.put("/roles/{role_id}/permissions/{permission_id}", status_code=204)
def grant_permission(role_id: UUID, permission_id: UUID, request: Request,
                     resource_id: Annotated[str | None, Query(min_length=1, max_length=180)] = None,
                     actor: User = Depends(platform_admin), db: Session = Depends(get_db_session)) -> None:
    # 同一角色授权变更与批量更新串行化，避免并发创建重复授予。
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    permission = db.scalar(select(Permission).where(Permission.id == permission_id).with_for_update())
    if not role or not permission: raise HTTPException(404, "角色或权限不存在")
    if permission.status != "active": raise HTTPException(409, "停用权限不能新增角色授权")
    exists = db.scalar(select(RolePermission.id).where(RolePermission.role_id == role_id, RolePermission.permission_id == permission_id, RolePermission.resource_id == resource_id))
    if exists: return
    db.add(RolePermission(role_id=role_id, permission_id=permission_id, resource_id=resource_id)); audit(db, actor, request, "role.permission.grant", "role", str(role_id), {"permission": permission.code, "resource_id": resource_id}); commit_or_conflict(db)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=204)
def revoke_permission(
    role_id: UUID,
    permission_id: UUID,
    request: Request,
    actor: User = Depends(platform_admin),
    db: Session = Depends(get_db_session),
    resource_id: Annotated[str | None, Query(min_length=1, max_length=180)] = None,
) -> None:
    """按资源 ID 精确撤销授权；同一权限仍有其他 grant 时保留数据策略。"""
    role = db.scalar(select(Role).where(Role.id == role_id).with_for_update())
    permission = db.get(Permission, permission_id)
    if not role or not permission: raise HTTPException(404, "角色或权限不存在")
    result = db.execute(delete(RolePermission).where(RolePermission.role_id == role_id,
                                                     RolePermission.permission_id == permission_id,
                                                     RolePermission.resource_id == resource_id))
    if result.rowcount:
        # 通用授权与多个实例授权可以并存；只有最后一条授权撤销时数据策略才失去前置条件。
        remaining_grant = db.scalar(select(RolePermission.id).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        ).limit(1))
        removed_scope_count = 0
        if not remaining_grant:
            removed_scope_count = db.execute(delete(RoleDataScope).where(
                RoleDataScope.role_id == role_id,
                RoleDataScope.permission_id == permission_id,
            )).rowcount or 0
        audit(db, actor, request, "role.permission.revoke", "role", str(role_id), {
            "permission": permission.code,
            "resource_id": resource_id,
            "removed_data_scope_policy_count": removed_scope_count,
        })
        commit_or_conflict(db)
