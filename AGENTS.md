# NeedRadar 项目指引

## 项目概述

NeedRadar 是一个 AI 驱动的用户需求挖掘系统。从全网（GitHub、StackOverflow、掘金、B站等）爬取讨论，通过 LLM 提取结构化需求，存储到 Obsidian vault，生成洞察报告并进行内容验证。

技术栈：Python / FastAPI / SQLAlchemy / SQLite / Vue 3 / Naive UI / LiteLLM / DeepSeek / LanceDB / Apache Burr / APScheduler

## 每日启动流程

**每次新对话开始时，必须执行以下步骤：**

1. 读取 `vault/05-工作日志/` 目录下最新的日志文件，了解最近的工作内容、关键决策和待办事项
2. 确认理解项目的当前状态：哪些功能已完成、哪些正在进行、哪些阻塞
3. 检查日志中的待办事项列表，主动报告哪些已完成、哪些仍待处理
4. 基于最新进度，向用户确认下一步工作方向

使用以下命令读取最新日志：
```
# 找到最新日志
ls -t vault/05-工作日志/*.md | head -1
# 读取内容
cat vault/05-工作日志/<最新文件名>
```

如果日志中有未完成的待办事项，主动提醒用户并询问是否继续推进。

## 关键目录结构

```
vault/                    # Obsidian vault（内容存储）
  01-原始素材库/           # 原始爬取数据
  02-需求池/               # LLM 提取的需求卡片
  03-分析车间/
    初稿打磨/              # 生成的报告和调研报告
    大纲挑选/              # 筛选后的大纲
    终稿确认/              # 待确认的终稿
  04-报告归档/             # 终稿归档
  05-工作日志/             # 每日工作日志（日期命名）
  06-关系图谱/             # Mermaid 需求关系图
src/needradar/
  api/v1/                 # REST API 路由（12 个模块）
  core/                   # 配置、数据库、日志、安全
  crawlers/               # 各平台爬虫（插件化自动发现）
  llm/                    # LLM 调用层（provider, pricing, presets, sanitizer）
  models/                 # SQLAlchemy 数据模型
  schemas/                # Pydantic 请求/响应 Schema
  services/               # 业务逻辑（pipeline_orchestrator, pipeline_actions, analysis, report, rag_retriever, vault_vectorizer, scheduler, verification, vault, usage, prompt_optimizer）
  utils/                  # 工具函数
  vector/                 # LanceDB 向量存储（去重/检索/RAG）
  cli.py                  # CLI 一键管道
frontend/                 # Vue 3 + Naive UI 前端（TypeScript）
  src/views/              # 12 个页面组件
  src/composables/        # Vue composables (useAgent, useReveal)
  src/styles/             # Design tokens (CSS variables)
  src/i18n/               # 国际化（zh/en）
config/                   # prompts.yaml, prompt_test_cases.yaml 等
scripts/                  # 开发辅助脚本
```

## 工作日志规范

每天工作结束时，将当天的工作内容写入 `vault/05-工作日志/YYYY-MM-DD.md`，格式遵循：
- YAML frontmatter：标题、阶段、日期、标签
- 正文包含：今日工作、关键决策、遇到的问题、待办事项
- 待办事项用 `- [ ]` 标记，完成时改为 `- [x]`

## 开发注意事项

- 后端启动命令：`cd F:/NeedRadar && python -m uvicorn needradar.main:app --host 127.0.0.1 --port 8900`
- 前端启动命令：`cd F:/NeedRadar/frontend && npx vite --port 5173`
- CLI 一键命令：`python -m needradar.cli run "关键词"`
- Prompt 优化：`python scripts/optimize_prompt.py [迭代次数] [耐心值] [候选数]`
- Obsidian vault 路径：`./vault`（相对于项目根目录）
- 数据库：SQLite（WAL 模式），文件位于 `data/needradar.db`
- LLM 配置持久化：`data/llm_config.json`
- 修改后端代码后建议手动重启 uvicorn（Windows 下 `--reload` 不稳定）
- 支持平台：GitHub / StackOverflow / 掘金 / B站（插件化自动发现，新增爬虫无需改配置）
- 前端审计规则：每次前端改动后需 Playwright CLI 验证（参见 memory/frontend_testing_rule）
