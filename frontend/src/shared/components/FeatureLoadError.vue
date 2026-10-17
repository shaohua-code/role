<script setup lang="ts">
defineProps<{ error: Error }>()

function reloadPage(): void {
  // 缓存中的旧入口可能引用已清理的 chunk；整页刷新后会重新读取静态资源清单。
  window.location.reload()
}
</script>

<template>
  <div class="feature-load-error" role="alert">
    <strong>管理模块暂时无法加载</strong>
    <span>请检查网络连接后重新加载页面。</span>
    <button type="button" @click="reloadPage">重新加载</button>
  </div>
</template>

<style scoped>
.feature-load-error {
  display: grid;
  min-height: 240px;
  align-content: center;
  justify-items: center;
  gap: 10px;
  color: #667085;
  font-size: 14px;
  text-align: center;
}

.feature-load-error strong { color: #344054; font-size: 16px; }
.feature-load-error button {
  min-height: 36px;
  padding: 0 14px;
  border: 0;
  border-radius: 7px;
  background: #756df2;
  color: white;
  cursor: pointer;
}
.feature-load-error button:focus-visible { outline: 3px solid #b8b4ff; outline-offset: 2px; }
</style>
