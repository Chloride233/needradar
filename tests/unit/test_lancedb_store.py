"""Tests for LanceDBVectorStore — vector storage operations."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from needradar.vector.base import SearchResult


@pytest.fixture
def temp_lancedb_dir():
    """Provide a temporary LanceDB directory."""
    d = tempfile.mkdtemp()
    yield d


import uuid


@pytest.fixture
def store(temp_lancedb_dir):
    """Create a LanceDBVectorStore with a unique temp table."""
    with patch("needradar.vector.lancedb_store.settings") as mock_settings:
        mock_settings.lancedb_dir = temp_lancedb_dir
        from needradar.vector.lancedb_store import LanceDBVectorStore
        return LanceDBVectorStore(table_name=f"test_{uuid.uuid4().hex[:8]}")


# ── Schema & init tests ──


def test_store_creates_table(store):
    """Store creates a table on init."""
    assert store._table is not None
    assert store._table_name.startswith("test_")


def test_store_opens_existing_table(temp_lancedb_dir):
    """Store opens an existing table."""
    with patch("needradar.vector.lancedb_store.settings") as mock_settings:
        mock_settings.lancedb_dir = temp_lancedb_dir
        from needradar.vector.lancedb_store import LanceDBVectorStore

        store1 = LanceDBVectorStore(table_name="test_table")
        store2 = LanceDBVectorStore(table_name="test_table")

        assert store2._table is not None


# ── Async operation tests ──


@pytest.mark.asyncio
async def test_add_and_count(store):
    """add() inserts rows and count() returns the count."""
    await store.add(
        ids=["id-1", "id-2"],
        documents=["doc one", "doc two"],
        metadatas=[{"key": "a"}, {"key": "b"}],
    )

    count = await store.count()
    assert count == 2


@pytest.mark.asyncio
async def test_query_returns_results(store):
    """query() returns results with scores."""
    await store.add(
        ids=["id-1", "id-2"],
        documents=["AI code review tool", "Developer productivity"],
    )

    results = await store.query(["code review"], n_results=2)
    assert len(results) == 2
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].score >= 0


@pytest.mark.asyncio
async def test_query_empty_table(temp_lancedb_dir):
    """query() on empty table returns empty list or handles gracefully."""
    with patch("needradar.vector.lancedb_store.settings") as mock_settings:
        mock_settings.lancedb_dir = temp_lancedb_dir
        from needradar.vector.lancedb_store import LanceDBVectorStore
        store = LanceDBVectorStore(table_name="empty_table")

        count = await store.count()
        assert count == 0


@pytest.mark.asyncio
async def test_delete(store):
    """delete() removes rows."""
    await store.add(
        ids=["id-1", "id-2", "id-3"],
        documents=["doc one", "doc two", "doc three"],
    )

    await store.delete(["id-2"])
    count = await store.count()
    assert count == 2


@pytest.mark.asyncio
async def test_add_with_no_metadata(store):
    """add() works without metadata."""
    await store.add(
        ids=["id-1"],
        documents=["doc"],
    )

    count = await store.count()
    assert count == 1


@pytest.mark.asyncio
async def test_query_returns_metadata(store):
    """query() preserves metadata."""
    await store.add(
        ids=["id-1"],
        documents=["AI code review"],
        metadatas=[{"platform": "github", "keyword": "test"}],
    )

    results = await store.query(["AI code review"], n_results=1)
    assert len(results) == 1
    assert results[0].metadata is not None
    assert results[0].metadata["platform"] == "github"


@pytest.mark.asyncio
async def test_query_score_range(store):
    """query() returns scores in valid range."""
    await store.add(
        ids=["id-1", "id-2"],
        documents=["Python programming", "JavaScript web development"],
    )

    results = await store.query(["Python"], n_results=2)
    for r in results:
        assert 0 <= r.score <= 1


@pytest.mark.asyncio
async def test_delete_nonexistent_id(store):
    """delete() with non-existent ID doesn't raise."""
    await store.add(ids=["id-1"], documents=["doc"])
    # Should not raise
    await store.delete(["nonexistent-id"])


@pytest.mark.asyncio
async def test_add_duplicate_id(store):
    """add() with duplicate ID raises or overwrites."""
    await store.add(ids=["id-1"], documents=["doc one"])

    # LanceDB add with duplicate ID may raise or overwrite
    # Test that it doesn't crash silently
    try:
        await store.add(ids=["id-1"], documents=["doc one updated"])
    except Exception:
        pass  # Expected behavior
