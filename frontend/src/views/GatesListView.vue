<template>
  <div class="gates-list-page" ref="pageRef">
    <!-- Hero -->
    <div class="page-hero" data-reveal="up">
      <div class="hero-orb hero-orb--1"></div>
      <div class="hero-orb hero-orb--2"></div>
      <div class="hero-content">
        <h1 class="page-title">质量门总览</h1>
        <p class="page-sub">所有管道的质量门状态一览</p>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters" data-reveal="up" data-delay="100">
      <button
        v-for="f in filterOptions"
        :key="f.value"
        class="filter-chip"
        :class="{ active: currentFilter === f.value }"
        @click="currentFilter = f.value; loadGates()"
      >
        {{ f.label }}
        <span v-if="f.count !== undefined" class="filter-count">{{ f.count }}</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <!-- Pending Gates (action required) -->
    <div v-if="!loading && pendingGates.length > 0" class="gates-section" data-reveal="up" data-delay="150">
      <h3 class="section-heading">
        <span class="section-heading-dot pulse"></span>
        待审门 ({{ pendingGates.length }})
      </h3>
      <div class="gates-grid">
        <div
          v-for="gate in pendingGates"
          :key="gate.id"
          class="gate-card gate-card--pending"
          role="button"
          tabindex="0"
          @click="$router.push(`/gates/${gate.pipeline_run_id}`)"
          @keydown.enter="$router.push(`/gates/${gate.pipeline_run_id}`)"
        >
          <div class="gate-card-header">
            <span class="gate-type" :class="gate.gate_type">{{ gateTypeLabel(gate.gate_type) }}</span>
            <span class="gate-status awaiting_review">待审查</span>
          </div>
          <div class="gate-card-body">
            <span class="gate-run">Run #{{ gate.pipeline_run_id }}</span>
            <span class="gate-items">{{ gate.items_count }} 项</span>
          </div>
          <div class="gate-card-footer">
            <span class="gate-time">{{ formatTime(gate.created_at) }}</span>
            <span class="gate-link gate-link--urgent">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              去审查
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- All Gates -->
    <div v-if="!loading" class="gates-section" data-reveal="up" data-delay="200">
      <h3 v-if="pendingGates.length > 0" class="section-heading">全部门记录</h3>
      <div v-if="gates.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <span>暂无质量门记录</span>
      </div>
      <div class="gates-grid">
        <div
          v-for="gate in gates"
          :key="gate.id"
          class="gate-card"
          role="button"
          tabindex="0"
          @click="$router.push(`/gates/${gate.pipeline_run_id}`)"
          @keydown.enter="$router.push(`/gates/${gate.pipeline_run_id}`)"
        >
          <div class="gate-card-header">
            <span class="gate-type" :class="gate.gate_type">{{ gateTypeLabel(gate.gate_type) }}</span>
            <span class="gate-status" :class="gate.status">{{ statusLabel(gate.status) }}</span>
          </div>
          <div class="gate-card-body">
            <span class="gate-run">Run #{{ gate.pipeline_run_id }}</span>
            <span class="gate-items">{{ gate.items_count }} 项</span>
          </div>
          <div class="gate-card-footer">
            <span class="gate-time">{{ formatTime(gate.created_at) }}</span>
            <span v-if="gate.status === 'awaiting_review'" class="gate-link gate-link--urgent">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              去审查
            </span>
            <span v-else class="gate-link">查看详情 →</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useReveal } from '../composables/useReveal'
import api from '../api/client'

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

interface Gate {
  id: number
  pipeline_run_id: number
  gate_type: string
  status: string
  items_count: number
  created_at: string
}

const gates = ref<Gate[]>([])
const loading = ref(true)
const currentFilter = ref('')
const totalCount = ref(0)

const pendingGates = computed(() => gates.value.filter(g => g.status === 'awaiting_review'))

// Re-trigger reveal whenever gates data changes (covers initial load + filter switch)
watch(gates, () => {
  nextTick(() => {
    pageRef.value?.querySelectorAll('[data-reveal]:not([data-revealed])').forEach((el) => {
      el.setAttribute('data-revealed', '')
    })
  })
}, { flush: 'post' })

const filterOptions = ref([
  { label: '全部', value: '', count: 0 },
  { label: '待审', value: 'awaiting_review', count: 0 },
  { label: '已通过', value: 'approved', count: 0 },
  { label: '已驳回', value: 'rejected', count: 0 },
])

async function loadGates() {
  loading.value = true
  try {
    const params: Record<string, any> = { page_size: 50 }
    if (currentFilter.value) params.status = currentFilter.value
    const { data } = await api.get('/gates', { params })
    gates.value = data.items || []
    totalCount.value = data.total || 0

    // Update counts
    if (!currentFilter.value) {
      filterOptions.value[0].count = data.total
    }
  } catch {
    gates.value = []
  } finally {
    loading.value = false
  }
}

async function loadCounts() {
  try {
    const [all, pending, approved, rejected] = await Promise.allSettled([
      api.get('/gates', { params: { page_size: 1 } }),
      api.get('/gates', { params: { status: 'awaiting_review', page_size: 1 } }),
      api.get('/gates', { params: { status: 'approved', page_size: 1 } }),
      api.get('/gates', { params: { status: 'rejected', page_size: 1 } }),
    ])
    if (all.status === 'fulfilled') filterOptions.value[0].count = all.value.data.total
    if (pending.status === 'fulfilled') filterOptions.value[1].count = pending.value.data.total
    if (approved.status === 'fulfilled') filterOptions.value[2].count = approved.value.data.total
    if (rejected.status === 'fulfilled') filterOptions.value[3].count = rejected.value.data.total
  } catch { /* ignore */ }
}

function gateTypeLabel(t: string): string {
  const map: Record<string, string> = { material: '素材确认', requirement: '需求确认', insight: '洞察确认' }
  return map[t] || t
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: '待处理', awaiting_review: '待审', approved: '已通过', rejected: '已驳回', editing: '编辑中',
  }
  return map[s] || s
}

function formatTime(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  loadGates()
  loadCounts()
})
</script>

<style scoped>
.gates-list-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ── Hero ── */
.page-hero {
  position: relative;
  padding: var(--space-7) 0 var(--space-5);
  overflow: hidden;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
}

.hero-orb--1 {
  width: 250px;
  height: 250px;
  background: rgba(255, 149, 0, 0.1);
  top: 0;
  left: 30%;
}

.hero-orb--2 {
  width: 200px;
  height: 200px;
  background: rgba(0, 122, 255, 0.08);
  top: 10%;
  right: 25%;
}

.hero-content {
  position: relative;
  text-align: center;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.03em;
  margin-bottom: var(--space-2);
}

.page-sub {
  font-size: 15px;
  color: var(--color-text-secondary);
}

/* ── Filters ── */
.filters {
  display: flex;
  gap: var(--space-2);
  justify-content: center;
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  background: var(--glass-bg);
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: all var(--duration-fast) var(--ease-apple);
}

.filter-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.filter-chip.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.filter-count {
  font-size: 11px;
  font-weight: 700;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: rgba(0, 0, 0, 0.1);
}

.filter-chip.active .filter-count {
  background: rgba(255, 255, 255, 0.25);
}

/* ── Loading ── */
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

/* ── Empty ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8);
  color: var(--color-text-tertiary);
  font-size: 15px;
}

/* ── Section ── */
.gates-section {
  margin-bottom: var(--space-6);
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-4);
}

.section-heading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-warning);
}

.section-heading-dot.pulse {
  animation: pulse-glow 2s ease-in-out infinite;
}

/* ── Gates Grid ── */
.gates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
  padding-bottom: var(--space-8);
}

.gate-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  cursor: pointer;
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              border-color var(--duration-normal) var(--ease-apple);
}

.gate-card:hover {
  box-shadow: var(--shadow-glass-hover);
  border-color: rgba(0, 122, 255, 0.2);
}

.gate-card--pending {
  border-color: rgba(255, 149, 0, 0.25);
  background: rgba(255, 149, 0, 0.04);
}

.gate-card--pending:hover {
  border-color: rgba(255, 149, 0, 0.4);
  box-shadow: 0 4px 20px rgba(255, 149, 0, 0.12);
}

.gate-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.gate-type {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-full);
}

.gate-type.material {
  background: rgba(0, 122, 255, 0.1);
  color: var(--color-primary);
}

.gate-type.requirement {
  background: rgba(88, 86, 214, 0.1);
  color: var(--color-secondary);
}

.gate-type.insight {
  background: rgba(52, 199, 89, 0.1);
  color: var(--color-success);
}

.gate-status {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.gate-status.awaiting_review {
  background: rgba(255, 149, 0, 0.1);
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

.gate-status.pending {
  background: var(--color-bg-secondary);
  color: var(--color-text-tertiary);
}

.gate-card-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.gate-run {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.gate-items {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.gate-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.gate-time {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.gate-link {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 500;
}

.gate-link--urgent {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-warning);
  font-weight: 600;
  padding: 4px 12px;
  background: rgba(255, 149, 0, 0.08);
  border-radius: var(--radius-full);
  transition: background var(--duration-fast);
}

.gate-link--urgent:hover {
  background: rgba(255, 149, 0, 0.15);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .page-title { font-size: 24px; }
  .gates-grid { grid-template-columns: 1fr; }
}
</style>
