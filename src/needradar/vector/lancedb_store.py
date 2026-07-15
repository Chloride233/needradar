"""LanceDB-backed vector store.

Embedded, zero-service, columnar (Lance format).
Supports vector search and SQL-like filtering.
"""

from __future__ import annotations

import hashlib
import os

import lancedb
from lancedb.index import FTS
from loguru import logger

from needradar.core.config import settings
from needradar.vector.base import SearchResult, VectorStore

_db = None
_ef = None
_warned_fallback = False


def _get_db():
    global _db
    if _db is None:
        _db = lancedb.connect(settings.lancedb_dir)
    return _db


def _get_embedding_function():
    """Get the shared embedding model or a lightweight fallback."""
    global _ef, _warned_fallback
    if _ef is None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        try:
            from sentence_transformers import SentenceTransformer

            _ef = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            if not _warned_fallback:
                logger.warning("sentence_transformers_missing_using_fallback_embeddings")
                _warned_fallback = True
            _ef = "fallback"
    return _ef


def _reset_globals() -> None:
    global _db, _ef, _warned_fallback
    _db = None
    _ef = None
    _warned_fallback = False


def _fallback_embed(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * 384
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % len(vector)
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5
        if norm:
            vector = [value / norm for value in vector]
        vectors.append(vector)
    return vectors


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the shared model."""
    model = _get_embedding_function()
    if model == "fallback":
        return _fallback_embed(texts)
    return model.encode(texts, show_progress_bar=False).tolist()


class LanceDBVectorStore(VectorStore):
    def __init__(self, table_name: str = "requirements") -> None:
        self._table_name = table_name
        self._init_table()

    def _init_table(self) -> None:
        db = _get_db()
        try:
            self._table = db.open_table(self._table_name)
        except Exception:
            import pyarrow as pa

            schema = pa.schema(
                [
                    pa.field("id", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), 384)),
                    pa.field("document", pa.string()),
                    pa.field("metadata", pa.string()),
                ]
            )
            self._table = db.create_table(
                self._table_name,
                schema=schema,
                mode="overwrite",
            )

    def _ensure_index(self) -> None:
        try:
            if self._table.count_rows() > 0:
                self._table.create_index(metric="cosine")
        except Exception:
            pass

    def _ensure_fts_index(self) -> None:
        if self._table.count_rows() == 0:
            return
        indexes = self._table.list_indices()
        if any(index.index_type == "FTS" and "document" in index.columns for index in indexes):
            return
        self._table.create_index(
            "document",
            config=FTS(
                base_tokenizer="ngram",
                ngram_min_length=2,
                ngram_max_length=3,
                stem=False,
                remove_stop_words=False,
            ),
        )

    def _reset_table(self) -> None:
        _reset_globals()
        self._init_table()

    async def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        import json

        vectors = _embed(documents)
        rows = []
        for i, (id_, doc, vec) in enumerate(zip(ids, documents, vectors)):
            meta = (metadatas or [{}] * len(ids))[i]
            rows.append(
                {
                    "id": id_,
                    "vector": vec,
                    "document": doc,
                    "metadata": json.dumps(meta, ensure_ascii=False),
                }
            )

        try:
            self._table.add(rows)
        except Exception as e:
            logger.warning("lancedb_add_failed", error=str(e), resetting=True)
            self._reset_table()
            self._table.add(rows)

        self._ensure_index()

    async def query(
        self,
        query_texts: list[str],
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[SearchResult]:
        query_vectors = _embed(query_texts)
        try:
            return self._do_query(query_vectors, n_results, where)
        except Exception as e:
            logger.warning("lancedb_query_failed", error=str(e), resetting=True)
            try:
                self._reset_table()
                return self._do_query(query_vectors, n_results, where)
            except Exception as e2:
                logger.error("lancedb_query_reset_failed", error=str(e2))
                return []

    async def hybrid_query(
        self,
        query_texts: list[str],
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[SearchResult]:
        """Fuse independent dense and full-text recall with deterministic RRF."""
        if not query_texts or not query_texts[0].strip() or n_results <= 0:
            return []
        fetch_k = max(n_results * 3, n_results)
        dense_results = await self.query(query_texts, n_results=fetch_k, where=where)
        try:
            self._ensure_fts_index()
            lexical_rows = (
                self._table.search(query_texts[0], query_type="fts", fts_columns="document").limit(fetch_k).to_list()
            )
            lexical_results = self._rows_to_results(lexical_rows, score_key="_score")
        except Exception as error:
            logger.warning("lancedb_fts_query_failed", error=str(error), fallback="dense")
            return [self._with_recall_metadata(item, mode="dense_fallback") for item in dense_results[:n_results]]
        return self._fuse_results(dense_results, lexical_results, n_results=n_results)

    def _do_query(
        self,
        query_vectors: list[list[float]],
        n_results: int,
        where: dict | None = None,
    ) -> list[SearchResult]:
        results = self._table.search(query_vectors[0]).metric("cosine").limit(n_results).to_list()

        return self._rows_to_results(results, score_key="_distance", distance=True)

    @staticmethod
    def _rows_to_results(
        rows: list[dict],
        *,
        score_key: str,
        distance: bool = False,
    ) -> list[SearchResult]:
        import json

        search_results = []
        for row in rows:
            meta = None
            if row.get("metadata"):
                try:
                    meta = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    pass

            raw_score = float(row.get(score_key, 0.0))
            score = max(0.0, 1.0 - raw_score) if distance else raw_score

            search_results.append(
                SearchResult(
                    id=row["id"],
                    score=score,
                    metadata=meta,
                    document=row.get("document"),
                )
            )

        return search_results

    @staticmethod
    def _with_recall_metadata(
        result: SearchResult,
        *,
        score: float | None = None,
        **recall: object,
    ) -> SearchResult:
        metadata = dict(result.metadata or {})
        metadata["recall"] = recall
        return SearchResult(
            id=result.id,
            score=result.score if score is None else score,
            metadata=metadata,
            document=result.document,
        )

    @classmethod
    def _fuse_results(
        cls,
        dense_results: list[SearchResult],
        lexical_results: list[SearchResult],
        *,
        n_results: int,
        rrf_k: int = 60,
    ) -> list[SearchResult]:
        candidates: dict[str, dict] = {}
        for recall_name, results in (("dense", dense_results), ("lexical", lexical_results)):
            for rank, result in enumerate(results, start=1):
                entry = candidates.setdefault(
                    result.id,
                    {
                        "result": result,
                        "rrf_score": 0.0,
                        "best_rank": rank,
                        "recall": {"mode": "hybrid_rrf", "rrf_k": rrf_k},
                    },
                )
                entry["rrf_score"] += 1.0 / (rrf_k + rank)
                entry["best_rank"] = min(entry["best_rank"], rank)
                entry["recall"][f"{recall_name}_rank"] = rank
                entry["recall"][f"{recall_name}_score"] = result.score

        max_rrf_score = 2.0 / (rrf_k + 1)
        ordered = sorted(
            candidates.values(),
            key=lambda entry: (-entry["rrf_score"], entry["best_rank"], entry["result"].id),
        )[:n_results]
        fused = []
        for entry in ordered:
            result = entry["result"]
            normalized_score = entry["rrf_score"] / max_rrf_score
            recall = {**entry["recall"], "rrf_score": normalized_score}
            fused.append(cls._with_recall_metadata(result, score=normalized_score, **recall))
        return fused

    async def delete(self, ids: list[str]) -> None:
        safe_ids = [i.replace("'", "''") for i in ids]
        id_filter = ", ".join(f"'{i}'" for i in safe_ids)
        self._table.delete(f"id IN ({id_filter})")

    async def count(self) -> int:
        return self._table.count_rows()
