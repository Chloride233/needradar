# NeedRadar — AI 驱动的全网需求挖掘引擎

> 扫描全网讨论，发现下一个爆款 AI 产品的方向

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- [DeepSeek API Key](https://platform.deepseek.com/)（推荐）或 OpenAI API Key

### 一键启动

```bash
# 1. 安装依赖
pip install -e .
cd frontend && npm install && cd ..

# 2. 启动后端（默认端口 8900）
python -m uvicorn needradar.main:app --host 127.0.0.1 --port 8900

# 3. 启动前端（默认端口 5173）
cd frontend && npx vite --port 5173
```

打开 http://localhost:5173 即可使用。

### CLI 一行命令

```bash
# 全流程：爬取 → 提取 → 报告 → 验证
python -m needradar.cli run "AI编程助手" --platforms github,stackoverflow

# 仅生成报告（基于已有数据）
python -m needradar.cli report "AI编程助手"

# 查看当前状态
python -m needradar.cli status
```

### 配置 API Key

方式一：环境变量
```bash
export NR_DEEPSEEK_API_KEY=your-key-here
```

方式二：在 Web 界面 → 设置页直接配置

## 核心功能

| 功能 | 说明 |
|------|------|
| **多平台爬取** | GitHub Issues/Discussions、Stack Overflow、掘金 |
| **AI 需求提取** | LLM 自动从讨论中提取结构化需求（痛点、场景、情感倾向） |
| **语义去重** | 基于 Embedding 向量的需求去重，合并相似表述 |
| **洞察报告** | 自动生成包含核心发现、需求聚类、痛点分析、行动建议的报告 |
| **内容验证** | 8 步幻觉检测管道：事实核查、一致性校验、来源可靠性评估 |
| **用量追踪** | Token 消耗、成本统计、缓存命中率、预算告警 |
| **Obsidian 集成** | 所有内容存储为 Obsidian vault 中的 Markdown 文件 |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python / FastAPI / SQLAlchemy / SQLite (WAL) |
| AI | LiteLLM / DeepSeek V4 / ChromaDB |
| 前端 | Vue 3 / Naive UI / ECharts / Pinia |
| 存储 | SQLite + Obsidian Vault + ChromaDB 向量索引 |

## 项目结构

```
NeedRadar/
├── src/needradar/
│   ├── api/v1/              # REST API（tasks, reports, requirements, verification...）
│   ├── crawlers/            # 各平台爬虫（github, stackoverflow, juejin）
│   ├── llm/                 # LLM 调用层（provider, presets, pricing, sanitizer）
│   ├── models/              # 数据模型（crawl_task, llm_usage, verification）
│   ├── services/            # 业务逻辑（analysis, report, verification, vault_store）
│   ├── vector/              # ChromaDB 向量存储（去重 + RAG）
│   └── cli.py               # CLI 入口
├── frontend/src/
│   └── views/               # 页面（Dashboard, Tasks, Requirements, Reports, Verification, Settings）
├── config/
│   ├── prompts.yaml         # LLM Prompt 模板（可自定义）
│   ├── platforms.yaml       # 平台爬虫配置
│   └── default.yaml         # 默认配置
├── vault/                   # Obsidian vault（内容存储）
│   ├── 01-原始素材库/
│   ├── 02-需求池/
│   ├── 03-分析车间/          # 初稿、报告
│   ├── 04-报告归档/
│   └── 05-工作日志/
├── data/                    # 运行时数据（gitignore）
│   ├── needradar.db         # SQLite 数据库
│   ├── chroma/              # ChromaDB 持久化
│   └── llm_config.json      # LLM 配置持久化
└── CLAUDE.md                # AI 协作指引
```

## 自定义报告模板

报告生成的 Prompt 存储在 `config/prompts.yaml`，可直接编辑：

- `report_analysis` — 报告分析 prompt
- `requirement_extraction` — 需求提取 prompt
- `sentiment_analysis` — 情感分析 prompt

修改后无需重启，下次调用自动生效。

## API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/tasks` | POST | 创建爬取任务 |
| `/api/v1/tasks` | GET | 任务列表 |
| `/api/v1/tasks/sse/stream` | GET | SSE 实时任务流 |
| `/api/v1/reports` | POST | 生成报告 |
| `/api/v1/reports` | GET | 报告列表 |
| `/api/v1/requirements` | GET | 需求列表（支持搜索/筛选） |
| `/api/v1/verification/verify` | POST | 触发内容验证 |
| `/api/v1/verification/results` | GET | 验证结果列表 |
| `/api/v1/usage/summary` | GET | 用量统计 |
| `/api/v1/dashboard` | GET | 仪表盘数据 |
| `/api/v1/llm/config` | GET/PUT | LLM 配置 |

完整 API 文档：启动后访问 http://localhost:8900/docs

## 工作流程

```
用户输入关键词
      │
      ▼
┌─ Phase 1: 并发爬取 ─┐
│  GitHub │ SO │ 掘金  │  ← 3 个平台同时爬取
└────────┴────┴───────┘
      │
      ▼
┌─ Phase 2: AI 提取 ──┐
│  每条讨论 → LLM 提取  │  ← 结构化需求（标题/描述/痛点/场景/情感）
│  Embedding 向量去重   │  ← 合并相似需求
└──────────────────────┘
      │
      ▼
┌─ Phase 3: 报告生成 ──┐
│  RAG 检索 + LLM 分析  │  ← 核心发现/聚类/痛点/建议
│  写入 Obsidian Vault  │
└──────────────────────┘
      │
      ▼
┌─ Phase 4: 内容验证 ──┐
│  声明提取 → 事实核查   │  ← 8 步幻觉检测
│  一致性 → 来源可靠性   │  ← 加权评分 0-100
└──────────────────────┘
```

## 成本优化

- DeepSeek V4 Flash 作为默认模型（Input ¥1/M，Output ¥2/M）
- 共享 System Prefix 利用 DeepSeek 前缀缓存（缓存命中 Token 成本降低 50%+）
- 批量处理减少 API 调用次数
- 用量仪表盘实时监控成本和缓存命中率

---

*NeedRadar — 让每一个 AI 产品方向，都有数据支撑。*
