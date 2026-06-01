"""Unit tests for OpportunityScorer — heuristic scoring, clustering, traction."""

from unittest.mock import AsyncMock, patch

import pytest
from needradar.services.opportunity_scorer import OpportunityScorer


@pytest.fixture
async def scorer(db_session):
    return OpportunityScorer(db_session)


class TestHeuristicScore:
    @pytest.mark.asyncio
    async def test_web_app_scores_85(self, scorer):
        s = scorer._heuristic_score(["Web Dashboard for AI tools"])
        assert s.vibe_code_suitability == 85.0
        assert s.overall > 50

    @pytest.mark.asyncio
    async def test_cli_scores_75(self, scorer):
        s = scorer._heuristic_score(["CLI tool for automation"])
        assert s.vibe_code_suitability == 75.0

    @pytest.mark.asyncio
    async def test_mobile_scores_50(self, scorer):
        s = scorer._heuristic_score(["iOS app for developers"])
        assert s.vibe_code_suitability == 50.0

    @pytest.mark.asyncio
    async def test_system_scores_20(self, scorer):
        s = scorer._heuristic_score(["Kernel module for linux"])
        assert s.vibe_code_suitability == 20.0

    @pytest.mark.asyncio
    async def test_generic_defaults_60(self, scorer):
        s = scorer._heuristic_score(["Some random tool"])
        assert s.vibe_code_suitability == 60.0

    @pytest.mark.asyncio
    async def test_demand_scales_with_count(self, scorer):
        small = scorer._heuristic_score(["A"])
        large = scorer._heuristic_score(["A"] * 10)
        assert large.demand_intensity > small.demand_intensity


class TestClustering:
    @pytest.mark.asyncio
    async def test_one_cluster_for_few(self, scorer):
        reqs = [{"标题": "A"}, {"标题": "B"}, {"标题": "C"}]
        clusters = scorer._cluster(reqs)
        assert len(clusters) == 1

    @pytest.mark.asyncio
    async def test_empty(self, scorer):
        assert scorer._cluster([]) == []

    @pytest.mark.asyncio
    async def test_groups_by_overlap(self, scorer):
        reqs = [{"标题": "AI code review"}, {"标题": "AI review tool"},
                {"标题": "Weather app"}, {"标题": "AI code analysis"}]
        clusters = scorer._cluster(reqs)
        assert len(clusters) <= 3


class TestBuildTraction:
    @pytest.mark.asyncio
    async def test_groups_by_platform(self, scorer):
        cluster = [{"标题": "X", "来源平台": "github", "情感倾向": "strong"},
                   {"标题": "Y", "来源平台": "github", "情感倾向": "moderate"},
                   {"标题": "Z", "来源平台": "stackoverflow", "情感倾向": "mild"}]
        traction = scorer._build_traction(cluster)
        sources = {t.source for t in traction}
        assert sources == {"github", "stackoverflow"}
        gh = next(t for t in traction if t.source == "github")
        assert gh.mention_count == 2
        assert gh.sentiment_strength == 0.8


class TestList:
    @pytest.mark.asyncio
    async def test_empty(self, db_session):
        scorer = OpportunityScorer(db_session)
        rows, total = await scorer.list_opportunities()
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, scorer):
        assert await scorer.get_opportunity(99999) is None


class TestLLMScore:
    @pytest.mark.asyncio
    async def test_fallback_no_prompt(self, scorer):
        with patch("needradar.services.opportunity_scorer._load_prompts", return_value={}):
            s = await scorer._llm_score(["Web App"], ["desc"])
        assert s.overall > 0
