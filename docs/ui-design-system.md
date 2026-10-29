# *12 — UI 设计系统与前端开发规范*

> *适用：`frontend/`（Vue 3 + Ant Design Vue 4 + Tailwind 4）\
> 气质参考：Linear / Vercel Dashboard / Stripe Dashboard —* ***高级、克制、强层级、中等信息密度**\
> 目标：统一重调管理台观感，并约束后续开发。\
> 现状锚点：深色侧栏 + 浅色内容区；品牌紫* *`#7c5cff`* *大量硬编码于* *`App.vue`* */* *`style.css`；`shared/theme.ts`* *主要服务* ***OIDC 登录主题**，不是管理台 design token。*

***

## *0. 现状摘要（改造前）*

| *项*        | *现状*                                                                  | *问题*                        |
| ---------- | --------------------------------------------------------------------- | --------------------------- |
| *布局*       | *`a-layout`* *+* *`AppSidebar`* *244/76 + content* *`max-w-[1500px]`* | *尚可，缺统一页面模板约定*              |
| *主题*       | *`ConfigProvider`* *+ localStorage 主色/深浅/疏密*                          | *token 与 CSS 双轨，硬编码 hex 遍地* |
| *侧栏*       | *深色 +* *`AuroraGlow`*                                                 | *偏「花」；高级风应减弱光斑*             |
| *登录页*      | *多层 radial-gradient + 渐变按钮*                                           | *与控制台克制风割裂（登录可略强，控制台必须克制）*  |
| *组件封装*     | *曾有 Admin\* 组件；路径以仓库为准*                                               | *新页常直接堆 antd，间距/卡片不齐*       |
| *Tailwind* | *已接* *`@tailwindcss/vite`*                                            | *与 antd token 未统一源*         |

***

## *1. 品牌气质定位*

***一句话：*** *B2B IAM 控制台 — 冷静、可信、密而不挤、少装饰。*

| *要*                           | *不要*                           |
| ----------------------------- | ------------------------------ |
| *清晰层级（侧栏 / 顶栏 / 页头 / 卡片 / 表）* | *大面积炫光、彩虹渐变堆砌*                 |
| *中性色主导，品牌色作点缀（≤5% 面积）*        | *主按钮、侧栏选中、链接、图表全用高饱和紫*         |
| *8px 网格、对齐、留白可呼吸*             | *随意* *`margin: 13px`、卡片套卡片套卡片* |
| *状态可读（成功/警告/危险/信息）*           | *只靠颜色不靠文案/图标*                  |
| *表格与筛选是一等公民*                  | *为「好看」牺牲扫描效率*                  |

***模式决策（写死）：***

- ***管理台：深色侧栏 + 浅色内容区（Split）*** *— 保留现结构，取消侧栏强 Aurora。*
- ***用户可选「内容区暗色」**：内容区跟随* *`data-theme`，侧栏始终深色中性（非品牌渐变底）。*
- ***登录 / OIDC 品牌页**：允许稍强品牌表现，但主色仍来自同一 token，禁止第三套紫色。*

***

## *2. 色彩 Token*

### *2.1 原则*

1. ***禁止**在业务 Vue/CSS 新写* *`#7c5cff`、`#f4f5f9`* *等魔法色；必须用 CSS 变量或 Tailwind 语义类。*
2. *单一真相：`frontend/src/styles/tokens.css`（新建）→ 映射到 Ant Design* *`theme.token`* *+ Tailwind* *`@theme`。*
3. *品牌色可被用户 ColorPicker 覆盖，但只改* *`--color-brand`* *一处，禁止改散落 hex。*

### *2.2 色板（P350 黑白灰轻奢，现行）*

***中性（Zinc 纯中性灰，不带蓝调）***

| *Token*                    | *Light 内容区* | *用途*         |
| -------------------------- | ----------- | ------------ |
| *`--color-bg-canvas`*      | *`#FAFAFA`* | *页面底*        |
| *`--color-bg-elevated`*    | *`#FFFFFF`* | *卡片/顶栏*      |
| *`--color-bg-subtle`*      | *`#F4F4F5`* | *表头、toolbar* |
| *`--color-border`*         | *`#E4E4E7`* | *默认边框*       |
| *`--color-border-strong`*  | *`#D4D4D8`* | *强调分割*       |
| *`--color-text-primary`*   | *`#18181B`* | *主文案*        |
| *`--color-text-secondary`* | *`#52525B`* | *次要*         |
| *`--color-text-muted`*     | *`#A1A1AA`* | *占位/禁用辅助*    |

***侧栏（固定纯黑）***

| *Token*                       | *值*                     | *用途*              |
| ----------------------------- | ----------------------- | ----------------- |
| *`--color-sider-bg`*          | *`#09090B`*             | *侧栏底（纯黑，无渐变）*     |
| *`--color-sider-text`*        | *`#A1A1AA`*             | *未选中*             |
| *`--color-sider-text-active`* | *`#FAFAFA`*             | *选中文字/logo 方块底*   |
| *`--color-sider-item-hover`*  | *`rgba(255,255,255,0.06)`* | *hover*           |
| *`--color-sider-item-active`* | *`rgba(255,255,255,0.10)`* | *选中底（中性白叠加）*      |
| *`--color-sider-accent`*      | *`#FAFAFA`*             | *选中指示条 2px（白，不用品牌色）* |

***品牌（石墨黑；高饱和只留给语义色）***

| *Token*                  | *默认*                       | *说明*                           |
| ------------------------ | -------------------------- | ------------------------------ |
| *`--color-brand`*        | *`#18181B`*                | *石墨黑主色；暗色内容区块翻转为 `#FAFAFA`（黑上黑不可见）* |
| *`--color-brand-hover`*  | *`#3F3F46`*                | <br />                         |
| *`--color-brand-subtle`* | *`rgba(24,24,27,0.06)`*    | *浅选中/focus ring（暗色块为白 8%）*      |

> *P350 起默认即石墨黑；历史默认紫 `#5B5BD6` 在 App.vue 读 localStorage 时视为未设置。ColorPicker 仍可覆盖 `--color-brand`。*

***语义（唯一点缀）***

| *Token*             | *值*         | *Ant 映射*         |
| ------------------- | ----------- | ---------------- |
| *`--color-success`* | *`#059669`* | *`colorSuccess`* |
| *`--color-warning`* | *`#D97706`* | *`colorWarning`* |
| *`--color-error`*   | *`#DC2626`* | *`colorError`*   |
| *`--color-info`*    | *`#2563EB`* | *`colorInfo`*    |

***antd 特殊 token（实测坑，P350）***：`colorLink` 默认跟 `colorInfo` 蓝而非 `colorPrimary`——黑白灰下必须在 bridge 显式设 `colorLink: primary`（操作列/退出等 link 收归墨色）；`colorTextLightSolid`（实底按钮文字）暗色下必须反转深色，否则浅底白字白上白。

### *2.3 Ant Design 映射（ConfigProvider）*

```ts
// 规格示意：从 CSS 变量或 tokens.ts 读入
token: {
  colorPrimary: brand,
  colorSuccess, colorWarning, colorError, colorInfo,
  colorBgLayout: canvas,
  colorBgContainer: elevated,
  colorBorder: border,
  colorText: textPrimary,
  colorTextSecondary: textSecondary,
  borderRadius: 8,          // 见 §4
  fontFamily: 'Inter, "Noto Sans SC", system-ui, sans-serif',
  fontSize: 14,
  controlHeight: 36,        // comfortable；compact=32
}
components: {
  Layout: { siderBg: 'transparent', headerBg: 'transparent', bodyBg: canvas },
  Menu: {
    // 侧栏 dark 菜单：用中性选中，避免整条亮紫
    darkItemBg: 'transparent',
    darkItemSelectedBg: 'rgba(255,255,255,0.08)',
    darkItemSelectedColor: '#F8FAFC',
    itemBorderRadius: 8,
  },
  Table: { headerBg: subtle, rowHoverBg: brandSubtle },
  Card: { /* 弱阴影，见 §4 */ },
}
```

***

## *3. 字体*

| *级别*         | *Token / 用途*    | *规格*                                                      |
| ------------ | --------------- | --------------------------------------------------------- |
| *字体栈*        | *`--font-sans`* | *`Inter, "Noto Sans SC", system-ui, sans-serif`*          |
| *等宽*         | *`--font-mono`* | *`ui-monospace, SFMono-Regular, Menlo, monospace`（ID/密钥）* |
| *Display*    | *登录大标题等*        | *24–28 / 600 / 1.25*                                      |
| *Page title* | *页头标题*          | *20 / 600 / 1.3*                                          |
| *Section*    | *卡片标题*          | *15–16 / 600 / 1.4*                                       |
| *Body*       | *默认*            | *14 / 400 / 1.55*                                         |
| *Secondary*  | *说明、表头*         | *13 / 400–500 / 1.5*                                      |
| *Caption*    | *标签、时间戳*        | *12 / 400 / 1.45*                                         |
| *Overline*   | *侧栏分组标题*        | *11 / 500 / 1.4 / tracking 0.06em / uppercase 可选*         |

***字重：*** *常规 400、强调 500、标题 600；**禁止**大段 700，品牌 mark 除外。\
**中文：*** *避免全大写英文 tracking 过大导致中文标题难看；分组可用「小型标签」而非强制 uppercase。*

***

## *4. 间距 · 圆角 · 阴影 · 边框（8px 网格）*

### *4.1 间距*

| *Token*        | *px* | *用途*                 |
| -------------- | ---- | -------------------- |
| *`--space-1`*  | *4*  | *图标与文字间隙*            |
| *`--space-2`*  | *8*  | *紧凑控件内边距*            |
| *`--space-3`*  | *12* | <br />               |
| *`--space-4`*  | *16* | *顶栏 padding、卡片内边距基准* |
| *`--space-5`*  | *20* | <br />               |
| *`--space-6`*  | *24* | *内容区 padding（桌面）*    |
| *`--space-8`*  | *32* | *区块之间*               |
| *`--space-10`* | *40* | *罕见大分隔*              |

***规则：*** *新写 margin/padding 只能是 4 的倍数；Review 打回* *`13px`、`18px`* *除非在 tokens 注册例外。*

### *4.2 圆角*

| *Token*           | *px*   | *用途*                 |
| ----------------- | ------ | -------------------- |
| *`--radius-sm`*   | *6*    | *输入框、Tag*            |
| *`--radius-md`*   | *8*    | *按钮、菜单项、小卡片（**默认**）* |
| *`--radius-lg`*   | *12*   | *大卡片、Modal*          |
| *`--radius-full`* | *9999* | *Avatar、pill*        |

*默认控件圆角* ***8**，与 Ant* *`borderRadius: 8`* *对齐（现状 12 偏「消费级」，升级时改为 8）。*

### *4.3 阴影（克制）*

| *Token*           | *值*                                 | *用途*           |
| ----------------- | ----------------------------------- | -------------- |
| *`--shadow-none`* | *none*                              | *默认卡片可用边框代替阴影* |
| *`--shadow-sm`*   | *`0 1px 2px rgba(15,23,42,0.05)`*   | *顶栏轻微*         |
| *`--shadow-md`*   | *`0 4px 16px rgba(15,23,42,0.06)`*  | *下拉/Popover*   |
| *`--shadow-lg`*   | *`0 12px 40px rgba(15,23,42,0.10)`* | *Modal*        |

***Don't：*** *卡片* *`0 28px 90px`* *级重阴影（登录卡除外）。管理台卡片：**1px border + 极弱 sm 阴影或无阴影**。*

### *4.4 边框*

*默认* *`1px solid var(--color-border)`；不要用 2px 描边装饰。*

***

## *5. 布局*

### *5.1 壳层尺寸*

| *区域*           | *规格*                              |
| -------------- | --------------------------------- |
| *侧栏展开*         | ***240px**（现 244，统一到 240=30×8）*   |
| *侧栏折叠*         | ***72px**（现 76 → 72）*             |
| *顶栏高度*         | ***56px***                        |
| *内容水平 padding* | *24px（≥sm）；16px（窄屏）*              |
| *内容最大宽*        | ***1440px**（现 1500 → 1440，更整齐）居中* |
| *页头与首卡片间距*     | *16–24px*                         |

### *5.2 页面模板（新页必须套用）*

1. ***ListPage（表格页）**\
   `AdminPageHeader`* *→ 可选* *`FilterPanel`* *→* *`DataCard`* *包* *`Table`* *+ 底部分页。*
2. ***DetailPage**\
   页头（标题+主操作）→ 2 栏或单栏 Form/Descriptions。*
3. ***SettingsPage**\
   左锚点或顶 Tabs + 右表单分区（`section`* *间距 32）。*

*禁止新页面从零搭* *`div`* *嵌套而不用 shared 页头/工具条。*

### *5.3 卡片*

- *列表主表面：**一张**主卡片包住表格，不要「筛选一张卡 + 表一张卡」除非筛选很重。*
- *内边距：24（桌面）/ 16（移动）。*
- *标题与操作同一行，右对齐 Primary + Secondary。*

***

## *6. 组件 Do / Don't*

### *Button*

| *Do*                                    | *Don't*        |
| --------------------------------------- | -------------- |
| *每页主操作* ***最多一个*** *`type="primary"`*   | *一排多个 primary* |
| *危险操作用* *`danger`* *+ Popconfirm/Modal* | *红按钮无确认*       |
| *次要用* *`default`，文字链用* *`link`* *且少用*   | *幽灵按钮满屏*       |
| *图标按钮提供* *`aria-label`*                 | *只有图标无标题*      |

### *Table*

| *Do*                                     | *Don't*                  |
| ---------------------------------------- | ------------------------ |
| *列少而精；超长 ID 用 mono + ellipsis + Tooltip* | *列宽拖到横向地狱无* *`scroll.x`* |
| *操作列固定右侧，≤3 个动作，其余收入「更多」*                | *每行 6 个 link*            |
| *空态用* *`Empty`* *+ 一句说明 + 可选 CTA*        | *空白一片*                   |
| *表头背景* *`--color-bg-subtle`，字重 500*      | *深色表头花纹*                 |

### *Form*

| *Do*                              | *Don't*            |
| --------------------------------- | ------------------ |
| *标签在上（垂直），宽度* *`max-w-xl`* *单列优先* | *无标签只 placeholder* |
| *校验文案具体（「邮箱格式不正确」）*               | *只红框无字*            |
| *提交中* *`loading`* *防重复*           | *可连点创建 10 条*       |

### *Modal / Drawer*

| *Do*           | *Don't*              |
| -------------- | -------------------- |
| *标题明确动作；主按钮在右* | *宽 > 720 还不用 Drawer* |
| *销毁时重置表单*      | *关闭后残留校验*            |

### *Menu（侧栏）*

| *Do*                                          | *Don't*                |
| --------------------------------------------- | ---------------------- |
| *选中：左侧 2px brand 条 + 中性底*                     | *整条高饱和紫底（现状偏亮）*        |
| *图标来自同一套* *`@ant-design/icons-vue`* *outline* | *混 filled / 自定义描边粗细不一* |
| *分组：上边距 16 + 小组标题 Caption*                    | *15 项一长串无分组时至少用视觉间隔*   |

***

## *7. 导航与信息架构视觉*

1. ***选中态：*** *中性底 + 文字变亮 + 左指示条（brand）；不要依赖渐变。*
2. ***分组建议（高级感来自结构）：***
   - *总览*
   - *资源（租户/应用/接入）*
   - *身份（用户/邀请/组/组织）*
   - *授权（角色/权限/模拟）*
   - *可观测（模型/用量/审计）*
   - *外观（主题）*
3. ***顶栏：*** *左：面包屑或页标题；右：密度、主题、主色、用户 — 控件高度一致，间距 8。*
4. ***健康状态点：*** *用语义色小圆点 + 文案，不要大色块。*

***

## *8. 动效*

| *允许*                               | *禁止*          |
| ---------------------------------- | ------------- |
| *150–200ms ease 边框/背景*             | *侧栏常驻大面积流动光斑* |
| *Modal/Drawer 使用 antd 默认*          | *自定义弹跳、视差*    |
| *`prefers-reduced-motion`* *已有则保持* | *无限闪烁、脉冲 CTA* |

*侧栏* *`AuroraGlow`：**默认关闭**或降为极低透明度静态光；高级风优先纯色侧栏。*

***

## *9. 可访问性与状态*

| *状态*       | *要求*                                                                                 |
| ---------- | ------------------------------------------------------------------------------------ |
| *Hover*    | *背景或边框可辨，对比度足够*                                                                      |
| *Focus*    | ***可见*** *focus ring：`0 0 0 3px var(--color-brand-subtle)`；勿* *`outline: none`* *不补* |
| *Disabled* | *降低透明度 +* *`not-allowed`；仍可读标签*                                                      |
| *Empty*    | *图标 + 标题 + 说明*                                                                       |
| *Error*    | *字段下红字 +* *`role="alert"`（表单）*                                                       |
| *Loading*  | *Spin 包住表格区域，保留页头*                                                                   |

*对比度：正文与底 ≥ 4.5:1；侧栏未选中文字用* *`#94A3B8`* *级别，勿过暗。*

***

## *10. 工程约定*

### *10.1 文件位置（落地时）*

```text
frontend/src/styles/tokens.css          # CSS 变量唯一源
frontend/src/styles/antd-bridge.ts      # 读 token → ConfigProvider theme
frontend/src/styles/tailwind-theme.css  # @theme 映射（可选）
frontend/src/shared/theme.ts            # 仅 OIDC 登录主题工具（勿塞管理台色）
frontend/src/shared/ui/                 # PageHeader / DataCard / FilterBar 等
frontend/src/appearance.css             # 仅放「覆盖 antd 且必须用 CSS」的桥接，禁止新业务色值
frontend/src/style.css                  # 全局 reset + import tokens；逐步删除硬编码 hex
```

### *10.2 硬规则*

1. ***新代码禁止**新增裸 hex（除* *`tokens.css`）。*
2. ***禁止**大段 inline* *`style="color:#..."`；动态主色只设 CSS 变量。*
3. *新页面必须使用 List/Detail/Settings 模板组件之一。*
4. *业务 feature 内* ***不写*** *Layout/Sider；只写内容区。*
5. *Tailwind：优先语义类（若映射）或* *`gap-4`/`p-6`* *等网格刻度；避免* *`p-[13px]`。*
6. *图标仅* *`@ant-design/icons-vue`（outline 为主）。*
7. *密度：`comfortable`（默认）与* *`compact`* *只切* *`componentSize`* *+ 少量间距变量，不维护两套页面。*
8. ***有通用组件必须先用通用组件**；新 UI 块默认进* *`shared/ui/`* *再被引用。*
9. ***文件按「文件夹/index」组织**；有关联的文件同一文件夹（见 10.5）。*

### *10.3 Code Review 检查项*

- [ ] *是否出现新增魔法色 / 重阴影 / 渐变按钮（管理台）？*
- [ ] *是否使用 PageHeader + 统一卡片？*
- [ ] *表格空态、加载、错误是否齐全？*
- [ ] *主按钮是否 ≤1？危险操作是否有确认？*
- [ ] *侧栏/路由是否只加数据未加视觉特例？*
- [ ] *暗色内容区是否仍可读（勿写死* *`#202a3b`* *在 dark 下）？*

### *10.5 通用组件与目录结构（强制）*

> *用户约定：后续每次改项目都按本规范走；**先不改代码，只定规则。***

1. ***通用组件优先***
   - *先查* *`frontend/src/shared/ui/`（及现有 Admin\* / 布局壳）是否已有可用组件。*
   - *有则复用并扩展 props；**禁止**在 feature 里再造同职责按钮条、页头、筛选条、空态、表格壳。*
   - *新抽通用组件必须进* *`shared/ui/`（或约定公共目录），并在本规范或 README 登记用途。*
2. ***文件夹 +*** ***`index`****写法***&#x20;
   - *一个模块 / 页面 / 组件 = 一个文件夹，入口为* *`index.vue`* */* *`index.ts`* */* *`index.tsx`。*
   - *对外只从文件夹根导入：`import X from '@/features/foo'`* *或* *`.../FooBar`（解析到* *`index`），避免深路径散落引用内部文件。*
   - *示例：*
     ```text
     features/users/
       index.vue              # 页面入口
       UserTable.vue          # 仅本页用
       useUserList.ts
       api.ts
     shared/ui/PageHeader/
       index.vue
       types.ts
     ```
3. ***有关联关系的文件放同一文件夹***
   - *同一功能域的页面、子组件、hooks、api、类型、样式放一起。*
   - *仅当被 ≥2 个无关 feature 使用时，才上提到* *`shared/`。*
   - *禁止把互相关联的文件拆到无关目录「图省事」。*
4. ***与现有仓库对齐***
   - *新增代码一律按上述结构；存量文件在触碰该模块时再顺手收拢，不要求一次性全仓搬迁。*

### *10.4 与 Ant Design Vue 落地步骤*

1. *抽出* *`tokens.css`，`:root`* */* *`[data-theme=dark]`* *两套内容区变量。*
2. *`antd-bridge.ts`* *生成* *`theme`* *供* *`App.vue`* *`a-config-provider`。*
3. *删减* *`App.vue`* *内联大段颜色对象，改为 bridge。*
4. *`appearance.css`* */* *`style.css`* *中硬编码改为* *`var(--...)`。*
5. *侧栏选中态改为中性 + accent bar。*
6. *统一 Admin 页面骨架组件后再改 feature 页。*

***

## *11. 分阶段（UI only）*

| *阶段* | *内容*                                           |
| ---- | ---------------------------------------------- |
| *U1* | *tokens + ConfigProvider bridge + 去 Aurora 强光* |
| *U2* | *侧栏/顶栏/内容宽/圆角 8 统一*                            |
| *U3* | *PageHeader/DataCard/FilterBar；表格页迁模板*         |
| *U4* | *style.css 去魔法色；登录页仅保留受控品牌渐变*                  |
| *U5* | *按 checklist 全页走查*                             |

***

## *12. 相关文档*

- *菜单与角色：[11-menu-role-relation.md](./11-menu-role-relation.md)*
- *前端守卫：[06-frontend.md](./06-frontend.md)*
- *验收清单：[12-ui-design-system-checklist.md](./12-ui-design-system-checklist.md)*

