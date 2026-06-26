<!-- 生成日期: 2026-05-31 | 扫描文件: 76 | Token估算: ~800 -->

# 后端架构

## API 路由 (`/api/v1`)

| 方法 | 路径 | 处理函数 | 模块 |
|--------|------|---------|--------|
| GET | `/health` | health_check | router.py |
| GET | `/health/detail` | health_detail | router.py |
| GET | `/dashboard` | get_dashboard | dashboard.py |
| GET | `/llm/presets` | list_presets | llm_config.py |
| PUT | `/llm/presets/{id}` | update_preset | llm_config.py |
| POST | `/llm/test/{id}` | test_model | llm_config.py |
| POST | `/tasks` | create_task → 后台流水线 | tasks.py |
| GET | `/tasks` | list_tasks | tasks.py |
| GET | `/tasks/{id}` | get_task | tasks.py |
| GET | `/tasks/sse/stream` | SSE 任务状态推送 | tasks.py |
| GET | `/tasks/platforms` | list_platforms | tasks.py |
| GET | `/requirements` | list_requirements | requirements.py |
| GET | `/requirements/summary` | requirement_summary | requirements.py |
| GET/POST | `/reports` | 列表 / 生成 | reports.py |
| GET | `/reports/download/{title}` | download_report (md) | reports.py |
| GET | `/reports/by-filename/{name}` | get_report_by_filename | reports.py |
| GET/POST | `/trending` | 列表 / 抓取 | trending.py |
| POST | `/trending/fetch-all` | fetch_all_trending | trending.py |
| POST | `/trending/analyze/{id}` | analyze_project (LLM) | trending.py |
| POST | `/trending/recommend` | recommend_topics (LLM) | trending.py |
| GET | `/trending/suggest-keywords` | suggest_keywords | trending.py |
| GET/POST | `/verification` | 列表 / 触发验证 | verification.py |
| GET | `/verification/results/{id}` | get_result | verification.py |
| POST | `/verification/results/{id}/feedback` | submit_feedback | verification.py |
| GET | `/verification/stats` | verification_stats | verification.py |
| GET/POST | `/scheduler` | 列表 / 创建 | scheduler.py |
| GET/PATCH/DELETE | `/scheduler/{id}` | 查看/更新/删除 | scheduler.py |
| POST | `/scheduler/{id}/trigger` | trigger_job | scheduler.py |
| GET | `/usage/summary` | usage_summary | usage.py |
| GET | `/usage/trend` | usage_trend | usage.py |
| GET | `/usage/records` | usage_records | usage.py |
| GET | `/usage/model-stats` | usage_model_stats | usage.py |
| GET | `/usage/budget` | usage_budget | usage.py |
| GET/POST | `/prompt-optimizer/start` | start_optimization | prompt_optimizer.py |
| POST | `/prompt-optimizer/stop` | stop_optimization | prompt_optimizer.py |
| GET | `/prompt-optimizer/status` | get_status | prompt_optimizer.py |
| GET | `/prompt-optimizer/results` | get_results | prompt_optimizer.py |

## 中间件链

1. CORS（来源从配置读取，credentials=True）
2. TrustedHost（允许所有主机）
   → 定义在 `core/security.py`，在 `main.py` 中应用

## 服务层

| 服务 | 用途 | 依赖 |
|---------|---------|-------------|
| `PipelineOrchestrator` | Burr 状态机编排 + 质量门 | Burr, PipelineActions, SQLAlchemy |
| `PipelineActions` | 爬取/提取/报告/归档/蒸馏 | CrawlerFactory, LLMProvider, LanceDB, VaultStore |
| `AnalysisService` | 爬取→提取→存储流水线 | CrawlerFactory, LLMProvider, LanceDB, VaultStore |
| `ReportService` | RAG 报告生成 + 关系图谱 | LLMProvider, LanceDB, VaultStore |
| `RAGRetriever` | 语义检索 vault 知识 | LanceDB (vault_knowledge) |
| `VaultVectorizer` | vault → chunk → embedding | LanceDB, VaultStore |
| `ContentVerifier` | 8步幻觉检测 | LLMProvider, VaultStore |
| `PromptOptimizer` | 迭代式提示词优化循环 | LLMProvider |
| `UsageService` | LLM 费用追踪 + 预算告警 | SQLAlchemy session |
| `VaultStore` | Obsidian vault 读写搜索 | config (vault路径) |
| `SchedulerService` | APScheduler 任务生命周期 | DB, Scheduler API |

## LLM 层 (`src/needradar/llm/`)

```
provider.py      — LLMProvider 单例 (litellm 封装, 结构化提取)
model_presets.py — PRESETS 注册表 (deepseek-v4-pro, deepseek-v4-flash)
config_store.py  — JSON 配置持久化 (data/llm_config.json)
pricing.py       — 按模型计费 (人民币)
sanitizer.py     — 注入检测, 输出净化, JSON 解析
```

## 爬虫 (`src/needradar/crawlers/`)

| 爬虫 | 平台 | 数据源 |
|---------|----------|--------|
| `GitHubCrawler` | github | GitHub Issues 搜索 API |
| `StackOverflowCrawler` | stackoverflow | Stack Exchange API |
| `JuejinCrawler` | juejin | 掘金搜索 API |
| `BilibiliCrawler` | bilibili | B站视频评论 (WBI签名) |
| `GitHubTrendingCrawler` | (trending) | GitHub Trending HTML 页面 |

由 `factory.py` 通过 `PLATFORM` 类属性自动发现。

## 向量存储 (`src/needradar/vector/`)

```
base.py           — VectorStore 抽象基类 (add/query/delete/count)
lancedb_store.py  — LanceDBVectorStore (all-MiniLM-L6-v2, 余弦距离, 嵌入式)
__init__.py       — create_vector_store() 工厂函数
```
