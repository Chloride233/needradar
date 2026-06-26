<template>
  <div class="scheduler-page" ref="pageRef">
    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-orb hero-orb-1"></div>
        <div class="hero-orb hero-orb-2"></div>
      </div>
      <div class="hero-content">
        <div class="hero-icon" data-reveal="up">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <h1 class="hero-title" data-reveal="up" data-delay="100">定时任务调度</h1>
        <p class="hero-sub" data-reveal="up" data-delay="200">创建自动化采集任务，定时从多个平台挖掘需求，让洞察永不停歇。</p>
      </div>
    </section>

    <!-- Create Job -->
    <div class="create-card" data-reveal="up" data-delay="100">
      <div class="create-header">
        <h3 class="section-label">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
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
    <div class="list-card" data-reveal="up" data-delay="200">
      <div class="list-header">
        <h3 class="list-title">
          定时任务列表
          <span class="list-count">{{ jobs.length }} 个任务</span>
        </h3>
      </div>

      <div v-if="jobs.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        <p>暂无定时任务，创建一个自动挖掘任务吧</p>
      </div>

      <div v-else class="job-list">
        <div v-for="(job, idx) in jobs" :key="job.id" class="job-item" :class="'job-' + job.status" data-reveal="up" :data-delay="(idx + 1) * 100">
          <div class="job-left">
            <div class="job-status-dot" :class="'dot-' + job.status"></div>
            <div class="job-info">
              <div class="job-name">{{ job.name }}</div>
              <div class="job-meta">
                <span class="meta-keyword">{{ job.keyword }}</span>
                <span class="meta-sep">&middot;</span>
                <span class="meta-platforms">{{ formatPlatforms(job.platforms) }}</span>
                <span class="meta-sep">&middot;</span>
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
            <button class="modal-btn btn-secondary" @click="pendingDelete = null">取消</button>
            <button class="modal-btn btn-danger" @click="deleteJob">确认删除</button>
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
import { useReveal } from '../composables/useReveal'

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

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
  { label: 'B站', value: 'bilibili', color: '#fb7299' },
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
  const map: Record<string, string> = { github: 'GitHub', stackoverflow: 'SO', juejin: '掘金', bilibili: 'B站' }
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
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
  gap: var(--space-5);
}

/* ── Hero Section ── */
.hero {
  position: relative;
  padding: var(--space-8) 0 var(--space-7);
  overflow: hidden;
}

.hero-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
  animation: float 8s ease-in-out infinite;
}

.hero-orb-1 {
  width: 320px;
  height: 320px;
  background: var(--color-primary);
  top: -60px;
  left: -40px;
  opacity: 0.18;
  animation-delay: 0s;
}

.hero-orb-2 {
  width: 240px;
  height: 240px;
  background: var(--color-secondary);
  bottom: -40px;
  right: -20px;
  opacity: 0.14;
  animation-delay: -3s;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.hero-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-glass);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-5);
}

.hero-title {
  font-family: var(--font-sans);
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
  margin: 0 0 var(--space-3) 0;
}

.hero-sub {
  font-size: 15px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin: 0;
  max-width: 520px;
}

/* ── Create Card ── */
.create-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-6);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.create-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.create-header {
  margin-bottom: var(--space-5);
}

.section-label {
  font-family: var(--font-sans);
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.section-label svg {
  color: var(--color-primary);
}

.create-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-row {
  display: flex;
  gap: var(--space-4);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group.flex1 {
  flex: 1;
}

.form-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.form-input {
  height: 40px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  font-size: 13px;
  font-family: var(--font-sans);
  color: var(--color-text);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(12px);
  outline: none;
  box-sizing: border-box;
  transition: border-color var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple),
              background var(--duration-normal) var(--ease-apple);
}

.form-input::placeholder {
  color: var(--color-text-tertiary);
}

.form-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15);
  background: var(--color-bg);
}

.platform-checks {
  display: flex;
  gap: var(--space-2);
}

.platform-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-border-light);
  color: var(--color-text-secondary);
  transition: border-color var(--duration-normal) var(--ease-apple),
              background var(--duration-normal) var(--ease-apple),
              color var(--duration-normal) var(--ease-apple);
}

.chip-input {
  display: none;
}

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
}

.platform-chip.active .chip-dot {
  opacity: 1;
}

.interval-group {
  min-width: 260px;
}

.interval-input-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 14px;
  color: var(--color-text-secondary);
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
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(8px);
  font-size: 11px;
  font-weight: 500;
  font-family: var(--font-sans);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-apple),
              color var(--duration-fast) var(--ease-apple),
              background var(--duration-fast) var(--ease-apple);
}

.preset-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.preset-btn.active {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.create-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-6);
  height: 44px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-sans);
  color: #fff;
  background: var(--gradient-accent);
  cursor: pointer;
  transition: transform var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple);
}

.create-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(0, 122, 255, 0.3);
}

.create-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Job List ── */
.list-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-6);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.list-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}

.list-title {
  font-family: var(--font-sans);
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.list-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(8px);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--glass-border);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: 48px 0;
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.empty-state svg {
  color: var(--color-border-light);
}

.job-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.job-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(12px);
  border: 1px solid var(--color-border-light);
  transition: border-color var(--duration-normal) var(--ease-apple),
              background var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.job-item:hover {
  background: var(--glass-bg);
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-1px);
  border-color: var(--glass-border);
}

.job-item.job-active {
  background: var(--color-success-bg);
  border-color: rgba(52, 199, 89, 0.2);
}

.job-left {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
}

.job-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
}

.dot-active {
  background: var(--color-success);
  animation: pulse 2s ease-in-out infinite;
}

.dot-paused {
  background: var(--color-border);
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(52, 199, 89, 0.4); }
  50% { box-shadow: 0 0 0 5px rgba(52, 199, 89, 0); }
}

.job-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.job-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.meta-keyword {
  font-weight: 500;
  color: var(--color-text-secondary);
}

.meta-sep {
  color: var(--color-border-light);
}

.job-stats {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: 6px;
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.job-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.job-badge {
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
}

.badge-active {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.badge-paused {
  background: var(--glass-bg-heavy);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-light);
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-apple),
              color var(--duration-normal) var(--ease-apple),
              background var(--duration-normal) var(--ease-apple),
              transform var(--duration-fast) var(--ease-apple);
  color: var(--color-text-secondary);
}

.action-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-bg);
  transform: scale(1.05);
}

.action-btn.delete:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
  background: var(--color-danger-bg);
}

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
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

.modal-card {
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(var(--glass-blur-heavy));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  width: 400px;
  max-width: 90vw;
  box-shadow: var(--shadow-float);
  animation: modal-in 0.3s var(--ease-apple);
}

@keyframes modal-in {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--color-border-light);
}

.modal-head h3 {
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
}

.modal-close:hover {
  color: var(--color-text);
}

.modal-body {
  padding: var(--space-6);
}

.modal-body p {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-5);
}

.modal-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
}

.modal-btn {
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-sans);
  cursor: pointer;
  transition: background var(--duration-normal) var(--ease-apple),
              border-color var(--duration-normal) var(--ease-apple),
              transform var(--duration-fast) var(--ease-apple);
}

.modal-btn:hover {
  transform: translateY(-1px);
}

.btn-secondary {
  border: 1px solid var(--color-border);
  background: var(--glass-bg-heavy);
  color: var(--color-text-secondary);
}

.btn-secondary:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-text-tertiary);
}

.btn-danger {
  border: none;
  background: var(--color-danger);
  color: #fff;
}

.btn-danger:hover {
  box-shadow: 0 4px 12px rgba(255, 59, 48, 0.3);
}
</style>
