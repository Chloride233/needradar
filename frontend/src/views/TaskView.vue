<template>
  <div class="task-page">
    <!-- Create Task -->
    <div class="create-card">
      <div class="create-inner">
        <div class="create-input-area">
          <div class="input-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </div>
          <input
            v-model="keyword"
            class="search-input"
            placeholder="输入关键词，如 AI工具、AI编程、LLM Agent…"
            aria-label="搜索关键词"
            @keyup.enter="createTask"
          />
        </div>
        <div class="platform-checks">
          <label
            v-for="p in platformList"
            :key="p.value"
            class="platform-chip"
            :class="{ active: platforms.includes(p.value) }"
          >
            <input type="checkbox" :value="p.value" v-model="platforms" class="chip-input" />
            <span class="chip-dot" :style="{ background: p.color }"></span>
            {{ p.label }}
          </label>
        </div>
        <button class="create-btn" :class="{ loading: creating }" @click="createTask" :disabled="creating" aria-label="开始挖掘">
          <svg v-if="!creating" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          <span v-else class="btn-spinner"></span>
          {{ creating ? '启动中...' : '开始挖掘' }}
        </button>
      </div>
    </div>

    <!-- Trending Suggestions -->
    <div class="suggest-card">
      <div class="suggest-header">
        <h3 class="suggest-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
          </svg>
          不知道搜什么？从热门趋势选题
        </h3>
        <button class="suggest-refresh" @click="loadSuggestions" :disabled="loadingSuggestions" aria-label="刷新推荐">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
          换一批
        </button>
      </div>

      <div v-if="loadingSuggestions" class="suggest-loading">
        <span class="btn-spinner dark"></span> 正在获取热门选题...
      </div>

      <div v-else-if="suggestions.length" class="suggest-list">
        <div v-for="s in suggestions" :key="s.name" class="suggest-item" @click="applySuggestion(s)">
          <div class="suggest-item-left">
            <span class="suggest-lang" v-if="s.language" :style="langStyle(s.language)">{{ s.language }}</span>
            <div class="suggest-item-info">
              <span class="suggest-name">{{ s.name }}</span>
              <span class="suggest-desc" v-if="s.description">{{ s.description }}</span>
            </div>
          </div>
          <div class="suggest-item-right">
            <span class="suggest-heat">+{{ s.period_stars }}</span>
            <span class="suggest-action">选题挖掘</span>
          </div>
        </div>
      </div>

      <div v-else class="suggest-empty">
        <button class="suggest-fetch-btn" @click="fetchAndSuggest">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
          先抓取 GitHub 趋势数据
        </button>
      </div>
    </div>

    <!-- Task List -->
    <div class="list-card">
      <div class="list-header">
        <h3 class="list-title">
          任务列表
          <span class="list-count">{{ tasks.length }} 个任务</span>
        </h3>
        <div v-if="hasRunning" class="live-indicator">
          <span class="live-dot"></span>
          <span>实时刷新中</span>
        </div>
      </div>

      <div v-if="tasks.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>
        <p>暂无任务，试试下方的热门选题推荐</p>
      </div>

      <div v-else class="task-list">
        <div v-for="task in tasks" :key="task.id" class="task-item" :class="'task-' + task.status">
          <div class="task-left">
            <div class="task-status-dot" :class="'dot-' + task.status"></div>
            <div class="task-info">
              <div class="task-keyword">{{ task.keyword }}</div>
              <div class="task-meta">
                <span class="meta-platform">{{ task.platform }}</span>
                <span class="meta-sep">·</span>
                <span class="meta-time">{{ formatTime(task.created_at) }}</span>
              </div>
            </div>
          </div>
          <div class="task-right">
            <span class="task-badge" :class="'badge-' + task.status">
              {{ statusLabel[task.status] || task.status }}
            </span>
            <span v-if="task.total_items > 0" class="task-items">
              {{ task.total_items }} 条
            </span>
            <button v-if="task.report_path" class="report-link-btn" @click.stop="viewReport(task.report_path)" aria-label="查看报告">
              查看报告
            </button>
            <span v-if="task.new_items > 0" class="task-items">
              +{{ task.new_items }} 新
            </span>
            <span v-if="task.skipped_items > 0" class="task-items skip">
              {{ task.skipped_items }} 跳过
            </span>
            <span v-if="task.status === 'pending' || task.status === 'running'" class="task-elapsed running">
              {{ elapsed(task.created_at, task.status === 'completed' || task.status === 'failed' ? task.updated_at : undefined) }}
            </span>
            <span v-else-if="task.status === 'completed' || task.status === 'failed'" class="task-elapsed done">
              {{ elapsed(task.created_at, task.updated_at) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Report Modal -->
    <div v-if="viewingReport" class="modal-overlay" @click.self="viewingReport = null">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ reportTitle }}</h3>
          <button class="modal-close" @click="viewingReport = null" aria-label="关闭">&times;</button>
        </div>
        <div class="modal-body">
          <div class="report-markdown" v-html="reportHtml"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'
import { sanitize } from '../utils/sanitize'
import api from '../api/client'

marked.setOptions({ breaks: true, gfm: true })

const keyword = ref('')
const platforms = ref(['github', 'stackoverflow', 'juejin'])
const creating = ref(false)
const suggestions = ref<any[]>([])
const loadingSuggestions = ref(false)
const viewingReport = ref(false)
const reportHtml = ref('')
const reportTitle = ref('')
let eventSource: EventSource | null = null
let sseRetryDelay = 2000

const platformList = [
  { label: 'GitHub', value: 'github', color: '#24292f' },
  { label: 'Stack Overflow', value: 'stackoverflow', color: '#f48024' },
  { label: '掘金', value: 'juejin', color: '#0d9488' },
]

interface TaskItem {
  id: number
  keyword: string
  platform: string
  status: string
  total_items: number
  new_items: number
  skipped_items: number
  error_message: string | null
  report_path: string | null
  created_at: string
  updated_at?: string
}

const tasks = ref<TaskItem[]>([])

const hasRunning = computed(() =>
  tasks.value.some(t => t.status === 'pending' || t.status === 'running')
)

const statusLabel: Record<string, string> = {
  pending: '排队中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

function elapsed(start: string, end?: string): string {
  const s = new Date(start).getTime()
  const e = end ? new Date(end).getTime() : Date.now()
  const sec = Math.floor((e - s) / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  const rem = sec % 60
  if (min < 60) return `${min}m ${rem}s`
  const hr = Math.floor(min / 60)
  return `${hr}h ${min % 60}m`
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

async function createTask() {
  if (!keyword.value.trim()) return
  creating.value = true
  try {
    await api.post('/tasks', { keyword: keyword.value, platforms: platforms.value })
    keyword.value = ''
    await loadTasks()
  } finally {
    creating.value = false
  }
}

const LANG_COLORS: Record<string, string> = {
  Python: '#3572A5', TypeScript: '#3178C6', JavaScript: '#F7DF1E', Rust: '#DEA584',
  Go: '#00ADD8', Java: '#B07219', 'C++': '#F34B7D', C: '#555555', Shell: '#89E051',
  Kotlin: '#A97BFF', Swift: '#F05138',
}

function langStyle(lang: string) {
  const c = LANG_COLORS[lang] || '#94a3b8'
  return { background: c + '18', color: c }
}

async function loadSuggestions() {
  loadingSuggestions.value = true
  try {
    const { data } = await api.get('/trending/suggest-keywords', { params: { limit: 8 } })
    suggestions.value = data.projects
  } finally {
    loadingSuggestions.value = false
  }
}

async function fetchAndSuggest() {
  loadingSuggestions.value = true
  try {
    await api.post('/trending/fetch-all')
    await loadSuggestions()
  } finally {
    loadingSuggestions.value = false
  }
}

function applySuggestion(s: any) {
  keyword.value = s.keyword
  createTask()
}

async function viewReport(reportPath: string) {
  try {
    const { data } = await api.get(`/reports/by-filename/${reportPath}`)
    reportTitle.value = data.title
    let content = data.content.replace(/\\n/g, '\n')
    reportHtml.value = sanitize(marked.parse(content) as string)
    viewingReport.value = true
  } catch {
    // error handled by interceptor
  }
}

async function loadTasks() {
  try {
    const { data } = await api.get('/tasks', { params: { page_size: 50 } })
    tasks.value = data.items
  } catch { /* handled by interceptor */ }
}

function startSSE() {
  stopSSE()
  eventSource = new EventSource('/api/v1/tasks/sse/stream')
  eventSource.addEventListener('tasks', (e) => {
    try { tasks.value = JSON.parse(e.data) } catch {}
    sseRetryDelay = 2000 // reset on success
  })
  eventSource.onerror = () => {
    eventSource?.close()
    eventSource = null
    // Exponential backoff: 2s → 4s → 8s → 16s max
    sseRetryDelay = Math.min(sseRetryDelay * 2, 16000)
    setTimeout(startSSE, sseRetryDelay)
  }
}

function stopSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

onMounted(() => {
  loadTasks().catch(() => {})
  loadSuggestions()
  startSSE()
})
onUnmounted(stopSSE)
</script>

<style scoped>
.task-page {
  display: flex;
  flex-direction: column;
  gap: 20px;

}


/* ── Create Card ── */
.create-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.create-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}

.create-input-area {
  flex: 1;
  position: relative;
}

.input-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--slate-400);
  display: flex;
}

.search-input {
  width: 100%;
  height: 44px;
  padding: 0 14px 0 42px;
  border-radius: 12px;
  border: 1.5px solid var(--slate-200);
  font-size: 14px;
  font-family: inherit;
  color: var(--slate-800);
  background: var(--slate-50);
  outline: none;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.search-input::placeholder { color: var(--slate-400); }
.search-input:focus {
  border-color: var(--teal-400);
  background: #141414;
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.1);
}

.platform-checks {
  display: flex;
  gap: 8px;
}

.platform-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  background: var(--slate-50);
  border: 1.5px solid var(--slate-200);
  color: var(--slate-500);
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.chip-input { display: none; }

.chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  opacity: 0.4;
  transition: opacity 0.2s;
}

.platform-chip.active {
  border-color: var(--teal-400);
  background: var(--teal-50);
  color: var(--teal-700);
}

.platform-chip.active .chip-dot { opacity: 1; }

.create-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 24px;
  height: 44px;
  border-radius: 12px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  background: linear-gradient(135deg, var(--teal-500), var(--teal-700));
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.create-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(20, 196, 166, 0.25);
}

.create-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Task List ── */
.list-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.list-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
  display: flex;
  align-items: center;
  gap: 10px;
}

.list-count {
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  font-weight: 500;
  color: var(--slate-400);
  background: var(--slate-50);
  padding: 3px 10px;
  border-radius: 6px;
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--teal-600);
  font-weight: 500;
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--teal-500);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(13,148,136,0.4); }
  50% { box-shadow: 0 0 0 5px rgba(13,148,136,0); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
  color: var(--slate-400);
  font-size: 14px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--slate-50);
  border: 1px solid transparent;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.task-item:hover {
  background: #1a1a1a;
  border-color: var(--slate-200);
  border-color: var(--card-border-hover);
}

.task-item.task-running {
  background: rgba(20, 196, 166, 0.06);
  border-color: rgba(20, 196, 166, 0.2);
}

.task-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.task-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-pending { background: var(--slate-300); }
.dot-running { background: var(--teal-500); animation: pulse 1.5s ease-in-out infinite; }
.dot-completed { background: var(--emerald-500); }
.dot-failed { background: #f43f5e; }

.task-keyword {
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-800);
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--slate-400);
  margin-top: 3px;
}

.meta-sep { color: var(--slate-300); }

.task-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-badge {
  padding: 4px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
}

.badge-pending { background: var(--slate-100); color: var(--slate-500); }
.badge-running { background: rgba(13,148,136,0.1); color: var(--teal-700); }
.badge-completed { background: var(--success-bg); color: var(--success-text); }
.badge-failed { background: var(--error-bg); color: var(--error-text); }

.task-items {
  font-size: 13px;
  color: var(--teal-600);
  font-weight: 500;
}

.task-items.skip {
  color: var(--slate-400);
}

.task-elapsed {
  font-size: 12px;
  font-family: 'Outfit', sans-serif;
  font-weight: 500;
}

.task-elapsed.running { color: var(--amber-500); }
.task-elapsed.done { color: var(--slate-400); }

/* ── Suggestions ── */
.suggest-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 20px 24px;
}

.suggest-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.suggest-title {
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-600);
  display: flex;
  align-items: center;
  gap: 8px;
}

.suggest-title svg { color: var(--teal-500); }

.suggest-refresh {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 8px;
  border: 1px solid var(--slate-200);
  background: #141414;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  color: var(--slate-500);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.suggest-refresh:hover { border-color: var(--teal-300); color: var(--teal-600); }
.suggest-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

.suggest-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  color: var(--slate-400);
  font-size: 13px;
}

.btn-spinner.dark {
  border-color: rgba(0,0,0,0.1);
  border-top-color: var(--slate-600);
  width: 14px;
  height: 14px;
}

.suggest-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 8px;
}

.suggest-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--slate-50);
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
  gap: 12px;
}

.suggest-item:hover {
  background: var(--teal-50);
  border: 1px solid var(--teal-200);
  box-shadow: 0 2px 8px rgba(13, 148, 136, 0.08);
}

.suggest-item-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.suggest-lang {
  padding: 2px 8px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.suggest-item-info {
  min-width: 0;
}

.suggest-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--slate-700);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.suggest-desc {
  display: block;
  font-size: 11px;
  color: var(--slate-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.suggest-item-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.suggest-heat {
  font-family: 'Outfit', sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: var(--amber-500);
}

.suggest-action {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: var(--teal-50);
  color: var(--teal-700);
  border: 1px solid var(--teal-200);
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.suggest-item:hover .suggest-action {
  background: var(--teal-600);
  color: #fff;
  border-color: var(--teal-600);
}

.suggest-empty {
  text-align: center;
  padding: 16px;
}

.suggest-fetch-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 10px;
  border: 1.5px solid var(--teal-300);
  background: var(--teal-50);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: var(--teal-700);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.suggest-fetch-btn:hover {
  background: var(--teal-600);
  color: #fff;
  border-color: var(--teal-600);
}

/* ── Report Link ── */
.report-link-btn {
  padding: 3px 10px;
  border-radius: 6px;
  border: 1px solid var(--teal-200);
  background: var(--teal-50);
  font-size: 11px;
  font-weight: 600;
  font-family: inherit;
  color: var(--teal-700);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.report-link-btn:hover {
  background: var(--teal-600);
  color: #fff;
  border-color: var(--teal-600);
}

/* ── Report Modal ── */
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
  width: 700px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--slate-100);
  flex-shrink: 0;
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
  overflow-y: auto;
  flex: 1;
}

.report-markdown {
  font-size: 14px;
  line-height: 1.8;
  color: var(--slate-700);
}

.report-markdown :deep(h1) { font-family: 'Outfit', sans-serif; font-size: 20px; font-weight: 700; color: var(--slate-900); margin-bottom: 16px; }
.report-markdown :deep(h2) { font-family: 'Outfit', sans-serif; font-size: 16px; font-weight: 600; color: var(--slate-800); margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 2px solid var(--teal-100); }
.report-markdown :deep(h3) { font-family: 'Outfit', sans-serif; font-size: 14px; font-weight: 600; color: var(--slate-800); margin: 16px 0 8px; }
.report-markdown :deep(strong) { color: var(--slate-900); }
.report-markdown :deep(li) { list-style: disc; margin-left: 20px; margin-bottom: 4px; }
.report-markdown :deep(table) { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }
.report-markdown :deep(td), .report-markdown :deep(th) { padding: 8px 12px; border: 1px solid var(--slate-200); text-align: left; }
.report-markdown :deep(blockquote) { border-left: 3px solid var(--teal-300); padding: 8px 16px; margin: 12px 0; background: var(--slate-50); border-radius: 0 8px 8px 0; }
.report-markdown :deep(p) { margin-bottom: 10px; }
.report-markdown :deep(ul), .report-markdown :deep(ol) { padding-left: 24px; margin-bottom: 12px; }
.report-markdown :deep(hr) { border: none; border-top: 1px solid var(--slate-200); margin: 20px 0; }
</style>
