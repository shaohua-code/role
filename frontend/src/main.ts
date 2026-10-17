import { createApp } from 'vue'
import 'ant-design-vue/dist/reset.css'
import App from './app/App.vue'
import { router } from './app/router'
import { installPublicUi } from './app/ui/antd'
import './style.css'
import './appearance.css'

// 首屏先挂载公开登录壳；有 token 时由 App 并行恢复会话并注册管理组件，避免阻塞 #app 挂载。
function bootstrap(): void {
  const app = createApp(App)
  installPublicUi(app)
  app.use(router)
  app.mount('#app')
}

bootstrap()
