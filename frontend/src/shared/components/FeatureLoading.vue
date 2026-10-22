<script setup lang="ts">
withDefaults(defineProps<{
  tip?: string
}>(), {
  tip: '正在加载管理模块…',
})
</script>

<template>
  <div class="flex min-h-60 w-full items-center justify-center">
    <a-spin :tip="tip" />
  </div>
</template>
