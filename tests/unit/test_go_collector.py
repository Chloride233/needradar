from __future__ import annotations

import json

import httpx
import pytest

from needradar.services.go_collector import GoCollectorClient, GoCollectorError


@pytest.mark.asyncio
async def test_collect_creates_polls_and_converts_items():
    polls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal polls
        if request.method == "POST" and request.url.path == "/v1/tasks":
            payload = json.loads(request.content)
            assert payload["task_ids"] == {"github": 41}
            return httpx.Response(201, json={"items": [{"id": 41, "status": "pending"}]})
        if request.method == "GET" and request.url.path == "/v1/tasks/41":
            polls += 1
            if polls == 1:
                return httpx.Response(200, json={"id": 41, "status": "running"})
            return httpx.Response(
                200,
                json={
                    "id": 41,
                    "status": "completed",
                    "attempts": 1,
                    "items": [
                        {
                            "platform": "github",
                            "source_url": "https://github.test/41",
                            "title": "Context",
                            "content": "Details",
                            "author": "dev",
                            "tags": ["go"],
                        }
                    ],
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GoCollectorClient(
            "http://collector.test", timeout_seconds=1, poll_interval_seconds=0, client=http_client
        )
        items, attempts = await client.collect("context", "github", 41)

    assert attempts == 1
    assert len(items) == 1
    assert items[0].source_url == "https://github.test/41"


@pytest.mark.asyncio
async def test_collect_retries_existing_failed_task_with_same_id():
    actions: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        actions.append(f"{request.method} {request.url.path}")
        if request.method == "POST" and request.url.path == "/v1/tasks":
            return httpx.Response(409, json={"error": "task 77 already exists"})
        if request.method == "GET" and request.url.path == "/v1/tasks/77":
            return httpx.Response(
                200,
                json={
                    "id": 77,
                    "keyword": "context",
                    "platform": "github",
                    "status": "failed",
                    "error_message": "timeout",
                },
            )
        if request.method == "POST" and request.url.path == "/v1/tasks/77/retry":
            return httpx.Response(200, json={"id": 77, "status": "completed", "attempts": 2, "items": []})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GoCollectorClient(
            "http://collector.test", timeout_seconds=1, poll_interval_seconds=0, client=http_client
        )
        items, attempts = await client.collect("context", "github", 77)

    assert items == []
    assert attempts == 2
    assert "POST /v1/tasks/77/retry" in actions


@pytest.mark.asyncio
async def test_collect_rejects_conflicting_task_from_different_request():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/tasks":
            return httpx.Response(409, json={"error": "task 77 already exists"})
        if request.method == "GET" and request.url.path == "/v1/tasks/77":
            return httpx.Response(
                200,
                json={"id": 77, "keyword": "different", "platform": "github", "status": "completed", "items": []},
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GoCollectorClient(
            "http://collector.test", timeout_seconds=1, poll_interval_seconds=0, client=http_client
        )
        with pytest.raises(GoCollectorError, match="belongs to a different request"):
            await client.collect("context", "github", 77)


@pytest.mark.asyncio
async def test_collect_raises_for_failed_task():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"items": [{"id": 5, "status": "failed", "error_message": "bad"}]})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GoCollectorClient(
            "http://collector.test", timeout_seconds=1, poll_interval_seconds=0, client=http_client
        )
        with pytest.raises(GoCollectorError, match="task 5 failed: bad"):
            await client.collect("context", "github", 5)
