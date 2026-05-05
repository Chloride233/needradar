from __future__ import annotations

import re

from loguru import logger

from needradar.core.config import settings
from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text)


class StackOverflowCrawler(BaseCrawler):
    PLATFORM = "stackoverflow"

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        client = await self._get_client()
        page_size = 100
        items: list[RawDiscussionItem] = []
        page = 1

        while len(items) < max_items:
            url = "https://api.stackexchange.com/2.3/search/excerpts"
            params = {
                "order": "desc",
                "sort": "relevance",
                "q": keyword,
                "site": "stackoverflow",
                "pagesize": page_size,
                "page": page,
                "filter": "default",
            }
            if settings.stackexchange_key:
                params["key"] = settings.stackexchange_key

            resp = await self._request_with_retry("get", url, params=params)
            data = resp.json()

            entries = data.get("items", [])
            if not entries:
                break

            for entry in entries:
                body = _strip_html(entry.get("body", ""))
                link = f"https://stackoverflow.com/questions/{entry['question_id']}"
                owner = entry.get("owner", {})
                items.append(
                    RawDiscussionItem(
                        platform="stackoverflow",
                        source_url=link,
                        title=entry.get("title", ""),
                        content=body,
                        author=owner.get("display_name", ""),
                        tags=entry.get("tags", []),
                    )
                )

            logger.info("stackoverflow_crawl_page", keyword=keyword, page=page,
                        entries=len(entries), total=data.get("total", 0))

            has_more = data.get("has_more", False)
            if not has_more or len(entries) < page_size:
                break
            page += 1

        return items[:max_items]
