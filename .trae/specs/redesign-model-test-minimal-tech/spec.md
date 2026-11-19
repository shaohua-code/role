# 模型测试台「极简浅色科技」改版 Spec（取代 redesign-model-test-lab 深色实验舱方向）

## Why
用户在看到深色实验舱实现后明确要求推翻换方向，选定 Linear / Vercel 式极简浅色科技：冷静、精密、工程感，与其长期偏好的轻奢极简黑白灰体系一致。深舱方向（LAB 令牌 + 五组件深舱化）已落地代码，本 spec 将其整体替换为浅色科技视觉；业务逻辑（SSE 流式、探针、判权、Markdown、诊断、调试抽屉）零改动。

## 设计方向
- **语言**：Linear / Vercel 控制台——大留白、1px 细线框、克制圆角与阴影、mono 数据字体、单点高饱和电光蓝承载「活性/进行中/交互焦点」。
- **强调色**：电光蓝（浅色主题 `#2563eb`，与现有 `--color-info` 同值；深色主题提亮为 `#60a5fa` 保证对比），经新令牌 `--color-tech-accent` 引用；成功/失败/警告仍走既有语义色，不与强调色混用。
- **状态表达**：静态小圆点（无呼吸辉光、无发光）——ok=success 绿、fail=error 红、warn=warning 琥珀、pending=zinc 空心；进行中的「活性」由蓝色控件/光标表达。
- **纹理**：仅页面舱区一层极淡点阵（zinc 透明线，alpha ≤0.5），可一键移除；拒绝扫描线/粒子/辉光等重装饰。
- **熟悉感**：布局骨架（AdminPageHeader / 身份卡 / 上下文行 / 状态行 / 双列工作区）不动；与全站浅色管理台自然同构，无「入舱」割裂。

## What Changes
- `frontend/src/styles/tokens.css`：
  - **移除**深色实验舱令牌组（`--color-lab-*` 全部）、`--lab-grid-image`、`@keyframes lab-breathe`；
  - 新增 TECH 令牌：`--color-tech-accent`（电光蓝，双主题）、`--color-tech-accent-subtle`（蓝 8% 底）、`--tech-dot-image`（极淡点阵）、`@keyframes tech-blink`（终端光标闪烁，替代 lab-blink）。
- `views/models/test/index.vue`：深舱容器 → 浅色卡片组（白底 `--color-bg-elevated` + 1px `--color-border` + `--shadow-sm` + radius-lg）；模型身份卡精修：mono 编号小标（模型 key，非 LAB-01）、静态状态点、mono 大写字段标签；控制钮回浅色描边风；权限守卫/空态浅色化。
- `StatusStrip.vue`：工程化遥测条——hairline 四格保留但改白底细线；英文 mono 模块标签（CONFIG/AUTHZ/PROVIDER/GENERATION）+ 中文 tooltip；静态状态点四态 + 大号状态词（ok 绿/ fail 红/ warn 琥珀/ pending zinc）；探针钮改全站主按钮风（石墨黑实心，与 antd primary 同源语言）。
- `ContextBar.vue`：浅色参数面板——移除深舱任意变体类，Select/Segmented 回归组件默认浅色外观（仅保留必要圆角/宽度）；能力 chips 细线标签，reasoning/thinking_output 用蓝描边 + subtle 蓝底高亮。
- `ChatColumn.vue`：浅色会话流——用户消息右对齐浅灰气泡（`--color-bg-subtle`）+ `YOU` mono 角标；助手消息细 zinc 左边线（非蓝）+ 模型名角标；思考折叠块、探针卡、错误横幅、操作行、回底按钮、输入区全部浅色化；发送钮石墨黑实心、停止钮红描边、探针钮蓝描边；三点加载与光标用 tech 蓝 + tech-blink。
- `DiagnosticPanel.vue`：浅色工程监控面板——Tab ink-bar 改 tech 蓝；时间线节点静态语义点（无发光 shadow）；思考卡/用量三格白底细框；payload pre 用 subtle 灰底。
- `markdown.ts`：输出类名切回浅色令牌（正文 zinc-900、表格 zinc-200 线、行内码灰底蓝文字、引用灰线）；**代码块保持深色卡片**（工程文档惯例：深底代码在浅色页面中聚焦可读），语言标签/复制钮浅色化适配深底。
- 深舱期间引入的原生 `<button>` 保留（行为已验证），仅换浅色样式类，不回退组件结构。

## Impact
- Affected specs: 取代 `.trae/specs/redesign-model-test-lab/`（该 spec 文档保留存档，不再实施）。
- Affected code:
  - `frontend/src/styles/tokens.css`
  - `frontend/src/views/models/test/index.vue`
  - `frontend/src/views/models/test/components/{ChatColumn,StatusStrip,ContextBar,DiagnosticPanel}.vue`
  - `frontend/src/views/models/test/markdown.ts`
- 不动：后端、路由权限、DebugDrawer（仅走查可读性）、其他页面、已验证的全部交互逻辑。

## ADDED Requirements
### Requirement: 浅色科技令牌
系统 SHALL 以 `--color-tech-accent` 等 TECH 令牌提供电光蓝强调（双主题对比达标）；`views/models/test` 内禁止裸 hex，且不再残留任何 `--color-lab-*` 引用。

#### Scenario: 深舱令牌清理
- **WHEN** 改版完成后全局搜索
- **THEN** 源码与样式中不存在 `--color-lab`、`lab-breathe`、`lab-blink`、`lab-grid` 字样

### Requirement: 浅色控制台视觉
测试台 SHALL 与全站浅色管理台同构：白底细框卡片、静态状态点、mono 数据标签、单点电光蓝；深色全站主题下自动翻转且层次不塌陷。

#### Scenario: 双主题可读
- **WHEN** 分别在浅色/深色全站主题打开 /models/test
- **THEN** 卡片、描边、正文、代码块对比达标，无白块/黑块漏底，无发光呼吸类重动效

### Requirement: 功能零回归
改版 SHALL 保留全部既有交互：发送/流式/停止/编辑重发/清空确认、探针分阶段报告、Markdown 与代码块复制、思考折叠、智能滚动与回底按钮、调试抽屉能力禁用、权限守卫。

#### Scenario: 流式对话回归
- **WHEN** 应用对话模式发送消息
- **THEN** 三点加载 → 思考折叠 → Markdown 流式正文（含深色代码块）→ 完成态操作行，行为与改版前一致

## 验收口径
- ESLint 0 / vue-tsc 0 / Vite build EXIT=0；`--color-lab` 全局零命中。
- 浏览器走查：浅色 + 深色主题各一轮；375px 无横向溢出；console 无新增解析告警。

## 增补：布局架构与降噪（用户二轮反馈，2026-11-18）
### 背景
用户反馈：对话区块太小、滚动不对（页面与对话区双滚动）；对话与诊断（思考/事件/用量）都应有独立滚动；部分区域应收起避免杂乱；授权增删不必要元素。

### What Changes（增补）
- **视口锁定双列布局（lg+）**：页面根 `lg:overflow-hidden`；顶部控制卡全部 `shrink-0`；工作区 grid 去掉 `h-[calc(max(480px,100vh-470px))]` hack，改 `min-h-0 flex-1` 吃满剩余高度；ChatColumn 消息区与 DiagnosticPanel Tab 内容区各自独立滚动，外壳（mgmt-shell-content）不产生页面滚动。
- **窄屏降级（<lg）**：根容器恢复 `overflow-y-auto`，对话/诊断面板给固定高度（560/420px），页面纵向滚动可达。
- **上下文行可折叠**：ContextBar 卡片加「测试上下文」折叠头（chevron）；收起后仅一行摘要（模式 · 租户 · 应用 · 模型），默认展开。
- **状态行瘦身**：StatusStrip 单元 padding 与状态词字号下调，探针行压缩为单行。
- **删减重复信息**：ChatColumn 输入区参数 chips 行删除（调试抽屉与诊断面板「请求与用量」已含同信息）；同步移除 `paramChips` prop 与 index.vue 对应 computed，`paramsSummary` 改为直接由 params 计算。
- 诊断三 Tab（思考过程/事件/请求与用量）保持 Tab 隔离（同屏只看一类，本身即降噪），内容区独立滚动不变。

### 增补验收场景
#### Scenario: 独立滚动
- **WHEN** lg+ 视口下发送长回答
- **THEN** 仅对话消息区滚动，顶部控制卡与输入区固定；诊断面板内容区独立滚动；外壳无滚动条
#### Scenario: 上下文折叠
- **WHEN** 点击上下文卡片折叠头
- **THEN** ContextBar 隐藏并显示一行上下文摘要，工作区高度自动扩大；再次点击恢复

