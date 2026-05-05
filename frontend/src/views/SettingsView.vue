<template>
  <div class="settings-page">
    <div class="settings-header-card">
      <div class="settings-header-inner">
        <div class="settings-header-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </div>
        <div>
          <h3 class="settings-header-title">LLM 模型配置</h3>
          <p class="settings-header-desc">配置 DeepSeek API Key 后即可使用。配置自动持久化到服务端，重启后保留。所有模型共享同一 API Key。</p>
        </div>
      </div>
    </div>

    <div class="preset-list">
      <div
        v-for="p in presets"
        :key="p.id"
        class="preset-card"
        :class="{ active: activeId === p.id }"
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

interface HealthInfo { success?: boolean; latency_ms?: number; error?: string }
interface PresetData { id: string; name: string; base_url: string; has_api_key: boolean; api_key_masked: string; max_tokens: number; temperature: number; health?: HealthInfo | null }
interface TestResult { success: boolean; latency_ms?: number; error?: string }

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
  gap: 20px;

}


/* ── Header ── */
.settings-header-card {
  background: #141414;
  border-radius: 16px;
  border: 1px solid var(--slate-100);
  box-shadow: none;
  padding: 24px;
}

.settings-header-inner {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.settings-header-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: var(--teal-50);
  color: var(--teal-600);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.settings-header-title {
  font-family: 'Outfit', sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--slate-900);
  margin-bottom: 4px;
}

.settings-header-desc {
  font-size: 13px;
  color: var(--slate-400);
  line-height: 1.6;
}

/* ── Preset Cards ── */
.preset-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.preset-card {
  background: #141414;
  border-radius: 16px;
  border: 2px solid var(--card-border);
  box-shadow: none;
  padding: 24px;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.preset-card:hover {
  border-color: var(--card-border-hover);
}

.preset-card.active {
  border-color: var(--teal-300);
  border-color: var(--teal-300);box-shadow: 0 0 0 1px var(--teal-200);
}

.preset-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 20px;
}

.preset-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.preset-name {
  font-family: 'Outfit', sans-serif;
  font-size: 17px;
  font-weight: 600;
  color: var(--slate-900);
}

.active-badge {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 6px;
  background: var(--teal-50);
  color: var(--teal-700);
  font-size: 11px;
  font-weight: 600;
}

.preset-url {
  display: block;
  font-size: 12px;
  color: var(--slate-400);
  margin-top: 4px;
}

.health-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
}

.health-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.health-ok { background: var(--success-bg); color: var(--success-text); }
.dot-ok { background: #10b981; }
.health-err { background: var(--error-bg); color: var(--error-text); }
.dot-err { background: #f43f5e; }
.health-warn { background: var(--warning-bg); color: var(--warning-text); }
.dot-warn { background: #f59e0b; }

/* ── Fields ── */
.preset-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.field-group { display: flex; flex-direction: column; gap: 6px; }

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--slate-500);
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
  border-radius: 10px;
  border: 1.5px solid var(--slate-200);
  font-size: 13px;
  font-family: inherit;
  color: var(--slate-800);
  background: var(--slate-50);
  outline: none;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.field-input:focus {
  border-color: var(--teal-300);
  background: #1a1a1a;
  box-shadow: 0 0 0 3px rgba(20,196,166,0.15);
}

.field-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--slate-400);
  cursor: pointer;
  padding: 4px;
  display: flex;
}

.field-toggle:hover { color: var(--slate-600); }

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.slider-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.temp-slider {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--slate-200);
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}

.temp-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--teal-600);
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(13,148,136,0.3);
  transition: transform 0.15s;
}

.temp-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.temp-value {
  font-family: 'Outfit', sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--slate-700);
  min-width: 28px;
  text-align: right;
}

/* ── Actions ── */
.preset-actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 20px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  border: none;
}

.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-primary {
  color: #fff;
  background: linear-gradient(135deg, var(--teal-500), var(--teal-700));
}

.btn-primary:hover:not(:disabled) {
  box-shadow: 0 4px 14px rgba(20,196,166,0.2);
  transform: translateY(-1px);
}

.btn-secondary {
  color: var(--slate-600);
  background: var(--slate-50);
  border: 1.5px solid var(--slate-200);
}

.btn-secondary:hover:not(:disabled) {
  border-color: var(--slate-300);
  background: #141414;
}

.btn-spinner-sm {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.btn-secondary .btn-spinner-sm {
  border-color: rgba(0,0,0,0.1);
  border-top-color: var(--slate-600);
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Test Result ── */
.test-result {
  margin-top: 14px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
}

.result-ok {
  background: var(--success-bg);
  color: var(--success-text);
}

.result-err {
  background: var(--error-bg);
  color: var(--error-text);
}
</style>
