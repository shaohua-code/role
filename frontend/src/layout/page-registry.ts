/**
 * Admin page component catalog (App.vue template still wires per-page props;
 * keep this map as the single inventory for PageKey → async feature).
 */
import type { Component } from 'vue'
import type { PageKey } from '@/router/navigation'
import {
  ApplicationManagement,
  ApplicationWorkspace,
  ApplicationRoleManagement,
  AuditLogPage,
  AuthorizationSimulator,
  GroupManagement,
  InvitationManagement,
  LoginThemeManagement,
  ModelGovernancePage,
  OrganizationManagement,
  OrganizationWorkspace,
  OverviewPage,
  PermissionCatalog,
  RoleManagement,
  TenantAccessManagement,
  TenantManagement,
  UserManagement,
} from '@/router/loaders'

export const PAGE_COMPONENTS: Partial<Record<PageKey, Component>> = {
  overview: OverviewPage,
  organization_workspace: OrganizationWorkspace,
  users: UserManagement,
  groups: GroupManagement,
  invitations: InvitationManagement,
  application_workspace: ApplicationWorkspace,
  applications: ApplicationManagement,
  application_roles: ApplicationRoleManagement,
  roles: RoleManagement,
  permissions: PermissionCatalog,
  organizations: OrganizationManagement,
  tenants: TenantManagement,
  tenant_access: TenantAccessManagement,
  themes: LoginThemeManagement,
  models: ModelGovernancePage,
  model_usage: ModelGovernancePage,
  audit: AuditLogPage,
  authorization_simulation: AuthorizationSimulator,
}

export function createVisitedPages(initial?: PageKey): Set<PageKey> {
  return new Set<PageKey>(initial ? [initial] : [])
}
