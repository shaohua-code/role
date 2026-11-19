# Tasks

- [x] Task 1: 令牌层——tokens.css 新增 LAB 实验舱令牌组与动效
  - [x] 1.1 新增 `--color-lab-accent`（终端绿）与 dim/bg 变体、舱体面板/描边引用令牌、40px 网格纹理令牌；浅色主题固定深舱用色、深色主题沿用
  - [x] 1.2 新增 `@keyframes lab-breathe`（呼吸辉光）与 `lab-blink`（光标闪烁），并给出对应工具类用法说明注释
- [x] Task 2: index.vue 舱体框架 + 舱位卡（视觉层，逻辑零改动）
  - [x] 2.1 页面工作区容器改实验舱（纯黑画布 + 网格纹理 + 舱体描边）；AdminPageHeader 保持舱外全站语言
  - [x] 2.2 模型身份条重塑为舱位卡：LAB-01 mono 角标、模型大字、发光状态灯、遥测字段（Provider/模型名/端点/凭据）、清空会话/调试设置控制钮
  - [x] 2.3 权限守卫与未选模型空态深舱化
- [x] Task 3: StatusStrip 遥测面板化
  - [x] 3.1 四格改遥测模块（mono 大写模块标签 + 发光状态灯四态 + 大号状态词 + hint）
  - [x] 3.2 探针按钮与最近测试时间终端绿描边风
- [x] Task 4: ContextBar 参数面板化
  - [x] 4.1 字段标签 mono 大写化、能力 chips 规格标签化（reasoning/thinking_output 终端绿描边高亮）
  - [x] 4.2 Segmented/Select 在深舱上的可读性处理（必要时组件 token 局部覆盖）
- [x] Task 5: ChatColumn 终端会话流
  - [x] 5.1 消息滚动区深底；用户消息右对齐深灰块 + YOU 角标；助手消息终端绿竖线 + 模型名角标
  - [x] 5.2 思考折叠块/探针报告卡/错误横幅/操作行/输入区/回底按钮/loading 三点/流式光标全部深舱化
- [x] Task 6: DiagnosticPanel 示波器风
  - [x] 6.1 Tab 行、事件时间线（发光节点 + 连接线）、思考卡、用量三格 mono 数据卡深舱化
- [x] Task 7: markdown.ts 输出类名深舱适配
  - [x] 7.1 正文文字色/表格/行内码/引用/链接在深底上的变体；代码块语言标签与复制钮终端绿系
- [ ] Task 8: 检查与走查
  - [ ] 8.1 ESLint 0 / vue-tsc 0 / Vite build EXIT=0；清理构建产物
  - [ ] 8.2 浏览器走查：浅色 + 深色主题各一轮（入舱对比、流式回归、探针报告、无 console 解析告警）；375px 无横向溢出
  - [ ] 8.3 CHANGELOG 补记（含未运行项如实记录）

# Task Dependencies
- Task 2–7 均依赖 Task 1（令牌先行）
- Task 5 与 Task 7 有类名衔接（正文容器类与 markdown 输出类需一致），实现时同批核对
- Task 8 依赖 Task 1–7 全部完成
