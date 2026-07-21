from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from needradar.schemas.schemas import RawDiscussionItem
from needradar.services.phase3_corpus import (
    Phase3CorpusRetriever,
    collect_held_out_corpus,
    write_corpus,
)


def _item(platform: str, index: int) -> RawDiscussionItem:
    return RawDiscussionItem(
        platform=platform,
        source_url=f"https://example.test/{platform}/{index}",
        title=f"Title {index}",
        content=f"Discussion body {index} with enough detail for retrieval.",
        author="not persisted",
        tags=["ai"],
    )


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_collect_corpus_excludes_phase2_urls_and_requires_each_quota(tmp_path):
    phase2 = tmp_path / "phase2.jsonl"
    _write_jsonl(
        phase2,
        [
            {
                "id": "old",
                "platform": "github",
                "source_url": "https://example.test/github/0",
            }
        ],
    )
    crawler = AsyncMock()
    crawler.crawl.return_value = [_item("github", index) for index in range(3)]

    with patch("needradar.services.phase3_corpus.create_crawler", return_value=crawler):
        records = await collect_held_out_corpus(
            phase2,
            plan={"github": 2},
            keywords={"github": "AI tool"},
        )

    assert [record["source_url"] for record in records] == [
        "https://example.test/github/1",
        "https://example.test/github/2",
    ]
    assert all("author" not in record for record in records)
    crawler.crawl.assert_awaited_once_with("AI tool", max_items=3)
    crawler.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_collect_corpus_rejects_shortfall_after_exclusion(tmp_path):
    phase2 = tmp_path / "phase2.jsonl"
    _write_jsonl(
        phase2,
        [{"id": "old", "platform": "github", "source_url": "https://example.test/github/0"}],
    )
    crawler = AsyncMock()
    crawler.crawl.return_value = [_item("github", 0), _item("github", 1)]

    with patch("needradar.services.phase3_corpus.create_crawler", return_value=crawler):
        with pytest.raises(RuntimeError, match="returned 1 held-out items; required 2"):
            await collect_held_out_corpus(
                phase2,
                plan={"github": 2},
                keywords={"github": "AI tool"},
            )


def test_write_corpus_records_source_and_dataset_hashes(tmp_path):
    phase2 = tmp_path / "phase2.jsonl"
    phase2.write_text(
        '{"id":"old","source_url":"https://example.test/github/0"}\n',
        encoding="utf-8",
    )
    records = [
        {
            "id": "new",
            "platform": "github",
            "query": "AI tool",
            "source_url": "https://example.test/github/1",
            "title": "Title",
            "content": "Content",
            "tags": [],
            "collected_at": "2026-07-13T00:00:00+00:00",
        }
    ]

    dataset_path, manifest_path = write_corpus(records, tmp_path / "output", phase2)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert dataset_path.name == "rag-corpus.jsonl"
    assert manifest["sample_size"] == 1
    assert manifest["phase2_url_overlap"] == 0
    assert len(manifest["source_dataset_sha256"]) == 64
    assert len(manifest["dataset_sha256"]) == 64
    assert manifest["gold_fields_stored"] is False


class FakeVectorStore:
    def __init__(self) -> None:
        self.rows = []

    async def count(self) -> int:
        return len(self.rows)

    async def add(self, ids, documents, metadatas) -> None:
        self.rows = list(zip(ids, documents, metadatas))

    async def query(self, query_texts, n_results=10):
        return [
            SimpleNamespace(
                id=self.rows[0][0],
                document=self.rows[0][1],
                metadata=self.rows[0][2],
                score=0.8,
            )
        ]

    async def hybrid_query(self, query_texts, n_results=10):
        return await self.query(query_texts, n_results=n_results)


@pytest.mark.asyncio
async def test_frozen_retriever_indexes_corpus_and_exposes_provenance(tmp_path):
    corpus = tmp_path / "rag-corpus.jsonl"
    _write_jsonl(
        corpus,
        [
            {
                "id": "new",
                "platform": "github",
                "source_url": "https://example.test/github/1",
                "title": "CSV export request",
                "content": "Teams need reliable exports for weekly reporting.",
            }
        ],
    )
    vector_store = FakeVectorStore()
    retriever = Phase3CorpusRetriever(corpus, vector_store=vector_store)

    context = await retriever.retrieve_context(
        "CSV export",
        n_results=3,
        min_score=0.2,
        max_chars=1500,
    )
    provenance = retriever.get_provenance()
    candidates = await retriever.retrieve("CSV export", n_results=20)
    hybrid_candidates = await retriever.retrieve_hybrid("CSV export", n_results=20)

    assert "Teams need reliable exports" in context
    assert len(vector_store.rows) == 1
    assert provenance["corpus_sha256"]
    assert provenance["corpus_records"] == 1
    assert provenance["table_name"].startswith("phase3_rag_")
    assert provenance["embedding_backend"] == "injected"
    assert candidates[0].id == "new"
    assert hybrid_candidates[0].id == "new"
