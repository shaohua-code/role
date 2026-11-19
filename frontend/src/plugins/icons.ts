/**
 * 图标统一出口：全站图标统一使用 antd 官方 @ant-design/icons-vue。
 *
 * 历史背景：本文件曾按 createIcon 模式手绘同名的 24×24 线性 SVG（P348 记录为既有架构偏离），
 * 现已全部替换为官方图标具名 re-export——消费方仍从 `@/plugins/icons` 导入，写法不变；
 * 新增图标直接加进 re-export 列表（名字以 @ant-design/icons-vue 官方导出为准）。
 * 说明：仅做具名 re-export、不做模块别名/重定向，不影响 antd 内部对该包的 /es/icons 子路径导入。
 */
export {
  AppstoreOutlined,
  ApartmentOutlined,
  BankOutlined,
  UserOutlined,
  MailOutlined,
  TeamOutlined,
  HomeOutlined,
  SafetyCertificateOutlined,
  SafetyOutlined,
  ExperimentOutlined,
  DashboardOutlined,
  AuditOutlined,
  SkinOutlined,
  FileSearchOutlined,
  ReadOutlined,
  SearchOutlined,
  IdcardOutlined,
  MenuOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  CheckOutlined,
  FilterOutlined,
  DownOutlined,
  UpOutlined,
  LockOutlined,
  LogoutOutlined,
  EditOutlined,
  CopyOutlined,
  PlusOutlined,
  EllipsisOutlined,
  // 调节滑块：资源权限树「按钮」类型计数 chip 的语义图标（与 ResourceIcon 内按钮图标同源）。
  ControlOutlined,
  // 圆圈 i：工作台权限规则提示条的降噪信息图标（区别于感叹号的警示语义）。
  InfoCircleOutlined,
  // 圆圈感叹号：页头副标题 / 工具条提示的降噪入口图标，悬停经 a-tooltip 展示完整说明。
  ExclamationCircleOutlined,
  SettingOutlined,
  // 模型测试台：发送 / 连接探针 / 停止生成 / 清空会话 / 回到底部（均为官方具名图标）。
  SendOutlined,
  ThunderboltOutlined,
  StopOutlined,
  ClearOutlined,
  ArrowDownOutlined,
  // 模型测试台：助手消息「重新生成」动作（官方 redo 图标）。
  RedoOutlined,
} from '@ant-design/icons-vue'
