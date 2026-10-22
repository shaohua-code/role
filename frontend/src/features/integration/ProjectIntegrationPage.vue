<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PAGE_PATHS, type PageKey } from '../../app/navigation'
import { CheckCircleFilled } from '../../app/icons'
import AdminPageHeader from '../../shared/components/AdminPageHeader.vue'
import IntegrationCodeBlock from './IntegrationCodeBlock.vue'
import {
  API_PROJECT_STEPS,
  LOGIN_PROJECT_STEPS,
  SETUP_STEPS,
  type IntegrationPath,
  type WizardPhase,
} from './integrationGuide'

withDefaults(defineProps<{
  active: boolean
}>(), {
  active: false,
})

const router = useRouter()
// 方案与步数只存在本页，不写 URL。
const selectedPath = ref<IntegrationPath>('login')
const phase = ref<WizardPhase>('setup')
const setupIndex = ref(0)
const projectIndex = ref(0)

const projectSteps = computed(() => selectedPath.value === 'login' ? LOGIN_PROJECT_STEPS : API_PROJECT_STEPS)
const visibleSteps = computed(() => phase.value === 'setup' ? SETUP_STEPS : projectSteps.value)
const currentIndex = computed(() => phase.value === 'setup' ? setupIndex.value : projectIndex.value)
const progressLabel = computed(() => {
  if (phase.value === 'setup') {
    return `平台准备 ${setupIndex.value + 1} / ${SETUP_STEPS.length}`
  }
  return `改造项目 ${projectIndex.value + 1} / ${projectSteps.value.length}`
})
const phaseStep = computed(() => phase.value === 'setup' ? 0 : 1)
const canGoPrev = computed(() => !(phase.value === 'setup' && setupIndex.value === 0))
const canGoNext = computed(() => !(phase.value === 'project' && projectIndex.value === projectSteps.value.length - 1))
const nextLabel = computed(() => {
  if (phase.value === 'setup' && setupIndex.value === SETUP_STEPS.length - 1) {
    return '开始改项目'
  }
  return '下一步'
})
// a-collapse accordion 用步骤 order 当 key，与当前步双向同步。
const activeCollapseKey = computed({
  get: () => visibleSteps.value[currentIndex.value]?.order ?? '',
  set: (key: string | string[]) => {
    const next = Array.isArray(key) ? key[0] : key
    const index = visibleSteps.value.findIndex(step => step.order === next)
    if (index >= 0) openStep(index)
  },
})

function goAdminPage(key: PageKey): void {
  void router.push(PAGE_PATHS[key])
}

// Card 默认白底会盖掉 Tailwind，选中态用内联边框和浅紫底。
function pathCardStyle(path: IntegrationPath) {
  if (selectedPath.value !== path) {
    return { borderColor: '#e2e8f0' }
  }
  return {
    borderColor: '#756df2',
    borderWidth: '2px',
    backgroundColor: '#f3f0ff',
  }
}

function selectPath(path: IntegrationPath): void {
  selectedPath.value = path
  // 切方案只重置业务改造步，平台准备进度保留。
  projectIndex.value = 0
}

function openPhase(next: WizardPhase): void {
  phase.value = next
}

function onPhaseStepChange(current: number): void {
  openPhase(current === 0 ? 'setup' : 'project')
}

function openStep(index: number): void {
  if (phase.value === 'setup') {
    setupIndex.value = index
    return
  }
  projectIndex.value = index
}

function goPrev(): void {
  if (phase.value === 'project') {
    if (projectIndex.value === 0) {
      phase.value = 'setup'
      setupIndex.value = SETUP_STEPS.length - 1
      return
    }
    projectIndex.value -= 1
    return
  }
  if (setupIndex.value > 0) {
    setupIndex.value -= 1
  }
}

function goNext(): void {
  if (phase.value === 'setup') {
    if (setupIndex.value === SETUP_STEPS.length - 1) {
      phase.value = 'project'
      projectIndex.value = 0
      return
    }
    setupIndex.value += 1
    return
  }
  if (projectIndex.value < projectSteps.value.length - 1) {
    projectIndex.value += 1
  }
}

function isDone(index: number): boolean {
  return index < currentIndex.value
}
</script>

<template>
  <div class="flex w-full min-w-0 max-w-4xl flex-col gap-6 pb-28">
    <AdminPageHeader
      eyebrow="接入指南"
      title="新项目接入"
      subtitle="先在本平台登记，再改你的项目代码。一次只展开一步，可复制示例贴进业务仓库。"
    />

    <section class="grid grid-cols-1 gap-3 md:grid-cols-2" aria-label="选择接入方案">
      <a-card
        hoverable
        :style="pathCardStyle('login')"
        @click="selectPath('login')"
      >
        <div class="flex items-start justify-between gap-3">
          <a-tag color="purple">方案 A</a-tag>
          <CheckCircleFilled v-if="selectedPath === 'login'" class="text-lg text-violet-600" />
        </div>
        <a-typography-title :level="5" class="mt-2">平台托管登录</a-typography-title>
        <a-typography-paragraph type="secondary" class="mb-0">
          用户跳转到本平台登录页（OIDC）。业务不自建账号密码页，登录成功后回到你的站点。
        </a-typography-paragraph>
      </a-card>
      <a-card
        hoverable
        :style="pathCardStyle('api')"
        @click="selectPath('api')"
      >
        <div class="flex items-start justify-between gap-3">
          <a-tag :color="selectedPath === 'api' ? 'purple' : 'default'">方案 B</a-tag>
          <CheckCircleFilled v-if="selectedPath === 'api'" class="text-lg text-violet-600" />
        </div>
        <a-typography-title :level="5" class="mt-2">平台提供接口</a-typography-title>
        <a-typography-paragraph type="secondary" class="mb-0">
          业务自己的页面调用登录和判权接口，按 allowed 放行。
        </a-typography-paragraph>
      </a-card>
    </section>

    <a-alert
      type="warning"
      show-icon
      message="Client Secret、用户密码和 access_token 只放业务服务端。创建应用时 secret 只显示一次；超时或 5xx 一律当未授权。"
    />

    <a-card :bordered="false">
      <a-steps :current="phaseStep" size="small" @change="onPhaseStepChange">
        <a-step title="平台准备" :description="phase === 'setup' ? progressLabel : undefined" />
        <a-step title="改造你的项目" :description="phase === 'project' ? progressLabel : undefined" />
      </a-steps>
      <a-typography-paragraph v-if="phase === 'project'" type="secondary" class="mt-4 mb-0">
        下面改的是你的业务仓库。完整对照：
        <code class="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">examples/iam-crud-fastapi</code>
      </a-typography-paragraph>
    </a-card>

    <section class="flex min-w-0 flex-col">
      <a-typography-title :level="5">
        {{ phase === 'setup'
          ? '平台准备'
          : selectedPath === 'login' ? '改造你的项目 · 托管登录' : '改造你的项目 · HTTP 接口' }}
      </a-typography-title>
      <a-collapse accordion :active-key="activeCollapseKey" @update:activeKey="activeCollapseKey = $event">
        <a-collapse-panel
          v-for="(step, index) in visibleSteps"
          :key="step.order"
          :header="`${isDone(index) ? '✓ ' : ''}${step.order} ${step.title}`"
        >
          <a-typography-paragraph type="secondary">{{ step.summary }}</a-typography-paragraph>
          <ul class="list-disc space-y-1.5 pl-5 text-sm leading-relaxed break-words">
            <li v-for="item in step.items" :key="item">{{ item }}</li>
          </ul>
          <IntegrationCodeBlock :tabs="step.samples" />
          <a-button v-if="step.action" type="primary" class="mt-4" @click="goAdminPage(step.action)">
            {{ step.actionLabel }}
          </a-button>
        </a-collapse-panel>
      </a-collapse>
    </section>

    <a-flex
      justify="space-between"
      align="center"
      wrap="wrap"
      :gap="12"
      class="sticky bottom-0 w-full border-t border-slate-200 bg-slate-50/95 px-1 py-4 dark:border-slate-700 dark:bg-slate-950/95"
    >
      <a-button size="large" :disabled="!canGoPrev" @click="goPrev">上一步</a-button>
      <a-typography-text type="secondary">{{ visibleSteps[currentIndex]?.title }}</a-typography-text>
      <a-button type="primary" size="large" :disabled="!canGoNext" @click="goNext">{{ nextLabel }}</a-button>
    </a-flex>
  </div>
</template>
