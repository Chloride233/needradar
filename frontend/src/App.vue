<template>
  <n-config-provider :theme-overrides="themeOverrides" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <div class="app-shell">
        <!-- Scroll Progress -->
        <div class="scroll-progress" :style="{ transform: `scaleX(${scrollProgress})` }"></div>

        <!-- Sidebar -->
        <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
          <div class="sidebar-glass">
            <div class="sidebar-brand">
              <div class="brand-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                </svg>
              </div>
              <span class="brand-name">NeedRadar</span>
            </div>

            <nav class="sidebar-nav" aria-label="主导航">
              <div v-for="group in navGroups" :key="group.label" class="nav-group">
                <span class="nav-group-label">{{ group.label }}</span>
                <router-link
                  v-for="item in group.items"
                  :key="item.path"
                  :to="item.path"
                  class="nav-item"
                  :class="{ active: isActive(item.path) }"
                >
                  <component :is="item.icon" class="nav-icon" />
                  <span class="nav-label">{{ item.label }}</span>
                </router-link>
              </div>
            </nav>

            <div class="sidebar-footer">
              <div class="status-indicator" :class="{ online: isOnline }">
                <span class="status-dot"></span>
                <span class="status-text">{{ isOnline ? '服务正常' : '服务离线' }}</span>
              </div>
            </div>
          </div>
        </aside>

        <!-- Main Content -->
        <div class="main-area">
          <main class="content" ref="contentRef" @scroll="onScroll">
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
import { computed, ref, onMounted, onUnmounted, h } from 'vue'
import { useRoute } from 'vue-router'
import { zhCN, dateZhCN, type GlobalThemeOverrides } from 'naive-ui'

// ── Route ──
const route = useRoute()
const isActive = (path: string) => route.path === path || route.path.startsWith(path + '/')

// ── Scroll progress ──
const contentRef = ref<HTMLElement | null>(null)
const scrollProgress = ref(0)
const sidebarCollapsed = ref(false)

function onScroll() {
  const el = contentRef.value
  if (!el) return
  const max = el.scrollHeight - el.clientHeight
  scrollProgress.value = max > 0 ? Math.min(el.scrollTop / max, 1) : 0
}

// ── Online status ──
const isOnline = ref(navigator.onLine)
function onOnline() { isOnline.value = true }
function onOffline() { isOnline.value = false }
onMounted(() => {
  window.addEventListener('online', onOnline)
  window.addEventListener('offline', onOffline)
})
onUnmounted(() => {
  window.removeEventListener('online', onOnline)
  window.removeEventListener('offline', onOffline)
})

// ── Inline SVG Icons (Lucide-style) ──
const Icon = (d: string) => () => h('svg', {
  width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
}, [h('path', { d })])

const IconHome = Icon('M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10')
const IconTrending = Icon('M23 6l-9.5 9.5-5-5L1 18')
const IconTarget = Icon('M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M12 6a6 6 0 1 0 0 12 6 6 0 0 0 0-12z M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z')
const IconFileText = Icon('M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8')
const IconClipboard = Icon('M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2 M9 2h6a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z')
const IconCheckCircle = Icon('M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4L12 14.01l-3-3')
const IconShield = Icon('M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z')
const IconBarChart = Icon('M12 20V10 M18 20V4 M6 20v-4')
const IconClock = Icon('M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M12 6v6l4 2')
const IconSettings = Icon('M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z')

// ── Navigation groups ──
const navGroups = [
  {
    label: 'Agent',
    items: [
      { path: '/', label: '指挥中心', icon: IconHome },
    ],
  },
  {
    label: '数据',
    items: [
      { path: '/requirements', label: '需求池', icon: IconFileText },
      { path: '/trending', label: '趋势选题', icon: IconTrending },
      { path: '/opportunities', label: '项目机会', icon: IconTarget },
      { path: '/reports', label: '报告', icon: IconBarChart },
    ],
  },
  {
    label: '系统',
    items: [
      { path: '/tasks', label: '爬取任务', icon: IconClipboard },
      { path: '/verification', label: '内容验证', icon: IconCheckCircle },
      { path: '/gates', label: '质量门', icon: IconShield },
      { path: '/scheduler', label: '调度器', icon: IconClock },
      { path: '/usage', label: '用量统计', icon: IconBarChart },
      { path: '/settings', label: '设置', icon: IconSettings },
    ],
  },
]

// ── Naive UI Theme (Apple-inspired) ──
const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#007AFF',
    primaryColorHover: '#0066D6',
    primaryColorPressed: '#004FAD',
    primaryColorSuppl: '#007AFF',
    bodyColor: '#F5F5F7',
    cardColor: '#FFFFFF',
    modalColor: '#FFFFFF',
    popoverColor: '#FFFFFF',
    inputColor: '#FFFFFF',
    actionColor: '#F5F5F7',
    borderColor: '#D2D2D7',
    dividerColor: '#E8E8ED',
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    fontFamilyMono: "'SF Mono', 'Fira Code', 'JetBrains Mono', monospace",
    borderRadius: '10px',
    borderRadiusSmall: '8px',
    textColor1: '#1D1D1F',
    textColor2: '#86868B',
    textColor3: '#AEAEB2',
    successColor: '#34C759',
    warningColor: '#FF9500',
    errorColor: '#FF3B30',
  },
  Card: {
    borderRadius: '12px',
    paddingMedium: '20px',
    color: '#FFFFFF',
    borderColor: '#E8E8ED',
  },
  Button: {
    borderRadiusMedium: '10px',
  },
  Tag: {
    borderRadius: '8px',
  },
  Input: {
    borderRadius: '10px',
    color: '#FFFFFF',
    borderColor: '#D2D2D7',
    colorFocus: '#FFFFFF',
    borderHover: '#007AFF',
    boxShadowFocus: '0 0 0 3px rgba(0, 122, 255, 0.15)',
  },
  DataTable: {
    borderRadius: '12px',
    thColor: '#F5F5F7',
    tdColor: '#FFFFFF',
    borderColor: '#E8E8ED',
  },
}
</script>

<style>
@import './styles/design-tokens.css';

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-sans);
  background: var(--color-bg-secondary);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overflow: hidden;
}

.app-shell { display: flex; height: 100vh; width: 100vw; }

/* ── Scroll Progress ── */
.scroll-progress {
  position: fixed;
  top: 0;
  left: var(--sidebar-width);
  right: 0;
  height: 2px;
  background: var(--gradient-accent);
  transform-origin: left;
  z-index: 100;
  transition: transform 150ms linear;
}

/* ── Sidebar ── */
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  position: relative;
  z-index: 10;
}

.sidebar-glass {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--glass-bg-heavy);
  backdrop-filter: blur(var(--glass-blur-heavy));
  -webkit-backdrop-filter: blur(var(--glass-blur-heavy));
  border-right: 1px solid var(--glass-border);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 20px 20px;
}

.brand-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--gradient-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3);
}

.brand-name {
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.02em;
}

.sidebar-nav {
  flex: 1;
  padding: 0 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-group {
  margin-bottom: 8px;
}

.nav-group-label {
  display: block;
  padding: 12px 12px 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--duration-normal) var(--ease-apple);
  position: relative;
}

.nav-item:hover {
  color: var(--color-text);
  background: rgba(0, 0, 0, 0.04);
}

.nav-item.active {
  color: var(--color-primary);
  background: var(--color-primary-bg);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 16px;
  background: var(--color-primary);
  border-radius: 0 2px 2px 0;
}

.nav-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  opacity: 0.7;
  transition: opacity var(--duration-fast);
}

.nav-item.active .nav-icon,
.nav-item:hover .nav-icon {
  opacity: 1;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-danger);
  transition: background var(--duration-normal);
}

.status-indicator.online .status-dot {
  background: var(--color-success);
  animation: pulse-glow 2s ease-in-out infinite;
}

.status-text {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

/* ── Main ── */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--color-bg-secondary);
}

.content::-webkit-scrollbar { width: 6px; }
.content::-webkit-scrollbar-track { background: transparent; }
.content::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}
.content::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-tertiary);
}

/* ── Naive UI Apple Overrides ── */
.n-card {
  border-radius: var(--radius-md) !important;
  transition: box-shadow var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple) !important;
}

/* ── Page Transition (Apple spring) ── */
.page-enter-active {
  transition: opacity var(--duration-hero) var(--ease-apple),
              transform var(--duration-hero) var(--ease-apple);
}

.page-leave-active {
  transition: opacity var(--duration-normal) var(--ease-apple),
              transform var(--duration-normal) var(--ease-apple);
}

.page-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ── Focus ── */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* ── Reduced Motion ── */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
  [data-reveal] {
    opacity: 1 !important;
    transform: none !important;
  }
}
</style>
