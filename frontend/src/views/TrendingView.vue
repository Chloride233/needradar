<template>
  <div class="trending-page" ref="pageRef">
    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-orb hero-orb-1"></div>
        <div class="hero-orb hero-orb-2"></div>
      </div>
      <div class="hero-content" data-reveal="up">
        <h1 class="hero-title">GitHub Trending 选题</h1>
        <p class="hero-sub">基于 GitHub 趋势项目，发现技术热点与选题机会</p>
        <div class="hero-actions">
          <select v-model="filters.since" class="filter-select" @change="loadProjects">
            <option value="daily">今日</option>
            <option value="weekly">本周</option>
            <option value="monthly">本月</option>
          </select>
          <select v-model="filters.language" class="filter-select" @change="loadProjects">
            <option value="">全部语言</option>
            <option v-for="lang in languages" :key="lang" :value="lang">{{ lang }}</option>
          </select>
          <button class="fetch-btn" :class="{ loading: fetching }" @click="fetchTrending" :disabled="fetching">
            <svg v-if="!fetching" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
            <span v-else class="btn-spinner"></span>
            {{ fetching ? '抓取中...' : '刷新数据' }}
          </button>
        </div>
      </div>
    </section>

    <!-- Stats Row -->
    <section class="stats-section" data-reveal="up" data-delay="100">
      <div class="stats-row">
        <div class="stat-pill">
          <span class="stat-val">{{ stats.total_projects }}</span>
          <span class="stat-lbl">项目数</span>
        </div>
        <div class="stat-pill" v-for="(count, lang) in topLanguages" :key="lang">
          <span class="stat-val">{{ count }}</span>
          <span class="stat-lbl">{{ lang }}</span>
        </div>
      </div>
    </section>

    <!-- Recommend Section -->
    <section class="recommend-card" data-reveal="up" data-delay="200">
      <div class="recommend-header">
        <div>
          <h3 class="recommend-title">AI 选题推荐</h3>
          <p class="recommend-desc">基于当前趋势项目，为你推荐最适合的选题方向</p>
        </div>
        <div class="recommend-actions">
          <input v-model="interest" class="interest-input" placeholder="输入关注领域，如 AI编程、前端开发..." @keyup.enter="getRecommendations" />
          <button class="recommend-btn" :class="{ loading: recommending }" @click="getRecommendations" :disabled="recommending">
            <span v-if="recommending" class="btn-spinner"></span>
            {{ recommending ? '分析中...' : '智能推荐' }}
          </button>
        </div>
      </div>
      <div v-if="recommendations.length" class="recommend-list">
        <div v-for="(rec, i) in recommendations" :key="i" class="recommend-item">
          <div class="rec-index">{{ i + 1 }}</div>
          <div class="rec-body">
            <h4 class="rec-title">{{ rec.title }}</h4>
            <p class="rec-rationale">{{ rec.rationale }}</p>
            <div class="rec-angle">
              <span class="rec-angle-label">选题角度：</span>{{ rec.angle }}
            </div>
            <div class="rec-projects">
              <span v-for="p in rec.related_projects" :key="p" class="rec-project-chip">{{ p }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="!recommending" class="recommend-empty">
        输入你的关注领域，点击「智能推荐」获取个性化选题建议
      </div>
    </section>

    <!-- Project Grid -->
    <div v-if="projects.length === 0 && !fetching" class="empty-state" data-reveal="up">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-tertiary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
      </svg>
      <p>暂无数据，点击「刷新数据」抓取最新趋势</p>
    </div>

    <div v-else class="project-grid">
      <div v-for="(proj, i) in projects" :key="proj.id" class="project-card" :class="{ analyzed: proj.is_analyzed }" data-reveal="up" :data-delay="Math.min(i * 100, 500)">
        <div class="card-header">
          <a :href="'https://github.com/' + proj.full_name" target="_blank" class="card-name">
            {{ proj.full_name }}
          </a>
          <span v-if="proj.language" class="lang-badge" :style="langStyle(proj.language)">{{ proj.language }}</span>
        </div>
        <p class="card-desc">{{ proj.description || 'No description' }}</p>
        <div class="card-footer">
          <div class="card-stats">
            <span class="stat-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 12 .25Z"/></svg>
              {{ formatNum(proj.stars) }}
            </span>
            <span class="stat-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="18" r="3"/><path d="M12 2v10"/><path d="M8.5 8 12 2l3.5 6"/></svg>
              {{ formatNum(proj.forks) }}
            </span>
            <span class="stat-item period-stars">
              +{{ formatNum(proj.period_stars) }} {{ sinceLabel }}
            </span>
          </div>
          <button class="analyze-btn" :class="{ done: proj.is_analyzed }" @click="analyzeProject(proj)" :disabled="analyzingId === proj.id || proj.is_analyzed">
            <span v-if="analyzingId === proj.id" class="btn-spinner"></span>
            {{ proj.is_analyzed ? '已分析' : '选题分析' }}
          </button>
        </div>
        <div v-if="proj.tags" class="card-tags">
          <span v-for="tag in proj.tags.split(',')" :key="tag" class="tag-chip">{{ tag }}</span>
        </div>
      </div>
    </div>

    <!-- Analysis Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="analysisResult" class="modal-overlay" @click.self="analysisResult = null">
          <div class="modal-content">
            <div class="modal-header">
              <h3>{{ analysisResult.full_name }}</h3>
              <button class="modal-close" @click="analysisResult = null" aria-label="关闭">&times;</button>
            </div>
            <div class="modal-body">
              <div class="modal-section">
                <h4>技术亮点</h4>
                <ul><li v-for="h in analysisResult.highlights" :key="h">{{ h }}</li></ul>
              </div>
              <div class="modal-section">
                <h4>应用场景</h4>
                <ul><li v-for="u in analysisResult.use_cases" :key="u">{{ u }}</li></ul>
              </div>
              <div class="modal-section">
                <h4>趋势分析</h4>
                <p>{{ analysisResult.analysis }}</p>
              </div>
              <div class="modal-section">
                <h4>主题标签</h4>
                <div class="modal-tags">
                  <span v-for="t in analysisResult.tags" :key="t" class="tag-chip">{{ t }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/client'
import { useReveal } from '../composables/useReveal'

interface TrendingProject {
  id: number
  full_name: string
  description: string
  language: string
  stars: number
  forks: number
  period_stars: number
  since: string
  contributors: string
  tags: string
  snapshot_date: string
  is_analyzed: boolean
}

const projects = ref<TrendingProject[]>([])
const languages = ref<string[]>([])
const fetching = ref(false)
const analyzingId = ref<number | null>(null)
const analysisResult = ref<any>(null)
const interest = ref('')
const recommending = ref(false)
const recommendations = ref<any[]>([])

const filters = ref({ language: '', since: 'daily' })

const stats = ref({ total_projects: 0, language_distribution: {} as Record<string, number>, snapshots_available: [] as string[] })

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

const sinceLabel = computed(() => {
  const m: Record<string, string> = { daily: '今日', weekly: '本周', monthly: '本月' }
  return m[filters.value.since] || ''
})

const topLanguages = computed(() => {
  const dist = stats.value.language_distribution
  const sorted = Object.entries(dist).sort((a, b) => b[1] - a[1]).slice(0, 5)
  return Object.fromEntries(sorted)
})

const LANG_COLORS: Record<string, string> = {
  Python: '#3572A5', TypeScript: '#3178C6', JavaScript: '#F7DF1E', Rust: '#DEA584',
  Go: '#00ADD8', Java: '#B07219', 'C++': '#F34B7D', C: '#555555', Shell: '#89E051',
  Swift: '#F05138', Kotlin: '#A97BFF', Ruby: '#CC342D', PHP: '#4F5D95',
  Dart: '#00B4AB', Vue: '#41B883', HTML: '#E34C26', CSS: '#563D7C',
}

function langStyle(lang: string) {
  const c = LANG_COLORS[lang] || '#94a3b8'
  return { background: c + '18', color: c, borderColor: c + '40' }
}

function formatNum(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

async function loadProjects() {
  try {
    const [projRes, langRes, statsRes] = await Promise.all([
      api.get('/trending', { params: { language: filters.value.language, since: filters.value.since, page_size: 50 } }),
      api.get('/trending/languages'),
      api.get('/trending/stats', { params: { since: filters.value.since } }),
    ])
    projects.value = projRes.data.items
    languages.value = langRes.data
    stats.value = statsRes.data
  } catch { /* handled by interceptor */ }
}

async function fetchTrending() {
  fetching.value = true
  try {
    await api.post('/trending/fetch-all')
    await loadProjects()
  } finally {
    fetching.value = false
  }
}

async function analyzeProject(proj: TrendingProject) {
  analyzingId.value = proj.id
  try {
    const { data } = await api.post(`/trending/analyze/${proj.id}`)
    analysisResult.value = { ...data, full_name: proj.full_name }
    proj.tags = data.tags.join(',')
    proj.is_analyzed = true
  } finally {
    analyzingId.value = null
  }
}

async function getRecommendations() {
  recommending.value = true
  try {
    const { data } = await api.post('/trending/recommend', null, { params: { interest: interest.value } })
    recommendations.value = data.recommendations
  } finally {
    recommending.value = false
  }
}

onMounted(loadProjects)
</script>

<style scoped>
.trending-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ── Hero ── */
.hero {
  position: relative;
  border-radius: var(--radius-2xl);
  overflow: hidden;
  padding: var(--space-8) var(--space-6);
  margin-top: var(--space-4);
}

.hero-bg {
  position: absolute;
  inset: 0;
  background: var(--gradient-hero-subtle);
  z-index: 0;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.5;
  animation: float 8s ease-in-out infinite;
}

.hero-orb-1 {
  width: 260px;
  height: 260px;
  background: rgba(0, 122, 255, 0.2);
  top: -40px;
  right: -30px;
  animation-delay: 0s;
}

.hero-orb-2 {
  width: 200px;
  height: 200px;
  background: rgba(88, 86, 214, 0.18);
  bottom: -30px;
  left: -20px;
  animation-delay: -3s;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.hero-title {
  font-family: var(--font-sans);
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.5px;
  line-height: 1.2;
}

.hero-sub {
  font-size: 15px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  max-width: 480px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-2);
}

/* ── Filter & Buttons ── */
.filter-select {
  height: 40px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(var(--glass-blur));
  font-size: 13px;
  font-family: inherit;
  color: var(--color-text);
  outline: none;
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.filter-select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15);
}

.fetch-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-5);
  height: 40px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  background: var(--gradient-accent);
  cursor: pointer;
  transition: box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple);
  white-space: nowrap;
}

.fetch-btn:hover:not(:disabled) {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-1px);
}

.fetch-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Stats ── */
.stats-section {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-4) var(--space-5);
  transition: box-shadow var(--duration-normal) var(--ease-apple);
}

.stats-row {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-light);
  transition: background var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.stat-pill:hover {
  background: var(--color-primary-bg);
  box-shadow: var(--shadow-sm);
}

.stat-val {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 700;
  color: var(--color-primary);
}

.stat-lbl {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

/* ── Recommend ── */
.recommend-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-6);
  transition: box-shadow var(--duration-normal) var(--ease-apple);
}

.recommend-card:hover {
  box-shadow: var(--shadow-glass-hover);
}

.recommend-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.recommend-title {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 4px;
}

.recommend-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.recommend-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.interest-input {
  height: 40px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  font-size: 13px;
  font-family: inherit;
  color: var(--color-text);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(var(--glass-blur));
  outline: none;
  width: 240px;
  transition: border-color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.interest-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15);
}

.interest-input::placeholder { color: var(--color-text-tertiary); }

.recommend-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-5);
  height: 40px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  background: var(--gradient-accent);
  cursor: pointer;
  transition: box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple);
  white-space: nowrap;
}

.recommend-btn:hover:not(:disabled) {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-1px);
}

.recommend-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.recommend-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.recommend-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple), border-color var(--duration-normal) var(--ease-apple);
}

.recommend-item:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
  border-color: var(--color-primary);
}

.rec-index {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--gradient-accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

.rec-body { flex: 1; }

.rec-title {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-1);
}

.rec-rationale {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-2);
}

.rec-angle {
  font-size: 13px;
  color: var(--color-primary);
  margin-bottom: var(--space-2);
  line-height: 1.5;
}

.rec-angle-label {
  font-weight: 600;
}

.rec-projects {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.rec-project-chip {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-light);
  transition: background var(--duration-normal) var(--ease-apple), color var(--duration-normal) var(--ease-apple);
}

.rec-project-chip:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.recommend-empty {
  color: var(--color-text-tertiary);
  font-size: 14px;
  text-align: center;
  padding: var(--space-5) 0;
}

/* ── Grid ── */
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: var(--space-4);
}

.project-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  transition: box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple), border-color var(--duration-normal) var(--ease-apple);
}

.project-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-glass-hover);
  border-color: rgba(0, 122, 255, 0.2);
}

.project-card.analyzed {
  border-left: 3px solid var(--color-success);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.card-name {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color var(--duration-fast) var(--ease-apple);
}

.card-name:hover { color: var(--color-primary); }

.lang-badge {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  flex-shrink: 0;
}

.card-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.card-stats {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.stat-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.stat-item svg { opacity: 0.5; }
.period-stars { color: var(--color-warning); font-weight: 600; }

.analyze-btn {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(var(--glass-blur));
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  color: var(--color-primary);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-apple), background var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple);
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.analyze-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.analyze-btn.done {
  color: var(--color-text-tertiary);
  border-color: var(--color-border-light);
  cursor: default;
  background: transparent;
  backdrop-filter: none;
}

.analyze-btn.done:hover {
  transform: none;
  box-shadow: none;
}

.analyze-btn:disabled { opacity: 0.5; }

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.tag-chip {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border: 1px solid transparent;
}

.btn-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(0, 0, 0, 0.1);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8) 0;
  color: var(--color-text-tertiary);
  font-size: 14px;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
}

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-content {
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(var(--glass-blur-heavy));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  width: 560px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-float);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border-light);
}

.modal-header h3 {
  font-family: var(--font-sans);
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
}

.modal-close {
  background: none;
  border: none;
  font-size: 22px;
  color: var(--color-text-tertiary);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
  transition: color var(--duration-fast) var(--ease-apple);
  border-radius: var(--radius-sm);
}

.modal-close:hover {
  color: var(--color-text);
  background: var(--color-bg-secondary);
}

.modal-body {
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.modal-section h4 {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-2);
}

.modal-section ul {
  padding-left: var(--space-4);
  list-style: disc;
}

.modal-section li {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.modal-section p {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.modal-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

/* ── Modal Transition ── */
.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--duration-slow) var(--ease-apple);
}

.modal-enter-active .modal-content,
.modal-leave-active .modal-content {
  transition: transform var(--duration-slow) var(--ease-apple), opacity var(--duration-slow) var(--ease-apple);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-content {
  transform: translateY(20px) scale(0.96);
  opacity: 0;
}

.modal-leave-to .modal-content {
  transform: translateY(10px) scale(0.98);
  opacity: 0;
}
</style>
