/** 资源模糊匹配：空格分隔多词 AND，每个词命中名称/编码/描述任一字段即算通过。 */
export interface ResourceSearchable {
  name: string
  code: string
  description?: string | null
}

export function matchResource(record: ResourceSearchable, keyword: string): boolean {
  const terms = keyword.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (!terms.length) return true
  const haystack = `${record.name} ${record.code} ${record.description ?? ''}`.toLowerCase()
  return terms.every(term => haystack.includes(term))
}

export interface ResourcePathable {
  id: string
  parent_id: string | null
  code: string
}

/**
 * 计算每个节点的路径化编码（根→当前逐级拼接）：
 * 自身 code 已含父路径（新数据自动前缀）则原样；否则父路径 + '.' + 自身 code（兼容旧数据）。
 * 返回 id → pathCode 映射；带访问标记防历史脏数据成环导致死递归。
 */
export function buildResourcePathCodes(records: ResourcePathable[]): Map<string, string> {
  const byId = new Map(records.map(record => [record.id, record]))
  const resolved = new Map<string, string>()
  const visiting = new Set<string>()
  const resolve = (record: ResourcePathable): string => {
    const cached = resolved.get(record.id)
    if (cached !== undefined) return cached
    if (visiting.has(record.id)) return record.code
    visiting.add(record.id)
    let path = record.code
    const parent = record.parent_id ? byId.get(record.parent_id) : undefined
    if (parent) {
      const parentPath = resolve(parent)
      path = record.code.startsWith(`${parentPath}.`) ? record.code : `${parentPath}.${record.code}`
    }
    visiting.delete(record.id)
    resolved.set(record.id, path)
    return path
  }
  records.forEach(record => resolve(record))
  return resolved
}
