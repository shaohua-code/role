import type { PageKey } from '@/router/navigation'

/** 步骤的执行者：决定徽章文案与颜色语义。 */
export type GuideActor = 'admin' | 'dev' | 'both'

export type GuideFact = {
  icon: string
  title: string
  summary: string
}

export type GuideStep = {
  id: string
  index: string
  icon: string
  title: string
  /** 一句大白话（面向所有人），配合比喻降低理解成本。 */
  plain: string
  actor: GuideActor
  /** 白话要点：非开发者读完即可理解这一步做什么。 */
  points: string[]
  /** 折叠的技术细节：契约条款与代码示例，开发者按需展开。 */
  techTitle: string
  techItems: string[]
  sampleLabel: string
  sample: string
}

export const HERO = {
  eyebrow: '统一身份平台 · 应用接入',
  title: '接入，其实只有五步',
  plain: '把账号、登录、权限判断交给平台保管，你的应用专心做业务——用户在你的界面里操作，安全的事平台兜底。',
  cta: '打开应用工作台',
  meta: ['不用自建账号体系', '官方 SDK 封装协议', '配置一次长期生效'],
}

export const FACTS: GuideFact[] = [
  {
    icon: '🪪',
    title: '这是什么',
    summary: '一个集中管账号和权限的中台：谁能登录、谁能做什么，都由平台统一判定，你的应用不再自己维护一套账号密码。',
  },
  {
    icon: '👥',
    title: '谁来接入',
    summary: '管理员和开发者各做一半：管理员在管理台点选配置（建应用、发角色）；开发者用官方 SDK 写少量代码。',
  },
  {
    icon: '🔌',
    title: '怎么用起来',
    summary: '只有两件事：登录时由平台验一次身份（跳到平台页，或在你自己的登录页直接验）；之后每个敏感操作问一句「这个人能不能做」，按回答放行。',
  },
]

/** 执行者徽章文案。 */
export const ACTOR_LABELS: Record<GuideActor, string> = {
  admin: '管理员配置',
  dev: '开发者接入',
  both: '管理员 + 开发者',
}

const CHECK_SAMPLE = `POST /api/v1/authorization/check
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "tenant_id": "<uuid>",
  "application_id": "<uuid>",
  "permission_code": "crm.document.read"
}`

const RESOURCES_SAMPLE = `GET /api/v1/authorization/my-resources?client_id={client_id}
Authorization: Bearer <access_token>`

// 应用内直登（密码授权）：服务端持密钥换取令牌的完整请求示例。
const PASSWORD_TOKEN_SAMPLE = `# 应用内直登：仅 trusted 应用，密钥只放服务端
POST /api/v1/oidc/token
Authorization: Basic base64(client_id:client_secret)
Content-Type: application/x-www-form-urlencoded

grant_type=password&username=user%40example.com&password=***&scope=openid%20profile%20email%20offline_access

# → 200  { access_token, id_token, refresh_token, expires_in, ... }
# → 400  { "error": "invalid_grant" }   账号密码错误 / 无该应用租户授权`

export const STEPS: GuideStep[] = [
  {
    id: 'prepare',
    index: '01',
    icon: '🏢',
    title: '登记你的应用',
    plain: '告诉平台「我有一个应用」，平台给它发一张身份证——之后的登录、判权都凭这张证。',
    actor: 'admin',
    points: [
      '在「应用工作台」创建应用：填名称，再填一个「登录后跳回的地址」。',
      '拿到两样东西：应用标识（client_id，可公开）和密钥（只显示一次，务必保存）。',
      '想让登录页长你家的样子？在「登录主题」里配 Logo 和配色，不用写代码。',
    ],
    techTitle: '契约细节',
    techItems: [
      '回调地址须与白名单精确匹配：默认允许 HTTPS 或 localhost 的 HTTP；内网 HTTP 部署可由运维配置 IAM_ALLOW_INSECURE_REDIRECT_URIS=true 放行。不允许通配。',
      'client_secret 仅在创建或轮换时展示一次，须写入业务服务端密钥库，不得放浏览器。',
      '登出地址与来源域名白名单一并登记；登录主题 show_register 只控制展示，不能开通注册。',
    ],
    sampleLabel: '',
    sample: '',
  },
  {
    id: 'grants',
    index: '02',
    icon: '🔑',
    title: '定义权限与数据范围',
    plain: '把「谁能读、谁能写」列成清单交给平台保管——还包括能看「多少」数据。',
    actor: 'both',
    points: [
      '把业务里的动作登记成权限码，例如「读文档」= crm.document.read。',
      '建角色勾上权限，再把角色发给用户；用户能做什么由角色决定。',
      '每个权限还要说清数据范围——最常用的是「只看自己的」，不配的话判权会直接失败。',
    ],
    techTitle: '契约细节',
    techItems: [
      '权限码必须落在该应用的 permission_namespace 内；应用侧登记固定 surface=business、requires_data_scope=true。',
      '创建应用时系统已自动放置 app.admin 与 app.member 模板；业务角色另建，不要占用这两个模板。',
      '数据范围（RoleDataScope）在角色「应用权限 → 数据权限」配置，常用 self；缺少策略时 check 失败，原因为 data_scope_policy_missing。',
    ],
    sampleLabel: '',
    sample: '',
  },
  {
    id: 'oidc',
    index: '03',
    icon: '🔐',
    title: '接入登录',
    plain: '默认跳到平台验一次身份——像进景区：先在入口验票，再凭票根进园；也可以把检票员请到你家门口，用户在你的登录页输账号密码，验证仍在平台完成。',
    actor: 'dev',
    points: [
      '跳转登录（默认）：点登录 → 跳到平台登录页 → 验证通过后自动带凭证回到你登记的地址。',
      '应用内直登（可选）：用户在你的登录页输入账号密码，你的服务端向平台换取令牌，全程不离开你的界面。',
      '令牌过期前可以无声续期，用户不用反复输密码。',
      '直登只对平台标记「可信」的应用开放，密钥只能放在服务端——这是平台与你的约定。',
    ],
    techTitle: '契约细节（跳转 = 授权码 + PKCE；直登 = 密码授权）',
    techItems: [
      '跳转形态：业务服务端校验签名、iss、aud、exp 与随机 state；refresh 支持轮换与重放撤销。',
      '直登形态：POST /api/v1/oidc/token 带 grant_type=password；客户端凭据走 Authorization: Basic 头，不得进请求体。',
      '直登 scope 固定白名单 openid / profile / email / offline_access（必须含 openid），客户端不可自扩。',
      '直登仅对 trusted 应用开放；失败统一 invalid_grant（账号密码错与无租户授权同文案），防账号枚举。',
      '两种形态同一条入场判权：用户须持应用所属租户的有效角色；会话租户以令牌 tenant_id 为准，不信任请求头。',
      '访问令牌默认约 10 分钟；客户端密钥、长期令牌不得放浏览器；敏感操作仍需在线授权。',
    ],
    sampleLabel: 'token · password grant',
    sample: PASSWORD_TOKEN_SAMPLE,
  },
  {
    id: 'check',
    index: '04',
    icon: '🛡️',
    title: '每个操作问一句',
    plain: '拿不准就问平台：「这个人能不能做这件事？」平台回答能或不能，顺带告诉他能看哪些数据。',
    actor: 'dev',
    points: [
      '敏感操作执行前，用 SDK 问平台一次（一次最多可问 32 个权限）。',
      '平台返回「允许 + 数据范围」，你的列表按这个范围过滤数据。',
      '问不到（超时、故障）一律按「不能」处理——宁可拒绝，绝不放行。',
    ],
    techTitle: '契约细节',
    techItems: [
      'tenant_id 必须等于签发令牌的租户；application_id 可省略（默认令牌对应应用），不可切换到别的应用。',
      '通过时期望 allowed=true 且 data_scope.mode=any_of 带合法 constraints；SDK 默认超时 3 秒，失败关闭。',
      '同一用户多角色按并集合并；钉住 A 应用的角色不会进入 B 应用的 check。管理接口只用 IAM 管理会话。',
    ],
    sampleLabel: 'check',
    sample: CHECK_SAMPLE,
  },
  {
    id: 'resources',
    index: '05',
    icon: '🧭',
    title: '菜单按角色显隐',
    plain: '普通员工和管理员登录后看到的界面不一样——哪些菜单、按钮该出现，平台帮你算好。',
    actor: 'dev',
    points: [
      '在应用工作台维护应用的「资源树」：菜单是主干，按钮挂在菜单下。',
      '前端读取「当前用户的资源树」，按 code 控制显示或隐藏。',
      '显隐只是体验层，真正的安全把关仍在上一步的判权。',
    ],
    techTitle: '契约细节',
    techItems: [
      '菜单可带 path、icon、extra；按钮与数据规则必须挂在菜单下，角色勾选时服务端自动补齐祖先。',
      'my-resources 仅返回 active 节点；按钮/数据规则用 code 做前端显隐。',
      'data_rule 的过滤条件存于 extra 由业务端解释，不能替代 RoleDataScope。',
    ],
    sampleLabel: 'my-resources',
    sample: RESOURCES_SAMPLE,
  },
]

/** 上线前检查清单：五条「必须如此」的行为断言。 */
export const CHECKLIST: string[] = [
  '有数据范围的权限：check 返回「允许」，且带着数据范围',
  '没配数据范围的权限：必须失败，而不是悄悄放行',
  '拿 A 租户的令牌访问 B 租户的数据：必须被拒绝（403）',
  '启用应用内直登：应用已标记「可信」，密钥只在服务端，失败提示不泄露账号是否存在',
  '曾用旧方式接入：删除旧 client_id 与密钥，升级 SDK 2.x 后重新验证',
]

/** 页脚范围说明：本页只讲契约，不含联调承诺。 */
export const SCOPE_NOTE =
  '本页只说明对接契约：不在页面内创建应用、也不展示密钥。本阶段不含业务系统联调、生产 npm / PyPI 发版、公开注册与配额限制上线。'

/** 顶部快速入口（管理员旅程的起点）。 */
export const QUICK_LINKS: Array<{ page: PageKey; label: string }> = [
  { page: 'application_workspace', label: '应用工作台' },
  { page: 'themes', label: '登录主题' },
]
