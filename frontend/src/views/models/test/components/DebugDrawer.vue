<script setup lang="ts">
// 调试设置抽屉：仅展示当前受控通道实际转发给 Provider 的参数。
// 草稿模式：抽屉内修改先落草稿，「应用参数」才提交给下一轮发送；关闭抽屉未应用的修改被重置。
import { ref, watch } from 'vue'
import { defaultDebugParams, type DebugParams } from '../api'

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  params: DebugParams
}>()

const emit = defineEmits<{ apply: [params: DebugParams] }>()

// 草稿：打开抽屉时从已提交参数复制；取消 / 关闭直接丢弃。
const draft = ref<DebugParams>(defaultDebugParams())

watch(open, (isOpen) => {
  if (isOpen) draft.value = { ...props.params }
})

function resetDefaults(): void {
  draft.value = defaultDebugParams()
}

function cancel(): void {
  open.value = false
}

function apply(): void {
  emit('apply', { ...draft.value })
  open.value = false
}
</script>

<template>
  <a-drawer v-model:open="open" title="调试设置" width="min(420px, 100vw)" class="debug-drawer">
    <p class="mb-4 mt-0 text-[11px] leading-relaxed text-[var(--color-text-muted)]">
      以下参数会随下一次请求发送给 Provider。关闭抽屉会放弃未应用的修改。
    </p>

    <h4 class="mb-1 mt-0 text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">生成参数</h4>
    <div class="mb-5 flex flex-col divide-y divide-[var(--color-border)]">
      <div class="flex items-center justify-between gap-4 py-2.5">
        <span class="text-[13px]">Temperature</span>
        <a-slider v-model:value="draft.temperature" class="w-32" :min="0" :max="2" :step="0.1" :tooltip-open="false" aria-label="Temperature" />
        <span class="w-8 text-right font-mono text-xs tabular-nums">{{ draft.temperature }}</span>
      </div>
      <div class="flex items-center justify-between gap-4 py-2.5">
        <span class="text-[13px]">Top P</span>
        <a-slider v-model:value="draft.topP" class="w-32" :min="0" :max="1" :step="0.05" :tooltip-open="false" aria-label="Top P" />
        <span class="w-8 text-right font-mono text-xs tabular-nums">{{ draft.topP }}</span>
      </div>
      <div class="flex items-center justify-between gap-4 py-2.5">
        <span class="text-[13px]">最大输出 token</span>
        <a-input-number v-model:value="draft.maxTokens" class="w-24" size="small" :min="64" :max="8192" :step="64" aria-label="最大输出 token" />
      </div>
    </div>

    <h4 class="mb-1 mt-0 text-[11px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">对话指令</h4>
    <div class="mb-5 flex flex-col divide-y divide-[var(--color-border)]">
      <div class="py-3">
        <p class="mb-1.5 mt-0 text-[13px]">系统提示词</p>
        <a-textarea
          v-model:value="draft.systemPrompt" :auto-size="{ minRows: 3, maxRows: 8 }"
          :maxlength="8000" show-count placeholder="留空则不注入系统提示词" aria-label="系统提示词"
        />
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-between gap-2">
        <a-button size="small" @click="resetDefaults">恢复默认</a-button>
        <div class="flex gap-2">
          <a-button size="small" @click="cancel">取消</a-button>
          <a-button type="primary" size="small" @click="apply">应用参数</a-button>
        </div>
      </div>
    </template>
  </a-drawer>
</template>
