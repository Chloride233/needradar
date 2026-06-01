"""知乎搜索爬虫 — 通过官方搜索 API 获取问答、文章和想法。"""

from __future__ import annotations

from loguru import logger

from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem


class ZhihuCrawler(BaseCrawler):
    PLATFORM = "zhihu"

    SEARCH_URL = "https://www.zhihu.com/api/v4/search_v3"
    PAGE_SIZE = 20

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        items: list[RawDiscussionItem] = []
        offset = 0
        seen_ids: set[int] = set()

        while len(items) < max_items:
            params = {"q": keyword, "type": "content", "offset": offset, "limit": self.PAGE_SIZE}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://www.zhihu.com/search",
            }
            try:
                resp = await self._request_with_retry("get", self.SEARCH_URL, params=params, headers=headers)
            except (ValueError, ConnectionError, TimeoutError, RuntimeError):
                logger.warning("zhihu_search_failed", keyword=keyword, offset=offset)
                break

            data = resp.json()
            entries = data.get("data", [])
            if not entries:
                break

            for entry in entries:
                obj = entry.get("object", {}) or entry.get("target", {}) or entry
                obj_id = obj.get("id")
                if not obj_id or obj_id in seen_ids:
                    continue
                seen_ids.add(obj_id)

                obj_type = entry.get("type", obj.get("type", ""))
                if obj_type == "search_result":
                    obj_type = entry.get("object", {}).get("type", "")

                if obj_type == "answer":
                    question = obj.get("question", {})
                    title = question.get("title", "")
                    content = obj.get("excerpt", "")
                    url = f"https://www.zhihu.com/question/{question.get('id','')}/answer/{obj_id}"
                elif obj_type == "article":
                    title = obj.get("title", "")
                    content = obj.get("excerpt", "")
                    url = obj.get("url", f"https://zhuanlan.zhihu.com/p/{obj_id}")
                elif obj_type == "question":
                    title = obj.get("title", "")
                    content = obj.get("excerpt", obj.get("detail", ""))
                    url = f"https://www.zhihu.com/question/{obj_id}"
                elif obj_type == "pin":
                    title = f"知乎想法 {obj_id}"
                    content = obj.get("excerpt", "")
                    url = f"https://www.zhihu.com/pin/{obj_id}"
                else:
                    title = obj.get("title", obj.get("excerpt", f"知乎内容 {obj_id}"))
                    content = obj.get("excerpt", obj.get("content", ""))
                    url = obj.get("url", "")

                if not title or not content:
                    continue

                author_name = ""
                author_obj = obj.get("author", {}) or obj.get("member", {})
                if isinstance(author_obj, dict):
                    author_name = author_obj.get("name", "")

                tags = [t.get("name", "") for t in obj.get("topics", [])[:5] if isinstance(t, dict)]

                items.append(RawDiscussionItem(
                    platform="zhihu", source_url=url, title=title[:200],
                    content=content[:5000], author=author_name, tags=tags,
                ))

            logger.info("zhihu_crawl", keyword=keyword, offset=offset, count=len(items))
            paging = data.get("paging", {})
            if paging.get("is_end", False):
                break
            offset += self.PAGE_SIZE

        return items[:max_items]
