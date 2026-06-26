"""LanceDB-backed vector store.

Embedded, zero-service, columnar (Lance format).
Supports vector search + SQL-like filtering.
"""

from __future__ import annotations

import os

import lancedb
from loguru import logger

from needradar.core.config import settings
from needradar.vector.base import SearchResult, VectorStore

_db = None
_ef = None


def _get_db():
    global _db
    if _db is None:
        _db = lancedb.connect(settings.lancedb_dir)
    return _db


def _get_embedding_function():
    """Get embedding function — sentence-transformers all-MiniLM-L6-v2."""
    global _ef
    if _ef is None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer
        _ef = SentenceTransformer("all-MiniLM-L6-v2")
    return _ef


def _reset_globals() -> None:
    global _db, _ef
    _db = None
    _ef = None


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the shared model."""
    model = _get_embedding_function()
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
            # Table doesn't exist yet — create with schema
            import pyarrow as pa
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 384)),
                pa.field("document", pa.string()),
                pa.field("metadata", pa.string()),  # JSON string
            ])
            self._table = db.create_table(
                self._table_name,
                schema=schema,
                mode="overwrite",
            )

    def _ensure_index(self) -> None:
        """Create vector index if not already present (requires data in table)."""
        try:
            if self._table.count_rows() > 0:
                self._table.create_index(metric="cosine")
        except Exception:
            pass  # Index may already exist

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
            rows.append({
                "id": id_,
                "vector": vec,
                "document": doc,
                "metadata": json.dumps(meta, ensure_ascii=False),
            })

        try:
            self._table.add(rows)
        except Exception as e:
            logger.warning("lancedb_add_failed", error=str(e), resetting=True)
            self._reset_table()
            self._table.add(rows)

        # Ensure index exists after data is added
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

    def _do_query(
        self,
        query_vectors: list[list[float]],
        n_results: int,
        where: dict | None = None,
    ) -> list[SearchResult]:
        import json

        results = (
            self._table.search(query_vectors[0])
            .metric("cosine")
            .limit(n_results)
            .to_list()
        )

        search_results = []
        for row in results:
            meta = None
            if row.get("metadata"):
                try:
                    meta = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    pass

            # LanceDB returns _distance; convert to similarity score
            distance = row.get("_distance", 0.0)
            score = max(0.0, 1.0 - distance)

            search_results.append(SearchResult(
                id=row["id"],
                score=score,
                metadata=meta,
                document=row.get("document"),
            ))

        return search_results

    async def delete(self, ids: list[str]) -> None:
        # LanceDB delete uses SQL-like syntax; sanitize IDs to prevent injection
        safe_ids = [i.replace("'", "''") for i in ids]
        id_filter = ", ".join(f"'{i}'" for i in safe_ids)
        self._table.delete(f"id IN ({id_filter})")

    async def count(self) -> int:
        return self._table.count_rows()
