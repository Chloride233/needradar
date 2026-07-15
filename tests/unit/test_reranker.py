from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from needradar.services.reranker import (
    RerankCandidate,
    RerankerError,
    SiliconFlowReranker,
)


def _candidates(count: int = 4) -> list[RerankCandidate]:
    return [
        RerankCandidate(
            document_id=f"doc-{index}",
            text=f"document {index}",
            original_rank=index + 1,
            original_score=1.0 - index / 10,
            metadata={"source": f"source-{index}"},
        )
        for index in range(count)
    ]


def _response(
    results: list[dict] | None = None,
    *,
    model: str | None = None,
) -> dict:
    body = {
        "id": "rerank-response-id",
        "results": results
        or [
            {"index": 2, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.7},
            {"index": 1, "relevance_score": 0.2},
        ],
        "meta": {"tokens": {"input_tokens": 42, "output_tokens": 0}},
    }
    if model:
        body["model"] = model
    return body


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_success_maps_indexes_and_records_request_metadata():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(__import__("json").loads(request.content))
        return httpx.Response(
            200,
            json=_response(),
            headers={"x-siliconcloud-trace-id": "trace-id"},
        )

    reranker = SiliconFlowReranker(
        mode="bge",
        api_key="test-key",
        client=_client(handler),
    )
    outcome = await reranker.rerank("query", _candidates(), top_k=2, fail_open=False)

    assert captured == {
        "model": "BAAI/bge-reranker-v2-m3",
        "query": "query",
        "documents": ["document 0", "document 1", "document 2", "document 3"],
        "return_documents": False,
        "top_n": 2,
    }
    assert [item.document_id for item in outcome.items] == ["doc-2", "doc-0"]
    assert [item.reranked_rank for item in outcome.items] == [1, 2]
    assert outcome.request_id == "trace-id"
    assert outcome.usage.input_tokens == 42
    assert outcome.usage.total_tokens == 42
    assert outcome.degraded is False


@pytest.mark.asyncio
async def test_empty_candidates_and_none_mode_do_not_call_provider():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    client = _client(handler)
    enabled = SiliconFlowReranker(mode="qwen3", api_key="test-key", client=client)
    empty = await enabled.rerank("query", [], fail_open=False)
    disabled = SiliconFlowReranker(mode="none", api_key="", client=client)
    baseline = await disabled.rerank("query", _candidates(2), top_k=3)

    assert empty.items == []
    assert [item.document_id for item in baseline.items] == ["doc-0", "doc-1"]
    assert calls == 0


@pytest.mark.asyncio
async def test_ties_and_duplicate_ids_have_stable_behavior():
    candidates = _candidates(3)
    candidates.append(
        RerankCandidate(
            document_id="doc-1",
            text="duplicate",
            original_rank=4,
            original_score=0.1,
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_response(
                [
                    {"index": 1, "relevance_score": 0.5},
                    {"index": 0, "relevance_score": 0.5},
                    {"index": 2, "relevance_score": 0.1},
                ]
            ),
        )

    outcome = await SiliconFlowReranker(mode="bge", api_key="test-key", client=_client(handler)).rerank(
        "query", candidates, top_k=3, fail_open=False
    )

    assert [item.document_id for item in outcome.items] == ["doc-0", "doc-1", "doc-2"]
    assert [item.original_rank for item in outcome.items] == [1, 2, 3]


@pytest.mark.asyncio
async def test_mixed_transient_failures_stop_after_three_total_attempts():
    events: list[str] = []
    responses: list[object] = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(503),
        httpx.ReadTimeout("timed out"),
        httpx.Response(200, json=_response()),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        events.append(type(response).__name__)
        if isinstance(response, Exception):
            raise response
        return response

    async def no_sleep(delay: float) -> None:
        assert delay >= 0

    reranker = SiliconFlowReranker(
        mode="bge",
        api_key="test-key",
        client=_client(handler),
        max_attempts=3,
        sleep=no_sleep,
    )

    with pytest.raises(RerankerError, match="timed out"):
        await reranker.rerank("query", _candidates(), fail_open=False)
    assert len(events) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_response",
    [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(503),
        httpx.ReadTimeout("timed out"),
    ],
)
async def test_each_transient_failure_retries_then_succeeds(first_response):
    responses = [first_response, httpx.Response(200, json=_response())]
    delays = []

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    outcome = await SiliconFlowReranker(
        mode="bge",
        api_key="test-key",
        client=_client(handler),
        max_attempts=3,
        sleep=record_sleep,
    ).rerank("query", _candidates(), fail_open=False)

    assert outcome.retry_count == 1
    assert len(delays) == 1


@pytest.mark.asyncio
async def test_non_transient_4xx_is_not_retried():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"message": "bad request"})

    reranker = SiliconFlowReranker(
        mode="qwen3",
        api_key="test-key",
        client=_client(handler),
        max_attempts=3,
    )
    with pytest.raises(RerankerError) as raised:
        await reranker.rerank("query", _candidates(), fail_open=False)

    assert raised.value.error_type == "client_error"
    assert calls == 1


@pytest.mark.asyncio
async def test_retry_exhaustion_fails_open_or_closed_explicitly():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "unavailable"})

    async def no_sleep(delay: float) -> None:
        pass

    reranker = SiliconFlowReranker(
        mode="bge",
        api_key="test-key",
        client=_client(handler),
        max_attempts=3,
        sleep=no_sleep,
    )
    degraded = await reranker.rerank("query", _candidates(), top_k=3, fail_open=True)

    assert degraded.degraded is True
    assert degraded.error_type == "server_error"
    assert degraded.retry_count == 2
    assert [item.document_id for item in degraded.items] == ["doc-0", "doc-1", "doc-2"]

    with pytest.raises(RerankerError):
        await reranker.rerank("query", _candidates(), fail_open=False)


@pytest.mark.asyncio
async def test_model_mismatch_and_missing_usage_are_invalid_responses():
    bodies = [
        _response(model="unexpected/model"),
        {"id": "response", "results": [{"index": 0, "relevance_score": 0.5}]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=bodies.pop(0))

    reranker = SiliconFlowReranker(mode="bge", api_key="test-key", client=_client(handler))
    with pytest.raises(RerankerError) as mismatch:
        await reranker.rerank("query", _candidates(1), fail_open=False)
    assert mismatch.value.error_type == "model_mismatch"

    with pytest.raises(RerankerError) as missing_usage:
        await reranker.rerank("query", _candidates(1), fail_open=False)
    assert missing_usage.value.error_type == "invalid_response"
