"""Tests for ReportService — report generation and relationship graphs."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from needradar.services.report_service import (
    ReportService,
    _load_prompts,
    get_report_service,
)

# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestSanitizeWikilinkTitle:
    def test_no_special_chars(self):
        assert ReportService._sanitize_wikilink_title("hello") == "hello"

    def test_replaces_pipe(self):
        assert ReportService._sanitize_wikilink_title("a|b") == "a-b"

    def test_replaces_brackets(self):
        result = ReportService._sanitize_wikilink_title("a[b]c")
        assert result == "a(b)c"

    def test_complex_title(self):
        result = ReportService._sanitize_wikilink_title("test|pipe[open]close")
        assert result == "test-pipe(open)close"


# ---------------------------------------------------------------------------
# _load_prompts
# ---------------------------------------------------------------------------

class TestLoadPrompts:
    def test_loads_real_prompts(self):
        import needradar.services.report_service as mod
        mod._prompts_cache = None
        result = _load_prompts()
        assert "report_analysis" in result
        cached = _load_prompts()
        assert cached is result


# ---------------------------------------------------------------------------
# get_report_service singleton
# ---------------------------------------------------------------------------

class TestGetReportService:
    def test_returns_singleton(self):
        import needradar.services.report_service as mod
        mod._report_service = None
        with patch("needradar.services.report_service.create_vector_store") as mc:
            mc.return_value = MagicMock()
            svc1 = get_report_service()
            svc2 = get_report_service()
            assert svc1 is svc2
        mod._report_service = None


# ---------------------------------------------------------------------------
# ReportService unit tests
# ---------------------------------------------------------------------------

@pytest.fixture
def svc_with_mocks():
    """Create ReportService with mocked vector store."""
    with patch("needradar.services.report_service.create_vector_store") as mc:
        mock_vs = MagicMock()
        mc.return_value = mock_vs
        svc = ReportService()
        svc._vs = mock_vs
        yield svc


class TestFrontmatter:
    def test_basic_metadata(self, svc_with_mocks):
        meta = svc_with_mocks._frontmatter("Report Title", "python", "2026-05-31")
        assert meta["标题"] == "Report Title"
        assert meta["阶段"] == "初稿"
        assert meta["关键词"] == ["python"]
        assert meta["创建时间"] == "2026-05-31"
        assert meta["关联需求"] == []

    def test_with_refs(self, svc_with_mocks):
        refs = ["[[02-需求池/Need1|Need1]]"]
        meta = svc_with_mocks._frontmatter("R", "k", "d", refs)
        assert meta["关联需求"] == refs


class TestRetrieve:
    @pytest.mark.asyncio
    async def test_empty_results(self, svc_with_mocks):
        svc_with_mocks._vs.query = AsyncMock(return_value=[])
        result = await svc_with_mocks._retrieve("python")
        assert result["documents"] == []
        assert result["top_titles"] == []

    @pytest.mark.asyncio
    async def test_with_results(self, svc_with_mocks):
        from needradar.vector.base import SearchResult
        r1 = SearchResult(id="Need AI", score=0.9, document="AI content", metadata={})
        r2 = SearchResult(id="Need Web", score=0.8, document="Web content", metadata={})
        svc_with_mocks._vs.query = AsyncMock(return_value=[r1, r2])

        result = await svc_with_mocks._retrieve("python")
        assert len(result["documents"]) == 2
        assert len(result["top_titles"]) == 2
        assert "[[02-需求池/Need AI|Need AI]]" in result["top_titles"][0]


class TestRetrieveFallback:
    def test_searches_vault(self, svc_with_mocks):
        with patch("needradar.services.report_service.vault") as mv:
            mv.search.return_value = (
                [
                    {"标题": "Need 1", "_body": "body 1"},
                    {"标题": "Need 2", "_body": "body 2"},
                ],
                2,
            )
            result = svc_with_mocks._retrieve_fallback("python")
            assert len(result["documents"]) == 2
            assert len(result["top_titles"]) == 2

    def test_empty_search(self, svc_with_mocks):
        with patch("needradar.services.report_service.vault") as mv:
            mv.search.return_value = ([], 0)
            result = svc_with_mocks._retrieve_fallback("python")
            assert result["documents"] == []

    def test_sanitizes_titles(self, svc_with_mocks):
        with patch("needradar.services.report_service.vault") as mv:
            mv.search.return_value = (
                [{"标题": "a|b[c]d", "_body": "x"}],
                1,
            )
            result = svc_with_mocks._retrieve_fallback("python")
            assert "a-b(c)d" in result["top_titles"][0]


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_empty_documents(self, svc_with_mocks):
        result = await svc_with_mocks._analyze("python", {"documents": []})
        assert "未检索到相关需求数据" in result

    @pytest.mark.asyncio
    async def test_with_context(self, svc_with_mocks):
        prompts = {"report_analysis": "Analyze the following needs"}
        with patch("needradar.services.report_service._load_prompts", return_value=prompts), \
             patch("needradar.services.report_service.llm") as ml:
            ml.complete = AsyncMock(return_value="## Analysis Result\n\nKey findings here.")
            result = await svc_with_mocks._analyze("python", {"documents": ["doc1", "doc2"]})
            assert "Analysis Result" in result
            ml.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_normalizes_literal_newlines(self, svc_with_mocks):
        prompts = {"report_analysis": "Analyze"}
        with patch("needradar.services.report_service._load_prompts", return_value=prompts), \
             patch("needradar.services.report_service.llm") as ml:
            ml.complete = AsyncMock(return_value="line1\\nline2\\nline3")
            result = await svc_with_mocks._analyze("python", {"documents": ["d"]})
            assert "\n" in result
            assert "\\n" not in result

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self, svc_with_mocks):
        prompts = {"report_analysis": "Analyze"}
        with patch("needradar.services.report_service._load_prompts", return_value=prompts), \
             patch("needradar.services.report_service.llm") as ml:
            ml.complete = AsyncMock(side_effect=RuntimeError("API error"))
            result = await svc_with_mocks._analyze("python", {"documents": ["d"]})
            assert "AI 分析生成失败" in result

    @pytest.mark.asyncio
    async def test_limits_to_15_documents(self, svc_with_mocks):
        prompts = {"report_analysis": "Analyze"}
        docs = [f"doc{i}" for i in range(25)]
        with patch("needradar.services.report_service._load_prompts", return_value=prompts), \
             patch("needradar.services.report_service.llm") as ml:
            ml.complete = AsyncMock(return_value="ok")
            await svc_with_mocks._analyze("python", {"documents": docs})
            sent_content = ml.complete.call_args[0][0][1]["content"]
            assert "doc14" in sent_content
            assert "doc15" not in sent_content


class TestBuildStats:
    def test_empty_results(self, svc_with_mocks):
        result = svc_with_mocks._build_stats_from_retrieval({"results": []})
        assert "检索到相关需求: **0**" in result

    def test_with_results_from_vault(self, svc_with_mocks):
        from needradar.vector.base import SearchResult
        r1 = SearchResult(id="Need1", score=0.9)
        r2 = SearchResult(id="Need2", score=0.8)

        with patch("needradar.services.report_service.vault") as mv:
            mv.find_by_title.side_effect = lambda stage, title: (
                __import__("pathlib").Path(f"/v/{title}.md")
            )
            mv.read.side_effect = [
                ({"来源平台": "github", "情感倾向": "strong", "情绪极性": "positive", "提及次数": 3}, ""),
                ({"来源平台": "stackoverflow", "情感倾向": "moderate", "情绪极性": "negative", "提及次数": 1}, ""),
            ]
            result = svc_with_mocks._build_stats_from_retrieval({"results": [r1, r2]})
            assert "检索到相关需求: **2**" in result
            assert "github" in result
            assert "强烈需求占比" in result


class TestUpdateBacklinks:
    def test_adds_backlink_to_need(self, svc_with_mocks):
        refs = ["[[02-需求池/Need1|Need1]]"]
        with patch("needradar.services.report_service.vault") as mv:
            mv.find_by_title.return_value = __import__("pathlib").Path("/v/Need1.md")
            mv.read.return_value = ({"关联报告": []}, "body")
            svc_with_mocks._update_backlinks("My Report", refs)
            mv.update_frontmatter.assert_called_once()

    def test_skips_when_need_not_found(self, svc_with_mocks):
        with patch("needradar.services.report_service.vault") as mv:
            mv.find_by_title.return_value = None
            svc_with_mocks._update_backlinks("My Report", ["[[02-需求池/Missing|Missing]]"])
            mv.update_frontmatter.assert_not_called()

    def test_no_duplicate_backlinks(self, svc_with_mocks):
        refs = ["[[02-需求池/Need1|Need1]]"]
        with patch("needradar.services.report_service.vault") as mv:
            mv.find_by_title.return_value = __import__("pathlib").Path("/v/Need1.md")
            mv.read.return_value = ({"关联报告": ["[[03-分析车间/初稿打磨/My Report|My Report]]"]}, "body")
            svc_with_mocks._update_backlinks("My Report", refs)
            mv.update_frontmatter.assert_not_called()


class TestWriteRelationshipGraph:
    def test_empty_when_no_matching_needs(self, svc_with_mocks):
        with patch("needradar.services.report_service.vault") as mv:
            mv.list_files.return_value = []
            svc_with_mocks._write_relationship_graph("python")
            mv.write.assert_not_called()

    def test_generates_graph_for_matching_needs(self, svc_with_mocks):
        needs = [
            (None, {"标题": "Need A", "关键词": ["python"], "来源平台": "github", "情感倾向": "strong", "情绪极性": "positive"}, ""),
            (None, {"标题": "Need B", "关键词": ["python", "web"], "来源平台": "stackoverflow", "情感倾向": "moderate", "情绪极性": "negative"}, ""),
        ]
        with patch("needradar.services.report_service.vault") as mv:
            mv.list_files.return_value = needs
            svc_with_mocks._write_relationship_graph("python")
            mv.write.assert_called_once()
            args, _kwargs = mv.write.call_args
            # vault.write(stage, title, meta, body) — body is 4th positional arg
            assert "```mermaid" in args[3]

    def test_handles_string_keyword_gracefully(self, svc_with_mocks):
        with patch("needradar.services.report_service.vault") as mv:
            mv.list_files.return_value = [
                (None, {"标题": "Need C", "关键词": "python", "来源平台": "github", "情感倾向": "mild", "情绪极性": "neutral"}, ""),
            ]
            svc_with_mocks._write_relationship_graph("python")
            mv.write.assert_not_called()

    def test_keyword_list_contains_match(self, svc_with_mocks):
        with patch("needradar.services.report_service.vault") as mv:
            mv.list_files.return_value = [
                (None, {"标题": "Need D", "关键词": ["python", "async"], "来源平台": "github", "情感倾向": "strong", "情绪极性": "positive"}, ""),
            ]
            svc_with_mocks._write_relationship_graph("python")
            mv.write.assert_called_once()


class TestGenerateReport:
    @pytest.mark.asyncio
    async def test_full_flow(self, svc_with_mocks):
        from needradar.vector.base import SearchResult
        sr = SearchResult(id="Need1", score=0.9, document="content", metadata={})
        svc_with_mocks._vs.query = AsyncMock(return_value=[sr])

        prompts = {"report_analysis": "Analyze"}
        with patch("needradar.services.report_service._load_prompts", return_value=prompts), \
             patch("needradar.services.report_service.llm") as ml, \
             patch("needradar.services.report_service.vault") as mv:
            ml.complete = AsyncMock(return_value="## Analysis\n\nFindings here.")
            mv.write.return_value = __import__("pathlib").Path("/v/report.md")
            mv.find_by_title.return_value = __import__("pathlib").Path("/v/Need1.md")
            mv.read.return_value = ({"关联报告": []}, "body")
            mv.list_files.return_value = [
                (None, {"标题": "Need1", "关键词": ["python"], "来源平台": "github", "情感倾向": "strong", "情绪极性": "positive"}, ""),
            ]

            result = await svc_with_mocks.generate_report("python")
            assert result is not None
            mv.write.assert_called()

    @pytest.mark.asyncio
    async def test_falls_back_when_vector_fails(self, svc_with_mocks):
        svc_with_mocks._vs.query = AsyncMock(side_effect=RuntimeError("ChromaDB error"))
        prompts = {"report_analysis": "Analyze"}

        with patch("needradar.services.report_service._load_prompts", return_value=prompts), \
             patch("needradar.services.report_service.llm") as ml, \
             patch("needradar.services.report_service.vault") as mv:
            ml.complete = AsyncMock(return_value="## Fallback analysis")
            mv.search.return_value = ([], 0)
            mv.write.return_value = __import__("pathlib").Path("/v/report.md")
            mv.list_files.return_value = []

            result = await svc_with_mocks.generate_report("python")
            assert result is not None
            mv.search.assert_called()
