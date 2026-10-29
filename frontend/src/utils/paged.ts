/** 列表接口分页包装；兼容升级前返回裸数组的调用方。 */
export interface PagedList<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export function asPagedList<T>(result: T[] | Partial<PagedList<T>> | null | undefined): PagedList<T> {
  if (Array.isArray(result)) {
    return { items: result, total: result.length, limit: result.length, offset: 0 }
  }
  if (result && Array.isArray(result.items)) {
    return {
      items: result.items,
      total: Number(result.total) || result.items.length,
      limit: Number(result.limit) || result.items.length,
      offset: Number(result.offset) || 0,
    }
  }
  return { items: [], total: 0, limit: 0, offset: 0 }
}
