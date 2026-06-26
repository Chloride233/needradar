<template>
  <div class="opportunities" ref="pageRef">
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>加载机会数据...</span>
    </div>
    <div v-if="error" class="error-banner">
      <span>{{ error }}</span>
      <button class="retry-btn" @click="fetchData">重试</button>
    </div>

    <template v-if="!loading && !error">
      <!-- Hero Header -->
      <div class="page-hero" data-reveal="up">
        <div class="hero-bg">
          <div class="hero-orb hero-orb-1"></div>
          <div class="hero-orb hero-orb-2"></div>
        </div>
        <div class="hero-inner">
          <h1 class="page-title">项目机会评分</h1>
          <p class="page-sub">基于需求分析生成的项目机会，按综合评分排序</p>
          <div class="hero-meta">
            <span class="count-badge">{{ total }} 项机会</span>
            <input
              v-model="minScore"
              type="number"
              min="0"
              max="100"
              placeholder="最低分"
              class="score-filter"
              @change="fetchData"
            />
          </div>
        </div>
      </div>

      <div v-if="items.length === 0" class="empty-state" data-reveal="up">
        <p>暂无评分。请先运行爬取管道，然后执行评分。</p>
      </div>

      <div class="opp-grid">
        <div
          v-for="(opp, i) in items"
          :key="opp.id"
          class="opp-card"
          data-reveal="up"
          :data-delay="Math.min(i * 100, 500)"
          role="button"
          tabindex="0"
          @click="goProposal(opp.id)"
          @keydown.enter="goProposal(opp.id)"
        >
          <div class="opp-score">
            <div class="score-ring" :style="{ '--pct': opp.scores.overall }">
              <span class="score-num">{{ opp.scores.overall }}</span>
            </div>
          </div>
          <div class="opp-body">
            <h3 class="opp-title">{{ opp.title }}</h3>
            <p class="opp-desc">{{ opp.description }}</p>
            <div class="opp-meta">
              <span class="opp-kw">{{ opp.keyword }}</span>
              <div class="opp-srcs">
                <span v-for="t in opp.traction?.slice(0, 3)" :key="t.source" class="src-tag">
                  {{ t.source }} {{ t.mention_count }}
                </span>
              </div>
            </div>
            <div class="opp-bars">
              <div v-for="dim in dims" :key="dim.key" class="bar">
                <span class="bar-label">{{ dim.label }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :class="dim.cls" :style="{ width: opp.scores[dim.key] + '%' }"></div>
                </div>
                <span class="bar-val">{{ opp.scores[dim.key] }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useReveal } from '../composables/useReveal'
import api from '../api/client'

const router = useRouter()
const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

const items = ref<any[]>([])
const total = ref(0)
const loading = ref(true)
const error = ref('')
const minScore = ref(0)

const dims = [
  { key: 'vibe_code_suitability', label: 'Vibe 适配', cls: 'bar-blue' },
  { key: 'demand_intensity', label: '需求热度', cls: 'bar-amber' },
  { key: 'technical_feasibility', label: '技术可行', cls: 'bar-green' },
  { key: 'market_freshness', label: '市场新鲜', cls: 'bar-gray' },
]

function goProposal(id: number) {
  router.push(`/opportunity-detail?id=${id}`)
}

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const params: any = { page_size: 50 }
    if (minScore.value > 0) params.min_score = minScore.value
    const { data } = await api.get('/opportunities', { params })
    items.value = data.items
    total.value = data.total
  } catch (e: any) {
    error.value = '加载失败：' + (e.response?.data?.detail || e.message)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.opportunities {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ── Hero ── */
.page-hero {
  position: relative;
  padding: var(--space-8) var(--space-6);
  border-radius: var(--radius-2xl);
  overflow: hidden;
  margin-bottom: var(--space-2);
}

.hero-bg {
  position: absolute;
  inset: -50%;
  pointer-events: none;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  animation: float 8s ease-in-out infinite;
}

.hero-orb-1 {
  width: 300px;
  height: 300px;
  background: rgba(0, 122, 255, 0.1);
  top: 0;
  right: 20%;
}

.hero-orb-2 {
  width: 250px;
  height: 250px;
  background: rgba(88, 86, 214, 0.08);
  bottom: 0;
  left: 30%;
  animation-delay: -3s;
}

.hero-inner {
  position: relative;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
  margin-bottom: var(--space-2);
}

.page-sub {
  font-size: 15px;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.count-badge {
  font-size: 13px;
  color: var(--color-primary);
  background: var(--color-primary-bg);
  padding: 6px 14px;
  border-radius: var(--radius-full);
  font-weight: 600;
}

.score-filter {
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  color: var(--color-text);
  font-size: 13px;
  width: 80px;
  font-family: inherit;
}

.score-filter:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15);
}

/* ── States ── */
.loading-state, .error-banner, .empty-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-7);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border-radius: var(--radius-xl);
  color: var(--color-text-secondary);
  justify-content: center;
  border: 1px solid var(--glass-border);
}

.error-banner {
  background: var(--color-danger-bg);
  color: var(--color-danger);
  border-color: rgba(255, 59, 48, 0.2);
}

.retry-btn {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Grid ── */
.opp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: var(--space-4);
}

.opp-card {
  display: flex;
  gap: var(--space-4);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  cursor: pointer;
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
  box-shadow: var(--shadow-glass);
}

.opp-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.opp-score {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
}

.score-ring {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: conic-gradient(var(--color-primary) calc(var(--pct) * 1%), var(--color-bg-secondary) 0);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.score-ring::after {
  content: '';
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-bg);
  position: absolute;
}

.score-num {
  position: relative;
  z-index: 1;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}

.opp-body {
  flex: 1;
  min-width: 0;
}

.opp-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: var(--space-1);
}

.opp-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.opp-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  flex-wrap: wrap;
}

.opp-kw {
  font-size: 11px;
  color: var(--color-primary);
  background: var(--color-primary-bg);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

.opp-srcs {
  display: flex;
  gap: 4px;
}

.src-tag {
  font-size: 10px;
  color: var(--color-text-tertiary);
  background: var(--color-bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}

/* ── Bars ── */
.opp-bars {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.bar-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
  width: 56px;
  flex-shrink: 0;
}

.bar-track {
  flex: 1;
  height: 4px;
  background: var(--color-bg-secondary);
  border-radius: 2px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width var(--duration-slow) var(--ease-apple);
}

.bar-blue { background: var(--color-primary); }
.bar-amber { background: var(--color-warning); }
.bar-green { background: var(--color-success); }
.bar-gray { background: var(--color-text-tertiary); }

.bar-val {
  font-size: 11px;
  color: var(--color-text-tertiary);
  width: 20px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
