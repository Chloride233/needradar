from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from needradar.crawlers.factory import create_crawler

PHASE3_RAG_PLAN = {"github": 50, "stackoverflow": 50, "juejin": 50}
PHASE3_RAG_KEYWORDS = {
    "github": "AI tool",
    "stackoverflow": "AI tool",
    "juejin": "AI 工具",
}


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def collect_held_out_corpus(
    phase2_dataset_path: Path,
    plan: Mapping[str, int] = PHASE3_RAG_PLAN,
    keywords: Mapping[str, str] = PHASE3_RAG_KEYWORDS,
) -> list[dict]:
    phase2_records = _read_jsonl(phase2_dataset_path)
    excluded_by_platform: dict[str, set[str]] = {}
    for record in phase2_records:
        excluded_by_platform.setdefault(record["platform"], set()).add(record["source_url"])

    records = []
    collected_at = datetime.now(timezone.utc).isoformat()
    for platform, quota in plan.items():
        excluded_urls = excluded_by_platform.get(platform, set())
        crawler = create_crawler(platform)
        try:
            items = await crawler.crawl(keywords[platform], max_items=quota + len(excluded_urls))
        finally:
            await crawler.close()

        unique_items = {
            item.source_url: item for item in items if item.source_url and item.source_url not in excluded_urls
        }
        if len(unique_items) < quota:
            raise RuntimeError(f"{platform} returned {len(unique_items)} held-out items; required {quota}")

        for item in list(unique_items.values())[:quota]:
            record_id = hashlib.sha256(f"{platform}:{item.source_url}".encode()).hexdigest()[:16]
            records.append(
                {
                    "id": record_id,
                    "platform": platform,
                    "query": keywords[platform],
                    "source_url": item.source_url,
                    "title": item.title,
                    "content": item.content,
                    "tags": item.tags,
                    "collected_at": collected_at,
                }
            )
    return records


def write_corpus(
    records: list[dict],
    output_dir: Path,
    phase2_dataset_path: Path,
) -> tuple[Path, Path]:
    phase2_urls = {record["source_url"] for record in _read_jsonl(phase2_dataset_path)}
    corpus_urls = [record["source_url"] for record in records]
    overlap = phase2_urls & set(corpus_urls)
    if overlap:
        raise ValueError(f"corpus overlaps Phase 2 by {len(overlap)} URLs")
    if len(corpus_urls) != len(set(corpus_urls)):
        raise ValueError("corpus contains duplicate source URLs")

    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "rag-corpus.jsonl"
    manifest_path = output_dir / "rag-corpus-manifest.json"
    dataset_text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    counts: dict[str, int] = {}
    keywords: dict[str, str] = {}
    for record in records:
        platform = record["platform"]
        counts[platform] = counts.get(platform, 0) + 1
        keywords[platform] = record["query"]

    dataset_path.write_text(dataset_text, encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "sample_size": len(records),
                "platform_counts": counts,
                "sample_plan": counts,
                "keywords": keywords,
                "source_dataset_sha256": _sha256_file(phase2_dataset_path),
                "dataset_sha256": hashlib.sha256(dataset_text.encode()).hexdigest(),
                "phase2_url_overlap": 0,
                "author_fields_stored": False,
                "gold_fields_stored": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset_path, manifest_path


class Phase3CorpusRetriever:
    def __init__(self, corpus_path: Path, vector_store: Any | None = None) -> None:
        self._corpus_path = corpus_path
        self._records = _read_jsonl(corpus_path)
        self._corpus_sha256 = _sha256_file(corpus_path)
        self._vector_store = vector_store
        self._embedding_backend = self._detect_embedding_backend()
        backend_hash = hashlib.sha256(self._embedding_backend.encode()).hexdigest()[:8]
        self._table_name = f"phase3_rag_{self._corpus_sha256[:12]}_{backend_hash}"
        self._ready = False

    def _detect_embedding_backend(self) -> str:
        if self._vector_store is not None:
            return "injected"
        from needradar.vector.lancedb_store import _get_embedding_function

        model = _get_embedding_function()
        if model == "fallback":
            return "fallback-sha256-bow-384"
        return str(getattr(model, "model_name_or_path", type(model).__name__))

    def _get_vector_store(self):
        if self._vector_store is None:
            from needradar.vector.lancedb_store import LanceDBVectorStore

            self._vector_store = LanceDBVectorStore(table_name=self._table_name)
        return self._vector_store

    def get_provenance(self) -> dict[str, Any]:
        return {
            "corpus_sha256": self._corpus_sha256,
            "corpus_records": len(self._records),
            "table_name": self._table_name,
            "embedding_backend": self._embedding_backend,
        }

    async def _ensure_index(self) -> None:
        if self._ready:
            return
        vector_store = self._get_vector_store()
        count = await vector_store.count()
        if count == 0:
            await vector_store.add(
                ids=[record["id"] for record in self._records],
                documents=[f"{record['title']}\n\n{record['content']}" for record in self._records],
                metadatas=[
                    {
                        "source": record["source_url"],
                        "title": record["title"],
                        "platform": record["platform"],
                        "corpus_sha256": self._corpus_sha256,
                    }
                    for record in self._records
                ],
            )
        elif count != len(self._records):
            raise RuntimeError(f"frozen corpus index has {count} rows; expected {len(self._records)}")
        self._ready = True

    async def retrieve_context(
        self,
        query: str,
        n_results: int = 3,
        min_score: float = 0.2,
        max_chars: int = 1500,
    ) -> str:
        results = await self.retrieve(query, n_results=n_results)
        parts = []
        total_chars = 0
        for result in results:
            if result.score < min_score:
                continue
            metadata = result.metadata or {}
            header = (
                f"[来源: {metadata.get('platform', '')} | {metadata.get('title', '')} | {metadata.get('source', '')}]\n"
            )
            remaining = max_chars - total_chars - len(header)
            if remaining <= 0:
                break
            document = (result.document or "")[:remaining]
            if document:
                parts.append(header + document)
                total_chars += len(header) + len(document)
        if not parts:
            return ""
        return "## Held-out RAG context\n\n" + "\n\n---\n\n".join(parts)

    async def retrieve(self, query: str, n_results: int = 20) -> list[Any]:
        """Return structured frozen-corpus candidates for offline experiments."""
        await self._ensure_index()
        return await self._get_vector_store().query([query], n_results=n_results)

    async def retrieve_hybrid(self, query: str, n_results: int = 20) -> list[Any]:
        """Return hybrid dense and lexical candidates for rerank experiments."""
        await self._ensure_index()
        vector_store = self._get_vector_store()
        hybrid_query = getattr(vector_store, "hybrid_query", None)
        if not callable(hybrid_query):
            raise RuntimeError("frozen corpus vector store does not support hybrid recall")
        return await hybrid_query([query], n_results=n_results)
