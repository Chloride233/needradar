<template>
  <div class="opp-detail">
    <div v-if="loading" class="loading-state"><div class="spinner"></div><span>加载机会...</span></div>
    <div v-if="error" class="error-banner"><span>{{ error }}</span><button class="retry-btn" @click="fetchAll">重试</button></div>
    <div v-if="!loading && !error && !opp" class="empty-state">机会未找到。<router-link to="/opportunities">返回列表</router-link></div>

    <template v-if="opp">
      <div class="ov-header">
        <router-link to="/opportunities" class="back-link">&larr; 返回机会列表</router-link>
        <h1 class="ov-title">💼 {{ opp.title }}</h1>
        <div class="ov-meta">{{ opp.keyword }} · {{ opp.status }} · {{ opp.created_at }}</div>
      </div>

      <div class="tabs">
        <button :class="{ active: tab === 'overview' }" @click="tab = 'overview'">概览</button>
        <button :class="{ active: tab === 'links' }" @click="tab = 'links'">关联对象</button>
      </div>

      <div v-if="tab === 'overview'" class="tab-content">
        <div class="score-section">
          <div class="score-ring-wrapper">
            <div class="score-ring" :style="{ '--pct': opp.scores.overall }">
              <span class="score-num">{{ opp.scores.overall }}</span>
            </div>
            <span class="score-label">综合评分</span>
          </div>
          <div class="score-bars">
            <div class="bar" v-for="dim in dims" :key="dim.key">
              <span class="bar-label">{{ dim.label }}</span>
              <div class="bar-track"><div class="bar-fill" :class="dim.cls" :style="{ width: opp.scores[dim.key] + '%' }"></div></div>
              <span class="bar-val">{{ opp.scores[dim.key] }}</span>
            </div>
          </div>
        </div>

        <section v-if="opp.description" class="ov-section">
          <h2>描述</h2>
          <p class="desc-text">{{ opp.description }}</p>
        </section>

        <section v-if="opp.traction?.length" class="ov-section">
          <h2>牵引力信号</h2>
          <div class="traction-grid">
            <div v-for="t in opp.traction" :key="t.source" class="traction-card">
              <span class="traction-source">{{ t.source }}</span>
              <span class="traction-count">{{ t.mention_count }} 次</span>
              <span class="traction-trend">{{ t.growth_trend }}</span>
              <p v-if="t.representative_quote" class="traction-quote">"{{ t.representative_quote }}"</p>
            </div>
          </div>
        </section>

        <section class="ov-section">
          <h2>动作</h2>
          <div class="action-row">
            <button class="action-btn primary" @click="goGenerate">生成提案</button>
            <button class="action-btn" disabled title="即将上线">刷新评分</button>
          </div>
        </section>
      </div>

      <div v-if="tab === 'links'" class="tab-content">
        <div v-if="linksLoading" class="loading-state"><div class="spinner"></div><span>加载关联...</span></div>
        <div v-else-if="linkedReqs.length === 0 && linkedProposals.length === 0" class="empty-state">暂无关联对象</div>
        <div v-else class="links-list">
          <div v-if="linkedReqs.length" class="link-group">
            <h3>📋 包含的需求 ({{ linkedReqs.length }})</h3>
            <div v-for="item in linkedReqs" :key="item.id" class="link-item">
              <span>📄 {{ item.target_id }}</span>
              <button class="link-nav-btn" @click="goRequirement(item.target_id)">查看 →</button>
            </div>
          </div>
          <div v-if="linkedProposals.length" class="link-group">
            <h3>📝 生成的提案 ({{ linkedProposals.length }})</h3>
            <div v-for="item in linkedProposals" :key="item.id" class="link-item">
              <span>提案 #{{ item.source_id }}</span>
              <button class="link-nav-btn" @click="goProposal(parseInt(item.source_id))">查看 →</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'

const route = useRoute()
const router = useRouter()
const oppId = computed(() => parseInt(route.query.id as string) || 0)

const opp = ref<any>(null)
const loading = ref(true)
const error = ref('')
const tab = ref('overview')
const linkedReqs = ref<any[]>([])
const linkedProposals = ref<any[]>([])
const linksLoading = ref(false)

const dims = [
  { key: 'vibe_code_suitability', label: 'Vibe适配', cls: 'bar-teal' },
  { key: 'demand_intensity', label: '需求热度', cls: 'bar-amber' },
  { key: 'technical_feasibility', label: '技术可行', cls: 'bar-emerald' },
  { key: 'market_freshness', label: '市场新鲜', cls: 'bar-slate' },
]

function goGenerate() { router.push(`/proposals/${oppId.value}`) }
function goProposal(id: number) { router.push(`/proposals/${id}`) }
function goRequirement(title: string) {
  router.push(`/requirement-detail?path=${encodeURIComponent('02-需求池/' + title + '.md')}`)
}

async function fetchAll() {
  loading.value = true; error.value = ''
  try {
    const id = oppId.value
    if (!id) { error.value = '缺少机会 ID'; loading.value = false; return }
    const { data } = await api.get(`/opportunities/${id}`)
    opp.value = data
    linksLoading.value = true
    try {
      const lr = await api.get('/links', { params: { entity_type: 'opportunity', entity_id: String(id), direction: 'outgoing' } })
      linkedReqs.value = lr.data.items.filter((l: any) => l.link_type === 'contains' && l.target_type === 'requirement')
    } catch { linkedReqs.value = [] }
    try {
      const lr2 = await api.get('/links', { params: { entity_type: 'opportunity', entity_id: String(id), direction: 'incoming' } })
      linkedProposals.value = lr2.data.items.filter((l: any) => l.link_type === 'generates' && l.source_type === 'proposal')
    } catch { linkedProposals.value = [] }
    linksLoading.value = false
  } catch (e: any) {
    error.value = '加载失败：' + (e.response?.data?.detail || e.message)
  } finally { loading.value = false }
}

onMounted(fetchAll)
</script>

<style scoped>
.opp-detail { display: flex; flex-direction: column; gap: 20px; }
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

.score-section { display: flex; gap: 32px; align-items: center; background: var(--slate-50); border: 1px solid var(--card-border); border-radius: 12px; padding: 24px; }
.score-ring-wrapper { display: flex; flex-direction: column; align-items: center; gap: 8px; flex-shrink: 0; }
.score-ring { width: 80px; height: 80px; border-radius: 50%; background: conic-gradient(var(--teal-500) calc(var(--pct) * 1%), var(--slate-200) 0); display: flex; align-items: center; justify-content: center; position: relative; }
.score-ring::after { content: ''; width: 62px; height: 62px; border-radius: 50%; background: var(--slate-50); position: absolute; }
.score-num { position: relative; z-index: 1; font-size: 22px; font-weight: 700; color: var(--teal-600); }
.score-label { font-size: 12px; color: var(--slate-500); }
.score-bars { flex: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.bar { display: flex; align-items: center; gap: 8px; }
.bar-label { font-size: 12px; color: var(--slate-500); width: 72px; flex-shrink: 0; }
.bar-track { flex: 1; height: 8px; background: var(--slate-200); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; }
.bar-teal { background: var(--teal-500); }
.bar-amber { background: var(--amber-400); }
.bar-emerald { background: var(--emerald-500); }
.bar-slate { background: var(--slate-500); }
.bar-val { font-size: 12px; color: var(--slate-400); width: 28px; text-align: right; font-variant-numeric: tabular-nums; }

.ov-section { background: var(--slate-50); border: 1px solid var(--card-border); border-radius: 10px; padding: 18px; }
.ov-section h2 { font-size: 14px; font-weight: 600; color: var(--slate-800); margin: 0 0 10px; }
.desc-text { font-size: 13px; color: var(--slate-600); line-height: 1.7; margin: 0; }

.traction-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.traction-card { background: var(--slate-100); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 4px; }
.traction-source { font-size: 12px; font-weight: 600; color: var(--slate-700); }
.traction-count { font-size: 11px; color: var(--teal-600); }
.traction-trend { font-size: 10px; color: var(--slate-400); }
.traction-quote { font-size: 11px; color: var(--slate-500); font-style: italic; margin: 4px 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.action-row { display: flex; gap: 8px; flex-wrap: wrap; }
.action-btn { padding: 8px 16px; border-radius: 8px; border: 1px solid var(--card-border); background: var(--slate-100); color: var(--slate-700); font-size: 13px; cursor: pointer; }
.action-btn:hover:not(:disabled) { background: var(--teal-50); border-color: var(--teal-300); color: var(--teal-700); }
.action-btn.primary { background: var(--teal-500); color: white; border-color: var(--teal-500); }
.action-btn.primary:hover { background: var(--teal-600); }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.links-list { display: flex; flex-direction: column; gap: 12px; }
.link-group { background: var(--slate-50); border: 1px solid var(--card-border); border-radius: 10px; padding: 14px; }
.link-group h3 { font-size: 13px; font-weight: 600; color: var(--slate-700); margin: 0 0 8px; }
.link-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--slate-100); font-size: 12px; justify-content: space-between; }
.link-item:last-child { border-bottom: none; }
.link-nav-btn { padding: 2px 10px; border-radius: 6px; border: 1px solid var(--card-border); background: var(--slate-100); color: var(--teal-600); font-size: 11px; cursor: pointer; }
.link-nav-btn:hover { background: var(--teal-50); border-color: var(--teal-300); }
</style>
