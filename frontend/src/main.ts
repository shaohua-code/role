import { createApp } from 'vue'
import 'ant-design-vue/dist/reset.css'
import App from './app/App.vue'
import { ensureManagementUi, installPublicUi } from './app/ui/antd'
import { getToken, setToken } from './shared/services/api'
import './style.css'
import './appearance.css'

async function bootstrap(): Promise<void> {
  const app = createApp(App)
  installPublicUi(app)

  // 标签页恢复已有管理会话时，先完成按需注册再渲染控制台，避免模板出现未注册组件。
  if (getToken()) {
    try { await ensureManagementUi() }
    catch {
      setToken(null)
    }
  }

  app.mount('#app')
}

void bootstrap()
