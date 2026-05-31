"""Tests for PromptOptimizer — iterative prompt improvement."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from needradar.schemas.schemas import (
    EmotionEnum,
    ExtractedRequirement,
    SentimentEnum,
)
from needradar.services.prompt_optimizer import (
    IterationResult,
    OptimizationRun,
    PromptOptimizer,
    TestCaseResult,
    _evaluate_single,
    _keyword_overlap,
    _load_prompts,
    _load_test_cases,
    _save_requirement_prompt,
)


# ---------------------------------------------------------------------------
# _keyword_overlap
# ---------------------------------------------------------------------------

class TestKeywordOverlap:
    def test_empty_keywords_returns_one(self):
        assert _keyword_overlap([], "any text") == 1.0

    def test_all_match(self):
        assert _keyword_overlap(["python", "async"], "python async programming") == 1.0

    def test_partial_match(self):
        result = _keyword_overlap(["python", "rust"], "python programming")
        assert result == 0.5

    def test_no_match(self):
        assert _keyword_overlap(["rust"], "python programming") == 0.0

    def test_case_insensitive(self):
        assert _keyword_overlap(["PYTHON"], "Python Programming") == 1.0


# ---------------------------------------------------------------------------
# _evaluate_single
# ---------------------------------------------------------------------------

class TestEvaluateSingle:
    def test_perfect_match(self):
        extracted = ExtractedRequirement(
            title="AI Code Review Tool",
            description="Need AI review",
            sentiment=SentimentEnum.STRONG,
            emotion=EmotionEnum.NEGATIVE,
            confidence=0.85,
            pain_point="Manual review is slow",
            use_case="Team code review in GitLab",
        )
        expected = {
            "id": "test_1",
            "title_keywords": ["AI", "Code", "Review"],
            "sentiment": "strong",
            "emotion": "negative",
            "confidence_min": 0.7,
            "confidence_max": 1.0,
            "pain_point_keywords": ["manual", "review", "slow"],
            "use_case_keywords": ["team", "GitLab"],
        }
        result = _evaluate_single(extracted, expected)
        assert result.passed is True
        assert result.score > 0.9

    def test_sentiment_mismatch(self):
        extracted = ExtractedRequirement(
            title="Something", description="Desc",
            sentiment=SentimentEnum.MILD, emotion=EmotionEnum.NEUTRAL, confidence=0.5,
        )
        expected = {"sentiment": "strong", "emotion": "neutral"}
        result = _evaluate_single(extracted, expected)
        assert result.score < 0.8
        assert result.details["sentiment"]["ok"] is False

    def test_confidence_out_of_range(self):
        extracted = ExtractedRequirement(
            title="Something", description="Desc",
            sentiment=SentimentEnum.STRONG, emotion=EmotionEnum.NEUTRAL, confidence=0.1,
        )
        expected = {"sentiment": "strong", "emotion": "neutral",
                    "confidence_min": 0.7, "confidence_max": 1.0}
        result = _evaluate_single(extracted, expected)
        assert result.details["confidence"]["ok"] is False

    def test_passed_threshold(self):
        extracted = ExtractedRequirement(
            title="AI Tool", description="Desc",
            sentiment=SentimentEnum.STRONG, emotion=EmotionEnum.NEUTRAL, confidence=0.5,
        )
        expected = {"title_keywords": ["AI"], "sentiment": "strong", "emotion": "neutral"}
        result = _evaluate_single(extracted, expected)
        assert result.passed is True


# ---------------------------------------------------------------------------
# _load_test_cases / _load_prompts
# ---------------------------------------------------------------------------

class TestLoadTestCases:
    def test_loads_real_cases(self):
        cases = _load_test_cases()
        assert isinstance(cases, list)
        assert len(cases) > 0
        for tc in cases:
            assert "id" in tc
            assert "input" in tc
            assert "expected" in tc


class TestLoadPrompts:
    def test_loads_real_prompts(self):
        prompts = _load_prompts()
        assert "requirement_extraction" in prompts


# ---------------------------------------------------------------------------
# _save_requirement_prompt
# ---------------------------------------------------------------------------

class TestSaveRequirementPrompt:
    def test_saves_and_preserves_other_keys(self, tmp_path):
        import needradar.services.prompt_optimizer as mod
        original_path = mod.PROMPTS_PATH
        test_file = tmp_path / "prompts.yaml"
        test_file.write_text("requirement_extraction: |\n  old content\n\nother_key: value\n")
        mod.PROMPTS_PATH = test_file
        try:
            _save_requirement_prompt("new\nimproved\nprompt")
            content = test_file.read_text()
            assert "new" in content
            assert "improved" in content
            assert "other_key" in content
        finally:
            mod.PROMPTS_PATH = original_path


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestOptimizationRun:
    def test_defaults(self):
        run = OptimizationRun()
        assert run.status == "idle"
        assert run.baseline_score == 0.0
        assert run.iterations == []


class TestIterationResult:
    def test_defaults(self):
        it = IterationResult(iteration=0, prompt_version="baseline", score=0.75, passed=3, total=5)
        assert it.improved is False
        assert it.prompt_diff == ""


class TestTestCaseResult:
    def test_defaults(self):
        r = TestCaseResult(test_id="t1", passed=True, score=0.9)
        assert r.details == {}
        assert r.extracted is None


# ---------------------------------------------------------------------------
# PromptOptimizer — status / get_results
# ---------------------------------------------------------------------------

class TestPromptOptimizerStatus:
    def test_initial_idle(self):
        opt = PromptOptimizer()
        assert opt.status["status"] == "idle"

    def test_reflects_state(self):
        opt = PromptOptimizer()
        opt._run.status = "running"
        opt._run.current_iteration = 3
        opt._run.baseline_score = 0.75
        opt._run.best_score = 0.82
        assert opt.status["status"] == "running"
        assert opt.status["current_iteration"] == 3


class TestPromptOptimizerGetResults:
    def test_empty(self):
        opt = PromptOptimizer()
        results = opt.get_results()
        assert results["status"] == "idle"
        assert results["iterations"] == []
        assert results["best_prompt"] is None

    def test_with_iterations(self):
        opt = PromptOptimizer()
        tr = TestCaseResult(test_id="t1", passed=True, score=0.9)
        it = IterationResult(iteration=1, prompt_version="v1", score=0.85,
                           passed=4, total=5, results=[tr], improved=True)
        opt._run.iterations = [it]
        opt._run.best_score = 0.85
        opt._run.best_prompt = "improved"
        results = opt.get_results()
        assert len(results["iterations"]) == 1
        assert results["best_prompt"] == "improved"


# ---------------------------------------------------------------------------
# PromptOptimizer — start / stop
# ---------------------------------------------------------------------------

class TestPromptOptimizerStartStop:
    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        opt = PromptOptimizer()
        result = opt.start(max_iterations=3, patience=2, num_candidates=1)
        assert result is True
        assert opt._run.status == "running"
        opt.stop()

    def test_start_rejects_when_running(self):
        opt = PromptOptimizer()
        opt._run.status = "running"
        assert opt.start() is False

    @pytest.mark.asyncio
    async def test_caps_candidates(self):
        opt = PromptOptimizer()
        opt.start(max_iterations=1, patience=1, num_candidates=100)
        assert opt._run.num_candidates == 10
        opt.stop()

    def test_stop_cancels_task(self):
        opt = PromptOptimizer()
        opt._task = MagicMock()
        opt._task.done.return_value = False
        opt.stop()
        opt._task.cancel.assert_called_once()
        assert opt._run.status == "stopped"


# ---------------------------------------------------------------------------
# _propose_improvement
# ---------------------------------------------------------------------------

class TestProposeImprovement:
    @pytest.mark.asyncio
    async def test_returns_improved_prompt(self):
        opt = PromptOptimizer()
        tr = TestCaseResult(test_id="t1", passed=False, score=0.3,
                          details={"sentiment": {"ok": False}})
        last_iter = IterationResult(iteration=0, prompt_version="baseline",
                                   score=0.5, passed=0, total=1, results=[tr])
        improved = json.dumps({
            "title": "t", "description": "d", "sentiment": "s",
            "emotion": "e", "confidence": 0.5, "use_case": "u", "pain_point": "p",
        })
        with patch("needradar.services.prompt_optimizer.llm") as ml:
            ml.complete = AsyncMock(return_value=improved)
            result = await opt._propose_improvement("current", last_iter)
            assert result == improved

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_failure(self):
        opt = PromptOptimizer()
        tr = TestCaseResult(test_id="t1", passed=False, score=0.3)
        last_iter = IterationResult(iteration=0, prompt_version="baseline",
                                   score=0.5, passed=0, total=1, results=[tr])
        with patch("needradar.services.prompt_optimizer.llm") as ml:
            ml.complete = AsyncMock(side_effect=RuntimeError("API error"))
            result = await opt._propose_improvement("current", last_iter)
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_fields(self):
        opt = PromptOptimizer()
        tr = TestCaseResult(test_id="t1", passed=False, score=0.3)
        last_iter = IterationResult(iteration=0, prompt_version="baseline",
                                   score=0.5, passed=0, total=1, results=[tr])
        with patch("needradar.services.prompt_optimizer.llm") as ml:
            ml.complete = AsyncMock(return_value='{"title": "only one"}')
            result = await opt._propose_improvement("current", last_iter)
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self):
        opt = PromptOptimizer()
        tr = TestCaseResult(test_id="t1", passed=False, score=0.3)
        last_iter = IterationResult(iteration=0, prompt_version="baseline",
                                   score=0.5, passed=0, total=1, results=[tr])
        with patch("needradar.services.prompt_optimizer.llm") as ml:
            ml.complete = AsyncMock(return_value="not json")
            result = await opt._propose_improvement("current", last_iter)
            assert result is None

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self):
        opt = PromptOptimizer()
        tr = TestCaseResult(test_id="t1", passed=True, score=1.0)
        last_iter = IterationResult(iteration=0, prompt_version="baseline",
                                   score=1.0, passed=1, total=1, results=[tr])
        valid = json.dumps({
            "title": "T", "description": "D", "sentiment": "S",
            "emotion": "E", "confidence": 0.5, "use_case": "U", "pain_point": "P",
        })
        with patch("needradar.services.prompt_optimizer.llm") as ml:
            ml.complete = AsyncMock(return_value=f"```json\n{valid}\n```")
            result = await opt._propose_improvement("current", last_iter)
            assert result == valid
