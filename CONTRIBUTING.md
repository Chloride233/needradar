# Contributing to NeedRadar

感谢你对 NeedRadar 的关注！欢迎贡献代码、报告问题或建议新功能。

## 常用命令

| 命令 | 说明 |
|------|------|
| `python -m uvicorn needradar.main:app --host 127.0.0.1 --port 8900` | 启动后端服务 |
| `python -m needradar.cli run "关键词"` | CLI 一键管道（爬取→提取→报告） |
| `python -m needradar.cli report "关键词"` | CLI 仅生成报告 |
| `python scripts/optimize_prompt.py` | Prompt 自优化（默认 10 轮） |
| `python scripts/optimize_prompt.py 20 5 3` | Prompt 自优化（20 轮, 耐心 5, 3 候选/轮） |
| `python -m pytest tests/ -v` | 运行全部测试 |
| `python -m pytest tests/ -q` | 运行测试（安静模式） |
| `cd frontend && npm run dev` | 启动前端开发服务器 |
| `cd frontend && npm run build` | 构建前端生产包 |
| `cd frontend && npm run preview` | 预览前端生产构建 |

## 环境变量

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `NR_DEEPSEEK_API_KEY` | 是 | DeepSeek API 密钥 | `sk-xxx` |
| `NR_DEBUG` | 否 | 调试模式（默认 false） | `true` |
| `NR_LOG_LEVEL` | 否 | 日志级别（默认 INFO） | `DEBUG`, `INFO`, `WARN` |
| `NR_LANCEDB_DIR` | 否 | LanceDB 持久化路径 | `./data/lancedb` |
| `NR_DATABASE_URL` | 否 | PostgreSQL 连接串（生产用） | `postgresql+asyncpg://...` |

## 快速开始

```bash
git clone https://github.com/Chloride233/needradar.git
cd needradar
cp .env.example .env
# 编辑 .env，填入 NR_DEEPSEEK_API_KEY
pip install -e ".[dev]"
python -m uvicorn needradar.main:app --host 127.0.0.1 --port 8900
```

前端开发：

```bash
cd frontend
npm install
npm run dev
```

## 项目结构

```
src/needradar/
  api/v1/          # REST API 路由（18 个已注册模块）
  core/            # 配置、数据库、日志、安全中间件
  crawlers/        # 各平台爬虫（插件化自动发现）
  llm/             # LLM 调用层（provider, pricing, presets, sanitizer）
  models/          # SQLAlchemy 数据模型
  schemas/         # Pydantic 请求/响应 Schema
  services/        # 业务逻辑（analysis, report, scheduler, verification, vault, usage, prompt_optimizer）
  utils/           # 工具函数
  vector/          # LanceDB 向量存储（去重/检索/RAG）
  cli.py           # 一键管道 CLI
  main.py          # FastAPI 入口
frontend/          # Vue 3 + Naive UI（TypeScript）
  src/views/       # 16 个页面组件
  src/i18n/        # 国际化（zh/en）
  src/api/         # API 客户端
config/            # prompts.yaml, prompt_test_cases.yaml 等
scripts/           # 开发辅助脚本
vault/             # Obsidian vault（内容存储）
  01-原始素材库/    # 原始爬取数据
  02-需求池/        # LLM 提取的需求卡片
  03-分析车间/      # 初稿打磨、大纲挑选、终稿确认
  04-报告归档/      # 终稿归档
  05-工作日志/      # 每日工作日志
  06-关系图谱/      # Mermaid 需求关系图
```

## 支持的数据源

NeedRadar 当前有 3 个 Full Support 和 6 个 Experimental 关键词采集平台。认证、
限流、支持等级和测试覆盖以 [crawler audit](docs/crawler-audit.md) 为准。

## 如何贡献

### 添加新的数据源爬虫

1. 在 `src/needradar/crawlers/` 下创建新文件，如 `reddit.py`
2. 继承 `BaseCrawler`，定义 `PLATFORM` 类属性，实现 `crawl()` 方法
3. 返回 `list[RawDiscussionItem]` — 系统会自动发现并注册

```python
from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem

class RedditCrawler(BaseCrawler):
    PLATFORM = "reddit"

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        # 实现爬取逻辑
        return items
```

无需修改任何其他文件，系统会在启动时自动注册。

### 运行测试

```bash
# 全部测试
python -m pytest tests/ -v

# 仅单元测试
python -m pytest tests/unit/ -v

# 仅集成测试
python -m pytest tests/integration/ -v
```

### 报告 Bug

使用 GitHub Issues，包含：
- 复现步骤
- 期望行为 vs 实际行为
- 后端日志（如有）

### 提交 PR

1. Fork 仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "feat: add your feature"`
4. 推送：`git push origin feature/your-feature`
5. 创建 Pull Request

### 代码规范

- **后端**: Python 3.11+，ruff 格式化（line-length=100，select E/F/I/N/W）
- **前端**: Vue 3 Composition API + TypeScript，Naive UI 组件
- **提交信息**: 遵循 [Conventional Commits](https://www.conventionalcommits.org/)（feat/fix/refactor/docs/test/chore）
- **PR 描述**: 可用中英文
