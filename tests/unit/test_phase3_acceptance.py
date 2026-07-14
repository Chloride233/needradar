from __future__ import annotations

import json
from pathlib import Path

from needradar.services.phase3_acceptance import build_phase3_acceptance, render_phase3_acceptance


def test_phase3_acceptance_maps_all_issue_criteria_to_frozen_evidence():
    report = build_phase3_acceptance(
        Path("evaluation/phase3/full-report.json"),
        Path("evaluation/phase3/verifier-runs/full-v2/report.json"),
    )

    assert report["status"] == "passed"
    assert len(report["criteria"]) == 5
    assert all(criterion["passed"] for criterion in report["criteria"])
    assert report["rag_hitl"]["no_rag_requirement_accuracy"] == 0.49
    assert report["rag_hitl"]["rag_requirement_accuracy"] == 0.49
    assert report["rag_hitl"]["hitl_record_edit_rate"] == 0.97
    assert report["verifier"]["paired_denominators"] == {
        "extraction": 29,
        "evidence": 23,
        "score_composition": 23,
    }
    assert report["verifier"]["full_weighted_auroc"] < report["verifier"]["fact_only_auroc"]
    assert report["verifier"]["stage_failures"] == 2


def test_checked_in_phase3_acceptance_matches_rebuilt_report():
    rebuilt = build_phase3_acceptance(
        Path("evaluation/phase3/full-report.json"),
        Path("evaluation/phase3/verifier-runs/full-v2/report.json"),
    )
    checked_in = json.loads(Path("evaluation/phase3/acceptance.json").read_text(encoding="utf-8"))

    assert checked_in == rebuilt
    assert Path("evaluation/phase3/acceptance.md").read_text(encoding="utf-8") == render_phase3_acceptance(rebuilt)
