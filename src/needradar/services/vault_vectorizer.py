"""Vault Vectorizer — indexes vault markdown files into LanceDB for RAG.

Walks vault directories, chunks markdown content, and writes embeddings
to a dedicated LanceDB collection. Supports incremental updates by
tracking file modification times.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from loguru import logger

from needradar.core.config import settings
from needradar.services.vault_store import VaultStore

# Directories to index (relative to vault root)
_INDEX_DIRS = [
    "02-需求池",
    "03-分析车间/初稿打磨",
    "07-知识沉淀",
]

# Chunking: max characters per chunk
_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100


def _file_hash(path: Path) -> str:
    """Fast hash based on path + mtime + size."""
    stat = path.stat()
    raw = f"{path}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.md5(raw.encode()).hexdigest()


def _chunk_text(text: str, max_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_size and current:
            chunks.append(current.strip())
            # Keep overlap from end of current chunk
            current = current[-overlap:] + "\n\n" + para if overlap else para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text[:max_size]] if text else []


class VaultVectorizer:
    """Indexes vault markdown files into LanceDB for RAG retrieval."""

    def __init__(self) -> None:
        self._vault = VaultStore()
        self._vs = None
        self._state_file = Path(settings.lancedb_dir).parent / "vault_index_state.json"
        self._state: dict[str, str] = {}  # path -> hash
        self._load_state()

    def _get_vs(self):
        if self._vs is None:
            from needradar.vector.lancedb_store import LanceDBVectorStore
            self._vs = LanceDBVectorStore(table_name="vault_knowledge")
        return self._vs

    def _load_state(self) -> None:
        if self._state_file.exists():
            try:
                self._state = json.loads(self._state_file.read_text(encoding="utf-8"))
            except Exception:
                self._state = {}

    def _save_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def index_all(self, force: bool = False) -> dict:
        """Index all configured vault directories.

        Args:
            force: Re-index all files regardless of changes.

        Returns:
            Stats: {indexed, skipped, total_files, total_chunks}
        """
        vs = self._get_vs()
        stats = {"indexed": 0, "skipped": 0, "total_files": 0, "total_chunks": 0}
        all_ids: list[str] = []
        all_docs: list[str] = []
        all_metas: list[dict] = []

        for rel_dir in _INDEX_DIRS:
            abs_dir = self._vault.root / rel_dir
            if not abs_dir.exists():
                continue

            for md_file in abs_dir.rglob("*.md"):
                stats["total_files"] += 1
                file_key = str(md_file.relative_to(self._vault.root))
                current_hash = _file_hash(md_file)

                if not force and self._state.get(file_key) == current_hash:
                    stats["skipped"] += 1
                    continue

                try:
                    meta, body = self._vault.read(md_file)
                    if not body.strip():
                        continue

                    chunks = _chunk_text(body)
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"{file_key}::chunk:{i}"
                        chunk_meta = {
                            "source": file_key,
                            "title": meta.get("标题", md_file.stem),
                            "stage": rel_dir,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                        }
                        all_ids.append(chunk_id)
                        all_docs.append(chunk)
                        all_metas.append(chunk_meta)

                    self._state[file_key] = current_hash
                    stats["indexed"] += 1
                    stats["total_chunks"] += len(chunks)
                except Exception as e:
                    logger.warning("vault_index_failed", file=file_key, error=str(e))

        # Batch write to LanceDB
        if all_ids:
            # Delete old chunks for re-indexed files
            old_ids = await self._find_stale_ids(vs, set(all_ids))
            if old_ids:
                await vs.delete(old_ids)

            await vs.add(ids=all_ids, documents=all_docs, metadatas=all_metas)
            self._save_state()

        logger.info("vault_index_done", **stats)
        return stats

    async def _find_stale_ids(self, vs, new_ids: set[str]) -> list[str]:
        """Delete old chunks for files being re-indexed, return IDs that were removed.

        Instead of searching for stale IDs (expensive), we delete by source prefix
        and let the re-add recreate them.
        """
        try:
            sources = {id_.split("::")[0] for id_ in new_ids}
            # Query a small batch to find any existing chunks from these sources
            stale = []
            for source in sources:
                results = await vs.query([source], n_results=100, min_score=0.0)
                for r in results:
                    if r.id not in new_ids and r.metadata and r.metadata.get("source") == source:
                        stale.append(r.id)
            return stale
        except Exception:
            return []


async def index_vault(force: bool = False) -> dict:
    """Convenience function to index the vault."""
    vectorizer = VaultVectorizer()
    return await vectorizer.index_all(force=force)
