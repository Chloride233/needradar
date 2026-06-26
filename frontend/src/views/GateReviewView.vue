<template>
  <div ref="pageRef" class="gate-review-page">
    <!-- Hero Section -->
    <div class="page-hero" data-reveal="up">
      <div class="hero-orb hero-orb--1"></div>
      <div class="hero-orb hero-orb--2"></div>
      <div class="hero-content">
        <button class="back-btn" @click="$router.push('/gates')" aria-label="返回质量门列表">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          返回
        </button>
        <div class="hero-text">
          <h1 class="page-title">质量门审查</h1>
          <span class="run-id">Run #{{ runId }}</span>
        </div>
      </div>
    </div>

    <!-- Gate Status Overview (only when gates exist) -->
    <div v-if="gates.length > 0" class="gate-progress" data-reveal="up" data-delay="100">
      <div v-for="g in gateSteps" :key="g.type" class="gate-step" :class="g.status">
        <div class="step-icon">
          <svg v-if="g.status === 'approved'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          <svg v-else-if="g.status === 'awaiting_review'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <svg v-else-if="g.status === 'rejected'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>
        </div>
        <span class="step-label">{{ g.label }}</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <span class="spinner"></span>
      <span>加载中...</span>
    </div>

    <!-- Gate Detail -->
    <div v-else-if="currentGate" class="gate-detail" data-reveal="up" data-delay="200">
      <div class="gate-header">
        <h2 class="gate-title">{{ gateTypeLabel(currentGate.gate_type) }}</h2>
        <span class="gate-status" :class="currentGate.status">{{ statusLabel(currentGate.status) }}</span>
      </div>

      <!-- Material Gate: crawled items -->
      <div v-if="currentGate.gate_type === 'material'" class="items-list">
        <div class="items-toolbar">
          <label class="select-all">
            <input type="checkbox" :checked="allApproved" @change="toggleAll" />
            全选 ({{ approvedCount }}/{{ items.length }})
          </label>
        </div>
        <div v-for="(item, idx) in items" :key="idx" class="item-card" :class="{ rejected: !item.approved }" :data-reveal="'up'" :data-delay="String(100 + idx * 50)">
          <div class="item-check">
            <input type="checkbox" v-model="item.approved" />
          </div>
          <div class="item-body">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-meta">
              <span class="platform-tag">{{ item.platform }}</span>
              <a :href="item.source_url" target="_blank" class="source-link">原文链接</a>
            </div>
            <div class="item-preview">{{ item.content_preview }}</div>
          </div>
        </div>
      </div>

      <!-- Requirement Gate: extracted requirements -->
      <div v-else-if="currentGate.gate_type === 'requirement'" class="items-list">
        <div v-for="(item, idx) in items" :key="idx" class="item-card requirement-card" :class="{ rejected: !item.approved }" :data-reveal="'up'" :data-delay="String(100 + idx * 50)">
          <div class="item-check">
            <input type="checkbox" v-model="item.approved" />
          </div>
          <div class="item-body">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-meta">
              <span class="sentiment-tag" :class="item.sentiment">{{ item.sentiment }}</span>
              <span class="emotion-tag" :class="item.emotion">{{ item.emotion }}</span>
              <span class="confidence">置信度: {{ (item.confidence * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Insight Gate: report + verification -->
      <div v-else-if="currentGate.gate_type === 'insight'" class="items-list">
        <div v-for="(item, idx) in items" :key="idx" class="item-card insight-card" :data-reveal="'up'" :data-delay="String(100 + idx * 50)">
          <div class="item-body">
            <div class="item-title">报告: {{ item.report_title }}</div>
            <div v-if="item.verification" class="verification-scores">
              <div class="score-item">
                <span class="score-label">总分</span>
                <span class="score-value">{{ item.verification.overall_score?.toFixed(1) }}</span>
              </div>
              <div class="score-item">
                <span class="score-label">事实核查</span>
                <span class="score-value">{{ item.verification.fact_check_score?.toFixed(1) }}</span>
              </div>
              <div class="score-item">
                <span class="score-label">一致性</span>
                <span class="score-value">{{ item.verification.consistency_score?.toFixed(1) }}</span>
              </div>
              <div class="score-item">
                <span class="score-label">幻觉数</span>
                <span class="score-value warn">{{ item.verification.hallucination_count }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Review Actions -->
      <div v-if="currentGate.status === 'awaiting_review'" class="review-actions" data-reveal="up" data-delay="300">
        <textarea v-model="reviewerNote" class="review-note" placeholder="审查备注（可选）" rows="2"></textarea>

        <!-- Confirmation step -->
        <div v-if="confirmAction" class="confirm-bar" :class="confirmAction">
          <div class="confirm-text">
            <strong>{{ confirmLabel }}</strong>
            <span v-if="confirmAction === 'reject'">此操作将终止管道，已提取的数据不会丢失。</span>
            <span v-else-if="confirmAction === 'edit'">将提交 {{ rejectedCount }} 项修改并继续。</span>
            <span v-else>确认通过此质量门，管道将继续执行下一阶段。</span>
          </div>
          <div class="confirm-buttons">
            <button class="btn-sm cancel" @click="confirmAction = ''" :disabled="submitting">取消</button>
            <button class="btn-sm confirm" :class="confirmAction" @click="executeAction" :disabled="submitting">
              {{ submitting ? '提交中...' : '确认' }}
            </button>
          </div>
        </div>

        <div v-else class="action-buttons">
          <button class="btn reject" @click="confirmAction = 'reject'" :disabled="submitting">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            批驳
          </button>
          <button class="btn edit" @click="confirmAction = 'edit'" :disabled="submitting">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            编辑后批准
          </button>
          <button class="btn approve" @click="confirmAction = 'approve'" :disabled="submitting">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            批准
          </button>
        </div>
      </div>

      <!-- Already reviewed -->
      <div v-else class="review-result" data-reveal="up" data-delay="300">
        <span class="result-label">审查结果:</span>
        <span class="result-value" :class="currentGate.status">{{ statusLabel(currentGate.status) }}</span>
        <span v-if="currentGate.reviewer_note" class="result-note">"{{ currentGate.reviewer_note }}"</span>
      </div>
    </div>

    <!-- No gates -->
    <div v-else-if="!loading" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
      <p>此管道暂无质量门</p>
      <p class="empty-hint">质量门会在管道执行过程中自动创建</p>
      <button class="back-link" @click="$router.push('/')">返回指挥中心</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useReveal } from '../composables/useReveal'

const route = useRoute()
const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)
const runId = computed(() => route.params.runId)

const loading = ref(true)
const submitting = ref(false)
const gates = ref<any[]>([])
const currentGate = ref<any>(null)
const items = ref<any[]>([])
const reviewerNote = ref('')
const confirmAction = ref('') // '' | 'approve' | 'reject' | 'edit'

const confirmLabel = computed(() => {
  const map: Record<string, string> = { approve: '确认批准', reject: '确认批驳', edit: '确认编辑后批准' }
  return map[confirmAction.value] || ''
})

const rejectedCount = computed(() => items.value.filter((i: any) => !i.approved).length)

const gateSteps = computed(() => {
  const types = [
    { type: 'material', label: '素材确认' },
    { type: 'requirement', label: '需求确认' },
    { type: 'insight', label: '洞察确认' },
  ]
  return types.map(t => {
    const g = gates.value.find((g: any) => g.gate_type === t.type)
    return { ...t, status: g?.status || 'pending' }
  })
})

const allApproved = computed(() => items.value.length > 0 && items.value.every((i: any) => i.approved))
const approvedCount = computed(() => items.value.filter((i: any) => i.approved).length)

function toggleAll() {
  const newVal = !allApproved.value
  items.value.forEach((i: any) => i.approved = newVal)
}

function gateTypeLabel(type: string) {
  const map: Record<string, string> = { material: '素材确认门', requirement: '需求确认门', insight: '洞察确认门' }
  return map[type] || type
}

function statusLabel(status: string) {
  const map: Record<string, string> = { pending: '待处理', awaiting_review: '待审查', approved: '已批准', rejected: '已批驳', editing: '编辑中' }
  return map[status] || status
}

async function loadGates() {
  loading.value = true
  try {
    const resp = await fetch(`/api/v1/gates?pipeline_run_id=${runId.value}`)
    const data = await resp.json()
    gates.value = data.items || []
    // Find the first awaiting_review gate, or the last gate
    const awaiting = gates.value.find((g: any) => g.status === 'awaiting_review')
    if (awaiting) {
      await loadGateDetail(awaiting.id)
    } else if (gates.value.length > 0) {
      await loadGateDetail(gates.value[0].id)
    }
  } catch (e) {
    console.error('Failed to load gates:', e)
  } finally {
    loading.value = false
  }
}

async function loadGateDetail(gateId: number) {
  try {
    confirmAction.value = ''
    const resp = await fetch(`/api/v1/gates/${gateId}`)
    const data = await resp.json()
    currentGate.value = data
    items.value = data.items || []
  } catch (e) {
    console.error('Failed to load gate detail:', e)
  }
}

async function executeAction() {
  if (!confirmAction.value) return
  const action = confirmAction.value
  confirmAction.value = ''
  if (action === 'approve') await approveGate()
  else if (action === 'reject') await rejectGate()
  else if (action === 'edit') await editGate()
}

async function approveGate() {
  submitting.value = true
  try {
    const resp = await fetch(`/api/v1/gates/${currentGate.value.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: reviewerNote.value }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unknown error' }))
      alert(`批准失败: ${err.detail || resp.statusText}`)
      return
    }
    await loadGates()
  } catch (e: any) {
    alert(`网络错误: ${e.message}`)
  } finally {
    submitting.value = false
  }
}

async function rejectGate() {
  submitting.value = true
  try {
    const resp = await fetch(`/api/v1/gates/${currentGate.value.id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reviewerNote.value }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unknown error' }))
      alert(`批驳失败: ${err.detail || resp.statusText}`)
      return
    }
    await loadGates()
  } catch (e: any) {
    alert(`网络错误: ${e.message}`)
  } finally {
    submitting.value = false
  }
}

async function editGate() {
  submitting.value = true
  try {
    // Only include edits for items that were actually changed (unchecked = removed)
    const edits = items.value
      .filter((item: any) => !item.approved)
      .map((item: any, idx: number) => ({
        feedback_type: 'item_removed',
        entity_type: currentGate.value.gate_type === 'material' ? 'raw_item' : 'requirement',
        entity_id: item.source_url || item.vault_path || `item_${idx}`,
        before: item,
        after: null,
        reason: 'Human rejected at gate review',
      }))
    const resp = await fetch(`/api/v1/gates/${currentGate.value.id}/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ edits, note: reviewerNote.value }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unknown error' }))
      alert(`编辑失败: ${err.detail || resp.statusText}`)
      return
    }
    await loadGates()
  } catch (e: any) {
    alert(`网络错误: ${e.message}`)
  } finally {
    submitting.value = false
  }
}

onMounted(loadGates)
</script>

<style scoped>
/* ── Page Layout ── */
.gate-review-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
  padding-bottom: var(--space-9);
}

/* ── Hero Section ── */
.page-hero {
  position: relative;
  padding: var(--space-8) 0 var(--space-7);
  overflow: hidden;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
  opacity: 0.5;
}

.hero-orb--1 {
  width: 320px;
  height: 320px;
  background: var(--color-primary);
  top: -80px;
  left: -60px;
  opacity: 0.15;
}

.hero-orb--2 {
  width: 240px;
  height: 240px;
  background: var(--color-secondary);
  top: -40px;
  right: -40px;
  opacity: 0.12;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.hero-text {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  color: var(--color-text-secondary);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  transition: border-color var(--duration-normal) var(--ease-apple),
              color var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple);
}

.back-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: var(--shadow-glass-hover);
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.run-id {
  font-size: 13px;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-weight: 500;
}

/* ── Gate Progress ── */
.gate-progress {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-6);
}

.gate-step {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  transition: border-color var(--duration-normal) var(--ease-apple),
              background var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.gate-step:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.gate-step.approved {
  border-color: var(--color-success);
  background: rgba(52, 199, 89, 0.08);
}

.gate-step.awaiting_review {
  border-color: var(--color-warning);
  background: rgba(255, 149, 0, 0.08);
  animation: pulse-glow 2s ease-in-out infinite;
}

.gate-step.rejected {
  border-color: var(--color-danger);
  background: rgba(255, 59, 48, 0.08);
}

.step-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  transition: background var(--duration-normal) var(--ease-apple);
}

.gate-step.approved .step-icon { color: var(--color-success); background: var(--color-success-bg); }
.gate-step.awaiting_review .step-icon { color: var(--color-warning); background: var(--color-warning-bg); }
.gate-step.rejected .step-icon { color: var(--color-danger); background: var(--color-danger-bg); }
.gate-step.pending .step-icon { color: var(--color-text-tertiary); }

.step-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  transition: color var(--duration-normal) var(--ease-apple);
}

.gate-step.awaiting_review .step-label { color: var(--color-warning); font-weight: 600; }
.gate-step.approved .step-label { color: var(--color-success); }
.gate-step.rejected .step-label { color: var(--color-danger); }

/* ── Loading ── */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-9);
  color: var(--color-text-secondary);
  font-size: 15px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Gate Detail Card ── */
.gate-detail {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple);
}

.gate-detail:hover {
  box-shadow: var(--shadow-glass-hover);
}

.gate-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--glass-border);
}

.gate-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.01em;
}

.gate-status {
  font-size: 12px;
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.gate-status.awaiting_review {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.gate-status.approved {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.gate-status.rejected {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

/* ── Items List ── */
.items-list {
  padding: var(--space-5) var(--space-6);
}

.items-toolbar {
  margin-bottom: var(--space-4);
}

.select-all {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: color var(--duration-fast) var(--ease-apple);
}

.select-all:hover {
  color: var(--color-text);
}

/* ── Item Cards ── */
.item-card {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-3);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple),
              border-color var(--duration-normal) var(--ease-apple);
}

.item-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.item-card.rejected {
  opacity: 0.5;
  border-color: var(--color-danger);
}

.item-check {
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
}

.item-check input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.item-body { flex: 1; min-width: 0; }

.item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-1);
  line-height: 1.4;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  font-size: 12px;
}

.platform-tag {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.source-link {
  color: var(--color-text-tertiary);
  text-decoration: none;
  font-weight: 500;
  transition: color var(--duration-fast) var(--ease-apple);
}

.source-link:hover { color: var(--color-primary); }

.item-preview {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  max-height: 60px;
  overflow: hidden;
}

/* ── Requirement Tags ── */
.sentiment-tag,
.emotion-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-weight: 600;
  letter-spacing: 0.02em;
}

.sentiment-tag.strong { background: var(--color-danger-bg); color: var(--color-danger); }
.sentiment-tag.moderate { background: var(--color-warning-bg); color: var(--color-warning); }
.sentiment-tag.mild { background: var(--color-success-bg); color: var(--color-success); }

.emotion-tag.positive { background: var(--color-success-bg); color: var(--color-success); }
.emotion-tag.negative { background: var(--color-danger-bg); color: var(--color-danger); }
.emotion-tag.neutral { background: var(--color-bg-tertiary); color: var(--color-text-secondary); }

.confidence {
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 500;
}

/* ── Verification Scores ── */
.verification-scores {
  display: flex;
  gap: var(--space-5);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--glass-border);
}

.score-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  min-width: 64px;
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  transition: transform var(--duration-normal) var(--ease-apple);
}

.score-item:hover {
  transform: translateY(-2px);
}

.score-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.score-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.score-value.warn { color: var(--color-danger); }

/* ── Confirm Bar ── */
.confirm-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-lg);
  border: 1px solid;
  animation: slideUp 200ms var(--ease-apple);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.confirm-bar.approve {
  background: rgba(52, 199, 89, 0.06);
  border-color: rgba(52, 199, 89, 0.2);
}

.confirm-bar.reject {
  background: rgba(255, 59, 48, 0.06);
  border-color: rgba(255, 59, 48, 0.2);
}

.confirm-bar.edit {
  background: rgba(255, 149, 0, 0.06);
  border-color: rgba(255, 149, 0, 0.2);
}

.confirm-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.confirm-text strong {
  color: var(--color-text);
  font-size: 14px;
}

.confirm-buttons {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.btn-sm {
  padding: 6px 16px;
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--duration-fast) var(--ease-apple);
}

.btn-sm.cancel {
  background: transparent;
  color: var(--color-text-secondary);
  border-color: var(--color-border);
}

.btn-sm.cancel:hover {
  background: var(--color-bg-secondary);
}

.btn-sm.confirm.approve {
  background: var(--color-success);
  color: #fff;
}

.btn-sm.confirm.reject {
  background: var(--color-danger);
  color: #fff;
}

.btn-sm.confirm.edit {
  background: var(--color-warning);
  color: #fff;
}

.btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Review Actions ── */
.review-actions {
  padding: var(--space-5) var(--space-6);
  border-top: 1px solid var(--glass-border);
}

.review-note {
  width: 100%;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  color: var(--color-text);
  font-size: 14px;
  resize: vertical;
  margin-bottom: var(--space-4);
  font-family: inherit;
  outline: none;
  transition: border-color var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple);
}

.review-note::placeholder {
  color: var(--color-text-tertiary);
}

.review-note:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.12);
}

.action-buttons {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
}

.btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-full);
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background var(--duration-normal) var(--ease-apple),
              border-color var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple);
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none !important;
}

.btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.btn:active:not(:disabled) {
  transform: translateY(0);
}

.btn.approve {
  background: var(--color-success);
  color: #fff;
  border-color: var(--color-success);
}

.btn.approve:hover:not(:disabled) {
  background: #2DB84E;
  box-shadow: 0 4px 16px rgba(52, 199, 89, 0.3);
}

.btn.reject {
  background: transparent;
  color: var(--color-danger);
  border-color: var(--color-danger);
}

.btn.reject:hover:not(:disabled) {
  background: var(--color-danger-bg);
  box-shadow: 0 4px 16px rgba(255, 59, 48, 0.15);
}

.btn.edit {
  background: transparent;
  color: var(--color-warning);
  border-color: var(--color-warning);
}

.btn.edit:hover:not(:disabled) {
  background: var(--color-warning-bg);
  box-shadow: 0 4px 16px rgba(255, 149, 0, 0.15);
}

/* ── Review Result ── */
.review-result {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5) var(--space-6);
  border-top: 1px solid var(--glass-border);
  font-size: 14px;
}

.result-label {
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.result-value.approved { color: var(--color-success); font-weight: 600; }
.result-value.rejected { color: var(--color-danger); font-weight: 600; }

.result-note {
  color: var(--color-text-secondary);
  font-style: italic;
  margin-left: var(--space-1);
}

/* ── Empty State ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-9);
  color: var(--color-text-tertiary);
}

.empty-state svg {
  opacity: 0.4;
}

.empty-state p {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.empty-hint {
  font-size: 13px;
  color: var(--color-text-tertiary) !important;
  font-weight: 400 !important;
}

.back-link {
  margin-top: var(--space-4);
  padding: 8px 20px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  background: var(--glass-bg);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all var(--duration-fast) var(--ease-apple);
}

.back-link:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .gate-review-page {
    padding: 0 var(--space-4);
  }

  .page-hero {
    padding: var(--space-6) 0 var(--space-5);
  }

  .page-title {
    font-size: 22px;
  }

  .gate-progress {
    flex-direction: column;
    gap: var(--space-2);
  }

  .gate-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-4);
  }

  .items-list {
    padding: var(--space-4);
  }

  .item-card {
    padding: var(--space-3);
  }

  .review-actions {
    padding: var(--space-4);
  }

  .action-buttons {
    flex-direction: column;
  }

  .btn {
    justify-content: center;
  }

  .verification-scores {
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  .review-result {
    flex-wrap: wrap;
    padding: var(--space-4);
  }
}
</style>
