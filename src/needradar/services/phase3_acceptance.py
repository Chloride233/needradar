from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_phase3_acceptance(rag_report_path: Path, verifier_report_path: Path) -> dict[str, Any]:
    rag = json.loads(rag_report_path.read_text(encoding="utf-8"))
    verifier = json.loads(verifier_report_path.read_text(encoding="utf-8"))
    configurations = rag.get("configurations", {})
    required_configurations = {"no_rag", "rag", "rag_hitl"}
    rag_complete = rag.get("records") == 100 and set(configurations) == required_configurations
    metric_fields = {
        "requirement_presence_accuracy",
        "duplicate_rate",
        "proxy_edit_rate",
        "total_tokens",
        "cost_cny",
    }
    metrics_complete = rag_complete and all(
        metric_fields <= set(configurations[name]) for name in required_configurations
    )
    verifier_complete = (
        verifier.get("records") == 30
        and verifier.get("status") == "complete_with_stage_failures"
        and verifier.get("paired_denominators") == {"extraction": 29, "evidence": 23, "score_composition": 23}
        and set(verifier.get("component_ablation", {})) >= {"extraction", "evidence", "score_composition", "deltas"}
        and len(verifier.get("eight_stage_audit", {})) == 8
    )
    failure_analysis_complete = (
        bool(rag.get("rag_cases", {}).get("largest_regressions"))
        and len(verifier.get("failure_cases", [])) == 2
        and bool(rag.get("limitations"))
        and bool(verifier.get("limitations"))
    )
    reproducible = (
        bool(rag.get("input_hashes"))
        and bool(verifier.get("provenance", {}).get("artifact_sha256"))
        and verifier.get("provenance", {}).get("schema_version") == 2
    )
    criteria = [
        {
            "id": "three_configurations",
            "title": "Compare no RAG, RAG, and RAG plus HITL",
            "passed": rag_complete,
            "evidence": "evaluation/phase3/full-report.md",
        },
        {
            "id": "quality_cost_metrics",
            "title": "Measure accuracy, duplication, edit rate, tokens, and cost",
            "passed": metrics_complete,
            "evidence": "evaluation/phase3/full-report.json",
        },
        {
            "id": "verifier_ablation",
            "title": "Ablate verifier components and audit all eight stages",
            "passed": verifier_complete,
            "evidence": "evaluation/phase3/verifier-runs/full-v2/report.md",
            "interpretation": (
                "Interchangeable components use paired ablations; structural stages use stage-specific audit metrics. "
                "Literal cumulative step prefixes are not treated as causal ablations."
            ),
        },
        {
            "id": "negative_cases",
            "title": "Analyze limited and negative gains",
            "passed": failure_analysis_complete,
            "evidence": "evaluation/phase3/full-report.md and verifier-runs/full-v2/report.md",
        },
        {
            "id": "reproducibility",
            "title": "Publish reproducible configuration and reports",
            "passed": reproducible,
            "evidence": "evaluation/phase3/README.md and artifact regression tests",
        },
    ]
    return {
        "phase": 3,
        "issue": "https://github.com/Chloride233/needradar/issues/4",
        "status": "passed" if all(item["passed"] for item in criteria) else "failed",
        "criteria": criteria,
        "rag_hitl": {
            "records_per_configuration": rag.get("records"),
            "no_rag_requirement_accuracy": configurations.get("no_rag", {}).get("requirement_presence_accuracy"),
            "rag_requirement_accuracy": configurations.get("rag", {}).get("requirement_presence_accuracy"),
            "rag_cost_relative_change": rag.get("rag_vs_no_rag", {}).get("cost_cny", {}).get("relative_change"),
            "hitl_record_edit_rate": rag.get("hitl", {}).get("record_edit_rate"),
            "hitl_edited_fields": rag.get("hitl", {}).get("edited_fields"),
            "cache_savings_rate": rag.get("cache", {}).get("savings_rate"),
        },
        "verifier": {
            "records": verifier.get("records"),
            "paired_denominators": verifier.get("paired_denominators"),
            "hybrid_extraction_f1": verifier.get("component_ablation", {})
            .get("extraction", {})
            .get("hybrid", {})
            .get("f1"),
            "snippet_800_macro_f1": verifier.get("component_ablation", {})
            .get("evidence", {})
            .get("snippet_800", {})
            .get("verdicts", {})
            .get("macro_f1"),
            "fact_only_auroc": verifier.get("component_ablation", {})
            .get("score_composition", {})
            .get("fact_only", {})
            .get("auroc"),
            "full_weighted_auroc": verifier.get("component_ablation", {})
            .get("score_composition", {})
            .get("full_weighted", {})
            .get("auroc"),
            "actual_cost_cny": verifier.get("cost", {}).get("actual_cost_cny"),
            "provider_cache_savings_rate": verifier.get("cost", {}).get("provider_cache_savings_rate"),
            "stage_failures": len(verifier.get("failure_cases", [])),
        },
        "conclusions": [
            "RAG did not improve requirement-presence accuracy and increased cost and duplication.",
            "Simulated HITL reached proxy-perfect post-review output only by editing 97% of records; it is not model quality.",
            "Hybrid claim extraction improved aggregate F1, but regressed on long reports and tail recall.",
            "Longer evidence improved verdict classification, while report-level ranking remained weak.",
            "Consistency and source-prior weighting did not improve AUROC; full weighting reduced it.",
        ],
        "phase4_handoff": [
            "Measure real reviewer time and edit burden instead of simulated HITL only.",
            "Evaluate long-report extraction and structured-output failures before production automation.",
            "Keep fact-only scoring as the evidence-backed baseline until source priors show a gain.",
        ],
        "source_sha256": {
            str(rag_report_path): _sha256(rag_report_path),
            str(verifier_report_path): _sha256(verifier_report_path),
        },
    }


def render_phase3_acceptance(report: dict[str, Any]) -> str:
    rag = report["rag_hitl"]
    verifier = report["verifier"]
    lines = [
        "# Phase 3 acceptance report",
        "",
        f"Status: **{report['status'].upper()}**",
        "",
        "## Issue #4 checklist",
        "",
    ]
    for criterion in report["criteria"]:
        mark = "x" if criterion["passed"] else " "
        lines.append(f"- [{mark}] {criterion['title']} — `{criterion['evidence']}`")
    lines.extend(
        [
            "",
            "## Evidence summary",
            "",
            (
                f"- RAG/HITL: {rag['records_per_configuration']} records per configuration; requirement accuracy "
                f"{rag['no_rag_requirement_accuracy']:.2%} without RAG and {rag['rag_requirement_accuracy']:.2%} "
                f"with RAG; cost change {rag['rag_cost_relative_change']:+.2%}."
            ),
            (
                f"- Simulated HITL: {rag['hitl_record_edit_rate']:.2%} record edit rate and "
                f"{rag['hitl_edited_fields']} edited fields."
            ),
            (
                f"- Verifier: paired extraction/evidence/score denominators "
                f"{verifier['paired_denominators']['extraction']}/"
                f"{verifier['paired_denominators']['evidence']}/"
                f"{verifier['paired_denominators']['score_composition']}; hybrid extraction F1 "
                f"{verifier['hybrid_extraction_f1']:.3f}."
            ),
            (
                f"- Ranking: fact-only AUROC {verifier['fact_only_auroc']:.3f}; full-weighted AUROC "
                f"{verifier['full_weighted_auroc']:.3f}."
            ),
            (
                f"- Verifier cost: CNY {verifier['actual_cost_cny']:.6f}; provider cache saved "
                f"{verifier['provider_cache_savings_rate']:.2%}."
            ),
            "",
            "## Conclusions",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["conclusions"])
    lines.extend(["", "## Phase 4 handoff", ""])
    lines.extend(f"- {item}" for item in report["phase4_handoff"])
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            "PYTHONPATH=src .venv/bin/python scripts/report_phase3_acceptance.py",
            "PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_acceptance.py -q",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def write_phase3_acceptance(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_phase3_acceptance(report), encoding="utf-8")
