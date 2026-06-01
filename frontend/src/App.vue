<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <div class="app-shell">
        <aside class="sidebar">
          <div class="sidebar-brand">
            <div class="brand-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
            </div>
            <span class="brand-name">NeedRadar</span>
          </div>

          <nav class="sidebar-nav" aria-label="主导航">
            <router-link v-for="item in menuItems" :key="item.key" :to="item.key"
              class="nav-item" :class="{ active: currentRoute === item.key }">
              <span class="nav-dot"></span>
              <span class="nav-label">{{ item.label }}</span>
            </router-link>
          </nav>

          <div class="sidebar-footer">
            <div class="pulse" :class="{ off: !isOnline }"></div>
            <span class="status-label">{{ isOnline ? '在线' : '离线' }}</span>
          </div>
        </aside>

        <div class="main-area">
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
import { darkTheme, zhCN, dateZhCN, type GlobalThemeOverrides } from 'naive-ui'

const route = useRoute()
const currentRoute = computed(() => route.path)
const isOnline = ref(navigator.onLine)

function onOnline() { isOnline.value = true }
function onOffline() { isOnline.value = false }
onMounted(() => { window.addEventListener('online', onOnline); window.addEventListener('offline', onOffline) })
onUnmounted(() => { window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline) })

const menuItems = [
  { key: '/',              label: '发现中心' },
  { key: '/trending',      label: '趋势选题' },
  { key: '/opportunities', label: '项目机会' },
]

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#f5a623',
    primaryColorHover: '#f7b955',
    primaryColorPressed: '#d4891a',
    primaryColorSuppl: '#f5a623',
    bodyColor: '#0c0b0a',
    cardColor: 'rgba(255,255,255,0.03)',
    modalColor: '#141210',
    popoverColor: '#141210',
    inputColor: 'rgba(255,255,255,0.04)',
    actionColor: 'rgba(255,255,255,0.04)',
    borderColor: 'rgba(255,255,255,0.06)',
    dividerColor: 'rgba(255,255,255,0.04)',
    fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    fontFamilyMono: "'JetBrains Mono', monospace",
    borderRadius: '10px',
    borderRadiusSmall: '8px',
    textColor1: '#f0ebe3',
    textColor2: '#b8b0a4',
    textColor3: '#6b6460',
  },
  Card: { borderRadius: '12px', paddingMedium: '20px', color: 'rgba(255,255,255,0.02)', borderColor: 'rgba(255,255,255,0.05)' },
  Button: { borderRadiusMedium: '10px' },
  Tag: { borderRadius: '8px' },
  Input: { borderRadius: '10px', color: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.06)' },
  DataTable: { borderRadius: '12px', thColor: 'rgba(255,255,255,0.03)', tdColor: 'rgba(255,255,255,0.01)', borderColor: 'rgba(255,255,255,0.04)' },
}
</script>

<style>
:root {
  color-scheme: dark;
  --bg-root: #0c0b0a;
  --bg-surface: rgba(255,255,255,0.025);
  --bg-elevated: rgba(255,255,255,0.04);
  --border-subtle: rgba(255,255,255,0.06);
  --border-hover: rgba(255,255,255,0.10);
  --text-primary: #f0ebe3;
  --text-secondary: #b8b0a4;
  --text-muted: #6b6460;
  --accent: #f5a623;
  --accent-glow: rgba(245,166,35,0.15);
  --green: #34d399;
  --green-bg: rgba(52,211,153,0.1);
  --red: #fb7185;
  --red-bg: rgba(251,113,133,0.1);
  --amber: #fbbf24;
  --amber-bg: rgba(251,191,36,0.1);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --font-sans: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-display: 'Outfit', sans-serif;
  /* Legacy aliases — map old slate/teal tokens to new warm-amber system.
     Remove once all views are migrated to the new semantic tokens. */
  --slate-50: var(--bg-surface);
  --slate-100: var(--bg-elevated);
  --slate-200: var(--border-subtle);
  --slate-300: var(--border-hover);
  --slate-400: var(--text-muted);
  --slate-500: var(--text-muted);
  --slate-600: var(--text-secondary);
  --slate-700: var(--text-secondary);
  --slate-800: var(--text-primary);
  --slate-900: var(--text-primary);
  --teal-50: var(--accent-glow);
  --teal-100: var(--accent-glow);
  --teal-200: rgba(245,166,35,0.25);
  --teal-300: var(--accent);
  --teal-400: var(--accent);
  --teal-500: var(--accent);
  --card-border: var(--border-subtle);
  --card-border-hover: var(--border-hover);
  --error-bg: var(--red-bg);
  --error-text: var(--red);
  --error-border: rgba(251,113,133,0.2);
  --warning-bg: var(--amber-bg);
  --warning-text: var(--amber);
  --warning-border: rgba(251,191,36,0.2);
  --success-bg: var(--green-bg);
  --success-text: var(--green);
  --success-border: rgba(52,211,153,0.2);
  --emerald-500: var(--green);
  --amber-400: var(--amber);
  --amber-500: var(--amber);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-sans);
  background: var(--bg-root);
  color: var(--text-secondary);
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}

.app-shell { display: flex; height: 100vh; width: 100vw; }

/* ── Sidebar ── */
.sidebar {
  width: 200px; min-width: 200px;
  background: rgba(12,11,10,0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  display: flex; flex-direction: column;
  border-right: 1px solid var(--border-subtle);
  position: relative; z-index: 10;
}
.sidebar-brand { display: flex; align-items: center; gap: 10px; padding: 28px 20px 32px; }
.brand-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--accent-glow); display: flex;
  align-items: center; justify-content: center; color: var(--accent);
}
.brand-name { font-family: var(--font-display); font-size: 18px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.02em; }
.sidebar-nav { flex: 1; padding: 0 12px; display: flex; flex-direction: column; gap: 2px; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-radius: var(--radius-sm);
  color: var(--text-muted); text-decoration: none;
  font-size: 14px; font-weight: 500;
  transition: all 0.2s ease;
}
.nav-item:hover { color: var(--text-primary); background: var(--bg-elevated); }
.nav-item.active { color: var(--accent); background: var(--accent-glow); }
.nav-dot {
  width: 6px; height: 6px; border-radius: 50%; background: currentColor;
  opacity: 0.4; transition: opacity 0.2s, transform 0.2s;
}
.nav-item:hover .nav-dot, .nav-item.active .nav-dot { opacity: 1; }
.nav-item.active .nav-dot { transform: scale(1.4); }
.sidebar-footer {
  padding: 20px; border-top: 1px solid var(--border-subtle);
  display: flex; align-items: center; gap: 8px;
}
.pulse { width: 6px; height: 6px; border-radius: 50%; background: var(--green); animation: pulse 2s ease-in-out infinite; }
.pulse.off { background: var(--red); animation: none; }
.status-label { font-size: 11px; color: var(--text-muted); }
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(52,211,153,0.4); }
  50% { opacity: 0.6; box-shadow: 0 0 0 4px rgba(52,211,153,0); }
}

/* ── Main ── */
.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.content {
  flex: 1; overflow-y: auto;
  padding: 32px 36px 48px;
  background: var(--bg-root);
}
.content::-webkit-scrollbar { width: 5px; }
.content::-webkit-scrollbar-track { background: transparent; }
.content::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }

/* ── Naive overrides ── */
.n-card { backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); }
.n-card:hover { border-color: var(--border-hover) !important; }

/* ── Shared utility classes ── */
.section-heading { font-family: var(--font-display); font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 14px; }
.stat-num { font-variant-numeric: tabular-nums; }

/* ── Page transition ── */
.page-enter-active, .page-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to { opacity: 0; transform: translateY(-4px); }

/* ── Focus ── */
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
</style>
