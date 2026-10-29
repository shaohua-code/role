import type { PageKey } from '@/router/navigation'

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
    title: '创建应用组织（租户）',
    summary: '在本平台建一个租户，记下 UUID。界面名称用中文，标识可保留英文。',
    items: [
      '打开「租户管理」，新建租户：名称填中文（如「演示应用组织」），类型选「组织/企业租户」。',
      'slug / 类型枚举值可保留英文标识；列表与表单展示名一律中文。',
      '面向 C 端用户时选「ToC 消费」租户，不要与组织租户混用角色。',
    ],
    action: 'tenants',
    actionLabel: '去租户管理',
    samples: [],
  },
  {
    order: '2',
    title: '登记应用',
    summary: '登记应用；页面直连登录不依赖 OIDC 回调，仍建议填好回调以便日后扩展。',
    items: [
      '打开「应用管理」，选择上一步租户，填写应用中文名称（如「演示业务应用」）与稳定 client_id。',
      '页面直连 IAM 登录（方案 A）用邮箱密码调平台 /auth/login，不经业务后端 SSO 包装。',
      '若仍保留 OIDC，回调须含 http/https、host 与 path，并与业务环境变量字节级相同。',
      'Client Secret 只在创建或轮换时显示一次，写入业务服务端密钥库。',
    ],
    action: 'applications',
    actionLabel: '去应用管理',
    samples: [],
  },
  {
    order: '3',
    title: '登记权限编码',
    summary: '登记稳定权限编码；界面展示名用中文，code 保持英文点分标识。',
    items: [
      '打开「权限编码」，与 SDK 清单同步到对应应用命名空间。',
      '编码格式：{项目}.{资源}.{动作}，例如 demo.document.read；说明列写中文（如「读取文档」）。',
      '业务码默认 surface=business 且 requires_data_scope=true（绿场 2.x）。',
      '停用只改状态，不要删除历史授权过的码。',
    ],
    action: 'permissions',
    actionLabel: '去权限编码',
    samples: [],
  },
  {
    order: '4',
    title: '配置角色并授权',
    summary: '创建普通角色、挂上权限编码；只能看自己数据的配 self。',
    items: [
      '打开「角色管理」，在该租户下创建角色：名称用中文（如「文档读者」），标识可保留英文 key。',
      '把上一步的权限编码赋给该角色。',
      '业务行只能看自己的：为对应权限编码配置 RoleDataScope=self（缺省会导致 check 失败）。',
      '创建应用时系统会自动生成「应用管理员」「应用成员」模板，勿直接当业务自定义角色。',
    ],
    action: 'roles',
    actionLabel: '打开角色管理',
    samples: [],
  },
  {
    order: '5',
    title: '准备可登录用户',
    summary: '账号必须在 IAM 中，并绑定到该租户的一个或多个角色；权限码按角色并集生效。',
    items: [
      '打开「用户管理」或「成员邀请」，确保账号属于该租户并挂上角色。',
      '没有租户角色的用户登录后无法通过业务鉴权。',
    ],
    action: 'invitations',
    actionLabel: '打开成员邀请',
    samples: [],
  },
]

const loginEnvSample = [
  '# 页面直连 IAM：浏览器调平台登录接口，不要再包一层业务 /auth/login OIDC',
  'IAM_API_URL=http://localhost:8002',
  'IAM_APPLICATION_ID=<应用UUID>',
  '# 以下仅在仍使用 OIDC 扩展时需要；方案 A 密码登录可不配 secret',
  '# IAM_CLIENT_ID=YOUR_CLIENT_ID',
  '# IAM_CLIENT_SECRET=<创建应用时仅显示一次>',
].join('\n')

const loginCurlSample = [
  '# 1) 页面登录：直接 POST 权限管理平台',
  'curl -sS -X POST "$IAM_API_URL/api/v1/auth/login" \\',
  '  -H "Content-Type: application/json" \\',
  '  -d \'{"email":"demo@example.com","password":"<密码>"}\'',
  '',
  '# 响应含 access_token；再拉身份 + 角色 + 权限编码',
  'curl -sS "$IAM_API_URL/api/v1/auth/me" \\',
  '  -H "Authorization: Bearer $ACCESS_TOKEN"',
].join('\n')

const loginVueFrontend = [
  "<script setup lang='ts'>",
  "import { ref } from 'vue'",
  '',
  "const IAM_API = import.meta.env.VITE_IAM_API_URL || 'http://localhost:8002'",
  'const email = ref(\'\')',
  'const password = ref(\'\')',
  'const me = ref<{ display_name?: string; roles?: { name: string; key: string }[]; capabilities?: { permission_codes?: string[] } } | null>(null)',
  'const error = ref(\'\')',
  '',
  '// 浏览器直连平台登录接口，不经业务后端 SSO / OIDC 包装',
  'async function login() {',
  '  error.value = \'\'',
  '  const res = await fetch(`${IAM_API}/api/v1/auth/login`, {',
  '    method: \'POST\',',
  '    headers: { \'Content-Type\': \'application/json\' },',
  '    credentials: \'include\',',
  '    body: JSON.stringify({ email: email.value, password: password.value }),',
  '  })',
  '  if (!res.ok) { error.value = \'登录失败\'; return }',
  '  const session = await res.json() as { access_token: string }',
  '  sessionStorage.setItem(\'iam-access-token\', session.access_token)',
  '  const meRes = await fetch(`${IAM_API}/api/v1/auth/me`, {',
  '    headers: { Authorization: `Bearer ${session.access_token}` },',
  '    credentials: \'include\',',
  '  })',
  '  me.value = meRes.ok ? await meRes.json() : null',
  '}',
  '</script>',
  '',
  '<template>',
  '  <form v-if="!me" @submit.prevent="login">',
  '    <input v-model="email" type="email" placeholder="邮箱" required />',
  '    <input v-model="password" type="password" placeholder="密码" required />',
  '    <button type="submit">登录</button>',
  '    <p v-if="error">{{ error }}</p>',
  '  </form>',
  '  <div v-else>',
  '    <p>已登录 {{ me.display_name }}</p>',
  '    <p>角色：{{ (me.roles || []).map(r => r.name).join(\'、\') }}</p>',
  '    <p>权限编码：{{ (me.capabilities?.permission_codes || []).join(\'、\') }}</p>',
  '  </div>',
  '</template>',
].join('\n')

const loginReactFrontend = [
  '// 浏览器直连权限管理平台登录，不经业务 /api/v1/auth/oauth 或 login/local 包装',
  'const IAM_API = process.env.NEXT_PUBLIC_IAM_API_URL || \'http://localhost:8002\'',
  '',
  'async function login(email: string, password: string) {',
  '  const res = await fetch(`${IAM_API}/api/v1/auth/login`, {',
  '    method: \'POST\',',
  '    headers: { \'Content-Type\': \'application/json\' },',
  '    credentials: \'include\',',
  '    body: JSON.stringify({ email, password }),',
  '  })',
  '  if (!res.ok) throw new Error(\'登录失败\')',
  '  const { access_token } = await res.json()',
  '  sessionStorage.setItem(\'iam-access-token\', access_token)',
  '  const me = await fetch(`${IAM_API}/api/v1/auth/me`, {',
  '    headers: { Authorization: `Bearer ${access_token}` },',
  '    credentials: \'include\',',
  '  }).then(r => r.json())',
  '  return me // { display_name, roles:[{name,key}], capabilities }',
  '}',
].join('\n')

const loginPermissionSample = [
  'from iam_authorization import IamAuthorizationClient',
  'from iam_fastapi import IAMFastAPI',
  '',
  '# 权限编码：key 英文，展示名在管理台用中文（如「读取文档」）',
  'PERMISSION_MAP = {',
  "    'document.read': 'demo.document.read',  # 展示名：读取文档",
  '}',
  '',
  'iam = IAMFastAPI(',
  '    authorization_client=IamAuthorizationClient(api_base_url=os.environ["IAM_API_URL"]),',
  '    permission_map=PERMISSION_MAP,',
  '    application_id=os.environ["IAM_APPLICATION_ID"],',
  ')',
  '',
  '@app.get("/documents")',
  'def list_documents(decision=Depends(iam.require_permission("document.read", owner_only=True))):',
  '    # 入场可先 require_roles；细粒度仍可用权限编码 + data_scope',
  '    return store.list_for(decision)',
].join('\n')

export const LOGIN_PROJECT_STEPS: GuideStep[] = [
  {
    order: 'A1',
    title: '写入环境变量',
    summary: '业务前端需要知道 IAM API 地址；secret 不要进浏览器。',
    items: [
      '从应用管理复制应用 UUID；API 地址本地一般为 http://localhost:8002。',
      '前端只配 IAM_API_URL（或 VITE_/NEXT_PUBLIC_ 前缀）；client_secret 仅留服务端。',
      '本页下方「试用直连登录」可对照同一套接口。',
    ],
    action: 'applications',
    actionLabel: '看应用管理',
    samples: [{ label: '.env', text: loginEnvSample }],
  },
  {
    order: 'A2',
    title: '页面直连平台登录接口',
    summary: '浏览器 POST /api/v1/auth/login，不要跳业务后端 OIDC/SSO 包装。',
    items: [
      '请求体：{ email, password }；成功返回 access_token。',
      '禁止再挂 mount_oidc_auth / 业务 /auth/login 只做跳转包装作为登录入口。',
      '跨域时 IAM CORS 须包含业务前端源（如 http://localhost:3000），并 credentials: include。',
    ],
    action: null,
    actionLabel: '',
    samples: [
      { label: 'curl', text: loginCurlSample },
      { label: 'Vue', text: loginVueFrontend },
      { label: 'React', text: loginReactFrontend },
    ],
  },
  {
    order: 'A3',
    title: '登录后拉 me / 权限编码',
    summary: '用 Bearer access_token 调 GET /auth/me，前端按权限编码裁 UI。',
    items: [
      'me 含 roles（角色中文名 + key）与 capabilities（权限编码列表）。',
      '前端只信码做菜单/按钮；后端安全边界仍是角色。',
      '业务会话若还需本站 Cookie，可用已拿到的 IAM token 在服务端建本地会话，但登录入口必须是平台 /auth/login。',
    ],
    action: null,
    actionLabel: '',
    samples: [{ label: 'Vue', text: loginVueFrontend }],
  },
  {
    order: 'A4',
    title: '后端按角色 / 权限编码护栏',
    summary: '写接口用角色门禁；敏感资源可再 check 权限编码。',
    items: [
      'permission_map 别名必须登记全名；未登记别名构建期失败。',
      'owner_only 要求角色数据范围为 self，否则 SDK 403。',
      '列表查询用返回的 data_scope，再 AND 租户过滤。',
    ],
    action: 'roles',
    actionLabel: '去配角色数据范围',
    samples: [{ label: 'Python', text: loginPermissionSample }],
  },
]

const apiCurlCheck = [
  'curl -sS -X POST "$IAM_API_URL/api/v1/authorization/check" \\',
  '  -H "Authorization: Bearer $ACCESS_TOKEN" \\',
  '  -H "Content-Type: application/json" \\',
  '  -d "{\\"tenant_id\\":\\"<租户UUID>\\",\\"application_id\\":\\"<应用UUID>\\",\\"permission_code\\":\\"demo.document.read\\"}"',
  '',
  '# 权限编码 demo.document.read 在管理台说明应为中文「读取文档」',
  '# SDK 2.x：不要再传 include_data_scope=false 当业务默认。',
].join('\n')

const apiPythonCheck = [
  'from iam_authorization import IamAuthorizationClient',
  '',
  'client = IamAuthorizationClient(api_base_url=os.environ["IAM_API_URL"])',
  'decision = client.require(',
  '    token=access_token,',
  '    tenant_id=tenant_id,',
  '    permission_code="demo.document.read",  # 展示名：读取文档',
  '    application_id=application_id,',
  ')',
  'scope = decision.data_scope  # mode=any_of + constraints',
].join('\n')

const apiSyncL2 = [
  'from iam_permission_sync import IamAdminClient, sync_permission_manifest',
  '',
  '# L2：同步到应用命名空间；清单里 code 英文，description 用中文',
  'client = IamAdminClient(',
  '    api_base_url=os.environ["IAM_API_URL"],',
  '    application_id=os.environ["IAM_APPLICATION_ID"],',
  ')',
  'report = sync_permission_manifest(',
  '    [{"code": "demo.document.read", "resource_type": "document", "scope": "read", "description": "读取文档"}],',
  '    client=client,',
  '    management_token=app_admin_access_token,',
  ')',
].join('\n')

export const API_PROJECT_STEPS: GuideStep[] = [
  {
    order: 'B1',
    title: '在线鉴权 check',
    summary: '业务端持用户 access token 调 IAM；业务权限必须带 data_scope。',
    items: [
      '使用 POST /api/v1/authorization/check（或 SDK require）。',
      '不要默认传 include_data_scope=false。',
      '缺 RoleDataScope 时判定失败（data_scope_policy_missing / SDK 403/502）。',
    ],
    action: null,
    actionLabel: '',
    samples: [
      { label: 'curl', text: apiCurlCheck },
      { label: 'Python', text: apiPythonCheck },
    ],
  },
  {
    order: 'B2',
    title: '权限编码清单同步（可选）',
    summary: 'CI 里用 SDK 幂等登记业务码；说明字段写中文。',
    items: [
      'L1：IamAdminClient() 调 /admin/permissions。',
      'L2：传入 application_id 调 applications/{id}/permissions。',
      '完整流程见 examples/iam-crud-fastapi/provision.py。',
    ],
    action: 'permissions',
    actionLabel: '看权限编码',
    samples: [{ label: 'Python L2', text: apiSyncL2 }],
  },
]

export function stepsFor(path: IntegrationPath): GuideStep[] {
  return path === 'login' ? LOGIN_PROJECT_STEPS : API_PROJECT_STEPS
}
