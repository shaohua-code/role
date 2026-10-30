<script setup lang="ts">
// 应用权限项抽屉：只保留抽屉壳，面板逻辑统一在 ApplicationPermissionPanel（工作台 Tab 同样复用）。
import ApplicationPermissionPanel from './ApplicationPermissionPanel.vue'

interface ApplicationRef {
  id: string
  name: string
  permission_namespace: string
  can_manage?: boolean
}

const open = defineModel<boolean>('open', { default: false })

withDefaults(defineProps<{
  application: ApplicationRef | null
  apiPrefix?: string
}>(), {
  apiPrefix: '/admin',
})

const emit = defineEmits<{ changed: [] }>()
</script>

<template>
  <a-drawer
    v-model:open="open"
    :title="application ? `${application.name} · 权限项` : '应用权限项'"
    width="720"
    destroy-on-close
  >
    <ApplicationPermissionPanel
      :application="application"
      :api-prefix="apiPrefix"
      :active="open"
      @changed="emit('changed')"
    />
  </a-drawer>
</template>
