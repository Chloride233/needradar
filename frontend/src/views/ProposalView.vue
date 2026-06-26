<template>
  <div class="proposal-page" ref="pageRef">
    <!-- Loading -->
    <div v-if="loading" class="loading-state" data-reveal="up">
      <div class="spinner"></div>
      <span>加载方案...</span>
    </div>

    <!-- Error -->
    <div v-if="error" class="error-banner" data-reveal="up">
      <span>{{ error }}</span>
      <button class="retry-btn" @click="fetchOrGenerate">重试</button>
    </div>

    <!-- Empty -->
    <div v-if="!loading && !error && !proposal" class="empty-state" data-reveal="up">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
      </svg>
      <p>方案未找到。该机会尚未生成方案。</p>
      <router-link to="/opportunities">← 返回项目机会</router-link>
    </div>

    <template v-if="!loading && !error && proposal">
      <!-- Hero -->
      <div class="page-hero" data-reveal="up">
        <div class="hero-bg">
          <div class="hero-orb hero-orb-1"></div>
          <div class="hero-orb hero-orb-2"></div>
        </div>
        <div class="hero-inner">
          <h1 class="page-title">{{ proposal.title }}</h1>
          <div class="hero-tags">
            <span class="tag">{{ proposal.keyword }}</span>
            <span class="tag tag-status">{{ proposal.status }}</span>
          </div>
          <div class="hero-actions">
            <button class="btn btn-primary" @click="copyPrompt" :disabled="copied">
              {{ copied ? '已复制!' : '复制 Claude 提示词' }}
            </button>
            <button class="btn btn-secondary" @click="fetchOrGenerate">刷新</button>
          </div>
        </div>
      </div>

      <!-- Sections -->
      <div
        v-for="(sec, i) in sections"
        :key="sec.key"
        class="glass-card"
        data-reveal="up"
        :data-delay="(i * 80 + 100).toString()"
      >
        <h2 class="section-title">{{ sec.label }}</h2>

        <!-- Problem -->
        <template v-if="sec.key === 'problem'">
          <p class="text">{{ proposal.problem_statement }}</p>
        </template>

        <!-- Users -->
        <template v-if="sec.key === 'users'">
          <p class="text">{{ proposal.target_user }}</p>
        </template>

        <!-- MVP -->
        <template v-if="sec.key === 'mvp'">
          <div class="mvp-list">
            <div
              v-for="(m, j) in proposal.mvp_scope"
              :key="j"
              class="mvp-row"
              :class="'pri-' + m.priority?.toLowerCase()"
            >
              <span class="pri">{{ m.priority }}</span>
              <div class="mvp-body">
                <b>{{ m.name }}</b>
                <p>{{ m.description }}</p>
              </div>
            </div>
          </div>
        </template>

        <!-- Stack -->
        <template v-if="sec.key === 'stack'">
          <div class="stack-grid">
            <div
              v-for="(v, k) in proposal.suggested_stack"
              :key="k"
              class="stack-item"
              v-if="k !== 'rationale'"
            >
              <span class="stack-label">{{ k }}</span>
              <span class="stack-value">{{ v }}</span>
            </div>
          </div>
          <p class="rationale">{{ proposal.suggested_stack.rationale }}</p>
        </template>

        <!-- Effort -->
        <template v-if="sec.key === 'effort'">
          <div class="effort-total">{{ proposal.effort_estimate_hours }}h</div>
          <div v-for="(h, a) in proposal.effort_breakdown" :key="a" class="effort-bar">
            <span class="effort-area">{{ a }}</span>
            <div class="effort-track">
              <div class="effort-fill" :style="{ width: (h / proposal.effort_estimate_hours * 100) + '%' }"></div>
            </div>
            <span class="effort-hours">{{ h }}h</span>
          </div>
        </template>

        <!-- Risks -->
        <template v-if="sec.key === 'risks' && proposal.risks?.length">
          <ul class="risk-list">
            <li v-for="(r, j) in proposal.risks" :key="j">{{ r }}</li>
          </ul>
        </template>

        <!-- Prompt -->
        <template v-if="sec.key === 'prompt'">
          <pre class="prompt-block">{{ proposal.claude_prompt }}</pre>
          <button class="btn btn-primary btn-block" @click="copyPrompt" :disabled="copied">
            {{ copied ? '已复制!' : '复制到剪贴板' }}
          </button>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import { useReveal } from '../composables/useReveal'

const route = useRoute()
const proposal = ref<any>(null)
const loading = ref(true)
const error = ref('')
const copied = ref(false)

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

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
  try { await navigator.clipboard.writeText(proposal.value.claude_prompt) } catch {
    const ta = document.createElement('textarea')
    ta.value = proposal.value.claude_prompt; document.body.appendChild(ta)
    ta.select(); document.execCommand('copy'); document.body.removeChild(ta)
  }
  copied.value = true; setTimeout(() => copied.value = false, 2500)
}

onMounted(fetchOrGenerate)
</script>

<style scoped>
.proposal-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ── Hero ── */
.page-hero {
  position: relative;
  padding: var(--space-8) var(--space-6);
  border-radius: var(--radius-2xl);
  overflow: hidden;
  margin-bottom: var(--space-2);
}

.hero-bg {
  position: absolute;
  inset: -50%;
  pointer-events: none;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  animation: float 8s ease-in-out infinite;
}

.hero-orb-1 {
  width: 300px;
  height: 300px;
  background: rgba(0, 122, 255, 0.1);
  top: 0;
  right: 20%;
}

.hero-orb-2 {
  width: 250px;
  height: 250px;
  background: rgba(88, 86, 214, 0.08);
  bottom: 0;
  left: 30%;
  animation-delay: -3s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(10px, -10px); }
}

.hero-inner {
  position: relative;
}

.page-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
  margin-bottom: var(--space-3);
}

.hero-tags {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.tag {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  color: var(--color-primary);
  background: var(--color-primary-bg);
  font-weight: 600;
}

.tag-status {
  color: var(--color-warning);
  background: var(--color-warning-bg);
}

.hero-actions {
  display: flex;
  gap: var(--space-2);
}

/* ── States ── */
.loading-state,
.error-banner,
.empty-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-7);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border-radius: var(--radius-xl);
  color: var(--color-text-secondary);
  justify-content: center;
  border: 1px solid var(--glass-border);
  text-align: center;
  flex-direction: column;
}

.empty-state p {
  margin: 0;
  font-size: 15px;
}

.empty-state a {
  color: var(--color-primary);
  text-decoration: none;
  margin-top: var(--space-2);
  font-size: 14px;
  transition: opacity var(--duration-fast) var(--ease-apple);
}

.empty-state a:hover {
  opacity: 0.8;
}

.error-banner {
  background: var(--color-danger-bg);
  color: var(--color-danger);
  border-color: rgba(255, 59, 48, 0.2);
}

.retry-btn {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Glass Card ── */
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.glass-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 var(--space-4);
  letter-spacing: -0.01em;
}

.text {
  font-size: 15px;
  line-height: 1.7;
  color: var(--color-text-secondary);
  margin: 0;
}

/* ── Buttons ── */
.btn {
  padding: 10px 20px;
  border-radius: var(--radius-sm);
  border: none;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-apple);
}

.btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.btn-primary {
  background: var(--color-primary);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-secondary {
  background: var(--glass-bg);
  color: var(--color-text-secondary);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
}

.btn-secondary:hover {
  background: var(--color-bg-secondary);
  color: var(--color-text);
}

.btn-block {
  width: 100%;
  margin-top: var(--space-4);
}

/* ── MVP ── */
.mvp-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.mvp-row {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  transition: background var(--duration-fast) var(--ease-apple);
}

.mvp-row:hover {
  background: var(--color-bg-secondary);
}

.mvp-row b {
  font-size: 14px;
  color: var(--color-text);
  font-weight: 600;
}

.mvp-row p {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 4px 0 0;
  line-height: 1.5;
}

.pri {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
  height: fit-content;
  margin-top: 2px;
}

.pri-p0 .pri { color: var(--color-danger); background: var(--color-danger-bg); }
.pri-p1 .pri { color: var(--color-warning); background: var(--color-warning-bg); }
.pri-p2 .pri { color: var(--color-text-tertiary); background: var(--color-bg-tertiary); }

/* ── Stack ── */
.stack-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.stack-item {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  text-align: center;
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.stack-item:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.stack-label {
  display: block;
  font-size: 10px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 4px;
  font-weight: 600;
}

.stack-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary);
}

.rationale {
  font-size: 13px;
  color: var(--color-text-tertiary);
  font-style: italic;
  margin: 0;
  line-height: 1.6;
}

/* ── Effort ── */
.effort-total {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-primary);
  margin-bottom: var(--space-4);
  letter-spacing: -0.02em;
}

.effort-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.effort-area {
  font-size: 13px;
  color: var(--color-text-secondary);
  width: 80px;
  font-weight: 500;
}

.effort-track {
  flex: 1;
  height: 8px;
  background: var(--color-bg-secondary);
  border-radius: 4px;
  overflow: hidden;
}

.effort-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), rgba(0, 122, 255, 0.6));
  border-radius: 4px;
  transition: width var(--duration-slow) var(--ease-apple);
}

.effort-hours {
  font-size: 13px;
  color: var(--color-text-tertiary);
  width: 40px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

/* ── Risks ── */
.risk-list {
  padding-left: 20px;
  color: var(--color-warning);
  font-size: 14px;
  line-height: 1.8;
  margin: 0;
}

.risk-list li {
  margin-bottom: var(--space-1);
}

/* ── Prompt ── */
.prompt-block {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-text-secondary);
  background: var(--color-bg-secondary);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  line-height: 1.7;
  margin: 0;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .stack-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .hero-actions {
    flex-direction: column;
  }

  .page-title {
    font-size: 26px;
  }

  .effort-total {
    font-size: 28px;
  }
}
</style>
