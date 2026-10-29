import type { App } from 'vue'
import {
  Alert,
  Avatar,
  Button,
  Card,
  ConfigProvider,
  Empty,
  Form,
  Input,
  Layout,
  Popover,
  Radio,
  Space,
  Spin,
  StyleProvider,
  Tag,
} from 'ant-design-vue'

let rootApp: App | null = null
let managementUiPromise: Promise<void> | null = null

/**
 * 先安装登录入口与根壳需要的基础组件。
 * 表单/输入/单选组件各自的 install 会继续注册 Item、Password、Search 等子组件。
 * 注意：App 根组件的 renderCache 会在首次渲染时缓存组件解析结果（miss 也缓存），
 * 因此 App.vue 模板里直接用到的组件必须在这里注册，不能延后到登录后。
 */
export function installPublicUi(app: App): void {
  rootApp = app
  app.use(StyleProvider)
  // Layout 给公开登录页居中壳使用；Avatar/Space 供已登录顶栏使用，必须在首帧前注册。
  for (const component of [Alert, Avatar, Button, Card, ConfigProvider, Empty, Form, Input, Layout, Popover, Radio, Space, Spin, Tag]) {
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
