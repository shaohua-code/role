# Checklist

- [x] tokens.css 中 LAB 令牌/纹理/keyframes 全部移除；TECH 令牌与 tech-blink 就位
- [x] 全局搜索 `--color-lab`、`lab-breathe`、`lab-blink`、`lab-grid` 零命中
- [x] `views/models/test` 内无新增裸 hex（grep `#[0-9a-fA-F]{3,8}` 无业务色值，令牌定义除外）
- [x] 浅色主题：白底细框卡片组与全站管理台同构，无深舱黑底残留
- [x] 深色主题：卡片/描边/正文对比不塌陷，无白块漏底（浏览器实测五区块暗底、accent #60a5fa）
- [x] 身份卡：模型 key mono 小标、静态状态点（无呼吸辉光）、mono 字段标签、浅色控制钮
- [x] 遥测条四格：英文 mono 标签 + 静态点四态 + 状态词 + tooltip；探针钮石墨黑主按钮风（lg 内联第五格）
- [x] ContextBar：Select/Segmented 默认浅色外观；能力 chips 蓝描边高亮正确
- [x] 对话流：YOU 角标浅灰气泡；助手细 zinc 左边线；加载三点/光标为 tech 蓝
- [x] 流式回归：三点加载 → 思考折叠 → Markdown 正文（深色代码块 + 复制钮可读）→ 操作行（真实外呼多轮验证）
- [ ] 探针报告卡、错误横幅、调试抽屉、清空确认、编辑重发、回底按钮功能与可读性正常（探针卡与回底按钮已走查；调试抽屉/清空确认/编辑重发/错误横幅本轮未运行走查，逻辑未改动）
- [x] 诊断面板：Tab/时间线静态点/思考卡/用量数据卡浅色可读；事件 Tab 独立滚动实测（6.7 万字符内容内部消化）
- [x] 375px 窄屏无横向溢出（scrollWidth=375），面板固定 560/420px 纵向堆叠、页面级容器可纵向滚动
- [x] ESLint 0 / vue-tsc 0 / Vite build EXIT=0，dist 已清理
- [x] console 无新增组件解析告警
- [x] CHANGELOG 已补记（含深舱被推翻的决策事实与未运行项）
