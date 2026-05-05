<template>
  <div class="scheduler-page">
    <!-- Create Job -->
    <div class="create-card">
      <div class="create-header">
        <h3 class="section-label">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          新建定时任务
        </h3>
      </div>
      <div class="create-body">
        <div class="form-row">
          <div class="form-group flex1">
            <label class="form-label">任务名称</label>
            <input v-model="form.name" class="form-input" placeholder="如：每日 AI 工具需求监控…" aria-label="任务名称" />
          </div>
          <div class="form-group flex1">
            <label class="form-label">搜索关键词</label>
            <input v-model="form.keyword" class="form-input" placeholder="输入关键词…" aria-label="搜索关键词" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">采集平台</label>
            <div class="platform-checks">
              <label v-for="p in platformList" :key="p.value" class="platform-chip" :class="{ active: form.platforms.includes(p.value) }">
                <input type="checkbox" :value="p.value" v-model="form.platforms" class="chip-input" />
                <span class="chip-dot" :style="{ background: p.color }"></span>
                {{ p.label }}
              </label>
            </div>
          </div>
          <div class="form-group interval-group">
            <label class="form-label">执行间隔</label>
            <div class="interval-input-wrap">
              <span>每</span>
              <input v-model.number="form.interval_minutes" type="number" min="10" max="10080" class="form-input interval-input" />
              <span>分钟</span>
            </div>
            <div class="interval-presets">
              <button v-for="preset in presets" :key="preset.value" class="preset-btn" :class="{ active: form.interval_minutes === preset.value }" @click="form.interval_minutes = preset.value">
                {{ preset.label }}
              </button>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button class="create-btn" :class="{ loading: creating }" @click="createJob" :disabled="creating || !form.name || !form.keyword">
            <svg v-if="!creating" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            <span v-else class="btn-spinner"></span>
            {{ creating ? '创建中...' : '创建定时任务' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Job List -->
    <div class="list-card">
      <div class="list-header">
        <h3 class="list-title">
          定时任务列表
          <span class="list-count">{{ jobs.length }} 个任务</span>
        </h3>
      </div>

      <div v-if="jobs.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        <p>暂无定时任务，创建一个自动挖掘任务吧</p>
      </div>

      <div v-else class="job-list">
        <div v-for="job in jobs" :key="job.id" class="job-item" :class="'job-' + job.status">
          <div class="job-left">
            <div class="job-status-dot" :class="'dot-' + job.status"></div>
            <div class="job-info">
              <div class="job-name">{{ job.name }}</div>
              <div class="job-meta">
                <span class="meta-keyword">{{ job.keyword }}</span>
                <span class="meta-sep">·</span>
                <span class="meta-platforms">{{ formatPlatforms(job.platforms) }}</span>
                <span class="meta-sep">·</span>
                <span>每 {{ job.interval_minutes }} 分钟</span>
              </div>
              <div class="job-stats">
                <span class="stat-item">已执行 {{ job.run_count }} 次</span>
                <span v-if="job.last_run_at" class="stat-item last-run">上次: {{ formatTime(job.last_run_at) }}</span>
              </div>
            </div>
          </div>
          <div class="job-right">
            <span class="job-badge" :class="'badge-' + job.status">
              {{ job.status === 'active' ? '运行中' : '已暂停' }}
            </span>
            <button class="action-btn trigger" @click="triggerJob(job)" title="立即执行" aria-label="立即执行">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </button>
            <button class="action-btn toggle" @click="toggleJob(job)" :title="job.status === 'active' ? '暂停' : '恢复'" :aria-label="job.status === 'active' ? '暂停' : '恢复'">
              <svg v-if="job.status === 'active'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <line x1="6" y1="4" x2="6" y2="20"/><line x1="18" y1="4" x2="18" y2="20"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </button>
            <button class="action-btn delete" @click="confirmDeleteJob(job)" title="删除" aria-label="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
    <!-- Delete Confirmation Modal -->
    <div v-if="pendingDelete" class="modal-overlay" @click.self="pendingDelete = null" role="dialog" aria-modal="true" aria-label="确认删除">
      <div class="modal-card">
        <div class="modal-head">
          <h3>确认删除</h3>
          <button class="modal-close" @click="pendingDelete = null" aria-label="关闭">&times;</button>
        </div>
        <div class="modal-body">
          <p>确定删除定时任务「{{ pendingDelete.name }}」？此操作不可撤销。</p>
          <div class="modal-actions">
            <button class="action-btn btn-secondary" @click="pendingDelete = null">取消</button>
            <button class="action-btn btn-danger" @click="deleteJob">确认删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import api from '../api/client'

const message = useMessage()

const creating = ref(false)

const form = ref({
  name: '',
  keyword: '',
  platforms: ['github', 'stackoverflow', 'juejin'],
  interval_minutes: 60,
})

const platformList = [
  { label: 'GitHub', value: 'github', color: '#24292f' },
  { label: 'Stack Overflow', value: 'stackoverflow', color: '#f48024' },
  { label: '掘金', value: 'juejin', color: '#0d9488' },
]

const presets = [
  { label: '10分钟', value: 10 },
  { label: '30分钟', value: 30 },
  { label: '1小时', value: 60 },
  { label: '6小时', value: 360 },
  { label: '12小时', value: 720 },
  { label: '每天', value: 1440 },
]

interface ScheduledJob {
  id: number
  name: string
  keyword: string
  platforms: string[]
  interval_minutes: number
  status: 'active' | 'paused'
  last_run_at: string | null
  last_task_ids: number[] | null
  run_count: number
  created_at: string
  updated_at: string | null
}

const jobs = ref<ScheduledJob[]>([])
const pendingDelete = ref<ScheduledJob | null>(null)

function formatPlatforms(platforms: string[]): string {
  const map: Record<string, string> = { github: 'GitHub', stackoverflow: 'SO', juejin: '掘金' }
  return platforms.map(p => map[p] || p).join(' / ')
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

async function loadJobs() {
  try {
    const { data } = await api.get('/scheduler')
    jobs.value = data.items
  } catch { /* handled by interceptor */ }
}

async function createJob() {
  if (!form.value.name || !form.value.keyword) return
  creating.value = true
  try {
    await api.post('/scheduler', form.value)
    message.success('定时任务已创建')
    form.value = { name: '', keyword: '', platforms: ['github', 'stackoverflow', 'juejin'], interval_minutes: 60 }
    await loadJobs()
  } finally {
    creating.value = false
  }
}

async function triggerJob(job: ScheduledJob) {
  try {
    await api.post(`/scheduler/${job.id}/trigger`)
    message.success(`已触发「${job.name}」`)
    await loadJobs()
  } catch { /* handled by interceptor */ }
}

async function toggleJob(job: ScheduledJob) {
  const newStatus = job.status === 'active' ? 'paused' : 'active'
  try {
    await api.patch(`/scheduler/${job.id}`, { status: newStatus })
    message.success(newStatus === 'active' ? '任务已恢复' : '任务已暂停')
    await loadJobs()
  } catch { /* handled by interceptor */ }
}

async function confirmDeleteJob(job: ScheduledJob) {
  pendingDelete.value = job
}

async function deleteJob() {
  const job = pendingDelete.value
  if (!job) return
  try {
    await api.delete(`/scheduler/${job.id}`)
    message.success('已删除')
    pendingDelete.value = null
    await loadJobs()
  } catch { /* handled by interceptor */ }
}

onMounted(loadJobs)
</script>

<style scoped>
.scheduler-page {
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

.create-header {
  margin-bottom: 18px;
}

.section-label {
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--slate-700);
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-label svg { color: var(--teal-500); }

.create-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group.flex1 { flex: 1; }

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--slate-500);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.form-input {
  height: 40px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1.5px solid var(--slate-200);
  font-size: 14px;
  font-family: inherit;
  color: var(--slate-800);
  background: var(--slate-50);
  outline: none;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.form-input::placeholder { color: var(--slate-400); }
.form-input:focus {
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

.interval-group { min-width: 260px; }

.interval-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--slate-500);
}

.interval-input {
  width: 80px;
  text-align: center;
}

.interval-presets {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.preset-btn {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--slate-200);
  background: var(--slate-50);
  font-size: 11px;
  font-weight: 500;
  font-family: inherit;
  color: var(--slate-500);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.preset-btn:hover { border-color: var(--teal-300); color: var(--teal-600); }
.preset-btn.active { background: var(--teal-50); border-color: var(--teal-400); color: var(--teal-700); }

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.create-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 24px;
  height: 40px;
  border-radius: 10px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  background: linear-gradient(135deg, var(--teal-500), var(--teal-700));
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.create-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(20, 196, 166, 0.25);
}

.create-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Job List ── */
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

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
  color: var(--slate-400);
  font-size: 14px;
}

.job-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.job-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-radius: 12px;
  background: var(--slate-50);
  border: 1px solid transparent;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.job-item:hover {
  background: #141414;
  border-color: var(--slate-200);
  border-color: var(--card-border-hover);
}

.job-item.job-active {
  background: rgba(13, 148, 136, 0.03);
  border-color: rgba(13, 148, 136, 0.1);
}

.job-left {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.job-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
}

.dot-active { background: var(--teal-500); animation: pulse 2s ease-in-out infinite; }
.dot-paused { background: var(--slate-300); }

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(13,148,136,0.4); }
  50% { box-shadow: 0 0 0 5px rgba(13,148,136,0); }
}

.job-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-800);
}

.job-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--slate-400);
  margin-top: 4px;
}

.meta-keyword {
  font-weight: 500;
  color: var(--slate-500);
}

.meta-sep { color: var(--slate-300); }

.job-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--slate-400);
}

.job-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.job-badge {
  padding: 4px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
}

.badge-active { background: rgba(13,148,136,0.1); color: var(--teal-700); }
.badge-paused { background: var(--slate-100); color: var(--slate-500); }

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--slate-200);
  background: #141414;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
  color: var(--slate-400);
}

.action-btn:hover { border-color: var(--teal-300); color: var(--teal-600); background: var(--teal-50); }
.action-btn.delete:hover { border-color: #fca5a5; color: #ef4444; background: var(--error-bg); }

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

.modal-card {
  background: #141414;
  border-radius: 16px;
  width: 400px;
  max-width: 90vw;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--slate-100);
}

.modal-head h3 {
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
}

.modal-body p {
  font-size: 14px;
  color: var(--slate-600);
  line-height: 1.6;
  margin-bottom: 20px;
}

.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.btn-secondary {
  padding: 8px 18px;
  border-radius: 10px;
  border: 1.5px solid var(--slate-200);
  background: var(--slate-50);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: var(--slate-600);
  cursor: pointer;
}

.btn-danger {
  padding: 8px 18px;
  border-radius: 10px;
  border: none;
  background: #ef4444;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  cursor: pointer;
}

.btn-danger:hover { background: #dc2626; }
</style>
