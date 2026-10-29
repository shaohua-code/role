# 管理台权限页面重度重设计（P389 候选）

## Summary

对两个管理台界面做「黑白灰重度精修 + 交互重构」：

1. **授权弹窗**（`RolePermissionGrantModal.vue`）：从「顶部 chips + 单列滚动」重构为**左域导航 + 右码区双栏**，新增**已选摘要条**（当前最大交互缺口——67 码勾选后无处总览），码项卡片化，预览区对比化，操作条固定。
2. **权限目录页**（`PermissionCatalog.vue`）：顶部新增**域总览统计卡带**（账本式编号区块，对齐 P368/P369 设计语言），点击卡片即筛选；表格行视觉精修。
3. 零后端改动、保存链路（v-model → preview → PUT）零改动、判权/可选性逻辑零改动——纯展示与交互层。

视觉基准：项目「轻奢极简黑白灰」设计系统（zinc + 石墨黑，token 变量，深浅主题自适应），重度精修而非换风格。

## Current State（实测于 2026-10-28）

### RolePermissionGrantModal.vue（P388 后现状）
- 宽 680px 单列；顶部 2 个 a-alert + 横排域 chips + 单个 `a-checkbox-group` 内六组分区（组头可折叠）
- **交互缺口**：① 勾选后无「已选总览」，需在 67 码中回找；② chips 横排 7 个占一行半，挤压码区垂直空间；③ checkbox 裸样式无质感；④ 预览影响区为纯文字堆叠；⑤ 底部按钮随内容滚动
- 保存链路：`selectedIds`（checkbox-group v-model）→ `previewChanges` → `applySave`（PUT）——**不可动**

### PermissionCatalog.vue（P388 后现状）
- `AdminListPage` 单表格 + 两个下拉筛选（域/命名空间）+ 搜索；域信息仅以小 tag 呈现在命名空间列
- **交互缺口**：① 无全域概览（67 码按域分布一眼不可见）；② 下拉筛选比可点击统计卡多一步；③ 行视觉平淡（编码列无主次、状态 tag 平铺）
- 登记弹窗为标准 a-form，视觉与主站一致但无精修

### 共享资产
- `utils/permissionGroups.ts`：六域映射（platform/tenant/collab/app/platform-res/business + other）——保持唯一口径，不改
- 设计 token：`--color-border/-strong`、`--color-text-primary/-secondary/-muted`、`--color-bg-container`、`--color-brand`（深浅自动翻转）
- 教训约束：不用 a-tag 承载自定义样式（cssinjs 注入顺序坑，P362/P388 已验证原生 span + token 更稳）；未注册的 antd 组件不可用（P358）

## Proposed Changes

### 1. RolePermissionGrantModal.vue — 双栏重构

**布局**：modal `width="680px"` → `"880px"`；内容区改 `display:grid; grid-template-columns: 188px 1fr`（窄屏 <760px 降级单列，左导航变横滑 chips——保留现 chips 样式作窄屏形态）。

**左栏域导航（新增）**：
- 竖向列表：首项「全部 67」+ 六域项（`PERMISSION_DOMAINS` 过滤 count>0）
- 每项：域名 + 灰色计数徽标 + **该域已选数**（如「成员协作 8/12」）——点击切换 `domainFilter`（单选语义与现 chips 相同）
- active 项：左侧 3px 石墨黑竖条 + 加粗 + 浅灰底（token 自适应）
- 底部附「已选合计 N」小字
- 窄屏：整条横向滚动，行为不变

**右栏码区（重构）**：
- **已选摘要条（新增，常驻）**：`已选 N 项` + 最近勾选的前 6 个码 chips（中文主显，点击可取消勾选）+ N>6 时「+M」+「清空」文字按钮（清空后需重新预览，与既有 selectionChanged 警戒兼容）
- 码项**卡片化**：每个选项改为带边框圆角卡片（`border 1px var(--color-border)`、radius 8、padding 8 10、hover 提升边框色）；选中态：`border-color: var(--color-text-primary)` + 背景浅灰（`color-mix` 或 token）；禁选态：透明度 .55 +「停用，仅可撤销」保留
- 组头精修：左 3px 竖条（石墨黑）+ caret + 名称 + 计数徽标（灰底圆角小方块）+ hint 右对齐；折叠/展开加 `transition`（max-height 或 v-show + CSS transition，避免 JS 动画库）
- 双栏时 `max-height: 56vh` 独立滚动（左栏随弹窗，右栏内滚）

**预览影响区（精修）**：
- 「新增 / 撤销」改两列对比卡：新增卡（绿字标 + 码列表 mono）、撤销卡（红字标）——语义色仅此两处（符合设计系统「语义色仅绿/红/琥珀」）
- 成员影响 alert 保留在上方

**操作条（固定）**：
- 底部按钮区改 `position: sticky; bottom: 0` + `background: var(--color-bg-container)` + 上 hairline 边——滚动时始终可见

**零改动清单**：props/emits、`selectedIds`/`previewChanges`/`applySave`、AUTHORITY_MANAGE_CODES 禁选、disableIamCodes、关闭重置逻辑（追加重置摘要条相关状态即可）。

### 2. PermissionCatalog.vue — 域总览带 + 表格精修

**域总览统计卡带（新增，账本式）**：
- 位于 `AdminListPage` 之上（页面根包一层 `div.permission-page`，flex column gap）
- 7 张卡横排（grid 7 列，<1100px 换 4 列，<700px 2 列）：「00 全部 67」+ 六域（编号 01–06 + 域名 + 大号 mono 数量 + 活动数小字）
- 点击卡片 = 设置 `domainFilter`（选中卡黑边加重，与弹窗导航同语言）；再次点击取消回全部
- 卡片样式：白底细边 radius 10、编号 mono 极小字、数量 22px tabular、hover 边框加深 + 轻阴影（对齐 P368 OverviewStatCard 语言但非 clickable 跳转而是筛选）

**表格行精修**：
- 权限编码列：改为双行（描述中文主行 + mono 码副行），与弹窗口径统一——说明列改为仅 resource/scope 补充说明，列重排：`编码（含说明）/ 命名空间+域 / 状态 / 关联角色 / 操作`，砍掉独立「说明」列（描述已上主行）与「资源类型」「操作 Scope」合并为 `resource · scope` mono 小列——列数 8→6，去横向滚动（总宽 ≤992 原则）
- 域列：域标签改为「色点 + 域名」（色点=石墨黑空心圆点，业务码=命名空间名）——全部行有归属，不再只 iam 打标
- 状态 tag、行 hover（依赖现有 --color-row-hover，无需改）保持

**登记弹窗**：表单结构不变，仅间距/文案微调（与整体节奏一致）。

### 3. 不做的事（边界）
- 不动后端、不动 `utils/permissionGroups.ts` 口径
- 不引入新依赖/动效库（纯 CSS transition）
- 不改 RolesTab / RoleManagement 调用方（弹窗 props 契约不变，自动继承新 UI）
- 不实施 P1 收敛可选集 / Q2 隐藏平台组（仍待裁决）

## Assumptions & Decisions

- 「交互重点全选」解读为对这两个界面的全方位升级：章节导航→弹窗左域导航；动效→折叠/选中/摘要微交互；矩阵重构→目录域统计卡+表格精修；整体视觉→字号层级/hover/固定操作条
- 弹窗 880px 在 1280 视口下安全（项目已有 820px 弹窗先例）
- 已选摘要条「清空」直接改 `selectedIds`（触发既有「选择已变化需重新预览」警戒，无需新增状态）
- 窄屏（<760px）双栏降级为「横滑域 chips + 单列码区」，保留 P388 chips 作为移动形态

## Verification

1. `npm run build`（vue-tsc + Vite）exit 0
2. 静态自查：props/emits 契约未变（两调用方零改动）、保存链路字段未变、全部颜色走 token（grep 无裸 hex 新增）
3. 浏览器走查（用户复看）：弹窗双栏/域导航切换/已选摘要/卡片选中态/预览对比卡/固定操作条；目录页统计卡点击筛选/表格新列结构；深浅主题两套
4. P389 入 CHANGELOG + 进度文档 + 速览表前端行
