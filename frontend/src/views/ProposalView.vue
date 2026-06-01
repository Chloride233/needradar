<template>
  <div class="proposal-view">
    <div v-if="loading" class="loading-state"><div class="spinner"></div><span>加载方案...</span></div>
    <div v-if="error" class="error-banner"><span>{{ error }}</span><button class="retry-btn" @click="fetchOrGenerate">重试</button></div>

    <div v-if="!loading && !error && !proposal" class="empty-state">
      方案未找到。该机会尚未生成方案。<br/>
      <router-link to="/opportunities">← 返回项目机会</router-link>
    </div>
    <template v-if="!loading && !error && proposal">
      <div class="header">
        <div>
          <h1 class="title">{{ proposal.title }}</h1>
          <span class="tag">{{ proposal.keyword }}</span>
          <span class="tag status">{{ proposal.status }}</span>
        </div>
        <div class="actions">
          <button class="btn btn-primary" @click="copyPrompt" :disabled="copied">{{ copied ? '已复制!' : '复制 Claude 提示词' }}</button>
          <button class="btn btn-secondary" @click="fetchOrGenerate">刷新</button>
        </div>
      </div>

      <section v-for="sec in sections" :key="sec.key" class="section">
        <h2>{{ sec.label }}</h2>
        <template v-if="sec.key === 'problem'"><p class="text">{{ proposal.problem_statement }}</p></template>
        <template v-if="sec.key === 'users'"><p>{{ proposal.target_user }}</p></template>
        <template v-if="sec.key === 'mvp'">
          <div v-for="(m,i) in proposal.mvp_scope" :key="i" class="mvp-row" :class="'pri-'+m.priority?.toLowerCase()">
            <span class="pri">{{ m.priority }}</span><div><b>{{ m.name }}</b><p>{{ m.description }}</p></div>
          </div>
        </template>
        <template v-if="sec.key === 'stack'">
          <div class="stack-row">
            <div v-for="(v,k) in proposal.suggested_stack" :key="k" class="stack-item" v-if="k!=='rationale'">
              <span class="sl">{{ k }}</span><span class="sv">{{ v }}</span>
            </div>
          </div>
          <p class="rationale">{{ proposal.suggested_stack.rationale }}</p>
        </template>
        <template v-if="sec.key === 'effort'">
          <div class="effort-total">{{ proposal.effort_estimate_hours }}h</div>
          <div v-for="(h,a) in proposal.effort_breakdown" :key="a" class="effort-bar">
            <span class="ea">{{ a }}</span><div class="et"><div class="ef" :style="{width:(h/proposal.effort_estimate_hours*100)+'%'}"></div></div><span class="eh">{{ h }}h</span>
          </div>
        </template>
        <template v-if="sec.key === 'risks' && proposal.risks?.length">
          <ul><li v-for="(r,i) in proposal.risks" :key="i">{{ r }}</li></ul>
        </template>
        <template v-if="sec.key === 'prompt'">
          <pre class="prompt">{{ proposal.claude_prompt }}</pre>
          <button class="btn btn-primary" style="width:100%;margin-top:10px" @click="copyPrompt" :disabled="copied">{{ copied ? '已复制!' : '复制到剪贴板' }}</button>
        </template>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'

const route = useRoute()
const proposal = ref<any>(null)
const loading = ref(true)
const error = ref('')
const copied = ref(false)

const sections = [
  { key: 'problem', label: '问题陈述' },
  { key: 'users', label: '目标用户' },
  { key: 'mvp', label: 'MVP 功能' },
  { key: 'stack', label: '技术栈' },
  { key: 'effort', label: '工作量' },
  { key: 'risks', label: '风险' },
  { key: 'prompt', label: 'Claude 启动提示词' },
]

async function fetchOrGenerate() {
  loading.value = true; error.value = ''
  const oid = Number(route.params.id)
  try {
    const { data: list } = await api.get('/proposals', { params: { page_size: 200 } })
    const existing = list.items?.find((p: any) => p.opportunity_id === oid)
    if (existing) {
      const { data } = await api.get(`/proposals/${existing.id}`)
      proposal.value = data
    } else {
      const { data: gen } = await api.post('/proposals/generate', { opportunity_id: oid })
      const { data } = await api.get(`/proposals/${gen.id}`)
      proposal.value = data
    }
  } catch (e: any) {
    error.value = '加载失败：' + (e.response?.data?.detail || e.message)
  } finally { loading.value = false }
}

async function copyPrompt() {
  if (!proposal.value?.claude_prompt) return
  try {
    await navigator.clipboard.writeText(proposal.value.claude_prompt)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = proposal.value.claude_prompt; document.body.appendChild(ta)
    ta.select(); document.execCommand('copy'); document.body.removeChild(ta)
  }
  copied.value = true; setTimeout(() => copied.value = false, 2500)
}

onMounted(fetchOrGenerate)
</script>

<style scoped>
.proposal-view { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
.loading-state, .error-banner, .empty-state { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px; background: var(--slate-50); border-radius: 12px; color: var(--slate-500); justify-content: center; text-align: center; }
.empty-state a { color: var(--accent); text-decoration: none; margin-top: 8px; }
.empty-state a:hover { text-decoration: underline; }
.error-banner { background: var(--error-bg); color: var(--error-text); border: 1px solid var(--error-border); }
.retry-btn { padding: 4px 12px; border-radius: 6px; border: 1px solid var(--error-border); background: transparent; color: var(--error-text); cursor: pointer; }
.spinner { width: 20px; height: 20px; border: 2px solid var(--slate-300); border-top-color: var(--teal-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.title { font-family: 'Outfit', sans-serif; font-size: 22px; font-weight: 700; color: var(--slate-900); margin-bottom: 6px; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 6px; color: var(--teal-300); background: var(--teal-50); margin-right: 6px; }
.tag.status { color: var(--amber-400); background: var(--warning-bg); }
.actions { display: flex; gap: 8px; flex-shrink: 0; }
.btn { padding: 8px 16px; border-radius: 8px; border: none; font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn:disabled { opacity: 0.6; cursor: default; }
.btn-primary { background: var(--teal-500); color: #000; }
.btn-primary:hover:not(:disabled) { background: var(--teal-300); }
.btn-secondary { background: var(--slate-200); color: var(--slate-700); }
.btn-secondary:hover { background: var(--slate-300); }
.section { background: var(--slate-50); border: 1px solid var(--card-border); border-radius: 12px; padding: 18px 22px; }
.section h2 { font-family: 'Outfit', sans-serif; font-size: 15px; font-weight: 600; color: var(--slate-800); margin-bottom: 10px; }
.text { line-height: 1.7; color: var(--slate-600); }
.mvp-row { display: flex; gap: 10px; padding: 8px 10px; border-radius: 8px; background: var(--slate-100); margin-bottom: 6px; }
.mvp-row b { font-size: 13px; color: var(--slate-800); }
.mvp-row p { font-size: 11px; color: var(--slate-500); }
.pri { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 5px; flex-shrink: 0; height: fit-content; }
.pri-p0 .pri { color: #ef4444; background: rgba(239,68,68,0.1); }
.pri-p1 .pri { color: var(--amber-400); background: var(--warning-bg); }
.pri-p2 .pri { color: var(--slate-500); background: var(--slate-200); }
.stack-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 10px; }
.stack-item { padding: 12px; border-radius: 8px; background: var(--slate-100); text-align: center; }
.sl { display: block; font-size: 10px; color: var(--slate-500); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 3px; }
.sv { font-size: 13px; font-weight: 600; color: var(--teal-300); }
.rationale { font-size: 11px; color: var(--slate-500); font-style: italic; }
.effort-total { font-size: 28px; font-weight: 700; color: var(--teal-300); margin-bottom: 8px; }
.effort-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.ea { font-size: 11px; color: var(--slate-500); width: 45px; }
.et { flex: 1; height: 6px; background: var(--slate-200); border-radius: 3px; overflow: hidden; }
.ef { height: 100%; background: var(--teal-500); border-radius: 3px; }
.eh { font-size: 11px; color: var(--slate-400); width: 28px; text-align: right; }
ul { padding-left: 18px; color: var(--amber-400); font-size: 13px; }
.prompt { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--slate-500); background: #0a0a0a; border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; max-height: 260px; overflow-y: auto; white-space: pre-wrap; line-height: 1.5; }
@media (max-width: 768px) { .stack-row { grid-template-columns: repeat(2,1fr); } .header { flex-direction: column; } }
</style>
