"""集中导入 ORM 实体，确保 Alembic 加载元数据时注册完整模型集合。"""

from app.models.application import Application, ApplicationTheme
from app.models.application_resource import ApplicationResource, RoleApplicationResource
from app.models.authorization import Permission, Role, RoleBinding, RolePermission
from app.models.groups import UserGroup, UserGroupMembership, UserGroupRole
from app.models.identity import (
    AuditEvent,
    LoginAttemptBucket,
    PasswordResetThrottle,
    PasswordResetToken,
    PublicRegistrationChallenge,
    PublicRegistrationConsent,
    PublicRegistrationEmailOutbox,
    PublicRegistrationThrottle,
    RefreshSession,
    RevokedAccessToken,
    Tenant,
    TenantMembership,
    User,
    UserInvitation,
)
from app.models.model_catalog import (
    ModelCatalog,
    ModelUsageEvent,
    ModelUsageReservation,
)
from app.models.oidc import (
    OAuthAuthorizationCode,
    OAuthConsentRequest,
    OAuthRefreshToken,
)
from app.models.organization import MembershipOrganization, Organization, RoleDataScope

__all__ = [
    "Permission",
    "Application",
    "ApplicationTheme",
    "ApplicationResource",
    "RoleApplicationResource",
    "AuditEvent",
    "LoginAttemptBucket",
    "PasswordResetThrottle",
    "PasswordResetToken",
    "PublicRegistrationChallenge",
    "PublicRegistrationConsent",
    "PublicRegistrationEmailOutbox",
    "PublicRegistrationThrottle",
    "RefreshSession",
    "RevokedAccessToken",
    "ModelCatalog",
    "ModelUsageEvent",
    "ModelUsageReservation",
    "OAuthAuthorizationCode",
    "OAuthConsentRequest",
    "OAuthRefreshToken",
    "Organization",
    "MembershipOrganization",
    "RoleDataScope",
    "Role",
    "RoleBinding",
    "RolePermission",
    "Tenant",
    "TenantMembership",
    "User",
    "UserInvitation",
    "UserGroup",
    "UserGroupMembership",
    "UserGroupRole",
]
