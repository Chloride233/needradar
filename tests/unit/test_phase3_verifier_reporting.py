from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from needradar.services.phase3_verifier_reporting import build_failed_verifier_audit, build_verifier_report

FROZEN_RUN_HASHES = {
    "predictions.jsonl": "08750c890c36836e3d6899bb1117ed6a458c7a5ffd259d43f5a9490e0155a098",
    "metrics.json": "0276ff9552b506bb9711adf901248ed0a735260b46a805fd9c30a94d5ca58a61",
    "run.json": "7587ac417a3917a9d52cf14e488d0e2237a8fa00001208a9cdf59815f941f4bf",
}
FROZEN_V2_HASHES = {
    "predictions.jsonl": "90d159dbf18094284c9987171cca5ad6ee7071973549147a63ee40aea729b9c4",
    "metrics.json": "269478bb8e0f7c42c841a04c6a6849c18f0842382254062b261bf7682a12f13b",
    "run.json": "28a812b8992ffd0b6a87ec05ed2c689c9d1d7aca5b8c2f6a7d271e18c0432bf5",
    "report.json": "acc7bcb9419fa10a78f3bd5bdf8d1915697ac7942ff483d501a38a1e774db329",
    "report.md": "f51ef8dfd09911dc0d4d2a71e76a6c00bae1171055ddbb1c22473495f4f7a904",
}


def test_failed_verifier_run_is_rejected_with_corrected_attempt_and_reuse_counts():
    report = build_failed_verifier_audit(
        Path("evaluation/phase3/verifier-runs/full"),
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
    )

    assert report["accepted"] is False
    assert report["stage_counts"]["claim_extraction"] == {"failed": 28, "success": 2}
    assert report["extraction"]["predicted_claims"]["llm_only"] == 0
    assert report["extraction"]["valid_llm_records"] == 0
    assert report["extraction"]["strata"]["naturalistic"]["hybrid_claims"] == 0
    assert report["diagnostic_rule_fallback_ranking"] == {
        "records": 15,
        "auroc": pytest.approx(0.48214285714285715),
        "average_precision": pytest.approx(0.5532360032360033),
    }
    assert report["cost_accounting"]["provider_attempts"] == 114
    assert report["cost_accounting"]["responses_with_usage"] == 113
    assert report["cost_accounting"]["structural_artifact_reuse_calls_saved"] == 450
    assert report["cost_accounting"]["stage_calls_skipped_for_empty_claims"] == 36


def test_failed_verifier_run_artifacts_remain_byte_exact():
    root = Path("evaluation/phase3/verifier-runs/full")
    for name, expected in FROZEN_RUN_HASHES.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected


def test_schema_v2_report_uses_paired_denominators_and_preserves_failures():
    report = build_verifier_report(
        Path("evaluation/phase3/verifier-runs/full-v2"),
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
    )

    assert report["status"] == "complete_with_stage_failures"
    assert report["paired_denominators"] == {
        "extraction": 29,
        "evidence": 23,
        "score_composition": 23,
    }
    assert (
        report["component_ablation"]["extraction"]["hybrid"]["f1"]
        > report["component_ablation"]["extraction"]["rule_only"]["f1"]
    )
    assert (
        report["component_ablation"]["score_composition"]["full_weighted"]["auroc"]
        < report["component_ablation"]["score_composition"]["fact_only"]["auroc"]
    )
    assert len(report["failure_cases"]) == 2
    assert report["cost"]["actual_calls"] == 139
    assert report["cost"]["actual_cost_cny"] == pytest.approx(0.076725)
    assert report["cost"]["provider_cache_savings_rate"] == pytest.approx(0.27660760277348223)
    assert set(report["slices"]) == {"platform", "length_bucket", "stratum"}
    assert report["eight_stage_audit"]["consistency"] == {
        "precision": 0.5,
        "recall": 1 / 3,
        "f1": 0.4,
    }
    assert (
        report["slices"]["length_bucket"]["long"]["extraction"]["hybrid"]["f1"]
        < report["slices"]["length_bucket"]["long"]["extraction"]["rule_only"]["f1"]
    )


def test_schema_v2_artifacts_remain_byte_exact():
    root = Path("evaluation/phase3/verifier-runs/full-v2")
    for name, expected in FROZEN_V2_HASHES.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
