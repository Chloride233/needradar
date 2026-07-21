"""Tests for RAGRetriever — vault knowledge retrieval."""

from unittest.mock import AsyncMock

import pytest

from needradar.services.reranker import (
    RerankedDocument,
    RerankOutcome,
    RerankUsage,
)
from needradar.vector.base import SearchResult


@pytest.fixture
def mock_vs():
    """Mock vector store that returns predefined results."""
    vs = AsyncMock()
    results = [
        SearchResult(
            id="chunk-1",
            score=0.8,
            metadata={"title": "AI Code Review", "source": "02-需求池/test.md", "stage": "02-需求池"},
            document="Users need AI code review tools",
        ),
        SearchResult(
            id="chunk-2",
            score=0.61234,
            metadata={
                "title": "Dev Tools",
                "source": "02-需求池/test2.md",
                "stage": "02-需求池",
                "recall": {"mode": "hybrid_rrf", "dense_rank": 2, "lexical_rank": 1},
            },
            document="Developer productivity is important",
        ),
        SearchResult(
            id="chunk-3",
            score=0.15,
            metadata={"title": "Low Score", "source": "02-需求池/test3.md", "stage": "02-需求池"},
            document="This should be filtered out",
        ),
    ]
    vs.query.return_value = results
    vs.hybrid_query.return_value = results
    return vs


@pytest.mark.asyncio
async def test_retrieve_returns_filtered_results(mock_vs):
    from needradar.services.rag_retriever import RAGRetriever

    retriever = RAGRetriever()
    retriever._vs = mock_vs

    results = await retriever.retrieve("AI code review", n_results=5, min_score=0.2)

    # chunk-3 (score=0.15) should be filtered out by min_score=0.2
    assert len(results) == 2
    assert results[0]["id"] == "chunk-1"
    assert results[0]["score"] == 0.8
    assert results[0]["title"] == "AI Code Review"
    assert results[0]["chunk"] == "Users need AI code review tools"


@pytest.mark.asyncio
async def test_retrieve_with_stage_filter(mock_vs):
    from needradar.services.rag_retriever import RAGRetriever

    retriever = RAGRetriever()
    retriever._vs = mock_vs

    results = await retriever.retrieve("test", stage_filter="07-知识沉淀")
    # No results match stage "07-知识沉淀"
    assert len(results) == 0


@pytest.mark.asyncio
async def test_retrieve_empty_on_error():
    from needradar.services.rag_retriever import RAGRetriever

    retriever = RAGRetriever()
    mock_vs = AsyncMock()
    mock_vs.query.side_effect = RuntimeError("Vector store down")
    retriever._vs = mock_vs

    results = await retriever.retrieve("test")
    assert results == []


@pytest.mark.asyncio
async def test_retrieve_context_formats_output(mock_vs):
    from needradar.services.rag_retriever import RAGRetriever

    retriever = RAGRetriever()
    retriever._vs = mock_vs

    context = await retriever.retrieve_context("AI code review", max_chars=5000)

    assert "## 相关历史知识" in context
    assert "[来源: 02-需求池/test.md | AI Code Review]" in context
    assert "Users need AI code review tools" in context


@pytest.mark.asyncio
async def test_retrieve_context_respects_max_chars(mock_vs):
    from needradar.services.rag_retriever import RAGRetriever

    retriever = RAGRetriever()
    retriever._vs = mock_vs

    context = await retriever.retrieve_context("test", max_chars=30)
    # With max_chars=30, only the first short chunk fits
    assert len(context) < 200


@pytest.mark.asyncio
async def test_retrieve_context_empty_when_no_results():
    from needradar.services.rag_retriever import RAGRetriever

    retriever = RAGRetriever()
    mock_vs = AsyncMock()
    mock_vs.query.return_value = []
    retriever._vs = mock_vs

    context = await retriever.retrieve_context("test")
    assert context == ""


def test_get_retriever_singleton():
    import needradar.services.rag_retriever as mod
    from needradar.services.rag_retriever import get_retriever

    # Reset singleton
    mod._retriever = None

    r1 = get_retriever()
    r2 = get_retriever()
    assert r1 is r2

    # Cleanup
    mod._retriever = None


@pytest.mark.asyncio
async def test_enabled_reranker_recalls_twenty_and_returns_ranked_top_three(mock_vs, monkeypatch):
    from needradar.core.config import settings
    from needradar.services.rag_retriever import RAGRetriever

    monkeypatch.setattr(settings, "rerank_mode", "bge")
    reranker = AsyncMock()
    reranker.rerank.return_value = RerankOutcome(
        items=[
            RerankedDocument(
                document_id="chunk-2",
                text="Developer productivity is important",
                original_rank=2,
                original_score=0.61234,
                reranked_rank=1,
                relevance_score=0.91,
                metadata={
                    "title": "Dev Tools",
                    "source": "02-需求池/test2.md",
                    "stage": "02-需求池",
                    "recall": {"mode": "hybrid_rrf", "dense_rank": 2, "lexical_rank": 1},
                },
            ),
            RerankedDocument(
                document_id="chunk-1",
                text="Users need AI code review tools",
                original_rank=1,
                original_score=0.8,
                reranked_rank=2,
                relevance_score=0.82,
                metadata={"title": "AI Code Review", "source": "02-需求池/test.md", "stage": "02-需求池"},
            ),
        ],
        provider="siliconflow",
        requested_model_id="BAAI/bge-reranker-v2-m3",
        returned_model_id=None,
        request_id="trace-id",
        latency_ms=12.5,
        usage=RerankUsage(input_tokens=20, total_tokens=20),
        retry_count=0,
        degraded=False,
    )
    retriever = RAGRetriever(reranker=reranker)
    retriever._vs = mock_vs

    results = await retriever.retrieve("AI code review", n_results=5, min_score=0.2)

    mock_vs.hybrid_query.assert_awaited_once_with(["AI code review"], n_results=20)
    mock_vs.query.assert_not_awaited()
    assert [item["id"] for item in results] == ["chunk-2", "chunk-1"]
    assert results[0]["original_rank"] == 2
    assert results[0]["reranked_rank"] == 1
    assert results[0]["relevance_score"] == 0.91
    assert results[0]["rerank_token_usage"]["total_tokens"] == 20
    assert results[0]["recall"] == {"mode": "hybrid_rrf", "dense_rank": 2, "lexical_rank": 1}
    assert results[0]["recall_degraded"] is False
    reranker.rerank.assert_awaited_once()
    assert reranker.rerank.await_args.args[1][1].original_score == 0.61234
