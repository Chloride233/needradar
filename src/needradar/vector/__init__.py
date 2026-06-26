"""Vector store factory."""

from needradar.vector.base import VectorStore


def create_vector_store(**kwargs) -> VectorStore:
    """Create a LanceDB vector store instance."""
    from needradar.vector.lancedb_store import LanceDBVectorStore
    return LanceDBVectorStore(**kwargs)
