import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // 本地直连开发默认用原生文件事件；Compose bind mount 需显式开启轮询以免 HMR 失效。
  const devWatchPolling = env.VITE_DEV_USE_POLLING === 'true' || env.CI_DOCKER === 'true'
  const pollingInterval = Number(env.VITE_DEV_POLLING_INTERVAL || 1000)
  return {
    plugins: [vue(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      watch: devWatchPolling ? {
        usePolling: true,
        interval: Number.isFinite(pollingInterval) && pollingInterval > 0 ? pollingInterval : 1000,
      } : undefined,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          // 把 ant-design-vue 与 Vue 运行时拆出主入口，缩短首屏 JS 解析时间。
          manualChunks(id) {
            if (id.includes('node_modules/ant-design-vue') || id.includes('node_modules/@ant-design')) {
              return 'ant-design-vue'
            }
            if (id.includes('node_modules/vue') || id.includes('node_modules/@vue')) {
              return 'vue-vendor'
            }
          },
        },
      },
    },
  }
})
