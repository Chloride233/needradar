<template>
  <div class="req-detail">
    <!-- Loading / Error / Empty -->
    <div v-if="loading" class="loading-state"><div class="spinner"></div><span>加载需求...</span></div>
    <div v-if="error" class="error-banner"><span>{{ error }}</span><button class="retry-btn" @click="fetchAll">重试</button></div>
    <div v-if="!loading && !error && !req" class="empty-state">需求未找到。<router-link to="/requirements">返回需求池</router-link></div>

    <!-- Object View -->
    <template v-if="req">
      <div class="ov-header">
        <router-link to="/requirements" class="back-link">&larr; 返回需求池</router-link>
        <h1 class="ov-title">📋 {{ req.title }}</h1>
        <div class="ov-meta">{{ req.source_platform }} · {{ req.keyword }} · {{ req.created_at }}</div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button :class="{ active: tab === 'overview' }" @click="tab = 'overview'">概览</button>
        <button :class="{ active: tab === 'links' }" @click="tab = 'links'">关联对象</button>
        <button :class="{ active: tab === 'similar' }" @click="tab = 'similar'">相似需求</button>
      </div>

      <!-- Tab: Overview -->
      <div v-if="tab === 'overview'" class="tab-content">
        <div class="prominent-cards">
          <div class="prom-card" :class="req.sentiment">
            <span class="prom-label">情感强度</span>
            <span class="prom-value">{{ sentimentLabel(req.sentiment) }}</span>
          </div>
          <div class="prom-card confidence">
            <span class="prom-label">置信度</span>
            <span class="prom-value">{{ (req.confidence * 100).toFixed(0) }}%</span>
          </div>
          <div class="prom-card mentions">
            <span class="prom-label">提及次数</span>
            <span class="prom-value">{{ req.mention_count }}</span>
          </div>
          <div class="prom-card source">
            <span class="prom-label">来源平台</span>
            <span class="prom-value">{{ req.source_platform }}</span>
          </div>
        </div>

        <section class="ov-section">
          <h2>描述</h2>
          <p class="desc-text">{{ req.description }}</p>
        </section>

        <section class="ov-section">
          <h2>情感分析</h2>
          <div class="emotion-row">
            <span class="emotion-tag" :class="req.emotion">{{ emotionLabel(req.emotion) }}</span>
            <div class="sentiment-bar"><div class="sent-fill" :style="{ width: (req.confidence * 100) + '%' }"></div></div>
          </div>
        </section>

        <section v-if="req.source_url" class="ov-section">
          <h2>来源链接</h2>
          <a :href="req.source_url" target="_blank" rel="noopener" class="source-link">{{ req.source_url }}</a>
        </section>

        <section class="ov-section">
          <h2>动作</h2>
          <div class="action-row">
            <button class="action-btn" disabled title="即将上线">标记为已验证</button>
            <button class="action-btn" @click="copyTitle">复制标题</button>
          </div>
        </section>
      </div>

      <!-- Tab: Linked Objects -->
      <div v-if="tab === 'links'" class="tab-content">
        <div v-if="linksLoading" class="loading-state"><div class="spinner"></div><span>加载关联...</span></div>
        <div v-else-if="links.length === 0" class="empty-state">暂无关联对象</div>
        <div v-else class="links-list">
          <div v-for="group in groupedLinks" :key="group.label" class="link-group">
            <h3>{{ group.label }} ({{ group.items.length }})</h3>
            <div v-for="item in group.items" :key="item.id" class="link-item">
              <span class="link-direction">{{ item.direction === 'outgoing' ? '→' : '←' }}</span>
              <span class="link-type-tag">{{ item.link_type }}</span>
              <span class="link-target-type">{{ item.other_type }}</span>
              <span class="link-target-id">{{ item.other_id }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab: Similar (stub) -->
      <div v-if="tab === 'similar'" class="tab-content">
        <div class="empty-state">
          <p>相似需求检索即将上线</p>
          <p class="hint">基于 ChromaDB 向量相似度，发现语义相近的需求</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'

const route = useRoute()
const pathParam = computed(() => route.query.path as string)

const req = ref<any>(null)
const loading = ref(true)
const error = ref('')
const tab = ref('overview')
const links = ref<any[]>([])
const linksLoading = ref(false)

function sentimentLabel(s: string): string {
  return { strong: '强烈', moderate: '中等', mild: '轻微' }[s] || s
}

function emotionLabel(e: string): string {
  return { positive: '😊 正向', negative: '😞 负向', neutral: '😐 中性' }[e] || e
}

const groupedLinks = computed(() => {
  const groups: Record<string, { label: string; items: any[] }> = {}
  const labels: Record<string, string> = {
    derived_from: '来源于', contains: '包含', generates: '生成',
    references: '引用', verified_by: '被验证', executed_in: '执行于',
  }
  for (const l of links.value) {
    const key = l.link_type
    if (!groups[key]) groups[key] = { label: labels[key] || key, items: [] }
    groups[key].items.push(l)
  }
  return Object.values(groups)
})

function copyTitle() {
  if (req.value?.title) navigator.clipboard.writeText(req.value.title)
}

async function fetchAll() {
  loading.value = true; error.value = ''
  try {
    const path = pathParam.value
    if (!path) { error.value = '缺少需求路径参数'; loading.value = false; return }
    const { data } = await api.get('/requirements/by-filename/' + encodeURIComponent(path))
    req.value = data
    linksLoading.value = true
    try {
      const lr = await api.get('/links', { params: { entity_type: 'requirement', entity_id: path } })
      links.value = lr.data.items.map((l: any) => {
        const isOut = l.source_type === 'requirement' && l.source_id === path
        return { ...l, direction: isOut ? 'outgoing' : 'incoming', other_type: isOut ? l.target_type : l.source_type, other_id: isOut ? l.target_id : l.source_id }
      })
    } catch { links.value = [] }
    linksLoading.value = false
  } catch (e: any) {
    error.value = '加载失败：' + (e.response?.data?.detail || e.message)
  } finally { loading.value = false }
}

onMounted(fetchAll)
</script>

<style scoped>
.req-detail { display: flex; flex-direction: column; gap: 20px; }
.loading-state, .error-banner, .empty-state { display: flex; align-items: center; gap: 12px; padding: 40px; border-radius: 12px; justify-content: center; color: var(--slate-500); }
.error-banner { background: var(--error-bg); color: var(--error-text); border: 1px solid var(--error-border); }
.retry-btn { padding: 4px 12px; border-radius: 6px; border: 1px solid var(--error-border); background: transparent; color: var(--error-text); cursor: pointer; }
.spinner { width: 20px; height: 20px; border: 2px solid var(--slate-300); border-top-color: var(--teal-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { flex-direction: column; }
.empty-state a { color: var(--teal-500); }

.ov-header { display: flex; flex-direction: column; gap: 4px; }
.back-link { font-size: 13px; color: var(--teal-500); text-decoration: none; }
.ov-title { font-size: 22px; font-weight: 700; color: var(--slate-800); margin: 0; }
.ov-meta { font-size: 12px; color: var(--slate-500); }

.tabs { display: flex; border-bottom: 1px solid var(--card-border); }
.tabs button { padding: 10px 20px; border: none; background: transparent; color: var(--slate-500); font-size: 13px; cursor: pointer; border-bottom: 2px solid transparent; }
.tabs button.active { color: var(--teal-600); border-bottom-color: var(--teal-500); font-weight: 600; }
.tab-content { display: flex; flex-direction: column; gap: 20px; }

.prominent-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.prom-card { background: var(--slate-50); border: 1px solid var(--card-border); border-radius: 10px; padding: 16px; display: flex; flex-direction: column; gap: 6px; }
.prom-card.strong { border-left: 3px solid var(--amber-400); }
.prom-card.moderate { border-left: 3px solid var(--teal-400); }
.prom-card.mild { border-left: 3px solid var(--slate-400); }
.prom-card.confidence { border-left: 3px solid var(--emerald-400); }
.prom-card.mentions { border-left: 3px solid var(--teal-400); }
.prom-card.source { border-left: 3px solid var(--slate-400); }
.prom-label { font-size: 11px; color: var(--slate-500); text-transform: uppercase; }
.prom-value { font-size: 18px; font-weight: 700; color: var(--slate-800); }

.ov-section { background: var(--slate-50); border: 1px solid var(--card-border); border-radius: 10px; padding: 18px; }
.ov-section h2 { font-size: 14px; font-weight: 600; color: var(--slate-800); margin: 0 0 10px; }
.desc-text { font-size: 13px; color: var(--slate-600); line-height: 1.7; white-space: pre-wrap; margin: 0; }

.emotion-row { display: flex; align-items: center; gap: 12px; }
.emotion-tag { font-size: 13px; padding: 4px 10px; border-radius: 6px; }
.emotion-tag.positive { background: var(--emerald-50); color: var(--emerald-700); }
.emotion-tag.negative { background: var(--amber-50); color: var(--amber-700); }
.emotion-tag.neutral { background: var(--slate-100); color: var(--slate-600); }
.sentiment-bar { flex: 1; height: 8px; background: var(--slate-200); border-radius: 4px; overflow: hidden; }
.sent-fill { height: 100%; background: var(--teal-500); border-radius: 4px; }

.source-link { font-size: 12px; color: var(--teal-500); word-break: break-all; }

.action-row { display: flex; gap: 8px; flex-wrap: wrap; }
.action-btn { padding: 8px 16px; border-radius: 8px; border: 1px solid var(--card-border); background: var(--slate-100); color: var(--slate-700); font-size: 13px; cursor: pointer; }
.action-btn:hover:not(:disabled) { background: var(--teal-50); border-color: var(--teal-300); color: var(--teal-700); }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.links-list { display: flex; flex-direction: column; gap: 12px; }
.link-group { background: var(--slate-50); border: 1px solid var(--card-border); border-radius: 10px; padding: 14px; }
.link-group h3 { font-size: 13px; font-weight: 600; color: var(--slate-700); margin: 0 0 8px; }
.link-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--slate-100); font-size: 12px; }
.link-item:last-child { border-bottom: none; }
.link-direction { color: var(--slate-400); font-weight: 700; }
.link-type-tag { background: var(--teal-50); color: var(--teal-700); padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.link-target-type { color: var(--slate-500); }
.link-target-id { color: var(--slate-700); font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hint { font-size: 12px; color: var(--slate-400); margin: 0; }
</style>
