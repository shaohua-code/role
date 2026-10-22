<script setup lang="ts">
defineProps<{ error: Error }>()

function reloadPage(): void {
  // 缓存中的旧入口可能引用已清理的 chunk；整页刷新后会重新读取静态资源清单。
  window.location.reload()
}
</script>

<template>
  <a-result status="error" title="管理模块暂时无法加载" sub-title="请检查网络连接后重新加载页面。">
    <template #extra>
      <a-button type="primary" @click="reloadPage">重新加载</a-button>
    </template>
  </a-result>
</template>
