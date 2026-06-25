<template>
  <div class="gate-review-page">
    <div class="page-header">
      <button class="back-btn" @click="$router.push('/tasks')" aria-label="返回任务列表">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
        返回
      </button>
      <h1 class="page-title">质量门审查</h1>
      <span class="run-id">Run #{{ runId }}</span>
    </div>

    <!-- Gate Status Overview -->
    <div class="gate-progress">
      <div v-for="g in gateSteps" :key="g.type" class="gate-step" :class="g.status">
        <div class="step-icon">
          <svg v-if="g.status === 'approved'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          <svg v-else-if="g.status === 'awaiting_review'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <svg v-else-if="g.status === 'rejected'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>
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
    <div v-else-if="currentGate" class="gate-detail">
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
        <div v-for="(item, idx) in items" :key="idx" class="item-card" :class="{ rejected: !item.approved }">
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
        <div v-for="(item, idx) in items" :key="idx" class="item-card requirement-card" :class="{ rejected: !item.approved }">
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
        <div v-for="(item, idx) in items" :key="idx" class="item-card insight-card">
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
      <div v-if="currentGate.status === 'awaiting_review'" class="review-actions">
        <textarea v-model="reviewerNote" class="review-note" placeholder="审查备注（可选）" rows="2"></textarea>
        <div class="action-buttons">
          <button class="btn reject" @click="rejectGate" :disabled="submitting">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            批驳
          </button>
          <button class="btn edit" @click="editGate" :disabled="submitting">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            编辑后批准
          </button>
          <button class="btn approve" @click="approveGate" :disabled="submitting">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            批准
          </button>
        </div>
      </div>

      <!-- Already reviewed -->
      <div v-else class="review-result">
        <span class="result-label">审查结果:</span>
        <span class="result-value" :class="currentGate.status">{{ statusLabel(currentGate.status) }}</span>
        <span v-if="currentGate.reviewer_note" class="result-note">"{{ currentGate.reviewer_note }}"</span>
      </div>
    </div>

    <!-- No gates -->
    <div v-else-if="!loading" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
      <p>暂无质量门</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const runId = computed(() => route.params.runId)

const loading = ref(true)
const submitting = ref(false)
const gates = ref<any[]>([])
const currentGate = ref<any>(null)
const items = ref<any[]>([])
const reviewerNote = ref('')

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
    const resp = await fetch(`/api/v1/gates/${gateId}`)
    const data = await resp.json()
    currentGate.value = data
    items.value = data.items || []
  } catch (e) {
    console.error('Failed to load gate detail:', e)
  }
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
.gate-review-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: 1px solid var(--card-border, #2a2a2a);
  color: var(--text-secondary, #999);
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
.back-btn:hover { border-color: var(--card-border-hover, #363636); }

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #eee);
  flex: 1;
}

.run-id {
  font-size: 12px;
  color: var(--text-secondary, #666);
  font-family: var(--font-mono, monospace);
}

/* Gate Progress */
.gate-progress {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.gate-step {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--card-border, #2a2a2a);
  border-radius: 10px;
  transition: all 0.2s;
}

.gate-step.approved { border-color: rgba(34,197,94,0.3); background: rgba(34,197,94,0.05); }
.gate-step.awaiting_review { border-color: rgba(245,166,35,0.3); background: rgba(245,166,35,0.05); }
.gate-step.rejected { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.05); }

.step-icon { display: flex; align-items: center; }
.gate-step.approved .step-icon { color: #22c55e; }
.gate-step.awaiting_review .step-icon { color: #f5a623; }
.gate-step.rejected .step-icon { color: #ef4444; }
.gate-step.pending .step-icon { color: #666; }

.step-label { font-size: 13px; color: var(--text-secondary, #999); }
.gate-step.awaiting_review .step-label { color: #f5a623; font-weight: 500; }

/* Loading */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px;
  color: var(--text-secondary, #666);
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--card-border, #2a2a2a);
  border-top-color: #f5a623;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Gate Detail */
.gate-detail {
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--card-border, #2a2a2a);
  border-radius: 12px;
  overflow: hidden;
}

.gate-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--card-border, #2a2a2a);
}

.gate-title { font-size: 16px; font-weight: 600; color: var(--text-primary, #eee); }

.gate-status {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 20px;
  font-weight: 500;
}
.gate-status.awaiting_review { background: rgba(245,166,35,0.15); color: #f5a623; }
.gate-status.approved { background: rgba(34,197,94,0.15); color: #22c55e; }
.gate-status.rejected { background: rgba(239,68,68,0.15); color: #ef4444; }

/* Items */
.items-list { padding: 16px 20px; }

.items-toolbar {
  margin-bottom: 12px;
}

.select-all {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary, #999);
  cursor: pointer;
}

.item-card {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--card-border, #2a2a2a);
  border-radius: 10px;
  margin-bottom: 8px;
  transition: all 0.2s;
}
.item-card.rejected { opacity: 0.5; border-color: rgba(239,68,68,0.2); }

.item-check {
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
}

.item-body { flex: 1; min-width: 0; }

.item-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #eee);
  margin-bottom: 6px;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
}

.platform-tag {
  background: rgba(245,166,35,0.1);
  color: #f5a623;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.source-link {
  color: var(--text-secondary, #666);
  text-decoration: none;
}
.source-link:hover { color: #f5a623; }

.item-preview {
  font-size: 12px;
  color: var(--text-secondary, #666);
  line-height: 1.5;
  max-height: 60px;
  overflow: hidden;
}

/* Requirement tags */
.sentiment-tag, .emotion-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}
.sentiment-tag.strong { background: rgba(239,68,68,0.15); color: #ef4444; }
.sentiment-tag.moderate { background: rgba(245,166,35,0.15); color: #f5a623; }
.sentiment-tag.mild { background: rgba(34,197,94,0.15); color: #22c55e; }
.emotion-tag.positive { background: rgba(34,197,94,0.15); color: #22c55e; }
.emotion-tag.negative { background: rgba(239,68,68,0.15); color: #ef4444; }
.emotion-tag.neutral { background: rgba(255,255,255,0.08); color: #999; }

.confidence { color: var(--text-secondary, #666); font-size: 12px; }

/* Verification scores */
.verification-scores {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}

.score-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.score-label { font-size: 11px; color: var(--text-secondary, #666); }
.score-value { font-size: 18px; font-weight: 600; color: var(--text-primary, #eee); }
.score-value.warn { color: #ef4444; }

/* Review Actions */
.review-actions {
  padding: 16px 20px;
  border-top: 1px solid var(--card-border, #2a2a2a);
}

.review-note {
  width: 100%;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--card-border, #2a2a2a);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--text-primary, #eee);
  font-size: 13px;
  resize: vertical;
  margin-bottom: 12px;
  font-family: inherit;
}
.review-note:focus { outline: none; border-color: #f5a623; }

.action-buttons {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn.approve {
  background: rgba(34,197,94,0.15);
  color: #22c55e;
  border-color: rgba(34,197,94,0.3);
}
.btn.approve:hover:not(:disabled) { background: rgba(34,197,94,0.25); }

.btn.reject {
  background: rgba(239,68,68,0.15);
  color: #ef4444;
  border-color: rgba(239,68,68,0.3);
}
.btn.reject:hover:not(:disabled) { background: rgba(239,68,68,0.25); }

.btn.edit {
  background: rgba(245,166,35,0.15);
  color: #f5a623;
  border-color: rgba(245,166,35,0.3);
}
.btn.edit:hover:not(:disabled) { background: rgba(245,166,35,0.25); }

/* Review Result */
.review-result {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid var(--card-border, #2a2a2a);
  font-size: 13px;
}

.result-label { color: var(--text-secondary, #666); }
.result-value.approved { color: #22c55e; font-weight: 500; }
.result-value.rejected { color: #ef4444; font-weight: 500; }
.result-note { color: var(--text-secondary, #666); font-style: italic; }

/* Empty */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px;
  color: var(--text-secondary, #666);
}
</style>
