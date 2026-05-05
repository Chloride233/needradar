<template>
  <div class="req-page">
    <!-- Summary Header -->
    <div class="summary-header">
      <div>
        <h2 class="summary-title">需求洞察汇总</h2>
        <p class="summary-desc">基于 {{ summaries.length }} 份分析报告，提取高优先级需求与关键痛点</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <span>分析报告中...</span>
    </div>

    <!-- Empty -->
    <div v-else-if="summaries.length === 0" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <p>暂无分析报告，请先执行挖掘任务生成报告</p>
    </div>

    <!-- Summaries -->
    <template v-else>
      <!-- High Priority Pain Points Summary -->
      <div class="section-card">
        <div class="section-head">
          <div class="section-icon icon-alert">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <div>
            <h3 class="section-title">高优先级痛点</h3>
            <span class="section-sub">跨报告合并的共性问题，按严重程度排列</span>
          </div>
        </div>
        <div class="pain-list">
          <div v-for="p in allPainPoints" :key="p.title" class="pain-item">
            <span class="pain-severity" :class="severityClass(p.severity)">{{ p.severity }}</span>
            <div class="pain-body">
              <span class="pain-title">{{ p.title }}</span>
              <p class="pain-desc" v-if="p.description">{{ p.description }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Core Findings per Report -->
      <div class="section-card">
        <div class="section-head">
          <div class="section-icon icon-insight">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
          </div>
          <div>
            <h3 class="section-title">核心洞察</h3>
            <span class="section-sub">每份报告的核心发现</span>
          </div>
        </div>
        <div class="findings-list">
          <div v-for="s in summaries" :key="s.report_title" class="finding-group">
            <div class="finding-source">
              <span class="finding-keyword">{{ s.keyword }}</span>
              <span class="finding-report">{{ s.report_title }}</span>
            </div>
            <div class="finding-items">
              <div v-for="(f, i) in s.core_findings" :key="i" class="finding-item">
                <span class="finding-num">{{ i + 1 }}</span>
                <span>{{ f }}</span>
              </div>
            </div>
            <div v-if="s.categories.length" class="finding-categories">
              <div v-for="cat in s.categories" :key="cat.name" class="cat-group">
                <span class="cat-name">{{ cat.name }}</span>
                <div class="cat-items">
                  <span v-for="item in cat.items" :key="item" class="cat-chip">{{ item }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '../api/client'

interface PainPoint {
  title: string
  severity: string
  description: string
}

interface InsightSummary {
  report_title: string
  keyword: string
  core_findings: string[]
  pain_points: PainPoint[]
  categories: { name: string; items: string[] }[]
}

const loading = ref(false)
const summaries = ref<InsightSummary[]>([])

const allPainPoints = computed(() => {
  const points: (PainPoint & { _order: number })[] = []
  summaries.value.forEach(s => {
    s.pain_points.forEach(p => {
      points.push({ ...p, _order: severityOrder(p.severity) })
    })
  })
  return points.sort((a, b) => b._order - a._order)
})

function severityOrder(s: string): number {
  if (s.includes('高') && !s.includes('中')) return 3
  if (s.includes('中到高') || s.includes('高')) return 2
  return 1
}

function severityClass(s: string): string {
  const order = severityOrder(s)
  if (order >= 3) return 'sev-high'
  if (order >= 2) return 'sev-med-high'
  return 'sev-med'
}

async function loadSummary() {
  loading.value = true
  try {
    const { data } = await api.get('/requirements/summary')
    summaries.value = data.summaries
  } finally {
    loading.value = false
  }
}

onMounted(loadSummary)
</script>

<style scoped>
.req-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Header ── */
.summary-header {
  background: linear-gradient(135deg, #1a1a1a, #141414);
  border-radius: 16px;
  padding: 24px 28px;
  color: #fff;
}

.summary-title {
  font-family: 'Outfit', sans-serif;
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}

.summary-desc {
  font-size: 13px;
  color: rgba(255,255,255,0.5);
}

/* ── Section Card ── */
.section-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
}

.section-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-alert {
  background: var(--error-bg);
  color: var(--error-text);
}

.icon-insight {
  background: rgba(99, 102, 241, 0.1);
  color: #818cf8;
}

.section-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
}

.section-sub {
  font-size: 12px;
  color: var(--slate-400);
}

/* ── Pain Points ── */
.pain-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pain-item {
  display: flex;
  gap: 14px;
  padding: 16px;
  border-radius: 12px;
  background: var(--slate-50);
  border: 1px solid transparent;
  transition: border-color 0.2s, background 0.2s, color 0.2s;
}

.pain-item:hover {
  background: #141414;
  border-color: var(--slate-200);
  border-color: var(--card-border-hover);
}

.pain-severity {
  padding: 4px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  height: fit-content;
  margin-top: 2px;
}

.sev-high { background: var(--error-bg); color: var(--error-text); }
.sev-med-high { background: var(--warning-bg); color: var(--warning-text); }
.sev-med { background: var(--slate-100); color: var(--slate-500); }

.pain-body {
  flex: 1;
  min-width: 0;
}

.pain-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-800);
  line-height: 1.5;
}

.pain-desc {
  font-size: 13px;
  color: var(--slate-500);
  line-height: 1.6;
  margin-top: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Findings ── */
.findings-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.finding-group {
  padding: 20px;
  border-radius: 14px;
  background: var(--slate-50);
  border: 1px solid var(--slate-100);
}

.finding-source {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.finding-keyword {
  display: inline-flex;
  padding: 3px 12px;
  border-radius: 8px;
  background: var(--teal-50);
  color: var(--teal-700);
  font-size: 12px;
  font-weight: 600;
}

.finding-report {
  font-size: 13px;
  color: var(--slate-500);
}

.finding-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.finding-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 14px;
  color: var(--slate-700);
  line-height: 1.6;
}

.finding-num {
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: var(--teal-600);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Outfit', sans-serif;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;
}

.finding-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--slate-200);
}

.cat-group {
  flex: 1;
  min-width: 200px;
}

.cat-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--slate-600);
  margin-bottom: 8px;
}

.cat-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cat-chip {
  padding: 4px 10px;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 500;
  background: #141414;
  color: var(--slate-600);
  border: 1px solid var(--slate-200);
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.cat-chip:hover {
  border-color: var(--teal-300);
  color: var(--teal-700);
  background: var(--teal-50);
}

/* ── Loading / Empty ── */
.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 64px 0;
  color: var(--slate-400);
  font-size: 14px;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--slate-200);
  border-top-color: var(--teal-500);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
