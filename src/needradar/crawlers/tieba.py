"""百度贴吧爬虫 — HTML 搜索解析帖子列表。"""

from __future__ import annotations

import re
from html import unescape

from loguru import logger

from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem


class TiebaCrawler(BaseCrawler):
    PLATFORM = "tieba"

    SEARCH_URL = "https://tieba.baidu.com/f/search/res"

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        items: list[RawDiscussionItem] = []
        page = 1
        seen_urls: set[str] = set()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        while len(items) < max_items:
            params = {"qw": keyword, "pn": (page - 1) * 50, "ie": "utf-8"}
            try:
                resp = await self._request_with_retry("get", self.SEARCH_URL, params=params, headers=headers)
            except (ValueError, ConnectionError, TimeoutError, RuntimeError):
                logger.warning("tieba_search_failed", keyword=keyword, page=page)
                break

            html = resp.text
            post_blocks = re.findall(r'<div\s+class="s_post"[^>]*>(.*?)</div>\s*(?:</div>)?', html, re.DOTALL)

            if not post_blocks:
                # Fallback: detect title links directly
                links = re.findall(
                    r'<span\s+class="p_title"[^>]*>.*?<a[^>]*href="(/p/\d+)"[^>]*>(.*?)</a>', html)
                for url, title in links:
                    url = "https://tieba.baidu.com" + url
                    title_clean = unescape(re.sub(r'<[^>]+>', '', title)).strip()
                    if not title_clean or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    items.append(RawDiscussionItem(
                        platform="tieba", source_url=url, title=title_clean[:200],
                        content=title_clean,
                    ))
                break

            found = 0
            for block in post_blocks:
                m = re.search(r'<a\s+[^>]*href="(/p/\d+)"[^>]*>(.*?)</a>', block, re.DOTALL)
                if not m:
                    continue
                url = "https://tieba.baidu.com" + m.group(1)
                title = unescape(re.sub(r'<[^>]+>', '', m.group(2))).strip()
                if not title or url in seen_urls:
                    continue
                seen_urls.add(url)

                excerpt = ""
                em = re.search(r'<p[^>]*class="[^"]*p_content[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
                if em:
                    excerpt = unescape(re.sub(r'<[^>]+>', '', em.group(1))).strip()
                author = ""
                am = re.search(r'p_author_name"[^>]*>(.*?)<', block)
                if am:
                    author = am.group(1).strip()

                items.append(RawDiscussionItem(
                    platform="tieba", source_url=url, title=title[:200],
                    content=excerpt[:3000] if excerpt else title, author=author,
                ))
                found += 1

            logger.info("tieba_crawl", keyword=keyword, page=page, found=found)
            if found == 0:
                break
            page += 1

        return items[:max_items]
