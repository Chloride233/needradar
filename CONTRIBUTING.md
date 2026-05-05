# Contributing to NeedRadar

感谢你对 NeedRadar 的关注！欢迎贡献代码、报告问题或建议新功能。

## 快速开始

```bash
git clone https://github.com/YOUR_USERNAME/NeedRadar.git
cd NeedRadar
pip install -e ".[dev]"
python -m uvicorn needradar.main:app --host 127.0.0.1 --port 8900
```

前端开发：

```bash
cd frontend
npm install
npx vite --port 5173
```

## 项目结构

```
src/needradar/
  api/v1/          # REST API 路由
  crawlers/        # 各平台爬虫（插件化）
  llm/             # LLM 调用层
  models/          # SQLAlchemy 数据模型
  services/        # 业务逻辑
  vector/          # ChromaDB 向量存储
frontend/          # Vue 3 + Naive UI
config/            # prompts.yaml 等配置
vault/             # Obsidian vault（内容存储）
```

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

### 报告 Bug

使用 GitHub Issues，包含：
- 复现步骤
- 期望行为 vs 实际行为
- 后端日志（如有）

### 提交 PR

1. Fork 仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "Add your feature"`
4. 推送：`git push origin feature/your-feature`
5. 创建 Pull Request

### 代码规范

- 后端：Python 3.11+，使用 ruff 格式化
- 前端：Vue 3 Composition API + TypeScript
- 提交信息使用英文，PR 描述可用中英文
