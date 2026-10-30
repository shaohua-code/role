<script setup lang="ts">
// 组织工作台新建弹窗：从原组织管理列表抽出创建字段，不新造 API。
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '@/api'

interface TenantOption {
  id: string
  name: string
  status: string
  slug?: string
}

interface OrganizationOption {
  id: string
  tenant_id: string
  name: string
  key: string
  status: 'active' | 'disabled'
}

const open = defineModel<boolean>('open', { default: false })

const props = withDefaults(defineProps<{
  apiPrefix?: string
  tenants: TenantOption[]
  organizations: OrganizationOption[]
  presetTenantId?: string
  presetParentId?: string
}>(), {
  apiPrefix: '/admin',
  presetTenantId: '',
  presetParentId: '',
})

const emit = defineEmits<{
  created: [payload: { id: string }]
}>()

const saving = ref(false)
const formRef = ref<{ validate: () => Promise<unknown> }>()
const form = reactive({
  tenant_id: '',
  parent_id: undefined as string | undefined,
  key: '',
  name: '',
})

const tenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.slug !== 'platform' && tenant.status === 'active')
  .map(tenant => ({ value: tenant.id, label: tenant.name })))

const parentOptions = computed(() => props.organizations
  .filter(organization => organization.tenant_id === form.tenant_id && organization.status === 'active')
  .map(organization => ({ value: organization.id, label: `${organization.name} (${organization.key})` })))

const rules = {
  tenant_id: [{ required: true, message: '请选择所属租户', trigger: 'change' }],
  key: [
    { required: true, min: 2, max: 100, pattern: /^[a-z0-9][a-z0-9._-]+$/, message: '使用 2–100 位小写字母、数字、点、下划线或连字符，首字符须为字母或数字', trigger: 'blur' },
  ],
  name: [
    { required: true, whitespace: true, max: 160, message: '请输入不超过 160 个字符的组织名称', trigger: 'blur' },
  ],
}

function resetForm(): void {
  const presetTenant = tenantOptions.value.some(item => item.value === props.presetTenantId)
    ? props.presetTenantId
    : (tenantOptions.value[0]?.value || '')
  const presetParent = props.presetParentId && props.organizations.some(item =>
    item.id === props.presetParentId && item.tenant_id === presetTenant && item.status === 'active')
    ? props.presetParentId
    : undefined
  Object.assign(form, {
    tenant_id: presetTenant,
    parent_id: presetParent,
    key: '',
    name: '',
  })
}

function changeCreateTenant(): void {
  // 换租户后上级必须落在同一租户；预填的 parent 若不属于新租户则清空。
  if (form.parent_id && !parentOptions.value.some(item => item.value === form.parent_id)) {
    form.parent_id = undefined
  }
}

async function createOrganization(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!tenantOptions.value.some(tenant => tenant.value === form.tenant_id)) {
    message.error('请选择活动租户')
    return
  }
  saving.value = true
  try {
    const payload: Record<string, string> = {
      tenant_id: form.tenant_id,
      key: form.key.trim(),
      name: form.name.trim(),
    }
    if (form.parent_id) payload.parent_id = form.parent_id
    const result = await api<{ id: string }>(`${props.apiPrefix}/organizations`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    message.success('组织已创建')
    open.value = false
    emit('created', { id: result.id })
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建组织失败')
  } finally {
    saving.value = false
  }
}

watch(open, isOpen => {
  if (isOpen) resetForm()
})
</script>

<template>
  <a-modal
    v-model:open="open"
    title="新建组织"
    ok-text="创建"
    cancel-text="取消"
    :confirm-loading="saving"
    @ok="createOrganization"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item label="所属租户" name="tenant_id">
        <a-select v-model:value="form.tenant_id" :options="tenantOptions" placeholder="选择活动租户" @change="changeCreateTenant" />
      </a-form-item>
      <a-form-item label="组织标识" name="key">
        <a-input v-model:value="form.key" :maxlength="100" placeholder="例如 eng（英文标识，名称另填中文）" />
      </a-form-item>
      <a-form-item label="组织名称" name="name">
        <a-input v-model:value="form.name" :maxlength="160" />
      </a-form-item>
      <a-form-item label="上级组织（可选）" name="parent_id">
        <a-select v-model:value="form.parent_id" allow-clear :options="parentOptions" placeholder="顶层组织" />
      </a-form-item>
      <a-alert type="info" show-icon message="服务端会拒绝跨租户父组织及循环层级；更改组织结构会影响下游数据范围计算。" />
    </a-form>
  </a-modal>
</template>
