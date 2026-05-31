from __future__ import annotations

from loguru import logger

from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem


class JuejinCrawler(BaseCrawler):
    PLATFORM = "juejin"

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        url = "https://api.juejin.cn/search_api/v1/search"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        items: list[RawDiscussionItem] = []
        cursor = "0"
        page_size = 40

        while len(items) < max_items:
            payload = {
                "key_word": keyword,
                "search_type": 0,
                "cursor": cursor,
                "limit": page_size,
            }

            resp = await self._request_with_retry("post", url, json=payload, headers=headers)
            data = resp.json()

            entries = data.get("data", [])
            if not entries:
                break

            for entry in entries:
                article_info = entry.get("article_info", entry.get("pin_info", {}))
                article_id = article_info.get("article_id", article_info.get("pin_id", ""))
                user_info = entry.get("author_user_info", {})
                content = article_info.get("brief_content") or article_info.get("content", "")

                if article_id:
                    source_url = f"https://juejin.cn/post/{article_id}"
                else:
                    source_url = ""

                items.append(
                    RawDiscussionItem(
                        platform="juejin",
                        source_url=source_url,
                        title=article_info.get("title", ""),
                        content=content,
                        author=user_info.get("user_name", ""),
                        tags=[kw for kw in entry.get("keywords", "").split(",") if kw] if isinstance(entry.get("keywords"), str) else [],
                    )
                )

            logger.info("juejin_crawl_page", keyword=keyword, cursor=cursor,
                        entries=len(entries), total_so_far=len(items))

            # 掘金 cursor 是下一页的游标字符串
            cursor = str(data.get("cursor", ""))
            if not cursor or cursor == "0" or len(entries) < page_size:
                break

        return items[:max_items]
