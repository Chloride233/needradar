from __future__ import annotations

import asyncio
import os

import chromadb
from chromadb.utils import embedding_functions
from loguru import logger

from needradar.core.config import settings
from needradar.vector.base import SearchResult, VectorStore

_client = None
_ef = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client


def _get_ef():
    global _ef
    if _ef is None:
        # Prevent network calls to HuggingFace — model must be pre-cached
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
        )
    return _ef


def _reset_globals() -> None:
    global _client, _ef
    _client = None
    _ef = None


class ChromaVectorStore(VectorStore):
    def __init__(self, collection_name: str = "requirements") -> None:
        self._collection_name = collection_name
        self._init_collection()

    def _init_collection(self) -> None:
        self._collection = _get_client().get_or_create_collection(
            name=self._collection_name,
            embedding_function=_get_ef(),
            metadata={"hnsw:space": "cosine"},
        )

    def _reset_collection(self) -> None:
        _reset_globals()
        self._init_collection()

    async def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        try:
            self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
        except Exception as e1:
            logger.warning("vector_add_failed", error=str(e1), retrying=True)
            # Light retry: just retry the operation once
            await asyncio.sleep(0.1)
            try:
                self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
                return
            except Exception as e2:
                logger.warning("vector_add_retry_failed", error=str(e2), resetting=True)
                # Heavy retry: reset client and retry
                self._reset_collection()
                try:
                    self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
                except Exception as e3:
                    logger.error("vector_add_reset_failed", error=str(e3))
                    raise

    async def query(
        self,
        query_texts: list[str],
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[SearchResult]:
        try:
            return self._do_query(query_texts, n_results, where)
        except Exception as e1:
            logger.warning("vector_query_failed", error=str(e1), retrying=True)
            # Light retry
            await asyncio.sleep(0.1)
            try:
                return self._do_query(query_texts, n_results, where)
            except Exception as e2:
                logger.warning("vector_query_retry_failed", error=str(e2), resetting=True)
                # Heavy retry: reset client
                try:
                    self._reset_collection()
                    return self._do_query(query_texts, n_results, where)
                except Exception as e3:
                    logger.error("vector_query_reset_failed", error=str(e3))
                    return []

    def _do_query(
        self,
        query_texts: list[str],
        n_results: int,
        where: dict | None = None,
    ) -> list[SearchResult]:
        results = self._collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where,
        )
        ids = results["ids"][0]
        distances = results["distances"][0]
        metas = results["metadatas"][0] if results["metadatas"] else [None] * len(ids)
        docs = results["documents"][0] if results["documents"] else [None] * len(ids)
        return [
            SearchResult(id=i, score=1 - d, metadata=m, document=doc)
            for i, d, m, doc in zip(ids, distances, metas, docs)
        ]

    async def delete(self, ids: list[str]) -> None:
        self._collection.delete(ids=ids)

    async def count(self) -> int:
        return self._collection.count()
