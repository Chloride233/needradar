<template>
  <div class="verify-page">
    <!-- Header -->
    <div class="verify-header">
      <div>
        <h2 class="verify-title">AI 内容验证</h2>
        <p class="verify-desc">对 AI 生成报告进行多维度幻觉检测与事实核查</p>
      </div>
      <button class="verify-btn" :class="{ loading: verifying }" @click="showReportPicker = true" :disabled="verifying">
        <svg v-if="!verifying" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        <span v-else class="btn-spinner-sm"></span>
        {{ verifying ? '验证进行中...' : '验证报告' }}
      </button>
    </div>

    <!-- Running Banner -->
    <div v-if="runningCount > 0" class="running-banner">
      <span class="running-dot"></span>
      <span>{{ runningCount }} 项验证正在进行中，自动刷新中...</span>
    </div>

    <!-- Stats Bar -->
    <div class="stats-bar" v-if="stats">
      <div class="stat-chip">
        <span class="stat-val">{{ stats.total_verifications || 0 }}</span>
        <span class="stat-label">验证次数</span>
      </div>
      <div class="stat-chip">
        <span class="stat-val" :class="scoreClass(stats.average_score)">{{ stats.average_score ?? '--' }}</span>
        <span class="stat-label">平均得分</span>
      </div>
      <div class="stat-chip">
        <span class="stat-val text-red">{{ stats.total_hallucinations || 0 }}</span>
        <span class="stat-label">幻觉标记</span>
      </div>
      <div class="stat-chip">
        <span class="stat-val text-amber">{{ stats.total_flagged || 0 }}</span>
        <span class="stat-label">风险标记</span>
      </div>
    </div>

    <!-- Report Picker Modal -->
    <div v-if="showReportPicker" class="modal-overlay" @click.self="showReportPicker = false">
      <div class="modal-card">
        <div class="modal-head">
          <h3>选择要验证的报告</h3>
          <button class="modal-close" @click="showReportPicker = false" aria-label="关闭">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="reports.length === 0" class="empty-sm">暂无可验证报告</div>
          <div v-for="r in reports" :key="r.title" class="report-pick-item" @click="startVerify(r.title)">
            <div class="report-pick-info">
              <span class="report-pick-title">{{ r.title }}</span>
              <span class="report-pick-meta">{{ r.keyword }} · {{ r.created_at }}</span>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="activeDetail" class="modal-overlay" @click.self="activeDetail = null">
      <div class="modal-card modal-lg">
        <div class="modal-head">
          <div>
            <h3>{{ activeDetail.report_title }}</h3>
            <span class="modal-sub">验证详情 · {{ activeDetail.created_at }}</span>
          </div>
          <button class="modal-close" @click="activeDetail = null" aria-label="关闭">&times;</button>
        </div>
        <div class="modal-body">
          <!-- Score Radar -->
          <div class="score-grid">
            <div class="score-item">
              <div class="score-ring" :class="scoreClass(activeDetail.overall_score)">
                <span class="score-num">{{ activeDetail.overall_score ?? '--' }}</span>
              </div>
              <span class="score-name">综合评分</span>
            </div>
            <div class="score-item">
              <div class="score-ring" :class="scoreClass(activeDetail.fact_check_score)">
                <span class="score-num">{{ activeDetail.fact_check_score ?? '--' }}</span>
              </div>
              <span class="score-name">事实核查</span>
            </div>
            <div class="score-item">
              <div class="score-ring" :class="scoreClass(activeDetail.consistency_score)">
                <span class="score-num">{{ activeDetail.consistency_score ?? '--' }}</span>
              </div>
              <span class="score-name">逻辑一致性</span>
            </div>
            <div class="score-item">
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
            <div v-for="(claim, i) in activeDetail.claims" :key="i" class="claim-card" :class="'verdict-' + claim.verdict">
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
            <div v-for="(sug, i) in activeDetail.suggestions" :key="i" class="sug-card" :class="'sug-' + sug.type">
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

    <!-- Results List -->
    <div class="results-card">
      <div class="results-head">
        <h3 class="results-title">验证历史 <span class="count-tag">{{ results.length }} 条</span></h3>
      </div>
      <div v-if="results.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <p>暂无验证记录，点击上方"验证报告"开始</p>
      </div>
      <div v-else class="results-list">
        <div v-for="r in results" :key="r.id" class="result-item" @click="openDetail(r)">
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
          <svg class="result-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import api from '../api/client'

const message = useMessage()

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
.verify-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Header ── */
.verify-header {
  background: linear-gradient(135deg, #1e293b, #0f172a);
  border-radius: 16px;
  padding: 24px 28px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.verify-title {
  font-family: 'Outfit', sans-serif;
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}

.verify-desc {
  font-size: 13px;
  color: rgba(255,255,255,0.5);
}

.verify-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border-radius: 10px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: #0f172a;
  background: #141414;
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.verify-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.2);
}

.verify-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.verify-btn.loading { background: rgba(255,255,255,0.15); color: rgba(255,255,255,0.7); }

.btn-spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(0,0,0,0.15);
  border-top-color: #0f172a;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.verify-btn.loading .btn-spinner-sm {
  border-color: rgba(255,255,255,0.2);
  border-top-color: rgba(255,255,255,0.8);
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Running Banner ── */
.running-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 500;
}

.running-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(59,130,246,0.4); }
  50% { opacity: 0.6; box-shadow: 0 0 0 5px rgba(59,130,246,0); }
}

/* ── Stats Bar ── */
.stats-bar {
  display: flex;
  gap: 12px;
}

.stat-chip {
  flex: 1;
  background: #141414;
  border-radius: 12px;
  border: 1px solid var(--slate-100);
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  box-shadow: none;
}

.stat-val {
  font-family: 'Outfit', sans-serif;
  font-size: 24px;
  font-weight: 700;
  color: var(--slate-800);
}

.stat-val.score-good, .text-green { color: #10b981; }
.stat-val.score-ok { color: var(--teal-600); }
.stat-val.score-warn { color: #f59e0b; }
.stat-val.score-bad, .text-red { color: #ef4444; }
.text-amber { color: #f59e0b; }

.stat-label {
  font-size: 12px;
  color: var(--slate-400);
  font-weight: 500;
}

/* ── Results Card ── */
.results-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.results-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.results-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
  display: flex;
  align-items: center;
  gap: 10px;
}

.count-tag {
  font-size: 12px;
  font-weight: 500;
  color: var(--slate-400);
  background: var(--slate-50);
  padding: 3px 10px;
  border-radius: 6px;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--slate-50);
  border: 1px solid transparent;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
  cursor: pointer;
}

.result-item:hover {
  background: #141414;
  border-color: var(--slate-200);
  border-color: var(--card-border-hover);
}

.result-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  flex: 1;
}

.result-score-circle {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
  background: var(--slate-100);
  color: var(--slate-500);
}

.result-score-circle.score-good { background: var(--success-bg); color: #059669; }
.result-score-circle.score-ok { background: var(--teal-50); color: var(--teal-700); }
.result-score-circle.score-warn { background: var(--warning-bg); color: #d97706; }
.result-score-circle.score-bad { background: var(--error-bg); color: var(--error-text); }

.result-info { min-width: 0; }

.result-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-800);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--slate-400);
  margin-top: 3px;
}

.result-badge {
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.result-badge.status-completed { background: var(--success-bg); color: #059669; }
.result-badge.status-running { background: rgba(99, 102, 241, 0.1); color: #818cf8; }
.result-badge.status-pending { background: var(--slate-100); color: var(--slate-500); }
.result-badge.status-failed { background: var(--error-bg); color: var(--error-text); }

.result-sep { color: var(--slate-300); }

.result-arrow {
  color: var(--slate-300);
  flex-shrink: 0;
  transition: color 0.2s;
}

.result-item:hover .result-arrow { color: var(--teal-500); }

.empty-state, .empty-sm {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
  color: var(--slate-400);
  font-size: 14px;
}

.empty-sm { padding: 24px 0; }

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-card {
  background: #141414;
  border-radius: 16px;
  width: 480px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px rgba(0,0,0,0.15);
}

.modal-lg { width: 640px; }

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--slate-100);
}

.modal-head h3 {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
}

.modal-sub {
  font-size: 12px;
  color: var(--slate-400);
}

.modal-close {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: var(--slate-50);
  font-size: 18px;
  color: var(--slate-500);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.modal-close:hover {
  background: var(--slate-100);
  color: var(--slate-700);
}

.modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

.report-pick-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.report-pick-item:hover {
  background: var(--slate-50);
}

.report-pick-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-800);
}

.report-pick-meta {
  font-size: 12px;
  color: var(--slate-400);
}

.report-pick-item svg { color: var(--slate-300); }
.report-pick-item:hover svg { color: var(--teal-500); }

/* ── Score Grid ── */
.score-grid {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.score-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.score-ring {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 3px solid var(--slate-200);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.3s;
}

.score-ring.score-good { border-color: #10b981; }
.score-ring.score-ok { border-color: var(--teal-600); }
.score-ring.score-warn { border-color: #f59e0b; }
.score-ring.score-bad { border-color: #ef4444; }

.score-num {
  font-family: 'Outfit', sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: var(--slate-800);
}

.score-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--slate-400);
}

/* ── Section Label ── */
.section-label {
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-700);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Trend Section ── */
.trend-section {
  margin-bottom: 20px;
  padding: 16px;
  border-radius: 12px;
  background: var(--slate-50);
  border: 1px solid var(--slate-100);
}

.trend-bars {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 100px;
  padding-top: 8px;
}

.trend-bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  max-width: 60px;
}

.trend-bar {
  width: 100%;
  border-radius: 4px 4px 0 0;
  background: var(--slate-300);
  min-height: 4px;
  transition: border-color 0.3s;
}

.trend-bar.score-good { background: #10b981; }
.trend-bar.score-ok { background: var(--teal-600); }
.trend-bar.score-warn { background: #f59e0b; }
.trend-bar.score-bad { background: #ef4444; }

.trend-bar-item.current .trend-bar {
  box-shadow: 0 0 0 2px var(--slate-800);
}

.trend-label {
  font-family: 'Outfit', sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: var(--slate-700);
}

.trend-bar-item.current .trend-label {
  color: var(--slate-900);
}

.trend-date {
  font-size: 10px;
  color: var(--slate-400);
}

/* ── Claim Cards ── */
.claims-section, .suggestions-section, .feedback-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px dashed var(--slate-200);
}

.claim-card {
  padding: 14px 16px;
  border-radius: 10px;
  border-left: 3px solid var(--slate-200);
  background: var(--slate-50);
  margin-bottom: 8px;
}

.claim-card.verdict-supported { border-left-color: #10b981; }
.claim-card.verdict-partially { border-left-color: #f59e0b; }
.claim-card.verdict-unverifiable { border-left-color: var(--slate-300); }
.claim-card.verdict-contradicted { border-left-color: #f97316; }
.claim-card.verdict-hallucination { border-left-color: #fb7185; background: var(--error-bg); }

.claim-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.claim-verdict {
  padding: 2px 8px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 700;
}

.badge-supported { background: var(--success-bg); color: #059669; }
.badge-partially { background: var(--warning-bg); color: #d97706; }
.badge-unverifiable { background: var(--slate-100); color: var(--slate-500); }
.badge-contradicted { background: rgba(234, 88, 12, 0.1); color: #fb923c; }
.badge-hallucination { background: var(--error-bg); color: var(--error-text); }

.claim-conf {
  font-size: 11px;
  color: var(--slate-400);
}

.claim-section {
  font-size: 11px;
  color: var(--slate-400);
  background: var(--slate-100);
  padding: 1px 8px;
  border-radius: 4px;
}

.claim-text {
  font-size: 14px;
  color: var(--slate-700);
  line-height: 1.6;
}

.claim-evidence {
  font-size: 12px;
  color: var(--slate-500);
  margin-top: 4px;
  line-height: 1.5;
}

.claim-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.flag-chip {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: var(--error-bg);
  color: var(--error-text);
}

/* ── Suggestion Cards ── */
.sug-card {
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid var(--slate-200);
  margin-bottom: 8px;
}

.sug-card.sug-correction { border-color: var(--error-border); background: var(--error-bg); }
.sug-card.sug-review { border-color: #fcd34d; background: var(--warning-bg); }

.sug-type-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 5px;
  display: inline-block;
  margin-bottom: 6px;
}

.sug-correction .sug-type-badge { background: rgba(220, 38, 38, 0.15); color: #fca5a5; }
.sug-review .sug-type-badge { background: rgba(245, 158, 11, 0.15); color: var(--warning-text); }

.sug-claim {
  font-size: 13px;
  font-weight: 600;
  color: var(--slate-800);
  line-height: 1.5;
}

.sug-reason {
  font-size: 12px;
  color: var(--slate-500);
  margin-top: 4px;
}

.sug-action {
  font-size: 12px;
  color: var(--teal-700);
  margin-top: 4px;
  font-weight: 500;
}

/* ── Feedback ── */
.feedback-row {
  display: flex;
  gap: 8px;
}

.feedback-input {
  flex: 1;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid var(--slate-200);
  font-family: inherit;
  font-size: 13px;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
}

.feedback-input:focus { border-color: var(--teal-400); }

.feedback-btn {
  padding: 10px 18px;
  border-radius: 8px;
  border: none;
  background: var(--teal-600);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.feedback-btn:hover { background: var(--teal-700); }

.existing-feedback {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--slate-50);
  font-size: 13px;
  color: var(--slate-600);
  line-height: 1.5;
}
</style>
