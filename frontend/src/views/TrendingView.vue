<template>
  <div class="trending-page">
    <!-- Header Actions -->
    <div class="header-card">
      <div class="header-left">
        <h3 class="header-title">GitHub Trending 选题</h3>
        <p class="header-desc">基于 GitHub 趋势项目，发现技术热点与选题机会</p>
      </div>
      <div class="header-actions">
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

    <!-- Stats Row -->
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

    <!-- Recommend Section -->
    <div class="recommend-card">
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
    </div>

    <!-- Project Grid -->
    <div v-if="projects.length === 0 && !fetching" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
      </svg>
      <p>暂无数据，点击「刷新数据」抓取最新趋势</p>
    </div>

    <div v-else class="project-grid">
      <div v-for="proj in projects" :key="proj.id" class="project-card" :class="{ analyzed: proj.is_analyzed }">
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/client'

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
  gap: 20px;
}

/* ── Header ── */
.header-card {
  background: linear-gradient(135deg, #1a1a1a, #141414);
  border-radius: 16px;
  padding: 24px 28px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  font-family: 'Outfit', sans-serif;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}

.header-desc {
  font-size: 13px;
  color: rgba(255,255,255,0.55);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-select {
  height: 38px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1.5px solid rgba(255,255,255,0.2);
  background: rgba(255,255,255,0.1);
  font-size: 13px;
  font-family: inherit;
  color: #fff;
  outline: none;
  cursor: pointer;
}

.filter-select option { color: #e0e0e0; background: #1a1a1a; }

.fetch-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 18px;
  height: 38px;
  border-radius: 10px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: var(--slate-800);
  background: #141414;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
  white-space: nowrap;
}

.fetch-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
.fetch-btn:disabled { opacity: 0.7; cursor: not-allowed; }

/* ── Stats ── */
.stats-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 10px;
  background: #141414;
  border: 1px solid var(--slate-100);
  box-shadow: none;
}

.stat-val {
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 700;
  color: var(--teal-600);
}

.stat-lbl {
  font-size: 12px;
  color: var(--slate-400);
  font-weight: 500;
}

/* ── Grid ── */
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}

.project-card {
  background: #141414;
  border-radius: 14px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.project-card:hover {
  border-color: var(--card-border-hover);
  border-color: var(--slate-200);
}

.project-card.analyzed {
  border-left: 3px solid var(--teal-400);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.card-name {
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--slate-800);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-name:hover { color: var(--teal-600); }

.lang-badge {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  flex-shrink: 0;
}

.card-desc {
  font-size: 13px;
  color: var(--slate-500);
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
  gap: 10px;
}

.card-stats {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--slate-400);
  font-weight: 500;
}

.stat-item svg { opacity: 0.5; }
.period-stars { color: var(--amber-500); font-weight: 600; }

.analyze-btn {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1.5px solid var(--slate-200);
  background: #141414;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  color: var(--teal-600);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.analyze-btn:hover:not(:disabled) {
  border-color: var(--teal-400);
  background: var(--teal-50);
}

.analyze-btn.done {
  color: var(--slate-400);
  border-color: var(--slate-200);
  cursor: default;
}

.analyze-btn:disabled { opacity: 0.6; }

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-chip {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  background: var(--teal-50);
  color: var(--teal-700);
  border: 1px solid var(--teal-200);
}

.btn-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(0,0,0,0.1);
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
  gap: 12px;
  padding: 60px 0;
  color: var(--slate-400);
  font-size: 14px;
}

/* ── Recommend ── */
.recommend-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.recommend-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}

.recommend-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
  margin-bottom: 4px;
}

.recommend-desc {
  font-size: 13px;
  color: var(--slate-400);
}

.recommend-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.interest-input {
  height: 40px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1.5px solid var(--slate-200);
  font-size: 13px;
  font-family: inherit;
  color: var(--slate-800);
  outline: none;
  width: 240px;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.interest-input:focus {
  border-color: var(--teal-400);
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.1);
}

.interest-input::placeholder { color: var(--slate-400); }

.recommend-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px;
  height: 40px;
  border-radius: 10px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  background: linear-gradient(135deg, var(--teal-500), var(--teal-700));
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
  white-space: nowrap;
}

.recommend-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(13, 148, 136, 0.3);
}

.recommend-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.recommend-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.recommend-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-radius: 12px;
  background: var(--slate-50);
  border: 1px solid var(--slate-100);
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.recommend-item:hover {
  background: var(--teal-50);
  border-color: var(--teal-200);
}

.rec-index {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--teal-600);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

.rec-body { flex: 1; }

.rec-title {
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--slate-800);
  margin-bottom: 6px;
}

.rec-rationale {
  font-size: 13px;
  color: var(--slate-500);
  line-height: 1.6;
  margin-bottom: 8px;
}

.rec-angle {
  font-size: 13px;
  color: var(--teal-700);
  margin-bottom: 10px;
  line-height: 1.5;
}

.rec-angle-label {
  font-weight: 600;
}

.rec-projects {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.rec-project-chip {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  background: #141414;
  color: var(--slate-600);
  border: 1px solid var(--slate-200);
}

.recommend-empty {
  color: var(--slate-400);
  font-size: 14px;
  text-align: center;
  padding: 24px 0;
}

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-content {
  background: #141414;
  border-radius: 16px;
  width: 560px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--slate-100);
}

.modal-header h3 {
  font-family: 'Outfit', sans-serif;
  font-size: 17px;
  font-weight: 600;
  color: var(--slate-800);
}

.modal-close {
  background: none;
  border: none;
  font-size: 22px;
  color: var(--slate-400);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.modal-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.modal-section h4 {
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-700);
  margin-bottom: 8px;
}

.modal-section ul {
  padding-left: 18px;
  list-style: disc;
}

.modal-section li {
  font-size: 13px;
  color: var(--slate-600);
  line-height: 1.7;
}

.modal-section p {
  font-size: 13px;
  color: var(--slate-600);
  line-height: 1.7;
}

.modal-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
