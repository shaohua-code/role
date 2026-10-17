<script setup lang="ts">
import type { AdminOverview } from '../../shared/services/api'

defineProps<{
  overview: AdminOverview | null
  healthState: string
  loading: boolean
}>()

const emit = defineEmits<{
  navigate: [page: 'applications']
  refresh: []
}>()
</script>

<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">IDENTITY &amp; ACCESS</p>
      <h1>统一身份与权限管理</h1>
      <p class="subtitle">集中管理租户、应用、用户和访问策略。</p>
    </div>
    <a-button type="primary" @click="emit('navigate', 'applications')">管理接入应用</a-button>
  </div>

  <div class="welcome-card">
    <div class="welcome-copy">
      <span class="pill" :class="{ 'service-offline': healthState !== '服务正常' }">
        <span class="status-dot" :class="{ offline: healthState !== '服务正常' }"></span>{{ healthState }}
      </span>
      <h2>让身份统一，<br />让访问规则清晰可控。</h2>
      <p>从一个控制台管理应用接入、用户身份和资源权限，并持续记录关键操作。</p>
    </div>
    <div class="orbit orbit-one"></div>
    <div class="orbit orbit-two"></div>
    <div class="orbit-core">ID</div>
    <div class="welcome-foot">
      <span>当前试点</span><strong>DeerFlow</strong><span class="foot-divider"></span>
      <span>本阶段</span><strong>仅本人数据</strong>
    </div>
  </div>

  <div class="section-heading">
    <div><h2>平台概况</h2><p>当前数据库中的管理数据</p></div>
    <a-button type="link" :loading="loading" @click="emit('refresh')">刷新数据</a-button>
  </div>
  <a-spin :spinning="loading">
    <div class="status-grid">
      <article
        v-for="stat in ([
          ['租户', overview?.tenants ?? '—', '◫', 'violet'],
          ['接入应用', overview?.applications ?? '—', '▣', 'blue'],
          ['平台用户', overview?.users ?? '—', '♙', 'green'],
          ['角色', overview?.roles ?? '—', '⌘', 'amber'],
          ['模型目录', overview?.models ?? '—', '✧', 'violet'],
        ] as [string, number | string, string, string][])"
        :key="stat[0]"
        class="status-card"
      >
        <div class="card-top">
          <span class="card-icon" :class="stat[3]">{{ stat[2] }}</span>
          <span class="tag">实时统计</span>
        </div>
        <h3>{{ stat[0] }}</h3>
        <div class="metric number">{{ stat[1] }} <small>条记录</small></div>
      </article>
    </div>
  </a-spin>

  <div class="section-heading"><div><h2>管理能力</h2><p>选择左侧菜单进入数据管理</p></div></div>
  <div class="roadmap">
    <article
      v-for="item in [
        ['身份目录', '租户、用户和多租户成员关系'],
        ['访问控制', '按资源与 Scope 维护角色授权'],
        ['应用品牌', '版本化配置各系统登录页主题'],
      ]"
      :key="item[0]"
      class="roadmap-item"
    >
      <span class="step">✓</span>
      <div><span class="roadmap-state">已提供管理 API</span><h3>{{ item[0] }}</h3><p>{{ item[1] }}</p></div>
    </article>
  </div>
</template>
