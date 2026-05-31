from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import httpx
from loguru import logger

from needradar.schemas.schemas import RawDiscussionItem


class BaseCrawler(ABC):
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "NeedRadar/0.1.0"},
                follow_redirects=True,
            )
        return self._client

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs,
    ) -> httpx.Response:
        client = await self._get_client()
        for attempt in range(max_retries):
            try:
                resp = await getattr(client, method)(url, **kwargs)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", base_delay * (2 ** attempt)))
                    logger.warning("rate_limited", url=url, retry_after=retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning("http_retry", url=url, status=e.response.status_code, attempt=attempt + 1, delay=delay)
                    await asyncio.sleep(delay)
                    continue
                raise
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning("timeout_retry", url=url, attempt=attempt + 1, delay=delay)
                    await asyncio.sleep(delay)
                    continue
                raise
        raise RuntimeError(f"Max retries exceeded for {url}")

    @abstractmethod
    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]: ...

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
