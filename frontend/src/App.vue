<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <div class="app-shell">
        <aside class="sidebar">
          <div class="sidebar-brand">
            <div class="brand-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                <path d="M2 12h20"/>
              </svg>
            </div>
            <span class="brand-name">NeedRadar</span>
          </div>

          <nav class="sidebar-nav" aria-label="主导航">
            <router-link
              v-for="item in menuItems"
              :key="item.key"
              :to="item.key"
              class="nav-item"
              :class="{ active: currentRoute === item.key }"
            >
              <span class="nav-icon" v-html="item.icon"></span>
              <span class="nav-label">{{ item.label }}</span>
            </router-link>
          </nav>

          <div class="sidebar-footer">
            <button class="lang-toggle" @click="toggleLocale" aria-label="切换语言">
              {{ locale === 'zh' ? 'EN' : '中文' }}
            </button>
            <div class="version-tag">v0.1.0</div>
          </div>
        </aside>

        <div class="main-area">
          <header class="topbar">
            <h1 class="page-title">{{ pageTitle }}</h1>
            <div class="topbar-right">
              <div class="pulse-dot" :class="{ offline: !isOnline }"></div>
              <span class="status-text" :class="{ offline: !isOnline }">{{ isOnline ? t('status.online') : t('status.offline') }}</span>
            </div>
          </header>

          <main class="content">
            <router-view v-slot="{ Component }">
              <transition name="page" mode="out-in">
                <component :is="Component" :key="$route.path" />
              </transition>
            </router-view>
          </main>
        </div>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { darkTheme, zhCN, dateZhCN, type GlobalThemeOverrides } from 'naive-ui'

const { t, locale } = useI18n()

const route = useRoute()
const currentRoute = computed(() => route.path)
const isOnline = ref(navigator.onLine)

function onOnline() { isOnline.value = true }
function onOffline() { isOnline.value = false }

function toggleLocale() {
  const next = locale.value === 'zh' ? 'en' : 'zh'
  locale.value = next
  localStorage.setItem('nr-locale', next)
}

onMounted(() => { window.addEventListener('online', onOnline); window.addEventListener('offline', onOffline) })
onUnmounted(() => { window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline) })
const pageTitle = computed(() => {
  const map: Record<string, string> = {
    '/': t('nav.dashboard'),
    '/tasks': t('nav.tasks'),
    '/requirements': t('nav.requirements'),
    '/reports': t('nav.reports'),
    '/trending': t('nav.trending'),
    '/verification': t('nav.verification'),
    '/scheduler': t('nav.scheduler'),
    '/usage': t('nav.usage'),
    '/settings': t('nav.settings'),
  }
  return map[route.path] || 'NeedRadar'
})

const menuItems = [
  {
    key: '/',
    label: '数据概览',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
  },
  {
    key: '/tasks',
    label: '任务管理',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  },
  {
    key: '/requirements',
    label: '需求洞察',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
  },
  {
    key: '/reports',
    label: '报告中心',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
  },
  {
    key: '/trending',
    label: '趋势选题',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
  },
  {
    key: '/verification',
    label: '内容验证',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
  },
  {
    key: '/scheduler',
    label: '定时调度',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
  },
  {
    key: '/usage',
    label: '用量统计',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
  },
  {
    key: '/settings',
    label: '模型配置',
    icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  },
]

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#14c4a6',
    primaryColorHover: '#2dd4bf',
    primaryColorPressed: '#0d9488',
    primaryColorSuppl: '#14c4a6',
    bodyColor: '#0a0a0a',
    cardColor: '#141414',
    modalColor: '#1a1a1a',
    popoverColor: '#1a1a1a',
    tableColor: '#141414',
    inputColor: '#1a1a1a',
    actionColor: '#1a1a1a',
    borderColor: '#2a2a2a',
    dividerColor: '#222222',
    fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    fontFamilyMono: "'JetBrains Mono', 'Fira Code', monospace",
    borderRadius: '10px',
    borderRadiusSmall: '8px',
    textColor1: '#f0f0f0',
    textColor2: '#c0c0c0',
    textColor3: '#888888',
  },
  Card: {
    borderRadius: '12px',
    paddingMedium: '20px',
    paddingLarge: '24px',
    color: '#141414',
    borderColor: '#2a2a2a',
  },
  Button: {
    borderRadiusMedium: '10px',
    borderRadiusSmall: '8px',
  },
  Tag: {
    borderRadius: '8px',
  },
  Input: {
    borderRadius: '10px',
    color: '#1a1a1a',
    borderColor: '#2a2a2a',
  },
  DataTable: {
    borderRadius: '12px',
    thColor: '#1a1a1a',
    tdColor: '#141414',
    borderColor: '#222222',
  },
}
</script>

<style>
:root {
  color-scheme: dark;

  /* Dark surface scale (mapped from slate) */
  --slate-50: #141414;
  --slate-100: #1a1a1a;
  --slate-200: #2a2a2a;
  --slate-300: #363636;
  --slate-400: #666666;
  --slate-500: #888888;
  --slate-600: #a0a0a0;
  --slate-700: #c0c0c0;
  --slate-800: #e0e0e0;
  --slate-900: #f0f0f0;

  --amber-400: #fbbf24;
  --amber-500: #f59e0b;

  --emerald-500: #34d399;

  /* Accent teal — brighter for dark backgrounds */
  --teal-50: rgba(20, 196, 166, 0.08);
  --teal-100: rgba(20, 196, 166, 0.15);
  --teal-200: rgba(20, 196, 166, 0.25);
  --teal-300: #2dd4bf;
  --teal-400: #3eeadb;
  --teal-500: #14c4a6;
  --teal-600: #0d9488;
  --teal-700: #0f766e;
  --teal-800: #115e59;
  --teal-900: #134e4a;

  --sidebar-bg: linear-gradient(180deg, #0c5c54 0%, #0a4a44 50%, #083834 100%);
  --card-border: #2a2a2a;
  --card-border-hover: #363636;

  /* Semantic colors for dark */
  --success-bg: rgba(52, 211, 153, 0.1);
  --success-text: #34d399;
  --success-border: rgba(52, 211, 153, 0.2);
  --error-bg: rgba(244, 63, 94, 0.1);
  --error-text: #fb7185;
  --error-border: rgba(244, 63, 94, 0.2);
  --warning-bg: rgba(245, 158, 11, 0.1);
  --warning-text: #fbbf24;
  --warning-border: rgba(245, 158, 11, 0.2);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #0a0a0a;
  color: var(--slate-800);
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}

.app-shell {
  display: flex;
  height: 100vh;
  width: 100vw;
}

/* ── Sidebar ── */
.sidebar {
  width: 232px;
  min-width: 232px;
  background: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  padding: 0;
  position: relative;
  z-index: 10;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px 28px;
}

.brand-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-name {
  font-family: 'Outfit', sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.02em;
}

.sidebar-nav {
  flex: 1;
  padding: 0 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.55);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.2s ease, background 0.2s ease;
  cursor: pointer;
}

.nav-item:hover {
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.06);
}

.nav-item.active {
  color: #fff;
  background: rgba(20, 196, 166, 0.15);
  border: 1px solid rgba(20, 196, 166, 0.2);
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.nav-label {
  line-height: 1;
}

.sidebar-footer {
  padding: 16px 20px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.lang-toggle {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.4);
  font-size: 11px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.lang-toggle:hover {
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.7);
}

.version-tag {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.25);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

/* ── Main Area ── */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 32px;
  background: #0e0e0e;
  border-bottom: 1px solid var(--slate-200);
  flex-shrink: 0;
}

.page-title {
  font-family: 'Outfit', sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--slate-900);
  letter-spacing: -0.02em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--emerald-500);
  animation: pulse 2s ease-in-out infinite;
}

.pulse-dot.offline {
  background: #f43f5e;
  animation: none;
}

@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.4); }
  50% { opacity: 0.8; box-shadow: 0 0 0 6px rgba(52, 211, 153, 0); }
}

.status-text {
  font-size: 13px;
  color: var(--slate-500);
  font-weight: 500;
}

.status-text.offline {
  color: #fb7185;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px 40px;
  background: #0a0a0a;
}

/* ── Scrollbar ── */
.content::-webkit-scrollbar { width: 6px; }
.content::-webkit-scrollbar-track { background: transparent; }
.content::-webkit-scrollbar-thumb { background: var(--slate-300); border-radius: 3px; }
.content::-webkit-scrollbar-thumb:hover { background: var(--slate-400); }

/* ── Naive UI Overrides for Dark ── */
.n-card {
  background: #141414 !important;
  border: 1px solid var(--card-border) !important;
  box-shadow: none !important;
  transition: border-color 0.25s ease;
}
.n-card:hover {
  border-color: var(--card-border-hover) !important;
}

.n-data-table .n-data-table-th {
  background: #1a1a1a !important;
  font-weight: 600 !important;
  color: var(--slate-500) !important;
  font-size: 12px !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--slate-200) !important;
}

.n-data-table .n-data-table-td {
  font-size: 13px !important;
  color: var(--slate-700) !important;
  border-bottom: 1px solid rgba(42, 42, 42, 0.5) !important;
}

.n-data-table .n-data-table-tr:hover .n-data-table-td {
  background: rgba(20, 196, 166, 0.04) !important;
}

/* ── Utility classes ── */
.section-title {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-700);
  margin-bottom: 16px;
}

/* ── Focus Visible ── */
:focus-visible {
  outline: 2px solid var(--teal-400);
  outline-offset: 2px;
}

button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {
  outline: 2px solid var(--teal-400);
  outline-offset: 2px;
}

/* ── Tabular numbers ── */
.stat-value, .stat-val, .summary-value, .list-count, .count-tag, .task-items, .task-elapsed, .task-badge, .suggest-heat, .job-stats .stat-item, .meta-keyword {
  font-variant-numeric: tabular-nums;
}

/* ── Reduced Motion ── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  .page-enter-active, .page-leave-active {
    transition: none !important;
  }
}

/* Global page transition */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
