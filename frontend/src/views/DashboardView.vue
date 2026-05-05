<template>
  <div class="dashboard">
    <div v-if="loadError" class="error-banner">
      <div class="error-banner-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      </div>
      <span>数据加载失败，请稍后刷新页面重试</span>
      <button class="retry-btn" @click="loadData">重试</button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>正在加载数据...</span>
    </div>

    <template v-if="!loading && !loadError">
    <!-- Stat Cards Row -->
    <div class="stat-row">
      <div class="stat-card stat-teal">
        <div class="stat-card-glow"></div>
        <div class="stat-card-content">
          <div class="stat-card-header">
            <span class="stat-label">总需求数</span>
            <div class="stat-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
          </div>
          <div class="stat-value">{{ stats.total_requirements }}</div>
          <div class="stat-bar"><div class="stat-bar-fill bar-teal"></div></div>
        </div>
      </div>

      <div class="stat-card stat-amber">
        <div class="stat-card-glow"></div>
        <div class="stat-card-content">
          <div class="stat-card-header">
            <span class="stat-label">爬取任务</span>
            <div class="stat-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            </div>
          </div>
          <div class="stat-value">{{ stats.total_tasks }}</div>
          <div class="stat-bar"><div class="stat-bar-fill bar-amber"></div></div>
        </div>
      </div>

      <div class="stat-card stat-emerald">
        <div class="stat-card-glow"></div>
        <div class="stat-card-content">
          <div class="stat-card-header">
            <span class="stat-label">数据源</span>
            <div class="stat-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z"/>
              </svg>
            </div>
          </div>
          <div class="stat-value">{{ Object.keys(stats.platform_distribution).length }}</div>
          <div class="stat-bar"><div class="stat-bar-fill bar-emerald"></div></div>
        </div>
      </div>

      <div class="stat-card stat-slate">
        <div class="stat-card-glow"></div>
        <div class="stat-card-content">
          <div class="stat-card-header">
            <span class="stat-label">追踪关键词</span>
            <div class="stat-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
            </div>
          </div>
          <div class="stat-value">{{ stats.top_keywords.length }}</div>
          <div class="stat-bar"><div class="stat-bar-fill bar-slate"></div></div>
        </div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="charts-row">
      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">平台分布</h3>
          <span class="chart-subtitle">各数据源需求量占比</span>
        </div>
        <div class="chart-body">
          <v-chart :option="platformOption" autoresize />
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-header">
          <h3 class="chart-title">情感分布</h3>
          <span class="chart-subtitle">用户需求强烈程度</span>
        </div>
        <div class="chart-body">
          <v-chart :option="sentimentOption" autoresize />
        </div>
      </div>
    </div>

    <!-- Keywords Section -->
    <div class="keywords-card">
      <div class="chart-header">
        <h3 class="chart-title">热门关键词</h3>
        <span class="chart-subtitle">按需求提及频次排序</span>
      </div>
      <div class="keyword-tags">
        <span v-for="(kw, i) in stats.top_keywords" :key="kw" class="kw-tag" :class="'kw-rank-' + Math.min(i, 3)">
          {{ kw }}
        </span>
        <div v-if="!stats.top_keywords.length" class="empty-hint">暂无数据，请先执行爬取任务</div>
      </div>
    </div>

    <!-- Recent Activity -->
    <div class="activity-card">
      <div class="chart-header">
        <h3 class="chart-title">最近任务</h3>
        <router-link to="/tasks" class="chart-subtitle" style="text-decoration: none; color: var(--teal-400);">查看全部</router-link>
      </div>
      <div v-if="recentTasks.length === 0" class="empty-hint">暂无任务记录</div>
      <div v-else class="activity-list">
        <div v-for="task in recentTasks" :key="task.id" class="activity-item">
          <div class="activity-dot" :class="'dot-' + task.status"></div>
          <div class="activity-body">
            <span class="activity-keyword">{{ task.keyword }}</span>
            <span class="activity-meta">{{ task.platform }}</span>
          </div>
          <span class="activity-badge" :class="'badge-' + task.status">{{ statusLabel[task.status] }}</span>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const loading = ref(true)
const loadError = ref(false)

async function loadData() {
  loading.value = true
  loadError.value = false
  try {
    const { data } = await api.get('/dashboard')
    stats.value = data
    const { data: taskData } = await api.get('/tasks', { params: { page_size: 5 } })
    recentTasks.value = taskData.items
  } catch (e) {
    console.error('[Dashboard] load failed:', e)
    loadError.value = true
  } finally {
    loading.value = false
  }
}
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import api from '../api/client'

use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

interface DashboardStats {
  total_requirements: number
  total_tasks: number
  platform_distribution: Record<string, number>
  sentiment_distribution: Record<string, number>
  top_keywords: string[]
}

const stats = ref<DashboardStats>({
  total_requirements: 0,
  total_tasks: 0,
  platform_distribution: {},
  sentiment_distribution: {},
  top_keywords: [],
})

const platformColors = ['#14c4a6', '#f59e0b', '#818cf8', '#ec4899', '#8b5cf6', '#06b6d4']

const platformOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    backgroundColor: '#1a1a1a',
    borderColor: '#2a2a2a',
    borderWidth: 1,
    textStyle: { color: '#e0e0e0', fontFamily: "'Inter', sans-serif", fontSize: 13 },
    formatter: '{b}: {c} ({d}%)',
  },
  series: [{
    type: 'pie',
    radius: ['45%', '72%'],
    center: ['50%', '50%'],
    itemStyle: { borderColor: '#141414', borderWidth: 3, borderRadius: 6 },
    label: {
      formatter: '{b}\n{d}%',
      color: '#a0a0a0',
      fontSize: 12,
      fontFamily: "'Inter', sans-serif",
      lineHeight: 18,
    },
    labelLine: { length: 12, length2: 8, lineStyle: { color: '#363636' } },
    emphasis: {
      scaleSize: 8,
      itemStyle: { shadowBlur: 20, shadowColor: 'rgba(0,0,0,0.3)' },
    },
    data: Object.entries(stats.value.platform_distribution).map(([name, value], i) => ({
      name, value,
      itemStyle: { color: platformColors[i % platformColors.length] },
    })),
  }],
}))

const sentimentColors: Record<string, string> = { strong: '#fb7185', moderate: '#14c4a6', mild: '#666666' }
const sentimentLabels: Record<string, string> = { strong: '强烈', moderate: '一般', mild: '轻微' }

const sentimentOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    backgroundColor: '#1a1a1a',
    borderColor: '#2a2a2a',
    borderWidth: 1,
    textStyle: { color: '#e0e0e0', fontFamily: "'Inter', sans-serif", fontSize: 13 },
    formatter: '{b}: {c} ({d}%)',
  },
  series: [{
    type: 'pie',
    radius: ['45%', '72%'],
    center: ['50%', '50%'],
    itemStyle: { borderColor: '#141414', borderWidth: 3, borderRadius: 6 },
    label: {
      formatter: '{b}\n{d}%',
      color: '#a0a0a0',
      fontSize: 12,
      fontFamily: "'Inter', sans-serif",
      lineHeight: 18,
    },
    labelLine: { length: 12, length2: 8, lineStyle: { color: '#363636' } },
    emphasis: {
      scaleSize: 8,
      itemStyle: { shadowBlur: 20, shadowColor: 'rgba(0,0,0,0.3)' },
    },
    data: Object.entries(stats.value.sentiment_distribution).map(([name, value]) => ({
      name: sentimentLabels[name] || name,
      value,
      itemStyle: { color: sentimentColors[name] || '#666666' },
    })),
  }],
}))

onMounted(loadData)

interface TaskItem {
  id: number
  keyword: string
  platform: string
  status: string
  total_items: number
  created_at: string
  updated_at?: string
}

const recentTasks = ref<TaskItem[]>([])

const statusLabel: Record<string, string> = {
  pending: '排队中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 12px;
  color: var(--error-text);
  font-size: 14px;
}

.error-banner-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(244, 63, 94, 0.08);
}

.retry-btn {
  margin-left: auto;
  padding: 6px 16px;
  border-radius: 8px;
  border: 1px solid var(--error-border);
  background: rgba(244, 63, 94, 0.06);
  color: var(--error-text);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.retry-btn:hover {
  background: rgba(244, 63, 94, 0.12);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 80px 0;
  color: var(--slate-500);
  font-size: 14px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--slate-300);
  border-top-color: var(--teal-500);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Stat Cards ── */
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
}

.stat-card {
  position: relative;
  background: #141414;
  border-radius: 12px;
  padding: 22px 24px;
  overflow: hidden;
  border: 1px solid var(--card-border);
  transition: border-color 0.3s ease;
}

.stat-card:hover {
  border-color: var(--card-border-hover);
}

.stat-card-glow {
  position: absolute;
  top: -30px;
  right: -30px;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  opacity: 0.06;
}

.stat-teal .stat-card-glow { background: var(--teal-500); }
.stat-amber .stat-card-glow { background: var(--amber-500); }
.stat-emerald .stat-card-glow { background: var(--emerald-500); }
.stat-slate .stat-card-glow { background: var(--slate-400); }

.stat-card-content { position: relative; z-index: 1; }

.stat-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.stat-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--slate-500);
}

.stat-icon-wrap {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-teal .stat-icon-wrap { background: var(--teal-50); color: var(--teal-400); }
.stat-amber .stat-icon-wrap { background: rgba(245, 158, 11, 0.1); color: var(--amber-500); }
.stat-emerald .stat-icon-wrap { background: rgba(52, 211, 153, 0.1); color: var(--emerald-500); }
.stat-slate .stat-icon-wrap { background: var(--slate-100); color: var(--slate-500); }

.stat-value {
  font-family: 'Outfit', sans-serif;
  font-size: 32px;
  font-weight: 700;
  color: var(--slate-900);
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-bottom: 14px;
}

.stat-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--slate-200);
  overflow: hidden;
}

.stat-bar-fill {
  height: 100%;
  border-radius: 2px;
  width: 70%;
  animation: barGrow 1.2s ease-out;
}

@keyframes barGrow {
  from { width: 0; }
}

.bar-teal { background: linear-gradient(90deg, var(--teal-300), var(--teal-500)); }
.bar-amber { background: linear-gradient(90deg, #fcd34d, var(--amber-500)); }
.bar-emerald { background: linear-gradient(90deg, #34d399, var(--emerald-500)); }
.bar-slate { background: linear-gradient(90deg, var(--slate-400), var(--slate-500)); }

/* ── Charts ── */
.charts-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}

.chart-card {
  background: #141414;
  border-radius: 12px;
  border: 1px solid var(--card-border);
  padding: 24px;
  transition: border-color 0.3s ease;
}

.chart-card:hover {
  border-color: var(--card-border-hover);
}

.chart-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 20px;
}

.chart-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
}

.chart-subtitle {
  font-size: 12px;
  color: var(--slate-500);
}

.chart-body {
  height: 280px;
}

.chart-body .echarts {
  width: 100% !important;
  height: 100% !important;
}

/* ── Keywords ── */
.keywords-card {
  background: #141414;
  border-radius: 12px;
  border: 1px solid var(--card-border);
  padding: 24px;
}

.keyword-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.kw-tag {
  display: inline-flex;
  align-items: center;
  padding: 7px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  background: var(--slate-100);
  color: var(--slate-600);
  border: 1px solid var(--slate-200);
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.kw-tag:hover {
  border-color: var(--teal-200);
  color: var(--teal-400);
  background: var(--teal-50);
}

.kw-rank-0 {
  background: var(--teal-50);
  color: var(--teal-400);
  border-color: var(--teal-200);
  font-weight: 600;
}

.kw-rank-1 {
  background: rgba(245, 158, 11, 0.1);
  color: var(--amber-500);
  border-color: rgba(245, 158, 11, 0.2);
}

.kw-rank-2 {
  background: rgba(52, 211, 153, 0.1);
  color: var(--emerald-500);
  border-color: rgba(52, 211, 153, 0.2);
}

.kw-rank-3 {
  background: rgba(99, 102, 241, 0.1);
  color: #818cf8;
  border-color: rgba(99, 102, 241, 0.2);
}

.empty-hint {
  color: var(--slate-500);
  font-size: 14px;
  padding: 12px 0;
}

/* ── Activity ── */
.activity-card {
  background: #141414;
  border-radius: 12px;
  border: 1px solid var(--card-border);
  padding: 24px;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  transition: background 0.15s;
}

.activity-item:hover {
  background: var(--slate-100);
}

.activity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-pending { background: var(--slate-500); }
.dot-running { background: var(--teal-500); animation: pulse 2s ease-in-out infinite; }
.dot-completed { background: var(--emerald-500); }
.dot-failed { background: #fb7185; }

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(20,196,166,0.4); }
  50% { box-shadow: 0 0 0 5px rgba(20,196,166,0); }
}

.activity-body {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.activity-keyword {
  font-size: 14px;
  font-weight: 500;
  color: var(--slate-700);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.activity-meta {
  font-size: 12px;
  color: var(--slate-500);
  flex-shrink: 0;
}

.activity-badge {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.badge-pending { background: var(--slate-100); color: var(--slate-500); }
.badge-running { background: var(--teal-50); color: var(--teal-400); }
.badge-completed { background: var(--success-bg); color: var(--success-text); }
.badge-failed { background: var(--error-bg); color: var(--error-text); }
</style>
