<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PAGE_PATHS, type PageKey } from '@/router/navigation'
import { ArrowRightOutlined } from '@ant-design/icons-vue'
import CodeSample from './CodeSample.vue'
import { ACTOR_LABELS, CHECKLIST, FACTS, HERO, QUICK_LINKS, SCOPE_NOTE, STEPS } from './guideContent'

const router = useRouter()
const rootRef = ref<HTMLElement | null>(null)
let revealObserver: IntersectionObserver | undefined

function goPage(key: PageKey): void {
  void router.push(PAGE_PATHS[key])
}

// 内容区在壳层内部滚动，观察器挂在实际滚动容器上；进入视口的块加 .revealed 触发上浮渐显。
function findScrollParent(node: HTMLElement): HTMLElement | null {
  let current = node.parentElement
  while (current) {
    const overflowY = window.getComputedStyle(current).overflowY
    if (overflowY === 'auto' || overflowY === 'scroll') return current
    current = current.parentElement
  }
  return null
}

function observeReveals(): void {
  const root = rootRef.value
  if (!root) return
  const targets = root.querySelectorAll('[data-reveal]')
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduceMotion || !('IntersectionObserver' in window)) {
    targets.forEach(target => target.classList.add('revealed'))
    return
  }
  revealObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue
      entry.target.classList.add('revealed')
      revealObserver?.unobserve(entry.target)
    }
  }, { root: findScrollParent(root), rootMargin: '0px 0px -8% 0px', threshold: 0.08 })
  targets.forEach(target => revealObserver?.observe(target))
}

onMounted(() => {
  observeReveals()
})

onUnmounted(() => {
  revealObserver?.disconnect()
})
</script>

<template>
  <div ref="rootRef" class="flex w-full min-w-0 max-w-3xl flex-col gap-10 pb-20">
    <!-- ── 封面：近黑渐变 + 超大编号装饰，整页的「书封」 ───────────────────── -->
    <section
      data-reveal
      class="guide-hero relative overflow-hidden rounded-2xl px-7 py-12 sm:px-10 sm:py-16"
    >
      <!-- 装饰层：右上柔光 + 极淡网格 + 背景大编号，只在小屏以上逐步展开 -->
      <div class="guide-hero-glow pointer-events-none absolute inset-0" aria-hidden="true" />
      <div
        class="pointer-events-none absolute -right-4 -bottom-10 select-none font-mono text-[11rem] leading-none font-bold tracking-tighter text-white/6 sm:text-[15rem]"
        aria-hidden="true"
      >05</div>

      <div class="relative flex flex-col items-start gap-6">
        <p class="text-xs font-medium tracking-[0.22em] text-white/50 uppercase">{{ HERO.eyebrow }}</p>
        <h2 class="max-w-xl text-4xl leading-[1.15] font-bold tracking-tight text-white sm:text-5xl">
          {{ HERO.title }}
        </h2>
        <p class="max-w-xl text-base leading-7 text-white/65">{{ HERO.plain }}</p>
        <div class="flex flex-wrap items-center gap-3 pt-1">
          <button
            type="button"
            class="guide-hero-cta group inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-medium transition hover:bg-zinc-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            @click="goPage('application_workspace')"
          >
            {{ HERO.cta }}
            <ArrowRightOutlined class="text-xs transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
          </button>
          <button
            v-for="link in QUICK_LINKS"
            :key="link.page"
            type="button"
            class="guide-hero-ghost rounded-full border border-white/25 px-4 py-2 text-sm transition hover:border-white/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            @click="goPage(link.page)"
          >{{ link.label }}</button>
        </div>
        <ul class="flex flex-wrap gap-x-5 gap-y-1 pt-2 text-xs text-white/45" aria-label="接入特点">
          <li v-for="item in HERO.meta" :key="item" class="flex items-center gap-1.5">
            <span class="inline-block h-1 w-1 rounded-full bg-white/40" aria-hidden="true" />
            {{ item }}
          </li>
        </ul>
      </div>
    </section>

    <!-- ── 三句话看懂：是什么 / 谁来接 / 怎么用 ───────────────────────────── -->
    <section aria-label="三句话看懂" class="grid grid-cols-1 gap-3 md:grid-cols-3">
      <article
        v-for="(fact, index) in FACTS"
        :key="fact.title"
        data-reveal
        :style="{ transitionDelay: `${index * 70}ms` }"
        class="flex flex-col gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-5 transition-shadow hover:shadow-[var(--shadow-lg)]"
      >
        <span class="text-2xl" aria-hidden="true">{{ fact.icon }}</span>
        <h3 class="text-sm font-semibold text-[var(--color-text-primary)]">{{ fact.title }}</h3>
        <p class="text-sm leading-6 text-[var(--color-text-secondary)]">{{ fact.summary }}</p>
      </article>
    </section>

    <!-- ── 旅程标题 ──────────────────────────────────────────────────────── -->
    <div data-reveal class="flex items-baseline gap-4">
      <h3 class="text-2xl font-bold tracking-tight text-[var(--color-text-primary)]">五步旅程</h3>
      <p class="text-sm text-[var(--color-text-secondary)]">按顺序走完，应用就接好了</p>
    </div>

    <!-- ── 旅程时间线：左侧连线 + emoji 节点；白话在上，契约折叠在下 ─────────── -->
    <ol class="flex flex-col">
      <li
        v-for="(step, stepIndex) in STEPS"
        :key="step.id"
        :id="step.id"
        data-reveal
        class="relative pl-16 sm:pl-20"
      >
        <!-- 连接线：最后一步不画 -->
        <span
          v-if="stepIndex < STEPS.length - 1"
          class="absolute top-14 bottom-0 left-[27px] w-px bg-[var(--color-border)] sm:left-[31px]"
          aria-hidden="true"
        />
        <!-- 节点圆片 -->
        <span
          class="absolute top-0 left-0 flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] text-2xl shadow-[var(--shadow-sm)] sm:h-16 sm:w-16"
          aria-hidden="true"
        >{{ step.icon }}</span>

        <div class="flex flex-col gap-3 pt-1 pb-12">
          <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span class="font-mono text-xs font-semibold tracking-widest text-[var(--color-text-muted)]">{{ step.index }}</span>
            <h4 class="text-lg font-semibold tracking-tight text-[var(--color-text-primary)]">{{ step.title }}</h4>
            <span
              class="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-0.5 text-xs text-[var(--color-text-secondary)]"
            >{{ ACTOR_LABELS[step.actor] }}</span>
          </div>
          <p class="max-w-xl text-[15px] leading-7 text-[var(--color-text-secondary)]">{{ step.plain }}</p>
          <ul class="flex max-w-xl flex-col gap-2">
            <li
              v-for="point in step.points"
              :key="point"
              class="flex items-start gap-2.5 text-sm leading-6 text-[var(--color-text-primary)]"
            >
              <span
                class="mt-[9px] inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-text-muted)]"
                aria-hidden="true"
              />
              {{ point }}
            </li>
          </ul>

          <!-- 技术细节：默认折叠，开发者按需展开；非开发者可整页无视 -->
          <details v-if="step.techItems.length" class="group mt-1 max-w-xl">
            <summary
              class="inline-flex cursor-pointer list-none items-center gap-1.5 text-sm font-medium text-[var(--color-text-secondary)] transition hover:text-[var(--color-text-primary)] [&::-webkit-details-marker]:hidden"
            >
              <span
                class="inline-block text-xs transition-transform group-open:rotate-90"
                aria-hidden="true"
              >▶</span>
              {{ step.techTitle }}
            </summary>
            <div class="mt-3 flex flex-col gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-4">
              <ul class="flex flex-col gap-2">
                <li
                  v-for="item in step.techItems"
                  :key="item"
                  class="flex items-start gap-2.5 font-mono text-xs leading-5 text-[var(--color-text-secondary)]"
                >
                  <span class="mt-[7px] inline-block h-1 w-1 shrink-0 rounded-full bg-[var(--color-text-muted)]" aria-hidden="true" />
                  {{ item }}
                </li>
              </ul>
              <CodeSample
                v-if="step.sample"
                :label="step.sampleLabel"
                :text="step.sample"
              />
            </div>
          </details>
        </div>
      </li>
    </ol>

    <!-- ── 上线前检查清单 ────────────────────────────────────────────────── -->
    <section
      data-reveal
      class="flex flex-col gap-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6 sm:p-8"
      aria-label="上线前检查清单"
    >
      <div class="flex items-center gap-3">
        <span class="text-2xl" aria-hidden="true">✅</span>
        <h3 class="text-lg font-semibold tracking-tight text-[var(--color-text-primary)]">上线前，最后过一遍</h3>
      </div>
      <ul class="flex flex-col gap-3">
        <li
          v-for="item in CHECKLIST"
          :key="item"
          class="flex items-start gap-3 text-sm leading-6 text-[var(--color-text-primary)]"
        >
          <span
            class="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-[var(--color-border-strong)] bg-[var(--color-bg-subtle)] text-xs text-[var(--color-text-secondary)]"
            aria-hidden="true"
          >✓</span>
          {{ item }}
        </li>
      </ul>
    </section>

    <!-- ── 页脚范围说明 ──────────────────────────────────────────────────── -->
    <footer data-reveal class="flex items-start gap-2.5 px-1">
      <span class="mt-[7px] inline-block h-1 w-1 shrink-0 rounded-full bg-[var(--color-text-muted)]" aria-hidden="true" />
      <p class="text-xs leading-5 text-[var(--color-text-muted)]">{{ SCOPE_NOTE }}</p>
    </footer>
  </div>
</template>

<style scoped>
/* Tailwind v4 层叠坑：无层表单 reset（button{color:inherit}）会压过 @layer 内的 color 工具类，
   封面按钮文字色与侧栏折叠按钮同解——用无层 scoped 规则固定（底色恒黑，文字恒白系）。 */
.guide-hero-cta,
.guide-hero-cta:hover {
  color: #18181b;
}

.guide-hero-ghost,
.guide-hero-ghost:hover {
  color: rgba(255, 255, 255, 0.75);
}

.guide-hero-ghost:hover {
  color: #fff;
}

/* 封面底色：恒定近黑（与侧栏同源），双主题下都成立；只能用原生 CSS 表达渐变叠层。 */
.guide-hero {
  background:
    radial-gradient(ellipse 60% 90% at 85% -10%, rgba(255, 255, 255, 0.14), transparent 60%),
    radial-gradient(ellipse 40% 60% at 0% 110%, rgba(255, 255, 255, 0.06), transparent 55%),
    linear-gradient(150deg, var(--color-sider-bg) 20%, #27272a 130%);
  border: 1px solid var(--color-border-strong);
}

/* 极淡网格纹理：给封面加纸面质感。 */
.guide-hero-glow {
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse 90% 100% at 70% 0%, black 30%, transparent 75%);
}

/* 进场动效：未进入视口时下沉隐藏，.revealed 后上浮渐显；尊重系统减动效偏好。 */
[data-reveal] {
  opacity: 0;
  transform: translateY(14px);
  transition: opacity 0.55s ease, transform 0.55s cubic-bezier(0.22, 0.61, 0.36, 1);
}

[data-reveal].revealed {
  opacity: 1;
  transform: none;
}

@media (prefers-reduced-motion: reduce) {
  [data-reveal] {
    opacity: 1;
    transform: none;
    transition: none;
  }
}
</style>
