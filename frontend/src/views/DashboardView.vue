<template>
  <div class="dashboard" ref="pageRef">
    <!-- Hero — Compact Agent Command Center Header -->
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-orb hero-orb-1"></div>
        <div class="hero-orb hero-orb-2"></div>
      </div>
      <div class="hero-content">
        <div class="hero-badge" data-reveal="up">
          <span class="badge-dot" :class="{ pulse: activeRunCount > 0 }"></span>
          <span>Agent 指挥中心</span>
        </div>
        <h1 class="hero-title" data-reveal="up" data-delay="50">
          {{ heroHeadline }}
        </h1>
        <p class="hero-sub" data-reveal="up" data-delay="100">
          {{ heroSubtext }}
        </p>
      </div>
    </section>

    <!-- Quick Start (compact, secondary) -->
    <section class="quick-start" data-reveal="up" data-delay="150">
      <form class="quick-start-form" @submit.prevent="quickStart">
        <div class="search-glass">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            v-model="keyword"
            placeholder="输入关键词启动 Agent 管道..."
            class="search-input"
          />
          <button type="submit" class="search-btn" :disabled="starting">
            {{ starting ? '启动中...' : '启动' }}
          </button>
        </div>
      </form>
      <p v-if="startMsg" class="start-msg">{{ startMsg }}</p>
    </section>

    <!-- Error -->
    <div v-if="agentError" class="error-banner" data-reveal="up">
      <span>{{ agentError }}</span>
      <button class="retry-btn" @click="fetchStatus">重试</button>
    </div>

    <!-- Loading -->
    <div v-if="agentLoading && !status" class="loading-state">
      <div class="spinner"></div>
    </div>

    <!-- Agent 3-Section Layout -->
    <div v-if="status" class="agent-grid">
      <!-- Section 1: Active Runs -->
      <section class="agent-section section-runs" data-reveal="up" data-delay="200">
        <div class="section-header">
          <div class="section-title-group">
            <div class="section-icon section-icon--blue">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </div>
            <h2 class="section-title">活跃管道</h2>
          </div>
          <span class="section-count" v-if="status.active_runs.length">{{ status.active_runs.length }}</span>
        </div>
        <div v-if="status.active_runs.length === 0" class="section-empty">
          <div class="empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          </div>
          <span>暂无运行中的管道</span>
          <span class="empty-hint">使用上方搜索启动一个</span>
        </div>
        <div v-else class="run-list">
          <div
            v-for="run in status.active_runs"
            :key="run.id"
            class="run-card"
            :class="{ 'run-paused': run.status === 'paused' }"
          >
            <div class="run-header">
              <span class="run-keyword">{{ run.keyword }}</span>
              <span class="run-status-badge" :class="run.status">
                {{ statusLabel(run.status) }}
              </span>
            </div>
            <div class="run-phase" v-if="run.current_phase">
              <span class="phase-label">当前阶段</span>
              <span class="phase-value">{{ phaseLabel(run.current_phase) }}</span>
            </div>
            <div class="run-progress">
              <div class="progress-track">
                <div
                  class="progress-fill"
                  :style="{ width: progressPercent(run) + '%' }"
                  :class="{ 'progress-paused': run.status === 'paused' }"
                ></div>
              </div>
              <span class="progress-text">{{ progressPercent(run) }}%</span>
            </div>
            <div class="run-stages" v-if="run.stages.length">
              <span
                v-for="(stage, i) in run.stages"
                :key="i"
                class="stage-chip"
                :class="stageChipClass(run, i)"
              >{{ stage }}</span>
            </div>
            <div class="run-actions" v-if="run.status === 'paused' && run.gate_status === 'awaiting_review'">
              <button class="action-btn action-btn--primary" @click="goToGate(run.id)">
                前往审查
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Section 2: Action Required (Pending Gates) -->
      <section class="agent-section section-gates" data-reveal="up" data-delay="300">
        <div class="section-header">
          <div class="section-title-group">
            <div class="section-icon section-icon--amber">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <h2 class="section-title">待审质量门</h2>
          </div>
          <span class="section-count section-count--urgent" v-if="status.pending_gates.length">
            {{ status.pending_gates.length }}
          </span>
        </div>
        <div v-if="status.pending_gates.length === 0" class="section-empty">
          <div class="empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          </div>
          <span>所有质量门已通过</span>
          <span class="empty-hint">Agent 将在需要时暂停等待审查</span>
        </div>
        <div v-else class="gate-list">
          <div
            v-for="gate in status.pending_gates"
            :key="gate.id"
            class="gate-card"
            role="button"
            tabindex="0"
            @click="goToGate(gate.pipeline_run_id)"
            @keydown.enter="goToGate(gate.pipeline_run_id)"
          >
            <div class="gate-header">
              <span class="gate-type-badge" :class="gate.gate_type">
                {{ gateTypeLabel(gate.gate_type) }}
              </span>
              <span class="gate-items">{{ gate.items_count }} 项待审</span>
            </div>
            <div class="gate-keyword" v-if="gate.keyword">
              关键词: {{ gate.keyword }}
            </div>
            <div class="gate-action">
              <span class="gate-action-text">点击前往审查</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
          </div>
        </div>
      </section>

      <!-- Section 3: Recent Activity -->
      <section class="agent-section section-activity" data-reveal="up" data-delay="400">
        <div class="section-header">
          <div class="section-title-group">
            <div class="section-icon section-icon--green">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            </div>
            <h2 class="section-title">最近完成</h2>
          </div>
        </div>
        <div v-if="status.recent_completed.length === 0" class="section-empty">
          <div class="empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/></svg>
          </div>
          <span>暂无完成记录</span>
        </div>
        <div v-else class="activity-list">
          <div
            v-for="run in status.recent_completed"
            :key="run.id"
            class="activity-item"
          >
            <div class="activity-dot"></div>
            <div class="activity-info">
              <span class="activity-keyword">{{ run.keyword }}</span>
              <span class="activity-meta">
                <span v-if="run.is_agent_mode" class="agent-mode-tag">Agent</span>
                {{ formatTime(run.updated_at) }}
              </span>
            </div>
            <button class="activity-link" @click="$router.push('/reports')">查看报告</button>
          </div>
        </div>
      </section>
    </div>

    <!-- Stats Bar (bottom) -->
    <div v-if="status" class="stats-bar" data-reveal="up" data-delay="500">
      <div class="stat-item">
        <span class="stat-number">{{ status.stats.total_runs }}</span>
        <span class="stat-label">总管道数</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-number">{{ status.stats.approved_gates }}</span>
        <span class="stat-label">已通过门</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-number">{{ status.stats.rejected_gates }}</span>
        <span class="stat-label">已驳回门</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-number">{{ status.stats.pending_gates_count }}</span>
        <span class="stat-label">待审门</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useReveal } from '../composables/useReveal'
import { useAgent } from '../composables/useAgent'
import api from '../api/client'

const router = useRouter()
const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

const { status, loading: agentLoading, error: agentError, activeRunCount, fetchStatus } = useAgent()

// Re-trigger reveal after agent data loads (v-if delayed elements miss initial observer)
watch(status, (val) => {
  if (val) {
    nextTick(() => {
      pageRef.value?.querySelectorAll('[data-reveal]:not([data-revealed])').forEach((el) => {
        el.setAttribute('data-revealed', '')
      })
    })
  }
})

const keyword = ref('')
const starting = ref(false)
const startMsg = ref('')
const platforms = ref<string[]>([])

// Fetch available platforms once
api.get('/tasks/platforms').then(({ data }) => {
  platforms.value = (data.platforms || []).map((p: any) => typeof p === 'string' ? p : p.value)
}).catch(() => { platforms.value = ['github', 'stackoverflow', 'juejin'] })

// ── Hero dynamic text ──
const heroHeadline = computed(() => {
  if (!status.value) return 'Agent 指挥中心'
  const ar = status.value.active_runs.length
  const pg = status.value.pending_gates.length
  if (pg > 0) return `${pg} 个质量门等待审查`
  if (ar > 0) return `${ar} 条管道正在运行`
  return '一切就绪，等待指令'
})

const heroSubtext = computed(() => {
  if (!status.value) return '加载中...'
  const pg = status.value.pending_gates.length
  if (pg > 0) return 'Agent 已暂停，需要你确认后继续推进'
  const ar = status.value.active_runs.length
  if (ar > 0) return 'Agent 正在自主推进管道，完成后将通知你'
  return '输入关键词，让 Agent 开始挖掘需求'
})

// ── Phase progress (must match backend PhaseName enum) ──
const PHASE_ORDER = ['crawling', 'extracting', 'reporting', 'archiving', 'distilling', 'completed']

function progressPercent(run: { current_phase: string | null; stages: string[] }): number {
  if (!run.current_phase) return 0
  const idx = PHASE_ORDER.indexOf(run.current_phase)
  if (idx < 0) return 0
  return Math.round(((idx + 1) / PHASE_ORDER.length) * 100)
}

function stageChipClass(run: { current_phase: string | null }, index: number) {
  const currentIdx = PHASE_ORDER.indexOf(run.current_phase || '')
  if (index < currentIdx) return 'stage-done'
  if (index === currentIdx) return 'stage-active'
  return 'stage-pending'
}

// ── Labels ──
function statusLabel(s: string): string {
  const map: Record<string, string> = { running: '运行中', paused: '已暂停', completed: '已完成', failed: '失败' }
  return map[s] || s
}

function phaseLabel(p: string): string {
  const map: Record<string, string> = {
    crawling: '素材爬取', extracting: '需求提取', reporting: '洞察报告',
    archiving: '归档', distilling: '知识沉淀', completed: '已完成',
    material_gate: '素材确认门', requirement_gate: '需求确认门', insight_gate: '洞察确认门',
  }
  return map[p] || p
}

function gateTypeLabel(t: string): string {
  const map: Record<string, string> = { material: '素材确认', requirement: '需求确认', insight: '洞察确认' }
  return map[t] || t
}

function formatTime(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

// ── Navigation ──
function goToGate(runId: number) {
  router.push(`/gates/${runId}`)
}

// ── Quick start ──
async function quickStart() {
  if (!keyword.value.trim() || starting.value) return
  starting.value = true
  startMsg.value = ''
  try {
    await api.post('/tasks?mode=agent', {
      keyword: keyword.value.trim(),
      platforms: platforms.value.length ? platforms.value : ['github', 'stackoverflow', 'juejin'],
    })
    startMsg.value = 'Agent 管道已启动！'
    keyword.value = ''
    setTimeout(() => fetchStatus(), 2000)
  } catch (e: any) {
    startMsg.value = '启动失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    starting.value = false
  }
}
</script>

<style scoped>
.dashboard {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ── Hero (compact) ── */
.hero {
  position: relative;
  padding: var(--space-7) 0 var(--space-5);
  overflow: hidden;
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
  left: 30%;
}

.hero-orb-2 {
  width: 250px;
  height: 250px;
  background: rgba(88, 86, 214, 0.08);
  top: 10%;
  right: 20%;
  animation-delay: -3s;
}

.hero-content {
  position: relative;
  text-align: center;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary);
  letter-spacing: 0.02em;
  margin-bottom: var(--space-3);
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  transition: background var(--duration-normal);
}

.badge-dot.pulse {
  background: var(--color-success);
  animation: pulse-glow 2s ease-in-out infinite;
}

.hero-title {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.03em;
  line-height: 1.15;
  margin-bottom: var(--space-2);
}

.hero-sub {
  font-size: 15px;
  color: var(--color-text-secondary);
  font-weight: 400;
}

/* ── Quick Start ── */
.quick-start {
  max-width: 520px;
  margin: 0 auto var(--space-6);
}

.quick-start-form {
  width: 100%;
}

.search-glass {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px 4px 4px 14px;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              border-color var(--duration-normal) var(--ease-apple);
}

.search-glass:focus-within {
  box-shadow: var(--shadow-glass-hover), 0 0 0 3px rgba(0, 122, 255, 0.12);
  border-color: rgba(0, 122, 255, 0.3);
}

.search-icon {
  flex-shrink: 0;
  color: var(--color-text-tertiary);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--color-text);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  padding: 8px 0;
}

.search-input::placeholder {
  color: var(--color-text-tertiary);
}

.search-btn {
  padding: 8px 20px;
  border-radius: var(--radius-lg);
  border: none;
  background: var(--gradient-accent);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  transition: opacity var(--duration-fast), transform var(--duration-fast);
  box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3);
}

.search-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.search-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.start-msg {
  margin-top: var(--space-2);
  font-size: 12px;
  color: var(--color-primary);
  text-align: center;
}

/* ── Loading / Error ── */
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-8);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  background: var(--color-danger-bg);
  color: var(--color-danger);
  border: 1px solid rgba(255, 59, 48, 0.2);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-5);
  font-size: 14px;
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

/* ── Agent Grid (3 sections) ── */
.agent-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto;
  gap: var(--space-5);
  margin-bottom: var(--space-5);
}

.section-runs { grid-column: 1 / -1; }
.section-gates { grid-column: 1; }
.section-activity { grid-column: 2; }

.agent-section {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5) var(--space-6);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple);
}

.agent-section:hover {
  box-shadow: var(--shadow-glass-hover);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.section-title-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.section-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.section-icon--blue {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.section-icon--amber {
  background: rgba(255, 149, 0, 0.1);
  color: var(--color-warning);
}

.section-icon--green {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.01em;
}

.section-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-tertiary);
  background: var(--color-bg-secondary);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.section-count--urgent {
  color: #fff;
  background: var(--color-warning);
  animation: pulse-glow 2s ease-in-out infinite;
}

.section-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-6) 0;
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.empty-icon {
  color: var(--color-border);
  margin-bottom: var(--space-1);
}

.empty-hint {
  font-size: 12px;
  color: var(--color-text-tertiary);
  opacity: 0.7;
}

/* ── Run Cards ── */
.run-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.run-card {
  padding: var(--space-4);
  background: rgba(0, 0, 0, 0.02);
  border-radius: var(--radius-md);
  border: 1px solid rgba(0, 0, 0, 0.04);
  transition: border-color var(--duration-fast);
}

.run-card:hover {
  border-color: rgba(0, 0, 0, 0.08);
}

.run-card.run-paused {
  border-color: rgba(255, 149, 0, 0.2);
  background: rgba(255, 149, 0, 0.03);
}

.run-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.run-keyword {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.run-status-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-full);
}

.run-status-badge.running {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.run-status-badge.paused {
  background: rgba(255, 149, 0, 0.1);
  color: var(--color-warning);
}

.run-phase {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  font-size: 13px;
}

.phase-label {
  color: var(--color-text-tertiary);
}

.phase-value {
  color: var(--color-text-secondary);
  font-weight: 500;
}

.run-progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.progress-track {
  flex: 1;
  height: 4px;
  background: var(--color-border-light);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--gradient-accent);
  border-radius: 2px;
  transition: width var(--duration-slow) var(--ease-apple);
}

.progress-fill.progress-paused {
  background: var(--color-warning);
}

.progress-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-tertiary);
  font-variant-numeric: tabular-nums;
  min-width: 32px;
  text-align: right;
}

.run-stages {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.stage-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-weight: 500;
}

.stage-chip.stage-done {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.stage-chip.stage-active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.stage-chip.stage-pending {
  background: var(--color-bg-secondary);
  color: var(--color-text-tertiary);
}

.run-actions {
  margin-top: var(--space-2);
}

.action-btn {
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: opacity var(--duration-fast), transform var(--duration-fast);
}

.action-btn--primary {
  background: var(--gradient-accent);
  color: #fff;
  box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3);
}

.action-btn--primary:hover {
  transform: translateY(-1px);
}

/* ── Gate Cards ── */
.gate-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.gate-card {
  padding: var(--space-4);
  background: rgba(255, 149, 0, 0.03);
  border: 1px solid rgba(255, 149, 0, 0.15);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--duration-fast), box-shadow var(--duration-fast);
}

.gate-card:hover {
  border-color: rgba(255, 149, 0, 0.3);
  box-shadow: 0 2px 12px rgba(255, 149, 0, 0.1);
}

.gate-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.gate-type-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-full);
}

.gate-type-badge.material {
  background: rgba(0, 122, 255, 0.1);
  color: var(--color-primary);
}

.gate-type-badge.requirement {
  background: rgba(88, 86, 214, 0.1);
  color: var(--color-secondary);
}

.gate-type-badge.insight {
  background: rgba(52, 199, 89, 0.1);
  color: var(--color-success);
}

.gate-items {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.gate-keyword {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.gate-action {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 500;
}

/* ── Activity List ── */
.activity-list {
  display: flex;
  flex-direction: column;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  flex-shrink: 0;
}

.activity-info {
  flex: 1;
  min-width: 0;
}

.activity-keyword {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.activity-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

.agent-mode-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.activity-link {
  font-size: 12px;
  color: var(--color-primary);
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  white-space: nowrap;
  transition: opacity var(--duration-fast);
}

.activity-link:hover {
  opacity: 0.7;
}

/* ── Stats Bar ── */
.stats-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  padding: var(--space-5) var(--space-6);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  margin-bottom: var(--space-8);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-number {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: var(--color-border-light);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .hero-title { font-size: 28px; }
  .hero-sub { font-size: 14px; }
  .agent-grid { grid-template-columns: 1fr; }
  .section-gates { grid-column: 1; }
  .section-activity { grid-column: 1; }
  .stats-bar { gap: var(--space-4); padding: var(--space-4); }
  .stat-number { font-size: 20px; }
}
</style>
