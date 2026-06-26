"""Tests for RAGRetriever — vault knowledge retrieval."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from needradar.vector.base import SearchResult


@pytest.fixture
def mock_vs():
    """Mock vector store that returns predefined results."""
    vs = AsyncMock()
    vs.query.return_value = [
        SearchResult(id="chunk-1", score=0.8, metadata={"title": "AI Code Review", "source": "02-需求池/test.md", "stage": "02-需求池"}, document="Users need AI code review tools"),
        SearchResult(id="chunk-2", score=0.6, metadata={"title": "Dev Tools", "source": "02-需求池/test2.md", "stage": "02-需求池"}, document="Developer productivity is important"),
        SearchResult(id="chunk-3", score=0.15, metadata={"title": "Low Score", "source": "02-需求池/test3.md", "stage": "02-需求池"}, document="This should be filtered out"),
    ]
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
    from needradar.services.rag_retriever import get_retriever, _retriever
    # Reset singleton
    import needradar.services.rag_retriever as mod
    mod._retriever = None

    r1 = get_retriever()
    r2 = get_retriever()
    assert r1 is r2

    # Cleanup
    mod._retriever = None
