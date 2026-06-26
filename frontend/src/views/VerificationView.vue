<template>
  <div ref="pageRef" class="verify-page">
    <!-- Hero Section -->
    <section class="hero-section" data-reveal="up">
      <div class="hero-orb hero-orb-1"></div>
      <div class="hero-orb hero-orb-2"></div>
      <div class="hero-content">
        <h1 class="hero-title">AI 内容验证</h1>
        <p class="hero-desc">对 AI 生成报告进行多维度幻觉检测与事实核查</p>
        <button class="verify-btn" :class="{ loading: verifying }" @click="showReportPicker = true" :disabled="verifying">
          <svg v-if="!verifying" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <span v-else class="btn-spinner-sm"></span>
          {{ verifying ? '验证进行中...' : '验证报告' }}
        </button>
      </div>
    </section>

    <!-- Running Banner -->
    <div v-if="runningCount > 0" class="running-banner" data-reveal="up">
      <span class="running-dot"></span>
      <span>{{ runningCount }} 项验证正在进行中，自动刷新中...</span>
    </div>

    <!-- Stats Bar -->
    <section class="stats-bar" v-if="stats" data-reveal="up" data-delay="100">
      <div class="stat-chip glass-card" data-reveal="up" data-delay="100">
        <span class="stat-val">{{ stats.total_verifications || 0 }}</span>
        <span class="stat-label">验证次数</span>
      </div>
      <div class="stat-chip glass-card" data-reveal="up" data-delay="200">
        <span class="stat-val" :class="scoreClass(stats.average_score)">{{ stats.average_score ?? '--' }}</span>
        <span class="stat-label">平均得分</span>
      </div>
      <div class="stat-chip glass-card" data-reveal="up" data-delay="300">
        <span class="stat-val text-red">{{ stats.total_hallucinations || 0 }}</span>
        <span class="stat-label">幻觉标记</span>
      </div>
      <div class="stat-chip glass-card" data-reveal="up" data-delay="400">
        <span class="stat-val text-amber">{{ stats.total_flagged || 0 }}</span>
        <span class="stat-label">风险标记</span>
      </div>
    </section>

    <!-- Report Picker Modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="showReportPicker" class="modal-overlay" @click.self="showReportPicker = false">
          <div class="modal-card glass-card">
            <div class="modal-head">
              <h3>选择要验证的报告</h3>
              <button class="modal-close" @click="showReportPicker = false" aria-label="关闭">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
            <div class="modal-body">
              <div v-if="reports.length === 0" class="empty-sm">暂无可验证报告</div>
              <div v-for="(r, i) in reports" :key="r.title" class="report-pick-item" :style="{ transitionDelay: (i * 50) + 'ms' }" @click="startVerify(r.title)">
                <div class="report-pick-info">
                  <span class="report-pick-title">{{ r.title }}</span>
                  <span class="report-pick-meta">{{ r.keyword }} · {{ r.created_at }}</span>
                </div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Detail Modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="activeDetail" class="modal-overlay" @click.self="activeDetail = null">
          <div class="modal-card modal-lg glass-card">
            <div class="modal-head">
              <div>
                <h3>{{ activeDetail.report_title }}</h3>
                <span class="modal-sub">验证详情 · {{ activeDetail.created_at }}</span>
              </div>
              <button class="modal-close" @click="activeDetail = null" aria-label="关闭">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
            <div class="modal-body">
              <!-- Score Radar -->
              <div class="score-grid">
                <div class="score-item" data-reveal="up" data-delay="0">
                  <div class="score-ring" :class="scoreClass(activeDetail.overall_score)">
                    <span class="score-num">{{ activeDetail.overall_score ?? '--' }}</span>
                  </div>
                  <span class="score-name">综合评分</span>
                </div>
                <div class="score-item" data-reveal="up" data-delay="100">
                  <div class="score-ring" :class="scoreClass(activeDetail.fact_check_score)">
                    <span class="score-num">{{ activeDetail.fact_check_score ?? '--' }}</span>
                  </div>
                  <span class="score-name">事实核查</span>
                </div>
                <div class="score-item" data-reveal="up" data-delay="200">
                  <div class="score-ring" :class="scoreClass(activeDetail.consistency_score)">
                    <span class="score-num">{{ activeDetail.consistency_score ?? '--' }}</span>
                  </div>
                  <span class="score-name">逻辑一致性</span>
                </div>
                <div class="score-item" data-reveal="up" data-delay="300">
                  <div class="score-ring" :class="scoreClass(activeDetail.source_reliability_score)">
                    <span class="score-num">{{ activeDetail.source_reliability_score ?? '--' }}</span>
                  </div>
                  <span class="score-name">来源可靠度</span>
                </div>
              </div>

              <!-- Verification Trend -->
              <div v-if="reportHistory.length > 1" class="trend-section">
                <h4 class="section-label">验证趋势 <span class="count-tag">{{ reportHistory.length }} 次验证</span></h4>
                <div class="trend-bars">
                  <div v-for="(h, i) in reportHistory" :key="h.id" class="trend-bar-item" :class="{ current: h.id === activeDetail.id }">
                    <div class="trend-bar" :style="{ height: (h.overall_score || 0) + '%' }" :class="scoreClass(h.overall_score)"></div>
                    <span class="trend-label">{{ h.overall_score ?? '--' }}</span>
                    <span class="trend-date">{{ formatShortDate(h.created_at) }}</span>
                  </div>
                </div>
              </div>

              <!-- Claims -->
              <div class="claims-section">
                <h4 class="section-label">声明验证结果 <span class="count-tag">{{ activeDetail.claims.length }} 条</span></h4>
                <div v-if="activeDetail.claims.length === 0" class="empty-sm">未提取到可验证声明</div>
                <div v-for="(claim, i) in activeDetail.claims" :key="i" class="claim-card" :class="'verdict-' + claim.verdict" :style="{ animationDelay: (i * 60) + 'ms' }">
                  <div class="claim-head">
                    <span class="claim-verdict" :class="'badge-' + claim.verdict">{{ verdictLabel(claim.verdict) }}</span>
                    <span class="claim-conf">置信度 {{ Math.round(claim.confidence * 100) }}%</span>
                    <span v-if="claim.section" class="claim-section">{{ claim.section }}</span>
                  </div>
                  <p class="claim-text">{{ claim.text }}</p>
                  <p v-if="claim.evidence" class="claim-evidence">{{ claim.evidence }}</p>
                  <div v-if="claim.risk_flags.length" class="claim-flags">
                    <span v-for="f in claim.risk_flags" :key="f" class="flag-chip">{{ f }}</span>
                  </div>
                </div>
              </div>

              <!-- Suggestions -->
              <div v-if="activeDetail.suggestions.length" class="suggestions-section">
                <h4 class="section-label">修正建议 <span class="count-tag">{{ activeDetail.suggestions.length }} 条</span></h4>
                <div v-for="(sug, i) in activeDetail.suggestions" :key="i" class="sug-card" :class="'sug-' + sug.type" :style="{ animationDelay: (i * 60) + 'ms' }">
                  <div class="sug-head">
                    <span class="sug-type-badge">{{ sug.type === 'correction' ? '需修正' : '需审查' }}</span>
                  </div>
                  <p class="sug-claim">{{ sug.claim }}</p>
                  <p class="sug-reason">{{ sug.reason }}</p>
                  <p class="sug-action">{{ sug.action }}</p>
                </div>
              </div>

              <!-- Feedback -->
              <div class="feedback-section">
                <h4 class="section-label">人工审核反馈</h4>
                <div class="feedback-row">
                  <textarea v-model="feedbackNote" class="feedback-input" placeholder="输入审核意见..." rows="2"></textarea>
                  <button class="feedback-btn" @click="submitFeedback(activeDetail.id)">提交</button>
                </div>
                <p v-if="activeDetail.reviewer_note" class="existing-feedback">
                  <strong>已审核：</strong>{{ activeDetail.reviewer_note }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Results List -->
    <section class="results-card glass-card" data-reveal="up" data-delay="200">
      <div class="results-head">
        <h3 class="results-title">验证历史 <span class="count-tag">{{ results.length }} 条</span></h3>
      </div>
      <div v-if="results.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-tertiary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <p>暂无验证记录，点击上方"验证报告"开始</p>
      </div>
      <div v-else class="results-list">
        <div v-for="(r, i) in results" :key="r.id" class="result-item" :style="{ animationDelay: (i * 50) + 'ms' }" @click="openDetail(r)">
          <div class="result-left">
            <div class="result-score-circle" :class="scoreClass(r.overall_score)">
              {{ r.overall_score ?? '--' }}
            </div>
            <div class="result-info">
              <span class="result-title">{{ r.report_title }}</span>
              <div class="result-meta">
                <span class="result-badge" :class="'status-' + r.status">{{ statusLabel(r.status) }}</span>
                <span class="result-sep">·</span>
                <span>{{ r.total_claims }} 条声明</span>
                <span class="result-sep">·</span>
                <span v-if="r.hallucination_count" class="text-red">{{ r.hallucination_count }} 幻觉</span>
                <span v-else class="text-green">无幻觉</span>
                <span class="result-sep">·</span>
                <span>{{ formatShortDate(r.created_at) }}</span>
              </div>
            </div>
          </div>
          <svg class="result-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import api from '../api/client'
import { useReveal } from '../composables/useReveal'

const message = useMessage()

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

interface ClaimDetail {
  text: string
  section: string
  verdict: string
  confidence: number
  evidence: string
  risk_flags: string[]
}

interface SuggestionDetail {
  type: string
  claim: string
  verdict: string
  reason: string
  action: string
}

interface VerificationItem {
  id: number
  report_title: string
  status: string
  overall_score: number | null
  fact_check_score: number | null
  consistency_score: number | null
  source_reliability_score: number | null
  total_claims: number
  hallucination_count: number
  flagged_count: number
  claims: ClaimDetail[]
  suggestions: SuggestionDetail[]
  reviewer_note: string | null
  reviewed_at: string | null
  created_at: string
}

interface StatsData {
  total_verifications: number
  average_score: number | null
  total_hallucinations: number
  total_flagged: number
}

const results = ref<VerificationItem[]>([])
const reports = ref<{ title: string; keyword: string; created_at: string }[]>([])
const stats = ref<StatsData | null>(null)
const showReportPicker = ref(false)
const activeDetail = ref<VerificationItem | null>(null)
const reportHistory = ref<VerificationItem[]>([])
const feedbackNote = ref('')
const verifying = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const runningCount = computed(() =>
  results.value.filter(r => r.status === 'pending' || r.status === 'running').length
)

function scoreClass(score: number | null | undefined): string {
  if (score == null) return ''
  if (score >= 80) return 'score-good'
  if (score >= 60) return 'score-ok'
  if (score >= 40) return 'score-warn'
  return 'score-bad'
}

function verdictLabel(v: string): string {
  const map: Record<string, string> = {
    supported: '已验证',
    partially: '部分支持',
    unverifiable: '无法验证',
    contradicted: '有矛盾',
    hallucination: '幻觉',
  }
  return map[v] || v
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '验证中',
    completed: '已完成',
    failed: '失败',
  }
  return map[s] || s
}

function formatShortDate(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

async function loadStats() {
  try {
    const { data } = await api.get('/verification/stats')
    stats.value = data
  } catch { /* ignore */ }
}

async function loadResults() {
  try {
    const { data } = await api.get('/verification/results', { params: { page_size: 50 } })
    results.value = data.items
  } catch { /* handled by interceptor */ }
}

async function loadReports() {
  try {
    const { data } = await api.get('/verification/reports')
    reports.value = data.items
  } catch { /* handled by interceptor */ }
}

function startPolling() {
  stopPolling()
  if (runningCount.value > 0) {
    pollTimer = setTimeout(async () => {
      await loadResults()
      await loadStats()
      // Keep polling if still running
      if (runningCount.value > 0) {
        startPolling()
      }
    }, 3000)
  }
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

async function startVerify(title: string) {
  showReportPicker.value = false
  verifying.value = true
  try {
    await api.post('/verification/verify', { report_title: title })
    message.info('验证已启动，正在后台执行...')
    await loadResults()
    await loadStats()
    startPolling()
  } catch (e: any) {
    message.error(e.response?.data?.detail || '验证启动失败')
  } finally {
    // Keep verifying state until completion
    const checkDone = () => {
      if (runningCount.value === 0) {
        verifying.value = false
        message.success('验证完成')
      } else {
        setTimeout(checkDone, 2000)
      }
    }
    setTimeout(checkDone, 2000)
  }
}

async function openDetail(r: VerificationItem) {
  const { data } = await api.get(`/verification/results/${r.id}`)
  activeDetail.value = data
  feedbackNote.value = ''

  // Load verification history for this report
  try {
    const { data: hist } = await api.get(`/verification/results/by-report/${encodeURIComponent(r.report_title)}`)
    reportHistory.value = hist.items
  } catch {
    reportHistory.value = []
  }
}

async function submitFeedback(id: number) {
  if (!feedbackNote.value.trim()) return
  await api.post(`/verification/results/${id}/feedback`, { reviewer_note: feedbackNote.value })
  message.success('反馈已提交')
  if (activeDetail.value) {
    activeDetail.value.reviewer_note = feedbackNote.value
  }
  feedbackNote.value = ''
}

onMounted(() => {
  loadResults()
  loadStats()
  loadReports()
  // Auto-poll if there are running verifications on mount
  setTimeout(() => {
    if (runningCount.value > 0) startPolling()
  }, 1000)
})
onUnmounted(stopPolling)
</script>

<style scoped>
/* ── Reveal Animations ── */
[data-reveal] {
  opacity: 0;
  transform: translateY(24px);
  transition: opacity var(--duration-slow, 300ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              transform var(--duration-slow, 300ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}
[data-reveal="up"][data-revealed],
[data-reveal][data-revealed] {
  opacity: 1;
  transform: translateY(0);
}
[data-delay="100"] { transition-delay: 100ms; }
[data-delay="200"] { transition-delay: 200ms; }
[data-delay="300"] { transition-delay: 300ms; }
[data-delay="400"] { transition-delay: 400ms; }

/* ── Glass Card Base ── */
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}

/* ── Page Layout ── */
.verify-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5, 20px);
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6, 24px);
}

/* ── Hero Section ── */
.hero-section {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-xl);
  padding: var(--space-9, 48px) var(--space-7, 28px);
  background: linear-gradient(135deg, var(--color-bg) 0%, var(--color-bg-secondary) 100%);
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-glass);
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
  opacity: 0.4;
}

.hero-orb-1 {
  width: 260px;
  height: 260px;
  background: var(--color-primary);
  top: -60px;
  right: -40px;
}

.hero-orb-2 {
  width: 180px;
  height: 180px;
  background: var(--color-success, #34C759);
  bottom: -40px;
  left: -30px;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-3, 12px);
}

.hero-title {
  font-family: var(--font-display, var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif));
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-text);
  margin: 0;
}

.hero-desc {
  font-size: 15px;
  color: var(--color-text-secondary);
  margin: 0 0 var(--space-2, 8px);
  line-height: 1.6;
}

/* ── Verify Button ── */
.verify-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2, 8px);
  padding: 12px 28px;
  border-radius: var(--radius-full, 9999px);
  border: none;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  background: var(--color-primary);
  cursor: pointer;
  transition: transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              box-shadow var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              background var(--duration-fast, 100ms);
}

.verify-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-glass-hover);
}

.verify-btn:active:not(:disabled) {
  transform: translateY(0);
}

.verify-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.verify-btn.loading {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.btn-spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(0,122,255,0.2);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.verify-btn.loading .btn-spinner-sm {
  border-color: rgba(0,122,255,0.2);
  border-top-color: var(--color-primary);
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Running Banner ── */
.running-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  padding: var(--space-3, 12px) var(--space-4, 18px);
  border-radius: var(--radius-xl);
  background: var(--color-primary-bg);
  border: 1px solid rgba(0,122,255,0.15);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 500;
}

.running-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0,122,255,0.3); }
  50% { opacity: 0.6; box-shadow: 0 0 0 5px rgba(0,122,255,0); }
}

/* ── Stats Bar ── */
.stats-bar {
  display: flex;
  gap: var(--space-3, 12px);
}

.stat-chip {
  flex: 1;
  padding: var(--space-4, 16px) var(--space-5, 20px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1, 4px);
  transition: box-shadow var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}

.stat-chip:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.stat-val {
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
}

.stat-val.score-good, .text-green { color: var(--color-success, #34C759); }
.stat-val.score-ok { color: var(--color-primary); }
.stat-val.score-warn, .text-amber { color: var(--color-warning, #FF9500); }
.stat-val.score-bad, .text-red { color: var(--color-danger, #FF3B30); }

.stat-label {
  font-size: 12px;
  color: var(--color-text-tertiary);
  font-weight: 500;
}

/* ── Results Card ── */
.results-card {
  padding: var(--space-6, 24px);
}

.results-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4, 18px);
}

.results-title {
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: var(--space-2, 10px);
}

.count-tag {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-tertiary);
  background: var(--color-bg-secondary);
  padding: 3px 10px;
  border-radius: var(--radius-sm, 8px);
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1, 4px);
}

.result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3, 14px) var(--space-4, 16px);
  border-radius: var(--radius-lg, 16px);
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background var(--duration-fast, 100ms),
              border-color var(--duration-fast, 100ms),
              box-shadow var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}

.result-item:hover {
  background: var(--glass-bg);
  border-color: var(--glass-border);
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.result-left {
  display: flex;
  align-items: center;
  gap: var(--space-3, 14px);
  min-width: 0;
  flex: 1;
}

.result-score-circle {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg, 16px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
}

.result-score-circle.score-good { background: var(--color-success-bg, rgba(52,199,89,0.1)); color: var(--color-success, #34C759); }
.result-score-circle.score-ok { background: var(--color-primary-bg, rgba(0,122,255,0.1)); color: var(--color-primary); }
.result-score-circle.score-warn { background: var(--color-warning-bg, rgba(255,149,0,0.1)); color: var(--color-warning, #FF9500); }
.result-score-circle.score-bad { background: var(--color-danger-bg, rgba(255,59,48,0.1)); color: var(--color-danger, #FF3B30); }

.result-info { min-width: 0; }

.result-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: var(--space-1, 6px);
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 3px;
}

.result-badge {
  padding: 1px 8px;
  border-radius: var(--radius-sm, 8px);
  font-size: 11px;
  font-weight: 500;
}

.result-badge.status-completed { background: var(--color-success-bg, rgba(52,199,89,0.1)); color: var(--color-success, #34C759); }
.result-badge.status-running { background: var(--color-primary-bg, rgba(0,122,255,0.1)); color: var(--color-primary); }
.result-badge.status-pending { background: var(--color-bg-tertiary); color: var(--color-text-secondary); }
.result-badge.status-failed { background: var(--color-danger-bg, rgba(255,59,48,0.1)); color: var(--color-danger, #FF3B30); }

.result-sep { color: var(--color-border); }

.result-arrow {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
  transition: color var(--duration-fast, 100ms),
              transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}

.result-item:hover .result-arrow {
  color: var(--color-primary);
  transform: translateX(2px);
}

.empty-state, .empty-sm {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3, 12px);
  padding: var(--space-9, 48px) 0;
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.empty-sm { padding: var(--space-6, 24px) 0; }

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}
.modal-fade-enter-from,
.modal-fade-leave-to { opacity: 0; }

.modal-fade-enter-active .modal-card,
.modal-fade-leave-active .modal-card {
  transition: transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              opacity var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}
.modal-fade-enter-from .modal-card { transform: translateY(16px) scale(0.97); opacity: 0; }
.modal-fade-leave-to .modal-card { transform: translateY(8px) scale(0.98); opacity: 0; }

.modal-card {
  width: 480px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.modal-lg { width: 640px; }

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5, 20px) var(--space-6, 24px);
  border-bottom: 1px solid var(--glass-border);
}

.modal-head h3 {
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.modal-sub {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.modal-close {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full, 9999px);
  border: none;
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--duration-fast, 100ms), color var(--duration-fast, 100ms);
}

.modal-close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}

.modal-body {
  padding: var(--space-5, 20px) var(--space-6, 24px);
  overflow-y: auto;
  flex: 1;
}

.report-pick-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3, 12px) var(--space-3, 14px);
  border-radius: var(--radius-lg, 16px);
  cursor: pointer;
  transition: background var(--duration-fast, 100ms),
              box-shadow var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}

.report-pick-item:hover {
  background: var(--color-bg-secondary);
  box-shadow: var(--shadow-glass-hover);
  transform: translateX(4px);
}

.report-pick-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.report-pick-meta {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.report-pick-item svg { color: var(--color-text-tertiary); transition: transform var(--duration-normal, 200ms) var(--ease-apple); }
.report-pick-item:hover svg { color: var(--color-primary); transform: translateX(2px); }

/* ── Score Grid ── */
.score-grid {
  display: flex;
  gap: var(--space-4, 16px);
  margin-bottom: var(--space-6, 24px);
}

.score-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2, 8px);
}

.score-ring {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 3px solid var(--glass-border);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color var(--duration-slow, 300ms),
              box-shadow var(--duration-slow, 300ms);
}

.score-ring.score-good { border-color: var(--color-success, #34C759); box-shadow: 0 0 16px rgba(52,199,89,0.2); }
.score-ring.score-ok { border-color: var(--color-primary); box-shadow: 0 0 16px rgba(0,122,255,0.15); }
.score-ring.score-warn { border-color: var(--color-warning, #FF9500); box-shadow: 0 0 16px rgba(255,149,0,0.15); }
.score-ring.score-bad { border-color: var(--color-danger, #FF3B30); box-shadow: 0 0 16px rgba(255,59,48,0.15); }

.score-num {
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
}

.score-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
}

/* ── Section Label ── */
.section-label {
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-3, 12px);
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
}

/* ── Trend Section ── */
.trend-section {
  margin-bottom: var(--space-5, 20px);
  padding: var(--space-4, 16px);
  border-radius: var(--radius-xl);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
}

.trend-bars {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2, 8px);
  height: 100px;
  padding-top: var(--space-2, 8px);
}

.trend-bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1, 4px);
  max-width: 60px;
}

.trend-bar {
  width: 100%;
  border-radius: var(--radius-sm, 8px) var(--radius-sm, 8px) 0 0;
  background: var(--glass-border);
  min-height: 4px;
  transition: background var(--duration-slow, 300ms),
              box-shadow var(--duration-slow, 300ms);
}

.trend-bar.score-good { background: var(--color-success, #34C759); }
.trend-bar.score-ok { background: var(--color-primary); }
.trend-bar.score-warn { background: var(--color-warning, #FF9500); }
.trend-bar.score-bad { background: var(--color-danger, #FF3B30); }

.trend-bar-item.current .trend-bar {
  box-shadow: 0 0 0 2px var(--color-text), 0 0 12px rgba(0,0,0,0.1);
}

.trend-label {
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text);
}

.trend-bar-item.current .trend-label {
  color: var(--color-text);
}

.trend-date {
  font-size: 10px;
  color: var(--color-text-tertiary);
}

/* ── Claim Cards ── */
.claims-section, .suggestions-section, .feedback-section {
  margin-top: var(--space-5, 20px);
  padding-top: var(--space-4, 16px);
  border-top: 1px solid var(--glass-border);
}

.claim-card {
  padding: var(--space-3, 14px) var(--space-4, 16px);
  border-radius: var(--radius-lg, 16px);
  border-left: 3px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  margin-bottom: var(--space-2, 8px);
  transition: box-shadow var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}

.claim-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-1px);
}

.claim-card.verdict-supported { border-left-color: var(--color-success, #34C759); }
.claim-card.verdict-partially { border-left-color: var(--color-warning, #FF9500); }
.claim-card.verdict-unverifiable { border-left-color: var(--glass-border); }
.claim-card.verdict-contradicted { border-left-color: var(--color-warning, #FF9500); }
.claim-card.verdict-hallucination {
  border-left-color: var(--color-danger, #FF3B30);
  background: var(--color-danger-bg, rgba(255,59,48,0.06));
}

.claim-head {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  margin-bottom: var(--space-1, 6px);
}

.claim-verdict {
  padding: 2px 8px;
  border-radius: var(--radius-full, 9999px);
  font-size: 11px;
  font-weight: 700;
}

.badge-supported { background: var(--color-success-bg, rgba(52,199,89,0.1)); color: var(--color-success, #34C759); }
.badge-partially { background: var(--color-warning-bg, rgba(255,149,0,0.1)); color: var(--color-warning, #FF9500); }
.badge-unverifiable { background: var(--color-bg-tertiary); color: var(--color-text-secondary); }
.badge-contradicted { background: var(--color-warning-bg, rgba(255,149,0,0.1)); color: var(--color-warning, #FF9500); }
.badge-hallucination { background: var(--color-danger-bg, rgba(255,59,48,0.1)); color: var(--color-danger, #FF3B30); }

.claim-conf {
  font-size: 11px;
  color: var(--color-text-tertiary);
}

.claim-section {
  font-size: 11px;
  color: var(--color-text-secondary);
  background: var(--color-bg-tertiary);
  padding: 1px 8px;
  border-radius: var(--radius-full, 9999px);
}

.claim-text {
  font-size: 14px;
  color: var(--color-text);
  line-height: 1.6;
}

.claim-evidence {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: var(--space-1, 4px);
  line-height: 1.5;
}

.claim-flags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1, 4px);
  margin-top: var(--space-1, 6px);
}

.flag-chip {
  padding: 2px 8px;
  border-radius: var(--radius-full, 9999px);
  font-size: 11px;
  font-weight: 500;
  background: var(--color-danger-bg, rgba(255,59,48,0.1));
  color: var(--color-danger, #FF3B30);
}

/* ── Suggestion Cards ── */
.sug-card {
  padding: var(--space-3, 14px) var(--space-4, 16px);
  border-radius: var(--radius-lg, 16px);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  margin-bottom: var(--space-2, 8px);
  transition: box-shadow var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}

.sug-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-1px);
}

.sug-card.sug-correction { border-color: var(--color-danger, #FF3B30); background: var(--color-danger-bg, rgba(255,59,48,0.06)); }
.sug-card.sug-review { border-color: var(--color-warning, #FF9500); background: var(--color-warning-bg, rgba(255,149,0,0.06)); }

.sug-type-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: var(--radius-full, 9999px);
  display: inline-block;
  margin-bottom: var(--space-1, 6px);
}

.sug-correction .sug-type-badge { background: var(--color-danger-bg, rgba(255,59,48,0.1)); color: var(--color-danger, #FF3B30); }
.sug-review .sug-type-badge { background: var(--color-warning-bg, rgba(255,149,0,0.1)); color: var(--color-warning, #FF9500); }

.sug-claim {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.5;
}

.sug-reason {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: var(--space-1, 4px);
}

.sug-action {
  font-size: 12px;
  color: var(--color-primary);
  margin-top: var(--space-1, 4px);
  font-weight: 500;
}

/* ── Feedback ── */
.feedback-row {
  display: flex;
  gap: var(--space-2, 8px);
}

.feedback-input {
  flex: 1;
  padding: 10px 14px;
  border-radius: var(--radius-lg, 16px);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  font-family: inherit;
  font-size: 13px;
  color: var(--color-text);
  resize: none;
  outline: none;
  transition: border-color var(--duration-fast, 100ms),
              box-shadow var(--duration-fast, 100ms);
}

.feedback-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0,122,255,0.15);
}

.feedback-btn {
  padding: 10px 18px;
  border-radius: var(--radius-full, 9999px);
  border: none;
  background: var(--color-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background var(--duration-fast, 100ms),
              transform var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1)),
              box-shadow var(--duration-normal, 200ms) var(--ease-apple, cubic-bezier(0.25, 0.1, 0.25, 1));
}

.feedback-btn:hover {
  background: var(--color-primary-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-glass-hover);
}

.existing-feedback {
  margin-top: var(--space-2, 10px);
  padding: 10px 14px;
  border-radius: var(--radius-lg, 16px);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}
</style>
