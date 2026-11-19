/**
 * Admin page component catalog (App.vue template still wires per-page props;
 * keep this map as the single inventory for PageKey → async feature).
 */
import type { Component } from 'vue'
import type { PageKey } from '@/router/navigation'
import {
  ApplicationWorkspace,
  AuditLogPage,
  AuthorizationSimulator,
  GroupManagement,
  IntegrationGuidePage,
  InvitationManagement,
  LoginThemeManagement,
  ModelGovernancePage,
  ModelTestPage,
  OrganizationWorkspace,
  OverviewPage,
  RoleManagement,
  TenantAccessManagement,
  TenantManagement,
  UserManagement,
  ProfilePage,
} from '@/router/loaders'

export const PAGE_COMPONENTS: Partial<Record<PageKey, Component>> = {
  overview: OverviewPage,
  profile: ProfilePage,
  organization_workspace: OrganizationWorkspace,
  users: UserManagement,
  groups: GroupManagement,
  invitations: InvitationManagement,
  application_workspace: ApplicationWorkspace,
  integration_guide: IntegrationGuidePage,
  roles: RoleManagement,
  tenants: TenantManagement,
  tenant_access: TenantAccessManagement,
  themes: LoginThemeManagement,
  models: ModelGovernancePage,
  model_test: ModelTestPage,
  model_usage: ModelGovernancePage,
  audit: AuditLogPage,
  authorization_simulation: AuthorizationSimulator,
}
