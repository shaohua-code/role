import { defineAsyncComponent, type Component } from 'vue'
import FeatureLoadError from '@/components/FeatureLoadError.vue'
import FeatureLoading from '@/components/FeatureLoading.vue'

// 异步 feature 定义独立模块，避免与 App 主壳挤在同一静态分析图里，便于 Vite 按路由拆包。
type FeatureLoader = () => Promise<{ default: Component }>
const loadFeature = (loader: FeatureLoader) => defineAsyncComponent({
  loader,
  loadingComponent: FeatureLoading,
  errorComponent: FeatureLoadError,
  delay: 120,
  timeout: 30_000,
})

export const AuthorizationSimulator = loadFeature(() => import('@/views/access-control/AuthorizationSimulator.vue'))
export const GroupManagement = loadFeature(() => import('@/views/groups/GroupManagement.vue'))
export const LoginThemeManagement = loadFeature(() => import('@/views/themes/LoginThemeManagement.vue'))
export const OverviewPage = loadFeature(() => import('@/views/overview/OverviewPage.vue'))
export const ModelGovernancePage = loadFeature(() => import('@/views/models/ModelGovernancePage.vue'))
export const TenantManagement = loadFeature(() => import('@/views/tenants/TenantManagement.vue'))
export const ApplicationManagement = loadFeature(() => import('@/views/applications/ApplicationManagement.vue'))
export const ApplicationWorkspace = loadFeature(() => import('@/views/application-workspace/index.vue'))
export const ApplicationRoleManagement = loadFeature(() => import('@/views/application-roles/ApplicationRoleManagement.vue'))
export const AuditLogPage = loadFeature(() => import('@/views/audit/AuditLogPage.vue'))
export const InvitationManagement = loadFeature(() => import('@/views/invitations/InvitationManagement.vue'))
export const RoleManagement = loadFeature(() => import('@/views/roles/RoleManagement.vue'))
export const PermissionCatalog = loadFeature(() => import('@/views/permissions/PermissionCatalog.vue'))
export const UserManagement = loadFeature(() => import('@/views/users/UserManagement.vue'))
export const OrganizationManagement = loadFeature(() => import('@/views/organizations/OrganizationManagement.vue'))
export const OrganizationWorkspace = loadFeature(() => import('@/views/organization-workspace/index.vue'))
export const TenantAccessManagement = loadFeature(() => import('@/views/tenant-admin/TenantAccessManagement.vue'))
