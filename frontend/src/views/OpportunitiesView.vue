<template>
  <div class="opportunities">
    <div v-if="loading" class="loading-state"><div class="spinner"></div><span>加载机会数据...</span></div>
    <div v-if="error" class="error-banner"><span>{{ error }}</span><button class="retry-btn" @click="fetchData">重试</button></div>

    <template v-if="!loading && !error">
      <div class="toolbar">
        <span class="section-title">项目机会评分</span>
        <span class="count-badge">{{ total }}</span>
        <div class="toolbar-right">
          <input v-model="minScore" type="number" min="0" max="100" placeholder="最低分" class="score-input" @change="fetchData" />
        </div>
      </div>

      <div v-if="items.length === 0" class="empty-state">暂无评分。请先运行爬取管道，然后执行评分。</div>

      <div class="opp-grid">
        <div v-for="opp in items" :key="opp.id" class="opp-card" :class="scoreClass(opp.scores.overall)"
          role="button" tabindex="0" @click="goProposal(opp.id)"
          @keydown.enter="goProposal(opp.id)" @keydown.space.prevent="goProposal(opp.id)">
          <div class="opp-score">
            <div class="score-circle" :style="{ '--pct': opp.scores.overall }">
              <span class="score-num">{{ opp.scores.overall }}</span>
            </div>
          </div>
          <div class="opp-body">
            <h3 class="opp-title">{{ opp.title }}</h3>
            <p class="opp-desc">{{ opp.description }}</p>
            <span class="opp-kw">{{ opp.keyword }}</span>
            <div class="opp-bars">
              <div class="bar" v-for="dim in dims" :key="dim.key">
                <span class="bar-label">{{ dim.label }}</span>
                <div class="bar-track"><div class="bar-fill" :class="dim.cls" :style="{ width: opp.scores[dim.key] + '%' }"></div></div>
                <span class="bar-val">{{ opp.scores[dim.key] }}</span>
              </div>
            </div>
            <div class="opp-srcs">
              <span v-for="t in opp.traction?.slice(0,3)" :key="t.source" class="src-tag">{{ t.source }} {{ t.mention_count }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'

const router = useRouter()
const items = ref<any[]>([])
const total = ref(0)
const loading = ref(true)
const error = ref('')
const minScore = ref(0)

const dims = [
  { key: 'vibe_code_suitability', label: 'Vibe适配', cls: 'bar-teal' },
  { key: 'demand_intensity', label: '需求热度', cls: 'bar-amber' },
  { key: 'technical_feasibility', label: '技术可行', cls: 'bar-emerald' },
  { key: 'market_freshness', label: '市场新鲜', cls: 'bar-slate' },
]

function scoreClass(s: number): string { return s >= 80 ? 'green' : s >= 60 ? 'amber' : 'gray' }
function goProposal(id: number) { router.push(`/opportunity-detail?id=${id}`) }

async function fetchData() {
  loading.value = true; error.value = ''
  try {
    const params: any = { page_size: 50 }
    if (minScore.value > 0) params.min_score = minScore.value
    const { data } = await api.get('/opportunities', { params })
    items.value = data.items; total.value = data.total
  } catch (e: any) {
    error.value = '加载失败：' + (e.response?.data?.detail || e.message)
  } finally { loading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.opportunities { display: flex; flex-direction: column; gap: 20px; }
.loading-state, .error-banner, .empty-state { display: flex; align-items: center; gap: 12px; padding: 40px; background: var(--slate-50); border-radius: 12px; color: var(--slate-500); justify-content: center; }
.error-banner { background: var(--error-bg); color: var(--error-text); border: 1px solid var(--error-border); }
.retry-btn { padding: 4px 12px; border-radius: 6px; border: 1px solid var(--error-border); background: transparent; color: var(--error-text); cursor: pointer; }
.spinner { width: 20px; height: 20px; border: 2px solid var(--slate-300); border-top-color: var(--teal-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.toolbar { display: flex; align-items: center; gap: 12px; }
.section-title { font-family: 'Outfit', sans-serif; font-size: 18px; font-weight: 700; color: var(--slate-800); }
.count-badge { font-size: 12px; color: var(--slate-500); background: var(--slate-100); padding: 2px 8px; border-radius: 10px; }
.toolbar-right { margin-left: auto; }
.score-input { padding: 6px 12px; border-radius: 8px; border: 1px solid var(--card-border); background: var(--slate-100); color: var(--slate-700); font-size: 13px; width: 80px; }
.opp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 14px; }
.opp-card { display: flex; gap: 14px; background: var(--slate-50); border: 1px solid var(--card-border); border-radius: 12px; padding: 18px; cursor: pointer; transition: border-color .2s, transform .15s; }
.opp-card:hover { border-color: var(--teal-200); transform: translateY(-1px); }
.opp-card.green { border-left: 3px solid var(--emerald-500); }
.opp-card.amber { border-left: 3px solid var(--amber-400); }
.opp-card.gray { border-left: 3px solid var(--slate-400); }
.opp-score { flex-shrink: 0; display: flex; align-items: center; }
.score-circle { width: 52px; height: 52px; border-radius: 50%; background: conic-gradient(var(--teal-500) calc(var(--pct) * 1%), var(--slate-200) 0); display: flex; align-items: center; justify-content: center; position: relative; }
.score-circle::after { content: ''; width: 40px; height: 40px; border-radius: 50%; background: var(--slate-50); position: absolute; }
.score-num { position: relative; z-index: 1; font-size: 16px; font-weight: 700; color: var(--teal-300); }
.opp-body { flex: 1; min-width: 0; }
.opp-title { font-size: 14px; font-weight: 600; color: var(--slate-800); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; }
.opp-desc { font-size: 12px; color: var(--slate-500); margin-bottom: 6px; }
.opp-kw { font-size: 11px; color: var(--teal-400); background: var(--teal-50); padding: 2px 8px; border-radius: 6px; display: inline-block; margin-bottom: 8px; }
.opp-bars { display: flex; flex-direction: column; gap: 3px; margin-bottom: 6px; }
.bar { display: flex; align-items: center; gap: 6px; }
.bar-label { font-size: 10px; color: var(--slate-500); width: 52px; flex-shrink: 0; }
.bar-track { flex: 1; height: 4px; background: var(--slate-200); border-radius: 2px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 2px; }
.bar-teal { background: var(--teal-500); }
.bar-amber { background: var(--amber-400); }
.bar-emerald { background: var(--emerald-500); }
.bar-slate { background: var(--slate-500); }
.bar-val { font-size: 10px; color: var(--slate-400); width: 20px; text-align: right; font-variant-numeric: tabular-nums; }
.opp-srcs { display: flex; gap: 4px; flex-wrap: wrap; }
.src-tag { font-size: 10px; color: var(--slate-500); background: var(--slate-100); padding: 2px 6px; border-radius: 5px; }
</style>
