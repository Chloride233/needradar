<template>
  <div class="usage-page">
    <!-- Budget Alert -->
    <div v-if="budgetAlerts.length" class="alert-banner">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      <div>
        <div v-for="a in budgetAlerts" :key="a.level">{{ a.message }}</div>
      </div>
    </div>

    <!-- Summary Cards -->
    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-icon icon-blue">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
        </div>
        <div class="summary-body">
          <div class="summary-label">总请求次数</div>
          <div class="summary-value">{{ formatInt(summary.requests) }}</div>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon icon-emerald">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
          </svg>
        </div>
        <div class="summary-body">
          <div class="summary-label">总费用 (CNY)</div>
          <div class="summary-value">¥{{ summary.total_cost_cny?.toFixed(4) ?? '0.0000' }}</div>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon icon-violet">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>
          </svg>
        </div>
        <div class="summary-body">
          <div class="summary-label">总 Token 数</div>
          <div class="summary-value">{{ formatInt(summary.total_tokens) }}</div>
          <div class="summary-sub">输入 {{ formatK(summary.input_tokens) }}k · 输出 {{ formatK(summary.output_tokens) }}k</div>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon icon-amber">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
          </svg>
        </div>
        <div class="summary-body">
          <div class="summary-label">缓存命中率</div>
          <div class="summary-value">{{ cacheHitRate }}%</div>
          <div class="summary-sub">{{ formatInt(summary.cached_tokens) }} tokens cached</div>
        </div>
      </div>
    </div>

    <!-- Trend Chart -->
    <div class="chart-card">
      <div class="card-top">
        <h3 class="card-title">用量趋势</h3>
        <select v-model="days" class="range-select" @change="loadSummary">
          <option :value="1">今天</option>
          <option :value="7">最近 7 天</option>
          <option :value="30">最近 30 天</option>
          <option :value="90">最近 90 天</option>
        </select>
      </div>
      <div ref="chartRef" class="chart-area"></div>
    </div>

    <!-- Tabs -->
    <div class="tabs-card">
      <div class="tab-bar">
        <button class="tab-btn" :class="{ active: activeTab === 'logs' }" @click="activeTab = 'logs'; onTabChange()">请求记录</button>
        <button class="tab-btn" :class="{ active: activeTab === 'modelStats' }" @click="activeTab = 'modelStats'; onTabChange()">模型统计</button>
      </div>

      <!-- Logs Tab -->
      <div v-if="activeTab === 'logs'">
        <div class="log-filters">
          <input v-model="filterModel" placeholder="筛选模型..." class="log-filter-input" @keyup.enter="applyFilter" />
          <select v-model="filterType" class="log-filter-select" @change="applyFilter">
            <option value="">全部类型</option>
            <option value="completion">Completion</option>
            <option value="embedding">Embedding</option>
            <option value="test">Test</option>
          </select>
        </div>
        <n-data-table
          :columns="logColumns"
          :data="records"
          :loading="loadingRecords"
          :pagination="tablePagination"
          :row-key="(r: any) => r.id"
          remote
          @update:page="onPageChange"
        />
      </div>

      <!-- Model Stats Tab -->
      <div v-if="activeTab === 'modelStats'">
        <n-data-table
          :columns="modelColumns"
          :data="modelStats"
          :loading="loadingModelStats"
          :bordered="false"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, h } from 'vue'
import { NTag } from 'naive-ui'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'
import api from '../api/client'

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const days = ref(30)
const summary = ref<any>({})
const budgetAlerts = ref<any[]>([])
const records = ref<any[]>([])
const modelStats = ref<any[]>([])
const loadingRecords = ref(false)
const loadingModelStats = ref(false)
const chartRef = ref<HTMLElement>()
let chart: ECharts | null = null

const activeTab = ref('logs')
const filterModel = ref('')
const filterType = ref<string | null>(null)

const currentPage = ref(1)
const pageSize = 20

const tablePagination = ref({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: false,
  prefix: ({ itemCount }: { itemCount: number }) => `共 ${itemCount} 条`,
})

const cacheHitRate = computed(() => {
  const inp = summary.value.input_tokens
  if (!inp) return '0.0'
  return ((summary.value.cached_tokens / inp) * 100).toFixed(1)
})

const logColumns = [
  {
    title: '时间',
    key: 'created_at',
    width: 160,
    render: (row: any) => new Date(row.created_at).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
    }),
  },
  { title: '模型', key: 'model', width: 220, ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'call_type',
    width: 100,
    render: (row: any) => h(NTag, {
      size: 'small',
      type: row.call_type === 'embedding' ? 'info' : row.call_type === 'test' ? 'warning' : 'success',
    }, { default: () => row.call_type }),
  },
  { title: '输入', key: 'input_tokens', width: 100, render: (row: any) => formatInt(row.input_tokens) },
  { title: '输出', key: 'output_tokens', width: 100, render: (row: any) => formatInt(row.output_tokens) },
  { title: '缓存', key: 'cached_tokens', width: 100, render: (row: any) => formatInt(row.cached_tokens) },
  { title: '费用 (¥)', key: 'cost_cny', width: 110, render: (row: any) => `¥${row.cost_cny?.toFixed(4)}` },
]

const modelColumns = [
  { title: '模型', key: 'model', width: 220, ellipsis: { tooltip: true } },
  {
    title: '类型', key: 'call_type', width: 100,
    render: (row: any) => h(NTag, {
      size: 'small',
      type: row.call_type === 'embedding' ? 'info' : row.call_type === 'test' ? 'warning' : 'success',
    }, { default: () => row.call_type }),
  },
  { title: '请求数', key: 'requests', width: 90, render: (row: any) => formatInt(row.requests) },
  { title: '总 Tokens', key: 'total_tokens', width: 120, render: (row: any) => formatInt(row.total_tokens) },
  { title: '输入', key: 'input_tokens', width: 100, render: (row: any) => formatK(row.input_tokens) + 'k' },
  { title: '输出', key: 'output_tokens', width: 100, render: (row: any) => formatK(row.output_tokens) + 'k' },
  { title: '缓存', key: 'cached_tokens', width: 100, render: (row: any) => formatK(row.cached_tokens) + 'k' },
  { title: '总费用 (¥)', key: 'total_cost_cny', width: 120, render: (row: any) => `¥${row.total_cost_cny?.toFixed(4)}` },
  { title: '平均费用 (¥)', key: 'avg_cost_cny', width: 120, render: (row: any) => `¥${row.avg_cost_cny?.toFixed(6)}` },
]

function formatInt(n: number) { return !n ? '0' : Math.trunc(n).toLocaleString('zh-CN') }
function formatK(n: number) { return !n ? '0.0' : (n / 1000).toFixed(1) }

async function loadSummary() {
  try {
    const { data } = await api.get('/usage/summary', { params: { days: days.value } })
    summary.value = data
    await loadTrend()
    if (activeTab.value === 'modelStats') loadModelStats()
  } catch { /* handled by interceptor */ }
}

async function loadTrend() {
  const { data } = await api.get('/usage/trend', { params: { days: days.value } })
  await nextTick()
  if (!chart && chartRef.value) {
    chart = echarts.init(chartRef.value) as unknown as ECharts
  }
  if (!chart) return
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, backgroundColor: '#1a1a1a', borderColor: '#2a2a2a', borderWidth: 1, textStyle: { color: '#e0e0e0', fontFamily: "'Inter', sans-serif" } },
    legend: { data: ['请求数', 'Token 数', '费用 (¥)'], textStyle: { fontFamily: "'Inter', sans-serif", color: '#a0a0a0' }, top: 4 },
    grid: { left: 60, right: 60, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: data.map((d: any) => d.date), axisLine: { lineStyle: { color: '#e2e8f0' } }, axisLabel: { color: '#666666', fontSize: 11 } },
    yAxis: [
      { type: 'value', name: '请求/Token', splitLine: { lineStyle: { color: '#f1f5f9' } }, axisLabel: { color: '#666666' } },
      { type: 'value', name: '费用 (¥)', splitLine: { show: false }, axisLabel: { color: '#666666' } },
    ],
    series: [
      {
        name: '请求数', type: 'bar', data: data.map((d: any) => d.requests),
        itemStyle: { color: '#0d9488', borderRadius: [5, 5, 0, 0] }, barWidth: 16,
      },
      {
        name: 'Token 数', type: 'line', data: data.map((d: any) => d.tokens), smooth: true,
        lineStyle: { color: '#8b5cf6', width: 2 }, itemStyle: { color: '#8b5cf6' }, symbol: 'circle', symbolSize: 4,
      },
      {
        name: '费用 (¥)', type: 'line', yAxisIndex: 1, data: data.map((d: any) => d.cost_cny), smooth: true,
        lineStyle: { color: '#10b981', width: 2 }, itemStyle: { color: '#10b981' }, symbol: 'circle', symbolSize: 4,
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(16,185,129,0.15)' }, { offset: 1, color: 'rgba(16,185,129,0)' }] } },
      },
    ],
  })
}

async function loadRecords() {
  loadingRecords.value = true
  try {
    const params: any = { limit: pageSize, offset: (currentPage.value - 1) * pageSize }
    if (filterModel.value) params.model = filterModel.value
    if (filterType.value) params.call_type = filterType.value
    const { data } = await api.get('/usage/records', { params })
    records.value = data.items
    tablePagination.value.itemCount = data.total
    tablePagination.value.page = currentPage.value
  } finally {
    loadingRecords.value = false
  }
}

async function loadModelStats() {
  loadingModelStats.value = true
  try {
    const { data } = await api.get('/usage/model-stats', { params: { days: days.value } })
    modelStats.value = data
  } finally {
    loadingModelStats.value = false
  }
}

function onPageChange(page: number) { currentPage.value = page; loadRecords() }
function applyFilter() { currentPage.value = 1; loadRecords() }
function onTabChange() { if (activeTab.value === 'modelStats' && !modelStats.value.length) loadModelStats() }

async function loadBudget() {
  try {
    const { data } = await api.get('/usage/budget')
    budgetAlerts.value = data.alerts || []
  } catch { /* handled by interceptor */ }
}

function handleResize() { chart?.resize() }

onMounted(() => { loadSummary(); loadRecords(); loadBudget(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { chart?.dispose(); window.removeEventListener('resize', handleResize) })
</script>

<style scoped>
.usage-page {
  display: flex;
  flex-direction: column;
  gap: 20px;

}


/* ── Alert Banner ── */
.alert-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-radius: 12px;
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  color: var(--error-text);
  font-size: 13px;
  font-weight: 500;
}

/* ── Summary Grid ── */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.summary-card {
  background: #141414;
  border-radius: 14px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 20px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  transition: transform 0.25s ease, border-color 0.25s ease;
}

.summary-card:hover {
  transform: translateY(-2px);
  border-color: var(--card-border-hover);
}

.summary-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-blue { background: rgba(99, 102, 241, 0.1); color: #818cf8; }
.icon-emerald { background: var(--success-bg); color: #059669; }
.icon-violet { background: rgba(124, 58, 237, 0.1); color: #a78bfa; }
.icon-amber { background: var(--warning-bg); color: #d97706; }

.summary-body { flex: 1; }

.summary-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--slate-400);
  margin-bottom: 6px;
}

.summary-value {
  font-family: 'Outfit', sans-serif;
  font-size: 26px;
  font-weight: 700;
  color: var(--slate-900);
  letter-spacing: -0.02em;
  line-height: 1.1;
}

.summary-sub {
  font-size: 12px;
  color: var(--slate-400);
  margin-top: 4px;
}

/* ── Chart Card ── */
.chart-card {
  background: #141414;
  border-radius: 14px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
}

.range-select {
  height: 34px;
  padding: 0 28px 0 12px;
  border-radius: 8px;
  border: 1.5px solid var(--slate-200);
  font-size: 12px;
  font-family: inherit;
  color: var(--slate-600);
  background: var(--slate-50);
  outline: none;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
}

.chart-area { height: 320px; }

/* ── Tabs Card ── */
.tabs-card {
  background: #141414;
  border-radius: 14px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  padding: 3px;
  background: var(--slate-100);
  border-radius: 10px;
  width: fit-content;
}

.tab-btn {
  padding: 7px 20px;
  border-radius: 8px;
  border: none;
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  color: var(--slate-500);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.tab-btn.active {
  background: #141414;
  color: var(--slate-800);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  font-weight: 600;
}

.log-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.log-filter-input {
  height: 34px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1.5px solid var(--slate-200);
  font-size: 13px;
  font-family: inherit;
  color: var(--slate-700);
  background: var(--slate-50);
  outline: none;
  width: 180px;
  transition: border-color 0.2s, background 0.2s;
}

.log-filter-input:focus {
  border-color: var(--teal-400);
  background: #141414;
  box-shadow: 0 0 0 3px rgba(20,196,166,0.15);
}

.log-filter-select {
  height: 34px;
  padding: 0 28px 0 12px;
  border-radius: 8px;
  border: 1.5px solid var(--slate-200);
  font-size: 13px;
  font-family: inherit;
  color: var(--slate-700);
  background: var(--slate-50);
  outline: none;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
}
</style>
