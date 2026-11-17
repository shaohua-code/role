"""绿场种子：平台租户、菜单/按钮权限目录、三管理员模板与引导超管绑定。

用法（迁移完成后执行）：
    python -m app.db.seed_greenfield
或经 manage.py：python manage.py seed-greenfield

幂等可重跑；不删除任何已存在的业务数据。
"""

from __future__ import annotations

import argparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_engine
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.services.permission_kinds import ROLE_SCOPE_SUPER, PermissionCatalog
from app.services.role_provisioning import (
    L1_ROLE_KEY,
    L4_ROLE_KEY,
    LEGACY_REVOKED_NODE_CODES,
    RoleProvisioning,
)

PLATFORM_TENANT_SLUG = "platform"


def seed_permissions(db: Session) -> int:
    """幂等写入管理面「菜单 → 按钮」目录；业务码由应用注册接口创建（强制 requires_data_scope）。"""
    return PermissionCatalog.seed_ui_permissions(db)


def seed_platform_tenant(db: Session) -> Tenant:
    """专用平台租户：所有 roles.kind=platform 的归属，避免空 application_id 语义过载。"""
    tenant = db.scalar(select(Tenant).where(Tenant.slug == PLATFORM_TENANT_SLUG))
    if tenant is None:
        tenant = Tenant(name="平台管理租户", slug=PLATFORM_TENANT_SLUG, kind="organization")
        db.add(tenant)
        db.flush()
    return tenant


def seed_l1_role(db: Session, platform_tenant: Tenant) -> Role:
    """超管角色：scope=super，持全部管理面菜单/按钮节点；不默认绑定任何业务码。"""
    role = db.scalar(select(Role).where(
        Role.tenant_id == platform_tenant.id, Role.key == L1_ROLE_KEY,
    ))
    if role is None:
        role = Role(
            tenant_id=platform_tenant.id, application_id=None, kind="platform",
            key=L1_ROLE_KEY, name="平台超级管理员", scope=ROLE_SCOPE_SUPER,
            description="超管：平台所有内容可见；全部菜单/按钮节点；可代管任意租户/应用；默认无业务码",
        )
        db.add(role)
        db.flush()
    if role.scope != ROLE_SCOPE_SUPER:
        role.scope = ROLE_SCOPE_SUPER
    existing_permission_ids = set(db.scalars(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id),
    ).all())
    for permission in db.scalars(select(Permission).where(
        Permission.code.in_(PermissionCatalog.all_ui_codes()),
    )).all():
        if permission.id not in existing_permission_ids:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.flush()
    _prune_retired_catalog_codes(db)
    return role


def _prune_retired_catalog_codes(db: Session) -> None:
    """目录收敛：清理已下线管理面节点（LEGACY_REVOKED_NODE_CODES）的授权与目录行。

    幂等重跑时防死节点复活——旧库里 permission_health 等已下线节点若不清理，
    会继续出现在 L1 配权树但无任何页面/端点消费。
    """
    retired = [row for row in db.scalars(select(Permission).where(
        Permission.code.in_(LEGACY_REVOKED_NODE_CODES),
    )).all()]
    if not retired:
        return
    retired_ids = [row.id for row in retired]
    db.execute(delete(RolePermission).where(RolePermission.permission_id.in_(retired_ids)))
    for row in retired:
        db.delete(row)
    db.flush()
    print(f"已清理下线管理面节点：{sorted(row.code for row in retired)}")


def seed_bootstrap_admin(db: Session, platform_tenant: Tenant, l1_role: Role) -> None:
    """引导超管：仅 seed 场景创建并绑定 L1；运行时不允许邮箱旁路（默认 bypass=false）。"""
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        print("未配置 BOOTSTRAP_ADMIN_EMAIL/PASSWORD，跳过引导超管")
        return
    email = settings.bootstrap_admin_email.casefold()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name="平台管理员",
                    password_hash=hash_password(settings.bootstrap_admin_password))
        db.add(user)
        db.flush()
        print(f"已创建引导超管：{email}")
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.user_id == user.id, TenantMembership.tenant_id == platform_tenant.id,
    ))
    if membership is None:
        membership = TenantMembership(user_id=user.id, tenant_id=platform_tenant.id)
        db.add(membership)
        db.flush()
    from app.models.authorization import RoleBinding

    binding = db.scalar(select(RoleBinding).where(
        RoleBinding.membership_id == membership.id, RoleBinding.role_id == l1_role.id,
    ))
    if binding is None:
        db.add(RoleBinding(membership_id=membership.id, role_id=l1_role.id))
        print("已绑定 L1 platform.admin")


def seed_demo_tenant(db: Session, *, with_demo_application: bool = False) -> None:
    """可选演示租户：模板角色全局化后仅幂等确保全局 L3；演示应用可选（含 L2/L4 模板）。"""
    tenant = db.scalar(select(Tenant).where(Tenant.slug == "demo"))
    if tenant is None:
        tenant = Tenant(name="演示租户", slug="demo", kind="organization")
        db.add(tenant)
        db.flush()
        print("已创建演示租户 demo")
    # 平台角色全局化：tenant.admin 全局一份（宿主平台租户），演示租户不再预置副本。
    RoleProvisioning.provision_tenant_admin_role(db)
    if with_demo_application:
        from app.models.application import Application

        application = db.scalar(select(Application).where(Application.client_id == "demo-app"))
        if application is None:
            application = Application(
                tenant_id=tenant.id, name="演示应用", client_id="demo-app",
                permission_namespace="demo", description="绿场演示应用",
                redirect_uris=["http://localhost:3000/callback"],
                post_logout_redirect_uris=["http://localhost:3000/"],
                trusted=False, client_secret_hash=None,
            )
            db.add(application)
            db.flush()
            print("已创建演示应用 demo-app")
        RoleProvisioning.provision_application_platform_roles(db, tenant.id, application.id)


def run_seed(*, demo_tenant: bool = False, demo_application: bool = False) -> None:
    """绿场种子主流程；全部步骤幂等，可在任意时刻重跑。"""
    with Session(get_engine()) as db:
        # 阶段一：幂等写入菜单/按钮节点管理面目录（menu.* / button.*，见 services/permission_kinds.py；
        # 业务码不在此种子）。旧五域 27 接口码目录已下线，仅存于历史记录。
        created = seed_permissions(db)
        print(f"权限目录：新增 {created} 条管理面码")
        # 阶段二：创建专用平台租户，并预置 L1 超管角色（授予全部管理面码）。
        platform_tenant = seed_platform_tenant(db)
        l1_role = seed_l1_role(db, platform_tenant)
        # 阶段三：幂等确保全局唯一的 L3 租户管理员模板（宿主平台租户；全局生效）。
        RoleProvisioning.provision_tenant_admin_role(db)
        # 阶段四：按环境变量创建引导超管并绑定 L1；未配置则跳过。
        seed_bootstrap_admin(db, platform_tenant, l1_role)
        # 阶段五（可选）：--demo-tenant / --demo-application 追加演示租户与应用。
        if demo_tenant:
            seed_demo_tenant(db, with_demo_application=demo_application)
        db.commit()
        print("绿场种子完成")


# 走查演示账号统一密码（仅本地开发验收用；生产严禁使用该种子命令）。
WALKTHROUGH_PASSWORD = "Walkthrough#2026"
# 走查用业务码：surface=business + requires_data_scope=True，验证 L4「业务码必须带行级范围」。
WALKTHROUGH_BUSINESS_CODE = "demo.document.read"


def seed_walkthrough_accounts(db: Session) -> None:
    """走查演示账号（五级口径：L2/L3/L4 各一名，幂等，不改动已有绑定）。

    前置：需要 demo 租户（--demo-tenant 已建）。本函数补建演示应用、L2/L4 模板角色、
    业务码 demo.document.read 与 L4 的 self 数据范围，最后创建三个用户并完成绑定。
    """
    from app.models.application import Application
    from app.models.authorization import RoleBinding
    from app.models.organization import RoleDataScope

    demo_tenant = db.scalar(select(Tenant).where(Tenant.slug == "demo"))
    if demo_tenant is None:
        raise RuntimeError("演示租户不存在：请先以 --demo-tenant 运行 seed-greenfield")

    # 演示应用（seed --demo-tenant 默认不建；此处补齐并预置 L2/L4 模板角色）。
    application = db.scalar(select(Application).where(Application.client_id == "demo-app"))
    if application is None:
        application = Application(
            tenant_id=demo_tenant.id, name="演示应用", client_id="demo-app",
            permission_namespace="demo", description="绿场走查演示应用",
            redirect_uris=["http://localhost:3000/callback"],
            post_logout_redirect_uris=["http://localhost:3000/"],
            trusted=False, client_secret_hash=None,
        )
        db.add(application)
        db.flush()
        print("已创建演示应用 demo-app")
    l2_role, l4_role = RoleProvisioning.provision_application_platform_roles(db, demo_tenant.id, application.id)
    # 平台角色全局化：走查 L3 账号绑定全局唯一的 tenant.admin（跨租户生效）。
    l3_role = RoleProvisioning.provision_tenant_admin_role(db)

    # 业务码登记：与应用命名空间对齐，强制行级数据范围（缺策略时 evaluate_access 拒绝）。
    business_permission = db.scalar(select(Permission).where(Permission.code == WALKTHROUGH_BUSINESS_CODE))
    if business_permission is None:
        business_permission = Permission(
            code=WALKTHROUGH_BUSINESS_CODE, catalog_namespace="demo", resource_type="document",
            scope="read", description="演示业务码：读取文档（走查用）",
            surface="business", requires_data_scope=True,
        )
        db.add(business_permission)
        db.flush()
        print(f"已登记业务码 {WALKTHROUGH_BUSINESS_CODE}（business + 强制 data_scope）")

    # P405：业务码挂在自定义应用角色上，不挂 app.member。
    reader = db.scalar(select(Role).where(
        Role.tenant_id == demo_tenant.id,
        Role.application_id == application.id,
        Role.key == "demo.reader",
    ))
    if reader is None:
        reader = Role(
            tenant_id=demo_tenant.id, application_id=application.id, kind="application",
            key="demo.reader", name="文档只读", description="走查用应用角色：读取文档",
        )
        db.add(reader)
        db.flush()
        print("已创建应用角色 demo.reader")
    granted = db.scalar(select(RolePermission).where(
        RolePermission.role_id == reader.id,
        RolePermission.permission_id == business_permission.id,
    ))
    if granted is None:
        db.add(RolePermission(role_id=reader.id, permission_id=business_permission.id))
        print("已为应用角色 demo.reader 授予 demo.document.read")
    scope = db.scalar(select(RoleDataScope).where(
        RoleDataScope.role_id == reader.id,
        RoleDataScope.permission_id == business_permission.id,
    ))
    if scope is None:
        db.add(RoleDataScope(
            tenant_id=demo_tenant.id, role_id=reader.id,
            permission_id=business_permission.id, scope_type="self", organization_ids=[],
        ))
        print("已为 demo.reader 配置 demo.document.read 的 self 数据范围")
    # 清掉历史上误挂在 app.member 上的业务码。
    db.execute(delete(RolePermission).where(
        RolePermission.role_id == l4_role.id,
        RolePermission.permission_id == business_permission.id,
    ))
    db.execute(delete(RoleDataScope).where(
        RoleDataScope.role_id == l4_role.id,
        RoleDataScope.permission_id == business_permission.id,
    ))

    # 三个走查账号：统一密码，分别绑 L2/L3/L4；全部幂等（已存在则只补缺失的绑定）。
    # 邮箱用 example.com 子域——.test 属 IANA 保留 TLD，会被 pydantic 邮箱校验拒绝。
    accounts: tuple[tuple[str, str, Role], ...] = (
        ("l2-admin@demo.example.com", "走查·L2 应用管理员", l2_role),
        ("l3-admin@demo.example.com", "走查·L3 租户管理员", l3_role),
        ("l4-member@demo.example.com", "走查·L4 应用成员", l4_role),
    )
    for email, display_name, role in accounts:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, display_name=display_name,
                        password_hash=hash_password(WALKTHROUGH_PASSWORD))
            db.add(user)
            db.flush()
            print(f"已创建账号：{email}")
        membership = db.scalar(select(TenantMembership).where(
            TenantMembership.user_id == user.id, TenantMembership.tenant_id == demo_tenant.id,
        ))
        if membership is None:
            membership = TenantMembership(user_id=user.id, tenant_id=demo_tenant.id)
            db.add(membership)
            db.flush()
        binding = db.scalar(select(RoleBinding).where(
            RoleBinding.membership_id == membership.id, RoleBinding.role_id == role.id,
        ))
        if binding is None:
            db.add(RoleBinding(membership_id=membership.id, role_id=role.id))
            print(f"已绑定 {role.key} → {email}")
        # L4 同时持有应用角色，才能拿到业务码 / 菜单。
        if role.key == L4_ROLE_KEY:
            reader_binding = db.scalar(select(RoleBinding).where(
                RoleBinding.membership_id == membership.id, RoleBinding.role_id == reader.id,
            ))
            if reader_binding is None:
                db.add(RoleBinding(membership_id=membership.id, role_id=reader.id))
                print(f"已绑定 demo.reader → {email}")
    print(f"走查账号就绪（统一密码见 seed_greenfield.WALKTHROUGH_PASSWORD）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="绿场 RBAC 种子")
    parser.add_argument("--demo-tenant", action="store_true", help="创建演示租户与 L3 模板")
    parser.add_argument("--demo-application", action="store_true", help="连同演示应用与 L2/L4 模板（隐含 --demo-tenant）")
    args = parser.parse_args()
    run_seed(demo_tenant=args.demo_tenant or args.demo_application, demo_application=args.demo_application)
