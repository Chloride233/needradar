"""RAG Retriever — semantic search over vault knowledge for LLM context enrichment.

Given a query (keyword or text), retrieves relevant chunks from the
vault_knowledge LanceDB collection and formats them for LLM injection.
"""

from __future__ import annotations

import hashlib

from loguru import logger

from needradar.core.config import settings
from needradar.services.reranker import RerankCandidate, SiliconFlowReranker


class RAGRetriever:
    """Retrieves relevant vault context for a given query."""

    def __init__(self, reranker: SiliconFlowReranker | None = None) -> None:
        self._vs = None
        self._reranker = reranker

    def _get_vs(self):
        if self._vs is None:
            from needradar.vector.lancedb_store import LanceDBVectorStore

            self._vs = LanceDBVectorStore(table_name="vault_knowledge")
        return self._vs

    async def retrieve(
        self,
        query: str,
        n_results: int = 5,
        min_score: float = 0.2,
        stage_filter: str | None = None,
    ) -> list[dict]:
        """Retrieve relevant vault chunks for a query.

        Args:
            query: Search text (keyword or natural language).
            n_results: Maximum results to return.
            min_score: Minimum similarity score (0-1).
            stage_filter: Optional stage filter (e.g., "02-需求池").

        Returns:
            List of {id, score, title, source, chunk, stage}.
        """
        try:
            vs = self._get_vs()
            recall_k = settings.rerank_recall_k if settings.rerank_mode != "none" else n_results
            if settings.rerank_mode == "none":
                results = await vs.query([query], n_results=recall_k)
            else:
                hybrid_query = getattr(vs, "hybrid_query", None)
                if not callable(hybrid_query):
                    raise RuntimeError("vector store does not support hybrid recall")
                results = await hybrid_query([query], n_results=recall_k)

            filtered = []
            for original_rank, r in enumerate(results, start=1):
                if r.score < min_score:
                    continue
                meta = r.metadata or {}
                if stage_filter and meta.get("stage") != stage_filter:
                    continue
                filtered.append(
                    {
                        "id": r.id,
                        "score": round(r.score, 3),
                        "title": meta.get("title", ""),
                        "source": meta.get("source", ""),
                        "chunk": r.document or "",
                        "stage": meta.get("stage", ""),
                        "_original_rank": original_rank,
                        "_original_score": float(r.score),
                        "_metadata": dict(meta),
                    }
                )

            if settings.rerank_mode == "none":
                return [{key: value for key, value in item.items() if not key.startswith("_")} for item in filtered]

            if self._reranker is None:
                self._reranker = SiliconFlowReranker.from_settings(settings)
            candidates = [
                RerankCandidate(
                    document_id=item["id"],
                    text=item["chunk"],
                    original_rank=item["_original_rank"],
                    original_score=item["_original_score"],
                    metadata=item["_metadata"],
                )
                for item in filtered
            ]
            outcome = await self._reranker.rerank(
                query,
                candidates,
                top_k=min(n_results, settings.rerank_top_k),
                relevance_threshold=settings.rerank_relevance_threshold,
                fail_open=True,
            )
            recall_degraded = any(
                item.metadata.get("recall", {}).get("mode") == "dense_fallback" for item in outcome.items
            )
            return [
                {
                    "id": item.document_id,
                    "score": item.original_score,
                    "title": item.metadata.get("title", ""),
                    "source": item.metadata.get("source", ""),
                    "chunk": item.text,
                    "stage": item.metadata.get("stage", ""),
                    "source_metadata": item.metadata,
                    "recall": item.metadata.get("recall"),
                    "original_rank": item.original_rank,
                    "original_score": item.original_score,
                    "reranked_rank": item.reranked_rank,
                    "relevance_score": item.relevance_score,
                    "rerank_provider": outcome.provider,
                    "requested_model_id": outcome.requested_model_id,
                    "returned_model_id": outcome.returned_model_id,
                    "rerank_request_id": outcome.request_id,
                    "rerank_latency_ms": outcome.latency_ms,
                    "rerank_token_usage": {
                        "input_tokens": outcome.usage.input_tokens,
                        "output_tokens": outcome.usage.output_tokens,
                        "total_tokens": outcome.usage.total_tokens,
                    },
                    "rerank_retry_count": outcome.retry_count,
                    "degraded": outcome.degraded or recall_degraded,
                    "recall_degraded": recall_degraded,
                    "rerank_error_type": outcome.error_type,
                    "rerank_error_reason": outcome.error_reason,
                }
                for item in outcome.items
            ]

        except Exception as e:
            logger.warning(
                "rag_retrieve_failed",
                query_hash=hashlib.sha256(query.encode()).hexdigest(),
                error=str(e),
            )
            return []

    async def retrieve_context(
        self,
        query: str,
        n_results: int = 5,
        min_score: float = 0.2,
        max_chars: int = 2000,
    ) -> str:
        """Retrieve and format context string for LLM prompt injection.

        Returns a formatted string ready to be appended to a system/user prompt.
        """
        results = await self.retrieve(query, n_results=n_results, min_score=min_score)
        if not results:
            return ""

        context_parts = []
        total_chars = 0
        for r in results:
            chunk_text = r["chunk"]
            if total_chars + len(chunk_text) > max_chars:
                break
            source = r["source"]
            title = r["title"]
            context_parts.append(f"[来源: {source} | {title}]\n{chunk_text}")
            total_chars += len(chunk_text)

        if not context_parts:
            return ""

        return "## 相关历史知识\n\n" + "\n\n---\n\n".join(context_parts)


# Singleton
_retriever: RAGRetriever | None = None


def get_retriever() -> RAGRetriever:
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever
