import { defineComponent, h, type Component } from 'vue'

/** 侧栏与壳层用的线性图标。不把整包 @ant-design/icons-vue 别名到本文件，以免打断 antd 内部的 /es/icons 子路径。 */
function createIcon(name: string, path: string): Component {
  return defineComponent({
    name,
    setup() {
      return () => h('span', { class: 'anticon', role: 'img', 'aria-hidden': 'true' }, [
        h('svg', {
          viewBox: '0 0 24 24',
          width: '1em',
          height: '1em',
          fill: 'none',
          stroke: 'currentColor',
          'stroke-width': '1.8',
          'stroke-linecap': 'round',
          'stroke-linejoin': 'round',
        }, [h('path', { d: path })]),
      ])
    },
  })
}

export const AppstoreOutlined = createIcon('AppstoreOutlined', 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z')
export const BankOutlined = createIcon('BankOutlined', 'M3 10h18M5 10v8M19 10v8M3 18h18M12 4l9 6H3z')
export const ClusterOutlined = createIcon('ClusterOutlined', 'M4 6h6v6H4zM14 4h6v6h-6zM14 14h6v6h-6zM7 12v3h7')
export const ApiOutlined = createIcon('ApiOutlined', 'M10 8h4M9 12h6M8 16h8M7 4h10v16H7z')
export const UserOutlined = createIcon('UserOutlined', 'M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4zM5 20a7 7 0 0 1 14 0')
export const MailOutlined = createIcon('MailOutlined', 'M4 6h16v12H4zM4 7l8 6 8-6')
export const TeamOutlined = createIcon('TeamOutlined', 'M9 11a3 3 0 1 0-3-3 3 3 0 0 0 3 3zM16 12a3 3 0 1 0-2.5-3M4 20a5 5 0 0 1 10 0M14 20a5 5 0 0 1 6-4')
export const HomeOutlined = createIcon('HomeOutlined', 'M4 11l8-7 8 7v9H4zM10 20v-7h4v7')
export const SafetyCertificateOutlined = createIcon('SafetyCertificateOutlined', 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4')
export const SafetyOutlined = createIcon('SafetyOutlined', 'M12 3l8 4v6c0 5-3.5 8-8 8s-8-3-8-8V7z')
export const ExperimentOutlined = createIcon('ExperimentOutlined', 'M9 3h6M10 3v6L5 20h14L14 9V3M8 14h8')
export const DashboardOutlined = createIcon('DashboardOutlined', 'M4 13a8 8 0 1 1 16 0M12 13l4-4M12 13h.01')
export const AuditOutlined = createIcon('AuditOutlined', 'M7 4h10v16H7zM10 8h4M10 12h4M10 16h3')
export const SkinOutlined = createIcon('SkinOutlined', 'M6 9a6 6 0 0 1 12 0v11H6zM9 20v-4h6v4')
export const FileSearchOutlined = createIcon('FileSearchOutlined', 'M7 3h7l5 5v13H7zM14 3v5h5M10 16a3 3 0 1 0-2.2-1M12.5 17.5L14 19')
export const SearchOutlined = createIcon('SearchOutlined', 'M11 11a4 4 0 1 0-4-4 4 4 0 0 0 4 4zM20 20l-4.2-4.2')
export const UserSwitchOutlined = createIcon('UserSwitchOutlined', 'M8 11a3 3 0 1 0-3-3 3 3 0 0 0 3 3zM16 12a3 3 0 1 0-2-3M3 20a5 5 0 0 1 9 0M20 8l2 2-2 2M4 6L2 8l2 2')
export const IdcardOutlined = createIcon('IdcardOutlined', 'M3 6h18v12H3zM8 10a2 2 0 1 0 0 4M12 10h6M12 14h4')
export const MenuOutlined = createIcon('MenuOutlined', 'M4 7h16M4 12h16M4 17h16')
export const MenuFoldOutlined = createIcon('MenuFoldOutlined', 'M4 7h16M4 12h10M4 17h16M20 9l-4 3 4 3')
export const MenuUnfoldOutlined = createIcon('MenuUnfoldOutlined', 'M4 7h16M10 12h10M4 17h16M4 9l4 3-4 3')
export const CheckOutlined = createIcon('CheckOutlined', 'M5 12l5 5 9-10')
export const CheckCircleFilled = defineComponent({
  name: 'CheckCircleFilled',
  setup() {
    return () => h('span', { class: 'anticon', role: 'img', 'aria-hidden': 'true' }, [
      h('svg', { viewBox: '0 0 24 24', width: '1em', height: '1em', fill: 'currentColor' }, [
        h('path', { d: 'M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm-1.2 14.2-4-4 1.4-1.4 2.6 2.58 5.6-5.6 1.4 1.42z' }),
      ]),
    ])
  },
})
