/**
 * Markdown 渲染底座（模型测试台对话正文专用）。
 *
 * 成熟依赖方案（兼容主流模型输出）：
 * - markdown-it v15：GFM 表格/分隔线/引用/嵌套列表/自动链接（linkify）/单换行（breaks），
 *   html:false 原始 HTML 一律转义，无注入面；
 * - highlight.js core 按需注册 15 个高频语言（控制包体），未知语言安全降级纯转义；
 * - GFM 任务列表（- [ ] / - [x]）以零依赖 renderer 规则实现；
 * - 链接强制 target=_blank + rel=noopener；代码块带语言标签与复制按钮（data-md-copy
 *   由消息区 click 事件委托处理，契约与旧版一致）；
 * - 流式生成中 options.cursor=true 时在最后文本块尾随闪烁光标。
 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/core'
import 'highlight.js/styles/github-dark.css'

import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import go from 'highlight.js/lib/languages/go'
import rust from 'highlight.js/lib/languages/rust'
import dockerfile from 'highlight.js/lib/languages/dockerfile'
import ini from 'highlight.js/lib/languages/ini'
import markdownLang from 'highlight.js/lib/languages/markdown'
import plaintext from 'highlight.js/lib/languages/plaintext'

// 主流模型输出高频语言子集；未覆盖语言走纯转义降级，不影响阅读。
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('json', json)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('java', java)
hljs.registerLanguage('go', go)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('dockerfile', dockerfile)
hljs.registerLanguage('docker', dockerfile)
hljs.registerLanguage('ini', ini)
hljs.registerLanguage('toml', ini)
hljs.registerLanguage('markdown', markdownLang)
hljs.registerLanguage('md', markdownLang)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('text', plaintext)

/** 流式光标片段（插在最后一个段落/列表项闭合标签前）。 */
const CURSOR_HTML =
  '<span data-md-cursor aria-hidden="true" class="ml-0.5 inline-block h-[1em] w-[7px] translate-y-[2px] animate-[tech-blink_1.1s_steps(1)_infinite] rounded-[1px] bg-[var(--color-tech-accent)]"></span>'

const md = new MarkdownIt({
  // 安全红线：模型输出中的原始 HTML 全部转义，只渲染 Markdown 结构。
  html: false,
  // LLM 中文输出习惯单换行，按软换行呈现（与旧手写渲染器行为一致）。
  breaks: true,
  // 裸 URL 自动识别为链接（GPT/Claude/DeepSeek 常见输出）。
  linkify: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
      } catch {
        // 落到下方纯转义
      }
    }
    return md.utils.escapeHtml(code)
  },
})

// 链接安全：统一新窗口打开并隔离来源。
const defaultLinkOpen = md.renderer.rules.link_open ??
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self): string => {
  const token = tokens[idx]
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

// GFM 任务列表：- [ ] 未完成 / - [x] 已完成（零依赖 renderer 规则）。
md.renderer.rules.list_item_open = (tokens, idx, options, env, self): string => {
  const inline = tokens.slice(idx + 1).find(token => token.type === 'inline')
  if (inline && /^\[[ xX]\]/.test(inline.content)) {
    const checked = /^\[[xX]\]/.test(inline.content)
    // content 与首个 text child 同步去掉 [ ] 前缀，避免渲染残留。
    inline.content = inline.content.replace(/^\[[ xX]\]\s?/, '')
    const firstText = inline.children?.find(child => child.type === 'text')
    if (firstText) firstText.content = firstText.content.replace(/^\[[ xX]\]\s?/, '')
    const box = `<span aria-hidden="true" class="md-task-checkbox${checked ? ' is-checked' : ''}">${checked ? '✓' : ''}</span>`
    return `<li class="md-task-list-item">${box}`
  }
  return self.renderToken(tokens, idx, options)
}

// fenced 代码块外壳：深色卡片 + 语言标签 + 复制按钮（hljs 高亮由 highlight 选项注入）。
md.renderer.rules.fence = (tokens, idx, options): string => {
  const token = tokens[idx]
  const lang = token.info ? token.info.trim().split(/\s+/)[0] : ''
  const highlighted = options.highlight?.(token.content, lang, '') ?? md.utils.escapeHtml(token.content)
  return [
    '<div data-md-block class="my-3 overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-sider-bg)]">',
    '<div class="flex items-center justify-between border-b border-white/10 px-3 py-1.5">',
    `<span class="font-mono text-[10px] uppercase tracking-wider text-zinc-500">${md.utils.escapeHtml(lang) || 'code'}</span>`,
    '<button type="button" data-md-copy class="cursor-pointer rounded px-1.5 py-0.5 text-[11px] leading-none text-zinc-400 transition-colors hover:bg-white/10 hover:text-zinc-100">复制</button>',
    '</div>',
    '<pre class="overflow-x-auto p-3 text-[12.5px] leading-relaxed"><code class="hljs font-mono text-zinc-100">',
    highlighted,
    '</code></pre></div>',
  ].join('')
}

/**
 * 渲染 Markdown 为安全 HTML（消费方以 v-html 渲染，容器需挂 MD_BODY_CLASS 排版类）。
 * options.cursor=true 时在最后文本块追加流式光标。
 */
export function renderMarkdown(source: string, options?: { cursor?: boolean }): string {
  const html = md.render(source ?? '')
  if (!options?.cursor) return html
  // 光标锚定最后一个段落或列表项；纯代码块结尾时不插（代码光标无意义）。
  const anchor = Math.max(html.lastIndexOf('</p>'), html.lastIndexOf('</li>'))
  if (anchor < 0) return html
  return html.slice(0, anchor) + CURSOR_HTML + html.slice(anchor)
}

/**
 * 消息正文容器排版类：Tailwind 后代任意值覆盖 markdown-it 输出的标准标签。
 * 代码块内部配色由 github-dark 主题与 fence 外壳类承担，不在此重复定义。
 */
export const MD_BODY_CLASS = [
  'text-[14px] leading-7 text-[var(--color-text-primary)]',
  '[&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0',
  '[&_h1]:mb-2 [&_h1]:mt-5 [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:leading-snug',
  '[&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:leading-snug',
  '[&_h3]:mb-1.5 [&_h3]:mt-3 [&_h3]:text-[15px] [&_h3]:font-semibold',
  '[&_h4]:mb-1.5 [&_h4]:mt-3 [&_h4]:text-sm [&_h4]:font-semibold',
  '[&_ul]:my-2 [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5',
  '[&_ol]:my-2 [&_ol]:list-decimal [&_ol]:space-y-1 [&_ol]:pl-5',
  '[&_li]:leading-7',
  '[&_strong]:font-semibold [&_strong]:text-[var(--color-text-primary)]',
  '[&_em]:italic',
  '[&_del]:opacity-70',
  '[&_a]:font-medium [&_a]:text-[var(--color-tech-accent)] [&_a]:underline [&_a]:underline-offset-2',
  '[&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-[var(--color-border-strong)] [&_blockquote]:pl-3 [&_blockquote]:text-[var(--color-text-secondary)]',
  '[&_hr]:my-4 [&_hr]:border-0 [&_hr]:border-t [&_hr]:border-[var(--color-border)]',
  '[&_code]:rounded [&_code]:border [&_code]:border-[var(--color-border)] [&_code]:bg-[var(--color-bg-subtle)] [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.85em] [&_code]:text-[var(--color-tech-accent)]',
  // pre 内代码不受行内码样式影响（fence 已自带 .hljs 配色）。
  '[&_pre_code]:border-0 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-inherit',
  '[&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_table]:text-[13px]',
  '[&_th]:border-b [&_th]:border-[var(--color-border-strong)] [&_th]:bg-[var(--color-bg-subtle)] [&_th]:px-3 [&_th]:py-1.5 [&_th]:text-left [&_th]:font-medium',
  '[&_td]:border-b [&_td]:border-[var(--color-border)] [&_td]:px-3 [&_td]:py-1.5 [&_td]:align-top',
  // 任务列表：去默认圆点，勾选框用主题令牌绘制。
  '[&_.md-task-list-item]:relative [&_.md-task-list-item]:list-none [&_.md-task-list-item]:pl-6',
  '[&_.md-task-checkbox]:absolute [&_.md-task-checkbox]:left-0 [&_.md-task-checkbox]:top-[5px] [&_.md-task-checkbox]:flex [&_.md-task-checkbox]:h-3.5 [&_.md-task-checkbox]:w-3.5 [&_.md-task-checkbox]:items-center [&_.md-task-checkbox]:justify-center [&_.md-task-checkbox]:rounded-[3px] [&_.md-task-checkbox]:border [&_.md-task-checkbox]:border-[var(--color-border-strong)] [&_.md-task-checkbox]:text-[9px] [&_.md-task-checkbox]:text-[var(--color-bg-elevated)]',
  '[&_.md-task-checkbox.is-checked]:border-[var(--color-tech-accent)] [&_.md-task-checkbox]:bg-[var(--color-tech-accent)]',
].join(' ')
