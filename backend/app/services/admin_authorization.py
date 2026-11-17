"""租户管理 API 的服务端授权辅助；前端菜单状态不能替代这里的策略判定。

辅助逻辑收敛在 :class:`AdminAccessGuard`；节点码常量保留在模块层。
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import is_platform_admin_user
from app.models.application import Application
from app.models.authorization import Permission, Role, RolePermission
from app.models.identity import Tenant, TenantMembership, User
from app.services.effective_roles import EffectiveRoleResolver


# 管理面节点码（菜单/按钮）：目录重构后判权单元只有 menu.* / button.* 两类。
ORGANIZATION_READ = "menu.organization_workspace"
ORGANIZATION_MANAGE = "button.org.manage"
USERS_READ = "menu.users"
APPLICATION_READ = "menu.application_workspace"
APPLICATION_MANAGE = "button.apps.manage"
APPLICATION_SECRET_ROTATE = "button.apps.secret"


class AdminAccessGuard:
    """工作台访问守卫：组织/应用读写权限与可读应用能力批量筛选。

    全部方法为静态方法（db 会话由调用方传入），保持与原模块函数一一对应的行为。
    """

    @staticmethod
    def has_organization_admin_access(
        actor: User,
        tenant_id: UUID,
        db: Session,
        *,
        manage: bool = False,
    ) -> bool:
        """L1 代管；读 = 组织/用户管理菜单码任一 或 租户管理台角色；写统一认 button.org.manage 节点。

        判权单元对齐产品口径「后端接口按菜单/按钮节点判权」，读口径与前端入口可见性同源：
        - menu.organization_workspace：组织工作台入口码；
        - menu.users：绿场 §6.6 用户管理融合后，租户模式「用户管理」菜单（menu.users）渲染的
          即本模块守卫的成员/组织/角色数据页（TenantAccessManagement）——只判组织码会出现
          「菜单可见但接口成批 403」的口径漂移；
        - 兜底 CONSOLE_ADMIN_ROLE_KEYS（app.admin 等）：数据范围端点把读检查复用为
          「L1/L3/L2 任一可见」的角色可见性语义（F4 写分级：L2 只读），L2 模板不含上述
          租户级菜单码，去掉兜底会让 L2 的只读查询变 404。
        P1-2 收口：manage=True 时加判按钮节点（min_scope=tenant 同源语义），应用级
        管理员即便持 app.admin 模板也管不了全租户组织树、动不了成员离职。
        """
        from app.services.rbac_guards import PermissionEnforcer
        from app.services.role_provisioning import CONSOLE_ADMIN_ROLE_KEYS

        if is_platform_admin_user(actor, db):
            return True
        if manage:
            try:
                PermissionEnforcer.ensure_codes(actor, db, ORGANIZATION_MANAGE, tenant_id=tenant_id,
                                                detail="缺少组织管理权限：button.org.manage")
            except HTTPException:
                return False
            return True
        try:
            # 读主分支 any-of：组织工作台 或 租户模式用户管理（菜单可见即可读页面数据）。
            PermissionEnforcer.ensure_codes(actor, db, ORGANIZATION_READ, USERS_READ, tenant_id=tenant_id,
                                            detail="缺少组织查看权限")
            return True
        except HTTPException:
            # 兜底：无菜单码但持租户管理台角色（L2/L3）→ 角色可见性语义放行。
            return PermissionEnforcer.user_has_any_role(actor, db, CONSOLE_ADMIN_ROLE_KEYS, tenant_id=tenant_id)

    @staticmethod
    def require_organization_admin_access(
        actor: User,
        tenant_id: UUID,
        db: Session,
        *,
        manage: bool = False,
    ) -> None:
        """无有效租户范围管理权限时默认拒绝。"""
        if not AdminAccessGuard.has_organization_admin_access(actor, tenant_id, db, manage=manage):
            action = "管理" if manage else "查看"
            raise HTTPException(status_code=403, detail=f"缺少当前租户组织{action}权限")

    @staticmethod
    def has_active_tenant_membership(actor: User, tenant_id: UUID, db: Session) -> bool:
        """操作者是否在目标租户持有活动成员关系（跨租户访问的成员关系闸门）。

        `scope_at_least` 取操作者跨所有成员关系的最高角色范围，不能证明其属于
        本次请求的目标租户（产品需求 §3.2：租户级数据边界以操作者的活动租户
        成员关系为准）；按 ID 访问的单项端点必须先过这道闸门。
        """
        return db.scalar(select(TenantMembership.id).where(
            TenantMembership.user_id == actor.id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "active",
        ).limit(1)) is not None

    @staticmethod
    def has_application_admin_access(
        actor: User,
        tenant_id: UUID,
        db: Session,
        *,
        manage: bool = False,
        rotate_secret: bool = False,
        application_id: UUID | None = None,
    ) -> bool:
        """L1 代管；租户级及以上管本租户全部应用；应用级仅限绑定且持应用节点的应用。

        未指定 application_id 视为创建入口，仅租户级及以上（应用级不能向上）。
        判权按菜单/按钮节点：读 menu.application_workspace、写 button.apps.manage、
        密钥轮换 button.apps.secret；任命应用管理员的范围闸门在调用方收口。
        P404：应用级不能借「租户内任一应用管理员」走创建/删除。rotate_secret / manage 保留签名。
        P1 收口：非超管必须持有目标租户的活动成员关系，租户 A 的管理员
        不能凭跨成员关系的最高范围秩操作租户 B 的应用。
        """
        from app.services.rbac_guards import PermissionEnforcer
        from app.services.permission_kinds import ROLE_SCOPE_TENANT

        if is_platform_admin_user(actor, db):
            return True
        # 目标租户成员关系闸门：应用级分支按 tenant_id 过滤成员身份本就安全，
        # 这里统一前置拦截，堵住租户级范围分支「有范围秩即放行」的跨租户缺口。
        if not AdminAccessGuard.has_active_tenant_membership(actor, tenant_id, db):
            return False
        # 范围闸门：租户级及以上（超管/租户管理员）管本租户全部应用；
        # 密钥轮换仍需持 button.apps.secret 节点，不能被普通管理权隐式继承。
        if PermissionEnforcer.scope_at_least(actor, db, ROLE_SCOPE_TENANT):
            if rotate_secret:
                return PermissionEnforcer.user_has_management_code(
                    actor, db, APPLICATION_SECRET_ROTATE,
                    tenant_id=tenant_id, application_id=application_id,
                    resource_id=str(application_id) if application_id else None,
                )
            return True
        # 未钉应用 = 租户级生命周期（创建入口）；应用级不能向上。
        if application_id is None:
            return False
        # 应用级：按节点判权——钉住该应用的管理员角色持对应菜单/按钮节点才放行。
        if rotate_secret:
            needed_node = APPLICATION_SECRET_ROTATE
        else:
            needed_node = APPLICATION_MANAGE if manage else APPLICATION_READ
        return PermissionEnforcer.user_has_management_code(
            actor, db, needed_node,
            tenant_id=tenant_id, application_id=application_id,
            resource_id=str(application_id) if application_id else None,
        )

    @staticmethod
    def require_application_admin_access(
        actor: User,
        tenant_id: UUID,
        db: Session,
        *,
        manage: bool = False,
        rotate_secret: bool = False,
        application_id: UUID | None = None,
    ) -> None:
        """在租户应用管理 API 内默认拒绝；密钥轮换不能被普通 manage 权限隐式继承。"""
        if not AdminAccessGuard.has_application_admin_access(
            actor, tenant_id, db, manage=manage, rotate_secret=rotate_secret,
            application_id=application_id,
        ):
            action = "轮换应用密钥" if rotate_secret else "管理应用" if manage else "查看应用"
            raise HTTPException(status_code=403, detail=f"缺少当前租户{action}权限")

    @staticmethod
    def list_readable_application_capabilities(
        actor: User,
        tenant_id: UUID,
        db: Session,
    ) -> dict[UUID, dict[str, bool]]:
        """批量筛选可读应用：L1 全量；L3 本租户全可管；否则按有效角色钉住的应用（及租户级码兼容）。

        列表用有效角色并集；单项写/轮换仍走 has_application_admin_access。
        """
        from app.services.rbac_guards import PermissionEnforcer
        from app.services.role_provisioning import L3_ROLE_KEY

        if is_platform_admin_user(actor, db):
            applications = db.scalars(select(Application).where(Application.tenant_id == tenant_id)).all()
            return {
                application.id: {"can_manage": True, "can_rotate_secret": True}
                for application in applications
            }

        active_tenant = db.scalar(select(Tenant.id).where(
            Tenant.id == tenant_id, Tenant.status == "active",
        ))
        membership = db.scalar(select(TenantMembership).where(
            TenantMembership.user_id == actor.id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "active",
        ))
        if not active_tenant or not membership:
            return {}

        # L3 与写路径对齐：不依赖模板是否仍持 app.manage 码。
        if PermissionEnforcer.user_has_any_role(actor, db, (L3_ROLE_KEY,), tenant_id=tenant_id):
            applications = db.scalars(select(Application).where(Application.tenant_id == tenant_id)).all()
            return {
                application.id: {"can_manage": True, "can_rotate_secret": True}
                for application in applications
            }

        applications = db.scalars(select(Application).where(
            Application.tenant_id == tenant_id,
        )).all()
        if not applications:
            return {}

        effective_roles = EffectiveRoleResolver.list_effective_roles(
            db, membership_id=membership.id, tenant_id=tenant_id, application_id=None,
        )
        # 应用级授权需要按每个应用单独求值；数量有限（租户应用数），可接受。
        per_application_roles: dict[UUID, list[Role]] = {}
        for application in applications:
            per_application_roles[application.id] = EffectiveRoleResolver.list_effective_roles(
                db, membership_id=membership.id, tenant_id=tenant_id,
                application_id=application.id,
            )

        all_roles = {role.id: role for role in effective_roles}
        for roles in per_application_roles.values():
            for role in roles:
                all_roles[role.id] = role
        grant_rows = db.execute(
            select(RolePermission.role_id, Role.application_id, Permission.code, RolePermission.resource_id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                RolePermission.role_id.in_(all_roles) if all_roles else False,
                Permission.status == "active",
                Permission.code.in_((APPLICATION_READ, APPLICATION_MANAGE, APPLICATION_SECRET_ROTATE)),
            )
        ).all()

        grants_by_role: dict[UUID, list[tuple]] = {}
        for role_id, role_application_id, code, resource_id in grant_rows:
            grants_by_role.setdefault(role_id, []).append((role_application_id, code, resource_id))

        def matched_codes_for(role_ids: list[UUID], application_id_value: UUID) -> set[str]:
            """汇总一组角色在指定应用上命中的管理码（resource_id 为空表示通用授权）。"""
            matched: set[str] = set()
            for role_id in role_ids:
                for _, code, resource_id in grants_by_role.get(role_id, []):
                    if resource_id is None or resource_id == str(application_id_value):
                        matched.add(code)
            return matched

        capabilities: dict[UUID, dict[str, bool]] = {}
        for application in applications:
            # 租户级角色授予的应用码 + 钉住该应用的角色授权，合并为该应用能力。
            matched_codes = matched_codes_for(
                [role.id for role in effective_roles], application.id,
            ) | matched_codes_for(
                [role.id for role in per_application_roles[application.id]], application.id,
            )
            can_manage = APPLICATION_MANAGE in matched_codes
            if APPLICATION_READ not in matched_codes and not can_manage:
                # secret.rotate 不能据此枚举应用或暴露应用资料。
                continue
            capabilities[application.id] = {
                "can_manage": can_manage,
                "can_rotate_secret": APPLICATION_SECRET_ROTATE in matched_codes,
            }
        return capabilities
