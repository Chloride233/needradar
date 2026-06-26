<template>
  <div class="settings-page" ref="pageRef">
    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-bg">
        <div class="hero-orb hero-orb-1"></div>
        <div class="hero-orb hero-orb-2"></div>
      </div>
      <div class="hero-content">
        <div class="hero-icon" data-reveal="up">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </div>
        <h1 class="hero-title" data-reveal="up" data-delay="100">LLM 模型配置</h1>
        <p class="hero-sub" data-reveal="up" data-delay="200">配置 DeepSeek API Key 后即可使用。配置自动持久化到服务端，重启后保留。所有模型共享同一 API Key。</p>
      </div>
    </section>

    <!-- Preset Cards -->
    <div class="preset-list">
      <div
        v-for="(p, idx) in presets"
        :key="p.id"
        class="preset-card"
        :class="{ active: activeId === p.id }"
        data-reveal="up"
        :data-delay="(idx + 1) * 100"
      >
        <div class="preset-top">
          <div class="preset-info">
            <div class="preset-name-row">
              <h4 class="preset-name">{{ p.name }}</h4>
              <span v-if="activeId === p.id" class="active-badge">已激活</span>
            </div>
            <span class="preset-url">{{ p.base_url }}</span>
          </div>
          <div class="preset-health">
            <span v-if="p.health?.success === true" class="health-badge health-ok">
              <span class="health-dot dot-ok"></span>
              {{ p.health.latency_ms }}ms
            </span>
            <span v-else-if="p.health?.success === false" class="health-badge health-err">
              <span class="health-dot dot-err"></span>
              异常
            </span>
            <span v-else-if="p.has_api_key" class="health-badge health-warn">
              <span class="health-dot dot-warn"></span>
              未测试
            </span>
          </div>
        </div>

        <div class="preset-fields">
          <div class="field-group">
            <label class="field-label">API Key</label>
            <div class="field-input-wrap">
              <input
                v-model="forms[p.id].api_key"
                type="password"
                class="field-input"
                :placeholder="p.api_key_masked || '输入 DeepSeek API Key'"
              />
              <button class="field-toggle" @click="toggleKeyVisibility($event)" title="显示/隐藏" aria-label="显示或隐藏 API Key">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                </svg>
              </button>
            </div>
          </div>

          <div class="field-row">
            <div class="field-group field-half">
              <label class="field-label">Temperature</label>
              <div class="slider-wrap">
                <input
                  type="range"
                  v-model.number="forms[p.id].temperature"
                  class="temp-slider"
                  min="0" max="2" step="0.1"
                />
                <span class="temp-value">{{ forms[p.id].temperature }}</span>
              </div>
            </div>
            <div class="field-group field-half">
              <label class="field-label">Max Tokens</label>
              <input
                type="number"
                v-model.number="forms[p.id].max_tokens"
                class="field-input"
                min="256" max="32768" step="256"
              />
            </div>
          </div>
        </div>

        <div class="preset-actions">
          <button class="action-btn btn-primary" @click="save(p.id)" :disabled="savingId === p.id">
            <span v-if="savingId === p.id" class="btn-spinner-sm"></span>
            {{ savingId === p.id ? '保存中...' : '保存配置' }}
          </button>
          <button class="action-btn btn-secondary" @click="test(p.id)" :disabled="testingId === p.id">
            <span v-if="testingId === p.id" class="btn-spinner-sm"></span>
            {{ testingId === p.id ? '测试中...' : '测试连接' }}
          </button>
        </div>

        <div v-if="testResults[p.id]" class="test-result" :class="testResults[p.id].success ? 'result-ok' : 'result-err'">
          <template v-if="testResults[p.id].success">
            连接成功 · 延迟 {{ testResults[p.id].latency_ms }}ms
          </template>
          <template v-else>
            {{ testResults[p.id].error || '连接失败' }}
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import api from '../api/client'
import { useReveal } from '../composables/useReveal'

interface HealthInfo { success?: boolean; latency_ms?: number; error?: string }
interface PresetData { id: string; name: string; base_url: string; has_api_key: boolean; api_key_masked: string; max_tokens: number; temperature: number; health?: HealthInfo | null }
interface TestResult { success: boolean; latency_ms?: number; error?: string }

const pageRef = ref<HTMLElement | null>(null)
useReveal(pageRef)

const message = useMessage()
const presets = ref<PresetData[]>([])
const activeId = ref('')
const forms = reactive<Record<string, { api_key: string; temperature: number; max_tokens: number }>>({})
const savingId = ref<string | null>(null)
const testingId = ref<string | null>(null)
const testResults = reactive<Record<string, TestResult | null>>({})

function toggleKeyVisibility(e: Event) {
  const btn = e.currentTarget as HTMLElement
  const input = btn.previousElementSibling as HTMLInputElement
  input.type = input.type === 'password' ? 'text' : 'password'
}

async function load() {
  try {
    const { data } = await api.get('/llm/presets')
    activeId.value = data.active || ''
    presets.value = data.presets || []
    for (const p of data.presets || []) {
      if (!forms[p.id]) {
        forms[p.id] = { api_key: '', temperature: p.temperature, max_tokens: p.max_tokens }
      } else {
        forms[p.id].temperature = p.temperature
        forms[p.id].max_tokens = p.max_tokens
      }
    }
  } catch { /* handled by interceptor */ }
}

async function save(presetId: string) {
  savingId.value = presetId
  try {
    const payload: Record<string, unknown> = {}
    if (forms[presetId].api_key) payload.api_key = forms[presetId].api_key
    payload.temperature = forms[presetId].temperature
    payload.max_tokens = forms[presetId].max_tokens
    await api.put(`/llm/presets/${presetId}`, payload)
    message.success('配置已保存并持久化')
    forms[presetId].api_key = ''
    await load()
  } catch {
    // error handled by axios interceptor
  } finally {
    savingId.value = null
  }
}

async function test(presetId: string) {
  testingId.value = presetId
  testResults[presetId] = null
  try {
    const { data } = await api.post(`/llm/test/${presetId}`)
    testResults[presetId] = data
    await load()
  } catch (e: any) {
    testResults[presetId] = { success: false, error: e.response?.data?.detail || '测试请求失败' }
  } finally {
    testingId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 var(--space-6);
  gap: var(--space-5);
}

/* ── Hero Section ── */
.hero {
  position: relative;
  padding: var(--space-8) 0 var(--space-7);
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
  animation: float 8s ease-in-out infinite;
}

.hero-orb-1 {
  width: 320px;
  height: 320px;
  background: var(--color-primary);
  top: -60px;
  left: -40px;
  opacity: 0.18;
  animation-delay: 0s;
}

.hero-orb-2 {
  width: 240px;
  height: 240px;
  background: var(--color-secondary);
  bottom: -40px;
  right: -20px;
  opacity: 0.14;
  animation-delay: -3s;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.hero-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-glass);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-5);
}

.hero-title {
  font-family: var(--font-sans);
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
  margin: 0 0 var(--space-3) 0;
}

.hero-sub {
  font-size: 15px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin: 0;
  max-width: 520px;
}

/* ── Preset Cards ── */
.preset-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding-bottom: var(--space-8);
}

.preset-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-glass);
  padding: var(--space-6);
  transition: box-shadow var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple), border-color var(--duration-normal) var(--ease-apple);
}

.preset-card:hover {
  box-shadow: var(--shadow-glass-hover);
  transform: translateY(-2px);
}

.preset-card.active {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-glass), 0 0 0 1px rgba(0, 122, 255, 0.15);
}

.preset-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}

.preset-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.preset-name {
  font-family: var(--font-sans);
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.active-badge {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.preset-url {
  display: block;
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: var(--space-1);
  font-family: var(--font-mono);
}

.health-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  transition: background var(--duration-fast) var(--ease-apple);
}

.health-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.health-ok { background: var(--color-success-bg); color: var(--color-success); }
.dot-ok { background: var(--color-success); }
.health-err { background: var(--color-danger-bg); color: var(--color-danger); }
.dot-err { background: var(--color-danger); }
.health-warn { background: var(--color-warning-bg); color: var(--color-warning); }
.dot-warn { background: var(--color-warning); }

/* ── Fields ── */
.preset-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.field-input-wrap {
  position: relative;
}

.field-input {
  width: 100%;
  height: 40px;
  padding: 0 40px 0 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  font-size: 13px;
  font-family: inherit;
  color: var(--color-text);
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(12px);
  outline: none;
  box-sizing: border-box;
  transition: border-color var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple), background var(--duration-normal) var(--ease-apple);
}

.field-input::placeholder {
  color: var(--color-text-tertiary);
}

.field-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15);
  background: var(--color-bg);
}

.field-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--color-text-tertiary);
  cursor: pointer;
  padding: 4px;
  display: flex;
  border-radius: var(--radius-sm);
  transition: color var(--duration-fast) var(--ease-apple);
}

.field-toggle:hover {
  color: var(--color-text-secondary);
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.slider-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.temp-slider {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--color-bg-tertiary);
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}

.temp-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
  transition: transform var(--duration-fast) var(--ease-spring);
}

.temp-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.temp-value {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  min-width: 28px;
  text-align: right;
}

/* ── Actions ── */
.preset-actions {
  display: flex;
  gap: var(--space-3);
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 22px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background var(--duration-normal) var(--ease-apple), transform var(--duration-normal) var(--ease-apple), box-shadow var(--duration-normal) var(--ease-apple);
  border: none;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  color: #FFFFFF;
  background: var(--gradient-accent);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(0, 122, 255, 0.3);
}

.btn-secondary {
  color: var(--color-primary);
  background: transparent;
  border: 1px solid var(--color-border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
}

.btn-spinner-sm {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.btn-secondary .btn-spinner-sm {
  border-color: rgba(0, 122, 255, 0.2);
  border-top-color: var(--color-primary);
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Test Result ── */
.test-result {
  margin-top: var(--space-4);
  padding: 12px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  backdrop-filter: blur(8px);
}

.result-ok {
  background: var(--color-success-bg);
  color: var(--color-success);
  border: 1px solid rgba(52, 199, 89, 0.15);
}

.result-err {
  background: var(--color-danger-bg);
  color: var(--color-danger);
  border: 1px solid rgba(255, 59, 48, 0.15);
}
</style>
