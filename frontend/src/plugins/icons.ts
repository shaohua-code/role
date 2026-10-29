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
  ClusterOutlined,
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
  SearchOutlined,
  UserSwitchOutlined,
  IdcardOutlined,
  MenuOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  CheckOutlined,
  FilterOutlined,
  DownOutlined,
  UpOutlined,
  LockOutlined,
  CopyOutlined,
  // 圆圈感叹号：页头副标题 / 工具条提示的降噪入口图标，悬停经 a-tooltip 展示完整说明。
  ExclamationCircleOutlined,
  SettingOutlined,
  CheckCircleFilled,
} from '@ant-design/icons-vue'
