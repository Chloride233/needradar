<template>
  <div class="not-found">
    <div class="nf-content" data-reveal="scale">
      <div class="nf-code">404</div>
      <div class="nf-divider"></div>
      <div class="nf-body">
        <h2 class="nf-title">页面未找到</h2>
        <p class="nf-desc">你访问的页面不存在或已被移除</p>
        <router-link to="/" class="nf-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
          </svg>
          返回首页
        </router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  position: relative;
}

.nf-content {
  display: flex;
  align-items: center;
  gap: 40px;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-2xl);
  padding: var(--space-8) var(--space-9);
  box-shadow: var(--shadow-glass);
}

.nf-code {
  font-size: 120px;
  font-weight: 800;
  line-height: 1;
  background: var(--gradient-accent);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  user-select: none;
}

.nf-divider {
  width: 2px;
  height: 80px;
  background: var(--color-border-light);
  border-radius: 1px;
}

.nf-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 8px;
}

.nf-desc {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-bottom: 20px;
}

.nf-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 24px;
  border-radius: var(--radius-full);
  background: var(--gradient-accent);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: all var(--duration-normal) var(--ease-apple);
  box-shadow: 0 2px 8px rgba(0, 122, 255, 0.3);
}

.nf-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 122, 255, 0.4);
}
</style>
