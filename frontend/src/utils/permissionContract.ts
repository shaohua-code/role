// 权限契约共享缓存（F2 码表单一来源）：GET /admin/permissions/tree 全仓只在这里请求。
// 响应含 meta（菜单↔按钮↔接口映射、层级可见码集、模板码数），
// 权限目录页、挂码弹窗、角色页统计共用同一份数据，前端零硬编码。
import { api } from '@/api'
import {
  EMPTY_PERMISSION_TREE_META,
  normalizeTreeApiNodes,
  type PermissionTreeApiNode,
  type PermissionTreeNode,
  type PermissionTreeMeta,
} from '@/utils/permissionTree'

/** 一次契约快照：资源树 + 数据树（已归一化）+ meta 契约。 */
export interface PermissionContractSnapshot {
  resource: PermissionTreeNode[]
  data: PermissionTreeNode[]
  meta: PermissionTreeMeta
}

/** 后端 tree 响应原始形状（items 为 resource 的别名，向后兼容）。 */
interface TreeApiResponse {
  resource?: PermissionTreeApiNode[]
  data?: PermissionTreeApiNode[]
  items?: PermissionTreeApiNode[]
  meta?: PermissionTreeMeta
}

// 模块级单例：snapshot 命中直接返回；inflight 合并并发请求；
// 请求失败时清空 inflight（snapshot 保持为空），下次调用自动重试。
let snapshot: PermissionContractSnapshot | null = null
let inflight: Promise<PermissionContractSnapshot> | null = null

async function requestContract(): Promise<PermissionContractSnapshot> {
  const result = await api<TreeApiResponse>('/admin/permissions/tree')
  const contract: PermissionContractSnapshot = {
    resource: normalizeTreeApiNodes(result.resource || result.items || []),
    data: normalizeTreeApiNodes(result.data || []),
    // 后端契约必有 meta；极端情况下缺失时以空契约兜底，避免运行时崩溃（映射查询返回空清单）。
    meta: result.meta ?? EMPTY_PERMISSION_TREE_META,
  }
  snapshot = contract
  return contract
}

/** 获取权限契约（带缓存）。force=true 忽略缓存强制刷新（目录页「刷新」按钮用）。 */
export async function ensurePermissionContract(force = false): Promise<PermissionContractSnapshot> {
  if (!force && snapshot) return snapshot
  if (!force && inflight) return inflight
  inflight = requestContract().finally(() => {
    inflight = null
  })
  return inflight
}
