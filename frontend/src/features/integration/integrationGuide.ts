import type { PageKey } from '../../app/navigation'

export type IntegrationPath = 'login' | 'api'
export type WizardPhase = 'setup' | 'project'

export type CodeTab = {
  label: string
  text: string
}

export type GuideStep = {
  order: string
  title: string
  summary: string
  items: string[]
  action: PageKey | null
  actionLabel: string
  samples: CodeTab[]
}

export const SETUP_STEPS: GuideStep[] = [
  {
    order: '1',
    title: '创建租户',
    summary: '在本平台建一个租户，记下 UUID。',
    items: [
      '打开「租户管理」，新建租户并复制租户 UUID。',
      '企业内部系统选组织型；面向 C 端用户选 ToC 消费租户。',
    ],
    action: 'tenants',
    actionLabel: '打开租户管理',
    samples: [],
  },
  {
    order: '2',
    title: '登记应用',
    summary: '登记应用；方案 A 必须填与业务完全一致的回调。',
    items: [
      '打开「应用管理」，绑定上一步租户，填写应用名称与 client_id。',
      '方案 A：回调必须含 http/https、host 与 path，且与业务 IAM_REDIRECT_URI 逐字相同。',
      '方案 B：也要创建应用（权限归属该应用）；回调可先填业务占位地址。',
      'Client Secret 只在创建或轮换时显示一次，立刻写入业务服务端密钥库。',
    ],
    action: 'applications',
    actionLabel: '打开应用管理',
    samples: [],
  },
  {
    order: '3',
    title: '登记权限码',
    summary: '登记稳定权限码，创建后不能改名。',
    items: [
      '打开「权限目录」，为该项目登记权限码。',
      '建议格式：项目.资源.动作，例如 crm.document.read。',
      '停用后不能再新增授权。',
    ],
    action: 'permissions',
    actionLabel: '打开权限目录',
    samples: [],
  },
  {
    order: '4',
    title: '创建角色并授权',
    summary: '建普通角色并授予权限；只看自己的数据再配 self。',
    items: [
      '打开「角色管理」，在该租户下创建普通角色（可绑定刚登记的应用）。',
      '把上一步权限码授予该角色。',
      '业务数据只能看自己的，再为对应权限配置 self 数据范围。',
    ],
    action: 'roles',
    actionLabel: '打开角色管理',
    samples: [],
  },
  {
    order: '5',
    title: '准备可登录用户',
    summary: '账号必须在 IAM 里，并绑到该租户角色。',
    items: [
      '打开「用户管理」或「成员邀请」，确保账号属于该租户并绑上角色。',
      '没有租户角色的用户登录后无法通过判权。',
    ],
    action: 'invitations',
    actionLabel: '打开成员邀请',
    samples: [],
  },
]

const loginEnvSample = [
  'IAM_ISSUER=http://localhost:8002',
  'IAM_CLIENT_ID=YOUR_CLIENT_ID',
  'IAM_CLIENT_SECRET=<创建应用时回显一次>',
  'IAM_REDIRECT_URI=http://localhost:8000/auth/callback',
  'IAM_API_URL=http://localhost:8002',
  'IAM_APPLICATION_ID=<应用UUID>',
].join('\n')

const loginPythonMount = [
  'from iam_oidc import IamOIDCClient',
  'from iam_fastapi_auth import InMemorySessionStore, mount_oidc_auth',
  '',
  'oidc = IamOIDCClient(',
  '    issuer=os.environ[\'IAM_ISSUER\'],',
  '    client_id=os.environ[\'IAM_CLIENT_ID\'],',
  '    client_secret=os.environ[\'IAM_CLIENT_SECRET\'],',
  '    redirect_uri=os.environ[\'IAM_REDIRECT_URI\'],',
  ')',
  'mount_oidc_auth(app, oidc_client=oidc, session_store=InMemorySessionStore())',
].join('\n')

const loginNodeMount = [
  'import { IamOIDCClient, InMemoryIamSessionStore, mountOidcAuth } from \'iam-sdk\'',
  '',
  'const oidc = new IamOIDCClient({',
  '  issuer: process.env.IAM_ISSUER,',
  '  clientId: process.env.IAM_CLIENT_ID,',
  '  clientSecret: process.env.IAM_CLIENT_SECRET,',
  '  redirectUri: process.env.IAM_REDIRECT_URI,',
  '})',
  'mountOidcAuth(app, {',
  '  oidcClient: oidc,',
  '  sessionStore: new InMemoryIamSessionStore(),',
  '})',
].join('\n')

const loginVueFrontend = [
  '<script setup lang=\'ts\'>',
  'import { onMounted, ref } from \'vue\'',
  '',
  'const me = ref<{ subject?: string } | null>(null)',
  '',
  '// 只跳业务后端入口；平台弹出统一登录页，secret 不进前端。',
  'function goLogin() {',
  '  window.location.href = \'/auth/login\'',
  '}',
  '',
  'async function loadMe() {',
  '  const res = await fetch(\'/auth/me\', { credentials: \'include\' })',
  '  me.value = res.ok ? await res.json() : null',
  '}',
  '',
  'onMounted(() => {',
  '  void loadMe()',
  '})',
  '</script>',
  '',
  '<template>',
  '  <button v-if="!me" type="button" @click="goLogin">登录</button>',
  '  <p v-else>已登录 {{ me.subject }}</p>',
  '</template>',
].join('\n')

const loginPermissionSample = [
  'from iam_authorization import IamAuthorizationClient',
  'from iam_fastapi import IAMFastAPI',
  '',
  'PERMISSION_MAP = {',
  '    \'document.read\': \'crm.document.read\',',
  '    \'document.create\': \'crm.document.create\',',
  '}',
  '',
  'iam = IAMFastAPI(',
  '    client=IamAuthorizationClient(os.environ[\'IAM_API_URL\'], application_id=os.environ[\'IAM_APPLICATION_ID\']),',
  '    session_dependency=load_verified_session,',
  '    permission_map=PERMISSION_MAP,',
  ')',
  '',
  '@app.post(\'/documents\')',
  'def create_document(_=Depends(iam.require_permission(\'document.create\'))):',
  '    return {\'ok\': True}',
].join('\n')

const loginBatchSample = [
  '{',
  '  "results": {',
  '    "crm.document.read": { "allowed": true },',
  '    "crm.document.create": { "allowed": false }',
  '  }',
  '}',
].join('\n')

export const LOGIN_PROJECT_STEPS: GuideStep[] = [
  {
    order: 'A1',
    title: '写入业务环境变量',
    summary: '把凭证写进业务服务端 .env，不要进前端仓库。',
    items: [
      '从应用管理复制 client_id、应用 UUID，以及创建时回显的 client_secret。',
      'IAM_ISSUER 本机用 http://localhost:8002，须与浏览器访问 host 一致。',
      'IAM_REDIRECT_URI 必须与应用管理登记的回调逐字相同。',
      '不要混用 localhost 与 127.0.0.1，否则登录 Cookie 带不过去。',
    ],
    action: 'applications',
    actionLabel: '打开应用管理',
    samples: [{ label: '.env', text: loginEnvSample }],
  },
  {
    order: 'A2',
    title: '后端挂登录路由',
    summary: '业务后端挂 SDK，自动提供 /auth/login、callback、logout、me。',
    items: [
      'Python FastAPI：mount_oidc_auth；会话只存在业务服务端。',
      'Node Express：mountOidcAuth，语义相同。',
      '完整可运行对照：仓库 examples/iam-crud-fastapi（provision.py 后 uvicorn，访问 /auth/login）。',
    ],
    action: null,
    actionLabel: '',
    samples: [
      { label: 'Python', text: loginPythonMount },
      { label: 'Node', text: loginNodeMount },
    ],
  },
  {
    order: 'A3',
    title: '前端只跳登录入口',
    summary: '登录按钮跳业务 /auth/login，用 /auth/me 画当前用户。',
    items: [
      '用户点登录时跳转到业务站 /auth/login，由平台弹出统一登录页。',
      '业务前端不保存 Client Secret，也不直接调 IAM 管理接口。',
    ],
    action: null,
    actionLabel: '',
    samples: [{ label: 'Vue', text: loginVueFrontend }],
  },
  {
    order: 'A4',
    title: '受保护接口在线判权',
    summary: '写操作走 require_permission，或自行带 OIDC token 调 check。',
    items: [
      '别名必须登记到稳定权限码；未登记在启动期就应失败。',
      'owner_only 需要角色上已配置 self 数据范围，否则会 403。',
    ],
    action: null,
    actionLabel: '',
    samples: [{ label: 'Python', text: loginPermissionSample }],
  },
  {
    order: 'A5',
    title: '菜单用批量快照',
    summary: '展示用 check-batch；真正写操作仍须逐次在线判权。',
    items: [
      '业务后端一次判定 1–32 个权限码，前端只用来显示/隐藏按钮。',
      'allowed 不为 true 时不要渲染写操作；执行时后端再 check 一次。',
    ],
    action: null,
    actionLabel: '',
    samples: [{ label: 'JSON', text: loginBatchSample }],
  },
  {
    order: 'A6',
    title: '自测清单',
    summary: '按下面四项确认接入可用，再上线。',
    items: [
      '有角色用户能登录并回到业务站点。',
      '无角色用户被拒绝（403 / access_denied）。',
      '访问别人的资源被拒绝（404 或 403）。',
      '登出后受保护接口 401。',
    ],
    action: null,
    actionLabel: '',
    samples: [],
  },
]

const apiLoginCurl = [
  'curl -s http://localhost:8002/api/v1/auth/login \\',
  '  -H "Content-Type: application/json" \\',
  '  -d "{\\"email\\":\\"user@example.com\\",\\"password\\":\\"<业务侧保管>\\"}"',
].join('\n')

const apiLoginPython = [
  'import httpx',
  '',
  'res = httpx.post(',
  '    \'http://localhost:8002/api/v1/auth/login\',',
  '    json={\'email\': \'user@example.com\', \'password\': \'<业务侧保管>\'},',
  ')',
  'token = res.json()[\'access_token\']',
].join('\n')

const apiBearerSample = [
  'Authorization: Bearer <access_token>',
].join('\n')

const apiCheckSample = [
  'curl -s http://localhost:8002/api/v1/authorization/check \\',
  '  -H "Authorization: Bearer <access_token>" \\',
  '  -H "Content-Type: application/json" \\',
  '  -d "{\\"tenant_id\\":\\"<租户UUID>\\",\\"permission_code\\":\\"crm.document.read\\",\\"include_data_scope\\":false}"',
].join('\n')

const apiBatchSample = [
  'curl -s http://localhost:8002/api/v1/authorization/check-batch \\',
  '  -H "Authorization: Bearer <access_token>" \\',
  '  -H "Content-Type: application/json" \\',
  '  -d "{\\"tenant_id\\":\\"<租户UUID>\\",\\"permission_codes\\":[\\"crm.document.read\\",\\"crm.document.create\\"]}"',
].join('\n')

const apiVueFrontend = [
  '<script setup lang=\'ts\'>',
  'import { ref } from \'vue\'',
  '',
  'const canCreate = ref(false)',
  '',
  '// token 只应由业务服务端保管；这里仅示意如何读 allowed。',
  'async function loadMenu(token: string, tenantId: string) {',
  '  const res = await fetch(\'http://localhost:8002/api/v1/authorization/check-batch\', {',
  '    method: \'POST\',',
  '    headers: {',
  '      Authorization: `Bearer ${token}`,',
  '      \'Content-Type\': \'application/json\',',
  '    },',
  '    body: JSON.stringify({',
  '      tenant_id: tenantId,',
  '      permission_codes: [\'crm.document.read\', \'crm.document.create\'],',
  '    }),',
  '  })',
  '  if (!res.ok) {',
  '    canCreate.value = false',
  '    return',
  '  }',
  '  const data = await res.json()',
  '  canCreate.value = data.results?.[\'crm.document.create\']?.allowed === true',
  '}',
  '</script>',
  '',
  '<template>',
  '  <form><!-- 业务自己的邮箱密码表单，提交到你的后端去换 token --></form>',
  '  <button v-if="canCreate" type="button">新建文档</button>',
  '</template>',
].join('\n')

export const API_PROJECT_STEPS: GuideStep[] = [
  {
    order: 'B1',
    title: '服务端登录拿 token',
    summary: '用已存在用户调登录接口，access_token 只放业务服务端。',
    items: [
      'POST /api/v1/auth/login，JSON 提交 email 与 password。',
      '不要把 token 下发到浏览器长期存储。',
    ],
    action: null,
    actionLabel: '',
    samples: [
      { label: 'curl', text: apiLoginCurl },
      { label: 'Python', text: apiLoginPython },
    ],
  },
  {
    order: 'B2',
    title: '后续请求带 Bearer',
    summary: '每个受保护业务请求都带上登录拿到的令牌。',
    items: [
      '请求头：Authorization: Bearer <access_token>。',
      'token 过期后重新登录或走 refresh；过期令牌不能当已授权。',
    ],
    action: null,
    actionLabel: '',
    samples: [{ label: 'Header', text: apiBearerSample }],
  },
  {
    order: 'B3',
    title: '单次判权',
    summary: '写操作前调用 check；tenant_id 必须是该用户真实成员租户。',
    items: [
      'POST /api/v1/authorization/check。',
      'allowed 不为 true 时业务必须拒绝，不能靠前端藏按钮。',
      '不能靠请求体冒充别的租户或应用。',
    ],
    action: null,
    actionLabel: '',
    samples: [{ label: 'curl', text: apiCheckSample }],
  },
  {
    order: 'B4',
    title: '批量判权给菜单',
    summary: 'check-batch 只做界面快照，1–32 个码且去重。',
    items: [
      'POST /api/v1/authorization/check-batch，body 带 permission_codes 数组。',
      '创建、删除等写操作仍走单次 check。',
    ],
    action: null,
    actionLabel: '',
    samples: [{ label: 'curl', text: apiBatchSample }],
  },
  {
    order: 'B5',
    title: '前端改造',
    summary: '登录表单留在你的项目；按钮按 allowed 显示。',
    items: [
      '邮箱密码提交到你的后端，由后端调 IAM 换 token。',
      '菜单/按钮用 check-batch 的 results[code].allowed === true 再渲染。',
    ],
    action: null,
    actionLabel: '',
    samples: [{ label: 'Vue', text: apiVueFrontend }],
  },
  {
    order: 'B6',
    title: '失败关闭',
    summary: '不确定时一律拒绝；业务 token 不能打管理接口。',
    items: [
      'allowed !== true、网络超时或 5xx 都视为未授权。',
      '业务用户 token 不能调用 /api/v1/admin/*；管理台需要管理员会话。',
      '本机对照 OpenAPI：http://localhost:8002/docs。',
    ],
    action: null,
    actionLabel: '',
    samples: [],
  },
]
