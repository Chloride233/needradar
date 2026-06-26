<template>
  <div class="task-page" ref="pageRef">
    <!-- Hero Section — Create Task -->
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-orb hero-orb-1"></div>
        <div class="hero-orb hero-orb-2"></div>
        <div class="hero-orb hero-orb-3"></div>
      </div>
      <div class="hero-content">
        <div class="create-card glass-card" data-reveal="up">
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
            <div class="mode-toggle">
              <label class="toggle-label" :class="{ active: !agentMode }">
                <input type="radio" :value="false" v-model="agentMode" class="toggle-input" />
                自动模式
              </label>
              <label class="toggle-label" :class="{ active: agentMode }">
                <input type="radio" :value="true" v-model="agentMode" class="toggle-input" />
                Agent 模式
                <span class="agent-badge">质量门</span>
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
      </div>
    </section>

    <!-- Trending Suggestions -->
    <div class="suggest-card glass-card" data-reveal="up" data-delay="100">
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
        <span class="btn-spinner"></span> 正在获取热门选题...
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
    <div class="list-card glass-card" data-reveal="up" data-delay="200">
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
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-tertiary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>
        <p>暂无任务，试试上方的热门选题推荐</p>
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
      <div class="modal-content glass-card">
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
import { useReveal } from '../composables/useReveal'
import api from '../api/client'

marked.setOptions({ breaks: true, gfm: true })

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

const keyword = ref('')
const platforms = ref(['github', 'stackoverflow', 'juejin'])
const creating = ref(false)
const agentMode = ref(false)
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
  { label: 'B站', value: 'bilibili', color: '#fb7299' },
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
    const params: any = { keyword: keyword.value, platforms: platforms.value }
    if (agentMode.value) {
      params.mode = 'agent'
    }
    const resp = await api.post('/tasks?mode=' + (agentMode.value ? 'agent' : 'auto'), { keyword: keyword.value, platforms: platforms.value })
    keyword.value = ''
    // If agent mode, show gate review link
    if (agentMode.value && resp.data?.items?.length > 0) {
      // Find the pipeline run ID from the tasks
      // For now, just reload tasks
    }
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
/* ── Page Layout ── */
.task-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

/* ── Glass Card Base ── */
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple);
}

.glass-card:hover {
  box-shadow: var(--shadow-glass-hover);
}

/* ── Reveal Animations ── */
[data-reveal] {
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 0.6s var(--ease-apple), transform 0.6s var(--ease-apple);
}

[data-reveal="up"][data-revealed] {
  opacity: 1;
  transform: translateY(0);
}

[data-reveal][data-delay="100"] { transition-delay: 0.1s; }
[data-reveal][data-delay="200"] { transition-delay: 0.2s; }
[data-reveal][data-delay="300"] { transition-delay: 0.3s; }
[data-reveal][data-delay="400"] { transition-delay: 0.4s; }

/* ── Hero Section ── */
.hero {
  position: relative;
  overflow: hidden;
  padding: var(--space-8) 0 var(--space-4);
}

.hero-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
}

.hero-orb-1 {
  width: 320px;
  height: 320px;
  background: var(--color-primary);
  top: -60px;
  left: -40px;
  animation: orb-float 12s ease-in-out infinite;
}

.hero-orb-2 {
  width: 240px;
  height: 240px;
  background: var(--color-success);
  top: 20px;
  right: -30px;
  animation: orb-float 15s ease-in-out infinite reverse;
}

.hero-orb-3 {
  width: 180px;
  height: 180px;
  background: var(--color-warning);
  bottom: -40px;
  left: 40%;
  animation: orb-float 10s ease-in-out infinite 3s;
}

@keyframes orb-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, -15px) scale(1.05); }
  66% { transform: translate(-10px, 10px) scale(0.95); }
}

.hero-content {
  position: relative;
  z-index: 1;
}

/* ── Create Card ── */
.create-card {
  padding: var(--space-6);
}

.create-inner {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.create-input-area {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-tertiary);
  display: flex;
}

.search-input {
  width: 100%;
  height: 48px;
  padding: 0 14px 0 42px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--glass-border);
  font-size: 15px;
  font-family: inherit;
  color: var(--color-text);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  outline: none;
  transition: border-color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.search-input::placeholder { color: var(--color-text-tertiary); }
.search-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.12);
}

.platform-checks {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.platform-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  color: var(--color-text-secondary);
  transition: border-color var(--duration-normal) var(--ease-apple), background var(--duration-normal) var(--ease-apple), color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.chip-input { display: none; }

.chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  opacity: 0.4;
  transition: opacity var(--duration-normal) var(--ease-apple);
}

.platform-chip.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.1);
}

.platform-chip.active .chip-dot { opacity: 1; }

.mode-toggle {
  display: flex;
  gap: 4px;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border-radius: var(--radius-md);
  padding: 4px;
  border: 1px solid var(--glass-border);
}

.toggle-label {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: background var(--duration-normal) var(--ease-apple), color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.toggle-label.active {
  background: var(--color-bg);
  color: var(--color-text);
  font-weight: 500;
  box-shadow: var(--shadow-sm);
}

.toggle-input { display: none; }

.agent-badge {
  font-size: 10px;
  background: var(--color-warning-bg);
  color: var(--color-warning);
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.create-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0 var(--space-6);
  height: 48px;
  border-radius: var(--radius-lg);
  border: none;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  background: var(--color-primary);
  cursor: pointer;
  transition: background var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple);
  white-space: nowrap;
}

.create-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.create-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Suggestions ── */
.suggest-card {
  padding: var(--space-5) var(--space-6);
}

.suggest-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.suggest-title {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.suggest-title svg { color: var(--color-primary); }

.suggest-refresh {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-apple), color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.suggest-refresh:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.08);
}
.suggest-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

.suggest-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-5);
  color: var(--color-text-secondary);
  font-size: 13px;
}

.suggest-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: var(--space-3);
}

.suggest-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  cursor: pointer;
  transition: background var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple);
  gap: var(--space-3);
}

.suggest-item:hover {
  background: var(--color-bg);
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.suggest-item-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.suggest-desc {
  display: block;
  font-size: 11px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.suggest-item-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.suggest-heat {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-warning);
}

.suggest-action {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  border: 1px solid transparent;
  transition: background var(--duration-normal) var(--ease-apple), color var(--duration-normal) var(--ease-apple);
}

.suggest-item:hover .suggest-action {
  background: var(--color-primary);
  color: #fff;
}

.suggest-empty {
  text-align: center;
  padding: var(--space-3);
}

.suggest-fetch-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-primary);
  background: var(--color-primary-bg);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: var(--color-primary);
  cursor: pointer;
  transition: background var(--duration-normal) var(--ease-apple), color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.suggest-fetch-btn:hover {
  background: var(--color-primary);
  color: #fff;
  box-shadow: var(--shadow-md);
}

/* ── Task List ── */
.list-card {
  padding: var(--space-5) var(--space-6);
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.list-title {
  font-family: var(--font-sans);
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.list-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  padding: 3px 10px;
  border-radius: 6px;
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: 12px;
  color: var(--color-success);
  font-weight: 500;
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(52, 199, 89, 0.4); }
  50% { box-shadow: 0 0 0 5px rgba(52, 199, 89, 0); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-7) 0;
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  transition: background var(--duration-normal) var(--ease-apple), border-color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple);
}

.task-item:hover {
  background: var(--color-bg);
  border-color: var(--color-border);
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-1px);
}

.task-item.task-running {
  background: rgba(0, 122, 255, 0.05);
  border-color: rgba(0, 122, 255, 0.2);
}

.task-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.task-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-pending { background: var(--color-text-tertiary); }
.dot-running { background: var(--color-primary); animation: pulse 1.5s ease-in-out infinite; }
.dot-completed { background: var(--color-success); }
.dot-failed { background: var(--color-danger); }

.task-keyword {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.task-meta {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 3px;
}

.meta-sep { color: var(--color-border); }

.task-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.task-badge {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
}

.badge-pending { background: var(--color-bg-tertiary); color: var(--color-text-secondary); }
.badge-running { background: var(--color-primary-bg); color: var(--color-primary); }
.badge-completed { background: var(--color-success-bg); color: var(--color-success); }
.badge-failed { background: var(--color-danger-bg); color: var(--color-danger); }

.task-items {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 500;
}

.task-items.skip {
  color: var(--color-text-tertiary);
}

.task-elapsed {
  font-size: 12px;
  font-family: var(--font-sans);
  font-weight: 500;
}

.task-elapsed.running { color: var(--color-warning); }
.task-elapsed.done { color: var(--color-text-tertiary); }

/* ── Report Link ── */
.report-link-btn {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-primary);
  background: var(--color-primary-bg);
  font-size: 11px;
  font-weight: 600;
  font-family: inherit;
  color: var(--color-primary);
  cursor: pointer;
  transition: background var(--duration-normal) var(--ease-apple), color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
}

.report-link-btn:hover {
  background: var(--color-primary);
  color: #fff;
  box-shadow: var(--shadow-md);
}

/* ── Report Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fade-in 0.2s var(--ease-apple);
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-content {
  width: 700px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  padding: 0;
  animation: modal-in 0.3s var(--ease-apple);
}

@keyframes modal-in {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
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
  transition: color var(--duration-normal) var(--ease-apple);
}

.modal-close:hover { color: var(--color-text); }

.modal-body {
  padding: var(--space-6);
  overflow-y: auto;
  flex: 1;
}

.report-markdown {
  font-size: 14px;
  line-height: 1.8;
  color: var(--color-text-secondary);
}

.report-markdown :deep(h1) { font-family: var(--font-sans); font-size: 20px; font-weight: 700; color: var(--color-text); margin-bottom: var(--space-4); }
.report-markdown :deep(h2) { font-family: var(--font-sans); font-size: 16px; font-weight: 600; color: var(--color-text); margin: var(--space-5) 0 var(--space-3); padding-bottom: var(--space-2); border-bottom: 1px solid var(--glass-border); }
.report-markdown :deep(h3) { font-family: var(--font-sans); font-size: 14px; font-weight: 600; color: var(--color-text); margin: var(--space-4) 0 var(--space-2); }
.report-markdown :deep(strong) { color: var(--color-text); }
.report-markdown :deep(li) { list-style: disc; margin-left: 20px; margin-bottom: 4px; }
.report-markdown :deep(table) { width: 100%; border-collapse: collapse; margin: var(--space-4) 0; font-size: 13px; }
.report-markdown :deep(th) { padding: 8px 12px; text-align: left; background: var(--glass-bg); border-bottom: 1px solid var(--glass-border); font-weight: 600; color: var(--color-text); }
.report-markdown :deep(td) { padding: 8px 12px; border-bottom: 1px solid var(--glass-border); text-align: left; }
.report-markdown :deep(blockquote) { border-left: 3px solid var(--color-primary); padding: var(--space-2) var(--space-4); margin: var(--space-3) 0; background: var(--glass-bg); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; }
.report-markdown :deep(p) { margin-bottom: var(--space-2); }
.report-markdown :deep(ul), .report-markdown :deep(ol) { padding-left: var(--space-5); margin-bottom: var(--space-3); }
.report-markdown :deep(hr) { border: none; border-top: 1px solid var(--glass-border); margin: var(--space-5) 0; }
</style>
