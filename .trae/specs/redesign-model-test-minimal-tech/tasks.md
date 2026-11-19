# Tasks

- [x] Task 1: 令牌层换血——移除 LAB 深舱令牌，新增 TECH 浅色科技令牌
  - [x] 1.1 tokens.css 删除 `--color-lab-*` 全部令牌、`--lab-grid-image`、`@keyframes lab-breathe`/`lab-blink`
  - [x] 1.2 新增 `--color-tech-accent`（浅色 #2563eb / 深色主题 #60a5fa）、`--color-tech-accent-subtle`、`--tech-dot-image`（极淡点阵，alpha ≤0.5）、`@keyframes tech-blink`
- [x] Task 2: index.vue 浅色卡片骨架 + 身份卡精修（逻辑零改动）
  - [x] 2.1 深舱容器换白底细框卡片组；网格纹理换极淡点阵或移除；AdminPageHeader 保持舱外
  - [x] 2.2 身份卡：LAB-01 角标换模型 key mono 小标、发光灯换静态状态点、mono 字段标签、控制钮浅色描边风
  - [x] 2.3 权限守卫/空态浅色化
- [x] Task 3: StatusStrip 工程化遥测条
  - [x] 3.1 hairline 四格白底化；英文 mono 标签 + 静态点四态（绿/红/琥珀/空心）+ 大号状态词 + tooltip hint
  - [x] 3.2 探针钮改石墨黑主按钮风；最近测试时间 mono 弱化
- [x] Task 4: ContextBar 浅色参数面板
  - [x] 4.1 删除深舱任意变体类，Select/Segmented 回归默认浅色外观
  - [x] 4.2 字段标签 mono 化；能力 chips 细线标签，reasoning/thinking_output 蓝描边 subtle 蓝底
- [x] Task 5: ChatColumn 浅色会话流
  - [x] 5.1 根卡片/空态/用户气泡（+YOU 角标）/助手细 zinc 左边线/思考块/探针卡/错误横幅浅色化
  - [x] 5.2 操作行/回底钮/输入区（a-textarea 变体类回浅色）/参数 chips/三个原生按钮浅色风；加载三点与光标 tech 蓝 + tech-blink
- [x] Task 6: DiagnosticPanel 浅色工程监控面板
  - [x] 6.1 Tab ink-bar 蓝、时间线静态语义点（去发光 shadow）、思考卡/用量卡/pre 浅色化
- [x] Task 7: markdown.ts 浅色适配
  - [x] 7.1 正文/表格/行内码/引用/链接/ hr 切浅色令牌；代码块保留深色卡片，语言标签与复制钮适配
- [x] Task 8: 检查与走查
  - [x] 8.1 全局 grep 确认 `--color-lab`/`lab-breathe`/`lab-blink`/`lab-grid` 零命中；ESLint 0 / vue-tsc 0 / Vite build EXIT=0；清理 dist
  - [x] 8.2 浏览器走查：浅色 + 深色主题各一轮（卡片同构、流式回归含深色代码块、探针报告、无 console 告警）；375px 无横向溢出
  - [x] 8.3 CHANGELOG 补记：深舱方向被用户推翻、浅色科技落地事实与未运行项
- [x] Task 9: 视口锁定布局——双列独立滚动（用户二轮反馈）
  - [x] 9.1 index.vue 根容器 lg:overflow-hidden；控制卡 shrink-0；工作区 grid 去 calc hack 改 flex-1 min-h-0；窄屏固定面板高度 + 页面滚动降级
  - [x] 9.2 验证 ChatColumn 消息区与 DiagnosticPanel 内容区在 lg+ 各自独立滚动、外壳不滚
- [x] Task 10: 折叠降噪与信息删减
  - [x] 10.1 ContextBar 卡片折叠头 + 收起态一行摘要（contextCollapsed 状态，默认折叠）
  - [x] 10.2 StatusStrip 瘦身（padding/字号/探针行 lg 内联）
  - [x] 10.3 删除输入区参数 chips 行 + paramChips prop/computed，paramsSummary 直算
- [x] Task 11: 窄屏高度链修复（375px 走查发现）
  - [x] 11.1 ChatColumn/DiagnosticPanel 根 h-full → lg:h-full，窄屏固定高度（560/420px）生效、页面纵向滚动恢复

# Task Dependencies
- Task 2–7 均依赖 Task 1（令牌先行）
- Task 5 与 Task 7 同批核对正文容器与 markdown 输出类名
- Task 8 依赖 Task 1–7 全部完成
