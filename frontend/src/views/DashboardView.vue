<template>
  <div class="discover">
    <div class="hero">
      <h1 class="hero-title">发现可构建的<br/>开源项目</h1>
      <p class="hero-sub">从全网技术讨论中，找到值得用 AI 构建的机会</p>
      <form class="hero-search" @submit.prevent="quickStart">
        <input v-model="keyword" placeholder="输入关键词，如 AI tools、developer tools..."
          class="search-input" />
        <button type="submit" class="search-btn" :disabled="starting">
          {{ starting ? '启动中...' : '开始发现' }}
        </button>
      </form>
      <div v-if="startMsg" class="start-msg">{{ startMsg }}</div>
    </div>

    <div v-if="error" class="error-banner"><span>{{ error }}</span><button class="retry-btn" @click="loadData">重试</button></div>
    <div v-if="loading && !error" class="loading-state"><div class="spinner"></div></div>

    <div v-if="!loading && !error" class="bento">
      <!-- Trending -->
      <div class="bento-card trending-card">
        <div class="card-head">
          <span class="card-dot tr"></span>
          <h2>今日趋势</h2>
        </div>
        <div v-if="trending.length === 0" class="card-empty">暂无，获取 GitHub Trending 显示</div>
        <div v-for="t in trending.slice(0,4)" :key="t.full_name" class="trend-row">
          <span class="trend-name">{{ t.full_name }}</span>
          <span class="trend-stars">★ {{ t.period_stars || t.stars || 0 }}</span>
        </div>
      </div>

      <!-- Top Opportunities -->
      <div class="bento-card opps-card">
        <div class="card-head">
          <span class="card-dot op"></span>
          <h2>高评分机会</h2>
          <router-link to="/opportunities" class="card-link">全部 →</router-link>
        </div>
        <div v-if="opportunities.length === 0" class="card-empty">运行管道后自动生成</div>
        <div v-for="o in opportunities.slice(0,3)" :key="o.id" class="opp-row"
          role="button" tabindex="0" @click="$router.push('/proposals/'+o.id)"
          @keydown.enter="$router.push('/proposals/'+o.id)"
          @keydown.space.prevent="$router.push('/proposals/'+o.id)">
          <div class="opp-score-ring" :class="o.scores.overall >= 80 ? 'high' : o.scores.overall >= 60 ? 'mid' : 'low'">
            {{ o.scores.overall }}
          </div>
          <div class="opp-info">
            <span class="opp-title">{{ o.title }}</span>
            <span class="opp-kw">{{ o.keyword }}</span>
          </div>
        </div>
      </div>

      <!-- Recent Requirements -->
      <div class="bento-card reqs-card">
        <div class="card-head">
          <span class="card-dot rq"></span>
          <h2>最新需求</h2>
        </div>
        <div v-if="requirements.length === 0" class="card-empty">先用关键词爬取讨论</div>
        <div v-for="r in requirements.slice(0,5)" :key="r.title" class="req-row"
          role="button" tabindex="0" @click="$router.push('/requirement-detail?path=' + encodeURIComponent(r.vault_path))"
          @keydown.enter="$router.push('/requirement-detail?path=' + encodeURIComponent(r.vault_path))">
          <span class="req-title">{{ r.title }}</span>
          <span class="req-platform">{{ r.source_platform }}</span>
        </div>
      </div>

      <!-- Recent Tasks -->
      <div class="bento-card tasks-card">
        <div class="card-head">
          <span class="card-dot tk"></span>
          <h2>最近任务</h2>
        </div>
        <div v-if="tasks.length === 0" class="card-empty">暂无</div>
        <div v-for="t in tasks.slice(0,5)" :key="t.id" class="task-row">
          <span class="task-status" :class="t.status">●</span>
          <span class="task-kw">{{ t.keyword }}</span>
          <span class="task-platform">{{ t.platform }}</span>
          <span class="task-num">{{ t.total_items }}条</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'

const router = useRouter()
const keyword = ref('')
const starting = ref(false)
const startMsg = ref('')
const error = ref('')
const loading = ref(true)
const trending = ref<any[]>([])
const opportunities = ref<any[]>([])
const requirements = ref<any[]>([])
const tasks = ref<any[]>([])

async function quickStart() {
  if (!keyword.value.trim() || starting.value) return
  starting.value = true; startMsg.value = ''
  try {
    const { data } = await api.post('/tasks', {
      keyword: keyword.value.trim(),
      platforms: ['github', 'stackoverflow', 'juejin'],
    })
    startMsg.value = `任务已创建！等待管道完成...`
    keyword.value = ''
    setTimeout(() => loadData(), 3000)
  } catch (e: any) {
    startMsg.value = '创建失败: ' + (e.response?.data?.detail || e.message)
  } finally { starting.value = false }
}

async function loadData() {
  loading.value = true
  try {
    const [tr, op, rq, tk] = await Promise.allSettled([
      api.get('/trending', { params: { page_size: 5 } }),
      api.get('/opportunities', { params: { page_size: 3, min_score: 50 } }),
      api.get('/requirements/summary'),
      api.get('/tasks', { params: { page_size: 5 } }),
    ])
    trending.value = tr.status === 'fulfilled' ? (tr.value.data.items || []) : []
    opportunities.value = op.status === 'fulfilled' ? (op.value.data.items || []) : []
    if (rq.status === 'fulfilled') {
      const rd = rq.value.data
      requirements.value = Array.isArray(rd) ? rd : (rd.requirements || rd.items || [])
    }
    tasks.value = tk.status === 'fulfilled' ? (tk.value.data.items || []) : []
  } catch (e) { error.value = '数据加载失败，请检查服务是否启动' } finally { loading.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.discover { max-width: 960px; margin: 0 auto; }
.hero { text-align: center; padding: 48px 0 40px; }
.hero-title { font-family: var(--font-display); font-size: 40px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.03em; line-height: 1.2; margin-bottom: 10px; }
.error-banner { display: flex; align-items: center; gap: 12px; padding: 16px 24px; background: var(--red-bg); color: var(--red); border: 1px solid rgba(251,113,133,0.2); border-radius: var(--radius-md); margin-bottom: 20px; }
.retry-btn { padding: 4px 12px; border-radius: 6px; border: 1px solid currentColor; background: transparent; color: inherit; cursor: pointer; font-family: inherit; }
.hero-sub { font-size: 16px; color: var(--text-muted); margin-bottom: 24px; }
.hero-search { display: flex; gap: 8px; max-width: 520px; margin: 0 auto; }
.search-input {
  flex: 1; padding: 12px 18px; border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle); background: var(--bg-elevated);
  color: var(--text-primary); font-size: 15px; font-family: inherit;
  transition: border-color 0.2s;
}
.search-input:focus { border-color: var(--accent); outline: none; }
.search-input::placeholder { color: var(--text-muted); }
.search-btn {
  padding: 12px 28px; border-radius: var(--radius-md); border: none;
  background: var(--accent); color: #0c0b0a; font-size: 14px; font-weight: 600;
  cursor: pointer; font-family: inherit; white-space: nowrap; transition: background 0.2s;
}
.search-btn:hover:not(:disabled) { background: #f7b955; }
.search-btn:disabled { opacity: 0.5; cursor: default; }
.start-msg { margin-top: 12px; font-size: 13px; color: var(--accent); }
.loading-state { display: flex; justify-content: center; padding: 60px; }
.spinner { width: 24px; height: 24px; border: 2px solid var(--border-subtle); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.bento { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.bento-card {
  background: var(--bg-surface); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); padding: 20px 24px;
  transition: border-color 0.2s, transform 0.15s;
}
.bento-card:hover { border-color: var(--border-hover); }
.card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.card-head h2 { font-family: var(--font-display); font-size: 14px; font-weight: 600; color: var(--text-primary); flex: 1; }
.card-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.card-dot.tr { background: #f59e0b; }
.card-dot.op { background: var(--accent); }
.card-dot.rq { background: #8b5cf6; }
.card-dot.tk { background: var(--green); }
.card-link { font-size: 12px; color: var(--accent); text-decoration: none; }
.card-link:hover { text-decoration: underline; }
.card-empty { font-size: 12px; color: var(--text-muted); padding: 12px 0; }

.trending-card { grid-column: 1; grid-row: 1 / 3; }
.trend-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-subtle); }
.trend-row:last-child { border-bottom: none; }
.trend-name { font-size: 13px; color: var(--text-secondary); font-family: monospace; }
.trend-stars { font-size: 12px; color: var(--amber); font-weight: 600; }

.opps-card { grid-column: 2; grid-row: 1; }
.opp-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; cursor: pointer; border-bottom: 1px solid var(--border-subtle); }
.opp-row:last-child { border-bottom: none; }
.opp-score-ring { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; flex-shrink: 0; border: 2px solid; }
.opp-score-ring.high { color: var(--green); border-color: var(--green); background: var(--green-bg); }
.opp-score-ring.mid { color: var(--amber); border-color: var(--amber); background: var(--amber-bg); }
.opp-score-ring.low { color: var(--text-muted); border-color: var(--text-muted); }
.opp-info { min-width: 0; }
.opp-title { font-size: 13px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
.opp-kw { font-size: 11px; color: var(--accent); }

.reqs-card { grid-column: 2; grid-row: 2; }
.req-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border-subtle); cursor: pointer; transition: color .15s; }
.req-row:hover { color: var(--teal-500); }
.req-row:last-child { border-bottom: none; }
.req-title { font-size: 12px; color: var(--text-secondary); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.req-platform { font-size: 11px; color: var(--text-muted); margin-left: 8px; flex-shrink: 0; }

.tasks-card { grid-column: 1 / 3; }
.task-row { display: flex; align-items: center; gap: 10px; padding: 5px 0; border-bottom: 1px solid var(--border-subtle); font-size: 13px; }
.task-row:last-child { border-bottom: none; }
.task-status { font-size: 10px; flex-shrink: 0; }
.task-status.completed { color: var(--green); }
.task-status.running { color: var(--amber); }
.task-status.failed { color: var(--red); }
.task-status.pending { color: var(--text-muted); }
.task-kw { color: var(--text-secondary); font-weight: 500; }
.task-platform { color: var(--text-muted); font-size: 11px; }
.task-num { margin-left: auto; color: var(--text-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
</style>
