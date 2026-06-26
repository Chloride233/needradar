"""Tests for VaultVectorizer — vault content indexing."""
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from needradar.services.vault_vectorizer import _chunk_text, _file_hash, VaultVectorizer


# ── Unit tests for pure functions ──


def test_chunk_text_short_text():
    """Text shorter than max_size returns a single chunk."""
    chunks = _chunk_text("Hello world", max_size=100)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_chunk_text_splits_paragraphs():
    """Text is split at paragraph boundaries."""
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = _chunk_text(text, max_size=30, overlap=0)
    assert len(chunks) >= 2
    assert "Paragraph one." in chunks[0]


def test_chunk_text_empty():
    """Empty text returns empty list."""
    chunks = _chunk_text("")
    assert chunks == []


def test_chunk_text_very_long_paragraph():
    """A single paragraph longer than max_size is kept as one chunk."""
    text = "A" * 1000
    chunks = _chunk_text(text, max_size=500, overlap=0)
    assert len(chunks) >= 1


def test_chunk_text_with_overlap():
    """Overlap creates overlapping content between chunks."""
    text = "A" * 400 + "\n\n" + "B" * 400
    chunks = _chunk_text(text, max_size=500, overlap=50)
    assert len(chunks) >= 2


def test_file_hash_deterministic():
    """Same file produces same hash."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("test content")
        path = Path(f.name)

    h1 = _file_hash(path)
    h2 = _file_hash(path)
    assert h1 == h2
    assert len(h1) == 32  # MD5 hex

    path.unlink()


def test_file_hash_different_for_different_files():
    """Different files produce different hashes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f1:
        f1.write("content A")
        path1 = Path(f1.name)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f2:
        f2.write("content B")
        path2 = Path(f2.name)

    assert _file_hash(path1) != _file_hash(path2)

    path1.unlink()
    path2.unlink()


# ── Vectorizer init tests ──


def test_vectorizer_loads_state(tmp_path):
    """VaultVectorizer loads state from file."""
    state_file = tmp_path / "vault_index_state.json"
    state_file.write_text('{"02-需求池/test.md": "abc123"}', encoding="utf-8")

    with patch("needradar.services.vault_vectorizer.settings") as mock_settings:
        mock_settings.lancedb_dir = str(tmp_path / "lancedb")
        mock_settings.vault_path = str(tmp_path)

        vectorizer = VaultVectorizer()
        vectorizer._state_file = state_file
        vectorizer._load_state()

    assert vectorizer._state == {"02-需求池/test.md": "abc123"}


def test_vectorizer_saves_state(tmp_path):
    """VaultVectorizer saves state to file."""
    state_file = tmp_path / "vault_index_state.json"

    with patch("needradar.services.vault_vectorizer.settings") as mock_settings:
        mock_settings.lancedb_dir = str(tmp_path / "lancedb")
        mock_settings.vault_path = str(tmp_path)

        vectorizer = VaultVectorizer()
        vectorizer._state_file = state_file
        vectorizer._state = {"test.md": "hash123"}
        vectorizer._save_state()

    assert state_file.exists()
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved == {"test.md": "hash123"}


def test_vectorizer_handles_corrupt_state(tmp_path):
    """VaultVectorizer handles corrupt state file gracefully."""
    state_file = tmp_path / "vault_index_state.json"
    state_file.write_text("NOT VALID JSON", encoding="utf-8")

    with patch("needradar.services.vault_vectorizer.settings") as mock_settings:
        mock_settings.lancedb_dir = str(tmp_path / "lancedb")
        mock_settings.vault_path = str(tmp_path)

        vectorizer = VaultVectorizer()
        vectorizer._state_file = state_file
        vectorizer._load_state()

    assert vectorizer._state == {}


@pytest.mark.asyncio
async def test_index_all_empty_vault(tmp_path):
    """index_all handles empty vault directory gracefully."""
    vault_dir = tmp_path / "02-需求池"
    vault_dir.mkdir(parents=True)

    with patch("needradar.services.vault_vectorizer.settings") as mock_settings:
        mock_settings.lancedb_dir = str(tmp_path / "lancedb")
        mock_settings.vault_path = str(tmp_path)

        vectorizer = VaultVectorizer()
        # Override the vault's root via the private attribute
        vectorizer._vault._root = tmp_path

        with patch.object(vectorizer, "_get_vs") as mock_get_vs:
            mock_vs = AsyncMock()
            mock_get_vs.return_value = mock_vs

            stats = await vectorizer.index_all(force=True)

    assert stats["total_files"] == 0
    assert stats["indexed"] == 0
    assert stats["total_chunks"] == 0
