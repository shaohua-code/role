<template>
  <div class="feature-load-state" role="status" aria-live="polite">
    <span class="feature-load-spinner" aria-hidden="true"></span>
    <span>正在加载管理模块…</span>
  </div>
</template>

<style scoped>
.feature-load-state {
  display: grid;
  min-height: 240px;
  place-content: center;
  justify-items: center;
  gap: 12px;
  color: #667085;
  font-size: 14px;
}

.feature-load-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e6e8ef;
  border-top-color: #756df2;
  border-radius: 50%;
  animation: feature-load-spin 0.8s linear infinite;
}

@keyframes feature-load-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .feature-load-spinner { animation: none; }
}
</style>
