"""绿场测试夹具：在测试数据库内授予五级角色（L1 平台超管等）。

旧套件依赖「邮箱 == BOOTSTRAP 即超管」的隐式旁路；绿场改造后平台权限
只认角色绑定，因此直接调用 handler 的测试必须显式给 actor 授予角色。
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authorization import Role, RoleBinding
from app.models.identity import Tenant, TenantMembership, User


def ensure_platform_tenant(db: Session) -> Tenant:
    """幂等确保平台管理租户（slug=platform）存在并返回。

    平台角色全局化后，平台类角色的全局宿主即该租户；
    provision_tenant_admin_role / PLATFORM_TENANT_ID 依赖它存在，
    所有调用种子供给的测试必须先经本夹具建好。
    """
    from app.db.seed_greenfield import PLATFORM_TENANT_SLUG

    tenant = db.scalar(select(Tenant).where(Tenant.slug == PLATFORM_TENANT_SLUG))
    if tenant is None:
        tenant = Tenant(id=uuid4(), name="平台管理租户", slug=PLATFORM_TENANT_SLUG)
        db.add(tenant)
        db.flush()
    return tenant


def make_platform_admin_binding(db: Session, actor: User) -> None:
    """为 actor 在平台管理租户建立 membership 并绑定 L1 platform.admin（幂等）。

    平台角色全局化：平台租户全局唯一（slug=platform），L1 角色全局一份宿主其中；
    多个超管共享同一租户与角色，本夹具只补各自缺失的 membership 与绑定。
    """
    from app.services.role_provisioning import L1_ROLE_KEY

    tenant = ensure_platform_tenant(db)
    role = db.scalar(select(Role).where(
        Role.tenant_id == tenant.id, Role.key == L1_ROLE_KEY,
    ))
    if role is None:
        role = Role(
            id=uuid4(), tenant_id=tenant.id, application_id=None, kind="platform",
            key=L1_ROLE_KEY, name="平台超级管理员", status="active",
        )
        db.add(role)
        db.flush()
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == actor.id,
        TenantMembership.tenant_id == tenant.id,
    ))
    if membership is None:
        membership = TenantMembership(
            id=uuid4(), tenant_id=tenant.id, user_id=actor.id, status="active",
        )
        db.add(membership)
        db.flush()
    if db.scalar(select(RoleBinding.id).where(
        RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id,
    )) is None:
        db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
        db.flush()


def make_tenant_role_binding(
    db: Session,
    *,
    tenant_id: UUID,
    actor: User,
    role_key: str = "tenant.admin",
    role_name: str = "租户管理员",
    application_id: UUID | None = None,
    permission_ids: list[UUID] | None = None,
) -> Role:
    """为 actor 在指定租户（可选钉应用）创建角色并绑定，可附带权限授予。"""
    from app.models.authorization import RolePermission

    role = Role(
        id=uuid4(), tenant_id=tenant_id, application_id=application_id,
        kind="application" if application_id is not None else "tenant",
        key=role_key, name=role_name, status="active",
    )
    db.add(role)
    membership = db.query(TenantMembership).filter(
        TenantMembership.user_id == actor.id,
        TenantMembership.tenant_id == tenant_id,
    ).first()
    if membership is None:
        membership = TenantMembership(
            id=uuid4(), tenant_id=tenant_id, user_id=actor.id, status="active",
        )
        db.add(membership)
        db.flush()
    db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
    for permission_id in permission_ids or []:
        db.add(RolePermission(role_id=role.id, permission_id=permission_id))
    db.flush()
    return role
