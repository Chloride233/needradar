"""RAG Retriever — semantic search over vault knowledge for LLM context enrichment.

Given a query (keyword or text), retrieves relevant chunks from the
vault_knowledge LanceDB collection and formats them for LLM injection.
"""

from __future__ import annotations

from loguru import logger


class RAGRetriever:
    """Retrieves relevant vault context for a given query."""

    def __init__(self) -> None:
        self._vs = None

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
            results = await vs.query([query], n_results=n_results)

            filtered = []
            for r in results:
                if r.score < min_score:
                    continue
                meta = r.metadata or {}
                if stage_filter and meta.get("stage") != stage_filter:
                    continue
                filtered.append({
                    "id": r.id,
                    "score": round(r.score, 3),
                    "title": meta.get("title", ""),
                    "source": meta.get("source", ""),
                    "chunk": r.document or "",
                    "stage": meta.get("stage", ""),
                })

            return filtered
        except Exception as e:
            logger.warning("rag_retrieve_failed", query=query[:50], error=str(e))
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
