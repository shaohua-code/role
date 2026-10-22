import type { App } from 'vue'
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Empty,
  Form,
  Input,
  Layout,
  Popover,
  Radio,
  Spin,
  StyleProvider,
  Tag,
} from 'ant-design-vue'

let rootApp: App | null = null
let managementUiPromise: Promise<void> | null = null

/**
 * 先安装登录入口与根壳需要的基础组件。
 * 表单/输入/单选组件各自的 install 会继续注册 Item、Password、Search 等子组件。
 */
export function installPublicUi(app: App): void {
  rootApp = app
  app.use(StyleProvider)
  // Layout 给公开登录页居中壳使用；表格等管理件仍延后注册。
  for (const component of [Alert, Button, Card, ConfigProvider, Empty, Form, Input, Layout, Popover, Radio, Spin, Tag]) {
    app.use(component)
  }
}

/** 登录并进入控制台前再下载管理组件，避免把表格和治理控件塞进公开登录入口。 */
export function ensureManagementUi(): Promise<void> {
  if (!rootApp) return Promise.reject(new Error('Ant Design Vue 根应用尚未初始化'))
  if (!managementUiPromise) {
    managementUiPromise = import('./registerManagementUi')
      .then(({ registerManagementUi }) => registerManagementUi(rootApp!))
      .catch((error: unknown) => {
        managementUiPromise = null
        throw error
      })
  }
  return managementUiPromise
}
