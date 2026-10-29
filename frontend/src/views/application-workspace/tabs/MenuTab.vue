<script setup lang="ts">
// 应用工作台「资源权限」Tab（P357 重构，P358 感知增强）：
// 面向应用的显式资源树——菜单（路由/图标/额外参数 JSON）+ 挂在菜单下的按钮与数据规则；
// 新增节点编码自动带上父级/命名空间前缀，弹窗内置图标选择器与描述字段；
// 角色「配置资源」入口在「角色」Tab；业务端通过 my-resources 接口拉取整棵树。
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '@/api'
import AdminSearchField from '@/components/AdminSearchField.vue'
import AdminEmpty from '@/components/AdminEmpty.vue'
import ResourceIcon from '../components/ResourceIcon.vue'
import { matchResource, buildResourcePathCodes } from '../components/resourceSearch'

interface ApplicationRef {
  id: string
  name: string
  permission_namespace: string
  can_manage?: boolean
}

type ResourceType = 'menu' | 'button' | 'data_rule'

interface ResourceRecord {
  id: string
  parent_id: string | null
  resource_type: ResourceType
  code: string
  name: string
  description: string | null
  path: string | null
  icon: string | null
  sort: number
  extra: Record<string, unknown>
  status: 'active' | 'disabled'
}

interface ResourceNode {
  key: string
  title: string
  children?: ResourceNode[]
  record: ResourceRecord
}

const props = withDefaults(defineProps<{
  application: ApplicationRef | null
  apiPrefix?: string
  active?: boolean
}>(), {
  apiPrefix: '/admin',
  active: true,
})

const emit = defineEmits<{ changed: [], stats: [count: number] }>()

const resources = ref<ResourceRecord[]>([])
const loading = ref(false)
const searchText = ref('')
const dialogOpen = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<{ validate: () => Promise<unknown> }>()
const form = reactive({
  resource_type: 'menu' as ResourceType,
  parent_id: undefined as string | undefined,
  code: '',
  name: '',
  description: '',
  path: '',
  icon: '',
  sort: 0,
  extra: '',
  status: 'active' as 'active' | 'disabled',
})
let requestSequence = 0

// 管理动作与后端 manage 门禁同口径：应用管理员（can_manage）即可维护资源树。
const canManage = computed(() => props.application?.can_manage === true)

// 编码前缀自动化：有父级用父级完整 code，根节点用应用命名空间；用户只需输入尾段。
const codePrefix = computed(() => {
  const parent = form.parent_id
    ? resources.value.find(item => item.id === form.parent_id)
    : undefined
  const base = parent ? parent.code : props.application?.permission_namespace ?? ''
  return base ? `${base}.` : ''
})

// 父级菜单仅在应用已有菜单节点时显示；创建第一个节点（必为菜单）时隐藏该字段。
const hasMenuNodes = computed(() => resources.value.some(item => item.resource_type === 'menu'))

// 树节点展示的路径化编码：根→当前逐级拼接，上级/上上级编码始终可见。
const resourcePathCodes = computed(() => buildResourcePathCodes(resources.value))

function applicationPath(path: string): string {
  return `${props.apiPrefix}${path}`
}

async function loadResources(): Promise<void> {
  if (!props.application) {
    resources.value = []
    emit('stats', 0)
    return
  }
  const sequence = ++requestSequence
  loading.value = true
  try {
    const rows = await api<ResourceRecord[]>(applicationPath(`/applications/${props.application.id}/resources`))
    if (sequence === requestSequence) {
      resources.value = rows
      // 上报资源数给父级概览统计条（resources 为扁平记录列表，行数即节点总数）
      emit('stats', rows.length)
    }
  } catch (error) {
    if (sequence !== requestSequence) return
    resources.value = []
    emit('stats', 0)
    message.error(error instanceof Error ? error.message : '读取资源树失败')
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

// 平铺清单组装资源树（后端按 sort/code 排序）；搜索命中时保留祖先链。
const resourceTree = computed<ResourceNode[]>(() => {
  const nodeMap = new Map<string, ResourceNode>()
  const roots: ResourceNode[] = []
  for (const record of resources.value) {
    nodeMap.set(record.id, { key: record.id, title: record.name, record, children: [] })
  }
  for (const record of resources.value) {
    const node = nodeMap.get(record.id)!
    const parent = record.parent_id ? nodeMap.get(record.parent_id) : undefined
    if (parent) parent.children!.push(node)
    else roots.push(node)
  }
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return roots
  // 模糊搜索：多词 AND，命中名称/编码/描述任一字段；命中节点连带全部祖先保留。
  const keep = new Set<string>()
  for (const record of resources.value) {
    if (matchResource(record, keyword)) {
      let cursor: ResourceRecord | undefined = record
      while (cursor && !keep.has(cursor.id)) {
        keep.add(cursor.id)
        cursor = cursor.parent_id ? resources.value.find(item => item.id === cursor!.parent_id) : undefined
      }
    }
  }
  const filterNodes = (nodes: ResourceNode[]): ResourceNode[] =>
    nodes
      .filter(node => keep.has(node.record.id))
      .map(node => ({ ...node, children: node.children?.length ? filterNodes(node.children) : undefined }))
  return filterNodes(roots)
})

const expandedKeys = ref<string[]>([])
watch(resourceTree, (nodes) => {
  // 默认展开全部含子级的节点，与 P354 组织树行为一致。
  const keys: string[] = []
  const walk = (list: ResourceNode[]): void => {
    for (const node of list) {
      if (node.children?.length) {
        keys.push(node.key)
        walk(node.children)
      }
    }
  }
  walk(nodes)
  expandedKeys.value = keys
})

// 父节点候选：只能是菜单；编辑时排除自身与后代，防止客户端造环（服务端仍兜底）。
const parentTreeData = computed(() => {
  const disabledIds = new Set<string>()
  if (editingId.value) {
    const collectDescendants = (id: string): void => {
      disabledIds.add(id)
      for (const record of resources.value) {
        if (record.parent_id === id) collectDescendants(record.id)
      }
    }
    collectDescendants(editingId.value)
  }
  const toTreeNode = (node: ResourceNode): Record<string, unknown> => ({
    value: node.record.id,
    title: node.record.name,
    selectable: false,
    children: (node.children ?? [])
      .filter(child => child.record.resource_type === 'menu' && !disabledIds.has(child.record.id))
      .map(toTreeNode),
  })
  const menuRoots = resourceTree.value
    .filter(node => node.record.resource_type === 'menu' && !disabledIds.has(node.record.id))
    .map(toTreeNode)
  // 顶级选项允许清空父级（value 用空串占位，提交时还原为 null）。
  return [{ value: '', title: '顶级菜单', selectable: false, children: menuRoots }]
})

const typeOptions = [
  { label: '菜单', value: 'menu' },
  { label: '按钮', value: 'button' },
  { label: '数据规则', value: 'data_rule' },
]

const rules = computed(() => ({
  code: [
    { required: true, whitespace: true, message: '请输入编码尾段' },
    {
      validator: (_rule: unknown, value: string) => {
        const suffix = (value || '').trim()
        if (!suffix) return Promise.resolve()
        // 校验「前缀 + 尾段」拼出的完整编码，与提交口径一致。
        const fullCode = `${codePrefix.value}${suffix}`
        if (!/^[a-z0-9][a-z0-9._-]*$/.test(fullCode)) {
          return Promise.reject('编码仅允许小写字母、数字、点、下划线、连字符，且以字母或数字开头')
        }
        return Promise.resolve()
      },
      trigger: 'blur',
    },
  ],
  name: [{ required: true, whitespace: true, message: '请输入资源名称' }],
  parent_id: [
    {
      // 按钮/数据规则必须挂菜单；菜单可留空作为顶级。
      validator: (_rule: unknown, value: string | undefined) => {
        if (form.resource_type !== 'menu' && !value) return Promise.reject('按钮与数据规则必须选择父级菜单')
        return Promise.resolve()
      },
      trigger: 'change',
    },
  ],
  extra: [
    {
      validator: (_rule: unknown, value: string) => {
        const trimmed = (value || '').trim()
        if (!trimmed) return Promise.resolve()
        try {
          const parsed = JSON.parse(trimmed)
          if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
            return Promise.reject('额外参数必须是 JSON 对象，例如 {"redirect": "/home"}')
          }
          return Promise.resolve()
        } catch {
          return Promise.reject('额外参数不是合法 JSON')
        }
      },
      trigger: 'blur',
    },
  ],
}))

function resetForm(): void {
  form.resource_type = 'menu'
  form.parent_id = undefined
  form.code = ''
  form.name = ''
  form.description = ''
  form.path = ''
  form.icon = ''
  form.sort = 0
  form.extra = ''
  form.status = 'active'
}

function openCreate(parent?: ResourceRecord): void {
  resetForm()
  editingId.value = null
  if (parent) {
    form.parent_id = parent.id
    // 按钮默认挂在当前菜单下，减少一次点选。
    if (parent.resource_type === 'menu') form.resource_type = 'button'
  }
  dialogOpen.value = true
}

function openEdit(record: ResourceRecord): void {
  resetForm()
  editingId.value = record.id
  form.resource_type = record.resource_type
  form.parent_id = record.parent_id ?? ''
  // 编码只让用户编辑尾段：按「当前前缀口径」拆分原编码，保证回显后拼接不变形。
  const basePrefix = record.parent_id
    ? resources.value.find(item => item.id === record.parent_id)?.code
    : props.application?.permission_namespace
  const prefix = basePrefix ? `${basePrefix}.` : ''
  form.code = prefix && record.code.startsWith(prefix) ? record.code.slice(prefix.length) : record.code
  form.name = record.name
  form.description = record.description ?? ''
  form.path = record.path ?? ''
  form.icon = record.icon ?? ''
  form.sort = record.sort
  form.extra = record.extra && Object.keys(record.extra).length ? JSON.stringify(record.extra, null, 2) : ''
  form.status = record.status
  dialogOpen.value = true
}

async function saveResource(): Promise<void> {
  try { await formRef.value?.validate() } catch { return }
  const application = props.application
  if (!application) return
  saving.value = true
  // 父级空串还原为 null（顶级菜单）；extra 解析为对象后提交。
  const parentId = form.parent_id ? form.parent_id : null
  const extra = form.extra.trim() ? JSON.parse(form.extra.trim()) as Record<string, unknown> : {}
  const payload = {
    parent_id: parentId,
    resource_type: form.resource_type,
    // 完整编码 = 前缀（父级 code 或应用命名空间）+ 用户输入尾段。
    code: `${codePrefix.value}${form.code.trim()}`,
    name: form.name.trim(),
    description: form.description.trim() || null,
    path: form.path.trim() || null,
    icon: form.icon.trim() || null,
    sort: form.sort,
    extra,
    status: form.status,
  }
  try {
    if (editingId.value) {
      await api(applicationPath(`/applications/${application.id}/resources/${editingId.value}`), {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
      message.success('资源节点已更新')
    } else {
      await api(applicationPath(`/applications/${application.id}/resources`), {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      message.success('资源节点已创建')
    }
    dialogOpen.value = false
    await loadResources()
    emit('changed')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存资源节点失败')
  } finally {
    saving.value = false
  }
}

function removeResource(record: ResourceRecord): void {
  Modal.confirm({
    title: `删除资源「${record.name}」？`,
    content: '删除后所有角色的该资源授权立即回收；存在子节点时需先删除子级。',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await api(applicationPath(`/applications/${props.application!.id}/resources/${record.id}`), {
          method: 'DELETE',
        })
        message.success('资源节点已删除')
        await loadResources()
        emit('changed')
      } catch (error) {
        message.error(error instanceof Error ? error.message : '删除资源节点失败')
      }
    },
  })
}

watch([() => props.active, () => props.application?.id], ([active]) => {
  if (!active) return
  void loadResources()
}, { immediate: true })
</script>

<template>
  <div class="flex min-w-0 flex-col gap-4">
    <!-- 提示降噪 P399：资源树定位说明已上移至工作台页头小字，本 Tab 不再重复横幅 -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <AdminSearchField v-model="searchText" placeholder="搜索资源名称或编码" :submit-on-clear="false" />
      <div class="flex items-center gap-2">
        <a-button :loading="loading" :disabled="!application" @click="loadResources">刷新</a-button>
        <a-button v-if="canManage && application" type="primary" @click="openCreate()">新建菜单</a-button>
      </div>
    </div>

    <a-spin :spinning="loading" class="min-h-32">
      <div v-if="resourceTree.length" class="min-w-0 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
        <a-tree
          v-model:expanded-keys="expandedKeys"
          :tree-data="resourceTree"
          block-node
        >
          <template #title="{ record }">
            <div class="group/node flex min-w-0 flex-1 items-center gap-2"
              :title="[record.description, record.path].filter(Boolean).join(' · ')">
              <ResourceIcon :type="record.resource_type" :icon="record.icon"
                class="shrink-0 text-[15px] text-[var(--color-text-secondary)]" />
              <span class="truncate">{{ record.name }}</span>
              <span class="max-w-[100px] shrink truncate font-mono text-xs text-[var(--color-text-muted)]"
                :title="resourcePathCodes.get(record.id)">{{ resourcePathCodes.get(record.id) }}</span>
              <a-tag v-if="record.resource_type === 'button'" class="mr-0 shrink-0" color="default">按钮</a-tag>
              <a-tag v-else-if="record.resource_type === 'data_rule'" class="mr-0 shrink-0" color="default">数据</a-tag>
              <a-tag v-if="record.status === 'disabled'" class="mr-0 shrink-0" color="default">已停用</a-tag>
              <span class="ml-auto flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover/node:opacity-100">
                <a-button v-if="canManage && record.resource_type === 'menu'" type="link" size="small" class="text-xs" @click.stop="openCreate(record as ResourceRecord)">加子级</a-button>
                <a-button v-if="canManage" type="link" size="small" class="text-xs" @click.stop="openEdit(record as ResourceRecord)">编辑</a-button>
                <a-button v-if="canManage" type="link" size="small" class="text-xs" danger @click.stop="removeResource(record as ResourceRecord)">删除</a-button>
              </span>
            </div>
          </template>
        </a-tree>
      </div>
      <AdminEmpty v-else-if="!loading" emoji="🧭" description="该应用还没有资源节点">
        <template v-if="canManage && application">
          <a-button type="primary" @click="openCreate()">新建第一个菜单</a-button>
        </template>
      </AdminEmpty>
    </a-spin>

    <a-modal v-model:open="dialogOpen" :title="editingId ? '编辑资源节点' : '新建资源节点'"
      ok-text="保存" cancel-text="取消" :confirm-loading="saving" :width="520" @ok="saveResource">
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <a-form-item label="资源类型" name="resource_type">
          <a-radio-group v-model:value="form.resource_type" :disabled="Boolean(editingId)">
            <a-radio-button v-for="option in typeOptions" :key="option.value" :value="option.value">{{ option.label }}</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item v-if="hasMenuNodes" label="父级菜单" name="parent_id" help="编码前缀自动跟随父级（顶级则用应用命名空间）">
          <a-tree-select v-model:value="form.parent_id" :tree-data="parentTreeData"
            placeholder="顶级菜单" tree-default-expand-all allow-clear tree-node-filter-prop="title" />
        </a-form-item>
        <a-form-item label="资源编码" name="code">
          <a-input v-model:value="form.code" :maxlength="180" placeholder="project.list">
            <template #prefix>
              <!-- 父菜单编码置灰展示在框内，仅尾段可编辑。 -->
              <span class="mr-0.5 font-mono text-xs text-[var(--color-text-muted)]">{{ codePrefix }}</span>
            </template>
          </a-input>
        </a-form-item>
        <a-form-item label="资源名称" name="name">
          <a-input v-model:value="form.name" :maxlength="160" placeholder="例如：项目列表" />
        </a-form-item>
        <a-form-item label="描述" name="description">
          <a-textarea v-model:value="form.description" :rows="2" :maxlength="500" placeholder="说明这个资源的用途，供管理与下发提示" />
        </a-form-item>
        <a-form-item v-if="form.resource_type === 'menu'" label="路由路径" name="path">
          <a-input v-model:value="form.path" :maxlength="300" placeholder="例如 /project/list" />
        </a-form-item>
        <a-form-item v-if="form.resource_type === 'menu'" label="图标" name="icon">
          <a-input v-model:value="form.icon" :maxlength="120" placeholder="图标标识，自行配置，例如 FolderOutlined" />
        </a-form-item>
        <a-form-item label="排序" name="sort">
          <a-input-number v-model:value="form.sort" :min="-9999" :max="9999" class="w-32" />
        </a-form-item>
        <a-form-item label="额外参数（JSON）" name="extra">
          <a-textarea v-model:value="form.extra" :rows="3" placeholder='例如 {"redirect": "/home", "badge": 3}' />
        </a-form-item>
        <a-form-item label="状态" name="status">
          <a-radio-group v-model:value="form.status">
            <a-radio value="active">启用</a-radio>
            <a-radio value="disabled">停用</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
