<template>
  <div ref="pageRef" class="req-page">
    <!-- Hero -->
    <div class="hero" data-reveal="up">
      <div class="hero-orb hero-orb--blue"></div>
      <div class="hero-orb hero-orb--purple"></div>
      <div class="hero-content">
        <h1 class="hero-title">需求洞察汇总</h1>
        <p class="hero-sub">基于 {{ summaries.length }} 份分析报告，提取高优先级需求与关键痛点</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>分析报告中...</span>
    </div>

    <!-- Empty -->
    <div v-else-if="summaries.length === 0" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <p>暂无分析报告，请先执行挖掘任务生成报告</p>
    </div>

    <!-- Summaries -->
    <template v-else>
      <!-- High Priority Pain Points -->
      <div class="glass-card" data-reveal="up" data-delay="100">
        <div class="section-head">
          <div class="section-icon icon-alert">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </div>
          <div>
            <h3 class="section-title">高优先级痛点</h3>
            <span class="section-sub">跨报告合并的共性问题，按严重程度排列</span>
          </div>
        </div>
        <div class="pain-list">
          <div v-for="(p, i) in allPainPoints" :key="p.title" class="pain-item" data-reveal="up" :data-delay="(i * 50 + 150).toString()">
            <span class="pain-severity" :class="severityClass(p.severity)">{{ p.severity }}</span>
            <div class="pain-body">
              <span class="pain-title">{{ p.title }}</span>
              <p class="pain-desc" v-if="p.description">{{ p.description }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Core Findings per Report -->
      <div class="glass-card" data-reveal="up" data-delay="200">
        <div class="section-head">
          <div class="section-icon icon-insight">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
          </div>
          <div>
            <h3 class="section-title">核心洞察</h3>
            <span class="section-sub">每份报告的核心发现</span>
          </div>
        </div>
        <div class="findings-list">
          <div v-for="(s, gi) in summaries" :key="s.report_title" class="finding-group" data-reveal="up" :data-delay="(gi * 80 + 300).toString()">
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
import { useReveal } from '../composables/useReveal'

interface PainPoint { title: string; severity: string; description: string }
interface InsightSummary {
  report_title: string; keyword: string; core_findings: string[];
  pain_points: PainPoint[]; categories: { name: string; items: string[] }[]
}

const loading = ref(false)
const summaries = ref<InsightSummary[]>([])
const pageRef = ref<HTMLElement | null>(null)

useReveal(pageRef)

const allPainPoints = computed(() => {
  const points: (PainPoint & { _order: number })[] = []
  summaries.value.forEach(s => {
    s.pain_points.forEach(p => { points.push({ ...p, _order: severityOrder(p.severity) }) })
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
  } finally { loading.value = false }
}

onMounted(loadSummary)
</script>

<style scoped>
.req-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ── Hero ── */
.hero {
  position: relative;
  padding: var(--space-9) 0 var(--space-7);
  overflow: hidden;
  text-align: center;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
  pointer-events: none;
}

.hero-orb--blue {
  width: 320px;
  height: 320px;
  background: var(--color-primary);
  top: -40px;
  left: -60px;
  opacity: 0.12;
}

.hero-orb--purple {
  width: 280px;
  height: 280px;
  background: var(--color-secondary);
  bottom: -40px;
  right: -40px;
  opacity: 0.1;
}

.hero-content {
  position: relative;
  z-index: 1;
}

.hero-title {
  font-size: 40px;
  font-weight: 700;
  letter-spacing: -0.025em;
  color: var(--color-text);
  line-height: 1.15;
}

.hero-sub {
  font-size: 17px;
  color: var(--color-text-secondary);
  margin-top: var(--space-3);
  line-height: 1.5;
}

/* ── Glass Card ── */
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-6);
  transition: box-shadow var(--duration-normal) var(--ease-apple);
}

.glass-card:hover {
  box-shadow: var(--shadow-glass-hover);
}

/* ── Section Head ── */
.section-head {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.section-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-alert {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.icon-insight {
  background: rgba(88, 86, 214, 0.08);
  color: var(--color-secondary);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.01em;
}

.section-sub {
  font-size: 13px;
  color: var(--color-text-tertiary);
  display: block;
  margin-top: 2px;
}

/* ── Pain Points ── */
.pain-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.pain-item {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-normal) var(--ease-apple);
}

.pain-item:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-border);
  transform: translateY(-1px);
}

.pain-severity {
  padding: 4px 14px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  height: fit-content;
  margin-top: 2px;
}

.sev-high {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.sev-med-high {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.sev-med {
  background: var(--color-bg-tertiary);
  color: var(--color-text-secondary);
}

.pain-body {
  flex: 1;
  min-width: 0;
}

.pain-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.5;
}

.pain-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-top: var(--space-1);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Findings ── */
.findings-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.finding-group {
  padding: var(--space-5);
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-normal) var(--ease-apple);
}

.finding-group:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.finding-source {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.finding-keyword {
  display: inline-flex;
  padding: 4px 14px;
  border-radius: var(--radius-full);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
}

.finding-report {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.finding-items {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.finding-item {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  font-size: 14px;
  color: var(--color-text);
  line-height: 1.6;
}

.finding-num {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: var(--gradient-accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;
}

/* ── Categories ── */
.finding-categories {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--glass-border);
}

.cat-group {
  flex: 1;
  min-width: 200px;
}

.cat-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-2);
}

.cat-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cat-chip {
  padding: 4px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  background: var(--glass-bg);
  color: var(--color-text-secondary);
  border: 1px solid var(--glass-border);
  transition: all var(--duration-fast) var(--ease-apple);
}

.cat-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

/* ── Loading / Empty ── */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8) 0;
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--color-border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
