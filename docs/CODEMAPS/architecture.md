<!-- 生成日期: 2026-05-31 | 扫描文件: 76 | Token估算: ~650 -->

# NeedRadar 架构总览

## 系统概览

AI 驱动的用户需求挖掘引擎：全网爬取 → LLM 提取结构化需求 → 存入 Obsidian vault → 生成洞察报告 → 幻觉检测验证。

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Vue 3 SPA   │────▶│  FastAPI      │────▶│  SQLite      │
│  (端口5173)  │     │  (端口8900)   │     │  (WAL模式)   │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌─────────┐  ┌──────────┐  ┌───────────┐
        │ LiteLLM │  │ ChromaDB │  │  Obsidian │
        │(DeepSeek)│  │ (向量库) │  │   Vault   │
        └─────────┘  └──────────┘  └───────────┘
              │
        ┌─────┴─────┐
        │ GitHub API │  StackExchange API
        │ 掘金 API   │  B站 API (WBI签名)
        └───────────┘
```

## 数据流（Pipeline）

```
关键词 → 爬虫 → RawDiscussionItem[] → 指纹去重
    → LLM 提取 (ExtractedRequirement) → ChromaDB 语义去重
    → Vault 写入 (02-需求池) → 报告生成 (RAG)
    → 内容验证 → Vault 归档 (03-分析车间 / 04-报告归档)
```

## 核心文件

| 文件 | 职责 | 行数 |
|------|------|------|
| `src/needradar/main.py` | FastAPI 入口，生命周期管理，中间件 | 56 |
| `src/needradar/core/config.py` | pydantic-settings，全局环境配置 | 57 |
| `src/needradar/core/database.py` | SQLAlchemy 异步引擎 + 会话工厂 | 43 |
| `src/needradar/services/analysis_service.py` | 核心爬取→提取→存储流水线 | 248 |
| `src/needradar/services/report_service.py` | RAG 报告生成 | 337 |
| `src/needradar/services/content_verifier.py` | 幻觉检测引擎 | 467 |
| `src/needradar/llm/provider.py` | LiteLLM 封装，结构化提取 | 322 |
| `src/needradar/crawlers/factory.py` | 爬虫自动发现工厂 | 56 |

## 架构决策

- **SQLite WAL 模式**：单进程 FastAPI 场景下支持并发读写
- **Vault 作为内容存储**：Obsidian 兼容的 Markdown + YAML frontmatter
- **ChromaDB 去重**：基于 all-MiniLM-L6-v2 的余弦相似度
- **DeepSeek via LiteLLM**：OpenAI 兼容 API，利用共享前缀缓存
- **无 Pinia stores**：所有状态在视图内通过 `ref`/`reactive` 管理
- **APScheduler** 处理定时抓取任务
