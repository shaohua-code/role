import type { App } from 'vue'
import { Badge, Checkbox, Descriptions, Divider, InputNumber, Modal, Select, Space, Switch, Table, Tabs, Tooltip } from 'ant-design-vue'

/** 只在打开已认证管理台后注册的表格、筛选、弹窗及策略编辑组件。 */
export function registerManagementUi(app: App): void {
  for (const component of [Badge, Checkbox, Descriptions, Divider, InputNumber, Modal, Select, Space, Switch, Table, Tabs, Tooltip]) {
    app.use(component)
  }
}
