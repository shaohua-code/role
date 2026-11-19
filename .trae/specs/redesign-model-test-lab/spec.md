# 模型测试台「深色实验舱」改版 Spec

## Why
用户反馈当前测试台页面「太丑」，要求更「科技」。页面功能（SSE 流式、探针、Markdown、诊断）已完备，纯视觉层重塑：把测试台做成与全站浅色管理台形成仪式感对比的深色任务控制台。

## 设计方向（已与用户确认）
- **路线**：深色实验舱——页面局部深色化（纯黑画布 + 面板舱体），像进入任务控制台；浅色主题下形成「入舱」对比，深色主题下自然融合。
- **点缀色**：终端绿（示波器/黑客终端语义，配「运行正常」的测试台语境）。
- **美学原则**（frontend-design + aesthetics 原则落点）：
  - 克制的高对比：黑底 zinc 灰阶 + 唯一终端绿点缀（immersion / form-follows-function——点缀只承载「活性/通过/进行中」语义）；
  - mono 数据语言：编号、遥测字段、状态值全大写 + 字距加宽，任务控制台的仪表感；
  - 微动效克制：呼吸状态灯、光标闪烁、hover 辉光；拒绝大面积扫描线/粒子等炫技（immersion-distraction-cost）；
  - 熟悉感保留：布局骨架（身份条/上下文行/状态行/双列工作区）不动，用户已建立的空间记忆零迁移成本（exposure-redesign-risk）。

## What Changes
- `frontend/src/styles/tokens.css`：新增 LAB 实验舱令牌组（`--color-lab-accent` 终端绿及其 dim/bg 变体、实验舱面板/描边用色引用现有 zinc 令牌）+ 实验舱专用 `@keyframes`（状态灯呼吸 `lab-breathe`、光标 `lab-blink`）+ 舱内网格纹理令牌（40px 网格线，低透明度）。业务组件不新增任何裸 hex。
- `views/models/test/index.vue`（视觉层）：
  - 页面根容器变为实验舱：纯黑画布 + 网格纹理 + 内描边圆角舱体；
  - 顶部模型身份条重塑为「舱位卡」：左侧 `LAB-01` mono 编号角标 + 模型展示名大字 + 活动状态发光灯；右侧 Provider / 模型名 / 端点 / 凭据引用遥测字段（mono 大写字段标签）；「清空会话 / 调试设置」控制钮科技化；
  - 权限守卫与空态适配深舱配色；
  - 工作区网格、页头（AdminPageHeader 保持全站语言，置于舱外）不动。
- `StatusStrip.vue`：四格改为「遥测面板」——每格 mono 大写模块标签（CONFIG / AUTHZ / PROVIDER / GENERATION）、发光状态灯（ok=终端绿呼吸、fail=红、warn=琥珀、pending=zinc 空心）、大号状态词、hint 悬停；「执行连接测试」按钮终端绿描边风。
- `ContextBar.vue`：参数面板风——测试模式 Segmented、租户/应用/模型选择器字段标签 mono 大写化、能力 chips 改「规格标签」（终端绿描边高亮 reasoning/thinking_output）。
- `ChatColumn.vue`：终端会话流——消息滚动区深底；用户消息 = 右对齐深灰块 + `YOU` mono 角标；助手消息 = 左侧终端绿竖线 + 模型名 mono 角标；思考块、探针报告卡、错误横幅、操作行、输入区（含发送/停止钮、参数 chips）、回底按钮全部深舱化；loading 三点与流式光标适配。
- `DiagnosticPanel.vue`：示波器风——Tab 行深舱化；事件时间线节点改终端绿/语义色发光点 + 连接线；思考过程卡、用量三格 mono 数据卡深舱化。
- `markdown.ts`：渲染输出的 Tailwind 类名适配深舱（正文文字色、表格描边、行内码、引用、链接在深底上的可读性变体；代码块语言标签/复制钮改终端绿系）。
- 业务逻辑零改动：事件流、判权、探针、取消、编辑重发、清空、调试抽屉、用量落账展示逻辑全部原样保留。

## Impact
- Affected specs: 无既有 spec 覆盖模型测试台视觉；本 spec 独立。
- Affected code:
  - `frontend/src/styles/tokens.css`（追加令牌与 keyframes）
  - `frontend/src/views/models/test/index.vue`
  - `frontend/src/views/models/test/components/{ChatColumn,StatusStrip,ContextBar,DiagnosticPanel}.vue`
  - `frontend/src/views/models/test/markdown.ts`（仅类名常量）
- 不动：后端、路由、权限、`DebugDrawer.vue`（仅在校验时确认抽屉在深舱上的可读性，必要处最小调整）、其他页面。

## ADDED Requirements
### Requirement: 实验舱画布
测试台页面 SHALL 渲染为局部深色舱体：纯黑画布、网格纹理、舱体描边；浅色与深色全站主题下均无白块残留、文字对比达标。

#### Scenario: 浅色主题进入测试台
- **WHEN** 全站为浅色主题时进入 /models/test
- **THEN** 测试台区域呈深色舱体，与浅色管理台形成明确「入舱」切换，无浅色漏底

#### Scenario: 深色主题进入测试台
- **WHEN** 全站为深色主题时进入 /models/test
- **THEN** 舱体与画布层次依然可辨（面板/描边/文字对比不塌陷）

### Requirement: 终端绿点缀令牌
系统 SHALL 通过 tokens.css 新增的 LAB 令牌（`--color-lab-accent` 等）提供终端绿点缀；业务组件只引用 var()，不新增裸 hex。

#### Scenario: 状态灯发光
- **WHEN** 探针 verdict=ok 或消息 status=done
- **THEN** 对应状态灯以终端绿呈现并带呼吸/辉光动效；失败=红、警告=琥珀、未测试=zinc 空心

### Requirement: 功能零回归
改版 SHALL 保留全部既有交互：发送/流式渲染/停止/编辑重发/清空确认、探针分阶段报告、Markdown 与代码块复制、思考折叠、智能滚动、调试抽屉能力禁用逻辑、权限守卫。

#### Scenario: 流式对话回归
- **WHEN** 在应用对话模式发送消息
- **THEN** 三点加载 → 思考折叠块 → Markdown 流式正文 → 完成态操作行全链路与改版前行为一致，仅视觉变化

## 验收口径
- ESLint 0 / vue-tsc 0 / Vite build EXIT=0。
- 浏览器走查：浅色主题 + 深色主题各一轮；375px 窄屏无横向溢出；console 无新增解析告警。
- 真实外呼一轮（可选，费用极小）：确认流式视觉链路。
