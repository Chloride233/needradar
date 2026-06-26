<!-- 生成日期: 2026-05-31 | 扫描文件: 76 | Token估算: ~450 -->

# 依赖与集成

## 外部服务

| 服务 | 用途 | 认证 | 模块 |
|---------|---------|------|--------|
| DeepSeek API | LLM (对话 + 结构化提取) | API key (`NR_DEEPSEEK_API_KEY`) | `llm/provider.py` |
| DeepSeek API | 嵌入 (text-embedding-3-small) | API key | `llm/provider.py` |
| GitHub API | Issues 搜索 (爬虫) | Token 可选 (`NR_GITHUB_TOKEN`) | `crawlers/github.py` |
| GitHub Trending | HTML 抓取 (无API) | 无 | `crawlers/github_trending.py` |
| Stack Exchange API | 问答搜索 | Key 可选 (`NR_STACKEXCHANGE_KEY`) | `crawlers/stackoverflow.py` |
| 掘金 API | 文章搜索 | 无 (公开) | `crawlers/juejin.py` |
| B站 API | 视频评论 (WBI签名) | Cookie会话 | `crawlers/bilibili.py` |
| OpenAI API | 可选备用 LLM | `NR_OPENAI_API_KEY` | `llm/provider.py` |
| Anthropic API | 可选备用 LLM | `NR_ANTHROPIC_API_KEY` | `llm/provider.py` |

## Python 核心包

| 包 | 版本 | 用途 |
|---------|---------|---------|
| fastapi | ≥0.115 | Web 框架 |
| uvicorn | ≥0.34 | ASGI 服务器 |
| sqlalchemy[asyncio] | ≥2.0 | ORM + 异步引擎 |
| litellm | ≥1.81 | 统一 LLM 接口 |
| lancedb | ≥0.17 | 向量数据库（嵌入式） |
| pydantic | ≥2.10 | 数据验证 |
| pydantic-settings | ≥2.7 | 环境配置 |
| httpx | ≥0.28 | 异步 HTTP 客户端 (爬虫) |
| apscheduler | ≥3.10 | 定时任务调度 |
| burr | ≥0.40 | Agent 编排框架 |
| pyyaml | ≥6.0 | 配置/提示词 YAML |
| loguru | ≥0.7 | 结构化日志 |
| alembic | ≥1.14 | 数据库迁移 (已配置, 未使用) |

## 前端包

| 包 | 版本 | 用途 |
|---------|---------|---------|
| vue | ^3.5 | UI 框架 |
| vue-router | ^4.4 | 客户端路由 |
| naive-ui | ^2.40 | 组件库 (暗色主题) |
| echarts | ^5.5 | 图表 (饼图、柱状图、折线图、双轴) |
| vue-echarts | ^7.0 | ECharts Vue 封装 |
| axios | ^1.7 | HTTP 客户端 |
| marked | ^18.0.3 | Markdown → HTML |
| dompurify | ^3.4.2 | HTML 净化 |
| vue-i18n | ^9.14.4 | 国际化 (中/英) |

## 配置文件

| 文件 | 用途 |
|------|---------|
| `config/prompts.yaml` | LLM 提示词 (requirement_extraction + _system_rules) |
| `config/prompt_test_cases.yaml` | 提示词优化的黄金测试用例 |
| `data/llm_config.json` | 持久化的 LLM 提供商配置 (运行时写入) |
| `.env` | 环境变量 (NR_ 前缀) |

## 已清理的未使用依赖 (2026-05-31)

以下依赖已从项目中移除（无代码引用）：
- ~~`celery[redis]`~~ — 已移除，实际用 APScheduler
- ~~`crawl4ai`~~ — 已移除，实际用 httpx 自建爬虫
- ~~`asyncpg`~~ — 已移除，实际数据库为 SQLite
- ~~`alembic`~~ — 已移除，无迁移脚本
- ~~`pinia`~~ — 已移除，stores/ 为空且无使用
