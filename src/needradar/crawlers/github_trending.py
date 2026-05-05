from __future__ import annotations

import re
from datetime import date
from typing import Iterator

from loguru import logger

from needradar.crawlers.base import BaseCrawler

_STRIP_HTML = re.compile(r"<[^>]+>")
_SINCE_MAP = {"daily": "today", "weekly": "this week", "monthly": "this month"}


class GitHubTrendingCrawler(BaseCrawler):
    """Scrape GitHub Trending pages. Not a keyword crawler — calls crawl_trending()."""

    async def crawl(self, keyword: str, max_items: int = 100) -> list:
        # Unused but required by BaseCrawler ABC
        return []

    async def crawl_trending(
        self,
        language: str = "",
        since: str = "daily",
    ) -> list[dict]:
        """Scrape one trending page. Returns list of raw project dicts."""
        client = await self._get_client()
        path = "/trending"
        if language:
            path += f"/{language}"
        url = f"https://github.com{path}"
        params = {"since": since}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html",
        }

        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        html = resp.text

        articles = re.findall(
            r'<article class="Box-row">(.*?)</article>', html, re.DOTALL
        )
        logger.info("trending_scrape", language=language or "any", since=since, count=len(articles))

        projects = []
        for article in articles:
            project = self._parse_article(article, since)
            if project:
                projects.append(project)

        return projects

    def _parse_article(self, html: str, since: str) -> dict | None:
        # Full name (owner/repo) from h2 link
        h2 = re.search(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
        if not h2:
            return None
        links = re.findall(r'<a[^>]+href="(/[^"]+)"', h2.group(1))
        full_name = links[-1].strip().lstrip("/") if links else None
        if not full_name or "/" not in full_name:
            return None

        # Description
        desc_m = re.search(r'<p class="col-9[^"]*">(.*?)</p>', html, re.DOTALL)
        description = _STRIP_HTML.sub("", desc_m.group(1)).strip() if desc_m else ""

        # Language
        lang_m = re.search(r'itemprop="programmingLanguage">(.*?)</span>', html)
        language = lang_m.group(1).strip() if lang_m else ""

        # Total stars
        stars_m = re.search(r'/stargazers[^>]*>(.*?)</a>', html, re.DOTALL)
        stars_text = _STRIP_HTML.sub("", stars_m.group(1)).strip() if stars_m else "0"
        stars = int(stars_text.replace(",", "")) if stars_text.replace(",", "").isdigit() else 0

        # Forks
        forks_m = re.search(r'/forks[^>]*>(.*?)</a>', html, re.DOTALL)
        forks_text = _STRIP_HTML.sub("", forks_m.group(1)).strip() if forks_m else "0"
        forks = int(forks_text.replace(",", "")) if forks_text.replace(",", "").isdigit() else 0

        # Period stars
        period_label = _SINCE_MAP.get(since, "today")
        period_m = re.search(rf'([\d,]+)\s*stars?\s+{re.escape(period_label)}', html)
        period_stars = int(period_m.group(1).replace(",", "")) if period_m else 0

        # Contributors
        contribs = re.findall(r'alt="(@[^"]+)"', html)

        return {
            "full_name": full_name,
            "description": description,
            "language": language,
            "stars": stars,
            "forks": forks,
            "period_stars": period_stars,
            "since": since,
            "contributors": ",".join(contribs),
            "snapshot_date": str(date.today()),
        }
