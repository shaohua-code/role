<script setup lang="ts">
import { useRouter } from 'vue-router'
import { PAGE_PATHS } from '../../app/navigation'

defineProps<{
  active: boolean
}>()

const router = useRouter()

// 从接入页一键跳到管理台已有能力，避免复制整份运维文档。
function goAdminPage(key: keyof typeof PAGE_PATHS): void {
  void router.push(PAGE_PATHS[key])
}

const integrationSteps = [
  {
    order: '1',
    title: '登记应用',
    body: '平台管理员在「应用管理」创建 OAuth 应用：绑定 tenant、填写 1–20 个精确 HTTPS 回调、记录 client_id；Client Secret 只在创建或轮换时回显一次，立即写入服务端密钥库。',
    action: 'applications' as const,
    actionLabel: '打开应用管理',
  },
  {
    order: '2',
    title: '接入 OIDC',
    body: '业务后端使用 sdk/python 或 sdk/typescript 的 OIDC 客户端：Discovery、授权码 + PKCE S256、state/nonce 校验、RS256 验签；会话与 refresh 只存服务端。浏览器只跳 /auth/login，不持有 client secret。',
    action: null,
    actionLabel: '',
  },
  {
    order: '3',
    title: '声明权限',
    body: '在「权限目录」登记稳定权限码（建议 `<应用>.<资源>.<动作>`，如 deerflow.thread.read）；停用码不能新增 grant。业务 handler 逐次在线判权，不把 IAM /auth/me 当 permissions 快照。',
    action: 'permissions' as const,
    actionLabel: '打开权限目录',
  },
  {
    order: '4',
    title: '角色分配',
    body: '在「角色管理」创建普通/管理员角色并绑定权限；通过邀请或成员关系授予用户。新项目默认 owner-only：登记应用不会自动获得管理员或跨用户数据范围。',
    action: 'roles' as const,
    actionLabel: '打开角色管理',
  },
  {
    order: '5',
    title: '验收',
    body: '至少覆盖：登录成功、缺 grant 拒绝、跨用户 resource_id 拒绝、撤权后在线拒绝、IAM 超时/503 失败关闭、refresh 与本地登出。当前唯一正式试点是 DeerFlow，其它产品须在其端到端验收后再评审。',
    action: 'authorization_simulation' as const,
    actionLabel: '打开授权模拟',
  },
]

const inputChecklist = [
  '目标 tenant（组织型或 consumer）与 application 名称、client_id',
  '精确 callback / logout redirect（与 IAM 登记完全一致，含 scheme 与 path）',
  'IAM API 基址与 issuer（常规部署可与 API origin 相同；分域时显式配置，禁止猜测）',
  '权限码命名空间清单（逐条登记，短别名须映射到稳定 code）',
  '`(issuer, sub) → 业务 local user_id` 映射策略（禁止凭邮箱静默合并）',
  '服务端 secret / vault key / Provider key 注入方式（Secret Manager 或受保护 env，不进浏览器）',
  'DeerFlow 试点：36 项 permission map、模型 UUID 级 grant、工具按注册名授权（见架构文档第 5 节）',
]

const sdkEntries = [
  {
    lang: 'Python',
    path: 'sdk/python/iam_authorization.py、iam_oidc.py',
    authz: 'IamAuthorizationClient.check/require，默认 timeout_seconds=3.0',
    oidc: 'IamOIDCClient（Discovery、code exchange、refresh rotation）',
    failClosed: '超时/网络 → AuthorizationServiceError(503)；拒绝保留 IAM 状态码',
  },
  {
    lang: 'TypeScript',
    path: 'sdk/typescript/src/index.ts（IamAuthorizationClient、IamOIDCClient）',
    authz: '默认 3000ms，构造函数第三参可调正整数毫秒',
    oidc: 'OIDC 单请求默认 5000ms；授权与读 body 共享 AbortController 截止',
    failClosed: '超时/网络 → AuthorizationServiceError(503)；畸形响应 → 502',
  },
]

const docAnchors = [
  { label: '§3 多项目简单接入方案', hint: '四步压缩流程、业务 /auth/me 设计目标、验收清单' },
  { label: '§4 当前 API 与服务端 SDK 契约', hint: 'authorization/check、OIDC 端点、管理 API 边界' },
  { label: '§4.2 在线授权与数据范围', hint: 'include_data_scope、owner/self 与本地 user_id 求交' },
  { label: '§5 DeerFlow 映射', hint: '唯一试点 permission map、model:use、工具 grant' },
]
</script>

<template>
  <div class="flex w-full max-w-5xl flex-col gap-6 px-1 pb-8 sm:px-0">
    <header class="flex flex-col gap-2 border-b border-slate-200/80 pb-5 dark:border-slate-700/80">
      <p class="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600 dark:text-violet-300">PROJECT ONBOARDING</p>
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-50 sm:text-3xl">新项目接入</h1>
      <p class="max-w-3xl text-sm leading-relaxed text-slate-600 dark:text-slate-300">
        按平台已实现的 OIDC 与在线授权契约接入业务系统。SDK 已提供登录路由插件（mount_oidc_auth / mountOidcAuth）、FastAPI/Express 授权适配层、批量判定与权限清单同步工具、CRUD 模板项目（examples/iam-crud-fastapi）；权限清单向导仍属后续目标。业务侧仍须自行完成会话存储与 owner 过滤。
      </p>
    </header>

    <section class="rounded-2xl border border-amber-200/80 bg-amber-50/90 p-4 dark:border-amber-500/30 dark:bg-amber-950/40">
      <h2 class="text-sm font-semibold text-amber-900 dark:text-amber-100">密钥与浏览器边界</h2>
      <ul class="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-amber-950/90 dark:text-amber-50/90">
        <li>禁止在浏览器、前端构建产物、Prompt、日志或审计详情中放置 Client Secret、模型服务 key、Provider 凭证或长期 refresh token。</li>
        <li>Client Secret 创建/轮换仅在管理台回显一次；业务侧须同步更新服务端配置，无重叠宽限期。</li>
        <li>界面权限提示仅供交互展示；每个受保护 API 必须在服务端逐次调用 IAM 或等价判权。</li>
      </ul>
    </section>

    <section class="flex flex-col gap-4">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-50">推荐接入顺序</h2>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <article
          v-for="step in integrationSteps"
          :key="step.order"
          class="flex flex-col gap-3 rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-sm dark:border-slate-700/80 dark:bg-slate-900/50"
        >
          <div class="flex items-center gap-3">
            <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-violet-600 text-sm font-semibold text-white">{{ step.order }}</span>
            <h3 class="text-base font-semibold text-slate-900 dark:text-slate-50">{{ step.title }}</h3>
          </div>
          <p class="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{{ step.body }}</p>
          <button
            v-if="step.action"
            type="button"
            class="mt-auto w-fit rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-violet-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-400"
            @click="goAdminPage(step.action)"
          >
            {{ step.actionLabel }}
          </button>
        </article>
      </div>
    </section>

    <section class="rounded-2xl border border-slate-200/80 bg-slate-50/80 p-4 dark:border-slate-700/80 dark:bg-slate-900/40">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-50">接入前输入清单</h2>
      <ul class="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
        <li v-for="item in inputChecklist" :key="item">{{ item }}</li>
      </ul>
      <p class="mt-4 text-xs text-slate-500 dark:text-slate-400">
        仓库根目录《docs/技术架构与接入.md》§3 表格列出的「接入方需要提供 / 当前实现边界」与本清单一致；DeerFlow 为当前唯一业务试点，AI Resume / Knowledge Base 旧接入已清理。
      </p>
    </section>

    <section class="flex flex-col gap-4">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-50">服务端 SDK（3 秒失败关闭）</h2>
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <article
          v-for="sdk in sdkEntries"
          :key="sdk.lang"
          class="rounded-2xl border border-slate-200/80 bg-white/80 p-4 dark:border-slate-700/80 dark:bg-slate-900/50"
        >
          <h3 class="text-base font-semibold text-slate-900 dark:text-slate-50">{{ sdk.lang }}</h3>
          <dl class="mt-3 space-y-2 text-sm text-slate-600 dark:text-slate-300">
            <div><dt class="font-medium text-slate-800 dark:text-slate-100">入口</dt><dd class="mt-0.5 font-mono text-xs break-all">{{ sdk.path }}</dd></div>
            <div><dt class="font-medium text-slate-800 dark:text-slate-100">在线授权</dt><dd class="mt-0.5">{{ sdk.authz }}</dd></div>
            <div><dt class="font-medium text-slate-800 dark:text-slate-100">OIDC</dt><dd class="mt-0.5">{{ sdk.oidc }}</dd></div>
            <div><dt class="font-medium text-slate-800 dark:text-slate-100">失败关闭</dt><dd class="mt-0.5">{{ sdk.failClosed }}</dd></div>
          </dl>
        </article>
      </div>
      <p class="text-sm text-slate-600 dark:text-slate-300">
        调用 <code class="rounded bg-slate-200/80 px-1 py-0.5 text-xs dark:bg-slate-800">POST /api/v1/authorization/check</code> 时使用用户 OIDC access token（RS256），tenant 必须等于 token 内 tenant_id；管理台 API 仅接受 IAM 管理会话，不得用 OIDC 客户端 token 冒充平台管理员。
      </p>
    </section>

    <section class="rounded-2xl border border-violet-200/70 bg-violet-50/60 p-4 dark:border-violet-500/30 dark:bg-violet-950/30">
      <h2 class="text-lg font-semibold text-violet-950 dark:text-violet-50">DeerFlow 已确认决策（试点）</h2>
      <ul class="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-violet-950/90 dark:text-violet-50/90">
        <li>首阶段项目/线程/运行/文档等资源 <strong class="font-semibold">owner-only</strong>；IAM owner/self 与业务库 <code class="rounded bg-violet-200/60 px-1 text-xs dark:bg-violet-900/60">user_id</code> 条件须同时成立。</li>
        <li>稳定身份为 <code class="rounded bg-violet-200/60 px-1 text-xs dark:bg-violet-900/60">(issuer, sub)</code>；首登只建普通用户，管理权限仅 IAM 显式 grant。</li>
        <li>DeerFlow <code class="rounded bg-violet-200/60 px-1 text-xs dark:bg-violet-900/60">/auth/logout</code> 只清理本地 session/vault，本阶段不向 issuer 发送 access/refresh token。</li>
        <li>公开注册与模型配额 enforcement 默认关闭；无 grant、IAM 超时、身份/应用/租户不匹配一律拒绝。</li>
      </ul>
    </section>

    <section class="flex flex-col gap-3">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-slate-50">详细文档（仓库内）</h2>
      <p class="text-sm text-slate-600 dark:text-slate-300">
        管理台无法直接打开 Markdown 文件时，请在 IDE 或文档站点查看仓库根目录
        <span class="font-mono text-xs">docs/技术架构与接入.md</span> 与
        <span class="font-mono text-xs">docs/后续项目对接手册.md</span>。
      </p>
      <ul class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <li
          v-for="doc in docAnchors"
          :key="doc.label"
          class="rounded-xl border border-slate-200/80 bg-white/70 px-3 py-2 text-sm dark:border-slate-700/80 dark:bg-slate-900/40"
        >
          <span class="font-medium text-slate-900 dark:text-slate-50">{{ doc.label }}</span>
          <span class="mt-1 block text-xs text-slate-500 dark:text-slate-400">{{ doc.hint }}</span>
        </li>
      </ul>
      <p class="text-xs text-slate-500 dark:text-slate-400">
        PRD §9 接入规范与 §5.1 新应用接入流程描述产品侧验收要求；F02 简单接入框架插件仍待 DeerFlow 试点端到端证据。
      </p>
    </section>
  </div>
</template>
