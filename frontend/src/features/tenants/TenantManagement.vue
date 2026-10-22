<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { api } from '../../shared/services/api'
import AdminPageHeader from '../../shared/components/AdminPageHeader.vue'
import AdminTableToolbar from '../../shared/components/AdminTableToolbar.vue'

interface Tenant {
  id: string
  name: string
  slug: string
  kind: 'organization' | 'consumer'
  status: 'active' | 'disabled'
  member_count: number
}

const props = defineProps<{
  active: boolean
  shellTenants?: Tenant[] | null
  shellCatalogGeneration?: number
}>()
const emit = defineEmits<{ changed: [] }>()

let hydratedCatalogGeneration = -1

const tenants = ref<Tenant[]>([])
const loading = ref(false)
const saving = ref(false)
const modalOpen = ref(false)
const formRef = ref<{ validate: () => Promise<unknown> }>()
const form = reactive({ name: '', slug: '', kind: 'organization' as 'organization' | 'consumer' })
let requestSequence = 0
const rules = {
  name: [{ required: true, whitespace: true, max: 120, message: '请输入不超过 120 个字符的租户名称', trigger: 'blur' }],
  slug: [
    { required: true, message: '请输入租户标识', trigger: 'blur' },
    { pattern: /^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$/, message: '使用 3–80 位小写字母、数字或连字符，首尾必须为字母或数字', trigger: 'blur' },
  ],
}
const columns = [
  { title: '租户名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '租户标识', dataIndex: 'slug', key: 'slug', width: 220 },
  { title: '租户类型', dataIndex: 'kind', key: 'kind', width: 130 },
  { title: '成员数', dataIndex: 'member_count', key: 'member_count', width: 110 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '操作', dataIndex: 'actions', key: 'actions', width: 245, fixed: 'right' as const },
]

function hydrateFromShell(): boolean {
  if (props.shellTenants == null) return false
  const generation = props.shellCatalogGeneration ?? -1
  if (generation < 0 || generation === hydratedCatalogGeneration) return false
  tenants.value = props.shellTenants
  hydratedCatalogGeneration = generation
  return true
}

async function loadTenants(): Promise<void> {
  const sequence = ++requestSequence
  loading.value = true
  try {
    const result = await api<Tenant[]>('/admin/tenants')
    if (sequence === requestSequence) tenants.value = result
  } catch (error) {
    if (sequence === requestSequence) {
      tenants.value = []
      message.error(error instanceof Error ? error.message : '读取租户失败')
    }
  } finally { if (sequence === requestSequence) loading.value = false }
}

function createTenant(): void {
  Object.assign(form, { name: '', slug: '', kind: 'organization' })
  modalOpen.value = true
}

async function saveTenant(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    // Ant Design Vue 已展示字段错误；校验失败时不向 API 发送请求。
    return
  }
  saving.value = true
  try {
    await api('/admin/tenants', {
      method: 'POST',
      body: JSON.stringify({ name: form.name.trim(), slug: form.slug.trim(), kind: form.kind }),
    })
    message.success('租户已创建')
    modalOpen.value = false
    await loadTenants()
    emit('changed')
  } catch (error) { message.error(error instanceof Error ? error.message : '创建租户失败') }
  finally { saving.value = false }
}

function changeKind(tenant: Tenant): void {
  const kind = tenant.kind === 'consumer' ? 'organization' : 'consumer'
  const label = kind === 'consumer' ? 'ToC 消费租户' : '组织租户'
  Modal.confirm({
    title: `将“${tenant.name}”转为${label}？`,
    content: '转换前必须先关闭该租户下所有应用的自助注册。组织租户中的应用不能开放匿名注册；切换后仍需逐应用配置普通角色和协议，再单独开启注册。',
    okText: '确认切换', cancelText: '取消',
    onOk: async () => {
      try {
        await api(`/admin/tenants/${tenant.id}/kind`, {
          method: 'PATCH', body: JSON.stringify({ expected_kind: tenant.kind, kind }),
        })
        message.success('租户类型已更新')
        await loadTenants()
        emit('changed')
      } catch (error) { message.error(error instanceof Error ? error.message : '更新租户类型失败') }
    },
  })
}

function changeStatus(tenant: Tenant): void {
  const status = tenant.status === 'active' ? 'disabled' : 'active'
  const update = async (): Promise<void> => {
    try {
      await api(`/admin/tenants/${tenant.id}/status?status=${status}`, { method: 'PATCH' })
      message.success(status === 'active' ? '租户已启用' : '租户已停用')
      await loadTenants()
      emit('changed')
    } catch (error) { message.error(error instanceof Error ? error.message : '更新租户状态失败') }
  }
  if (status === 'disabled') Modal.confirm({
    title: '停用租户？',
    content: `停用“${tenant.name}”会阻止旗下成员和应用继续使用，并撤销其 OAuth 刷新会话；重新启用不会恢复旧会话。`,
    okText: '停用租户', cancelText: '取消', okButtonProps: { danger: true }, onOk: update,
  })
  else void update()
}

watch(() => props.active, active => {
  if (!active) return
  // 平台壳已预拉租户目录时复用，避免路由激活重复请求 /admin/tenants。
  if (hydrateFromShell()) return
  void loadTenants()
}, { immediate: true })

watch(() => [props.shellCatalogGeneration, props.shellTenants?.length] as const, () => {
  if (props.active) hydrateFromShell()
})
</script>

<template>
  <section class="tenant-management-page">
    <AdminPageHeader
      eyebrow="TENANT DIRECTORY"
      title="租户管理"
      subtitle="管理业务隔离边界。租户停用会阻止旗下应用续期登录会话，并立即影响成员访问。"
    >
      <template #extra>
        <a-button type="primary" @click="createTenant">＋ 新建租户</a-button>
      </template>
    </AdminPageHeader>

    <a-card class="data-card" :bordered="false">
      <AdminTableToolbar :hint="`共 ${tenants.length} 个租户；租户标识创建后不可修改。`">
        <template #actions>
          <a-button :loading="loading" @click="loadTenants">刷新</a-button>
        </template>
      </AdminTableToolbar>
      <a-table :data-source="tenants" :columns="columns" :loading="loading" row-key="id"
        :scroll="{ x: 1045 }" :pagination="{ pageSize: 10, showSizeChanger: true }">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'kind'"><a-tag :color="record.kind === 'consumer' ? 'purple' : 'blue'">{{ record.kind === 'consumer' ? 'ToC 消费' : '组织/企业' }}</a-tag></template>
          <template v-else-if="column.key === 'status'"><a-tag :color="record.status === 'active' ? 'green' : 'default'">{{ record.status === 'active' ? '启用' : '停用' }}</a-tag></template>
          <template v-else-if="column.key === 'actions'"><a-space><a-button type="link" size="small" @click="changeKind(record)">{{ record.kind === 'consumer' ? '转为组织租户' : '转为 ToC 消费' }}</a-button><a-button type="link" size="small" :danger="record.status === 'active'" @click="changeStatus(record)">{{ record.status === 'active' ? '停用' : '启用' }}</a-button></a-space></template>
        </template>
        <template #emptyText><a-empty description="暂无租户，可点击新建租户创建隔离空间" /></template>
      </a-table>
    </a-card>

    <a-modal v-model:open="modalOpen" title="新建租户" ok-text="创建" cancel-text="取消"
      :confirm-loading="saving" @ok="saveTenant">
      <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
        <a-form-item label="租户名称" name="name"><a-input v-model:value="form.name" :maxlength="120" /></a-form-item>
        <a-form-item label="租户标识" name="slug"><a-input v-model:value="form.slug" :maxlength="80" placeholder="example-team" /></a-form-item>
        <a-form-item label="租户类型" name="kind"><a-radio-group v-model:value="form.kind"><a-radio value="organization">组织/企业租户</a-radio><a-radio value="consumer">ToC 消费租户</a-radio></a-radio-group></a-form-item>
        <a-alert type="info" show-icon message="ToC 自助注册只允许绑定消费租户。创建组织租户不会开放匿名注册；转换类型前需要关闭租户内所有应用的自助注册。" />
      </a-form>
    </a-modal>
  </section>
</template>

<style scoped>
.tenant-management-page { display: grid; gap: 20px; }
.data-card { border-radius: 16px; }
</style>
