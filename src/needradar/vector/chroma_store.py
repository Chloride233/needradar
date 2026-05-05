from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions

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
        _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
        )
    return _ef


class ChromaVectorStore(VectorStore):
    def __init__(self, collection_name: str = "requirements") -> None:
        self._collection = _get_client().get_or_create_collection(
            name=collection_name,
            embedding_function=_get_ef(),
            metadata={"hnsw:space": "cosine"},
        )

    async def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    async def query(
        self,
        query_texts: list[str],
        n_results: int = 10,
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
