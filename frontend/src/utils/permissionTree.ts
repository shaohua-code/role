// 权限目录：资源树（侧栏形菜单 + 按钮 + 接口）与数据树。与后端 permission_kinds 同一口径。
export type PermissionKind = 'menu' | 'button' | 'data' | 'api'

export interface PermissionLeaf {
  id: string
  code: string
  description?: string | null
  catalog_namespace?: string
  status?: string
  kind?: PermissionKind
  assigned_role_count?: number
}

export interface PermissionTreeNode {
  key: string
  title: string
  kind: PermissionKind
  code: string | null
  status: string
  assigned_role_count: number
  isLeaf: boolean
  selectable: boolean
  children: PermissionTreeNode[]
  parentCode?: string | null
  parentTitle?: string | null
  prefix?: string
}

export const DATA_SCOPE_TYPES = [
  'self',
  'organization',
  'organization_tree',
  'selected_organizations',
  'tenant',
] as const

export const KIND_LABELS: Record<PermissionKind, string> = {
  menu: '菜单',
  button: '按钮',
  data: '数据权限',
  api: '接口',
}

export const CREATE_KIND_OPTIONS: Array<{ value: PermissionKind; label: string }> = [
  { value: 'menu', label: '子菜单' },
  { value: 'button', label: '按钮' },
  { value: 'api', label: '接口' },
  { value: 'data', label: '数据' },
]

export const DOMAIN_CHIPS: Array<{ key: string; label: string }> = [
  { key: 'platform', label: '平台' },
  { key: 'rbac', label: '角色与授权' },
  { key: 'org', label: '组织与成员' },
  { key: 'app', label: '应用' },
  { key: 'ops', label: '资源与运营' },
]

// 菜单/按钮 ↔ 对应接口：挂码时浅色提示，不自动勾选。
export const MENU_RELATED_APIS: Record<string, string[]> = {
  'menu.overview': ['platform.overview.read'],
  'menu.organization_workspace': ['org.read', 'org.manage'],
  'menu.users': ['platform.account.read', 'platform.account.manage', 'org.member.read', 'org.member.manage'],
  'menu.invitations': ['org.invite.manage'],
  'menu.application_workspace': [
    'app.read', 'app.manage', 'app.secret.rotate',
    'rbac.app_role.read', 'rbac.app_role.manage', 'rbac.app_role.assign',
  ],
  'menu.roles': ['rbac.role.read', 'rbac.role.manage'],
  'menu.permissions': ['rbac.permission.read', 'rbac.permission.manage'],
  'menu.groups': ['org.group.read', 'org.group.manage'],
  'menu.tenants': ['platform.tenant.read', 'platform.tenant.manage'],
  'menu.themes': ['ops.theme.manage'],
  'menu.models': ['ops.model.read', 'ops.model.manage'],
  'menu.model_usage': ['ops.model.read'],
  'menu.audit': ['ops.audit.read'],
  'menu.authz': ['ops.authz.simulate'],
}

export const BUTTON_RELATED_APIS: Record<string, string[]> = {
  'button.users.manage': ['platform.account.manage'],
  'button.tenants.manage': ['platform.tenant.manage'],
  'button.roles.manage': ['rbac.role.manage', 'org.manage'],
  'button.permissions.manage': ['rbac.permission.manage'],
  'button.org.manage': ['org.manage'],
  'button.groups.manage': ['org.group.manage'],
  'button.invitations.manage': ['org.invite.manage'],
  'button.apps.manage': ['app.manage'],
  'button.apps.secret': ['app.secret.rotate'],
  'button.app_role.manage': ['rbac.app_role.manage'],
  'button.app_role.assign': ['rbac.app_role.assign'],
  'button.models.manage': ['ops.model.manage'],
  'button.themes.manage': ['ops.theme.manage'],
}

const MENU_BUTTONS: Record<string, string[]> = {
  'menu.organization_workspace': ['button.org.manage'],
  'menu.users': ['button.users.manage'],
  'menu.invitations': ['button.invitations.manage'],
  'menu.application_workspace': [
    'button.apps.manage', 'button.apps.secret',
    'button.app_role.manage', 'button.app_role.assign',
  ],
  'menu.roles': ['button.roles.manage'],
  'menu.permissions': ['button.permissions.manage'],
  'menu.groups': ['button.groups.manage'],
  'menu.tenants': ['button.tenants.manage'],
  'menu.themes': ['button.themes.manage'],
  'menu.models': ['button.models.manage'],
}

const MENU_GROUPS: Array<{ key: string; title: string; codes: string[] }> = [
  { key: 'identity', title: '身份与组织', codes: ['menu.organization_workspace', 'menu.users', 'menu.invitations'] },
  { key: 'access', title: '应用与权限', codes: ['menu.application_workspace'] },
  { key: 'advanced', title: '高级管理', codes: ['menu.roles', 'menu.permissions', 'menu.groups'] },
  { key: 'platform', title: '平台治理', codes: ['menu.tenants', 'menu.themes', 'menu.models', 'menu.model_usage'] },
  { key: 'ops', title: '审计与验证', codes: ['menu.authz', 'menu.audit'] },
]

export function relatedApiCodes(code: string): string[] {
  if (MENU_RELATED_APIS[code]) return MENU_RELATED_APIS[code]
  if (BUTTON_RELATED_APIS[code]) return BUTTON_RELATED_APIS[code]
  const parts = code.split('.')
  while (parts.length > 1) {
    parts.pop()
    const prefix = parts.join('.')
    if (MENU_RELATED_APIS[prefix]) return MENU_RELATED_APIS[prefix]
    if (BUTTON_RELATED_APIS[prefix]) return BUTTON_RELATED_APIS[prefix]
  }
  return []
}

export function kindIconType(kind: PermissionKind): 'menu' | 'button' | 'data_rule' {
  if (kind === 'button') return 'button'
  if (kind === 'data') return 'data_rule'
  return 'menu'
}

export function inferPermissionKind(code: string): PermissionKind {
  if (code.startsWith('menu.')) return 'menu'
  if (code.startsWith('button.')) return 'button'
  const split = splitDataScopeCode(code)
  if (split) return 'data'
  return 'api'
}

export function splitDataScopeCode(code: string): { parent: string; scopeType: string } | null {
  const marker = '.scope.'
  const at = code.lastIndexOf(marker)
  if (at < 0) return null
  const parent = code.slice(0, at)
  const scopeType = code.slice(at + marker.length)
  if (!parent || !(DATA_SCOPE_TYPES as readonly string[]).includes(scopeType)) return null
  return { parent, scopeType }
}

function leaf(item: PermissionLeaf, extra: Partial<PermissionTreeNode> = {}): PermissionTreeNode {
  return {
    key: item.id,
    title: item.description || item.code,
    kind: item.kind || inferPermissionKind(item.code),
    code: item.code,
    status: item.status || 'active',
    assigned_role_count: item.assigned_role_count || 0,
    isLeaf: true,
    selectable: true,
    children: [],
    prefix: `${item.code}.`,
    parentCode: extra.parentCode ?? null,
    parentTitle: extra.parentTitle ?? null,
    ...extra,
  }
}

function menuNode(item: PermissionLeaf, children: PermissionTreeNode[], extra: Partial<PermissionTreeNode> = {}): PermissionTreeNode {
  return {
    key: item.id,
    title: item.description || item.code,
    kind: 'menu',
    code: item.code,
    status: item.status || 'active',
    assigned_role_count: item.assigned_role_count || 0,
    isLeaf: children.length === 0,
    selectable: true,
    children,
    prefix: `${item.code}.`,
    parentCode: extra.parentCode ?? null,
    parentTitle: extra.parentTitle ?? null,
    ...extra,
  }
}

function group(key: string, title: string, kind: PermissionKind, children: PermissionTreeNode[], prefix = ''): PermissionTreeNode {
  return {
    key,
    title,
    kind,
    code: null,
    status: 'active',
    assigned_role_count: 0,
    isLeaf: false,
    selectable: false,
    children,
    prefix,
    parentCode: null,
    parentTitle: null,
  }
}

export function createPrefixForNode(node: PermissionTreeNode): string {
  if (node.code) return `${node.code}.`
  if (node.prefix) return node.prefix
  return ''
}

function longestMenuParent(code: string, menuCodes: Set<string>): string | null {
  const parts = code.split('.')
  for (let end = parts.length - 1; end > 0; end -= 1) {
    const candidate = parts.slice(0, end).join('.')
    if (menuCodes.has(candidate)) return candidate
  }
  return null
}

function buildDataTree(items: PermissionLeaf[], byCode: Map<string, PermissionLeaf>): PermissionTreeNode[] {
  const dataByNs = new Map<string, Map<string, PermissionTreeNode[]>>()
  for (const item of items) {
    const split = splitDataScopeCode(item.code)
    const parentCode = split?.parent || item.code
    const namespace = item.catalog_namespace || parentCode.split('.')[0] || 'other'
    const parentTitle = byCode.get(parentCode)?.description || parentCode
    if (!dataByNs.has(namespace)) dataByNs.set(namespace, new Map())
    const parents = dataByNs.get(namespace) as Map<string, PermissionTreeNode[]>
    const packed = `${parentCode}|${parentTitle}`
    if (!parents.has(packed)) parents.set(packed, [])
    parents.get(packed)?.push(leaf(item, { parentCode, parentTitle }))
  }
  const roots: PermissionTreeNode[] = []
  for (const [namespace, parents] of [...dataByNs.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    const parentNodes: PermissionTreeNode[] = []
    for (const [packed, leaves] of [...parents.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
      const [parentCode, parentTitle] = packed.split('|')
      parentNodes.push(group(`data:${parentCode}`, parentTitle, 'data', leaves, `${parentCode}.scope.`))
    }
    roots.push(group(`data-ns:${namespace}`, namespace, 'data', parentNodes, `${namespace}.`))
  }
  return roots
}

export function buildPermissionTrees(items: PermissionLeaf[]): { resource: PermissionTreeNode[]; data: PermissionTreeNode[] } {
  const byCode = new Map<string, PermissionLeaf>()
  for (const raw of items) {
    const kind = raw.kind || inferPermissionKind(raw.code)
    byCode.set(raw.code, { ...raw, kind })
  }
  const menuCodes = new Set([...byCode.entries()].filter(([, item]) => item.kind === 'menu').map(([code]) => code))
  const used = new Set<string>()

  const attachUnderMenu = (menuCode: string): PermissionTreeNode[] => {
    const children: PermissionTreeNode[] = []
    const menuItem = byCode.get(menuCode)
    const menuTitle = menuItem?.description || menuCode
    for (const btn of MENU_BUTTONS[menuCode] || []) {
      const item = byCode.get(btn)
      if (!item) continue
      children.push(leaf(item, { parentCode: menuCode, parentTitle: menuTitle }))
      used.add(btn)
    }
    for (const api of MENU_RELATED_APIS[menuCode] || []) {
      const item = byCode.get(api)
      if (!item) continue
      children.push(leaf(item, { parentCode: menuCode, parentTitle: menuTitle }))
      used.add(api)
    }
    const nestedMenus: PermissionLeaf[] = []
    const nestedOthers: PermissionLeaf[] = []
    const prefix = `${menuCode}.`
    for (const [code, item] of byCode.entries()) {
      if (code === menuCode || used.has(code) || !code.startsWith(prefix) || item.kind === 'data') continue
      if (longestMenuParent(code, menuCodes) !== menuCode) continue
      if (item.kind === 'menu') nestedMenus.push(item)
      else nestedOthers.push(item)
    }
    for (const item of nestedOthers) {
      children.push(leaf(item, { parentCode: menuCode, parentTitle: menuTitle }))
      used.add(item.code)
    }
    for (const item of nestedMenus.sort((a, b) => a.code.localeCompare(b.code))) {
      used.add(item.code)
      children.push(menuNode(item, attachUnderMenu(item.code), { parentCode: menuCode, parentTitle: menuTitle }))
    }
    return children
  }

  const resource: PermissionTreeNode[] = []
  const overview = byCode.get('menu.overview')
  if (overview) {
    used.add('menu.overview')
    resource.push(menuNode(overview, attachUnderMenu('menu.overview')))
  }
  for (const block of MENU_GROUPS) {
    const groupChildren: PermissionTreeNode[] = []
    for (const code of block.codes) {
      const item = byCode.get(code)
      if (!item) continue
      used.add(code)
      groupChildren.push(menuNode(item, attachUnderMenu(code), { parentTitle: block.title }))
    }
    if (groupChildren.length) resource.push(group(`nav:${block.key}`, block.title, 'menu', groupChildren, 'menu.'))
  }
  const strayTop = [...menuCodes].filter(code => !used.has(code) && !longestMenuParent(code, menuCodes)).sort()
  if (strayTop.length) {
    const otherChildren = strayTop.map(code => {
      used.add(code)
      return menuNode(byCode.get(code) as PermissionLeaf, attachUnderMenu(code))
    })
    resource.push(group('nav:other', '其他', 'menu', otherChildren, 'menu.'))
  }
  const leftovers = [...byCode.entries()]
    .filter(([code, item]) => !used.has(code) && item.kind !== 'data')
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([, item]) => leaf(item))
  if (leftovers.length) resource.push(group('nav:unmapped', '未挂载', 'api', leftovers))

  const dataItems = [...byCode.values()].filter(item => item.kind === 'data')
  return { resource, data: buildDataTree(dataItems, byCode) }
}

export function buildPermissionTree(items: PermissionLeaf[]): PermissionTreeNode[] {
  return buildPermissionTrees(items).resource
}

export function flattenGrantable(nodes: PermissionTreeNode[]): PermissionTreeNode[] {
  const grantable: PermissionTreeNode[] = []
  const walk = (list: PermissionTreeNode[]) => {
    for (const node of list) {
      if (node.selectable && node.code) grantable.push(node)
      if (node.children.length) walk(node.children)
    }
  }
  walk(nodes)
  return grantable
}

export function flattenLeaves(nodes: PermissionTreeNode[]): PermissionTreeNode[] {
  return flattenGrantable(nodes)
}

function nodeMatchesDomain(node: PermissionTreeNode, domains: string[]): boolean {
  if (!domains.length) return true
  const code = node.code || ''
  if (domains.some(domain => code.startsWith(`${domain}.`) || node.key === `api:${domain}` || node.key.startsWith(`api:${domain}:`))) {
    return true
  }
  const related = relatedApiCodes(code)
  if (related.some(api => domains.some(domain => api.startsWith(`${domain}.`)))) return true
  return node.children.some(child => nodeMatchesDomain(child, domains))
}

export function filterPermissionTree(
  nodes: PermissionTreeNode[],
  query: string,
  kinds: PermissionKind[],
  domains: string[] = [],
): PermissionTreeNode[] {
  const keyword = query.trim().toLowerCase()
  const kindSet = new Set(kinds)
  const match = (node: PermissionTreeNode): PermissionTreeNode | null => {
    const nextChildren = node.children.map(match).filter((item): item is PermissionTreeNode => Boolean(item))
    const selfHit = !keyword
      || node.title.toLowerCase().includes(keyword)
      || (node.code || '').toLowerCase().includes(keyword)
    const kindHit = !kindSet.size || kindSet.has(node.kind) || !node.code
    const domainHit = nodeMatchesDomain(node, domains)
    if (node.selectable && node.code) return selfHit && kindHit && domainHit ? { ...node, children: nextChildren } : (nextChildren.length ? { ...node, children: nextChildren } : null)
    if (!nextChildren.length && !(selfHit && (!kindSet.size || kindSet.has(node.kind)) && domainHit)) return null
    return { ...node, children: nextChildren }
  }
  return nodes.map(match).filter((item): item is PermissionTreeNode => Boolean(item))
}
