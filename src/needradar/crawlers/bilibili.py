from __future__ import annotations

import asyncio
import hashlib
import re
import time
import urllib.parse
from typing import Any

import httpx
from loguru import logger

from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem

SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
COMMENT_MAIN_URL = "https://api.bilibili.com/x/v2/reply/wbi/main"
COMMENT_REPLY_URL = "https://api.bilibili.com/x/v2/reply/reply"
VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
WBI_KEYS_URL = "https://api.bilibili.com/x/web-interface/nav"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}

# AI 召唤指令：用户呼叫机器人总结/转发，非真实需求讨论
_AI_SUMMON_RE = re.compile(
    r"^@?(?:MilkyAi|AI视频总结|AI全文总结|AI总结喵)\b",
    re.IGNORECASE,
)

MIN_CONTENT_LEN = 15

# WBI 签名混淆表
_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


def _get_mixin_key(img_key: str, sub_key: str) -> str:
    orig = img_key + sub_key
    return "".join(orig[i] for i in _MIXIN_KEY_ENC_TAB)[:32]


def wbi_sign(params: dict[str, Any], img_key: str, sub_key: str) -> dict[str, Any]:
    mixin_key = _get_mixin_key(img_key, sub_key)
    wts = int(time.time())
    params["wts"] = wts
    query = urllib.parse.urlencode(sorted(params.items()))
    params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params


async def fetch_wbi_keys(client: httpx.AsyncClient) -> tuple[str, str]:
    resp = await client.get(WBI_KEYS_URL)
    data = resp.json().get("data", {})
    wbi = data.get("wbi_img", {})
    img_key = wbi.get("img_url", "").rsplit("/", 1)[-1].split(".")[0]
    sub_key = wbi.get("sub_url", "").rsplit("/", 1)[-1].split(".")[0]
    return img_key, sub_key


class BilibiliCrawler(BaseCrawler):
    PLATFORM = "bilibili"

    def __init__(self) -> None:
        super().__init__()
        self._img_key: str | None = None
        self._sub_key: str | None = None
        self._keys_ts: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=HEADERS,
                follow_redirects=True,
                cookies=httpx.Cookies(),
            )
        return self._client

    async def _init_session(self) -> None:
        client = await self._get_client()
        try:
            await client.get("https://www.bilibili.com")
        except Exception:
            pass

    async def _ensure_wbi_keys(self) -> tuple[str, str]:
        # Cache keys for 10 minutes
        if self._img_key and self._sub_key and (time.time() - self._keys_ts < 600):
            return self._img_key, self._sub_key
        client = await self._get_client()
        self._img_key, self._sub_key = await fetch_wbi_keys(client)
        self._keys_ts = time.time()
        logger.debug("wbi_keys_refreshed", img_key=self._img_key)
        return self._img_key, self._sub_key

    async def _wbi_get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        img_key, sub_key = await self._ensure_wbi_keys()
        signed = wbi_sign(params.copy(), img_key, sub_key)
        return await self._request_with_retry("get", url, params=signed)

    # ── Public API ──

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        """Search videos by keyword, then extract comments."""
        await self._init_session()

        items: list[RawDiscussionItem] = []
        seen_oids: set[int] = set()

        for page in range(1, 6):
            if len(items) >= max_items:
                break

            resp = await self._request_with_retry(
                "get", SEARCH_URL,
                params={"keyword": keyword, "search_type": "video", "page": page, "page_size": 30},
            )
            data = resp.json()
            if data.get("code") != 0:
                logger.warning("bilibili_search_error", code=data.get("code"), msg=data.get("message"))
                break

            results = data.get("data", {}).get("result", [])
            if not results:
                break

            logger.info("bilibili_search_page", keyword=keyword, page=page, results=len(results))

            for video in results:
                if len(items) >= max_items:
                    break

                aid = video.get("aid")
                if not aid or aid in seen_oids:
                    continue
                seen_oids.add(aid)

                title = self._clean_title(video.get("title", ""))
                author = video.get("author", "")
                bvid = video.get("bvid", "")
                video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""

                new_items = await self._collect_from_video(aid, title, author, video_url, keyword, max_items - len(items))
                items.extend(new_items)

            await asyncio.sleep(1.0)

        logger.info("bilibili_crawl_done", keyword=keyword, total=len(items))
        return items[:max_items]

    async def crawl_by_bvid(self, bvid: str, max_items: int = 100) -> list[RawDiscussionItem]:
        """Fetch all comments from a specific video by BV号."""
        await self._init_session()

        resp = await self._request_with_retry("get", VIEW_URL, params={"bvid": bvid})
        info = resp.json().get("data", {})
        if not info:
            logger.warning("bilibili_bvid_not_found", bvid=bvid)
            return []

        aid = info["aid"]
        title = info.get("title", "")
        author = info.get("owner", {}).get("name", "")
        video_url = f"https://www.bilibili.com/video/{bvid}"
        expected_total = info.get("stat", {}).get("reply", 0)

        items = await self._collect_from_video(aid, title, author, video_url, bvid, max_items)
        got = len(items)
        if expected_total > 0 and got < expected_total * 0.5:
            logger.warning(
                "bilibili_comment_gap",
                bvid=bvid,
                expected=expected_total,
                got=got,
                hint="Consider using a logged-in session for more comments",
            )

        logger.info("bilibili_bvid_crawl_done", bvid=bvid, total=got)
        return items[:max_items]

    # ── Internal ──

    async def _collect_from_video(
        self,
        aid: int,
        title: str,
        author: str,
        video_url: str,
        tag: str,
        limit: int,
    ) -> list[RawDiscussionItem]:
        items: list[RawDiscussionItem] = []
        comments = await self._fetch_comments(aid, max_pages=3)

        if not comments:
            return items

        for c in comments:
            if len(items) >= limit:
                break

            msg = c["content"]
            uname = c["author"]
            if self._should_skip(msg):
                continue

            items.append(RawDiscussionItem(
                platform="bilibili",
                source_url=video_url,
                title=f"[B站评论] {title}",
                content=msg,
                author=uname,
                tags=[tag],
            ))

            # Collect full sub-replies via dedicated API
            if c.get("rcount", 0) > 0 and len(items) < limit:
                sub_replies = await self._fetch_sub_replies(aid, c["rpid"], limit=max(3, c["rcount"]))
                for sub in sub_replies:
                    if len(items) >= limit:
                        break
                    sub_msg = sub["content"]
                    if self._should_skip(sub_msg):
                        continue
                    items.append(RawDiscussionItem(
                        platform="bilibili",
                        source_url=video_url,
                        title=f"[B站子回复] {title}",
                        content=sub_msg,
                        author=sub["author"],
                        tags=[tag],
                    ))

        return items

    async def _fetch_comments(self, oid: int, max_pages: int = 3) -> list[dict[str, Any]]:
        """Fetch comments using WBI-signed cursor-based pagination."""
        comments: list[dict[str, Any]] = []
        next_offset: str | None = None

        for page in range(max_pages):
            params: dict[str, Any] = {"type": 1, "oid": oid, "mode": 3}
            if next_offset:
                params["pagination_str"] = '{"offset":' + next_offset + '}'
            else:
                params["pagination_str"] = ""

            try:
                resp = await self._wbi_get(COMMENT_MAIN_URL, params)
                data = resp.json()

                if data.get("code") == -403:
                    # WBI keys expired, refresh once
                    self._img_key = None
                    self._sub_key = None
                    resp = await self._wbi_get(COMMENT_MAIN_URL, params)
                    data = resp.json()

                if data.get("code") != 0:
                    logger.debug("bilibili_comment_error", oid=oid, code=data.get("code"), msg=data.get("message"))
                    break

                replies_data = data.get("data", {})

                # Collect hot comments from first page
                if page == 0:
                    for hot in replies_data.get("hots", []) or []:
                        comments.append(self._parse_reply(hot))

                for reply in replies_data.get("replies", []) or []:
                    comments.append(self._parse_reply(reply))

                # Check pagination
                cursor = replies_data.get("cursor", {})
                if cursor.get("is_end", True):
                    break
                next_offset_raw = (cursor.get("pagination_reply") or {}).get("next_offset")
                if not next_offset_raw:
                    break
                # next_offset is already a JSON string value
                next_offset = str(next_offset_raw)

            except Exception as e:
                logger.debug("bilibili_comment_fetch_failed", oid=oid, error=str(e))
                break

        return comments

    async def _fetch_sub_replies(self, oid: int, root: int, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch sub-replies for a specific root comment via /x/v2/reply/reply."""
        results: list[dict[str, Any]] = []
        page = 1

        while len(results) < limit:
            try:
                resp = await self._request_with_retry(
                    "get", COMMENT_REPLY_URL,
                    params={"type": 1, "oid": oid, "root": root, "pn": page, "ps": 20},
                )
                data = resp.json()
                if data.get("code") != 0:
                    break

                replies = (data.get("data", {}) or {}).get("replies", []) or []
                if not replies:
                    break

                for r in replies:
                    results.append(self._parse_reply(r))
                    if len(results) >= limit:
                        break

                page += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug("bilibili_sub_reply_failed", oid=oid, root=root, error=str(e))
                break

        return results

    @staticmethod
    def _parse_reply(reply: dict[str, Any]) -> dict[str, Any]:
        content = (reply.get("content", {}) or {}).get("message", "")
        author = (reply.get("member", {}) or {}).get("uname", "")
        return {
            "content": content,
            "author": author,
            "rpid": reply.get("rpid", 0),
            "like": reply.get("like", 0),
            "rcount": reply.get("rcount", 0),
            "ctime": reply.get("ctime", 0),
        }

    @staticmethod
    def _should_skip(msg: str) -> bool:
        if len(msg) < MIN_CONTENT_LEN:
            return True
        if _AI_SUMMON_RE.match(msg.replace(" ", "")):
            return True
        return False

    @staticmethod
    def _clean_title(raw: str) -> str:
        return raw.replace('<em class="keyword">', "").replace("</em>", "")
