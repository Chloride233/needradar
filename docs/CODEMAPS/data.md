<!-- 生成日期: 2026-05-31 | 扫描文件: 76 | Token估算: ~550 -->

# 数据层

## 数据库: SQLite (WAL模式) via SQLAlchemy async

连接: `data/needradar.db` | PRAGMAs: WAL, busy_timeout=5000ms, synchronous=NORMAL

## 数据表

### `crawl_tasks`
记录每次按关键词/平台的抓取执行情况。

| 列名 | 类型 | 说明 |
|--------|------|-------|
| id | UUID PK | |
| keyword | String, 索引 | |
| platform | String | github/stackoverflow/juejin/bilibili |
| status | Enum: PENDING/RUNNING/COMPLETED/FAILED | 索引 |
| total_items | Int | |
| new_items | Int | |
| skipped_items | Int | |
| error_message | String, 可空 | |
| report_path | String, 可空 | 生成报告的路径 |
| created_at/updated_at | DateTime(tz) | TimestampMixin |

### `crawl_fingerprints`
去重：追踪哪些URL已按关键词/平台处理过。

| 列名 | 类型 | 说明 |
|--------|------|-------|
| id | UUID PK | |
| keyword | String, 索引 | |
| platform | String | |
| source_url | String | |
| content_hash | String, 可空 | |
| 复合索引 | (keyword, platform) | |

### `scheduled_jobs`
定时抓取任务定义。

| 列名 | 类型 | 说明 |
|--------|------|-------|
| id | UUID PK | |
| name | String | |
| keyword | String, 索引 | |
| platforms | Text (JSON) | 例如 ["github","juejin"] |
| interval_minutes | Int | |
| status | Enum: ACTIVE/PAUSED | 索引 |
| last_run_at | DateTime | |
| last_task_ids | Text (JSON) | 任务UUID数组 |
| run_count | Int | |
| created_at/updated_at | DateTime(tz) | TimestampMixin |

### `trending_projects`
GitHub 热门项目快照。

| 列名 | 类型 | 说明 |
|--------|------|-------|
| id | UUID PK | |
| full_name | String, 索引 | 例如 "owner/repo" |
| description | String | |
| language | String, 索引 | |
| stars | Int | |
| forks | Int | |
| period_stars | Int | 周期内新增星数 |
| since | Enum: DAILY/WEEKLY/MONTHLY | 索引 |
| contributors | String | |
| tags | Text (JSON) | LLM生成 |
| snapshot_date | Date, 索引 | |
| is_analyzed | Bool | |
| created_at/updated_at | DateTime(tz) | TimestampMixin |

### `llm_usage`
LLM API 调用费用追踪。

| 列名 | 类型 | 说明 |
|--------|------|-------|
| id | UUID PK | |
| preset_id | String, 索引 | |
| model | String | |
| call_type | String | 例如 extraction, analysis, embed |
| input_tokens | Int | |
| output_tokens | Int | |
| cached_tokens | Int | DeepSeek 缓存命中 |
| total_tokens | Int | |
| cost_cny | Float | 人民币 |
| created_at/updated_at | DateTime(tz) | TimestampMixin |

### `verification_results`
内容验证/幻觉检测结果。

| 列名 | 类型 | 说明 |
|--------|------|-------|
| id | UUID PK | |
| report_title | String, 索引 | |
| status | Enum: PENDING/RUNNING/COMPLETED/FAILED | |
| overall_score | Float | 0.0–1.0 |
| fact_check_score | Float | 事实核查 |
| consistency_score | Float | 一致性 |
| source_reliability_score | Float | 来源可靠性 |
| total_claims | Int | |
| hallucination_count | Int | |
| flagged_count | Int | |
| claims_json | Text (JSON) | 带判定的声明数组 |
| suggestions_json | Text (JSON) | 修正建议 |
| reviewer_note | String, 可空 | 人工反馈 |
| reviewed_at | DateTime, 可空 | |
| created_at/updated_at | DateTime(tz) | TimestampMixin |

## Vault 结构 (Obsidian Markdown)

```
vault/
├── 01-原始素材库/     ← 原始爬取数据 (stage: "素材")
├── 02-需求池/         ← LLM提取的需求 (stage: "需求")
├── 03-分析车间/       
│   └── 初稿打磨/      ← 生成的报告、调研报告 (stage: "初稿")
├── 04-报告归档/       ← 终稿归档 (stage: "归档")
└── 05-工作日志/       ← 每日工作日志
```

每个文件: YAML frontmatter (keyword, platform, sentiment, emotion, source_url, tags, date) + Markdown 正文。使用 Wikilinks (`[[...]]`) 进行交叉引用。

## 向量存储: ChromaDB

- 集合: 可配置名称
- 嵌入: all-MiniLM-L6-v2 (SentenceTransformer, 离线模式)
- 距离: cosine
- 用途: 需求语义去重, 报告的 RAG 检索
- 持久化目录: 来自 `NR_CHROMA_PERSIST_DIR` 环境变量
