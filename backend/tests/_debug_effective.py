"""临时调试：隔离复现 list_effective_roles 空结果。"""
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.authorization import Permission, RoleBinding
from app.models.identity import Tenant, TenantMembership, User
from app.services.effective_roles import (
    authorized_role_ids_statement,
    list_effective_roles,
)
from app.services.role_provisioning import (
    L2_GRANT_NODE_CODES,
    L3_GRANT_NODE_CODES,
    provision_tenant_admin_role,
)
from tests.greenfield_fixture import ensure_platform_tenant

engine = create_engine("sqlite://", echo=False)
Base.metadata.create_all(engine)
db = Session(engine)
platform_tenant = ensure_platform_tenant(db)
tenant_x = Tenant(name="X", slug=f"x-{uuid4().hex[:8]}")
db.add(tenant_x)
db.flush()
for code in sorted(set(L3_GRANT_NODE_CODES) | set(L2_GRANT_NODE_CODES)):
    db.add(Permission(
        code=code, catalog_namespace="platform",
        resource_type=code.split(".", 1)[0], scope=code.rsplit(".", 1)[-1],
        surface="management", requires_data_scope=False,
        kind="menu" if code.startswith("menu.") else "button",
    ))
db.flush()
l3_role = provision_tenant_admin_role(db)
print("l3_role:", l3_role.id, l3_role.status, l3_role.kind, "tenant_id==platform:", l3_role.tenant_id == platform_tenant.id)
user = User(email=f"u-{uuid4().hex[:8]}@example.com", password_hash="x", display_name="u")
db.add(user)
db.flush()
membership = TenantMembership(user_id=user.id, tenant_id=tenant_x.id, status="active")
db.add(membership)
db.flush()
db.add(RoleBinding(membership_id=membership.id, role_id=l3_role.id))
db.commit()

stmt = authorized_role_ids_statement(membership.id, tenant_x.id)
print("statement:")
print(stmt.compile(compile_kwargs={"literal_binds": True}))
ids = list(db.scalars(stmt).all())
print("authorized ids:", ids)
roles = list_effective_roles(db, membership_id=membership.id, tenant_id=tenant_x.id)
print("effective:", [r.id for r in roles])
db.close()
engine.dispose()
