"""Verify VectorStore interface contract."""

from needradar.vector.base import SearchResult, VectorStore


def test_search_result_dataclass():
    r = SearchResult(id="test", score=0.95, metadata={"platform": "github"})
    assert r.id == "test"
    assert r.score == 0.95


def test_vector_store_is_abstract():
    import abc

    assert issubclass(VectorStore, abc.ABC)
    # Verify the abstract methods exist
    abstract_methods = VectorStore.__abstractmethods__
    assert "add" in abstract_methods
    assert "query" in abstract_methods
    assert "delete" in abstract_methods
    assert "count" in abstract_methods
