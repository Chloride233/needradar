from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    id: str
    score: float
    metadata: dict | None = None
    document: str | None = None


class VectorStore(ABC):
    @abstractmethod
    async def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None: ...

    @abstractmethod
    async def query(
        self,
        query_texts: list[str],
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> None: ...

    @abstractmethod
    async def count(self) -> int: ...
