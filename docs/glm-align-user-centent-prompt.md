> ⚠️ **口径提示（2026-10-29）**：本文含历史 DeerFlow / 「新项目接入」描述，**不代表现行产品路径**。现行配权请以 [`配权说明书.md`](./配权说明书.md) 与管理台工作台为准；接入示例已归档至 `docs/_archive/examples`。


# GLM 5.3 执行提示词：对齐 user-centent 的 IAM 管理台改造（工程落 role）

> 你是编程执行代理。打开本文件后**立即开工**，不要再向用户追问范围或方案。  
> 用户已确认原则：**方案看 `user-centent`，工程落在 `role`**。
> **口径更新（2026-10-29）：** 应用资源树为正式方案；git 仓库暂不新建。 已废除「资源≈仅权限编码 / 不建 Resource」硬约束，见 §2.2.1 与 `docs/配权说明书.md`。  
> 本文件自包含；仍须在改代码前**实读**蓝图与现网源码，禁止凭记忆瞎改。

---

## 1. 角色与目标

### 1.1 你是谁

- 在 Windows 本机仓库上改代码的全栈工程师（偏前端管理台，必要时补后端小接口）。
- 技术栈以 `D:\project\role` 现有为准，不要引入无关框架。

### 1.2 总目标

把 `D:\project\role` 的权限管理台，按 `D:\project\user-centent\apps\user-center-sys` 的**信息架构与主操作流**对齐，解决「权限系统乱、入口散」问题。

产品主路径写死为三步（中文 UI 全程可见）：

1. **权限编码**（登记/维护 code）
2. **角色挂码**（角色绑定权限编码）
3. **用户配角色**（一用户可多角色；生效权限 = 角色并集）

### 1.3 本回合必须完成（Wave 1）

**先只做 Wave 1**，做完自检通过后再停下来汇报；**不要**擅自开做 Wave 2–4，除非用户本回合明确说继续。

Wave 1 交付物见第 5 节。

---

## 2. 硬约束（做 / 不做）

### 2.1 必须做

| 项 | 说明 |
|---|---|
| 工程仓 | 只改 `D:\project\role` |
| 蓝图仓 | 只读参考 `D:\project\user-centent`（尤其 `apps\user-center-sys`） |
| IA 对齐 | 应用工作台 = 左树应用 + 右 Tab「角色 / 权限编码 / **应用资源树**」 |
| 主路径 | 权限编码 → 角色挂码 → 用户多角色；**应用内菜单/按钮用资源树挂到角色** |
| 中文 UI | 侧栏、页标题、空态、按钮、Toast 用中文；**权限 code / 角色码保持英文** |
| UI 规范 | 遵守 `D:\project\role\docs\ui-design-system.md` 与 checklist |
| 通用组件 | 优先复用 `frontend/src/components/Admin*.vue`、`shared/ui`；禁止重复造轮子 |
| 文件夹/index | 新模块用「文件夹 + index」；有关联的文件同目录 |
| 进度同步 | 改完后更新 `docs/项目总览与进度.md`（若文件名乱码，按 AGENTS.md 指向的交接文件更新）与 `CHANGELOG.md` 事实记录 |

### 2.2 明确不做（违反即失败）

- **不做 DeerFlow**：不迁移、不改 `D:\project\deer-flow`、不恢复 IAM/SSO 对接、不写接入文档。
- **不做「新项目接入」能力**：Wave 1 必须从导航/路由/懒加载中**下线** `project_integration`（可保留源码目录但不可再进侧栏；优先删除路由与 NAV 项）。
- **不迁仓**：不把工程搬到 `user-centent`，不在 `user-centent` 补生产后端。
- **不推倒绿场模型**：不重做 L1–L4；不另起一套与现网冲突的平行权限体系。
- **应用资源树为正式能力（已落地）**：`application_resources` + `role_application_resources`；类型 `menu | button | data_rule`。蓝图「资源」Tab = **应用资源树**（菜单/按钮等），**不是**「仅把资源当成权限编码的别名」。权限编码与资源树**并存、分工不同**——见 §2.2.1。
- **组织归属不改挂应用**：组织仍挂租户；Wave 1 不改组织模型。
- **不做蓝图里的这些页**：应用字段配置、数据条件 DSL、应用组实体、互斥角色、B/C/G 三端、portal、business 端。
- **不擅自清库 / 重置 DB / 删生产数据 / 强推 git**。
- **不引入**与现仓无关的 UI 库；保持 Vue 3 + Ant Design Vue 4 + Tailwind 4 + Vite。

### 2.2.1 三层模型（正式口径，消除「标准打架」）

配权与鉴权相关能力分三层，**全部正式，不要互相替代**：

| 层 | 是什么 | 管什么 | 典型落点 |
|---|---|---|---|
| **① 权限编码** | 全局/平台权限码目录（如五域管理码） | 管理台菜单裁剪、能力清单；角色可挂码 | `/admin/permissions`、角色 permissions |
| **② 角色挂码** | 用户 ← 多角色；角色 ← 权限编码（并集生效） | 「谁能进管理能力 / 业务身份」 | role-bindings、RolePermission |
| **③ 应用资源树** | 按应用维护的菜单/按钮/数据规则树；角色勾选资源子集 | 业务端菜单渲染、按钮显隐、规则挂载 | `application_resources`、角色资源授权、`GET /authorization/my-resources` |

**对照蓝图 user-centent：**「资源」Tab = 第 ③ 层，不是第 ① 层的别名。  
**不要再写：**「资源 ≈ 仅权限编码」「不建 Resource / 不对齐 Resource」。现网资源树保留并作为正式方案。详见 `docs/配权说明书.md`。

### 2.3 决策优先级

用户当次指令 > 本提示词 > `AGENTS.md` > 蓝图视觉细节 > 个人审美。

---

## 3. 路径与技术栈

### 3.1 仓库路径

| 用途 | 路径 |
|---|---|
| 工程（改这里） | `D:\project\role` |
| 蓝图（只读） | `D:\project\user-centent` |
| 蓝图核心应用 | `D:\project\user-centent\apps\user-center-sys` |
| 蓝图：应用与角色 | `...\views\appAndRoleManagement\`（`index.vue` + `components\appTreeList.vue` + `role\` + `resource\`） |
| 蓝图：组织 | `...\views\department\`（左树 + 成员/组 Tab；Wave 2 才做） |
| 管理台前端 | `D:\project\role\frontend` |
| 导航 | `frontend\src\app\navigation.ts` |
| 路由 | `frontend\src\app\router.ts` |
| 侧栏 | `frontend\src\app\components\AppSidebar.vue` |
| Feature 懒加载 | `frontend\src\app\featureLoaders.ts`、`App.vue` |
| 功能模块 | `frontend\src\features\*` |
| API 封装 | `frontend\src\shared\services\api.ts` |
| UI 规范 | `docs\ui-design-system.md` |
| 后端 | `D:\project\role\backend`（FastAPI） |
| Admin API | `backend\app\api\v1\admin\` |
| 应用侧角色/权限 | `backend\app\api\v1\tenant_admin_application_roles.py` 与 `admin\applications.py`、`admin\access_control.py` |

### 3.2 前端技术栈

- Vue 3 + TypeScript + Vue Router
- Ant Design Vue 4
- Tailwind CSS 4（`@tailwindcss/vite`）
- pnpm；开发脚本：`pnpm -C frontend dev`（以 package.json 为准）
- 管理台默认口：常见为 `http://127.0.0.1:5175`（以实际 vite 配置为准）

### 3.3 后端技术栈

- FastAPI，`/api/v1`
- 管理面权限码 `iam.*`；绿场 L1–L4 角色码不变
- 已有关键能力（优先复用，勿重复造端点）：
  - `GET/POST /admin/applications`
  - `GET/POST /admin/applications/{id}/permissions`
  - `GET /admin/roles`、`PUT /admin/roles/{id}/permissions`
  - 应用维度：`GET/POST /applications/{id}/roles`、`GET/PUT .../roles/{role_id}/permissions`（见 `tenant_admin_application_roles.py`）
  - 用户多角色：`GET/PUT /admin/users/{id}/role-bindings`
  - 权限目录：`GET/POST /admin/permissions`

### 3.4 现有侧栏分组（已部分对齐，Wave 1 在此上收敛）

当前 `NAV_GROUPS`：`root` / `identity`（身份与组织）/ `access`（应用与权限）/ `platform`（平台治理）/ `ops`（审计与验证）。

Wave 1 目标侧栏「应用与权限」应变为以 **应用工作台** 为主入口；列表页可暂时保留深链，但侧栏优先工作台。

---

## 4. 蓝图对照摘要（必须对齐的交互）

### 4.1 概念映射（蓝图 → role）

| user-centent | role 落地 |
|---|---|
| 应用左树 | `applications` 列表做成左树/左列表 |
| 角色 Tab | 该应用下的角色（复用应用角色 API 或全局角色按应用过滤） |
| 资源 Tab | **应用资源树**（menu/button/data_rule；正式能力，已落地） |
| 字段配置 / 数据字段 Tab | **不做** |
| 组织左树 + 成员/组 | Wave 2；组织仍挂租户 |
| 用户配角色 | 已有多选 bindings；Wave 3 再打磨 Transfer |
| 审计登录/操作 | Wave 3 拆 Tab |
| IAM 设置/用户池 | Wave 3 弱化聚合；Wave 1 不动 |

### 4.2 应用工作台布局（Wave 1 对标）

蓝图 `appAndRoleManagement/index.vue`：

- 左：`appTreeList` 选应用
- 右：`a-tabs` —— 对齐蓝图做 **角色 / 资源（应用资源树）**；现网另可保留「权限编码」Tab（管理码，与资源树分工）
- 未选应用或无效节点：空态（中文）

你在 `role` 中实现等价布局，视觉跟 `ui-design-system.md`（克制、深色侧栏+浅色内容），不要抄蓝图的花哨样式或 i18n 键名。资源树 CRUD / 角色勾选复用现有 `application_resources` API，**禁止**再改回「资源=权限编码别名」。

### 4.3 日常配权主路径（写进工作台副标题/空态）

1. （平台/管理能力）在「权限编码」维护码 → 「角色」挂码 → 「用户」多选角色  
2. （业务应用菜单/按钮）在应用工作台 **资源树** Tab 维护菜单/按钮 → 在角色上勾选资源 → 用户持有角色后业务端拉 `my-resources`  

---

## 5. Wave 1（本回合立即执行）

### 5.1 功能清单

1. **新建「应用工作台」页面**
   - 建议路径：`/application-workspace`（或等价清晰 path）
   - 建议 PageKey：`application_workspace`
   - 建议 feature 目录：`frontend/src/features/application-workspace/`（`index` 组织）
   - 布局：左应用树/列表 + 右 Tabs（与现网对齐时可含）：
     - Tab：**角色** —— 列出/创建该应用角色；挂权限编码 + **勾选应用资源树**
     - Tab：**应用资源树（资源）** —— 菜单/按钮/数据规则 CRUD（正式；`/applications/{id}/resources`）
     - Tab：**权限编码** —— 管理/能力码（与资源树并存，勿合并成一层）
   - 未选应用：中文空态，提示「请先选择左侧应用」
   - 页头副标题点明：管理码三步 + 资源树何时用

2. **导航改造**
   - 在「应用与权限」组加入「应用工作台」，并尽量置于组内靠前
   - **下线「新项目接入」**：从 `NAV_ITEMS`、`PAGE_PATHS` 展示、`featureLoaders`、路由可见入口移除 `project_integration`  
     - 旧 URL `/project-integration`：重定向到应用工作台或应用管理（二选一，推荐工作台）
   - 过渡期可保留「应用管理 / 角色管理 / 权限编码」列表入口，但文案可标注「列表」；**不要**再强调接入

3. **权限码**
   - 工作台入口的 `requiredPermissions` 与现有应用/角色/权限读权限对齐（例如同时满足应用读 + 角色读或权限读中的合理组合，保持与现网能力模型一致）
   - 不要发明未入库的新 `iam.*` code，除非同步后端种子；Wave 1 优先复用已有 code

4. **后端**
   - 若现有 API 已能按 `application_id` 拉角色与权限：**前端组装即可，不强制新接口**
   - 仅当确实缺「按应用过滤」且前端无法安全拼装时，再补最小只读/写入端点；保持绿场模型

5. **文档**
   - 更新交接进度文档与 `CHANGELOG.md`：写明 Wave 1 完成项、验证方式、未做 Wave 2+

### 5.2 实现指引（执行顺序）

1. 通读：
   - `user-center-sys/.../appAndRoleManagement/index.vue` 与 `components/appTreeList.vue`、`role/roleTable.vue`、`resource/resourceTable.vue`（只学结构）
   - `role/frontend/src/app/navigation.ts`、`featureLoaders.ts`、`features/applications/*`、`features/roles/*`、`features/permissions/*`、`features/application-roles/*`
   - `docs/ui-design-system.md` 关键章节
2. 设计组件拆分（示例，可按现仓风格微调）：
   - `features/application-workspace/index.vue`（壳：左树+右 Tab）
   - `components/AppTree.vue`（或同目录）
   - `tabs/RolesTab.vue`、`tabs/PermissionsTab.vue`
3. 接线 API：统一走 `shared/services/api.ts`，禁止页面直接硬编码 fetch。
4. 改导航与懒加载；下线接入入口。
5. 本地启动管理台，用管理员账号点验（见验收）。
6. 更新文档。

### 5.3 Wave 1 验收标准（全部满足才算完成）

- [ ] 侧栏「应用与权限」可见 **应用工作台**；**不可见**「新项目接入」
- [ ] 打开应用工作台：左侧可选应用；选中后右侧有 **角色 / 应用资源树（资源）**（及可选的权限编码）Tab
- [ ] 在权限编码 Tab 能看到（或新增）与该应用相关的权限码
- [ ] 在角色 Tab 能查看该应用相关角色，并能进入/完成挂码（与现网权限编辑能力一致）
- [ ] 未选应用有中文空态
- [ ] UI 无明显魔法色堆砌；使用现有 Admin* 页头/表格/空态组件
- [ ] `pnpm -C frontend build` 或至少 `vue-tsc`/dev 无新增错误（按你环境能跑的最严一项）
- [ ] 未改 DeerFlow；未清库；未迁仓
- [ ] CHANGELOG / 进度文档已记一笔

### 5.4 完成后的汇报格式（对用户）

用中文简短汇报：

1. 改了哪些路径/文件  
2. 如何点验（URL + 步骤）  
3. 已知限制  
4. Wave 2 是否等待指令  

---

## 6. 后续 Wave（本回合不要做，除非用户另说）

### Wave 2 — 组织工作台

- 左组织树 + 右 Tab「成员 / 用户组」
- 组仍挂租户，仅在组织上下文展示
- 若缺 `GET /admin/organizations/{id}/members` 再补最小 API
- 不做组织改挂应用

### Wave 3 — 用户与审计体验

- 用户配角色 Transfer/多选体验打磨（后端 bindings 已有）
- 审计页登录/操作 Tab（可前端过滤）
- 租户 + 登录主题弱化聚合；平台治理默认折叠

### Wave 4 — 收口

- 散落的应用/角色/权限列表并进工作台或降为高级入口
- 工作台空态引导强化三步主路径
- 仍不做 DeerFlow、不做新项目接入；**应用资源树已是正式方案，保持演进，勿再写成「不做 Resource」**

---

## 7. 编码规范

1. **文件夹 / index**：新功能 `features/<name>/index.vue`（或 `index.ts` 导出），子组件放同目录 `components/`、`tabs/`。
2. **Token**：禁止新写散落 `#7c5cff` 等；用 CSS 变量 / 设计 token（见 ui-design-system）。
3. **通用组件优先**：`AdminPageHeader`、`AdminListPage`、`AdminEmpty`、`AdminTableToolbar`、`AdminFilterPanel` 等。
4. **中文文案**：用户可见字符串中文；code/role key 英文。
5. **API**：只经 `api()` 封装；错误用现有 Toast/Error 模式。
6. **权限**：页面 `requiredPermissions` 与后端守卫一致；无权限走现有无权限页逻辑。
7. **Git**：不强推；不改无关大文件；不提交密钥与 `.env`。
8. **数据库**：不做 destructive migration；不 reset；不删除用户数据。
9. **范围控制**：一次只交付 Wave 1；发现蓝图诱惑（字段配置等）一律跳过并在汇报里注明「刻意不做」。
10. **AGENTS.md**：尊重项目接手约定；DeerFlow 相关历史描述以「本任务不做」覆盖。

---

## 8. 自检清单（提交前逐条打勾）

### 范围

- [ ] 只改了 `D:\project\role`
- [ ] 只读了 `user-centent`，未在蓝图仓写生产代码
- [ ] 未碰 DeerFlow
- [ ] 未做新项目接入功能；侧栏已去掉接入

### Wave 1 功能

- [ ] 应用工作台左树 + 右 Tab（角色 / 应用资源树；权限编码可并存）可用
- [ ] 主路径文案出现在页头或空态
- [ ] 多角色既有能力未被破坏（用户管理仍可多选角色）

### 质量

- [ ] 符合 ui-design-system（克制、token、组件复用）
- [ ] TypeScript / 构建无明显新增错误
- [ ] 中文 UI，英文 code

### 文档与安全

- [ ] CHANGELOG + 进度交接已更新
- [ ] 未清库、未泄露密钥、未强推

---

## 9. 一句话开工指令（给你自己）

> 在 `D:\project\role` 对齐「应用工作台」（左树+角色/资源树/权限编码）；**资源 Tab = 应用资源树（正式）**，与权限编码分属不同层；从导航下线「新项目接入」；遵守 UI 设计系统与中文文案；文档口径见三层模型与《配权说明书》。

**现在开始执行 Wave 1。**
