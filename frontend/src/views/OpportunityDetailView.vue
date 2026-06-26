<template>
  <div ref="pageRef" class="opp-detail">
    <!-- Hero -->
    <div class="hero">
      <div class="hero-orbs">
        <div class="orb orb-1"></div>
        <div class="orb orb-2"></div>
        <div class="orb orb-3"></div>
      </div>
      <div class="hero-content">
        <router-link to="/opportunities" class="back-link">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          返回机会列表
        </router-link>
        <div v-if="loading" class="hero-loading">
          <div class="spinner"></div>
          <span>加载机会...</span>
        </div>
        <template v-else-if="opp">
          <h1 class="detail-title">{{ opp.title }}</h1>
          <div class="detail-meta">
            <span class="meta-tag">{{ opp.keyword }}</span>
            <span class="meta-dot">·</span>
            <span>{{ opp.status }}</span>
            <span class="meta-dot">·</span>
            <span>{{ opp.created_at }}</span>
          </div>
        </template>
      </div>
    </div>

    <!-- Error / Empty States -->
    <div v-if="error" class="error-banner glass-card">
      <span>{{ error }}</span>
      <button class="retry-btn" @click="fetchAll">重试</button>
    </div>
    <div v-if="!loading && !error && !opp" class="empty-state glass-card">
      机会未找到。<router-link to="/opportunities">返回列表</router-link>
    </div>

    <template v-if="opp">
      <!-- Tabs -->
      <div class="tabs glass-card" data-reveal="up">
        <button :class="{ active: tab === 'overview' }" @click="tab = 'overview'">概览</button>
        <button :class="{ active: tab === 'links' }" @click="tab = 'links'">关联对象</button>
      </div>

      <!-- Tab: Overview -->
      <div v-if="tab === 'overview'" class="tab-content">
        <!-- Score Section -->
        <div class="score-section glass-card" data-reveal="up">
          <div class="score-ring-wrapper">
            <div class="score-ring" :style="{ '--pct': opp.scores.overall }">
              <span class="score-num">{{ opp.scores.overall }}</span>
            </div>
            <span class="score-label">综合评分</span>
          </div>
          <div class="score-bars">
            <div v-for="(dim, i) in dims" :key="dim.key" class="bar" :style="{ '--bar-delay': i * 80 + 'ms' }">
              <span class="bar-label">{{ dim.label }}</span>
              <div class="bar-track">
                <div class="bar-fill" :class="dim.cls" :style="{ width: opp.scores[dim.key] + '%' }"></div>
              </div>
              <span class="bar-val">{{ opp.scores[dim.key] }}</span>
            </div>
          </div>
        </div>

        <!-- Description -->
        <section v-if="opp.description" class="detail-section glass-card" data-reveal="up" data-delay="100">
          <h2>描述</h2>
          <p class="desc-text">{{ opp.description }}</p>
        </section>

        <!-- Traction -->
        <section v-if="opp.traction?.length" class="detail-section glass-card" data-reveal="up" data-delay="200">
          <h2>牵引力信号</h2>
          <div class="traction-grid">
            <div v-for="(t, i) in opp.traction" :key="t.source" class="traction-card" :style="{ '--stagger': i * 60 + 'ms' }">
              <span class="traction-source">{{ t.source }}</span>
              <span class="traction-count">{{ t.mention_count }} 次</span>
              <span class="traction-trend">{{ t.growth_trend }}</span>
              <p v-if="t.representative_quote" class="traction-quote">"{{ t.representative_quote }}"</p>
            </div>
          </div>
        </section>

        <!-- Actions -->
        <section class="detail-section glass-card" data-reveal="up" data-delay="300">
          <h2>动作</h2>
          <div class="action-row">
            <button class="action-btn primary" @click="goGenerate">生成提案</button>
            <button class="action-btn" disabled title="即将上线">刷新评分</button>
          </div>
        </section>
      </div>

      <!-- Tab: Links -->
      <div v-if="tab === 'links'" class="tab-content">
        <div v-if="linksLoading" class="loading-state glass-card"><div class="spinner"></div><span>加载关联...</span></div>
        <div v-else-if="linkedReqs.length === 0 && linkedProposals.length === 0" class="empty-state glass-card">暂无关联对象</div>
        <div v-else class="links-list">
          <div v-if="linkedReqs.length" class="link-group glass-card" data-reveal="up">
            <h3>包含的需求 ({{ linkedReqs.length }})</h3>
            <div v-for="(item, i) in linkedReqs" :key="item.id" class="link-item" :style="{ '--stagger': i * 50 + 'ms' }">
              <span class="link-id">{{ item.target_id }}</span>
              <button class="link-nav" @click="goRequirement(item.target_id)">查看 →</button>
            </div>
          </div>
          <div v-if="linkedProposals.length" class="link-group glass-card" data-reveal="up" data-delay="100">
            <h3>生成的提案 ({{ linkedProposals.length }})</h3>
            <div v-for="(item, i) in linkedProposals" :key="item.id" class="link-item" :style="{ '--stagger': i * 50 + 'ms' }">
              <span class="link-id">提案 #{{ item.source_id }}</span>
              <button class="link-nav" @click="goProposal(parseInt(item.source_id))">查看 →</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import { useReveal } from '../composables/useReveal'

const route = useRoute()
const router = useRouter()
const oppId = computed(() => parseInt(route.query.id as string) || 0)

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

const opp = ref<any>(null)
const loading = ref(true)
const error = ref('')
const tab = ref('overview')
const linkedReqs = ref<any[]>([])
const linkedProposals = ref<any[]>([])
const linksLoading = ref(false)

const dims = [
  { key: 'vibe_code_suitability', label: 'Vibe 适配', cls: 'bar-blue' },
  { key: 'demand_intensity', label: '需求热度', cls: 'bar-amber' },
  { key: 'technical_feasibility', label: '技术可行', cls: 'bar-green' },
  { key: 'market_freshness', label: '市场新鲜', cls: 'bar-gray' },
]

function goGenerate() { router.push(`/proposals/${oppId.value}`) }
function goProposal(id: number) { router.push(`/proposals/${id}`) }
function goRequirement(title: string) {
  router.push(`/requirement-detail?path=${encodeURIComponent('02-需求池/' + title + '.md')}`)
}

async function fetchAll() {
  loading.value = true; error.value = ''
  try {
    const id = oppId.value
    if (!id) { error.value = '缺少机会 ID'; loading.value = false; return }
    const { data } = await api.get(`/opportunities/${id}`)
    opp.value = data
    linksLoading.value = true
    try {
      const lr = await api.get('/links', { params: { entity_type: 'opportunity', entity_id: String(id), direction: 'outgoing' } })
      linkedReqs.value = lr.data.items.filter((l: any) => l.link_type === 'contains' && l.target_type === 'requirement')
    } catch { linkedReqs.value = [] }
    try {
      const lr2 = await api.get('/links', { params: { entity_type: 'opportunity', entity_id: String(id), direction: 'incoming' } })
      linkedProposals.value = lr2.data.items.filter((l: any) => l.link_type === 'generates' && l.source_type === 'proposal')
    } catch { linkedProposals.value = [] }
    linksLoading.value = false
  } catch (e: any) {
    error.value = '加载失败：' + (e.response?.data?.detail || e.message)
  } finally { loading.value = false }
}

onMounted(fetchAll)
</script>

<style scoped>
.opp-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ── Glass Card ── */
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

/* ── Hero ── */
.hero {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-2xl);
  padding: var(--space-9) var(--space-7) var(--space-7);
  background: var(--gradient-hero-subtle);
  margin-bottom: var(--space-2);
}

.hero-orbs {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
  animation: float 8s ease-in-out infinite;
}

.orb-1 {
  width: 300px;
  height: 300px;
  background: rgba(0, 122, 255, 0.3);
  top: -80px;
  left: -60px;
  animation-delay: 0s;
}

.orb-2 {
  width: 220px;
  height: 220px;
  background: rgba(88, 86, 214, 0.25);
  top: 20px;
  right: -40px;
  animation-delay: -3s;
}

.orb-3 {
  width: 180px;
  height: 180px;
  background: rgba(240, 147, 251, 0.2);
  bottom: -40px;
  left: 40%;
  animation-delay: -5s;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.hero-loading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text-secondary);
  font-size: 14px;
}

/* ── States ── */
.loading-state, .error-banner, .empty-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6);
  justify-content: center;
  color: var(--color-text-secondary);
}

.error-banner {
  background: var(--color-danger-bg);
  color: var(--color-danger);
  border-color: rgba(255, 59, 48, 0.2);
  backdrop-filter: blur(var(--glass-blur));
}

.retry-btn {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  transition: all var(--duration-fast) var(--ease-apple);
}

.retry-btn:hover {
  background: rgba(255, 59, 48, 0.1);
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  flex-direction: column;
}

.empty-state a {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}

.empty-state a:hover {
  text-decoration: underline;
}

/* ── Back Link ── */
.back-link {
  font-size: 13px;
  color: var(--color-primary);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  transition: color var(--duration-fast) var(--ease-apple);
}

.back-link:hover {
  color: var(--color-primary-hover);
}

/* ── Title & Meta ── */
.detail-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
  letter-spacing: -0.025em;
  line-height: 1.2;
}

.detail-meta {
  font-size: 13px;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.meta-tag {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.meta-dot {
  color: var(--color-text-tertiary);
}

/* ── Tabs ── */
.tabs {
  display: flex;
  gap: 0;
  padding: var(--space-1);
}

.tabs button {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
  border-radius: var(--radius-lg);
  font-family: inherit;
  font-weight: 500;
  transition: all var(--duration-normal) var(--ease-apple);
}

.tabs button.active {
  color: var(--color-primary);
  background: var(--color-primary-bg);
  font-weight: 600;
}

.tabs button:hover:not(.active) {
  color: var(--color-text);
  background: var(--color-bg-secondary);
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* ── Score Section ── */
.score-section {
  display: flex;
  gap: var(--space-6);
  align-items: center;
  padding: var(--space-6);
}

.score-section:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.score-ring-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.score-ring {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: conic-gradient(var(--color-primary) calc(var(--pct) * 1%), var(--color-bg-secondary) 0);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: transform var(--duration-normal) var(--ease-apple);
}

.score-ring:hover {
  transform: scale(1.05);
}

.score-ring::after {
  content: '';
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: var(--glass-bg-heavy);
  position: absolute;
  backdrop-filter: blur(8px);
}

.score-num {
  position: relative;
  z-index: 1;
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}

.score-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.score-bars {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  animation: bar-enter var(--duration-reveal) var(--ease-apple) both;
  animation-delay: var(--bar-delay, 0ms);
}

@keyframes bar-enter {
  from { opacity: 0; transform: translateX(-12px); }
  to { opacity: 1; transform: translateX(0); }
}

.bar-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  width: 72px;
  flex-shrink: 0;
  font-weight: 500;
}

.bar-track {
  flex: 1;
  height: 8px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width var(--duration-slow) var(--ease-out);
}

.bar-blue { background: var(--gradient-accent); }
.bar-amber { background: var(--color-warning); }
.bar-green { background: var(--color-success); }
.bar-gray { background: var(--color-text-tertiary); }

.bar-val {
  font-size: 12px;
  color: var(--color-text-tertiary);
  width: 28px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

/* ── Detail Sections ── */
.detail-section {
  padding: var(--space-6);
}

.detail-section:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.detail-section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 var(--space-4);
  letter-spacing: -0.01em;
}

.desc-text {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.8;
  margin: 0;
  white-space: pre-wrap;
}

/* ── Traction ── */
.traction-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-3);
}

.traction-card {
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
  animation: traction-enter var(--duration-reveal) var(--ease-apple) both;
  animation-delay: var(--stagger, 0ms);
}

@keyframes traction-enter {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.traction-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.traction-source {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.traction-count {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}

.traction-trend {
  font-size: 11px;
  color: var(--color-text-tertiary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.traction-quote {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-style: italic;
  margin: var(--space-1) 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.5;
}

/* ── Actions ── */
.action-row {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.action-btn {
  padding: 10px 20px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  background: var(--glass-bg);
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  transition: all var(--duration-normal) var(--ease-apple);
}

.action-btn:hover:not(:disabled) {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: var(--shadow-md);
}

.action-btn.primary {
  background: var(--gradient-accent);
  color: #fff;
  border-color: transparent;
}

.action-btn.primary:hover {
  box-shadow: 0 4px 16px rgba(0, 122, 255, 0.3);
  transform: translateY(-1px);
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Links ── */
.links-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.link-group {
  padding: var(--space-5);
}

.link-group h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 var(--space-3);
  letter-spacing: -0.01em;
}

.link-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 13px;
  justify-content: space-between;
  animation: link-enter var(--duration-normal) var(--ease-apple) both;
  animation-delay: var(--stagger, 0ms);
}

@keyframes link-enter {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: translateX(0); }
}

.link-item:last-child {
  border-bottom: none;
}

.link-id {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
}

.link-nav {
  padding: 4px 14px;
  border-radius: var(--radius-full);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  color: var(--color-primary);
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  transition: all var(--duration-normal) var(--ease-apple);
}

.link-nav:hover {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}
</style>
