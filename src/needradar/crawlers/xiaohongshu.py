"""小红书爬虫 — SSR 数据提取 + Cookie API 降级。

优先从 HTML __INITIAL_STATE__ 提取（免 cookie）。
如果 SSR 解析失败，尝试 cookie API（需环境变量 NR_XHS_COOKIE）。
"""

from __future__ import annotations

import json
import os
import re

from loguru import logger

from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem


class XiaohongshuCrawler(BaseCrawler):
    PLATFORM = "xiaohongshu"

    SEARCH_URL = "https://www.xiaohongshu.com/search_result"

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        items: list[RawDiscussionItem] = []
        page = 1
        seen_ids: set[str] = set()
        cookie = os.environ.get("NR_XHS_COOKIE", "")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.xiaohongshu.com/",
        }
        if cookie:
            headers["Cookie"] = cookie

        while len(items) < max_items:
            params = {"keyword": keyword, "page": page}
            try:
                resp = await self._request_with_retry("get", self.SEARCH_URL, params=params, headers=headers)
            except (ValueError, ConnectionError, TimeoutError, RuntimeError):
                logger.warning("xhs_search_failed", keyword=keyword, page=page)
                break

            html = resp.text
            notes = self._parse_ssr(html, seen_ids)
            if not notes and cookie:
                notes = await self._api_fallback(keyword, page, cookie, seen_ids)

            if not notes:
                break

            items.extend(notes)
            logger.info("xhs_crawl", keyword=keyword, page=page, count=len(notes))
            page += 1

        return items[:max_items]

    def _parse_ssr(self, html: str, seen_ids: set[str]) -> list[RawDiscussionItem]:
        m = re.search(r'__INITIAL_STATE__\s*=\s*({.*?})\s*</script>', html, re.DOTALL)
        if not m:
            m = re.search(r'__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
        if not m:
            return []

        try:
            raw = m.group(1).replace("undefined", "null")
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []

        note_list = self._find_notes(data)
        return self._build_items(note_list, seen_ids)

    def _find_notes(self, data: dict, depth: int = 0) -> list[dict]:
        if depth > 6 or not isinstance(data, dict):
            return []
        for key in ("notes", "noteList", "note_list", "items", "feeds"):
            val = data.get(key)
            if isinstance(val, list) and val and isinstance(val[0], dict):
                return val
        for val in data.values():
            if isinstance(val, dict):
                r = self._find_notes(val, depth + 1)
                if r:
                    return r
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        r = self._find_notes(item, depth + 1)
                        if r:
                            return r
        return []

    def _build_items(self, note_list: list[dict], seen_ids: set[str]) -> list[RawDiscussionItem]:
        items: list[RawDiscussionItem] = []
        for note in note_list:
            nid = str(note.get("id", note.get("noteId", note.get("note_id", ""))))
            if not nid or nid in seen_ids:
                continue
            seen_ids.add(nid)

            title = note.get("title", note.get("displayTitle", note.get("display_title", "")))
            desc = note.get("desc", note.get("description", ""))
            author = ""
            au = note.get("author", note.get("user", {}))
            if isinstance(au, dict):
                author = au.get("name", au.get("nickname", ""))
            tags = []
            for t in note.get("tags", []) or []:
                if isinstance(t, dict):
                    tags.append(t.get("name", ""))
                elif isinstance(t, str):
                    tags.append(t)

            if not title and not desc:
                continue

            items.append(RawDiscussionItem(
                platform="xiaohongshu",
                source_url=f"https://www.xiaohongshu.com/explore/{nid}" if nid else "",
                title=(title or desc)[:200],
                content=(desc or title)[:5000],
                author=author, tags=tags,
            ))
        return items

    async def _api_fallback(
        self, keyword: str, page: int, cookie: str, seen_ids: set[str]
    ) -> list[RawDiscussionItem]:
        if not cookie:
            return []
        url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
        h = {"Cookie": cookie, "Content-Type": "application/json",
             "User-Agent": "Mozilla/5.0", "Referer": "https://www.xiaohongshu.com/"}
        payload = {"keyword": keyword, "page": page, "page_size": 20,
                    "search_id": "", "sort": "general", "note_type": 0}
        try:
            resp = await self._request_with_retry("post", url, json=payload, headers=h)
            data = resp.json()
        except (ValueError, ConnectionError, TimeoutError, RuntimeError):
            return []
        if not data.get("success", True):
            return []
        notes = data.get("data", {}).get("notes", [])
        return self._build_items(notes, seen_ids)
