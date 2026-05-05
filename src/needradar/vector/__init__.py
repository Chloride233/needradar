"""Vector store factory."""

from needradar.vector.base import VectorStore


def create_vector_store(backend: str = "chroma", **kwargs) -> VectorStore:
    if backend == "chroma":
        from needradar.vector.chroma_store import ChromaVectorStore
        return ChromaVectorStore(**kwargs)
    raise ValueError(f"Unknown vector store backend: {backend}")
