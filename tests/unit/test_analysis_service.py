"""Tests for AnalysisService — the core pipeline orchestrator."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from needradar.models.crawl_task import CrawlTask, TaskStatus
from needradar.models.fingerprint import CrawlFingerprint
from needradar.schemas.schemas import (
    EmotionEnum,
    ExtractedRequirement,
    RawDiscussionItem,
    SentimentEnum,
)
from needradar.services.analysis_service import (
    AnalysisService,
    _load_prompts,
    invalidate_prompts_cache,
)

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_item():
    return RawDiscussionItem(
        platform="github",
        source_url="http://github.com/test/1",
        title="Need AI-powered code review features in CI pipeline",
        content="Users want AI-powered code review to improve development efficiency and reduce manual overhead in pull request workflows",
        author="dev1",
    )


@pytest.fixture
def fake_extracted():
    return ExtractedRequirement(
        title="AI Code Review",
        description="Need AI-powered code review tool",
        sentiment=SentimentEnum.STRONG,
        emotion=EmotionEnum.POSITIVE,
        confidence=0.9,
        use_case="Code review automation",
        pain_point="Manual reviews are slow",
    )


# ---------------------------------------------------------------------------
# _load_prompts / invalidate_prompts_cache
# ---------------------------------------------------------------------------

class TestLoadPrompts:
    def test_loads_real_prompts_and_caches(self):
        """_load_prompts reads the real config/prompts.yaml and caches the result."""
        invalidate_prompts_cache()
        result = _load_prompts()
        assert "_system_rules" in result
        assert "requirement_extraction" in result
        result2 = _load_prompts()
        assert result2 is result  # cached

    def test_invalidate_clears_cache(self):
        invalidate_prompts_cache()
        result1 = _load_prompts()
        invalidate_prompts_cache()
        result2 = _load_prompts()
        assert result1 is not result2


# ---------------------------------------------------------------------------
# AnalysisService — unit tests
# ---------------------------------------------------------------------------

class TestInit:
    @pytest.mark.asyncio
    async def test_constructor(self, db_session):
        svc = AnalysisService(db_session)
        assert svc._db is db_session
        assert svc._vector_store is None


class TestBuildSystemPrompt:
    @pytest.mark.asyncio
    async def test_with_rules(self, db_session):
        svc = AnalysisService(db_session)
        prompts = {"_system_rules": "Rule: Be concise.", "requirement_extraction": "Extract"}
        with patch("needradar.services.analysis_service._load_prompts", return_value=prompts):
            result = svc._build_system_prompt("Task: extract")
            assert "Rule: Be concise." in result
            assert "Task: extract" in result

    @pytest.mark.asyncio
    async def test_without_rules(self, db_session):
        svc = AnalysisService(db_session)
        with patch("needradar.services.analysis_service._load_prompts", return_value={}):
            result = svc._build_system_prompt("Task: extract")
            assert result == "Task: extract"


class TestSafeFlush:
    @pytest.mark.asyncio
    async def test_flush_succeeds_first_try(self, db_session):
        svc = AnalysisService(db_session)
        await svc._safe_flush()

    @pytest.mark.asyncio
    async def test_retries_on_failure(self, db_session):
        svc = AnalysisService(db_session)
        call_count = [0]
        original_flush = db_session.flush

        async def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("transient")
            await original_flush()

        db_session.flush = flaky
        try:
            await svc._safe_flush()
            assert call_count[0] == 2
        finally:
            db_session.flush = original_flush

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, db_session):
        svc = AnalysisService(db_session)
        original_flush = db_session.flush

        async def always_fails():
            raise RuntimeError("persistent")

        db_session.flush = always_fails
        try:
            with pytest.raises(RuntimeError):
                await svc._safe_flush()
        finally:
            db_session.flush = original_flush


class TestLoadKnownUrls:
    @pytest.mark.asyncio
    async def test_empty_when_no_fingerprints(self, db_session):
        svc = AnalysisService(db_session)
        urls = await svc._load_known_urls("python", "github")
        assert urls == set()

    @pytest.mark.asyncio
    async def test_returns_known_urls(self, db_session):
        svc = AnalysisService(db_session)
        fp = CrawlFingerprint(keyword="python", platform="github", source_url="http://gh.com/1")
        db_session.add(fp)
        await db_session.flush()
        urls = await svc._load_known_urls("python", "github")
        assert urls == {"http://gh.com/1"}

    @pytest.mark.asyncio
    async def test_only_matches_keyword_and_platform(self, db_session):
        svc = AnalysisService(db_session)
        fp1 = CrawlFingerprint(keyword="python", platform="github", source_url="http://a.com")
        fp2 = CrawlFingerprint(keyword="rust", platform="github", source_url="http://b.com")
        db_session.add_all([fp1, fp2])
        await db_session.flush()
        urls = await svc._load_known_urls("python", "github")
        assert urls == {"http://a.com"}


class TestSaveFingerprints:
    @pytest.mark.asyncio
    async def test_saves_fingerprints(self, db_session):
        svc = AnalysisService(db_session)
        items = [
            RawDiscussionItem(platform="github", source_url="http://a.com", title="A", content="c"),
            RawDiscussionItem(platform="github", source_url="http://b.com", title="B", content="c"),
        ]
        await svc._save_fingerprints("python", "github", items)
        await db_session.flush()
        result = await db_session.execute(select(CrawlFingerprint))
        rows = result.scalars().all()
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_empty_items_no_error(self, db_session):
        svc = AnalysisService(db_session)
        await svc._save_fingerprints("python", "github", [])
        result = await db_session.execute(select(CrawlFingerprint))
        assert len(result.scalars().all()) == 0


class TestFilterNewItems:
    @pytest.mark.asyncio
    async def test_all_new(self, db_session, fake_item):
        svc = AnalysisService(db_session)
        new_items, skipped = await svc._filter_new_items("python", "github", [fake_item])
        assert len(new_items) == 1
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_all_known(self, db_session, fake_item):
        svc = AnalysisService(db_session)
        fp = CrawlFingerprint(keyword="python", platform="github", source_url=fake_item.source_url)
        db_session.add(fp)
        await db_session.flush()
        new_items, skipped = await svc._filter_new_items("python", "github", [fake_item])
        assert len(new_items) == 0
        assert skipped == 1

    @pytest.mark.asyncio
    async def test_mixed(self, db_session, fake_item):
        svc = AnalysisService(db_session)
        new_item = RawDiscussionItem(
            platform="github", source_url="http://github.com/new", title="New", content="c"
        )
        fp = CrawlFingerprint(keyword="python", platform="github", source_url=fake_item.source_url)
        db_session.add(fp)
        await db_session.flush()
        new_items, skipped = await svc._filter_new_items("python", "github", [fake_item, new_item])
        assert len(new_items) == 1
        assert new_items[0].source_url == "http://github.com/new"
        assert skipped == 1


class TestRecordUsage:
    @pytest.mark.asyncio
    async def test_none_does_nothing(self, db_session):
        svc = AnalysisService(db_session)
        with patch("needradar.services.analysis_service.llm") as mock_llm:
            mock_llm.pop_last_usage.return_value = None
            svc._record_usage()

    @pytest.mark.asyncio
    async def test_records_usage_row(self, db_session):
        svc = AnalysisService(db_session)
        usage_data = {
            "preset_id": "deepseek-v4-pro",
            "model": "openai/deepseek-v4-pro",
            "call_type": "extract",
            "input_tokens": 100,
            "output_tokens": 50,
            "cached_tokens": 0,
            "total_tokens": 150,
            "cost_cny": 0.00035,
        }
        with patch("needradar.services.analysis_service.llm") as mock_llm:
            mock_llm.pop_last_usage.return_value = usage_data
            svc._record_usage()
        await svc._db.flush()


# ---------------------------------------------------------------------------
# extract_and_store
# ---------------------------------------------------------------------------

class TestExtractAndStore:
    @pytest.mark.asyncio
    async def test_new_requirement_stored(self, db_session, fake_item, fake_extracted):
        svc = AnalysisService(db_session)
        mock_vs = MagicMock()
        mock_vs.query = AsyncMock(return_value=[])
        mock_vs.add = AsyncMock()

        with patch("needradar.services.analysis_service._load_prompts") as mp, \
             patch("needradar.services.analysis_service.llm") as ml, \
             patch("needradar.services.analysis_service.vault") as mv, \
             patch.object(svc, "_get_vector_store", return_value=mock_vs):
            mp.return_value = {"_system_rules": "R", "requirement_extraction": "E"}
            ml.extract_structured = AsyncMock(return_value=fake_extracted)
            ml.pop_last_usage.return_value = None
            mv.write.return_value = __import__("pathlib").Path("/v/file.md")

            result = await svc.extract_and_store("python", fake_item)
            assert result is not None
            ml.extract_structured.assert_called_once()
            mv.write.assert_called_once()
            mock_vs.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_dedup_skips_storage(self, db_session, fake_item, fake_extracted):
        svc = AnalysisService(db_session)
        from needradar.vector.base import SearchResult
        mock_vs = MagicMock()
        mock_vs.query = AsyncMock(return_value=[SearchResult(id="Existing", score=0.95)])

        with patch("needradar.services.analysis_service._load_prompts") as mp, \
             patch("needradar.services.analysis_service.llm") as ml, \
             patch("needradar.services.analysis_service.vault") as mv, \
             patch("needradar.services.analysis_service.settings") as ms, \
             patch.object(svc, "_get_vector_store", return_value=mock_vs):
            mp.return_value = {"_system_rules": "", "requirement_extraction": "E"}
            ml.extract_structured = AsyncMock(return_value=fake_extracted)
            ml.pop_last_usage.return_value = None
            ms.similarity_threshold = 0.8
            mv.find_by_title.return_value = __import__("pathlib").Path("/v/existing.md")
            mv.read.return_value = ({"提及次数": 1, "相似来源": []}, "body")

            result = await svc.extract_and_store("python", fake_item)
            assert result is None
            mv.update_frontmatter.assert_called_once()
            mv.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_title_fallback_when_vector_fails(self, db_session, fake_item, fake_extracted):
        svc = AnalysisService(db_session)
        mock_vs = MagicMock()
        mock_vs.query = AsyncMock(side_effect=RuntimeError("Vector store down"))

        with patch("needradar.services.analysis_service._load_prompts") as mp, \
             patch("needradar.services.analysis_service.llm") as ml, \
             patch("needradar.services.analysis_service.vault") as mv, \
             patch.object(svc, "_get_vector_store", return_value=mock_vs):
            mp.return_value = {"_system_rules": "", "requirement_extraction": "E"}
            ml.extract_structured = AsyncMock(return_value=fake_extracted)
            ml.pop_last_usage.return_value = None
            mv.find_by_title.return_value = __import__("pathlib").Path("/v/existing.md")
            mv.read.return_value = ({"提及次数": 1}, "body")

            result = await svc.extract_and_store("python", fake_item)
            assert result is None
            mv.update_frontmatter.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_add_failure_non_fatal(self, db_session, fake_item, fake_extracted):
        svc = AnalysisService(db_session)
        mock_vs = MagicMock()
        mock_vs.query = AsyncMock(return_value=[])
        mock_vs.add = AsyncMock(side_effect=RuntimeError("add failed"))

        with patch("needradar.services.analysis_service._load_prompts") as mp, \
             patch("needradar.services.analysis_service.llm") as ml, \
             patch("needradar.services.analysis_service.vault") as mv, \
             patch.object(svc, "_get_vector_store", return_value=mock_vs):
            mp.return_value = {"_system_rules": "", "requirement_extraction": "E"}
            ml.extract_structured = AsyncMock(return_value=fake_extracted)
            ml.pop_last_usage.return_value = None
            mv.write.return_value = __import__("pathlib").Path("/v/file.md")

            result = await svc.extract_and_store("python", fake_item)
            assert result is not None  # vault store succeeded despite vector failure
            mv.write.assert_called_once()


# ---------------------------------------------------------------------------
# run_pipeline
# ---------------------------------------------------------------------------

class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_creates_tasks(self, db_session):
        svc = AnalysisService(db_session)
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(return_value=[])
        mock_crawler.close = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc:
            mc.return_value = mock_crawler
            tasks = await svc.run_pipeline("python", ["github"])
            assert len(tasks) == 1
            assert tasks[0].keyword == "python"
            assert tasks[0].platform == "github"
            assert tasks[0].status == TaskStatus.COMPLETED  # empty crawl completes

    @pytest.mark.asyncio
    async def test_multi_platform(self, db_session, fake_item, fake_extracted):
        svc = AnalysisService(db_session)
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(return_value=[fake_item])
        mock_crawler.close = AsyncMock()
        mock_vs = MagicMock()
        mock_vs.query = AsyncMock(return_value=[])
        mock_vs.add = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc, \
             patch("needradar.services.analysis_service._load_prompts") as mp, \
             patch("needradar.services.analysis_service.llm") as ml, \
             patch("needradar.services.analysis_service.vault") as mv, \
             patch.object(svc, "_get_vector_store", return_value=mock_vs):
            mc.return_value = mock_crawler
            mp.return_value = {"_system_rules": "", "requirement_extraction": "E"}
            ml.extract_structured = AsyncMock(return_value=fake_extracted)
            ml.pop_last_usage.return_value = None
            mv.write.return_value = __import__("pathlib").Path("/v/f.md")

            tasks = await svc.run_pipeline("python", ["github", "stackoverflow"])
            assert len(tasks) == 2
            assert all(t.status == TaskStatus.COMPLETED for t in tasks)

    @pytest.mark.asyncio
    async def test_crawl_timeout_marks_failed(self, db_session):
        svc = AnalysisService(db_session)
        import asyncio
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_crawler.close = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc:
            mc.return_value = mock_crawler
            tasks = await svc.run_pipeline("python", ["github"])
            assert tasks[0].status == TaskStatus.FAILED
            assert "超时" in (tasks[0].error_message or "")

    @pytest.mark.asyncio
    async def test_crawl_exception_marks_failed(self, db_session):
        svc = AnalysisService(db_session)
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(side_effect=ValueError("API rate limited"))
        mock_crawler.close = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc:
            mc.return_value = mock_crawler
            tasks = await svc.run_pipeline("python", ["github"])
            assert tasks[0].status == TaskStatus.FAILED
            assert "API rate limited" in (tasks[0].error_message or "")

    @pytest.mark.asyncio
    async def test_full_extraction_flow(self, db_session, fake_item, fake_extracted):
        svc = AnalysisService(db_session)
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(return_value=[fake_item])
        mock_crawler.close = AsyncMock()
        mock_vs = MagicMock()
        mock_vs.query = AsyncMock(return_value=[])
        mock_vs.add = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc, \
             patch("needradar.services.analysis_service._load_prompts") as mp, \
             patch("needradar.services.analysis_service.llm") as ml, \
             patch("needradar.services.analysis_service.vault") as mv, \
             patch.object(svc, "_get_vector_store", return_value=mock_vs):
            mc.return_value = mock_crawler
            mp.return_value = {"_system_rules": "", "requirement_extraction": "E"}
            ml.extract_structured = AsyncMock(return_value=fake_extracted)
            ml.pop_last_usage.return_value = None
            mv.write.return_value = __import__("pathlib").Path("/v/f.md")

            tasks = await svc.run_pipeline("python", ["github"])
            assert tasks[0].status == TaskStatus.COMPLETED
            assert tasks[0].total_items == 1
            assert tasks[0].new_items == 1

    @pytest.mark.asyncio
    async def test_closes_crawlers(self, db_session):
        svc = AnalysisService(db_session)
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(return_value=[])
        mock_crawler.close = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc:
            mc.return_value = mock_crawler
            await svc.run_pipeline("python", ["github"])
            mock_crawler.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_error_silent(self, db_session):
        svc = AnalysisService(db_session)
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(return_value=[])
        mock_crawler.close = AsyncMock(side_effect=RuntimeError("close err"))

        with patch("needradar.services.analysis_service.create_crawler") as mc:
            mc.return_value = mock_crawler
            tasks = await svc.run_pipeline("python", ["github"])
            assert tasks[0].status == TaskStatus.COMPLETED  # empty crawl completes
            mock_crawler.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_resumes_existing_tasks(self, db_session):
        svc = AnalysisService(db_session)
        task = CrawlTask(keyword="python", platform="github", status=TaskStatus.PENDING)
        db_session.add(task)
        await db_session.flush()
        tid = task.id

        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(return_value=[])
        mock_crawler.close = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc:
            mc.return_value = mock_crawler
            tasks = await svc.run_pipeline("python", ["github"], existing_task_ids=[tid])
            assert len(tasks) == 1
            assert tasks[0].id == tid

    @pytest.mark.asyncio
    async def test_skips_failed_in_extraction(self, db_session):
        svc = AnalysisService(db_session)
        import asyncio
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_crawler.close = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc:
            mc.return_value = mock_crawler
            tasks = await svc.run_pipeline("python", ["github"])
            assert tasks[0].status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_item_extract_error_non_fatal(self, db_session, fake_item):
        svc = AnalysisService(db_session)
        mock_crawler = MagicMock()
        mock_crawler.crawl = AsyncMock(return_value=[fake_item])
        mock_crawler.close = AsyncMock()

        with patch("needradar.services.analysis_service.create_crawler") as mc, \
             patch("needradar.services.analysis_service._load_prompts") as mp, \
             patch("needradar.services.analysis_service.llm") as ml:
            mc.return_value = mock_crawler
            mp.return_value = {"_system_rules": "", "requirement_extraction": "E"}
            ml.extract_structured = AsyncMock(side_effect=ValueError("parse error"))

            tasks = await svc.run_pipeline("python", ["github"])
            # Task completes but item was skipped
            assert tasks[0].status == TaskStatus.COMPLETED


class TestGetVectorStore:
    @pytest.mark.asyncio
    async def test_creates_once(self, db_session):
        svc = AnalysisService(db_session)
        # create_vector_store is imported locally inside _get_vector_store()
        with patch("needradar.vector.create_vector_store") as mc:
            mc.return_value = MagicMock()
            vs1 = svc._get_vector_store()
            vs2 = svc._get_vector_store()
            assert vs1 is vs2
            mc.assert_called_once()
