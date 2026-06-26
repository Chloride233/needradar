<template>
  <div ref="pageRef" class="req-detail">
    <!-- Loading / Error / Empty states -->
    <div v-if="loading" class="loading-state" data-reveal="scale">
      <div class="spinner"></div>
      <span>加载需求...</span>
    </div>
    <div v-if="error" class="error-banner" data-reveal="up">
      <span>{{ error }}</span>
      <button class="retry-btn" @click="fetchAll">重试</button>
    </div>
    <div v-if="!loading && !error && !req" class="empty-state" data-reveal="up">
      需求未找到。<router-link to="/requirements">返回需求池</router-link>
    </div>

    <template v-if="req">
      <!-- Hero -->
      <div class="hero" data-reveal="up">
        <div class="hero-orbs">
          <div class="orb orb--blue"></div>
          <div class="orb orb--purple"></div>
          <div class="orb orb--pink"></div>
        </div>
        <div class="hero-content">
          <router-link to="/requirements" class="back-link">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            返回需求池
          </router-link>
          <h1 class="detail-title">{{ req.title }}</h1>
          <div class="detail-meta">
            <span class="meta-tag">{{ req.source_platform }}</span>
            <span class="meta-dot">·</span>
            <span>{{ req.keyword }}</span>
            <span class="meta-dot">·</span>
            <span>{{ req.created_at }}</span>
          </div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs" data-reveal="up" data-delay="100">
        <button :class="{ active: tab === 'overview' }" @click="tab = 'overview'">概览</button>
        <button :class="{ active: tab === 'links' }" @click="tab = 'links'">关联对象</button>
        <button :class="{ active: tab === 'similar' }" @click="tab = 'similar'">相似需求</button>
      </div>

      <!-- Tab: Overview -->
      <div v-if="tab === 'overview'" class="tab-content">
        <div class="stat-cards" data-reveal="up" data-delay="150">
          <div class="stat-card" :class="req.sentiment">
            <span class="stat-label">情感强度</span>
            <span class="stat-value">{{ sentimentLabel(req.sentiment) }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">置信度</span>
            <span class="stat-value">{{ (req.confidence * 100).toFixed(0) }}%</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">提及次数</span>
            <span class="stat-value">{{ req.mention_count }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">来源平台</span>
            <span class="stat-value">{{ req.source_platform }}</span>
          </div>
        </div>

        <section class="detail-section" data-reveal="up" data-delay="200">
          <h2>描述</h2>
          <p class="desc-text">{{ req.description }}</p>
        </section>

        <section class="detail-section" data-reveal="up" data-delay="250">
          <h2>情感分析</h2>
          <div class="emotion-row">
            <span class="emotion-tag" :class="req.emotion">{{ emotionLabel(req.emotion) }}</span>
            <div class="sentiment-bar"><div class="sent-fill" :style="{ width: (req.confidence * 100) + '%' }"></div></div>
          </div>
        </section>

        <section v-if="req.source_url" class="detail-section" data-reveal="up" data-delay="300">
          <h2>来源链接</h2>
          <a :href="req.source_url" target="_blank" rel="noopener" class="source-link">{{ req.source_url }}</a>
        </section>

        <section class="detail-section" data-reveal="up" data-delay="400">
          <h2>动作</h2>
          <div class="action-row">
            <button class="action-btn" disabled title="即将上线">标记为已验证</button>
            <button class="action-btn" @click="copyTitle">复制标题</button>
          </div>
        </section>
      </div>

      <!-- Tab: Links -->
      <div v-if="tab === 'links'" class="tab-content">
        <div v-if="linksLoading" class="loading-state" data-reveal="scale">
          <div class="spinner"></div>
          <span>加载关联...</span>
        </div>
        <div v-else-if="links.length === 0" class="empty-state" data-reveal="up">暂无关联对象</div>
        <div v-else class="links-list" data-reveal="up">
          <div v-for="(group, gi) in groupedLinks" :key="group.label" class="link-group" :data-reveal="'up'" :data-delay="(gi * 100 + 100).toString()">
            <h3>{{ group.label }} ({{ group.items.length }})</h3>
            <div v-for="item in group.items" :key="item.id" class="link-item">
              <span class="link-dir">{{ item.direction === 'outgoing' ? '→' : '←' }}</span>
              <span class="link-type">{{ item.link_type }}</span>
              <span class="link-target">{{ item.other_type }}</span>
              <span class="link-id">{{ item.other_id }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab: Similar -->
      <div v-if="tab === 'similar'" class="tab-content">
        <div class="empty-state" data-reveal="up">
          <p>相似需求检索即将上线</p>
          <p class="hint">基于 LanceDB 向量相似度，发现语义相近的需求</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/client'
import { useReveal } from '../composables/useReveal'

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

const route = useRoute()
const pathParam = computed(() => route.query.path as string)

const req = ref<any>(null)
const loading = ref(true)
const error = ref('')
const tab = ref('overview')
const links = ref<any[]>([])
const linksLoading = ref(false)

function sentimentLabel(s: string): string { return { strong: '强烈', moderate: '中等', mild: '轻微' }[s] || s }
function emotionLabel(e: string): string { return { positive: '正向', negative: '负向', neutral: '中性' }[e] || e }

const groupedLinks = computed(() => {
  const groups: Record<string, { label: string; items: any[] }> = {}
  const labels: Record<string, string> = { derived_from: '来源于', contains: '包含', generates: '生成', references: '引用', verified_by: '被验证', executed_in: '执行于' }
  for (const l of links.value) {
    const key = l.link_type
    if (!groups[key]) groups[key] = { label: labels[key] || key, items: [] }
    groups[key].items.push(l)
  }
  return Object.values(groups)
})

function copyTitle() { if (req.value?.title) navigator.clipboard.writeText(req.value.title) }

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
/* ── Page layout ── */
.req-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}

/* ── Loading / Error / Empty ── */
.loading-state,
.error-banner,
.empty-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-7);
  border-radius: var(--radius-xl);
  justify-content: center;
  color: var(--color-text-secondary);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-glass);
}
.error-banner {
  background: rgba(255, 59, 48, 0.06);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid rgba(255, 59, 48, 0.2);
  color: var(--color-danger);
}
.retry-btn {
  padding: 6px 16px;
  border-radius: var(--radius-full);
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  transition: all var(--duration-normal) var(--ease-apple);
}
.retry-btn:hover {
  background: rgba(255, 59, 48, 0.08);
}
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border-light);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state {
  flex-direction: column;
}
.empty-state a {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
  transition: opacity var(--duration-normal) var(--ease-apple);
}
.empty-state a:hover { opacity: 0.7; }
.hint {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin: 0;
}

/* ── Hero ── */
.hero {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-2xl);
  padding: var(--space-9) var(--space-7) var(--space-7);
  background: var(--gradient-hero-subtle);
}
.hero-orbs {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
  animation: float 8s ease-in-out infinite;
}
.orb--blue {
  width: 300px;
  height: 300px;
  background: rgba(0, 122, 255, 0.2);
  top: -80px;
  left: -60px;
}
.orb--purple {
  width: 250px;
  height: 250px;
  background: rgba(88, 86, 214, 0.18);
  top: -40px;
  right: -40px;
  animation-delay: -3s;
}
.orb--pink {
  width: 200px;
  height: 200px;
  background: rgba(240, 147, 251, 0.15);
  bottom: -60px;
  left: 40%;
  animation-delay: -5s;
}
.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* ── Header ── */
.back-link {
  font-size: 13px;
  color: var(--color-primary);
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  transition: opacity var(--duration-normal) var(--ease-apple);
  width: fit-content;
}
.back-link:hover { opacity: 0.7; }
.detail-title {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
  letter-spacing: -0.025em;
  line-height: 1.2;
}
.detail-meta {
  font-size: 13px;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.meta-tag {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
}
.meta-dot { color: var(--color-text-tertiary); }

/* ── Tabs ── */
.tabs {
  display: flex;
  gap: var(--space-1);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--space-1);
  box-shadow: var(--shadow-glass);
}
.tabs button {
  flex: 1;
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
  border-radius: var(--radius-lg);
  font-family: inherit;
  font-weight: 500;
  transition: all var(--duration-normal) var(--ease-apple);
}
.tabs button.active {
  color: var(--color-text);
  background: var(--color-bg);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}
.tabs button:hover:not(.active) {
  color: var(--color-text);
  background: rgba(0, 0, 0, 0.03);
}
.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* ── Stat cards ── */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}
.stat-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}
.stat-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}
.stat-card.strong { border-left: 3px solid var(--color-warning); }
.stat-card.moderate { border-left: 3px solid var(--color-primary); }
.stat-card.mild { border-left: 3px solid var(--color-text-tertiary); }
.stat-label {
  font-size: 11px;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
}

/* ── Detail sections ── */
.detail-section {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}
.detail-section:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}
.detail-section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 var(--space-4);
  letter-spacing: -0.01em;
}
.desc-text {
  font-size: 15px;
  color: var(--color-text-secondary);
  line-height: 1.75;
  white-space: pre-wrap;
  margin: 0;
}

/* ── Emotion ── */
.emotion-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.emotion-tag {
  font-size: 13px;
  padding: 5px 14px;
  border-radius: var(--radius-full);
  font-weight: 600;
  flex-shrink: 0;
}
.emotion-tag.positive { background: var(--color-success-bg); color: var(--color-success); }
.emotion-tag.negative { background: var(--color-danger-bg); color: var(--color-danger); }
.emotion-tag.neutral { background: var(--color-bg-secondary); color: var(--color-text-secondary); }
.sentiment-bar {
  flex: 1;
  height: 6px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.sent-fill {
  height: 100%;
  background: var(--gradient-accent);
  border-radius: var(--radius-full);
  transition: width var(--duration-slow) var(--ease-out);
}

/* ── Source link ── */
.source-link {
  font-size: 14px;
  color: var(--color-primary);
  word-break: break-all;
  text-decoration: none;
  transition: opacity var(--duration-normal) var(--ease-apple);
}
.source-link:hover { opacity: 0.7; }

/* ── Action buttons ── */
.action-row {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.action-btn {
  padding: 10px 20px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(var(--glass-blur));
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  font-weight: 500;
  transition: all var(--duration-normal) var(--ease-apple);
}
.action-btn:hover:not(:disabled) {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-1px);
}
.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Links ── */
.links-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.link-group {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  box-shadow: var(--shadow-glass);
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}
.link-group:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}
.link-group h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 var(--space-3);
}
.link-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 13px;
}
.link-item:last-child { border-bottom: none; }
.link-dir {
  color: var(--color-text-tertiary);
  font-weight: 700;
  font-size: 14px;
}
.link-type {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
}
.link-target {
  color: var(--color-text-secondary);
}
.link-id {
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Responsive ── */
@media (max-width: 640px) {
  .req-detail {
    padding: 0 var(--space-4);
  }
  .hero {
    padding: var(--space-7) var(--space-5) var(--space-5);
  }
  .detail-title {
    font-size: 24px;
  }
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
