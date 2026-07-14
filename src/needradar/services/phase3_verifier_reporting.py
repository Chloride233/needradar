from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from needradar.services.phase3_verifier_metrics import score_verifier_predictions


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _failure_kind(reason: str) -> str:
    if "InternalServerError" in reason:
        return "provider_error"
    if "quote does not match" in reason:
        return "quote_offset_mismatch"
    return "empty_or_malformed_json"


def build_failed_verifier_audit(
    run_dir: Path,
    input_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    records = _read_jsonl(run_dir / "predictions.jsonl")
    inputs = _read_jsonl(input_path)
    gold = _read_jsonl(gold_path)
    if run["input_sha256"] != _sha256(input_path) or run["gold_sha256"] != _sha256(gold_path):
        raise ValueError("verifier failed-run audit provenance does not match frozen benchmark")

    input_by_id = {record["id"]: record for record in inputs}
    stage_counts: dict[str, Counter] = {}
    for record in records:
        for stage, result in record["stage_statuses"].items():
            stage_counts.setdefault(stage, Counter())[result["status"]] += 1

    extraction_failure_kinds = Counter(
        _failure_kind(record["stage_statuses"]["claim_extraction"]["reason"])
        for record in records
        if record["stage_statuses"]["claim_extraction"]["status"] == "failed"
    )
    extraction_claims = {
        configuration: sum(len(record["extraction"][configuration]) for record in records)
        for configuration in ("rule_only", "llm_only", "hybrid")
    }
    stratum_claims = {
        stratum: {
            "records": sum(input_by_id[record["id"]]["stratum"] == stratum for record in records),
            "hybrid_claims": sum(
                len(record["extraction"]["hybrid"])
                for record in records
                if input_by_id[record["id"]]["stratum"] == stratum
            ),
        }
        for stratum in ("controlled", "naturalistic")
    }

    diagnostic_records = [
        record
        for record in records
        if record["extraction"]["hybrid"]
        and record["evidence"]["snippet_200"]
        and record["stage_statuses"]["consistency"]["status"] == "success"
        and record["score_variants"]["full_weighted"] is not None
    ]
    diagnostic_ids = {record["id"] for record in diagnostic_records}
    diagnostic_predictions = [
        {
            "id": record["id"],
            "claims": record["evidence"]["snippet_200"],
            "resolved_source_ids": record["resolved_source_ids"],
            "internal_contradiction": record["internal_contradiction"],
            "overall_score": record["score_variants"]["full_weighted"],
            "suggestions": record["suggestions"],
        }
        for record in diagnostic_records
    ]
    diagnostic_ranking = score_verifier_predictions(
        [record for record in inputs if record["id"] in diagnostic_ids],
        [record for record in gold if record["id"] in diagnostic_ids],
        diagnostic_predictions,
    )["ranking"]

    provider_attempts = sum(2 + (3 if record["extraction"]["hybrid"] else 0) for record in records)
    responses_with_usage = sum(len(record["usage"]) for record in records)
    planned_dag_calls = len(records) * 5
    naive_calls = len(records) * 20
    return {
        "accepted": False,
        "reason": "model-assisted claim extraction produced zero claims and required stages failed",
        "records": len(records),
        "stage_counts": {stage: dict(sorted(counts.items())) for stage, counts in sorted(stage_counts.items())},
        "extraction": {
            "failure_kinds": dict(sorted(extraction_failure_kinds.items())),
            "predicted_claims": extraction_claims,
            "valid_llm_records": sum(
                record["stage_statuses"]["claim_extraction"]["status"] == "success"
                and bool(record["extraction"]["llm_only"])
                for record in records
            ),
            "strata": stratum_claims,
        },
        "diagnostic_rule_fallback_ranking": diagnostic_ranking,
        "cost_accounting": {
            "provider_attempts": provider_attempts,
            "responses_with_usage": responses_with_usage,
            "planned_dag_calls": planned_dag_calls,
            "stage_calls_skipped_for_empty_claims": planned_dag_calls - provider_attempts,
            "naive_independent_calls": naive_calls,
            "structural_artifact_reuse_calls_saved": naive_calls - planned_dag_calls,
            "recorded_cost_cny_lower_bound": run["usage"]["actual_cost_cny"],
        },
        "artifact_sha256": {
            name: _sha256(run_dir / name) for name in ("predictions.jsonl", "metrics.json", "run.json")
        },
        "required_recovery": [
            "disable provider thinking for structured verifier calls",
            "derive quote offsets locally and cap hybrid claims at 12",
            "exclude failed dependencies from downstream scores and report valid denominators",
            "write a new schema-v2 run instead of resuming this directory",
        ],
    }


def render_failed_verifier_audit(report: dict[str, Any]) -> str:
    stages = report["stage_counts"]
    extraction = report["extraction"]
    cost = report["cost_accounting"]
    ranking = report["diagnostic_rule_fallback_ranking"]
    hashes = report["artifact_sha256"]
    lines = [
        "# Phase 3 verifier failed-run audit",
        "",
        "## Decision",
        "",
        "This run is rejected as component-ablation evidence. It is retained as reproducible failure evidence.",
        "",
        "## Stage coverage",
        "",
        "| Stage | Success | Failed |",
        "| --- | ---: | ---: |",
    ]
    for stage in ("claim_extraction", "fact_check", "consistency"):
        lines.append(f"| `{stage}` | {stages[stage].get('success', 0)} | {stages[stage].get('failed', 0)} |")
    lines.extend(
        [
            "",
            "## Extraction failure",
            "",
            f"- LLM-only claims: {extraction['predicted_claims']['llm_only']} across {report['records']} reports.",
            f"- Valid non-empty LLM records: {extraction['valid_llm_records']}.",
            f"- Failure kinds: `{json.dumps(extraction['failure_kinds'], sort_keys=True)}`.",
            (
                "- Naturalistic coverage: "
                f"{extraction['strata']['naturalistic']['hybrid_claims']} hybrid claims across "
                f"{extraction['strata']['naturalistic']['records']} reports."
            ),
            "",
            "## Diagnostic only",
            "",
            (
                f"The non-empty rule-fallback subset contains {ranking['records']} reports; "
                f"AUROC is {ranking['auroc']:.6f} and average precision is {ranking['average_precision']:.6f}. "
                "These values are not hybrid verifier results."
            ),
            "",
            "## Cost correction",
            "",
            f"- Provider attempts: {cost['provider_attempts']}.",
            f"- Responses with usage: {cost['responses_with_usage']}.",
            f"- Structural artifact reuse: {cost['structural_artifact_reuse_calls_saved']} calls.",
            f"- Calls skipped because claims were empty: {cost['stage_calls_skipped_for_empty_claims']}.",
            f"- Recorded provider cost lower bound: CNY {cost['recorded_cost_cny_lower_bound']:.6f}.",
            "",
            "## Frozen artifacts",
            "",
        ]
    )
    lines.extend(f"- `{name}`: `{value}`" for name, value in hashes.items())
    lines.extend(["", "## Recovery", ""])
    lines.extend(f"- {item}." for item in report["required_recovery"])
    return "\n".join(lines) + "\n"


def write_failed_verifier_audit(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_failed_verifier_audit(report), encoding="utf-8")


def _metric_subset(
    inputs: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    records: list[dict[str, Any]],
    evidence_configuration: str,
    score_configuration: str | None = None,
) -> dict[str, Any]:
    ids = {record["id"] for record in records}
    predictions = [
        {
            "id": record["id"],
            "claims": record["evidence"][evidence_configuration],
            "resolved_source_ids": ([] if evidence_configuration == "no_evidence" else record["resolved_source_ids"]),
            "internal_contradiction": record["internal_contradiction"],
            "overall_score": (
                record["score_variants"][score_configuration]
                if score_configuration
                else record["evidence_scores"][evidence_configuration]
            ),
            "suggestions": record["suggestions"] if evidence_configuration == "snippet_200" else [],
        }
        for record in records
    ]
    return score_verifier_predictions(
        [record for record in inputs if record["id"] in ids],
        [record for record in gold if record["id"] in ids],
        predictions,
    )


def build_verifier_report(run_dir: Path, input_path: Path, gold_path: Path) -> dict[str, Any]:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    records = _read_jsonl(run_dir / "predictions.jsonl")
    inputs = _read_jsonl(input_path)
    gold = _read_jsonl(gold_path)
    if run["schema_version"] != 2:
        raise ValueError("formal verifier report requires schema version 2")
    if run["input_sha256"] != _sha256(input_path) or run["gold_sha256"] != _sha256(gold_path):
        raise ValueError("formal verifier report provenance does not match frozen benchmark")

    input_by_id = {record["id"]: record for record in inputs}
    extraction_records = [
        record
        for record in records
        if all(
            status["status"] == "success"
            for status in record["stage_statuses"]["claim_extraction"]["configurations"].values()
        )
    ]
    evidence_records = [
        record
        for record in extraction_records
        if record["extraction"]["hybrid"]
        and all(
            status["status"] == "success"
            for status in record["stage_statuses"]["fact_check"]["configurations"].values()
        )
    ]
    score_records = [
        record
        for record in evidence_records
        if all(
            record["score_variants"][configuration] is not None
            for configuration in ("fact_only", "fact_consistency", "full_weighted")
        )
    ]

    extraction = {}
    extraction_ids = {record["id"] for record in extraction_records}
    for configuration in ("rule_only", "llm_only", "hybrid"):
        predictions = [
            {"id": record["id"], "claims": record["extraction"][configuration]} for record in extraction_records
        ]
        extraction[configuration] = score_verifier_predictions(
            [record for record in inputs if record["id"] in extraction_ids],
            [record for record in gold if record["id"] in extraction_ids],
            predictions,
        )["claim_extraction"]

    evidence = {
        configuration: _metric_subset(inputs, gold, evidence_records, configuration)
        for configuration in ("no_evidence", "titles_only", "snippet_200", "snippet_800")
    }
    score_composition = {
        configuration: _metric_subset(
            inputs,
            gold,
            score_records,
            "snippet_200",
            configuration,
        )["ranking"]
        for configuration in ("fact_only", "fact_consistency", "full_weighted")
    }

    slices = {}
    for field in ("platform", "length_bucket", "stratum"):
        slices[field] = {}
        for value in sorted({record[field] for record in inputs}):
            extraction_subset = [record for record in extraction_records if input_by_id[record["id"]][field] == value]
            extraction_subset_ids = {record["id"] for record in extraction_subset}
            extraction_metrics = {}
            for configuration in ("rule_only", "llm_only", "hybrid"):
                predictions = [
                    {"id": record["id"], "claims": record["extraction"][configuration]} for record in extraction_subset
                ]
                extraction_metrics[configuration] = score_verifier_predictions(
                    [record for record in inputs if record["id"] in extraction_subset_ids],
                    [record for record in gold if record["id"] in extraction_subset_ids],
                    predictions,
                )["claim_extraction"]
            evidence_subset = [record for record in evidence_records if input_by_id[record["id"]][field] == value]
            evidence_metrics = _metric_subset(inputs, gold, evidence_subset, "snippet_800")
            slices[field][value] = {
                "extraction_records": len(extraction_subset),
                "extraction": extraction_metrics,
                "evidence_records": len(evidence_subset),
                "flagged": evidence_metrics["verdicts"]["flagged"],
                "ranking": evidence_metrics["ranking"],
            }

    structural_predictions = [
        {
            "id": record["id"],
            "claims": [],
            "resolved_source_ids": record["resolved_source_ids"],
            "internal_contradiction": record["internal_contradiction"],
            "overall_score": None,
            "suggestions": [],
        }
        for record in records
    ]
    structural_metrics = score_verifier_predictions(inputs, gold, structural_predictions)

    source_scores = [record["source_reliability_score"] for record in records]
    failure_cases = [
        {
            "id": record["id"],
            "platform": input_by_id[record["id"]]["platform"],
            "length_bucket": input_by_id[record["id"]]["length_bucket"],
            "stratum": input_by_id[record["id"]]["stratum"],
            "stage_statuses": record["stage_statuses"],
            "retry_count": record.get("retry_count", 0),
        }
        for record in records
        if _has_failed_record(record)
    ]
    usage = run["usage"]
    return {
        "status": "complete_with_stage_failures",
        "records": len(records),
        "paired_denominators": {
            "extraction": len(extraction_records),
            "evidence": len(evidence_records),
            "score_composition": len(score_records),
        },
        "eligibility_funnel": {
            "total": len(records),
            "extraction_success": len(extraction_records),
            "nonempty_hybrid": sum(bool(record["extraction"]["hybrid"]) for record in extraction_records),
            "all_evidence_success": len(evidence_records),
        },
        "stage_summary": run["stage_summary"],
        "component_ablation": {
            "extraction": extraction,
            "evidence": evidence,
            "score_composition": score_composition,
            "deltas": {
                "hybrid_f1_vs_rule_only": extraction["hybrid"]["f1"] - extraction["rule_only"]["f1"],
                "snippet_800_macro_f1_vs_no_evidence": (
                    evidence["snippet_800"]["verdicts"]["macro_f1"] - evidence["no_evidence"]["verdicts"]["macro_f1"]
                ),
                "full_weighted_auroc_vs_fact_only": (
                    score_composition["full_weighted"]["auroc"] - score_composition["fact_only"]["auroc"]
                ),
            },
        },
        "eight_stage_audit": {
            "input_loading": run["stage_summary"]["input_loading"],
            "claim_extraction": extraction["hybrid"],
            "source_resolution": structural_metrics["source_resolution"],
            "fact_check": evidence["snippet_200"]["verdicts"],
            "consistency": structural_metrics["consistency"],
            "source_prior": {
                "minimum": min(source_scores),
                "mean": sum(source_scores) / len(source_scores),
                "maximum": max(source_scores),
                "auroc_delta_vs_fact_consistency": (
                    score_composition["full_weighted"]["auroc"] - score_composition["fact_consistency"]["auroc"]
                ),
            },
            "aggregation": score_composition["full_weighted"],
            "suggestions": evidence["snippet_200"]["suggestions"],
        },
        "slices": slices,
        "failure_cases": failure_cases,
        "cost": {
            **usage,
            "provider_cache_savings_rate": (
                usage["provider_cache_savings_cny"] / usage["cost_without_provider_cache_cny"]
                if usage["cost_without_provider_cache_cny"]
                else 0.0
            ),
        },
        "provenance": {
            "schema_version": run["schema_version"],
            "input_sha256": run["input_sha256"],
            "gold_sha256": run["gold_sha256"],
            "manifest_sha256": run["manifest_sha256"],
            "model_id": run["model_id"],
            "provider_params": run["provider_params"],
            "artifact_sha256": {
                name: _sha256(run_dir / name) for name in ("predictions.jsonl", "metrics.json", "run.json")
            },
        },
        "limitations": [
            "Component deltas use paired available records, not all 30 reports.",
            "Five successful extractions returned no hybrid claims; one additional extraction failed.",
            "One extraction response and one snippet-200 fact-check response failed after a retry.",
            "The evidence intersection retains 7/12 naturalistic and 6/10 long reports, so slices are descriptive only.",
            "Controlled corruptions and agent-adjudicated naturalistic gold are proxy evidence, not human-user validation.",
            "Platform remains confounded with source content type, and source-reliability weights are heuristic priors.",
        ],
    }


def _has_failed_record(record: dict[str, Any]) -> bool:
    return any(result["status"] == "failed" for result in record["stage_statuses"].values())


def render_verifier_markdown(report: dict[str, Any]) -> str:
    extraction = report["component_ablation"]["extraction"]
    evidence = report["component_ablation"]["evidence"]
    scores = report["component_ablation"]["score_composition"]
    cost = report["cost"]
    lines = [
        "# Phase 3 verifier component ablation and eight-stage audit",
        "",
        "## Executive summary",
        "",
        f"- Run status: `{report['status']}`; all {report['records']} records completed.",
        (
            f"- Paired denominators are {report['paired_denominators']['extraction']} for extraction, "
            f"{report['paired_denominators']['evidence']} for evidence, and "
            f"{report['paired_denominators']['score_composition']} for score composition."
        ),
        (
            f"- Hybrid extraction F1 is {extraction['hybrid']['f1']:.3f}, compared with "
            f"{extraction['rule_only']['f1']:.3f} for rule-only."
        ),
        (
            f"- 800-character evidence macro-F1 is {evidence['snippet_800']['verdicts']['macro_f1']:.3f}; "
            f"200-character evidence macro-F1 is {evidence['snippet_200']['verdicts']['macro_f1']:.3f}."
        ),
        (
            f"- Full-weighted ranking AUROC is {scores['full_weighted']['auroc']:.3f}; "
            f"fact-only AUROC is {scores['fact_only']['auroc']:.3f}."
        ),
        (
            f"- Actual cost is CNY {cost['actual_cost_cny']:.6f}; prefix caching saved "
            f"{cost['provider_cache_savings_rate'] * 100:.2f}% and structural reuse saved "
            f"{cost['artifact_reuse_calls_saved']} calls."
        ),
        "",
        "## Component ablation",
        "",
        "### Claim extraction",
        "",
        "| Configuration | Precision | Recall | F1 | Tail recall |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name in ("rule_only", "llm_only", "hybrid"):
        metric = extraction[name]
        lines.append(
            f"| `{name}` | {metric['precision']:.3f} | {metric['recall']:.3f} | "
            f"{metric['f1']:.3f} | {metric['tail_recall']:.3f} |"
        )
    lines.extend(
        [
            "",
            "### Evidence context",
            "",
            "| Configuration | Macro-F1 | Hallucination precision | Hallucination recall | Flagged F1 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in ("no_evidence", "titles_only", "snippet_200", "snippet_800"):
        metric = evidence[name]["verdicts"]
        lines.append(
            f"| `{name}` | {metric['macro_f1']:.3f} | {metric['hallucination']['precision']:.3f} | "
            f"{metric['hallucination']['recall']:.3f} | {metric['flagged']['f1']:.3f} |"
        )
    lines.extend(
        [
            "",
            "### Score composition",
            "",
            "| Configuration | AUROC | Average precision |",
            "| --- | ---: | ---: |",
        ]
    )
    for name in ("fact_only", "fact_consistency", "full_weighted"):
        metric = scores[name]
        lines.append(f"| `{name}` | {metric['auroc']:.3f} | {metric['average_precision']:.3f} |")
    lines.extend(["", "## Stage failures", ""])
    for case in report["failure_cases"]:
        failed = [stage for stage, result in case["stage_statuses"].items() if result["status"] == "failed"]
        lines.append(
            f"- `{case['id']}` ({case['platform']}, {case['stratum']}, {case['length_bucket']}): "
            f"{', '.join(failed)} failed after {case['retry_count']} retry."
        )
    audit = report["eight_stage_audit"]
    lines.extend(
        [
            "",
            "## Eight-stage audit",
            "",
            f"1. Input loading: {audit['input_loading'].get('success', 0)}/{report['records']} succeeded.",
            f"2. Claim extraction: hybrid F1 {audit['claim_extraction']['f1']:.3f} on the paired extraction set.",
            (
                f"3. Source resolution: {audit['source_resolution']['resolved_sources']}/"
                f"{audit['source_resolution']['expected_sources']} references resolved."
            ),
            (
                f"4. Fact checking: macro-F1 {audit['fact_check']['macro_f1']:.3f}; "
                f"flagged F1 {audit['fact_check']['flagged']['f1']:.3f}."
            ),
            (
                f"5. Consistency: precision {audit['consistency']['precision']:.3f}, "
                f"recall {audit['consistency']['recall']:.3f}, F1 {audit['consistency']['f1']:.3f} on all 30 reports."
            ),
            (
                f"6. Source prior: mean {audit['source_prior']['mean']:.3f}; AUROC delta versus "
                f"fact+consistency {audit['source_prior']['auroc_delta_vs_fact_consistency']:+.3f}."
            ),
            (
                f"7. Aggregation: AUROC {audit['aggregation']['auroc']:.3f}; "
                f"average precision {audit['aggregation']['average_precision']:.3f}."
            ),
            (
                f"8. Suggestions: precision {audit['suggestions']['precision']:.3f}, "
                f"recall {audit['suggestions']['recall']:.3f}, "
                f"unsupported rate {audit['suggestions']['unsupported_rate']:.3f}."
            ),
            "",
            "## Cost and reuse",
            "",
            f"- Provider attempts: {cost['actual_calls']} ({cost['responses_with_usage']} with usage).",
            f"- Final-stage calls: {cost['final_stage_calls']}; superseded retry history: {cost['retry_attempts']} calls.",
            f"- Tokens: {cost['input_tokens']:,} input, {cost['output_tokens']:,} output, {cost['cached_tokens']:,} cached.",
            f"- Actual cost: CNY {cost['actual_cost_cny']:.6f}; no-cache counterfactual: CNY {cost['cost_without_provider_cache_cny']:.6f}.",
            f"- Provider-cache savings: CNY {cost['provider_cache_savings_cny']:.6f} ({cost['provider_cache_savings_rate'] * 100:.2f}%).",
            f"- Structural artifact reuse: {cost['artifact_reuse_calls_saved']} calls saved versus {cost['naive_independent_calls']} naive calls.",
        ]
    )
    lines.extend(["", "## Slices", ""])
    for field, values in report["slices"].items():
        lines.extend(
            [
                f"### {field}",
                "",
                "| Value | Extraction n | Rule F1 | Hybrid F1 | Evidence n | 800-char flagged F1 | AUROC | AP |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for value, metric in values.items():
            ranking = metric["ranking"]
            auroc = "n/a" if ranking["auroc"] is None else f"{ranking['auroc']:.3f}"
            average_precision = "n/a" if ranking["average_precision"] is None else f"{ranking['average_precision']:.3f}"
            lines.append(
                f"| `{value}` | {metric['extraction_records']} | "
                f"{metric['extraction']['rule_only']['f1']:.3f} | "
                f"{metric['extraction']['hybrid']['f1']:.3f} | {metric['evidence_records']} | "
                f"{metric['flagged']['f1']:.3f} | {auroc} | {average_precision} |"
            )
        lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    return "\n".join(lines) + "\n"


def write_verifier_report(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_verifier_markdown(report), encoding="utf-8")
