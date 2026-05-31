"""Tests for VaultStore."""

import pytest

from needradar.services.vault_store import VaultStore


@pytest.fixture
def vault(tmp_path):
    """Create a VaultStore with a temp root."""
    store = VaultStore()
    store._root = tmp_path
    for sub in [
        "01-原始素材库/灵感剪报",
        "02-需求池",
        "03-分析车间/大纲挑选",
        "03-分析车间/初稿打磨",
        "03-分析车间/终稿确认",
        "04-报告归档",
        "05-工作日志",
        "06-关系图谱",
    ]:
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return store


class TestSafeFilename:
    def test_normal_title(self):
        assert VaultStore._safe_filename("hello world") == "hello world"

    def test_removes_illegal_chars(self):
        result = VaultStore._safe_filename('test:<file>?*')
        assert result == "testfile"

    def test_truncates_long_title(self):
        result = VaultStore._safe_filename("a" * 100)
        assert len(result) <= 80

    def test_empty_title_returns_untitled(self):
        assert VaultStore._safe_filename("") == "untitled"

    def test_all_illegal_chars(self):
        result = VaultStore._safe_filename('<>:"/\\|?*')
        assert result == "untitled"


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        text = "---\nkey: value\n---\n\nbody content\n"
        meta, body = VaultStore()._parse_frontmatter(text)
        assert meta == {"key": "value"}
        assert body == "body content"

    def test_no_frontmatter(self):
        text = "just plain text"
        meta, body = VaultStore()._parse_frontmatter(text)
        assert meta == {}
        assert body == "just plain text"

    def test_unclosed_frontmatter(self):
        text = "---\nkey: value\n"
        meta, body = VaultStore()._parse_frontmatter(text)
        assert meta == {}

    def test_invalid_yaml_falls_back(self):
        text = "---\nkey: *invalid_alias\n---\n\nbody\n"
        meta, body = VaultStore()._parse_frontmatter(text)
        assert meta == {}
        assert body == "body"


class TestDir:
    def test_known_stages(self, vault):
        assert vault._dir("需求").name == "02-需求池"
        assert vault._dir("初稿").name == "初稿打磨"
        assert vault._dir("已归档").name == "04-报告归档"

    def test_unknown_stage_defaults_to_root(self, vault):
        assert vault._dir("nonexistent") == vault._root


class TestWriteAndRead:
    def test_write_and_read(self, vault):
        path = vault.write("需求", "Test Need", {"关键词": ["python"]}, "body text")
        meta, body = vault.read(path)
        assert meta["关键词"] == ["python"]
        assert "body text" in body

    def test_write_creates_directory(self, vault):
        import shutil
        stage_dir = vault._dir("需求")
        shutil.rmtree(stage_dir)
        vault.write("需求", "New Need", {"test": True}, "content")
        assert stage_dir.exists()

    def test_read_with_relative_path(self, vault):
        path = vault.write("需求", "Relative Test", {"id": 1}, "rel")
        rel_path = path.relative_to(vault._root)
        meta, body = vault.read(rel_path)
        assert meta["id"] == 1

    def test_update_frontmatter(self, vault):
        path = vault.write("需求", "Updatable", {"version": 1}, "body")
        vault.update_frontmatter(path, {"version": 2, "status": "done"})
        meta, _ = vault.read(path)
        assert meta["version"] == 2
        assert meta["status"] == "done"


class TestListFiles:
    def test_list_empty_stage(self, vault):
        assert vault.list_files("需求") == []

    def test_list_with_files(self, vault):
        vault.write("需求", "Need 1", {"id": 1}, "content 1")
        vault.write("需求", "Need 2", {"id": 2}, "content 2")
        assert len(vault.list_files("需求")) == 2

    def test_list_nonexistent_directory(self, vault):
        import shutil
        shutil.rmtree(vault._dir("需求"))
        assert vault.list_files("需求") == []


class TestFindByTitle:
    def test_exact_match(self, vault):
        vault.write("需求", "Python Async", {}, "")
        result = vault.find_by_title("需求", "Python Async")
        assert result is not None
        assert result.stem == "Python Async"

    def test_no_match(self, vault):
        assert vault.find_by_title("需求", "Nonexistent") is None

    def test_nonexistent_stage(self, vault):
        import shutil
        shutil.rmtree(vault._dir("需求"))
        assert vault.find_by_title("需求", "anything") is None

    def test_fuzzy_match(self, vault):
        vault.write("需求", "Python Async Programming", {}, "")
        result = vault.find_by_title("需求", "python async programming")
        assert result is not None

    def test_partial_match(self, vault):
        vault.write("需求", "Long Title About Python", {}, "")
        result = vault.find_by_title("需求", "Python")
        assert result is not None


class TestSearch:
    def test_search_by_keyword(self, vault):
        vault.write("需求", "Python Web", {"关键词": ["python", "web"]}, "body")
        vault.write("需求", "Rust Async", {"关键词": ["rust"]}, "body")
        results, total = vault.search("需求", keyword="python")
        assert total == 1

    def test_search_by_platform(self, vault):
        vault.write("需求", "G Issue", {"来源平台": "github"}, "body")
        vault.write("需求", "SO Post", {"来源平台": "stackoverflow"}, "body")
        results, total = vault.search("需求", platform="github")
        assert total == 1

    def test_search_pagination(self, vault):
        for i in range(5):
            vault.write("需求", f"Need {i}", {"id": i}, f"body {i}")
        results, total = vault.search("需求", page=1, page_size=2)
        assert total == 5
        assert len(results) == 2

    def test_search_empty_stage(self, vault):
        results, total = vault.search("需求")
        assert results == []
        assert total == 0


class TestTopKeywords:
    def test_empty_stage(self, vault):
        assert vault.top_keywords("需求") == []

    def test_ranked_keywords(self, vault):
        vault.write("需求", "A", {"关键词": ["python", "async"]}, "")
        vault.write("需求", "B", {"关键词": ["python", "web"]}, "")
        vault.write("需求", "C", {"关键词": ["rust"]}, "")
        result = vault.top_keywords("需求", limit=5)
        assert len(result) == 4
        assert "python" in result

    def test_single_keyword_as_string(self, vault):
        vault.write("需求", "String KW", {"关键词": "single_kw"}, "")
        result = vault.top_keywords("需求")
        assert "single_kw" in result
