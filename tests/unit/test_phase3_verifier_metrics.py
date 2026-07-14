from __future__ import annotations

import pytest

from needradar.services.phase3_verifier_metrics import _average_precision, compose_score, score_verifier_predictions


def test_compose_score_renormalizes_available_components():
    assert compose_score(80.0, None, None) == 80.0
    assert compose_score(80.0, 50.0, None) == pytest.approx((80 * 0.45 + 50 * 0.30) / 0.75)
    assert compose_score(None, 90.0, 70.0) is None


def test_average_precision_is_invariant_to_tie_order():
    assert _average_precision([True, False], [0.5, 0.5]) == 0.5
    assert _average_precision([False, True], [0.5, 0.5]) == 0.5


def test_scores_claims_verdicts_sources_consistency_ranking_and_suggestions():
    inputs = [
        {"id": "clean", "report_meta": {"source_ids": ["s1", "s2"]}},
        {"id": "flagged", "report_meta": {"source_ids": ["s3"]}},
    ]
    gold = [
        {
            "id": "clean",
            "flagged": False,
            "internal_contradiction": False,
            "claims": [
                {
                    "claim_id": "c1",
                    "start": 100,
                    "verdict": "supported",
                    "needs_correction": False,
                },
                {
                    "claim_id": "c2",
                    "start": 5000,
                    "verdict": "partially",
                    "needs_correction": True,
                },
            ],
        },
        {
            "id": "flagged",
            "flagged": True,
            "internal_contradiction": True,
            "claims": [
                {
                    "claim_id": "c3",
                    "start": 50,
                    "verdict": "hallucination",
                    "needs_correction": True,
                }
            ],
        },
    ]
    predictions = [
        {
            "id": "clean",
            "claims": [
                {"claim_id": "c1", "verdict": "supported"},
                {"claim_id": "c2", "verdict": "supported"},
            ],
            "resolved_source_ids": ["s1"],
            "internal_contradiction": False,
            "overall_score": 90.0,
            "suggestions": [],
        },
        {
            "id": "flagged",
            "claims": [
                {"claim_id": "c3", "verdict": "hallucination"},
                {"claim_id": "extra", "verdict": "contradicted"},
            ],
            "resolved_source_ids": ["s3"],
            "internal_contradiction": True,
            "overall_score": 20.0,
            "suggestions": [{"claim_id": "c3"}],
        },
    ]

    metrics = score_verifier_predictions(inputs, gold, predictions)

    assert metrics["claim_extraction"] == {
        "precision": 0.75,
        "recall": 1.0,
        "f1": pytest.approx(0.8571428571428571),
        "duplicate_rate": 0.0,
        "tail_recall": 1.0,
    }
    assert metrics["source_resolution"]["recall"] == 2 / 3
    assert metrics["verdicts"]["hallucination"]["precision"] == 1.0
    assert metrics["verdicts"]["hallucination"]["recall"] == 1.0
    assert metrics["consistency"]["f1"] == 1.0
    assert metrics["ranking"] == {"records": 2, "auroc": 1.0, "average_precision": 1.0}
    assert metrics["suggestions"]["precision"] == 1.0
    assert metrics["suggestions"]["recall"] == 0.5
