// 权限目录：资源树（侧栏形菜单 + 按钮 + 接口）与数据树。
// F2 码表契约单一来源：菜单↔按钮↔接口映射、层级码集、模板码数全部来自
// GET /admin/permissions/tree 响应的 meta（与后端 permission_kinds 同源），
// 本文件只保留纯函数——树组装与映射查询均以传入的 meta 为准，零硬编码。
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

// ===== tree 响应 meta 契约（F2）：与后端 _permission_tree_meta 输出一一对应 =====

/**
 * 菜单契约：单个菜单映射的按钮码与授权下限（与后端 MENU_CATALOG / MENU_BUTTONS 同源）。
 * 管理面接口码已从契约删除：apis 仅作旧快照兼容保留（新响应不再下发）。
 */
export interface PermissionMenuMeta {
  code: string
  name: string
  /** 节点授权下限（super/tenant/app）：低于该范围的角色不可被授予本节点。 */
  min_scope?: string
  apis?: string[]
  buttons: string[]
  /** 按钮级授权下限：按钮可高于宿主菜单（如任命应用管理员=租户级、菜单=应用级）；缺省回落菜单 min_scope。 */
  button_scopes?: Record<string, string>
}

/** 层级可见码集：三管理员模板各级持有的管理面节点码全集（节点=菜单/按钮）。 */
export interface PermissionLevelScopes {
  platform_admin: string[]
  tenant_admin: string[]
  app_admin: string[]
}

/** 三管理员模板节点数（后端运行时 len 推导）。 */
export interface PermissionTemplateSizes {
  platform_admin: number
  tenant_admin: number
  app_admin: number
}

/** 授权范围下拉契约项：value/label/rank，前端按操作者 scope 的秩过滤可选项。 */
export interface PermissionScopeOption {
  value: string
  label: string
  rank: number
}

/** tree 响应 meta：前端零硬编码所需的全部契约数据。 */
export interface PermissionTreeMeta {
  menus: PermissionMenuMeta[]
  level_scopes: PermissionLevelScopes
  template_sizes: PermissionTemplateSizes
  scopes: PermissionScopeOption[]
}

/** 范围秩表：与后端 ROLE_SCOPE_RANK 一致（member 不参与配权，仅兜底比较用）。 */
export const ROLE_SCOPE_RANK: Record<string, number> = {
  member: 0,
  app: 1,
  tenant: 2,
  super: 3,
}

/** 空契约兜底：契约缓存未就绪时组树/查映射用（调用方应等待 ensurePermissionContract）。 */
export const EMPTY_PERMISSION_TREE_META: PermissionTreeMeta = {
  menus: [],
  level_scopes: { platform_admin: [], tenant_admin: [], app_admin: [] },
  template_sizes: { platform_admin: 0, tenant_admin: 0, app_admin: 0 },
  scopes: [],
}

// ===== tree API 原始节点（snake_case）→ 前端节点（camelCase）归一化 =====

/** 后端 tree 端点的原始节点形状（兼容 is_leaf / isLeaf 双写）。 */
export interface PermissionTreeApiNode {
  key: string
  title: string
  kind: PermissionKind
  code: string | null
  status: string
  assigned_role_count: number
  is_leaf?: boolean
  isLeaf?: boolean
  selectable?: boolean
  prefix?: string
  parent_code?: string | null
  parent_title?: string | null
  children?: PermissionTreeApiNode[]
}

/** 单个 API 节点归一化为前端树节点（递归处理子级）。 */
export function normalizeTreeApiNode(node: PermissionTreeApiNode): PermissionTreeNode {
  const children = (node.children || []).map(normalizeTreeApiNode)
  return {
    key: node.key,
    title: node.title,
    kind: node.kind,
    code: node.code,
    status: node.status,
    assigned_role_count: node.assigned_role_count || 0,
    isLeaf: Boolean(node.is_leaf ?? node.isLeaf),
    selectable: node.selectable !== false,
    children,
    prefix: node.prefix || '',
    parentCode: node.parent_code || null,
    parentTitle: node.parent_title || null,
  }
}

/** 批量归一化后端 tree 节点。 */
export function normalizeTreeApiNodes(nodes: PermissionTreeApiNode[]): PermissionTreeNode[] {
  return nodes.map(normalizeTreeApiNode)
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

/**
 * 码 → 相关接口清单（纯函数，映射完全来自传入的 meta.menus）：
 * 新契约管理面已无接口码（menus 不再下发 apis），菜单/按钮码返回空清单；
 * 数据范围叶子码仍回溯父码，接口码仍反查所属菜单（业务面兼容保留）。
 */
export function relatedApiCodes(code: string, menus: PermissionMenuMeta[] = []): string[] {
  const menu = menus.find(item => item.code === code)
  if (menu) return menu.apis || []
  const buttonOwner = menus.find(item => item.buttons.includes(code))
  if (buttonOwner) return buttonOwner.apis || []
  const split = splitDataScopeCode(code)
  if (split) return relatedApiCodes(split.parent, menus)
  const apiOwner = menus.find(item => (item.apis || []).includes(code))
  if (apiOwner) return apiOwner.apis || []
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

/**
 * 组装资源树 + 数据树（纯函数）：菜单→按钮的挂载关系完全由传入 meta 驱动。
 * 管理面只有菜单/按钮两类节点；顶层按 meta.menus 顺序平铺契约菜单；
 * 契约外的顶层菜单进「其他」；未挂载码进「未挂载」。
 */
export function buildPermissionTrees(items: PermissionLeaf[], meta: PermissionTreeMeta): { resource: PermissionTreeNode[]; data: PermissionTreeNode[] } {
  const byCode = new Map<string, PermissionLeaf>()
  for (const raw of items) {
    const kind = raw.kind || inferPermissionKind(raw.code)
    byCode.set(raw.code, { ...raw, kind })
  }
  const menuCodes = new Set([...byCode.entries()].filter(([, item]) => item.kind === 'menu').map(([code]) => code))
  const menuMetaByCode = new Map(meta.menus.map(item => [item.code, item]))
  const used = new Set<string>()

  // 菜单下挂按钮/子菜单：按钮清单来自契约映射，不再读前端硬编码表。
  const attachUnderMenu = (menuCode: string): PermissionTreeNode[] => {
    const children: PermissionTreeNode[] = []
    const menuItem = byCode.get(menuCode)
    const menuTitle = menuItem?.description || menuCode
    const menuMeta = menuMetaByCode.get(menuCode)
    for (const btn of menuMeta?.buttons || []) {
      const item = byCode.get(btn)
      if (!item) continue
      children.push(leaf(item, { parentCode: menuCode, parentTitle: menuTitle }))
      used.add(btn)
    }
    // 管理面接口码已从契约删除：菜单下只挂按钮与嵌套菜单/未挂载码。
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
  // 顶层按契约菜单顺序平铺（meta.menus 顺序即后端 MENU_CATALOG 顺序）。
  for (const menuMeta of meta.menus) {
    const item = byCode.get(menuMeta.code)
    if (!item) continue
    used.add(menuMeta.code)
    resource.push(menuNode(item, attachUnderMenu(menuMeta.code)))
  }
  // 契约外兜底：库里有但契约未列的顶层菜单码进「其他」组。
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

export function buildPermissionTree(items: PermissionLeaf[], meta: PermissionTreeMeta): PermissionTreeNode[] {
  return buildPermissionTrees(items, meta).resource
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

function nodeMatchesDomain(node: PermissionTreeNode, domains: string[], menus: PermissionMenuMeta[]): boolean {
  if (!domains.length) return true
  const code = node.code || ''
  if (domains.some(domain => code.startsWith(`${domain}.`) || node.key === `api:${domain}` || node.key.startsWith(`api:${domain}:`))) {
    return true
  }
  const related = relatedApiCodes(code, menus)
  if (related.some(api => domains.some(domain => api.startsWith(`${domain}.`)))) return true
  return node.children.some(child => nodeMatchesDomain(child, domains, menus))
}

export function filterPermissionTree(
  nodes: PermissionTreeNode[],
  query: string,
  kinds: PermissionKind[],
  domains: string[] = [],
  menus: PermissionMenuMeta[] = [],
): PermissionTreeNode[] {
  const keyword = query.trim().toLowerCase()
  const kindSet = new Set(kinds)
  const match = (node: PermissionTreeNode): PermissionTreeNode | null => {
    const nextChildren = node.children.map(match).filter((item): item is PermissionTreeNode => Boolean(item))
    const selfHit = !keyword
      || node.title.toLowerCase().includes(keyword)
      || (node.code || '').toLowerCase().includes(keyword)
    const kindHit = !kindSet.size || kindSet.has(node.kind) || !node.code
    const domainHit = nodeMatchesDomain(node, domains, menus)
    if (node.selectable && node.code) return selfHit && kindHit && domainHit ? { ...node, children: nextChildren } : (nextChildren.length ? { ...node, children: nextChildren } : null)
    if (!nextChildren.length && !(selfHit && (!kindSet.size || kindSet.has(node.kind)) && domainHit)) return null
    return { ...node, children: nextChildren }
  }
  return nodes.map(match).filter((item): item is PermissionTreeNode => Boolean(item))
}
