import { defineAsyncComponent, type Component } from 'vue'
import FeatureLoadError from '../shared/components/FeatureLoadError.vue'
import FeatureLoading from '../shared/components/FeatureLoading.vue'

// 异步 feature 定义独立模块，避免与 App 主壳挤在同一静态分析图里，便于 Vite 按路由拆包。
type FeatureLoader = () => Promise<{ default: Component }>
const loadFeature = (loader: FeatureLoader) => defineAsyncComponent({
  loader,
  loadingComponent: FeatureLoading,
  errorComponent: FeatureLoadError,
  delay: 120,
  timeout: 30_000,
})

export const AuthorizationSimulator = loadFeature(() => import('../features/access-control/AuthorizationSimulator.vue'))
export const GroupManagement = loadFeature(() => import('../features/groups/GroupManagement.vue'))
export const LoginThemeManagement = loadFeature(() => import('../features/themes/LoginThemeManagement.vue'))
export const OverviewPage = loadFeature(() => import('../features/overview/OverviewPage.vue'))
export const ModelGovernancePage = loadFeature(() => import('../features/models/ModelGovernancePage.vue'))
export const TenantManagement = loadFeature(() => import('../features/tenants/TenantManagement.vue'))
export const ApplicationManagement = loadFeature(() => import('../features/applications/ApplicationManagement.vue'))
export const ApplicationRoleManagement = loadFeature(() => import('../features/application-roles/ApplicationRoleManagement.vue'))
export const AuditLogPage = loadFeature(() => import('../features/audit/AuditLogPage.vue'))
export const InvitationManagement = loadFeature(() => import('../features/invitations/InvitationManagement.vue'))
export const RoleManagement = loadFeature(() => import('../features/roles/RoleManagement.vue'))
export const PermissionCatalog = loadFeature(() => import('../features/permissions/PermissionCatalog.vue'))
export const UserManagement = loadFeature(() => import('../features/users/UserManagement.vue'))
export const OrganizationManagement = loadFeature(() => import('../features/organizations/OrganizationManagement.vue'))
export const TenantAccessManagement = loadFeature(() => import('../features/tenant-admin/TenantAccessManagement.vue'))
export const ProjectIntegrationPage = loadFeature(() => import('../features/integration/ProjectIntegrationPage.vue'))
