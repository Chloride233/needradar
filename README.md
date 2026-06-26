<![CDATA[<div align="center">

# 🔍 NeedRadar

**AI-Powered User Needs Mining Engine**

*Scan global tech discussions. Discover what to build next. Backed by data, verified by AI.*

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3-brightgreen.svg)](https://vuejs.org/)

</div>

---

## What is NeedRadar?

NeedRadar is an **end-to-end AI agent** that mines user needs from global tech discussions — GitHub Issues, Stack Overflow, Juejin, Bilibili — and transforms them into structured, verified insight reports.

It's not just a scraper. It's a **needs discovery pipeline** with human-in-the-loop quality gates, RAG-powered context enrichment, and hallucination detection.

```
Keyword → Crawl → AI Extract → Quality Gate → Report → Verify → Knowledge
            ↑          ↑              ↑
         4 platforms  LLM + RAG    Human confirms
```

## Why?

> The bottleneck in AI product development isn't coding — it's knowing **what to build**.

Most teams build features based on intuition. NeedRadar replaces that with a systematic pipeline:

- **Crawl** real discussions from where developers actually talk
- **Extract** structured needs with LLM (pain points, scenarios, sentiment)
- **Verify** reports against source material (8-step hallucination detection)
- **Learn** — every human correction feeds back into the knowledge base

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [DeepSeek API Key](https://platform.deepseek.com/) (recommended) or OpenAI/Anthropic key

### Install & Run

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/needradar.git
cd needradar

# Backend
pip install -e .
export NR_DEEPSEEK_API_KEY=your-key-here
python -m uvicorn needradar.main:app --host 127.0.0.1 --port 8900

# Frontend (new terminal)
cd frontend
npm install
npx vite --port 5173
```

Open **http://localhost:5173** — the Agent Command Center.

### One-Line CLI

```bash
# Full pipeline: crawl → extract → report → verify
python -m needradar.cli run "AI coding assistant" --platforms github,stackoverflow
```

## Features

| Feature | What it does |
|---------|-------------|
| 🕷️ **Multi-platform Crawl** | GitHub Issues/Discussions, Stack Overflow, Juejin, Bilibili — concurrent, incremental, fingerprint-based dedup |
| 🧠 **AI Needs Extraction** | LLM extracts structured requirements: title, description, pain point, scenario, sentiment, confidence |
| 🚦 **Quality Gates** | 3 human-in-the-loop checkpoints (material → requirement → insight). Approve, reject, or edit before proceeding |
| 📊 **Insight Reports** | RAG-enriched analysis with need clustering, pain point mapping, and actionable recommendations |
| ✅ **Content Verification** | 8-step hallucination detection: claim extraction → fact check → consistency → source reliability → weighted score |
| 🔮 **RAG Knowledge Base** | Vault content vectorized into LanceDB. Historical context enriches every LLM call |
| 📝 **Obsidian Native** | All content stored as Markdown in an Obsidian vault — browse, search, link with your existing knowledge base |
| 💰 **Cost Tracking** | Token usage, cost breakdown, cache hit rate, budget alerts — DeepSeek V4 Flash at ¥1/M input |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Command Center                  │
│              (Vue 3 + Naive UI Dashboard)                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Crawlers │  │   LLM    │  │ LanceDB  │  │ Vault  │  │
│  │ GitHub   │  │ LiteLLM  │  │ (vector) │  │ (Obsi- │  │
│  │ SO/Juejin│  │ DeepSeek │  │ 721 reqs │  │ dian)  │  │
│  │ Bilibili │  │          │  │ 1134 rag │  │ 936 md │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘  │
│       │              │              │            │       │
│       └──────────────┴──────────────┴────────────┘       │
│                          │                               │
│              ┌───────────┴───────────┐                   │
│              │ Pipeline Orchestrator  │                   │
│              │    (Apache Burr)       │                   │
│              │                        │                   │
│              │  crawl → GATE → extract │                   │
│              │  → GATE → report → GATE │                   │
│              │  → archive → distill    │                   │
│              └────────────────────────┘                   │
│                                                         │
│  FastAPI · SQLAlchemy · SQLite · APScheduler             │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python · FastAPI · SQLAlchemy · SQLite (WAL) |
| **AI/LLM** | LiteLLM · DeepSeek V4 · LanceDB (vector search + RAG) |
| **Orchestration** | Apache Burr (state machine + quality gates) |
| **Frontend** | Vue 3 · Naive UI · ECharts · TypeScript |
| **Storage** | SQLite + Obsidian Vault (Markdown) + LanceDB (embeddings) |
| **Scheduler** | APScheduler (background tasks) |

## Project Structure

```
needradar/
├── src/needradar/
│   ├── api/v1/           # REST API (16 modules)
│   ├── crawlers/         # Platform crawlers (plugin-based)
│   ├── llm/              # LLM layer (provider, pricing, sanitizer)
│   ├── models/           # SQLAlchemy models
│   ├── services/         # Business logic
│   │   ├── pipeline_orchestrator.py  # Burr state machine
│   │   ├── pipeline_actions.py       # Phase actions
│   │   ├── rag_retriever.py          # RAG context retrieval
│   │   ├── vault_vectorizer.py       # Vault → embeddings
│   │   └── ...
│   ├── vector/           # LanceDB vector store
│   └── cli.py            # CLI entry point
├── frontend/
│   ├── src/views/        # 12 page components
│   ├── src/composables/  # Vue composables (useAgent, useReveal)
│   └── src/styles/       # Design tokens (Apple-inspired)
├── config/
│   └── prompts.yaml      # LLM prompt templates (editable)
├── vault/                # Obsidian vault (content storage)
└── data/                 # Runtime data (gitignored)
```

## Pipeline Flow

```
         ┌─────────────┐
         │  User Input  │  keyword + platforms
         └──────┬──────┘
                ▼
    ┌───────────────────────┐
    │   1. CRAWL            │  GitHub / SO / Juejin / Bilibili
    │   Concurrent, incr.   │  Fingerprint dedup, noise filter
    └───────────┬───────────┘
                ▼
    ┌───────────────────────┐
    │ 🚦 MATERIAL GATE      │  Human: review raw items
    └───────────┬───────────┘
                ▼
    ┌───────────────────────┐
    │   2. EXTRACT           │  LLM + RAG context
    │   Structured needs     │  Embedding dedup
    └───────────┬───────────┘
                ▼
    ┌───────────────────────┐
    │ 🚦 REQUIREMENT GATE   │  Human: review extracted needs
    └───────────┬───────────┘
                ▼
    ┌───────────────────────┐
    │   3. REPORT + VERIFY   │  RAG analysis + 8-step verification
    │   Insight report       │  Hallucination detection
    └───────────┬───────────┘
                ▼
    ┌───────────────────────┐
    │ 🚦 INSIGHT GATE       │  Human: review report quality
    └───────────┬───────────┘
                ▼
    ┌───────────────────────┐
    │   4. ARCHIVE + DISTILL │  Knowledge extraction
    │   Feedback → Learning  │  Vault RAG index update
    └───────────────────────┘
```

## Configuration

### API Key

```bash
# Option 1: Environment variable
export NR_DEEPSEEK_API_KEY=your-key

# Option 2: Web UI → Settings page
```

### Custom Prompts

Edit `config/prompts.yaml` — changes take effect immediately, no restart needed:

- `requirement_extraction` — How needs are extracted from discussions
- `report_analysis` — How insight reports are generated
- `sentiment_analysis` — How sentiment is classified

## API

Full API docs: http://localhost:8900/docs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/agent/status` | GET | Agent dashboard data (runs, gates, stats) |
| `/api/v1/tasks` | POST/GET | Create/list crawl tasks |
| `/api/v1/gates` | GET | Quality gates list |
| `/api/v1/gates/{id}/approve` | POST | Approve a gate |
| `/api/v1/reports` | POST/GET | Generate/list reports |
| `/api/v1/requirements` | GET | Search/filter requirements |
| `/api/v1/verification/verify` | POST | Run content verification |
| `/api/v1/tasks/vault/index` | POST | Re-index vault for RAG |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and PR guidelines.

## License

[MIT](LICENSE)

---

<div align="center">

**NeedRadar** — *Every AI product direction, backed by data.*

</div>
]]>