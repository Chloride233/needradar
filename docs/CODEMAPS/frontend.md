<!-- 生成日期: 2026-05-31 | 扫描文件: 76 | Token估算: ~700 -->

# 前端架构

## 技术栈

Vue 3 (组合式API) / Vite 6 / Naive UI 2.40 / ECharts 5 / Vue Router 4 / Axios / marked + DOMPurify / Vue I18n 9

## 路由映射

```
/                    → DashboardView.vue      (统计、图表、最近任务)
/tasks               → TaskView.vue           (创建任务、SSE实时更新)
/requirements        → RequirementView.vue    (AI洞察、痛点分析)
/reports             → ReportView.vue         (生成、查看、下载报告)
/trending            → TrendingView.vue       (GitHub热门、AI分析)
/verification        → VerificationView.vue   (幻觉检测评分)
/scheduler           → SchedulerView.vue      (类cron定时任务)
/usage               → UsageView.vue          (LLM费用追踪 + 图表)
/settings            → SettingsView.vue       (LLM模型配置)
/*                   → NotFoundView.vue       (404)
```

## 组件树

```
App.vue (外壳: 侧边栏 + 顶栏 + <router-view>)
├── DashboardView.vue
│   └── (ECharts VChart 内联, NTag)
├── TaskView.vue
│   └── (NDataTable 内联, SSE EventSource)
├── RequirementView.vue
│   └── (NTag 严重程度徽章)
├── ReportView.vue
│   └── (marked Markdown 渲染 + DOMPurify)
├── VerificationView.vue
│   └── (评分环, 声明判定表, 反馈表单)
├── TrendingView.vue
│   └── (项目卡片, AI分析模态框)
├── UsageView.vue
│   └── (ECharts 双轴图表, NDataTable)
├── SettingsView.vue
│   └── (NSlider, NInput, NTag)
└── SchedulerView.vue
    └── (间隔预设, 确认删除模态框)
```

无独立组件文件 — 所有UI内联在10个视图文件中（10 views, 0 components）。

## 状态管理

所有状态在视图内通过 `ref`/`reactive` 本地管理，无全局状态库。

| 状态 | 位置 | 持久化 |
|-------|----------|-------------|
| 语言 (zh/en) | localStorage (`nr-locale`) + i18n 实例 | localStorage |
| 主题 | Naive UI darkTheme + App.vue 中自定义覆盖 | 静态 |
| 后端在线状态 | `backendOnline` ref in api/client.ts | 内存 |
| 所有页面数据 | 每个视图内的 `ref`/`reactive` | 内存 |

## API 客户端 (`src/api/client.ts`)

- 基础路径: `/api/v1`（开发环境下通过 Vite 代理到 `localhost:8900`）
- 超时: 30秒
- 网络/503错误自动重试一次（延迟2秒）
- 错误、恢复、限流均通过 toast 通知
- 导出 `isConnected()` 用于在线/离线状态指示

## 关键工具

| 文件 | 用途 |
|------|---------|
| `src/utils/sanitize.ts` | DOMPurify 封装 (强制链接 noopener) |
| `src/i18n/zh.ts` | 中文标签 (导航 + 状态, 9个导航项) |
| `src/i18n/en.ts` | 英文标签 (与 zh.ts 镜像) |
| `src/i18n/index.ts` | I18n 配置 (组合式API, localStorage 持久化) |

## 构建配置

- Vite 代理: `/api` → `http://localhost:8900`
- 手动分包: `naive-ui`, `echarts`, `vendor` (Vue/Router/Axios)
- 开发端口: 5173
