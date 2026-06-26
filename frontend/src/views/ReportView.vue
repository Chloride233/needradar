<template>
  <div class="report-page" ref="pageRef">
    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-orb hero-orb-1"></div>
        <div class="hero-orb hero-orb-2"></div>
        <div class="hero-orb hero-orb-3"></div>
      </div>
      <div class="hero-content">
        <h1 class="hero-title" data-reveal="up">洞察报告</h1>
        <p class="hero-sub" data-reveal="up" data-delay="100">基于已采集的需求数据，自动生成结构化分析报告</p>
      </div>
    </section>

    <!-- Generate Card -->
    <div class="generate-card" data-reveal="up" data-delay="200">
      <div class="generate-content">
        <div class="generate-text">
          <h3 class="generate-title">生成新报告</h3>
          <p class="generate-desc">输入关键词，AI 将自动分析需求数据并生成洞察报告</p>
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
    <div v-if="activeReport" class="report-card" data-reveal="up">
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
        <div class="toolbar-actions">
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
      </div>
      <div class="report-body">
        <div class="markdown-content" v-html="renderedMarkdown"></div>
      </div>
    </div>

    <!-- Report List -->
    <div v-else class="list-card" data-reveal="up" data-delay="300">
      <div class="list-header">
        <h3 class="list-title">
          历史报告
          <span class="list-count">{{ reports.length }} 份</span>
        </h3>
      </div>

      <div v-if="reports.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
        <p>暂无报告，输入关键词生成你的第一份洞察报告</p>
      </div>

      <div v-else class="report-list">
        <div v-for="(report, index) in reports" :key="report.title" class="report-item" :data-reveal="'up'" :data-delay="String(100 + index * 60)" @click="openReport(report)">
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
                <span class="report-item-sep">&middot;</span>
                <span class="report-item-stage">{{ report.stage }}</span>
                <span class="report-item-sep">&middot;</span>
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
import { useReveal } from '../composables/useReveal'
import api from '../api/client'

marked.setOptions({ breaks: true, gfm: true })

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

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
  // List API returns empty content -- fetch full content by filename
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
<style>body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#1D1D1F;line-height:1.8}
h1{font-size:24px;border-bottom:2px solid #007AFF;padding-bottom:8px}h2{font-size:18px;margin-top:32px;border-bottom:1px solid #E8E8ED;padding-bottom:6px}
h3{font-size:16px;margin-top:24px}table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px}
td,th{padding:8px 12px;border:1px solid #E8E8ED;text-align:left}tr:first-child{background:#F5F5F7;font-weight:600}
blockquote{border-left:3px solid #007AFF;padding:8px 16px;margin:12px 0;background:rgba(0,122,255,0.05)}code{background:#F5F5F7;padding:2px 6px;border-radius:4px;font-size:13px}
hr{border:none;border-top:1px solid #E8E8ED;margin:24px 0}</style></head>
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
<style>body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#1D1D1F;line-height:1.8}
h1{font-size:22px;border-bottom:2px solid #007AFF;padding-bottom:8px}h2{font-size:17px;margin-top:28px;border-bottom:1px solid #E8E8ED;padding-bottom:6px}
h3{font-size:15px;margin-top:20px}table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}
td,th{padding:8px 12px;border:1px solid #E8E8ED;text-align:left}tr:first-child{background:#F5F5F7;font-weight:600}
blockquote{border-left:3px solid #007AFF;padding:8px 16px;margin:12px 0;background:rgba(0,122,255,0.05)}
hr{border:none;border-top:1px solid #E8E8ED;margin:20px 0}@media print{body{padding:0}}</style></head>
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
/* ── Page Layout ── */
.report-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
  padding-bottom: var(--space-8);
}

/* ── Hero Section ── */
.hero {
  position: relative;
  padding: var(--space-9) 0 var(--space-7);
  overflow: hidden;
}

.hero-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
}

.hero-orb-1 {
  width: 400px;
  height: 400px;
  background: var(--color-primary);
  top: -120px;
  left: -100px;
  animation: float 8s ease-in-out infinite;
}

.hero-orb-2 {
  width: 300px;
  height: 300px;
  background: var(--color-secondary);
  top: -60px;
  right: -80px;
  animation: float 10s ease-in-out infinite 2s;
}

.hero-orb-3 {
  width: 250px;
  height: 250px;
  background: #f093fb;
  bottom: -80px;
  left: 40%;
  animation: float 12s ease-in-out infinite 4s;
}

.hero-content {
  position: relative;
  z-index: 1;
  text-align: center;
}

.hero-title {
  font-family: var(--font-sans);
  font-size: clamp(32px, 5vw, 48px);
  font-weight: 700;
  letter-spacing: -0.025em;
  color: var(--color-text);
  margin-bottom: var(--space-3);
}

.hero-sub {
  font-size: clamp(15px, 2vw, 18px);
  color: var(--color-text-secondary);
  max-width: 480px;
  margin: 0 auto;
  line-height: 1.6;
}

/* ── Generate Card (Glass) ── */
.generate-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-6);
  transition: box-shadow var(--duration-normal) var(--ease-apple);
}

.generate-card:hover {
  box-shadow: var(--shadow-glass-hover);
}

.generate-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-5);
}

.generate-title {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-1);
}

.generate-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.generate-action {
  flex-shrink: 0;
}

.generate-input-wrap {
  display: flex;
  gap: var(--space-2);
}

.generate-input {
  height: 44px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-size: 14px;
  font-family: var(--font-sans);
  color: var(--color-text);
  outline: none;
  width: 260px;
  transition: border-color var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple);
}

.generate-input::placeholder {
  color: var(--color-text-tertiary);
}

.generate-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15);
}

.generate-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-5);
  height: 44px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-sans);
  color: #fff;
  background: var(--gradient-accent);
  background-size: 200% 200%;
  cursor: pointer;
  transition: transform var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple),
              background-position var(--duration-slow) var(--ease-apple);
  white-space: nowrap;
}

.generate-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-lg);
  background-position: 100% 0;
}

.generate-btn:active:not(:disabled) {
  transform: translateY(0);
}

.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Report Detail (Glass) ── */
.report-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  overflow: hidden;
}

.report-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--glass-border);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(var(--glass-blur-heavy));
  -webkit-backdrop-filter: blur(var(--glass-blur-heavy));
  gap: var(--space-3);
  flex-wrap: wrap;
}

.toolbar-actions {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-sans);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-apple),
              color var(--duration-normal) var(--ease-apple),
              background var(--duration-normal) var(--ease-apple);
}

.back-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.report-stage {
  display: inline-flex;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.report-heading {
  font-family: var(--font-sans);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
}

.report-date {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font-sans);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-apple),
              color var(--duration-normal) var(--ease-apple),
              background var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.download-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-bg);
  transform: translateY(-1px);
}

.report-body {
  padding: var(--space-6);
  max-height: 65vh;
  overflow-y: auto;
}

/* ── Markdown Content ── */
.markdown-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--color-text);
}

.markdown-content :deep(h1) {
  font-family: var(--font-sans);
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: var(--space-4);
  letter-spacing: -0.02em;
}

.markdown-content :deep(h2) {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: var(--space-6) 0 var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-border-light);
}

.markdown-content :deep(h3) {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: var(--space-5) 0 var(--space-2);
}

.markdown-content :deep(h4) {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: var(--space-4) 0 var(--space-2);
}

.markdown-content :deep(strong) {
  color: var(--color-text);
}

.markdown-content :deep(li) {
  list-style: disc;
  margin-left: 20px;
  margin-bottom: var(--space-1);
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: var(--space-4) 0;
  font-size: 13px;
}

.markdown-content :deep(td),
.markdown-content :deep(th) {
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border-light);
  text-align: left;
}

.markdown-content :deep(th) {
  background: var(--color-bg-secondary);
  font-weight: 600;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.markdown-content :deep(tr:hover td) {
  background: var(--color-bg-secondary);
}

.markdown-content :deep(blockquote) {
  border-left: 3px solid var(--color-primary);
  padding: var(--space-2) var(--space-4);
  margin: var(--space-3) 0;
  background: var(--color-primary-bg);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border-light);
  margin: var(--space-6) 0;
}

.markdown-content :deep(code) {
  background: var(--color-bg-secondary);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: var(--font-mono);
  color: var(--color-text);
}

.markdown-content :deep(p) {
  margin-bottom: var(--space-3);
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 24px;
  margin-bottom: var(--space-3);
}

.markdown-content :deep(a) {
  color: var(--color-primary);
  text-decoration: none;
  transition: color var(--duration-fast) var(--ease-apple);
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

/* ── Report List (Glass) ── */
.list-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-6);
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}

.list-title {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.list-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  padding: 3px 10px;
  border-radius: var(--radius-full);
}

.report-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.report-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
  transition: border-color var(--duration-normal) var(--ease-apple),
              background var(--duration-normal) var(--ease-apple),
              box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
  cursor: pointer;
}

.report-item:hover {
  background: var(--glass-bg-heavy);
  border-color: var(--color-primary);
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.report-item-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  flex: 1;
}

.report-item-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--gradient-accent);
  color: #fff;
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
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.report-item-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.report-item-keyword {
  color: var(--color-primary);
  font-weight: 500;
}

.report-item-sep {
  color: var(--color-border-light);
}

.report-item-stage {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.report-item-arrow {
  color: var(--color-border);
  flex-shrink: 0;
  transition: color var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.report-item:hover .report-item-arrow {
  color: var(--color-primary);
  transform: translateX(4px);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  padding: 80px 0;
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.empty-state svg {
  color: var(--color-border-light);
  opacity: 0.6;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .report-page {
    padding: 0 var(--space-4);
  }

  .hero {
    padding: var(--space-7) 0 var(--space-5);
  }

  .generate-content {
    flex-direction: column;
    align-items: flex-start;
  }

  .generate-input-wrap {
    flex-direction: column;
    width: 100%;
  }

  .generate-input {
    width: 100%;
  }

  .generate-btn {
    width: 100%;
    justify-content: center;
  }

  .report-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .toolbar-actions {
    width: 100%;
  }

  .download-btn {
    flex: 1;
    justify-content: center;
  }
}
</style>
