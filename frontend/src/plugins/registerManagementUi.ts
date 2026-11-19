import type { App } from 'vue'
import {
  Badge,
  Checkbox,
  Collapse,
  DatePicker,
  Descriptions,
  Divider,
  Drawer,
  Flex,
  InputNumber,
  List,
  Menu,
  Modal,
  Progress,
  Result,
  Row,
  Col,
  // 模型测试台「应用对话 / 平台连接」模式切换（走查发现未注册导致 a-segmented 解析告警、fallback 渲染）。
  Segmented,
  Select,
  // 模型测试台调试抽屉 Temperature / Top P 滑杆（与 Segmented 同轮走查发现未注册告警）。
  Slider,
  Statistic,
  Steps,
  Switch,
  Table,
  Tabs,
  Tooltip,
  Transfer,
  Tree,
  // P358 资源节点弹窗父级菜单选择（走查发现未注册导致 a-tree-select 视觉空白不可选）。
  TreeSelect,
  Typography,
} from 'ant-design-vue'

/** 只在打开已认证管理台后注册的表格、筛选、弹窗、布局及向导组件。 */
export function registerManagementUi(app: App): void {
  for (const component of [
    Badge,
    Checkbox,
    Collapse,
    DatePicker,
    Descriptions,
    Divider,
    Drawer,
    Flex,
    InputNumber,
    List,
    Menu,
    Modal,
    Progress,
    Result,
    Row,
    Col,
    Segmented,
    Select,
    Slider,
    Statistic,
    Steps,
    Switch,
    Table,
    Tabs,
    Tooltip,
    // P345 用户配角色穿梭框（走查发现未注册导致 a-transfer 不渲染）。
    Transfer,
    Tree,
    // P358 资源节点弹窗父级菜单选择（走查发现未注册导致 a-tree-select 视觉空白不可选）。
    TreeSelect,
    Typography,
  ]) {
    app.use(component)
  }
}
