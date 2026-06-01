"""豆瓣爬虫 — 搜索小组讨论话题。"""

from __future__ import annotations

import re
from html import unescape

from loguru import logger

from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem


class DoubanCrawler(BaseCrawler):
    PLATFORM = "douban"

    SEARCH_URL = "https://www.douban.com/search"
    PAGE_SIZE = 20

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        items: list[RawDiscussionItem] = []
        start = 0
        seen_urls: set[str] = set()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        while len(items) < max_items:
            params = {"q": keyword, "cat": "1014", "start": start}
            try:
                resp = await self._request_with_retry("get", self.SEARCH_URL, params=params, headers=headers)
            except (ValueError, ConnectionError, TimeoutError, RuntimeError):
                logger.warning("douban_search_failed", keyword=keyword, start=start)
                break

            html = resp.text

            # Find all topic links with surrounding context
            pattern = (
                r'<a\s+[^>]*href="(https://www\.douban\.com/group/topic/\d+/)"[^>]*>'
                r'(.+?)</a>'
            )
            matches = re.findall(pattern, html, re.DOTALL)

            found = 0
            for url, raw_title in matches:
                title = unescape(re.sub(r'<[^>]+>', '', raw_title)).strip()
                if not title or url in seen_urls:
                    continue
                seen_urls.add(url)

                # Try to find excerpt near this URL in the full HTML
                idx = html.find(url)
                context = html[max(0, idx - 200):idx + 2000] if idx >= 0 else ""

                excerpt = ""
                for pat in [
                    r'<span\s+class="subject-cast"[^>]*>(.*?)</span>',
                    r'<p[^>]*>(.*?)</p>',
                ]:
                    m = re.search(pat, context, re.DOTALL)
                    if m:
                        excerpt = unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
                        if excerpt:
                            break

                rating_match = re.search(r'<span\s+class="rating_nums">([\d.]+)</span>', context)

                items.append(RawDiscussionItem(
                    platform="douban", source_url=url, title=title[:200],
                    content=excerpt[:3000] if excerpt else title,
                    tags=[f"评分:{rating_match.group(1)}"] if rating_match else [],
                ))
                found += 1

            logger.info("douban_crawl", keyword=keyword, start=start, found=found)
            if found == 0:
                break
            start += self.PAGE_SIZE

        return items[:max_items]
