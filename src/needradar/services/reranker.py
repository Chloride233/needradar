from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx
from loguru import logger

RerankMode = Literal["none", "bge", "qwen3"]
MODEL_IDS: dict[RerankMode, str | None] = {
    "none": None,
    "bge": "BAAI/bge-reranker-v2-m3",
    "qwen3": "Qwen/Qwen3-Reranker-0.6B",
}
MAX_RECALL_CANDIDATES = 20
DEFAULT_TOP_K = 3


@dataclass(frozen=True)
class RerankCandidate:
    document_id: str
    text: str
    original_rank: int
    original_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RerankUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class RerankedDocument:
    document_id: str
    text: str
    original_rank: int
    original_score: float
    reranked_rank: int
    relevance_score: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RerankOutcome:
    items: list[RerankedDocument]
    provider: str
    requested_model_id: str | None
    returned_model_id: str | None
    request_id: str | None
    latency_ms: float
    usage: RerankUsage
    retry_count: int
    degraded: bool
    error_type: str | None = None
    error_reason: str | None = None


class RerankerError(RuntimeError):
    def __init__(self, message: str, *, error_type: str, retry_count: int = 0) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.retry_count = retry_count


def _content_hash(query: str, candidates: list[RerankCandidate]) -> str:
    payload = {
        "query": query,
        "documents": [candidate.text for candidate in candidates],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _retry_after_seconds(value: str | None, fallback: float) -> float:
    if not value:
        return fallback
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return fallback


class SiliconFlowReranker:
    def __init__(
        self,
        *,
        mode: RerankMode,
        api_key: str,
        base_url: str = "https://api.siliconflow.cn/v1",
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if mode not in MODEL_IDS:
            raise ValueError(f"unsupported rerank mode: {mode}")
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self.mode = mode
        self.model_id = MODEL_IDS[mode]
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    @classmethod
    def from_settings(cls, settings: Any) -> SiliconFlowReranker:
        return cls(
            mode=settings.rerank_mode,
            api_key=settings.siliconflow_api_key,
            base_url=settings.rerank_base_url,
            timeout_seconds=settings.rerank_timeout_seconds,
            max_attempts=settings.rerank_max_attempts,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def rerank(
        self,
        query: str,
        candidates: list[RerankCandidate],
        *,
        top_k: int = DEFAULT_TOP_K,
        relevance_threshold: float | None = None,
        fail_open: bool = True,
    ) -> RerankOutcome:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        prepared = self._prepare_candidates(candidates)
        if not prepared or self.mode == "none":
            return self._baseline(prepared, top_k=top_k)

        started = time.monotonic()
        try:
            if not self._api_key:
                raise RerankerError(
                    "SiliconFlow API key is not configured",
                    error_type="authentication",
                )
            return await self._request(
                query,
                prepared,
                top_k=top_k,
                relevance_threshold=relevance_threshold,
                started=started,
            )
        except RerankerError as error:
            latency_ms = round((time.monotonic() - started) * 1000, 3)
            logger.warning(
                "rerank_request_failed",
                request_id=None,
                model=self.model_id,
                candidate_count=len(prepared),
                latency_ms=latency_ms,
                status=error.error_type,
                retry_count=error.retry_count,
                content_hash=_content_hash(query, prepared),
            )
            if not fail_open:
                raise
            baseline = self._baseline(prepared, top_k=top_k)
            return RerankOutcome(
                items=baseline.items,
                provider="siliconflow",
                requested_model_id=self.model_id,
                returned_model_id=None,
                request_id=None,
                latency_ms=latency_ms,
                usage=RerankUsage(),
                retry_count=error.retry_count,
                degraded=True,
                error_type=error.error_type,
                error_reason=str(error)[:500],
            )

    @staticmethod
    def _prepare_candidates(candidates: list[RerankCandidate]) -> list[RerankCandidate]:
        ordered = sorted(enumerate(candidates), key=lambda pair: (pair[1].original_rank, pair[0]))
        seen_ids: set[str] = set()
        prepared = []
        for _, candidate in ordered:
            if not candidate.document_id or candidate.document_id in seen_ids:
                continue
            seen_ids.add(candidate.document_id)
            prepared.append(candidate)
            if len(prepared) == MAX_RECALL_CANDIDATES:
                break
        return prepared

    def _baseline(self, candidates: list[RerankCandidate], *, top_k: int) -> RerankOutcome:
        items = [
            RerankedDocument(
                document_id=candidate.document_id,
                text=candidate.text,
                original_rank=candidate.original_rank,
                original_score=candidate.original_score,
                reranked_rank=index,
                relevance_score=None,
                metadata=candidate.metadata,
            )
            for index, candidate in enumerate(candidates[:top_k], start=1)
        ]
        return RerankOutcome(
            items=items,
            provider="none" if self.mode == "none" else "siliconflow",
            requested_model_id=self.model_id,
            returned_model_id=None,
            request_id=None,
            latency_ms=0.0,
            usage=RerankUsage(),
            retry_count=0,
            degraded=False,
        )

    async def _request(
        self,
        query: str,
        candidates: list[RerankCandidate],
        *,
        top_k: int,
        relevance_threshold: float | None,
        started: float,
    ) -> RerankOutcome:
        request_top_k = min(top_k, len(candidates))
        payload = {
            "model": self.model_id,
            "query": query,
            "documents": [candidate.text for candidate in candidates],
            "return_documents": False,
            "top_n": request_top_k,
        }
        content_hash = _content_hash(query, candidates)
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._client.post(
                    f"{self._base_url}/rerank",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
            except httpx.TimeoutException as error:
                if attempt == self._max_attempts:
                    raise RerankerError(
                        str(error) or "rerank request timed out",
                        error_type="timeout",
                        retry_count=attempt - 1,
                    ) from error
                await self._sleep(0.25 * 2 ** (attempt - 1))
                continue
            except httpx.NetworkError as error:
                if attempt == self._max_attempts:
                    raise RerankerError(
                        str(error) or "rerank network error",
                        error_type="network",
                        retry_count=attempt - 1,
                    ) from error
                await self._sleep(0.25 * 2 ** (attempt - 1))
                continue

            if response.status_code == 429 or response.status_code == 408 or response.status_code >= 500:
                if response.status_code == 429:
                    error_type = "rate_limit"
                elif response.status_code == 408:
                    error_type = "timeout"
                else:
                    error_type = "server_error"
                if attempt == self._max_attempts:
                    raise RerankerError(
                        f"SiliconFlow rerank returned HTTP {response.status_code}",
                        error_type=error_type,
                        retry_count=attempt - 1,
                    )
                fallback = 0.25 * 2 ** (attempt - 1)
                await self._sleep(_retry_after_seconds(response.headers.get("Retry-After"), fallback))
                continue
            if 400 <= response.status_code < 500:
                raise RerankerError(
                    f"SiliconFlow rerank returned HTTP {response.status_code}",
                    error_type="client_error",
                    retry_count=attempt - 1,
                )

            outcome = self._parse_response(
                response,
                candidates,
                top_k=request_top_k,
                relevance_threshold=relevance_threshold,
                latency_ms=round((time.monotonic() - started) * 1000, 3),
                retry_count=attempt - 1,
            )
            logger.info(
                "rerank_request_succeeded",
                request_id=outcome.request_id,
                model=self.model_id,
                candidate_count=len(candidates),
                latency_ms=outcome.latency_ms,
                input_tokens=outcome.usage.input_tokens,
                output_tokens=outcome.usage.output_tokens,
                status="success",
                retry_count=outcome.retry_count,
                content_hash=content_hash,
            )
            return outcome
        raise AssertionError("unreachable")

    def _parse_response(
        self,
        response: httpx.Response,
        candidates: list[RerankCandidate],
        *,
        top_k: int,
        relevance_threshold: float | None,
        latency_ms: float,
        retry_count: int,
    ) -> RerankOutcome:
        try:
            body = response.json()
        except ValueError as error:
            raise RerankerError(
                "SiliconFlow rerank returned invalid JSON",
                error_type="invalid_response",
                retry_count=retry_count,
            ) from error
        returned_model_id = body.get("model")
        if returned_model_id is not None and returned_model_id != self.model_id:
            raise RerankerError(
                f"returned model {returned_model_id!r} does not match requested model",
                error_type="model_mismatch",
                retry_count=retry_count,
            )
        results = body.get("results")
        tokens = (body.get("meta") or {}).get("tokens")
        request_id = response.headers.get("x-siliconcloud-trace-id") or body.get("id")
        if (
            not isinstance(results, list)
            or not isinstance(tokens, dict)
            or "input_tokens" not in tokens
            or not request_id
        ):
            raise RerankerError(
                "SiliconFlow rerank response is missing results or token usage",
                error_type="invalid_response",
                retry_count=retry_count,
            )

        parsed = []
        seen_indexes: set[int] = set()
        for result in results:
            index = result.get("index") if isinstance(result, dict) else None
            score = result.get("relevance_score") if isinstance(result, dict) else None
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < len(candidates)
                or index in seen_indexes
                or not isinstance(score, (int, float))
            ):
                raise RerankerError(
                    "SiliconFlow rerank response contains an invalid result",
                    error_type="invalid_response",
                    retry_count=retry_count,
                )
            seen_indexes.add(index)
            parsed.append((float(score), index, candidates[index]))
        parsed.sort(key=lambda item: (-item[0], item[2].original_rank, item[1]))
        if relevance_threshold is not None:
            parsed = [item for item in parsed if item[0] >= relevance_threshold]
        parsed = parsed[:top_k]
        items = [
            RerankedDocument(
                document_id=candidate.document_id,
                text=candidate.text,
                original_rank=candidate.original_rank,
                original_score=candidate.original_score,
                reranked_rank=rank,
                relevance_score=score,
                metadata=candidate.metadata,
            )
            for rank, (score, _, candidate) in enumerate(parsed, start=1)
        ]
        input_tokens = int(tokens.get("input_tokens", 0))
        output_tokens = int(tokens.get("output_tokens", 0))
        return RerankOutcome(
            items=items,
            provider="siliconflow",
            requested_model_id=self.model_id,
            returned_model_id=returned_model_id,
            request_id=request_id,
            latency_ms=latency_ms,
            usage=RerankUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            retry_count=retry_count,
            degraded=False,
        )
