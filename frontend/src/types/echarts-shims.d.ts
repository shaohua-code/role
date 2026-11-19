/**
 * echarts 5.6.0 类型 shim：
 * 运行时模块化入口位于 echarts/lib/export/*（tree-shaking 按需引入），
 * 但包 package.json 的 exports 未给这些子路径映射 types，类型声明实际在 types/dist/*。
 * 此声明桥接两者；升级 echarts 后若官方修复 exports 映射可删除本文件。
 */
declare module 'echarts/lib/export/core' {
  export * from 'echarts/types/dist/core'
}
declare module 'echarts/lib/export/charts' {
  export * from 'echarts/types/dist/charts'
}
declare module 'echarts/lib/export/components' {
  export * from 'echarts/types/dist/components'
}
declare module 'echarts/lib/export/renderers' {
  export * from 'echarts/types/dist/renderers'
}
