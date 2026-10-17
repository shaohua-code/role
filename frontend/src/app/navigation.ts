/** 管理台的页面白名单和展示标题；按钮与窄屏选择器共用同一数据源。 */
export type PageKey = 'overview' | 'tenants' | 'applications' | 'project_integration' | 'application_roles' | 'users' | 'invitations' | 'groups' | 'organizations' | 'tenant_access' | 'roles' | 'permissions' | 'authorization_simulation' | 'models' | 'model_usage' | 'themes' | 'audit'

/** PageKey 与浏览器 path 的一一映射，供 vue-router 与侧栏链接共用。 */
export const PAGE_PATHS: Record<PageKey, string> = {
  overview: '/overview',
  tenants: '/tenants',
  applications: '/applications',
  project_integration: '/project-integration',
  application_roles: '/application-roles',
  users: '/users',
  invitations: '/invitations',
  groups: '/groups',
  organizations: '/organizations',
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
  icon: string
  label: string
}

export const NAV_ITEMS: NavigationItem[] = [
  { key: 'overview', icon: '▦', label: '工作台' },
  { key: 'tenants', icon: '◫', label: '租户管理' },
  { key: 'applications', icon: '▣', label: '应用管理' },
  { key: 'project_integration', icon: '⎈', label: '新项目接入' },
  { key: 'users', icon: '♙', label: '用户管理' },
  { key: 'invitations', icon: '✉', label: '成员邀请' },
  { key: 'groups', icon: '♧', label: '用户组' },
  { key: 'organizations', icon: '⌂', label: '组织管理' },
  { key: 'roles', icon: '⌘', label: '角色管理' },
  { key: 'permissions', icon: '⛨', label: '权限目录' },
  { key: 'authorization_simulation', icon: '⊙', label: '授权模拟' },
  { key: 'models', icon: '✧', label: '模型管理' },
  { key: 'model_usage', icon: '◴', label: '模型用量' },
  { key: 'themes', icon: '◐', label: '登录主题' },
  { key: 'audit', icon: '≋', label: '审计日志' },
]

/** 租户管理员只看到已实现且具备租户级服务端授权的页面。 */
export const TENANT_NAV_ITEMS: NavigationItem[] = [
  { key: 'organizations', icon: '⌂', label: '组织管理' },
  { key: 'tenant_access', icon: '♙', label: '成员与数据范围' },
  { key: 'applications', icon: '▣', label: '应用管理' },
  { key: 'application_roles', icon: '⌘', label: '应用角色与成员' },
]

export const PAGE_INFO: Record<PageKey, { title: string }> = {
  overview: { title: '工作台' },
  tenants: { title: '租户管理' },
  applications: { title: '应用管理' },
  project_integration: { title: '新项目接入' },
  application_roles: { title: '应用角色与成员' },
  users: { title: '用户管理' },
  roles: { title: '角色管理' },
  groups: { title: '用户组' },
  invitations: { title: '成员邀请' },
  organizations: { title: '组织管理' },
  tenant_access: { title: '成员与数据范围' },
  authorization_simulation: { title: '授权模拟' },
  permissions: { title: '权限目录' },
  models: { title: '模型管理' },
  model_usage: { title: '模型用量' },
  themes: { title: '登录主题' },
  audit: { title: '审计日志' },
}
