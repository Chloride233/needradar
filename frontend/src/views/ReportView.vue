<template>
  <div class="report-page">
    <!-- Generate -->
    <div class="generate-card">
      <div class="generate-content">
        <div class="generate-text">
          <h3 class="generate-title">生成需求洞察报告</h3>
          <p class="generate-desc">基于已采集的需求数据，自动生成结构化分析报告</p>
        </div>
        <div class="generate-action">
          <div class="generate-input-wrap">
            <input v-model="keyword" class="generate-input" placeholder="输入关键词..." @keyup.enter="generateReport" />
            <button class="generate-btn" :class="{ loading: generating }" @click="generateReport" :disabled="generating">
              <svg v-if="!generating" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
              <span v-else class="btn-spinner"></span>
              {{ generating ? '生成中...' : '生成报告' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Report Display (viewing a specific report) -->
    <div v-if="activeReport" class="report-card">
      <div class="report-toolbar">
        <div class="report-meta">
          <button class="back-btn" @click="activeReport = null">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
            </svg>
            返回列表
          </button>
          <span class="report-stage">{{ activeReport.stage }}</span>
          <h2 class="report-heading">{{ activeReport.title }}</h2>
          <span class="report-date">{{ activeReport.created_at }}</span>
        </div>
        <button class="download-btn" @click="downloadReport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Markdown
        </button>
        <button class="download-btn" @click="downloadHtml">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
          </svg>
          HTML
        </button>
        <button class="download-btn" @click="printReport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>
          </svg>
          Print / PDF
        </button>
        <button class="download-btn" @click="copyReport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
      <div class="report-body">
        <div class="markdown-content" v-html="renderedMarkdown"></div>
      </div>
    </div>

    <!-- Report List -->
    <div v-else class="list-card">
      <div class="list-header">
        <h3 class="list-title">
          历史报告
          <span class="list-count">{{ reports.length }} 份</span>
        </h3>
      </div>

      <div v-if="reports.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
        <p>暂无报告，输入关键词生成你的第一份洞察报告</p>
      </div>

      <div v-else class="report-list">
        <div v-for="report in reports" :key="report.title" class="report-item" @click="openReport(report)">
          <div class="report-item-left">
            <div class="report-item-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <div class="report-item-info">
              <span class="report-item-title">{{ report.title }}</span>
              <div class="report-item-meta">
                <span class="report-item-keyword">{{ report.keyword }}</span>
                <span class="report-item-sep">·</span>
                <span class="report-item-stage">{{ report.stage }}</span>
                <span class="report-item-sep">·</span>
                <span class="report-item-date">{{ report.created_at }}</span>
              </div>
            </div>
          </div>
          <svg class="report-item-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { marked } from 'marked'
import { sanitize } from '../utils/sanitize'
import api from '../api/client'

marked.setOptions({ breaks: true, gfm: true })

interface ReportItem {
  title: string
  keyword: string
  content: string
  stage: string
  created_at: string
}

const keyword = ref('')
const generating = ref(false)
const reports = ref<ReportItem[]>([])
const activeReport = ref<ReportItem | null>(null)
const copied = ref(false)
let lastGenerateTime = 0

const renderedMarkdown = computed(() => {
  if (!activeReport.value?.content) return ''
  let content = activeReport.value.content.replace(/\\n/g, '\n')
  return sanitize(marked.parse(content) as string)
})

async function generateReport() {
  if (!keyword.value.trim() || generating.value) return
  if (Date.now() - lastGenerateTime < 3000) return
  generating.value = true
  try {
    const { data } = await api.post('/reports', null, { params: { keyword: keyword.value } })
    activeReport.value = data
    lastGenerateTime = Date.now()
    await loadReports()
  } finally {
    generating.value = false
  }
}

async function loadReports() {
  try {
    const { data } = await api.get('/reports', { params: { page_size: 50 } })
    reports.value = data.items
  } catch { /* handled by interceptor */ }
}

async function openReport(report: ReportItem) {
  if (report.content) {
    activeReport.value = report
    return
  }
  // List API returns empty content — fetch full content by filename
  const filename = encodeURIComponent(report.title + '.md')
  try {
    const { data } = await api.get(`/reports/by-filename/${filename}`)
    activeReport.value = data
  } catch {
    // Fallback: re-generate on demand
    if (report.keyword) {
      const { data } = await api.post('/reports', null, { params: { keyword: report.keyword } })
      activeReport.value = data
    }
  }
}

function downloadReport() {
  if (!activeReport.value) return
  const blob = new Blob([activeReport.value.content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `needradar-${activeReport.value.keyword}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function downloadHtml() {
  if (!activeReport.value) return
  const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>${activeReport.value.title}</title>
<style>body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#1e293b;line-height:1.8}
h1{font-size:24px;border-bottom:2px solid #0d9488;padding-bottom:8px}h2{font-size:18px;margin-top:32px;border-bottom:1px solid #e2e8f0;padding-bottom:6px}
h3{font-size:16px;margin-top:24px}table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px}
td,th{padding:8px 12px;border:1px solid #e2e8f0;text-align:left}tr:first-child{background:#f8fafc;font-weight:600}
blockquote{border-left:3px solid #0d9488;padding:8px 16px;margin:12px 0;background:#f0fdfa}code{background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:13px}
hr{border:none;border-top:1px solid #e2e8f0;margin:24px 0}</style></head>
<body>${renderedMarkdown.value}</body></html>`
  const blob = new Blob([html], { type: 'text/html' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `needradar-${activeReport.value.keyword}.html`
  a.click()
  URL.revokeObjectURL(url)
}

function printReport() {
  if (!activeReport.value) return
  const safeHtml = sanitize(renderedMarkdown.value)
  const safeTitle = activeReport.value.title.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const printWin = window.open('', '_blank')
  if (!printWin) return
  printWin.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${safeTitle}</title>
<style>body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#1e293b;line-height:1.8}
h1{font-size:22px;border-bottom:2px solid #0d9488;padding-bottom:8px}h2{font-size:17px;margin-top:28px;border-bottom:1px solid #e2e8f0;padding-bottom:6px}
h3{font-size:15px;margin-top:20px}table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}
td,th{padding:8px 12px;border:1px solid #e2e8f0;text-align:left}tr:first-child{background:#f8fafc;font-weight:600}
blockquote{border-left:3px solid #0d9488;padding:8px 16px;margin:12px 0;background:#f0fdfa}
hr{border:none;border-top:1px solid #e2e8f0;margin:20px 0}@media print{body{padding:0}}</style></head>
<body>${safeHtml}</body></html>`)
  printWin.document.close()
  printWin.print()
}

async function copyReport() {
  if (!activeReport.value) return
  try {
    await navigator.clipboard.writeText(activeReport.value.content)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch { /* clipboard API not available */ }
}

onMounted(loadReports)
</script>

<style scoped>
.report-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Generate Card ── */
.generate-card {
  background: linear-gradient(135deg, var(--teal-600), var(--teal-800));
  border-radius: 16px;
  padding: 28px 32px;
  color: #fff;
}

.generate-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.generate-title {
  font-family: 'Outfit', sans-serif;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}

.generate-desc {
  font-size: 13px;
  color: rgba(255,255,255,0.65);
}

.generate-action { flex-shrink: 0; }

.generate-input-wrap {
  display: flex;
  gap: 8px;
}

.generate-input {
  height: 42px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1.5px solid rgba(255,255,255,0.2);
  background: rgba(255,255,255,0.12);
  font-size: 13px;
  font-family: inherit;
  color: #fff;
  outline: none;
  width: 240px;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.generate-input::placeholder { color: rgba(255,255,255,0.45); }
.generate-input:focus {
  border-color: rgba(255,255,255,0.5);
  background: rgba(255,255,255,0.18);
}

.generate-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px;
  height: 42px;
  border-radius: 10px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  color: var(--teal-800);
  background: #141414;
  cursor: pointer;
  transition: transform 0.25s, box-shadow 0.25s;
  white-space: nowrap;
}

.generate-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}

.generate-btn:disabled { opacity: 0.7; cursor: not-allowed; }

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(0,0,0,0.15);
  border-top-color: var(--teal-700);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Report Detail ── */
.report-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  overflow: hidden;
}

.report-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--slate-100);
  background: var(--slate-50);
  gap: 8px;
  flex-wrap: wrap;
}

.download-btn-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--slate-200);
  background: #141414;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  color: var(--slate-500);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.back-btn:hover {
  border-color: var(--teal-300);
  color: var(--teal-600);
}

.report-stage {
  display: inline-flex;
  padding: 4px 12px;
  border-radius: 8px;
  background: var(--teal-50);
  color: var(--teal-700);
  font-size: 12px;
  font-weight: 600;
}

.report-heading {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
}

.report-date {
  font-size: 12px;
  color: var(--slate-400);
}

.download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  border: 1.5px solid var(--slate-200);
  background: #141414;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  color: var(--slate-600);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}

.download-btn:hover {
  border-color: var(--teal-400);
  color: var(--teal-700);
}

.report-body {
  padding: 28px 32px;
  max-height: 65vh;
  overflow-y: auto;
}

.markdown-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--slate-700);
}

.markdown-content :deep(h1) { font-family: 'Outfit', sans-serif; font-size: 22px; font-weight: 700; color: var(--slate-900); margin-bottom: 16px; }
.markdown-content :deep(h2) { font-family: 'Outfit', sans-serif; font-size: 17px; font-weight: 600; color: var(--slate-800); margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 2px solid var(--teal-100); }
.markdown-content :deep(h3) { font-family: 'Outfit', sans-serif; font-size: 15px; font-weight: 600; color: var(--slate-800); margin: 20px 0 8px; }
.markdown-content :deep(h4) { font-family: 'Outfit', sans-serif; font-size: 14px; font-weight: 600; color: var(--slate-800); margin: 16px 0 8px; }
.markdown-content :deep(strong) { color: var(--slate-900); }
.markdown-content :deep(li) { list-style: disc; margin-left: 20px; margin-bottom: 4px; }
.markdown-content :deep(table) { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }
.markdown-content :deep(td), .markdown-content :deep(th) { padding: 10px 14px; border: 1px solid var(--slate-200); text-align: left; }
.markdown-content :deep(tr:first-child td) { background: var(--slate-50); font-weight: 600; color: var(--slate-600); font-size: 12px; }
.markdown-content :deep(blockquote) { border-left: 3px solid var(--teal-300); padding: 8px 16px; margin: 12px 0; background: var(--slate-50); border-radius: 0 8px 8px 0; }
.markdown-content :deep(hr) { border: none; border-top: 1px solid var(--slate-200); margin: 24px 0; }
.markdown-content :deep(code) { background: var(--slate-100); padding: 2px 6px; border-radius: 4px; font-size: 13px; color: var(--teal-700); }
.markdown-content :deep(p) { margin-bottom: 12px; }
.markdown-content :deep(ul), .markdown-content :deep(ol) { padding-left: 24px; margin-bottom: 12px; }
.markdown-content :deep(a) { color: var(--teal-600); text-decoration: none; }
.markdown-content :deep(a:hover) { text-decoration: underline; }

/* ── Report List ── */
.list-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.list-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
  display: flex;
  align-items: center;
  gap: 10px;
}

.list-count {
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  font-weight: 500;
  color: var(--slate-400);
  background: var(--slate-50);
  padding: 3px 10px;
  border-radius: 6px;
}

.report-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.report-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--slate-50);
  border: 1px solid transparent;
  transition: border-color 0.2s ease, background 0.2s ease;
  cursor: pointer;
}

.report-item:hover {
  background: #1a1a1a;
  border-color: var(--slate-200);
  border-color: var(--card-border-hover);
}

.report-item-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  flex: 1;
}

.report-item-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--teal-50);
  color: var(--teal-600);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.report-item-info {
  min-width: 0;
}

.report-item-title {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-800);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.report-item-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--slate-400);
  margin-top: 3px;
}

.report-item-keyword {
  color: var(--teal-600);
  font-weight: 500;
}

.report-item-sep { color: var(--slate-300); }

.report-item-stage {
  padding: 1px 8px;
  border-radius: 4px;
  background: var(--slate-100);
  font-size: 11px;
  font-weight: 500;
}

.report-item-arrow {
  color: var(--slate-300);
  flex-shrink: 0;
  transition: color 0.2s;
}

.report-item:hover .report-item-arrow {
  color: var(--teal-500);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 72px 0;
  color: var(--slate-400);
  font-size: 14px;
}
</style>
