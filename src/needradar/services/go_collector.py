from __future__ import annotations

import asyncio
from typing import Any

import httpx

from needradar.schemas.schemas import RawDiscussionItem


class GoCollectorError(RuntimeError):
    pass


class GoCollectorClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=min(timeout_seconds, 30.0))

    async def collect(
        self,
        keyword: str,
        platform: str,
        task_id: int,
        *,
        max_items: int = 100,
    ) -> tuple[list[RawDiscussionItem], int]:
        try:
            response = await self._client.post(
                f"{self._base_url}/v1/tasks",
                json={
                    "keyword": keyword,
                    "platforms": [platform],
                    "max_items": max_items,
                    "task_ids": {platform: task_id},
                },
            )
            if response.status_code == httpx.codes.CONFLICT:
                task = await self._get_task(task_id)
                if task.get("keyword") != keyword or task.get("platform") != platform:
                    raise GoCollectorError(f"Go collector task {task_id} belongs to a different request")
                if task.get("status") == "failed":
                    task = await self._post_task_action(task_id, "retry")
            else:
                response.raise_for_status()
                payload = response.json()
                task = payload["items"][0]

            deadline = asyncio.get_running_loop().time() + self._timeout_seconds
            while task.get("status") not in {"completed", "failed"}:
                if asyncio.get_running_loop().time() >= deadline:
                    raise GoCollectorError(f"Go collector task {task_id} timed out")
                await asyncio.sleep(self._poll_interval_seconds)
                task = await self._get_task(task_id)

            if task.get("status") == "failed":
                message = task.get("error_message") or "collection failed"
                raise GoCollectorError(f"Go collector task {task_id} failed: {message}")
            items = [RawDiscussionItem.model_validate(item) for item in task.get("items", [])]
            return items, int(task.get("attempts", 1))
        except GoCollectorError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise GoCollectorError(f"Go collector request failed: {error}") from error

    async def _get_task(self, task_id: int) -> dict[str, Any]:
        response = await self._client.get(f"{self._base_url}/v1/tasks/{task_id}")
        response.raise_for_status()
        return response.json()

    async def _post_task_action(self, task_id: int, action: str) -> dict[str, Any]:
        response = await self._client.post(f"{self._base_url}/v1/tasks/{task_id}/{action}")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
