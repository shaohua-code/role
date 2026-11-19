<script setup lang="ts">
// 上下文行：测试模式 + 租户 / 应用 / 模型选择 + 能力标签（设计文档 §2）。
// 切换任一上下文由父页统一清空本地会话，避免把不同应用的结果混看。
import { computed } from 'vue'
import { MODEL_CAPABILITY_OPTIONS } from '@/utils/modelCapabilities'
import type { TestModelSummary } from '../api'

const mode = defineModel<'app' | 'platform'>('mode', { default: 'app' })
const modelId = defineModel<string>('modelId', { default: '' })
const tenantId = defineModel<string>('tenantId', { default: '' })
const applicationId = defineModel<string>('applicationId', { default: '' })

const props = defineProps<{
  models: TestModelSummary[]
  tenants: Array<{ id: string; name: string; status: string }>
  applications: Array<{ id: string; name: string; tenant_id: string; status: string }>
}>()

// 能力标签中文映射（标准集），reasoning 与 thinking_output 分开标注（设计文档 §3.2）。
const CAP_LABELS = new Map(MODEL_CAPABILITY_OPTIONS.map(option => [option.value, option.label]))
const CAP_HINTS = new Map(MODEL_CAPABILITY_OPTIONS.map(option => [option.value, option.hint]))

const modelOptions = computed(() => props.models.map(model => ({
  value: model.id,
  label: `${model.display_name}${model.status === 'disabled' ? '（已停用）' : ''}`,
})))
const tenantOptions = computed(() => props.tenants
  .filter(tenant => tenant.status === 'active')
  .map(tenant => ({ value: tenant.id, label: tenant.name })))
// 应用下拉只列当前租户下的应用；租户切换由父页联动纠正应用选择。
const applicationOptions = computed(() => props.applications
  .filter(application => application.tenant_id === tenantId.value && application.status === 'active')
  .map(application => ({ value: application.id, label: application.name })))

const selectedModel = computed(() => props.models.find(model => model.id === modelId.value) ?? null)

function capabilityLabel(code: string): string {
  return CAP_LABELS.get(code) ?? code
}
function capabilityHint(code: string): string {
  return CAP_HINTS.get(code) ?? code
}
</script>

<template>
  <!-- 窄栏紧凑布局（右栏统一卡内使用）：模式行 → 租户/应用双列 → 模型整行 → 能力标签 -->
  <div class="flex flex-col gap-2.5">
    <!-- 模式行：标签与切换器同行，节省纵向空间 -->
    <div class="flex items-center justify-between gap-2">
      <span class="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">测试模式</span>
      <a-segmented
        v-model:value="mode"
        size="small"
        :options="[
          { value: 'app', label: '应用对话' },
          { value: 'platform', label: '平台连接' },
        ]"
        aria-label="测试模式"
      />
    </div>
    <template v-if="mode === 'app'">
      <!-- 租户 / 应用：双列铺满窄栏 -->
      <div class="grid grid-cols-2 gap-2">
        <label class="flex flex-col gap-1">
          <span class="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">租户</span>
          <a-select v-model:value="tenantId" class="w-full" size="small" :options="tenantOptions" aria-label="选择租户" placeholder="选择租户" />
        </label>
        <label class="flex flex-col gap-1">
          <span class="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">应用</span>
          <a-select
            v-model:value="applicationId" class="w-full" size="small" :options="applicationOptions"
            aria-label="选择应用" placeholder="选择应用" :disabled="!tenantId"
          />
        </label>
      </div>
    </template>
    <label class="flex flex-col gap-1">
      <span class="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">模型</span>
      <a-select
        v-model:value="modelId" class="w-full" size="small" :options="modelOptions"
        aria-label="选择模型" placeholder="选择模型…" :show-search="true" option-filter-prop="label"
      />
    </label>
    <!-- 平台连接模式提示：仅验证链路，不代表应用已获授权（设计文档 §2）。 -->
    <a-alert
      v-if="mode === 'platform'"
      class="w-full" type="warning" show-icon
      message="平台级验证：仅验证部署 / 凭据 / Provider 链路，不代表业务应用已获授权"
    />
    <!-- 能力标签：来自目录真实数据；深度思考（可启用）与思考输出（可见）分开表达。 -->
    <div v-if="selectedModel" class="flex min-w-0 flex-wrap items-center gap-1.5">
      <a-tooltip v-for="cap in selectedModel.capabilities" :key="cap" :title="capabilityHint(cap)">
        <span
          class="inline-flex h-5 cursor-help items-center rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-2 text-[10px] leading-none text-[var(--color-text-secondary)]"
          :class="cap === 'reasoning' || cap === 'thinking_output' ? 'border-[var(--color-tech-accent)]/60 bg-[var(--color-tech-accent-subtle)] text-[var(--color-tech-accent)]' : ''"
        >{{ capabilityLabel(cap) }}</span>
      </a-tooltip>
    </div>
  </div>
</template>
