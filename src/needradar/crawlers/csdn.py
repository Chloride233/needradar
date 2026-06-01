"""CSDN 搜索爬虫 — 通过站内搜索 API 获取博客和问答。"""

from __future__ import annotations

from loguru import logger

from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem


class CsdnCrawler(BaseCrawler):
    PLATFORM = "csdn"

    SEARCH_URL = "https://so.csdn.net/api/v3/search"
    PAGE_SIZE = 20

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        items: list[RawDiscussionItem] = []
        page = 1

        while len(items) < max_items:
            params = {"q": keyword, "t": "all", "p": page, "size": self.PAGE_SIZE}
            headers = {"User-Agent": "NeedRadar/0.2.0"}

            try:
                resp = await self._request_with_retry("get", self.SEARCH_URL, params=params, headers=headers)
            except (ValueError, ConnectionError, TimeoutError, RuntimeError):
                logger.warning("csdn_search_failed", keyword=keyword, page=page)
                break

            data = resp.json()
            if data.get("code") != 200:
                logger.warning("csdn_api_error", keyword=keyword, page=page, code=data.get("code"))
                break

            result_data = data.get("data", data)
            entries = result_data.get("result_vos", [])
            if not entries:
                break

            for entry in entries:
                title = entry.get("title", "").replace("<em>", "").replace("</em>", "")
                desc = entry.get("description", "").replace("<em>", "").replace("</em>", "")
                url = entry.get("url", "")
                author = entry.get("nickname", "")
                tags_str = entry.get("tags", "")

                if not title:
                    continue

                tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

                items.append(RawDiscussionItem(
                    platform="csdn", source_url=url, title=title[:200],
                    content=desc[:5000] if desc else title, author=author, tags=tags,
                ))

            logger.info("csdn_crawl", keyword=keyword, page=page, count=len(items))

            total = result_data.get("total", 0)
            total_pages = result_data.get("total_page", 0) or (total // self.PAGE_SIZE + 1 if total else 0)
            if page >= total_pages:
                break
            page += 1

        return items[:max_items]
