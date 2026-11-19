<script setup lang="ts">
// 模型新建 / 编辑弹窗：分区表单（01 基础信息 / 02 能力标准集 / 03 限流与价格 / 04 API 密钥）。
// 保存链路与字段契约与原页内实现一致；凭证只填环境变量名（服务端组装 secret://env/ 引用），
// 编辑态留空保持原引用，显式勾选「清除」才删除。
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { LockOutlined } from '@/plugins/icons'
import { api } from '@/api'
import { ADMIN_API_PREFIX } from '@/api/capabilities'
import { MODEL_CAPABILITY_OPTIONS } from '@/utils/modelCapabilities'

// 结构化最小契约：与页面 ModelRecord 字段兼容（TS 结构化类型，避免循环依赖）。
interface ModelFormTarget {
  id: string
  key: string
  provider: string
  model_name: string
  display_name: string
  endpoint_url?: string | null
  credential_configured?: boolean
  credential_env_var?: string | null
  credential_ref_kind?: 'secret_env' | 'other' | null
  capabilities: string[]
  rpm_limit?: number | null
  tpm_limit?: number | null
  input_cost_per_million?: number | null
  output_cost_per_million?: number | null
}

const open = defineModel<boolean>('open', { default: false })
const props = withDefaults(defineProps<{
  /** 编辑目标；null 表示新建 */
  model?: ModelFormTarget | null
}>(), {
  model: null,
})
const emit = defineEmits<{ saved: [] }>()

const saving = ref(false)
const clearCredentialRef = ref(false)
const form = reactive({
  key: '', provider: '', model_name: '', display_name: '', endpoint_url: '', credential_env_var: '',
  capabilities: ['chat'] as string[], rpm_limit: null as number | null, tpm_limit: null as number | null,
  input_cost_per_million: null as number | null, output_cost_per_million: null as number | null,
})

// 环境变量名必须是合法标识符：字母/下划线开头，仅含字母、数字、下划线（与部署平台注入约定一致）。
const ENV_VAR_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/

// 规范化 API 地址：兼容填完整端点的习惯（如 https://api.x.com/v1/chat/completions）——
// 服务端外呼时会自动拼接 /chat/completions，这里先剥掉尾部路径与尾斜杠，避免拼出重复路径。
function normalizeEndpointUrl(raw: string): string {
  return raw.trim().replace(/\/+$/, '').replace(/\/chat\/completions$/i, '')
}

const isEditing = computed(() => Boolean(props.model))

// 打开时按目标初始化：新建归零；编辑回填常规字段，凭证仅回显环境变量名
// （服务端只对 secret://env 引用回传变量名，明文密钥任何形态都不回读）。
watch(open, (isOpen) => {
  if (!isOpen) return
  clearCredentialRef.value = false
  const target = props.model
  if (target) {
    Object.assign(form, {
      key: target.key, provider: target.provider, model_name: target.model_name,
      display_name: target.display_name, endpoint_url: target.endpoint_url || '',
      credential_env_var: target.credential_ref_kind === 'secret_env' ? (target.credential_env_var || '') : '',
      capabilities: [...target.capabilities], rpm_limit: target.rpm_limit ?? null, tpm_limit: target.tpm_limit ?? null,
      input_cost_per_million: target.input_cost_per_million ?? null, output_cost_per_million: target.output_cost_per_million ?? null,
    })
  } else {
    Object.assign(form, {
      key: '', provider: '', model_name: '', display_name: '', endpoint_url: '', credential_env_var: '',
      capabilities: ['chat'], rpm_limit: null, tpm_limit: null,
      input_cost_per_million: null, output_cost_per_million: null,
    })
  }
})

// 能力勾选桥接：标准集单选框布尔 ↔ form.capabilities 数组。
function onCapabilityChange(value: string, event: Event | { target?: unknown }): void {
  const checked = Boolean((event.target as HTMLInputElement | undefined)?.checked)
  if (checked) {
    if (!form.capabilities.includes(value)) form.capabilities.push(value)
  } else {
    form.capabilities = form.capabilities.filter(item => item !== value)
  }
}

async function saveModel(): Promise<void> {
  if (!form.provider.trim() || !form.model_name.trim() || !form.display_name.trim() || (!isEditing.value && !form.key.trim())) {
    message.warning('请填写所有必填模型信息')
    return
  }
  // 凭证字段校验：填了就必须是合法环境变量名；编辑态留空表示保持现有引用。
  const envVar = form.credential_env_var.trim()
  if (envVar && !ENV_VAR_PATTERN.test(envVar)) {
    message.warning('API 密钥环境变量名不合法：字母或下划线开头，仅含字母、数字、下划线')
    return
  }
  saving.value = true
  // 平台目录行归属由服务端指定（platform 租户）；tenant_id 不进入契约。
  const payload: Record<string, unknown> = {
    provider: form.provider.trim(), model_name: form.model_name.trim(), display_name: form.display_name.trim(),
    // 地址规范化后提交：剥掉 /chat/completions 尾巴，留空提交 null 走供应商标识内置默认。
    endpoint_url: normalizeEndpointUrl(form.endpoint_url) || null,
    capabilities: [...form.capabilities],
    rpm_limit: form.rpm_limit, tpm_limit: form.tpm_limit,
    input_cost_per_million: form.input_cost_per_million, output_cost_per_million: form.output_cost_per_million,
  }
  // 凭证引用由环境变量名按服务端约定组装：secret://env/<变量名>，明文密钥永不入库。
  if (!isEditing.value) {
    payload.key = form.key.trim()
    if (envVar) payload.credential_ref = `secret://env/${envVar}`
  } else if (clearCredentialRef.value) payload.credential_ref = null
  else if (envVar) payload.credential_ref = `secret://env/${envVar}`
  try {
    await api(isEditing.value ? `${ADMIN_API_PREFIX}/models/${props.model?.id}` : `${ADMIN_API_PREFIX}/models`, {
      method: isEditing.value ? 'PATCH' : 'POST', body: JSON.stringify(payload),
    })
    message.success(isEditing.value ? '模型已更新' : '模型已创建')
    open.value = false
    emit('saved')
  } catch (error) { message.error(error instanceof Error ? error.message : '保存模型失败') }
  finally { saving.value = false }
}
</script>

<template>
  <a-modal v-model:open="open" :title="isEditing ? `编辑模型：${form.display_name}` : '新建平台模型'"
    :width="640" ok-text="保存" cancel-text="取消" :confirm-loading="saving" @ok="saveModel">
    <!-- a-form vertical 根节点不可省：提供 antd 竖排布局上下文（label 在上），
         缺失时 a-form-item 回落默认横排，出现标签与输入框同行错位（用户走查实测）。 -->
    <a-form class="modal-form" layout="vertical">
      <!-- 01 基础信息：标识与提供方 / 名称双列，端点整行 -->
      <p class="form-section"><span class="form-section-no">01</span>基础信息</p>
      <div class="grid grid-cols-1 gap-x-4 md:grid-cols-2">
        <a-form-item v-if="!isEditing" label="模型标识" required><a-input v-model:value="form.key" :maxlength="100" placeholder="gpt-4o" /></a-form-item>
        <a-form-item label="提供方" required><a-input v-model:value="form.provider" :maxlength="100" placeholder="openai-compatible" /></a-form-item>
        <a-form-item label="模型名称" required><a-input v-model:value="form.model_name" :maxlength="160" /></a-form-item>
        <a-form-item label="展示名称" required><a-input v-model:value="form.display_name" :maxlength="160" /></a-form-item>
        <a-form-item label="API 地址" class="md:col-span-2"><a-input v-model:value="form.endpoint_url" :maxlength="500" placeholder="留空使用供应商标识内置默认地址（deepseek / openai / moonshot / qwen / zhipu 等）" /></a-form-item>
      </div>

      <!-- 02 能力标准集：卡片化勾选，与后端白名单同源校验 -->
      <p class="form-section mt-2"><span class="form-section-no">02</span>能力标准集</p>
      <div class="cap-grid">
        <label
          v-for="option in MODEL_CAPABILITY_OPTIONS"
          :key="option.value"
          class="cap-card"
          :class="{ 'cap-card-checked': form.capabilities.includes(option.value) }"
        >
          <span class="cap-head">
            <input
              type="checkbox"
              :checked="form.capabilities.includes(option.value)"
              @change="onCapabilityChange(option.value, $event)"
            >
            <span class="cap-name">{{ option.label }}</span>
          </span>
          <span class="cap-hint">{{ option.hint }}</span>
        </label>
      </div>

      <!-- 03 限流与价格：目录级参考值；限额是否拦截由服务端配额开关控制 -->
      <p class="form-section mt-2"><span class="form-section-no">03</span>限流与价格</p>
      <div class="grid grid-cols-1 gap-x-4 md:grid-cols-2">
        <a-form-item label="RPM 限额（请求/分钟）"><a-input-number v-model:value="form.rpm_limit" :min="1" style="width:100%" placeholder="留空表示不限制" /></a-form-item>
        <a-form-item label="TPM 限额（Token/分钟）"><a-input-number v-model:value="form.tpm_limit" :min="1" style="width:100%" placeholder="留空表示不限制" /></a-form-item>
        <a-form-item label="输入价格 / 百万 Token"><a-input-number v-model:value="form.input_cost_per_million" :min="0" :precision="6" style="width:100%" /></a-form-item>
        <a-form-item label="输出价格 / 百万 Token"><a-input-number v-model:value="form.output_cost_per_million" :min="0" :precision="6" style="width:100%" /></a-form-item>
      </div>

      <!-- 04 API 密钥：只填环境变量名，服务端按 secret://env/<变量名> 解析；明文永不入库 -->
      <p class="form-section mt-2"><span class="form-section-no">04</span>API 密钥</p>
      <a-form-item>
        <template #label>
          <span class="inline-flex items-center gap-1.5">
            <LockOutlined class="text-xs text-[var(--color-text-muted)]" />API 密钥环境变量名
            <!-- 状态标签分级：环境变量（变量名已回显）/ 外部引用（vault 等旧格式，不回读）/ 未配置 -->
            <a-tag v-if="isEditing && form.credential_env_var" class="ml-1">环境变量</a-tag>
            <a-tag v-else-if="isEditing && props.model?.credential_ref_kind === 'other'" class="ml-1">外部引用</a-tag>
            <a-tag v-else-if="isEditing && props.model?.credential_configured" class="ml-1">已配置</a-tag>
            <a-tag v-else-if="isEditing" class="ml-1">未配置</a-tag>
          </span>
        </template>
        <a-input
          v-model:value="form.credential_env_var"
          :maxlength="100"
          class="credential-input"
          :disabled="clearCredentialRef"
          :placeholder="isEditing ? '留空保持现有凭证不变' : 'YASOLL_API_KEY'"
        />
        <p class="credential-hint">
          只填环境变量名，服务端按 secret://env/变量名 解析真实密钥；变量由部署平台注入（根目录 .env 写真实 Key，compose.yaml 透传给 api 服务后重启容器）。编辑时已配置的变量名会回显，修改后保存即替换；明文密钥不入库、不回读、不下发。
        </p>
        <a-checkbox v-if="isEditing" v-model:checked="clearCredentialRef" class="mt-2">清除当前凭证引用</a-checkbox>
      </a-form-item>

      <a-alert
        :message="isEditing
          ? '模型标识只读；凭证留空保持原引用，只有勾选清除才会删除。'
          : '目录统一归属平台租户；创建后通过「下发租户」控制租户可见性。API 密钥只填环境变量名，服务端组装为 secret://env/ 引用解析；限额是否拦截由服务端配额开关控制。'"
        type="info" show-icon
      />
    </a-form>
  </a-modal>
</template>

<style scoped>
.modal-form { display: flex; flex-direction: column; }
/* 分区头：mono 序号 + 标题，对齐页面 01/02 区块编号语言 */
.form-section {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.form-section-no {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-muted);
}
/* 能力卡片化（P389 码项卡片语言）：选中石墨黑边 + 浅灰底 */
.cap-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
@media (min-width: 640px) { .cap-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
.cap-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}
.cap-card:hover { border-color: var(--color-border-strong); }
.cap-card-checked { border-color: var(--color-text-primary); background: var(--color-bg-subtle); }
.cap-head { display: flex; align-items: center; gap: 8px; }
.cap-head input { width: 14px; height: 14px; accent-color: var(--color-brand); flex: none; }
.cap-name { font-size: 13px; font-weight: 500; color: var(--color-text-primary); }
.cap-hint { padding-left: 22px; font-size: 11px; line-height: 1.5; color: var(--color-text-muted); }
/* 凭证引用等宽字体：与外部密钥引用的书写形态一致 */
.credential-input :deep(input) { font-family: var(--font-mono); font-size: 12.5px; }
.credential-hint { margin: 6px 0 0; font-size: 11.5px; line-height: 1.6; color: var(--color-text-muted); }
</style>
