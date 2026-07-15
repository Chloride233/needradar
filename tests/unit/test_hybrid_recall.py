from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_hybrid_recall_fuses_dense_and_ngram_full_text(tmp_path):
    import needradar.vector.lancedb_store as module

    module._reset_globals()
    with patch.object(module.settings, "lancedb_dir", str(tmp_path)):
        store = module.LanceDBVectorStore(table_name="hybrid")
        lexical_vector = [0.0, 1.0, *([0.0] * 382)]
        dense_vector = [1.0, 0.0, *([0.0] * 382)]
        with patch.object(module, "_embed", return_value=[lexical_vector, dense_vector]):
            await store.add(
                ids=["lexical", "dense"],
                documents=["zebraquux marker", "alpha beta"],
                metadatas=[{"source": "lexical"}, {"source": "dense"}],
            )
        with patch.object(module, "_embed", return_value=[dense_vector]):
            results = await store.hybrid_query(["zebraquux"], n_results=2)
    module._reset_globals()

    assert [result.id for result in results] == ["lexical", "dense"]
    assert results[0].metadata["recall"]["mode"] == "hybrid_rrf"
    assert results[0].metadata["recall"]["lexical_rank"] == 1
    assert results[0].metadata["recall"]["dense_rank"] == 2
    assert results[0].score > results[1].score


@pytest.mark.asyncio
async def test_hybrid_recall_marks_dense_fallback_when_fts_fails():
    from needradar.vector.base import SearchResult
    from needradar.vector.lancedb_store import LanceDBVectorStore

    store = object.__new__(LanceDBVectorStore)
    dense = SearchResult(id="dense", score=0.8, metadata={"source": "dense"}, document="text")
    with (
        patch.object(store, "query", return_value=[dense]),
        patch.object(store, "_ensure_fts_index", side_effect=RuntimeError("fts unavailable")),
    ):
        results = await store.hybrid_query(["query"], n_results=1)

    assert results[0].id == "dense"
    assert results[0].metadata["recall"] == {"mode": "dense_fallback"}
