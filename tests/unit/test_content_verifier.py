"""Tests for ContentVerifier — hallucination detection and content verification."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from needradar.services.content_verifier import (
    PLATFORM_RELIABILITY,
    Claim,
    ContentVerifier,
    get_verifier,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def verifier():
    return ContentVerifier()


@pytest.fixture
def sample_claims():
    return [
        Claim(text="Python is the most popular language", section="核心发现",
              verdict="supported", confidence=0.9, evidence="Survey data confirms"),
        Claim(text="99% of developers use AI", section="核心发现",
              verdict="hallucination", confidence=0.2, evidence="No source"),
        Claim(text="Need better tooling", section="用户痛点",
              verdict="partially", confidence=0.6, evidence="Partial support"),
        Claim(text="Market is growing", section="机会",
              verdict="unverifiable", confidence=0.3, evidence=""),
    ]


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestTextOverlap:
    def test_identical_strings(self):
        assert ContentVerifier._text_overlap("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert ContentVerifier._text_overlap("abc", "xyz") == 0.0

    def test_partial_overlap(self):
        result = ContentVerifier._text_overlap("hello", "help")
        assert 0.0 < result < 1.0

    def test_empty_strings(self):
        assert ContentVerifier._text_overlap("", "hello") == 0.0
        assert ContentVerifier._text_overlap("hello", "") == 0.0
        assert ContentVerifier._text_overlap("", "") == 0.0


class TestRuleBasedClaims:
    def test_extracts_bold_claims(self):
        body = "1. **Python dominates AI development** and is growing.\n2. **Need better async support in frameworks**."
        claims = ContentVerifier()._rule_based_claims(body)
        assert len(claims) == 2
        assert claims[0].text == "Python dominates AI development"
        assert claims[0].section == "核心发现"

    def test_no_bold_claims(self):
        body = "Just plain text without any bold formatting."
        claims = ContentVerifier()._rule_based_claims(body)
        assert len(claims) == 0

    def test_dedup_identical(self):
        body = "1. **Same claim here**\n2. **Same claim here**"
        claims = ContentVerifier()._rule_based_claims(body)
        assert len(claims) == 1

    def test_skips_short_claims(self):
        body = "1. **abc**"
        claims = ContentVerifier()._rule_based_claims(body)
        assert len(claims) == 0


class TestDeduplicateClaims:
    def test_no_duplicates(self, verifier):
        claims = [Claim(text="Unique A"), Claim(text="Unique B")]
        result = verifier._deduplicate_claims(claims)
        assert len(result) == 2

    def test_removes_similar(self, verifier):
        claims = [
            Claim(text="Python is great for AI development"),
            Claim(text="Python is great for AI development!"),
        ]
        result = verifier._deduplicate_claims(claims)
        assert len(result) == 1

    def test_keeps_different(self, verifier):
        claims = [Claim(text="Python for AI"), Claim(text="Rust for systems")]
        result = verifier._deduplicate_claims(claims)
        assert len(result) == 2


class TestAssessSourceReliability:
    def test_no_sources(self, verifier):
        assert verifier._assess_source_reliability([], {}) == 30.0

    def test_single_github_source(self, verifier):
        sources = [{"platform": "github", "sentiment": "strong"}]
        score = verifier._assess_source_reliability(sources, {})
        assert score > 50

    def test_multi_platform_diversity(self, verifier):
        sources = [
            {"platform": "github", "sentiment": "strong"},
            {"platform": "stackoverflow", "sentiment": "moderate"},
            {"platform": "juejin", "sentiment": "mild"},
        ]
        score = verifier._assess_source_reliability(sources, {})
        assert 0 <= score <= 100

    def test_unknown_platform_penalty(self, verifier):
        sources = [{"platform": "unknown", "sentiment": "moderate"}]
        score = verifier._assess_source_reliability(sources, {})
        assert score < 60

    def test_volume_bonus(self, verifier):
        few = [{"platform": "github", "sentiment": "strong"}]
        many = [{"platform": "github", "sentiment": "strong"} for _ in range(10)]
        assert verifier._assess_source_reliability(many, {}) > verifier._assess_source_reliability(few, {})


class TestAggregate:
    def test_no_claims(self, verifier):
        output = verifier._aggregate([], 80.0, 70.0)
        assert output.fact_check_score == 50.0
        assert output.hallucination_count == 0

    def test_with_claims(self, verifier, sample_claims):
        output = verifier._aggregate(sample_claims, 80.0, 70.0)
        assert output.hallucination_count == 1
        assert output.flagged_count == 1
        assert output.consistency_score == 80.0
        assert output.source_reliability_score == 70.0

    def test_overall_score_formula(self, verifier):
        c = Claim(text="T", verdict="supported", confidence=1.0)
        output = verifier._aggregate([c], 100.0, 100.0)
        assert output.overall_score == 100.0

    def test_hallucination_gets_zero(self, verifier):
        c = Claim(text="Fake", verdict="hallucination", confidence=0.0)
        output = verifier._aggregate([c], 100.0, 100.0)
        assert output.fact_check_score == 50.0


class TestGenerateSuggestions:
    def test_hallucination_correction(self, verifier):
        claims = [Claim(text="Fake", verdict="hallucination", evidence="No source")]
        suggestions = verifier._generate_suggestions(claims)
        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "correction"

    def test_partially_review(self, verifier):
        claims = [Claim(text="Partial", verdict="partially", evidence="Weak")]
        suggestions = verifier._generate_suggestions(claims)
        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "review"

    def test_supported_no_suggestion(self, verifier):
        claims = [Claim(text="Good", verdict="supported")]
        assert verifier._generate_suggestions(claims) == []

    def test_contradicted_correction(self, verifier):
        claims = [Claim(text="Wrong", verdict="contradicted")]
        suggestions = verifier._generate_suggestions(claims)
        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "correction"


class TestPopUsage:
    def test_none_when_no_usage(self, verifier):
        with patch("needradar.services.content_verifier.llm") as ml:
            ml.pop_last_usage.return_value = None
            verifier._pop_usage()
            assert verifier._usage_records == []

    def test_records_usage(self, verifier):
        usage = {"preset_id": "test", "input_tokens": 10}
        with patch("needradar.services.content_verifier.llm") as ml:
            ml.pop_last_usage.return_value = usage
            verifier._pop_usage()
            assert verifier._usage_records == [usage]


class TestGetVerifier:
    def test_returns_singleton(self):
        import needradar.services.content_verifier as mod
        mod._verifier = None
        v1 = get_verifier()
        v2 = get_verifier()
        assert v1 is v2
        mod._verifier = None


class TestPlatformReliability:
    def test_known_platforms(self):
        assert PLATFORM_RELIABILITY["github"] == 0.85
        assert PLATFORM_RELIABILITY["stackoverflow"] == 0.80
        assert PLATFORM_RELIABILITY["juejin"] == 0.70
        assert PLATFORM_RELIABILITY["unknown"] == 0.40


# ---------------------------------------------------------------------------
# _collect_sources
# ---------------------------------------------------------------------------

class TestCollectSources:
    def test_empty_refs(self, verifier):
        assert verifier._collect_sources({"关联需求": []}) == []

    def test_collects_from_vault(self, verifier):
        meta = {"关联需求": ["[[02-需求池/Need1|Need1]]"]}
        with patch("needradar.services.content_verifier.vault") as mv:
            mv.find_by_title.return_value = __import__("pathlib").Path("/v/Need1.md")
            mv.read.return_value = (
                {"标题": "Need1", "来源平台": "github", "情感倾向": "strong"},
                "source body",
            )
            sources = verifier._collect_sources(meta)
            assert len(sources) == 1
            assert sources[0]["title"] == "Need1"
            assert sources[0]["platform"] == "github"

    def test_skips_missing_needs(self, verifier):
        meta = {"关联需求": ["[[02-需求池/Missing|Missing]]"]}
        with patch("needradar.services.content_verifier.vault") as mv:
            mv.find_by_title.return_value = None
            assert verifier._collect_sources(meta) == []


# ---------------------------------------------------------------------------
# verify_report
# ---------------------------------------------------------------------------

class TestVerifyReport:
    @pytest.mark.asyncio
    async def test_not_found(self, verifier):
        with patch("needradar.services.content_verifier.vault") as mv:
            mv.find_by_title.return_value = None
            result = await verifier.verify_report("Nonexistent")
            assert result.overall_score == 0.0
            assert result.claims == []

    @pytest.mark.asyncio
    async def test_full_flow(self, verifier):
        report_body = "## 核心发现\n\n1. **Python dominates AI** surveys show.\n\n## 用户痛点深度分析\n\nDevs need better tooling.\n\n## 机会与建议\n\nAI market grows 25% annually."

        with patch("needradar.services.content_verifier.vault") as mv, \
             patch("needradar.services.content_verifier.llm") as ml:

            # vault: report + source need
            mv.find_by_title.side_effect = lambda stage, title: (
                __import__("pathlib").Path("/v/report.md") if stage == "初稿"
                else __import__("pathlib").Path(f"/v/{title}.md")
            )
            mv.read.side_effect = [
                ({"关联需求": ["[[02-需求池/Need1|Need1]]"]}, report_body),
                ({"标题": "Need1", "来源平台": "github", "情感倾向": "strong"}, "body"),
            ]

            # LLM responses for 3 steps
            claim_json = json.dumps([
                {"text": "Python dominates AI", "section": "核心发现"},
                {"text": "AI market grows 25% annually", "section": "机会与建议"},
            ])
            fact_json = json.dumps([
                {"idx": 1, "verdict": "supported", "confidence": 0.9, "evidence": "Confirmed", "flags": []},
                {"idx": 2, "verdict": "partially", "confidence": 0.7, "evidence": "Rate varies", "flags": ["exaggerated"]},
            ])
            consistency_json = json.dumps({"consistent": True, "score": 95, "issues": []})

            ml.pop_last_usage.return_value = None
            ml.complete = AsyncMock(side_effect=[claim_json, fact_json, consistency_json])

            result = await verifier.verify_report("Test Report")
            assert result.overall_score > 0
            assert len(result.claims) == 2
            assert result.hallucination_count == 0
