<template>
  <div class="not-found">
    <div class="nf-content">
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
}

.nf-content {
  display: flex;
  align-items: center;
  gap: 40px;
}

.nf-code {
  font-family: 'Outfit', sans-serif;
  font-size: 120px;
  font-weight: 800;
  line-height: 1;
  color: var(--teal-200);
  user-select: none;
}

.nf-divider {
  width: 2px;
  height: 80px;
  background: var(--slate-200);
  border-radius: 1px;
}

.nf-title {
  font-family: 'Outfit', sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--slate-800);
  margin-bottom: 8px;
}

.nf-desc {
  font-size: 14px;
  color: var(--slate-400);
  margin-bottom: 20px;
}

.nf-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 10px;
  background: var(--teal-600);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s ease;
}

.nf-btn:hover {
  background: var(--teal-700);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(20, 196, 166, 0.2);
}
</style>
