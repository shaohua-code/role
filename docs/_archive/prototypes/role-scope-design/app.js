// 角色作用域设计原型 · 交互逻辑（静态数据，全部来自系统 P383 修正后的真实码集）

// 平台角色码集：27 个管理码全集（L1 platform.super_admin 专属）
const PLATFORM_CODES = [
  'iam.tenant.read', 'iam.tenant.manage', 'iam.user.read', 'iam.user.manage',
  'iam.role.manage', 'iam.role.read', 'iam.permission.read', 'iam.permission.manage',
  'iam.organization.read', 'iam.organization.manage', 'iam.member.read', 'iam.member.manage',
  'iam.group.read', 'iam.group.manage', 'iam.invitation.manage',
  'iam.application.read', 'iam.application.manage', 'iam.application.secret.rotate',
  'iam.app_role.assign', 'iam.app_role.read', 'iam.app_role.manage',
  'iam.model.read', 'iam.model.manage', 'iam.theme.manage',
  'iam.audit.read', 'iam.authorization.simulate', 'iam.platform.overview.read',
]

// 租户角色码集：L3 模板 21 码（P383 修正后）
const TENANT_CODES = [
  'iam.organization.read', 'iam.organization.manage',
  'iam.member.read', 'iam.member.manage',
  'iam.group.read', 'iam.group.manage',
  'iam.invitation.manage',
  'iam.application.read', 'iam.application.manage', 'iam.application.secret.rotate',
  'iam.app_role.assign', 'iam.app_role.read', 'iam.app_role.manage',
  'iam.role.read', 'iam.permission.read', 'iam.permission.manage',
  'iam.model.read', 'iam.model.manage', 'iam.theme.manage',
  'iam.audit.read', 'iam.authorization.simulate',
]

// 应用管理员码集：L2 模板 15 码（P383 收敛后，organization.* 归 L3）
const APP_ADMIN_CODES = [
  'iam.application.read', 'iam.application.manage', 'iam.application.secret.rotate',
  'iam.app_role.read', 'iam.app_role.manage',
  'iam.member.read', 'iam.member.manage',
  'iam.invitation.manage', 'iam.group.read', 'iam.group.manage',
  'iam.theme.manage', 'iam.audit.read', 'iam.model.read',
  'iam.permission.read', 'iam.authorization.simulate',
]

// 自定义「管理员」码集：同 L2 域但强制剥离 4 个授权权码（P383 三防线），可另持业务码
const CUSTOM_ADMIN_CODES = APP_ADMIN_CODES.filter(code =>
  !['iam.app_role.manage', 'iam.member.manage', 'iam.invitation.manage', 'iam.group.manage'].includes(code))

const AUTHORITY_CODES = new Set([
  'iam.app_role.manage', 'iam.member.manage', 'iam.invitation.manage', 'iam.group.manage'])

// 码分组（展示顺序）
const CODE_GROUPS = [
  { label: '租户域', match: code => code.startsWith('iam.organization') },
  { label: '成员协作', match: code => ['iam.member', 'iam.invitation', 'iam.group'].some(p => code.startsWith(p)) },
  { label: '应用域', match: code => ['iam.application', 'iam.app_role'].some(p => code.startsWith(p)) },
  { label: '目录治理', match: code => ['iam.role', 'iam.permission'].some(p => code.startsWith(p)) },
  { label: '模型 / 主题 / 审计', match: code => ['iam.model', 'iam.theme', 'iam.audit', 'iam.authorization'].some(p => code.startsWith(p)) },
  { label: '平台专属', match: code => ['iam.tenant', 'iam.user', 'iam.platform'].some(p => code.startsWith(p)) },
  { label: '业务码（应用命名空间）', match: code => !code.startsWith('iam.'), business: true },
]

// 演示器角色（数据来自系统真实实现）
const DEMO_ROLES = [
  {
    id: 'super-admin',
    name: '平台超级管理员',
    key: 'platform.super_admin',
    kind: 'platform',
    kindLabel: '平台角色',
    codes: PLATFORM_CODES,
    scopeNote: '全平台生效：对任意租户、任意应用都有管理能力（L1 代管路径）。仅平台租户的成员可持有，角色禁停用、禁删除。',
    layers: { platform: 'on', tenant: 'on', app: 'on', partial: false },
    impact: '泄漏影响面：全平台（最高危，故禁删禁停 + 种子固定）',
  },
  {
    id: 'org-admin',
    name: '租户管理员',
    key: 'tenant.org_admin',
    kind: 'tenant',
    kindLabel: '租户角色',
    codes: TENANT_CODES,
    scopeNote: '单个租户全域生效：该租户下所有应用、组织、成员、用户组、审计。application_id 为 NULL 的租户域角色，判权时对同租户任何应用都入选。',
    layers: { platform: 'dimmed', tenant: 'on', tenantFocus: 'a', app: 'on', partial: false },
    impact: '泄漏影响面：整个租户（中危）',
  },
  {
    id: 'app-admin',
    name: '应用管理员',
    key: 'app.admin',
    kind: 'application',
    kindLabel: '应用角色',
    codes: APP_ADMIN_CODES,
    scopeNote: '钉住单个应用生效：仅在该应用的授权检查中入选。组织域（organization.*）不可持有——P383 已从 L2 模板剥离，归 L3 专属。',
    layers: { platform: 'dimmed', tenant: 'partial', app: 'on', partial: true },
    impact: '泄漏影响面：单个应用（最低危）',
  },
  {
    id: 'custom-admin',
    name: '管理员（自定义角色）',
    key: 'ops.admin（示例 key）',
    kind: 'application',
    kindLabel: '应用角色 · 自定义',
    codes: CUSTOM_ADMIN_CODES,
    scopeNote: 'L2 创建的业务自定义角色：码域与应用管理员相同，但 4 个授权权码（角色/成员/邀请/用户组管理）被强制禁持——「管理员不能管理管理员」（P383 三防线：前后端禁选 + 克隆剥离）。',
    layers: { platform: 'dimmed', tenant: 'partial', app: 'on', partial: true },
    impact: '泄漏影响面：单个应用，且天然无法自我扩权',
  },
]

// ---- 03 作用域演示器 ----

const roleListEl = document.getElementById('roleList')
const scopeStackEl = document.getElementById('scopeStack')
const codeGroupsEl = document.getElementById('codeGroups')

function chip(code) {
  const isAuthority = AUTHORITY_CODES.has(code)
  const isBusiness = !code.startsWith('iam.')
  const classes = ['code-chip']
  if (isAuthority) classes.push('authority')
  if (isBusiness) classes.push('business')
  return `<span class="${classes.join(' ')}">${code}</span>`
}

function renderRole(role) {
  // 左侧选中态
  document.querySelectorAll('.role-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.roleId === role.id)
  })

  // 三层作用域图（on=该层生效点亮；partial=承载绑定但不授码，虚线；dimmed=与该角色无关）
  const layers = role.layers
  const platformClasses = ['scope-layer', layers.platform === 'on' ? 'on' : 'dimmed']
  const tenantClasses = ['scope-layer', layers.tenant === 'on' ? 'on' : '']
  const appClasses = ['scope-layer', layers.app === 'on' ? 'on' : '', layers.partial ? 'partial' : '']
  const tenantFocus = role.layers.tenantFocus === 'a'
  const tenantNodes = layers.platform === 'on'
    ? '<span class="layer-node">所有租户</span>'
    : `<span class="layer-node ${tenantFocus ? 'on' : ''}">租户 A</span><span class="layer-node">租户 B</span>`
  const appNodes = layers.platform === 'on'
    ? '<span class="layer-node">所有应用</span>'
    : '<span class="layer-node">DeerFlow</span><span class="layer-node">CRUD Demo</span>'
  scopeStackEl.innerHTML = `
    <div class="${platformClasses.join(' ').trim()}">
      <span class="layer-label">PLATFORM</span>
      <span class="layer-node">IAM 平台${layers.platform === 'on' ? '（全量）' : ''}</span>
    </div>
    <div class="${tenantClasses.join(' ').trim()}">
      <span class="layer-label">TENANT</span>
      ${tenantNodes}
    </div>
    <div class="${appClasses.join(' ').trim()}">
      <span class="layer-label">APPLICATION</span>
      ${appNodes}
      ${layers.partial ? '<span class="scope-note">仅钉住的应用（虚线 = 租户层只承载绑定，不授码）</span>' : ''}
    </div>`

  // 码分组
  let groupsHtml = ''
  CODE_GROUPS.forEach(group => {
    const codes = role.codes.filter(group.match)
    if (!codes.length) return
    groupsHtml += `<h4>${group.label} · ${codes.length}</h4><div class="code-chips">${codes.map(chip).join('')}</div>`
  })
  if (!groupsHtml) groupsHtml = '<p class="code-empty">该角色不持有任何权限码（如 app.member：业务码由管理员另行授予）。</p>'
  codeGroupsEl.innerHTML = groupsHtml

  // 影响面摘要
  const summary = document.createElement('p')
  summary.className = 'scope-summary'
  summary.innerHTML = `<strong>${role.name}</strong>（${role.kindLabel}）：共持有 <strong>${role.codes.length}</strong> 个权限码。${role.scopeNote} ${role.impact}。`
  codeGroupsEl.appendChild(summary)
}

DEMO_ROLES.forEach(role => {
  const btn = document.createElement('button')
  btn.className = 'role-btn'
  btn.dataset.roleId = role.id
  btn.innerHTML = `
    <span class="role-name">${role.name}</span>
    <span class="role-key">${role.key}</span>
    <span class="role-count">${role.codes.length} 码 · ${role.kindLabel}</span>`
  btn.addEventListener('click', () => renderRole(role))
  roleListEl.appendChild(btn)
})
renderRole(DEMO_ROLES[0])

// ---- 04 反事实推演 ----

const CF_STEPS = [
  {
    title: '起点：一个普通应用的「管理员」',
    desc: '单池设计下，他的角色持有 <code>iam.member.manage</code>——授权语义变成「全租户成员管理」，而不是「本应用成员管理」。',
    pool: { verdict: 'breach', text: '防线失守：码不分区，「本应用」约束不存在，member.manage 直通全租户。' },
    scoped: { verdict: 'block', text: '现状拦截：应用角色（application_id 钉住）只在单应用判权中入选，租户全域成员管理无从谈起。' },
  },
  {
    title: '第二步：把自己写进任意应用的管理角色',
    desc: '持 <code>iam.member.manage</code> 即可操作任意租户成员的角色绑定——把自己加进其他应用，甚至塞进 <code>app.admin</code>。',
    pool: { verdict: 'breach', text: '提权扩散：一个应用的管理员获得了跨应用的人员布局能力。' },
    scoped: { verdict: 'block', text: '现状拦截：绑定操作按应用判权（iam.app_role.manage 限本应用），跨应用写绑定直接 403。' },
  },
  {
    title: '第三步：吞并租户全域管理面',
    desc: '若租户域码（<code>iam.organization.manage</code>、<code>iam.audit.read</code>、<code>iam.model.manage</code>…）同池可授，组织、审计、模型、主题全域尽收。',
    pool: { verdict: 'breach', text: '全域沦陷：码域互斥消失，租户 21 码与应用 15 码的边界被抹平。' },
    scoped: { verdict: 'block', text: '现状拦截：P383 已把 organization.* 从 L2 模板剥离——应用角色物理上拿不到租户域码。' },
  },
  {
    title: '第四步：触碰平台层',
    desc: '若平台码（<code>iam.tenant.manage</code>、<code>iam.user.manage</code>）也在池中，可新建/停用任意租户、管理全平台用户——提权链顶格。',
    pool: { verdict: 'breach', text: '灾难：一个应用管理员的误配 = 全平台沦陷。' },
    scoped: { verdict: 'block', text: '现状拦截：平台码只授 platform 角色、只绑平台租户 membership；另有 slug=platform 五处防呆（P382）。' },
  },
]

const worldNoteEl = document.getElementById('worldNote')
const cfStepsEl = document.getElementById('cfSteps')

function renderWorld(world) {
  document.querySelectorAll('.cf-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.world === world)
  })
  worldNoteEl.textContent = world === 'pool'
    ? '假设：所有角色进同一个池子，判权不再按作用域过滤，只看「有没有这个码」。'
    : '现状：roles.kind 三级 + 绑定钉住 + 码域互斥，同一套攻击路径逐层被拦。'
  cfStepsEl.innerHTML = CF_STEPS.map((step, index) => {
    const verdict = world === 'pool' ? step.pool : step.scoped
    return `<li class="cf-step">
      <span class="step-no">${index + 1}</span>
      <div>
        <h4>${step.title}</h4>
        <p class="step-desc">${step.desc}</p>
      </div>
      <div class="verdict verdict-${verdict.verdict}">
        <span class="v-head">${verdict.verdict === 'breach' ? '✗ ' : '✓ '}${world === 'pool' ? '单池' : '现状'}</span>
        ${verdict.text}
      </div>
    </li>`
  }).join('')
}

document.querySelectorAll('.cf-btn').forEach(btn => {
  btn.addEventListener('click', () => renderWorld(btn.dataset.world))
})
renderWorld('pool')

// ---- 06 现状审计 ----

const AUDIT_ITEMS = [
  { text: '<code>roles.kind</code> 三值枚举（platform / tenant / application），绿场单头迁移即建', ref: 'P340 · 0001_greenfield_iam' },
  { text: '应用角色唯一键 (tenant, application, key) 钉住作用域，跨应用同名角色互不越界', ref: 'P340' },
  { text: '角色绑定挂 TenantMembership——角色永不脱离租户；平台角色仅存在于平台租户', ref: 'P340' },
  { text: 'capabilities 两层结构：租户域码在 tenants[].codes，应用码在 tenants[].applications[].codes，前端据此分流控制台', ref: 'P341' },
  { text: '模板码分域：L1 平台 27 码 / L3 租户 21 码 / L2 应用 15 码 / L4 零管理码', ref: 'P383' },
  { text: '组织域码（organization.*）从应用角色剥离，归租户角色专属', ref: 'P383' },
  { text: '自定义角色强制禁持 4 个授权权码（三防线：平台侧 422 / 应用侧 422 / 克隆剥离 + 前端禁选）', ref: 'P383' },
  { text: 'admin 路由逐路由按 iam.* 码判权，废除 platform_admin 一刀切', ref: 'P340 · rbac_guards' },
  { text: '平台租户五处业务写入口 422 防呆，防止 L1 宿主被误当业务租户使用', ref: 'P382' },
]

const auditListEl = document.getElementById('auditList')
auditListEl.innerHTML = AUDIT_ITEMS.map(item =>
  `<li><span class="check">✓</span><span>${item.text}</span><span class="ref">${item.ref}</span></li>`
).join('')

// ---- 吸顶导航当前区块高亮 ----

const navLinks = Array.from(document.querySelectorAll('.topnav a'))
const sections = navLinks.map(link => document.querySelector(link.getAttribute('href')))

function syncNav() {
  const offset = 120
  let current = 0
  sections.forEach((section, index) => {
    if (section.getBoundingClientRect().top <= offset) current = index
  })
  navLinks.forEach((link, index) => link.classList.toggle('active', index === current))
}
document.addEventListener('scroll', syncNav, { passive: true })
syncNav()
