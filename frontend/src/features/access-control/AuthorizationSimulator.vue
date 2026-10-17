<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { api } from '../../shared/services/api'

type Row = Record<string, unknown>

const props = withDefaults(defineProps<{
  active?: boolean
  seedTenants?: Row[]
  seedApplications?: Row[]
}>(), {
  active: false,
  seedTenants: () => [],
  seedApplications: () => [],
})
interface AuthorizationSimulationResult {
  subject: { user_id: string; email?: string | null; display_name: string; status: string }
  request: { tenant_id: string; application_id?: string | null; permission_code: string; resource_id?: string | null; include_data_scope: boolean }
  decision: { allowed: boolean; reason: string; data_scope?: { mode: string; constraints: Record<string, unknown>[] } }
  checks: { check: string; passed: boolean | null; reason: string }[]
  matching_roles: { id: string; key: string; name: string; application_id?: string | null; resource_id?: string | null }[]
}

const loading = ref(false)
const submitting = ref(false)
const tenants = ref<Row[]>([])
const users = ref<Row[]>([])
const applications = ref<Row[]>([])
const permissions = ref<Row[]>([])
const result = ref<AuthorizationSimulationResult | null>(null)
const form = reactive({ tenant_id: '', user_id: '', application_id: '', permission_code: '', resource_id: '', include_data_scope: true })
const applicationOptions = computed(() => applications.value.filter(row => String(row.tenant_id) === form.tenant_id))
const reasonLabels: Record<string, string> = {
  user_active: '用户处于启用状态', user_inactive: '用户已停用', token_context_valid: '身份上下文有效',
  token_tenant_mismatch: '令牌租户与请求不一致', token_application_mismatch: '令牌应用与请求不一致',
  tenant_active: '租户处于启用状态', tenant_inactive_or_missing: '租户不存在或已停用',
  active_tenant_membership: '用户拥有活动租户成员关系', no_active_tenant_membership: '用户没有该租户的活动成员关系',
  application_valid: '应用属于该租户且处于启用状态', tenant_wide_request: '请求按租户级角色授权判定',
  model_active: '模型属于该租户且处于启用状态', model_resource_id_required: '模型调用必须提供模型 ID',
  model_inactive_or_not_in_tenant: '模型不存在、停用或不属于该租户',
  matching_role_grant: '找到匹配的角色授权', no_matching_grant: '没有匹配的角色授权',
  data_scope_policy_missing: '权限没有配置数据范围，按默认拒绝处理', tenant_scope: '有效数据范围为当前租户',
  data_scope_resolved: '已解析数据范围条件', data_scope_resolves_to_empty: '数据范围解析为空，按默认拒绝处理',
  not_requested: '本次未请求数据范围解析', application_not_in_tenant_or_inactive: '应用不存在、停用或不属于该租户',
}

function labelOf(row: Row): string {
  return String(row.display_name || row.name || row.email || row.code || row.id)
}

function constraintText(constraint: Record<string, unknown>): string {
  if (constraint.kind === 'tenant') return `租户范围：${constraint.tenant_id}`
  if (constraint.kind === 'owner') return `本人数据：${constraint.field} = ${constraint.user_id}，租户 ${constraint.tenant_id}`
  if (constraint.kind === 'organizations') {
    const ids = Array.isArray(constraint.organization_ids) ? constraint.organization_ids.join('、') : '无'
    return `组织范围：${constraint.field} ∈ [${ids}]，租户 ${constraint.tenant_id}`
  }
  return JSON.stringify(constraint)
}

function onTenantChange(): void {
  // 应用列表按当前租户过滤；切换租户后必须清掉旧租户的应用 ID。
  form.application_id = ''
  result.value = null
}

async function loadOptions(): Promise<void> {
  loading.value = true
  try {
    const needTenantFetch = !props.seedTenants.length
    const needApplicationFetch = !props.seedApplications.length
    const [tenantRows, userRows, applicationRows, permissionRows] = await Promise.all([
      needTenantFetch ? api<Row[]>('/admin/tenants') : Promise.resolve(props.seedTenants),
      api<Row[]>('/admin/users'),
      needApplicationFetch ? api<Row[]>('/admin/applications') : Promise.resolve(props.seedApplications),
      api<Row[]>('/admin/permissions'),
    ])
    tenants.value = tenantRows.filter(row => row.status === 'active')
    users.value = userRows
    applications.value = applicationRows.filter(row => row.status === 'active')
    permissions.value = permissionRows
    if (!form.tenant_id) form.tenant_id = String(tenants.value[0]?.id || '')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '读取授权模拟选项失败')
  } finally {
    loading.value = false
  }
}

async function simulate(): Promise<void> {
  if (!form.tenant_id || !form.user_id || !form.permission_code) {
    message.warning('请先选择租户、用户和权限编码')
    return
  }
  submitting.value = true
  result.value = null
  try {
    result.value = await api<AuthorizationSimulationResult>('/admin/authorization/simulate', {
      method: 'POST',
      body: JSON.stringify({
        tenant_id: form.tenant_id,
        user_id: form.user_id,
        application_id: form.application_id || null,
        permission_code: form.permission_code,
        resource_id: form.resource_id.trim() || null,
        include_data_scope: form.include_data_scope,
      }),
    })
  } catch (error) {
    message.error(error instanceof Error ? error.message : '授权模拟失败')
  } finally {
    submitting.value = false
  }
}

// 首次进入授权模拟页再拉选项；平台字典已由 App 预加载时可跳过租户/应用重复请求。
watch(() => props.active, active => { if (active) void loadOptions() }, { immediate: true })
</script>

<template>
  <div class="authorization-simulator">
    <a-card class="data-card simulator-form-card" :bordered="false">
      <a-alert class="simulator-notice" type="info" show-icon message="只读预演" description="判定复用线上授权规则；模拟操作不会创建角色绑定、写入策略或修改业务数据。停用用户、租户或应用会按线上规则拒绝。" />
      <a-form layout="vertical" @finish="simulate">
        <div class="simulator-grid">
          <a-form-item label="租户" required>
            <a-select v-model:value="form.tenant_id" show-search option-filter-prop="label" :options="tenants.map(row => ({ value: String(row.id), label: labelOf(row) }))" placeholder="选择租户" @change="onTenantChange" />
          </a-form-item>
          <a-form-item label="用户" required>
            <a-select v-model:value="form.user_id" show-search option-filter-prop="label" :options="users.map(row => ({ value: String(row.id), label: `${labelOf(row)} · ${row.status === 'active' ? '启用' : '停用'}` }))" placeholder="选择要预演的用户" @change="result = null" />
          </a-form-item>
          <a-form-item label="应用范围">
            <a-select v-model:value="form.application_id" allow-clear show-search option-filter-prop="label" :options="applicationOptions.map(row => ({ value: String(row.id), label: labelOf(row) }))" placeholder="不选则检查租户级角色" @change="result = null" />
          </a-form-item>
          <a-form-item label="权限编码" required>
            <a-select v-model:value="form.permission_code" show-search option-filter-prop="label" :options="permissions.map(row => ({ value: String(row.code), label: `${row.code} · ${row.scope}` }))" placeholder="选择一个权限" @change="result = null" />
          </a-form-item>
          <a-form-item label="资源 ID（可选）">
            <a-input v-model:value="form.resource_id" :maxlength="180" placeholder="用于预演指定资源授权" @change="result = null" />
          </a-form-item>
          <a-form-item label="判定选项">
            <a-switch v-model:checked="form.include_data_scope" checked-children="解析数据范围" un-checked-children="仅检查 RBAC" @change="result = null" />
          </a-form-item>
        </div>
        <div class="simulator-actions">
          <a-button :loading="loading" @click="loadOptions">刷新选项</a-button>
          <a-button type="primary" :loading="submitting" :disabled="loading" @click="simulate">预演授权判定</a-button>
        </div>
      </a-form>
    </a-card>

    <a-card v-if="result" class="data-card simulator-result-card" :bordered="false">
      <div class="simulator-result-heading">
        <div><p class="eyebrow">DECISION TRACE</p><h2>判定结果</h2><p>{{ result.subject.display_name }} · {{ result.subject.email || result.subject.user_id }}</p></div>
        <a-tag :color="result.decision.allowed ? 'green' : 'red'">{{ result.decision.allowed ? '允许' : '拒绝' }}</a-tag>
      </div>
      <a-alert :type="result.decision.allowed ? 'success' : 'error'" show-icon :message="reasonLabels[result.decision.reason] || result.decision.reason" :description="`${result.request.permission_code}${result.request.resource_id ? ` · 资源 ${result.request.resource_id}` : ''}`" />
      <div class="simulator-result-grid">
        <section><h3>检查步骤</h3><ol class="simulator-checks"><li v-for="(check, index) in result.checks" :key="`${check.check}-${index}`"><a-tag :color="check.passed === false ? 'red' : check.passed === null ? 'default' : 'green'">{{ check.passed === false ? '拒绝' : check.passed === null ? '跳过' : '通过' }}</a-tag><span>{{ reasonLabels[check.reason] || check.reason }}</span></li></ol></section>
        <section><h3>命中的角色授权</h3><a-empty v-if="!result.matching_roles.length" description="没有匹配授权" /><ul v-else class="simulator-role-list"><li v-for="role in result.matching_roles" :key="`${role.id}-${role.resource_id || '*'}`"><strong>{{ role.name }}</strong><span>{{ role.key }} · {{ role.application_id ? '应用级' : '租户级' }} · {{ role.resource_id || '全部资源' }}</span></li></ul></section>
      </div>
      <section v-if="result.decision.data_scope" class="simulator-scope"><h3>有效数据范围</h3><p>策略按 any-of 合并；业务服务仍需把租户条件加入每条查询分支。</p><ul><li v-for="(constraint, index) in result.decision.data_scope.constraints" :key="index">{{ constraintText(constraint) }}</li></ul></section>
      <a-alert v-else-if="result.decision.allowed && result.request.include_data_scope" class="simulator-scope-alert" type="warning" show-icon message="未返回数据范围条件；调用方应拒绝数据读取。" />
    </a-card>
  </div>
</template>

<style scoped>
.authorization-simulator { display: grid; gap: 20px; }
.simulator-notice { margin-bottom: 24px; }
.simulator-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 20px; }
.simulator-grid :deep(.ant-select) { width: 100%; }
.simulator-actions { display: flex; justify-content: flex-end; gap: 10px; }
.simulator-result-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 18px; }
.simulator-result-heading h2 { margin: 2px 0 4px; font-size: 20px; }
.simulator-result-heading p:last-child { margin: 0; color: #748095; }
.simulator-result-heading :deep(.ant-tag) { margin-top: 8px; padding: 4px 12px; font-size: 14px; }
.simulator-result-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr); gap: 28px; margin-top: 26px; }
.simulator-result-grid h3, .simulator-scope h3 { margin: 0 0 14px; font-size: 15px; }
.simulator-checks, .simulator-role-list, .simulator-scope ul { display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }
.simulator-checks li { display: flex; align-items: center; gap: 8px; }
.simulator-checks :deep(.ant-tag) { min-width: 50px; margin: 0; text-align: center; }
.simulator-role-list li { display: grid; gap: 4px; padding: 12px; border: 1px solid #e9edf4; border-radius: 10px; }
.simulator-role-list span, .simulator-scope p { color: #748095; font-size: 13px; }
.simulator-scope { margin-top: 26px; padding-top: 22px; border-top: 1px solid #edf0f5; }
.simulator-scope p { margin: -6px 0 14px; }
.simulator-scope li { overflow-wrap: anywhere; padding: 10px 12px; background: #f6f8fc; border-radius: 8px; }
.simulator-scope-alert { margin-top: 20px; }
@media (max-width: 900px) { .simulator-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .simulator-grid, .simulator-result-grid { grid-template-columns: minmax(0, 1fr); } .simulator-actions { flex-direction: column-reverse; } .simulator-actions > :deep(.ant-btn) { width: 100%; } }
</style>
