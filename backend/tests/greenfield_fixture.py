"""绿场测试夹具：在测试数据库内授予四级角色（L1 平台超管等）。

旧套件依赖「邮箱 == BOOTSTRAP 即超管」的隐式旁路；绿场改造后平台权限
只认角色绑定，因此直接调用 handler 的测试必须显式给 actor 授予角色。
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.authorization import Role, RoleBinding
from app.models.identity import Tenant, TenantMembership, User


def make_platform_admin_binding(db: Session, actor: User) -> None:
    """为既有 actor 建立平台租户 membership 并绑定 L1 platform.admin。

    Role 与 Tenant 之间没有 ORM relationship，批量 add_all 的落库顺序
    不保证 tenants 先于 roles；必须分步 flush 以满足外键。
    """
    slug = f"platform-{uuid4().hex[:12]}"
    tenant = Tenant(id=uuid4(), name="测试平台租户", slug=slug)
    db.add(tenant)
    db.flush()
    role = Role(
        id=uuid4(), tenant_id=tenant.id, application_id=None, kind="platform",
        key="platform.admin", name="平台超级管理员", status="active",
    )
    membership = TenantMembership(
        id=uuid4(), tenant_id=tenant.id, user_id=actor.id, status="active",
    )
    db.add_all([role, membership])
    db.flush()
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
