"""One-shot: delete all roles except platform.admin on the platform tenant."""
from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.db.seed_greenfield import seed_l1_role, seed_platform_tenant
from app.db.session import get_engine
from app.models.application import Application
from app.models.authorization import Role, RoleBinding, RolePermission
from app.models.identity import Tenant, UserInvitation
from app.services.rbac_guards import bump_memberships_holding_role
from app.services.role_provisioning import L1_ROLE_KEY


def main() -> None:
    with Session(get_engine()) as db:
        platform_tenant = seed_platform_tenant(db)
        keep = db.scalar(
            select(Role).where(
                Role.tenant_id == platform_tenant.id,
                Role.key == L1_ROLE_KEY,
                Role.application_id.is_(None),
            )
        )
        if keep is None:
            raise SystemExit("platform.admin 不存在，拒绝继续以免锁死管理面")
        roles = list(db.scalars(select(Role)).all())
        doomed = [role for role in roles if role.id != keep.id]
        print(f"保留 {keep.key} id={keep.id} tenant={platform_tenant.slug} name={keep.name}")
        print(f"将删除 {len(doomed)} 个角色：")
        tenants = {row.id: row.slug for row in db.scalars(select(Tenant)).all()}
        for role in doomed:
            print(f"  - {tenants.get(role.tenant_id, '?')} {role.key} {role.name} app={role.application_id}")
        doomed_ids = [role.id for role in doomed]
        invitation_count = 0
        cleared_registration = 0
        bumped = 0
        if doomed_ids:
            invitation_count = db.scalar(
                select(func.count()).select_from(UserInvitation).where(
                    UserInvitation.role_id.in_(doomed_ids),
                )
            ) or 0
            # 邀请对角色是 RESTRICT，必须先删行才能删角色。
            db.execute(delete(UserInvitation).where(UserInvitation.role_id.in_(doomed_ids)))
            result = db.execute(
                update(Application)
                .where(Application.registration_role_id.in_(doomed_ids))
                .values(registration_role_id=None)
            )
            cleared_registration = result.rowcount or 0
            for role in doomed:
                bumped += bump_memberships_holding_role(db, role.id)
            # ORM delete 会把 role_permissions.role_id 置空；改走 SQL，让库级 CASCADE 清子表。
            for role in doomed:
                db.expunge(role)
            db.execute(delete(Role).where(Role.id.in_(doomed_ids)))
            db.expire_all()
        l1 = seed_l1_role(db, platform_tenant)
        grant_count = db.scalar(
            select(func.count()).select_from(RolePermission).where(
                RolePermission.role_id == l1.id,
            )
        ) or 0
        remaining = list(db.scalars(select(Role)).all())
        binding_count = db.scalar(
            select(func.count()).select_from(RoleBinding).where(
                RoleBinding.role_id == l1.id,
            )
        ) or 0
        db.commit()
        print(
            f"已删邀请 {invitation_count}；清空 registration_role_id {cleared_registration}；"
            f"bump 成员 {bumped}"
        )
        print(f"剩余角色 {len(remaining)}：{[role.key for role in remaining]}")
        print(f"L1 挂码 {grant_count}；L1 绑定 {binding_count}")
        if len(remaining) != 1 or remaining[0].id != keep.id:
            raise SystemExit("清理后角色数不是 1 个 platform.admin")
        if binding_count < 1:
            raise SystemExit("引导超管未绑定 L1")


if __name__ == "__main__":
    main()
