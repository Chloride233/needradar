from __future__ import annotations

from loguru import logger

from needradar.core.config import settings
from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem

MAX_GITHUB_PAGES = 5


class GitHubCrawler(BaseCrawler):
    PLATFORM = "github"

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        headers = {}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"

        per_page = min(max_items, 100)
        url = "https://api.github.com/search/issues"
        items: list[RawDiscussionItem] = []
        seen_urls: set[str] = set()

        for page in range(1, MAX_GITHUB_PAGES + 1):
            if len(items) >= max_items:
                break
            params = {
                "q": f"{keyword} is:issue",
                "sort": "updated",
                "order": "desc",
                "per_page": per_page,
                "page": page,
            }

            resp = await self._request_with_retry("get", url, params=params, headers=headers)
            data = resp.json()

            if page == 1:
                remaining = resp.headers.get("X-RateLimit-Remaining", "?")
                logger.info("github_crawl", keyword=keyword, total=data.get("total_count", 0), rate_remaining=remaining)

            page_items = data.get("items", [])
            if not page_items:
                break

            for issue in page_items:
                source_url = issue.get("html_url", "")
                if source_url in seen_urls:
                    continue
                seen_urls.add(source_url)
                items.append(
                    RawDiscussionItem(
                        platform="github",
                        source_url=source_url,
                        title=issue.get("title", ""),
                        content=issue.get("body") or "",
                        author=issue.get("user", {}).get("login", ""),
                        tags=[label["name"] for label in issue.get("labels", []) if isinstance(label, dict)],
                    )
                )

            if len(page_items) < per_page:
                break

        return items[:max_items]
