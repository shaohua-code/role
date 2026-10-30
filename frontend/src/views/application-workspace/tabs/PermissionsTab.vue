<script setup lang="ts">
// 工作台「权限编码」Tab：直接复用应用域抽出的 ApplicationPermissionPanel（列表/登记/启停），
// 与应用管理抽屉共享同一实现，避免重复造轮子。
import ApplicationPermissionPanel from '@/views/applications/ApplicationPermissionPanel.vue'

interface ApplicationRef {
  id: string
  name: string
  permission_namespace: string
  can_manage?: boolean
}

withDefaults(defineProps<{
  active?: boolean
  application: ApplicationRef | null
  apiPrefix?: string
}>(), {
  active: true,
  apiPrefix: '/admin',
})

const emit = defineEmits<{ changed: [], stats: [count: number] }>()
</script>

<template>
  <!-- 提示降噪 P399：两层权限规则已上移至工作台页头小字，本 Tab 不再重复横幅 -->
  <ApplicationPermissionPanel
    :application="application"
    :api-prefix="apiPrefix"
    :active="active"
    @changed="emit('changed')"
    @stats="count => emit('stats', count)"
  />
</template>
