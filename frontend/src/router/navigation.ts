import type { Component } from 'vue'
import {
  ApartmentOutlined,
  AppstoreOutlined,
  AuditOutlined,
  BankOutlined,
  ClusterOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  HomeOutlined,
  MailOutlined,
  SafetyCertificateOutlined,
  SafetyOutlined,
  SkinOutlined,
  TeamOutlined,
  UserOutlined,
} from '@/plugins/icons'

/** Admin page keys. 接入向导已下线；运营总览为 L1 入口，日常主路径是两个工作台，列表页进「高级管理」。 */
export type PageKey = 'overview' | 'tenants' | 'applications' | 'application_workspace' | 'application_roles' | 'users' | 'invitations' | 'groups' | 'organizations' | 'organization_workspace' | 'tenant_access' | 'roles' | 'permissions' | 'authorization_simulation' | 'models' | 'model_usage' | 'themes' | 'audit'

/** Sidebar groups aligned with user-centent IA + 高级收口。 */
export type NavGroupKey = 'root' | 'identity' | 'access' | 'advanced' | 'platform' | 'ops'

export interface NavGroupMeta {
  key: NavGroupKey
  label: string
}

export const PAGE_PATHS: Record<PageKey, string> = {
  overview: '/overview',
  tenants: '/tenants',
  applications: '/applications',
  application_workspace: '/application-workspace',
  application_roles: '/application-roles',
  users: '/users',
  invitations: '/invitations',
  groups: '/groups',
  organizations: '/organizations',
  organization_workspace: '/organization-workspace',
  tenant_access: '/tenant-access',
  roles: '/roles',
  permissions: '/permissions',
  authorization_simulation: '/authorization-simulation',
  models: '/models',
  model_usage: '/model-usage',
  themes: '/themes',
  audit: '/audit',
}

export interface NavigationItem {
  key: PageKey
  icon: Component
  label: string
  group: NavGroupKey
  requiredPermissions: string[]
}

export const NAV_GROUPS: NavGroupMeta[] = [
  { key: 'root', label: '' },
  { key: 'identity', label: '身份与组织' },
  { key: 'access', label: '应用与权限' },
  { key: 'advanced', label: '高级管理' },
  { key: 'platform', label: '平台治理' },
  { key: 'ops', label: '审计与验证' },
]

/**
 * 主路径：组织/应用工作台 + 用户多角色。
 * 散页列表（应用/角色/权限编码/组织/用户组）降级到「高级管理」，路由与深链保留。
 */
export const NAV_ITEMS: NavigationItem[] = [
  { key: 'overview', icon: AppstoreOutlined, label: '运营总览', group: 'root', requiredPermissions: ['platform.overview.read'] },

  { key: 'organization_workspace', icon: ApartmentOutlined, label: '组织工作台', group: 'identity', requiredPermissions: ['org.read', 'org.group.read'] },
  { key: 'users', icon: UserOutlined, label: '用户管理', group: 'identity', requiredPermissions: ['platform.account.read', 'org.member.read'] },
  { key: 'invitations', icon: MailOutlined, label: '成员邀请', group: 'identity', requiredPermissions: ['org.invite.manage'] },

  { key: 'application_workspace', icon: ApartmentOutlined, label: '应用工作台', group: 'access', requiredPermissions: ['app.read', 'rbac.app_role.read', 'rbac.role.read'] },

  { key: 'applications', icon: ClusterOutlined, label: '应用管理', group: 'advanced', requiredPermissions: ['app.read', 'app.manage'] },
  { key: 'roles', icon: SafetyCertificateOutlined, label: '角色管理', group: 'advanced', requiredPermissions: ['rbac.role.read', 'rbac.app_role.read'] },
  { key: 'permissions', icon: SafetyOutlined, label: '权限编码', group: 'advanced', requiredPermissions: ['rbac.permission.read'] },
  { key: 'organizations', icon: HomeOutlined, label: '组织管理', group: 'advanced', requiredPermissions: ['org.read'] },
  { key: 'groups', icon: TeamOutlined, label: '用户组', group: 'advanced', requiredPermissions: ['org.group.read'] },

  { key: 'tenants', icon: BankOutlined, label: '租户管理', group: 'platform', requiredPermissions: ['platform.tenant.read'] },
  { key: 'themes', icon: SkinOutlined, label: '登录主题', group: 'platform', requiredPermissions: ['ops.theme.manage'] },
  { key: 'models', icon: DashboardOutlined, label: '模型治理', group: 'platform', requiredPermissions: ['ops.model.read'] },
  { key: 'model_usage', icon: AuditOutlined, label: '模型用量', group: 'platform', requiredPermissions: ['ops.model.read'] },

  { key: 'authorization_simulation', icon: ExperimentOutlined, label: '鉴权模拟', group: 'ops', requiredPermissions: ['ops.authz.simulate'] },
  { key: 'audit', icon: FileSearchOutlined, label: '审计日志', group: 'ops', requiredPermissions: ['ops.audit.read'] },
]

export const TENANT_MERGED_PAGES: Partial<Record<PageKey, PageKey>> = {
  tenant_access: 'users',
  application_roles: 'roles',
}

export const PAGE_INFO: Record<PageKey, { title: string }> = {
  overview: { title: '运营总览' },
  tenants: { title: '租户管理' },
  applications: { title: '应用管理' },
  application_workspace: { title: '应用工作台' },
  application_roles: { title: '应用角色与成员' },
  users: { title: '用户管理' },
  roles: { title: '角色管理' },
  groups: { title: '用户组' },
  invitations: { title: '成员邀请' },
  organizations: { title: '组织管理' },
  organization_workspace: { title: '组织工作台' },
  tenant_access: { title: '成员与数据范围' },
  authorization_simulation: { title: '鉴权模拟' },
  permissions: { title: '权限编码' },
  models: { title: '模型治理' },
  model_usage: { title: '模型用量' },
  themes: { title: '登录主题' },
  audit: { title: '审计日志' },
}

export function buildNavGroups(items: NavigationItem[]): Array<NavGroupMeta & { items: NavigationItem[] }> {
  return NAV_GROUPS
    .map(group => ({
      ...group,
      items: items.filter(item => item.group === group.key),
    }))
    .filter(group => group.items.length > 0)
}
